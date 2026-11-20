"""Database schema for BrandShield AI.

One DDL template is rendered for both SQLite (local dev) and PostgreSQL.
Timestamps are stored as ISO-8601 UTC text so both engines behave identically and
ordering is lexicographic. Booleans are stored as integers (0/1).
"""
from __future__ import annotations

from .db import Database

_TABLES = [
    # --- tenancy -----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS organizations (
        id {pk},
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        id {pk},
        organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workspace_context (
        workspace_id INTEGER PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
        company_context TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL,
        updated_at TEXT NOT NULL
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
        is_active INTEGER NOT NULL DEFAULT 1,
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
        source_object_key TEXT,
        source_filename TEXT,
        source_content_type TEXT,
        source_size INTEGER,
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
    CREATE TABLE IF NOT EXISTS guideline_rules (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        good_example TEXT,
        bad_example TEXT,
        severity TEXT NOT NULL CHECK (severity IN ('low','medium','high')),
        mandatory INTEGER NOT NULL DEFAULT 1,
        content_types TEXT NOT NULL DEFAULT 'social,ad,email,document',
        source_passage_id INTEGER REFERENCES passages(id) ON DELETE SET NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        current_version INTEGER NOT NULL DEFAULT 1,
        effective_date TEXT NOT NULL DEFAULT '',
        created_by TEXT NOT NULL,
        updated_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS guideline_rule_versions (
        id {pk},
        rule_id INTEGER NOT NULL REFERENCES guideline_rules(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        version_no INTEGER NOT NULL,
        snapshot TEXT NOT NULL,
        effective_date TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (rule_id, version_no)
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
        source_object_key TEXT,
        source_filename TEXT,
        source_content_type TEXT,
        source_size INTEGER,
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
        source_rule_id INTEGER,
        source_rule_version INTEGER,
        source_rule_title TEXT,
        source_rule_text TEXT,
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
    """
    CREATE TABLE IF NOT EXISTS review_assignments (
        content_item_id INTEGER PRIMARY KEY REFERENCES content_items(id) ON DELETE CASCADE,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        assignee_user_id TEXT,
        assignee_name TEXT,
        due_at TEXT,
        updated_by TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_outbox (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        sent_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS api_keys (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        key_prefix TEXT NOT NULL,
        key_hash TEXT NOT NULL,
        scopes TEXT NOT NULL DEFAULT 'read',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (workspace_id, key_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS webhook_endpoints (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        secret TEXT NOT NULL,
        events TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS webhook_deliveries (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        endpoint_id INTEGER NOT NULL REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        last_status INTEGER,
        last_error TEXT,
        delivered_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_events (
        id {pk},
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        actor TEXT,
        created_at TEXT NOT NULL
    )
    """,
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_workspaces_organization ON workspaces(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_memberships_user_active ON memberships(user_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_passages_ws_document ON passages(workspace_id, document_id)",
    "CREATE INDEX IF NOT EXISTS idx_terms_ws ON terms(workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_facts_ws ON facts(workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_guideline_rules_workspace_enabled ON guideline_rules(workspace_id, enabled)",
    "CREATE INDEX IF NOT EXISTS idx_guideline_rule_versions_rule ON guideline_rule_versions(rule_id, version_no)",
    "CREATE INDEX IF NOT EXISTS idx_findings_version_workspace ON findings(version_id, workspace_id)",
    "CREATE INDEX IF NOT EXISTS idx_versions_item_version ON content_versions(content_item_id, version_no)",
    "CREATE INDEX IF NOT EXISTS idx_items_workspace_updated ON content_items(workspace_id, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_workspace_created ON audit_events(workspace_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_demo_sessions_created ON demo_sessions(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_notification_outbox_status ON notification_outbox(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status ON webhook_deliveries(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_usage_workspace_created ON usage_events(workspace_id, created_at)",
]

_OBSOLETE_INDEXES = [
    "DROP INDEX IF EXISTS idx_passages_ws",
    "DROP INDEX IF EXISTS idx_findings_version",
    "DROP INDEX IF EXISTS idx_versions_item",
    "DROP INDEX IF EXISTS idx_items_ws",
    "DROP INDEX IF EXISTS idx_audit_ws",
]


def create_schema(db: Database) -> None:
    pk = "BIGSERIAL PRIMARY KEY" if db.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    for ddl in _TABLES:
        db.execute(ddl.format(pk=pk))
    if db.is_postgres:
        membership_columns = db.query(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'memberships' AND table_schema = current_schema()"
        )
        has_active_column = any(row["column_name"] == "is_active" for row in membership_columns)
    else:
        membership_columns = db.query("PRAGMA table_info(memberships)")
        has_active_column = any(row["name"] == "is_active" for row in membership_columns)
    if not has_active_column:
        db.execute("ALTER TABLE memberships ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    if db.is_postgres:
        content_item_columns = {
            row["column_name"]
            for row in db.query(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'content_items' AND table_schema = current_schema()"
            )
        }
        document_columns = {
            row["column_name"]
            for row in db.query(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'knowledge_documents' AND table_schema = current_schema()"
            )
        }
    else:
        content_item_columns = {
            row["name"] for row in db.query("PRAGMA table_info(content_items)")
        }
        document_columns = {
            row["name"] for row in db.query("PRAGMA table_info(knowledge_documents)")
        }
    stored_file_columns = (
        ("source_object_key", "TEXT"),
        ("source_filename", "TEXT"),
        ("source_content_type", "TEXT"),
        ("source_size", "INTEGER"),
    )
    for column, column_type in stored_file_columns:
        if column not in content_item_columns:
            db.execute(f"ALTER TABLE content_items ADD COLUMN {column} {column_type}")
        if column not in document_columns:
            db.execute(f"ALTER TABLE knowledge_documents ADD COLUMN {column} {column_type}")
    if db.is_postgres:
        finding_columns = db.query(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'findings' AND table_schema = current_schema()"
        )
        finding_column_names = {row["column_name"] for row in finding_columns}
    else:
        finding_columns = db.query("PRAGMA table_info(findings)")
        finding_column_names = {row["name"] for row in finding_columns}
    for column, column_type in (
        ("source_rule_id", "INTEGER"),
        ("source_rule_version", "INTEGER"),
        ("source_rule_title", "TEXT"),
        ("source_rule_text", "TEXT"),
    ):
        if column not in finding_column_names:
            db.execute(f"ALTER TABLE findings ADD COLUMN {column} {column_type}")
    if db.is_postgres:
        rule_columns = db.query(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'guideline_rules' AND table_schema = current_schema()"
        )
        rule_column_names = {row["column_name"] for row in rule_columns}
    else:
        rule_columns = db.query("PRAGMA table_info(guideline_rules)")
        rule_column_names = {row["name"] for row in rule_columns}
    if "effective_date" not in rule_column_names:
        db.execute("ALTER TABLE guideline_rules ADD COLUMN effective_date TEXT NOT NULL DEFAULT ''")
    db.execute(
        "UPDATE guideline_rules SET effective_date = substr(created_at, 1, 10)"
        " WHERE effective_date = ''"
    )
    if db.is_postgres:
        workspace_columns = db.query(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'workspaces' AND table_schema = current_schema()"
        )
        has_organization_column = any(
            row["column_name"] == "organization_id" for row in workspace_columns
        )
    else:
        workspace_columns = db.query("PRAGMA table_info(workspaces)")
        has_organization_column = any(
            row["name"] == "organization_id" for row in workspace_columns
        )
    if not has_organization_column:
        db.execute(
            "ALTER TABLE workspaces ADD COLUMN organization_id INTEGER"
            " REFERENCES organizations(id) ON DELETE CASCADE"
        )
    legacy_workspaces = db.query(
        "SELECT id, name, slug, created_at FROM workspaces WHERE organization_id IS NULL"
    )
    for workspace in legacy_workspaces:
        organization_slug = f"legacy-{workspace['slug']}"
        db.execute(
            "INSERT INTO organizations (name, slug, created_at)"
            " SELECT ?, ?, ? WHERE NOT EXISTS"
            " (SELECT 1 FROM organizations WHERE slug = ?)",
            (
                workspace["name"],
                organization_slug,
                workspace["created_at"],
                organization_slug,
            ),
        )
        db.execute(
            "UPDATE workspaces SET organization_id ="
            " (SELECT id FROM organizations WHERE slug = ?) WHERE id = ?",
            (organization_slug, workspace["id"]),
        )
    for idx in _OBSOLETE_INDEXES:
        db.execute(idx)
    for idx in _INDEXES:
        db.execute(idx)
