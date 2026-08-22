"""Hermetic fixtures for the API layer.

Mirrors `app/tests/test_holdings.py`'s own `store` fixture exactly: redirect
`holdings.STORE`/`LEDGER` to a scratch directory before the client ever calls
an endpoint. `holdings._store`/`_ledger` resolve these module attributes at
call time (not at import time), which is what makes monkeypatching them
here actually reach the running FastAPI app -- the same property that
fixture's own docstring calls "the only thing standing between a test run
and someone's actual holdings."
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import holdings  # noqa: E402


@pytest.fixture
def isolated_holdings(tmp_path, monkeypatch):
    """Redirect both holdings files into a scratch directory for one test."""
    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")


@pytest.fixture
def client(isolated_holdings):
    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app)
