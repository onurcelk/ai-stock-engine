"""Shared fixtures and the fast/slow split.

Everything here is hermetic on purpose. `app/cache/` is gitignored, so its CSVs
will not exist on a fresh clone — a test that reads them would pass on the
machine that wrote them and fail everywhere else. Tests that need a cache build
one in `tmp_path` instead. `dataset/` *is* tracked, so the bundled CSVs are safe
to read. Nothing here touches the network.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

APP = pathlib.Path(__file__).resolve().parents[1]
REPO = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


# ------------------------------------------------------------------ fast/slow
#
# `--runslow` and the marker that honours it moved to the repository-root
# `conftest.py` on 2026-08-23. A conftest here is only loaded once collection
# reaches `app/tests`, so the gate silently did not apply to a run that
# selected another directory -- see that file's docstring.


# -------------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True, scope="session")
def never_touch_the_backup_drive():
    """No automated run may write to `D:\\prediction market backup`, ever.

    The backup drive holds copies of prospective forecasts that cannot be
    regenerated. Tests that want backup behaviour pass their own `tmp_path`
    root explicitly; this stops anything that forgets — a default argument, a
    launcher imported by accident — from reaching the real drive.

    Belt and braces: `run_app.py` is the only thing that installs the lifecycle
    hooks, and no test imports it.
    """
    import os

    from core import ledger_backup

    os.environ[ledger_backup.DISABLE_ENV] = "1"
    yield
    os.environ.pop(ledger_backup.DISABLE_ENV, None)


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO


@pytest.fixture(scope="session")
def bundled() -> pd.DataFrame:
    """GOOG-year: 252 close-only daily bars, and the canary's series."""
    from core import data
    return data.load("GOOG-year")


@pytest.fixture(scope="session")
def bundled_close(bundled) -> pd.Series:
    return bundled["close"]


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """A deterministic OHLCV frame on weekday bars, for chart and data tests."""
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2024-01-01", periods=260)
    close = 100 + np.cumsum(rng.standard_normal(len(dates)))
    spread = np.abs(rng.standard_normal(len(dates))) * 0.5
    return pd.DataFrame({
        "date": dates,
        "open": close - rng.standard_normal(len(dates)) * 0.2,
        "high": close + spread,
        "low": close - spread,
        "close": close,
        "volume": rng.integers(1_000, 100_000, len(dates)).astype(float),
    })


@pytest.fixture
def crypto_ohlcv(synthetic_ohlcv) -> pd.DataFrame:
    """The same shape but on calendar days, so weekends carry real bars."""
    frame = synthetic_ohlcv.copy()
    frame["date"] = pd.date_range("2024-01-01", periods=len(frame), freq="D")
    return frame


@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    """Point live.CACHE_DIR at a scratch directory for the duration of a test."""
    from core import live
    monkeypatch.setattr(live, "CACHE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def offline(monkeypatch):
    """Make any download attempt fail, so cache behaviour is observable.

    Patches the symbol `live._download` resolves at call time rather than
    yfinance itself, which keeps the test independent of whether yfinance is
    even installed.
    """
    from core import live

    calls = []

    def refuse(symbol, period, interval):
        calls.append((symbol, period, interval))
        raise live.FetchError("network disabled for this test")

    monkeypatch.setattr(live, "_download", refuse)
    return calls
