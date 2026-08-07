"""Saved training runs, so results survive a browser refresh.

Everything the app trains — a forecast, a walk-forward evaluation, a
reinforcement-learning agent — used to live in `st.session_state` and nothing
else. Streamlit clears that on reload, so an accidental refresh threw away
however long the run took, and there was no way to ask "what did I get last
week with different settings?".

One JSON file per run, written the moment training finishes. JSON rather than
pickle deliberately: a pickle is tied to the exact library versions that wrote
it and is unsafe to load from disk, neither of which is acceptable for
something meant to still be readable in a year.

Every run records three things, and the split is what makes runs comparable:

    settings   the recipe — model, epochs, seed, symbol, date range
    metrics    the headline numbers, for the comparison table
    payload    just enough to redraw the chart

Results are personal, so `app/runs/` is gitignored.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib
import re

import numpy as np
import pandas as pd

RUNS_DIR = pathlib.Path(__file__).resolve().parents[1] / "runs"

# Kinds, and how they are labelled in the UI.
AGENT = "agent"
FORECAST = "forecast"
WALKFORWARD = "walkforward"

KIND_LABELS = {
    AGENT: "Trading agent",
    FORECAST: "Forecast",
    WALKFORWARD: "Walk-forward",
}

# A run is a few KB, so this cap is about not letting the folder grow forever
# rather than about disk space.
MAX_RUNS = 200


def _jsonable(value):
    """Convert numpy/pandas types into something json.dumps accepts.

    Applied on the way in, so nothing on the read side has to know that a
    field was ever a numpy array or a Timestamp.
    """
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, pd.Series):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        # NaN and infinity are not valid JSON; store them as null.
        return number if np.isfinite(number) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


@dataclasses.dataclass
class Run:
    id: str
    kind: str
    label: str
    saved_at: dt.datetime
    settings: dict
    metrics: dict
    payload: dict

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    def describe_age(self) -> str:
        seconds = (dt.datetime.now() - self.saved_at).total_seconds()
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{int(seconds // 60)} min ago"
        if seconds < 86_400:
            return f"{int(seconds // 3600)} h ago"
        return f"{int(seconds // 86_400)} d ago"


def _safe(text: str) -> str:
    """Labels contain characters that are illegal in filenames (EURUSD=X, ·)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip("-")[:40] or "run"


def _path(run_id: str, directory: pathlib.Path | None = None) -> pathlib.Path:
    return (directory or RUNS_DIR) / f"{run_id}.json"


def save(
    kind: str,
    label: str,
    settings: dict,
    metrics: dict,
    payload: dict | None = None,
    directory: pathlib.Path | None = None,
) -> Run:
    """Write one run to disk and return it."""
    directory = directory or RUNS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now()
    run_id = f"{now:%Y%m%d-%H%M%S}__{_safe(kind)}__{_safe(label)}"

    run = Run(
        id=run_id,
        kind=kind,
        label=label,
        saved_at=now,
        settings=dict(settings),
        metrics=dict(metrics),
        payload=dict(payload or {}),
    )

    _path(run_id, directory).write_text(
        json.dumps(
            {
                "id": run.id,
                "kind": run.kind,
                "label": run.label,
                "saved_at": now.isoformat(timespec="seconds"),
                "settings": _jsonable(run.settings),
                "metrics": _jsonable(run.metrics),
                "payload": _jsonable(run.payload),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _prune(directory)
    return run


def _read(path: pathlib.Path) -> Run | None:
    """A corrupt or hand-edited file is skipped, never allowed to break listing."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Run(
            id=str(raw["id"]),
            kind=str(raw["kind"]),
            label=str(raw["label"]),
            saved_at=dt.datetime.fromisoformat(raw["saved_at"]),
            settings=dict(raw.get("settings") or {}),
            metrics=dict(raw.get("metrics") or {}),
            payload=dict(raw.get("payload") or {}),
        )
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        return None


def load_all(kind: str | None = None,
             directory: pathlib.Path | None = None) -> list[Run]:
    """Every saved run, newest first."""
    directory = directory or RUNS_DIR
    if not directory.exists():
        return []
    runs = [run for run in (_read(p) for p in directory.glob("*.json")) if run]
    if kind:
        runs = [run for run in runs if run.kind == kind]
    return sorted(runs, key=lambda r: r.saved_at, reverse=True)


def load(run_id: str, directory: pathlib.Path | None = None) -> Run | None:
    path = _path(run_id, directory)
    return _read(path) if path.exists() else None


def delete(run_id: str, directory: pathlib.Path | None = None) -> bool:
    path = _path(run_id, directory)
    if not path.exists():
        return False
    path.unlink(missing_ok=True)
    return True


def clear(directory: pathlib.Path | None = None) -> int:
    """Delete every saved run. Returns how many were removed."""
    directory = directory or RUNS_DIR
    if not directory.exists():
        return 0
    paths = list(directory.glob("*.json"))
    for path in paths:
        path.unlink(missing_ok=True)
    return len(paths)


def _prune(directory: pathlib.Path, keep: int | None = None) -> int:
    """Drop the oldest runs beyond `keep`, so the folder cannot grow forever.

    `keep` is read at call time rather than bound as a default, so changing
    MAX_RUNS actually takes effect.
    """
    keep = MAX_RUNS if keep is None else keep
    paths = sorted(directory.glob("*.json"), key=lambda p: p.name, reverse=True)
    removed = 0
    for path in paths[keep:]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def table(runs: list[Run]) -> pd.DataFrame:
    """One row per run, for the comparison table.

    Settings and metrics vary by kind, so they are flattened into columns and
    the gaps left empty — a forecast has no win rate, an agent has no epochs.
    """
    if not runs:
        return pd.DataFrame()

    rows = []
    for run in runs:
        row = {
            "When": run.saved_at.strftime("%Y-%m-%d %H:%M"),
            "Age": run.describe_age(),
            "Type": run.kind_label,
            "Series": run.label,
        }
        row.update({str(k): v for k, v in run.settings.items()})
        row.update({str(k): v for k, v in run.metrics.items()})
        row["id"] = run.id
        rows.append(row)

    frame = pd.DataFrame(rows)
    leading = ["When", "Age", "Type", "Series"]
    rest = [c for c in frame.columns if c not in leading and c != "id"]
    return frame[leading + sorted(rest) + ["id"]]
