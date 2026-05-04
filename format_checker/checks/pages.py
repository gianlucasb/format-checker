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
# "Ethics Considerations" / "Ethical Considerations", optionally numbered:
# "8 Ethics ...", "8. Ethics ...", "VIII. Ethics ...", "A. Ethics ...".
# End-anchored so paragraph text starting with "Ethical considerations ..." won't match.
ETHICS_RE = re.compile(
    r"^\s*(?:[IVXLCDM]+\.?\s+|\d+\.?\s+|[A-Z]\.?\s+)?(?:ethics|ethical)\s+considerations?\.?\s*$",
    re.IGNORECASE,
)


def _classify_pages(doc: fitz.Document, detect_ethics: bool) -> PageClassification:
    refs_start: int | None = None
    appendix_start: int | None = None
    ethics_start: int | None = None
    for i in range(doc.page_count):
        page = doc[i]
        blocks = page.get_text("blocks") or []
        # Scan every block on the page, not just the top few. Wide tables or
        # figures at the top of a column-break page can push a "References" /
        # "Appendix" / "Ethics Considerations" heading well below the fold.
        for b in blocks:
            for line in (b[4] or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                if refs_start is None and REFS_RE.match(line):
                    refs_start = i
                if appendix_start is None and APPENDIX_RE.match(line):
                    appendix_start = i
                if detect_ethics and ethics_start is None and ETHICS_RE.match(line):
                    ethics_start = i
    # The NDSS CFP describes Ethics Considerations as a section placed
    # immediately *before* references. An ethics heading found later (e.g. as
    # an appendix subsection) is not the exempt section — drop it so those
    # pages stay classified as references/appendix.
    if (
        ethics_start is not None
        and refs_start is not None
        and ethics_start >= refs_start
    ):
        ethics_start = None
    pc = PageClassification()
    n = doc.page_count
    starts = [
        ("ethics", ethics_start),
        ("references", refs_start),
        ("appendix", appendix_start),
    ]
    starts = [(k, s) for k, s in starts if s is not None]
    if not starts:
        pc.body = list(range(n))
        pc.ambiguous = True
        return pc
    starts.sort(key=lambda x: x[1])
    pc.body = list(range(starts[0][1]))
    for idx, (kind, s) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else n
        rng = list(range(s, end))
        if kind == "references":
            pc.references = rng
        elif kind == "appendix":
            pc.appendix = rng
        elif kind == "ethics":
            pc.ethics = rng
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

    pc = _classify_pages(doc, detect_ethics=not profile.page.ethics_counts_toward_body)
    counted = list(pc.body)
    if profile.page.refs_count_toward_body:
        counted += pc.references
    if profile.page.appendix_counts_toward_body:
        counted += pc.appendix
    if profile.page.ethics_counts_toward_body:
        counted += pc.ethics

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
