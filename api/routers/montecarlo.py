"""Phase 4: GET /api/montecarlo/{symbol}.

Calls `core.montecarlo.run` unmodified, on bars from `core.live.fetch` -- the
same data door `/api/ohlcv` reads through, so the simulation and the chart can
never be drawn from different series for the same symbol.

The response deliberately is not the raw path matrix. `montecarlo.run` returns
`simulations` columns of `days + 1` rows, which at the tab's own upper bounds
is 2,000 x 253 -- half a million floats. Streamlit never draws more than 120 of
those paths either, and says why in its own comment ("Drawing every path kills
the browser"). So the sampling, the envelope and the histogram binning all
happen here, and the wire carries a few hundred numbers instead.

Nothing here models anything. The drift, the volatility and every path come out
of `montecarlo.run`; the percentile bands are a plain quantile across the paths
it returned, for drawing.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from core import live, montecarlo

router = APIRouter()

DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"

# The Monte Carlo tab's own slider bounds, restated so the API refuses what the
# tab would never have offered rather than accepting it and running out of
# memory.
MAX_PATHS_DRAWN = 120


@router.get("/api/montecarlo/{symbol}")
def get_montecarlo(
    symbol: str,
    days: int = Query(30, ge=5, le=252),
    simulations: int = Query(200, ge=20, le=2000),
    seed: int | None = Query(None, ge=0, le=9999),
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    bins: int = Query(50, ge=10, le=100),
) -> dict:
    try:
        frame, entry = live.fetch(symbol, period=period, interval=interval)
    except live.FetchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    close = frame["close"]
    if len(close) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least two bars to estimate drift and volatility.",
        )

    simulation = montecarlo.run(close, days=days, simulations=simulations, seed=seed)
    paths = simulation.paths

    # Sampled for drawing, exactly as the tab samples: the first N columns.
    drawn = [[float(v) for v in paths[column]]
             for column in paths.columns[:MAX_PATHS_DRAWN]]

    values = paths.to_numpy()
    counts, edges = np.histogram(simulation.endings, bins=bins)

    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "days": days,
        "simulations": simulations,
        "seed": seed,
        "paths_drawn": len(drawn),
        "last_price": simulation.last_price,
        "daily_volatility": simulation.daily_volatility,
        "drift": simulation.drift,
        "summary": simulation.summary(),
        "paths": drawn,
        "median_path": [float(v) for v in np.median(values, axis=1)],
        "p5_path": [float(v) for v in np.percentile(values, 5, axis=1)],
        "p95_path": [float(v) for v in np.percentile(values, 95, axis=1)],
        "histogram": {
            "edges": [float(v) for v in edges],
            "counts": [int(v) for v in counts],
        },
        "is_fresh": entry.is_fresh,
    }
