"""Seed data for the fictional demo company, Northwind Foods.

Everything here is invented. It exists so a stranger can open the app and run the
full check -> findings -> fix -> approval loop with real data on first load.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .db import Database
from .samples import SAMPLES

DEMO_SLUG = "northwind-foods"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Brand knowledge
# ---------------------------------------------------------------------------
GUIDELINES = [
    {
        "title": "Northwind Foods Brand Voice Guide",
        "doc_type": "voice",
        "passages": [
            (
                "Voice and tone",
                "Northwind Foods speaks like a warm, knowledgeable neighbour. We are "
                "confident but never boastful. We write in plain language, use short "
                "sentences, and prefer concrete detail over adjectives. We say 'we', "
                "never 'the company'.",
            ),
            (
                "Tone: what to avoid",
                "Avoid hype and superlatives. Do not use words such as cheapest, "
                "guaranteed, miracle, detox, superfood, or number one. Do not create "
                "urgency or pressure. Never promise a health outcome.",
            ),
            (
                "Headlines and punctuation",
                "Headlines use sentence case, not Title Case. Avoid exclamation marks "
                "in body copy and avoid all-caps words. Emoji are allowed sparingly in "
                "social posts, at most one per post.",
            ),
            (
                "Claims policy",
                "Every factual claim must be traceable to an approved fact sheet. If a "
                "claim cannot be supported by an approved source, it must be removed or "
                "flagged for human verification. We never describe a competitor.",
            ),
        ],
    },
    {
        "title": "Northwind Harvest Oat Bars \u2014 Product Fact Sheet",
        "doc_type": "fact_sheet",
        "passages": [
            (
                "Nutrition",
                "Each Northwind Harvest Oat Bar contains 6g of protein. The bar weighs "
                "45g. It contains no palm oil.",
            ),
            (
                "Ingredients",
                "Northwind Harvest Oat Bars are made with oats, almonds, honey and sea "
                "salt. There are no artificial colours or preservatives.",
            ),
            (
                "Pricing",
                "The recommended retail price is \u20b9249 for a pack of 6 bars. "
                "Introductory offers must be approved by the brand manager.",
            ),
            (
                "Launch",
                "Northwind Harvest Oat Bars launched on 12 March 2025 and ship "
                "nationwide across India.",
            ),
            (
                "Certifications",
                "Northwind Foods holds FSSAI certification. The oat bars are not USDA "
                "Organic certified and must not be described as organic.",
            ),
        ],
    },
    {
        "title": "Northwind Foods Visual Identity Standards",
        "doc_type": "visual",
        "passages": [
            (
                "Colour",
                "The primary brand colour is Northwind Green #1F5C3A. Harvest Gold "
                "#E8A33D is the accent colour. Oat Cream #F5EFE3 is the background "
                "colour. Charcoal #2B2B2B is used for body text.",
            ),
            (
                "Logo usage",
                "The logo must keep clear space equal to the height of the letter N on "
                "all sides. Never stretch, rotate, recolour or place the logo on a "
                "low-contrast background.",
            ),
            (
                "Accessibility",
                "Body text must meet WCAG AA contrast of at least 4.5:1 against its "
                "background. Large display text must meet at least 3:1.",
            ),
        ],
    },
]

APPROVED_TERMS = [
    ("Northwind Harvest Oat Bars", "Use the full product name on first mention."),
    ("wholesome", "Preferred positive descriptor."),
    ("made with real ingredients", "Approved supporting phrase."),
    ("Northwind Kitchen", "Approved name for the product team."),
]

PROHIBITED_TERMS = [
    ("cheapest", "affordable", "Superlative pricing claim; not substantiated."),
    ("guaranteed", "designed", "Absolute promise; we never guarantee an outcome."),
    ("detox", "refresh", "Unapproved health claim."),
    ("superfood", "wholesome snack", "Unapproved health claim."),
    ("#1", "leading", "Ranking claim requires third-party evidence we do not hold."),
    ("the #1", "a leading", "Ranking claim requires third-party evidence we do not hold."),
    ("best price", "great value", "Superlative pricing claim; not substantiated."),
    ("miracle", "remarkable", "Unapproved health claim."),
]

BANNED_PHRASES = [
    ("thrilled to announce", "Hype opener; the voice guide asks for plain, warm language."),
    ("game changer", "Hype phrase."),
    ("act now", "Creates urgency, which the voice guide prohibits."),
    ("don't miss out", "Creates urgency, which the voice guide prohibits."),
]

FACTS = [
    ("protein_per_bar", "6", "g", "Nutrition"),
    ("pack_price", "249", "INR", "Pricing"),
    ("launch_date", "2025-03-12", "date", "Launch"),
    ("certifications", "FSSAI", "list", "Certifications"),
    ("ingredients", "oats, almonds, honey, sea salt", "list", "Ingredients"),
]

PALETTE = [
    ("Northwind Green", "#1F5C3A", "primary"),
    ("Harvest Gold", "#E8A33D", "accent"),
    ("Oat Cream", "#F5EFE3", "background"),
    ("Charcoal", "#2B2B2B", "text"),
]

ASSETS = [
    ("logo", "Northwind wordmark", "Clear space = height of the letter N on all sides."),
    ("logo", "Northwind leaf mark", "Never recolour; never place on Harvest Gold."),
]

# Required disclaimers per content type. ``None`` means no disclaimer required.
DISCLAIMERS = {
    "ad": "T&Cs apply.",
    "email": "You are receiving this email because you subscribed to Northwind Foods updates. Unsubscribe at any time.",
    "social": None,
    "document": None,
}

DEMO_MEMBERS = [
    ("demo-creator", "creator@northwind.example", "Priya Raman", "creator"),
    ("demo-manager", "manager@northwind.example", "Arun Mehta", "manager"),
    ("demo-approver", "approver@northwind.example", "Rohan Iyer", "approver"),
]


def seed_workspace(db: Database) -> int:
    """Create the demo workspace and all brand knowledge. Returns workspace id."""
    existing = db.query_one("SELECT id FROM workspaces WHERE slug = ?", (DEMO_SLUG,))
    if existing:
        return int(existing["id"])

    ts = now_iso()
    db.insert(
        "INSERT INTO workspaces (name, slug, created_at) VALUES (?, ?, ?)",
        ("Northwind Foods", DEMO_SLUG, ts),
    )
    ws = db.query_one("SELECT id FROM workspaces WHERE slug = ?", (DEMO_SLUG,))
    assert ws is not None
    ws_id = int(ws["id"])

    for user_id, email, name, role in DEMO_MEMBERS:
        db.insert(
            "INSERT INTO memberships (workspace_id, user_id, email, display_name, role, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (ws_id, user_id, email, name, role, ts),
        )

    # --- guidelines -> documents -> passages ------------------------------
    passage_ids: dict[str, int] = {}
    for doc in GUIDELINES:
        db.insert(
            "INSERT INTO knowledge_documents"
            " (workspace_id, title, doc_type, status, version, effective_date, created_at)"
            " VALUES (?, ?, ?, 'approved', 1, ?, ?)",
            (ws_id, doc["title"], doc["doc_type"], "2025-01-01", ts),
        )
        row = db.query_one(
            "SELECT id FROM knowledge_documents WHERE workspace_id = ? AND title = ?",
            (ws_id, doc["title"]),
        )
        assert row is not None
        doc_id = int(row["id"])
        for section, text in doc["passages"]:
            db.insert(
                "INSERT INTO passages (workspace_id, document_id, source, page, section, text, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ws_id, doc_id, doc["title"], 1, section, text, ts),
            )
            p = db.query_one(
                "SELECT id FROM passages WHERE workspace_id = ? AND section = ? AND text = ?",
                (ws_id, section, text),
            )
            assert p is not None
            passage_ids[section] = int(p["id"])

    # --- terms -------------------------------------------------------------
    for term, notes in APPROVED_TERMS:
        db.insert(
            "INSERT INTO terms (workspace_id, term, kind, replacement, notes, created_at)"
            " VALUES (?, ?, 'approved', NULL, ?, ?)",
            (ws_id, term, notes, ts),
        )
    for term, replacement, notes in PROHIBITED_TERMS:
        db.insert(
            "INSERT INTO terms (workspace_id, term, kind, replacement, notes, created_at)"
            " VALUES (?, ?, 'prohibited', ?, ?, ?)",
            (ws_id, term, replacement, notes, ts),
        )

    # --- facts -------------------------------------------------------------
    for key, value, unit, section in FACTS:
        db.insert(
            "INSERT INTO facts (workspace_id, fact_key, value, unit, source_passage_id,"
            " effective_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ws_id, key, value, unit, passage_ids.get(section), "2025-01-01", ts),
        )

    # --- palette + assets --------------------------------------------------
    for name, hex_value, role in PALETTE:
        db.insert(
            "INSERT INTO palette_colors (workspace_id, name, hex, role, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (ws_id, name, hex_value, role, ts),
        )
    for kind, name, notes in ASSETS:
        db.insert(
            "INSERT INTO brand_assets (workspace_id, kind, name, notes, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (ws_id, kind, name, notes, ts),
        )

    db.insert(
        "INSERT INTO audit_events (workspace_id, actor, action, entity_type, entity_id, detail, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ws_id, "system", "workspace.seeded", "workspace", ws_id, "Demo workspace created", ts),
    )
    return ws_id


def seed_samples(db: Database, ws_id: int) -> None:
    """Create the three sample drafts as content items in Draft status."""
    ts = now_iso()
    for sample in SAMPLES:
        existing = db.query_one(
            "SELECT id FROM content_items WHERE workspace_id = ? AND title = ?",
            (ws_id, sample["title"]),
        )
        if existing:
            continue
        db.insert(
            "INSERT INTO content_items"
            " (workspace_id, title, content_type, status, created_by, created_at, updated_at)"
            " VALUES (?, ?, ?, 'Draft', 'demo-creator', ?, ?)",
            (ws_id, sample["title"], sample["content_type"], ts, ts),
        )
        item = db.query_one(
            "SELECT id FROM content_items WHERE workspace_id = ? AND title = ?",
            (ws_id, sample["title"]),
        )
        assert item is not None
        item_id = int(item["id"])
        db.insert(
            "INSERT INTO content_versions"
            " (content_item_id, workspace_id, version_no, body, created_by, created_at, status)"
            " VALUES (?, ?, 1, ?, 'demo-creator', ?, 'Draft')",
            (item_id, ws_id, sample["body"], ts),
        )
        ver = db.query_one(
            "SELECT id FROM content_versions WHERE content_item_id = ? AND version_no = 1",
            (item_id,),
        )
        assert ver is not None
        db.execute(
            "UPDATE content_items SET current_version_id = ? WHERE id = ?",
            (int(ver["id"]), item_id),
        )


def seed_all(db: Database) -> int:
    ws_id = seed_workspace(db)
    seed_samples(db, ws_id)
    return ws_id


def new_demo_token() -> str:
    return uuid.uuid4().hex
