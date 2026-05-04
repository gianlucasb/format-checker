# format-checker

Batch-check conference submission PDFs against a venue format profile (IEEE,
ACM, USENIX, NDSS, …) and produce a chair-friendly report with per-page PNG
overlays showing where a paper deviates from the expected geometry.

## What it checks

- **Pages** — page size, body page count (references and appendix excluded by
  default), optional hard cap on total pages.
- **Margins & geometry** — main text block vs. profile margins, with running
  headers, footers, and title-page layouts filtered out.
- **Fonts** — body font family and size, detected per-span from the PDF.
- **Required sections** — flag if a CFP-mandated heading (e.g. *Ethics
  Considerations*, *Open Science*) is missing.
- **Anonymization** (submissions only) — author emails, affiliation keywords,
  and first-person self-citation patterns above the abstract / in the body.

Each issue is categorized and surfaced in the per-paper HTML report. Rendered
PNGs overlay the **expected text block** (green) and any **issue bboxes** (red
for font, orange for geometry).

## Install

Requires Python ≥ 3.11.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
```

Dependencies: `pymupdf`, `pillow`, `jinja2`, `pyyaml`, `click` (+ `pytest`,
`reportlab` for tests).

## Usage

```bash
# Batch a directory
format-checker check path/to/submissions --profile profiles/ndss_2026.yaml --out out

# Single PDF
format-checker check paper.pdf --profile profiles/usenix.yaml --out out
```

Open `out/index.html` for the batch landing page (sortable, filterable by
status) and `out/summary.csv` for a spreadsheet view. Click any paper to see
its full per-category issue breakdown and rendered pages.

## Profiles

Profiles are YAML files — the only thing you change between venues. Example
(`profiles/ndss_2026.yaml`):

```yaml
name: "NDSS 2026"
page:
  size: letter               # or A4, or [width_pt, height_pt]
  max_body_pages: 13
  refs_count_toward_body: false
  appendix_counts_toward_body: false
  ethics_counts_toward_body: false   # excludes an "Ethics Considerations" section from the body cap
text_block:
  top_margin: 63
  bottom_margin: 63
  left_margin: 45
  right_margin: 45
  columns: 2
  column_gap: 18
fonts:
  body:
    families: ["Times", "TimesNewRoman", "NimbusRomNo9L", "TeXGyreTermes"]
    min_size: 10.0
tolerance_pt: 4
anonymization:
  required: true
# Optional: required_sections (list of {name, patterns}) or shorthand strings.
```

Bundled profiles:

- `profiles/ieee_conf_a4.yaml`
- `profiles/acm_sigconf.yaml`
- `profiles/usenix.yaml`
- `profiles/ndss_2026.yaml` — submission rules (anonymous, 13-page body cap)
- `profiles/ndss_2026_proceedings.yaml` — camera-ready variant (no
  anonymization, looser margins matching the IEEE conference template)

Adding a new venue is a new YAML file — no code changes.

### Required sections

Profiles can enforce that specific headings appear. The checker does literal
heading matching (case-insensitive, tolerant of section-number prefixes like
`6` or `6.1`):

```yaml
required_sections:
  - name: "Ethics Considerations"
    patterns: ["ethics considerations?", "ethical considerations?"]
  - "Open Science"          # shorthand: name used as the only pattern
```

## Layout

```
format_checker/
  cli.py          click entry point
  runner.py       per-paper orchestration
  profile.py      YAML loader + profile dataclasses
  models.py       Issue / PageClassification / PaperReport
  checks/
    pages.py           size, body/refs/appendix classification, page caps
    geometry.py        margins and text-block bbox
    fonts.py           body font family and size
    sections.py        required-section heading detection
    anonymization.py   author emails, affiliations, self-citation
  render.py       page → PNG with overlay boxes
  report.py       Jinja2 HTML + CSV writer
  templates/      report.html.j2, index.html.j2
profiles/         YAML venue profiles
tests/
  fixtures/       synthetic PDFs built with ReportLab
```

## Tests

```bash
.venv/bin/python -m pytest tests/
```

Tests build synthetic fixtures with ReportLab and exercise every check
(pass/fail cases for page count, margins, fonts, required sections,
anonymization).

## Limitations

- Body-vs-references split is heading-based. A paper that styles its
  References heading unusually will produce an ambiguous classification and
  emit a `pages.section_detection` info issue so the chair can eyeball the
  split themselves.
- Anonymization is a best-effort heuristic (warnings, never errors). It will
  miss cleverly de-anonymized papers and occasionally flag legitimately
  third-person phrasing.
- OCR / scanned PDFs are not supported — born-digital only.
