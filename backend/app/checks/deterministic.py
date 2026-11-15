"""Deterministic brand checks.

These run in pure Python with no network access, so the review pipeline always
returns findings even when the LLM is unavailable. Each check returns
``FindingDraft`` objects with exact character offsets into the draft body.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..text import find_all, sentence_containing, split_sentences
from .base import FindingDraft

# ---------------------------------------------------------------------------
# Workspace brand context passed into the checks
# ---------------------------------------------------------------------------


@dataclass
class BrandContext:
    workspace_id: int
    prohibited_terms: list[dict]
    approved_terms: list[dict]
    facts: list[dict]
    passages: list[dict]
    palette: list[dict]
    assets: list[dict]
    required_disclaimer: str | None
    content_type: str

    def passage_for_section(self, section: str) -> int | None:
        for p in self.passages:
            if (p.get("section") or "").lower() == section.lower():
                return int(p["id"])
        return None

    def passage_for_text(self, needle: str) -> int | None:
        needle = needle.lower()
        for p in self.passages:
            if needle in (p.get("text") or "").lower():
                return int(p["id"])
        return None


# ---------------------------------------------------------------------------
# 1. Prohibited terminology
# ---------------------------------------------------------------------------
def check_prohibited_terms(body: str, ctx: BrandContext) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for term in ctx.prohibited_terms:
        word = term["term"]
        for start, end in find_all(body, word):
            # Contract: ``suggestion`` replaces exactly [span_start, span_end).
            replacement = (term.get("replacement") or "").strip() or None
            # Absorb a preceding article so "We're the #1" becomes "We're a leading"
            # rather than "We're the a leading".
            if replacement and re.match(r"^(a|an)\s", replacement, re.IGNORECASE):
                prefix = re.search(r"\b(the|a|an)\s+$", body[:start], re.IGNORECASE)
                if prefix:
                    start = prefix.start()
            out.append(
                FindingDraft(
                    category="terminology",
                    severity="high",
                    affected_text=body[start:end],
                    rule=f"Prohibited term: \u201c{word}\u201d",
                    explanation=(
                        f"\u201c{word}\u201d is on the prohibited terminology list. "
                        f"{term.get('notes') or 'It is not approved for brand use.'}"
                    ),
                    evidence_status="supported",
                    suggestion=replacement,
                    source_passage_id=ctx.passage_for_section("Tone: what to avoid")
                    or ctx.passage_for_text("prohibited"),
                    confidence=0.95,
                    span_start=start,
                    span_end=end,
                )
            )
    # Longer prohibited terms win: "the #1" beats "#1" on the same words.
    out.sort(key=lambda f: (f.span_start or 0, -(f.span_end or 0) + (f.span_start or 0)))
    deduped: list[FindingDraft] = []
    for f in out:
        if any(
            d.span_start is not None
            and f.span_start is not None
            and d.span_start <= f.span_start
            and (f.span_end or 0) <= (d.span_end or 0)
            for d in deduped
        ):
            continue
        deduped.append(f)
    return deduped


# ---------------------------------------------------------------------------
# 2. Wrong product names (near-miss against the approved list)
# ---------------------------------------------------------------------------
_PRODUCT_CANDIDATE_RE = re.compile(
    r"\bNorthwind\s+(?:[A-Z][a-z]+\s+){0,3}(?:Bars?|Crunch|Crisp|Bites|Granola)\b"
)


def check_product_names(body: str, ctx: BrandContext) -> list[FindingDraft]:
    approved = [t["term"] for t in ctx.approved_terms if "northwind" in t["term"].lower()]
    if not approved:
        return []
    out: list[FindingDraft] = []
    for m in _PRODUCT_CANDIDATE_RE.finditer(body):
        candidate = m.group(0)
        if any(candidate.lower() == a.lower() for a in approved):
            continue
        best = max(approved, key=lambda a: SequenceMatcher(None, a.lower(), candidate.lower()).ratio())
        ratio = SequenceMatcher(None, best.lower(), candidate.lower()).ratio()
        if ratio < 0.55:
            continue
        # If the approved name already ends in "Bars", absorb a trailing "bars"
        # from the draft so the replacement does not leave "…Oat Bars bars".
        span_end = m.end()
        if best.lower().endswith("bars"):
            trailing = re.match(r"\s+bars?\b", body[span_end:], re.IGNORECASE)
            if trailing:
                span_end += trailing.end()
        out.append(
            FindingDraft(
                category="product_name",
                severity="high",
                affected_text=body[m.start() : span_end],
                rule="Product name must match the approved product name",
                explanation=(
                    f"\u201c{candidate}\u201d is not an approved product name. "
                    f"The approved name is \u201c{best}\u201d."
                ),
                evidence_status="contradicted",
                suggestion=best,
                source_passage_id=ctx.passage_for_text("Northwind Harvest Oat Bars are made")
                or ctx.passage_for_section("Ingredients"),
                confidence=0.9,
                span_start=m.start(),
                span_end=span_end,
            )
        )
    return out


# ---------------------------------------------------------------------------
# 3. Required disclaimers by content type
# ---------------------------------------------------------------------------
def check_disclaimers(body: str, ctx: BrandContext) -> list[FindingDraft]:
    required = ctx.required_disclaimer
    if not required:
        return []
    # Compare on a normalised form so punctuation/spacing differences don't matter.
    norm = re.sub(r"\s+", " ", body).lower()
    probe = re.sub(r"\s+", " ", required).lower()[:60]
    if probe in norm:
        return []
    # The disclaimer is an *insertion* at the end of the draft, not a rewrite of
    # the last sentence. A zero-width span keeps it from colliding with any other
    # finding that happens to sit in the final sentence.
    insert_at = len(body.rstrip())
    return [
        FindingDraft(
            category="disclaimer",
            severity="high",
            affected_text="(end of draft)",
            rule=f"Required disclaimer for {ctx.content_type} content",
            explanation=(
                f"{ctx.content_type.capitalize()} content must carry the approved "
                "disclaimer. It is missing from this draft."
            ),
            evidence_status="supported",
            suggestion="\n\n" + required,
            source_passage_id=ctx.passage_for_section("Claims policy"),
            confidence=0.95,
            span_start=insert_at,
            span_end=insert_at,
        )
    ]


# ---------------------------------------------------------------------------
# 4. Banned phrases and punctuation
# ---------------------------------------------------------------------------
BANNED_PHRASES = [
    ("thrilled to announce", "Hype opener; the voice guide asks for plain, warm language."),
    ("game changer", "Hype phrase."),
    ("act now", "Creates urgency, which the voice guide prohibits."),
    ("don't miss out", "Creates urgency, which the voice guide prohibits."),
    ("guaranteed to", "Absolute promise; we never guarantee an outcome."),
]

_ALL_CAPS_RE = re.compile(r"\b[A-Z]{4,}\b")
# Legitimate acronyms that must not be flagged as shouting.
_ALLOWED_ACRONYMS = {
    "FSSAI",
    "USDA",
    "INR",
    "T&C",
    "FAQ",
    "PDF",
    "DOCX",
    "URL",
    "API",
    "AI",
    "WCAG",
    "CTA",
    "B2B",
    "B2C",
    "SKU",
    "GST",
    "MRP",
}
_EXCLAIM_RE = re.compile(r"!")
_EMOJI_RE = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "\U0001F1E6-\U0001F1FF" "]+"
)


def check_tone_mechanics(body: str, ctx: BrandContext) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    voice_passage = ctx.passage_for_section("Tone: what to avoid") or ctx.passage_for_section(
        "Voice and tone"
    )

    for phrase, why in BANNED_PHRASES:
        for start, end in find_all(body, phrase):
            sentence = sentence_containing(body, start, end)
            out.append(
                FindingDraft(
                    category="tone",
                    severity="medium",
                    affected_text=body[start:end],
                    rule="Banned hype phrase",
                    explanation=f"\u201c{phrase}\u201d is a banned phrase. {why}",
                    evidence_status="supported",
                    suggestion=None,
                    source_passage_id=voice_passage,
                    confidence=0.85,
                    span_start=start,
                    span_end=end,
                )
            )

    for m in _ALL_CAPS_RE.finditer(body):
        if m.group(0) in _ALLOWED_ACRONYMS:
            continue
        out.append(
            FindingDraft(
                category="tone",
                severity="low",
                affected_text=m.group(0),
                rule="Avoid all-caps words",
                explanation="The voice guide asks us to avoid all-caps words in body copy.",
                evidence_status="supported",
                suggestion=m.group(0).capitalize(),
                source_passage_id=ctx.passage_for_section("Headlines and punctuation"),
                confidence=0.7,
                span_start=m.start(),
                span_end=m.end(),
            )
        )

    exclaims = list(_EXCLAIM_RE.finditer(body))
    if len(exclaims) > 1:
        out.append(
            FindingDraft(
                category="tone",
                severity="low",
                affected_text=f"{len(exclaims)} exclamation marks",
                rule="Limit exclamation marks",
                explanation=(
                    "The voice guide asks for calm, confident copy. "
                    f"This draft uses {len(exclaims)} exclamation marks."
                ),
                evidence_status="supported",
                suggestion=None,
                source_passage_id=ctx.passage_for_section("Headlines and punctuation"),
                confidence=0.6,
                span_start=exclaims[0].start(),
                span_end=exclaims[-1].end(),
            )
        )

    emojis = list(_EMOJI_RE.finditer(body))
    if len(emojis) > 1:
        out.append(
            FindingDraft(
                category="tone",
                severity="low",
                affected_text="".join(e.group(0) for e in emojis),
                rule="At most one emoji per post",
                explanation=f"This draft uses {len(emojis)} emoji; the guide allows one.",
                evidence_status="supported",
                suggestion=None,
                source_passage_id=ctx.passage_for_section("Headlines and punctuation"),
                confidence=0.6,
                span_start=emojis[0].start(),
                span_end=emojis[-1].end(),
            )
        )
    return out


# ---------------------------------------------------------------------------
# 5. Exact fact mismatches (numbers, prices, dates, certifications)
# ---------------------------------------------------------------------------
_PROTEIN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\s+of\s+protein", re.IGNORECASE)
_PRICE_RE = re.compile(r"(?:\u20b9|Rs\.?\s?|INR\s?)(\d[\d,]*)", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}
_CERT_CLAIMS = [
    ("usda organic", "USDA Organic"),
    ("organic certified", "organic certification"),
    ("gluten free", "gluten-free certification"),
    ("vegan certified", "vegan certification"),
]


def _fact(ctx: BrandContext, key: str) -> dict | None:
    for f in ctx.facts:
        if f["fact_key"] == key:
            return f
    return None


def check_facts(body: str, ctx: BrandContext) -> list[FindingDraft]:
    out: list[FindingDraft] = []

    # -- protein ------------------------------------------------------------
    protein = _fact(ctx, "protein_per_bar")
    if protein:
        expected = float(protein["value"])
        for m in _PROTEIN_RE.finditer(body):
            actual = float(m.group(1))
            if abs(actual - expected) < 1e-9:
                continue
            out.append(
                FindingDraft(
                    category="fact",
                    severity="high",
                    affected_text=m.group(0),
                    rule="Protein per bar must match the approved fact sheet",
                    explanation=(
                        f"The draft says {m.group(1)}g of protein per bar. The approved "
                        f"fact sheet states {protein['value']}g per bar."
                    ),
                    evidence_status="contradicted",
                    suggestion=f"{protein['value']}g of protein",
                    source_passage_id=protein.get("source_passage_id"),
                    confidence=0.97,
                    span_start=m.start(),
                    span_end=m.end(),
                )
            )

    # -- price --------------------------------------------------------------
    price = _fact(ctx, "pack_price")
    if price:
        expected_price = float(str(price["value"]).replace(",", ""))
        for m in _PRICE_RE.finditer(body):
            raw = m.group(1).replace(",", "")
            try:
                actual = float(raw)
            except ValueError:
                continue
            if abs(actual - expected_price) < 1e-9:
                continue
            out.append(
                FindingDraft(
                    category="fact",
                    severity="high",
                    affected_text=m.group(0),
                    rule="Price must match the approved price list",
                    explanation=(
                        f"The draft quotes \u20b9{raw}. The approved retail price is "
                        f"\u20b9{price['value']} for a pack of 6 bars."
                    ),
                    evidence_status="contradicted",
                    suggestion=f"\u20b9{price['value']}",
                    source_passage_id=price.get("source_passage_id"),
                    confidence=0.95,
                    span_start=m.start(),
                    span_end=m.end(),
                )
            )

    # -- launch date --------------------------------------------------------
    launch = _fact(ctx, "launch_date")
    if launch:
        expected_date = str(launch["value"])  # YYYY-MM-DD
        for m in _DATE_RE.finditer(body):
            day = int(m.group(1))
            month = _MONTHS[m.group(2).lower()]
            year = int(m.group(3))
            actual = f"{year:04d}-{month:02d}-{day:02d}"
            if actual == expected_date:
                continue
            out.append(
                FindingDraft(
                    category="fact",
                    severity="high",
                    affected_text=m.group(0),
                    rule="Launch date must match the approved fact sheet",
                    explanation=(
                        f"The draft states a launch date of {m.group(0)}. The approved "
                        f"launch date is {expected_date}."
                    ),
                    evidence_status="contradicted",
                    suggestion=m.group(0),
                    source_passage_id=launch.get("source_passage_id"),
                    confidence=0.9,
                    span_start=m.start(),
                    span_end=m.end(),
                )
            )

    # -- certifications -----------------------------------------------------
    cert_fact = _fact(ctx, "certifications")
    approved_certs = (cert_fact["value"] if cert_fact else "").lower()
    for needle, label in _CERT_CLAIMS:
        if needle in approved_certs:
            continue
        for start, end in find_all(body, needle):
            out.append(
                FindingDraft(
                    category="fact",
                    severity="high",
                    affected_text=body[start:end],
                    rule="Certification claim must be on the approved list",
                    explanation=(
                        f"The draft claims {label}. The approved certifications are: "
                        f"{cert_fact['value'] if cert_fact else 'none on record'}. "
                        "This claim is not supported by an approved source."
                    ),
                    evidence_status="contradicted",
                    suggestion=None,
                    source_passage_id=cert_fact.get("source_passage_id") if cert_fact else None,
                    confidence=0.92,
                    span_start=start,
                    span_end=end,
                )
            )
    return out


# ---------------------------------------------------------------------------
# 6. Unsupported ranking / superlative claims -> needs human verification
# ---------------------------------------------------------------------------
_RANKING_PATTERNS = [
    (re.compile(r"#\s?1\b[^.!?\n]{0,40}", re.IGNORECASE), "ranking claim"),
    (re.compile(r"\bnumber\s+one\b[^.!?\n]{0,40}", re.IGNORECASE), "ranking claim"),
    (re.compile(r"\bbest[- ]selling\b[^.!?\n]{0,40}", re.IGNORECASE), "ranking claim"),
    (re.compile(r"\bmarket\s+leader\b[^.!?\n]{0,40}", re.IGNORECASE), "ranking claim"),
]


def check_unsupported_claims(body: str, ctx: BrandContext) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for pattern, label in _RANKING_PATTERNS:
        for m in pattern.finditer(body):
            text = m.group(0).strip().rstrip(",;")
            out.append(
                FindingDraft(
                    category="claim",
                    severity="high",
                    affected_text=text,
                    rule="Ranking claims require third-party evidence",
                    explanation=(
                        f"This is a {label}. No approved source in this workspace "
                        "supports it, so it needs human verification before publication."
                    ),
                    evidence_status="needs_verification",
                    suggestion=None,
                    source_passage_id=None,
                    confidence=0.8,
                    span_start=m.start(),
                    span_end=m.start() + len(text),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_deterministic_checks(body: str, ctx: BrandContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    findings += check_prohibited_terms(body, ctx)
    findings += check_product_names(body, ctx)
    findings += check_disclaimers(body, ctx)
    findings += check_tone_mechanics(body, ctx)
    findings += check_facts(body, ctx)
    findings += check_unsupported_claims(body, ctx)
    return findings


def claim_like_sentences(body: str) -> list[tuple[int, int, str]]:
    """Sentences worth retrieving evidence for (contain a number or a claim verb)."""
    claim_verbs = re.compile(
        r"\b(is|are|has|have|contains?|made|launched|available|certified|delivers?|"
        r"provides?|guarantee[sd]?|best|number|#1|only|free|natural|organic)\b",
        re.IGNORECASE,
    )
    out: list[tuple[int, int, str]] = []
    for span in split_sentences(body):
        if re.search(r"\d", span.text) or claim_verbs.search(span.text):
            out.append((span.start, span.end, span.text))
    return out
