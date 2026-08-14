"""The V5 forecast ledger freezes predictions without reading outcomes."""

from __future__ import annotations

import dataclasses
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core import forecast, forecast_ledger, ultimate


def _frame(*, rows: int = 900, seed: int = 23) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0007, 0.01, rows)))
    return pd.DataFrame({
        "date": pd.bdate_range("2019-01-01", periods=rows),
        "open": close * 0.999,
        "high": close * 1.006,
        "low": close * 0.994,
        "close": close,
        "volume": rng.integers(1_000_000, 4_000_000, rows).astype(float),
    })


def _fetcher(frame: pd.DataFrame):
    def fetch(symbol: str, *, period: str, interval: str, force: bool = False):
        assert symbol == "TEST"
        assert interval == "1d"
        return frame.copy(deep=True), None
    return fetch


def _freeze(tmp_path, frame: pd.DataFrame):
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    verdict, records = forecast_ledger.generate_and_freeze_incumbent(
        ledger,
        "TEST",
        horizons=[ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]],
        fetcher=_fetcher(frame),
    )
    return ledger, verdict, records


def test_incumbent_forecasts_round_trip_with_complete_evidence(tmp_path):
    ledger, verdict, records = _freeze(tmp_path, _frame())

    assert len(records) == len(verdict.available) == 2
    loaded = ledger.load(records[0].forecast_id)
    assert loaded == records[0]
    assert loaded.production_or_challenger == forecast_ledger.PRODUCTION_INCUMBENT
    assert loaded.probability_positive is None
    assert loaded.confidence == verdict.by_key(loaded.horizon).confidence
    assert loaded.feature_data_version["data"] == loaded.input_fingerprint
    assert loaded.model_versions["ultimate_ensemble"].startswith("sha256:")
    assert "ensemble" in loaded.model_predictions
    assert {reading.key for reading in verdict.by_key(loaded.horizon).readings} <= set(
        loaded.model_predictions
    )
    assert all(set(weight) == {"raw", "normalised"}
               for weight in loaded.model_weights.values())


def test_duplicate_forecast_cannot_overwrite_frozen_record(tmp_path):
    ledger, _, records = _freeze(tmp_path, _frame())
    original = ledger.load(records[0].forecast_id)

    with pytest.raises(forecast_ledger.ForecastExistsError):
        ledger.insert(records[0])

    assert ledger.load(records[0].forecast_id) == original


def test_database_rejects_updates_and_deletes(tmp_path):
    ledger, _, records = _freeze(tmp_path, _frame())
    forecast_id = records[0].forecast_id

    with sqlite3.connect(ledger.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE forecasts SET symbol = 'CHANGED' WHERE forecast_id = ?",
                (forecast_id,),
            )

    with sqlite3.connect(ledger.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM forecasts WHERE forecast_id = ?", (forecast_id,))

    assert ledger.load(forecast_id).symbol == "TEST"


def test_database_rejects_insert_or_replace(tmp_path):
    ledger, _, records = _freeze(tmp_path, _frame())
    original = ledger.load(records[0].forecast_id)

    with sqlite3.connect(ledger.path) as connection:
        row = connection.execute(
            "SELECT * FROM forecasts WHERE forecast_id = ?", (original.forecast_id,)
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """INSERT OR REPLACE INTO forecasts
                       (forecast_id, generated_at, cutoff_at, symbol, horizon,
                        source_path, production_or_challenger, input_fingerprint,
                        payload, payload_sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(row),
            )

    assert ledger.load(original.forecast_id) == original


def test_nested_forecast_evidence_is_frozen(tmp_path):
    _, _, records = _freeze(tmp_path, _frame())
    record = records[0]

    with pytest.raises(TypeError):
        record.model_predictions["ensemble"] = {"score": 999}
    with pytest.raises(TypeError):
        record.model_predictions["ensemble"]["score"] = 999
    with pytest.raises(ValueError, match="forecast_id"):
        dataclasses.replace(record, forecast_id="fcst_arbitrary")


def test_batch_insert_is_atomic_when_any_identity_exists(tmp_path):
    ledger, _, records = _freeze(tmp_path, _frame())
    _, _, alternates = _freeze(tmp_path / "other", _frame(seed=24))
    alternate = alternates[0]

    with pytest.raises(forecast_ledger.ForecastExistsError):
        ledger.insert_many([alternate, records[0]])

    assert {record.forecast_id for record in ledger.list()} == {
        record.forecast_id for record in records
    }


def test_declared_cutoff_rejects_any_future_input(tmp_path):
    frame = _frame()
    cutoff = frame["date"].iloc[-20]
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")

    with pytest.raises(forecast_ledger.ForecastIntegrityError, match="after cutoff"):
        forecast_ledger.generate_and_freeze_incumbent(
            ledger,
            "TEST",
            horizons=[ultimate.HORIZON_BY_KEY["1d"]],
            fetcher=_fetcher(frame),
            cutoff_at=cutoff,
        )

    assert ledger.list() == []


def test_rewriting_data_after_cutoff_cannot_change_stored_forecast(tmp_path):
    split = 800
    calm = _frame()
    storm = calm.copy(deep=True)
    storm.loc[split:, "close"] *= np.linspace(1.0, 0.2, len(storm) - split)
    cutoff = calm["date"].iloc[split - 1]
    generated_at = pd.Timestamp("2025-01-01", tz="UTC")

    def pit_fetcher(source: pd.DataFrame):
        truncated = source.loc[source["date"] <= cutoff].reset_index(drop=True)
        return _fetcher(truncated)

    left = forecast_ledger.ForecastLedger(tmp_path / "left.sqlite3")
    right = forecast_ledger.ForecastLedger(tmp_path / "right.sqlite3")
    _, left_records = forecast_ledger.generate_and_freeze_incumbent(
        left,
        "TEST",
        horizons=[ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]],
        fetcher=pit_fetcher(calm),
        generated_at=generated_at,
        cutoff_at=cutoff,
    )
    _, right_records = forecast_ledger.generate_and_freeze_incumbent(
        right,
        "TEST",
        horizons=[ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]],
        fetcher=pit_fetcher(storm),
        generated_at=generated_at,
        cutoff_at=cutoff,
    )

    assert [record.forecast_id for record in left_records] == [
        record.forecast_id for record in right_records
    ]
    for first, second in zip(left_records, right_records):
        assert first.cutoff_at == second.cutoff_at
        assert first.input_fingerprint == second.input_fingerprint
        assert first.model_predictions == second.model_predictions
        assert first.model_weights == second.model_weights
        assert pd.Timestamp(first.input_last_bar_at) <= pd.Timestamp(cutoff, tz="UTC")


def test_challenger_projection_freezes_path_and_training_identity(tmp_path):
    frame = _frame(rows=180)
    projection = forecast.Projection(
        model="LSTM",
        path=np.array([121.0, 123.0, 125.0]),
        horizon=3,
        last_price=float(frame["close"].iloc[-1]),
        last_date=frame["date"].iloc[-1],
    )
    metadata = {
        "num_layers": 1,
        "size_layer": 64,
        "timestamp": 5,
        "epochs": 20,
        "dropout": 0.8,
        "learning_rate": 0.01,
        "training_first_bar": frame["date"].iloc[0],
        "training_last_bar": frame["date"].iloc[-1],
        "training_rows": len(frame),
    }

    record = forecast_ledger.challenger_record(
        projection,
        symbol="TEST",
        input_frame=frame,
        interval="1d",
        model_version="lstm-settings-sha256:abc123",
        training_metadata=metadata,
    )
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    ledger.insert(record)
    loaded = ledger.load(record.forecast_id)

    assert loaded == record
    assert loaded.production_or_challenger == forecast_ledger.CHALLENGER
    assert loaded.source_path == "app.core.forecast.project"
    assert loaded.model_predictions["model"]["path"] == (121.0, 123.0, 125.0)
    assert loaded.model_versions["neural_challenger"] == "lstm-settings-sha256:abc123"
    assert loaded.metadata["training"]["training_rows"] == len(frame)
    assert loaded.probability_positive is None


def test_challenger_requires_complete_training_metadata():
    frame = _frame(rows=180)
    projection = forecast.Projection(
        model="GRU", path=np.array([101.0]), horizon=1,
        last_price=float(frame["close"].iloc[-1]), last_date=frame["date"].iloc[-1],
    )

    with pytest.raises(ValueError, match="training_metadata missing"):
        forecast_ledger.challenger_record(
            projection,
            symbol="TEST",
            input_frame=frame,
            interval="1d",
            model_version="gru-v1",
            training_metadata={},
        )


def test_challenger_rejects_training_window_mismatch():
    frame = _frame(rows=180)
    projection = forecast.Projection(
        model="LSTM", path=np.array([101.0]), horizon=1,
        last_price=float(frame["close"].iloc[-1]), last_date=frame["date"].iloc[-1],
    )
    metadata = {
        "num_layers": 1,
        "size_layer": 64,
        "timestamp": 5,
        "epochs": 20,
        "dropout": 0.8,
        "learning_rate": 0.01,
        "training_first_bar": frame["date"].iloc[1],
        "training_last_bar": frame["date"].iloc[-1],
        "training_rows": len(frame),
    }

    with pytest.raises(forecast_ledger.ForecastIntegrityError, match="training start"):
        forecast_ledger.challenger_record(
            projection,
            symbol="TEST",
            input_frame=frame,
            interval="1d",
            model_version="lstm-v1",
            training_metadata=metadata,
        )
