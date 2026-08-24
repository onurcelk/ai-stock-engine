"""The engine's own evidence, drawn on the chart.

`/api/studies` serves `core.pine` -- seven TradingView ports, each drawing the
lines its author drew. This serves the other thing the desk computes:
`indicators.SOURCES`, the fourteen sources `ultimate.py` actually weights into
a verdict. Until now they were visible only as a table of numbers on the Signal
page, which is a poor way to answer the question people actually ask of them --
*when* did this source change its mind, and was it early or late?

Two things make them drawable as one pane rather than fourteen:

**They are already on one scale.** Every source returns [-1, +1] by contract:
sign is the direction it argues for, magnitude is how hard, and 0 means no
opinion on that bar. So the reference levels are the same for all of them
(-1, 0, +1) and two sources can be drawn on the same axis honestly, which is
not true of an RSI and a MACD histogram.

**Zero is meaningful, not missing.** A source that cannot read a series returns
zeros rather than raising -- `opening_range` on a daily frame, the volume
sources on a close-only one. That is the engine's own convention and it is
reported here as `silent` with the reason, never as a failure and never as a
flat line the reader might mistake for a measured neutral.

Rules carried over from `routers/studies.py`, both correctness rather than
taste:

- **Computed on the whole frame, sliced afterwards.** A source fitted to
  whatever window is on screen would change its reading every time the range
  buttons are touched.
- **Read-only.** No ledger, no book, no saved run. Drawing a source is not
  recording a forecast, and `indicators.py` is imported and never written --
  its sha256 is the `technical_sources` version key on every row in the
  forecast ledger, so a router that edited it would re-version live models
  against a record of real prospective calls.

`filings_evidence.attach` runs before the sources are read, for the same reason
`ultimate.evaluate` runs it: `pead` reads two columns the price feed does not
carry, and without them it would draw an honest but permanently empty pane.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core import filings_evidence, indicators, live

from ..schemas import to_jsonable

router = APIRouter()

DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"

#: Every source shares these, because every source shares one scale.
LEVELS = (-1.0, 0.0, 1.0)

#: What each family means, in the words `indicators.py` uses for it. Served
#: with the catalogue so the picker can group by something more useful than
#: alphabetical order -- the families are how `ultimate.cap_families` stops
#: correlated evidence carrying a verdict alone, so they are the grouping that
#: actually means something.
FAMILIES = {
    indicators.TREND: "Follows a move once it is established.",
    indicators.MOMENTUM: "Reads the rate of change rather than the level.",
    indicators.REVERSION: "Argues against a stretch, not with it.",
    indicators.VOLUME: "Reads participation rather than price.",
    indicators.STRUCTURE: "Reads the shape of the path itself.",
    indicators.FUNDAMENTAL: "Not a reading of the price at all.",
}


def _catalogue_entry(source: indicators.Source) -> dict:
    return {
        "key": source.key,
        "name": source.name,
        "family": source.family,
        "describe": source.describe,
        "pane": "oscillator",
        "levels": list(LEVELS),
    }


@router.get("/api/evidence")
def get_evidence() -> dict:
    """The catalogue. Static -- no series involved."""
    return {
        "sources": [_catalogue_entry(s) for s in indicators.SOURCES.values()],
        "families": dict(FAMILIES),
        "levels": list(LEVELS),
        "scale": "Every source returns [-1, +1]. The sign is the direction it "
                 "argues for, the magnitude is how hard it argues, and 0 means "
                 "it has no opinion on that bar.",
    }


@router.get("/api/evidence/{symbol}")
def get_evidence_for(
    symbol: str,
    keys: str = Query("", description="Comma-separated source keys. Empty "
                                      "means none."),
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    bars: int = Query(0, ge=0, description="Trailing bars to return. 0 means "
                                           "all."),
) -> dict:
    try:
        frame, entry = live.fetch(symbol, period=period, interval=interval)
    except live.FetchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    wanted = [key.strip() for key in keys.split(",") if key.strip()]
    unknown = [key for key in wanted if key not in indicators.SOURCES]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source {', '.join(unknown)}. Known: "
                   f"{', '.join(sorted(indicators.SOURCES))}.",
        )

    # `pead` reads columns the price feed does not carry. Attached here for the
    # same reason `ultimate.evaluate` attaches them, so the chart and the
    # verdict are reading the identical frame.
    frame = filings_evidence.attach(frame, symbol)

    # Computed on the whole frame, then sliced -- never fitted to the window.
    keep = len(frame) if bars == 0 else min(bars, len(frame))
    computed: dict[str, list] = {}
    silent: dict[str, str] = {}

    for key in wanted:
        source = indicators.SOURCES[key]
        series = source.read(frame)
        if series.abs().max() == 0:
            # The engine's own words for this, so the chart and the Signal
            # page's "Why not" column cannot describe the same state
            # differently.
            silent[key] = f"{source.name} is not computable on this series"
            continue
        computed[key] = to_jsonable(list(series.iloc[len(frame) - keep:]))

    tail = frame.iloc[len(frame) - keep:]
    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "dates": [value.isoformat() for value in tail["date"]],
        "sources": computed,
        "silent": silent,
        "levels": list(LEVELS),
        "bars": keep,
        "is_fresh": entry.is_fresh,
    }
