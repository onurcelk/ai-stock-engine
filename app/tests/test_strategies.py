"""The three rule-based agents.

They only emit signals — backtest.run() does the money — so the contract here
is narrow: the right length, the right index, and only the three legal values.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core import strategies

LEGAL = {strategies.HOLD, strategies.BUY, strategies.SELL}


def emitters(close):
    return {
        "turtle": strategies.turtle(close, window=20),
        "turtle_follow": strategies.turtle(close, window=20, follow_breakout=True),
        "moving_average": strategies.moving_average(close, short_window=5, long_window=20),
        "signal_rolling": strategies.signal_rolling(close, delay=5),
    }


@pytest.mark.parametrize("name", ["turtle", "turtle_follow", "moving_average",
                                  "signal_rolling"])
def test_signal_contract(bundled_close, name):
    signal = emitters(bundled_close)[name]
    assert len(signal) == len(bundled_close)
    assert signal.index.equals(bundled_close.index)
    assert set(signal.unique()) <= LEGAL
    assert not signal.isna().any()


@pytest.mark.parametrize("name", ["turtle", "moving_average", "signal_rolling"])
def test_signals_actually_fire(bundled_close, name):
    """A strategy that never trades would pass every other check silently."""
    signal = emitters(bundled_close)[name]
    assert (signal != strategies.HOLD).any(), f"{name} emitted nothing"


def test_turtle_follow_breakout_changes_behaviour(bundled_close):
    plain = strategies.turtle(bundled_close, window=20, follow_breakout=False)
    follow = strategies.turtle(bundled_close, window=20, follow_breakout=True)
    assert not plain.equals(follow)


def test_bands_line_up_with_the_price_series(bundled_close):
    """The chart draws these as overlays, so they must share the index."""
    for bands in (strategies.turtle_bands(bundled_close, window=20),
                  strategies.moving_average_bands(bundled_close, 5, 20)):
        assert isinstance(bands, pd.DataFrame)
        assert len(bands) == len(bundled_close)
        assert len(bands.columns) >= 1


def test_short_series_does_not_crash():
    """The UI warns below 40 rows but still renders, so nothing may raise."""
    tiny = pd.Series([100.0, 101.0, 99.0, 102.0, 98.0])
    for signal in emitters(tiny).values():
        assert len(signal) == len(tiny)
