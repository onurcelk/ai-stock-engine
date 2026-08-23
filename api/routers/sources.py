"""Phase 6e: what a caller may ask for -- intervals, periods, datasets.

One endpoint, serving `api.bars.catalogue()`. It exists because two of the
parity gaps were not missing engine capability at all: `live.fetch` has always
accepted every interval in `live.INTERVALS`, and `data.load` has always read
the bundled CSVs. What was missing was any way for a page to *discover* them,
so the frontend hardcoded daily bars and had no offline path.

The per-interval period lists are the part that matters. Yahoo will not serve
five years of hourly bars, so a selector offering that combination produces a
failure the person using it cannot diagnose. `live.periods_for` already knows;
this puts it where the selector can read it.
"""

from __future__ import annotations

from fastapi import APIRouter

from .. import bars

router = APIRouter()


@router.get("/api/sources")
def get_sources() -> dict:
    return bars.catalogue()
