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

Phase 6 adds the forecast ledger, which is the one file here that could not be
put back. `app/forecast_ledger.sqlite3` is append-only and never regenerable,
and until 2026-08-23 this fixture did not redirect it -- so the first test to
call the Signal endpoint would have appended to the real prospective record.
`ledger_activation.writes_blocked` refuses that independently, and a test below
asserts it does; this redirect is the belt to that brace, so the suite is
hermetic by construction rather than only by refusal.
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

from core import forecast_ledger, holdings, live, runs, watchlist  # noqa: E402


@pytest.fixture
def isolated_holdings(tmp_path, monkeypatch):
    """Redirect both holdings files into a scratch directory for one test."""
    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")


@pytest.fixture
def isolated_watchlist(tmp_path, monkeypatch):
    """Redirect the saved board, since the watchlist endpoints now write.

    Deliberately not created: absence is the `auto` mode the endpoint reports,
    and a fixture that wrote an empty file would start every test in `custom`
    -- the one state the derived-default tests are about.
    """
    path = tmp_path / "watchlist.json"
    monkeypatch.setattr(watchlist, "STORE", path)
    return path


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

    def fake_fetch(symbol, period="1y", interval="1d", force=False):
        # `force` is in the signature because `ultimate.evaluate` passes it,
        # and a stub that cannot be called the way production calls it is a
        # stub that quietly excludes the engine from the suite.
        if not str(symbol).strip():
            raise live.FetchError("no symbol")
        return frame.copy(), types.SimpleNamespace(is_fresh=True)

    monkeypatch.setattr(live, "fetch", fake_fetch)
    return frame


@pytest.fixture
def isolated_ledger(tmp_path, monkeypatch):
    """Point the forecast ledger at a scratch path, and do not create it.

    Deliberately not created: `ForecastLedger.__init__` creates its file, so a
    fixture that made one would hide the "reading a page must not start a
    record" guarantee the Research endpoint's own test rests on.
    """
    path = tmp_path / "forecast_ledger.sqlite3"
    monkeypatch.setattr(forecast_ledger, "DEFAULT_PATH", path)
    return path


@pytest.fixture
def jobs_registry(monkeypatch):
    """A private job registry per test, shut down afterwards.

    The app serves from a module-level `api.jobs.REGISTRY` holding a worker
    thread; sharing one across tests would leak a queue between them and leave
    threads alive at the end of the run.
    """
    from api import jobs as jobs_module
    from api.routers import jobs as jobs_router

    registry = jobs_module.JobRegistry()
    monkeypatch.setattr(jobs_module, "REGISTRY", registry)
    monkeypatch.setattr(jobs_router, "JOBS", registry)
    try:
        yield registry
    finally:
        registry.shutdown(wait=True)


@pytest.fixture
def client(isolated_holdings, isolated_runs, isolated_ledger,
           isolated_watchlist, stub_bars, jobs_registry):
    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app)
