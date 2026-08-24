"""FastAPI service in front of `app/core/*`. Since Phase 7, the desk's server.

Normally started with the frontend, from the repository root:

    python run_desk.py

Directly, when only the API is wanted:

    ./venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000

`app/` has no `__init__.py` (Streamlit ran it as a script, not a package),
so `core.*` is only importable once `app/` is on `sys.path` -- the same
pattern already used in `alpha/vix1_power_gate.py` and `alpha/orb1h_power_gate.py`
for the identical reason. Done once, here, before any router imports `core`.

**This process can change the forecast ledger, so it owns a backup lifecycle.**
Until the cutover that lifecycle belonged to `run_app.py`, because Streamlit's
process has no reliable shutdown callback and a launcher was the only thing
that did. The API does not have that problem -- `lifespan` below is exactly the
hook Streamlit lacked -- so the guarantee now holds however this server is
started, including by hand, and does not depend on remembering a launcher.
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

from core import ledger_lifecycle                   # noqa: E402

from .jobs import REGISTRY as JOB_REGISTRY          # noqa: E402
from .routers import (                              # noqa: E402
    basket, chart, evidence, jobs, montecarlo, options, portfolio, research,
    runs, signal, sources, strategies, studies, watchlist,
)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Back the ledger up around the session; drop the job queue on the way out.

    **The backup.** `ledger_lifecycle.start` takes a recovery snapshot if the
    last process died before its own, and `shutdown` takes one if this session
    changed anything. Both are fingerprint-guarded, so a server that froze
    nothing writes no file, and `run_desk.py` running the same hooks around
    this process produces one snapshot between them rather than two. Neither
    raises: a backup problem must never stop the server starting or stopping.

    Nothing here freezes a forecast. The startup prospective sweep stays in the
    launcher (`core.startup.collect_then_replay`) because it appends to the
    append-only record, and `uvicorn --reload` re-runs this on every file save.

    **The jobs.** `ThreadPoolExecutor` joins its workers at interpreter exit, so
    a queue of pending trainings would hold the process open long after the
    server was asked to stop. Cancelling the queue means only the job already
    running has to finish -- a running thread cannot be interrupted, and
    pretending otherwise would be worse than waiting for it.

    No job state is persisted, on purpose. A job's progress and result live in
    memory and are gone with the process; `GET /api/jobs/{id}` answers a poll
    from a previous boot with 410 and says so, rather than leaving a page to
    infer it from a 404.
    """
    ledger_lifecycle.start()
    try:
        yield
    finally:
        JOB_REGISTRY.shutdown(wait=False)
        ledger_lifecycle.shutdown()


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
app.include_router(strategies.router)
app.include_router(basket.router)
app.include_router(sources.router)
app.include_router(watchlist.router)
app.include_router(research.router)
app.include_router(jobs.router)
app.include_router(options.router)
app.include_router(evidence.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
