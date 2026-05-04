"""Persistence for chair-side 'cleared' decisions on reports.

A *cleared* paper is a report the chair has manually reviewed and decided
is safe to ignore (e.g. the tool flagged something that's actually fine).

State is stored in ``<out_dir>/cleared.json``::

    {
      "version": 1,
      "cleared": {
        "<slug>": {
          "hash": "<sha256 of PDF bytes>",
          "note": "<optional reason>",
          "cleared_at": "<ISO 8601 timestamp>"
        }
      }
    }

Entries are keyed by slug and validated against the PDF hash on every run,
so a paper that gets re-uploaded with different content automatically
loses its cleared state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

CLEARED_FILENAME = "cleared.json"
SCHEMA_VERSION = 1


def hash_pdf(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cleared(out_dir: Path) -> dict[str, dict]:
    path = out_dir / CLEARED_FILENAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict) or data.get("version") != SCHEMA_VERSION:
        return {}
    raw = data.get("cleared") or {}
    return {k: dict(v) for k, v in raw.items() if isinstance(v, dict)}


def save_cleared(out_dir: Path, cleared: dict[str, dict]) -> Path:
    path = out_dir / CLEARED_FILENAME
    payload = {"version": SCHEMA_VERSION, "cleared": cleared}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def merge_cleared(
    existing: dict[str, dict], current: Iterable[tuple[str, str]]
) -> dict[str, dict]:
    """Drop entries whose slug is no longer present or whose PDF hash changed.

    `current` is an iterable of (slug, hash) for the just-completed run.
    """
    valid = {slug: h for slug, h in current}
    return {
        slug: entry
        for slug, entry in existing.items()
        if slug in valid and entry.get("hash") == valid[slug]
    }
