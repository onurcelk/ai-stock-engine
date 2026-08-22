"""FastAPI service in front of `app/core/*`, for the new Next.js frontend.

Run from the repository root (`Stock-Prediction-Models/`):

    ./venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000

`app/` has no `__init__.py` (Streamlit runs it as a script, not a package),
so `core.*` is only importable once `app/` is on `sys.path` -- the same
pattern already used in `alpha/vix1_power_gate.py` and `alpha/orb1h_power_gate.py`
for the identical reason. Done once, here, before any router imports `core`.
"""

from __future__ import annotations

import pathlib
import sys

_APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from fastapi import FastAPI                        # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from .routers import (                              # noqa: E402
    chart, montecarlo, portfolio, runs, signal, studies,
)

app = FastAPI(title="Stock Prediction Models API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signal.router)
app.include_router(chart.router)
app.include_router(portfolio.router)
app.include_router(montecarlo.router)
app.include_router(runs.router)
app.include_router(studies.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
