"""Headless scoring: the same score_matured path, pointed at the live ledger.

Before this module existed, nothing called `outcome_ledger.score_matured`
against the production ledger — only `replay_study.py` (a different file) and
tests did. Independent prospective cutoffs would have stayed at 0 forever.
These tests assert the delegation is real and that the module invents no
scoring logic of its own, mirroring `test_collector.py`'s discipline for the
sibling freeze path.

Every test uses `tmp_path`. None writes to the production ledger.
"""

from __future__ import annotations

import inspect
import json

import numpy as np
import pandas as pd
import pytest

from core import forecast_ledger, ledger_backup, outcome_ledger, score_outcomes, ultimate


ROWS = 920
CUTOFF_ROWS = 900


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


def _freeze(tmp_path, symbol: str, observed: pd.DataFrame):
    ledger = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3")
    _, records = forecast_ledger.generate_and_freeze_incumbent(
        ledger, symbol,
        horizons=[ultimate.HORIZON_BY_KEY["1d"]],
        fetcher=_fetcher(observed),
    )
    return ledger, records


@pytest.fixture
def enabled(monkeypatch):
    """Opt into real backup behaviour, against `tmp_path` roots only."""
    monkeypatch.delenv(ledger_backup.DISABLE_ENV, raising=False)


# ------------------------------------------------------------------ it works


def test_a_matured_forecast_is_scored(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)

    run = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3",
        backup=False, log_dir=tmp_path / "logs",
        fetcher=_fetcher(full),
    )

    assert run.ok is True
    assert len(run.scored) == 1
    store = outcome_ledger.OutcomeStore(tmp_path / "forecasts.sqlite3")
    assert len(store.list()) == 1
    assert store.list()[0].symbol == "AAA"


def test_an_unmatured_forecast_scores_nothing(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)

    run = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3",
        backup=False, log_dir=tmp_path / "logs",
        fetcher=_fetcher(observed),          # no future bars supplied
    )

    assert run.scored == ()
    assert outcome_ledger.OutcomeStore(tmp_path / "forecasts.sqlite3").list() == []


def test_a_run_writes_a_log(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)

    score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3",
        backup=False, log_dir=tmp_path / "logs",
        fetcher=_fetcher(full),
    )

    logs = list((tmp_path / "logs").glob("score_*.json"))
    assert len(logs) == 1
    payload = json.loads(logs[0].read_text())
    assert payload["ok"] is True
    assert payload["scored_count"] == 1


def test_a_run_backs_the_ledger_up_after_scoring(tmp_path, enabled):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)
    backups = tmp_path / "backups"
    backups.mkdir()

    run = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3",
        backup_dir=backups, state_path=tmp_path / "state.json",
        log_dir=tmp_path / "logs",
        fetcher=_fetcher(full),
    )

    assert run.backup is not None
    assert len(ledger_backup.list_backups(backups)) == 1


def test_nothing_scored_means_no_backup(tmp_path, enabled):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)
    backups = tmp_path / "backups"
    backups.mkdir()

    run = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3",
        backup_dir=backups, state_path=tmp_path / "state.json",
        log_dir=tmp_path / "logs",
        fetcher=_fetcher(observed),           # nothing matured
    )

    assert run.backup is None
    assert ledger_backup.list_backups(backups) == []


# ------------------------------------------------------------- it is idempotent


def test_rerunning_never_rescores(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)

    first = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3", backup=False,
        log_dir=tmp_path / "logs", fetcher=_fetcher(full))
    second = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3", backup=False,
        log_dir=tmp_path / "logs", fetcher=_fetcher(full))

    assert len(first.scored) == 1
    assert second.scored == ()
    assert len(outcome_ledger.OutcomeStore(tmp_path / "forecasts.sqlite3").list()) == 1


# --------------------------------------------------------------- it isolates failure


def test_one_symbols_fetch_failure_does_not_cost_the_others(tmp_path):
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)
    _freeze(tmp_path, "BAD", observed)

    def fetch(symbol, *, period, interval, force=False):
        if symbol == "BAD":
            raise RuntimeError("delisted")
        return full.copy(deep=True), None

    run = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3", backup=False,
        log_dir=tmp_path / "logs", fetcher=fetch)

    assert run.ok is False
    assert "BAD" in run.symbols_failed
    assert "AAA" not in run.symbols_failed
    scored_symbols = {
        record.symbol for record in
        outcome_ledger.OutcomeStore(tmp_path / "forecasts.sqlite3").list()
    }
    assert scored_symbols == {"AAA"}


def test_a_symbols_integrity_refusal_does_not_cost_the_others(tmp_path, monkeypatch):
    """An AB-1-style basis refusal on one symbol must not lose every symbol's date."""
    full = _frame()
    observed = full.iloc[:CUTOFF_ROWS].copy()
    _freeze(tmp_path, "AAA", observed)
    _freeze(tmp_path, "BBB", observed)

    real_score_matured = outcome_ledger.score_matured

    def flaky_score_matured(ledger, store, frames, *, symbol=None, **kwargs):
        if symbol == "AAA":
            raise outcome_ledger.OutcomeIntegrityError("basis drift, not a rescaling")
        return real_score_matured(ledger, store, frames, symbol=symbol, **kwargs)

    monkeypatch.setattr(outcome_ledger, "score_matured", flaky_score_matured)

    run = score_outcomes.score(
        path=tmp_path / "forecasts.sqlite3", backup=False,
        log_dir=tmp_path / "logs", fetcher=_fetcher(full))

    assert run.ok is False
    assert run.symbols_failed == ("AAA",)
    assert "basis drift" in run.failure_detail["AAA"]
    scored_symbols = {
        record.symbol for record in
        outcome_ledger.OutcomeStore(tmp_path / "forecasts.sqlite3").list()
    }
    assert scored_symbols == {"BBB"}


def test_intraday_intervals_request_a_yahoo_safe_period():
    assert score_outcomes._fetch_period("1h") == score_outcomes.FETCH_PERIOD_INTRADAY
    assert score_outcomes._fetch_period("1d") == score_outcomes.FETCH_PERIOD_DAILY_PLUS
    assert score_outcomes._fetch_period("1w") == score_outcomes.FETCH_PERIOD_DAILY_PLUS


def test_failures_reach_the_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(score_outcomes, "score", lambda **kwargs: score_outcomes.ScoringRun(
        started_at="x", finished_at="y", scored=(),
        symbols_attempted=("AAA",), symbols_failed=("AAA",)))

    assert score_outcomes.main([]) == 1
    assert "AAA" in capsys.readouterr().err


# ------------------------------------------------ it is not a second engine


def test_it_delegates_and_invents_no_scoring_logic():
    """It must call score_matured, not reimplement outcome resolution."""
    text = inspect.getsource(score_outcomes)
    code = "".join(text.split('"""')[::2])
    code = "\n".join(line for line in code.splitlines()
                     if not line.strip().startswith("#"))

    assert "score_matured(" in code
    for forbidden in ("resolve_outcome(", "insert_many(", "ultimate.evaluate(",
                      "evaluate_and_freeze("):
        assert forbidden not in code, forbidden


def test_tests_do_not_write_to_the_production_ledger(tmp_path):
    assert (tmp_path / "forecasts.sqlite3") != forecast_ledger.DEFAULT_PATH
    assert score_outcomes.DEFAULT_LOG_DIR != tmp_path
