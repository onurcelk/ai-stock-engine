"""Signal generators for the rule-based agents.

Each strategy turns a price series into a signal series over the same
index, using the convention:

     1  -> buy
    -1  -> sell
     0  -> do nothing

Execution (money, inventory, fees) is deliberately not handled here — see
backtest.py — so strategies stay comparable and testable on their own.

Ported from agent/1.turtle-agent.ipynb, agent/2.moving-average-agent.ipynb
and agent/3.signal-rolling-agent.ipynb.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BUY, SELL, HOLD = 1, -1, 0


def turtle(close: pd.Series, window: int, follow_breakout: bool = False) -> pd.Series:
    """Breakout strategy against a rolling high/low channel.

    The original notebook *sells* when price breaks above the channel and
    *buys* when it breaks below — i.e. it fades the move (mean reversion).
    Real turtle trading does the opposite, so `follow_breakout` flips it.
    """
    signal = pd.Series(HOLD, index=close.index, dtype=float)

    rolling_max = close.shift(1).rolling(window).max()
    rolling_min = close.shift(1).rolling(window).min()

    broke_high = rolling_max < close
    broke_low = rolling_min > close

    if follow_breakout:
        signal[broke_high] = BUY
        signal[broke_low] = SELL
    else:
        signal[broke_high] = SELL
        signal[broke_low] = BUY
    return signal


def moving_average(close: pd.Series, short_window: int, long_window: int) -> pd.Series:
    """Classic MA crossover: signal only on the crossing itself."""
    short_ma = close.rolling(window=short_window, min_periods=1).mean()
    long_ma = close.rolling(window=long_window, min_periods=1).mean()

    above = pd.Series(0.0, index=close.index)
    above[short_window:] = np.where(short_ma[short_window:] > long_ma[short_window:], 1.0, 0.0)

    # diff() is +1 on a golden cross and -1 on a death cross.
    return above.diff().fillna(HOLD)


def signal_rolling(close: pd.Series, delay: int) -> pd.Series:
    """Momentum flip: act after `delay` consecutive moves against our state.

    State 1 means "holding"; state 0 means "flat". We only change our mind
    once the price has moved the other way `delay` times in a row.
    """
    prices = close.to_numpy()
    signal = np.full(len(prices), HOLD, dtype=float)

    signal[0] = BUY  # the notebook opens the position on day one
    state = 1
    pending = 0
    previous = prices[0]

    for i in range(1, len(prices)):
        if prices[i] < previous and state == 0:
            if pending < delay:
                pending += 1
            else:
                state, pending = 1, 0
                signal[i] = BUY
        elif prices[i] > previous and state == 1:
            if pending < delay:
                pending += 1
            else:
                state, pending = 0, 0
                signal[i] = SELL
        previous = prices[i]

    return pd.Series(signal, index=close.index)


def moving_average_bands(close: pd.Series, short_window: int, long_window: int) -> pd.DataFrame:
    """The two MA lines, for drawing them underneath the price."""
    return pd.DataFrame(
        {
            "short_ma": close.rolling(window=short_window, min_periods=1).mean(),
            "long_ma": close.rolling(window=long_window, min_periods=1).mean(),
        }
    )


def turtle_bands(close: pd.Series, window: int) -> pd.DataFrame:
    """The rolling channel, for drawing it underneath the price."""
    return pd.DataFrame(
        {
            "upper": close.shift(1).rolling(window).max(),
            "lower": close.shift(1).rolling(window).min(),
        }
    )
