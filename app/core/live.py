"""Live market data via yfinance, with a disk cache in front of it.

The repo's bundled CSVs stop in 2017-2019 and hold ~250 rows each. One call
here returns decades of daily bars for any symbol Yahoo knows about, which
is both a freshness fix and — more importantly — the difference between
training a recurrent net on 222 samples and on several thousand.

yfinance talks to an undocumented endpoint that throttles by IP, so every
fetch goes through a day-granularity disk cache. In normal use a symbol is
downloaded once per day no matter how much the UI is clicked, which keeps
us far below any rate limit and lets the app work offline afterwards.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib
import re

import pandas as pd

from . import data

CACHE_DIR = pathlib.Path(__file__).resolve().parents[1] / "cache"

INTERVALS = {
    "1 Hour": "1h",
    "4 Hour": "4h",
    "Daily": "1d",
    "Weekly": "1wk",
    "Monthly": "1mo",
}

# Yahoo refuses intraday requests older than 730 days. Asking anyway returns an
# empty frame rather than an error, so the choices are constrained up front.
INTRADAY = {"1h", "4h"}
INTRADAY_MAX_DAYS = 730

INTRADAY_PERIODS = ["5d", "1mo", "3mo", "6mo", "1y", "2y"]
DAILY_PERIODS = ["1y", "2y", "5y", "10y", "max"]

PERIODS = DAILY_PERIODS  # kept for callers that don't care about interval

# Yahoo's symbol conventions aren't guessable, so these double as documentation.
QUICK_PICKS = ["AAPL", "NVDA", "MSFT", "TSLA", "SPY", "BTC-USD", "ETH-USD", "EURUSD=X"]

# Rough fallbacks. Prefer data.periods_per_year(), which measures the actual
# series — hourly crypto has ~5x the bars per year of hourly equities.
PERIODS_PER_YEAR = {"1h": 1750, "4h": 440, "1d": 252, "1wk": 52, "1mo": 12}


# Calendar days each period covers, for trimming a wider cache back down.
PERIOD_DAYS = {
    "5d": 7, "1mo": 31, "3mo": 93, "6mo": 186,
    "1y": 366, "2y": 731, "5y": 1827, "10y": 3653,
}


def periods_for(interval: str) -> list[str]:
    """History lengths Yahoo will actually serve at this interval."""
    return INTRADAY_PERIODS if interval in INTRADAY else DAILY_PERIODS


def slice_to_period(frame: pd.DataFrame, period: str) -> pd.DataFrame:
    """Trim a frame to the requested lookback.

    The cache deliberately keeps the widest range ever downloaded, so a
    "1y" request served from a cache built by a "max" request would
    otherwise quietly return decades. Every tab reads the returned frame
    directly, so the trim has to happen here.
    """
    days = PERIOD_DAYS.get(period)
    if days is None or frame.empty:  # "max", or nothing to trim
        return frame
    cutoff = frame["date"].iloc[-1] - dt.timedelta(days=days)
    trimmed = frame[frame["date"] >= cutoff]
    return trimmed.reset_index(drop=True) if len(trimmed) else frame


def default_period(interval: str) -> str:
    return "1mo" if interval in INTRADAY else "5y"


class FetchError(RuntimeError):
    """Raised for anything the UI should show as a readable message.

    Plain FetchError means the request was reasonable but failed — offline,
    rate-limited, Yahoo down. Those fall back to cached data.
    """


class RequestError(FetchError):
    """The request itself was wrong, so cached data would answer a different question.

    Never satisfied from cache: returning yesterday's daily bars when someone
    asked for five years of hourly ones is worse than an error.
    """


class UnknownSymbol(RequestError):
    """Yahoo has no data for this symbol (it returns an empty frame, not an error)."""


class InvalidRange(RequestError):
    """This period is not available at this interval (intraday is capped at 730 days)."""


@dataclasses.dataclass
class CacheEntry:
    symbol: str
    interval: str
    rows: int
    start: dt.date
    end: dt.date
    fetched_at: dt.datetime

    @property
    def age(self) -> dt.timedelta:
        return dt.datetime.now() - self.fetched_at

    @property
    def is_fresh(self) -> bool:
        """Fresh means fetched today — daily bars don't change intraday."""
        return self.fetched_at.date() == dt.date.today()

    def describe_age(self) -> str:
        seconds = self.age.total_seconds()
        if seconds < 3600:
            return f"{int(seconds // 60)} min ago"
        if seconds < 86_400:
            return f"{int(seconds // 3600)} h ago"
        return f"{self.age.days} d ago"


def _safe(symbol: str) -> str:
    """Symbols contain characters that are illegal in filenames (BRK.B, EURUSD=X)."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", symbol.upper())


def _paths(symbol: str, interval: str) -> tuple[pathlib.Path, pathlib.Path]:
    stem = f"{_safe(symbol)}__{interval}"
    return CACHE_DIR / f"{stem}.csv", CACHE_DIR / f"{stem}.meta.json"


def read_cache(symbol: str, interval: str = "1d") -> tuple[pd.DataFrame, CacheEntry] | None:
    """Return the cached frame and its metadata, or None if absent/corrupt."""
    csv_path, meta_path = _paths(symbol, interval)
    if not (csv_path.exists() and meta_path.exists()):
        return None
    try:
        frame = data.normalise(pd.read_csv(csv_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        entry = CacheEntry(
            symbol=meta["symbol"],
            interval=meta["interval"],
            rows=len(frame),
            start=frame["date"].iloc[0].date(),
            end=frame["date"].iloc[-1].date(),
            fetched_at=dt.datetime.fromisoformat(meta["fetched_at"]),
        )
        return frame, entry
    except Exception:
        # A half-written or hand-edited cache file should never break the app.
        return None


def _write_cache(symbol: str, interval: str, frame: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    csv_path, meta_path = _paths(symbol, interval)
    frame.to_csv(csv_path, index=False)
    meta_path.write_text(
        json.dumps(
            {
                "symbol": symbol.upper(),
                "interval": interval,
                "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
                "rows": len(frame),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _download(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """The only function in the app that touches the network."""
    try:
        import yfinance
    except ImportError as exc:  # pragma: no cover - install-time problem
        raise FetchError("yfinance is not installed — run: pip install yfinance") from exc

    try:
        raw = yfinance.download(
            symbol,
            period=period,
            interval=interval,
            # Split/dividend adjusted, so backtests don't see phantom gaps on
            # split dates. The default has flipped between releases; be explicit.
            auto_adjust=True,
            # Defaults to True even for one ticker, which yields MultiIndex
            # columns and breaks every downstream frame["close"].
            multi_level_index=False,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        raise FetchError(f"Download failed: {exc}") from exc

    # An empty frame is Yahoo's way of reporting both a bad symbol and an
    # out-of-range request, so say which one this probably is.
    if raw is None or raw.empty:
        if interval in INTRADAY and period not in INTRADAY_PERIODS:
            raise InvalidRange(
                f"Yahoo only serves {interval} bars for the last "
                f"{INTRADAY_MAX_DAYS} days — {period!r} is too far back. "
                f"Try {', '.join(INTRADAY_PERIODS)}."
            )
        raise UnknownSymbol(
            f"Yahoo returned no data for {symbol!r} at {interval} bars. Check the "
            "symbol — crypto looks like BTC-USD and FX like EURUSD=X."
        )

    frame = data.normalise(raw.reset_index())
    if frame.empty:
        raise UnknownSymbol(f"No usable rows for {symbol!r}.")
    return frame


def fetch(
    symbol: str,
    period: str = "5y",
    interval: str = "1d",
    force: bool = False,
) -> tuple[pd.DataFrame, CacheEntry]:
    """Daily bars for `symbol`, from cache when possible.

    Returns the frame plus the cache metadata so the UI can show how old the
    data is. Raises FetchError (or UnknownSymbol) with a message fit to
    display; on a network failure a usable cached copy is preferred over
    raising, so the app keeps working offline.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise FetchError("Enter a ticker symbol.")

    cached = read_cache(symbol, interval)

    if cached and not force:
        frame, entry = cached
        if entry.is_fresh:
            return frame, entry

    try:
        frame = _download(symbol, period, interval)
    except RequestError:
        # A bad symbol or an impossible range is a user error — don't paper
        # over it with cached data that answers a different question.
        raise
    except FetchError:
        if cached:
            return cached  # offline, but we have something to show
        raise

    if cached:
        # Keep the widest range we've ever seen: a "1y" fetch shouldn't
        # discard a "max" pull from yesterday.
        merged = pd.concat([cached[0], frame], ignore_index=True)
        merged = merged.drop_duplicates(subset="date", keep="last")
        frame = merged.sort_values("date").reset_index(drop=True)

    _write_cache(symbol, interval, frame)
    result = read_cache(symbol, interval)
    if result is None:  # pragma: no cover - only if the disk write failed
        return frame, CacheEntry(
            symbol=symbol, interval=interval, rows=len(frame),
            start=frame["date"].iloc[0].date(), end=frame["date"].iloc[-1].date(),
            fetched_at=dt.datetime.now(),
        )
    return result


def cache_entries() -> list[CacheEntry]:
    """Everything currently cached, newest first."""
    if not CACHE_DIR.exists():
        return []
    entries = []
    for meta_path in CACHE_DIR.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        found = read_cache(meta["symbol"], meta["interval"])
        if found:
            entries.append(found[1])
    return sorted(entries, key=lambda e: e.fetched_at, reverse=True)


def clear_cache(symbol: str | None = None, interval: str = "1d") -> int:
    """Delete cached data. Returns the number of files removed."""
    if not CACHE_DIR.exists():
        return 0
    if symbol is None:
        targets = list(CACHE_DIR.glob("*.csv")) + list(CACHE_DIR.glob("*.meta.json"))
    else:
        targets = [p for p in _paths(symbol, interval) if p.exists()]
    for path in targets:
        path.unlink(missing_ok=True)
    return len(targets)
