from __future__ import annotations

import dataclasses

import fitz
import pytest

from format_checker.checks import anonymization, fonts, geometry, pages, sections


def _checks(pdf, profile):
    doc = fitz.open(pdf)
    try:
        page_issues, classification = pages.run(doc, profile)
        body = classification.body or list(range(doc.page_count))
        geom = geometry.run(doc, profile, body)
        font_issues, body_font, body_size = fonts.run(doc, profile, body)
        anon = anonymization.run(doc, profile)
    finally:
        doc.close()
    return page_issues, geom, font_issues, anon, classification, body_font, body_size


def check_codes(issues):
    return {i.check for i in issues}


def test_good_pdf_passes(fixtures_dir, ieee_profile):
    p, g, f, a, _, _, _ = _checks(fixtures_dir / "good.pdf", ieee_profile)
    all_errors = [i for i in p + g + f if i.severity == "error"]
    assert all_errors == [], all_errors


def test_too_many_body_pages(fixtures_dir, ieee_profile):
    p, *_ = _checks(fixtures_dir / "too_many_body_pages.pdf", ieee_profile)
    assert "pages.max_body_pages" in check_codes(p)


def test_appendix_excluded(fixtures_dir, ieee_profile):
    p, g, f, *_ = _checks(fixtures_dir / "body_ok_long_appendix.pdf", ieee_profile)
    assert "pages.max_body_pages" not in check_codes(p + g + f)


def test_ethics_excluded_when_flag_off(fixtures_dir, ieee_profile):
    # Same profile, but with Ethics Considerations excluded from the body cap
    # (as in the NDSS profiles). The fixture has 10 body + 2 ethics + 1 refs;
    # without the exclusion the body count would be 12, exceeding the cap of 10.
    page_rule = dataclasses.replace(ieee_profile.page, ethics_counts_toward_body=False)
    profile = dataclasses.replace(ieee_profile, page=page_rule)
    doc = fitz.open(fixtures_dir / "body_ok_with_ethics.pdf")
    try:
        issues, classification = pages.run(doc, profile)
    finally:
        doc.close()
    assert "pages.max_body_pages" not in check_codes(issues)
    assert len(classification.body) == 10
    assert len(classification.ethics) == 2
    assert len(classification.references) == 1


def test_ethics_counts_by_default(fixtures_dir, ieee_profile):
    # Default behaviour: ethics_counts_toward_body=True, so body+ethics = 12 > 10.
    p, *_ = _checks(fixtures_dir / "body_ok_with_ethics.pdf", ieee_profile)
    assert "pages.max_body_pages" in check_codes(p)


def test_no_refs_heading_is_ambiguous(fixtures_dir, ieee_profile):
    p, *_ = _checks(fixtures_dir / "no_refs_heading.pdf", ieee_profile)
    assert "pages.section_detection" in check_codes(p)


def test_wrong_font_family(fixtures_dir, ieee_profile):
    _, _, f, *_ = _checks(fixtures_dir / "wrong_font.pdf", ieee_profile)
    assert "fonts.body_family" in check_codes(f)


def test_small_font(fixtures_dir, ieee_profile):
    _, _, f, *_ = _checks(fixtures_dir / "small_font.pdf", ieee_profile)
    assert "fonts.body_size" in check_codes(f)


def test_narrow_margins(fixtures_dir, ieee_profile):
    _, g, *_ = _checks(fixtures_dir / "narrow_margins.pdf", ieee_profile)
    assert "geometry.margins" in check_codes(g)


def test_anonymization_flags_author_block(fixtures_dir, ieee_profile):
    _, _, _, a, *_ = _checks(fixtures_dir / "has_authors.pdf", ieee_profile)
    codes = check_codes(a)
    assert "anonymization.email" in codes


def test_required_sections_present(fixtures_dir, usenix_profile):
    import fitz
    doc = fitz.open(fixtures_dir / "with_required_sections.pdf")
    try:
        issues = sections.run(doc, usenix_profile)
    finally:
        doc.close()
    assert issues == []


def test_required_sections_missing(fixtures_dir, usenix_profile):
    import fitz
    doc = fitz.open(fixtures_dir / "missing_required_sections.pdf")
    try:
        issues = sections.run(doc, usenix_profile)
    finally:
        doc.close()
    names = {i.expected for i in issues}
    assert "Ethics Considerations" in names
    assert "Open Science" in names
