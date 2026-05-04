from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PAGE_SIZES_PT: dict[str, tuple[float, float]] = {
    "A4": (595.276, 841.890),
    "letter": (612.0, 792.0),
    "Letter": (612.0, 792.0),
}


@dataclass
class FontRule:
    families: list[str] = field(default_factory=list)
    min_size: float | None = None
    max_size: float | None = None


@dataclass
class PageRule:
    size_name: str
    width_pt: float
    height_pt: float
    max_body_pages: int
    max_total_pages: int | None
    refs_count_toward_body: bool
    appendix_counts_toward_body: bool
    ethics_counts_toward_body: bool


@dataclass
class TextBlockRule:
    top_margin: float
    bottom_margin: float
    left_margin: float
    right_margin: float
    columns: int
    column_gap: float


@dataclass
class RequiredSection:
    name: str
    patterns: list[str]  # regex fragments, case-insensitive


@dataclass
class Profile:
    name: str
    page: PageRule
    text_block: TextBlockRule
    body_font: FontRule
    caption_font: FontRule
    tolerance_pt: float
    anonymization_required: bool
    required_sections: list[RequiredSection]

    @property
    def expected_text_rect(self) -> tuple[float, float, float, float]:
        p, t = self.page, self.text_block
        return (
            t.left_margin,
            t.top_margin,
            p.width_pt - t.right_margin,
            p.height_pt - t.bottom_margin,
        )


def _resolve_size(raw) -> tuple[str, float, float]:
    if isinstance(raw, str):
        if raw not in PAGE_SIZES_PT:
            raise ValueError(f"Unknown page size {raw!r}")
        w, h = PAGE_SIZES_PT[raw]
        return raw, w, h
    if isinstance(raw, list) and len(raw) == 2:
        return "custom", float(raw[0]), float(raw[1])
    raise ValueError(f"Invalid page.size: {raw!r}")


def load_profile(path: str | Path) -> Profile:
    data = yaml.safe_load(Path(path).read_text())
    page_raw = data["page"]
    size_name, w, h = _resolve_size(page_raw["size"])
    page = PageRule(
        size_name=size_name,
        width_pt=w,
        height_pt=h,
        max_body_pages=int(page_raw["max_body_pages"]),
        max_total_pages=page_raw.get("max_total_pages"),
        refs_count_toward_body=bool(page_raw.get("refs_count_toward_body", False)),
        appendix_counts_toward_body=bool(page_raw.get("appendix_counts_toward_body", False)),
        ethics_counts_toward_body=bool(page_raw.get("ethics_counts_toward_body", True)),
    )
    tb = data["text_block"]
    text_block = TextBlockRule(
        top_margin=float(tb["top_margin"]),
        bottom_margin=float(tb["bottom_margin"]),
        left_margin=float(tb["left_margin"]),
        right_margin=float(tb["right_margin"]),
        columns=int(tb.get("columns", 1)),
        column_gap=float(tb.get("column_gap", 0)),
    )
    fonts = data.get("fonts", {})
    body_raw = fonts.get("body", {})
    cap_raw = fonts.get("caption", {})
    body_font = FontRule(
        families=list(body_raw.get("families", [])),
        min_size=body_raw.get("min_size"),
        max_size=body_raw.get("max_size"),
    )
    caption_font = FontRule(
        families=list(cap_raw.get("families", [])),
        min_size=cap_raw.get("min_size"),
        max_size=cap_raw.get("max_size"),
    )
    req_raw = data.get("required_sections", []) or []
    required: list[RequiredSection] = []
    for entry in req_raw:
        if isinstance(entry, str):
            required.append(RequiredSection(name=entry, patterns=[entry]))
        elif isinstance(entry, dict):
            name = entry["name"]
            patterns = list(entry.get("patterns") or [name])
            required.append(RequiredSection(name=name, patterns=patterns))
        else:
            raise ValueError(f"Invalid required_sections entry: {entry!r}")
    return Profile(
        name=data["name"],
        page=page,
        text_block=text_block,
        body_font=body_font,
        caption_font=caption_font,
        tolerance_pt=float(data.get("tolerance_pt", 2)),
        anonymization_required=bool(data.get("anonymization", {}).get("required", False)),
        required_sections=required,
    )
