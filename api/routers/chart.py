"""Phase 1: GET /api/ohlcv/{symbol}. Phase 4 adds GET /api/stats/{symbol}.

Calls `core.live.fetch` unmodified -- the same data door every tab in the
app reads live bars through (`live.py` has zero Streamlit coupling, so this
is a direct reuse, not a port) -- and `core.data.describe`, the same function
the Overview tab's key-stats rail is built from.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core import data, live

from ..schemas import to_jsonable

router = APIRouter()

DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"


@router.get("/api/ohlcv/{symbol}")
def get_ohlcv(symbol: str, period: str = DEFAULT_PERIOD,
              interval: str = DEFAULT_INTERVAL) -> dict:
    try:
        frame, entry = live.fetch(symbol, period=period, interval=interval)
    except live.FetchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    bars = [
        {
            "date": row.date.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in frame.itertuples(index=False)
    ]
    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "bars": bars,
        "is_fresh": entry.is_fresh,
    }


@router.get("/api/stats/{symbol}")
def get_stats(symbol: str, period: str = DEFAULT_PERIOD,
              interval: str = DEFAULT_INTERVAL) -> dict:
    """The Overview rail's key stats, straight out of `data.describe`."""
    try:
        frame, entry = live.fetch(symbol, period=period, interval=interval)
    except live.FetchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "stats": to_jsonable(data.describe(frame)),
        "is_fresh": entry.is_fresh,
    }
