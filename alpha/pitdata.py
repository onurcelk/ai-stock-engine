"""The V2 point-in-time data door. One way in, and it truncates before it computes.

Same contract as `validation/pit.py`, restated for a panel rather than a single
symbol: **nothing on the prediction side may see a bar dated after the cutoff.**
The V1 door proved its guarantee with a test that rewrites the future and
demands an identical verdict; `app/tests/test_alpha.py` does the same to this
one, which is the only reason to believe either.

The shape is different because the question is. V1 asked "what does the engine
say about AAPL on this date"; V2 asks "rank 480 names against each other on
this date", and a cross-section wants wide matrices — date x symbol — not 480
independent frames. So the book loads once, and `PriceBook.view(cutoff)`
returns a `PriceView` holding matrices already sliced to `[:cutoff]`. A view
has no method that can reach past its own edge; the full history is only
reachable from the book, and the only book method that reads forward is
`forward_return`, which is named to be greppable and is called exclusively from
the scoring side.
"""

from __future__ import annotations

import dataclasses
import functools
import pathlib

import numpy as np
import pandas as pd

CACHE_DIR = pathlib.Path(__file__).resolve().parent / "cache"

# Symbols whose filename had to be sanitised on the way to disk.
_FILE_ALIASES = {"_VIX": "^VIX"}

FIELDS = ("close", "open", "high", "low", "volume")


def _unsafe(stem: str) -> str:
    return _FILE_ALIASES.get(stem, stem)


@dataclasses.dataclass(frozen=True)
class PriceView:
    """Everything knowable at a cutoff, and nothing else.

    Each matrix is date x symbol with the index already cut at the cutoff. A
    holder of a view cannot obtain future bars from it by any route, which is
    what makes it safe to hand to the feature pipeline.
    """

    cutoff: pd.Timestamp
    close: pd.DataFrame
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    volume: pd.DataFrame

    @property
    def calendar(self) -> pd.DatetimeIndex:
        return self.close.index

    @property
    def bars(self) -> int:
        return len(self.close.index)

    def last_close(self) -> pd.Series:
        return self.close.iloc[-1]

    def history_length(self) -> pd.Series:
        """Sessions of non-null close behind each symbol — the §2 eligibility input."""
        return self.close.notna().sum()

    def subset(self, symbols: list[str]) -> "PriceView":
        keep = [s for s in symbols if s in self.close.columns]
        return PriceView(self.cutoff, *(getattr(self, f)[keep] for f in FIELDS))


class PriceBook:
    """The full cache, loaded once. Hand out views; never hand out this."""

    def __init__(self, frames: dict[str, pd.DataFrame]):
        self._matrices = {
            field: pd.DataFrame({s: f.set_index("date")[field]
                                 for s, f in frames.items() if field in f.columns})
            .sort_index()
            for field in FIELDS
        }
        self.symbols = sorted(self._matrices["close"].columns)

    @property
    def calendar(self) -> pd.DatetimeIndex:
        """The study calendar: sessions SPY actually printed.

        Anchoring on SPY rather than on the union of all symbols keeps crypto-
        style 7-day series and half-loaded names from inventing sessions that
        the equity market never had.
        """
        spy = self._matrices["close"].get("SPY")
        if spy is None:
            raise RuntimeError("SPY is required as the study calendar")
        return pd.DatetimeIndex(spy.dropna().index)

    def view(self, cutoff: pd.Timestamp) -> PriceView:
        """The prediction-side accessor. Truncation happens here and only here."""
        edge = pd.Timestamp(cutoff).normalize()
        sliced = {field: matrix.loc[:edge] for field, matrix in self._matrices.items()}
        if sliced["close"].empty:
            raise ValueError(f"no bars at or before {edge.date()}")
        return PriceView(edge, **sliced)

    # ------------------------------------------------------------------
    # Scoring side. Everything below reads bars after the cutoff and must
    # never be reachable from feature or model code.
    # ------------------------------------------------------------------

    def forward_return(self, cutoff: pd.Timestamp, horizon: int,
                       symbols: list[str] | None = None) -> pd.Series:
        """`Close[T+H] / Close[T] - 1`, H measured in sessions on the study calendar.

        SCORER SIDE. Returns NaN where the symbol has no bar at either end —
        a name that stopped trading inside the window has no measurable
        outcome, and inventing one (carrying the last price forward) would
        quietly turn a delisting into a flat return.
        """
        calendar = self.calendar
        edge = pd.Timestamp(cutoff).normalize()
        position = calendar.searchsorted(edge, side="right") - 1
        if position < 0 or position + horizon >= len(calendar):
            return pd.Series(dtype=float)

        start, end = calendar[position], calendar[position + horizon]
        close = self._matrices["close"]
        if symbols is not None:
            close = close[[s for s in symbols if s in close.columns]]
        base = close.reindex([start]).iloc[0]
        later = close.reindex([end]).iloc[0]
        out = later / base - 1.0
        return out.replace([np.inf, -np.inf], np.nan)

    def horizon_end(self, cutoff: pd.Timestamp, horizon: int) -> pd.Timestamp | None:
        calendar = self.calendar
        position = calendar.searchsorted(pd.Timestamp(cutoff).normalize(), side="right") - 1
        if position < 0 or position + horizon >= len(calendar):
            return None
        return calendar[position + horizon]


def _read(path: pathlib.Path) -> pd.DataFrame | None:
    try:
        frame = pd.read_csv(path, parse_dates=["date"])
    except Exception:  # noqa: BLE001 — a half-written cache file is not a crash
        return None
    if frame.empty or "close" not in frame.columns:
        return None
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return frame.drop_duplicates("date").sort_values("date")


@functools.lru_cache(maxsize=1)
def load_book(cache_dir: str | None = None) -> PriceBook:
    """Load every cached series. Cached because the panel is ~2M rows."""
    directory = pathlib.Path(cache_dir) if cache_dir else CACHE_DIR
    frames: dict[str, pd.DataFrame] = {}
    for path in sorted(directory.glob("*.csv")):
        frame = _read(path)
        if frame is not None:
            frames[_unsafe(path.stem)] = frame
    if "SPY" not in frames:
        raise RuntimeError(f"no SPY bars in {directory} — run: python -m alpha.download")
    return PriceBook(frames)


@dataclasses.dataclass(frozen=True)
class Calendar:
    """Just the study calendar. Enough for anything that only needs to count sessions."""

    calendar: pd.DatetimeIndex


@functools.lru_cache(maxsize=1)
def load_calendar(cache_dir: str | None = None) -> Calendar:
    """The SPY session index, without loading all 654 series.

    The walk-forward and the embargo arithmetic need to count sessions and
    nothing else. Reading one CSV instead of the whole cache is the difference
    between a second and a minute per process, and it removes any temptation to
    reach for a price matrix from a stage that has no business holding one.
    """
    directory = pathlib.Path(cache_dir) if cache_dir else CACHE_DIR
    frame = _read(directory / "SPY.csv")
    if frame is None:
        raise RuntimeError(f"no SPY bars in {directory} — run: python -m alpha.download")
    return Calendar(pd.DatetimeIndex(frame["date"].dropna().unique()).sort_values())


def sessions_before(calendar: pd.DatetimeIndex, cutoff: pd.Timestamp) -> int:
    return int(calendar.searchsorted(pd.Timestamp(cutoff).normalize(), side="right"))


def align_to_calendar(calendar: pd.DatetimeIndex, target: pd.Timestamp) -> pd.Timestamp:
    """The last session at or before `target` — the V1 `last_trading_day` rule."""
    stamp = pd.Timestamp(target).normalize()
    position = calendar.searchsorted(stamp, side="right") - 1
    if position < 0:
        raise ValueError(f"no session at or before {stamp.date()}")
    return calendar[position]
