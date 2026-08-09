"""The experiment grid: which dates, which symbols, which horizons.

Shared by the prediction stage and the scoring stage so neither can drift from
the other, and so the random cutoffs are reproducible from the seed alone
rather than from whatever the first run happened to draw.
"""

from __future__ import annotations

import pandas as pd

from . import pit

SEED = 20260807

# The four the procedure names, as calendar offsets from the last cached bar.
NAMED_OFFSETS = [
    ("6 months ago", pd.DateOffset(months=6)),
    ("3 months ago", pd.DateOffset(months=3)),
    ("1 month ago", pd.DateOffset(months=1)),
    ("2 weeks ago", pd.DateOffset(weeks=2)),
]

RANDOM_CUTOFFS = 8

# A cutoff needs history behind it and outcomes in front of it.
#
# Behind: five years of daily bars, measured against the *median* symbol's
# cache depth rather than the deepest one. SPY reaches back to 1993 and would
# happily supply a 1999 cutoff, but two thirds of this universe has nothing
# before 2016, so a 1999 experiment would be a study of SPY wearing a
# thirty-symbol costume. The floor lands on 2021-08 for this cache.
#
# In front: 126 sessions, the six-month outcome the procedure asks to measure.
MIN_HISTORY_YEARS = 5
MAX_OUTCOME_BARS = 126

# Forward windows every prediction is scored over, in trading days. The first
# two are the system's own native horizons; the rest exist to answer the
# procedure's 1-month / 3-month / 6-month questions, and to show what happens
# when a call is held far past the distance it was made for.
OUTCOME_BARS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "6m": 126}

# The neural forecaster costs ~35 s per experiment, so it runs on a subset:
# two index funds, four megacaps, one high-beta name and one crypto pair, which
# is enough spread to tell "works on indices only" apart from "works".
MODEL_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "TSLA", "BTC-USD"]

# Production defaults from streamlit_app.py — not tuned for this study.
MODEL_FOLDS, MODEL_EPOCHS, MODEL_UNITS, MODEL_HORIZON = 3, 30, 64, 5


def history_floor() -> pd.Timestamp:
    """Earliest cutoff at which the median symbol still has five years behind it."""
    starts = []
    for symbol in symbols():
        frame = pit.full_history(symbol)
        if frame is not None and len(frame):
            starts.append(pd.Timestamp(frame["date"].iloc[0]))
    median = pd.Series(sorted(starts)).median()
    return pd.Timestamp(median) + pd.DateOffset(years=MIN_HISTORY_YEARS)


def cutoffs(calendar: pd.Series | None = None) -> list[dict]:
    """Every historical evaluation date, named ones first."""
    calendar = pit.trading_days() if calendar is None else calendar
    today = pd.Timestamp(calendar.iloc[-1]).normalize()

    out: list[dict] = []
    for label, offset in NAMED_OFFSETS:
        day = pit.last_trading_day(today - offset, calendar)
        out.append({"date": day, "label": label, "kind": "named"})

    # Draw the extra dates from the window where a full six-month outcome and a
    # full five years of prior history both exist, so every random experiment
    # is scoreable at every horizon.
    floor = history_floor()
    eligible = calendar[(calendar >= floor)
                        & (calendar <= calendar.iloc[-1 - MAX_OUTCOME_BARS])]
    drawn = eligible.sample(n=RANDOM_CUTOFFS, random_state=SEED).sort_values()
    for day in drawn:
        out.append({"date": pd.Timestamp(day).normalize(),
                    "label": pd.Timestamp(day).strftime("%Y-%m-%d"),
                    "kind": "random"})

    # A random draw could in principle land on a named date; keep one copy.
    seen: dict[pd.Timestamp, dict] = {}
    for entry in out:
        seen.setdefault(entry["date"], entry)
    return sorted(seen.values(), key=lambda e: e["date"])


def symbols() -> list[str]:
    """The universe: everything with cached daily bars."""
    return pit.cached_symbols("1d")
