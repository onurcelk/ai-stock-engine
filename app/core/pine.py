"""TradingView indicators, ported from Pine Script to pandas.

These are the community indicators dropped into `agent/*.txt` — Williams Vix
Fix, LazyBear's Squeeze Momentum and WaveTrend, MavilimW, Supertrend, Leledc
exhaustion levels, and the High/Low Optimized Trend Tracker. Each one is a
faithful port: same defaults, same recursion, same quirks, so a line drawn here
lands where TradingView draws it.

**These are chart furniture, not evidence.** They are deliberately *not*
registered in `indicators.SOURCES`, and nothing here reaches `ultimate.py`, the
forecast ledger, or `model_registry`. That separation is load-bearing rather
than tidiness:

- `ultimate.evaluate` consumes `dict(indicators.SOURCES)` wholesale, so a source
  added there changes the live incumbent's evidence set while the ensemble's
  version — the sha256 of `ultimate.py` — stays put. The prospective record
  would silently split across two different models wearing one version string.
- Every `technical.*` model versions off `app.core.indicators`, so *any* edit to
  that file re-versions all ten of them and reads as drift against every
  forecast already frozen into the ledger.

Promoting any of these to weighted evidence therefore needs an owner decision
and a preregistration amendment, not an import. Until then they draw, and that
is all they do.

Two conventions worth stating, because they are where a Pine port usually goes
wrong:

- **Pine's smoothers seed with an SMA.** `ta.ema` and `ta.rma` are NaN until bar
  `length-1`, take the mean of that first window as their seed, and only then go
  recursive. `indicators.ema` seeds with the first value instead, which is the
  house convention there and is left alone — but it would put a visible offset
  into a chart meant to match TradingView, so this module implements Pine's
  version in `_seeded`.
- **Pine's `stdev` is a population standard deviation.** pandas defaults to the
  sample one, so every call here passes `ddof=0`.

There is exactly one deliberate departure from the source scripts, in HL OTT's
recursive averages, and `_adaptive_blend` documents why. Everything else that
looks odd — an unused `multiplier` in Squeeze Momentum, a two-bar lag on the
OTT bands — is odd in the original and is kept.

Pure pandas — no network, no state. Indicators that need columns the frame
lacks raise rather than guessing; `available` filters the catalogue for a frame
so the UI never offers one it cannot draw.
"""

from __future__ import annotations

import dataclasses
from typing import Callable

import numpy as np
import pandas as pd

from .indicators import true_range

#: Where an indicator belongs on the page. Overlays share the price axis;
#: oscillators are unit-less and need a pane of their own underneath.
OVERLAY = "overlay"
OSCILLATOR = "oscillator"

IndicatorFn = Callable[[pd.DataFrame], pd.DataFrame]


class MissingColumns(ValueError):
    """Raised when a frame lacks a column the indicator cannot do without."""


@dataclasses.dataclass(frozen=True)
class PineIndicator:
    """One ported indicator, with enough metadata for the UI to draw it."""

    key: str
    name: str
    pane: str
    describe: str
    requires: tuple[str, ...]
    fn: IndicatorFn
    #: The Pine script this was ported from, under `agent/`.
    source: str = ""
    #: Columns to draw as lines, in order. Everything else the function returns
    #: (booleans, markers, trend states) is for the caller to interpret.
    lines: tuple[str, ...] = ()
    #: Horizontal reference levels, for oscillators that have them.
    levels: tuple[float, ...] = ()

    def read(self, frame: pd.DataFrame) -> pd.DataFrame:
        _require(frame, self.requires, self.name)
        return self.fn(frame)


def _require(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise MissingColumns(
            f"{name} needs {', '.join(missing)}, which this series does not have"
        )


# ------------------------------------------------------------------ primitives


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def stdev(series: pd.Series, length: int) -> pd.Series:
    """Pine's `ta.stdev`: the population deviation, not the sample one."""
    return series.rolling(length).std(ddof=0)


def highest(series: pd.Series, length: int) -> pd.Series:
    """Rolling maximum *including* the current bar, as Pine's `ta.highest`."""
    return series.rolling(length).max()


def lowest(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).min()


def wma(series: pd.Series, length: int) -> pd.Series:
    """Linearly weighted average — weight `length` on the newest bar, 1 on the oldest."""
    weights = np.arange(1, length + 1, dtype=float)
    return series.rolling(length).apply(
        lambda window: np.dot(window, weights) / weights.sum(), raw=True
    )


def _seeded(series: pd.Series, length: int, alpha: float) -> pd.Series:
    """Pine's recursive smoothers: SMA seed at bar `length-1`, then alpha blend.

    Leading NaNs are skipped rather than poisoning the seed — an input that is
    itself a smoothing (WaveTrend's `d`, HL OTT's DEMA) arrives with a warm-up
    hole in front of it, and Pine starts counting from the first real value.
    NaNs appearing *after* the seed hold the previous value, which is what
    `nz(x[1])` does inside a recursive Pine assignment.
    """
    values = series.to_numpy(dtype=float)
    out = np.full(values.shape, np.nan)

    valid = np.flatnonzero(~np.isnan(values))
    if valid.size < length:
        return pd.Series(out, index=series.index)

    seed_at = valid[0] + length - 1
    if seed_at >= len(values):
        return pd.Series(out, index=series.index)

    out[seed_at] = np.nanmean(values[valid[0]:seed_at + 1])
    for i in range(seed_at + 1, len(values)):
        value = values[i]
        out[i] = out[i - 1] if np.isnan(value) else alpha * value + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=series.index)


def ema(series: pd.Series, length: int) -> pd.Series:
    """Pine's `ta.ema`. Not `indicators.ema` — see the module docstring."""
    return _seeded(series, length, 2.0 / (length + 1))


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's smoothing, Pine's `ta.rma`."""
    return _seeded(series, length, 1.0 / length)


def linreg(series: pd.Series, length: int, offset: int = 0) -> pd.Series:
    """Pine's `ta.linreg`: the least-squares line over `length` bars, read at `offset`.

    Offset counts backwards from the current bar, so 0 is the line's endpoint —
    the value the fit predicts for *now*, which is what Squeeze Momentum plots.
    """
    x = np.arange(length, dtype=float)
    centred = x - x.mean()
    denominator = float((centred ** 2).sum())

    def fit(window: np.ndarray) -> float:
        slope = float(np.dot(centred, window)) / denominator
        intercept = float(window.mean()) - slope * x.mean()
        return intercept + slope * (length - 1 - offset)

    return series.rolling(length).apply(fit, raw=True)


def hl2(frame: pd.DataFrame) -> pd.Series:
    return (frame["high"] + frame["low"]) / 2.0


def hlc3(frame: pd.DataFrame) -> pd.Series:
    return (frame["high"] + frame["low"] + frame["close"]) / 3.0


def atr(frame: pd.DataFrame, length: int) -> pd.Series:
    """Pine's `ta.atr` — Wilder-smoothed true range, unfloored.

    `indicators.atr` clips to a basis point of price because every source there
    divides by it. Supertrend multiplies instead, so the floor would only push
    its bands off TradingView's by a hair for no benefit.
    """
    return rma(true_range(frame), length)


# ------------------------------------------------------------------ indicators


def williams_vix_fix(
    frame: pd.DataFrame,
    period: int = 22,
    bb_length: int = 20,
    multiplier: float = 2.0,
    lookback: int = 50,
    high_percentile: float = 0.85,
    low_percentile: float = 1.01,
) -> pd.DataFrame:
    """CM_Williams_Vix_Fix — a synthetic VIX that spikes at capitulation lows.

    The reading is how far the low has fallen below the highest close of the
    last `period` bars, as a percentage of that high. It is a *bottom* finder:
    a tall bar means fear, and the flagged bars are the ones where fear cleared
    either its own Bollinger band or the `high_percentile` of its recent range.
    """
    close, low = frame["close"], frame["low"]
    top = highest(close, period)
    wvf = ((top - low) / top) * 100.0

    deviation = multiplier * stdev(wvf, bb_length)
    middle = sma(wvf, bb_length)
    range_high = highest(wvf, lookback) * high_percentile

    upper = middle + deviation
    return pd.DataFrame(
        {
            "wvf": wvf,
            "mid": middle,
            "upper_band": upper,
            "lower_band": middle - deviation,
            "range_high": range_high,
            "range_low": lowest(wvf, lookback) * low_percentile,
            # The original colours the histogram lime on this condition; it is
            # the only output of the study anyone trades off.
            "bottom": (wvf >= upper) | (wvf >= range_high),
        },
        index=frame.index,
    )


def squeeze_momentum(
    frame: pd.DataFrame,
    length: int = 20,
    multiplier: float = 2.0,
    kc_length: int = 20,
    kc_multiplier: float = 1.5,
    use_true_range: bool = True,
) -> pd.DataFrame:
    """LazyBear's Squeeze Momentum — Bollinger bands inside Keltner channels.

    A "squeeze" is volatility compressing: the Bollinger band narrower than the
    Keltner channel, which historically precedes an expansion. The histogram is
    the linear-regression endpoint of price against the midpoint of its own
    range, and its sign is the direction the release is leaning.

    `multiplier` is carried and unused, exactly as in the original — LazyBear's
    Bollinger deviation is scaled by the *Keltner* multiplier, and "fixing" that
    would put this histogram somewhere TradingView does not draw it.
    """
    del multiplier  # faithful to the original; see the docstring.
    close, high, low = frame["close"], frame["high"], frame["low"]

    basis = sma(close, length)
    deviation = kc_multiplier * stdev(close, length)
    upper_bb, lower_bb = basis + deviation, basis - deviation

    average = sma(close, kc_length)
    span = true_range(frame) if use_true_range else (high - low)
    span_ma = sma(span, kc_length)
    upper_kc = average + span_ma * kc_multiplier
    lower_kc = average - span_ma * kc_multiplier

    squeeze_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    squeeze_off = (lower_bb < lower_kc) & (upper_bb > upper_kc)

    midpoint = (highest(high, kc_length) + lowest(low, kc_length)) / 2.0
    baseline = (midpoint + sma(close, kc_length)) / 2.0
    momentum = linreg(close - baseline, kc_length, 0)

    return pd.DataFrame(
        {
            "momentum": momentum,
            "squeeze_on": squeeze_on,
            "squeeze_off": squeeze_off,
            "no_squeeze": ~squeeze_on & ~squeeze_off,
            # Four-state colouring: direction from the sign, shade from whether
            # the bar is still building or already fading.
            "rising": momentum > momentum.shift(1),
        },
        index=frame.index,
    )


def wavetrend(frame: pd.DataFrame, channel: int = 10, average: int = 21) -> pd.DataFrame:
    """LazyBear's WaveTrend — a smoothed, normalised distance from the mean.

    Typical price against its own EMA, divided by its average absolute
    deviation, then smoothed again. The 0.015 divisor is Lambert's CCI constant
    and puts the bulk of readings inside +/-100, which is what makes the fixed
    +/-60 and +/-53 levels mean anything.
    """
    price = hlc3(frame)
    baseline = ema(price, channel)
    deviation = ema((price - baseline).abs(), channel)
    # A dead-flat series has zero deviation; Pine yields infinity there, which
    # plots as a gap rather than a spike.
    index = (price - baseline) / (0.015 * deviation.replace(0.0, np.nan))

    wt1 = ema(index, average)
    wt2 = sma(wt1, 4)
    return pd.DataFrame(
        {"wt1": wt1, "wt2": wt2, "difference": wt1 - wt2}, index=frame.index
    )


def mavilim(frame: pd.DataFrame, first: int = 3, second: int = 5) -> pd.DataFrame:
    """MavilimW — six weighted averages stacked, with Fibonacci lengths.

    Each WMA smooths the one before it and the lengths grow as a Fibonacci
    series seeded by `first` and `second`, so the result lags heavily but turns
    cleanly. Colour, and the alerts in the original, come off the turn alone.
    """
    lengths = [first, second]
    while len(lengths) < 6:
        lengths.append(lengths[-1] + lengths[-2])

    line = frame["close"]
    for length in lengths:
        line = wma(line, length)

    return pd.DataFrame(
        {
            "mavw": line,
            "rising": line > line.shift(1),
            "turned_up": (line > line.shift(1)) & (line.shift(1) <= line.shift(2)),
            "turned_down": (line < line.shift(1)) & (line.shift(1) >= line.shift(2)),
        },
        index=frame.index,
    )


def supertrend(
    frame: pd.DataFrame,
    periods: int = 10,
    multiplier: float = 3.0,
    change_atr: bool = True,
) -> pd.DataFrame:
    """Supertrend — an ATR band that ratchets and only flips when price breaks it.

    The two stops tighten but never loosen while the trend holds, which is the
    whole mechanism: `up` may only rise while price is above it, `dn` may only
    fall while price is below. A flip needs the close through the *previous*
    bar's opposing stop, so the state cannot repaint.
    """
    source = hl2(frame)
    close = frame["close"]
    band = atr(frame, periods) if change_atr else sma(true_range(frame), periods)

    source_values = source.to_numpy(dtype=float)
    close_values = close.to_numpy(dtype=float)
    offset = (multiplier * band).to_numpy(dtype=float)

    count = len(frame)
    up = np.full(count, np.nan)
    down = np.full(count, np.nan)
    trend = np.ones(count)

    for i in range(count):
        raw_up = source_values[i] - offset[i]
        raw_down = source_values[i] + offset[i]

        previous_up = up[i - 1] if i and not np.isnan(up[i - 1]) else raw_up
        previous_down = down[i - 1] if i and not np.isnan(down[i - 1]) else raw_down

        if np.isnan(raw_up):
            # Still inside the ATR warm-up: no band to ratchet yet.
            up[i], down[i] = np.nan, np.nan
            trend[i] = trend[i - 1] if i else 1.0
            continue

        previous_close = close_values[i - 1] if i else np.nan
        up[i] = max(raw_up, previous_up) if previous_close > previous_up else raw_up
        down[i] = (min(raw_down, previous_down)
                   if previous_close < previous_down else raw_down)

        carried = trend[i - 1] if i else 1.0
        if carried == -1 and close_values[i] > previous_down:
            trend[i] = 1.0
        elif carried == 1 and close_values[i] < previous_up:
            trend[i] = -1.0
        else:
            trend[i] = carried

    trend_series = pd.Series(trend, index=frame.index)
    up_series = pd.Series(up, index=frame.index)
    down_series = pd.Series(down, index=frame.index)

    flipped = trend_series != trend_series.shift(1)
    return pd.DataFrame(
        {
            "up": up_series.where(trend_series == 1),
            "down": down_series.where(trend_series == -1),
            # One continuous line for charting: whichever stop is live.
            "supertrend": up_series.where(trend_series == 1, down_series),
            "trend": trend_series,
            "buy": flipped & (trend_series == 1),
            "sell": flipped & (trend_series == -1),
        },
        index=frame.index,
    )


def leledc(frame: pd.DataFrame, bars: int = 10, length: int = 40) -> pd.DataFrame:
    """Leledc exhaustion bars and the support/resistance they leave behind.

    Counts how long price has been pushing one way against its value four bars
    back. Once that count clears `bars` *and* the bar closes against itself at
    a `length`-bar extreme, the push is called exhausted, the counter resets,
    and the bar's high or low is held as a level until the next exhaustion.
    """
    close = frame["close"].to_numpy(dtype=float)
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)

    highest_high = highest(frame["high"], length).to_numpy(dtype=float)
    lowest_low = lowest(frame["low"], length).to_numpy(dtype=float)

    count = len(frame)
    exhaustion = np.zeros(count)
    buy_index = sell_index = 0

    for i in range(count):
        if i >= 4:
            if close[i] > close[i - 4]:
                buy_index += 1
            if close[i] < close[i - 4]:
                sell_index += 1

        if buy_index > bars and close[i] < open_[i] and high[i] >= highest_high[i]:
            buy_index = 0
            exhaustion[i] = -1.0
        elif sell_index > bars and close[i] > open_[i] and low[i] <= lowest_low[i]:
            sell_index = 0
            exhaustion[i] = 1.0

    exhaustion_series = pd.Series(exhaustion, index=frame.index)
    bearish = exhaustion_series == -1
    bullish = exhaustion_series == 1

    resistance = frame["high"].where(bearish).ffill()
    support = frame["low"].where(bullish).ffill()

    return pd.DataFrame(
        {
            "exhaustion": exhaustion_series,
            "resistance": resistance,
            "support": support,
            "top": frame["high"].where(bearish),
            "bottom": frame["low"].where(bullish),
        },
        index=frame.index,
    )


#: The moving averages HL OTT offers. VAR is its default and the reason the
#: indicator exists — a CMO-scaled EMA that speeds up when the move is one-sided.
OTT_MA_TYPES = ("SMA", "EMA", "WMA", "DEMA", "TMA", "VAR", "WWMA", "ZLEMA", "TSF", "HULL")


def _var_ma(series: pd.Series, length: int) -> pd.Series:
    """Vidya-style adaptive EMA: alpha scaled by the Chande momentum oscillator.

    Seeded at the first real value rather than at zero — see `_adaptive_blend`.
    """
    alpha = 2.0 / (length + 1)
    change = series.diff()
    up = change.clip(lower=0.0)
    down = (-change).clip(lower=0.0)

    total_up = up.rolling(9).sum()
    total_down = down.rolling(9).sum()
    spread = (total_up + total_down).replace(0.0, np.nan)
    cmo = ((total_up - total_down) / spread).fillna(0.0)

    values = series.to_numpy(dtype=float)
    factor = (alpha * cmo.abs()).to_numpy(dtype=float)
    return _adaptive_blend(values, factor, series.index)


def _wwma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's average, seeded at the first real value rather than at zero."""
    values = series.to_numpy(dtype=float)
    factor = np.full(len(values), 1.0 / length)
    return _adaptive_blend(values, factor, series.index)


# Both recursive averages above are written in Pine as `x := nz(a*src) +
# (1-a)*nz(x[1])`, which makes bar zero *zero* — the line then climbs out of the
# floor over the next several bars. On TradingView that artefact sits far off
# the left edge and nobody sees it; on a 260-bar frame it is a spike from 0 to
# 100 that flattens the price axis. Seeding at the first real value instead is
# the one deliberate deviation from the source scripts. The recursion converges
# exponentially, so the two agree to floating point within a couple of dozen
# bars, and it is the warm-up — where Pine is simply wrong — that differs.
def _adaptive_blend(values: np.ndarray, factor: np.ndarray, index: pd.Index) -> pd.Series:
    """`out = f*x + (1-f)*out[-1]`, held through NaNs and seeded, not floored."""
    out = np.full(values.shape, np.nan)
    previous = np.nan

    for i, value in enumerate(values):
        if np.isnan(value):
            out[i] = previous
            continue
        if np.isnan(previous):
            previous = value  # the seed, in place of Pine's implicit zero
        weight = 0.0 if np.isnan(factor[i]) else factor[i]
        out[i] = weight * value + (1 - weight) * previous
        previous = out[i]
    return pd.Series(out, index=index)


def _ott_ma(series: pd.Series, length: int, kind: str) -> pd.Series:
    if kind == "SMA":
        return sma(series, length)
    if kind == "EMA":
        return ema(series, length)
    if kind == "WMA":
        return wma(series, length)
    if kind == "DEMA":
        return 2 * ema(series, length) - ema(ema(series, length), length)
    if kind == "TMA":
        return sma(sma(series, int(np.ceil(length / 2))), int(np.floor(length / 2)) + 1)
    if kind == "VAR":
        return _var_ma(series, length)
    if kind == "WWMA":
        return _wwma(series, length)
    if kind == "ZLEMA":
        lag = length // 2
        return ema(series + series - series.shift(lag), length)
    if kind == "TSF":
        # The regression endpoint plus one step of its own slope.
        return 2 * linreg(series, length, 0) - linreg(series, length, 1)
    if kind == "HULL":
        half = max(int(round(length / 2)), 1)
        root = max(int(round(np.sqrt(length))), 1)
        return wma(2 * wma(series, half) - wma(series, length), root)
    raise ValueError(f"unknown moving average {kind!r}; expected one of {OTT_MA_TYPES}")


def _ott_line(source: pd.Series, length: int, percent: float, kind: str) -> pd.Series:
    """One OTT band: a ratcheting stop around a moving average, then widened.

    Identical in shape to Supertrend's mechanism, but the band is a percentage
    of the average rather than a multiple of ATR, and the final line is nudged
    another half-percent clear of the stop it flipped on.
    """
    average = _ott_ma(source, length, kind)
    values = average.to_numpy(dtype=float)
    offset = values * percent * 0.01

    count = len(values)
    result = np.full(count, np.nan)
    warming = source.isna().to_numpy()
    long_stop = short_stop = np.nan
    direction = 1.0

    for i in range(count):
        if np.isnan(values[i]) or warming[i]:
            # No rolling high/low yet, so there is no band to draw. Pine emits
            # zero here; a gap is the honest rendering of "not yet".
            continue

        raw_long = values[i] - offset[i]
        raw_short = values[i] + offset[i]

        previous_long = raw_long if np.isnan(long_stop) else long_stop
        previous_short = raw_short if np.isnan(short_stop) else short_stop

        long_stop = max(raw_long, previous_long) if values[i] > previous_long else raw_long
        short_stop = (min(raw_short, previous_short)
                      if values[i] < previous_short else raw_short)

        if direction == -1 and values[i] > previous_short:
            direction = 1.0
        elif direction == 1 and values[i] < previous_long:
            direction = -1.0

        stop = long_stop if direction == 1 else short_stop
        result[i] = stop * (200 + percent) / 200 if values[i] > stop \
            else stop * (200 - percent) / 200

    return pd.Series(result, index=source.index)


def hl_ott(
    frame: pd.DataFrame,
    length: int = 2,
    percent: float = 0.6,
    hl_length: int = 10,
    ma_type: str = "VAR",
) -> pd.DataFrame:
    """High/Low Optimized Trend Tracker — two OTT bands, one per side of the range.

    The upper band tracks the rolling high and the lower band the rolling low,
    giving a corridor rather than a single stop. Price above the upper band is
    the buy state, below the lower band the sell state, and inside the corridor
    is deliberately no state at all.

    Both bands are published shifted two bars, because that is how the study
    plots them — `nz(HOTT[2])`. The unshifted lines are returned alongside so
    the lag is visible rather than baked in silently.
    """
    if ma_type not in OTT_MA_TYPES:
        raise ValueError(
            f"unknown moving average {ma_type!r}; expected one of {OTT_MA_TYPES}")

    upper_source = highest(frame["high"], hl_length)
    lower_source = lowest(frame["low"], hl_length)

    hott_raw = _ott_line(upper_source, length, percent, ma_type)
    lott_raw = _ott_line(lower_source, length, percent, ma_type)

    hott, lott = hott_raw.shift(2), lott_raw.shift(2)
    close = frame["close"]

    return pd.DataFrame(
        {
            "hott": hott,
            "lott": lott,
            "hott_raw": hott_raw,
            "lott_raw": lott_raw,
            "state": np.select([close > hott, close < lott], [1.0, -1.0], default=0.0),
            "buy": (close > hott) & (close.shift(1) <= hott.shift(1)),
            "sell": (close < lott) & (close.shift(1) >= lott.shift(1)),
        },
        index=frame.index,
    )


# --------------------------------------------------------------------- catalogue


INDICATORS: dict[str, PineIndicator] = {
    indicator.key: indicator
    for indicator in [
        PineIndicator(
            "supertrend", "Supertrend", OVERLAY,
            "ATR band that ratchets one way and flips only when price breaks it.",
            ("high", "low", "close"), supertrend, source="super trend.txt",
            lines=("supertrend",),
        ),
        PineIndicator(
            "mavilim", "MavilimW", OVERLAY,
            "Six weighted averages stacked over Fibonacci lengths.",
            ("close",), mavilim, source="mavilim.txt", lines=("mavw",),
        ),
        PineIndicator(
            "hl_ott", "HL Optimized Trend Tracker", OVERLAY,
            "A corridor of two ratcheting bands, one on the rolling high and "
            "one on the rolling low.",
            ("high", "low", "close"), hl_ott,
            source="high low optimized trend tracker.txt",
            lines=("hott", "lott"),
        ),
        PineIndicator(
            "leledc", "Leledc exhaustion levels", OVERLAY,
            "Support and resistance left behind by exhausted pushes.",
            ("open", "high", "low", "close"), leledc,
            source="leledc levels.txt", lines=("resistance", "support"),
        ),
        PineIndicator(
            "wavetrend", "WaveTrend", OSCILLATOR,
            "Smoothed, normalised distance from the mean, with fixed "
            "overbought and oversold levels.",
            ("high", "low", "close"), wavetrend,
            source="WaveTrend Oscillator.txt", lines=("wt1", "wt2"),
            levels=(60.0, 53.0, 0.0, -53.0, -60.0),
        ),
        PineIndicator(
            "squeeze", "Squeeze Momentum", OSCILLATOR,
            "Bollinger bands compressing inside Keltner channels, with the "
            "direction the release is leaning.",
            ("high", "low", "close"), squeeze_momentum,
            source="Squeeze Momentum Indicator.txt", lines=("momentum",),
            levels=(0.0,),
        ),
        PineIndicator(
            "vix_fix", "Williams Vix Fix", OSCILLATOR,
            "A synthetic VIX that spikes at capitulation lows.",
            ("low", "close"), williams_vix_fix,
            source="Fix Finds Market Bottoms.txt",
            lines=("wvf", "upper_band", "range_high"),
        ),
    ]
}


# ----------------------------------------------------------------- as agents

# `backtest.run` takes an *event* series: +1 on the bars where a position is
# opened, -1 where it is closed, 0 elsewhere. Same convention as strategies.py,
# restated here rather than imported — editing that module would re-version the
# three registered `rule_agent.*` models against the live ledger.
BUY, SELL, HOLD = 1, -1, 0

#: The trading rule each study implies, in the words its author would use.
#: Four of the seven publish their own signal and those are quoted as-is. The
#: three oscillators are read the conventional way, and where a study has no
#: exit at all — the Vix Fix is a bottom finder, it never says when to leave —
#: the exit is stated here as an addition rather than smuggled in as if the
#: original had one.
SIGNAL_RULES: dict[str, str] = {
    "supertrend": "Buy when the trend flips up, sell when it flips down. The "
                  "study's own buy/sell markers.",
    "hl_ott": "Buy when the close crosses above the upper band, sell when it "
              "crosses below the lower one. The study's own alert conditions.",
    "mavilim": "Buy when the line turns up, sell when it turns down — the "
               "study's own colour-change alerts.",
    "leledc": "Buy a bullish exhaustion bar, sell a bearish one.",
    "wavetrend": "Buy when WT1 crosses above WT2 while oversold (below -53), "
                 "sell when it crosses below while overbought (above +53). The "
                 "conventional reading; the study itself only draws the levels.",
    "squeeze": "Buy when a squeeze releases with positive momentum, sell when "
               "it releases negative. The release is the signal, not the squeeze.",
    "vix_fix": "Buy a flagged capitulation bar. The study has no exit, so one "
               "is added here: leave when the reading falls back under its own "
               "20-bar mean.",
}


def _events(buy: pd.Series, sell: pd.Series, index: pd.Index) -> pd.Series:
    """Fold two boolean masks into the backtester's event series."""
    buy = buy.fillna(False).to_numpy(dtype=bool)
    sell = sell.fillna(False).to_numpy(dtype=bool)
    # Buy wins a same-bar tie. The alternative is to emit nothing, which loses
    # a real entry to a coincidence that these rules make very rare.
    return pd.Series(np.select([buy, sell], [BUY, SELL], default=HOLD),
                     index=index, dtype=float)


def _crosses(fast: pd.Series, slow: pd.Series) -> tuple[pd.Series, pd.Series]:
    """The two crossing masks: fast up through slow, and fast down through it."""
    above = fast > slow
    was_above = above.shift(1, fill_value=False)
    return above & ~was_above, ~above & was_above


def signals(key: str, frame: pd.DataFrame) -> pd.Series:
    """The study's trading rule as a buy/sell event series.

    This is what makes the ports runnable on the agents tab: the same backtester
    that scores the turtle and the RL policies scores these, against the same
    buy-and-hold benchmark. `SIGNAL_RULES[key]` states the rule in words.
    """
    if key not in INDICATORS:
        raise KeyError(f"no ported study {key!r}; expected one of {sorted(INDICATORS)}")

    output = INDICATORS[key].read(frame)

    if key in {"supertrend", "hl_ott"}:
        return _events(output["buy"], output["sell"], frame.index)

    if key == "mavilim":
        return _events(output["turned_up"], output["turned_down"], frame.index)

    if key == "leledc":
        return _events(output["exhaustion"] == 1, output["exhaustion"] == -1, frame.index)

    if key == "wavetrend":
        up, down = _crosses(output["wt1"], output["wt2"])
        return _events(up & (output["wt2"] < -53), down & (output["wt2"] > 53), frame.index)

    if key == "squeeze":
        released = output["squeeze_on"].shift(1, fill_value=False) & ~output["squeeze_on"]
        momentum = output["momentum"]
        return _events(released & (momentum > 0), released & (momentum < 0), frame.index)

    # vix_fix: a rising edge on the capitulation flag, and the added exit.
    flagged = output["bottom"]
    entry = flagged & ~flagged.shift(1, fill_value=False)
    _, cooled = _crosses(output["wvf"], output["mid"])
    return _events(entry, cooled, frame.index)


def bands(key: str, frame: pd.DataFrame) -> pd.DataFrame | None:
    """The study's overlay lines, for drawing underneath the backtest.

    Oscillators have nothing that belongs on a price axis, so they return None
    and the chart is left as candles plus the trade markers.
    """
    indicator = INDICATORS[key]
    if indicator.pane != OVERLAY:
        return None
    return indicator.read(frame)[list(indicator.lines)]


def available(frame: pd.DataFrame) -> dict[str, PineIndicator]:
    """The subset of the catalogue this frame has the columns to draw.

    Close-only series (several of the bundled CSVs) can support none of these,
    which is a fact about the data rather than a failure — the UI offers what
    is left and says so.
    """
    return {
        key: indicator
        for key, indicator in INDICATORS.items()
        if set(indicator.requires).issubset(frame.columns)
    }


def read_all(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Every drawable indicator computed over the frame, keyed by id."""
    return {key: indicator.read(frame) for key, indicator in available(frame).items()}
