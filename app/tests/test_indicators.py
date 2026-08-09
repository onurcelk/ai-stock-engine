"""The evidence layer: every source on one scale, and nothing off it.

The contract `ultimate.py` depends on is narrow and worth guarding exactly —
finite, inside [-1, 1], indexed like the frame, and signed the way the
textbook signs it. A source that quietly returned 1.4, or NaN through its
warm-up, would not raise anywhere; it would just move a verdict.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import indicators


def trending(direction: int, rows: int = 400, noise: float = 0.05) -> pd.DataFrame:
    """A series that goes one way, with just enough noise to be a price."""
    rng = np.random.default_rng(7)
    steps = direction * 0.25 + rng.standard_normal(rows) * noise
    close = 100 + np.cumsum(steps)
    return pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=rows),
        "open": close,
        "high": close + 0.4,
        "low": close - 0.4,
        "close": close,
        "volume": np.full(rows, 10_000.0) + rng.integers(0, 500, rows),
    })


@pytest.fixture
def rising() -> pd.DataFrame:
    return trending(1)


@pytest.fixture
def falling() -> pd.DataFrame:
    return trending(-1)


# --------------------------------------------------------------- the contract


@pytest.mark.parametrize("key", list(indicators.SOURCES))
def test_every_source_stays_inside_the_scale(key, rising):
    series = indicators.SOURCES[key].read(rising)
    assert len(series) == len(rising)
    assert series.index.equals(rising.index)
    assert np.isfinite(series.to_numpy()).all(), f"{key} produced NaN or inf"
    assert series.between(-1.0, 1.0).all(), f"{key} left [-1, 1]"


@pytest.mark.parametrize("key", list(indicators.SOURCES))
def test_every_source_survives_a_close_only_frame(key, rising):
    """Bundled CSVs and FX files have no high, low or volume.

    A source that needs them must return zeros — "no opinion" — rather than
    raising or inventing a reading from the close.
    """
    close_only = rising[["date", "close"]].copy()
    series = indicators.SOURCES[key].read(close_only)
    assert np.isfinite(series.to_numpy()).all()
    assert series.between(-1.0, 1.0).all()


@pytest.mark.parametrize("key", list(indicators.SOURCES))
def test_every_source_survives_a_flat_series(key):
    """A constant price divides by zero in most of these formulas."""
    rows = 200
    flat = pd.DataFrame({
        "date": pd.bdate_range("2021-01-01", periods=rows),
        "open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0,
        "volume": 0.0,
    })
    series = indicators.SOURCES[key].read(flat)
    assert np.isfinite(series.to_numpy()).all()
    assert (series.abs() < 0.2).all(), f"{key} found a trend in a flat line"


@pytest.mark.parametrize("key", list(indicators.SOURCES))
def test_every_source_survives_a_frame_shorter_than_its_warmup(key):
    short = trending(1, rows=12)
    series = indicators.SOURCES[key].read(short)
    assert len(series) == len(short)
    assert np.isfinite(series.to_numpy()).all()


# ------------------------------------------------------------------- the signs
#
# These are the assertions that would catch an inverted source, which is the
# one bug in this file that calibration cannot save you from: ultimate.py may
# lower a source's weight but is deliberately forbidden from flipping it.


# MACD is absent on purpose. Its histogram is the gap between the MACD line
# and its own signal line, which converges to zero on a *constant* slope — it
# measures acceleration, not direction, so asserting its sign on a straight
# ramp tests a misunderstanding rather than the source. It gets its own test.
TREND_FOLLOWING = ["trend_ma", "trend_slope", "adx", "rsi", "roc",
                   "donchian", "obv", "structure"]


@pytest.mark.parametrize("key", TREND_FOLLOWING)
def test_trend_followers_are_bullish_on_a_rising_series(key, rising):
    assert indicators.SOURCES[key].read(rising).iloc[-1] > 0


@pytest.mark.parametrize("key", TREND_FOLLOWING)
def test_trend_followers_are_bearish_on_a_falling_series(key, falling):
    assert indicators.SOURCES[key].read(falling).iloc[-1] < 0


def test_macd_reads_acceleration_not_slope():
    """Positive when the advance is speeding up, negative when it stalls."""
    rows = 300
    ramp = np.linspace(0, 1, rows)
    accelerating = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=rows),
        "close": 100 + 60 * ramp ** 2,
    })
    decelerating = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=rows),
        "close": 100 + 60 * np.sqrt(ramp),
    })
    for column in ("open", "high", "low"):
        accelerating[column] = accelerating["close"]
        decelerating[column] = decelerating["close"]

    assert indicators.SOURCES["macd"].read(accelerating).iloc[-1] > 0
    assert indicators.SOURCES["macd"].read(decelerating).iloc[-1] < 0


def test_bollinger_argues_against_the_stretch(rising, falling):
    """The one deliberate contrarian. Its disagreement is the information."""
    assert indicators.SOURCES["bollinger"].read(rising).iloc[-1] < 0
    assert indicators.SOURCES["bollinger"].read(falling).iloc[-1] > 0


def test_sources_are_scale_free(rising):
    """The same shape at $3 and at $90,000 has to read the same.

    Without this a verdict on BTC and a verdict on a penny stock are on
    different scales and the family cap in ultimate.py stops meaning anything.
    """
    scaled = rising.copy()
    for column in ("open", "high", "low", "close"):
        scaled[column] = scaled[column] * 1_000

    for key in indicators.SOURCES:
        here = indicators.SOURCES[key].read(rising).iloc[-1]
        there = indicators.SOURCES[key].read(scaled).iloc[-1]
        assert here == pytest.approx(there, abs=0.02), key


# ----------------------------------------------------------------- primitives


def test_rsi_pins_at_100_on_an_unbroken_run():
    """avg_loss of zero is a division by zero, not an undefined RSI."""
    close = pd.Series(np.arange(1, 60, dtype=float))
    assert indicators.rsi(close).iloc[-1] == pytest.approx(100.0)


def test_rsi_holds_its_warmup_open():
    close = pd.Series(np.arange(1, 60, dtype=float))
    assert indicators.rsi(close, 14).iloc[:13].isna().all()


def test_atr_never_reaches_zero_on_a_flat_series():
    """Every source divides by this."""
    flat = pd.DataFrame({"close": np.full(60, 25.0), "high": np.full(60, 25.0),
                         "low": np.full(60, 25.0)})
    assert (indicators.atr(flat).dropna() > 0).all()


def test_true_range_falls_back_to_close_moves_without_high_and_low():
    frame = pd.DataFrame({"close": [10.0, 12.0, 9.0]})
    assert list(indicators.true_range(frame).iloc[1:]) == [2.0, 3.0]


def test_donchian_excludes_the_current_bar():
    """Including it would make every new high sit at the channel top by
    construction, which is a definition rather than an observation."""
    rows = 60
    close = pd.Series(np.arange(rows, dtype=float) + 100)
    frame = pd.DataFrame({"close": close, "high": close, "low": close})
    upper, _ = indicators.donchian(frame, 20)
    # On a strictly rising series the channel top is yesterday's high, so the
    # close is always above it. If today's bar leaked in they would be equal.
    assert upper.iloc[-1] == pytest.approx(close.iloc[-2])
    assert close.iloc[-1] > upper.iloc[-1]


def test_squash_is_monotonic_and_bounded():
    values = pd.Series([-100.0, -1.0, 0.0, 1.0, 100.0])
    squashed = indicators.squash(values)
    assert squashed.is_monotonic_increasing
    assert squashed.between(-1, 1).all()
    assert squashed.iloc[2] == 0.0


# --------------------------------------------------------------------- stance


def test_stance_forward_fills_an_event_signal():
    """backtest.py's signals are events; a standing position is what they mean."""
    signal = pd.Series([0.0, 1.0, 0.0, 0.0, -1.0, 0.0, 0.0])
    assert list(indicators.stance(signal)) == [0.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0]


def test_stance_is_flat_before_the_first_signal():
    assert list(indicators.stance(pd.Series([0.0, 0.0, 1.0]))) == [0.0, 0.0, 1.0]


def test_registry_keys_match_their_sources():
    for key, source in indicators.SOURCES.items():
        assert source.key == key
        assert source.name and source.describe
        assert source.family
