from __future__ import annotations

from collections import Counter

import fitz

from ..models import Issue
from ..profile import Profile


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _family_matches(actual: str, families: list[str]) -> bool:
    if not families:
        return True
    a = _norm(actual)
    return any(_norm(f) in a or a in _norm(f) for f in families)


def _iter_spans(page: fitz.Page):
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = (span.get("text") or "").strip()
                if text:
                    yield span, text


def run(doc: fitz.Document, profile: Profile, body_pages: list[int]) -> tuple[list[Issue], str, float]:
    issues: list[Issue] = []
    counter: Counter[tuple[str, float]] = Counter()
    for i in body_pages or range(doc.page_count):
        for span, text in _iter_spans(doc[i]):
            key = (span.get("font", ""), round(float(span.get("size", 0)), 1))
            counter[key] += len(text)
    if not counter:
        return issues, "", 0.0
    (body_font, body_size), _ = counter.most_common(1)[0]
    rule = profile.body_font

    if not _family_matches(body_font, rule.families):
        issues.append(
            Issue(
                severity="error",
                check="fonts.body_family",
                message="Body font family does not match profile.",
                expected=", ".join(rule.families),
                actual=body_font,
            )
        )
    if rule.min_size is not None and body_size + 0.15 < rule.min_size:
        issues.append(
            Issue(
                severity="error",
                check="fonts.body_size",
                message="Body font size below minimum.",
                expected=f">= {rule.min_size}",
                actual=str(body_size),
            )
        )
    if rule.max_size is not None and body_size - 0.05 > rule.max_size:
        issues.append(
            Issue(
                severity="warning",
                check="fonts.body_size",
                message="Body font size above maximum.",
                expected=f"<= {rule.max_size}",
                actual=str(body_size),
            )
        )
    return issues, body_font, body_size
