"""Phase 0: GET /api/signal/{symbol}.

Calls `core.ledger_activation.evaluate_and_freeze` -- the exact function
`streamlit_app.py`'s Signal/Ultimate-signal tabs call -- so this endpoint and
the Streamlit tab share one write path into the forecast ledger, never two.
Nothing here recomputes a verdict or reimplements any part of the engine.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core import ledger_activation

from ..schemas import to_jsonable, verdict_to_dict

router = APIRouter()


@router.get("/api/signal/{symbol}")
def get_signal(symbol: str) -> dict:
    try:
        verdict, report = ledger_activation.evaluate_and_freeze(symbol)
    except Exception as error:                                    # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "verdict": verdict_to_dict(verdict),
        "freeze": to_jsonable(report),
    }
