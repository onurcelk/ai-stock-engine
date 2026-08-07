"""Saved training runs.

The whole point of this module is that a result outlives the browser session,
so the round-trip is what matters most: what goes in must come back out
unchanged, and one bad file must never take the listing down with it.

Hermetic via `temp_runs`, the same pattern `test_live.py` uses for the cache.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core import runs


@pytest.fixture
def temp_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RUNS_DIR", tmp_path)
    return tmp_path


def make(kind=runs.FORECAST, label="AAPL · Daily", **settings):
    return runs.save(
        kind=kind,
        label=label,
        settings={"model": "lstm", "epochs": 150, **settings},
        metrics={"directional": 53.3, "mae": 11.16},
        payload={"actual": [1.0, 2.0, 3.0]},
    )


# ------------------------------------------------------------------ round-trip


def test_save_then_load_returns_what_went_in(temp_runs):
    saved = make()
    loaded = runs.load(saved.id)

    assert loaded is not None
    assert loaded.id == saved.id
    assert loaded.kind == runs.FORECAST
    assert loaded.label == "AAPL · Daily"
    assert loaded.settings["model"] == "lstm"
    assert loaded.settings["epochs"] == 150
    assert loaded.metrics["directional"] == pytest.approx(53.3)
    assert loaded.payload["actual"] == [1.0, 2.0, 3.0]


def test_numpy_and_pandas_types_survive(temp_runs):
    """Training code hands over numpy arrays and Timestamps, not plain lists."""
    saved = runs.save(
        kind=runs.AGENT,
        label="GOOG",
        settings={"seed": np.int64(42), "window": np.int32(30)},
        metrics={"roi": np.float64(4.56), "beat": np.bool_(True)},
        payload={
            "rewards": np.array([1.5, 2.5, 3.5]),
            "signal": pd.Series([1.0, 0.0, -1.0]),
            "when": pd.Timestamp("2026-08-07 13:45"),
        },
    )
    loaded = runs.load(saved.id)

    assert loaded.settings["seed"] == 42
    assert loaded.metrics["roi"] == pytest.approx(4.56)
    assert loaded.metrics["beat"] is True
    assert loaded.payload["rewards"] == [1.5, 2.5, 3.5]
    assert loaded.payload["signal"] == [1.0, 0.0, -1.0]
    assert loaded.payload["when"].startswith("2026-08-07")


def test_non_finite_numbers_become_null(temp_runs):
    """NaN and infinity are not valid JSON and would corrupt the file."""
    saved = runs.save(runs.FORECAST, "X", settings={},
                      metrics={"mae": np.nan, "rmse": np.inf, "ok": 1.5},
                      payload={})
    loaded = runs.load(saved.id)

    assert loaded.metrics["mae"] is None
    assert loaded.metrics["rmse"] is None
    assert loaded.metrics["ok"] == pytest.approx(1.5)


def test_awkward_labels_do_not_break_filenames(temp_runs):
    """Symbols like EURUSD=X and the app's "·" separator are not filename-safe."""
    saved = runs.save(runs.FORECAST, "EURUSD=X · 1 Hour", settings={},
                      metrics={}, payload={})
    assert runs.load(saved.id) is not None
    assert len(runs.load_all()) == 1


# --------------------------------------------------------------------- listing


def test_newest_first(temp_runs):
    first = make(label="one")
    second = make(label="two")
    # Both land in the same second, so nudge the older one back explicitly.
    path = temp_runs / f"{first.id}.json"
    import json
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["saved_at"] = (dt.datetime.now() - dt.timedelta(hours=2)).isoformat(
        timespec="seconds")
    path.write_text(json.dumps(raw), encoding="utf-8")

    listing = runs.load_all()
    assert [r.label for r in listing] == ["two", "one"]
    assert listing[0].id == second.id


def test_filter_by_kind(temp_runs):
    make(kind=runs.FORECAST, label="f")
    make(kind=runs.AGENT, label="a")
    make(kind=runs.WALKFORWARD, label="w")

    assert len(runs.load_all()) == 3
    assert len(runs.load_all(kind=runs.AGENT)) == 1
    assert runs.load_all(kind=runs.AGENT)[0].label == "a"


def test_empty_directory_is_not_an_error(temp_runs):
    assert runs.load_all() == []
    assert runs.load("nope") is None


def test_missing_directory_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RUNS_DIR", tmp_path / "never-created")
    assert runs.load_all() == []


def test_corrupt_file_is_skipped_not_fatal(temp_runs):
    """One hand-edited file must not hide every other run."""
    good = make(label="good")
    (temp_runs / "20260101-000000__forecast__broken.json").write_text(
        "{not json at all", encoding="utf-8")
    (temp_runs / "20260101-000001__forecast__partial.json").write_text(
        '{"id": "x"}', encoding="utf-8")  # valid JSON, missing required keys

    listing = runs.load_all()
    assert [r.label for r in listing] == ["good"]
    assert runs.load(good.id) is not None


# -------------------------------------------------------------------- deleting


def test_delete_one(temp_runs):
    keep = make(label="keep")
    drop = make(label="drop")

    assert runs.delete(drop.id) is True
    assert runs.delete(drop.id) is False  # already gone
    assert [r.label for r in runs.load_all()] == ["keep"]
    assert runs.load(keep.id) is not None


def test_clear_everything(temp_runs):
    make(label="a")
    make(label="b")
    assert runs.clear() == 2
    assert runs.load_all() == []


def test_pruning_caps_the_folder(temp_runs, monkeypatch):
    """Otherwise the folder grows forever on a machine that trains a lot."""
    monkeypatch.setattr(runs, "MAX_RUNS", 5)
    for index in range(12):
        runs.save(runs.FORECAST, f"run-{index:02d}", settings={}, metrics={},
                  payload={}, directory=temp_runs)

    assert len(list(temp_runs.glob("*.json"))) == 5
    # The survivors must be the newest, not an arbitrary five.
    assert "run-11" in sorted(p.name for p in temp_runs.glob("*.json"))[-1]


# ----------------------------------------------------------------------- table


def test_table_has_one_row_per_run(temp_runs):
    make(kind=runs.FORECAST, label="AAPL")
    make(kind=runs.AGENT, label="MSFT")

    frame = runs.table(runs.load_all())
    assert len(frame) == 2
    assert list(frame.columns[:4]) == ["When", "Age", "Type", "Series"]
    assert "id" in frame.columns
    assert set(frame["Series"]) == {"AAPL", "MSFT"}


def test_table_flattens_settings_and_metrics_into_columns(temp_runs):
    make()
    frame = runs.table(runs.load_all())
    assert "model" in frame.columns
    assert "epochs" in frame.columns
    assert "directional" in frame.columns


def test_table_of_nothing_is_empty(temp_runs):
    assert runs.table([]).empty


def test_kinds_all_have_a_display_label():
    for kind in (runs.AGENT, runs.FORECAST, runs.WALKFORWARD):
        assert kind in runs.KIND_LABELS


def test_describe_age_reads_sensibly(temp_runs):
    run = make()
    assert run.describe_age() == "just now"
    run.saved_at = dt.datetime.now() - dt.timedelta(minutes=30)
    assert run.describe_age().endswith("min ago")
    run.saved_at = dt.datetime.now() - dt.timedelta(hours=5)
    assert run.describe_age().endswith("h ago")
    run.saved_at = dt.datetime.now() - dt.timedelta(days=3)
    assert run.describe_age().endswith("d ago")
