"""Phase 4: the History endpoints.

Wraps `core.runs` unmodified -- `load_all`, `table`, `load`, `delete`, `clear`,
the same five calls the History tab makes, in the same order.

The listing deliberately omits each run's `payload`. A payload carries enough
to redraw that run's chart (an equity curve, a fold's predictions), so sending
every one of them to list up to `runs.MAX_RUNS` entries would put megabytes on
the wire to draw a table that shows none of it. The tab has the same shape: the
table is metadata, and a payload is read only once a run is selected.

`DELETE /api/runs/{id}` and `POST /api/runs/clear` remove saved results
permanently. They are the only writes here, and `clear` requires an explicit
confirmation flag -- a bare POST that wipes every saved run is too easy to
reach by accident.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core import runs

from ..schemas import to_jsonable

router = APIRouter()


def _summary(run: runs.Run) -> dict:
    """One run without its payload, plus the two computed properties the table
    shows that `dataclasses.fields()` does not see."""
    return {
        "id": run.id,
        "kind": run.kind,
        "kind_label": run.kind_label,
        "label": run.label,
        "saved_at": run.saved_at.isoformat(),
        "age": run.describe_age(),
        "settings": to_jsonable(run.settings),
        "metrics": to_jsonable(run.metrics),
    }


@router.get("/api/runs")
def get_runs(kind: str | None = None) -> dict:
    if kind is not None and kind not in runs.KIND_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown kind {kind!r}. Expected one of: "
                   f"{', '.join(sorted(runs.KIND_LABELS))}.",
        )

    saved = runs.load_all(kind)
    table = runs.table(saved)

    return {
        "runs": [_summary(run) for run in saved],
        "table": to_jsonable(table.to_dict(orient="records")) if len(table) else [],
        "columns": list(table.columns) if len(table) else [],
        "kinds": dict(runs.KIND_LABELS),
        "total": len(saved),
    }


@router.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = runs.load(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No saved run {run_id!r}.")
    return {**_summary(run), "payload": to_jsonable(run.payload)}


@router.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict:
    if not runs.delete(run_id):
        raise HTTPException(status_code=404, detail=f"No saved run {run_id!r}.")
    return {"deleted": run_id}


@router.post("/api/runs/clear")
def clear_runs(confirm: bool = Query(False)) -> dict:
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Refusing to delete every saved run without confirm=true.",
        )
    return {"removed": runs.clear()}
