"""The options premium screen: live quotes, read-only, never backtested.

Commissioned 2026-08-24 under `reports/OPTIONS1_ADMISSIBILITY.md` §4's second
path -- "scope the options track down to what free data can support" -- after
the account holder was shown §3's Stage 1 FAIL and chose it over amending the
free-data-only rule. What free data supports is a description of what is
quoted right now. It does not support a P&L, a margin model, a tail-risk
simulation or any backtest, and none of those appear here or may be added
later without a data-source decision that is the account holder's to make.

Everything delegates to `core.options`, which carries the reasoning and the
`WARNING` string. This file adds routing and nothing else -- no yield
arithmetic is restated here, for the same reason `routers/strategies.py`
restates no signal maths.

**These are GETs and they are safe in fact, not merely by convention.** No
ledger, no book, no saved run, no forecast. A premium screen must never be
recordable as a prospective call: `app/forecast_ledger.sqlite3` is append-only
and never regenerable, and its whole value is that every row is a deliberate
forecast on a series that can be replayed against real subsequent prices. An
options snapshot can never be replayed, because expired contracts do not exist
at any free source. `api/tests/test_options.py` asserts this module names
neither `holdings`, `ledger_activation` nor `forecast_ledger`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core import live, options

from ..schemas import to_jsonable

router = APIRouter()

#: The two ways of being short premium that a cash account can actually hold.
#: Naked calls and spreads are deliberately absent: both need a margin model
#: to describe honestly, and a margin model needs the historical implied-vol
#: surface that §3 established does not exist for free.
KINDS = {
    options.CASH_SECURED_PUT: {
        "name": "Cash-secured put",
        "describe": "Sell a put and hold the strike in cash. Collateral is "
                    "the strike; assignment means buying the shares.",
    },
    options.COVERED_CALL: {
        "name": "Covered call",
        "describe": "Sell a call against shares you hold. Collateral is the "
                    "shares; assignment means selling them at the strike.",
    },
}


@router.get("/api/options/kinds")
def get_kinds() -> dict:
    """What this screen can describe, and what it deliberately cannot."""
    return {
        "kinds": [{"key": key, **value} for key, value in KINDS.items()],
        "backtestable": False,
        "WARNING": options.WARNING,
    }


@router.get("/api/options/{symbol}/expiries")
def get_expiries(symbol: str) -> dict:
    """Expiries currently listed. An empty list is an answer, not a failure."""
    try:
        listed = options.expiries(symbol)
    except live.FetchError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {
        "symbol": symbol.strip().upper(),
        "expiries": [value.isoformat() for value in listed],
        "WARNING": options.WARNING,
    }


@router.get("/api/options/{symbol}/screen")
def get_screen(
    symbol: str,
    kind: str = Query(options.CASH_SECURED_PUT,
                      description="cash_secured_put or covered_call."),
    expiry: str | None = Query(None, description="ISO date. Defaults to the "
                                                 "nearest listed expiry."),
    min_open_interest: int = Query(0, ge=0, description="Drop strikes with "
                                   "less open interest than this."),
    out_of_the_money_only: bool = Query(True, description="Keep only strikes "
                                        "that are out of the money. On by "
                                        "default: an in-the-money short "
                                        "option is a directional position, "
                                        "not premium harvesting, and it "
                                        "quotes the largest premium on the "
                                        "board precisely because it is "
                                        "expected to be assigned."),
) -> dict:
    """One expiry's strikes, ranked by the premium they quote right now.

    The ranking is of quotes. It is not a recommendation and not a measured
    edge -- `WARNING` travels in the payload saying so, and the frontend is
    expected to render it rather than drop it.
    """
    if kind not in KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown screen {kind!r}. Try: {', '.join(KINDS)}")

    try:
        quoted = options.chain(symbol, expiry)
        table = options.premium_screen(
            quoted, kind=kind, min_open_interest=min_open_interest,
            out_of_the_money_only=out_of_the_money_only)
    except live.UnknownSymbol as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except live.FetchError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return to_jsonable(options.screen_payload(
        quoted, table, kind, out_of_the_money_only=out_of_the_money_only))
