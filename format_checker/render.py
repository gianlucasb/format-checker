from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from .models import Issue
from .profile import Profile

DPI = 120


def _scale(bbox, s):
    return tuple(v * s for v in bbox)


def render_pages(
    doc: fitz.Document,
    profile: Profile,
    issues: list[Issue],
    out_dir: Path,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    scale = DPI / 72.0
    by_page: dict[int, list[Issue]] = {}
    for issue in issues:
        if issue.page:
            by_page.setdefault(issue.page - 1, []).append(issue)
    pages = set(by_page) | {0}
    # For papers with no flagged pages, include a second thumbnail showing
    # a representative body page so the chair sees both the title block and
    # the body layout at a glance. Use the document midpoint — typically a
    # plain body page, away from title and references.
    if not by_page and doc.page_count > 1:
        pages.add(doc.page_count // 2)
    pages_to_render = sorted(pages)
    paths: list[Path] = []
    exp = profile.expected_text_rect
    for i in pages_to_render:
        page = doc[i]
        pix = page.get_pixmap(dpi=DPI)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        draw = ImageDraw.Draw(img)
        draw.rectangle(_scale(exp, scale), outline=(0, 170, 0), width=3)
        for issue in by_page.get(i, []):
            if not issue.bbox:
                continue
            color = (220, 20, 20) if issue.check.startswith("fonts") else (240, 140, 0)
            draw.rectangle(_scale(issue.bbox, scale), outline=color, width=3)
        path = out_dir / f"page-{i + 1:03d}.png"
        img.save(path)
        paths.append(path)
    return paths
