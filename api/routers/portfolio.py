"""Phase 1 (read side) + Phase 2 (writes): the Portfolio endpoints.

GET /api/portfolio reuses exactly the functions `streamlit_app.py`'s
Portfolio tab calls, in the same order, so this endpoint can never disagree
with the tab for the same book: `holdings.load/load_ledger/value/realised_total`,
`portfolio.fetch_many` for pricing, and `ultimate.scan` + `ultimate.book_signal`
for the per-position calls and the book-level aggregate -- the same engine
the Signal tab uses, never a cheaper approximation (see `ultimate.scan`'s own
docstring on why: a portfolio row disagreeing with the signal tab for the
same ticker would be worse than no row at all).

POST /api/portfolio/trade calls `holdings.execute` unmodified -- "the one
place in the app that writes a position", per its own docstring -- now
guarded by `_EXECUTE_LOCK` (added alongside this endpoint) against the
concurrent-request race a single-threaded Streamlit script was never exposed
to. POST /api/portfolio/ledger/clear calls `holdings.save_ledger([])`, the
same call the roadmap named for this phase.

**Direct position editing, re-authorised by owner decision 2026-08-23.** It
was retired at the Phase 7 cutover -- `holdings.editable`/`from_frame`
rewrote the book with nothing anywhere recording that anything had changed,
so the book and the ledger could disagree and neither said which was wrong.
The reversal keeps the constraint that actually mattered and drops the
prohibition: `POST /api/portfolio/position` and `DELETE
/api/portfolio/position/{symbol}` go through the same `holdings.execute` as a
trade, take the same lock, and leave a ledger row apiece -- side `adjust` or
`discard` rather than `buy`/`sell`, because no money moved and pretending
otherwise would put invented fills in the record. `editable` and `from_frame`
themselves stay unreached: they are the version with no ledger row, and that
version is still the wrong one.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import holdings, portfolio, ultimate

from ..schemas import to_jsonable, verdict_to_dict

router = APIRouter()

DEFAULT_PERIOD = "6mo"
DEFAULT_INTERVAL = "1d"


class PositionRequest(BaseModel):
    """A position stated outright, rather than a fill that produces one."""

    symbol: str
    quantity: float = Field(gt=0)
    unit_cost: float = Field(gt=0)
    note: str = Field(default="", max_length=200)


class TradeRequest(BaseModel):
    side: str = Field(pattern="^(buy|sell)$")
    symbol: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fee: float = Field(default=0.0, ge=0)


@router.get("/api/portfolio")
def get_portfolio(period: str = DEFAULT_PERIOD, interval: str = DEFAULT_INTERVAL) -> dict:
    saved = holdings.load()
    ledger = holdings.load_ledger()

    frames, errors = portfolio.fetch_many(
        [h.symbol for h in saved], period=period, interval=interval)
    prices = {symbol: float(frame["close"].iloc[-1])
              for symbol, frame in frames.items() if len(frame)}
    book = holdings.value(saved, prices)

    realised = holdings.realised_total(ledger)
    fees = holdings.fees_total(ledger)

    symbols = sorted({h.symbol for h in saved})
    scanned = ultimate.scan(symbols) if symbols else {}
    weights = {p.symbol: p.market_value for p in book.priced}
    signal = ultimate.book_signal(scanned, weights) if scanned else None

    # The book's market value over time, from the frames already fetched above
    # -- `holdings.history` takes them rather than re-reading, so the curve
    # costs no extra download.
    #
    # Three properties travel with it because none of them is inferable from
    # the line, and all three change what it means:
    #   * it is defined only where every holding traded, so one recent listing
    #     can shrink it to almost nothing (`shortest_history` names which);
    #   * it assumes today's share counts throughout, so it is a what-if on the
    #     current book, not a record of what was actually held;
    #   * an empty curve is reported as empty rather than as a stub.
    curve = holdings.history(saved, frames)
    limiting = holdings.shortest_history(frames)
    value_curve = None
    if not curve.empty:
        totals = curve.sum(axis=1)
        value_curve = {
            "dates": [str(d) for d in curve.index],
            "value": [float(v) for v in totals],
            "cost_basis": book.cost_basis,
            "bars": len(curve),
            "limited_by": limiting[0] if limiting else None,
            "assumes_today_s_quantities": True,
        }

    positions = book.table().to_dict(orient="records")
    calls = {symbol: {"action": verdict.action, "score": verdict.score,
                       "confidence": verdict.confidence}
             for symbol, verdict in scanned.items()}
    for row in positions:
        row["call"] = calls.get(row["Symbol"])

    return {
        "summary": {
            "market_value": book.market_value,
            "cost_basis": book.cost_basis,
            "pnl": book.pnl,
            "pnl_pct": book.pnl_pct,
            "concentration_pct": book.concentration_pct,
            "positions": len(book.priced),
            "realised": realised,
            "fees": fees,
        },
        "positions": to_jsonable(positions),
        "unpriced": book.unpriced,
        "errors": errors,
        "signal": ({
            "score": signal.score,
            "confidence": signal.confidence,
            "buying": signal.buying,
            "selling": signal.selling,
            "unreadable": signal.unreadable,
            "total": signal.total,
        } if signal else None),
        "verdicts": {symbol: verdict_to_dict(verdict) for symbol, verdict in scanned.items()},
        "ledger": to_jsonable(holdings.ledger_table(ledger).to_dict(orient="records")),
        "curve": value_curve,
    }


@router.post("/api/portfolio/trade")
def post_trade(trade: TradeRequest) -> dict:
    try:
        transaction = holdings.execute(
            trade.side, trade.symbol, trade.quantity, trade.price, trade.fee)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return to_jsonable(transaction)


@router.post("/api/portfolio/ledger/clear")
def post_clear_ledger() -> dict:
    holdings.save_ledger([])
    return {"cleared": True}


@router.post("/api/portfolio/position")
def post_position(position: PositionRequest) -> dict:
    """Add a holding, or set an existing one to these numbers.

    Deliberately not a buy: a buy re-averages the basis over what was already
    held, which is right when units are being acquired and wrong when the
    point is to correct what the book says. A mistyped quantity re-averaged is
    a second error on top of the first.
    """
    try:
        transaction = holdings.execute(
            holdings.ADJUST, position.symbol, position.quantity,
            position.unit_cost, note=position.note)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return to_jsonable(transaction)


@router.delete("/api/portfolio/position/{symbol}")
def delete_position(symbol: str, note: str = "") -> dict:
    """Drop a holding from the book without selling it.

    Distinct from selling every unit, which books a realised figure and claims
    the position was closed at a price. This says the row should not be there,
    and realises nothing -- so it can neither flatter nor damage the realised
    total. The units and basis that were dropped go into the ledger row, which
    is what makes it reversible by hand.
    """
    try:
        transaction = holdings.execute(
            holdings.DISCARD, symbol, note=note)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return to_jsonable(transaction)
