"""Database schema for BrandShield AI.

One DDL template is rendered for both SQLite (local dev) and Postgres (Supabase).
Timestamps are stored as ISO-8601 UTC text so both engines behave identically and
ordering is lexicographic. Booleans are stored as integers (0/1).
"""
from __future__ import annotations

from .db import Database

_TABLES = [
    # --- tenancy -----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        id {pk},
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memberships (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL,
        email TEXT,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('creator','manager','approver','admin')),
        created_at TEXT NOT NULL,
        UNIQUE (workspace_id, user_id)
    )
    """,
    # --- brand knowledge ---------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS knowledge_documents (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'approved',
        version INTEGER NOT NULL DEFAULT 1,
        effective_date TEXT,
        storage_path TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS passages (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        document_id INTEGER REFERENCES knowledge_documents(id) ON DELETE CASCADE,
        source TEXT NOT NULL,
        page INTEGER,
        section TEXT,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS terms (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        term TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('approved','prohibited')),
        replacement TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS facts (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        fact_key TEXT NOT NULL,
        value TEXT NOT NULL,
        unit TEXT,
        source_passage_id INTEGER REFERENCES passages(id) ON DELETE SET NULL,
        effective_date TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS palette_colors (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        hex TEXT NOT NULL,
        role TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS brand_assets (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL
    )
    """,
    # --- content -----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS content_items (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        content_type TEXT NOT NULL,
        status TEXT NOT NULL,
        created_by TEXT NOT NULL,
        current_version_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS content_versions (
        id {pk},
        content_item_id INTEGER NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        version_no INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        review_state TEXT NOT NULL DEFAULT 'unreviewed',
        UNIQUE (content_item_id, version_no)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS findings (
        id {pk},
        version_id INTEGER NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        category TEXT NOT NULL,
        severity TEXT NOT NULL CHECK (severity IN ('low','medium','high')),
        span_start INTEGER,
        span_end INTEGER,
        affected_text TEXT NOT NULL,
        rule TEXT NOT NULL,
        explanation TEXT NOT NULL,
        source_passage_id INTEGER REFERENCES passages(id) ON DELETE SET NULL,
        evidence_status TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.5,
        suggestion TEXT,
        creator_decision TEXT NOT NULL DEFAULT 'pending',
        edited_text TEXT,
        detector TEXT NOT NULL DEFAULT 'deterministic',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS comments (
        id {pk},
        version_id INTEGER NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        author TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS approvals (
        id {pk},
        version_id INTEGER NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        decision TEXT NOT NULL CHECK (decision IN ('approved','changes_requested','rejected')),
        reason TEXT,
        reviewer TEXT NOT NULL,
        high_severity_signoff INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        detail TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS demo_sessions (
        token TEXT PRIMARY KEY,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        display_name TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_runs (
        id {pk},
        version_id INTEGER NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        llm_status TEXT NOT NULL,
        llm_message TEXT,
        deterministic_count INTEGER NOT NULL DEFAULT 0,
        llm_count INTEGER NOT NULL DEFAULT 0,
        duration_ms INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_passages_ws ON passages(workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_terms_ws ON terms(workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_facts_ws ON facts(workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_findings_version ON findings(version_id)",
    "CREATE INDEX IF NOT EXISTS idx_versions_item ON content_versions(content_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_items_ws ON content_items(workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_ws ON audit_events(workspace_id)",
]


def create_schema(db: Database) -> None:
    pk = "BIGSERIAL PRIMARY KEY" if db.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    for ddl in _TABLES:
        db.execute(ddl.format(pk=pk))
    for idx in _INDEXES:
        db.execute(idx)
