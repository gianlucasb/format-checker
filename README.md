# format-checker

Batch-check conference submission PDFs against a venue format profile (IEEE,
ACM, USENIX, NDSS, …) and produce a chair-friendly report with per-page PNG
overlays showing where a paper deviates from the expected geometry.

Accepts a single PDF, a directory of PDFs, or a HotCRP-style archive
(`.zip`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar`) — drop in the file you
downloaded and the tool takes it from there.

## What it checks

- **Pages** — page size, body page count (references, appendix, and an
  optional pre-references *Ethics Considerations* section excluded by
  default), optional hard cap on total pages, and an optional warning when
  the main content is suspiciously short (likely incomplete submission).
- **Margins & geometry** — main text block vs. profile margins, checked
  symmetrically so a paper rendered with a *tighter* template (text sitting
  well inside the expected block — the classic "wrong template" signal) is
  flagged just like text bleeding outside. Running headers, footers, and
  title-page layouts are filtered out.
- **Column layout** — detected column count vs. profile, biased by the
  profile's expected column positions so math/table-heavy pages don't
  false-positive but a single-column paper submitted to a two-column venue
  still trips.
- **Fonts** — body font family and size, detected per-span from the PDF.
- **Required sections** — flag if a CFP-mandated heading (e.g. *Ethics
  Considerations*, *Open Science*) is missing.
- **Anonymization** (submissions only) — author emails, affiliation keywords,
  and prior-publication self-references like "our previous work" or
  "our earlier study". Internal cross-references like "as we previously
  showed in §3" are not flagged.

A margin violation has to show up on at least two sampled body pages before
it's reported, so a single anomalous page (a wide table breaking the column
flow, an embedded figure with unusual layout) doesn't condemn an otherwise
well-formatted paper.

Each issue is categorized and surfaced in the per-paper HTML report. Rendered
PNGs overlay the **expected text block** (green) and any **issue bboxes** (red
for font, orange for geometry). Papers that pass with no issues get a second
thumbnail showing a representative body page so the chair sees both the title
and the body layout at a glance.

## Install

Requires Python ≥ 3.11.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
```

Dependencies: `pymupdf`, `pillow`, `jinja2`, `pyyaml`, `click` (+ `pytest`,
`reportlab` for tests).

## Usage

The `check` command takes one positional argument — a PDF, a directory, or
an archive — plus `--profile` and `--out`:

```bash
# Single PDF
format-checker check paper.pdf --profile profiles/usenix.yaml --out out

# Directory of PDFs (non-recursive)
format-checker check path/to/submissions --profile profiles/ndss_2026.yaml --out out

# Archive (.zip, .tar.gz, .tgz, .tar.bz2, .tar)
format-checker check submissions.tar.gz --profile profiles/ndss_2026.yaml --out out
```

Archives are extracted to a temp directory for the duration of the run and
scanned recursively, so nested layouts like `papers/<id>/paper.pdf` work
without unpacking by hand. macOS resource-fork files (`__MACOSX/`, `._*`)
are skipped.

### HotCRP workflow

In HotCRP go to **Search → Download → Documents → as `.tar.gz`**, then point
the checker at the file:

```bash
format-checker check sub-pcrev.tar.gz --profile profiles/ndss_2026.yaml --out out
open out/index.html
```

Open `out/index.html` for the batch landing page (sortable, filterable by
status) and `out/summary.csv` for a spreadsheet view. Click any paper to see
its full per-category issue breakdown and rendered pages.

### Reviewing reports — clearing false positives

A chair reviewing the batch index can mark a paper as **cleared** (i.e.
"manually reviewed, safe to ignore") with the per-row "clear" button on the
batch index, or with the "clear" button at the top of the per-paper page.
Cleared rows show a green CLEARED badge, sink to the bottom of the index,
and can be hidden with the "hide cleared" toggle so only the still-failing
papers stay in view.

Decisions live in the browser's localStorage (so reloading preserves them)
and key by paper slug + PDF hash, so re-uploading a paper automatically
loses its cleared state. **Export cleared.json** downloads the decisions
to a file that can live alongside the report; on the next run,
`format-checker check` reads `out/cleared.json`, drops entries whose
slug is gone or whose PDF hash changed, and re-embeds the merged set into
the new `index.html`. **Import cleared.json** seeds localStorage from a
file (e.g. when sharing decisions across machines or reviewers).

## Profiles

Profiles are YAML files — the only thing you change between venues. Example
(`profiles/ndss_2027.yaml`):

```yaml
name: "NDSS 2027"
page:
  size: letter               # or A4, or [width_pt, height_pt]
  max_body_pages: 13
  max_total_pages: null              # refs + appendix + ethics: unlimited
  refs_count_toward_body: false
  appendix_counts_toward_body: false
  ethics_counts_toward_body: false   # exclude a pre-references "Ethics Considerations" section
  min_body_pages_warn: 7             # warn (not error) on suspiciously short submissions
text_block:
  top_margin: 48
  bottom_margin: 55
  left_margin: 45
  right_margin: 45
  columns: 2
  column_gap: 18
fonts:
  body:
    families: ["Times", "TimesNewRoman", "NimbusRomNo9L", "Nimbus Roman", "TeXGyreTermes"]
    min_size: 10.0
tolerance_pt: 8
anonymization:
  required: true
# Optional: required_sections (list of {name, patterns}) or shorthand strings.
```

Bundled profiles:

- `profiles/ieee_conf_a4.yaml`
- `profiles/acm_sigconf.yaml`
- `profiles/usenix.yaml`
- `profiles/ndss_2026.yaml`, `profiles/ndss_2027.yaml` — submission rules
  (anonymous, 13-page body cap, ethics excluded from the cap)
- `profiles/ndss_2026_proceedings.yaml`, `profiles/ndss_2027_proceedings.yaml`
  — camera-ready variants (no anonymization, looser margins matching the IEEE
  conference template)

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
  archive.py      .zip / .tar.gz extraction + recursive PDF discovery
  runner.py       per-paper orchestration (also computes the PDF hash)
  profile.py      YAML loader + profile dataclasses
  models.py       Issue / PageClassification / PaperReport
  cleared.py      cleared.json schema, hash, load/save/merge helpers
  checks/
    pages.py           size, body/refs/appendix/ethics classification, page caps
    geometry.py        margins (symmetric), text-block bbox, column count
    fonts.py           body font family and size
    sections.py        required-section heading detection
    anonymization.py   author emails, affiliations, self-citation
  render.py       page → PNG with overlay boxes
  report.py       Jinja2 HTML + CSV writer (merges cleared.json on each run)
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
