"""Phase 4: the ported TradingView studies, for the Overview chart.

Wraps `core.pine` unmodified: `available` decides what a series has the columns
to draw, and each `PineIndicator.read` computes it. No indicator maths is
restated here -- these are the same objects the Streamlit Overview tab and the
`Study` backtest agents read, so a study cannot mean one thing on the chart and
another in a backtest.

Two rules from the tab carry over, and both are correctness rather than taste:

- **Computed on the whole frame, sliced afterwards.** An indicator fitted to
  whatever window happens to be on screen would change its own reading every
  time the range buttons are touched. The tab has a comment saying exactly
  this; the same slice is applied here.
- **A study a series cannot support is absent, not failed.** Close-only series
  support none of the OHLC studies, which is a fact about the data. The
  catalogue endpoint reports `requires` so a caller can say so, rather than
  offering a study that will raise.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core import live, pine

from ..schemas import to_jsonable

router = APIRouter()

DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"


def _catalogue_entry(indicator: pine.PineIndicator) -> dict:
    return {
        "key": indicator.key,
        "name": indicator.name,
        "pane": indicator.pane,
        "describe": indicator.describe,
        "requires": list(indicator.requires),
        "lines": list(indicator.lines),
        "levels": list(indicator.levels),
        "source": indicator.source,
    }


@router.get("/api/studies")
def get_studies() -> dict:
    """The whole catalogue, with the panes and reference levels a caller needs
    to draw each one. Static -- no series involved."""
    return {
        "studies": [_catalogue_entry(i) for i in pine.INDICATORS.values()],
        "panes": {"overlay": pine.OVERLAY, "oscillator": pine.OSCILLATOR},
        "rules": dict(pine.SIGNAL_RULES),
    }


@router.get("/api/studies/{symbol}")
def get_studies_for(
    symbol: str,
    keys: str = Query("", description="Comma-separated study keys. Empty means none."),
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    bars: int = Query(0, ge=0, description="Trailing bars to return. 0 means all."),
) -> dict:
    try:
        frame, entry = live.fetch(symbol, period=period, interval=interval)
    except live.FetchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    drawable = pine.available(frame)
    wanted = [k.strip() for k in keys.split(",") if k.strip()]

    unknown = [k for k in wanted if k not in pine.INDICATORS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown study {', '.join(unknown)}. Known: "
                   f"{', '.join(sorted(pine.INDICATORS))}.",
        )

    # Computed on the whole frame, then sliced -- never fitted to the window.
    keep = len(frame) if bars == 0 else min(bars, len(frame))
    computed: dict[str, dict] = {}
    unsupported: dict[str, str] = {}

    for key in wanted:
        indicator = pine.INDICATORS[key]
        if key not in drawable:
            missing = [c for c in indicator.requires if c not in frame.columns]
            unsupported[key] = (f"{indicator.name} needs {', '.join(missing)}, "
                                "which this series does not have")
            continue
        try:
            output = indicator.read(frame)
        except (pine.MissingColumns, ValueError) as error:
            unsupported[key] = str(error)
            continue
        sliced = output.iloc[len(frame) - keep:].reset_index(drop=True)
        computed[key] = {
            column: to_jsonable(list(sliced[column])) for column in sliced.columns
        }

    tail = frame.iloc[len(frame) - keep:]
    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "dates": [d.isoformat() for d in tail["date"]],
        "available": [_catalogue_entry(i) for i in drawable.values()],
        "studies": computed,
        "unsupported": unsupported,
        "bars": keep,
        "is_fresh": entry.is_fresh,
    }
