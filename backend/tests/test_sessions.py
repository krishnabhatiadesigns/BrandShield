from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import Database, get_db
from app.routers import session
from app.schema import create_schema


@pytest.fixture
def session_client(monkeypatch):
    monkeypatch.setenv("DEMO_SESSION_TTL_HOURS", "12")
    monkeypatch.setenv("DEMO_AUTH_ENABLED", "true")
    get_settings.cache_clear()

    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at)"
        " VALUES (1, 'Northwind Foods', 'northwind-foods', 'now')"
    )

    app = FastAPI()
    app.include_router(session.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield db, client
    get_settings.cache_clear()


def test_logout_revokes_session_and_is_idempotent(session_client):
    _, client = session_client
    created = client.post("/api/demo/session", json={"role": "creator"})
    assert created.status_code == 200
    token = created.json()["token"]
    headers = {"X-Demo-Token": token}

    assert client.get("/api/me", headers=headers).status_code == 200
    assert client.post("/api/logout", headers=headers).status_code == 204
    assert client.post("/api/logout", headers=headers).status_code == 204
    assert client.get("/api/me", headers=headers).status_code == 401


def test_expired_session_is_rejected_and_cleaned_on_new_login(session_client):
    db, client = session_client
    created = client.post("/api/demo/session", json={"role": "manager"})
    assert created.status_code == 200
    token = created.json()["token"]
    db.execute(
        "UPDATE demo_sessions SET created_at = '2000-01-01T00:00:00+00:00' WHERE token = ?",
        (token,),
    )

    assert client.get("/api/me", headers={"X-Demo-Token": token}).status_code == 401

    replacement = client.post("/api/demo/session", json={"role": "manager"})
    assert replacement.status_code == 200
    assert db.query_one("SELECT COUNT(*) AS n FROM demo_sessions")["n"] == 1


def test_demo_sessions_work_when_legacy_toggle_is_false(session_client, monkeypatch):
    _, client = session_client
    monkeypatch.setenv("DEMO_AUTH_ENABLED", "false")
    get_settings.cache_clear()

    created = client.post("/api/demo/session", json={"role": "manager"})

    assert created.status_code == 200
    token = created.json()["token"]
    current_user = client.get("/api/me", headers={"X-Demo-Token": token})
    assert current_user.status_code == 200
    assert current_user.json()["role"] == "manager"


def test_cors_rejects_wildcard_and_accepts_explicit_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="explicit origins"):
        Settings()

    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://brandshield.example, http://localhost:5173",
    )
    settings = Settings()
    assert settings.cors_origins == [
        "https://brandshield.example",
        "http://localhost:5173",
    ]


def test_cors_default_keeps_local_and_deployed_frontend_origins(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings()

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://brand-shield-amber.vercel.app",
    ]


def test_supabase_url_requires_https_outside_local_development(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://auth.example.com")

    with pytest.raises(ValueError, match="SUPABASE_URL must be an HTTPS"):
        Settings()
