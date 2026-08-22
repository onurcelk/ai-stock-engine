"""Hermetic fixtures for the API layer.

Mirrors `app/tests/test_holdings.py`'s own `store` fixture exactly: redirect
`holdings.STORE`/`LEDGER` to a scratch directory before the client ever calls
an endpoint. `holdings._store`/`_ledger` resolve these module attributes at
call time (not at import time), which is what makes monkeypatching them
here actually reach the running FastAPI app -- the same property that
fixture's own docstring calls "the only thing standing between a test run
and someone's actual holdings."

Phase 4 adds two more isolations, on the same principle. `runs.RUNS_DIR` is
redirected because the History endpoints delete saved runs, and `live.fetch`
is replaced with a deterministic synthetic series because several Phase 4
endpoints read bars and this suite never touches the network.
"""

from __future__ import annotations

import pathlib
import sys
import types

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import holdings, live, runs  # noqa: E402


@pytest.fixture
def isolated_holdings(tmp_path, monkeypatch):
    """Redirect both holdings files into a scratch directory for one test."""
    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")


@pytest.fixture
def isolated_runs(tmp_path, monkeypatch):
    """Redirect the saved-runs folder, since the History endpoints delete."""
    directory = tmp_path / "runs"
    directory.mkdir()
    monkeypatch.setattr(runs, "RUNS_DIR", directory)
    return directory


def synthetic_bars(rows: int = 300, seed: int = 7) -> pd.DataFrame:
    """A deterministic OHLCV series with enough rows for every study to warm up.

    Built from a seeded random walk rather than a fixture file so it cannot go
    stale, and with a real high/low spread so the OHLC-only studies (Supertrend,
    WaveTrend, Squeeze) have the columns they require.
    """
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, rows)))
    spread = close * rng.uniform(0.004, 0.02, rows)
    open_ = close + rng.normal(0, 1, rows) * close * 0.003
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=rows, freq="D"),
        "open": open_,
        "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread,
        "close": close,
        "volume": rng.integers(1_000_000, 9_000_000, rows).astype(float),
    })


@pytest.fixture
def stub_bars(monkeypatch):
    """Replace the one data door with a synthetic series, so no test can reach
    the network. Returns the frame the endpoints will see."""
    frame = synthetic_bars()

    def fake_fetch(symbol, period="1y", interval="1d"):
        if not str(symbol).strip():
            raise live.FetchError("no symbol")
        return frame.copy(), types.SimpleNamespace(is_fresh=True)

    monkeypatch.setattr(live, "fetch", fake_fetch)
    return frame


@pytest.fixture
def client(isolated_holdings, isolated_runs, stub_bars):
    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app)
