"""The hybrid review pipeline.

Order of operations (matches the spec):
  1. extract text and split into spans
  2. deterministic checks (always run, no network)
  3. BM25 retrieval of approved in-force passages, workspace-scoped
  4. Groq analysis in JSON mode (optional, degrades gracefully)
  5. validation of every LLM finding against real approved sources
  6. merge, de-duplicate, sort by severity
"""
from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass, field
from datetime import date

from .checks.base import FindingDraft
from .checks.deterministic import (
    BrandContext,
    claim_like_sentences,
    run_deterministic_checks,
)
from .db import Database
from .llm import analyse
from .retrieval import WorkspaceRetriever, load_workspace_passages
from .validation import merge_findings, validate_llm_findings

log = logging.getLogger("brandshield.pipeline")

DISCLAIMERS = {
    "ad": "T&Cs apply.",
    "email": (
        "You are receiving this email because you subscribed to Northwind Foods updates. "
        "Unsubscribe at any time."
    ),
    "social": None,
    "document": None,
}


@dataclass
class ReviewOutcome:
    findings: list[FindingDraft]
    llm_status: str  # "ok" | "disabled" | "error" | "timeout"
    llm_message: str
    deterministic_count: int
    llm_count: int
    duration_ms: int
    validation_notes: list[str] = field(default_factory=list)


def build_brand_context(db: Database, workspace_id: int, content_type: str) -> BrandContext:
    terms = db.query(
        "SELECT id, term, kind, replacement, notes FROM terms WHERE workspace_id = ?",
        (workspace_id,),
    )
    facts = db.query(
        "SELECT id, fact_key, value, unit, source_passage_id FROM facts WHERE workspace_id = ?",
        (workspace_id,),
    )
    palette = db.query(
        "SELECT id, name, hex, role FROM palette_colors WHERE workspace_id = ?",
        (workspace_id,),
    )
    assets = db.query(
        "SELECT id, kind, name, notes FROM brand_assets WHERE workspace_id = ?",
        (workspace_id,),
    )
    policy_versions = db.query(
        "SELECT rule_id, version_no, snapshot, effective_date"
        " FROM guideline_rule_versions WHERE workspace_id = ? AND effective_date <= ?",
        (workspace_id, date.today().isoformat()),
    )
    effective_versions: dict[int, dict] = {}
    for version in policy_versions:
        rule_id = int(version["rule_id"])
        current = effective_versions.get(rule_id)
        if current and (
            current["effective_date"], int(current["version_no"])
        ) >= (version["effective_date"], int(version["version_no"])):
            continue
        effective_versions[rule_id] = version

    rules = []
    for rule_id, version in effective_versions.items():
        snapshot = json.loads(version["snapshot"])
        types = str(snapshot["content_types"]).split(",")
        if not snapshot["enabled"] or content_type not in types:
            continue
        rules.append(
            {
                **snapshot,
                "id": rule_id,
                "current_version": int(version["version_no"]),
                "content_types": types,
                "mandatory": bool(snapshot["mandatory"]),
                "effective_date": version["effective_date"],
            }
        )
    passages = load_workspace_passages(db, workspace_id)
    return BrandContext(
        workspace_id=workspace_id,
        prohibited_terms=[t for t in terms if t["kind"] == "prohibited"],
        approved_terms=[t for t in terms if t["kind"] == "approved"],
        facts=facts,
        passages=passages,
        palette=palette,
        assets=assets,
        rules=rules,
        required_disclaimer=DISCLAIMERS.get(content_type),
        content_type=content_type,
    )


def run_review(
    db: Database,
    workspace_id: int,
    body: str,
    content_type: str,
    use_llm: bool = True,
) -> ReviewOutcome:
    started = time.perf_counter()
    ctx = build_brand_context(db, workspace_id, content_type)

    # --- 2. deterministic ---------------------------------------------------
    deterministic = run_deterministic_checks(body, ctx)

    # --- 3. retrieval -------------------------------------------------------
    retriever = WorkspaceRetriever(ctx.passages)
    claims = claim_like_sentences(body)
    retrieved = retriever.retrieve_for_claims(claims, k=4)

    # --- 4. LLM -------------------------------------------------------------
    llm_findings: list[FindingDraft] = []
    notes: list[str] = []
    llm_status = "disabled"
    llm_message = "AI analysis is not configured on this server. Deterministic brand checks ran normally."

    if use_llm:
        # Give the model the union of passages retrieved for any claim, plus the
        # passages already cited by deterministic findings.
        passage_ids: list[int] = []
        for hits in retrieved.values():
            for hit in hits:
                if hit.id not in passage_ids:
                    passage_ids.append(hit.id)
        for f in deterministic:
            if f.source_passage_id and f.source_passage_id not in passage_ids:
                passage_ids.append(f.source_passage_id)
        for rule in ctx.rules:
            passage_id = rule.get("source_passage_id")
            if passage_id and int(passage_id) not in passage_ids:
                passage_ids.append(int(passage_id))
        llm_passages = [p for p in ctx.passages if int(p["id"]) in passage_ids]
        company_context = db.query_one(
            "SELECT company_context FROM workspace_context WHERE workspace_id = ?",
            (workspace_id,),
        )

        existing_summary = [f"{f.rule}: {f.affected_text}" for f in deterministic]
        result = analyse(
            body,
            content_type,
            llm_passages,
            existing_summary,
            company_context["company_context"] if company_context else "",
            ctx.rules,
        )

        if result.ok:
            llm_status = "ok"
            llm_message = result.message
            allowed = {int(p["id"]): p for p in ctx.passages}
            approved_numbers = {str(f["value"]) for f in ctx.facts}
            approved_numbers |= {n.replace(",", "") for n in approved_numbers}
            llm_findings, notes = validate_llm_findings(
                body,
                result.findings,
                allowed,
                [t["term"] for t in ctx.approved_terms],
                approved_numbers,
                {int(rule["id"]): rule for rule in ctx.rules},
            )
        else:
            llm_status = "timeout" if "timed out" in result.message.lower() else "error"
            llm_message = result.message

    # --- 6. merge -----------------------------------------------------------
    merged = merge_findings(deterministic + llm_findings)
    duration = int((time.perf_counter() - started) * 1000)

    return ReviewOutcome(
        findings=merged,
        llm_status=llm_status,
        llm_message=llm_message,
        deterministic_count=len(deterministic),
        llm_count=len(llm_findings),
        duration_ms=duration,
        validation_notes=notes,
    )
