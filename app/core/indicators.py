"""Technical evidence, every piece of it expressed on one scale.

Each *source* here turns a price frame into a series in [-1, +1]: the sign is
the direction it argues for, the magnitude is how hard it argues, and 0 means
it has no opinion on that bar. Nothing else about them is assumed to be
comparable — not their units, not their reputation, not their popularity.

That single convention is the whole point. Because every source speaks the
same language over the same index, `ultimate.py` can score all of them against
the same forward returns and weight them by *measured* skill. An indicator
that has never called this symbol correctly ends up weighted zero, and the
arithmetic works that out on its own rather than being told.

Two rules the sources follow:

- **Scale-free.** Readings are normalised by ATR or by rolling return
  volatility, never by raw price, so the same source reads the same way on a
  $3 stock and a $90,000 one, and on hourly bars as on weekly.
- **Fixed sign.** The standard interpretation of an indicator is baked in and
  the calibrator may only reduce a source's weight, never flip it. Letting the
  fit choose the sign would find an "edge" in any noise you handed it.

Pure pandas — no network, no TensorFlow, no state. A source needing a column
the frame lacks (volume, most often) returns zeros, which the calibrator reads
as "no opinion" and skips.
"""

from __future__ import annotations

import dataclasses
from typing import Callable

import numpy as np
import pandas as pd

# Families group sources that would otherwise double-count each other. Two
# trend followers agreeing is not two independent votes, and `ultimate.py`
# uses this to stop one family from carrying a verdict on its own.
TREND = "trend"
MOMENTUM = "momentum"
REVERSION = "reversion"
VOLUME = "volume"
STRUCTURE = "structure"
# Added 2026-08-24. Its own family rather than a REVERSION or MOMENTUM label:
# `ultimate.cap_families` stops one family carrying a verdict alone, and that
# only works if the grouping tracks what would actually double-count. An
# earnings surprise does not double-count a moving average — it is the one
# source here that is not a reading of the price at all.
FUNDAMENTAL = "fundamental"

SourceFn = Callable[[pd.DataFrame], pd.Series]


@dataclasses.dataclass(frozen=True)
class Source:
    """One named piece of evidence."""

    key: str
    name: str
    family: str
    describe: str
    fn: SourceFn

    def read(self, frame: pd.DataFrame) -> pd.Series:
        """Score the whole frame, guaranteed finite and inside [-1, 1]."""
        series = self.fn(frame)
        series = pd.Series(series, index=frame.index, dtype=float)
        return series.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-1.0, 1.0)


# ------------------------------------------------------------------ primitives


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def true_range(frame: pd.DataFrame) -> pd.Series:
    """High-low range including the overnight gap.

    Close-only series (the bundled CSVs, some FX files) have no high or low,
    so the absolute close-to-close move stands in. It understates the true
    range, but every source divides by it, so a consistent understatement
    only rescales the tanh input rather than changing any sign.
    """
    close = frame["close"]
    if "high" not in frame.columns or "low" not in frame.columns:
        return close.diff().abs()

    previous = close.shift(1)
    spans = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    )
    return spans.max(axis=1)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's average true range, floored so nothing divides by zero.

    The floor is a basis point of price rather than a constant: a flat penny
    stock and a flat index future both need a divisor proportional to what
    they cost.
    """
    smoothed = true_range(frame).ewm(alpha=1 / period, adjust=False,
                                     min_periods=period).mean()
    floor = frame["close"].abs() * 1e-4
    return smoothed.clip(lower=floor)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI. Returns NaN through the warm-up, not 50."""
    change = close.diff()
    gain = change.clip(lower=0.0)
    loss = -change.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    strength = avg_gain / avg_loss.replace(0.0, np.nan)
    result = 100 - 100 / (1 + strength)
    # avg_loss == 0 means an unbroken run of up bars: RSI 100 by definition.
    result = result.where(avg_loss != 0, 100.0)
    # Unless nothing moved at all, in which case both averages are zero and
    # the 100 above is a division by zero wearing a bullish hat — a flat line
    # is neutral, and reading it as maximum strength put a spurious +1 into
    # every verdict on a stale or halted series.
    return result.mask((avg_gain == 0) & (avg_loss == 0), 50.0).where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(close, fast) - ema(close, slow)
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, signal_line, line - signal_line


def bollinger(close: pd.Series, period: int = 20,
              deviations: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    middle = close.rolling(period).mean()
    spread = close.rolling(period).std(ddof=0)
    return middle, middle + deviations * spread, middle - deviations * spread


def donchian(frame: pd.DataFrame, period: int = 20) -> tuple[pd.Series, pd.Series]:
    """The rolling channel, excluding the current bar.

    Excluding it matters: a channel that includes today always contains
    today's price, so "price is at the top of its range" would be true on
    every new high by construction rather than as an observation.
    """
    high = frame["high"] if "high" in frame.columns else frame["close"]
    low = frame["low"] if "low" in frame.columns else frame["close"]
    return high.shift(1).rolling(period).max(), low.shift(1).rolling(period).min()


def directional_index(frame: pd.DataFrame,
                      period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ADX with its two directional components (Wilder).

    Close-only frames have no directional movement to measure, so this
    returns NaN for them and the source that uses it sits out.
    """
    if "high" not in frame.columns or "low" not in frame.columns:
        empty = pd.Series(np.nan, index=frame.index)
        return empty, empty.copy(), empty.copy()

    up = frame["high"].diff()
    down = -frame["low"].diff()
    plus = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=frame.index)
    minus = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=frame.index)

    alpha = 1 / period
    span = true_range(frame).ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    span = span.replace(0.0, np.nan)
    plus_di = 100 * plus.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / span
    minus_di = 100 * minus.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / span

    total = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / total
    adx = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    return adx, plus_di, minus_di


def on_balance_volume(frame: pd.DataFrame) -> pd.Series:
    """Cumulative volume signed by the day's direction."""
    if "volume" not in frame.columns:
        return pd.Series(np.nan, index=frame.index)
    volume = frame["volume"].fillna(0.0)
    if volume.abs().sum() == 0:
        return pd.Series(np.nan, index=frame.index)
    return (np.sign(frame["close"].diff().fillna(0.0)) * volume).cumsum()


def realised_volatility(close: pd.Series, period: int = 100) -> pd.Series:
    """Rolling standard deviation of returns, floored away from zero."""
    returns = close.pct_change()
    window = min(period, max(20, len(close) // 4)) if len(close) else period
    return returns.rolling(window, min_periods=max(10, window // 3)).std().clip(lower=1e-6)


def squash(series: pd.Series, scale: float = 1.0) -> pd.Series:
    """Map an unbounded reading onto [-1, 1].

    tanh rather than a hard clip so a source that is twice as stretched as
    usual still reads stronger than one that is merely stretched, instead of
    both pinning at 1 and losing the distinction.
    """
    return np.tanh(series.astype(float) / scale)


# --------------------------------------------------------------------- sources


def _trend_ma(frame: pd.DataFrame) -> pd.Series:
    """Fast EMA above slow EMA, measured in average true ranges."""
    close = frame["close"]
    gap = ema(close, 12) - ema(close, 48)
    return squash(gap / atr(frame, 14), scale=3.0)


def _trend_slope(frame: pd.DataFrame) -> pd.Series:
    """Which way the slow EMA is pointing, over 20 bars.

    Divided by ATR*sqrt(20) rather than ATR: a random walk drifts by roughly
    sqrt(n) ranges over n bars, so this asks whether the move is larger than
    drift, not merely larger than one bar.
    """
    baseline = ema(frame["close"], 50)
    move = baseline - baseline.shift(20)
    return squash(move / (atr(frame, 14) * np.sqrt(20)), scale=1.2)


def _macd_histogram(frame: pd.DataFrame) -> pd.Series:
    _, _, histogram = macd(frame["close"])
    return squash(histogram / atr(frame, 14), scale=0.9)


def _adx_direction(frame: pd.DataFrame) -> pd.Series:
    """Direction from +DI/-DI, amplitude from ADX.

    ADX below 20 is the conventional "no trend" reading, so it is subtracted
    off before scaling: a trendless market contributes nothing here instead of
    contributing a weak opinion.
    """
    adx, plus_di, minus_di = directional_index(frame, 14)
    strength = ((adx - 20.0) / 30.0).clip(lower=0.0, upper=1.0)
    spread = (plus_di - minus_di) / 40.0
    return (spread.clip(-1.0, 1.0) * strength)


def _rsi_momentum(frame: pd.DataFrame) -> pd.Series:
    """RSI as momentum: saturating at 75 and 25, not at 100 and 0."""
    return ((rsi(frame["close"], 14) - 50.0) / 25.0).clip(-1.0, 1.0)


def _rate_of_change(frame: pd.DataFrame) -> pd.Series:
    """Return over 20 bars, divided by what 20 bars of noise would produce."""
    close = frame["close"]
    move = close / close.shift(20) - 1.0
    expected = realised_volatility(close) * np.sqrt(20)
    return squash(move / expected, scale=1.5)


def _bollinger_reversion(frame: pd.DataFrame) -> pd.Series:
    """Distance from the 20-bar mean, argued *against*.

    The sign is deliberately opposite to the trend sources. When they and this
    one disagree, that disagreement is information the aggregate should carry,
    not something to hide by picking a house view.
    """
    close = frame["close"]
    middle, upper, _ = bollinger(close, 20, 2.0)
    spread = ((upper - middle) / 2.0).replace(0.0, np.nan)
    return squash(-(close - middle) / spread, scale=1.5)


def _donchian_position(frame: pd.DataFrame) -> pd.Series:
    """Where price sits in its 20-bar channel, weighted towards the edges.

    Cubed because the middle of a channel says nothing and the edges say
    everything; a linear reading would have the midpoint voting.
    """
    upper, lower = donchian(frame, 20)
    span = (upper - lower).replace(0.0, np.nan)
    position = (2 * (frame["close"] - lower) / span - 1).clip(-1.5, 1.5)
    return (position ** 3).clip(-1.0, 1.0)


def _volume_trend(frame: pd.DataFrame) -> pd.Series:
    """Whether on-balance volume is rising faster than it usually wanders."""
    obv = on_balance_volume(frame)
    if obv.isna().all():
        return pd.Series(0.0, index=frame.index)
    gap = ema(obv, 10) - ema(obv, 40)
    noise = obv.diff().abs().rolling(40, min_periods=15).mean().replace(0.0, np.nan)
    return squash(gap / (noise * np.sqrt(40)), scale=1.0)


def _vwap_reversion(frame: pd.DataFrame) -> pd.Series:
    """Distance from a 10-bar volume-weighted mean, argued against.

    `_bollinger_reversion`'s construction with VWAP swapped in for the simple
    moving average as the band's centre — the same window and the same
    "against the move" sign HT-2 froze in `ht2_vwap.py` before reading a
    forward return, restated here rather than imported because that module's
    source hash is not part of this one's version key.

    Measured and REJECTED as a standalone candidate (EXPERIMENT_REGISTRY §22).
    It sits here as one weighted voice among many, not as a claim that it
    works: an unskilled source is calibrated to zero weight by arithmetic.
    """
    if "volume" not in frame.columns:
        return pd.Series(0.0, index=frame.index)

    close = frame["close"]
    high = frame["high"] if "high" in frame.columns else close
    low = frame["low"] if "low" in frame.columns else close

    window = 10
    typical = (high + low + close) / 3.0
    volume = frame["volume"].fillna(0.0)
    turnover = volume.rolling(window).sum().replace(0.0, np.nan)
    vwap = (typical * volume).rolling(window).sum() / turnover

    spread = close.rolling(window).std(ddof=0).replace(0.0, np.nan)
    return squash(-(close - vwap) / spread, scale=1.5)


def _vix_reversion(frame: pd.DataFrame) -> pd.Series:
    """Williams' synthetic VIX, read as fear that mean-reverts.

    One-sided on purpose. The Vix Fix is a bottom finder: an elevated reading
    is capitulation and argues up, but a *low* reading is merely the absence
    of fear and the study has never claimed that predicts a fall. Inventing
    the short half would be asserting something nobody measured, so this
    source is silent — 0, no opinion — everywhere below its own threshold.

    Not `pine.vix_fix`, which HT-1 measured as a directional signal and placed
    among its worst (EXPERIMENT_REGISTRY §26 records the VIX1 reformulation's
    power gate failing at 0 slots). The construction is restated rather than
    imported for the same version-key reason as `_vwap_reversion`.
    """
    close = frame["close"]
    low = frame["low"] if "low" in frame.columns else close

    lookback = 22
    peak = close.rolling(lookback).max().replace(0.0, np.nan)
    fear = (peak - low) / peak * 100.0

    # Elevated against its *own* recent distribution, not an absolute level:
    # a 4% drawdown is capitulation on a utility and a Tuesday on a biotech.
    middle = fear.rolling(lookback).mean()
    spread = fear.rolling(lookback).std(ddof=0).replace(0.0, np.nan)
    return squash(((fear - middle) / spread - 2.0).clip(lower=0.0), scale=1.0)


def _opening_range(frame: pd.DataFrame) -> pd.Series:
    """Where price sits against the session's first bar, in average true ranges.

    Intraday only, and it works that out from the frame's own timestamps
    rather than being told: on a daily, weekly or monthly frame every session
    holds exactly one bar, so there is no range to break out of and this
    returns zeros — the same "no opinion" a close-only frame gets from the
    volume sources, for the same reason.

    Causal within the session. The range is fixed by the opening bar, so a bar
    at 14:00 is scored against something known at 10:00; the opening bar
    itself is scored 0 because it cannot break its own range.

    Measured and REJECTED standalone as `orb_1h` (EXPERIMENT_REGISTRY §24:
    +0.9 bp against a 39 bp hurdle, −4.1 bp net of costs).
    """
    if "date" not in frame.columns:
        return pd.Series(0.0, index=frame.index)

    stamps = pd.to_datetime(frame["date"], errors="coerce")
    if stamps.isna().all():
        return pd.Series(0.0, index=frame.index)

    session = stamps.dt.normalize()
    order = stamps.groupby(session).cumcount()
    if order.max() < 1:
        # One bar per calendar day: not an intraday frame.
        return pd.Series(0.0, index=frame.index)

    close = frame["close"]
    high = frame["high"] if "high" in frame.columns else close
    low = frame["low"] if "low" in frame.columns else close

    opening = order == 0
    range_high = high.where(opening).groupby(session).transform("max")
    range_low = low.where(opening).groupby(session).transform("min")

    beyond = pd.Series(
        np.where(close > range_high, close - range_high,
                 np.where(close < range_low, close - range_low, 0.0)),
        index=frame.index, dtype=float)
    return squash(beyond / atr(frame, 14), scale=1.0).where(~opening, 0.0)


#: How long post-earnings drift is read for, in calendar days. The
#: conventional PEAD window, and deliberately not fitted: no code in this
#: module reads a forward return, so there is nothing here to fit it against.
DRIFT_DAYS = 60.0


def _pead_drift(frame: pd.DataFrame) -> pd.Series:
    """Standardized earnings surprise, decaying over the weeks after the filing.

    The one source here that reads something other than the price. It needs
    `sue` and `days_since_filing`, which `filings_evidence.attach` puts on the
    frame from the EDGAR acceptance record; without them this is zeros — the
    same "no opinion" the volume sources give a close-only frame, and the
    reason this fits the source contract without bending it.

    Sign is the surprise's own. Magnitude decays linearly to nothing across
    `DRIFT_DAYS`, because the claim PEAD makes is about the weeks *after* an
    announcement, not about a firm's last earnings forever — without the decay
    a stale surprise would still be voting eleven months later.

    Measured and REJECTED (EXPERIMENT_REGISTRY §25): a real effect, but
    sub-threshold and substantially market-confounded, and §25 closes SUE
    permanently at every formulation tested. Present here as a weighted voice
    by owner decision, not as an accepted signal.
    """
    if "sue" not in frame.columns or "days_since_filing" not in frame.columns:
        return pd.Series(0.0, index=frame.index)

    sue = pd.to_numeric(frame["sue"], errors="coerce")
    age = pd.to_numeric(frame["days_since_filing"], errors="coerce")

    # A negative age would mean the filing is in the future relative to the
    # bar. `filings_evidence` cannot produce one, and if some other caller
    # supplied the columns by hand, silently trusting it is how a leak enters.
    fresh = (age >= 0) & (age <= DRIFT_DAYS)
    decay = (1.0 - age / DRIFT_DAYS).where(fresh, 0.0)

    return squash(sue, scale=2.0) * decay


def _market_structure(frame: pd.DataFrame) -> pd.Series:
    """Higher highs against lower lows over the last 20 bars.

    The one source here that reads the shape of the path rather than a
    smoothing of it, which is why it survives on frames where the moving
    averages all agree with each other.
    """
    high = frame["high"] if "high" in frame.columns else frame["close"]
    low = frame["low"] if "low" in frame.columns else frame["close"]
    window = 20
    higher = (high > high.shift(1)).rolling(window).sum()
    lower = (low < low.shift(1)).rolling(window).sum()
    return ((higher - lower) / (window * 0.5)).clip(-1.0, 1.0)


SOURCES: dict[str, Source] = {
    source.key: source
    for source in [
        Source("trend_ma", "EMA 12/48 spread", TREND,
               "Fast EMA above the slow one, in average true ranges.", _trend_ma),
        Source("trend_slope", "EMA 50 slope", TREND,
               "Direction of the 50-bar EMA over 20 bars, against random drift.",
               _trend_slope),
        Source("macd", "MACD histogram", MOMENTUM,
               "MACD minus its signal line, in average true ranges.", _macd_histogram),
        Source("adx", "ADX direction", TREND,
               "+DI against -DI, scaled by how trending ADX says the tape is.",
               _adx_direction),
        Source("rsi", "RSI 14", MOMENTUM,
               "Relative strength, saturating at 75 and 25.", _rsi_momentum),
        Source("roc", "20-bar return", MOMENTUM,
               "Move over 20 bars divided by 20 bars of typical noise.",
               _rate_of_change),
        Source("bollinger", "Bollinger reversion", REVERSION,
               "Stretch from the 20-bar mean, argued against.",
               _bollinger_reversion),
        Source("donchian", "Donchian position", TREND,
               "Where price sits in its 20-bar channel, weighted to the edges.",
               _donchian_position),
        Source("obv", "Volume trend", VOLUME,
               "On-balance volume rising faster than it usually wanders.",
               _volume_trend),
        Source("structure", "Market structure", STRUCTURE,
               "Higher highs against lower lows over 20 bars.", _market_structure),
        # Added 2026-08-24 by owner decision (reports/ENGINE_SOURCES_2026_08_24.md).
        # All three were measured standalone and rejected; they are entered as
        # weighted evidence, never as accepted signals, and the calibrator is
        # free to price them at zero.
        Source("vwap_reversion", "VWAP reversion", REVERSION,
               "Stretch from the 10-bar volume-weighted mean, argued against.",
               _vwap_reversion),
        Source("vix_reversion", "Vix Fix capitulation", REVERSION,
               "Synthetic VIX two deviations above its own mean. Long only — "
               "silent when fear is ordinary.", _vix_reversion),
        Source("opening_range", "Opening range break", TREND,
               "Break beyond the session's first bar, in average true ranges. "
               "Intraday frames only.", _opening_range),
        Source("pead", "Earnings drift", FUNDAMENTAL,
               "Standardized earnings surprise, decaying over the 60 days "
               "after the filing was accepted. Needs the EDGAR cache.",
               _pead_drift),
    ]
}

# The longest warm-up any source needs before its first honest reading (EMA 50
# sampled 20 bars back). Frames shorter than this produce all-zero scores, so
# `ultimate.py` refuses the horizon outright rather than calibrating on them.
WARMUP = 70


def read_all(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Every source scored over the frame, keyed by source id."""
    return {key: source.read(frame) for key, source in SOURCES.items()}


def stance(signal: pd.Series) -> pd.Series:
    """Turn a trading agent's buy/sell events into the position they imply.

    backtest.py's signal convention is an *event* series — ±1 on the bars where
    something happens, 0 everywhere else — so read literally, an agent has no
    opinion on 95% of bars, including almost always the last one. What it
    actually claims is a standing position: long from its last buy until its
    next sell. Forward-filling recovers that, which is the thing worth scoring
    and the thing worth reporting as "the turtle agent is currently long".
    """
    held = signal.replace(0.0, np.nan).ffill()
    return held.fillna(0.0).clip(-1.0, 1.0)
