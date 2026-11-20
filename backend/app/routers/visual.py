"""Visual brand compliance: palette similarity and WCAG contrast.

These are real calculations (CIE Lab distance and the WCAG 2.1 relative luminance
formula), not heuristics. OCR is deliberately not enabled; see the README.
"""
from __future__ import annotations

import math
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from ..auth import Principal, get_principal
from ..db import Database, get_db
from ..models import ImageVisualCheckResponse, VisualCheckRequest, VisualCheckResponse, VisualIssue

router = APIRouter(prefix="/api/visual", tags=["visual"])
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        raise ValueError(f"Invalid hex colour: {value}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _srgb_to_linear(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    # sRGB -> XYZ (D65)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    # Normalise by D65 white point
    xn, yn, zn = x / 0.95047, y / 1.0, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(xn), f(yn), f(zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """CIE76 colour difference. < 10 is a close match to the human eye."""
    a, b = _rgb_to_lab(c1), _rgb_to_lab(c2)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


@router.post("/check", response_model=VisualCheckResponse)
def check_visual(
    payload: VisualCheckRequest,
    principal: Principal = Depends(get_principal),
    db: Database = Depends(get_db),
) -> VisualCheckResponse:
    palette = db.query(
        "SELECT name, hex, role FROM palette_colors WHERE workspace_id = ?",
        (principal.workspace_id,),
    )
    issues: list[VisualIssue] = []
    matches: list[dict] = []

    for raw in payload.hex_colors:
        try:
            rgb = hex_to_rgb(raw)
        except ValueError:
            issues.append(
                VisualIssue(
                    category="visual",
                    severity="low",
                    rule="Colour must be a valid hex value",
                    explanation=f"\u201c{raw}\u201d is not a valid hex colour.",
                    affected_text=raw,
                )
            )
            continue
        best = None
        for colour in palette:
            d = delta_e(rgb, hex_to_rgb(colour["hex"]))
            if best is None or d < best[1]:
                best = (colour, d)
        if best:
            colour, d = best
            matches.append(
                {
                    "input": raw.upper(),
                    "closest": colour["name"],
                    "closest_hex": colour["hex"],
                    "delta_e": round(d, 2),
                    "on_brand": d < 10,
                }
            )
            if d >= 10:
                issues.append(
                    VisualIssue(
                        category="visual",
                        severity="medium" if d < 25 else "high",
                        rule="Colour must come from the approved palette",
                        explanation=(
                            f"{raw.upper()} is not in the approved palette. The closest "
                            f"approved colour is {colour['name']} ({colour['hex']}), "
                            f"a CIE76 difference of {d:.1f}."
                        ),
                        affected_text=raw.upper(),
                        suggestion=colour["hex"],
                    )
                )

    ratio = None
    if payload.text_hex and payload.background_hex:
        try:
            ratio = contrast_ratio(hex_to_rgb(payload.text_hex), hex_to_rgb(payload.background_hex))
        except ValueError:
            issues.append(
                VisualIssue(
                    category="visual",
                    severity="low",
                    rule="Contrast inputs must be valid hex colours",
                    explanation="One of the contrast colours was not a valid hex value.",
                    affected_text=f"{payload.text_hex} on {payload.background_hex}",
                )
            )
        else:
            if ratio < 4.5:
                issues.append(
                    VisualIssue(
                        category="visual",
                        severity="high" if ratio < 3 else "medium",
                        rule="Body text must meet WCAG AA contrast (4.5:1)",
                        explanation=(
                            f"{payload.text_hex} on {payload.background_hex} has a contrast "
                            f"ratio of {ratio:.2f}:1, below the 4.5:1 required by the visual "
                            "identity standards."
                        ),
                        affected_text=f"{payload.text_hex} on {payload.background_hex}",
                        suggestion=None,
                    )
                )

    return VisualCheckResponse(issues=issues, contrast_ratio=round(ratio, 2) if ratio else None,
                               palette_match=matches)


@router.post("/image", response_model=ImageVisualCheckResponse)
async def check_visual_image(
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    db: Database = Depends(get_db),
) -> ImageVisualCheckResponse:
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="Choose a non-empty image file.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="That image is larger than 10 MB.")
    try:
        with Image.open(BytesIO(data)) as original:
            image_format = (original.format or "").upper()
            content_type = Image.MIME.get(image_format, "")
            if content_type not in SUPPORTED_IMAGE_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail="Supported image formats are PNG, JPEG, and WebP.",
                )
            width, height = original.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=413,
                    detail="That image exceeds the 20-megapixel inspection limit.",
                )
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((512, 512))
            colors = image.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
            palette = colors.getpalette()
            counts = colors.getcolors(maxcolors=512 * 512) or []
            total = sum(count for count, _ in counts) or 1
            extracted = []
            for count, index in sorted(counts, reverse=True)[:8]:
                offset = index * 3
                rgb = palette[offset : offset + 3]
                if len(rgb) == 3:
                    extracted.append(
                        {
                            "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
                            "percentage": round(count / total * 100, 1),
                        }
                    )
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="That image is unreadable or damaged. Try a PNG, JPEG, or WebP export.",
        ) from exc

    color_result = check_visual(
        VisualCheckRequest(hex_colors=[item["hex"] for item in extracted]),
        principal,
        db,
    )
    return ImageVisualCheckResponse(
        issues=color_result.issues,
        contrast_ratio=None,
        palette_match=color_result.palette_match,
        image={
            "filename": (file.filename or "creative").replace("\r", "").replace("\n", "")[:240],
            "format": image_format,
            "width": width,
            "height": height,
            "colors": extracted,
        },
        limitations=[
            "Color palette is estimated from image pixels; transparent pixels and gradients may affect results.",
            "Text/background contrast, typography, and logo placement are not automatically verified; inspect these manually.",
        ],
    )
