"""Content submission, review, fix decisions, versioning and approval."""
from __future__ import annotations

import json
import mimetypes
import secrets
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from ..auth import Principal, get_principal, require_role
from ..db import Database, get_db
from ..models import (
    ApprovalOut,
    ApprovalRequest,
    CommentCreate,
    CommentOut,
    ContentCreate,
    ContentDetail,
    ContentSummary,
    DraftEditRequest,
    FindingDecisionRequest,
    FindingOut,
    ReviewRunOut,
    ReviewAssignmentOut,
    SampleInfo,
    SendBackRequest,
    VersionOut,
)
from ..pipeline import run_review
from ..samples import SAMPLES
from ..seed import now_iso
from ..storage import StorageError, get_private_object, put_private_object
from ..text import ExtractionError, extract_upload
from ..operations import queue_notification, queue_webhook, record_usage

router = APIRouter(prefix="/api", tags=["content"])

STATUS_DRAFT = "Draft"
STATUS_AI_COMPLETE = "AI Review Complete"
STATUS_CHANGES_REQUIRED = "Changes Required"
STATUS_RESUBMITTED = "Resubmitted"
STATUS_MANAGER_REVIEW = "Manager Review"
STATUS_APPROVER_REVIEW = "Approver Review"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _audit(
    db: Database,
    ws_id: int,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int | None,
    detail: str | None = None,
) -> None:
    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id, detail, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ws_id, actor, action, entity_type, entity_id, detail, now_iso()),
    )


def _get_item(db: Database, ws_id: int, item_id: int) -> dict[str, Any]:
    item = db.query_one(
        "SELECT * FROM content_items WHERE id = ? AND workspace_id = ?", (item_id, ws_id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="That submission was not found.")
    return item


def _get_version(db: Database, ws_id: int, version_id: int) -> dict[str, Any]:
    ver = db.query_one(
        "SELECT * FROM content_versions WHERE id = ? AND workspace_id = ?", (version_id, ws_id)
    )
    if not ver:
        raise HTTPException(status_code=404, detail="That version was not found.")
    return ver


def _finding_rows(db: Database, ws_id: int, version_id: int) -> list[dict[str, Any]]:
    return db.query(
        """
        SELECT f.*, p.text AS source_quote, p.source AS source_title
        FROM findings f
        LEFT JOIN passages p ON p.id = f.source_passage_id AND p.workspace_id = f.workspace_id
        WHERE f.version_id = ? AND f.workspace_id = ?
        ORDER BY CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                 COALESCE(f.span_start, 999999)
        """,
        (version_id, ws_id),
    )


def _review_run(db: Database, ws_id: int, version_id: int) -> dict[str, Any] | None:
    return db.query_one(
        "SELECT * FROM review_runs WHERE version_id = ? AND workspace_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (version_id, ws_id),
    )


def _detail(db: Database, ws_id: int, item: dict[str, Any]) -> ContentDetail:
    version = None
    findings: list[FindingOut] = []
    run = None
    comments: list[CommentOut] = []
    approvals: list[ApprovalOut] = []
    assignment_row = db.query_one(
        "SELECT * FROM review_assignments WHERE content_item_id = ? AND workspace_id = ?",
        (int(item["id"]), ws_id),
    )
    assignment = ReviewAssignmentOut(**assignment_row) if assignment_row else None

    if item.get("current_version_id"):
        ver = db.query_one(
            "SELECT * FROM content_versions WHERE id = ? AND workspace_id = ?",
            (int(item["current_version_id"]), ws_id),
        )
        if ver:
            version = VersionOut(
                id=int(ver["id"]),
                version_no=int(ver["version_no"]),
                body=ver["body"],
                status=ver["status"],
                review_state=ver["review_state"],
                created_at=ver["created_at"],
                created_by=ver["created_by"],
            )
            findings = [FindingOut(**{k: r[k] for k in FindingOut.model_fields if k in r})
                        for r in _finding_rows(db, ws_id, int(ver["id"]))]
            rr = _review_run(db, ws_id, int(ver["id"]))
            if rr:
                run = ReviewRunOut(
                    llm_status=rr["llm_status"],
                    llm_message=rr["llm_message"] or "",
                    deterministic_count=int(rr["deterministic_count"]),
                    llm_count=int(rr["llm_count"]),
                    duration_ms=int(rr["duration_ms"]),
                )
            comments = [
                CommentOut(id=int(c["id"]), author=c["author"], body=c["body"], created_at=c["created_at"])
                for c in db.query(
                    "SELECT * FROM comments WHERE version_id = ? AND workspace_id = ? ORDER BY id",
                    (int(ver["id"]), ws_id),
                )
            ]
            approvals = [
                ApprovalOut(
                    id=int(a["id"]),
                    version_id=int(a["version_id"]),
                    decision=a["decision"],
                    reason=a["reason"],
                    reviewer=a["reviewer"],
                    high_severity_signoff=bool(a["high_severity_signoff"]),
                    created_at=a["created_at"],
                )
                for a in db.query(
                    "SELECT * FROM approvals WHERE version_id = ? AND workspace_id = ? ORDER BY id",
                    (int(ver["id"]), ws_id),
                )
            ]

    return ContentDetail(
        id=int(item["id"]),
        title=item["title"],
        content_type=item["content_type"],
        status=item["status"],
        created_by=item["created_by"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        source_filename=item.get("source_filename"),
        assignment=assignment,
        current_version=version,
        findings=findings,
        review_run=run,
        comments=comments,
        approvals=approvals,
    )


def _summary(db: Database, ws_id: int, item: dict[str, Any]) -> ContentSummary:
    version_no = 0
    open_high = 0
    needs_verification = 0
    if item.get("current_version_id"):
        ver = db.query_one(
            "SELECT version_no FROM content_versions WHERE id = ? AND workspace_id = ?",
            (int(item["current_version_id"]), ws_id),
        )
        if ver:
            version_no = int(ver["version_no"])
            counts = db.query_one(
                """
                SELECT
                  SUM(CASE WHEN severity = 'high' AND creator_decision IN ('pending','rejected')
                           THEN 1 ELSE 0 END) AS open_high,
                  SUM(CASE WHEN evidence_status = 'needs_verification' THEN 1 ELSE 0 END) AS nv
                FROM findings WHERE version_id = ? AND workspace_id = ?
                """,
                (int(item["current_version_id"]), ws_id),
            )
            if counts:
                open_high = int(counts["open_high"] or 0)
                needs_verification = int(counts["nv"] or 0)
    return ContentSummary(
        id=int(item["id"]),
        title=item["title"],
        content_type=item["content_type"],
        status=item["status"],
        created_by=item["created_by"],
        updated_at=item["updated_at"],
        version_no=version_no,
        open_high=open_high,
        needs_verification=needs_verification,
        assigned_to=item.get("assigned_to"),
        due_at=item.get("due_at"),
    )


def _apply_review(
    db: Database, ws_id: int, item_id: int, version_id: int, body: str, content_type: str,
    actor: str, use_llm: bool = True,
) -> dict[str, Any]:
    """Run the pipeline and persist findings + run metadata for one version.

    Re-running a check is an *analysis refresh*, not a workflow transition. It
    must not move the version backwards in the approval chain, otherwise an
    approver who re-runs the check would lose their turn. Decisions already made
    on findings that still exist are preserved.
    """
    outcome = run_review(db, ws_id, body, content_type, use_llm=use_llm)
    ts = now_iso()

    # Remember decisions so a re-run does not silently discard the reviewer's work.
    previous = db.query(
        "SELECT rule, span_start, span_end, creator_decision, edited_text"
        " FROM findings WHERE version_id = ? AND workspace_id = ?"
        " AND creator_decision != 'pending'",
        (version_id, ws_id),
    )
    decided = {
        (r["rule"], r["span_start"], r["span_end"]): (r["creator_decision"], r["edited_text"])
        for r in previous
    }

    with db.tx() as conn:
        conn.execute("DELETE FROM findings WHERE version_id = ? AND workspace_id = ?", (version_id, ws_id))
        for f in outcome.findings:
            decision, edited_text = decided.get(
                (f.rule, f.span_start, f.span_end), ("pending", None)
            )
            conn.execute(
                "INSERT INTO findings (version_id, workspace_id, category, severity, span_start,"
                " span_end, affected_text, rule, explanation, source_passage_id, evidence_status,"
                " source_rule_id, source_rule_version, source_rule_title, source_rule_text,"
                " confidence, suggestion, creator_decision, edited_text, detector, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    version_id, ws_id, f.category, f.severity, f.span_start, f.span_end,
                    f.affected_text, f.rule, f.explanation, f.source_passage_id,
                    f.evidence_status, f.source_rule_id, f.source_rule_version,
                    f.source_rule_title, f.source_rule_text, f.confidence, f.suggestion,
                    decision, edited_text, f.detector, ts,
                ),
            )
        conn.execute(
            "INSERT INTO review_runs (version_id, workspace_id, llm_status, llm_message,"
            " deterministic_count, llm_count, duration_ms, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                version_id, ws_id, outcome.llm_status, outcome.llm_message,
                outcome.deterministic_count, outcome.llm_count, outcome.duration_ms, ts,
            ),
        )
        # Only mark the version as reviewed. The workflow status is left alone so
        # a re-run never pulls a version out of Manager/Approver Review. A brand
        # new draft does advance to "AI Review Complete" on its first check.
        conn.execute(
            "UPDATE content_versions SET review_state = 'reviewed' WHERE id = ?", (version_id,)
        )
        current = conn.execute(
            "SELECT status FROM content_versions WHERE id = ?", (version_id,)
        ).fetchone()
        current_status = current[0] if current else None
        if current_status in (STATUS_DRAFT, STATUS_CHANGES_REQUIRED):
            conn.execute(
                "UPDATE content_versions SET status = ? WHERE id = ?",
                (STATUS_AI_COMPLETE, version_id),
            )
            conn.execute(
                "UPDATE content_items SET status = ?, updated_at = ? WHERE id = ?",
                (STATUS_AI_COMPLETE, ts, item_id),
            )
        else:
            conn.execute(
                "UPDATE content_items SET updated_at = ? WHERE id = ?", (ts, item_id)
            )
    _audit(
        db, ws_id, actor, "review.completed", "version", version_id,
        f"{len(outcome.findings)} findings ({outcome.llm_status})",
    )
    record_usage(db, ws_id, "review_run", actor)
    queue_webhook(
        db,
        ws_id,
        "review.completed",
        {
            "item_id": item_id,
            "version_id": version_id,
            "finding_count": len(outcome.findings),
            "llm_status": outcome.llm_status,
        },
    )
    return {
        "llm_status": outcome.llm_status,
        "llm_message": outcome.llm_message,
        "deterministic_count": outcome.deterministic_count,
        "llm_count": outcome.llm_count,
        "duration_ms": outcome.duration_ms,
        "validation_notes": outcome.validation_notes,
    }


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@router.get("/samples", response_model=list[SampleInfo], tags=["demo"])
def list_samples() -> list[SampleInfo]:
    return [SampleInfo(**s) for s in SAMPLES]


@router.get("/content", response_model=list[ContentSummary])
def list_content(
    principal: Principal = Depends(get_principal), db: Database = Depends(get_db)
) -> list[ContentSummary]:
    rows = db.query(
        "SELECT ci.*, ra.assignee_name AS assigned_to, ra.due_at AS due_at"
        " FROM content_items ci LEFT JOIN review_assignments ra"
        " ON ra.content_item_id = ci.id AND ra.workspace_id = ci.workspace_id"
        " WHERE ci.workspace_id = ? ORDER BY ci.updated_at DESC, ci.id DESC",
        (principal.workspace_id,),
    )
    return [_summary(db, principal.workspace_id, r) for r in rows]


@router.get("/content/queue", response_model=list[ContentSummary])
def review_queue(
    principal: Principal = Depends(require_role("manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> list[ContentSummary]:
    """Only the versions actually waiting on this role."""
    if principal.role == "approver":
        waiting = (STATUS_APPROVER_REVIEW,)
    else:
        waiting = (STATUS_MANAGER_REVIEW, STATUS_RESUBMITTED)
    placeholders = ",".join("?" for _ in waiting)
    rows = db.query(
        "SELECT ci.*, ra.assignee_name AS assigned_to, ra.due_at AS due_at"
        " FROM content_items ci LEFT JOIN review_assignments ra"
        " ON ra.content_item_id = ci.id AND ra.workspace_id = ci.workspace_id"
        f" WHERE ci.workspace_id = ? AND ci.status IN ({placeholders})"
        " ORDER BY ci.updated_at DESC, ci.id DESC",
        (principal.workspace_id, *waiting),
    )
    return [_summary(db, principal.workspace_id, r) for r in rows]


@router.post("/content", response_model=ContentDetail, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate,
    principal: Principal = Depends(require_role("creator", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    return _create_content(payload, principal, db)


def _create_content(
    payload: ContentCreate,
    principal: Principal,
    db: Database,
    source_file: tuple[str, str, str, int] | None = None,
) -> ContentDetail:
    """Only creators author content.

    Separation of duties: the person who writes a draft must not be the person
    who reviews or approves it, so managers and approvers cannot create
    submissions at all.
    """
    ts = now_iso()
    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO content_items (workspace_id, title, content_type, status, created_by,"
            " source_object_key, source_filename, source_content_type, source_size,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (principal.workspace_id, payload.title.strip(), payload.content_type,
             STATUS_DRAFT, principal.user_id,
             *(source_file or (None, None, None, None)), ts, ts),
        )
        item_id = int(cur.lastrowid) if not db.is_postgres else int(
            conn.execute("SELECT lastval()").fetchone()[0]
        )
        cur = conn.execute(
            "INSERT INTO content_versions (content_item_id, workspace_id, version_no, body,"
            " created_by, created_at, status) VALUES (?,?,1,?,?,?,?)",
            (item_id, principal.workspace_id, payload.body, principal.user_id, ts, STATUS_DRAFT),
        )
        version_id = int(cur.lastrowid) if not db.is_postgres else int(
            conn.execute("SELECT lastval()").fetchone()[0]
        )
        conn.execute(
            "UPDATE content_items SET current_version_id = ? WHERE id = ?", (version_id, item_id)
        )
    _audit(db, principal.workspace_id, principal.display_name, "content.created", "content_item",
           item_id, payload.title)
    record_usage(db, principal.workspace_id, "submission_created", principal.display_name)
    queue_webhook(
        db,
        principal.workspace_id,
        "submission.created",
        {"submission_id": item_id, "title": payload.title, "content_type": payload.content_type},
    )
    item = _get_item(db, principal.workspace_id, item_id)
    return _detail(db, principal.workspace_id, item)


@router.post("/content/upload", response_model=ContentDetail, status_code=status.HTTP_201_CREATED)
async def create_from_upload(
    file: UploadFile = File(...),
    title: str = "",
    content_type: str = "document",
    principal: Principal = Depends(require_role("creator", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    if content_type not in {"social", "ad", "email", "document"}:
        raise HTTPException(status_code=400, detail="Unknown content type.")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="That file is larger than 10 MB.")
    try:
        body = extract_upload(file.filename or "upload.txt", data)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = ContentCreate(
        title=(title or (file.filename or "Uploaded draft")).strip()[:200],
        content_type=content_type,  # type: ignore[arg-type]
        body=body[:20000],
    )
    filename = (file.filename or "uploaded-document").replace("\r", "").replace("\n", "")
    object_key = f"submissions/{principal.workspace_id}/{secrets.token_urlsafe(24)}"
    detected_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        put_private_object(object_key, data, detected_type)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return _create_content(
        payload,
        principal,
        db,
        (object_key, filename[:240], detected_type, len(data)),
    )


@router.get("/content/{item_id}/source")
def download_submission_source(
    item_id: int,
    principal: Principal = Depends(get_principal),
    db: Database = Depends(get_db),
) -> Response:
    item = _get_item(db, principal.workspace_id, item_id)
    object_key = item.get("source_object_key")
    if not object_key:
        raise HTTPException(status_code=404, detail="This submission has no stored source file.")
    try:
        content = get_private_object(object_key)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    filename = quote(item.get("source_filename") or "source-file", safe="")
    return Response(
        content=content,
        media_type=item.get("source_content_type") or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/content/{item_id}", response_model=ContentDetail)
def get_content(
    item_id: int,
    principal: Principal = Depends(get_principal),
    db: Database = Depends(get_db),
) -> ContentDetail:
    item = _get_item(db, principal.workspace_id, item_id)
    return _detail(db, principal.workspace_id, item)


@router.post("/content/{item_id}/review", response_model=ContentDetail)
def review_content(
    item_id: int,
    principal: Principal = Depends(require_role("creator", "manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    item = _get_item(db, principal.workspace_id, item_id)
    if not item.get("current_version_id"):
        raise HTTPException(status_code=409, detail="This submission has no version to review.")
    ver = _get_version(db, principal.workspace_id, int(item["current_version_id"]))
    _apply_review(
        db, principal.workspace_id, item_id, int(ver["id"]), ver["body"],
        item["content_type"], principal.display_name,
    )
    return _detail(db, principal.workspace_id, _get_item(db, principal.workspace_id, item_id))


@router.post("/content/{item_id}/findings/{finding_id}/decision", response_model=ContentDetail)
def decide_finding(
    item_id: int,
    finding_id: int,
    payload: FindingDecisionRequest,
    principal: Principal = Depends(require_role("creator", "manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    item = _get_item(db, principal.workspace_id, item_id)
    finding = db.query_one(
        "SELECT * FROM findings WHERE id = ? AND workspace_id = ?",
        (finding_id, principal.workspace_id),
    )
    if not finding:
        raise HTTPException(status_code=404, detail="That finding was not found.")
    if int(finding["version_id"]) != int(item["current_version_id"] or 0):
        raise HTTPException(
            status_code=409,
            detail="That finding belongs to an older version. Re-run the check on the current draft.",
        )
    if payload.decision == "edited" and not (payload.edited_text or "").strip():
        raise HTTPException(status_code=422, detail="Provide the edited text for an edit decision.")

    db.execute(
        "UPDATE findings SET creator_decision = ?, edited_text = ? WHERE id = ? AND workspace_id = ?",
        (
            payload.decision,
            (payload.edited_text or "").strip() or None if payload.decision == "edited" else None,
            finding_id,
            principal.workspace_id,
        ),
    )
    _audit(db, principal.workspace_id, principal.display_name, f"finding.{payload.decision}",
           "finding", finding_id, finding["rule"])
    return _detail(db, principal.workspace_id, item)


@router.post("/content/{item_id}/revise", response_model=ContentDetail)
def revise_content(
    item_id: int,
    principal: Principal = Depends(require_role("creator", "manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    """Apply accepted/edited fixes to produce a NEW version.

    Editing always creates a new version and resets review state, which
    invalidates any prior approval for the previous version.
    """
    item = _get_item(db, principal.workspace_id, item_id)
    if not item.get("current_version_id"):
        raise HTTPException(status_code=409, detail="This submission has no version to revise.")
    ver = _get_version(db, principal.workspace_id, int(item["current_version_id"]))
    findings = _finding_rows(db, principal.workspace_id, int(ver["id"]))

    body: str = ver["body"]
    applied = 0
    # Apply from the end of the document backwards so offsets stay valid.
    editable = [
        f for f in findings
        if f["creator_decision"] in ("accepted", "edited")
        and f["span_start"] is not None and f["span_end"] is not None
    ]
    # Skip overlapping spans: applying two edits to the same characters would
    # corrupt the draft. The first (highest severity) edit wins.
    claimed: list[tuple[int, int]] = []
    for f in sorted(editable, key=lambda r: int(r["span_start"]), reverse=True):
        replacement = f["edited_text"] if f["creator_decision"] == "edited" else f["suggestion"]
        if not replacement:
            continue
        start, end = int(f["span_start"]), int(f["span_end"])
        if start < 0 or end > len(body) or start > end:
            continue
        if any(start < c_end and c_start < end for c_start, c_end in claimed):
            continue
        # Safety: the stored span must still match the text it was created for.
        # If the draft drifted, skip rather than corrupt the document.
        if start < end and body[start:end] != f["affected_text"]:
            continue
        body = body[:start] + replacement + body[end:]
        claimed.append((start, end))
        applied += 1

    if applied == 0:
        raise HTTPException(
            status_code=409,
            detail="Accept or edit at least one finding before creating a revised draft.",
        )

    ts = now_iso()
    next_no = int(ver["version_no"]) + 1
    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO content_versions (content_item_id, workspace_id, version_no, body,"
            " created_by, created_at, status) VALUES (?,?,?,?,?,?,?)",
            (item_id, principal.workspace_id, next_no, body, principal.user_id, ts, STATUS_DRAFT),
        )
        new_id = int(cur.lastrowid) if not db.is_postgres else int(
            conn.execute("SELECT lastval()").fetchone()[0]
        )
        conn.execute(
            "UPDATE content_items SET current_version_id = ?, status = ?, updated_at = ? WHERE id = ?",
            (new_id, STATUS_DRAFT, ts, item_id),
        )
    _audit(db, principal.workspace_id, principal.display_name, "version.created", "version",
           new_id, f"v{next_no} from {applied} accepted fixes")
    return _detail(db, principal.workspace_id, _get_item(db, principal.workspace_id, item_id))


@router.post("/content/{item_id}/edit-draft", response_model=ContentDetail)
def edit_draft(
    item_id: int,
    payload: DraftEditRequest,
    principal: Principal = Depends(require_role("creator", "manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    """Edit the draft text directly, creating a new version.

    Managers and approvers use this to fix wording the AI flagged as vague, or to
    correct anything the checks missed. Editing always creates a new version and
    resets review state, which invalidates any prior approval.
    """
    item = _get_item(db, principal.workspace_id, item_id)
    if not item.get("current_version_id"):
        raise HTTPException(status_code=409, detail="This submission has no version to edit.")
    ver = _get_version(db, principal.workspace_id, int(item["current_version_id"]))

    new_body = payload.body.strip()
    if not new_body:
        raise HTTPException(status_code=422, detail="The draft cannot be empty.")
    if new_body == ver["body"].strip():
        raise HTTPException(status_code=409, detail="The draft is unchanged.")

    ts = now_iso()
    next_no = int(ver["version_no"]) + 1
    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO content_versions (content_item_id, workspace_id, version_no, body,"
            " created_by, created_at, status) VALUES (?,?,?,?,?,?,?)",
            (item_id, principal.workspace_id, next_no, new_body, principal.user_id, ts, STATUS_DRAFT),
        )
        new_id = int(cur.lastrowid) if not db.is_postgres else int(
            conn.execute("SELECT lastval()").fetchone()[0]
        )
        conn.execute(
            "UPDATE content_items SET current_version_id = ?, status = ?, updated_at = ? WHERE id = ?",
            (new_id, STATUS_DRAFT, ts, item_id),
        )
    detail = f"v{next_no} edited directly by {principal.role}"
    if payload.note:
        detail += f": {payload.note.strip()}"
    _audit(db, principal.workspace_id, principal.display_name, "version.edited", "version",
           new_id, detail)
    return _detail(db, principal.workspace_id, _get_item(db, principal.workspace_id, item_id))


@router.post("/content/{item_id}/submit", response_model=ContentDetail)
def submit_for_approval(
    item_id: int,
    principal: Principal = Depends(require_role("creator", "manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    """Hand the version to the next person in the chain.

    Creator  -> Manager Review   (first review)
    Manager  -> Approver Review  (final sign-off)
    Approver -> Manager Review   (only after they revised it themselves)

    The destination is decided by the caller's role, so the button always means
    one specific thing and the audit trail records who sent it where.
    """
    item = _get_item(db, principal.workspace_id, item_id)
    if not item.get("current_version_id"):
        raise HTTPException(status_code=409, detail="This submission has no version to submit.")
    ver = _get_version(db, principal.workspace_id, int(item["current_version_id"]))
    if ver["review_state"] != "reviewed":
        raise HTTPException(
            status_code=409,
            detail="Run the brand check on this version before sending it on.",
        )

    current = ver["status"]
    if principal.role in ("manager", "admin"):
        # A manager forwards to the approver, but only from a state that is
        # actually waiting on them.
        if current not in (STATUS_MANAGER_REVIEW, STATUS_RESUBMITTED, STATUS_AI_COMPLETE):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This version is in '{current}', so there is nothing for you to forward. "
                    "It must be waiting on manager review first."
                ),
            )
        new_status = STATUS_APPROVER_REVIEW
        action = "content.forwarded"
        detail = f"v{ver['version_no']} forwarded to the approver by {principal.display_name}"
    elif principal.role == "approver":
        # An approver who revised the draft sends the new version back for
        # manager re-review, because a new version invalidates the old approval.
        if current not in (STATUS_DRAFT, STATUS_AI_COMPLETE, STATUS_CHANGES_REQUIRED):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This version is in '{current}'. You can only send a version you have "
                    "just revised back for re-review."
                ),
            )
        new_status = STATUS_MANAGER_REVIEW
        action = "content.returned"
        detail = (
            f"v{ver['version_no']} revised by the approver and returned to the manager "
            f"by {principal.display_name}"
        )
    else:
        if current not in (STATUS_DRAFT, STATUS_AI_COMPLETE, STATUS_CHANGES_REQUIRED):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This version is already in '{current}'. It is no longer waiting on you."
                ),
            )
        new_status = STATUS_MANAGER_REVIEW
        action = "content.submitted"
        detail = f"v{ver['version_no']} sent to the manager by {principal.display_name}"

    ts = now_iso()
    db.execute("UPDATE content_versions SET status = ? WHERE id = ?", (new_status, int(ver["id"])))
    db.execute(
        "UPDATE content_items SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, ts, item_id),
    )
    _audit(db, principal.workspace_id, principal.display_name, action, "version",
           int(ver["id"]), detail)
    assignment = db.query_one(
        "SELECT assignee_user_id, assignee_name FROM review_assignments"
        " WHERE content_item_id=? AND workspace_id=?",
        (item_id, principal.workspace_id),
    )
    recipient = None
    if assignment and assignment.get("assignee_user_id"):
        member = db.query_one(
            "SELECT email FROM memberships WHERE workspace_id=? AND user_id=? AND is_active=1",
            (principal.workspace_id, assignment["assignee_user_id"]),
        )
        recipient = member["email"] if member else None
    if recipient:
        queue_notification(
            db,
            principal.workspace_id,
            recipient,
            f"BrandShield: submission waiting for review — {item['title']}",
            f"{item['title']} is now in '{new_status}'. Assigned reviewer: "
            f"{assignment.get('assignee_name') or recipient}.",
        )
    return _detail(db, principal.workspace_id, _get_item(db, principal.workspace_id, item_id))


@router.post("/content/{item_id}/send-back", response_model=ContentDetail)
def send_back(
    item_id: int,
    payload: SendBackRequest,
    principal: Principal = Depends(require_role("manager", "approver", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    """Return a version to the previous level. A note is mandatory.

    Approver -> Manager Review   (needs another look before sign-off)
    Manager  -> Changes Required (goes back to the creator to fix)
    """
    item = _get_item(db, principal.workspace_id, item_id)
    if not item.get("current_version_id"):
        raise HTTPException(status_code=409, detail="This submission has no version to send back.")
    ver = _get_version(db, principal.workspace_id, int(item["current_version_id"]))
    note = payload.note.strip()
    if not note:
        raise HTTPException(
            status_code=422, detail="A note is required when sending a version back."
        )

    current = ver["status"]
    if principal.role == "approver":
        if current != STATUS_APPROVER_REVIEW:
            raise HTTPException(
                status_code=409,
                detail=f"This version is in '{current}', so it is not waiting on the approver.",
            )
        new_status = STATUS_MANAGER_REVIEW
        destination = "the manager"
    else:
        if current not in (STATUS_MANAGER_REVIEW, STATUS_RESUBMITTED, STATUS_AI_COMPLETE):
            raise HTTPException(
                status_code=409,
                detail=f"This version is in '{current}', so it is not waiting on the manager.",
            )
        new_status = STATUS_CHANGES_REQUIRED
        destination = "the creator"

    ts = now_iso()
    with db.tx() as conn:
        conn.execute(
            "UPDATE content_versions SET status = ? WHERE id = ?", (new_status, int(ver["id"]))
        )
        conn.execute(
            "UPDATE content_items SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, ts, item_id),
        )
        conn.execute(
            "INSERT INTO comments (version_id, workspace_id, author, body, created_at)"
            " VALUES (?,?,?,?,?)",
            (int(ver["id"]), principal.workspace_id, principal.display_name,
             f"Sent back to {destination}: {note}", ts),
        )
    _audit(db, principal.workspace_id, principal.display_name, "content.sent_back", "version",
           int(ver["id"]), f"Sent back to {destination}: {note}")
    return _detail(db, principal.workspace_id, _get_item(db, principal.workspace_id, item_id))


@router.post("/content/{item_id}/comments", response_model=ContentDetail)
def add_comment(
    item_id: int,
    payload: CommentCreate,
    principal: Principal = Depends(get_principal),
    db: Database = Depends(get_db),
) -> ContentDetail:
    item = _get_item(db, principal.workspace_id, item_id)
    if not item.get("current_version_id"):
        raise HTTPException(status_code=409, detail="This submission has no version to comment on.")
    db.insert(
        "INSERT INTO comments (version_id, workspace_id, author, body, created_at)"
        " VALUES (?,?,?,?,?)",
        (int(item["current_version_id"]), principal.workspace_id, principal.display_name,
         payload.body.strip(), now_iso()),
    )
    _audit(db, principal.workspace_id, principal.display_name, "comment.added", "content_item",
           item_id, None)
    return _detail(db, principal.workspace_id, item)


@router.post("/content/{item_id}/approval", response_model=ContentDetail)
def decide_approval(
    item_id: int,
    payload: ApprovalRequest,
    principal: Principal = Depends(require_role("approver", "admin")),
    db: Database = Depends(get_db),
) -> ContentDetail:
    item = _get_item(db, principal.workspace_id, item_id)
    if not item.get("current_version_id"):
        raise HTTPException(status_code=409, detail="This submission has no version to approve.")
    ver = _get_version(db, principal.workspace_id, int(item["current_version_id"]))
    if ver["status"] != STATUS_APPROVER_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This version is in '{ver['status']}', not waiting on the approver. "
                "A manager must forward it to you first."
            ),
        )

    open_high = db.query_one(
        "SELECT COUNT(*) AS n FROM findings WHERE version_id = ? AND workspace_id = ?"
        " AND severity = 'high' AND creator_decision IN ('pending','rejected')",
        (int(ver["id"]), principal.workspace_id),
    )
    unresolved_high = int(open_high["n"] or 0) if open_high else 0

    if payload.decision == "approved":
        if unresolved_high > 0 and not payload.high_severity_signoff:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{unresolved_high} high-severity finding(s) are still unresolved. "
                    "Tick the explicit sign-off to approve anyway."
                ),
            )
    elif not (payload.reason or "").strip():
        raise HTTPException(
            status_code=422,
            detail="A reason is required when requesting changes or rejecting.",
        )

    ts = now_iso()
    new_status = {
        "approved": STATUS_APPROVED,
        "changes_requested": STATUS_CHANGES_REQUIRED,
        "rejected": STATUS_REJECTED,
    }[payload.decision]
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO approvals (version_id, workspace_id, decision, reason, reviewer,"
            " high_severity_signoff, created_at) VALUES (?,?,?,?,?,?,?)",
            (int(ver["id"]), principal.workspace_id, payload.decision,
             (payload.reason or "").strip() or None, principal.display_name,
             1 if payload.high_severity_signoff else 0, ts),
        )
        conn.execute("UPDATE content_versions SET status = ? WHERE id = ?", (new_status, int(ver["id"])))
        conn.execute(
            "UPDATE content_items SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, ts, item_id),
        )
    _audit(db, principal.workspace_id, principal.display_name, f"approval.{payload.decision}",
           "version", int(ver["id"]), payload.reason)
    record_usage(db, principal.workspace_id, f"approval_{payload.decision}", principal.display_name)
    queue_webhook(
        db,
        principal.workspace_id,
        f"approval.{payload.decision}",
        {
            "item_id": item_id,
            "version_id": int(ver["id"]),
            "decision": payload.decision,
            "reviewer": principal.display_name,
        },
    )
    return _detail(db, principal.workspace_id, _get_item(db, principal.workspace_id, item_id))


@router.get("/content/{item_id}/history", response_model=list[dict])
def content_history(
    item_id: int,
    principal: Principal = Depends(require_role("approver")),
    db: Database = Depends(get_db),
) -> list[dict]:
    item = _get_item(db, principal.workspace_id, item_id)
    versions = db.query(
        "SELECT v.id, v.version_no, v.status,"
        " COALESCE(m.display_name, v.created_by) AS created_by, v.created_at, v.body"
        " FROM content_versions v"
        " LEFT JOIN memberships m ON m.workspace_id = v.workspace_id AND m.user_id = v.created_by"
        " WHERE v.content_item_id = ? AND v.workspace_id = ? ORDER BY v.version_no",
        (item_id, principal.workspace_id),
    )
    out: list[dict] = []
    for v in versions:
        approvals = db.query(
            "SELECT decision, reason, reviewer, created_at FROM approvals"
            " WHERE version_id = ? AND workspace_id = ? ORDER BY id",
            (int(v["id"]), principal.workspace_id),
        )
        findings = db.query_one(
            "SELECT COUNT(*) AS n FROM findings WHERE version_id = ? AND workspace_id = ?",
            (int(v["id"]), principal.workspace_id),
        )
        out.append(
            {
                "version_id": int(v["id"]),
                "version_no": int(v["version_no"]),
                "status": v["status"],
                "created_by": v["created_by"],
                "created_at": v["created_at"],
                "body": v["body"],
                "finding_count": int(findings["n"] or 0) if findings else 0,
                "approvals": approvals,
            }
        )
    return out


@router.get("/content/{item_id}/audit", response_model=list[dict])
def content_audit(
    item_id: int,
    principal: Principal = Depends(require_role("approver")),
    db: Database = Depends(get_db),
) -> list[dict]:
    """Audit events for one submission only, including its versions and findings."""
    _get_item(db, principal.workspace_id, item_id)
    version_ids = [
        int(v["id"])
        for v in db.query(
            "SELECT id FROM content_versions WHERE content_item_id = ? AND workspace_id = ?",
            (item_id, principal.workspace_id),
        )
    ]
    finding_ids = [
        int(f["id"])
        for f in db.query(
            "SELECT f.id FROM findings f JOIN content_versions v ON v.id = f.version_id"
            " WHERE v.content_item_id = ? AND f.workspace_id = ?",
            (item_id, principal.workspace_id),
        )
    ]

    clauses = ["(entity_type = 'content_item' AND entity_id = ?)"]
    params: list[Any] = [item_id]
    if version_ids:
        clauses.append(
            f"(entity_type = 'version' AND entity_id IN ({','.join('?' for _ in version_ids)}))"
        )
        params.extend(version_ids)
    if finding_ids:
        clauses.append(
            f"(entity_type = 'finding' AND entity_id IN ({','.join('?' for _ in finding_ids)}))"
        )
        params.extend(finding_ids)

    return db.query(
        "SELECT id, actor, action, entity_type, entity_id, detail, created_at FROM audit_events"
        f" WHERE workspace_id = ? AND ({' OR '.join(clauses)}) ORDER BY id DESC LIMIT 200",
        (principal.workspace_id, *params),
    )


@router.get("/audit", response_model=list[dict])
def audit_trail(
    principal: Principal = Depends(require_role("approver")), db: Database = Depends(get_db)
) -> list[dict]:
    return db.query(
        "SELECT id, actor, action, entity_type, entity_id, detail, created_at FROM audit_events"
        " WHERE workspace_id = ? ORDER BY id DESC LIMIT 200",
        (principal.workspace_id,),
    )
