"""HT-2's first candidate: swing VWAP mean reversion.

Pre-registered in `alpha/HT2_TOURNAMENT_PREREGISTRATION.md` §3.2, window and
threshold frozen in its Amendment 1 (window=10 sessions, chosen on
variance-only grounds; threshold=2.0 standard deviations, this repository's
own `indicators.bollinger` default) **before any forward return for this
candidate was read.**

This module does not modify `core/tournament.py`, its `CANDIDATES` roster, or
`app/tournament.sqlite3` — HT-1's frozen, trigger-immutable record. It reuses
HT-1's read-only instrument (`load_frames`, `build_grid`, `admissible_cells`,
`HORIZON_BARS`) and its exact scoring/statistics pipeline
(`tournament.leaderboard`, which calls `alpha/stats.py`'s block bootstrap)
against a dataframe this module builds independently, so the two studies'
numbers are produced by one shared, already-tested instrument and are not two
implementations that could quietly disagree.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

WINDOW = 10
DEVIATIONS = 2.0
CANDIDATE_KEY = "ht2.vwap_reversion"

BUY, HOLD, SELL = 1.0, 0.0, -1.0

MIN_ROWS_FOR_VWAP = WINDOW + 1


def vwap_reversion_series(
    frame: pd.DataFrame, *, window: int = WINDOW, deviations: float = DEVIATIONS,
) -> pd.Series:
    """BUY/HOLD/SELL at every bar. Purely backward-looking: bar `t` depends only
    on rows `<= t`, so reading `.iloc[position]` on the full frame equals
    reading it on a frame truncated to `position` — the two are computed from
    the identical trailing window either way, which is the property this
    function's PIT-safety rests on and every test below checks directly.

    Mirrors `indicators.bollinger`'s construction exactly, with VWAP swapped
    in for the simple moving average as the reversion band's centre, and
    argued the same "against the move" direction `indicators._bollinger_reversion`
    already establishes for this repository: short when price sits materially
    above the band, long when materially below.
    """
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    weighted = (typical * frame["volume"]).rolling(window).sum()
    volume = frame["volume"].rolling(window).sum()
    vwap = weighted / volume.replace(0.0, np.nan)

    spread = frame["close"].rolling(window).std(ddof=0)
    upper = vwap + deviations * spread
    lower = vwap - deviations * spread

    close = frame["close"]
    signal = pd.Series(HOLD, index=frame.index, dtype=float)
    valid = vwap.notna() & spread.notna() & (spread > 0)
    signal.loc[valid & (close >= upper)] = SELL
    signal.loc[valid & (close <= lower)] = BUY
    return signal


def call_at(frame: pd.DataFrame, position: int) -> float:
    """The signal at one bar, read from the full frame (see docstring above
    for why this equals truncate-then-read-last for a backward-looking
    rolling calculation)."""
    if position + 1 < MIN_ROWS_FOR_VWAP:
        return HOLD
    series = vwap_reversion_series(frame.iloc[: position + 1])
    return float(series.iloc[-1])


def measure(
    *,
    frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Build the (candidate, horizon, cutoff, symbol) frame `tournament.leaderboard`
    expects, on HT-1's own frozen grid. Writes nothing; returns the raw rows.
    """
    from . import tournament

    frames = frames if frames is not None else tournament.load_frames()
    grid = tournament.build_grid(frames)
    cells = tournament.admissible_cells(frames, grid)

    rows: list[dict] = []
    for cell in cells:
        frame = frames[cell.symbol]
        call = call_at(frame, cell.position)
        anchor = float(frame["close"].iloc[cell.position])
        if not anchor:
            continue
        for horizon, ahead in tournament.HORIZON_BARS.items():
            maturity = cell.position + ahead
            if maturity >= len(frame):
                continue
            matured = float(frame["close"].iloc[maturity])
            realised = matured / anchor - 1.0
            correct = (None if call == HOLD else
                       int((call > 0 and realised > 0) or (call < 0 and realised < 0)))
            rows.append({
                "candidate": CANDIDATE_KEY,
                "horizon": horizon,
                "symbol": cell.symbol,
                "cutoff_at": cell.cutoff,
                "matured_at": frame["date"].iloc[maturity],
                "call": call,
                "directional_correct": correct,
                "realised_return": realised,
            })
    return pd.DataFrame(rows)


def leaderboard_rows(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """`tournament.leaderboard`, unmodified, on this candidate's rows only.

    The returned table's own `p Holm` / `Holm reject` columns are NOT the
    final word — they correct across a family of 3 (this candidate's three
    horizons), not across HT-1's 81 plus these 3, which is what the
    pre-registration commits to reporting (§5). `combined_gate` does that.
    """
    from . import tournament

    frame = frame if frame is not None else measure()
    return tournament.leaderboard(frame)


def combined_gate(
    own: pd.DataFrame, *, ht1_csv: str | pathlib.Path | None = None,
) -> pd.DataFrame:
    """Recompute Holm-Bonferroni across HT-1's 81 resolved tests plus `own`'s.

    Per HT2_TOURNAMENT_PREREGISTRATION.md §5: "Multiplicity is combined with
    HT-1's own 81 tests, not treated as a fresh family of two [now three]."
    """
    from . import tournament
    from alpha import stats

    ht1_path = pathlib.Path(ht1_csv) if ht1_csv is not None else (
        pathlib.Path(__file__).resolve().parents[2] / "reports" / "ht1_leaderboard.csv"
    )
    ht1 = pd.read_csv(ht1_path)
    ht1_family = {
        f"{row.Candidate}@{row.Horizon}": float(row.p)
        for row in ht1.itertuples()
        if bool(row.Resolved) and not bool(row.Reference) and np.isfinite(row.p)
    }

    own_family = {
        f"{row.Candidate}@{row.Horizon}": float(row.p)
        for row in own.itertuples()
        if bool(row.Resolved) and not bool(row.Reference) and np.isfinite(row.p)
    }

    combined = {**ht1_family, **own_family}
    decisions = stats.holm_bonferroni(combined, alpha=tournament.GATE_ALPHA)

    table = own.copy()
    names = table["Candidate"].astype(str) + "@" + table["Horizon"].astype(str)
    table["Family size"] = len(combined)
    table["p Holm"] = [decisions.get(name, {}).get("p_holm") for name in names]
    table["Holm reject"] = [
        bool(decisions.get(name, {}).get("significant", False)) for name in names
    ]
    table["Beats baseline"] = (
        table["Resolved"] & ~table["Reference"] & table["Holm reject"]
        & np.isfinite(table["Adv CI low"]) & (table["Adv CI low"] > 0.0)
    )
    table["Verdict"] = np.select(
        [table["Reference"], ~table["Resolved"], table["Beats baseline"]],
        ["REFERENCE", "UNRESOLVED", "BEATS BASELINE"],
        default="REJECT")
    return table
