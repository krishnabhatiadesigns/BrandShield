from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import Principal, get_principal
from app.db import Database, get_db
from app.routers import brand
from app.schema import create_schema


def _client():
    db = Database("sqlite:///:memory:")
    create_schema(db)
    db.insert(
        "INSERT INTO workspaces (id, name, slug, created_at)"
        " VALUES (1, 'Acme', 'acme', 'now'), (2, 'Other', 'other', 'now')"
    )
    role = {"value": "manager"}

    def principal() -> Principal:
        return Principal("manager-id", "Mina Manager", role["value"], 1, "Acme", False)

    app = FastAPI()
    app.include_router(brand.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = principal
    return db, TestClient(app), role


def test_manager_can_create_update_and_delete_terms_facts_and_palette():
    db, client, _ = _client()

    term = client.post(
        "/api/brand/terms",
        json={"term": "  miracle  ", "kind": "prohibited", "replacement": "  "},
    )
    assert term.status_code == 201
    assert term.json()["term"] == "miracle"
    assert term.json()["replacement"] is None

    updated_term = client.put(
        f"/api/brand/terms/{term.json()['id']}",
        json={"term": "wellness", "kind": "approved", "replacement": "wellbeing"},
    )
    assert updated_term.status_code == 200
    assert updated_term.json()["kind"] == "approved"
    assert updated_term.json()["replacement"] == "wellbeing"
    assert client.delete(f"/api/brand/terms/{term.json()['id']}").status_code == 204
    assert client.delete(f"/api/brand/terms/{term.json()['id']}").status_code == 404

    fact = client.post(
        "/api/brand/facts",
        json={"fact_key": "  protein  ", "value": "6", "unit": "g"},
    )
    assert fact.status_code == 201
    updated_fact = client.put(
        f"/api/brand/facts/{fact.json()['id']}",
        json={"fact_key": "protein_per_bar", "value": "7", "unit": "g"},
    )
    assert updated_fact.status_code == 200
    assert updated_fact.json()["value"] == "7"
    assert client.delete(f"/api/brand/facts/{fact.json()['id']}").status_code == 204
    assert client.delete(f"/api/brand/facts/{fact.json()['id']}").status_code == 404

    color = client.post(
        "/api/brand/palette",
        json={"name": "  Forest  ", "hex": "#1f5c3a", "role": "primary"},
    )
    assert color.status_code == 201
    assert color.json()["name"] == "Forest"
    assert color.json()["hex"] == "#1F5C3A"
    updated_color = client.put(
        f"/api/brand/palette/{color.json()['id']}",
        json={"name": "Harvest", "hex": "#E8A33D", "role": "accent"},
    )
    assert updated_color.status_code == 200
    assert updated_color.json()["hex"] == "#E8A33D"
    assert client.delete(f"/api/brand/palette/{color.json()['id']}").status_code == 204
    assert client.delete(f"/api/brand/palette/{color.json()['id']}").status_code == 404

    audit_actions = {
        row["action"]
        for row in db.query("SELECT action FROM audit_events WHERE workspace_id = 1")
    }
    assert {
        "brand_term.created", "brand_term.updated", "brand_term.deleted",
        "brand_fact.created", "brand_fact.updated", "brand_fact.deleted",
        "brand_palette.created", "brand_palette.updated", "brand_palette.deleted",
    } <= audit_actions


def test_brand_profile_edits_are_manager_only_and_workspace_scoped():
    db, client, role = _client()
    db.insert(
        "INSERT INTO terms (workspace_id, term, kind, created_at)"
        " VALUES (2, 'other term', 'approved', 'now')"
    )
    other_term = db.query_one("SELECT id FROM terms WHERE workspace_id = 2")
    assert other_term is not None

    assert client.put(
        f"/api/brand/terms/{other_term['id']}",
        json={"term": "changed", "kind": "approved"},
    ).status_code == 404
    assert db.query_one("SELECT term FROM terms WHERE id = ?", (other_term["id"],))["term"] == (
        "other term"
    )

    db.insert(
        "INSERT INTO terms (workspace_id, term, kind, created_at)"
        " VALUES (1, 'brand term', 'approved', 'now')"
    )
    own_term = db.query_one("SELECT id FROM terms WHERE workspace_id = 1")
    assert own_term is not None
    role["value"] = "approver"
    assert client.put(
        f"/api/brand/terms/{own_term['id']}",
        json={"term": "changed", "kind": "approved"},
    ).status_code == 403
    assert client.delete(f"/api/brand/terms/{own_term['id']}").status_code == 403


def test_facts_accept_only_approved_passages_from_the_same_workspace():
    db, client, _ = _client()
    document_ids = {}
    for workspace_id, title in ((1, "Acme facts"), (2, "Other facts")):
        db.insert(
            "INSERT INTO knowledge_documents"
            " (workspace_id, title, doc_type, status, created_at)"
            " VALUES (?, ?, 'guideline', 'approved', 'now')",
            (workspace_id, title),
        )
        document = db.query_one(
            "SELECT id FROM knowledge_documents WHERE workspace_id = ? AND title = ?",
            (workspace_id, title),
        )
        assert document is not None
        db.insert(
            "INSERT INTO passages (workspace_id, document_id, source, text, created_at)"
            " VALUES (?, ?, ?, 'Approved fact passage.', 'now')",
            (workspace_id, document["id"], title),
        )
        passage = db.query_one(
            "SELECT id FROM passages WHERE workspace_id = ? AND document_id = ?",
            (workspace_id, document["id"]),
        )
        assert passage is not None
        document_ids[workspace_id] = int(passage["id"])

    rejected = client.post(
        "/api/brand/facts",
        json={
            "fact_key": "protein",
            "value": "6",
            "unit": "g",
            "source_passage_id": document_ids[2],
        },
    )
    assert rejected.status_code == 422

    created = client.post(
        "/api/brand/facts",
        json={
            "fact_key": "protein",
            "value": "6",
            "unit": "g",
            "source_passage_id": document_ids[1],
        },
    )
    assert created.status_code == 201
    assert created.json()["source_passage_id"] == document_ids[1]

    invalid_update = client.put(
        f"/api/brand/facts/{created.json()['id']}",
        json={
            "fact_key": "protein",
            "value": "7",
            "unit": "g",
            "source_passage_id": document_ids[2],
        },
    )
    assert invalid_update.status_code == 422
    stored = db.query_one(
        "SELECT value, source_passage_id FROM facts WHERE id = ?",
        (created.json()["id"],),
    )
    assert stored == {"value": "6", "source_passage_id": document_ids[1]}


def test_profile_exposes_stored_guideline_download_and_manual_passages_without_it(monkeypatch):
    db, client, _ = _client()
    db.insert(
        "INSERT INTO knowledge_documents"
        " (workspace_id, title, doc_type, status, source_object_key, source_filename,"
        " source_content_type, created_at)"
        " VALUES (1, 'Voice guide', 'guideline', 'approved', 'guidelines/1/guide',"
        " 'voice-guide.pdf', 'application/pdf', 'now')"
    )
    uploaded = db.query_one("SELECT id FROM knowledge_documents WHERE title = 'Voice guide'")
    assert uploaded is not None
    db.insert(
        "INSERT INTO passages (workspace_id, document_id, source, page, text, created_at)"
        " VALUES (1, ?, 'Voice guide', 1, 'Use a friendly tone.', 'now')",
        (uploaded["id"],),
    )
    db.insert(
        "INSERT INTO knowledge_documents (workspace_id, title, doc_type, status, created_at)"
        " VALUES (1, 'Manual notes', 'manual', 'approved', 'now')"
    )
    manual = db.query_one("SELECT id FROM knowledge_documents WHERE title = 'Manual notes'")
    assert manual is not None
    db.insert(
        "INSERT INTO passages (workspace_id, document_id, source, page, text, created_at)"
        " VALUES (1, ?, 'Manual notes', 1, 'Keep copy clear.', 'now')",
        (manual["id"],),
    )
    monkeypatch.setattr(brand, "get_private_object", lambda _key: b"sample pdf content")

    profile = client.get("/api/brand")
    assert profile.status_code == 200
    passages = {passage["source"]: passage for passage in profile.json()["passages"]}
    assert passages["Voice guide"]["source_available"] is True
    assert passages["Voice guide"]["document_id"] == uploaded["id"]
    assert passages["Manual notes"]["source_available"] is False

    downloaded = client.get(f"/api/brand/guidelines/{uploaded['id']}/source")
    assert downloaded.status_code == 200
    assert downloaded.content == b"sample pdf content"
    assert "voice-guide.pdf" in downloaded.headers["content-disposition"]
    assert client.get(f"/api/brand/guidelines/{manual['id']}/source").status_code == 404
