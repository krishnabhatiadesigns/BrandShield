"""Shared internal types for the review pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["low", "medium", "high"]
EvidenceStatus = Literal["supported", "contradicted", "unsupported", "needs_verification"]


@dataclass
class FindingDraft:
    """A finding before it is persisted. Mirrors the ``findings`` table."""

    category: str
    severity: Severity
    affected_text: str
    rule: str
    explanation: str
    evidence_status: EvidenceStatus
    suggestion: str | None = None
    source_passage_id: int | None = None
    confidence: float = 0.6
    span_start: int | None = None
    span_end: int | None = None
    detector: str = "deterministic"
    # Populated by the validator when a source is rejected.
    validation_note: str | None = field(default=None, compare=False)

    def key(self) -> tuple[str, str, int | None]:
        """De-duplication key: same rule on the same span is one finding."""
        return (self.category, self.rule, self.span_start)


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
