"""Supabase and demo-session authentication with server-side role enforcement."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Callable

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient, PyJWTError
from jwt.exceptions import PyJWKClientConnectionError

from .config import get_settings
from .db import Database, get_db
from .seed import DEMO_MEMBERS, DEMO_SLUG, now_iso, new_demo_token

ROLE_RANK = {"creator": 1, "manager": 2, "approver": 3, "admin": 4}
AUTHENTICATED_ROLE = "authenticated"


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(
        f"{url}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        timeout=5,
    )


def _verify_supabase_token(token: str) -> dict:
    settings = get_settings()
    if not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured on this server.",
        )

    issuer = f"{settings.supabase_url}/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256" and settings.supabase_jwt_secret:
            key = settings.supabase_jwt_secret
        elif algorithm in {"ES256", "RS256"}:
            key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token).key
        else:
            raise PyJWTError("Unsupported Supabase JWT signing algorithm.")
        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience=AUTHENTICATED_ROLE,
            issuer=issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except PyJWKClientConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider keys are temporarily unavailable. Please retry.",
        ) from exc
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your sign-in session is invalid or expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if claims.get("role") != AUTHENTICATED_ROLE or not isinstance(claims.get("sub"), str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your sign-in session is not a user session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


@dataclass
class Principal:
    user_id: str
    display_name: str
    role: str
    workspace_id: int
    workspace_name: str
    is_demo: bool

    def has_role(self, *roles: str) -> bool:
        return self.role in roles


def _demo_workspace(db: Database) -> dict:
    ws = db.query_one("SELECT id, name FROM workspaces WHERE slug = ?", (DEMO_SLUG,))
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The demo workspace is still being prepared. Please retry in a moment.",
        )
    return ws


def create_demo_session(db: Database, role: str) -> dict:
    if role not in {"creator", "manager", "approver"}:
        raise HTTPException(status_code=400, detail="Unknown demo role.")
    db.execute("DELETE FROM demo_sessions WHERE created_at < ?", (_session_cutoff(),))
    ws = _demo_workspace(db)
    member = next(m for m in DEMO_MEMBERS if m[3] == role)
    token = new_demo_token()
    db.insert(
        "INSERT INTO demo_sessions (token, workspace_id, role, display_name, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (token, int(ws["id"]), role, member[2], now_iso()),
    )
    return {
        "token": token,
        "role": role,
        "display_name": member[2],
        "workspace_id": int(ws["id"]),
        "workspace_name": ws["name"],
    }


def _session_cutoff() -> str:
    ttl = get_settings().demo_session_ttl_hours
    return (datetime.now(timezone.utc) - timedelta(hours=ttl)).replace(microsecond=0).isoformat()


def _extract_token(authorization: str | None, demo_token: str | None) -> str | None:
    if demo_token:
        return demo_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def get_verified_identity(
    authorization: str | None = Header(default=None),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified Supabase sign-in is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified Supabase sign-in is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _verify_supabase_token(token)


def resolve_principal(
    db: Database,
    authorization: str | None,
    demo_token: str | None,
    workspace_id: int | None = None,
) -> Principal:
    token = _extract_token(authorization, demo_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No session. Please sign in to continue.",
        )

    if demo_token:
        row = db.query_one(
            """
            SELECT s.token, s.role, s.display_name, s.workspace_id, w.name AS workspace_name
            FROM demo_sessions s JOIN workspaces w ON w.id = s.workspace_id
            WHERE s.token = ? AND s.created_at >= ?
            """,
            (token, _session_cutoff()),
        )
        if row:
            return Principal(
                user_id=f"demo-{row['role']}",
                display_name=row["display_name"],
                role=row["role"],
                workspace_id=int(row["workspace_id"]),
                workspace_name=row["workspace_name"],
                is_demo=True,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That demo session has expired. Please start again.",
        )

    claims = _verify_supabase_token(token)
    membership = db.query_one(
        """
        SELECT m.id AS membership_id, m.user_id, m.display_name, m.role, m.workspace_id,
               w.name AS workspace_name
        FROM memberships m
        JOIN workspaces w ON w.id = m.workspace_id
        WHERE m.user_id = ? AND m.is_active = 1
          AND (? IS NULL OR m.workspace_id = ?)
        ORDER BY m.id
        LIMIT 1
        """,
        (claims["sub"], workspace_id, workspace_id),
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not an active member of a BrandShield workspace.",
        )
    return Principal(
        user_id=membership["user_id"],
        display_name=membership["display_name"],
        role=membership["role"],
        workspace_id=int(membership["workspace_id"]),
        workspace_name=membership["workspace_name"],
        is_demo=False,
    )


def revoke_demo_session(
    db: Database,
    authorization: str | None,
    demo_token: str | None,
) -> None:
    token = _extract_token(authorization, demo_token)
    if token:
        db.execute("DELETE FROM demo_sessions WHERE token = ?", (token,))


def get_principal(
    authorization: str | None = Header(default=None),
    x_demo_token: str | None = Header(default=None),
    x_workspace_id: int | None = Header(default=None),
    db: Database = Depends(get_db),
) -> Principal:
    return resolve_principal(db, authorization, x_demo_token, x_workspace_id)


def require_role(*roles: str) -> Callable[..., Principal]:
    """Dependency factory enforcing that the caller holds one of ``roles``."""

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This action needs the {' or '.join(roles)} role. "
                    f"You are signed in as {principal.role}."
                ),
            )
        return principal

    return _dep
