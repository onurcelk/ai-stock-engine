"""Phase 6: the Forecast and Trading-agents endpoints, as background jobs.

Three kinds of work, all of them minutes long, all of them already emitting
progress through a callback the existing code takes:

  POST /api/jobs/walkforward   -> forecast.walk_forward(..., progress=)
  POST /api/jobs/project       -> forecast.project(..., progress=)
  POST /api/jobs/agent         -> agents.REGISTRY[name](...).train(on_progress=)
  GET  /api/jobs/{id}          -> poll one
  GET  /api/jobs               -> list what this process knows about
  GET  /api/agents             -> the catalogue the Trading-agents page needs

Each body is a transcription of what `streamlit_app.py` does for the same
button -- same functions, same arguments, same `runs.save` afterwards, so a run
started here and a run started there land in the same History tab looking the
same. The two differences are structural rather than behavioural: the callback
writes into a `Job` instead of a `st.progress` widget, and the work happens on
a worker thread instead of inside the request.

The agents are wrapped through `agents.REGISTRY`, which is the whole roster --
19 registered names across the 7 implementation modules (`actorcritic`,
`curiosity`, `deepq`, `evolution`, `neuroevolution`, `policygradient`,
`qlearning`). Wrapping the registry rather than a hand-copied list of names is
what stops this drifting from the tab the next time one is added.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import agents, backtest, data, forecast, runs

from ..bars import DEFAULT_INTERVAL, DEFAULT_PERIOD, resolve as resolve_bars

from ..jobs import BOOT_ID, REGISTRY as JOBS, Job, StaleJob, UnknownJob
from ..schemas import to_jsonable

router = APIRouter()

WALKFORWARD = "walkforward"
PROJECT = "project"
AGENT = "agent"



# --------------------------------------------------------------- request bodies


class _Series(BaseModel):
    """Which bars to run on. Shared by all three kinds.

    `dataset`, `start` and `end` are the same three the read endpoints take,
    resolved by the same `bars.resolve`, so a walk-forward can be run on a
    bundled CSV or on one year of a series and mean what it does everywhere
    else. `symbol` stays required even for a dataset: it is what the saved
    History run is filed under, and a run labelled only "GOOG-year" would not
    say which request produced it.
    """

    symbol: str = Field(min_length=1)
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    dataset: str | None = None
    start: str | None = None
    end: str | None = None


class _Network(_Series):
    """The neural settings the Forecast tab's sliders expose, same bounds."""

    model: str = "LSTM"
    num_layers: int = Field(1, ge=1, le=4)
    size_layer: int = Field(128, ge=8, le=512)
    timestamp: int = Field(5, ge=2, le=60)
    epochs: int = Field(100, ge=1, le=1000)
    dropout: float = Field(0.8, gt=0.0, le=1.0)
    learning_rate: float = Field(0.01, gt=0.0, le=1.0)
    seed: int | None = forecast.DEFAULT_SEED


class WalkForwardRequest(_Network):
    folds: int = Field(5, ge=2, le=20)
    horizon: int = Field(30, ge=1, le=252)
    min_train: int = Field(120, ge=20)


class ProjectRequest(_Network):
    epochs: int = Field(150, ge=1, le=1000)
    horizon: int = Field(5, ge=1, le=252)


class AgentRequest(_Series):
    agent: str
    iterations: int = Field(50, ge=1, le=500)
    window_size: int = Field(30, ge=5, le=60)
    layer_size: int = Field(64, ge=8, le=512)
    seed: int = Field(42, ge=0, le=9_999)
    initial_money: float = Field(10_000.0, gt=0)
    max_buy: int = Field(1, ge=1, le=100)
    max_sell: int = Field(1, ge=1, le=100)
    fee_pct: float = Field(0.0, ge=0, le=100)
    slippage_pct: float = Field(0.0, ge=0, le=100)
    sizing: str = backtest.FIXED_UNITS
    size_pct: float = Field(100.0, gt=0, le=100)


# -------------------------------------------------------------------- helpers


def _bars(request: _Series):
    """The one data door, and the label the History tab files a run under."""
    return resolve_bars(request.symbol, period=request.period,
                        interval=request.interval, dataset=request.dataset,
                        start=request.start, end=request.end)


def _accepted(job: Job, duplicate: bool) -> dict:
    return {**job.as_dict(include_result=False), "duplicate": duplicate}


def _epoch_progress(job: Job, slots: int, label: str):
    """Adapt `forecast.ProgressFn` -- (slot, epoch, epoch_total, loss, acc).

    The same arithmetic `streamlit_app.py` does for its own progress bar, so
    the two surfaces report the same fraction at the same moment.
    """
    def report(slot: int, epoch: int, epoch_total: int, loss: float, accuracy: float) -> None:
        done = slot * epoch_total + epoch + 1
        JOBS.report(
            job, done / max(1, slots * epoch_total),
            f"{label} {slot + 1}/{slots} · epoch {epoch + 1}/{epoch_total} "
            f"· loss {loss:.5f}",
        )
    return report


# ------------------------------------------------------------------- rosters


@router.get("/api/models")
def get_models() -> dict:
    """The network architectures a walk-forward or projection can run.

    Served from `forecast.MODELS` itself, the same way `GET /api/agents` is
    served from `agents.REGISTRY`: a model added there appears here without
    this file being touched, and a page reading it cannot offer one the engine
    does not have.
    """
    return {"models": list(forecast.MODELS), "default_seed": forecast.DEFAULT_SEED}


# ----------------------------------------------------------------- walk-forward


@router.post("/api/jobs/walkforward", status_code=202)
def start_walkforward(request: WalkForwardRequest) -> dict:
    frame, label = _bars(request)
    close, dates = frame["close"], frame["date"]

    available = forecast.max_folds(len(frame), request.horizon, request.min_train)
    if available < 2:
        # Refused here rather than inside the worker: the caller asked for
        # something this series cannot support, and that is a bad request, not
        # a failed job.
        raise HTTPException(
            status_code=400,
            detail=(f"Need at least {request.min_train + request.horizon * 2} bars "
                    f"for two folds; {label} has {len(frame)}."),
        )
    folds = min(request.folds, available)

    def work(job: Job) -> dict:
        result = forecast.walk_forward(
            close, dates, folds=folds, horizon=request.horizon,
            model=request.model, num_layers=request.num_layers,
            size_layer=request.size_layer, timestamp=request.timestamp,
            epochs=request.epochs, dropout=request.dropout,
            learning_rate=request.learning_rate, min_train=request.min_train,
            seed=request.seed,
            progress=_epoch_progress(job, folds, "fold"),
        )
        summary = result.summary()
        settings = {
            "model": request.model, "folds": folds, "horizon": request.horizon,
            "epochs": request.epochs, "layers": request.num_layers,
            "units": request.size_layer, "bars": len(frame),
        }
        metrics = {
            "folds_beating_naive": result.folds_beating_naive,
            "win_rate_pct": summary["win_rate_pct"],
            "mean_accuracy": summary["mean_accuracy"],
            "mean_naive": summary["mean_naive"],
            "mean_directional": summary["mean_directional"],
            "mean_mae": summary["mean_mae"],
        }
        saved = runs.save(
            kind=runs.WALKFORWARD, label=label, settings=settings, metrics=metrics,
            payload={
                "fold_index": [f.index + 1 for f in result.folds],
                "accuracies": result.accuracies,
                "naive_accuracies": result.naive_accuracies,
                "directionals": result.directionals,
                "maes": result.maes,
            },
        )
        return to_jsonable({
            "symbol": request.symbol.strip().upper(),
            "label": label,
            "run_id": saved.id,
            "folds": folds,
            "horizon": result.horizon,
            "model": result.model,
            "summary": summary,
            "folds_beating_naive": result.folds_beating_naive,
            "table": result.table().to_dict(orient="records"),
            "settings": settings,
            "metrics": metrics,
        })

    job, duplicate = JOBS.submit(WALKFORWARD, request.model_dump(), work)
    return _accepted(job, duplicate)


# --------------------------------------------------------------------- project


@router.post("/api/jobs/project", status_code=202)
def start_project(request: ProjectRequest) -> dict:
    frame, label = _bars(request)
    close, dates = frame["close"], frame["date"]

    if len(frame) <= request.timestamp + request.horizon + 5:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough history to project {request.horizon} bars from {label}.",
        )

    def work(job: Job) -> dict:
        projection = forecast.project(
            close, dates, model=request.model, num_layers=request.num_layers,
            size_layer=request.size_layer, timestamp=request.timestamp,
            epochs=request.epochs, dropout=request.dropout,
            learning_rate=request.learning_rate, horizon=request.horizon,
            seed=request.seed,
            progress=_epoch_progress(job, 1, "projection"),
        )
        return to_jsonable({
            "symbol": request.symbol.strip().upper(),
            "label": label,
            "model": projection.model,
            "horizon": projection.horizon,
            "last_price": projection.last_price,
            "last_date": projection.last_date,
            "path": list(projection.path),
            "final": projection.final,
            "move_pct": projection.move_pct,
            "direction": projection.direction,
        })

    job, duplicate = JOBS.submit(PROJECT, request.model_dump(), work)
    return _accepted(job, duplicate)


# ----------------------------------------------------------------------- agent


@router.get("/api/agents")
def get_agents() -> dict:
    """The roster, its per-agent default iteration count, and its citations.

    Served from `agents.REGISTRY` itself rather than a copy, so a name added to
    the registry appears here without this file being touched.
    """
    return {
        "agents": [
            {
                "name": name,
                "default_iterations": agents.DEFAULT_ITERATIONS.get(name),
                "notebook": agents.SOURCE_NOTEBOOK.get(name),
            }
            for name in agents.REGISTRY
        ],
        "sizing_modes": sorted(backtest.SIZING_MODES),
    }


@router.post("/api/jobs/agent", status_code=202)
def start_agent(request: AgentRequest) -> dict:
    if request.agent not in agents.REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent {request.agent!r}. Expected one of: "
                   f"{', '.join(agents.REGISTRY)}.",
        )
    if request.sizing not in backtest.SIZING_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sizing {request.sizing!r}. Expected one of: "
                   f"{', '.join(sorted(backtest.SIZING_MODES))}.",
        )
    frame, label = _bars(request)
    close, dates = frame["close"], frame["date"]

    def work(job: Job) -> dict:
        def on_agent_progress(step: int, total: int, reward: float) -> None:
            JOBS.report(job, (step + 1) / max(1, total),
                        f"Iteration {step + 1}/{total} · policy return {reward:+.2f}%")

        learner = agents.REGISTRY[request.agent](
            close, window_size=request.window_size,
            layer_size=request.layer_size, seed=request.seed,
        )
        try:
            report = learner.train(request.iterations, on_progress=on_agent_progress)
            signal = learner.signals()
        finally:
            # TF graphs are process-global; a leaked session accumulates.
            # Same `finally` the Trading agents tab wraps its own call in.
            if hasattr(learner, "close_session"):
                learner.close_session()

        scored = backtest.run(
            close, signal, dates, initial_money=request.initial_money,
            max_buy=request.max_buy, max_sell=request.max_sell,
            fee_pct=request.fee_pct, slippage_pct=request.slippage_pct,
            sizing=request.sizing, size_pct=request.size_pct,
            periods_per_year=data.periods_per_year(dates),
        )
        settings = {
            "agent": request.agent, "iterations": request.iterations,
            "window": request.window_size, "units": request.layer_size,
            "seed": request.seed, "sizing": request.sizing, "bars": len(frame),
        }
        metrics = {
            "return_pct": scored.roi_pct,
            "buy_hold_pct": scored.buy_hold_roi_pct,
            "trades": len(scored.trades),
            "win_rate_pct": scored.win_rate_pct,
            "max_drawdown_pct": scored.max_drawdown_pct,
            "train_seconds": report.seconds,
        }
        saved = runs.save(
            kind=runs.AGENT, label=label, settings=settings, metrics=metrics,
            payload={
                "rewards": report.rewards,
                "buys": scored.buys,
                "sells": scored.sells,
                "equity": scored.equity,
                "dates": dates,
            },
        )
        return to_jsonable({
            "symbol": request.symbol.strip().upper(),
            "label": label,
            "run_id": saved.id,
            "agent": request.agent,
            "settings": settings,
            "metrics": metrics,
            "rewards": report.rewards,
            "train_seconds": report.seconds,
            "improved": report.improved,
            "dates": [str(d) for d in dates],
            "equity": list(np.asarray(scored.equity, dtype=float)),
            "buys": scored.buys,
            "sells": scored.sells,
            "final_value": scored.final_value,
        })

    job, duplicate = JOBS.submit(AGENT, request.model_dump(), work)
    return _accepted(job, duplicate)


# ---------------------------------------------------------------------- polling


@router.get("/api/jobs")
def list_jobs() -> dict:
    """Every job this *process* knows about -- see `GET /api/jobs/{id}` on why
    that qualifier matters."""
    return {
        "jobs": [job.as_dict(include_result=False) for job in JOBS.list()],
        "boot": BOOT_ID,
    }


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    try:
        job = JOBS.get(job_id)
    except StaleJob as error:
        raise HTTPException(
            status_code=410,
            detail=("That job was started before the server restarted. The "
                    "registry is in memory, so its progress and its result "
                    "were lost with the process -- start it again."),
        ) from error
    except UnknownJob as error:
        raise HTTPException(status_code=404, detail=f"No job {job_id!r}.") from error
    return job.as_dict()
