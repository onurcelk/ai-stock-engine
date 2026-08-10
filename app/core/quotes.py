"""Last price and change for a list of symbols, read straight off the cache.

The watchlist rail wants a dozen quotes on every rerun, and `live.fetch()` is
the wrong tool for that twice over: it parses a full OHLCV history — up to a
decade of bars — to read two numbers off the end, and it will go to the
network to do it. A rail that quietly fires a dozen downloads is how an app
gets rate-limited, and a failure there has nowhere to be reported anyway.

So this module reads the cache files directly with `usecols`, and never
downloads. Only the symbol actually on screen is allowed to hit the network,
from the sidebar, where its error message has somewhere to go. A symbol with
no cache entry comes back as a quote-less row: still listed, still clickable,
and fetched properly once it is the one being looked at.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json

import pandas as pd

from . import live

# Suffixes Yahoo uses to say what a symbol is. Everything else is an equity,
# which is a guess — but it is the guess Yahoo's own symbol space makes, and
# it is the only asset class fact derivable without a fundamentals call.
FX_SUFFIX = "=X"
CRYPTO_QUOTES = ("-USD", "-EUR", "-GBP", "-USDT")


@dataclasses.dataclass(frozen=True)
class Quote:
    symbol: str
    last: float
    change: float
    change_pct: float
    stamp: dt.datetime
    asset: str

    @property
    def currency(self) -> str:
        return currency(self.symbol)


def currency(symbol: str) -> str:
    """What the price is quoted in, where the symbol says so.

    Yahoo encodes the quote currency in FX and crypto tickers and nowhere
    else, so an equity is assumed to be in dollars — wrong for a London or
    Istanbul listing, and the reason this is a caption rather than a label on
    the number itself.
    """
    symbol = symbol.upper()
    if symbol.endswith(FX_SUFFIX):
        return symbol[:-2][-3:]
    for suffix in CRYPTO_QUOTES:
        if symbol.endswith(suffix):
            return suffix[1:]
    return "USD"


def asset_class(symbol: str) -> str:
    symbol = symbol.upper()
    if symbol.endswith(FX_SUFFIX):
        return "FX"
    if symbol.endswith(CRYPTO_QUOTES):
        return "CRYPTO"
    return "EQUITY"


def cached_symbols(interval: str = "1d") -> list[str]:
    """Symbols already downloaded at this interval, most recently fetched first.

    Read from the sidecar metadata rather than the filenames, because the
    filenames are sanitised — EURUSD=X is stored as EURUSD_X — and a watchlist
    row has to link back to the symbol Yahoo actually knows.
    """
    directory = live.CACHE_DIR
    if not directory.exists():
        return []
    found: list[tuple[dt.datetime, str]] = []
    for path in directory.glob(f"*__{interval}.meta.json"):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            found.append((dt.datetime.fromisoformat(meta["fetched_at"]), meta["symbol"]))
        except Exception:
            continue  # a half-written sidecar must not empty the watchlist
    found.sort(reverse=True)
    return list(dict.fromkeys(symbol for _, symbol in found))


def read_quote(symbol: str, interval: str = "1d") -> Quote | None:
    """The last close and its move, or None if this symbol isn't cached."""
    path = live.cache_path(symbol, interval)
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path, usecols=["date", "close"])
        frame = frame.dropna()
        if len(frame) < 2:
            return None
        closes = pd.to_numeric(frame["close"], errors="coerce").dropna()
        if len(closes) < 2:
            return None
        last = float(closes.iloc[-1])
        previous = float(closes.iloc[-2])
        stamp = pd.to_datetime(frame["date"].iloc[-1])
    except Exception:
        # A corrupt cache file drops one row from the board, nothing more.
        return None

    change = last - previous
    return Quote(
        symbol=symbol.upper(),
        last=last,
        change=change,
        change_pct=change / previous * 100 if previous else 0.0,
        stamp=stamp.to_pydatetime(),
        asset=asset_class(symbol),
    )


def last_close(symbol: str, interval: str = "1d") -> float | None:
    """The most recent close we already hold for a symbol, or None.

    The trade ticket prefills its price field from this. Deliberately cache
    only — a ticket that fired a download on every keystroke would be the
    rail's original mistake made in a place where it costs money.
    """
    if not symbol or not symbol.strip():
        return None
    quote = read_quote(symbol, interval)
    if quote is None and interval != "1d":
        quote = read_quote(symbol, "1d")
    return quote.last if quote else None


def board(symbols: list[str], interval: str = "1d") -> list[dict]:
    """Watchlist rows, in the order given, uncached symbols included.

    Returns plain dicts rather than Quotes because this feeds
    `theme.watchlist()` and Streamlit's `cache_data`, and both are happier
    with something trivially serialisable.
    """
    rows: list[dict] = []
    for symbol in dict.fromkeys(s.upper() for s in symbols if s.strip()):
        quote = read_quote(symbol, interval)
        if quote is None:
            rows.append({"symbol": symbol, "last": None, "change": None,
                         "change_pct": None, "stamp": None})
        else:
            rows.append({
                "symbol": quote.symbol, "last": quote.last, "change": quote.change,
                "change_pct": quote.change_pct, "stamp": quote.stamp,
            })
    return rows


def watchlist_symbols(current: str, interval: str = "1d", limit: int = 14) -> list[str]:
    """What to show in the rail: this symbol, then what you've looked at, then the picks.

    The quick picks come last so a fresh clone still has something on the
    board — they double as documentation for Yahoo's symbol conventions,
    which was their original job in the sidebar.
    """
    ordered = [current.upper()] if current.strip() else []
    ordered += cached_symbols(interval)
    ordered += live.QUICK_PICKS
    return list(dict.fromkeys(s for s in ordered if s))[:limit]
