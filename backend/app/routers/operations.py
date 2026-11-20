"""Workspace operations: assignments, analytics, API keys and webhooks."""
from __future__ import annotations

import csv
import hashlib
import secrets
from io import StringIO

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from ..auth import Principal, require_role
from ..db import Database, get_db
from ..models import ApiKeyCreate, ReviewAssignmentUpdate, WebhookCreate
from ..operations import safe_webhook_url
from ..seed import now_iso

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.put("/content/{item_id}/assignment")
def update_assignment(
    item_id: int,
    payload: ReviewAssignmentUpdate,
    principal: Principal = Depends(require_role("manager", "admin")),
    db: Database = Depends(get_db),
) -> dict:
    item = db.query_one(
        "SELECT id FROM content_items WHERE id=? AND workspace_id=?",
        (item_id, principal.workspace_id),
    )
    if not item:
        raise HTTPException(status_code=404, detail="That submission was not found.")
    if payload.assignee_user_id:
        member = db.query_one(
            "SELECT user_id, display_name FROM memberships"
            " WHERE workspace_id=? AND user_id=? AND is_active=1",
            (principal.workspace_id, payload.assignee_user_id),
        )
        if not member:
            raise HTTPException(status_code=422, detail="Choose an active workspace member.")
        assignee_name = member["display_name"]
    else:
        assignee_name = payload.assignee_name
    db.insert(
        "INSERT INTO review_assignments"
        " (content_item_id, workspace_id, assignee_user_id, assignee_name, due_at, updated_by, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(content_item_id) DO UPDATE SET"
        " assignee_user_id=excluded.assignee_user_id,"
        " assignee_name=excluded.assignee_name, due_at=excluded.due_at,"
        " updated_by=excluded.updated_by, updated_at=excluded.updated_at",
        (
            item_id,
            principal.workspace_id,
            payload.assignee_user_id,
            assignee_name,
            payload.due_at,
            principal.display_name,
            now_iso(),
        ),
    )
    db.insert(
        "INSERT INTO audit_events"
        " (workspace_id, actor, action, entity_type, entity_id, detail, created_at)"
        " VALUES (?, ?, 'submission.assigned', 'content_item', ?, ?, ?)",
        (
            principal.workspace_id,
            principal.display_name,
            item_id,
            f"Assigned to {assignee_name or 'unassigned'}; due {payload.due_at or 'unspecified'}",
            now_iso(),
        ),
    )
    row = db.query_one(
        "SELECT * FROM review_assignments WHERE content_item_id=? AND workspace_id=?",
        (item_id, principal.workspace_id),
    )
    return dict(row or {})


@router.get("/analytics")
def analytics(
    principal: Principal = Depends(require_role("manager", "admin")),
    db: Database = Depends(get_db),
) -> dict:
    submissions = db.query_one(
        "SELECT COUNT(*) AS count FROM content_items WHERE workspace_id=?",
        (principal.workspace_id,),
    )
    approved = db.query_one(
        "SELECT COUNT(*) AS count FROM approvals a"
        " JOIN content_versions v ON v.id=a.version_id"
        " WHERE a.workspace_id=? AND a.decision='approved'",
        (principal.workspace_id,),
    )
    findings = db.query_one(
        "SELECT COUNT(*) AS count FROM findings f"
        " JOIN content_versions v ON v.id=f.version_id"
        " WHERE f.workspace_id=?",
        (principal.workspace_id,),
    )
    usage = db.query(
        "SELECT event_type, SUM(quantity) AS quantity"
        " FROM usage_events WHERE workspace_id=?"
        " GROUP BY event_type ORDER BY event_type",
        (principal.workspace_id,),
    )
    return {
        "submissions": int(submissions["count"] or 0),
        "approved_versions": int(approved["count"] or 0),
        "findings": int(findings["count"] or 0),
        "usage": usage,
    }


@router.get("/exports/audit.csv")
def export_audit(
    principal: Principal = Depends(require_role("manager", "admin")),
    db: Database = Depends(get_db),
) -> Response:
    rows = db.query(
        "SELECT created_at, actor, action, entity_type, entity_id, detail"
        " FROM audit_events WHERE workspace_id=? ORDER BY created_at DESC",
        (principal.workspace_id,),
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["created_at", "actor", "action", "entity_type", "entity_id", "detail"])
    for row in rows:
        writer.writerow([
            row["created_at"], row["actor"], row["action"], row["entity_type"],
            row["entity_id"], row["detail"],
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="brandshield-audit.csv"'},
    )


@router.post("/api-keys")
def create_api_key(
    payload: ApiKeyCreate,
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> dict:
    raw = f"bs_{secrets.token_urlsafe(32)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    prefix = raw[:10]
    db.insert(
        "INSERT INTO api_keys"
        " (workspace_id, name, key_prefix, key_hash, scopes, is_active, created_by, created_at)"
        " VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
        (
            principal.workspace_id,
            payload.name.strip(),
            prefix,
            digest,
            ",".join(payload.scopes),
            principal.display_name,
            now_iso(),
        ),
    )
    db.insert(
        "INSERT INTO audit_events"
        " (workspace_id, actor, action, entity_type, entity_id, detail, created_at)"
        " VALUES (?, ?, 'api_key.created', 'api_key', NULL, ?, ?)",
        (
            principal.workspace_id,
            principal.display_name,
            f"Created API key '{payload.name.strip()}'.",
            now_iso(),
        ),
    )
    return {
        "key": raw,
        "name": payload.name.strip(),
        "prefix": prefix,
        "scopes": payload.scopes,
        "warning": "Copy this key now. BrandShield stores only its hash.",
    }


@router.get("/api-keys")
def list_api_keys(
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> list[dict]:
    return db.query(
        "SELECT id, name, key_prefix, scopes, is_active, created_by, created_at"
        " FROM api_keys WHERE workspace_id=? ORDER BY id DESC",
        (principal.workspace_id,),
    )


@router.post("/webhooks")
def create_webhook(
    payload: WebhookCreate,
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> dict:
    if not safe_webhook_url(payload.url):
        raise HTTPException(
            status_code=422,
            detail="Webhook URLs must be public HTTP(S) endpoints, not local or private targets.",
        )
    db.insert(
        "INSERT INTO webhook_endpoints"
        " (workspace_id, name, url, secret, events, is_active, created_at)"
        " VALUES (?, ?, ?, ?, ?, 1, ?)",
        (
            principal.workspace_id,
            payload.name.strip(),
            payload.url,
            payload.secret,
            ",".join(payload.events),
            now_iso(),
        ),
    )
    row = db.query_one(
        "SELECT id, name, url, events, is_active, created_at"
        " FROM webhook_endpoints WHERE workspace_id=? ORDER BY id DESC LIMIT 1",
        (principal.workspace_id,),
    )
    return dict(row or {})


@router.get("/webhooks")
def list_webhooks(
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> list[dict]:
    return db.query(
        "SELECT id, name, url, events, is_active, created_at"
        " FROM webhook_endpoints WHERE workspace_id=? ORDER BY id DESC",
        (principal.workspace_id,),
    )


@router.get("/notifications")
def notification_status(
    principal: Principal = Depends(require_role("admin")),
    db: Database = Depends(get_db),
) -> list[dict]:
    return db.query(
        "SELECT id, recipient, subject, status, attempts, last_error, sent_at, created_at"
        " FROM notification_outbox WHERE workspace_id=? ORDER BY id DESC",
        (principal.workspace_id,),
    )
