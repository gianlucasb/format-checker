from __future__ import annotations

import builtins

import pytest

from format_checker.printpdf import (
    _discover_html_files,
    _missing_playwright_message,
    render_reports,
)


def test_discover_html_files_returns_per_paper_pairs(tmp_path):
    # Layout that mirrors what `format-checker check` produces.
    (tmp_path / "index.html").write_text("<batch>")
    (tmp_path / "summary.csv").write_text("paper,status\n")
    (tmp_path / "paper-a").mkdir()
    (tmp_path / "paper-a" / "index.html").write_text("<a>")
    (tmp_path / "paper-a" / "page-001.png").write_bytes(b"")
    (tmp_path / "paper-b").mkdir()  # subdir without an index.html
    (tmp_path / "paper-c").mkdir()
    (tmp_path / "paper-c" / "index.html").write_text("<c>")

    pairs = _discover_html_files(tmp_path)
    assert pairs == [
        (tmp_path / "paper-a" / "index.html", tmp_path / "paper-a" / "paper-a-format-check.pdf"),
        (tmp_path / "paper-c" / "index.html", tmp_path / "paper-c" / "paper-c-format-check.pdf"),
    ]


def test_discover_html_files_excludes_batch_index(tmp_path):
    # The batch index lives at out/index.html — it should not be in the list.
    (tmp_path / "index.html").write_text("<batch>")
    pairs = _discover_html_files(tmp_path)
    assert pairs == []


def test_render_reports_raises_clear_message_without_playwright(monkeypatch, tmp_path):
    # Simulate playwright not being installed by intercepting the import.
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright" or name.startswith("playwright."):
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError) as exc:
        render_reports(tmp_path)
    msg = str(exc.value)
    assert "playwright is not installed" in msg
    assert "pip install" in msg
    assert "playwright install chromium" in msg


def test_missing_playwright_message_is_actionable():
    msg = _missing_playwright_message()
    assert "[print]" in msg
    assert "playwright install chromium" in msg
