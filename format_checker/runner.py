from __future__ import annotations

from pathlib import Path

import fitz

from .checks import anonymization, fonts, geometry, pages, sections
from .cleared import hash_pdf
from .models import PaperReport
from .profile import Profile
from .render import render_pages
from .report import slugify, write_paper_report


def check_paper(pdf_path: Path, profile: Profile, out_dir: Path) -> PaperReport:
    doc = fitz.open(pdf_path)
    try:
        page_issues, classification = pages.run(doc, profile)
        body_pages = classification.body or list(range(doc.page_count))
        geom_issues = geometry.run(doc, profile, body_pages)
        font_issues, body_font, body_size = fonts.run(doc, profile, body_pages)
        anon_issues = anonymization.run(doc, profile)
        section_issues = sections.run(doc, profile)

        all_issues = page_issues + geom_issues + font_issues + section_issues + anon_issues

        paper_dir = out_dir / slugify(pdf_path.stem)
        rendered = render_pages(doc, profile, all_issues, paper_dir)

        report = PaperReport(
            pdf_path=pdf_path,
            profile_name=profile.name,
            page_count=doc.page_count,
            issues=all_issues,
            body_font=body_font,
            body_font_size=body_size,
            classification=classification,
            rendered_pages=rendered,
            pdf_hash=hash_pdf(pdf_path),
        )
        write_paper_report(report, paper_dir)
        return report
    finally:
        doc.close()
