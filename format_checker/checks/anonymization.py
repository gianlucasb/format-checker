from __future__ import annotations

import re

import fitz

from ..models import Issue
from ..profile import Profile

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ORCID_RE = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")
AFFIL_KEYWORDS = ("University", "Institute", "Laboratory", "Department of", "Inc.", "Corp.")
SELF_CITE_RE = re.compile(
    r"\b(our previous|as we showed|in our prior|we previously|our earlier)\b",
    re.IGNORECASE,
)


def run(doc: fitz.Document, profile: Profile) -> list[Issue]:
    if not profile.anonymization_required:
        return []
    issues: list[Issue] = []

    first = doc[0]
    first_text = first.get_text("text") or ""
    abstract_idx = first_text.lower().find("abstract")
    header = first_text[:abstract_idx] if abstract_idx != -1 else first_text[:800]

    if EMAIL_RE.search(header):
        issues.append(
            Issue(
                severity="warning",
                check="anonymization.email",
                message="Email address detected above abstract.",
                expected="no author contact info",
                actual=EMAIL_RE.search(header).group(0),
                page=1,
            )
        )
    if ORCID_RE.search(header):
        issues.append(
            Issue(
                severity="warning",
                check="anonymization.orcid",
                message="ORCID detected above abstract.",
                page=1,
            )
        )
    for kw in AFFIL_KEYWORDS:
        if kw in header:
            issues.append(
                Issue(
                    severity="warning",
                    check="anonymization.affiliation",
                    message=f"Possible affiliation keyword '{kw}' above abstract.",
                    page=1,
                )
            )
            break

    for i in range(doc.page_count):
        text = doc[i].get_text("text") or ""
        m = SELF_CITE_RE.search(text)
        if m:
            issues.append(
                Issue(
                    severity="warning",
                    check="anonymization.self_citation",
                    message="Potential non-anonymous self-reference.",
                    expected="third-person phrasing",
                    actual=m.group(0),
                    page=i + 1,
                )
            )
            break
    return issues
