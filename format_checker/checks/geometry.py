from __future__ import annotations

from collections import Counter

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

MIN_LINES_FOR_COLUMN_DETECTION = 20  # below this, the page is too sparse to read columns
COLUMN_GAP_MIN = 100.0               # min x-distance between two distinct columns
COLUMN_PEAK_MIN_FRACTION = 0.05      # a column must contain at least this fraction of body lines


def _column_count_from_x0s(x0s: list[float]) -> int:
    """Cluster line-start x-coordinates into column peaks.

    Returns 0 when there aren't enough lines for a robust call. Otherwise
    walks 4-pt buckets in descending frequency and greedily accepts those
    at least ``COLUMN_GAP_MIN`` away from any peak already accepted.
    """
    if len(x0s) < MIN_LINES_FOR_COLUMN_DETECTION:
        return 0
    threshold = max(5, len(x0s) * COLUMN_PEAK_MIN_FRACTION)
    buckets = Counter(round(x / 4) * 4 for x in x0s)
    peaks: list[int] = []
    for bucket, freq in buckets.most_common():
        if freq < threshold:
            break
        if all(abs(bucket - p) >= COLUMN_GAP_MIN for p in peaks):
            peaks.append(bucket)
    return len(peaks)


def _detect_columns(page: fitz.Page) -> int:
    """Estimate the number of text columns on a page (0 if too sparse)."""
    x0s: list[float] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            if any((sp.get("text") or "").strip() for sp in line.get("spans", [])):
                x0s.append(line["bbox"][0])
    return _column_count_from_x0s(x0s)


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
    detected_col_counts: list[int] = []
    for i in sorted(sample):
        page = doc[i]
        n_cols = _detect_columns(page)
        if n_cols > 0:
            detected_col_counts.append(n_cols)
        bbox = _page_text_bbox(page)
        if bbox is None:
            continue
        ex0, ey0, ex1, ey1 = exp
        x0, y0, x1, y1 = bbox
        violations = []
        # Left edge — symmetric: text bleeding left, OR sitting too far right
        # (margin wider than expected, classic "wrong template" signal).
        if x0 + tol < ex0:
            violations.append(f"left {x0:.0f} < {ex0:.0f}")
        elif x0 - tol > ex0:
            violations.append(f"left {x0:.0f} > {ex0:.0f} (margin wider than expected)")
        # Top edge — symmetric.
        if y0 + tol < ey0:
            violations.append(f"top {y0:.0f} < {ey0:.0f}")
        elif y0 - tol > ey0:
            violations.append(f"top {y0:.0f} > {ey0:.0f} (margin wider than expected)")
        # Right edge — symmetric.
        if x1 - tol > ex1:
            violations.append(f"right {x1:.0f} > {ex1:.0f}")
        elif x1 + tol < ex1:
            violations.append(f"right {x1:.0f} < {ex1:.0f} (margin wider than expected)")
        # Bottom edge — outward only. Pages that legitimately end mid-column
        # (end of a section, figure on the next page) routinely fall short
        # of the expected bottom, so an inward check would false-positive.
        if y1 - tol > ey1:
            violations.append(f"bottom {y1:.0f} > {ey1:.0f}")
        if violations:
            issues.append(
                Issue(
                    severity="error",
                    check="geometry.margins",
                    message="Text block does not match the expected geometry.",
                    expected=f"bbox {ex0:.0f},{ey0:.0f},{ex1:.0f},{ey1:.0f}",
                    actual="; ".join(violations),
                    page=i + 1,
                    bbox=bbox,
                )
            )

    # Column-count check: majority vote across the sampled pages.
    if detected_col_counts:
        most_common = Counter(detected_col_counts).most_common(1)[0][0]
        if most_common != profile.text_block.columns:
            issues.append(
                Issue(
                    severity="error",
                    check="geometry.columns",
                    message="Column count does not match profile (likely wrong template).",
                    expected=f"{profile.text_block.columns} column(s)",
                    actual=f"{most_common} column(s)",
                )
            )
    return issues
