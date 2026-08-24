"""Named lists of symbols: the index and exchange universes a scan can run over.

Until this module the desk could only scan lists it already had -- the curated
watchlist, the book, whatever was in the price cache. All three are lists of
things somebody had already looked at, which is exactly the wrong shape for the
question "what should I be looking at?". A screen whose universe is the names
you already like cannot tell you about the ones you do not.

Four universes, each from a source that publishes a machine-readable list:

* **S&P 500** -- read from `alpha/cache/_meta/sp500_current.csv`, which the
  research programme already froze from Wikipedia's constituent table. Reused
  rather than re-downloaded, so the desk and its own research record cannot
  disagree about who is in the index, and so this universe needs no network at
  all. If that file is absent the universe is simply unavailable; this module
  does not silently fall back to a second, different S&P list.
* **NASDAQ** and **NYSE** -- Nasdaq Trader's official symbol directory files,
  `nasdaqlisted.txt` and `otherlisted.txt`. Pipe-delimited, updated nightly,
  and carrying the two flags that make them usable: a test-issue marker and an
  ETF marker.
* **London (FTSE 100)** -- Wikipedia's constituent table, parsed with the
  standard library because `lxml` is not installed in the serving venv and a
  universe list is not worth a new dependency.

**Why not "all of the London Stock Exchange", or all of NYSE including funds.**
The engine reads one symbol at a time and each read is a download. A list is
only worth offering if scanning it is possible, so the exchange universes are
filtered to operating companies (test issues and ETFs dropped) and London is
the FTSE 100 rather than the ~2,000 names the exchange lists, since there is no
free machine-readable file for the rest and a guessed list is worse than none.

**Nothing here downloads on import, and nothing downloads on a page load.**
`cached()` reads what is on disk and reports what is missing; `fetch()` is the
one function that touches the network, and the scan job calls it deliberately.
That is the same rule `core.watchlist` and `core.quotes` follow -- the board
never downloads -- for the same reason: a GET that quietly makes network calls
is a GET that fails in ways the person who triggered it cannot explain.

Lists are cached to `app/cache/universes/<key>.json` with the timestamp they
were fetched at, and they go stale rather than expiring: an index changes a few
times a year, so a list from last month is a fact worth stating, not a reason
to refuse to scan.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib
import urllib.request
from html.parser import HTMLParser

from . import live

CACHE_DIR = live.CACHE_DIR / "universes"

#: Where the research programme keeps its frozen S&P 500 constituent table.
#: A file read, deliberately not an import of `alpha.membership`: the product
#: surface reusing one CSV the research side already froze is reuse; the API
#: depending on the research package's code would be a new direction of
#: dependency that nothing else here has.
SP500_FROZEN = (pathlib.Path(__file__).resolve().parents[2]
                / "alpha" / "cache" / "_meta" / "sp500_current.csv")

_UA = {"User-Agent": "Mozilla/5.0 (trading desk; symbol directory)"}
_TIMEOUT = 90

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
FTSE_URL = "https://en.wikipedia.org/wiki/FTSE_100_Index"

#: A list older than this is reported stale. Not an expiry -- index membership
#: changes a handful of times a year, and refusing to scan on a three-week-old
#: constituent list would be a worse answer than scanning on one.
STALE_AFTER = dt.timedelta(days=30)


class UniverseError(RuntimeError):
    """A list could not be built, with a sentence saying why."""


@dataclasses.dataclass
class Listing:
    key: str
    symbols: list[str]
    fetched_at: dt.datetime | None
    source: str
    #: Rows the source carried that this list deliberately does not: test
    #: issues, funds, symbols Yahoo has no form of. Reported, never hidden.
    excluded: dict[str, int] = dataclasses.field(default_factory=dict)

    @property
    def stale(self) -> bool:
        if self.fetched_at is None:
            return True
        return dt.datetime.now() - self.fetched_at > STALE_AFTER

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "symbols": self.symbols,
            "count": len(self.symbols),
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "source": self.source,
            "excluded": self.excluded,
            "stale": self.stale,
        }


# ------------------------------------------------------------------ symbols


def to_yahoo(symbol: str) -> str | None:
    """A directory ticker in Yahoo's spelling, or None if it has none.

    Class shares are dotted on the exchange and hyphenated at Yahoo (BRK.B ->
    BRK-B). Preferred shares, warrants, units and rights carry `$`, `+`, `=` or
    `^` and have no dependable Yahoo form, so they are dropped rather than
    guessed at -- a guessed ticker becomes an unreadable row in every scan
    forever.
    """
    ticker = str(symbol).strip().upper()
    if not ticker or any(ch in ticker for ch in "$+=^ "):
        return None
    return ticker.replace(".", "-")


#: NASDAQ's fifth-letter convention and the NYSE's hyphenated equivalent, for
#: the three classes that are not a company: units, warrants and rights. These
#: are the bulk of a SPAC's footprint in the directory and none of them is
#: something a 4-hour trend reading means anything about.
#:
#: Deliberately only these three. `L` and `B` are also fifth letters, and
#: dropping them would take GOOGL and BRK-B with them -- the filter has to be
#: narrower than the convention, or it removes real companies.
_DERIVATIVE_SUFFIXES = ("U", "W", "R")


def is_derivative(symbol: str) -> bool:
    """A unit, warrant or right rather than a share in a company."""
    ticker = str(symbol).strip().upper()
    if "-" in ticker:
        head, _, tail = ticker.rpartition("-")
        return bool(head) and tail in _DERIVATIVE_SUFFIXES
    return len(ticker) == 5 and ticker[-1] in _DERIVATIVE_SUFFIXES


def _pipe_rows(text: str) -> list[dict]:
    """Nasdaq Trader's format: pipe-delimited, with a trailing file-stamp line."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise UniverseError("the symbol directory came back empty")
    header = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            continue
        parts = line.split("|")
        if len(parts) != len(header):
            continue
        rows.append(dict(zip(header, (p.strip() for p in parts))))
    return rows


def _read(url: str) -> str:
    try:
        request = urllib.request.Request(url, headers=_UA)
        return urllib.request.urlopen(request, timeout=_TIMEOUT).read().decode(
            "utf-8", "replace")
    except Exception as error:                                    # noqa: BLE001
        raise UniverseError(f"could not download {url}: {error}") from error


class _Tables(HTMLParser):
    """Every HTML table as rows of cell text. Enough for one Wikipedia list."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


# ------------------------------------------------------------- the four lists


def _sp500() -> Listing:
    if not SP500_FROZEN.exists():
        raise UniverseError(
            "the S&P 500 constituent table has not been frozen yet. It lives at "
            f"{SP500_FROZEN.name} and is written by the research programme's "
            "`alpha.membership.refresh()`."
        )
    lines = SP500_FROZEN.read_text(encoding="utf-8").splitlines()
    header = [h.strip().lower() for h in lines[0].split(",")]
    index = header.index("ticker")
    symbols, dropped = [], 0
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) <= index:
            continue
        symbol = to_yahoo(parts[index])
        if symbol:
            symbols.append(symbol)
        else:
            dropped += 1
    stamp = dt.datetime.fromtimestamp(SP500_FROZEN.stat().st_mtime)
    return Listing("sp500", list(dict.fromkeys(symbols)), stamp,
                   f"{SP500_FROZEN.name} (frozen by alpha.membership)",
                   {"no Yahoo form": dropped})


def _from_directory(key: str, url: str, symbol_column: str,
                    keep) -> Listing:
    """One Nasdaq Trader file, filtered to operating companies."""
    rows = _pipe_rows(_read(url))
    symbols: list[str] = []
    excluded = {"test issues": 0, "funds": 0, "units, warrants, rights": 0,
                "no Yahoo form": 0, "other venues": 0}
    for row in rows:
        if row.get("Test Issue") == "Y":
            excluded["test issues"] += 1
            continue
        if not keep(row):
            excluded["other venues"] += 1
            continue
        if row.get("ETF") == "Y":
            excluded["funds"] += 1
            continue
        symbol = to_yahoo(row.get(symbol_column, ""))
        if symbol is None:
            excluded["no Yahoo form"] += 1
            continue
        if is_derivative(symbol):
            excluded["units, warrants, rights"] += 1
            continue
        symbols.append(symbol)
    return Listing(key, list(dict.fromkeys(symbols)), dt.datetime.now(), url,
                   excluded)


def _nasdaq() -> Listing:
    return _from_directory("nasdaq", NASDAQ_URL, "Symbol", lambda row: True)


def _nyse() -> Listing:
    # `otherlisted` carries every venue that is not NASDAQ; `N` is the NYSE
    # proper. `A` (NYSE American) and `P` (Arca, which is nearly all funds) are
    # left out rather than folded in, so "NYSE" means what it says.
    return _from_directory("nyse", OTHER_URL, "ACT Symbol",
                           lambda row: row.get("Exchange") == "N")


def _lse() -> Listing:
    parser = _Tables()
    parser.feed(_read(FTSE_URL))
    for table in parser.tables:
        if not table:
            continue
        head = [cell.lower() for cell in table[0]]
        column = next((i for i, cell in enumerate(head)
                       if "ticker" in cell or "epic" in cell), None)
        if column is None or len(table) < 50:
            continue
        symbols, dropped = [], 0
        for row in table[1:]:
            if len(row) <= column:
                continue
            code = to_yahoo(row[column])
            # Yahoo spells London lines with a `.L` suffix, and a dotted class
            # share has already become hyphenated above.
            if code:
                symbols.append(f"{code}.L")
            else:
                dropped += 1
        return Listing("lse", list(dict.fromkeys(symbols)), dt.datetime.now(),
                       FTSE_URL, {"no Yahoo form": dropped})
    raise UniverseError(
        "could not find the constituent table on the FTSE 100 page. The page "
        "layout has changed; the list has not been updated."
    )


#: Everything a scan may be run over, in the order a page should offer them.
#: `describe` is the sentence the page shows, and it states the limit of the
#: list rather than selling it.
CATALOGUE: dict[str, dict] = {
    "sp500": {
        "label": "S&P 500",
        "builder": _sp500,
        "describe": "The 503 index constituents, read from the table the "
                    "research side already froze. Needs no download.",
        "needs_network": False,
    },
    "nasdaq": {
        "label": "NASDAQ",
        "builder": _nasdaq,
        "describe": "Every operating company NASDAQ lists, from Nasdaq "
                    "Trader's nightly symbol directory. Test issues and funds "
                    "are dropped.",
        "needs_network": True,
    },
    "nyse": {
        "label": "NYSE",
        "builder": _nyse,
        "describe": "Every operating company listed on the NYSE proper. NYSE "
                    "American and Arca are not folded in.",
        "needs_network": True,
    },
    "lse": {
        "label": "London (FTSE 100)",
        "builder": _lse,
        "describe": "The FTSE 100, in Yahoo's .L spelling. The exchange lists "
                    "far more, but publishes no free machine-readable file for "
                    "the rest, and a guessed list is worse than none.",
        "needs_network": True,
    },
}


# ------------------------------------------------------------------- storage


def _path(key: str) -> pathlib.Path:
    return CACHE_DIR / f"{key}.json"


def cached(key: str) -> Listing | None:
    """What is on disk for this list, or None. Never downloads."""
    if key not in CATALOGUE:
        return None
    path = _path(key)
    if not path.exists():
        # The S&P list is frozen elsewhere and needs no cache of its own.
        if not CATALOGUE[key]["needs_network"]:
            try:
                return CATALOGUE[key]["builder"]()
            except UniverseError:
                return None
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        stamp = body.get("fetched_at")
        return Listing(
            key=key,
            symbols=list(body.get("symbols", [])),
            fetched_at=dt.datetime.fromisoformat(stamp) if stamp else None,
            source=body.get("source", ""),
            excluded=body.get("excluded", {}),
        )
    except Exception:                                             # noqa: BLE001
        return None    # a half-written file must not break the page


def fetch(key: str, *, force: bool = False) -> Listing:
    """The list, downloading it if it is missing or `force` is set.

    The only function here that touches the network. A caller that must not
    download -- anything serving a GET -- calls `cached` instead and reports
    the absence.
    """
    if key not in CATALOGUE:
        raise UniverseError(f"unknown universe {key!r}")
    if not force:
        found = cached(key)
        if found is not None and found.symbols:
            return found

    listing = CATALOGUE[key]["builder"]()
    if not listing.symbols:
        raise UniverseError(f"{CATALOGUE[key]['label']} came back with no symbols")

    if CATALOGUE[key]["needs_network"]:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _path(key).write_text(json.dumps({
            "symbols": listing.symbols,
            "fetched_at": (listing.fetched_at or dt.datetime.now()).isoformat(),
            "source": listing.source,
            "excluded": listing.excluded,
        }, indent=2), encoding="utf-8")
    return listing


def catalogue() -> list[dict]:
    """Every list, with what is known about it without downloading anything."""
    out = []
    for key, entry in CATALOGUE.items():
        listing = cached(key)
        out.append({
            "key": key,
            "label": entry["label"],
            "describe": entry["describe"],
            "needs_network": entry["needs_network"],
            "count": len(listing.symbols) if listing else None,
            "fetched_at": (listing.fetched_at.isoformat()
                           if listing and listing.fetched_at else None),
            "stale": listing.stale if listing else True,
            "source": listing.source if listing else "",
            "excluded": listing.excluded if listing else {},
        })
    return out
