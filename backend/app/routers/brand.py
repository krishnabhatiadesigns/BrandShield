"""Brand profile: guidelines, passages, terms, facts, palette, and PDF ingestion."""
from __future__ import annotations

import json
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from ..auth import Principal, get_principal, require_role
from ..db import Database, _sql, get_db
from ..models import (
    BrandProfile,
    CompanyContextUpdate,
    FactCreate,
    FactOut,
    GuidelineRuleCreate,
    GuidelineRuleOut,
    GuidelineRuleUpdate,
    PaletteCreate,
    PaletteOut,
    PassageCreate,
    PassageOut,
    TermCreate,
    TermOut,
)
from ..pipeline import DISCLAIMERS
from ..seed import now_iso
from ..storage import StorageError, get_private_object, put_private_object
from ..text import ExtractionError, extract_pdf

router = APIRouter(prefix="/api/brand", tags=["brand"])


def _record_brand_change(
    conn,
    workspace_id: int,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int,
    detail: str,
    timestamp: str,
) -> None:
    conn.execute(
        _sql(
            "INSERT INTO audit_events (workspace_id, actor, action, entity_type,"
            " entity_id, detail, created_at) VALUES (?,?,?,?,?,?,?)"
        ),
        (workspace_id, actor, action, entity_type, entity_id, detail, timestamp),
    )


def _validate_source_passage(db: Database, workspace_id: int, passage_id: int | None) -> None:
    if passage_id is None:
        return
    passage = db.query_one(
        "SELECT p.id FROM passages p JOIN knowledge_documents d ON d.id = p.document_id"
        " WHERE p.id = ? AND p.workspace_id = ? AND d.status = 'approved'",
        (passage_id, workspace_id),
    )
    if not passage:
        raise HTTPException(
            status_code=422,
            detail="Choose an approved source passage from this brand.",
        )


def _rule_out(row: dict) -> GuidelineRuleOut:
    return GuidelineRuleOut(
        id=int(row["id"]),
        category=row["category"],
        title=row["title"],
        description=row["description"],
        good_example=row["good_example"],
        bad_example=row["bad_example"],
        severity=row["severity"],
        mandatory=bool(row["mandatory"]),
        content_types=row["content_types"].split(","),
        source_passage_id=row["source_passage_id"],
        enabled=bool(row["enabled"]),
        version=int(row["current_version"]),
        effective_date=row.get("effective_date") or row["created_at"][:10],
    )


def _rule_snapshot(data: dict, version: int, effective_date: str) -> str:
    snapshot = {
        key: data.get(key)
        for key in (
            "category", "title", "description", "good_example", "bad_example",
            "severity", "mandatory", "content_types", "source_passage_id", "enabled",
        )
    }
    snapshot["version"] = version
    snapshot["effective_date"] = effective_date
    return json.dumps(snapshot, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


@router.get("", response_model=BrandProfile)
def get_profile(
    principal: Principal = Depends(get_principal), db: Database = Depends(get_db)
) -> BrandProfile:
    ws = principal.workspace_id
    passages = db.query(
        """
        SELECT p.id, p.source, p.section, p.page, p.text, p.document_id,
               CASE WHEN d.source_object_key IS NULL THEN 0 ELSE 1 END AS source_available
        FROM passages p JOIN knowledge_documents d ON d.id = p.document_id
        WHERE p.workspace_id = ? AND d.status = 'approved'
        ORDER BY p.id
        """,
        (ws,),
    )
    terms = db.query(
        "SELECT id, term, kind, replacement, notes FROM terms WHERE workspace_id = ? ORDER BY kind, term",
        (ws,),
    )
    facts = db.query(
        "SELECT id, fact_key, value, unit, source_passage_id FROM facts WHERE workspace_id = ? ORDER BY fact_key",
        (ws,),
    )
    palette = db.query(
        "SELECT id, name, hex, role FROM palette_colors WHERE workspace_id = ? ORDER BY id", (ws,)
    )
    rules = db.query(
        "SELECT * FROM guideline_rules WHERE workspace_id = ? ORDER BY id", (ws,)
    )
    context = db.query_one(
        "SELECT company_context FROM workspace_context WHERE workspace_id = ?", (ws,)
    )
    return BrandProfile(
        workspace_id=ws,
        workspace_name=principal.workspace_name,
        company_context=context["company_context"] if context else "",
        passages=[PassageOut(**p) for p in passages],
        terms=[TermOut(**t) for t in terms],
        facts=[FactOut(**f) for f in facts],
        palette=[PaletteOut(**c) for c in palette],
        rules=[_rule_out(r) for r in rules],
        disclaimers=DISCLAIMERS,
    )


@router.post("/rules", response_model=GuidelineRuleOut, status_code=status.HTTP_201_CREATED)
def create_guideline_rule(
    payload: GuidelineRuleCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> GuidelineRuleOut:
    ws = principal.workspace_id
    if payload.source_passage_id is not None and not db.query_one(
        "SELECT p.id FROM passages p JOIN knowledge_documents d ON d.id = p.document_id"
        " WHERE p.id = ? AND p.workspace_id = ? AND d.status = 'approved'",
        (payload.source_passage_id, ws),
    ):
        raise HTTPException(status_code=422, detail="Choose a guideline passage from this brand.")
    ts = now_iso()
    effective_date = payload.effective_date or ts[:10]
    data = payload.model_dump()
    data["content_types"] = ",".join(payload.content_types)
    with db.tx() as conn:
        inserted = conn.execute(
            _sql(
                "INSERT INTO guideline_rules (workspace_id, category, title, description,"
                " good_example, bad_example, severity, mandatory, content_types,"
                " source_passage_id, enabled, current_version, effective_date, created_by,"
                " updated_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " RETURNING id"
            ),
            (
                ws, payload.category, payload.title, payload.description, payload.good_example,
                payload.bad_example, payload.severity, int(payload.mandatory),
                data["content_types"], payload.source_passage_id, int(payload.enabled), 1,
                effective_date, principal.display_name, principal.display_name, ts, ts,
            ),
        ).fetchone()
        rule_id = int(inserted["id"])
        conn.execute(
            _sql(
                "INSERT INTO guideline_rule_versions (rule_id, workspace_id, version_no,"
                " snapshot, effective_date, created_by, created_at) VALUES (?,?,?,?,?,?,?)"
            ),
            (
                rule_id, ws, 1, _rule_snapshot(data, 1, effective_date),
                effective_date, principal.display_name, ts,
            ),
        )
        conn.execute(
            _sql(
                "INSERT INTO audit_events (workspace_id, actor, action, entity_type,"
                " entity_id, detail, created_at) VALUES (?,?,?,?,?,?,?)"
            ),
            (
                ws, principal.display_name, "guideline_rule.created", "guideline_rule",
                rule_id, f"Created policy rule: {payload.title}", ts,
            ),
        )
    row = db.query_one("SELECT * FROM guideline_rules WHERE id = ? AND workspace_id = ?", (rule_id, ws))
    assert row is not None
    return _rule_out(row)


@router.patch("/rules/{rule_id}", response_model=GuidelineRuleOut)
def update_guideline_rule(
    rule_id: int,
    payload: GuidelineRuleUpdate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> GuidelineRuleOut:
    ws = principal.workspace_id
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    if "source_passage_id" in changes and changes["source_passage_id"] is not None:
        if not db.query_one(
            "SELECT p.id FROM passages p JOIN knowledge_documents d ON d.id = p.document_id"
            " WHERE p.id = ? AND p.workspace_id = ? AND d.status = 'approved'",
            (changes["source_passage_id"], ws),
        ):
            raise HTTPException(status_code=422, detail="Choose a guideline passage from this brand.")
    ts = now_iso()
    with db.tx() as conn:
        result = conn.execute(
            _sql("SELECT * FROM guideline_rules WHERE id = ? AND workspace_id = ?"),
            (rule_id, ws),
        ).fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="That brand rule was not found.")
        current = dict(result)
        next_data = {**current, **changes}
        if "content_types" in changes:
            next_data["content_types"] = ",".join(changes["content_types"])
        version = int(current["current_version"]) + 1
        effective_date = changes.get("effective_date") or ts[:10]
        fields = (
            "category", "title", "description", "good_example", "bad_example", "severity",
            "mandatory", "content_types", "source_passage_id", "enabled", "effective_date",
        )
        conn.execute(
            _sql(
                "UPDATE guideline_rules SET category=?, title=?, description=?, good_example=?,"
                " bad_example=?, severity=?, mandatory=?, content_types=?, source_passage_id=?,"
                " enabled=?, effective_date=?, current_version=?, updated_by=?, updated_at=?"
                " WHERE id=? AND workspace_id=?"
            ),
            (
                *(int(next_data[key]) if key in {"mandatory", "enabled"} else
                  (effective_date if key == "effective_date" else next_data[key])
                  for key in fields),
                version, principal.display_name, ts, rule_id, ws,
            ),
        )
        conn.execute(
            _sql(
                "INSERT INTO guideline_rule_versions (rule_id, workspace_id, version_no,"
                " snapshot, effective_date, created_by, created_at) VALUES (?,?,?,?,?,?,?)"
            ),
            (
                rule_id, ws, version, _rule_snapshot(next_data, version, effective_date),
                effective_date, principal.display_name, ts,
            ),
        )
        conn.execute(
            _sql(
                "INSERT INTO audit_events (workspace_id, actor, action, entity_type,"
                " entity_id, detail, created_at) VALUES (?,?,?,?,?,?,?)"
            ),
            (
                ws, principal.display_name, "guideline_rule.updated", "guideline_rule",
                rule_id, f"Updated policy rule to version {version}: {next_data['title']}", ts,
            ),
        )
    row = db.query_one("SELECT * FROM guideline_rules WHERE id = ? AND workspace_id = ?", (rule_id, ws))
    assert row is not None
    return _rule_out(row)


@router.get("/rules/{rule_id}/versions")
def list_guideline_rule_versions(
    rule_id: int,
    principal: Principal = Depends(get_principal),
    db: Database = Depends(get_db),
) -> list[dict]:
    if not db.query_one(
        "SELECT id FROM guideline_rules WHERE id = ? AND workspace_id = ?",
        (rule_id, principal.workspace_id),
    ):
        raise HTTPException(status_code=404, detail="That brand rule was not found.")
    rows = db.query(
        "SELECT version_no, snapshot, effective_date, created_by, created_at"
        " FROM guideline_rule_versions WHERE rule_id = ? AND workspace_id = ?"
        " ORDER BY version_no DESC",
        (rule_id, principal.workspace_id),
    )
    return [
        {
            "version": int(row["version_no"]),
            "snapshot": json.loads(row["snapshot"]),
            "effective_date": row["effective_date"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@router.put("/company-context", status_code=status.HTTP_204_NO_CONTENT)
def update_company_context(
    payload: CompanyContextUpdate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> None:
    ts = now_iso()
    db.execute(
        """
        INSERT INTO workspace_context (workspace_id, company_context, updated_by, updated_at)
        VALUES (?,?,?,?)
        ON CONFLICT (workspace_id) DO UPDATE SET
            company_context = excluded.company_context,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (principal.workspace_id, payload.company_context.strip(), principal.display_name, ts),
    )
    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id, detail, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (principal.workspace_id, principal.display_name, "company_context.updated", "workspace",
         principal.workspace_id, "Company context updated", ts),
    )


@router.post("/terms", response_model=TermOut, status_code=status.HTTP_201_CREATED)
def add_term(
    payload: TermCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> TermOut:
    ts = now_iso()
    with db.tx() as conn:
        inserted = conn.execute(
            _sql(
                "INSERT INTO terms (workspace_id, term, kind, replacement, notes, created_at)"
                " VALUES (?,?,?,?,?,?) RETURNING id"
            ),
            (principal.workspace_id, payload.term, payload.kind,
             payload.replacement, payload.notes, ts),
        ).fetchone()
        term_id = int(inserted["id"])
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_term.created",
            "brand_term", term_id, f"Added terminology: {payload.term}", ts,
        )
    row = db.query_one(
        "SELECT id, term, kind, replacement, notes FROM terms WHERE id = ? AND workspace_id = ?",
        (term_id, principal.workspace_id),
    )
    assert row is not None
    return TermOut(**row)


@router.put("/terms/{term_id}", response_model=TermOut)
def update_term(
    term_id: int,
    payload: TermCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> TermOut:
    ts = now_iso()
    with db.tx() as conn:
        current = conn.execute(
            _sql("SELECT term FROM terms WHERE id = ? AND workspace_id = ?"),
            (term_id, principal.workspace_id),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="That brand term was not found.")
        conn.execute(
            _sql(
                "UPDATE terms SET term = ?, kind = ?, replacement = ?, notes = ?"
                " WHERE id = ? AND workspace_id = ?"
            ),
            (
                payload.term, payload.kind, payload.replacement, payload.notes,
                term_id, principal.workspace_id,
            ),
        )
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_term.updated",
            "brand_term", term_id, f"Updated terminology: {current['term']} → {payload.term}", ts,
        )
    row = db.query_one(
        "SELECT id, term, kind, replacement, notes FROM terms WHERE id = ? AND workspace_id = ?",
        (term_id, principal.workspace_id),
    )
    assert row is not None
    return TermOut(**row)


@router.delete("/terms/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(
    term_id: int,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> Response:
    ts = now_iso()
    with db.tx() as conn:
        current = conn.execute(
            _sql("SELECT term FROM terms WHERE id = ? AND workspace_id = ?"),
            (term_id, principal.workspace_id),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="That brand term was not found.")
        conn.execute(
            _sql("DELETE FROM terms WHERE id = ? AND workspace_id = ?"),
            (term_id, principal.workspace_id),
        )
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_term.deleted",
            "brand_term", term_id, f"Deleted terminology: {current['term']}", ts,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/facts", response_model=FactOut, status_code=status.HTTP_201_CREATED)
def add_fact(
    payload: FactCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> FactOut:
    _validate_source_passage(db, principal.workspace_id, payload.source_passage_id)
    ts = now_iso()
    with db.tx() as conn:
        inserted = conn.execute(
            _sql(
                "INSERT INTO facts (workspace_id, fact_key, value, unit, source_passage_id,"
                " effective_date, created_at) VALUES (?,?,?,?,?,?,?) RETURNING id"
            ),
            (
                principal.workspace_id, payload.fact_key, payload.value,
                payload.unit, payload.source_passage_id, ts[:10], ts,
            ),
        ).fetchone()
        fact_id = int(inserted["id"])
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_fact.created",
            "brand_fact", fact_id, f"Added approved fact: {payload.fact_key}", ts,
        )
    row = db.query_one(
        "SELECT id, fact_key, value, unit, source_passage_id FROM facts"
        " WHERE id = ? AND workspace_id = ?",
        (fact_id, principal.workspace_id),
    )
    assert row is not None
    return FactOut(**row)


@router.put("/facts/{fact_id}", response_model=FactOut)
def update_fact(
    fact_id: int,
    payload: FactCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> FactOut:
    _validate_source_passage(db, principal.workspace_id, payload.source_passage_id)
    ts = now_iso()
    with db.tx() as conn:
        current = conn.execute(
            _sql("SELECT fact_key FROM facts WHERE id = ? AND workspace_id = ?"),
            (fact_id, principal.workspace_id),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="That approved fact was not found.")
        conn.execute(
            _sql(
                "UPDATE facts SET fact_key = ?, value = ?, unit = ?, source_passage_id = ?"
                " WHERE id = ? AND workspace_id = ?"
            ),
            (
                payload.fact_key, payload.value, payload.unit, payload.source_passage_id,
                fact_id, principal.workspace_id,
            ),
        )
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_fact.updated",
            "brand_fact", fact_id, f"Updated approved fact: {current['fact_key']} → {payload.fact_key}", ts,
        )
    row = db.query_one(
        "SELECT id, fact_key, value, unit, source_passage_id FROM facts"
        " WHERE id = ? AND workspace_id = ?",
        (fact_id, principal.workspace_id),
    )
    assert row is not None
    return FactOut(**row)


@router.delete("/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fact(
    fact_id: int,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> Response:
    ts = now_iso()
    with db.tx() as conn:
        current = conn.execute(
            _sql("SELECT fact_key FROM facts WHERE id = ? AND workspace_id = ?"),
            (fact_id, principal.workspace_id),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="That approved fact was not found.")
        conn.execute(
            _sql("DELETE FROM facts WHERE id = ? AND workspace_id = ?"),
            (fact_id, principal.workspace_id),
        )
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_fact.deleted",
            "brand_fact", fact_id, f"Deleted approved fact: {current['fact_key']}", ts,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/palette", response_model=PaletteOut, status_code=status.HTTP_201_CREATED)
def add_palette(
    payload: PaletteCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> PaletteOut:
    ts = now_iso()
    with db.tx() as conn:
        inserted = conn.execute(
            _sql(
                "INSERT INTO palette_colors (workspace_id, name, hex, role, created_at)"
                " VALUES (?,?,?,?,?) RETURNING id"
            ),
            (principal.workspace_id, payload.name, payload.hex, payload.role, ts),
        ).fetchone()
        palette_id = int(inserted["id"])
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_palette.created",
            "brand_palette", palette_id, f"Added palette colour: {payload.name}", ts,
        )
    row = db.query_one(
        "SELECT id, name, hex, role FROM palette_colors WHERE id = ? AND workspace_id = ?",
        (palette_id, principal.workspace_id),
    )
    assert row is not None
    return PaletteOut(**row)


@router.put("/palette/{color_id}", response_model=PaletteOut)
def update_palette(
    color_id: int,
    payload: PaletteCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> PaletteOut:
    ts = now_iso()
    with db.tx() as conn:
        current = conn.execute(
            _sql("SELECT name FROM palette_colors WHERE id = ? AND workspace_id = ?"),
            (color_id, principal.workspace_id),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="That palette colour was not found.")
        conn.execute(
            _sql(
                "UPDATE palette_colors SET name = ?, hex = ?, role = ?"
                " WHERE id = ? AND workspace_id = ?"
            ),
            (payload.name, payload.hex, payload.role, color_id, principal.workspace_id),
        )
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_palette.updated",
            "brand_palette", color_id, f"Updated palette colour: {current['name']} → {payload.name}", ts,
        )
    row = db.query_one(
        "SELECT id, name, hex, role FROM palette_colors WHERE id = ? AND workspace_id = ?",
        (color_id, principal.workspace_id),
    )
    assert row is not None
    return PaletteOut(**row)


@router.delete("/palette/{color_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_palette(
    color_id: int,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> Response:
    ts = now_iso()
    with db.tx() as conn:
        current = conn.execute(
            _sql("SELECT name FROM palette_colors WHERE id = ? AND workspace_id = ?"),
            (color_id, principal.workspace_id),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="That palette colour was not found.")
        conn.execute(
            _sql("DELETE FROM palette_colors WHERE id = ? AND workspace_id = ?"),
            (color_id, principal.workspace_id),
        )
        _record_brand_change(
            conn, principal.workspace_id, principal.display_name, "brand_palette.deleted",
            "brand_palette", color_id, f"Deleted palette colour: {current['name']}", ts,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
@router.post("/passages", response_model=PassageOut, status_code=status.HTTP_201_CREATED)
def add_passage(
    payload: PassageCreate,
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> PassageOut:
    ts = now_iso()
    db.insert(
        "INSERT INTO knowledge_documents (workspace_id, title, doc_type, status, version,"
        " effective_date, created_at) VALUES (?,?,'manual','approved',1,?,?)",
        (principal.workspace_id, payload.source.strip(), ts[:10], ts),
    )
    doc = db.query_one(
        "SELECT id FROM knowledge_documents WHERE workspace_id = ? ORDER BY id DESC LIMIT 1",
        (principal.workspace_id,),
    )
    assert doc is not None
    db.insert(
        "INSERT INTO passages (workspace_id, document_id, source, page, section, text, created_at)"
        " VALUES (?,?,?,1,?,?,?)",
        (principal.workspace_id, int(doc["id"]), payload.source.strip(), payload.section,
         payload.text.strip(), ts),
    )
    row = db.query_one(
        "SELECT id, source, section, page, text FROM passages WHERE workspace_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (principal.workspace_id,),
    )
    assert row is not None
    return PassageOut(**row)


@router.post("/guidelines/upload", response_model=list[PassageOut], status_code=status.HTTP_201_CREATED)
async def upload_guideline(
    file: UploadFile = File(...),
    title: str = "",
    principal: Principal = Depends(require_role("manager")),
    db: Database = Depends(get_db),
) -> list[PassageOut]:
    """Ingest a guideline PDF into approved passages, one passage per page."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Upload a PDF guideline document.")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="That PDF is larger than 15 MB.")
    try:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="That file could not be read as a PDF.") from exc

    pages = [(i + 1, page.get_text("text").strip()) for i, page in enumerate(doc)]
    doc.close()
    pages = [(n, t) for n, t in pages if t]
    if not pages:
        raise HTTPException(
            status_code=422,
            detail="No selectable text found in that PDF. Scanned PDFs need OCR, which is not enabled.",
        )

    ts = now_iso()
    doc_title = (title or (file.filename or "Uploaded guideline")).strip()[:200]
    source_filename = (file.filename or "guideline.pdf").replace("\r", "").replace("\n", "")[:240]
    object_key = f"guidelines/{principal.workspace_id}/{secrets.token_urlsafe(24)}"
    try:
        put_private_object(object_key, data, "application/pdf")
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    db.insert(
        "INSERT INTO knowledge_documents (workspace_id, title, doc_type, status, version,"
        " effective_date, source_object_key, source_filename, source_content_type, source_size,"
        " created_at) VALUES (?,?,'guideline','approved',1,?,?,?,?,?,?)",
        (
            principal.workspace_id, doc_title, ts[:10], object_key, source_filename,
            "application/pdf", len(data), ts,
        ),
    )
    doc_row = db.query_one(
        "SELECT id FROM knowledge_documents WHERE workspace_id = ? ORDER BY id DESC LIMIT 1",
        (principal.workspace_id,),
    )
    assert doc_row is not None
    doc_id = int(doc_row["id"])

    created: list[PassageOut] = []
    for page_no, text in pages:
        # Chunk long pages so retrieval stays precise.
        chunks = [text[i : i + 1200] for i in range(0, len(text), 1200)] or [text]
        for chunk in chunks:
            db.insert(
                "INSERT INTO passages (workspace_id, document_id, source, page, section, text, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (principal.workspace_id, doc_id, doc_title, page_no, f"Page {page_no}", chunk, ts),
            )
            row = db.query_one(
                "SELECT id, source, section, page, text FROM passages WHERE workspace_id = ?"
                " ORDER BY id DESC LIMIT 1",
                (principal.workspace_id,),
            )
            assert row is not None
            created.append(PassageOut(**row))

    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id, detail, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (principal.workspace_id, principal.display_name, "guideline.ingested", "knowledge_document",
         doc_id, f"{len(created)} passages from {doc_title}", ts),
    )
    return created


@router.get("/guidelines/{document_id}/source")
def download_guideline_source(
    document_id: int,
    principal: Principal = Depends(get_principal),
    db: Database = Depends(get_db),
) -> Response:
    document = db.query_one(
        "SELECT source_object_key, source_filename, source_content_type"
        " FROM knowledge_documents WHERE id = ? AND workspace_id = ?",
        (document_id, principal.workspace_id),
    )
    if not document or not document.get("source_object_key"):
        raise HTTPException(status_code=404, detail="That guideline has no stored source file.")
    try:
        content = get_private_object(document["source_object_key"])
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    filename = quote(document.get("source_filename") or "guideline.pdf", safe="")
    return Response(
        content=content,
        media_type=document.get("source_content_type") or "application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
        },
    )
