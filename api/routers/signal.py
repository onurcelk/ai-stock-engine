"""Phase 0: the Signal endpoints, split into a read and a write (2026-08-23).

Until this split there was one route, `GET /api/signal/{symbol}`, and it called
`ledger_activation.evaluate_and_freeze`. A GET is a *safe* method by contract:
browsers prefetch them, `next/link` prefetches them, React's StrictMode invokes
a fetching effect twice in development, end-to-end runs replay them, and any
uptime check or crawler will issue one unprompted. Every one of those, landing
on bars that had moved since the last freeze, appended a permanent row to
`app/forecast_ledger.sqlite3` -- the append-only, never-regenerable prospective
record whose entire value is that a person chose each cutoff.

So the two acts are now two routes:

`GET /api/signal/{symbol}` reads. It runs the engine with `active=False`, the
same function's own tested no-write path, and returns `"freeze": null` -- not a
report saying nothing happened, but the absence of one, because no freeze was
attempted. Routing the read through `evaluate_and_freeze` rather than calling
`ultimate.evaluate` directly keeps one door into the engine-and-ledger pair and
puts the decision not to write at the call site, in a word.

`POST /api/signal/{symbol}/freeze` writes, calling `evaluate_and_freeze`
unmodified -- the exact function `streamlit_app.py` and `core.collector` call,
so all three surfaces share one write path into the ledger, never three. The
engine runs once inside it and the verdict returned is the verdict frozen,
which is why this returns a verdict of its own rather than only a receipt.

Two further guards sit under this one, and neither is in this file: the
destination guard in `ledger_activation.writes_blocked` (a test run or a
process with writes switched off is refused even on the POST) and the
provenance now attached to every record written from here, so the ledger can
say which surface asked rather than leaving it to be inferred from timestamps.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core import forecast_ledger, ledger_activation

from ..schemas import to_jsonable, verdict_to_dict

router = APIRouter()

#: Stamped into `metadata["provenance"]` on everything frozen through here.
PROVENANCE = {"source": forecast_ledger.SOURCE_API}


@router.get("/api/signal/{symbol}")
def get_signal(symbol: str) -> dict:
    """The reading, and nothing else. This route cannot write to the ledger."""
    try:
        verdict, _ = ledger_activation.evaluate_and_freeze(symbol, active=False)
    except Exception as error:                                    # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"verdict": verdict_to_dict(verdict), "freeze": None}


@router.post("/api/signal/{symbol}/freeze")
def freeze_signal(symbol: str) -> dict:
    """Record this reading as a prospective forecast.

    A failed write comes back as `freeze.error` with a 200, not as a 5xx: the
    reading is valid whether or not the ledger accepted it, and withholding it
    would help nobody. That is `evaluate_and_freeze`'s own contract and this
    endpoint keeps it rather than reinterpreting it.
    """
    try:
        verdict, report = ledger_activation.evaluate_and_freeze(
            symbol, provenance=PROVENANCE,
        )
    except Exception as error:                                    # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "verdict": verdict_to_dict(verdict),
        "freeze": {**to_jsonable(report), "summary": report.summary()},
    }
