"""Build the (cutoff x symbol) panel: features from before T, outcomes from after.

The two halves are computed in separate passes on purpose. `feature_rows`
touches only `PriceView`s and cannot reach a future bar; `outcome_rows` calls
`book.forward_return` and does nothing else. They meet exactly once, in `build`,
by an index join — so a leak would have to be an outright index error rather
than a subtle boundary bug, and the leakage test in `app/tests/test_alpha.py`
would catch it.

The cutoff schedule is the §5 correction made concrete: cutoffs are spaced 5
sessions apart, which for a 5-session horizon makes consecutive outcome windows
exactly adjacent and non-overlapping. That is option (a) of §5 — the stronger
of the two, since it removes the overlap rather than correcting for it after
the fact. The block-bootstrap and Newey-West machinery in `stats.py` is then
applied *on top*, because non-overlap kills the mechanical autocorrelation but
not the market's own week-to-week persistence.
"""

from __future__ import annotations

import dataclasses
import time

import numpy as np
import pandas as pd

from . import features, membership, pitdata, targets, universe

HORIZON = targets.HORIZON
SPACING = 5                 # sessions between cutoffs — equals HORIZON, so no overlap
EMBARGO = 5                 # extra sessions purged between train and test
STUDY_START = "2016-01-04"

# The V1 exam paper (§19). Never used during development, evaluated once.
EXAM_CUTOFFS = [
    "2022-03-08", "2022-10-10", "2024-08-13", "2024-09-05", "2024-12-10",
    "2025-03-27", "2025-06-23", "2025-11-28", "2026-02-06", "2026-05-07",
    "2026-07-07", "2026-07-24",
]
# Development cutoffs this close to an exam date are dropped outright, so no
# development fit is ever warmed by a window abutting the exam.
EXAM_GUARD = HORIZON + EMBARGO


@dataclasses.dataclass
class Panel:
    """One tidy frame plus the bookkeeping every downstream stage needs."""

    frame: pd.DataFrame                 # MultiIndex (cutoff, symbol)
    feature_columns: list[str]
    regimes: pd.DataFrame               # cutoff -> trend, vol
    diagnostics: pd.DataFrame           # cutoff -> universe coverage counts

    @property
    def cutoffs(self) -> list[pd.Timestamp]:
        return sorted(self.frame.index.get_level_values(0).unique())

    def at(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        return self.frame.xs(pd.Timestamp(cutoff), level=0)

    def slice_cutoffs(self, keep: list[pd.Timestamp]) -> "Panel":
        wanted = pd.DatetimeIndex(sorted(set(pd.Timestamp(c) for c in keep)))
        mask = self.frame.index.get_level_values(0).isin(wanted)
        return Panel(self.frame[mask], self.feature_columns,
                     self.regimes.reindex(wanted).dropna(how="all"),
                     self.diagnostics.reindex(wanted).dropna(how="all"))


def schedule(book: pitdata.PriceBook, spacing: int = SPACING,
             start: str = STUDY_START, horizon: int = HORIZON) -> list[pd.Timestamp]:
    """Every `spacing`-th session from `start` that still has a full outcome ahead."""
    calendar = book.calendar
    begin = calendar.searchsorted(pd.Timestamp(start), side="left")
    last = len(calendar) - 1 - horizon
    return [calendar[i] for i in range(int(begin), last + 1, spacing)]


def split(cutoffs: list[pd.Timestamp], book: pitdata.PriceBook,
          guard: int = EXAM_GUARD) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    """Development and exam cutoffs, with the exam neighbourhood purged from dev."""
    calendar = book.calendar
    exam = [pitdata.align_to_calendar(calendar, pd.Timestamp(d)) for d in EXAM_CUTOFFS]
    exam_positions = [calendar.searchsorted(d) for d in exam]

    development = []
    for cutoff in cutoffs:
        position = calendar.searchsorted(cutoff)
        if any(abs(position - e) <= guard for e in exam_positions):
            continue
        development.append(cutoff)
    return development, sorted(set(exam))


def _feature_rows(book: pitdata.PriceBook, cutoff: pd.Timestamp,
                  tiers: tuple[str, ...], watchlist: set[str],
                  restrict_to: set[str] | None,
                  with_beta: bool) -> tuple[pd.DataFrame, dict, dict, pd.DataFrame | None]:
    """Everything knowable at `cutoff`. Reads a `PriceView` and nothing else."""
    eligible = universe.eligible_at(cutoff, book, restrict_to=restrict_to)
    if len(eligible.symbols) < 30:
        return pd.DataFrame(), {}, eligible.diagnostics, None

    view = book.view(cutoff)
    frame, regime = features.build(view, eligible.symbols, eligible.sectors,
                                   watchlist, tiers=tiers)
    frame["sector"] = eligible.sectors.reindex(frame.index).astype(object)
    frame["pre_vol_20d"] = features.pre_cutoff_volatility(view, eligible.symbols)

    betas = None
    if with_beta:
        panel = view.subset(eligible.symbols)
        sector_series = _sector_price_series(view, eligible)
        beta_market = targets.rolling_beta(panel, eligible.symbols, view.close["SPY"])
        beta_sector = targets.sector_beta(panel, eligible.symbols, sector_series,
                                          eligible.sectors, view.close["SPY"])
        betas = pd.DataFrame({"beta_market": beta_market, "beta_sector": beta_sector})
        frame["beta_market"] = beta_market
        frame["beta_sector"] = beta_sector

    return frame, regime, eligible.diagnostics, betas


def _sector_price_series(view: pitdata.PriceView, eligible: universe.Eligible) -> pd.DataFrame:
    """An equal-weighted price index per sector, from point-in-time members.

    Built from the cross-section rather than from a sector ETF so it inherits
    the as-of-cutoff membership: when a name joins or leaves the index, its
    sector's peer series changes with it, which a fixed ETF cannot do.
    """
    window = view.close.index[-(targets.BETA_WINDOW + 1):]
    out: dict[str, pd.Series] = {}
    for sector, names in eligible.by_sector().items():
        if sector == "UNKNOWN" or len(names) < 3:
            continue
        block = view.close[names].reindex(window)
        normalised = block / block.iloc[0]
        out[sector] = normalised.mean(axis=1, skipna=True)
    return pd.DataFrame(out)


def build(book: pitdata.PriceBook, cutoffs: list[pd.Timestamp],
          tiers: tuple[str, ...] = ("absolute",),
          restrict_to: set[str] | None = None,
          with_beta: bool = False, horizon: int = HORIZON,
          verbose: bool = True) -> Panel:
    """Features joined to outcomes, one row per (cutoff, symbol)."""
    watchlist = universe.watchlist_universe()
    rows, regimes, diagnostics = [], {}, {}
    started = time.time()

    for index, cutoff in enumerate(cutoffs):
        frame, regime, diagnostic, betas = _feature_rows(
            book, cutoff, tiers, watchlist, restrict_to, with_beta)
        diagnostics[cutoff] = diagnostic
        if frame.empty:
            continue
        regimes[cutoff] = regime

        symbols = list(frame.index)
        sectors = frame["sector"]
        outcome = targets.realise(book, cutoff, symbols, sectors,
                                  horizon=horizon, betas=betas)
        if outcome is None:
            continue

        joined = frame.join(outcome.frame, how="inner")
        joined = joined[joined["alpha_5d"].notna()]
        if len(joined) < 30:
            continue

        joined["target_train"] = targets.winsorise(joined["alpha_5d"])
        joined["target_rank"] = targets.cross_sectional_rank(joined["alpha_5d"])
        joined["target_vol_scaled"] = targets.volatility_scaled(
            joined["alpha_5d"], joined["pre_vol_20d"])
        joined["quintile"] = targets.quintile(joined["alpha_5d"])
        joined["horizon_end"] = outcome.horizon_end
        joined["cutoff"] = cutoff
        joined["symbol"] = joined.index
        rows.append(joined.reset_index(drop=True))

        if verbose and (index + 1) % 25 == 0:
            print(f"  {index + 1:4d}/{len(cutoffs)} cutoffs  "
                  f"({time.time() - started:.0f}s)", flush=True)

    if not rows:
        raise RuntimeError("no usable cutoffs — check the cache and the schedule")

    panel = pd.concat(rows, ignore_index=True).set_index(["cutoff", "symbol"]).sort_index()

    reserved = ("sector", "horizon_end", "asset_return", "spy_return", "sector_return",
                "alpha_5d", "sector_relative", "residual_alpha", "target_train",
                "target_rank", "target_vol_scaled", "quintile")
    feature_columns = [c for c in panel.columns if c not in reserved]

    regime_frame = pd.DataFrame(regimes).T if regimes else pd.DataFrame()
    diagnostic_frame = pd.DataFrame(
        {k: pd.Series(v) for k, v in diagnostics.items()}).T if diagnostics else pd.DataFrame()
    return Panel(panel, feature_columns, regime_frame, diagnostic_frame)


def training_cutoffs(panel_cutoffs: list[pd.Timestamp], test_cutoff: pd.Timestamp,
                     book: pitdata.PriceBook, horizon: int = HORIZON,
                     embargo: int = EMBARGO) -> list[pd.Timestamp]:
    """Cutoffs usable to train a model evaluated at `test_cutoff` (§19, §5).

    A training cutoff *T′* is admissible only when its outcome window has fully
    closed and an embargo has elapsed: `T′ + horizon + embargo <= T`. Without
    the horizon term the model would train on a label that had not happened yet
    at prediction time; without the embargo, adjacent windows would share the
    same few days of market noise, which is the time-series form of the
    "30 symbols on one date is not 30 draws" problem §5 warns about.
    """
    calendar = book.calendar
    limit = calendar.searchsorted(pd.Timestamp(test_cutoff)) - horizon - embargo
    if limit < 0:
        return []
    boundary = calendar[limit]
    return [c for c in panel_cutoffs if c <= boundary]
