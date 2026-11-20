from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Principal, get_principal
from app.db import Database, get_db
from app.llm import LLMResult
from app.pipeline import run_review
from app.routers import brand, content
from app.schema import create_schema


@pytest.fixture
def workspace():
    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at) VALUES (1, 'Acme', 'acme', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, display_name, role, created_at)"
        " VALUES (1, 'manager-id', 'Mina Manager', 'manager', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, display_name, role, created_at)"
        " VALUES (1, 'approver-id', 'Ari Approver', 'approver', 'now')"
    )

    app = FastAPI()
    app.include_router(brand.router)
    app.include_router(content.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "manager-id", "Mina Manager", "manager", 1, "Acme", False
    )
    return db, app


def test_company_context_is_saved_and_forwarded_to_ai(workspace):
    db, app = workspace
    client = TestClient(app)
    context = "Acme serves small businesses."

    response = client.put(
        "/api/brand/company-context", json={"company_context": context}
    )
    assert response.status_code == 204
    assert client.get("/api/brand").json()["company_context"] == context

    with patch(
        "app.pipeline.analyse",
        return_value=LLMResult(ok=False, message="test"),
    ) as analyse:
        run_review(db, 1, "Draft text.", "social", use_llm=True)

    assert analyse.call_args.args[4] == context


@pytest.mark.parametrize(
    ("user_id", "display_name", "role"),
    [
        ("creator-id", "Creator", "creator"),
        ("approver-id", "Approver", "approver"),
        ("admin-id", "Admin", "admin"),
    ],
)
def test_only_manager_can_update_company_context(workspace, user_id, display_name, role):
    _, app = workspace
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id, display_name, role, 1, "Acme", False
    )

    response = TestClient(app).put(
        "/api/brand/company-context", json={"company_context": "Unauthorized"}
    )

    assert response.status_code == 403


def test_history_attributes_revisions_to_workspace_members(workspace):
    db, app = workspace
    db.insert(
        "INSERT INTO content_items (id, workspace_id, title, content_type, status, created_by,"
        " created_at, updated_at) VALUES (1, 1, 'Launch', 'social', 'Draft', 'manager-id', 'now', 'now')"
    )
    db.insert(
        "INSERT INTO content_versions (id, content_item_id, workspace_id, version_no, body,"
        " created_by, created_at, status) VALUES (1, 1, 1, 1, 'Original', 'manager-id', 'now', 'Draft')"
    )
    db.insert(
        "INSERT INTO content_versions (id, content_item_id, workspace_id, version_no, body,"
        " created_by, created_at, status) VALUES (2, 1, 1, 2, 'Revised', 'approver-id', 'later', 'Draft')"
    )

    client = TestClient(app)
    assert client.get("/api/content/1/history").status_code == 403
    assert client.get("/api/content/1/audit").status_code == 403
    assert client.get("/api/audit").status_code == 403

    app.dependency_overrides[get_principal] = lambda: Principal(
        "approver-id", "Ari Approver", "approver", 1, "Acme", False
    )
    response = client.get("/api/content/1/history")

    assert response.status_code == 200
    assert [version["created_by"] for version in response.json()] == [
        "Mina Manager",
        "Ari Approver",
    ]
    assert client.get("/api/content/1/audit").status_code == 200
    assert client.get("/api/audit").status_code == 200
