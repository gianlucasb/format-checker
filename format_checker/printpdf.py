"""Render the per-paper HTML reports to PDF via headless Chromium.

Optional extra. Install with::

    pip install -e '.[print]'
    playwright install chromium

The strategy is "print the HTML page as it appears in a browser": Playwright
opens each ``<out>/<slug>/index.html`` with a real browser engine, then uses
``page.pdf()`` to write ``report.pdf`` next to it. Because it's a real
browser, every CSS rule, image, and overlay box renders the same way the
chair sees it on screen — no separate styling code path to maintain.
"""
from __future__ import annotations

from pathlib import Path

PDF_OPTIONS = {
    "format": "Letter",
    "margin": {"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"},
    "print_background": True,
}


def _discover_html_files(out_dir: Path) -> list[tuple[Path, Path]]:
    """Return ``(html, pdf)`` pairs — one per per-paper directory under out_dir.

    The batch ``index.html`` at the top level is excluded; this command is
    about archiving the individual paper reports.
    """
    pairs: list[tuple[Path, Path]] = []
    for sub in sorted(out_dir.iterdir()):
        if not sub.is_dir():
            continue
        html = sub / "index.html"
        if html.exists():
            pairs.append((html, sub / "report.pdf"))
    return pairs


def _missing_playwright_message() -> str:
    return (
        "playwright is not installed. To enable PDF rendering, run:\n"
        "  pip install -e '.[print]'\n"
        "  playwright install chromium"
    )


def render_reports(out_dir: Path) -> list[Path]:
    """Render each per-paper ``index.html`` under out_dir to ``report.pdf``.

    Returns the list of generated PDF paths.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(_missing_playwright_message()) from e

    pairs = _discover_html_files(out_dir)
    written: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            for html, pdf in pairs:
                page.goto(f"file://{html.resolve()}")
                page.pdf(path=str(pdf), **PDF_OPTIONS)
                written.append(pdf)
        finally:
            browser.close()
    return written
