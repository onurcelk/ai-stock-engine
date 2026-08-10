"""Layer 1 — the market environment at a cutoff, estimated without the stock.

Pre-registration §2.1. Everything here is a **frozen arithmetic composite of
columns that already exist** in the panel, all of which `alpha/features.py`
computed from a `PriceView` truncated at the cutoff. Nothing is fitted, nothing
is tuned, and nothing here is claimed to carry alpha.

Two deliberate restrictions, because a market-state layer is exactly where
degrees of freedom hide:

* **Only `(trend, vol)` is allowed to touch a scored baseline** — S4's
  conditional calibration, and nothing else. Every other field travels into the
  output object as context and is never selected on.
* `risk_score` is an unweighted mean of four terms that were written down before
  the first one was computed. It is a label for a reader, not a signal. If a
  later study wants it to be a signal it has to pre-register it as one.

The one quantity not lifted straight from a column is `dispersion_20d`, the
cross-sectional standard deviation of `ret_20d` on that date. It is computed
from the cutoff's own cross-section, which is pre-cutoff data by construction —
`ret_20d` is a trailing return.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

BULL = "BULL_TREND"
BEAR = "BEAR_TREND"
SIDEWAYS = "SIDEWAYS"
HIGH_VOL = "HIGH_VOL"

#: Panel columns Layer 1 reads. All are tier-3 context columns, constant within a cutoff.
CONTEXT_COLUMNS = ("vix_level", "vix_percentile", "index_breadth_above_sma50",
                   "index_advance_share", "mkt_spy_ret_20d", "mkt_spy_ret_60d")

DISPERSION_INPUT = "ret_20d"


@dataclasses.dataclass(frozen=True)
class MarketState:
    """One cutoff's environment. Carries no outcome and no forward-looking term."""

    cutoff: pd.Timestamp
    trend: str
    vol: str
    vix_level: float
    vix_percentile: float
    breadth_sma50: float
    advance_share: float
    spy_ret_20d: float
    spy_ret_60d: float
    dispersion_20d: float
    risk_score: float

    @property
    def bucket(self) -> tuple[str, str]:
        """The only part of Layer 1 that S4 is allowed to condition on (§2.1)."""
        return (self.trend, self.vol)

    @property
    def regime(self) -> str:
        """A single human-readable tag, e.g. `BULL_TREND/LOW_VOL`."""
        return f"{self.trend}/{self.vol}"

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "trend": self.trend,
            "vol": self.vol,
            "risk_score": _round(self.risk_score),
            "vix_percentile": _round(self.vix_percentile),
            "breadth_sma50": _round(self.breadth_sma50),
            "dispersion_20d": _round(self.dispersion_20d),
        }


def _round(value: float, digits: int = 6) -> float | None:
    value = float(value)
    return None if not np.isfinite(value) else round(value, digits)


def _scalar(block: pd.DataFrame, column: str) -> float:
    """A tier-3 column's single value for this cutoff.

    Context columns are broadcast across the cross-section, so every row carries
    the same number; the median is taken rather than `.iloc[0]` so that a single
    NaN row cannot decide the cutoff's state.
    """
    if column not in block.columns:
        return float("nan")
    return float(pd.to_numeric(block[column], errors="coerce").median(skipna=True))


def risk_score(trend: str, spy_ret_60d: float, breadth_sma50: float,
               vix_percentile: float) -> float:
    """The §2.1 composite: four terms in [0, 1], equally weighted, nothing fitted.

    Terms that cannot be computed are dropped rather than filled — an imputed
    breadth would be a silent bet on the missing value (CLAUDE.md §6.2). With no
    term available the score is NaN, and a NaN risk score is reported as absent.
    """
    terms = []
    if np.isfinite(spy_ret_60d):
        terms.append(1.0 if spy_ret_60d > 0 else 0.0)
    if np.isfinite(breadth_sma50):
        terms.append(float(np.clip(breadth_sma50, 0.0, 1.0)))
    if np.isfinite(vix_percentile):
        terms.append(float(np.clip(1.0 - vix_percentile, 0.0, 1.0)))
    terms.append(1.0 if trend == BULL else 0.0)
    return float(np.mean(terms)) if terms else float("nan")


def at(cutoff: pd.Timestamp, block: pd.DataFrame, regimes: pd.DataFrame) -> MarketState:
    """Layer 1 for one cutoff, from that cutoff's own cross-section.

    `block` is the panel rows at `cutoff` (index = symbol); `regimes` is the
    per-cutoff trend/vol frame the panel was built with. Neither can reach a bar
    after the cutoff: the regime tags came from `features.regime_state` on a
    truncated view, and every column read here is a trailing quantity.
    """
    cutoff = pd.Timestamp(cutoff)
    tags = regimes.loc[cutoff] if cutoff in regimes.index else pd.Series(dtype=object)
    trend = str(tags.get("trend", SIDEWAYS) or SIDEWAYS)
    vol = str(tags.get("vol", HIGH_VOL) or HIGH_VOL)

    values = {name: _scalar(block, name) for name in CONTEXT_COLUMNS}
    dispersion = float("nan")
    if DISPERSION_INPUT in block.columns:
        series = pd.to_numeric(block[DISPERSION_INPUT], errors="coerce").dropna()
        dispersion = float(series.std(ddof=1)) if len(series) > 2 else float("nan")

    return MarketState(
        cutoff=cutoff,
        trend=trend,
        vol=vol,
        vix_level=values["vix_level"],
        vix_percentile=values["vix_percentile"],
        breadth_sma50=values["index_breadth_above_sma50"],
        advance_share=values["index_advance_share"],
        spy_ret_20d=values["mkt_spy_ret_20d"],
        spy_ret_60d=values["mkt_spy_ret_60d"],
        dispersion_20d=dispersion,
        risk_score=risk_score(trend, values["mkt_spy_ret_60d"],
                              values["index_breadth_above_sma50"],
                              values["vix_percentile"]),
    )


def series(frame: pd.DataFrame, regimes: pd.DataFrame) -> dict[pd.Timestamp, MarketState]:
    """Layer 1 for every cutoff in a panel frame, keyed by cutoff."""
    out: dict[pd.Timestamp, MarketState] = {}
    for cutoff, block in frame.groupby(level=0):
        out[pd.Timestamp(cutoff)] = at(cutoff, block.droplevel(0), regimes)
    return out


def table(states: dict[pd.Timestamp, MarketState]) -> pd.DataFrame:
    """The states as a frame, for the report's regime-stability sections."""
    rows = [dataclasses.asdict(state) for state in states.values()]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("cutoff").sort_index()
