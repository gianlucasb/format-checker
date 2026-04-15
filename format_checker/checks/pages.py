from __future__ import annotations

import re

import fitz

from ..models import Issue, PageClassification
from ..profile import Profile

REFS_RE = re.compile(r"^\s*references\s*$", re.IGNORECASE)
# "Appendix", "Appendices", "Appendix A", "A. Appendix", "A Appendix".
APPENDIX_RE = re.compile(
    r"^\s*(?:[A-Z]\.?\s+)?(?:appendix|appendices)\b",
    re.IGNORECASE,
)


def _classify_pages(doc: fitz.Document) -> PageClassification:
    refs_start: int | None = None
    appendix_start: int | None = None
    for i in range(doc.page_count):
        page = doc[i]
        blocks = page.get_text("blocks") or []
        top_blocks = sorted(blocks, key=lambda b: b[1])[:6]
        for b in top_blocks:
            text = (b[4] or "").strip().splitlines()
            for line in text[:3]:
                line = line.strip()
                if refs_start is None and REFS_RE.match(line):
                    refs_start = i
                if appendix_start is None and APPENDIX_RE.match(line):
                    appendix_start = i
    pc = PageClassification()
    n = doc.page_count
    if refs_start is None and appendix_start is None:
        pc.body = list(range(n))
        pc.ambiguous = True
        return pc
    boundary = min(x for x in (refs_start, appendix_start) if x is not None)
    pc.body = list(range(boundary))
    # cover rest with refs/appendix ranges
    cursor = boundary
    if refs_start is not None and refs_start == boundary:
        end = appendix_start if appendix_start is not None and appendix_start > refs_start else n
        pc.references = list(range(cursor, end))
        cursor = end
    if appendix_start is not None and cursor < n:
        pc.appendix = list(range(max(cursor, appendix_start), n))
    return pc


def run(doc: fitz.Document, profile: Profile) -> tuple[list[Issue], PageClassification]:
    issues: list[Issue] = []
    # page size
    rect = doc[0].rect
    tol = profile.tolerance_pt
    if (
        abs(rect.width - profile.page.width_pt) > tol
        or abs(rect.height - profile.page.height_pt) > tol
    ):
        issues.append(
            Issue(
                severity="error",
                check="pages.size",
                message="Page size does not match profile.",
                expected=f"{profile.page.size_name} ({profile.page.width_pt:.0f}x{profile.page.height_pt:.0f} pt)",
                actual=f"{rect.width:.0f}x{rect.height:.0f} pt",
                page=1,
            )
        )

    pc = _classify_pages(doc)
    counted = list(pc.body)
    if profile.page.refs_count_toward_body:
        counted += pc.references
    if profile.page.appendix_counts_toward_body:
        counted += pc.appendix

    if len(counted) > profile.page.max_body_pages:
        issues.append(
            Issue(
                severity="error",
                check="pages.max_body_pages",
                message="Body exceeds allowed page count.",
                expected=f"<= {profile.page.max_body_pages}",
                actual=str(len(counted)),
            )
        )
    if profile.page.max_total_pages and doc.page_count > profile.page.max_total_pages:
        issues.append(
            Issue(
                severity="error",
                check="pages.max_total_pages",
                message="Total document exceeds hard page cap.",
                expected=f"<= {profile.page.max_total_pages}",
                actual=str(doc.page_count),
            )
        )
    if pc.ambiguous:
        issues.append(
            Issue(
                severity="info",
                check="pages.section_detection",
                message="Could not locate a 'References' or 'Appendix' heading; all pages counted as body.",
                expected="References/Appendix heading present",
                actual="none detected",
            )
        )
    return issues, pc
