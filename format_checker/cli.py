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


if __name__ == "__main__":
    main()
