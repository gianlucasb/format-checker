from __future__ import annotations

import csv
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import PaperReport

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "paper"


CATEGORY_LABELS = {
    "pages": "Pages",
    "geometry": "Margins & geometry",
    "fonts": "Fonts",
    "sections": "Required sections",
    "anonymization": "Anonymization",
}
CATEGORY_ORDER = ["pages", "geometry", "fonts", "sections", "anonymization"]


def _group_issues(report: PaperReport):
    groups: dict[str, list] = {k: [] for k in CATEGORY_ORDER}
    for issue in report.issues:
        key = issue.check.split(".", 1)[0]
        groups.setdefault(key, []).append(issue)
    return [
        (CATEGORY_LABELS.get(k, k.title()), k, groups[k])
        for k in CATEGORY_ORDER + [k for k in groups if k not in CATEGORY_ORDER]
        if groups.get(k)
    ]


def write_paper_report(report: PaperReport, paper_dir: Path) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    tmpl = _env().get_template("report.html.j2")
    html = tmpl.render(report=report, issue_groups=_group_issues(report))
    out = paper_dir / "index.html"
    out.write_text(html)
    return out


def write_batch_index(
    reports: list[PaperReport], out_dir: Path, profile_name: str
) -> Path:
    rows = []
    for r in reports:
        rows.append(
            {
                "status": r.status,
                "slug": slugify(r.pdf_path.stem),
                "pdf_path": r.pdf_path,
                "page_count": r.page_count,
                "body_font": r.body_font,
                "body_font_size": r.body_font_size,
                "n_errors": r.n_errors,
                "n_warnings": r.n_warnings,
            }
        )
    rows.sort(key=lambda r: {"fail": 0, "warn": 1, "pass": 2}[r["status"]])
    tmpl = _env().get_template("index.html.j2")
    html = tmpl.render(reports=rows, profile_name=profile_name)
    out = out_dir / "index.html"
    out.write_text(html)

    csv_path = out_dir / "summary.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["paper", "status", "page_count", "body_font", "body_size", "n_errors", "n_warnings"]
        )
        for r in rows:
            w.writerow(
                [
                    r["pdf_path"].name,
                    r["status"],
                    r["page_count"],
                    r["body_font"],
                    r["body_font_size"],
                    r["n_errors"],
                    r["n_warnings"],
                ]
            )
    return out
