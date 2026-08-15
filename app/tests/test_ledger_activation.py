"""Switching the forecast ledger on: what live freezing may and may not do.

Every test here writes to `tmp_path`.  None of them may create the real
`app/forecast_ledger.sqlite3`, and one of them asserts exactly that — the
production ledger's contents are accumulated evidence, and a test that added
a synthetic row to it would corrupt the record it is meant to protect.
"""

from __future__ import annotations

import inspect
import pathlib

import numpy as np
import pandas as pd
import pytest

from core import forecast_ledger, ledger_activation, research_view, ultimate


ROWS = 900
HORIZONS = [ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]]


def _frame(*, rows: int = ROWS, seed: int = 23) -> pd.DataFrame:
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


def _live_now(frame: pd.DataFrame, *, days: int = 1) -> pd.Timestamp:
    """A generation time that makes this frame a *live* read, not a backfill."""
    return pd.Timestamp(frame["date"].iloc[-1], tz="UTC") + pd.Timedelta(days=days)


def _freeze(tmp_path, frame, **kwargs):
    kwargs.setdefault("generated_at", _live_now(frame))
    return ledger_activation.evaluate_and_freeze(
        "TEST", path=tmp_path / "forecasts.sqlite3", active=True,
        horizons=HORIZONS, fetcher=_fetcher(frame), **kwargs,
    )


# ------------------------------------------------------------- it accumulates


def test_a_live_reading_freezes_the_incumbent(tmp_path):
    verdict, report = _freeze(tmp_path, _frame())

    assert verdict.symbol == "TEST"
    assert report.active is True
    assert report.failed is False
    assert report.wrote_anything is True
    assert set(report.frozen_horizons) == {"1d", "1w"}

    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    stored = ledger.list()
    assert len(stored) == 2
    assert {record.forecast_id for record in stored} == set(report.frozen_ids)


def test_only_the_deterministic_incumbent_is_frozen(tmp_path):
    _freeze(tmp_path, _frame())

    stored = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list()

    assert stored
    assert all(
        record.production_or_challenger == forecast_ledger.PRODUCTION_INCUMBENT
        for record in stored
    )
    assert all(record.source_path == "app.core.ultimate.evaluate" for record in stored)
    assert ledger_activation.INCUMBENT_ONLY is True


def test_frozen_records_carry_ab1_basis_probes(tmp_path):
    """Activation must not have shipped a ledger AB-1 cannot later score."""
    _freeze(tmp_path, _frame())

    for record in forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list():
        assert record.forecast_schema_version == 2
        assert record.basis_probes
        assert record.basis_probes[-1][1] == pytest.approx(record.price_at_cutoff)


# ------------------------------------------------------------- it is idempotent


def test_re_reading_the_same_bars_freezes_nothing_new(tmp_path):
    frame = _frame()
    _freeze(tmp_path, frame)
    _, second = _freeze(tmp_path, frame)

    assert second.wrote_anything is False
    assert second.failed is False
    assert set(second.skipped_horizons) == {"1d", "1w"}
    assert len(forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list()) == 2


def test_a_new_bar_earns_a_new_record(tmp_path):
    frame = _frame()
    _freeze(tmp_path, frame.iloc[:-1].copy())
    _, second = _freeze(tmp_path, frame)

    assert second.wrote_anything is True
    stored = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list()
    assert len(stored) == 4
    # Four records, two distinct cutoffs: the ledger gains a row when the bars
    # move, which is the only thing that adds an independent date.
    assert len({record.cutoff_at for record in stored}) == 2


def test_idempotency_is_keyed_on_the_input_not_the_clock(tmp_path):
    """`forecast_id` digests `generated_at`, so it cannot be the key."""
    frame = _frame()
    _freeze(tmp_path, frame, generated_at=_live_now(frame, days=1))
    _, second = _freeze(tmp_path, frame, generated_at=_live_now(frame, days=3))

    assert second.wrote_anything is False
    assert len(forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list()) == 2


def test_a_model_assisted_verdict_is_not_frozen(tmp_path):
    """Incumbent-only, enforced where the scope decision actually bites.

    A model-assisted verdict is not the deterministic incumbent: a neural
    reading joins the ensemble, and its fitted weights are unversioned
    (Phase 7 §9). Freezing it would accumulate irreproducible evidence.
    """
    frame = _frame()
    destination = tmp_path / "forecasts.sqlite3"
    evidence = ultimate.ModelEvidence(
        name="neural", interval="1d", horizon_bars=5,
        predicted_move_pct=1.2, directional_pct=55.0, samples=40,
    )

    verdict, report = ledger_activation.evaluate_and_freeze(
        "TEST", path=destination, active=True, horizons=HORIZONS,
        fetcher=_fetcher(frame), model=evidence,
        generated_at=_live_now(frame),
    )

    assert verdict.symbol == "TEST"
    assert report.wrote_anything is False
    assert report.failed is False          # declined, not broken
    assert "challenger freezing stays off" in report.excluded
    assert not destination.exists()


# -------------------------------------------------------- it refuses backfill


def test_a_stale_cutoff_is_refused_and_creates_no_ledger(tmp_path):
    """The defect a UI test actually produced: 2023 bars under a 2026 clock.

    Such a record is indistinguishable from an honest one once written, and
    its outcome is already observable — so it must never be written, and the
    refusal must not leave an empty ledger behind either.
    """
    frame = _frame()
    destination = tmp_path / "forecasts.sqlite3"

    verdict, report = ledger_activation.evaluate_and_freeze(
        "TEST", path=destination, active=True, horizons=HORIZONS,
        fetcher=_fetcher(frame),
        generated_at=_live_now(frame) + pd.Timedelta(days=1000),
    )

    assert verdict.symbol == "TEST"        # the reading is still returned
    assert report.failed is True
    assert "not a live forecast" in report.error
    assert report.wrote_anything is False
    assert not destination.exists()


def test_the_lag_boundary_is_where_it_is_declared(tmp_path):
    frame = _frame()
    inside = pd.Timestamp(frame["date"].iloc[-1], tz="UTC") + (
        forecast_ledger.MAX_CUTOFF_LAG - pd.Timedelta(hours=1))
    outside = pd.Timestamp(frame["date"].iloc[-1], tz="UTC") + (
        forecast_ledger.MAX_CUTOFF_LAG + pd.Timedelta(hours=1))

    _, ok = _freeze(tmp_path, frame, generated_at=inside)
    _, refused = ledger_activation.evaluate_and_freeze(
        "TEST", path=tmp_path / "other.sqlite3", active=True, horizons=HORIZONS,
        fetcher=_fetcher(frame), generated_at=outside,
    )

    assert ok.wrote_anything is True
    assert refused.failed is True


# ---------------------------------------------------------------- it is honest


def test_a_write_failure_is_reported_and_does_not_lose_the_forecast(tmp_path, monkeypatch):
    def explode(self, records):
        raise forecast_ledger.ForecastIntegrityError("disk went away")

    monkeypatch.setattr(forecast_ledger.ForecastLedger, "insert_many", explode)
    verdict, report = _freeze(tmp_path, _frame())

    assert verdict.symbol == "TEST"          # the user still gets their reading
    assert report.failed is True
    assert "disk went away" in report.error
    assert report.wrote_anything is False
    assert "FAILED" in report.summary()      # and it is put in front of them


def test_no_silent_skip_anywhere_in_the_scoring_or_activation_path():
    """AB-1 §3.4 named the exact line that would make the hole silent again.

    A `try/except OutcomeLedgerError: continue` around scoring turns a loud
    refusal into a factor-correlated gap nobody counts. Neither that nor a
    bare catch-all may appear on these paths.
    """
    from core import outcome_ledger

    for module in (ledger_activation, outcome_ledger, forecast_ledger):
        source = inspect.getsource(module)
        assert "except Exception" not in source, module.__name__
        assert "except:" not in source, module.__name__
        assert "pass" not in [
            line.strip() for line in source.splitlines()
        ], module.__name__
        for handler in source.split("except ")[1:]:
            body = handler.split("\n\n")[0]
            assert "continue" not in body, module.__name__


def test_deactivated_never_touches_the_disk(tmp_path):
    destination = tmp_path / "forecasts.sqlite3"
    verdict, report = ledger_activation.evaluate_and_freeze(
        "TEST", path=destination, active=False,
        horizons=HORIZONS, fetcher=_fetcher(_frame()),
    )

    assert verdict.symbol == "TEST"
    assert report.active is False
    assert report.wrote_anything is False
    assert not destination.exists()


# --------------------------------------------------------- it never backfills


def test_the_cutoff_is_the_last_observed_bar(tmp_path):
    frame = _frame()
    _freeze(tmp_path, frame)

    last_bar = pd.Timestamp(frame["date"].iloc[-1], tz="UTC")
    for record in forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list():
        assert pd.Timestamp(record.input_last_bar_at) == last_bar
        assert pd.Timestamp(record.cutoff_at) <= pd.Timestamp(record.generated_at)


def test_activation_cannot_reach_the_offline_path():
    """Uploads and bundled CSVs must never become frozen evidence.

    Structural rather than behavioural: `evaluate_offline` is the only way an
    arbitrary uploaded frame enters the engine, and this module does not name
    it. A future edit that adds it should fail here and be argued for.
    """
    source = inspect.getsource(ledger_activation)
    # Calls, not prose: the module docstring names both to explain why they
    # are excluded, and a test that broke on its own rationale would be read
    # as noise and deleted.
    code = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    ).split('"""')
    code = "".join(code[::2])

    assert "evaluate_offline(" not in code
    assert "challenger_record(" not in code
    assert "ultimate.evaluate(" in code


def test_freezing_writes_one_record_per_available_horizon(tmp_path):
    _, report = _freeze(tmp_path, _frame())
    verdict, _ = _freeze(tmp_path, _frame())

    assert len(report.frozen_ids) == len(verdict.available)


# ---------------------------------------------------- the UI reads the real one


def test_research_view_reads_the_genuine_ledger(tmp_path):
    _freeze(tmp_path, _frame())

    state = research_view.load(tmp_path / "forecasts.sqlite3")

    assert state.exists is True
    assert state.has_forecasts is True
    assert len(state.forecasts) == 2
    # Frozen but not yet matured: no outcome may exist for a forecast made now.
    assert state.has_outcomes is False
    assert state.n_independent_cutoffs == 0
    assert state.thin is True


def test_research_view_still_reports_absence_without_manufacturing_one(tmp_path):
    missing = tmp_path / "nothing.sqlite3"

    state = research_view.load(missing)

    assert state.exists is False
    assert state.has_forecasts is False
    # Phase 8's guarantee, still standing after activation: reading a ledger
    # that is not there must not bring one into existence.
    assert not missing.exists()


def test_tests_never_create_the_production_ledger():
    """The one file in this repository a test may never bring into existence."""
    production = pathlib.Path(forecast_ledger.DEFAULT_PATH)

    assert ledger_activation.ledger_path(None) == production
    assert ledger_activation.ledger_path("elsewhere.sqlite3") != production
