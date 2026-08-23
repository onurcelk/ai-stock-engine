"""Phase 6f: the quote board, from the cache and only from the cache.

`core.quotes`'s own docstring is the specification, and it is worth restating
because the obvious implementation of this endpoint would break it: a board of
a dozen symbols must never call `live.fetch`. That function parses a full OHLCV
history -- up to a decade of bars -- to read two numbers off the end, and it
will go to the network to do it. A rail that quietly fires a dozen downloads is
how an app gets rate-limited, and a failure there has nowhere to be reported.

So `quotes.board` reads the cache files directly and never downloads, and this
router adds nothing to that. A symbol with no cache entry comes back as a
quote-less row -- still listed, still selectable -- rather than being dropped
or triggering a fetch to fill it in. That is the honest state: "not downloaded
yet" is different from "no such symbol", and only one of them is worth hiding.

Which is also why the board can look empty on a fresh clone. Nothing here
populates the cache; the symbol actually being looked at populates it, through
the Signal or Chart page, where a fetch failure has somewhere to go. The quick
picks are appended last so a new checkout still shows something, which was
their original job in the sidebar.

It writes nothing. It does not even read a symbol into the cache.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from core import quotes

from ..bars import DEFAULT_INTERVAL

router = APIRouter()


@router.get("/api/watchlist")
def get_watchlist(
    symbol: str = Query("", description="The symbol being looked at; leads the "
                                        "board when given."),
    interval: str = DEFAULT_INTERVAL,
    limit: int = Query(14, ge=1, le=50),
) -> dict:
    """The rail: this symbol, then what has been looked at, then the picks."""
    names = quotes.watchlist_symbols(symbol, interval, limit)
    rows = quotes.board(names, interval)

    return {
        "interval": interval,
        "active": symbol.strip().upper(),
        # `asset` and `currency` are derived from the ticker's own suffix --
        # the only asset-class fact available without a fundamentals call, and
        # the guess Yahoo's own symbol space already makes.
        "quotes": [
            {
                **row,
                "stamp": str(row["stamp"]) if row["stamp"] else None,
                "asset": quotes.asset_class(row["symbol"]),
                "currency": quotes.currency(row["symbol"]),
                # Explicit, because a row with `last: null` is a real state and
                # a page that treated it as an error would hide a symbol that
                # is merely not downloaded yet.
                "cached": row["last"] is not None,
            }
            for row in rows
        ],
        "source": "cache only -- this endpoint never downloads",
    }
