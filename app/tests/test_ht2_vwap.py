"""HT-2's vwap_reversion signal: PIT-safety and the mean-reversion sign.

Window (10) and threshold (2.0) are frozen in
`alpha/HT2_TOURNAMENT_PREREGISTRATION.md` Amendment 1, before any forward
return for this candidate was read. These tests check the mechanism, not any
predictive claim about it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import ht2_vwap


def _flat_frame(rows: int = 60, price: float = 100.0, volume: float = 1_000_000.0):
    return pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=rows),
        "open": price, "high": price, "low": price, "close": price,
        "volume": volume,
    })


def test_a_flat_series_never_signals():
    frame = _flat_frame()
    signal = ht2_vwap.vwap_reversion_series(frame)
    # A flat price has zero spread, which the `spread > 0` guard excludes.
    assert (signal.iloc[ht2_vwap.WINDOW:] == ht2_vwap.HOLD).all()


def test_a_spike_above_a_flat_band_signals_sell():
    frame = _flat_frame()
    frame.loc[frame.index[-1], ["open", "high", "low", "close"]] = 200.0
    # Give the window some real spread to divide by, but not from the spike
    # itself, so the guard at "spread == 0" is not what is being tested here.
    frame.loc[frame.index[-5], ["open", "high", "low", "close"]] = 101.0
    signal = ht2_vwap.vwap_reversion_series(frame)
    assert signal.iloc[-1] == ht2_vwap.SELL


def test_a_dip_below_a_flat_band_signals_buy():
    frame = _flat_frame()
    frame.loc[frame.index[-1], ["open", "high", "low", "close"]] = 20.0
    frame.loc[frame.index[-5], ["open", "high", "low", "close"]] = 99.0
    signal = ht2_vwap.vwap_reversion_series(frame)
    assert signal.iloc[-1] == ht2_vwap.BUY


def test_too_little_history_is_a_hold():
    frame = _flat_frame(rows=5)
    assert ht2_vwap.call_at(frame, 4) == ht2_vwap.HOLD


def test_call_at_matches_truncate_then_read_last():
    """PIT-safety: the value at `position` must not depend on rows after it."""
    rng = np.random.default_rng(7)
    rows = 80
    close = 100 * np.exp(np.cumsum(rng.normal(0.0, 0.02, rows)))
    frame = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=rows),
        "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
        "volume": rng.integers(1_000, 10_000, rows).astype(float),
    })

    for position in (20, 40, 79):
        from_full = ht2_vwap.call_at(frame, position)
        truncated = frame.iloc[: position + 1]
        from_truncated = float(ht2_vwap.vwap_reversion_series(truncated).iloc[-1])
        assert from_full == pytest.approx(from_truncated)


def test_extending_the_future_never_changes_a_past_call():
    """The leak-detector property, specific to this signal."""
    rng = np.random.default_rng(11)
    rows = 60
    close = 100 * np.exp(np.cumsum(rng.normal(0.0, 0.02, rows)))
    base = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=rows),
        "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
        "volume": rng.integers(1_000, 10_000, rows).astype(float),
    })
    extra = pd.DataFrame({
        "date": pd.bdate_range(base["date"].iloc[-1] + pd.Timedelta(days=1), periods=10),
        "open": 9999.0, "high": 9999.0, "low": 9999.0, "close": 9999.0,
        "volume": 1.0,
    })
    extended = pd.concat([base, extra], ignore_index=True)

    for position in (30, 50, 59):
        assert ht2_vwap.call_at(base, position) == ht2_vwap.call_at(extended, position)


def test_measure_produces_the_columns_leaderboard_expects(monkeypatch):
    from core import tournament

    rng = np.random.default_rng(3)
    rows = 900
    frames = {}
    for symbol in ("AAA", "BBB"):
        close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, rows)))
        frames[symbol] = pd.DataFrame({
            "date": pd.bdate_range("2019-01-01", periods=rows, tz="UTC"),
            "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
            "volume": rng.integers(1_000, 10_000, rows).astype(float),
        })

    result = ht2_vwap.measure(frames=frames)

    assert not result.empty
    for column in ("candidate", "horizon", "symbol", "cutoff_at", "matured_at",
                    "call", "directional_correct", "realised_return"):
        assert column in result.columns
    assert set(result["candidate"]) == {ht2_vwap.CANDIDATE_KEY}
    assert set(result["horizon"]) <= set(tournament.HORIZON_BARS)


def test_it_does_not_touch_the_production_roster_or_store():
    """It must reuse tournament's read-only helpers, never its writable store."""
    import inspect

    text = inspect.getsource(ht2_vwap)
    for forbidden in ("TournamentStore(", "CANDIDATES[", "CANDIDATES.setdefault",
                      "record_outcomes(", "record_signals("):
        assert forbidden not in text, forbidden
