"""Brand profile: guidelines, passages, terms, facts, palette, and PDF ingestion."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ..auth import Principal, get_principal, require_role
from ..db import Database, get_db
from ..models import (
    BrandProfile,
    CompanyContextUpdate,
    FactCreate,
    FactOut,
    PaletteCreate,
    PaletteOut,
    PassageCreate,
    PassageOut,
    TermCreate,
    TermOut,
)
from ..pipeline import DISCLAIMERS
from ..seed import now_iso
from ..text import ExtractionError, extract_pdf

router = APIRouter(prefix="/api/brand", tags=["brand"])


@router.get("", response_model=BrandProfile)
def get_profile(
    principal: Principal = Depends(get_principal), db: Database = Depends(get_db)
) -> BrandProfile:
    ws = principal.workspace_id
    passages = db.query(
        """
        SELECT p.id, p.source, p.section, p.page, p.text
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
        disclaimers=DISCLAIMERS,
    )


@router.put("/company-context", status_code=status.HTTP_204_NO_CONTENT)
def update_company_context(
    payload: CompanyContextUpdate,
    principal: Principal = Depends(require_role("manager", "admin")),
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
    principal: Principal = Depends(require_role("manager", "admin")),
    db: Database = Depends(get_db),
) -> TermOut:
    db.insert(
        "INSERT INTO terms (workspace_id, term, kind, replacement, notes, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (principal.workspace_id, payload.term.strip(), payload.kind,
         payload.replacement, payload.notes, now_iso()),
    )
    row = db.query_one(
        "SELECT id, term, kind, replacement, notes FROM terms WHERE workspace_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (principal.workspace_id,),
    )
    assert row is not None
    return TermOut(**row)


@router.post("/facts", response_model=FactOut, status_code=status.HTTP_201_CREATED)
def add_fact(
    payload: FactCreate,
    principal: Principal = Depends(require_role("manager", "admin")),
    db: Database = Depends(get_db),
) -> FactOut:
    db.insert(
        "INSERT INTO facts (workspace_id, fact_key, value, unit, source_passage_id,"
        " effective_date, created_at) VALUES (?,?,?,?,NULL,?,?)",
        (principal.workspace_id, payload.fact_key.strip(), payload.value.strip(),
         payload.unit, now_iso()[:10], now_iso()),
    )
    row = db.query_one(
        "SELECT id, fact_key, value, unit, source_passage_id FROM facts WHERE workspace_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (principal.workspace_id,),
    )
    assert row is not None
    return FactOut(**row)


@router.post("/palette", response_model=PaletteOut, status_code=status.HTTP_201_CREATED)
def add_palette(
    payload: PaletteCreate,
    principal: Principal = Depends(require_role("manager", "admin")),
    db: Database = Depends(get_db),
) -> PaletteOut:
    db.insert(
        "INSERT INTO palette_colors (workspace_id, name, hex, role, created_at) VALUES (?,?,?,?,?)",
        (principal.workspace_id, payload.name.strip(), payload.hex.upper(), payload.role, now_iso()),
    )
    row = db.query_one(
        "SELECT id, name, hex, role FROM palette_colors WHERE workspace_id = ? ORDER BY id DESC LIMIT 1",
        (principal.workspace_id,),
    )
    assert row is not None
    return PaletteOut(**row)


@router.post("/passages", response_model=PassageOut, status_code=status.HTTP_201_CREATED)
def add_passage(
    payload: PassageCreate,
    principal: Principal = Depends(require_role("manager", "admin")),
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
    principal: Principal = Depends(require_role("manager", "admin")),
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
    db.insert(
        "INSERT INTO knowledge_documents (workspace_id, title, doc_type, status, version,"
        " effective_date, created_at) VALUES (?,?,'guideline','approved',1,?,?)",
        (principal.workspace_id, doc_title, ts[:10], ts),
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
