from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from app.auth import Principal, resolve_principal
from app.config import get_settings
from app.db import Database, get_db
from app.routers import members, session
from app.schema import create_schema

SUPABASE_URL = "https://example.supabase.co"
JWT_SECRET = "test-jwt-secret-with-enough-entropy"


def _token(
    user_id: str = "auth-user-1",
    *,
    role: str = "authenticated",
    audience: str = "authenticated",
    issuer: str = f"{SUPABASE_URL}/auth/v1",
    expires_in: int = 300,
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": user_id,
            "role": role,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def auth_database(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("DEMO_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at)"
        " VALUES (1, 'Acme', 'acme', 'now')"
    )
    yield db
    get_settings.cache_clear()


def test_supabase_token_uses_active_database_membership(auth_database):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'auth-user-1', 'user@example.com', 'A User', 'creator', 'now')"
    )

    principal = resolve_principal(db, f"Bearer {_token()}", None)

    assert principal == Principal("auth-user-1", "A User", "creator", 1, "Acme", False)


def test_supabase_asymmetric_jwks_signing_key_is_verified(auth_database, monkeypatch):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'auth-user-1', 'user@example.com', 'A User', 'creator', 'now')"
    )
    private_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "iss": f"{SUPABASE_URL}/auth/v1",
            "aud": "authenticated",
            "sub": "auth-user-1",
            "role": "authenticated",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key"},
    )

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _token: str):
            return SimpleNamespace(key=private_key.public_key())

    monkeypatch.setattr("app.auth._jwks_client", lambda _url: FakeJwksClient())

    principal = resolve_principal(db, f"Bearer {token}", None)

    assert principal.user_id == "auth-user-1"
    assert principal.role == "creator"


def test_unavailable_supabase_jwks_is_reported_as_temporary_service_failure(
    auth_database, monkeypatch
):
    class UnavailableJwksClient:
        def get_signing_key_from_jwt(self, _token: str):
            raise PyJWKClientConnectionError("JWKS unavailable")

    monkeypatch.setattr("app.auth._jwks_client", lambda _url: UnavailableJwksClient())
    token = jwt.encode(
        {
            "iss": f"{SUPABASE_URL}/auth/v1",
            "aud": "authenticated",
            "sub": "auth-user-1",
            "role": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        ec.generate_private_key(ec.SECP256R1()),
        algorithm="ES256",
        headers={"kid": "unavailable"},
    )

    with pytest.raises(HTTPException) as result:
        resolve_principal(auth_database, f"Bearer {token}", None)

    assert result.value.status_code == 503


def test_supabase_token_rejects_invalid_signature_and_non_user_role(auth_database):
    db = auth_database
    invalid_signature = jwt.encode(
        {
            "iss": f"{SUPABASE_URL}/auth/v1",
            "aud": "authenticated",
            "sub": "auth-user-1",
            "role": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "wrong-signing-key-that-is-at-least-thirty-two-bytes",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as invalid:
        resolve_principal(db, f"Bearer {invalid_signature}", None)
    assert invalid.value.status_code == 401

    with pytest.raises(HTTPException) as service_role:
        resolve_principal(db, f"Bearer {_token(role='service_role')}", None)
    assert service_role.value.status_code == 401

    for token in (
        _token(issuer="https://attacker.example/auth/v1"),
        _token(audience="anon"),
        _token(expires_in=-5),
    ):
        with pytest.raises(HTTPException) as invalid_claim:
            resolve_principal(db, f"Bearer {token}", None)
        assert invalid_claim.value.status_code == 401


def test_inactive_or_unprovisioned_user_cannot_access_workspace(auth_database):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role,"
        " is_active, created_at) VALUES (1, 'auth-user-1', 'user@example.com',"
        " 'A User', 'creator', 0, 'now')"
    )

    with pytest.raises(HTTPException) as inactive:
        resolve_principal(db, f"Bearer {_token()}", None)
    assert inactive.value.status_code == 403

    with pytest.raises(HTTPException) as missing:
        resolve_principal(db, f"Bearer {_token('unknown-user')}", None)
    assert missing.value.status_code == 403


def test_multiple_active_workspace_memberships_default_and_explicitly_switch(auth_database):
    db = auth_database
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at)"
        " VALUES (2, 'Other', 'other', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'auth-user-1', 'user@example.com', 'A User', 'creator', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (2, 'auth-user-1', 'user@example.com', 'A User', 'manager', 'now')"
    )

    default_principal = resolve_principal(db, f"Bearer {_token()}", None)
    selected_principal = resolve_principal(db, f"Bearer {_token()}", None, workspace_id=2)

    assert default_principal.workspace_id == 1
    assert selected_principal.workspace_id == 2
    with pytest.raises(HTTPException) as unauthorized_workspace:
        resolve_principal(db, f"Bearer {_token()}", None, workspace_id=99)
    assert unauthorized_workspace.value.status_code == 403


def test_admin_invitation_assigns_role_and_creates_workspace_membership(
    auth_database, monkeypatch
):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'admin-user', 'admin@example.com', 'Admin', 'admin', 'now')"
    )
    calls = []

    def fake_provider_request(method: str, path: str, payload: dict):
        calls.append((method, path, payload))
        return {"id": "invited-user"}

    monkeypatch.setattr(members, "_supabase_request", fake_provider_request)
    app = FastAPI()
    app.include_router(members.router)
    app.dependency_overrides[get_db] = lambda: db

    from app.auth import get_principal

    app.dependency_overrides[get_principal] = lambda: Principal(
        "admin-user", "Admin", "admin", 1, "Acme", False
    )
    response = TestClient(app).post(
        "/api/admin/members",
        json={
            "email": "new@example.com",
            "display_name": "New User",
            "role": "manager",
        },
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == "invited-user"
    assert response.json()["role"] == "manager"
    assert calls[0][0] == "POST"
    assert calls[0][1].startswith("invite?")
    row = db.query_one(
        "SELECT role, is_active FROM memberships WHERE workspace_id = 1 AND user_id = 'invited-user'"
    )
    assert row == {"role": "manager", "is_active": 1}
    duplicate = TestClient(app).post(
        "/api/admin/members",
        json={
            "email": "NEW@example.com",
            "display_name": "New User",
            "role": "manager",
        },
    )
    assert duplicate.status_code == 409


def test_admin_deactivation_revokes_provider_login_and_membership(
    auth_database, monkeypatch
):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'admin-user', 'admin@example.com', 'Admin', 'admin', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'member-user', 'member@example.com', 'Member', 'creator', 'now')"
    )
    calls = []
    monkeypatch.setattr(
        members,
        "_supabase_request",
        lambda method, path, payload: calls.append((method, path, payload)) or {"id": "member-user"},
    )
    from app.auth import get_principal

    app = FastAPI()
    app.include_router(members.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "admin-user", "Admin", "admin", 1, "Acme", False
    )

    response = TestClient(app).patch(
        "/api/admin/members/member-user", json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert calls == [
        ("PUT", "admin/users/member-user", {"ban_duration": "876000h"})
    ]
    assert db.query_one(
        "SELECT is_active FROM memberships WHERE user_id = 'member-user'"
    )["is_active"] == 0


def test_provider_failure_still_blocks_brandshield_access_on_deactivation(
    auth_database, monkeypatch
):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'admin-user', 'admin@example.com', 'Admin', 'admin', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'member-user', 'member@example.com', 'Member', 'creator', 'now')"
    )

    def fail_provider(*_args, **_kwargs):
        raise HTTPException(status_code=502, detail="provider unavailable")

    monkeypatch.setattr(members, "_supabase_request", fail_provider)
    from app.auth import get_principal

    app = FastAPI()
    app.include_router(members.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "admin-user", "Admin", "admin", 1, "Acme", False
    )

    response = TestClient(app).patch(
        "/api/admin/members/member-user", json={"is_active": False}
    )

    assert response.status_code == 502
    assert "BrandShield access is disabled" in response.json()["detail"]
    assert db.query_one(
        "SELECT is_active FROM memberships WHERE user_id = 'member-user'"
    )["is_active"] == 0


def test_last_workspace_admin_cannot_be_demoted(auth_database):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'admin-user', 'admin@example.com', 'Admin', 'admin', 'now')"
    )
    from app.auth import get_principal

    app = FastAPI()
    app.include_router(members.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "admin-user", "Admin", "admin", 1, "Acme", False
    )

    response = TestClient(app).patch(
        "/api/admin/members/admin-user", json={"role": "manager"}
    )

    assert response.status_code == 409
    assert "last active admin" in response.json()["detail"]


def test_non_admin_cannot_list_workspace_members(auth_database):
    from app.auth import get_principal

    app = FastAPI()
    app.include_router(members.router)
    app.dependency_overrides[get_db] = lambda: auth_database
    app.dependency_overrides[get_principal] = lambda: Principal(
        "creator-user", "Creator", "creator", 1, "Acme", False
    )

    response = TestClient(app).get("/api/admin/members")

    assert response.status_code == 403


def test_admin_member_list_hides_seeded_demo_accounts(auth_database):
    db = auth_database
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'admin-user', 'admin@example.com', 'Admin', 'admin', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
        " VALUES (1, 'demo-creator', 'creator@northwind.example', 'Demo Creator', 'creator', 'now')"
    )
    from app.auth import get_principal

    app = FastAPI()
    app.include_router(members.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "admin-user", "Admin", "admin", 1, "Acme", False
    )

    response = TestClient(app).get("/api/admin/members")

    assert response.status_code == 200
    assert [member["user_id"] for member in response.json()] == ["admin-user"]


def test_demo_sign_in_is_disabled_by_default_for_business_deployments(auth_database):
    app = FastAPI()
    app.include_router(session.router)
    app.dependency_overrides[get_db] = lambda: auth_database

    response = TestClient(app).post("/api/demo/session", json={"role": "creator"})

    assert response.status_code == 404


def test_schema_migration_adds_membership_active_flag_to_existing_database():
    db = Database("sqlite:///:memory:")
    db.execute(
        "CREATE TABLE memberships (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " workspace_id INTEGER NOT NULL, user_id TEXT NOT NULL, email TEXT,"
        " display_name TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL,"
        " UNIQUE(workspace_id, user_id))"
    )

    create_schema(db)

    columns = db.query("PRAGMA table_info(memberships)")
    assert any(column["name"] == "is_active" for column in columns)
