"""Generate synthetic PDF fixtures for tests.

Run directly:  python tests/fixtures/make_fixtures.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).parent
BODY_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
) * 6

# Match IEEE A4 profile: 54pt margins, Times 10pt body
MARGIN = 54
BODY_FONT = "Times-Roman"
BODY_SIZE = 10


def _draw_body(c: canvas.Canvas, font=BODY_FONT, size=BODY_SIZE, margin=MARGIN, text=BODY_LOREM):
    width, height = A4
    c.setFont(font, size)
    y = height - margin - size
    leading = size * 1.2
    max_width = width - 2 * margin
    words = text.split()
    line = ""
    for word in words:
        trial = (line + " " + word).strip()
        if c.stringWidth(trial, font, size) > max_width:
            c.drawString(margin, y, line)
            y -= leading
            if y < margin + size:
                return
            line = word
        else:
            line = trial
    if line and y >= margin + size:
        c.drawString(margin, y, line)


def _body_page(c: canvas.Canvas, **kw):
    _draw_body(c, **kw)
    c.showPage()


def _refs_page(c: canvas.Canvas):
    width, height = A4
    c.setFont(BODY_FONT, BODY_SIZE)
    c.drawString(MARGIN, height - MARGIN - BODY_SIZE, "References")
    c.drawString(MARGIN, height - MARGIN - 3 * BODY_SIZE, "[1] A. Author. Some paper. 2020.")
    c.showPage()


def _appendix_page(c: canvas.Canvas):
    width, height = A4
    c.setFont(BODY_FONT, BODY_SIZE)
    c.drawString(MARGIN, height - MARGIN - BODY_SIZE, "Appendix A")
    _draw_body(c, text=BODY_LOREM)
    c.showPage()


def _ethics_page(c: canvas.Canvas, heading: str = "VIII. Ethics Considerations"):
    width, height = A4
    c.setFont(BODY_FONT, BODY_SIZE)
    c.drawString(MARGIN, height - MARGIN - BODY_SIZE, heading)
    _draw_body(c, text=BODY_LOREM)
    c.showPage()


def make(name: str, build):
    path = HERE / name
    c = canvas.Canvas(str(path), pagesize=A4)
    build(c)
    c.save()
    return path


def good(c):
    for _ in range(8):
        _body_page(c)
    _refs_page(c)


def too_many_body_pages(c):
    for _ in range(12):
        _body_page(c)
    _refs_page(c)


def body_ok_long_appendix(c):
    for _ in range(10):
        _body_page(c)
    _refs_page(c)
    for _ in range(5):
        _appendix_page(c)


def body_ok_with_ethics(c):
    # 10 body pages + 2 "Ethics Considerations" pages + refs.
    # Under a profile that excludes ethics from the body cap, this stays at 10
    # body pages (limit) rather than the 12 it would be without exclusion.
    for _ in range(10):
        _body_page(c)
    _ethics_page(c)
    _ethics_page(c, heading="(continued)")
    _refs_page(c)


def no_refs_heading(c):
    for _ in range(8):
        _body_page(c)


def wrong_font(c):
    for _ in range(8):
        _body_page(c, font="Helvetica")
    _refs_page(c)


def small_font(c):
    for _ in range(8):
        _body_page(c, size=8)
    _refs_page(c)


def narrow_margins(c):
    for _ in range(8):
        _body_page(c, margin=20)
    _refs_page(c)


def with_required_sections(c):
    width, height = A4
    for _ in range(6):
        _body_page(c)
    c.setFont(BODY_FONT, BODY_SIZE)
    c.drawString(MARGIN, height - MARGIN - BODY_SIZE, "6 Ethics Considerations")
    _draw_body(c)
    c.showPage()
    c.setFont(BODY_FONT, BODY_SIZE)
    c.drawString(MARGIN, height - MARGIN - BODY_SIZE, "Open Science")
    _draw_body(c)
    c.showPage()
    _refs_page(c)


def missing_required_sections(c):
    for _ in range(8):
        _body_page(c)
    _refs_page(c)


def has_authors(c):
    width, height = A4
    c.setFont(BODY_FONT, BODY_SIZE)
    y = height - MARGIN - BODY_SIZE
    for line in [
        "Jane Doe",
        "Example University",
        "jane.doe@example.edu",
        "",
        "Abstract",
        "This paper describes ...",
    ]:
        c.drawString(MARGIN, y, line)
        y -= BODY_SIZE * 1.3
    c.showPage()
    for _ in range(7):
        _body_page(c)
    _refs_page(c)


FIXTURES = {
    "good.pdf": good,
    "too_many_body_pages.pdf": too_many_body_pages,
    "body_ok_long_appendix.pdf": body_ok_long_appendix,
    "body_ok_with_ethics.pdf": body_ok_with_ethics,
    "no_refs_heading.pdf": no_refs_heading,
    "wrong_font.pdf": wrong_font,
    "small_font.pdf": small_font,
    "narrow_margins.pdf": narrow_margins,
    "has_authors.pdf": has_authors,
    "with_required_sections.pdf": with_required_sections,
    "missing_required_sections.pdf": missing_required_sections,
}


def main():
    for name, fn in FIXTURES.items():
        p = make(name, fn)
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
