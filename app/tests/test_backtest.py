"""The execution engine — including the number that guards it.

The canary below is the whole reason this file exists first: the turtle agent
on GOOG-year returns 3.6198% under the original notebook's conditions, and any
accidental change to how signals are executed moves it.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from core import backtest, strategies

CANARY_ROI = 3.6198


def turtle_signal(close: pd.Series) -> pd.Series:
    """The UI's default turtle configuration: a 10%-of-series channel."""
    return strategies.turtle(close, window=int(math.ceil(len(close) * 0.1)))


def test_turtle_canary(bundled, bundled_close):
    """Reproduces the original notebook's printed output exactly.

    Zero costs and fixed one-unit sizing are what the notebook assumed. If this
    drifts, something in backtest.run() changed meaning — do not update the
    constant without understanding why.
    """
    result = backtest.run(
        bundled_close, turtle_signal(bundled_close), bundled["date"],
        initial_money=10_000, max_buy=1, max_sell=1,
        fee_pct=0.0, slippage_pct=0.0, sizing=backtest.FIXED_UNITS,
    )
    assert result.roi_pct == pytest.approx(CANARY_ROI, abs=1e-4)


def test_costs_strictly_reduce_return(bundled, bundled_close):
    """Paying commission and slippage cannot leave you better off."""
    signal = turtle_signal(bundled_close)
    common = dict(initial_money=10_000, max_buy=1, max_sell=1,
                  sizing=backtest.FIXED_UNITS)
    free = backtest.run(bundled_close, signal, bundled["date"],
                        fee_pct=0.0, slippage_pct=0.0, **common)
    charged = backtest.run(bundled_close, signal, bundled["date"],
                           fee_pct=0.10, slippage_pct=0.05, **common)

    assert charged.roi_pct < free.roi_pct
    assert charged.fees_paid > 0
    assert free.fees_paid == 0


def test_all_in_tracks_buy_and_hold_on_a_rising_series(bundled):
    """A fully-invested always-buy policy should approach the benchmark.

    Fixed one-unit sizing deploys a sliver of capital against a fully invested
    benchmark, which is what made the repo's original agent numbers look bad.
    all_in is the fair comparison, so it should land close to buy & hold.
    """
    dates = pd.bdate_range("2020-01-01", periods=200)
    close = pd.Series(np.linspace(100.0, 200.0, len(dates)))
    signal = pd.Series(strategies.HOLD, index=close.index, dtype=float)
    signal.iloc[0] = strategies.BUY

    result = backtest.run(close, signal, pd.Series(dates), initial_money=10_000,
                          fee_pct=0.0, slippage_pct=0.0, sizing=backtest.ALL_IN)

    assert result.roi_pct == pytest.approx(result.buy_hold_roi_pct, rel=0.02)


def test_never_sells_more_than_it_bought(bundled, bundled_close):
    """Selling requires inventory; the engine must not go short."""
    # A signal that screams sell from the first bar.
    signal = pd.Series(strategies.SELL, index=bundled_close.index, dtype=float)
    result = backtest.run(bundled_close, signal, bundled["date"],
                          initial_money=10_000, sizing=backtest.FIXED_UNITS)

    assert len(result.sells) <= len(result.buys)
    assert result.final_value == pytest.approx(10_000)


def test_equity_curve_matches_series_length(bundled, bundled_close):
    result = backtest.run(bundled_close, turtle_signal(bundled_close),
                          bundled["date"], initial_money=10_000)
    assert len(result.equity) == len(bundled_close)
    assert not np.isnan(np.asarray(result.equity, dtype=float)).any()


def test_trade_table_is_renderable(bundled, bundled_close):
    """The UI puts this straight into st.dataframe."""
    result = backtest.run(bundled_close, turtle_signal(bundled_close),
                          bundled["date"], initial_money=10_000)
    table = backtest.trade_table(result)
    assert isinstance(table, pd.DataFrame)
    assert len(table) == len(result.trades)
