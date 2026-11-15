"""Groq LLM client (server-side only) with strict JSON output handling.

The client never raises into the request path: it returns an ``LLMResult`` that
records whether the call succeeded, so the pipeline can degrade to deterministic
findings and the UI can explain what happened.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger("brandshield.llm")

SYSTEM_PROMPT = """You are a brand governance reviewer.
You review a draft against the organisation's approved brand passages and company context.

Rules you must follow:
1. Use the DRAFT, APPROVED PASSAGES, and COMPANY CONTEXT to identify relevant issues.
   Factual support or contradiction still requires an approved passage.
2. Every finding must quote the exact affected text from the draft, character for character.
3. If a claim is not supported by an approved passage, set evidence_status to
   "needs_verification". Never call a claim false unless an approved passage
   directly contradicts it, in which case use "contradicted".
4. source_passage_id must be the id of an approved passage you were given, or null.
   Never invent an id.
5. Suggestions must change only the problematic phrase, keep the author's intent,
   use approved terminology, and must not introduce new unverified claims.
6. Do not repeat issues already listed in DETERMINISTIC FINDINGS.
7. Company context is background guidance, not evidence. Do not cite it or use it
   to label a factual claim supported or contradicted; those labels require an
   approved passage. It may guide company-specific tone and messaging feedback.
8. Return JSON only, matching the schema exactly. No prose, no markdown fences.

Severity guide: high = factual/legal/brand-breaking; medium = tone or messaging
drift; low = style polish."""

USER_TEMPLATE = """CONTENT TYPE: {content_type}

COMPANY CONTEXT (background guidance; not evidence):
{company_context}

DRAFT:
<<<DRAFT
{body}
DRAFT

APPROVED PASSAGES (id | source | section | text):
{passages}

DETERMINISTIC FINDINGS ALREADY RAISED (do not repeat):
{existing}

Return JSON of this exact shape:
{{
  "findings": [
    {{
      "category": "tone|messaging|claim|terminology|fact|disclaimer|visual",
      "severity": "low|medium|high",
      "affected_text": "exact substring of the draft",
      "rule": "short rule name",
      "explanation": "why this matters, referencing the approved source",
      "source_passage_id": 12,
      "evidence_status": "supported|contradicted|unsupported|needs_verification",
      "confidence": 0.0,
      "suggestion": "replacement text for the affected phrase, or null"
    }}
  ]
}}"""


@dataclass
class LLMResult:
    ok: bool
    findings: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""
    model: str = ""
    latency_ms: int = 0


def _extract_json(content: str) -> dict[str, Any]:
    """Groq JSON mode should return pure JSON, but be defensive."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            return json.loads(content[start : end + 1])
        raise


def analyse(
    body: str,
    content_type: str,
    passages: list[dict[str, Any]],
    existing: list[str],
    company_context: str = "",
) -> LLMResult:
    settings = get_settings()
    if not settings.llm_enabled:
        return LLMResult(
            ok=False,
            message="AI analysis is not configured on this server (no GROQ_API_KEY). "
            "Deterministic brand checks ran normally.",
        )

    passage_block = "\n".join(
        f"{p['id']} | {p['source']} | {p.get('section') or '-'} | {p['text']}" for p in passages
    ) or "(no approved passages matched)"
    existing_block = "\n".join(f"- {e}" for e in existing) or "(none)"

    payload = {
        "model": settings.groq_model,
        "temperature": 0.1,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    content_type=content_type,
                    body=body,
                    passages=passage_block,
                    existing=existing_block,
                    company_context=company_context or "(none provided)",
                ),
            },
        ],
    }

    import time

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            resp = client.post(
                f"{settings.groq_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        latency = int((time.perf_counter() - started) * 1000)
        if resp.status_code == 429:
            return LLMResult(
                ok=False,
                message="The AI service is rate limited right now. Deterministic checks ran normally.",
                latency_ms=latency,
            )
        if resp.status_code >= 400:
            log.warning("Groq error %s: %s", resp.status_code, resp.text[:400])
            return LLMResult(
                ok=False,
                message=f"The AI service returned an error ({resp.status_code}). "
                "Deterministic checks ran normally.",
                latency_ms=latency,
            )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        findings = parsed.get("findings") or []
        if not isinstance(findings, list):
            raise ValueError("findings was not a list")
        return LLMResult(
            ok=True,
            findings=findings,
            message="AI analysis completed.",
            model=settings.groq_model,
            latency_ms=latency,
        )
    except httpx.TimeoutException:
        return LLMResult(
            ok=False,
            message="The AI service timed out. Deterministic checks ran normally.",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 - never break the request
        log.warning("Groq call failed: %s", exc)
        return LLMResult(
            ok=False,
            message="The AI service could not be reached. Deterministic checks ran normally.",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
