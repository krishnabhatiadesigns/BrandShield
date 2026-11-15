"""BM25 retrieval over approved, in-force passages, scoped to one workspace.

The workspace filter is applied in SQL *before* ranking, so a passage from another
workspace can never be returned even if it scores highly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from .db import Database

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class RetrievedPassage:
    id: int
    source: str
    section: str | None
    page: int | None
    text: str
    score: float


def load_workspace_passages(db: Database, workspace_id: int) -> list[dict]:
    """Only approved documents that are in force (effective_date <= today)."""
    return db.query(
        """
        SELECT p.id, p.source, p.section, p.page, p.text, d.status, d.effective_date
        FROM passages p
        JOIN knowledge_documents d ON d.id = p.document_id
        WHERE p.workspace_id = ?
          AND d.workspace_id = ?
          AND d.status = 'approved'
          AND (d.effective_date IS NULL OR d.effective_date <= date('now'))
        ORDER BY p.id
        """,
        (workspace_id, workspace_id),
    )


class WorkspaceRetriever:
    """Build once per review run; cheap enough for demo-sized corpora."""

    def __init__(self, passages: list[dict]) -> None:
        self.passages = passages
        self._corpus = [tokenize(p["text"]) for p in passages]
        self._bm25 = BM25Okapi(self._corpus) if self._corpus else None

    def search(self, query: str, k: int = 4) -> list[RetrievedPassage]:
        if not self._bm25 or not self.passages:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[RetrievedPassage] = []
        for i in ranked[:k]:
            if scores[i] <= 0:
                continue
            p = self.passages[i]
            out.append(
                RetrievedPassage(
                    id=int(p["id"]),
                    source=p["source"],
                    section=p.get("section"),
                    page=p.get("page"),
                    text=p["text"],
                    score=float(scores[i]),
                )
            )
        return out

    def retrieve_for_claims(
        self, claims: list[tuple[int, int, str]], k: int = 4
    ) -> dict[int, list[RetrievedPassage]]:
        """Map each claim's start offset to its top-k passages."""
        return {start: self.search(text, k=k) for start, _end, text in claims}
