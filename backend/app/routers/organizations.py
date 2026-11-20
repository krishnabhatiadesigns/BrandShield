"""Organization onboarding and brand workspace management."""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import Principal, get_verified_identity, require_role
from ..config import get_settings
from ..db import Database, get_db
from ..models import (
    OrganizationCreateRequest,
    OrganizationCreateResponse,
    WorkspaceCreateRequest,
    WorkspaceOut,
)
from ..seed import now_iso

router = APIRouter(prefix="/api", tags=["organizations"])


def _insert_id(conn, db: Database) -> int:
    if db.is_postgres:
        return int(conn.execute("SELECT lastval()").fetchone()[0])
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "brand"


@router.post(
    "/organizations",
    response_model=OrganizationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    payload: OrganizationCreateRequest,
    identity: dict = Depends(get_verified_identity),
    db: Database = Depends(get_db),
) -> OrganizationCreateResponse:
    if not get_settings().allow_organization_creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization self-service onboarding is disabled.",
        )

    auth_user_id = identity["sub"]
    existing_membership = db.query_one(
        "SELECT id FROM memberships WHERE user_id = ? AND is_active = 1 LIMIT 1",
        (auth_user_id,),
    )
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account already belongs to a workspace. Ask an admin to add another brand.",
        )

    now = now_iso()
    suffix = uuid.uuid4().hex[:8]
    organization_slug = f"{_slug(payload.name)}-{suffix}"
    brand_name = payload.brand_name or f"{payload.name} Brand"
    workspace_slug = f"{_slug(brand_name)}-{suffix}"
    email = identity.get("email")
    if not isinstance(email, str):
        email = None

    with db.tx() as conn:
        conn.execute(
            "INSERT INTO organizations (name, slug, created_at) VALUES (?, ?, ?)",
            (payload.name, organization_slug, now),
        )
        organization_id = _insert_id(conn, db)
        conn.execute(
            "INSERT INTO workspaces (organization_id, name, slug, created_at)"
            " VALUES (?, ?, ?, ?)",
            (organization_id, brand_name, workspace_slug, now),
        )
        workspace_id = _insert_id(conn, db)
        conn.execute(
            "INSERT INTO memberships (workspace_id, user_id, email, display_name, role,"
            " is_active, created_at) VALUES (?, ?, ?, ?, 'admin', 1, ?)",
            (workspace_id, auth_user_id, email, payload.display_name, now),
        )
        conn.execute(
            "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id,"
            " detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                workspace_id,
                payload.display_name,
                "organization.created",
                "organization",
                organization_id,
                f"Created organization {payload.name} and its first brand.",
                now,
            ),
        )
    return OrganizationCreateResponse(
        organization_id=organization_id,
        organization_name=payload.name,
        workspace_id=workspace_id,
        workspace_name=brand_name,
        role="admin",
    )


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    principal: Principal = Depends(require_role("creator", "manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> list[WorkspaceOut]:
    rows = db.query(
        """
        SELECT w.id, w.name, w.organization_id, o.name AS organization_name, m.role
        FROM memberships m
        JOIN workspaces w ON w.id = m.workspace_id
        JOIN organizations o ON o.id = w.organization_id
        WHERE m.user_id = ? AND m.is_active = 1
        ORDER BY o.name, w.name, w.id
        """,
        (principal.user_id,),
    )
    return [WorkspaceOut(**row) for row in rows]


@router.post(
    "/workspaces",
    response_model=WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_brand(
    payload: WorkspaceCreateRequest,
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> WorkspaceOut:
    current = db.query_one(
        "SELECT w.organization_id, o.name AS organization_name"
        " FROM workspaces w JOIN organizations o ON o.id = w.organization_id WHERE w.id = ?",
        (principal.workspace_id,),
    )
    if not current or current["organization_id"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workspace has not been linked to an organization.",
        )

    now = now_iso()
    slug = f"{_slug(payload.name)}-{uuid.uuid4().hex[:8]}"
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO workspaces (organization_id, name, slug, created_at)"
            " VALUES (?, ?, ?, ?)",
            (int(current["organization_id"]), payload.name, slug, now),
        )
        workspace_id = _insert_id(conn, db)
        conn.execute(
            "INSERT INTO memberships (workspace_id, user_id, email, display_name,"
            " role, is_active, created_at) VALUES (?, ?, NULL, ?, 'admin', 1, ?)",
            (workspace_id, principal.user_id, principal.display_name, now),
        )
        conn.execute(
            "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id,"
            " detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                workspace_id,
                principal.display_name,
                "brand.created",
                "workspace",
                workspace_id,
                f"Created brand {payload.name}.",
                now,
            ),
        )
    return WorkspaceOut(
        id=workspace_id,
        name=payload.name,
        role="admin",
        organization_id=int(current["organization_id"]),
        organization_name=current["organization_name"],
    )
