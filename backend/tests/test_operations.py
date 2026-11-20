from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Principal, get_principal
from app.db import Database, get_db
from app.routers import operations
from app.schema import create_schema


def _client():
    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at) VALUES (1, 'Acme', 'acme', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, display_name, role, is_active, created_at)"
        " VALUES (1, 'admin-id', 'Admin', 'admin', 1, 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, display_name, role, is_active, created_at)"
        " VALUES (1, 'reviewer-id', 'Reviewer', 'approver', 1, 'now')"
    )
    db.insert(
        "INSERT INTO content_items"
        " (workspace_id, title, content_type, status, created_by, created_at, updated_at)"
        " VALUES (1, 'Launch', 'social', 'Draft', 'admin-id', 'now', 'now')"
    )
    app = FastAPI()
    app.include_router(operations.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "admin-id", "Admin", "admin", 1, "Acme", False
    )
    return db, TestClient(app)


def test_assignment_analytics_api_key_and_webhook():
    db, client = _client()

    reviewers = client.get("/api/operations/reviewers")
    assert reviewers.status_code == 200
    assert {member["user_id"] for member in reviewers.json()} == {
        "admin-id",
        "reviewer-id",
    }

    assigned = client.put(
        "/api/operations/content/1/assignment",
        json={
            "assignee_user_id": "reviewer-id",
            "due_at": "2026-12-01T17:00:00",
        },
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignee_name"] == "Reviewer"
    assert assigned.json()["due_at"] == "2026-12-01T17:00:00"

    analytics = client.get("/api/operations/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["submissions"] == 1

    csv_export = client.get("/api/operations/exports/audit.csv")
    assert csv_export.status_code == 200
    assert "created_at,actor,action" in csv_export.text

    key = client.post(
        "/api/operations/api-keys",
        json={"name": "Reporting integration", "scopes": ["read"]},
    )
    assert key.status_code == 200
    assert key.json()["key"].startswith("bs_")
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM api_keys WHERE workspace_id=1"
    )["n"] == 1

    webhook = client.post(
        "/api/operations/webhooks",
        json={
            "name": "Audit sink",
            "url": "https://example.com/brandshield",
            "secret": "a-long-webhook-signing-secret",
            "events": ["*"],
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["name"] == "Audit sink"
