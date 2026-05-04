from __future__ import annotations

from format_checker.cleared import (
    CLEARED_FILENAME,
    SCHEMA_VERSION,
    hash_pdf,
    load_cleared,
    merge_cleared,
    save_cleared,
)


def test_hash_pdf_is_stable(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"hello world")
    assert hash_pdf(f) == hash_pdf(f)


def test_hash_pdf_changes_with_bytes(tmp_path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"hello world")
    b.write_bytes(b"hello WORLD")
    assert hash_pdf(a) != hash_pdf(b)


def test_load_returns_empty_when_missing(tmp_path):
    assert load_cleared(tmp_path) == {}


def test_load_ignores_wrong_version(tmp_path):
    (tmp_path / CLEARED_FILENAME).write_text('{"version": 99, "cleared": {"x": {}}}')
    assert load_cleared(tmp_path) == {}


def test_load_ignores_corrupt_file(tmp_path):
    (tmp_path / CLEARED_FILENAME).write_text("not json")
    assert load_cleared(tmp_path) == {}


def test_save_and_load_roundtrip(tmp_path):
    data = {"paper_a": {"hash": "abc", "note": "looks fine", "cleared_at": "2026-05-04T12:00:00Z"}}
    save_cleared(tmp_path, data)
    payload = (tmp_path / CLEARED_FILENAME).read_text()
    assert f'"version": {SCHEMA_VERSION}' in payload
    assert load_cleared(tmp_path) == data


def test_merge_keeps_matching_hash():
    existing = {"a": {"hash": "h1"}, "b": {"hash": "h2"}}
    current = [("a", "h1"), ("b", "h2")]
    assert merge_cleared(existing, current) == existing


def test_merge_drops_changed_hash():
    existing = {"a": {"hash": "h1"}}
    current = [("a", "h_new")]
    assert merge_cleared(existing, current) == {}


def test_merge_drops_removed_slug():
    existing = {"a": {"hash": "h1"}, "gone": {"hash": "h2"}}
    current = [("a", "h1")]
    assert merge_cleared(existing, current) == {"a": {"hash": "h1"}}
