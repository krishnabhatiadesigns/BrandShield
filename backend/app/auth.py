"""Authentication and role enforcement.

Two paths, both resolved server-side:

  * Demo sessions: the landing page calls ``POST /api/demo/session`` with a role and
    receives an opaque token. The token maps to a real membership row, so role
    checks are identical to production.
  * Supabase Auth (optional): a Supabase access token is verified and mapped to a
    membership by email. If Supabase is not configured this path is simply unused.

Roles are enforced here, not in the UI. Every router depends on ``require_role``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header, HTTPException, status

from .config import get_settings
from .db import Database, get_db
from .seed import DEMO_MEMBERS, DEMO_SLUG, now_iso, new_demo_token

log = logging.getLogger("brandshield.auth")

ROLE_RANK = {"creator": 1, "manager": 2, "approver": 3, "admin": 4}


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


def _verify_supabase_jwt(token: str) -> dict | None:
    """Verify a Supabase HS256 JWT using the project's JWT secret."""
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        return None
    try:
        import base64

        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected = hmac.new(
            settings.supabase_jwt_secret.encode(), signing_input, hashlib.sha256
        ).digest()
        actual = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        if not hmac.compare_digest(expected, actual):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
        if payload.get("exp") and int(payload["exp"]) < int(time.time()):
            return None
        return payload
    except Exception as exc:  # noqa: BLE001
        log.warning("Supabase token verification failed: %s", exc)
        return None


def resolve_principal(
    db: Database,
    authorization: str | None,
    demo_token: str | None,
) -> Principal:
    token = demo_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No session. Choose a demo role on the landing page to continue.",
        )

    # --- demo session ------------------------------------------------------
    row = db.query_one(
        """
        SELECT s.token, s.role, s.display_name, s.workspace_id, w.name AS workspace_name
        FROM demo_sessions s JOIN workspaces w ON w.id = s.workspace_id
        WHERE s.token = ?
        """,
        (token,),
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

    # --- supabase session --------------------------------------------------
    payload = _verify_supabase_jwt(token)
    if payload:
        email = payload.get("email")
        if email:
            member = db.query_one(
                """
                SELECT m.user_id, m.display_name, m.role, m.workspace_id, w.name AS workspace_name
                FROM memberships m JOIN workspaces w ON w.id = m.workspace_id
                WHERE lower(m.email) = lower(?)
                """,
                (email,),
            )
            if member:
                return Principal(
                    user_id=member["user_id"],
                    display_name=member["display_name"],
                    role=member["role"],
                    workspace_id=int(member["workspace_id"]),
                    workspace_name=member["workspace_name"],
                    is_demo=False,
                )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not a member of any workspace yet.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="That session has expired. Choose a demo role to start again.",
    )


def get_principal(
    authorization: str | None = Header(default=None),
    x_demo_token: str | None = Header(default=None),
    db: Database = Depends(get_db),
) -> Principal:
    return resolve_principal(db, authorization, x_demo_token)


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
