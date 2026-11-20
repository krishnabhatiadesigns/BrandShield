"""Application configuration, loaded from environment variables only.

No secrets are ever hardcoded. See .env.example at the repo root.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
DEFAULT_CORS_ORIGINS = "http://localhost:5173,https://brand-shield-amber.vercel.app"


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
        # PostgreSQL URLs are normalised to the psycopg driver.
        self.database_url: str = _env("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'brandshield.db'}"

        # --- LLM ------------------------------------------------------------
        self.groq_api_key: str = _env("GROQ_API_KEY")
        self.groq_model: str = _env("GROQ_MODEL", "openai/gpt-oss-120b")
        self.groq_base_url: str = _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        self.llm_timeout_seconds: float = float(_env("LLM_TIMEOUT_SECONDS", "25"))

        # --- Supabase Auth --------------------------------------------------
        self.supabase_url: str = _env("SUPABASE_URL").rstrip("/")
        if self.supabase_url:
            supabase_origin = urlsplit(self.supabase_url)
            local_hosts = {"localhost", "127.0.0.1", "::1"}
            if (
                not supabase_origin.hostname
                or supabase_origin.path not in {"", "/"}
                or supabase_origin.username
                or supabase_origin.password
                or supabase_origin.query
                or supabase_origin.fragment
                or (
                    supabase_origin.scheme != "https"
                    and supabase_origin.hostname not in local_hosts
                )
            ):
                raise ValueError(
                    "SUPABASE_URL must be an HTTPS project origin, except for local development."
                )
        self.supabase_service_role_key: str = _env("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase_jwt_secret: str = _env("SUPABASE_JWT_SECRET")
        self.app_frontend_url: str = _env("APP_FRONTEND_URL", "http://localhost:5173").rstrip("/")

        # --- app ------------------------------------------------------------
        cors_origins = _env("CORS_ORIGINS", DEFAULT_CORS_ORIGINS) or DEFAULT_CORS_ORIGINS
        self.cors_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must contain explicit origins; wildcard '*' is not allowed.")
        self.demo_workspace_slug: str = _env("DEMO_WORKSPACE_SLUG", "northwind-foods")
        self.demo_session_ttl_hours: int = int(_env("DEMO_SESSION_TTL_HOURS", "12"))
        if self.demo_session_ttl_hours < 1:
            raise ValueError("DEMO_SESSION_TTL_HOURS must be at least 1.")
        self.demo_auth_enabled: bool = _env("DEMO_AUTH_ENABLED", "false").lower() in {
            "1",
            "true",
            "yes",
        }
        self.allow_organization_creation: bool = _env(
            "ALLOW_ORGANIZATION_CREATION", "false"
        ).lower() in {"1", "true", "yes"}
        self.smtp_host: str = _env("SMTP_HOST")
        self.smtp_port: int = int(_env("SMTP_PORT", "587"))
        self.smtp_username: str = _env("SMTP_USERNAME")
        self.smtp_password: str = _env("SMTP_PASSWORD")
        self.smtp_from: str = _env("SMTP_FROM", "BrandShield <no-reply@brandshield.local>")
        self.smtp_use_tls: bool = _env("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
        self.notification_worker_enabled: bool = _env(
            "NOTIFICATION_WORKER_ENABLED", "false"
        ).lower() in {"1", "true", "yes"}
        self.storage_backend: str = _env("STORAGE_BACKEND", "local").lower()
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be 'local' or 's3'.")
        self.private_storage_dir: Path = Path(
            _env("PRIVATE_STORAGE_DIR", str(BASE_DIR / "data" / "private_uploads"))
        ).resolve()
        self.s3_bucket: str = _env("S3_BUCKET")
        self.s3_region: str = _env("S3_REGION", "us-east-1")
        self.s3_endpoint_url: str = _env("S3_ENDPOINT_URL").rstrip("/")
        self.s3_access_key_id: str = _env("S3_ACCESS_KEY_ID")
        self.s3_secret_access_key: str = _env("S3_SECRET_ACCESS_KEY")
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
