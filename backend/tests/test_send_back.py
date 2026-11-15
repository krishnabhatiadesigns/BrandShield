from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Principal, get_principal
from app.db import Database, get_db
from app.routers import content
from app.schema import create_schema


def _principal(role: str) -> Principal:
    return Principal(f"{role}-id", f"{role.title()} Person", role, 1, "Acme", False)


@pytest.fixture
def app():
    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at) VALUES (1, 'Acme', 'acme', 'now')"
    )
    db.insert(
        "INSERT INTO content_items (id, workspace_id, title, content_type, status, created_by,"
        " created_at, updated_at) VALUES (1, 1, 'Launch', 'social', 'Manager Review',"
        " 'creator-id', 'now', 'now')"
    )
    db.insert(
        "INSERT INTO content_versions (id, content_item_id, workspace_id, version_no, body,"
        " created_by, created_at, status, review_state) VALUES (1, 1, 1, 1, 'Draft',"
        " 'creator-id', 'now', 'Manager Review', 'reviewed')"
    )
    db.execute("UPDATE content_items SET current_version_id = 1 WHERE id = 1")
    db.insert(
        "INSERT INTO content_items (id, workspace_id, title, content_type, status, created_by,"
        " created_at, updated_at) VALUES (2, 1, 'Other', 'social', 'Draft', 'creator-id',"
        " 'now', 'now')"
    )
    db.insert(
        "INSERT INTO content_versions (id, content_item_id, workspace_id, version_no, body,"
        " created_by, created_at, status) VALUES (2, 2, 1, 1, 'Other draft', 'creator-id',"
        " 'now', 'Draft')"
    )

    app = FastAPI()
    app.include_router(content.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: _principal("manager")
    return db, app


def _set_status(db: Database, status: str) -> None:
    db.execute("UPDATE content_versions SET status = ? WHERE id = 1", (status,))
    db.execute("UPDATE content_items SET status = ? WHERE id = 1", (status,))


def test_manager_send_back_requires_a_note(app):
    _, app = app
    client = TestClient(app)

    response = client.post("/api/content/1/send-back", json={"note": "   "})

    assert response.status_code == 422


def test_manager_send_back_returns_version_to_creator(app):
    db, app = app
    client = TestClient(app)

    response = client.post("/api/content/1/send-back", json={"note": "Fix the pricing claim."})

    assert response.status_code == 200
    assert response.json()["status"] == "Changes Required"
    assert response.json()["comments"][-1]["body"] == (
        "Sent back to the creator: Fix the pricing claim."
    )


def test_approver_send_back_returns_version_to_manager(app):
    db, app = app
    _set_status(db, "Approver Review")
    app.dependency_overrides[get_principal] = lambda: _principal("approver")

    response = TestClient(app).post(
        "/api/content/1/send-back", json={"note": "Needs a manager pass first."}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Manager Review"


def test_send_back_rejects_a_version_not_waiting_on_you(app):
    db, app = app
    _set_status(db, "Draft")

    response = TestClient(app).post("/api/content/1/send-back", json={"note": "Too early."})

    assert response.status_code == 409


def test_submission_audit_excludes_other_submissions(app):
    db, app = app
    app.dependency_overrides[get_principal] = lambda: _principal("approver")
    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id, detail,"
        " created_at) VALUES (1, 'Manager Person', 'content.sent_back', 'version', 1,"
        " 'this one', 'now')"
    )
    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id, detail,"
        " created_at) VALUES (1, 'Manager Person', 'content.sent_back', 'version', 2,"
        " 'other one', 'now')"
    )

    response = TestClient(app).get("/api/content/1/audit")

    assert response.status_code == 200
    assert [event["detail"] for event in response.json()] == ["this one"]
