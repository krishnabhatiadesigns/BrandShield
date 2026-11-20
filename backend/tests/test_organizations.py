from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Principal, get_principal, get_verified_identity
from app.config import get_settings
from app.db import Database, get_db
from app.routers import organizations
from app.schema import create_schema


@pytest.fixture
def organization_client(monkeypatch):
    monkeypatch.setenv("ALLOW_ORGANIZATION_CREATION", "true")
    get_settings.cache_clear()
    db = Database("sqlite:///:memory:")
    create_schema(db)
    app = FastAPI()
    app.include_router(organizations.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_verified_identity] = lambda: {
        "sub": "founder-id",
        "email": "founder@example.com",
    }
    app.dependency_overrides[get_principal] = lambda: Principal(
        "founder-id", "Founder", "admin", 1, "Acme", False
    )
    with TestClient(app) as client:
        yield db, client
    get_settings.cache_clear()


def test_verified_employee_can_create_organization_and_first_brand(organization_client):
    db, client = organization_client

    response = client.post(
        "/api/organizations",
        json={
            "name": "Acme Agency",
            "brand_name": "Acme Consumer",
            "display_name": "Alex Founder",
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["organization_name"] == "Acme Agency"
    assert result["workspace_name"] == "Acme Consumer"
    assert result["role"] == "admin"
    membership = db.query_one(
        "SELECT user_id, email, role, is_active FROM memberships WHERE workspace_id = ?",
        (result["workspace_id"],),
    )
    assert membership == {
        "user_id": "founder-id",
        "email": "founder@example.com",
        "role": "admin",
        "is_active": 1,
    }


def test_user_cannot_create_a_second_organization_through_onboarding(organization_client):
    db, client = organization_client
    db.insert(
        "INSERT INTO organizations (id, name, slug, created_at)"
        " VALUES (1, 'Acme', 'acme', 'now')"
    )
    db.insert(
        "INSERT INTO workspaces (id, organization_id, name, slug, created_at)"
        " VALUES (1, 1, 'Acme Brand', 'acme-brand', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'founder-id', 'founder@example.com', 'Founder', 'admin', 'now')"
    )

    response = client.post(
        "/api/organizations",
        json={"name": "Another Org", "display_name": "Founder"},
    )

    assert response.status_code == 409
    assert db.query_one("SELECT COUNT(*) AS count FROM organizations")["count"] == 1


def test_organization_self_service_is_disabled_unless_explicitly_enabled(
    organization_client, monkeypatch
):
    _, client = organization_client
    monkeypatch.setenv("ALLOW_ORGANIZATION_CREATION", "false")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/organizations",
            json={"name": "Acme Agency", "display_name": "Founder"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 404


def test_org_admin_can_create_an_isolated_brand_and_switch_workspaces(organization_client):
    db, client = organization_client
    db.insert(
        "INSERT INTO organizations (id, name, slug, created_at)"
        " VALUES (1, 'Acme', 'acme', 'now')"
    )
    db.insert(
        "INSERT INTO workspaces (id, organization_id, name, slug, created_at)"
        " VALUES (1, 1, 'Acme Brand', 'acme-brand', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'founder-id', 'founder@example.com', 'Founder', 'admin', 'now')"
    )

    created = client.post("/api/workspaces", json={"name": "Acme Kids"})
    assert created.status_code == 201
    new_brand = created.json()
    assert new_brand["organization_id"] == 1
    assert new_brand["name"] == "Acme Kids"

    listed = client.get("/api/workspaces")
    assert listed.status_code == 200
    assert {workspace["name"] for workspace in listed.json()} == {
        "Acme Brand",
        "Acme Kids",
    }

    assert db.query_one(
        "SELECT COUNT(*) AS count FROM memberships"
        " WHERE user_id = 'founder-id' AND is_active = 1"
    )["count"] == 2
