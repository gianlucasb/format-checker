from __future__ import annotations

from pathlib import Path

import click

from .profile import load_profile
from .report import write_batch_index
from .runner import check_paper


@click.group()
def main():
    """Check conference submission PDFs against a format profile."""


@main.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option("--profile", "profile_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_dir", required=True, type=click.Path(path_type=Path))
def check(target: Path, profile_path: Path, out_dir: Path):
    """Check a single PDF or a directory of PDFs."""
    profile = load_profile(profile_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    if target.is_dir():
        pdfs = sorted(target.glob("*.pdf"))
    else:
        pdfs = [target]
    if not pdfs:
        raise click.ClickException(f"No PDFs found at {target}")

    reports = []
    for pdf in pdfs:
        click.echo(f"checking {pdf.name} ...")
        report = check_paper(pdf, profile, out_dir)
        click.echo(f"  {report.status.upper()}  ({report.n_errors}E / {report.n_warnings}W)")
        reports.append(report)

    write_batch_index(reports, out_dir, profile.name)
    click.echo(f"\nwrote {out_dir / 'index.html'}")


@main.command("print")
@click.argument("out_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def print_cmd(out_dir: Path):
    """Render each per-paper HTML report under OUT_DIR to a PDF.

    Requires the [print] extra and a one-time `playwright install chromium`.
    """
    from .printpdf import render_reports
    try:
        paths = render_reports(out_dir)
    except RuntimeError as e:
        raise click.ClickException(str(e))
    if not paths:
        click.echo(f"No per-paper reports found under {out_dir}")
        return
    for p in paths:
        click.echo(f"wrote {p}")


if __name__ == "__main__":
    main()
