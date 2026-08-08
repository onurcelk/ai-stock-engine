"""What the model is asked to predict: alpha, not direction (§1, §4, §5, §6).

Everything in this module reads bars *after* the cutoff, so it is scorer-side
by construction. Feature code must never import it. The one exception is
`rolling_beta`, which is estimated strictly on pre-cutoff bars and lives here
only because the residual target is the sole thing that consumes it — it takes
a `PriceView`, so it cannot see forward even if it wanted to.

The four rungs of §1:

* **A** absolute return — computed, reported, never the training target;
* **B** `alpha_5d = R_asset - R_SPY` — the primary target;
* **C** `R_asset - R_sector` — sector-relative, secondary;
* **D** `R_asset - β_m·R_SPY - β_s·R_sector⊥` — residual, later stage.

The sector leg is the leave-one-out equal-weighted mean of the *eligible index
members in that sector at that cutoff*, not a sector ETF. Point-in-time
membership makes the peer group move as the index does, and leaving the name
itself out stops a thin sector from being compared largely against itself.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import pitdata

HORIZON = 5                 # sessions — the §3 primary horizon
BETA_WINDOW = 252
BETA_MIN_OBS = 120
BETA_PRIOR = 1.0
BETA_PRIOR_SD = 0.5         # τ in the shrinkage weight τ²/(τ² + se²)
WINSOR = 0.01               # per-cutoff tails trimmed for the training target
EPS = 1e-8                  # the §7-8 denominator floor, in return units


@dataclasses.dataclass
class Outcome:
    """Realised outcomes for one cutoff. Produced only after predictions exist."""

    cutoff: pd.Timestamp
    horizon_end: pd.Timestamp
    frame: pd.DataFrame     # index=symbol, columns as below

    COLUMNS = ("asset_return", "spy_return", "sector_return",
               "alpha_5d", "sector_relative", "residual_alpha")


def _leave_one_out_mean(values: pd.Series, groups: pd.Series) -> pd.Series:
    """Group mean excluding each row itself. NaN for singleton groups."""
    frame = pd.DataFrame({"x": values, "g": groups}).dropna(subset=["x"])
    total = frame.groupby("g")["x"].transform("sum")
    count = frame.groupby("g")["x"].transform("count")
    loo = (total - frame["x"]) / (count - 1).where(count > 1)
    return loo.reindex(values.index)


def rolling_beta(view: pitdata.PriceView, symbols: list[str],
                 benchmark: pd.Series) -> pd.Series:
    """Shrunk market beta on a fixed rolling window ending at the cutoff (§1 correction).

    Fixed window, never expanding: an expanding window silently gives later
    cutoffs a different estimator from earlier ones, and the difference is not
    something the system would have known at the time.

    Shrinkage is Bayesian rather than ad hoc — the posterior weight on the
    sample estimate is `τ² / (τ² + se²)`, so a name with a noisy beta (short or
    illiquid history, exactly the §1 case) is pulled toward 1.0 in proportion to
    how badly it is measured, and a well-measured beta is left alone.
    """
    close = view.close[symbols].iloc[-(BETA_WINDOW + 1):]
    asset = close.pct_change().iloc[1:]
    market = benchmark.reindex(close.index).pct_change().iloc[1:]

    out: dict[str, float] = {}
    market_values = market.to_numpy(dtype=float)
    for symbol in symbols:
        y = asset[symbol].to_numpy(dtype=float)
        mask = np.isfinite(y) & np.isfinite(market_values)
        if mask.sum() < BETA_MIN_OBS:
            out[symbol] = BETA_PRIOR
            continue
        x, yy = market_values[mask], y[mask]
        var = x.var(ddof=1)
        if var < EPS:
            out[symbol] = BETA_PRIOR
            continue
        beta = float(np.cov(yy, x, ddof=1)[0, 1] / var)
        residual = yy - beta * (x - x.mean()) - yy.mean()
        dof = max(mask.sum() - 2, 1)
        se = float(np.sqrt(max(residual.var(ddof=1), 0.0) / (var * dof)))
        weight = BETA_PRIOR_SD ** 2 / (BETA_PRIOR_SD ** 2 + se ** 2)
        out[symbol] = weight * beta + (1 - weight) * BETA_PRIOR
    return pd.Series(out, dtype=float)


def sector_beta(view: pitdata.PriceView, symbols: list[str],
                sector_series: pd.DataFrame, sectors: pd.Series,
                benchmark: pd.Series) -> pd.Series:
    """Loading on the sector leg *after* the market leg is taken out.

    Regressing on SPY and the sector jointly would split shared variance
    arbitrarily between two heavily collinear regressors. Orthogonalising the
    sector against SPY first makes the two loadings answer separate questions:
    how much market, then how much sector-beyond-market.
    """
    window = view.close.index[-(BETA_WINDOW + 1):]
    market = benchmark.reindex(window).pct_change().iloc[1:]
    asset = view.close[symbols].reindex(window).pct_change().iloc[1:]
    market_values = market.to_numpy(dtype=float)

    out: dict[str, float] = {}
    for symbol in symbols:
        sector = sectors.get(symbol)
        series = sector_series.get(sector) if sector is not None else None
        if series is None:
            out[symbol] = 0.0
            continue
        s = series.reindex(window).pct_change().iloc[1:].to_numpy(dtype=float)
        y = asset[symbol].to_numpy(dtype=float)
        mask = np.isfinite(y) & np.isfinite(s) & np.isfinite(market_values)
        if mask.sum() < BETA_MIN_OBS:
            out[symbol] = 0.0
            continue
        x_m, x_s, yy = market_values[mask], s[mask], y[mask]
        var_m = x_m.var(ddof=1)
        if var_m < EPS:
            out[symbol] = 0.0
            continue
        load = np.cov(x_s, x_m, ddof=1)[0, 1] / var_m
        x_perp = x_s - load * x_m
        var_perp = x_perp.var(ddof=1)
        out[symbol] = float(np.cov(yy, x_perp, ddof=1)[0, 1] / var_perp) if var_perp > EPS else 0.0
    return pd.Series(out, dtype=float)


def sector_forward_returns(asset_returns: pd.Series, sectors: pd.Series) -> pd.Series:
    """Peer-group forward return per name: leave-one-out sector mean."""
    return _leave_one_out_mean(asset_returns, sectors.reindex(asset_returns.index))


def realise(book: pitdata.PriceBook, cutoff: pd.Timestamp, symbols: list[str],
            sectors: pd.Series, horizon: int = HORIZON,
            betas: pd.DataFrame | None = None) -> Outcome | None:
    """Reveal the outcome for one cutoff. SCORER SIDE — never call from features."""
    end = book.horizon_end(cutoff, horizon)
    if end is None:
        return None

    asset = book.forward_return(cutoff, horizon, symbols)
    spy = book.forward_return(cutoff, horizon, ["SPY"])
    if asset.empty or spy.empty or not np.isfinite(spy.get("SPY", np.nan)):
        return None
    spy_return = float(spy["SPY"])

    sector = sector_forward_returns(asset, sectors)
    frame = pd.DataFrame({
        "asset_return": asset,
        "spy_return": spy_return,
        "sector_return": sector,
    })
    frame["alpha_5d"] = frame["asset_return"] - frame["spy_return"]
    frame["sector_relative"] = frame["asset_return"] - frame["sector_return"]

    if betas is not None:
        beta_m = betas["beta_market"].reindex(frame.index)
        beta_s = betas["beta_sector"].reindex(frame.index)
        # The sector leg enters orthogonalised, matching how its beta was fitted.
        frame["residual_alpha"] = (frame["asset_return"]
                                   - beta_m * frame["spy_return"]
                                   - beta_s * (frame["sector_return"] - frame["spy_return"]))
    else:
        frame["residual_alpha"] = np.nan

    return Outcome(pd.Timestamp(cutoff).normalize(), end, frame)


def winsorise(values: pd.Series, tail: float = WINSOR) -> pd.Series:
    """Trim the per-cutoff tails of the *training* target only (§3 of the prereg).

    A single name up 60% on a takeover bid is a real outcome and belongs in the
    IC, which is rank-based and immune to it. It does not belong in a squared
    error, where it would buy more attention than the other 480 names combined.
    """
    finite = values.dropna()
    if len(finite) < 20:
        return values
    low, high = finite.quantile(tail), finite.quantile(1 - tail)
    return values.clip(lower=low, upper=high)


def cross_sectional_rank(values: pd.Series) -> pd.Series:
    """Percentile in [0, 1] within the cutoff — the §5 secondary target."""
    return values.rank(pct=True, na_option="keep")


def quintile(values: pd.Series) -> pd.Series:
    """1 (bottom) .. 5 (top) by cross-sectional rank, for the §16-17 spread."""
    ranks = cross_sectional_rank(values)
    return pd.cut(ranks, bins=[0, .2, .4, .6, .8, 1.0], labels=[1, 2, 3, 4, 5],
                  include_lowest=True).astype("float")


def volatility_scaled(alpha: pd.Series, pre_cutoff_vol: pd.Series) -> pd.Series:
    """The §6 / V2-F target. Denominator floored, per the §7-8 correction."""
    floor = max(float(pre_cutoff_vol.median(skipna=True) or 0.0) * 0.1, EPS)
    return alpha / pre_cutoff_vol.clip(lower=floor)
