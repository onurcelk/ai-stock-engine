"""The alpha feature pipeline (§7-12). Absolute *and* relative *and* percentile.

Directive §7-8 is explicit that relative-only is a guess, not a finding: every
family is emitted four ways — the raw value, the spread against SPY, the spread
against the point-in-time sector peer group, and the within-cutoff percentile —
and the model decides. Pre-removing the absolute version would be assuming the
answer to one of the questions the study exists to ask.

Three tiers, matching the §27 experiment ladder:

* `TIER_ABSOLUTE` — V2-A. Momentum, trend, oscillator, volume, volatility.
* `TIER_RELATIVE` — V2-B adds these on top. `__vs_spy`, `__vs_sector`, `__pct`.
* `TIER_CONTEXT`  — V2-E adds these. Market regime, VIX, breadth, and the
  overnight/intraday split of §9.

Everything is computed from a `PriceView`, which is truncated at the cutoff
before it is handed over, so no function here *can* read a future bar. The
matrices are kept wide (date x symbol) and every operation is vectorised across
the cross-section — a per-symbol loop over 500 names x 500 cutoffs would be
minutes of pandas overhead for arithmetic that takes milliseconds.

**Denominator discipline (§7-8 correction).** Every ratio in this file divides
by a floored denominator and no result is allowed through as ±inf. The
eligibility filter in `universe.py` already removes names under \$3M median
daily turnover, so the volume ratios never meet a near-zero denominator in
practice; `_safe_divide` is the belt to that pair of braces, and it is code
rather than a principle, which is what the correction asked for.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import pitdata

EPS = 1e-8

RETURN_WINDOWS = (1, 3, 5, 10, 20, 60)
SMA_WINDOWS = (20, 50, 200)
VOL_WINDOWS = (5, 20, 60)
RSI_PERIOD = 14
DEEPEST = 253                       # 12-1 momentum needs 252 sessions + one

# Families that get the full absolute / vs-SPY / vs-sector / percentile
# treatment. Volume is deliberately excluded from the SPY spread: "this stock
# traded 2x its average while SPY traded 1.1x its average" is a comparison of
# two unrelated liquidity regimes, not a signal.
RELATIVISED = ("ret_", "sma", "rsi", "rvol_")


def _safe_divide(numerator, denominator, floor: float = EPS):
    """Division with the §7-8 denominator guard, applied to frames or series."""
    safe = denominator.where(denominator.abs() > floor, np.nan)
    out = numerator / safe
    return out.replace([np.inf, -np.inf], np.nan)


def _returns_over(close: pd.DataFrame, window: int) -> pd.Series:
    if len(close) <= window:
        return pd.Series(np.nan, index=close.columns)
    return _safe_divide(close.iloc[-1], close.iloc[-1 - window]) - 1.0


def _rsi(close: pd.DataFrame, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder RSI, vectorised across the whole cross-section at once."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = _safe_divide(avg_gain, avg_loss)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    # A zero denominator here is not missing data: no down-days in the window is
    # RSI 100, and no movement at all is 50. Leaving both as NaN would quietly
    # drop the most extreme names from the cross-section.
    no_loss = avg_loss.abs() <= EPS
    no_gain = avg_gain.abs() <= EPS
    rsi = rsi.mask(no_loss & ~no_gain, 100.0).mask(no_loss & no_gain, 50.0)
    return rsi.iloc[-1]


def absolute_block(view: pitdata.PriceView) -> pd.DataFrame:
    """Tier 1 — the V2-A feature set. One row per symbol, one column per feature."""
    close = view.close.iloc[-DEEPEST:]
    volume = view.volume.reindex(columns=close.columns).iloc[-DEEPEST:]
    out: dict[str, pd.Series] = {}

    for window in RETURN_WINDOWS:
        out[f"ret_{window}d"] = _returns_over(close, window)

    # 12-1 momentum: the classic cross-sectional factor, which deliberately
    # skips the most recent month because that month is short-term reversal,
    # not momentum, and mixing the two cancels both.
    #
    # The guard is `>= DEEPEST` against the same constant the slice above uses.
    # It was `> 253` while the slice capped the frame at 253 rows, so it could
    # never fire: `ret_12_1` — and the three relative columns derived from it —
    # were identically NaN across the whole panel, and `mom_12_1` was a dead
    # entry among the six Model A′ baselines. Found by its n=0 in the A′ table
    # on the first development run; see EXPERIMENT_LOG.md.
    if len(close) >= DEEPEST:
        out["ret_12_1"] = _safe_divide(close.iloc[-22], close.iloc[-DEEPEST]) - 1.0
    else:
        out["ret_12_1"] = pd.Series(np.nan, index=close.columns)

    for window in SMA_WINDOWS:
        if len(close) >= window:
            sma = close.iloc[-window:].mean()
            out[f"sma{window}_dist"] = _safe_divide(close.iloc[-1], sma) - 1.0
        else:
            out[f"sma{window}_dist"] = pd.Series(np.nan, index=close.columns)

    out["rsi14"] = _rsi(close)

    daily = close.pct_change().replace([np.inf, -np.inf], np.nan)
    for window in VOL_WINDOWS:
        out[f"rvol_{window}d"] = daily.iloc[-window:].std(ddof=1) * np.sqrt(252.0)

    average_volume = volume.iloc[-20:].mean()
    out["volratio_20"] = _safe_divide(volume.iloc[-1], average_volume, floor=1.0)
    spread = volume.iloc[-20:].std(ddof=1)
    out["vol_surprise"] = _safe_divide(volume.iloc[-1] - average_volume, spread, floor=1.0)
    out["log_dollar_volume"] = np.log10((close.iloc[-1] * average_volume).clip(lower=1.0))

    frame = pd.DataFrame(out)
    return frame.replace([np.inf, -np.inf], np.nan)


def overnight_block(view: pitdata.PriceView) -> pd.DataFrame:
    """§9 — separate the overnight gap from the intraday session.

    V1 found its 4-hour signal was 77% overnight and inverted when read after
    the close. Splitting the two here is what lets V2 distinguish an
    overnight-driven name from an intraday-driven one instead of rediscovering
    the same confound from the other end.
    """
    close = view.close.iloc[-70:]
    open_ = view.open.reindex(columns=close.columns).iloc[-70:]

    overnight = _safe_divide(open_, close.shift(1)) - 1.0
    intraday = _safe_divide(close, open_) - 1.0

    out: dict[str, pd.Series] = {}
    for window in (5, 20, 60):
        out[f"overnight_mean_{window}d"] = overnight.iloc[-window:].mean()
        out[f"intraday_mean_{window}d"] = intraday.iloc[-window:].mean()
    out["overnight_share_60d"] = _safe_divide(
        overnight.iloc[-60:].abs().sum(),
        overnight.iloc[-60:].abs().sum() + intraday.iloc[-60:].abs().sum())
    out["overnight_last"] = overnight.iloc[-1]
    out["intraday_last"] = intraday.iloc[-1]
    return pd.DataFrame(out).replace([np.inf, -np.inf], np.nan)


def _sector_means(frame: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    """Leave-one-out sector mean of every column — the §12 peer group."""
    groups = sectors.reindex(frame.index)
    counts = frame.notna().groupby(groups).transform("sum")
    sums = frame.groupby(groups).transform("sum")
    loo = _safe_divide(sums - frame.fillna(0.0), (counts - frame.notna()).astype(float),
                       floor=0.5)
    return loo


def relative_block(absolute: pd.DataFrame, market: pd.Series,
                   sectors: pd.Series) -> pd.DataFrame:
    """Tier 2 — the V2-B additions. Market spread, sector spread, percentile.

    Absolute columns are *not* removed by this; the caller concatenates. §7-8:
    "do not pre-remove absolute features on the assumption relative is always
    better."
    """
    relativisable = [c for c in absolute.columns if c.startswith(RELATIVISED)]
    out: dict[str, pd.Series] = {}

    for column in relativisable:
        reference = market.get(column, np.nan)
        out[f"{column}__vs_spy"] = absolute[column] - reference

    sector_mean = _sector_means(absolute[relativisable], sectors)
    for column in relativisable:
        out[f"{column}__vs_sector"] = absolute[column] - sector_mean[column]

    # Percentiles over every absolute column, including the ones with no
    # meaningful market analogue (volume, dollar volume) — a rank is always
    # comparable even when a difference is not.
    for column in absolute.columns:
        out[f"{column}__pct"] = absolute[column].rank(pct=True, na_option="keep")

    return pd.DataFrame(out).replace([np.inf, -np.inf], np.nan)


def _series_features(view: pitdata.PriceView, symbol: str) -> pd.Series:
    """The absolute block for a single benchmark series, as a Series."""
    if symbol not in view.close.columns:
        return pd.Series(dtype=float)
    single = view.subset([symbol])
    return absolute_block(single).iloc[0]


def regime_state(spy: pd.Series, vix_level: float, vix_median: float) -> dict:
    """Deterministic, pre-cutoff regime tags (§10-11). No model, by design."""
    close = float(spy.iloc[-1])
    sma50 = float(spy.iloc[-50:].mean()) if len(spy) >= 50 else np.nan
    sma200 = float(spy.iloc[-200:].mean()) if len(spy) >= 200 else np.nan

    if np.isfinite(sma200) and np.isfinite(sma50):
        if close > sma200 and sma50 > sma200:
            trend = "BULL_TREND"
        elif close < sma200 and sma50 < sma200:
            trend = "BEAR_TREND"
        else:
            trend = "SIDEWAYS"
    else:
        trend = "SIDEWAYS"

    vol = "HIGH_VOL" if (np.isfinite(vix_level) and np.isfinite(vix_median)
                         and vix_level > vix_median) else "LOW_VOL"
    return {"trend": trend, "vol": vol}


def context_block(view: pitdata.PriceView, index_symbols: list[str],
                  watchlist: set[str]) -> tuple[dict, dict]:
    """Tier 3 — one value per cutoff, broadcast across the cross-section (§10-11).

    Returns `(features, regime)`. Breadth is emitted twice under two names, and
    the naming is the §11 correction rather than decoration: `index_breadth` is
    computed over the full point-in-time index cross-section and is real;
    `watchlist_breadth_proxy` is computed over the 22-name V1 list and is a
    proxy over an arbitrarily small, non-representative set. Nothing downstream
    is allowed to call the second one "breadth".
    """
    out: dict[str, float] = {}

    for symbol, prefix in (("SPY", "mkt_spy"), ("QQQ", "mkt_qqq")):
        block = _series_features(view, symbol)
        for key in ("ret_5d", "ret_20d", "ret_60d", "sma50_dist", "sma200_dist",
                    "rsi14", "rvol_20d"):
            out[f"{prefix}_{key}"] = float(block.get(key, np.nan))

    vix_level, vix_median, vix_pct, vix_change = np.nan, np.nan, np.nan, np.nan
    if "^VIX" in view.close.columns:
        vix = view.close["^VIX"].dropna()
        if len(vix) > 20:
            vix_level = float(vix.iloc[-1])
            trailing = vix.iloc[-252:]
            vix_median = float(trailing.median())
            vix_pct = float((trailing <= vix_level).mean())
            vix_change = float(vix.iloc[-1] / vix.iloc[-6] - 1.0) if len(vix) > 6 else np.nan
    out.update({"vix_level": vix_level, "vix_percentile": vix_pct,
                "vix_change_5d": vix_change})

    close = view.close
    present = [s for s in index_symbols if s in close.columns]
    if present:
        panel = close[present].iloc[-DEEPEST:]
        sma20 = panel.iloc[-20:].mean()
        above = (panel.iloc[-1] > sma20)
        out["index_breadth_above_sma20"] = float(above.mean(skipna=True))
        sma50 = panel.iloc[-50:].mean()
        out["index_breadth_above_sma50"] = float((panel.iloc[-1] > sma50).mean(skipna=True))
        daily = panel.pct_change().iloc[-1]
        out["index_advance_share"] = float((daily > 0).mean(skipna=True))

    proxy = [s for s in watchlist if s in close.columns]
    if proxy:
        panel = close[proxy].iloc[-60:]
        out["watchlist_breadth_proxy_above_sma20"] = float(
            (panel.iloc[-1] > panel.iloc[-20:].mean()).mean(skipna=True))
        out["watchlist_breadth_proxy_advance_share"] = float(
            (panel.pct_change().iloc[-1] > 0).mean(skipna=True))

    regime = regime_state(view.close["SPY"].dropna(), vix_level, vix_median)
    out["regime_bull"] = float(regime["trend"] == "BULL_TREND")
    out["regime_bear"] = float(regime["trend"] == "BEAR_TREND")
    out["regime_sideways"] = float(regime["trend"] == "SIDEWAYS")
    out["regime_high_vol"] = float(regime["vol"] == "HIGH_VOL")
    return out, regime


def build(view: pitdata.PriceView, symbols: list[str], sectors: pd.Series,
          watchlist: set[str], tiers: tuple[str, ...] = ("absolute",)) -> tuple[pd.DataFrame, dict]:
    """Assemble the requested tiers into one symbol-indexed frame.

    `tiers` is what makes the §27 ladder a configuration rather than three
    copies of this function: V2-A passes `("absolute",)`, V2-B adds
    `"relative"`, V2-E adds `"context"`.
    """
    panel = view.subset(symbols)
    absolute = absolute_block(panel)
    blocks = [absolute]
    regime: dict = {}

    if "relative" in tiers:
        market = _series_features(view, "SPY")
        blocks.append(relative_block(absolute, market, sectors))

    if "context" in tiers:
        blocks.append(overnight_block(panel))
        values, regime = context_block(view, symbols, watchlist)
        broadcast = pd.DataFrame(
            {k: np.full(len(absolute.index), v) for k, v in values.items()},
            index=absolute.index)
        blocks.append(broadcast)
    else:
        # The regime tag is needed for the §22 no-regime-collapse check even
        # when the regime *features* are not in the model, so derive it anyway.
        vix = view.close["^VIX"].dropna() if "^VIX" in view.close.columns else pd.Series(dtype=float)
        level = float(vix.iloc[-1]) if len(vix) else np.nan
        median = float(vix.iloc[-252:].median()) if len(vix) > 20 else np.nan
        regime = regime_state(view.close["SPY"].dropna(), level, median)

    frame = pd.concat(blocks, axis=1)
    frame = frame.replace([np.inf, -np.inf], np.nan)
    return frame, regime


def pre_cutoff_volatility(view: pitdata.PriceView, symbols: list[str]) -> pd.Series:
    """20-session realised vol at the cutoff — the V2-F denominator (§6)."""
    close = view.close[symbols].iloc[-21:]
    daily = close.pct_change().replace([np.inf, -np.inf], np.nan)
    return daily.std(ddof=1) * np.sqrt(252.0)
