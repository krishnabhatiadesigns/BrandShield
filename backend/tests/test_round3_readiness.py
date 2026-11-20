from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.auth import Principal, get_principal
from app.checks.base import FindingDraft
from app.db import Database, get_db
from app.pipeline import ReviewOutcome
from app.routers import content, visual
from app.retrieval import load_workspace_passages
from app.schema import create_schema
from app.validation import validate_llm_findings


@pytest.fixture
def application():
    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at) VALUES (1, 'Acme', 'acme', 'now')"
    )
    db.insert(
        "INSERT INTO palette_colors (workspace_id, name, hex, role, created_at)"
        " VALUES (1, 'Forest', '#1F5C3A', 'primary', 'now')"
    )
    role = {"value": "creator"}
    people = {
        "creator": ("creator-id", "Priya Creator"),
        "manager": ("manager-id", "Arun Manager"),
        "approver": ("approver-id", "Rohan Approver"),
    }

    def principal() -> Principal:
        user_id, name = people[role["value"]]
        return Principal(user_id, name, role["value"], 1, "Acme", False)

    app = FastAPI()
    app.include_router(content.router)
    app.include_router(visual.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = principal
    return db, app, role


def test_llm_evidence_and_suggestion_are_verified():
    findings, notes = validate_llm_findings(
        body="The claim is amazing.",
        raw_findings=[
            {
                "category": "claim",
                "severity": "high",
                "affected_text": "claim",
                "rule": "Unsupported claim",
                "explanation": "There is no approved evidence for this statement.",
                "evidence_status": "contradicted",
                "source_passage_id": 404,
                "suggestion": "This claim is 97% proven.",
            },
            {
                "affected_text": "not in this draft",
                "explanation": "This finding must be discarded.",
            },
        ],
        allowed_passages={1: {"id": 1, "text": "Approved source"}},
        approved_terms=[],
        approved_numbers=set(),
    )

    assert len(findings) == 1
    assert findings[0].span_start == 4
    assert findings[0].span_end == 9
    assert findings[0].source_passage_id is None
    assert findings[0].evidence_status == "needs_verification"
    assert findings[0].suggestion is None
    assert any("not an approved passage" in note for note in notes)
    assert any("unverified figures" in note for note in notes)
    assert any("affected text not found" in note for note in notes)


def test_visual_checks_cover_palette_contrast_and_bad_input(application):
    _, app, _ = application
    response = TestClient(app).post(
        "/api/visual/check",
        json={
            "hex_colors": ["#1F5C3A", "#FF0000", "not-a-colour"],
            "text_hex": "#777777",
            "background_hex": "#FFFFFF",
        },
    )

    assert response.status_code == 200
    result = response.json()
    matches = {match["input"]: match for match in result["palette_match"]}
    assert matches["#1F5C3A"]["on_brand"] is True
    assert matches["#FF0000"]["on_brand"] is False
    assert result["contrast_ratio"] == pytest.approx(4.48, abs=0.01)
    assert any("4.5:1" in issue["rule"] for issue in result["issues"])
    assert any(issue["affected_text"] == "not-a-colour" for issue in result["issues"])


def test_visual_image_upload_checks_palette_and_reports_manual_review_limits(application):
    _, app, _ = application
    image = Image.new("RGB", (20, 10), "#FF0000")
    stream = BytesIO()
    image.save(stream, format="PNG")

    response = TestClient(app).post(
        "/api/visual/image",
        files={"file": ("creative.png", stream.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["image"]["format"] == "PNG"
    assert result["image"]["width"] == 20
    assert result["image"]["colors"][0]["hex"] == "#FF0000"
    assert result["palette_match"][0]["on_brand"] is False
    assert any("Text/background contrast" in note for note in result["limitations"])
    assert any(issue["category"] == "visual" for issue in result["issues"])


def test_visual_image_upload_rejects_unreadable_files(application):
    _, app, _ = application
    response = TestClient(app).post(
        "/api/visual/image",
        files={"file": ("creative.png", b"not an image", "image/png")},
    )

    assert response.status_code == 422
    assert "unreadable or damaged" in response.json()["detail"]


def test_end_to_end_version_review_and_approval_preserve_workflow(application, monkeypatch):
    db, app, role = application
    client = TestClient(app)

    def fake_run_review(_db, _workspace_id, body, _content_type, use_llm=True):
        findings = []
        if "Guaranteed" in body:
            start = body.index("Guaranteed")
            findings.append(
                FindingDraft(
                    category="claim",
                    severity="medium",
                    affected_text="Guaranteed",
                    rule="Avoid absolute guarantees",
                    explanation="This absolute claim needs approved evidence.",
                    evidence_status="needs_verification",
                    suggestion="Quality",
                    span_start=start,
                    span_end=start + len("Guaranteed"),
                    detector="deterministic",
                )
            )
        if "reliability" in body:
            start = body.index("reliability")
            findings.append(
                FindingDraft(
                    category="messaging",
                    severity="low",
                    affected_text="reliability",
                    rule="Use the approved product wording",
                    explanation="Use concise approved terminology.",
                    evidence_status="needs_verification",
                    suggestion="dependable",
                    span_start=start,
                    span_end=start + len("reliability"),
                    detector="deterministic",
                )
            )
        return ReviewOutcome(
            findings=findings,
            llm_status="disabled",
            llm_message="AI analysis is disabled for this test.",
            deterministic_count=len(findings),
            llm_count=0,
            duration_ms=0,
        )

    monkeypatch.setattr(content, "run_review", fake_run_review)

    created = client.post(
        "/api/content",
        json={"title": "Launch draft", "content_type": "social", "body": "Guaranteed; reliability."},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    reviewed = client.post(f"/api/content/{item_id}/review")
    assert reviewed.status_code == 200
    finding_ids = [finding["id"] for finding in reviewed.json()["findings"]]
    assert len(finding_ids) == 2
    assert reviewed.json()["status"] == "AI Review Complete"

    for finding_id in finding_ids:
        decision = client.post(
            f"/api/content/{item_id}/findings/{finding_id}/decision",
            json={"decision": "accepted"},
        )
        assert decision.status_code == 200

    refreshed = client.post(f"/api/content/{item_id}/review")
    assert refreshed.status_code == 200
    assert all(finding["creator_decision"] == "accepted" for finding in refreshed.json()["findings"])
    refreshed_finding_id = refreshed.json()["findings"][0]["id"]

    revised = client.post(f"/api/content/{item_id}/revise")
    assert revised.status_code == 200
    assert revised.json()["current_version"]["version_no"] == 2
    assert revised.json()["current_version"]["body"] == "Quality; dependable."
    assert revised.json()["status"] == "Draft"
    assert client.post(f"/api/content/{item_id}/revise").status_code == 409
    assert client.post(
        f"/api/content/{item_id}/findings/{refreshed_finding_id}/decision",
        json={"decision": "accepted"},
    ).status_code == 409

    reviewed_v2 = client.post(f"/api/content/{item_id}/review")
    assert reviewed_v2.status_code == 200
    assert reviewed_v2.json()["status"] == "AI Review Complete"

    submitted = client.post(f"/api/content/{item_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "Manager Review"
    assert client.post(f"/api/content/{item_id}/submit").status_code == 409

    role["value"] = "manager"
    forwarded = client.post(f"/api/content/{item_id}/submit")
    assert forwarded.status_code == 200
    assert forwarded.json()["status"] == "Approver Review"

    role["value"] = "approver"
    refreshed_v2 = client.post(f"/api/content/{item_id}/review")
    assert refreshed_v2.status_code == 200
    assert refreshed_v2.json()["status"] == "Approver Review"

    approved = client.post(
        f"/api/content/{item_id}/approval",
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"

    role["value"] = "creator"
    edited = client.post(
        f"/api/content/{item_id}/edit-draft",
        json={"body": "A reviewed copy.", "note": "Final wording update."},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "Draft"
    assert edited.json()["current_version"]["version_no"] == 3
    assert edited.json()["approvals"] == []
    assert db.query_one("SELECT COUNT(*) AS n FROM approvals WHERE version_id = 2")["n"] == 1


def test_reviewer_cannot_create_content(application):
    _, app, role = application
    role["value"] = "manager"

    response = TestClient(app).post(
        "/api/content",
        json={"title": "Not allowed", "content_type": "social", "body": "Draft"},
    )

    assert response.status_code == 403


def test_retrieval_only_includes_approved_in_force_workspace_passages(application):
    db, _, _ = application
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at)"
        " VALUES (2, 'Other', 'other', 'now')"
    )
    documents = [
        (1, "Approved in-force", "approved", None),
        (1, "Draft", "draft", None),
        (1, "Future", "approved", "2999-01-01"),
        (2, "Other workspace", "approved", None),
    ]
    for workspace_id, title, status, effective_date in documents:
        db.insert(
            "INSERT INTO knowledge_documents"
            " (workspace_id, title, doc_type, status, effective_date, created_at)"
            " VALUES (?, ?, 'policy', ?, ?, 'now')",
            (workspace_id, title, status, effective_date),
        )
        document = db.query_one(
            "SELECT id FROM knowledge_documents WHERE workspace_id = ? AND title = ?",
            (workspace_id, title),
        )
        db.insert(
            "INSERT INTO passages (workspace_id, document_id, source, text, created_at)"
            " VALUES (?, ?, ?, ?, 'now')",
            (workspace_id, document["id"], title, f"Passage for {title}"),
        )

    passages = load_workspace_passages(db, workspace_id=1)

    assert [passage["source"] for passage in passages] == ["Approved in-force"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   ", "content_type": "social", "body": "A valid draft."},
        {"title": "Launch draft", "content_type": "social", "body": " \n\t "},
    ],
)
def test_submission_rejects_whitespace_only_fields(application, payload):
    _, app, _ = application

    response = TestClient(app).post("/api/content", json=payload)

    assert response.status_code == 422


def test_overlapping_and_stale_fixes_cannot_corrupt_a_draft(application):
    db, app, _ = application
    client = TestClient(app)
    created = client.post(
        "/api/content",
        json={
            "title": "Overlap test",
            "content_type": "social",
            "body": "Guaranteed quality.",
        },
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    version_id = created.json()["current_version"]["id"]

    db.insert(
        "INSERT INTO findings (version_id, workspace_id, category, severity, span_start, span_end,"
        " affected_text, rule, explanation, evidence_status, confidence, suggestion,"
        " creator_decision, detector, created_at)"
        " VALUES (?,?, 'claim','high',0,18,'Guaranteed quality','Broad claim',"
        " 'Replace the broad claim.','needs_verification',0.8,'Reliable','accepted',"
        " 'deterministic','now')",
        (version_id, 1),
    )
    db.insert(
        "INSERT INTO findings (version_id, workspace_id, category, severity, span_start, span_end,"
        " affected_text, rule, explanation, evidence_status, confidence, suggestion,"
        " creator_decision, detector, created_at)"
        " VALUES (?,?, 'claim','medium',0,10,'Guaranteed','Absolute claim',"
        " 'Replace the absolute claim.','needs_verification',0.8,'Safe','accepted',"
        " 'deterministic','now')",
        (version_id, 1),
    )

    revised = client.post(f"/api/content/{item_id}/revise")
    assert revised.status_code == 200
    assert revised.json()["current_version"]["body"] == "Reliable."

    current_version_id = revised.json()["current_version"]["id"]
    db.execute(
        "UPDATE content_versions SET body = 'Different copy.' WHERE id = ?",
        (current_version_id,),
    )
    db.insert(
        "INSERT INTO findings (version_id, workspace_id, category, severity, span_start, span_end,"
        " affected_text, rule, explanation, evidence_status, confidence, suggestion,"
        " creator_decision, detector, created_at)"
        " VALUES (?,?, 'claim','medium',0,8,'Reliable','Stale claim',"
        " 'This span no longer matches.','needs_verification',0.8,'Better','accepted',"
        " 'deterministic','now')",
        (current_version_id, 1),
    )

    stale_revision = client.post(f"/api/content/{item_id}/revise")
    assert stale_revision.status_code == 409
    assert stale_revision.json()["detail"].startswith("Accept or edit at least one finding")
