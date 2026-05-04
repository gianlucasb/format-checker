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


MIN_LINES_FOR_COLUMN_DETECTION = 20  # below this, the page is too sparse to read columns
COLUMN_GAP_MIN = 100.0               # min x-distance between two distinct columns
COLUMN_PEAK_MIN_FRACTION = 0.15      # a column must hold at least this fraction of body lines
COLUMN_EXPECTED_TOLERANCE = 12.0     # pt: how close a line's x0 has to be to an expected column start
COLUMN_MIN_LINES_AT_EXPECTED = 10    # if every expected column has at least this many lines nearby, accept
MIN_PAGES_FOR_MARGIN_VIOLATION = 2   # a margin axis must violate on at least this many sampled pages


def _expected_column_starts(profile: Profile) -> list[float]:
    """The x-coordinate where each column begins, derived from the profile."""
    p, t = profile.page, profile.text_block
    n = t.columns
    text_width = p.width_pt - t.left_margin - t.right_margin
    col_width = (text_width - (n - 1) * t.column_gap) / n
    return [t.left_margin + i * (col_width + t.column_gap) for i in range(n)]


def _column_count_from_x0s(
    x0s: list[float], expected_starts: list[float] | None = None
) -> int:
    """Estimate the column count from a list of line-start x-coordinates.

    When ``expected_starts`` is given (the profile's column positions),
    a page is accepted as having ``len(expected_starts)`` columns whenever
    every expected position has at least ``COLUMN_MIN_LINES_AT_EXPECTED``
    lines nearby. This handles math/table-heavy pages whose actual columns
    are real but get diluted below the global frequency threshold.

    Otherwise, falls back to gap-based clustering: walk 4-pt buckets in
    descending frequency and greedily accept those at least
    ``COLUMN_GAP_MIN`` away from any peak already accepted, with a
    minimum frequency floor.
    """
    if len(x0s) < MIN_LINES_FOR_COLUMN_DETECTION:
        return 0
    if expected_starts:
        counts = [
            sum(1 for x in x0s if abs(x - start) <= COLUMN_EXPECTED_TOLERANCE)
            for start in expected_starts
        ]
        if all(c >= COLUMN_MIN_LINES_AT_EXPECTED for c in counts):
            return len(expected_starts)

    threshold = max(5, len(x0s) * COLUMN_PEAK_MIN_FRACTION)
    buckets = Counter(round(x / 4) * 4 for x in x0s)
    peaks: list[int] = []
    for bucket, freq in buckets.most_common():
        if freq < threshold:
            break
        if all(abs(bucket - p) >= COLUMN_GAP_MIN for p in peaks):
            peaks.append(bucket)
    return len(peaks)


def _detect_columns(page: fitz.Page, expected_starts: list[float] | None = None) -> int:
    """Estimate the number of text columns on a page (0 if too sparse)."""
    x0s: list[float] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            if any((sp.get("text") or "").strip() for sp in line.get("spans", [])):
                x0s.append(line["bbox"][0])
    return _column_count_from_x0s(x0s, expected_starts)


def _page_text_bbox(
    page: fitz.Page, expected_rect: tuple[float, float, float, float]
) -> tuple[float, float, float, float] | None:
    """Bounding box of the main text, ignoring running headers, page numbers, etc.

    A block whose *center* falls outside the profile's expected text rect is
    treated as a header/footer/sidebar and excluded — this is precise (it's
    literally the definition of "outside the body region") and avoids the
    char-count heuristic that mis-classified short table captions sitting
    right at the top margin as headers.
    """
    ex0, ey0, ex1, ey1 = expected_rect
    xs0, ys0, xs1, ys1 = [], [], [], []
    for block in page.get_text("blocks") or []:
        x0, y0, x1, y1, text, *_ = block
        if not text or not text.strip():
            continue
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        if cx < ex0 or cx > ex1 or cy < ey0 or cy > ey1:
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
    sample = sorted({interior[0], interior[len(interior) // 2], interior[-1]})
    ex0, ey0, ex1, ey1 = exp
    expected_starts = _expected_column_starts(profile)
    detected_col_counts: list[int] = []
    # Per-page: (page_index, bbox, {axis: violation_text}). Aggregated below
    # so a single anomalous page (a wide table, an embedded figure breaking
    # the column flow) can't condemn an otherwise well-formatted paper.
    per_page: list[tuple[int, tuple[float, float, float, float], dict[str, str]]] = []
    for i in sample:
        page = doc[i]
        n_cols = _detect_columns(page, expected_starts)
        if n_cols > 0:
            detected_col_counts.append(n_cols)
        bbox = _page_text_bbox(page, exp)
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        v: dict[str, str] = {}
        # Left/top/right are checked symmetrically — text bleeding outside the
        # expected block (narrow margin) AND text sitting well inside it (wide
        # margin, classic wrong-template signal). Bottom is outward-only since
        # legitimate pages routinely end short of the bottom margin.
        if x0 + tol < ex0:
            v["left"] = f"left {x0:.0f} < {ex0:.0f}"
        elif x0 - tol > ex0:
            v["left"] = f"left {x0:.0f} > {ex0:.0f} (margin wider than expected)"
        if y0 + tol < ey0:
            v["top"] = f"top {y0:.0f} < {ey0:.0f}"
        elif y0 - tol > ey0:
            v["top"] = f"top {y0:.0f} > {ey0:.0f} (margin wider than expected)"
        if x1 - tol > ex1:
            v["right"] = f"right {x1:.0f} > {ex1:.0f}"
        elif x1 + tol < ex1:
            v["right"] = f"right {x1:.0f} < {ex1:.0f} (margin wider than expected)"
        if y1 - tol > ey1:
            v["bottom"] = f"bottom {y1:.0f} > {ey1:.0f}"
        if v:
            per_page.append((i, bbox, v))

    # Only report axes that violated on at least MIN_PAGES_FOR_MARGIN_VIOLATION
    # sampled pages. One-off anomalies don't survive this filter.
    axis_hits: Counter[str] = Counter()
    for _, _, v in per_page:
        axis_hits.update(v.keys())
    confirmed_axes = {a for a, n in axis_hits.items() if n >= MIN_PAGES_FOR_MARGIN_VIOLATION}
    for i, bbox, v in per_page:
        confirmed = {a: t for a, t in v.items() if a in confirmed_axes}
        if not confirmed:
            continue
        issues.append(
            Issue(
                severity="error",
                check="geometry.margins",
                message="Text block does not match the expected geometry.",
                expected=f"bbox {ex0:.0f},{ey0:.0f},{ex1:.0f},{ey1:.0f}",
                actual="; ".join(confirmed.values()),
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
