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

**The board is now editable** (`core.watchlist`), which adds writes to this
file and nothing else: the four mutations rewrite a list of names and then
re-price it through the same cache-only read. `mode` says which list is in
force -- `auto` for the derived default, `custom` once somebody has edited it
-- because a board that was emptied on purpose must not refill itself from the
cache on the next read, and a board nobody has touched should still show the
picks. `saved` travels with every response so the caller never has to guess
which rows it may remove.

The GET still writes nothing. It does not even read a symbol into the cache.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core import quotes, watchlist

from ..bars import DEFAULT_INTERVAL

router = APIRouter()


class SymbolRequest(BaseModel):
    symbol: str


def _names(symbol: str, interval: str, limit: int) -> tuple[list[str], list[str] | None]:
    """The board's symbols, and the curated list behind them if there is one.

    In custom mode the saved list *is* the board, with the symbol on screen
    led in front of it whether or not it was saved -- looking something up is
    reason enough to see its price, and it is the row the add button acts on.
    """
    saved = watchlist.saved()
    if saved is None:
        return quotes.watchlist_symbols(symbol, interval, limit), None
    current = symbol.strip().upper()
    ordered = ([current] if current else []) + saved
    return list(dict.fromkeys(ordered))[:limit], saved


def _response(symbol: str, interval: str, limit: int) -> dict:
    names, saved = _names(symbol, interval, limit)
    rows = quotes.board(names, interval)
    on_board = set(saved or [])

    return {
        "interval": interval,
        "active": symbol.strip().upper(),
        "mode": "auto" if saved is None else "custom",
        "saved": saved if saved is not None else [],
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
                # Whether this row is on the curated list, so the caller knows
                # which rows it may remove without inferring it from `mode`.
                "saved": row["symbol"] in on_board,
            }
            for row in rows
        ],
        "source": "cache only -- this endpoint never downloads",
    }


@router.get("/api/watchlist")
def get_watchlist(
    symbol: str = Query("", description="The symbol being looked at; leads the "
                                        "board when given."),
    interval: str = DEFAULT_INTERVAL,
    limit: int = Query(14, ge=1, le=50),
) -> dict:
    """The rail: this symbol, then the saved board -- or the derived default."""
    return _response(symbol, interval, limit)


@router.post("/api/watchlist")
def post_watchlist_add(
    body: SymbolRequest,
    symbol: str = Query("", description="The symbol being looked at."),
    interval: str = DEFAULT_INTERVAL,
    limit: int = Query(14, ge=1, le=50),
) -> dict:
    """Put a symbol on the board and hand back the whole board, re-priced.

    The first add seeds the saved list from what the derived board was showing,
    so adding one name to the default keeps the other rows rather than
    replacing them all with one. `quotes.watchlist_symbols` is asked for the
    seed at its own cap, not this request's `limit`: what a caller chose to
    display is not a decision to discard the rest.
    """
    seed = quotes.watchlist_symbols(symbol, interval, watchlist.MAX_SYMBOLS)
    try:
        watchlist.add(body.symbol, seed=seed)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _response(symbol, interval, limit)


@router.delete("/api/watchlist/{name}")
def delete_watchlist_entry(
    name: str,
    symbol: str = Query("", description="The symbol being looked at."),
    interval: str = DEFAULT_INTERVAL,
    limit: int = Query(14, ge=1, le=50),
) -> dict:
    """Take one symbol off the board.

    Removing from a still-derived board materialises it first -- otherwise the
    row is back on the next read, which reads as the button not working.
    """
    seed = quotes.watchlist_symbols(symbol, interval, watchlist.MAX_SYMBOLS)
    watchlist.remove(name, seed=seed)
    return _response(symbol, interval, limit)


@router.post("/api/watchlist/clear")
def post_watchlist_clear(
    symbol: str = Query("", description="The symbol being looked at."),
    interval: str = DEFAULT_INTERVAL,
    limit: int = Query(14, ge=1, le=50),
) -> dict:
    """Empty the board, and keep it empty.

    Deliberately not the same as `reset`: an emptied board stays custom, so it
    does not refill itself from the cache on the next read. The symbol on
    screen still shows, because it is what the page is about.
    """
    watchlist.clear()
    return _response(symbol, interval, limit)


@router.post("/api/watchlist/reset")
def post_watchlist_reset(
    symbol: str = Query("", description="The symbol being looked at."),
    interval: str = DEFAULT_INTERVAL,
    limit: int = Query(14, ge=1, le=50),
) -> dict:
    """Hand the board back to the derived default: this symbol, cache, picks."""
    watchlist.reset()
    return _response(symbol, interval, limit)
