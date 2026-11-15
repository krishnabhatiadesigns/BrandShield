"""Text extraction and span segmentation.

The review pipeline needs character offsets so the UI can highlight the exact
affected text. Everything here works on plain strings and returns offsets into
the *original* body, so highlights always line up with what the creator typed.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

# Sentence boundary: end punctuation followed by whitespace, or a newline.
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]*", re.UNICODE)


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


def split_sentences(body: str) -> list[Span]:
    """Split into sentence-like spans, preserving exact offsets."""
    spans: list[Span] = []
    for match in _SENTENCE_RE.finditer(body):
        raw = match.group(0)
        if not raw.strip():
            continue
        # Trim leading whitespace but keep offsets accurate.
        lead = len(raw) - len(raw.lstrip())
        start = match.start() + lead
        end = match.end()
        text = body[start:end].rstrip()
        if not text:
            continue
        spans.append(Span(start=start, end=start + len(text), text=text))
    return spans


def find_all(body: str, needle: str) -> list[tuple[int, int]]:
    """Case-insensitive, word-boundary-aware search returning (start, end) pairs."""
    if not needle:
        return []
    pattern = re.escape(needle)
    # Only apply word boundaries when the needle starts/ends with a word char.
    if re.match(r"\w", needle[0]):
        pattern = r"\b" + pattern
    if re.match(r"\w", needle[-1]):
        pattern = pattern + r"\b"
    out: list[tuple[int, int]] = []
    for m in re.finditer(pattern, body, flags=re.IGNORECASE):
        out.append((m.start(), m.end()))
    return out


def sentence_containing(body: str, start: int, end: int) -> Span:
    """Return the sentence span that contains [start, end)."""
    for span in split_sentences(body):
        if span.start <= start < span.end or span.start < end <= span.end:
            return span
    return Span(start=start, end=end, text=body[start:end])


# ---------------------------------------------------------------------------
# File extraction
# ---------------------------------------------------------------------------
class ExtractionError(Exception):
    pass


def extract_pdf(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("PDF support is not installed on the server.") from exc
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ExtractionError("That file could not be read as a PDF.") from exc
    parts: list[str] = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    text = "\n".join(parts).strip()
    if not text:
        raise ExtractionError(
            "No selectable text found in that PDF. It may be a scan; OCR is not enabled."
        )
    return text


def extract_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("DOCX support is not installed on the server.") from exc
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("That file could not be read as a DOCX.") from exc
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts).strip()
    if not text:
        raise ExtractionError("That DOCX appears to be empty.")
    return text


def extract_upload(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_pdf(data)
    if lower.endswith(".docx"):
        return extract_docx(data)
    if lower.endswith((".txt", ".md")):
        try:
            return data.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ExtractionError("That text file is not valid UTF-8.") from exc
    raise ExtractionError("Unsupported file type. Upload a PDF, DOCX or TXT file.")
