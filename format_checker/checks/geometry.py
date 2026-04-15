from __future__ import annotations

import fitz

from ..models import Issue
from ..profile import Profile


def _text_spans(page: fitz.Page):
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if (span.get("text") or "").strip():
                    yield span


EDGE_BAND = 80.0   # pt from top/bottom: "near the page edge"
SHORT_BLOCK_CHARS = 120  # blocks shorter than this near an edge are treated as headers/footers


def _page_text_bbox(page: fitz.Page) -> tuple[float, float, float, float] | None:
    """Bounding box of the main text, ignoring running headers, page numbers, etc.

    Running headers/footers are short blocks (page number, venue banner, running title)
    that sit near the top or bottom edge. Body paragraphs and footnotes are long
    multi-line blocks, so a char-count + position filter reliably separates them.
    """
    page_h = page.rect.height
    xs0, ys0, xs1, ys1 = [], [], [], []
    for block in page.get_text("blocks") or []:
        x0, y0, x1, y1, text, *_ = block
        if not text or not text.strip():
            continue
        n_chars = len(text.strip())
        y_center = (y0 + y1) / 2
        near_edge = y_center < EDGE_BAND or y_center > page_h - EDGE_BAND
        if near_edge and n_chars < SHORT_BLOCK_CHARS:
            continue
        xs0.append(x0); ys0.append(y0); xs1.append(x1); ys1.append(y1)
    if not xs0:
        return None
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def run(doc: fitz.Document, profile: Profile, body_pages: list[int]) -> list[Issue]:
    issues: list[Issue] = []
    exp = profile.expected_text_rect
    tol = profile.tolerance_pt
    pages_to_check = body_pages or list(range(doc.page_count))
    # Skip the title page (page 1) — it has an irregular layout (title block,
    # author list, abstract, and often a copyright/ISBN footer) that doesn't
    # obey the body text-block geometry.
    interior = [p for p in pages_to_check if p != 0] or pages_to_check
    # Sample first, middle, last of the remaining body pages.
    sample = {interior[0], interior[len(interior) // 2], interior[-1]}
    for i in sorted(sample):
        page = doc[i]
        bbox = _page_text_bbox(page)
        if bbox is None:
            continue
        ex0, ey0, ex1, ey1 = exp
        x0, y0, x1, y1 = bbox
        violations = []
        if x0 + tol < ex0:
            violations.append(f"left {x0:.0f} < {ex0:.0f}")
        if y0 + tol < ey0:
            violations.append(f"top {y0:.0f} < {ey0:.0f}")
        if x1 - tol > ex1:
            violations.append(f"right {x1:.0f} > {ex1:.0f}")
        if y1 - tol > ey1:
            violations.append(f"bottom {y1:.0f} > {ey1:.0f}")
        if violations:
            issues.append(
                Issue(
                    severity="error",
                    check="geometry.margins",
                    message="Text extends outside the expected text block.",
                    expected=f"bbox {ex0:.0f},{ey0:.0f},{ex1:.0f},{ey1:.0f}",
                    actual="; ".join(violations),
                    page=i + 1,
                    bbox=bbox,
                )
            )
    return issues
