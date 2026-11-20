from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Principal, get_principal
from app.db import Database, get_db
from app.llm import LLMResult
from app.pipeline import build_brand_context, run_review
from app.routers import brand
from app.schema import create_schema
from app.validation import validate_llm_findings


def _client():
    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at) VALUES (1, 'Acme', 'acme', 'now')"
    )
    db.insert(
        "INSERT INTO memberships (workspace_id, user_id, display_name, role, created_at)"
        " VALUES (1, 'manager-id', 'Mina Manager', 'manager', 'now')"
    )
    app = FastAPI()
    app.include_router(brand.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: Principal(
        "manager-id", "Mina Manager", "manager", 1, "Acme", False
    )
    return db, TestClient(app)


def test_guideline_rules_are_versioned_and_workspace_scoped():
    db, client = _client()
    created = client.post(
        "/api/brand/rules",
        json={
            "category": "tone",
            "title": "Use a warm voice",
            "description": "Address readers in a helpful, approachable tone.",
            "severity": "medium",
            "mandatory": True,
            "content_types": ["social", "email"],
        },
    )
    assert created.status_code == 201
    assert created.json()["version"] == 1

    updated = client.patch(
        f"/api/brand/rules/{created.json()['id']}",
        json={"description": "Use a clear, friendly, and helpful tone."},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["description"] == "Use a clear, friendly, and helpful tone."

    versions = client.get(f"/api/brand/rules/{created.json()['id']}/versions")
    assert versions.status_code == 200
    assert [entry["version"] for entry in versions.json()] == [2, 1]
    assert versions.json()[1]["snapshot"]["description"] == (
        "Address readers in a helpful, approachable tone."
    )
    assert [rule["id"] for rule in client.get("/api/brand").json()["rules"]] == [
        created.json()["id"]
    ]

    assert client.patch(
        f"/api/brand/rules/{created.json()['id']}", json={"enabled": False}
    ).json()["enabled"] is False
    assert client.get("/api/brand/rules/999/versions").status_code == 404


def test_policy_rules_are_filtered_and_sent_to_the_ai():
    db, _ = _client()
    from app.models import GuidelineRuleCreate
    from app.routers.brand import create_guideline_rule

    principal = Principal("manager-id", "Mina Manager", "manager", 1, "Acme", False)
    create_guideline_rule(
        GuidelineRuleCreate(
            category="tone",
            title="Friendly tone",
            description="Use clear, welcoming language.",
            content_types=["social"],
        ),
        principal,
        db,
    )
    assert len(build_brand_context(db, 1, "social").rules) == 1
    assert build_brand_context(db, 1, "document").rules == []

    with patch(
        "app.pipeline.analyse",
        return_value=LLMResult(ok=False, message="test"),
    ) as analyse:
        run_review(db, 1, "Draft text.", "social", use_llm=True)
    assert analyse.call_args.args[5][0]["title"] == "Friendly tone"


def test_future_policy_version_does_not_replace_current_rule_early():
    db, client = _client()
    created = client.post(
        "/api/brand/rules",
        json={
            "category": "messaging",
            "title": "Current message",
            "description": "Use the current approved phrase.",
            "content_types": ["social"],
        },
    )
    updated = client.patch(
        f"/api/brand/rules/{created.json()['id']}",
        json={
            "description": "Use the new phrase after launch.",
            "effective_date": "2099-01-01",
        },
    )

    assert updated.status_code == 200
    active = build_brand_context(db, 1, "social").rules
    assert len(active) == 1
    assert active[0]["description"] == "Use the current approved phrase."
    assert active[0]["current_version"] == 1


def test_only_active_rules_can_support_policy_findings():
    body = "We can help your team."
    finding = {
        "category": "messaging",
        "severity": "medium",
        "affected_text": body,
        "rule": "Use welcoming language",
        "explanation": "The wording is less approachable than the required tone.",
        "source_rule_id": 7,
        "evidence_status": "supported",
    }
    valid, _ = validate_llm_findings(
        body,
        [finding],
        {},
        [],
        set(),
        {7: {"id": 7, "current_version": 3, "title": "Friendly tone",
             "description": "Use clear, welcoming language.", "severity": "medium",
             "mandatory": True, "source_passage_id": None}},
    )
    assert valid[0].evidence_status == "supported"
    assert valid[0].source_rule_version == 3

    invalid, _ = validate_llm_findings(body, [finding], {}, [], set(), {})
    assert invalid[0].evidence_status == "needs_verification"
    assert invalid[0].source_rule_id is None

    advisory, _ = validate_llm_findings(
        body,
        [finding],
        {},
        [],
        set(),
        {7: {"id": 7, "current_version": 4, "title": "Optional style",
             "description": "Prefer a warmer greeting.", "severity": "low",
             "mandatory": False, "source_passage_id": None}},
    )
    assert advisory[0].evidence_status == "needs_verification"
    assert advisory[0].severity == "low"
