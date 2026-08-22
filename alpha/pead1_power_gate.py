"""PEAD-1 power gate — alpha/PEAD1_CHARTER.md SS6. Half-width only, no point estimate.

Computes whether this history can resolve an event-time SUE effect at the
39 bp hurdle (Single-Name Phase 1's covered-book resolution), for each of the
three candidate windows named in the charter (5/20/60 sessions), **before any
predictive quantity is read**.

The discipline follows `reports/V5_HISTORICAL_REPLAY.md`'s own precedent
("the paired series was centred immediately, and a percentile bootstrap's
width is invariant to centring") and `alpha/V4_CHARTER.md` SS6.1 item 2 ("the
gate is permitted to touch variance and dependence structure... not permitted
to compute, report or inspect the point estimate"): the per-event advantage
series is computed (unavoidable, since variance is a property of the data),
immediately centred on its own mean, and only the centred series's bootstrap
half-width is ever printed or written to a file. The raw mean is held in a
local variable, never logged, never returned.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import numpy as np
import pandas as pd

from . import filings_features, stats

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
CACHE_DIR = pathlib.Path(__file__).resolve().parent / "cache"
CONCEPT = "NetIncomeLoss"
WINDOWS = (5, 20, 60)
MDE_BP = 39.0                       # Single-Name Phase 1's covered-book resolution (SN1)


@dataclasses.dataclass(frozen=True)
class GateResult:
    window: int
    n_events: int
    n_weeks: int
    block_weeks: int
    half_width_bp: float
    mde_bp: float

    @property
    def passes(self) -> bool:
        return self.half_width_bp <= self.mde_bp


def _load_events() -> dict[str, filings_features.FirmEvents]:
    meta = json.loads((EDGAR_DIR / "filings_meta.json").read_text())
    symbol_to_cik: dict[str, int] = meta["symbol_to_cik"]
    facts = pd.read_parquet(EDGAR_DIR / "facts.parquet")
    concept_rows = facts[facts["concept"] == CONCEPT]
    by_cik = {cik: rows for cik, rows in concept_rows.groupby("cik")}

    events: dict[str, filings_features.FirmEvents] = {}
    for symbol, cik in symbol_to_cik.items():
        if not (CACHE_DIR / f"{symbol}.csv").exists():
            continue
        rows = by_cik.get(cik)
        if rows is None or rows.empty:
            continue
        firm_events = filings_features.replay(rows)
        if len(firm_events.valid_from):
            events[symbol] = firm_events
    return events


def _load_price(symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(CACHE_DIR / f"{symbol}.csv")
    frame["date"] = pd.to_datetime(frame["Date"] if "Date" in frame.columns
                                    else frame["date"], errors="raise", utc=True)
    close_col = "Close" if "Close" in frame.columns else "close"
    frame = frame[["date", close_col]].rename(columns={close_col: "close"})
    frame = frame.dropna().sort_values("date").reset_index(drop=True)
    return frame


def _event_advantage_rows(events: dict[str, filings_features.FirmEvents]) -> pd.DataFrame:
    """One row per (symbol, event, window): the raw, SUE-sign-weighted forward
    return. Not centred yet -- this function's output must never be printed
    or written to a file as-is; `gate()` consumes it and discards it.
    """
    rows: list[dict] = []
    prices: dict[str, pd.DataFrame] = {}
    for symbol, firm_events in events.items():
        if symbol not in prices:
            try:
                prices[symbol] = _load_price(symbol)
            except FileNotFoundError:
                continue
        price = prices[symbol]
        dates = price["date"]
        closes = price["close"].to_numpy()
        total = len(price)

        for valid_from, sue in zip(firm_events.valid_from, firm_events.sue):
            if not np.isfinite(sue) or sue == 0.0:
                continue
            # Conservative PIT rule for a gate-only computation: never trade
            # on the acceptance day itself, always the next session or later.
            cutoff_date = pd.Timestamp(valid_from).normalize() + pd.Timedelta(days=1)
            position = int(np.searchsorted(dates.values, np.datetime64(cutoff_date)))
            if position >= total:
                continue
            anchor = closes[position]
            if not np.isfinite(anchor) or anchor <= 0:
                continue
            event_week = pd.Timestamp(dates.iloc[position]).tz_localize(None).to_period("W").start_time
            for window in WINDOWS:
                maturity = position + window
                if maturity >= total:
                    continue
                matured = closes[maturity]
                if not np.isfinite(matured) or matured <= 0:
                    continue
                realised = matured / anchor - 1.0
                rows.append({
                    "symbol": symbol, "window": window, "week": event_week,
                    "signed_return": realised * np.sign(sue),
                })
    return pd.DataFrame(rows)


def gate(*, min_weeks: int = 20) -> list[GateResult]:
    """The PEAD-1 power gate. Returns half-widths only, per window."""
    events = _load_events()
    raw = _event_advantage_rows(events)
    results: list[GateResult] = []

    for window in WINDOWS:
        subset = raw.loc[raw["window"] == window]
        if subset.empty:
            results.append(GateResult(window, 0, 0, 0, float("nan"), MDE_BP))
            continue
        per_week = subset.groupby("week")["signed_return"].mean().sort_index()
        n_weeks = len(per_week)
        if n_weeks < min_weeks:
            results.append(GateResult(window, len(subset), n_weeks, 0, float("nan"), MDE_BP))
            continue

        values = per_week.to_numpy(dtype=float)
        centred = values - values.mean()          # the mean is discarded here
        del values

        autocorr = pd.Series(centred).autocorr(lag=1)
        block = 4 if not np.isfinite(autocorr) or autocorr < 0.2 else (
            8 if autocorr < 0.4 else 13)           # ~1/3/6 months of weekly events
        block = min(block, max(1, n_weeks // 5))

        ci_low, ci_high = stats.block_bootstrap_ci(centred, block=block,
                                                    draws=stats.BOOTSTRAP_DRAWS)
        half_width_bp = float((ci_high - ci_low) / 2.0 * 1e4)

        results.append(GateResult(
            window=window, n_events=len(subset), n_weeks=n_weeks, block_weeks=block,
            half_width_bp=half_width_bp, mde_bp=MDE_BP))
    return results


def main() -> int:
    results = gate()
    print(f"{'Window':>8} {'Events':>8} {'Weeks':>8} {'Block(wk)':>10} "
          f"{'Half-width(bp)':>16} {'MDE(bp)':>10}  Verdict")
    all_fail = True
    for r in results:
        verdict = "PASS" if r.passes else "FAIL"
        if r.passes:
            all_fail = False
        hw = f"{r.half_width_bp:.1f}" if np.isfinite(r.half_width_bp) else "n/a (too few weeks)"
        print(f"{r.window:>8} {r.n_events:>8} {r.n_weeks:>8} {r.block_weeks:>10} "
              f"{hw:>16} {r.mde_bp:>10.1f}  {verdict}")
    print()
    print("PEAD-1 GATE: at least one window PASSES" if not all_fail
          else "PEAD-1 GATE: ALL WINDOWS FAIL — PEAD-1 MUST NOT RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
