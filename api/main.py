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

import contextlib                                  # noqa: E402
from collections.abc import AsyncIterator            # noqa: E402

from fastapi import FastAPI                        # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from .jobs import REGISTRY as JOB_REGISTRY          # noqa: E402
from .routers import (                              # noqa: E402
    chart, jobs, montecarlo, portfolio, research, runs, signal, studies,
)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Drop the job queue on the way out.

    `ThreadPoolExecutor` joins its workers at interpreter exit, so a queue of
    pending trainings would hold the process open long after the server was
    asked to stop. Cancelling the queue means only the job already running has
    to finish -- a running thread cannot be interrupted, and pretending
    otherwise would be worse than waiting for it.

    Nothing is persisted here on purpose. A job's progress and result live in
    memory and are gone with the process; `GET /api/jobs/{id}` answers a poll
    from a previous boot with 410 and says so, rather than leaving a page to
    infer it from a 404.
    """
    yield
    JOB_REGISTRY.shutdown(wait=False)


app = FastAPI(title="Stock Prediction Models API", lifespan=lifespan)

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
app.include_router(research.router)
app.include_router(jobs.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
