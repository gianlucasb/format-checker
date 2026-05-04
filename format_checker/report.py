from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .cleared import load_cleared, merge_cleared, save_cleared
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
    slug = slugify(report.pdf_path.stem)
    html = tmpl.render(
        report=report,
        issue_groups=_group_issues(report),
        slug=slug,
        pdf_hash=report.pdf_hash,
    )
    out = paper_dir / "index.html"
    out.write_text(html)
    return out


SEVERITY_LABELS = {"error": "Error", "warning": "Warning", "info": "Info"}


def _render_issue_md(issue) -> str:
    label = SEVERITY_LABELS.get(issue.severity, issue.severity.title())
    page = f" (page {issue.page})" if issue.page is not None else ""
    line = f"- **{label}**{page}: {issue.message}"
    details = []
    if issue.expected:
        details.append(f"expected {issue.expected}")
    if issue.actual:
        details.append(f"actual {issue.actual}")
    if details:
        line += f" — {'; '.join(details)}"
    return line


def write_paper_markdown(report: PaperReport, paper_dir: Path) -> Path | None:
    """Write a markdown summary for HotCRP comments. Returns None if no errors/warnings."""
    if report.status == "pass":
        return None
    paper_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Format check: {report.pdf_path.name}",
        "",
        f"Profile: **{report.profile_name}** — status: **{report.status.upper()}** "
        f"({report.n_errors} error(s), {report.n_warnings} warning(s))",
        "",
    ]
    for label, _key, issues in _group_issues(report):
        reportable = [i for i in issues if i.severity in ("error", "warning")]
        if not reportable:
            continue
        lines.append(f"## {label}")
        lines.append("")
        lines.extend(_render_issue_md(i) for i in reportable)
        lines.append("")
    out = paper_dir / "summary.md"
    out.write_text("\n".join(lines).rstrip() + "\n")
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
                "pdf_hash": r.pdf_hash,
            }
        )
    rows.sort(key=lambda r: {"fail": 0, "warn": 1, "pass": 2}[r["status"]])

    # Preserve chair-side "cleared" decisions across re-runs: drop any
    # decision whose paper is gone or whose PDF bytes have changed.
    existing = load_cleared(out_dir)
    merged = merge_cleared(existing, ((r["slug"], r["pdf_hash"]) for r in rows))
    save_cleared(out_dir, merged)

    # Escape HTML-significant characters so a note like "</script>" can't
    # break out of the embedded JSON block.
    cleared_json = (
        json.dumps(merged)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    tmpl = _env().get_template("index.html.j2")
    html = tmpl.render(
        reports=rows,
        profile_name=profile_name,
        cleared_json=cleared_json,
    )
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
