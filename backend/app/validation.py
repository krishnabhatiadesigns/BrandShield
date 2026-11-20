"""Validation and merging of findings.

This module is the trust boundary. Anything the LLM returns is treated as a
*proposal* and must survive these checks before it reaches the database:

  * the cited passage must exist, be approved, be in force, and belong to the
    same workspace;
  * the affected text must actually appear in the draft (offsets are recomputed);
  * evidence_status must be consistent with the citation (no citation means the
    claim can only be "needs_verification" or "unsupported");
  * unsupported claims are never labelled "false"/"contradicted" without a source;
  * suggestions must be minimal edits that do not introduce new numbers or
    unapproved claims.
"""
from __future__ import annotations

import re
from typing import Any

from .checks.base import SEVERITY_ORDER, FindingDraft
from .text import find_all

VALID_CATEGORIES = {
    "tone",
    "messaging",
    "claim",
    "terminology",
    "fact",
    "disclaimer",
    "visual",
    "product_name",
    "logo",
    "typography",
    "other",
}
VALID_SEVERITIES = {"low", "medium", "high"}
VALID_EVIDENCE = {"supported", "contradicted", "unsupported", "needs_verification"}

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _clamp_confidence(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, f))


def _locate(body: str, affected_text: str) -> tuple[int, int] | None:
    """Find the affected text in the draft. Exact match first, then case-insensitive."""
    if not affected_text:
        return None
    idx = body.find(affected_text)
    if idx != -1:
        return idx, idx + len(affected_text)
    hits = find_all(body, affected_text)
    if hits:
        return hits[0]
    # Tolerate whitespace differences introduced by the model.
    squashed = re.sub(r"\s+", " ", affected_text).strip()
    if squashed and squashed != affected_text:
        idx = body.find(squashed)
        if idx != -1:
            return idx, idx + len(squashed)
    return None


def validate_llm_findings(
    body: str,
    raw_findings: list[dict[str, Any]],
    allowed_passages: dict[int, dict[str, Any]],
    approved_terms: list[str],
    approved_numbers: set[str],
    allowed_rules: dict[int, dict[str, Any]] | None = None,
) -> tuple[list[FindingDraft], list[str]]:
    """Return (accepted findings, rejection notes)."""
    accepted: list[FindingDraft] = []
    notes: list[str] = []

    for raw in raw_findings:
        if not isinstance(raw, dict):
            notes.append("Discarded a malformed finding (not an object).")
            continue

        affected = str(raw.get("affected_text") or "").strip()
        located = _locate(body, affected)
        if not located:
            notes.append(f"Discarded finding: affected text not found in draft ({affected[:40]!r}).")
            continue
        span_start, span_end = located
        affected = body[span_start:span_end]

        category = str(raw.get("category") or "messaging").lower()
        if category not in VALID_CATEGORIES:
            category = "messaging"

        severity = str(raw.get("severity") or "medium").lower()
        if severity not in VALID_SEVERITIES:
            severity = "medium"

        evidence = str(raw.get("evidence_status") or "needs_verification").lower()
        if evidence not in VALID_EVIDENCE:
            evidence = "needs_verification"

        # --- citation validation -------------------------------------------
        source_id = raw.get("source_passage_id")
        source_passage_id: int | None = None
        if source_id is not None:
            try:
                candidate = int(source_id)
            except (TypeError, ValueError):
                candidate = -1
            if candidate in allowed_passages:
                source_passage_id = candidate
            else:
                notes.append(
                    f"Downgraded a finding: cited passage {source_id} is not an approved "
                    "passage in this workspace."
                )
                # A citation we cannot verify cannot support a claim.
                if evidence in {"supported", "contradicted"}:
                    evidence = "needs_verification"

        source_rule_id: int | None = None
        source_rule: dict[str, Any] | None = None
        raw_rule_id = raw.get("source_rule_id")
        if raw_rule_id is not None:
            try:
                candidate_rule_id = int(raw_rule_id)
            except (TypeError, ValueError):
                candidate_rule_id = -1
            source_rule = (allowed_rules or {}).get(candidate_rule_id)
            if source_rule:
                source_rule_id = candidate_rule_id
                linked_passage_id = source_rule.get("source_passage_id")
                if (
                    source_passage_id is None
                    and linked_passage_id is not None
                    and int(linked_passage_id) in allowed_passages
                ):
                    source_passage_id = int(linked_passage_id)
            else:
                notes.append(
                    f"Downgraded a finding: cited brand rule {raw_rule_id} is not active "
                    "for this workspace and content type."
                )

        if source_rule:
            severity = str(source_rule["severity"])
            if not source_rule["mandatory"] and evidence == "supported":
                evidence = "needs_verification"
                notes.append(
                    "Marked an advisory-rule finding for human verification; advisory "
                    "guidance cannot establish a confirmed violation."
                )

        # --- evidence consistency ------------------------------------------
        rule_supports_policy = evidence == "supported" and source_rule_id is not None
        if evidence in {"supported", "contradicted"} and source_passage_id is None \
                and not rule_supports_policy:
            notes.append(
                "Downgraded a finding to needs_verification: it claimed support but "
                "cited no valid approved passage."
            )
            evidence = "needs_verification"

        # --- suggestion safety ---------------------------------------------
        suggestion = raw.get("suggestion")
        if suggestion is not None:
            suggestion = str(suggestion).strip() or None
        if suggestion:
            new_numbers = set(_NUMBER_RE.findall(suggestion)) - set(_NUMBER_RE.findall(affected))
            unapproved = {n for n in new_numbers if n not in approved_numbers}
            if unapproved:
                notes.append(
                    "Removed a suggestion that introduced unverified figures: "
                    + ", ".join(sorted(unapproved))
                )
                suggestion = None
            elif len(suggestion) > max(240, len(affected) * 6):
                notes.append("Removed an over-long suggestion that rewrote too much text.")
                suggestion = None

        explanation = str(raw.get("explanation") or "").strip()
        if not explanation:
            notes.append("Discarded finding with no explanation.")
            continue

        accepted.append(
            FindingDraft(
                category=category,
                severity=severity,  # type: ignore[arg-type]
                affected_text=affected,
                rule=str(raw.get("rule") or "Brand guideline")[:200],
                explanation=explanation[:1200],
                evidence_status=evidence,  # type: ignore[arg-type]
                suggestion=suggestion,
                source_passage_id=source_passage_id,
                source_rule_id=source_rule_id,
                source_rule_version=int(source_rule["current_version"]) if source_rule else None,
                source_rule_title=str(source_rule["title"]) if source_rule else None,
                source_rule_text=str(source_rule["description"]) if source_rule else None,
                confidence=_clamp_confidence(raw.get("confidence", 0.6)),
                span_start=span_start,
                span_end=span_end,
                detector="llm",
            )
        )
    return accepted, notes


def merge_findings(findings: list[FindingDraft]) -> list[FindingDraft]:
    """De-duplicate overlapping findings and sort by severity then position."""
    # Prefer deterministic findings when two findings cover the same span.
    ordered = sorted(
        findings,
        key=lambda f: (
            f.span_start if f.span_start is not None else 10**9,
            SEVERITY_ORDER.get(f.severity, 3),
            0 if f.detector == "deterministic" else 1,
        ),
    )
    kept: list[FindingDraft] = []
    for candidate in ordered:
        duplicate = False
        for existing in kept:
            # Exact same span: one finding, whichever is more severe. This stops
            # e.g. the prohibited term "guaranteed" and the banned phrase
            # "guaranteed to" from both appearing for the same words.
            if (
                existing.span_start is not None
                and existing.span_start == candidate.span_start
                and existing.span_end == candidate.span_end
            ):
                duplicate = True
                break
            if existing.category != candidate.category:
                continue
            if existing.rule == candidate.rule and existing.span_start == candidate.span_start:
                duplicate = True
                break
            # Overlapping spans with the same category: keep the higher severity.
            # Require a *substantial* overlap so a wide aggregate finding (for
            # example "2 exclamation marks") cannot swallow a precise one.
            if (
                existing.span_start is not None
                and candidate.span_start is not None
                and existing.span_end is not None
                and candidate.span_end is not None
            ):
                overlap = min(existing.span_end, candidate.span_end) - max(
                    existing.span_start, candidate.span_start
                )
                if overlap > 0:
                    smaller = min(
                        existing.span_end - existing.span_start,
                        candidate.span_end - candidate.span_start,
                    )
                    if smaller > 0 and overlap / smaller >= 0.6:
                        duplicate = True
                        break
        if not duplicate:
            kept.append(candidate)

    kept.sort(
        key=lambda f: (
            SEVERITY_ORDER.get(f.severity, 3),
            f.span_start if f.span_start is not None else 10**9,
        )
    )
    return kept
