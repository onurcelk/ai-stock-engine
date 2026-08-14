"""V5 outcome scoring reads frozen forecasts and never writes them back."""

from __future__ import annotations

import inspect
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core import forecast, forecast_ledger, outcome_ledger, ultimate


TOTAL_ROWS = 920
CUTOFF_ROWS = 900


def _frame(*, rows: int = TOTAL_ROWS, seed: int = 23) -> pd.DataFrame:
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
        return frame.copy(deep=True), None
    return fetch


def _freeze(tmp_path, observed: pd.DataFrame):
    """Freeze 1d and 1w incumbent forecasts on the observed history only."""
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    _, records = forecast_ledger.generate_and_freeze_incumbent(
        ledger,
        "TEST",
        horizons=[ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]],
        fetcher=_fetcher(observed),
    )
    return ledger, {record.horizon: record for record in records}


def _store(tmp_path) -> outcome_ledger.OutcomeStore:
    return outcome_ledger.OutcomeStore(tmp_path / "forecasts.sqlite3")


def _frames(realised: pd.DataFrame):
    def supply(symbol: str, interval: str):
        return realised.copy(deep=True)
    return supply


# ----------------------------------------------------------------- matching


def test_matured_forecast_scores_against_the_realised_bar(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)
    record = records["1d"]

    outcome = outcome_ledger.resolve_outcome(record, full)

    anchor_close = float(full["close"].iloc[CUTOFF_ROWS - 1])
    matured_close = float(full["close"].iloc[CUTOFF_ROWS])
    expected = (matured_close / anchor_close - 1.0) * 100.0

    assert outcome is not None
    assert outcome.forecast_id == record.forecast_id
    assert outcome.bars_ahead == 1
    assert outcome.interval == "1d"
    assert outcome.price_at_maturity == pytest.approx(matured_close)
    assert outcome.realised_return == pytest.approx(expected)
    assert outcome.realised_direction == ("bullish" if expected > 0 else "bearish")
    assert outcome.error == pytest.approx(record.predicted_return - expected)
    assert outcome.absolute_error == pytest.approx(abs(record.predicted_return - expected))
    assert outcome.squared_error == pytest.approx(outcome.absolute_error ** 2)
    assert pd.Timestamp(outcome.matured_at) == pd.Timestamp(
        full["date"].iloc[CUTOFF_ROWS], tz="UTC"
    )


def test_scoring_is_horizon_aware(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)

    daily = outcome_ledger.resolve_outcome(records["1d"], full)
    weekly = outcome_ledger.resolve_outcome(records["1w"], full)

    assert daily.bars_ahead == 1
    assert weekly.bars_ahead == 5
    assert pd.Timestamp(weekly.matured_at) == pd.Timestamp(
        full["date"].iloc[CUTOFF_ROWS + 4], tz="UTC"
    )
    assert weekly.realised_return == pytest.approx(
        (float(full["close"].iloc[CUTOFF_ROWS + 4])
         / float(full["close"].iloc[CUTOFF_ROWS - 1]) - 1.0) * 100.0
    )
    assert daily.realised_return != weekly.realised_return


def test_unmatured_forecast_has_no_outcome(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)
    # Two bars of the future exist: the 1-bar horizon has matured, the 5-bar
    # horizon has not.
    partial = full.iloc[:CUTOFF_ROWS + 2].copy()

    assert outcome_ledger.resolve_outcome(records["1d"], partial) is not None
    assert outcome_ledger.resolve_outcome(records["1w"], partial) is None


def test_score_matured_skips_unmatured_and_never_rescores(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)
    store = _store(tmp_path)

    first = outcome_ledger.score_matured(
        ledger, store, _frames(full.iloc[:CUTOFF_ROWS + 2].copy())
    )
    assert [outcome.horizon for outcome in first] == ["1d"]

    second = outcome_ledger.score_matured(ledger, store, _frames(full))
    assert [outcome.horizon for outcome in second] == ["1w"]

    assert outcome_ledger.score_matured(ledger, store, _frames(full)) == []
    assert store.scored_ids() == {records["1d"].forecast_id, records["1w"].forecast_id}


# ------------------------------------------------------------- leak control


def test_prices_after_maturity_cannot_change_the_score(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)
    record = records["1w"]

    calm = outcome_ledger.resolve_outcome(
        record, full, scored_at=pd.Timestamp("2030-01-01", tz="UTC")
    )

    storm = full.copy()
    beyond = CUTOFF_ROWS + 5  # every bar strictly after the maturity bar
    for column in ("open", "high", "low", "close"):
        storm.loc[storm.index[beyond:], column] = 1.0
    storm.loc[storm.index[beyond:], "volume"] = 0.0

    stormy = outcome_ledger.resolve_outcome(
        record, storm, scored_at=pd.Timestamp("2030-01-01", tz="UTC")
    )

    assert stormy == calm
    assert stormy.outcome_id == calm.outcome_id
    assert stormy.realised_fingerprint == calm.realised_fingerprint


def test_scoring_leaves_the_frozen_forecast_byte_identical(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)
    store = _store(tmp_path)

    with sqlite3.connect(ledger.path) as connection:
        before = connection.execute(
            "SELECT forecast_id, payload, payload_sha256 FROM forecasts "
            "ORDER BY forecast_id"
        ).fetchall()

    outcome_ledger.score_matured(ledger, store, _frames(full))

    with sqlite3.connect(ledger.path) as connection:
        after = connection.execute(
            "SELECT forecast_id, payload, payload_sha256 FROM forecasts "
            "ORDER BY forecast_id"
        ).fetchall()

    assert before == after
    assert ledger.load(records["1d"].forecast_id) == records["1d"]


def test_realised_anchor_must_match_the_frozen_price(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)

    tampered = full.copy()
    tampered.loc[tampered.index[CUTOFF_ROWS - 1], "close"] *= 1.05

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="anchor price"):
        outcome_ledger.resolve_outcome(records["1d"], tampered)


def test_missing_anchor_bar_is_refused(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)

    gapped = full.drop(index=full.index[CUTOFF_ROWS - 1]).reset_index(drop=True)

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="exactly one bar"):
        outcome_ledger.resolve_outcome(records["1d"], gapped)


def test_forecast_ledger_holds_no_outcome_access():
    """The two-process separation is structural, not a convention."""
    forecast_source = inspect.getsource(forecast_ledger)
    assert "outcome_ledger" not in forecast_source
    assert "outcomes" not in forecast_source
    assert "realised" not in forecast_source

    outcome_source = inspect.getsource(outcome_ledger)
    assert "INSERT INTO forecasts" not in outcome_source
    assert "UPDATE forecasts" not in outcome_source
    assert "DELETE FROM forecasts" not in outcome_source


def test_scoring_never_regenerates_a_forecast(tmp_path, monkeypatch):
    """The Phase 2 gate: historical predictions score without a model call."""
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, _ = _freeze(tmp_path, observed)
    store = _store(tmp_path)

    def explode(*args, **kwargs):
        raise AssertionError("scoring must not evaluate a model")

    monkeypatch.setattr(ultimate, "evaluate", explode)
    monkeypatch.setattr(forecast, "project", explode)

    assert len(outcome_ledger.score_matured(ledger, store, _frames(full))) == 2


# ------------------------------------------------------------ immutability


def test_outcome_cannot_be_written_twice(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    store = _store(tmp_path)
    outcome = outcome_ledger.resolve_outcome(records["1d"], full)
    store.insert(outcome)

    with pytest.raises(outcome_ledger.OutcomeExistsError):
        store.insert(outcome)

    later = outcome_ledger.resolve_outcome(
        records["1d"], full, scored_at=pd.Timestamp("2031-01-01", tz="UTC")
    )
    assert later.outcome_id != outcome.outcome_id
    with pytest.raises(outcome_ledger.OutcomeExistsError):
        store.insert(later)

    assert store.load(records["1d"].forecast_id) == outcome


def test_database_rejects_outcome_updates_and_deletes(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    store = _store(tmp_path)
    store.insert(outcome_ledger.resolve_outcome(records["1d"], full))

    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE outcomes SET payload = '{}'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM outcomes")

    assert len(store.list()) == 1


def test_outcome_requires_an_existing_frozen_forecast(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    outcome = outcome_ledger.resolve_outcome(records["1d"], full)

    orphan = outcome_ledger.OutcomeStore(tmp_path / "orphan.sqlite3")
    with sqlite3.connect(orphan.path) as connection:
        connection.executescript(
            "CREATE TABLE IF NOT EXISTS forecasts (forecast_id TEXT PRIMARY KEY);"
        )

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="not frozen"):
        orphan.insert(outcome)


def test_stored_outcome_round_trips_and_detects_tampering(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    store = _store(tmp_path)
    outcome = outcome_ledger.resolve_outcome(records["1d"], full)
    store.insert(outcome)

    assert store.load(outcome.forecast_id) == outcome

    with sqlite3.connect(store.path) as connection:
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute("DROP TRIGGER outcomes_no_update")
        connection.execute(
            "UPDATE outcomes SET payload = json_set(payload, '$.realised_return', 99.0)"
        )

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="integrity check"):
        store.load(outcome.forecast_id)


# --------------------------------------------------------------- baselines


def test_trivial_baseline_is_built_from_forecast_time_information(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    record = records["1w"]
    outcome = outcome_ledger.resolve_outcome(record, full)

    assert record.baseline_prediction is None
    assert outcome.baseline_source == outcome_ledger.BASELINE_PHASE2_TRIVIAL
    # zero_return is the control for error; always_bullish for direction.
    assert outcome.baseline_absolute_error == pytest.approx(abs(outcome.realised_return))
    assert outcome.baseline_directional_correct == (outcome.realised_return > 0)
    assert outcome.baseline_relative_absolute_error == pytest.approx(
        outcome.baseline_absolute_error - outcome.absolute_error
    )


def test_forecast_time_baseline_overrides_the_trivial_control(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    _, records = forecast_ledger.generate_and_freeze_incumbent(
        ledger, "TEST",
        horizons=[ultimate.HORIZON_BY_KEY["1d"]],
        fetcher=_fetcher(observed),
        baseline_prediction={"predicted_return": 0.5, "predicted_direction": "bullish"},
    )
    outcome = outcome_ledger.resolve_outcome(records[0], full)

    assert outcome.baseline_source == outcome_ledger.BASELINE_FROM_RECORD
    assert outcome.baseline_absolute_error == pytest.approx(
        abs(0.5 - outcome.realised_return)
    )


def test_market_relative_outcome_uses_the_identical_window(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    market = _frame(seed=101)
    market["date"] = full["date"]

    outcome = outcome_ledger.resolve_outcome(
        records["1w"], full, market_frame=market, market_symbol="SPY"
    )

    expected = (float(market["close"].iloc[CUTOFF_ROWS + 4])
                / float(market["close"].iloc[CUTOFF_ROWS - 1]) - 1.0) * 100.0
    assert outcome.market_symbol == "SPY"
    assert outcome.market_return == pytest.approx(expected)
    assert outcome.market_relative_return == pytest.approx(
        outcome.realised_return - expected
    )
    assert outcome.sector_relative_return is None
    assert outcome.notes["sector_status"] == "UNAVAILABLE_NO_PIT_SECTOR_MAP"


# ----------------------------------------------------- probability scoring


def _challenger(frame: pd.DataFrame, *, probability: float | None, steps: int = 3):
    projection = forecast.Projection(
        model="LSTM",
        path=np.array([float(frame["close"].iloc[-1]) * 1.01] * steps),
        horizon=steps,
        last_price=float(frame["close"].iloc[-1]),
        last_date=frame["date"].iloc[-1],
    )
    return forecast_ledger.challenger_record(
        projection,
        symbol="TEST",
        input_frame=frame,
        interval="1d",
        model_version="lstm-v1",
        probability_positive=probability,
        training_metadata={
            "num_layers": 1, "size_layer": 64, "timestamp": 5, "epochs": 20,
            "dropout": 0.8, "learning_rate": 0.01,
            "training_first_bar": frame["date"].iloc[0],
            "training_last_bar": frame["date"].iloc[-1],
            "training_rows": len(frame),
        },
    )


def test_challenger_horizon_and_brier_are_scored(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    record = _challenger(observed, probability=0.75)
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    ledger.insert(record)

    outcome = outcome_ledger.resolve_outcome(record, full)

    assert outcome.horizon == "3x1d"
    assert outcome.bars_ahead == 3
    assert pd.Timestamp(outcome.matured_at) == pd.Timestamp(
        full["date"].iloc[CUTOFF_ROWS + 2], tz="UTC"
    )
    observed_bit = 1.0 if outcome.realised_return > 0 else 0.0
    assert outcome.brier_contribution == pytest.approx((0.75 - observed_bit) ** 2)
    assert outcome.notes["probability_status"] == "SCORED"


def test_a_neutral_forecast_abstains_rather_than_scoring_wrong(tmp_path):
    """Declining to name a direction is not a directional miss."""
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    record = records["1d"]
    outcome = outcome_ledger.resolve_outcome(record, full)

    assert record.predicted_direction == "neutral"
    assert outcome.realised_direction != "neutral"
    assert outcome.directional_correct is None

    frame = outcome_ledger.performance_frame([(record, outcome)])
    row = outcome_ledger.summarise(frame).iloc[0]
    assert row["n"] == 1
    assert row["n_directional"] == 0
    assert np.isnan(row["directional_accuracy"])
    # The return error is still scoreable even when the direction abstained.
    assert row["mae"] == pytest.approx(abs(outcome.realised_return))


def test_confidence_is_never_scored_as_a_probability(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    record = records["1d"]
    outcome = outcome_ledger.resolve_outcome(record, full)

    assert record.confidence is not None
    assert outcome.probability_positive is None
    assert outcome.brier_contribution is None
    assert outcome.notes["probability_status"] == "NO_PROBABILISTIC_FORECAST"

    frame = outcome_ledger.performance_frame([(record, outcome)])
    assert outcome_ledger.calibration(frame).empty


# ------------------------------------------------------ performance memory


def _synthetic(n: int, *, hits: int, model: str = "m", horizon: str = "1d",
               probability: float | None = None) -> pd.DataFrame:
    rows = []
    for index in range(n):
        correct = index < hits
        realised = 1.0 if index % 2 == 0 else -1.0
        predicted = realised if correct else -realised
        error = predicted - realised
        rows.append({
            "forecast_id": f"fcst_{model}_{horizon}_{index:03d}",
            "model_key": model,
            "status": "PRODUCTION_INCUMBENT",
            "symbol": "TEST",
            "horizon": horizon,
            "interval": "1d",
            "bars_ahead": 1,
            "cutoff_at": pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=index),
            "matured_at": pd.Timestamp("2024-01-02", tz="UTC") + pd.Timedelta(days=index),
            "predicted_return": predicted,
            "realised_return": realised,
            "predicted_direction": "bullish" if predicted > 0 else "bearish",
            "realised_direction": "bullish" if realised > 0 else "bearish",
            "error": error,
            "absolute_error": abs(error),
            "squared_error": error ** 2,
            "directional_correct": correct,
            "confidence": 50.0,
            "probability_positive": probability,
            "brier_contribution": (
                None if probability is None
                else (probability - (1.0 if realised > 0 else 0.0)) ** 2
            ),
            "baseline_source": outcome_ledger.BASELINE_PHASE2_TRIVIAL,
            "baseline_absolute_error": abs(realised),
            "baseline_squared_error": realised ** 2,
            "baseline_directional_correct": realised > 0,
            "baseline_relative_absolute_error": abs(realised) - abs(error),
            "market_relative_return": None,
            "sector_relative_return": None,
        })
    return pd.DataFrame(rows)


def test_summary_reports_sample_size_and_resolution():
    frame = _synthetic(40, hits=28)
    summary = outcome_ledger.summarise(frame)

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["n"] == 40
    assert row["n_directional"] == 40
    assert row["directional_accuracy"] == pytest.approx(0.7)
    assert row["directional_ci_low"] < 0.7 < row["directional_ci_high"]
    assert row["baseline_directional_accuracy"] == pytest.approx(0.5)
    assert np.isfinite(row["mae_half_width"])
    assert row["mae"] < row["baseline_mae"]
    assert row["mae_skill"] > 0
    assert np.isnan(row["brier"])
    assert row["n_probabilistic"] == 0


def test_a_forecast_worse_than_its_baseline_scores_negative_skill():
    frame = _synthetic(40, hits=0)
    row = outcome_ledger.summarise(frame).iloc[0]

    assert row["directional_accuracy"] == 0.0
    assert row["mae_skill"] < 0
    assert row["mae_advantage"] < 0


def test_breakdowns_are_suppressed_below_the_declared_sample_floor():
    thin = _synthetic(5, hits=4, model="thin")
    thick = _synthetic(40, hits=28, model="thick")
    frame = pd.concat([thin, thick], ignore_index=True)

    cut = outcome_ledger.breakdown(frame, by=("model_key",), min_samples=30)
    thin_row = cut.loc[cut["model_key"] == "thin"].iloc[0]
    thick_row = cut.loc[cut["model_key"] == "thick"].iloc[0]

    assert not thin_row["sufficient"]
    assert thin_row["n"] == 5
    assert np.isnan(thin_row["directional_accuracy"])
    assert bool(thick_row["sufficient"])
    assert thick_row["directional_accuracy"] == pytest.approx(0.7)


def test_rolling_and_expanding_summaries_advance_with_maturity():
    frame = _synthetic(40, hits=20)

    expanding = outcome_ledger.expanding_summary(frame)
    rolling = outcome_ledger.rolling_summary(frame, window=10)

    assert len(expanding) == len(rolling) == 40
    assert list(expanding["n"]) == list(range(1, 41))
    assert list(rolling["n"])[:10] == list(range(1, 11))
    assert set(rolling["n"][10:]) == {10}
    assert expanding["matured_at"].is_monotonic_increasing
    # The first twenty were hits, so a trailing window forgets them and the
    # all-history view does not.
    assert rolling["directional_accuracy"].iloc[-1] == 0.0
    assert expanding["directional_accuracy"].iloc[-1] == pytest.approx(0.5)


def test_performance_memory_is_known_only_after_maturity():
    frame = _synthetic(40, hits=20)
    cutoff_max = frame["cutoff_at"].max()

    visible = outcome_ledger.known_as_of(frame, frame["matured_at"].iloc[9])
    assert len(visible) == 10
    assert (visible["matured_at"] <= frame["matured_at"].iloc[9]).all()

    # Filtering on cutoff would admit an outcome that had not happened yet.
    assert len(outcome_ledger.known_as_of(frame, cutoff_max)) < len(
        frame.loc[frame["cutoff_at"] <= cutoff_max]
    )


def test_calibration_reports_bins_with_counts_and_intervals():
    confident = _synthetic(30, hits=30, model="m", probability=0.9)
    unsure = _synthetic(30, hits=0, model="m", horizon="1w", probability=0.1)
    table = outcome_ledger.calibration(pd.concat([confident, unsure], ignore_index=True))

    assert len(table) == 2
    assert set(table["n"]) == {30}
    assert (table["observed_ci_low"] <= table["observed_rate"]).all()
    assert (table["observed_rate"] <= table["observed_ci_high"]).all()
    assert table["mean_predicted"].tolist() == pytest.approx([0.1, 0.9])


def test_constituent_directional_diagnostic_carries_counts(tmp_path):
    full = _frame()
    ledger, records = _freeze(tmp_path, full.iloc[:CUTOFF_ROWS].copy())
    pairs = [
        (record, outcome_ledger.resolve_outcome(record, full))
        for record in records.values()
    ]

    table = outcome_ledger.constituent_directional(pairs)

    assert not table.empty
    assert "ensemble" not in set(table["constituent"])
    assert (table["n_directional"] >= 1).all()
    assert ((0.0 <= table["hit_rate"]) & (table["hit_rate"] <= 1.0)).all()
    assert not table["sufficient"].any()  # two forecasts is not evidence


def test_model_key_separates_incumbent_from_challenger(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)
    challenger = _challenger(observed, probability=None)
    ledger.insert(challenger)

    pairs = [
        (record, outcome_ledger.resolve_outcome(record, full))
        for record in list(records.values()) + [challenger]
    ]
    frame = outcome_ledger.performance_frame(pairs)
    summary = outcome_ledger.summarise(frame)

    # Phase 3 replaced the placeholder identities with registry model ids, and
    # split the version into its own column so pooling across versions is a
    # choice a caller makes rather than one the key makes for them.
    assert set(frame["model_key"]) == {"ensemble.ultimate", "neural.lstm"}
    assert "lstm-v1" in set(frame["model_version"])
    assert set(summary["horizon"]) == {"1d", "1w", "3x1d"}
    assert (summary["n"] == 1).all()
