from __future__ import annotations

import html
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SUBMISSION.md"
OUTPUT = ROOT / "BrandShield_Product.pdf"


def inline_markup(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        parts.append(html.escape(text[cursor : match.start()]))
        label, target = match.groups()
        parts.append(
            f'<a href="{html.escape(target, quote=True)}">{html.escape(label)}</a>'
        )
        cursor = match.end()
    parts.append(html.escape(text[cursor:]))
    result = "".join(parts)
    result = re.sub(r"`([^`]+)`", r"<code>\1</code>", result)
    result = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", result)
    result = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", result)
    return result


def markdown_body(source: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{inline_markup(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    for line in source.splitlines():
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                blocks.append(f'<pre class="diagram">{html.escape(chr(10).join(code_lines))}</pre>')
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{inline_markup(heading.group(2))}</h{level}>")
        elif line.startswith("- "):
            flush_paragraph()
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{inline_markup(line[2:])}</li>")
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            close_list()
            paragraph.append(line.strip())

    flush_paragraph()
    close_list()
    if in_code and code_lines:
        blocks.append(f'<pre class="diagram">{html.escape(chr(10).join(code_lines))}</pre>')
    return "\n".join(blocks)


def build_pdf() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    body = markdown_body(source)
    document_html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: sans-serif; font-size: 10.5pt; color: #26332c; line-height: 1.42; }}
h1 {{ color: #174b35; font-size: 25pt; margin: 0 0 12pt; }}
h2 {{ color: #174b35; font-size: 16pt; margin: 18pt 0 6pt; border-bottom: 1px solid #d6e5dc; }}
h3 {{ color: #285d44; font-size: 12pt; margin: 12pt 0 4pt; }}
p {{ margin: 4pt 0 8pt; }}
ul {{ margin: 3pt 0 8pt 14pt; padding-left: 8pt; }}
li {{ margin: 2pt 0; }}
strong {{ color: #26332c; }}
code {{ font-family: monospace; font-size: 9pt; color: #174b35; }}
a {{ color: #17684d; text-decoration: underline; }}
pre.diagram {{ font-family: monospace; font-size: 8pt; background-color: #f0f5f1; padding: 8pt; }}
</style>
</head>
<body>{body}</body>
</html>"""

    page_rect = pymupdf.paper_rect("a4")
    content_rect = page_rect + (42, 42, -42, -42)
    story = pymupdf.Story(html=document_html)
    writer = pymupdf.DocumentWriter(str(OUTPUT))
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _filled = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()

    pdf = pymupdf.open(OUTPUT)
    try:
        text = "\n".join(page.get_text() for page in pdf)
        required_sections = (
            "Round 3 submission",
            "Complete feature list",
            "Technical architecture",
            "Improvements delivered",
            "Testing details",
            "Product roadmap",
        )
        missing = [section for section in required_sections if section not in text]
        if missing:
            raise RuntimeError(f"Generated PDF is missing sections: {', '.join(missing)}")
        if len(pdf) < 2:
            raise RuntimeError("Generated PDF is unexpectedly short.")
    finally:
        pdf.close()

    print(f"Generated {OUTPUT.name} ({OUTPUT.stat().st_size:,} bytes).")


if __name__ == "__main__":
    build_pdf()
