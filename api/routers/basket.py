"""Phase 6e: the multi-symbol portfolio builder.

The largest gap the parity audit found. Everything else in the app looks at one
symbol at a time, which cannot answer the question that decides an allocation:
how these holdings behave *together*. Two series that each look strong but move
in lockstep are one bet, not two, and only the correlation shows it.

This is `core.portfolio` over HTTP and nothing else -- `fetch_many`, `align`,
`normalise_weights`, `build`, `per_symbol_stats`, `correlations` and
`diversification_note`, each called once, in the order the Portfolio tab calls
them. No allocation arithmetic is restated here; a test computes the same
basket directly from the module and compares.

Two properties inherited from `core.portfolio` that a caller must be told
about rather than left to infer:

- **The basket is only defined where every member traded.** `align` does an
  inner join and drops the rest, because forward-filling a price that never
  existed would invent the very thing the correlation is meant to measure. A
  basket whose members barely overlap is refused with that reason, not served
  as five bars.
- **Weights drift.** Without rebalancing the winners grow into a larger share,
  so `final_weights` is reported next to the target and the response says how
  far it moved. That drift is a finding, not a rendering detail.

**It does not write.** The saved book (`holdings.json`) is a different thing
entirely: this endpoint constructs a hypothetical basket and scores it. It
never reads or touches what you actually hold, and Streamlit's builder does not
either -- the tab keeps them apart on purpose so switching views cannot
overwrite either one.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core import live, portfolio

from .. import bars
from ..schemas import to_jsonable

router = APIRouter()

#: The fewest overlapping bars a basket can be scored on. `core.portfolio`'s
#: own tab refuses below this, with the same wording.
MIN_OVERLAP = 5


@router.get("/api/basket/options")
def get_basket_options() -> dict:
    """Rebalance schedules and the holding limit, from the module itself."""
    return {
        "rebalance": [
            {"label": label, "bars": every}
            for label, every in portfolio.REBALANCE.items()
        ],
        "max_holdings": portfolio.MAX_HOLDINGS,
        "quick_picks": list(live.QUICK_PICKS),
    }


@router.get("/api/basket")
def get_basket(
    symbols: str = Query(..., description="Comma-separated, at most MAX_HOLDINGS."),
    weights: str = Query("", description="Comma-separated percentages, in the "
                                         "same order. Empty means equal."),
    rebalance_every: int = Query(0, ge=0, le=2520,
                                 description="Bars between rebalances; 0 never."),
    initial_money: float = Query(10_000.0, gt=0),
    period: str = bars.DEFAULT_PERIOD,
    interval: str = bars.DEFAULT_INTERVAL,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    wanted = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not wanted:
        raise HTTPException(status_code=400, detail="Choose at least one holding.")
    if len(wanted) > portfolio.MAX_HOLDINGS:
        raise HTTPException(
            status_code=400,
            detail=f"At most {portfolio.MAX_HOLDINGS} holdings; {len(wanted)} given.",
        )

    given: list[float] = []
    if weights.strip():
        try:
            given = [float(w) for w in weights.split(",") if w.strip()]
        except ValueError as error:
            raise HTTPException(
                status_code=400, detail=f"Weights must be numbers: {error}",
            ) from error
        if len(given) != len(wanted):
            raise HTTPException(
                status_code=400,
                detail=(f"{len(given)} weights for {len(wanted)} holdings -- give one "
                        "per symbol, in the same order, or none for equal weights."),
            )

    frames, errors = portfolio.fetch_many(wanted, period=period, interval=interval)
    if not frames:
        raise HTTPException(
            status_code=400,
            detail=f"None of those symbols could be loaded: {'; '.join(errors.values())}",
        )

    # The window applies after the fetch, for the same reason it does in
    # `bars.resolve`: `period` decides what is downloaded, `start`/`end` decide
    # what is looked at.
    if start or end:
        frames = {s: bars.trim(f, start, end) for s, f in frames.items()}
        frames = {s: f for s, f in frames.items() if len(f)}
        if not frames:
            raise HTTPException(
                status_code=400,
                detail="No holding has any bars in that window.",
            )

    # A symbol that failed to load must not silently take its weight with it:
    # the remaining weights are re-read positionally from what survived, and
    # `normalise_weights` rescales them to 100.
    if given:
        by_symbol = dict(zip(wanted, given))
        chosen = {s: by_symbol.get(s, 0.0) for s in frames}
    else:
        chosen = {s: 100.0 / len(frames) for s in frames}

    prices = portfolio.align(frames)
    if len(prices) < MIN_OVERLAP:
        raise HTTPException(
            status_code=400,
            detail=("These holdings barely overlap in time -- the basket is only "
                    "defined where every member traded. Try a shorter history, a "
                    "wider window, or drop the newest listing."),
        )

    book = portfolio.build(prices, chosen, initial_money=initial_money,
                           rebalance_every=rebalance_every)
    stats = portfolio.per_symbol_stats(prices, book.bars_per_year)
    final = book.final_weights

    correlation = None
    diversification = None
    if len(prices.columns) > 1:
        matrix = portfolio.correlations(prices)
        average, verdict = portfolio.diversification_note(matrix)
        correlation = {
            "symbols": list(matrix.columns),
            "matrix": [[float(v) for v in row] for row in matrix.to_numpy()],
        }
        diversification = {"average": average, "verdict": verdict}

    drift = max((abs(final[s] - book.weights[s]) for s in final), default=0.0)
    heaviest = max(final, key=lambda s: final[s]) if final else None

    return to_jsonable({
        "symbols": list(prices.columns),
        "skipped": errors,
        "dates": [str(d) for d in book.dates],
        "equity": list(book.equity),
        # Each holding rebased to the same starting capital, which is what
        # makes the basket line readable against its members.
        "rebased": {
            symbol: list(prices[symbol] / float(prices[symbol].iloc[0]) * initial_money)
            for symbol in prices.columns
        },
        "contributions": {
            symbol: list(book.contributions[symbol]) for symbol in prices.columns
        },
        "weights": book.weights,
        "final_weights": final,
        "drift_pct": drift,
        "heaviest": heaviest,
        "rebalanced": book.rebalanced,
        "rebalance_every": rebalance_every,
        "initial_money": book.initial_money,
        "bars": len(prices),
        "metrics": {
            "final_value": book.final_value,
            "profit": book.profit,
            "roi_pct": book.roi_pct,
            "volatility_pct": book.volatility_pct,
            "sharpe": book.sharpe,
            "max_drawdown_pct": book.max_drawdown_pct,
            "bars_per_year": book.bars_per_year,
        },
        "per_symbol": stats.to_dict(orient="records"),
        "correlation": correlation,
        "diversification": diversification,
    })
