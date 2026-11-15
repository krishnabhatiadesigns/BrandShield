"""BrandShield AI backend.

Run locally:
    uvicorn app.main:app --reload --port 8000
OpenAPI docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import get_db
from .routers import brand, content, session, visual
from .schema import create_schema
from .seed import seed_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("brandshield")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = get_db()
    create_schema(db)
    if settings.seed_on_start:
        ws_id = seed_all(db)
        log.info("Demo workspace ready (id=%s)", ws_id)
    log.info(
        "BrandShield AI started | db=%s | llm=%s",
        "postgres" if settings.is_postgres else "sqlite",
        settings.groq_model if settings.llm_enabled else "disabled",
    )
    yield


app = FastAPI(
    title="BrandShield AI",
    version="1.0.0",
    description=(
        "Brand governance for content before publication. Submit a draft, get "
        "evidence-backed findings, fix them, and route the exact version to a human "
        "approver. Nothing is auto-published."
    ),
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(content.router)
app.include_router(brand.router)
app.include_router(visual.router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Keep-warm endpoint. Also used by the frontend to show 'waking up the server'."""
    db = get_db()
    ok = db.healthcheck()
    return {
        "status": "ok" if ok else "degraded",
        "database": "up" if ok else "down",
        "llm_enabled": get_settings().llm_enabled,
        "version": app.version,
    }


@app.get("/", tags=["ops"])
def root() -> dict:
    return {
        "name": "BrandShield AI API",
        "docs": "/docs",
        "health": "/health",
    }
