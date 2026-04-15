from __future__ import annotations

import re

import fitz

from ..models import Issue
from ..profile import Profile, RequiredSection

# Optional leading section number like "6", "6.1", "A.2"
NUM_PREFIX = r"(?:\d+(?:\.\d+)*|[A-Z])(?:\.|\))?\s+"


def _compile(section: RequiredSection) -> re.Pattern[str]:
    alts = "|".join(f"(?:{p})" for p in section.patterns)
    return re.compile(rf"^\s*(?:{NUM_PREFIX})?(?:{alts})\s*:?\s*$", re.IGNORECASE)


def _find_section(doc: fitz.Document, pattern: re.Pattern[str]) -> int | None:
    for i in range(doc.page_count):
        text = doc[i].get_text("text") or ""
        for line in text.splitlines():
            stripped = line.strip()
            if 0 < len(stripped) <= 80 and pattern.match(stripped):
                return i + 1
    return None


def run(doc: fitz.Document, profile: Profile) -> list[Issue]:
    issues: list[Issue] = []
    for section in profile.required_sections:
        pat = _compile(section)
        page = _find_section(doc, pat)
        if page is None:
            issues.append(
                Issue(
                    severity="error",
                    check="sections.missing",
                    message=f"Required section '{section.name}' not found.",
                    expected=section.name,
                    actual="not found",
                )
            )
    return issues
