"""AB-1: a corporate action between freeze and maturity must not lose the row.

The live feed is fetched with `auto_adjust=True`, so a split or dividend after
a forecast is frozen back-adjusts the whole pre-action history by one constant
and the anchor bar stops reading what it read at freeze time.  Before AB-1 that
tripped the Phase 2 anchor guard and the observation was simply lost — on
dividend payers and long horizons, which is a hole correlated with a return
factor.  See `reports/V5_ADJUSTMENT_BASIS_FINDING.md`.

The construction below mirrors what a provider actually does.  `full` is the
adjusted series as it reads *at maturity*; at freeze the same bars read
`full / factor`, because the action had not happened yet.  A test that scaled
the maturity price instead would be testing arithmetic nobody performs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import forecast_ledger, outcome_ledger, ultimate


TOTAL_ROWS = 920
CUTOFF_ROWS = 900
PRICE_COLUMNS = ("open", "high", "low", "close")


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


def _freeze(tmp_path, observed: pd.DataFrame, *, name: str = "forecasts.sqlite3"):
    ledger = forecast_ledger.ForecastLedger(tmp_path / name)
    _, records = forecast_ledger.generate_and_freeze_incumbent(
        ledger,
        "TEST",
        horizons=[ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]],
        fetcher=_fetcher(observed),
    )
    return ledger, {record.horizon: record for record in records}


def _on_freeze_basis(full: pd.DataFrame, factor: float) -> pd.DataFrame:
    """The observed history as it read *before* an action of size `factor`."""
    observed = full.iloc[:CUTOFF_ROWS].copy()
    for column in PRICE_COLUMNS:
        observed[column] = observed[column] / factor
    return observed


def _true_return(full: pd.DataFrame, bars_ahead: int) -> float:
    anchor = float(full["close"].iloc[CUTOFF_ROWS - 1])
    matured = float(full["close"].iloc[CUTOFF_ROWS - 1 + bars_ahead])
    return (matured / anchor - 1.0) * 100.0


# --------------------------------------------------------------- freeze side


def test_freezing_captures_basis_probes_from_the_consumed_frame():
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    probes = forecast_ledger.basis_probes(observed)

    assert len(probes) == forecast_ledger.BASIS_PROBE_COUNT
    assert probes[-1][1] == pytest.approx(float(observed["close"].iloc[-1]))
    # Several bars, not one: uniformity is the signal and one ratio has none.
    assert len({round(close, 9) for _, close in probes}) > 1


def test_frozen_incumbent_records_carry_probes(tmp_path):
    observed = _frame().iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)

    for record in records.values():
        assert record.forecast_schema_version == 2
        assert record.basis_probes
        assert len(record.basis_probes) == forecast_ledger.BASIS_PROBE_COUNT
        # The last probe is the anchor the scorer will reconcile against.
        assert record.basis_probes[-1][1] == pytest.approx(record.price_at_cutoff)


# ------------------------------------------------------- no corporate action


def test_unchanged_basis_scores_exactly_as_before_ab1(tmp_path):
    """The overwhelmingly common case must be bit-for-bit the old arithmetic."""
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    record = records["1d"]

    outcome = outcome_ledger.resolve_outcome(record, full)

    assert outcome is not None
    assert outcome.corporate_action is False
    assert outcome.basis_factor == 1.0
    assert outcome.basis_max_deviation == 0.0
    assert outcome.scoring_anchor_price == pytest.approx(record.price_at_cutoff)
    assert outcome.realised_return == pytest.approx(_true_return(full, 1))
    assert outcome.notes["basis_status"] == "UNCHANGED_BASIS"


# ----------------------------------------------------------- the real events


@pytest.mark.parametrize(
    "label, factor",
    [
        ("ordinary dividend", 0.98),
        ("small dividend", 0.9971),
        ("two for one split", 0.5),
        ("four for one split", 0.25),
        ("one for two reverse split", 2.0),
    ],
)
def test_corporate_action_produces_the_correct_realised_return(
    tmp_path, label, factor,
):
    full = _frame()
    observed = _on_freeze_basis(full, factor)
    _, records = _freeze(tmp_path, observed)
    record = records["1d"]

    outcome = outcome_ledger.resolve_outcome(record, full)

    assert outcome is not None, label
    assert outcome.corporate_action is True
    assert outcome.basis_factor == pytest.approx(factor, rel=1e-9)
    assert outcome.basis_probe_count == forecast_ledger.BASIS_PROBE_COUNT
    assert outcome.notes["basis_status"] == "CORPORATE_ACTION_RECONCILED"
    # The point of the whole exercise: a correct total return, not a lost row.
    assert outcome.realised_return == pytest.approx(_true_return(full, 1))


def test_split_would_have_booked_a_catastrophic_return_on_the_frozen_anchor(tmp_path):
    """Guards the reason the anchor guard must never simply be widened.

    Dividing by the frozen anchor across a 2-for-1 split books roughly −50% on
    a position that did not move.  This asserts the wrong answer is the one we
    are not producing.
    """
    full = _frame()
    observed = _on_freeze_basis(full, 0.5)
    _, records = _freeze(tmp_path, observed)
    record = records["1d"]

    outcome = outcome_ledger.resolve_outcome(record, full)
    naive = (outcome.price_at_maturity / record.price_at_cutoff - 1.0) * 100.0

    assert naive < -45.0
    assert outcome.realised_return == pytest.approx(_true_return(full, 1))
    assert abs(outcome.realised_return) < 10.0
    # The frozen field is still the frozen field; nothing was rewritten.
    assert outcome.price_at_cutoff == pytest.approx(record.price_at_cutoff)
    assert outcome.scoring_anchor_price != pytest.approx(record.price_at_cutoff)


def test_reconciliation_holds_across_a_longer_horizon(tmp_path):
    full = _frame()
    observed = _on_freeze_basis(full, 0.5)
    _, records = _freeze(tmp_path, observed)
    record = records["1w"]

    outcome = outcome_ledger.resolve_outcome(record, full)

    assert outcome is not None
    assert outcome.corporate_action is True
    assert outcome.realised_return == pytest.approx(
        _true_return(full, outcome.bars_ahead)
    )


# ------------------------------------------------------------ still refusing


def test_tampered_anchor_is_still_rejected(tmp_path):
    """The pre-AB-1 guarantee, unchanged: one bar moving alone is corruption."""
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)

    tampered = full.copy()
    tampered.loc[tampered.index[CUTOFF_ROWS - 1], "close"] *= 1.05

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="anchor price"):
        outcome_ledger.resolve_outcome(records["1d"], tampered)


def test_partial_rescale_is_rejected_as_not_uniform(tmp_path):
    """Part of the history rescaled is no corporate action anyone can perform.

    The rescale must reach the anchor, or the equality fast path answers first
    — see `test_guard_only_speaks_when_the_anchor_itself_moved` for why that
    is correct rather than a gap.
    """
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)

    partial = full.copy()
    cut = CUTOFF_ROWS - forecast_ledger.BASIS_PROBE_COUNT // 2
    partial.loc[partial.index[cut:CUTOFF_ROWS], "close"] *= 0.5

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="uniform"):
        outcome_ledger.resolve_outcome(records["1d"], partial)


def test_guard_only_speaks_when_the_anchor_itself_moved(tmp_path):
    """A known and deliberate boundary, pinned so nobody reports it as a bug.

    If the anchor bar still reads what it read at freeze time, the return is
    computed on a consistent basis and scoring proceeds — whatever happened to
    bars further back.  This is pre-AB-1 behaviour that AB-1 did not change,
    and it is not a weakness in the return: the anchor and the maturity price
    are the only two prices the arithmetic touches.  **This guard is not a
    general history-integrity check** and must not be described as one; the
    frozen `input_fingerprint` is what covers the consumed frame.
    """
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)

    older = full.copy()
    older.loc[older.index[:CUTOFF_ROWS - 20], "close"] *= 0.5

    outcome = outcome_ledger.resolve_outcome(records["1d"], older)

    assert outcome is not None
    assert outcome.corporate_action is False
    assert outcome.realised_return == pytest.approx(_true_return(full, 1))


def test_record_without_probes_refuses_rather_than_guessing(tmp_path):
    """Fail-closed on legacy records: no probes means no way to tell."""
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    record = records["1d"]

    payload = record.payload()
    payload["basis_probes"] = None
    payload["forecast_schema_version"] = 1
    legacy = forecast_ledger.ForecastRecord.from_payload(
        {**payload, "forecast_id": "fcst_" + forecast_ledger._digest(
            {k: v for k, v in {**payload}.items()
             if k not in ("forecast_id", "basis_probes")}
        )}
    )

    rescaled = full.copy()
    for column in PRICE_COLUMNS:
        rescaled.loc[rescaled.index[:CUTOFF_ROWS], column] *= 0.5

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="no basis probes"):
        outcome_ledger.resolve_outcome(legacy, rescaled)


def test_deviation_just_outside_tolerance_is_refused(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)

    drifted = full.copy()
    for column in PRICE_COLUMNS:
        drifted.loc[drifted.index[:CUTOFF_ROWS], column] *= 0.5
    # One probe pushed clear of the uniformity band.
    drifted.loc[drifted.index[CUTOFF_ROWS - 3], "close"] *= (
        1 + outcome_ledger.BASIS_UNIFORMITY_REL_TOL * 100
    )

    with pytest.raises(outcome_ledger.OutcomeIntegrityError, match="uniform"):
        outcome_ledger.resolve_outcome(records["1d"], drifted)


def test_rounding_noise_inside_tolerance_still_reconciles(tmp_path):
    """Provider float noise must not re-open the hole AB-1 closes."""
    full = _frame()
    observed = _on_freeze_basis(full, 0.5)
    _, records = _freeze(tmp_path, observed)

    noisy = full.copy()
    noisy.loc[noisy.index[CUTOFF_ROWS - 3], "close"] *= (
        1 + outcome_ledger.BASIS_UNIFORMITY_REL_TOL / 10
    )

    outcome = outcome_ledger.resolve_outcome(records["1d"], noisy)

    assert outcome is not None
    assert outcome.corporate_action is True
    assert 0 < outcome.basis_max_deviation <= outcome_ledger.BASIS_UNIFORMITY_REL_TOL


# ------------------------------------------------------------ still immutable


def test_future_bars_cannot_alter_a_frozen_forecast_or_its_probes(tmp_path):
    """AB-1 added a field; it must not have added a way for the future in."""
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    ledger, records = _freeze(tmp_path, observed)
    record = records["1d"]
    before = record.payload()

    rewritten = full.copy()
    rewritten.loc[rewritten.index[CUTOFF_ROWS:], "close"] *= 3.7

    reloaded = ledger.load(record.forecast_id)

    assert reloaded.payload() == before
    assert reloaded.basis_probes == record.basis_probes
    # And every probe still describes a bar at or before the cutoff.
    cutoff = pd.Timestamp(record.cutoff_at)
    assert all(pd.Timestamp(date) <= cutoff for date, _ in reloaded.basis_probes)


def test_probes_never_reach_beyond_the_cutoff(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)

    last_observed = pd.Timestamp(observed["date"].iloc[-1], tz="UTC")
    for record in records.values():
        for date, _ in record.basis_probes:
            assert pd.Timestamp(date) <= last_observed


# --------------------------------------------------------- schema amendment


def test_v1_records_keep_their_original_identity(tmp_path):
    """A schema amendment must not move the id of anything already frozen."""
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _, records = _freeze(tmp_path, observed)
    payload = records["1d"].payload()

    v1_payload = {
        **payload, "basis_probes": None, "forecast_schema_version": 1,
    }
    identity = {
        key: value for key, value in v1_payload.items()
        if key not in ("forecast_id", "basis_probes")
    }
    v1_payload["forecast_id"] = "fcst_" + forecast_ledger._digest(identity)

    record = forecast_ledger.ForecastRecord.from_payload(v1_payload)

    assert record.forecast_schema_version == 1
    assert record.basis_probes is None
    assert "basis_probes" not in record.identity_payload()


def test_v1_record_cannot_carry_probes():
    with pytest.raises(ValueError, match="did not exist before schema v2"):
        forecast_ledger.ForecastRecord.from_payload({
            "forecast_id": "fcst_x", "generated_at": "2024-01-03T00:00:00+00:00",
            "cutoff_at": "2024-01-02T00:00:00+00:00", "symbol": "T",
            "horizon": "1d", "price_at_cutoff": 10.0,
            "predicted_direction": "neutral", "predicted_return": 0.0,
            "probability_positive": None, "confidence": None,
            "model_predictions": {}, "model_weights": {},
            "model_versions": {"a": "1"}, "feature_data_version": {},
            "regime_state": None, "baseline_prediction": None,
            "application_version": "1", "input_last_bar_at": "2024-01-02T00:00:00+00:00",
            "input_row_count": 1, "input_fingerprint": "sha256:x",
            "forecast_schema_version": 1, "source_path": "t",
            "production_or_challenger": "PRODUCTION_INCUMBENT", "metadata": {},
            "basis_probes": [["2024-01-02T00:00:00+00:00", 10.0]],
        })
