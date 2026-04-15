from __future__ import annotations

from pathlib import Path

import pytest

from format_checker.profile import load_profile

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_fixtures():
    if not any(FIXTURES_DIR.glob("*.pdf")):
        from tests.fixtures import make_fixtures
        make_fixtures.main()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    _ensure_fixtures()
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def ieee_profile():
    return load_profile(REPO_ROOT / "profiles" / "ieee_conf_a4.yaml")


@pytest.fixture(scope="session")
def usenix_profile():
    return load_profile(REPO_ROOT / "profiles" / "usenix.yaml")
