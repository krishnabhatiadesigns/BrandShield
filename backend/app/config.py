"""Application configuration, loaded from environment variables only.

No secrets are ever hardcoded. See .env.example at the repo root.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


def _load_env_files() -> None:
    """Load .env files without adding a dependency.

    Real environment variables always win, so a host's dashboard settings are
    never overridden by a stray file. Looked up in order: repo root, backend dir.
    """
    for candidate in (REPO_ROOT / ".env", BASE_DIR / ".env"):
        if not candidate.is_file():
            continue
        try:
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue


_load_env_files()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class Settings:
    """Plain settings object. Kept dependency-free so it is easy to explain."""

    def __init__(self) -> None:
        # --- database -------------------------------------------------------
        # DATABASE_URL wins. Otherwise we fall back to a local SQLite file.
        # Postgres/Supabase URLs are normalised to the psycopg driver.
        self.database_url: str = _env("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'brandshield.db'}"

        # --- LLM ------------------------------------------------------------
        self.groq_api_key: str = _env("GROQ_API_KEY")
        self.groq_model: str = _env("GROQ_MODEL", "openai/gpt-oss-120b")
        self.groq_base_url: str = _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        self.llm_timeout_seconds: float = float(_env("LLM_TIMEOUT_SECONDS", "25"))

        # --- Supabase (optional: real auth + private storage) ---------------
        self.supabase_url: str = _env("SUPABASE_URL")
        self.supabase_anon_key: str = _env("SUPABASE_ANON_KEY")
        self.supabase_service_key: str = _env("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase_jwt_secret: str = _env("SUPABASE_JWT_SECRET")
        self.supabase_storage_bucket: str = _env("SUPABASE_STORAGE_BUCKET", "brand-docs")

        # --- app ------------------------------------------------------------
        self.cors_origins: list[str] = [
            o.strip() for o in _env("CORS_ORIGINS", "*").split(",") if o.strip()
        ]
        self.demo_workspace_slug: str = _env("DEMO_WORKSPACE_SLUG", "northwind-foods")
        self.seed_on_start: bool = _env("SEED_ON_START", "true").lower() in {"1", "true", "yes"}

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith(("postgres://", "postgresql://"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
