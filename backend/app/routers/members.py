"""Workspace member administration backed by Supabase Auth invitations."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import Principal, require_role
from ..config import get_settings
from ..db import Database, get_db
from ..models import MemberInviteRequest, MemberUpdateRequest, WorkspaceMemberOut
from ..seed import now_iso

log = logging.getLogger("brandshield.members")
router = APIRouter(prefix="/api/admin/members", tags=["members"])


def _supabase_request(method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Member administration requires Supabase service-role configuration.",
        )
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.request(
            method,
            f"{settings.supabase_url}/auth/v1/{path.lstrip('/')}",
            headers=headers,
            json=payload,
            timeout=15,
        )
    except httpx.RequestError as exc:
        log.error("Supabase member administration request failed: %s", exc.__class__.__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the authentication provider. No membership change was made.",
        ) from exc

    if response.is_error:
        log.warning("Supabase member administration returned HTTP %s", response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The authentication provider rejected this member operation. No membership change was made.",
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The authentication provider returned an unreadable response.",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The authentication provider returned an unexpected response.",
        )
    return data


@router.get("", response_model=list[WorkspaceMemberOut])
def list_members(
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> list[WorkspaceMemberOut]:
    rows = db.query(
        "SELECT user_id, email, display_name, role, is_active, created_at"
        " FROM memberships WHERE workspace_id = ? AND user_id NOT LIKE 'demo-%'"
        " ORDER BY display_name, email",
        (principal.workspace_id,),
    )
    return [
        WorkspaceMemberOut(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.post("", response_model=WorkspaceMemberOut, status_code=status.HTTP_201_CREATED)
def invite_member(
    payload: MemberInviteRequest,
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> WorkspaceMemberOut:
    existing = db.query_one(
        "SELECT id FROM memberships WHERE workspace_id = ? AND lower(email) = ?",
        (principal.workspace_id, payload.email),
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email already has a workspace membership.",
        )

    settings = get_settings()
    redirect_to = f"{settings.app_frontend_url}/set-password"
    invite_path = "invite?" + urlencode({"redirect_to": redirect_to})
    user = _supabase_request(
        "POST",
        invite_path,
        {
            "email": payload.email,
            "data": {"display_name": payload.display_name},
        },
    )
    user_id = user.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The provider accepted the invitation but did not return a user ID.",
        )

    created_at = now_iso()
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, email, display_name, role,"
        " is_active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
        (
            principal.workspace_id,
            user_id,
            payload.email,
            payload.display_name,
            payload.role,
            created_at,
        ),
    )
    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id,"
        " detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            principal.workspace_id,
            principal.display_name,
            "member.invited",
            "membership",
            None,
            f"Invited {payload.email} as {payload.role}.",
            created_at,
        ),
    )
    return WorkspaceMemberOut(
        user_id=user_id,
        email=payload.email,
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
        created_at=created_at,
    )


@router.patch("/{user_id}", response_model=WorkspaceMemberOut)
def update_member(
    user_id: str,
    payload: MemberUpdateRequest,
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> WorkspaceMemberOut:
    if payload.role is None and payload.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide a role or active-state change.",
        )

    member = db.query_one(
        "SELECT id, user_id, email, display_name, role, is_active, created_at"
        " FROM memberships WHERE workspace_id = ? AND user_id = ?"
        " AND user_id NOT LIKE 'demo-%'",
        (principal.workspace_id, user_id),
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    if payload.is_active is False and user_id == principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account.",
        )
    resulting_role = payload.role or member["role"]
    resulting_active = payload.is_active if payload.is_active is not None else bool(member["is_active"])
    if (
        member["role"] == "admin"
        and bool(member["is_active"])
        and (resulting_role != "admin" or not resulting_active)
    ):
        active_admins = db.query_one(
            "SELECT COUNT(*) AS count FROM memberships"
            " WHERE workspace_id = ? AND role = 'admin' AND is_active = 1",
            (principal.workspace_id,),
        )
        if active_admins and int(active_admins["count"]) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active admin cannot be deactivated or demoted.",
            )

    deactivating = payload.is_active is False and bool(member["is_active"])
    if deactivating:
        db.execute(
            "UPDATE memberships SET role = ?, is_active = 0"
            " WHERE workspace_id = ? AND user_id = ?",
            (resulting_role, principal.workspace_id, user_id),
        )
        now = now_iso()
        db.insert(
            "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id,"
            " detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                principal.workspace_id,
                principal.display_name,
                "member.updated",
                "membership",
                int(member["id"]),
                f"Deactivated {member['email'] or user_id}.",
                now,
            ),
        )
        try:
            _supabase_request("PUT", f"admin/users/{user_id}", {"ban_duration": "876000h"})
        except HTTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "BrandShield access is disabled, but the authentication provider could not "
                    "disable future sign-ins. Retry or disable this user in Supabase."
                ),
            ) from exc
        return WorkspaceMemberOut(
            user_id=user_id,
            email=member["email"],
            display_name=member["display_name"],
            role=resulting_role,
            is_active=False,
            created_at=member["created_at"],
        )

    if payload.is_active is True and not bool(member["is_active"]):
        _supabase_request(
            "PUT",
            f"admin/users/{user_id}",
            {"ban_duration": "none"},
        )

    db.execute(
        "UPDATE memberships SET role = ?, is_active = ? WHERE workspace_id = ? AND user_id = ?",
        (resulting_role, int(resulting_active), principal.workspace_id, user_id),
    )
    now = now_iso()
    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id,"
        " detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            principal.workspace_id,
            principal.display_name,
            "member.updated",
            "membership",
            int(member["id"]),
            f"Updated {member['email'] or user_id}: role={resulting_role}, active={resulting_active}.",
            now,
        ),
    )
    return WorkspaceMemberOut(
        user_id=user_id,
        email=member["email"],
        display_name=member["display_name"],
        role=resulting_role,
        is_active=resulting_active,
        created_at=member["created_at"],
    )
