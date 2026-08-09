"""Stage 2a — reveal what actually happened, and what a simple rule would have said.

Nothing here runs until `predictions.json` exists, and nothing here writes to
it. This is the only module in the package that reads bars after a cutoff.

Two things are produced per (cutoff, symbol):

* **Outcomes** — the realised forward return at each scoring window, plus the
  path statistics a signal claim can be checked against (max favourable and
  adverse excursion, realised volatility, and the same window on SPY so
  "did it outperform" is answerable).
* **Baselines** — what buy-and-hold, trend continuation, a moving-average
  filter and a coin flip would have predicted from the *same* frozen
  information. They are computed here rather than in `predict.py` only
  because they are trivially causal; each one is written to read strictly
  pre-cutoff bars, and the assertion in `_causal_check` enforces it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import pit, schedule

BENCHMARK = "SPY"

# Seeded so the "random directional prediction" baseline is a fixed draw
# rather than something that changes between runs of the report.
RANDOM_SEED = 424242


def _index_at(dates: pd.Series, cutoff: pd.Timestamp) -> int | None:
    """Position of the last bar at or before the cutoff."""
    edge = pit.as_of(cutoff)
    eligible = np.flatnonzero((dates <= edge).to_numpy())
    return int(eligible[-1]) if eligible.size else None


def forward(frame: pd.DataFrame, cutoff: pd.Timestamp, bars: int) -> dict | None:
    """The realised move `bars` ahead of the cutoff, or None if it hasn't happened."""
    if frame is None or frame.empty:
        return None
    here = _index_at(frame["date"], cutoff)
    if here is None or here + bars >= len(frame):
        return None

    start = float(frame["close"].iloc[here])
    end = float(frame["close"].iloc[here + bars])
    path = frame["close"].iloc[here + 1: here + bars + 1].to_numpy(dtype=float)
    if start == 0:
        return None

    return {
        "bars": bars,
        "start_price": round(start, 6),
        "end_price": round(end, 6),
        "end_date": str(frame["date"].iloc[here + bars].date()),
        "return_pct": round((end / start - 1.0) * 100, 5),
        "direction": int(np.sign(end - start)),
        # How far the trade went the right and wrong way before it ended —
        # a "correct" call that spent the window 20% underwater is not the
        # same claim as one that went straight there.
        "max_favourable_pct": round((path.max() / start - 1.0) * 100, 4),
        "max_adverse_pct": round((path.min() / start - 1.0) * 100, 4),
    }


def _causal_check(frame: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """A frame trimmed at the cutoff, with the trim asserted rather than assumed."""
    trimmed = frame[frame["date"] <= pit.as_of(cutoff)]
    # A symbol that had not listed yet trims to nothing, which is a legitimate
    # "no baseline here" rather than a leak — hence the emptiness check before
    # the assertion, whose NaT comparison would otherwise read as a violation.
    assert trimmed.empty or trimmed["date"].max() <= pit.as_of(cutoff), \
        "baseline saw the future"
    return trimmed


def baselines(frame: pd.DataFrame, cutoff: pd.Timestamp,
              bars: int, rng: np.random.Generator) -> dict:
    """What the simple rules predicted, from pre-cutoff bars only (Step 10)."""
    history = _causal_check(frame, cutoff)
    close = history["close"]
    if len(close) < 60:
        return {}

    last = float(close.iloc[-1])
    prior = float(close.iloc[-1 - bars]) if len(close) > bars else float(close.iloc[0])
    sma50 = float(close.tail(50).mean())
    sma200 = float(close.tail(200).mean()) if len(close) >= 200 else float("nan")

    out = {
        # Always long. The benchmark every long-only system has to beat, and
        # the reason directional accuracy alone flatters anything on a tape
        # that rose over the study window.
        "buy_and_hold": 1,
        # The move over the same length of window, repeated forward.
        "trend_continuation": int(np.sign(last - prior)),
        # Price against its own 50-bar mean.
        "sma_direction": int(np.sign(last - sma50)),
        # A coin flip, actually flipped.
        "random": int(rng.choice([-1, 1])),
    }
    if not np.isnan(sma200):
        out["golden_cross"] = int(np.sign(sma50 - sma200))
    return out


def realised_volatility_pct(frame: pd.DataFrame, cutoff: pd.Timestamp,
                            window: int = 60) -> float | None:
    """Annualised volatility of the 60 sessions before the cutoff.

    Pre-cutoff by construction: it labels the regime the prediction was *made*
    in, which is what Step 8 needs to ask whether the system fails in
    turbulence.
    """
    history = _causal_check(frame, cutoff)["close"]
    if len(history) < window + 1:
        return None
    returns = history.pct_change().dropna().tail(window)
    if returns.empty or returns.std() == 0:
        return None
    return float(returns.std() * np.sqrt(252) * 100)


def build(predictions: dict) -> dict:
    """Attach outcomes and baselines to every frozen prediction."""
    rng = np.random.default_rng(RANDOM_SEED)
    daily: dict[str, pd.DataFrame] = {}
    hourly: dict[str, pd.DataFrame] = {}

    def daily_frame(symbol: str) -> pd.DataFrame | None:
        if symbol not in daily:
            daily[symbol] = pit.full_history(symbol, "1d")
        return daily[symbol]

    def hourly_frame(symbol: str) -> pd.DataFrame | None:
        if symbol not in hourly:
            hourly[symbol] = pit.full_history(symbol, "1h")
        return hourly[symbol]

    benchmark = daily_frame(BENCHMARK)
    rows = []

    for record in predictions["predictions"]:
        symbol, cutoff = record["symbol"], pd.Timestamp(record["cutoff"])
        frame = daily_frame(symbol)
        row = {"cutoff": record["cutoff"], "symbol": symbol,
               "cutoff_label": record["cutoff_label"],
               "cutoff_kind": record["cutoff_kind"]}

        if frame is None:
            row["outcomes"] = {}
            rows.append(row)
            continue

        row["outcomes"] = {
            name: forward(frame, cutoff, bars)
            for name, bars in schedule.OUTCOME_BARS.items()
        }
        # The 4-hour horizon is scored on the bars it was actually made on.
        row["outcomes"]["4h"] = forward(hourly_frame(symbol), cutoff, 4)
        row["benchmark"] = {
            name: forward(benchmark, cutoff, bars)
            for name, bars in schedule.OUTCOME_BARS.items()
        }
        row["baselines"] = {
            name: baselines(frame, cutoff, bars, rng)
            for name, bars in schedule.OUTCOME_BARS.items()
        }
        row["volatility_pct"] = realised_volatility_pct(frame, cutoff)
        rows.append(row)

    return {"stage": "outcomes", "rows": rows}
