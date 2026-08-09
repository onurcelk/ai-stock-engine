"""The validation harness's own guarantee: it cannot see the future.

A backtest that leaks is worse than no backtest, because it produces a number
that looks like evidence. The central test here is `test_future_cannot_change
_the_verdict`: two caches that are byte-identical up to the cutoff and wildly
different afterwards must produce the same prediction. If any part of the
engine ever reaches past the cutoff — a scaler fitted on the whole series, a
calibration window measured from the end, an indicator using `.iloc[-1]` of an
untrimmed frame — that test fails and the study is void.

Hermetic like the rest of the suite: everything runs against a synthetic cache
in `tmp_path`, never `app/cache/`.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.core import live, ultimate  # noqa: E402
from validation import metrics, outcomes, pit  # noqa: E402

CUTOFF = pd.Timestamp("2024-06-28")


def _series(seed: int, rows: int = 1_400, after: int | None = None,
            shock: float = 0.0) -> pd.DataFrame:
    """A random walk with optional surgery applied only after bar `after`."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0004, 0.012, rows)
    if after is not None and shock:
        steps[after:] += shock
    close = 100 * np.exp(np.cumsum(steps))
    dates = pd.bdate_range("2019-01-01", periods=rows)
    return pd.DataFrame({
        "date": dates,
        "close": close,
        "open": close * 0.999,
        "high": close * 1.008,
        "low": close * 0.992,
        "volume": rng.integers(1_000_000, 5_000_000, rows).astype(float),
    })


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """A writable cache directory the whole package points at."""
    monkeypatch.setattr(live, "CACHE_DIR", tmp_path)
    def write(symbol: str, frame: pd.DataFrame, interval: str = "1d") -> None:
        live._write_cache(symbol, interval, frame, period="10y")
    return write


# ------------------------------------------------------------------ the trim


def test_fetcher_returns_nothing_after_the_cutoff(cache):
    cache("TEST", _series(1))
    frame, entry = pit.fetcher(CUTOFF)("TEST", period="10y", interval="1d")

    assert frame["date"].max() <= pit.as_of(CUTOFF)
    assert entry.end == frame["date"].iloc[-1].date()
    assert entry.rows == len(frame)


def test_period_is_measured_back_from_the_cutoff_not_from_today(cache):
    """A "1y" request at a 2024 cutoff is 2023-2024, not the last twelve months.

    Trimming before truncating — the obvious ordering — would hand the engine a
    frame that ends at the cutoff but *starts* a year before today, which is
    both shorter than production would have had and silently different per run.
    """
    cache("TEST", _series(2))
    frame, _ = pit.fetcher(CUTOFF)("TEST", period="1y", interval="1d")

    span = (frame["date"].iloc[-1] - frame["date"].iloc[0]).days
    assert 330 <= span <= 366
    assert frame["date"].iloc[-1] <= pit.as_of(CUTOFF)


def test_missing_symbol_raises_rather_than_returning_an_empty_frame(cache):
    cache("TEST", _series(3))
    with pytest.raises(live.FetchError):
        pit.fetcher(CUTOFF)("NOSUCH", period="10y", interval="1d")


def test_a_symbol_that_had_not_listed_yet_raises(cache):
    late = _series(4)
    late["date"] = pd.bdate_range("2025-01-01", periods=len(late))
    cache("LATE", late)
    with pytest.raises(live.FetchError):
        pit.fetcher(CUTOFF)("LATE", period="10y", interval="1d")


# ----------------------------------------------------------- the real property


def test_future_cannot_change_the_verdict(cache):
    """The whole study rests on this: rewrite the future, get the same call.

    Both series share every bar up to the cutoff and then diverge by a large
    persistent drift. A verdict that differs between them is a verdict that
    read a bar it was not entitled to.
    """
    split = 1_200
    calm = _series(7, after=split, shock=0.0)
    storm = _series(7, after=split, shock=-0.05)
    cutoff = pd.Timestamp(calm["date"].iloc[split - 1])

    # Sanity: the two series really are identical before and different after.
    assert np.allclose(calm["close"][:split], storm["close"][:split])
    assert not np.allclose(calm["close"][split:], storm["close"][split:])

    cache("CALM", calm)
    cache("STORM", storm)

    first = ultimate.evaluate("CALM", fetcher=pit.fetcher(cutoff))
    second = ultimate.evaluate("STORM", fetcher=pit.fetcher(cutoff))

    assert first.action == second.action
    assert first.score == pytest.approx(second.score)
    assert first.confidence == pytest.approx(second.confidence)
    for left, right in zip(first.horizons, second.horizons):
        assert left.score == pytest.approx(right.score)
        assert left.confidence == pytest.approx(right.confidence)


def test_baselines_cannot_see_the_future(cache):
    split = 1_200
    calm = _series(11, after=split, shock=0.0)
    storm = _series(11, after=split, shock=-0.05)
    cutoff = pd.Timestamp(calm["date"].iloc[split - 1])
    rng = np.random.default_rng(0)

    left = outcomes.baselines(calm, cutoff, 5, rng)
    right = outcomes.baselines(storm, cutoff, 5, np.random.default_rng(0))
    assert left == right


def test_information_set_is_recorded_at_the_cutoff(cache):
    cache("TEST", _series(13))
    described = pit.describe_information_set("TEST", CUTOFF)

    assert described["1d"]["available"] is True
    assert pd.Timestamp(described["1d"]["last_bar"]) <= pit.as_of(CUTOFF)
    # No hourly cache was written, so the harness says so rather than guessing.
    assert described["1h"]["available"] is False


# --------------------------------------------------------------- the outcomes


def test_forward_measures_the_move_after_the_cutoff(cache):
    frame = pd.DataFrame({
        "date": pd.bdate_range("2024-01-01", periods=10),
        "close": [100.0, 101, 102, 103, 104, 105, 106, 107, 108, 109],
    })
    cutoff = pd.Timestamp(frame["date"].iloc[4])       # close 104

    result = outcomes.forward(frame, cutoff, 3)
    assert result["start_price"] == 104
    assert result["end_price"] == 107
    assert result["return_pct"] == pytest.approx(2.8846, abs=1e-3)
    assert result["direction"] == 1
    assert result["max_adverse_pct"] == pytest.approx(0.9615, abs=1e-3)


def test_forward_returns_none_when_the_window_has_not_happened(cache):
    frame = pd.DataFrame({
        "date": pd.bdate_range("2024-01-01", periods=10),
        "close": np.linspace(100, 110, 10),
    })
    assert outcomes.forward(frame, pd.Timestamp(frame["date"].iloc[-2]), 5) is None


# ---------------------------------------------------------------- the statistics


def test_clustered_error_is_wider_when_the_rows_move_together():
    """Thirty symbols on one day is not thirty observations.

    The whole reason the report quotes clustered intervals: a perfectly
    correlated cluster carries one observation's worth of information, and an
    interval that ignores that is the mechanism by which noise gets published.
    """
    # Twelve dates, thirty symbols, every symbol in a date agreeing exactly.
    frame = pd.DataFrame([
        {"correct": float(date % 2), "cutoff": date}
        for date in range(12) for _ in range(30)
    ])
    estimate = metrics.accuracy(frame["correct"], frame["cutoff"])

    assert estimate.n == 360
    assert estimate.clusters == 12
    assert estimate.se > estimate.naive_se * 3
    # 50% by construction, and correctly indistinguishable from a coin flip.
    assert estimate.value == pytest.approx(50.0)
    assert estimate.p_value > 0.9


def test_clustered_error_matches_the_naive_one_for_singleton_clusters():
    rng = np.random.default_rng(5)
    values = pd.Series(rng.normal(0, 1, 200))
    clusters = pd.Series(range(200))
    estimate = metrics.estimate(values, clusters)

    assert estimate.clusters == 200
    assert estimate.se == pytest.approx(estimate.naive_se, rel=0.02)


def test_paired_difference_cancels_the_common_market_move():
    """Two systems that differ on one row in twelve, scored on the same rows."""
    rows = []
    for date in range(12):
        for index in range(10):
            outcome = float((date + index) % 2)
            rows.append({"a": outcome, "b": outcome, "cutoff": date})
    frame = pd.DataFrame(rows)
    frame.loc[0, "a"] = 1.0 - frame.loc[0, "b"]

    diff = metrics.paired(frame["a"], frame["b"], frame["cutoff"])
    assert diff.n == 120
    assert diff.value != 0
    # One flipped row out of 120 is not evidence of anything.
    assert not diff.significant
