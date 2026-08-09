"""Point-in-time data access: the system may only see bars at or before a cutoff.

Every historical experiment in this package runs the *production* code paths —
`ultimate.evaluate`, `forecast.project`, the rule-based strategies — against a
frame that has been truncated at a historical date. Nothing else about the
engine changes, which is the only way the resulting numbers describe the system
that actually ships rather than a re-implementation of it.

The one place look-ahead could leak in is data loading, so all of it lives here:

- `fetcher(cutoff)` produces a drop-in replacement for `live.fetch` that reads
  the cache, cuts everything after `cutoff`, and only then applies the period
  trim — so a "10y" request at a 2023 cutoff returns the ten years *ending in
  2023*, exactly as production would have seen it.
- `future(...)` is the other side, and is deliberately not importable by the
  prediction stage: it is what the scorer calls after predictions are frozen.

Known residual look-ahead, stated rather than hidden (validation rule 9):

1. **Adjusted prices.** The cache was downloaded with `auto_adjust=True`, so
   splits and dividends after a cutoff are already baked into the pre-cutoff
   level. Splits are a pure rescaling and leave returns untouched; dividend
   adjustment shifts historical returns by the yield. It is small for this
   universe and it is not removable without re-downloading unadjusted bars.
2. **Universe selection.** The symbols are whatever is in the local cache,
   which is a list a live user assembled *today*. Names that delisted or that
   nobody kept watching are absent. This inflates nothing about directional
   accuracy directly, but it does mean the sample is not a random draw of
   what was investable at the cutoff.
3. **Intraday depth.** Yahoo only serves ~730 days of hourly bars, so a 2022
   cutoff has no hourly history at all and a 2026-02 cutoff has ~18 months
   where production would have had 24. The engine reports those horizons as
   unavailable on its own; nothing is interpolated.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import glob
import os
import pathlib
import sys

import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core import live  # noqa: E402

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

# Filenames replace characters that are illegal on Windows; undo that so the
# symbol we hand back to the engine is the one Yahoo knows.
_UNSAFE = {"EURUSD_X": "EURUSD=X"}


def cached_symbols(interval: str = "1d") -> list[str]:
    """Every symbol with bars on disk at this interval."""
    pattern = str(live.CACHE_DIR / f"*__{interval}.csv")
    stems = [os.path.basename(p)[: -len(f"__{interval}.csv")] for p in sorted(glob.glob(pattern))]
    return [_UNSAFE.get(stem, stem) for stem in stems]


def full_history(symbol: str, interval: str = "1d") -> pd.DataFrame | None:
    """The whole cached series, future included. Scorer-side only."""
    found = live.read_cache(symbol, interval)
    return None if found is None else found[0]


def as_of(cutoff: pd.Timestamp) -> pd.Timestamp:
    """End-of-day on the cutoff, so a daily bar stamped 00:00 is included."""
    return pd.Timestamp(cutoff).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)


def fetcher(cutoff: pd.Timestamp):
    """A `live.fetch` stand-in that cannot see past `cutoff`.

    Signature matches `live.fetch` exactly because `ultimate.evaluate` calls it
    with keyword arguments and stores what comes back verbatim.
    """
    edge = as_of(cutoff)

    def fetch(symbol: str, period: str = "5y", interval: str = "1d",
              force: bool = False) -> tuple[pd.DataFrame, live.CacheEntry]:
        found = live.read_cache(symbol, interval)
        if found is None:
            raise live.FetchError(f"no cached {interval} bars for {symbol}")
        frame, entry = found

        frame = frame[frame["date"] <= edge].reset_index(drop=True)
        if frame.empty:
            raise live.FetchError(
                f"{symbol} has no {interval} bars at or before {edge.date()}")

        # Trim relative to the truncated frame's own last bar — slice_to_period
        # measures backwards from `frame['date'].iloc[-1]`, which is now the
        # cutoff rather than today.
        frame = live.slice_to_period(frame, period)
        entry = dataclasses.replace(
            entry, rows=len(frame),
            start=frame["date"].iloc[0].date(), end=frame["date"].iloc[-1].date(),
        )
        return frame, entry

    return fetch


def frame_at(symbol: str, cutoff: pd.Timestamp, interval: str = "1d",
             period: str = "10y") -> pd.DataFrame | None:
    """One truncated frame, for the callers that don't go through `evaluate`."""
    try:
        return fetcher(cutoff)(symbol, period=period, interval=interval)[0]
    except live.FetchError:
        return None


def trading_days(symbol: str = "SPY", interval: str = "1d") -> pd.Series:
    """The calendar this study runs on: bars a liquid US equity actually printed."""
    frame = full_history(symbol, interval)
    if frame is None:
        raise RuntimeError(f"no cached {interval} history for {symbol}")
    return frame["date"]


def last_trading_day(target: dt.date | pd.Timestamp,
                     calendar: pd.Series | None = None) -> pd.Timestamp:
    """The last session at or before `target`.

    A cutoff of "6 months ago" lands on a weekend often enough that leaving it
    unaligned would silently vary how much history each experiment got.
    """
    calendar = trading_days() if calendar is None else calendar
    stamp = pd.Timestamp(target).normalize()
    eligible = calendar[calendar <= as_of(stamp)]
    if eligible.empty:
        raise ValueError(f"no trading day at or before {stamp.date()}")
    return pd.Timestamp(eligible.iloc[-1]).normalize()


def describe_information_set(symbol: str, cutoff: pd.Timestamp) -> dict:
    """What the system could see at this cutoff — Step 1 of the procedure.

    Recorded per experiment so the report can state the information set rather
    than assert it.
    """
    out: dict[str, object] = {}
    for interval in ("1d", "1h"):
        frame = frame_at(symbol, cutoff, interval=interval,
                         period="10y" if interval == "1d" else "2y")
        if frame is None or frame.empty:
            out[interval] = {"bars": 0, "available": False}
            continue
        out[interval] = {
            "available": True,
            "bars": int(len(frame)),
            "first_bar": str(frame["date"].iloc[0]),
            "last_bar": str(frame["date"].iloc[-1]),
            "last_close": float(frame["close"].iloc[-1]),
            "columns": [c for c in frame.columns if c != "date"],
        }
    return out
