"""The market scan: one horizon, a whole universe, sorted by what it reads.

Every other reading endpoint answers "what does this symbol say?". This one
answers the question that comes before it -- *which* symbol -- by running the
same engine across a list and keeping the calls that cleared the bands.

Three things about it are deliberate, and all three are the difference between
a scan worth acting on and a screen that flatters itself:

**One horizon, chosen.** `ultimate.evaluate` reads all three timeframes by
default, which costs three downloads a symbol. A scan of a fifty-name board is
then a hundred and fifty requests to Yahoo, and Yahoo rate-limits. Narrowing to
one horizon is not an approximation of the full reading -- each horizon is
still scored on its own bars at its own depth -- so a row here and the Signal
page's card for the same timeframe are the same number computed by the same
code on the same bars.

The loop over symbols is written here rather than by giving `ultimate.scan` a
`horizons=` argument, which is where it would naturally belong. `evaluate`
already takes one; `scan` does not, and adding it would edit
`app/core/ultimate.py` -- whose sha256 *is* the engine's identity in the
forecast ledger (CLAUDE.md 1.2, 8). Re-versioning the live incumbent, and
splitting the prospective record in two, is not a price worth paying for a
convenience argument. So this file pays for it in eight lines of its own
instead, and `ultimate.py` is untouched.

**Nothing is filtered away server-side.** The response carries every symbol
asked for, including HOLDs, unreadable ones and outright failures, each with
its reason. Returning only the buys would make the page a list of winners with
no denominator -- eight BUYs out of twelve and eight out of two hundred are
different facts, and only one of them is a screen worth trusting. The page
filters; the endpoint reports.

**A universe is a named list.** Two kinds are offered, and the difference
matters. The desk's own lists -- the curated watchlist, the book, the price
cache, the quick picks -- are lists of names somebody already looked at, which
is the wrong shape for "what should I be looking at?". The market lists in
`core.universes` are the other kind: the S&P 500, every operating company on
NASDAQ and on the NYSE, and the FTSE 100, from sources that publish a
machine-readable file.

What is still not on offer is "the whole market". There is no free screener
behind this desk, the engine reads one symbol at a time, and a symbol is a
download -- so the exchange lists drop funds, test issues, units, warrants and
rights, and London is the FTSE 100 rather than a guessed list of everything the
exchange quotes. `source` on the response says which list was really read.

This endpoint writes nothing. It never freezes a forecast: a scan reads dozens
of symbols nobody chose individually, and recording those as prospective calls
would flood the one ledger whose value is that a person chose each cutoff.

**What is known about the 4-hour horizon travels with the response.** PIT-1
measured it *inverted* when read after the close -- 20.8% on acted calls,
p = 0.009 -- and `replay_study.STUDY_HORIZONS` leaves it out for that reason
and because two years of hourly bars is not a historical grid. A page that
ranked 4-hour BUYs without saying so would be the most misleading surface on
the desk, so `caveats` below is part of the payload rather than a footnote
somebody may forget to render.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import holdings, live, quotes, ultimate, universes, watchlist

from ..jobs import REGISTRY as JOBS, Job
from ..schemas import to_jsonable

router = APIRouter()

SCAN = "scan"

#: The most symbols one scan may take. A guard against a malformed request,
#: not a policy: NASDAQ alone is ~3,600 operating companies and scanning all of
#: them is a supported thing to ask for. Deliberately not
#: `watchlist.normalise`'s cap, which bounds a *board*.
MAX_SYMBOLS = 5_000

#: Measured, not guessed: 20 cold S&P names at the 4-hour horizon took 0.28s
#: each end to end on 2026-08-23, download included. The page multiplies this
#: by the symbol count so "scan NASDAQ" comes with its price in minutes
#: attached, rather than looking like a button that does nothing for a quarter
#: of an hour.
SECONDS_PER_SYMBOL = 0.3

#: Roughly what one symbol's hourly bars occupy in `app/cache` once fetched.
#: A 3,600-name scan is not just time, it is about two gigabytes of disk, and
#: that is worth knowing before rather than after.
CACHE_BYTES_PER_SYMBOL = 500_000

#: How many contributing sources a row names. The whole reading is on the
#: Signal page -- this is enough to see *why* a row is near the top without
#: turning a scan of fifty symbols into fifty full verdicts on screen.
TOP_SOURCES = 3

#: Sort order for the table: the strongest calls first, then by score. Rank is
#: separate from score on purpose -- confidence gates the action, so a +55 at
#: 20% confidence is a BUY and a +45 at 40% is a STRONG BUY, and the stronger
#: call belongs above the bigger number.
ACTION_RANK = {
    ultimate.STRONG_BUY: 4,
    ultimate.BUY: 3,
    ultimate.HOLD: 2,
    ultimate.SELL: 1,
    ultimate.STRONG_SELL: 0,
}

BUY_ACTIONS = [ultimate.BUY, ultimate.STRONG_BUY]


def _normalise(symbols: list[str]) -> list[str]:
    """Upper-cased, blank-free, first-occurrence-wins, capped at MAX_SYMBOLS."""
    seen = (str(s).strip().upper() for s in symbols)
    return list(dict.fromkeys(s for s in seen if s))[:MAX_SYMBOLS]


# ------------------------------------------------------------------ universes


def _cached_symbols() -> list[str]:
    """Everything in the price cache, at any interval, most recent first.

    Merged across intervals rather than read at one: a symbol looked at on the
    daily chart is a symbol this desk has an opinion about, and refusing to
    scan it because it has no hourly file yet would hide it behind an
    implementation detail of the cache.
    """
    seen: list[str] = []
    for interval in live.INTERVALS.values():
        seen.extend(quotes.cached_symbols(interval))
    return list(dict.fromkeys(seen))


def _desk_universes() -> list[dict]:
    """The four lists this desk assembled for itself, from its own state."""
    saved = watchlist.saved()
    board = (saved if saved is not None
             else quotes.watchlist_symbols("", "1d", watchlist.MAX_SYMBOLS))
    book = [h.symbol for h in holdings.load() if h.quantity]

    return [
        {
            "key": "watchlist",
            "label": "Watchlist",
            "describe": "The board you curated on the Signal page."
                        if saved is not None else
                        "No board has been saved, so this is the derived "
                        "default: what is in the cache, then the quick picks.",
            "symbols": board,
        },
        {
            "key": "book",
            "label": "Book",
            "describe": "Every position currently held. A scan of the book "
                        "answers what to do with what you own, which is a "
                        "different question from what to buy.",
            "symbols": book,
        },
        {
            "key": "cache",
            "label": "Everything cached",
            "describe": f"Every symbol this desk has downloaded, newest first, "
                        f"capped at {MAX_SYMBOLS}. The widest list available "
                        f"without a paid screener.",
            "symbols": _cached_symbols(),
        },
        {
            "key": "picks",
            "label": "Quick picks",
            "describe": "The bundled examples. Small, always available, and "
                        "useful mainly for checking the scan works.",
            "symbols": list(live.QUICK_PICKS),
        },
    ]


def _market_universes() -> list[dict]:
    """The index and exchange lists, as `core.universes` knows them.

    `count` is None for a list that has not been downloaded yet, and that is
    the honest answer rather than a zero: nothing here downloads to answer a
    GET, so an un-fetched list has no length until a scan goes and gets it.
    """
    rows = []
    for entry in universes.catalogue():
        rows.append({
            "key": entry["key"],
            "label": entry["label"],
            "describe": entry["describe"],
            "symbols": [],          # never inlined; these run to thousands
            "count": entry["count"],
            "market": True,
            "needs_network": entry["needs_network"],
            "fetched_at": entry["fetched_at"],
            "stale": entry["stale"],
            "source": entry["source"],
            "excluded": entry["excluded"],
        })
    return rows


def _all_universes() -> list[dict]:
    """Market lists first: they are what a scan is usually for."""
    desk = [{**u, "count": len(u["symbols"]), "market": False,
             "needs_network": False, "fetched_at": None, "stale": False,
             "source": "this desk", "excluded": {}}
            for u in _desk_universes()]
    return _market_universes() + desk


@router.get("/api/scan/options")
def get_scan_options() -> dict:
    """What a scan may be run on: the horizons, and the lists to run them over.

    Served from the engine's own `HORIZONS` and from the live stores, so a
    horizon added to `ultimate` appears here and a symbol added to the board is
    in the next scan without this file being touched.
    """
    return {
        "horizons": [
            {
                "key": h.key,
                "label": h.label,
                "interval": h.interval,
                "bars": h.bars,
                "period": h.period,
                "min_bars": h.min_bars,
                "caveats": _caveats(h.key),
            }
            for h in ultimate.HORIZONS
        ],
        "default_horizon": ultimate.HORIZONS[0].key,
        "universes": [
            {**u, "symbols": u["symbols"][:MAX_SYMBOLS]}
            for u in _all_universes()
        ],
        "actions": list(ultimate.ACTIONS),
        "buy_actions": list(BUY_ACTIONS),
        "max_symbols": MAX_SYMBOLS,
        "seconds_per_symbol": SECONDS_PER_SYMBOL,
        "cache_bytes_per_symbol": CACHE_BYTES_PER_SYMBOL,
        # The thresholds the calls are made against, so the page can state the
        # rule rather than describing a colour.
        "bands": {
            "act": ultimate.ACT_BAND,
            "strong": ultimate.STRONG_BAND,
            "min_confidence": ultimate.MIN_CONFIDENCE,
            "strong_confidence": ultimate.STRONG_CONFIDENCE,
        },
    }


# -------------------------------------------------------------------- the scan


class ScanRequest(BaseModel):
    """Which symbols, at which horizon.

    `symbols` wins over `universe` when both are given: a typed list is an
    explicit instruction and a universe key is a shorthand for one.
    """

    universe: str = "watchlist"
    symbols: list[str] = Field(default_factory=list)
    horizon: str = "4h"
    #: Re-download rather than reading the cache. Off by default: a scan is one
    #: request per symbol and forcing sixty of them through Yahoo at once is
    #: the reliable way to get rate-limited mid-scan.
    force: bool = False

    # Deliberately no agent toggle. The model-assisted verdict was retired
    # from the product surface at the Phase 7 cutover, and
    # `api/tests/test_cutover.py` fails on the keyword appearing anywhere in
    # `api/`. The engine default stands, which is also what the Signal page
    # gets -- so the two surfaces read the same evidence.


def _resolve_symbols(request: ScanRequest,
                     *, allow_download: bool = False) -> tuple[list[str], str]:
    """The symbols a request names, and a phrase describing where they came from.

    Called twice for a market universe, on purpose. At request time
    (`allow_download=False`) it validates the universe key and resolves
    anything already on disk, so a typo is a 400 rather than a job that fails a
    second later. Inside the job (`allow_download=True`) it may go and fetch a
    listing file, because a job is a place where downloading is expected and a
    request handler is not.
    """
    if request.symbols:
        symbols = _normalise(request.symbols)
        if not symbols:
            raise HTTPException(status_code=400,
                                detail="Nothing to scan: the list you typed is empty.")
        return symbols, "a typed list"

    known = {u["key"]: u for u in _all_universes()}
    found = known.get(request.universe)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown universe {request.universe!r}. Expected one of: "
                   f"{', '.join(known)}.",
        )
    source = found["label"]

    if found["market"]:
        try:
            listing = (universes.fetch(request.universe) if allow_download
                       else universes.cached(request.universe))
        except universes.UniverseError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if listing is None:
            # Not downloaded yet. Not an error at request time -- the job will
            # fetch it -- so hand back an empty list and let the job resolve.
            return [], source
        symbols = _normalise(listing.symbols)
    else:
        symbols = _normalise(found["symbols"])

    if not symbols and not found["market"]:
        raise HTTPException(
            status_code=400,
            detail=f"Nothing to scan: {source.lower()} is empty. Add symbols to "
                   f"it, or type a list.",
        )
    return symbols, source


#: What has actually been measured about a horizon, carried with every scan of
#: it. Quoted from `reports/EXPERIMENT_REGISTRY.md` (PIT-1) and from
#: `core.replay_study.STUDY_HORIZONS`, not paraphrased: a screen that ranks
#: 4-hour BUYs is exactly the surface where this finding has to be visible, and
#: a caveat kept only in the frontend is one refactor from being dropped.
HORIZON_CAVEATS: dict[str, list[str]] = {
    "4h": [
        "PIT-1 measured this horizon INVERTED when read after the close — "
        "20.8% on acted calls, p = 0.009 — scoped to after-close reads "
        "because every scored window straddles an overnight gap.",
        "It is deliberately excluded from the historical replay study: Yahoo "
        "serves ~2 years of hourly bars, so a PIT grid at this horizon "
        "reaches back almost nowhere and cannot re-test the finding.",
        "PIT-1 itself is resolution-bound at 12 effectively independent "
        "cutoffs, so it is evidence to respect, not a settled law to invert "
        "the calls by.",
    ],
    "1d": [
        "PIT-1: 0 of 9 components beat always-predicting-up on its own "
        "horizon, over 12 effectively independent cutoffs. The engine "
        "abstained on 74.3% of symbol-dates and that abstention was the "
        "correct output.",
    ],
    "1w": [
        "PIT-1: 0 of 9 components beat always-predicting-up on its own "
        "horizon, over 12 effectively independent cutoffs. The engine "
        "abstained on 74.3% of symbol-dates and that abstention was the "
        "correct output.",
    ],
}


def _caveats(key: str) -> list[str]:
    return HORIZON_CAVEATS.get(key, [])


def _row(symbol: str, verdict: ultimate.UltimateVerdict, key: str) -> dict:
    """One symbol's line in the table, at the horizon that was asked for.

    The horizon verdict is what is reported, not the aggregate: with a single
    horizon they are numerically identical, and reading the horizon directly
    means a scan narrowed to one timeframe cannot start quietly reporting a
    blend if this ever runs with more than one.
    """
    horizon = verdict.by_key(key)
    if horizon is None:
        reason = verdict.errors.get("all") or "; ".join(verdict.errors.values())
        return {
            "symbol": symbol, "action": ultimate.HOLD, "available": False,
            "unavailable": reason or "no reading", "score": 0.0,
            "confidence": 0.0, "last_price": None,
        }

    counted = [r for r in horizon.readings if r.counts]
    leaders = sorted(counted, key=lambda r: abs(r.contribution), reverse=True)

    return {
        "symbol": symbol,
        "action": horizon.action,
        "available": horizon.available,
        "unavailable": horizon.unavailable,
        "score": to_jsonable(horizon.score),
        "confidence": to_jsonable(horizon.confidence),
        "agreement": to_jsonable(horizon.agreement),
        "coverage": to_jsonable(horizon.coverage),
        "weighted_edge": to_jsonable(horizon.weighted_edge),
        "expected_move_pct": to_jsonable(horizon.expected_move_pct),
        "typical_move_pct": to_jsonable(horizon.typical_move_pct),
        "target_price": to_jsonable(horizon.target_price),
        "last_price": to_jsonable(horizon.last_price),
        "as_of": to_jsonable(horizon.as_of),
        "interval": horizon.interval,
        "bars_used": horizon.bars_used,
        "rows": horizon.rows,
        "sources": {"counted": len(counted), "total": len(horizon.readings)},
        "leaders": [
            {
                "name": r.name,
                "score": to_jsonable(r.score),
                "weight": to_jsonable(r.weight),
                "detail": r.detail,
            }
            for r in leaders[:TOP_SOURCES]
        ],
    }


@router.post("/api/jobs/scan", status_code=202)
def start_scan(request: ScanRequest) -> dict:
    """Read a universe at one horizon, in the background.

    A job rather than a plain GET because it is one download per symbol on a
    cold cache: sixty symbols is minutes, and `ultimate.scan` already emits the
    per-symbol progress a page needs to show it. The work runs on the same
    single worker as the trainings, so a scan queues behind one -- which is
    reported as `queued` rather than hidden, the same as everywhere else.
    """
    horizon = ultimate.HORIZON_BY_KEY.get(request.horizon)
    if horizon is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown horizon {request.horizon!r}. Expected one of: "
                   f"{', '.join(ultimate.HORIZON_BY_KEY)}.",
        )
    # Validates the universe key now, so a typo is a 400 rather than a job that
    # fails a moment later. A market list that is not on disk yet comes back
    # empty here and is fetched inside the job.
    _resolve_symbols(request)

    def work(job: Job) -> dict:
        JOBS.report(job, 0.0, "Resolving the universe")
        symbols, source = _resolve_symbols(request, allow_download=True)
        if not symbols:
            raise RuntimeError(
                f"{source} came back with no symbols to scan."
            )

        verdicts: dict[str, ultimate.UltimateVerdict] = {}
        total = len(symbols)

        for index, symbol in enumerate(symbols):
            JOBS.report(job, index / max(1, total),
                        f"{symbol} · {index + 1}/{total} at {horizon.label}")
            try:
                verdicts[symbol] = ultimate.evaluate(
                    symbol, horizons=[horizon], force=request.force,
                )
            except Exception as error:              # noqa: BLE001
                # One bad symbol is a row, not a dead scan -- the same
                # containment `ultimate.scan` applies for the same reason. A
                # symbol dropped from the table would quietly shorten a list
                # somebody is counting.
                verdicts[symbol] = ultimate.UltimateVerdict(
                    symbol=symbol, horizons=[], score=0.0, confidence=0.0,
                    alignment="none", generated_at=dt.datetime.now(),
                    errors={"all": str(error)},
                )

        rows = [_row(symbol, verdict, horizon.key)
                for symbol, verdict in verdicts.items()]
        rows.sort(key=lambda r: (ACTION_RANK.get(r["action"], 2), r["score"]),
                  reverse=True)

        counts = {action: 0 for action in ultimate.ACTIONS}
        for row in rows:
            if row["available"]:
                counts[row["action"]] = counts.get(row["action"], 0) + 1

        return {
            "horizon": {
                "key": horizon.key, "label": horizon.label,
                "interval": horizon.interval, "bars": horizon.bars,
                "period": horizon.period,
            },
            "universe": request.universe if not request.symbols else "custom",
            "source": source,
            "symbols": symbols,
            "seconds_per_symbol": SECONDS_PER_SYMBOL,
            "rows": rows,
            "counts": counts,
            "scanned": len(rows),
            "readable": sum(1 for r in rows if r["available"]),
            "buys": [r["symbol"] for r in rows if r["action"] in BUY_ACTIONS],
            "caveats": _caveats(horizon.key),
            "generated_at": dt.datetime.now().isoformat(),
        }

    job, duplicate = JOBS.submit(SCAN, request.model_dump(), work)
    return {**job.as_dict(include_result=False), "duplicate": duplicate}
