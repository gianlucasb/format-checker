from __future__ import annotations

import dataclasses

import fitz
import pytest

from format_checker.checks import anonymization, fonts, geometry, pages, sections
from format_checker.checks.anonymization import SELF_CITE_RE


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


def test_wide_margins(fixtures_dir, ieee_profile):
    # Text block sits well inside the expected one — caught by the symmetric
    # margin check (the wrong-template signal that initially missed paper14).
    _, g, *_ = _checks(fixtures_dir / "wide_margins.pdf", ieee_profile)
    msgs = " ".join(i.actual for i in g if i.check == "geometry.margins")
    assert "geometry.margins" in check_codes(g)
    assert "wider than expected" in msgs


def test_single_bad_page_is_not_flagged(fixtures_dir, ieee_profile):
    # Only the middle body page has a margin anomaly — likely a one-off
    # figure or table breaking the column flow, not a wrong template.
    # The multi-page evidence rule should suppress this.
    _, g, *_ = _checks(fixtures_dir / "one_bad_page.pdf", ieee_profile)
    assert "geometry.margins" not in check_codes(g)


def test_detect_columns_clusters_two_peaks():
    from format_checker.checks.geometry import _column_count_from_x0s
    # 2-column page: 60 lines starting near x=54, 60 near x=318.
    x0s = [54.0] * 60 + [318.0] * 60
    assert _column_count_from_x0s(x0s) == 2


def test_detect_columns_one_column():
    from format_checker.checks.geometry import _column_count_from_x0s
    # Single column: 60 lines, with a few outlier indents that shouldn't
    # count as a separate column.
    x0s = [54.0] * 60 + [64.0] * 5
    assert _column_count_from_x0s(x0s) == 1


def test_detect_columns_returns_zero_when_sparse():
    from format_checker.checks.geometry import _column_count_from_x0s
    # Below MIN_LINES_FOR_COLUMN_DETECTION → not enough signal.
    assert _column_count_from_x0s([54.0, 318.0, 54.0]) == 0


def test_detect_columns_uses_expected_starts_as_prior():
    # Math/table-heavy page: only 16 lines at the real left column and 22 at
    # the right, with the rest scattered across many positions. With pure
    # frequency clustering, the threshold (15% of 200 = 30) rejects both
    # real columns. With expected_starts as a prior, the detector accepts
    # 2 columns because both expected positions have ≥10 supporting lines.
    x0s = [48.0] * 16 + [312.0] * 22 + [120.0] * 21 + [164.0] * 17 + [216.0] * 13 + [200.0] * 14 + list(range(50, 600, 4))
    from format_checker.checks.geometry import _column_count_from_x0s
    # Without the prior: no bucket clears the 15% threshold, so clustering
    # returns 0 (no peaks). With the prior: both expected positions have
    # ≥10 supporting lines, so we accept the expected count.
    assert _column_count_from_x0s(x0s) == 0
    assert _column_count_from_x0s(x0s, expected_starts=[45.0, 315.0]) == 2


def test_detect_columns_expected_prior_rejected_when_unsupported():
    # A truly single-column page (all lines at x=72) should NOT be accepted
    # as 2 columns just because the profile expects 2 — neither expected
    # position has support, so we fall back to clustering.
    from format_checker.checks.geometry import _column_count_from_x0s
    x0s = [72.0] * 60
    assert _column_count_from_x0s(x0s, expected_starts=[45.0, 315.0]) == 1


def test_anonymization_flags_author_block(fixtures_dir, ieee_profile):
    _, _, _, a, *_ = _checks(fixtures_dir / "has_authors.pdf", ieee_profile)
    codes = check_codes(a)
    assert "anonymization.email" in codes


@pytest.mark.parametrize(
    "phrase",
    [
        "in our previous work",
        "Our prior paper [12] showed that",
        "our earlier study demonstrated",
        "as discussed in our recent publication",
        "Our past research has shown",
    ],
)
def test_self_citation_flags_prior_publication(phrase):
    assert SELF_CITE_RE.search(phrase), f"expected to flag: {phrase!r}"


@pytest.mark.parametrize(
    "phrase",
    [
        "as we previously showed",
        "as we showed in §3",
        "we previously demonstrated that",
        "we earlier described the protocol",
        "in our paper, we discuss the threat model",
        "we showed in Section 4 that",
        "Our approach proceeds in three steps",
    ],
)
def test_self_citation_ignores_internal_references(phrase):
    assert SELF_CITE_RE.search(phrase) is None, f"expected to ignore: {phrase!r}"


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
