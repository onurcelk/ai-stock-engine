"""V5 Phase 3: every predictive component has one identity and one standing.

The tests that matter here are the census tests and the guard tests. The
census tests fail when a model is added to the application without being
registered; the guard tests fail when something without production standing
reaches a production forecast. Both are meant to break loudly.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from core import (
    agents,
    forecast,
    forecast_ledger,
    indicators,
    model_registry,
    outcome_ledger,
    ultimate,
)


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
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    _, records = forecast_ledger.generate_and_freeze_incumbent(
        ledger,
        "TEST",
        horizons=[ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]],
        fetcher=_fetcher(observed),
    )
    return ledger, {record.horizon: record for record in records}


def _challenger(frame: pd.DataFrame, *, steps: int = 3, model: str = "LSTM"):
    projection = forecast.Projection(
        model=model,
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
        training_metadata={
            "num_layers": 1, "size_layer": 64, "timestamp": 5, "epochs": 20,
            "dropout": 0.8, "learning_rate": 0.01,
            "training_first_bar": frame["date"].iloc[0],
            "training_last_bar": frame["date"].iloc[-1],
            "training_rows": len(frame),
        },
    )


def _rewrite(record, **changes):
    """A record with fields replaced and its identity hash recomputed.

    Only tests do this. It exists so a tampered or mislabelled forecast can be
    handed to the guards without weakening `ForecastRecord`'s own invariants.
    """
    payload = record.payload()
    payload.update(changes)
    payload.pop("forecast_id")
    identity = {key: forecast_ledger._normalise_json(value)
                for key, value in payload.items()}
    return forecast_ledger.ForecastRecord(
        forecast_id="fcst_" + forecast_ledger._digest(identity), **payload
    )


# ------------------------------------------------------------------- census


def test_every_technical_source_is_registered():
    registered = {
        spec.record_key for spec in model_registry.specs()
        if spec.family == model_registry.TECHNICAL_INDICATOR
    }
    assert registered == set(indicators.SOURCES)


def test_every_trainable_agent_is_registered():
    registered = {
        spec.label for spec in model_registry.specs()
        if spec.model_id.startswith("rl.")
    }
    assert registered == set(agents.REGISTRY)


def test_every_recurrent_architecture_is_registered():
    registered = {
        spec.model_id for spec in model_registry.specs()
        if spec.model_id.startswith("neural.")
    }
    expected = {f"neural.{name.lower().replace(' ', '_')}" for name in forecast.MODELS}
    assert registered == expected


def test_registered_horizons_match_the_production_engine():
    engine = tuple(horizon.key for horizon in ultimate.HORIZONS)
    ensemble = model_registry.get(model_registry.ULTIMATE_ENSEMBLE)
    assert ensemble.horizons == engine
    for spec in model_registry.production_models():
        assert spec.horizons == engine


def test_registry_families_agree_with_the_frozen_agent_audit():
    """The taxonomy is reproduced, not reinvented.

    `alpha/agents_audit.py` froze the rule and RL family assignment before any
    outcome was read. The registry copies it by name rather than importing it,
    because `alpha` imports `app.core`; this test is what keeps the two
    copies honest.
    """
    from alpha.agents_audit import FAMILY_OF

    for spec in model_registry.specs():
        if spec.label in FAMILY_OF:
            assert spec.family == FAMILY_OF[spec.label], spec.model_id


def test_model_ids_and_record_keys_are_unique():
    specs = model_registry.specs()
    assert len({spec.model_id for spec in specs}) == len(specs)
    # "model" is deliberately shared by the three recurrent architectures,
    # which are separated by the prediction's own name.
    keys = [spec.record_key for spec in specs if spec.record_key is not None]
    assert len(set(keys)) == len(keys) - 2


# ------------------------------------------------------------------ metadata


def test_every_spec_declares_the_required_metadata():
    for spec in model_registry.specs():
        assert spec.model_id and spec.label and spec.implementation
        assert spec.family and spec.target
        assert spec.required_features
        assert spec.training_cutoff and spec.retraining_policy
        assert spec.pit_status in {
            model_registry.PIT_ADMISSIBLE, model_registry.PIT_CONDITIONAL,
            model_registry.PIT_INADMISSIBLE, model_registry.PIT_NOT_APPLICABLE,
        }
        assert spec.production_status in model_registry.STATUSES
        assert spec.version


def test_version_is_the_exact_source_in_use():
    """A registry version and a ledger version are the same string."""
    ensemble = model_registry.get(model_registry.ULTIMATE_ENSEMBLE)
    assert ensemble.version == forecast_ledger._module_version(ultimate)
    assert model_registry.get("technical.rsi").version == (
        forecast_ledger._module_version(indicators)
    )
    assert ensemble.version.startswith("sha256:")


def test_specs_are_frozen():
    spec = model_registry.get("technical.rsi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.production_status = model_registry.REJECTED  # type: ignore[misc]


def test_a_barred_model_cannot_declare_a_ledger_key():
    """The dataclass refuses the shape that would let a rejected model in."""
    with pytest.raises(ValueError, match="have no ledger key"):
        model_registry.ModelSpec(
            model_id="rl.smuggled",
            label="Smuggled agent",
            family=model_registry.VALUE_RL,
            implementation="app/core/agents/qlearning.py",
            target="trade action",
            horizons=(),
            required_features=("close",),
            training_cutoff="whole series",
            retraining_policy="none",
            pit_status=model_registry.PIT_INADMISSIBLE,
            production_status=model_registry.EXPERIMENTAL,
            output_kind=model_registry.SIGNAL_SCORE,
            score_class=model_registry.DIRECTIONAL_ONLY,
            version_module="app.core.agents.qlearning",
            record_key="agent_turtle",
            version_key="rule_agents",
        )


# ------------------------------------------------------------------ statuses


def test_production_is_exactly_the_incumbent_ensemble_and_its_sources():
    production = {spec.model_id for spec in model_registry.production_models()}
    expected = (
        {model_registry.ULTIMATE_ENSEMBLE}
        | {f"technical.{key}" for key in indicators.SOURCES}
        | {"rule_agent.turtle", "rule_agent.crossover", "rule_agent.rolling"}
    )
    assert production == expected


def test_every_trainable_agent_is_barred_from_production():
    """Same-series training and replay is the repository's own red line."""
    for spec in model_registry.specs():
        if spec.model_id.startswith("rl."):
            assert spec.production_status == model_registry.EXPERIMENTAL
            assert spec.pit_status == model_registry.PIT_INADMISSIBLE
            assert not spec.production_admissible
            assert spec.record_key is None


def test_closed_programmes_are_registered_as_rejected_with_evidence():
    closed = [spec for spec in model_registry.specs()
              if spec.model_id.startswith(("closed.", "blocked."))]
    assert len(closed) == 6
    for spec in closed:
        assert spec.production_status == model_registry.REJECTED
        assert spec.evidence, spec.model_id
        assert spec.notes, spec.model_id
        with pytest.raises(model_registry.RejectedModelError):
            model_registry.assert_not_reopened(spec.model_id)


def test_the_leaky_single_split_forecaster_is_retired():
    spec = model_registry.get("retired.forecast_single_split")
    assert spec.production_status == model_registry.RETIRED
    assert spec.pit_status == model_registry.PIT_INADMISSIBLE
    with pytest.raises(model_registry.RejectedModelError):
        model_registry.assert_production_admissible(spec.model_id)


def test_an_unregistered_model_is_never_silently_accepted():
    with pytest.raises(model_registry.UnregisteredModelError):
        model_registry.get("technical.invented")
    with pytest.raises(model_registry.UnregisteredModelError):
        model_registry.resolve_constituent("agent_invented")
    with pytest.raises(model_registry.UnregisteredModelError):
        model_registry.resolve_constituent("model", {"name": "Transformer"})


# ------------------------------------------------ one scoring framework


def test_incumbent_and_challenger_are_comparable_on_the_same_metrics():
    """The Phase 3 gate, stated as an assertion.

    The production ensemble and the neural challenger both emit a percentage
    return, so both admit the same metric set, so one scoring framework can
    rank them. Signal-only constituents admit strictly fewer metrics — that is
    a declared limit, not a silent one.
    """
    ensemble = model_registry.get(model_registry.ULTIMATE_ENSEMBLE)
    challenger = model_registry.get("neural.lstm")
    assert ensemble.output_kind == challenger.output_kind == model_registry.RETURN_PCT
    assert ensemble.metrics == challenger.metrics
    assert "mae" in ensemble.metrics and "directional_accuracy" in ensemble.metrics

    source = model_registry.get("technical.rsi")
    assert source.output_kind == model_registry.SIGNAL_SCORE
    assert set(source.metrics) < set(ensemble.metrics)


def test_declared_metrics_exist_in_the_phase_2_summary(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    pairs = [(record, outcome_ledger.resolve_outcome(record, full))
             for record in records.values()]
    summary = outcome_ledger.summarise(outcome_ledger.performance_frame(pairs))

    ensemble = model_registry.get(model_registry.ULTIMATE_ENSEMBLE)
    for metric in ensemble.metrics:
        assert metric in summary.columns


# ------------------------------------------------------ record resolution


def test_a_frozen_incumbent_resolves_to_registry_identity(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    record = records["1d"]

    assert model_registry.record_spec(record).model_id == (
        model_registry.ULTIMATE_ENSEMBLE
    )
    assert model_registry.record_version(record) == (
        record.model_versions["ultimate_ensemble"]
    )
    ids = model_registry.constituent_ids(record)
    assert ids["ensemble"] == model_registry.ULTIMATE_ENSEMBLE
    assert ids["trend_ma"] == "technical.trend_ma"
    assert ids["agent_turtle"] == "rule_agent.turtle"


def test_a_frozen_challenger_resolves_to_its_architecture(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    record = _challenger(observed)
    assert model_registry.record_spec(record).model_id == "neural.lstm"
    assert model_registry.record_version(record) == "lstm-v1"


def test_every_constituent_output_identifies_its_version(tmp_path):
    """Phase 3's version task, checked on a real frozen record."""
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    record = records["1w"]

    versions = model_registry.resolve_versions(record)
    assert set(versions) == set(model_registry.constituent_ids(record).values())
    assert all(version for version in versions.values())
    assert versions["technical.rsi"] == record.model_versions["technical_sources"]
    assert versions["rule_agent.turtle"] == record.model_versions["rule_agents"]


def test_a_forecast_that_hides_a_version_is_refused(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    stripped = _rewrite(
        records["1d"],
        model_versions={"ultimate_ensemble": records["1d"].model_versions[
            "ultimate_ensemble"]},
    )
    with pytest.raises(model_registry.ModelVersionError):
        model_registry.resolve_versions(stripped)


def test_version_drift_is_reported_and_never_gated(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    record = records["1d"]
    assert model_registry.version_drift(record) == {}

    stale = _rewrite(record, model_versions={
        **record.payload()["model_versions"], "technical_sources": "sha256:stale",
    })
    drift = model_registry.version_drift(stale)
    assert set(drift) == {f"technical.{key}" for key in indicators.SOURCES}
    assert drift["technical.rsi"][0] == "sha256:stale"
    # Drift is a diagnostic: the record is still admissible.
    model_registry.assert_record_admissible(stale)


# --------------------------------------------------------------- the guard


def test_a_clean_production_forecast_is_admissible(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    for record in records.values():
        assert model_registry.assert_record_admissible(record).model_id == (
            model_registry.ULTIMATE_ENSEMBLE
        )


def test_a_challenger_forecast_is_admissible(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    record = _challenger(observed)
    assert model_registry.assert_record_admissible(record).model_id == "neural.lstm"


def test_a_rejected_model_cannot_reach_a_production_forecast(tmp_path):
    """The task this phase exists for.

    A same-series RL stance is folded into a production verdict under a new
    constituent key. The registry does not know it, so the record is refused
    rather than scored as if the incumbent had said it.
    """
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    record = records["1d"]

    smuggled = _rewrite(record, model_predictions={
        **record.payload()["model_predictions"],
        "agent_qlearning": {"name": "Q-learning", "direction": "bullish",
                            "score": 1.0},
    })
    with pytest.raises(model_registry.UnregisteredModelError):
        model_registry.assert_record_admissible(smuggled)


def test_a_record_cannot_claim_a_status_its_model_does_not_hold(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    record = _challenger(observed)
    mislabelled = _rewrite(
        record, production_or_challenger=forecast_ledger.PRODUCTION_INCUMBENT
    )
    with pytest.raises(model_registry.RejectedModelError, match="CHALLENGER"):
        model_registry.assert_record_admissible(mislabelled)


def test_the_guard_names_the_evidence_when_it_refuses():
    with pytest.raises(model_registry.RejectedModelError) as raised:
        model_registry.assert_production_admissible("rl.q_learning")
    message = str(raised.value)
    assert "EXPERIMENTAL" in message
    assert "agents_audit" in message


def test_registry_reads_only_and_never_scores():
    """Phase 3 formalises identity; it does not open the outcome side.

    Checked on the import graph rather than on the text, because the module's
    own docstring explains what it replaced in `outcome_ledger` and a
    substring test would read that as a dependency.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(model_registry))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(alias.name for alias in node.names)
    assert "outcome_ledger" not in imported
    assert not any("outcome" in name for name in imported)

    # The dependency arrow points one way: scoring may name the registry.
    assert "model_registry" in inspect.getsource(outcome_ledger)
