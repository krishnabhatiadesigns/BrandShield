from __future__ import annotations

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def isolate_database_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
