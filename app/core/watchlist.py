"""The saved watchlist: the symbols a person put on the board, on disk.

`core.quotes.watchlist_symbols` *derives* a board — the symbol on screen, then
whatever is in the cache, then the quick picks. That is a good default and a
poor list: it cannot be added to, and removing something from it means
deleting a cache file. This module is the other half, the list someone
actually curates.

The two are kept apart rather than merged, because the difference between them
is the difference between "we guessed" and "you said", and only one of those
may be silently rewritten. So the store has two states and the API reports
which one is in force:

* **auto** — no file. The derived board, exactly as before. A fresh clone still
  shows something, which was the derived board's whole job.
* **custom** — a file exists. The board is exactly what it says, in the order
  it says, including empty. `clear()` writes an empty list and stays custom,
  so a board someone emptied stays empty instead of quietly refilling itself
  from the cache; `reset()` deletes the file and hands the board back to the
  derived default.

Nothing here downloads or reads a price. It stores names. Pricing them is
`core.quotes.board`'s job and it remains cache-only.
"""

from __future__ import annotations

import json
import pathlib

#: Beside the book and the ledger, for the same reason: it is user state, not
#: research state, and it is regenerable — losing it costs a list, not a record.
STORE = pathlib.Path(__file__).resolve().parents[1] / "watchlist.json"

#: A board is a rail, not a portfolio. The cap is here so a malformed write or
#: an enthusiastic script cannot turn one page into several hundred cache reads.
MAX_SYMBOLS = 50


def _store(path: pathlib.Path | None) -> pathlib.Path:
    """Resolve the store at call time, so a test can redirect it.

    Same reasoning as `holdings._store`: a default bound in the signature is
    bound at import, and monkeypatching the module attribute would then have
    no effect on the running app.
    """
    return STORE if path is None else path


def normalise(symbols: list[str]) -> list[str]:
    """Upper-cased, blank-free, first-occurrence-wins, capped."""
    seen = (str(s).strip().upper() for s in symbols)
    return list(dict.fromkeys(s for s in seen if s))[:MAX_SYMBOLS]


def saved(path: pathlib.Path | None = None) -> list[str] | None:
    """The curated list, or None when there is not one.

    None and `[]` are different answers and the caller has to tell them apart:
    None means nobody has touched the board, `[]` means somebody emptied it.
    """
    path = _store(path)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt file falls back to the derived board rather than to an
        # empty one: showing the default is recoverable, showing nothing looks
        # like the feature broke.
        return None
    symbols = raw.get("symbols") if isinstance(raw, dict) else raw
    if not isinstance(symbols, list):
        return None
    return normalise(symbols)


def save(symbols: list[str], path: pathlib.Path | None = None) -> list[str]:
    """Write the list, creating the file — which is what switches on custom."""
    path = _store(path)
    cleaned = normalise(symbols)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"symbols": cleaned}, indent=2), encoding="utf-8")
    return cleaned


def add(symbol: str, path: pathlib.Path | None = None,
        *, seed: list[str] | None = None) -> list[str]:
    """Put a symbol on the board, at the end.

    The first add is where a derived board becomes a real one: `seed` is what
    was on screen at the time, so adding one name to the default keeps the
    other rows instead of replacing thirteen of them with one. Adding a symbol
    already on the board is a no-op rather than a duplicate or an error — the
    button is idempotent because the request may well be a double click.
    """
    wanted = str(symbol).strip().upper()
    if not wanted:
        raise ValueError("A watchlist entry needs a symbol.")
    current = saved(path)
    if current is None:
        current = normalise(seed or [])
    if wanted in current:
        return save(current, path)
    if len(current) >= MAX_SYMBOLS:
        raise ValueError(
            f"The watchlist holds {MAX_SYMBOLS} symbols; remove one first.")
    return save(current + [wanted], path)


def remove(symbol: str, path: pathlib.Path | None = None,
           *, seed: list[str] | None = None) -> list[str]:
    """Take a symbol off the board.

    Removing from a derived board materialises it first, for the same reason
    `add` does: otherwise the row comes straight back on the next read.
    """
    wanted = str(symbol).strip().upper()
    current = saved(path)
    if current is None:
        current = normalise(seed or [])
    return save([s for s in current if s != wanted], path)


def clear(path: pathlib.Path | None = None) -> list[str]:
    """Empty the board and keep it custom, so it stays empty."""
    return save([], path)


def reset(path: pathlib.Path | None = None) -> None:
    """Delete the file: the board goes back to the derived default."""
    path = _store(path)
    path.unlink(missing_ok=True)
