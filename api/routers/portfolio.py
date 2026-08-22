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
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import holdings, portfolio, ultimate

from ..schemas import to_jsonable, verdict_to_dict

router = APIRouter()

DEFAULT_PERIOD = "6mo"
DEFAULT_INTERVAL = "1d"


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
