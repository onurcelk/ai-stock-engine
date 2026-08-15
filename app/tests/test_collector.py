"""Headless collection: the same freeze path, on a schedule instead of a click.

The collector's whole value is that it adds *nothing* to how a forecast is
made. Several tests below assert that negatively — no second methodology, no
challenger, no backfill — because those are the ways this file could quietly
become a second prediction system.

Every test uses `tmp_path`. None writes to the production ledger.
"""

from __future__ import annotations

import inspect
import json

import numpy as np
import pandas as pd
import pytest

from core import collector, forecast_ledger, ledger_backup, ultimate


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
    return pd.Timestamp(frame["date"].iloc[-1], tz="UTC") + pd.Timedelta(days=days)


@pytest.fixture
def enabled(monkeypatch):
    """Opt into real backup behaviour — against `tmp_path` roots only.

    `conftest.never_touch_the_backup_drive` disables backups for the whole
    session so nothing can reach `D:\\prediction market backup` by accident.
    """
    from core import ledger_backup

    monkeypatch.delenv(ledger_backup.DISABLE_ENV, raising=False)


def _run(tmp_path, frame, symbols=("AAA", "BBB"), **kwargs):
    kwargs.setdefault("generated_at", _live_now(frame))
    backups = tmp_path / "backups"
    backups.mkdir(exist_ok=True)
    return collector.collect(
        symbols=list(symbols),
        path=tmp_path / "forecasts.sqlite3",
        backup_dir=backups,
        state_path=tmp_path / "backup_state.json",
        log_dir=tmp_path / "logs",
        horizons=HORIZONS,
        fetcher=_fetcher(frame),
        **kwargs,
    )


# ------------------------------------------------------------------ it works


def test_a_collection_run_freezes_every_symbol(tmp_path):
    frame = _frame()
    run = _run(tmp_path, frame)

    assert run.ok is True
    assert run.frozen_records == 4                 # 2 symbols x 2 horizons
    assert {r.symbol for r in run.results} == {"AAA", "BBB"}
    assert all(r.status == "frozen" for r in run.results)

    stored = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list()
    assert len(stored) == 4
    assert {r.symbol for r in stored} == {"AAA", "BBB"}


def test_a_run_writes_a_log(tmp_path):
    frame = _frame()
    _run(tmp_path, frame)

    logs = list((tmp_path / "logs").glob("collection_*.json"))
    assert len(logs) == 1
    payload = json.loads(logs[0].read_text())
    assert payload["ok"] is True
    assert payload["frozen_records"] == 4
    assert len(payload["results"]) == 2


def test_a_run_backs_the_ledger_up_after_writing(tmp_path, enabled):
    frame = _frame()
    run = _run(tmp_path, frame)

    assert run.backup is not None
    assert run.backup_anomaly is None
    backups = ledger_backup.list_backups(tmp_path / "backups")
    assert len(backups) == 1
    assert ledger_backup.verify_backup(backups[0], tmp_path / "backups") is True


def test_nothing_new_means_no_backup(tmp_path, enabled):
    """A run that froze nothing has nothing to protect."""
    frame = _frame()
    _run(tmp_path, frame)
    second = _run(tmp_path, frame)

    assert second.frozen_records == 0
    assert second.backup is None
    assert len(ledger_backup.list_backups(tmp_path / "backups")) == 1


# ------------------------------------------------------------- it is idempotent


def test_rerunning_on_the_same_bars_duplicates_nothing(tmp_path):
    frame = _frame()
    _run(tmp_path, frame)
    second = _run(tmp_path, frame, generated_at=_live_now(frame, days=2))

    assert second.frozen_records == 0
    assert all(r.status == "nothing_new" for r in second.results)
    assert len(forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list()) == 4


def test_a_new_bar_earns_exactly_one_new_record_per_horizon(tmp_path):
    frame = _frame()
    _run(tmp_path, frame.iloc[:-1].copy())
    second = _run(tmp_path, frame)

    assert second.frozen_records == 4
    stored = forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list()
    assert len(stored) == 8
    assert len({record.cutoff_at for record in stored}) == 2


# --------------------------------------------------------------- it refuses


def test_a_backdated_cutoff_is_refused_and_reported(tmp_path):
    frame = _frame()
    run = _run(tmp_path, frame,
               generated_at=_live_now(frame) + pd.Timedelta(days=400))

    assert run.ok is False
    assert run.frozen_records == 0
    assert all(r.status == "refused" for r in run.results)
    assert all("not a live forecast" in r.detail for r in run.results)
    assert not (tmp_path / "forecasts.sqlite3").exists()


def test_one_bad_symbol_does_not_cost_the_others_their_date(tmp_path):
    frame = _frame()

    def fetch(symbol, *, period, interval, force=False):
        if symbol == "BAD":
            raise RuntimeError("delisted")
        return frame.copy(deep=True), None

    run = collector.collect(
        symbols=["AAA", "BAD", "BBB"],
        path=tmp_path / "forecasts.sqlite3",
        backup_dir=tmp_path / "backups", log_dir=tmp_path / "logs",
        horizons=HORIZONS, fetcher=fetch, generated_at=_live_now(frame),
    )

    assert run.frozen_records == 4
    assert run.ok is False                       # and the run still says so
    assert {r.symbol for r in run.failures} == {"BAD"}
    assert "delisted" in run.failures[0].detail


def test_failures_reach_the_exit_code(tmp_path, monkeypatch, capsys):
    frame = _frame()
    monkeypatch.setattr(collector, "collect", lambda **kwargs: collector.CollectionRun(
        started_at="x", finished_at="y",
        results=(collector.SymbolResult("AAA", "error", detail="boom"),),
        frozen_records=0))

    assert collector.main([]) == 1
    assert "boom" in capsys.readouterr().err


# ------------------------------------------------ it is not a second engine


def test_the_collector_only_ever_freezes_the_incumbent(tmp_path):
    frame = _frame()
    _run(tmp_path, frame)

    for record in forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list():
        assert record.production_or_challenger == forecast_ledger.PRODUCTION_INCUMBENT
        assert record.source_path == "app.core.ultimate.evaluate"
        assert record.forecast_schema_version == 2
        assert record.basis_probes                      # AB-1 probes present


def test_the_collector_delegates_and_invents_nothing():
    """It must call the production freeze path, not reimplement one."""
    text = inspect.getsource(collector)
    code = "".join(text.split('"""')[::2])
    code = "\n".join(line for line in code.splitlines()
                     if not line.strip().startswith("#"))

    assert "evaluate_and_freeze(" in code
    for forbidden in ("evaluate_offline(", "challenger_record(", "_incumbent_records(",
                      "ultimate.evaluate(", "insert_many("):
        assert forbidden not in code, forbidden


def test_the_collector_never_backfills(tmp_path):
    frame = _frame()
    _run(tmp_path, frame)

    last_bar = pd.Timestamp(frame["date"].iloc[-1], tz="UTC")
    for record in forecast_ledger.ForecastLedger(tmp_path / "forecasts.sqlite3").list():
        assert pd.Timestamp(record.input_last_bar_at) == last_bar
        lag = pd.Timestamp(record.generated_at) - pd.Timestamp(record.cutoff_at)
        assert lag <= forecast_ledger.MAX_CUTOFF_LAG


# ------------------------------------------------------------- the universe


def test_the_universe_is_declared_not_discovered():
    symbols = collector.read_universe()

    assert len(symbols) == 30
    assert symbols == sorted(set(symbols))          # unique and ordered
    assert "EURUSD_X" not in symbols                # delisted, deliberately out
    assert "AAPL" in symbols


def test_universe_parsing_ignores_comments_and_blanks(tmp_path):
    source = tmp_path / "universe.txt"
    source.write_text("# a comment\n\nAAA\n  bbb  # trailing\n\nAAA\n")

    assert collector.read_universe(source) == ["AAA", "BBB"]


def test_a_missing_or_empty_universe_refuses(tmp_path):
    with pytest.raises(collector.CollectionError, match="no collection universe"):
        collector.read_universe(tmp_path / "absent.txt")

    empty = tmp_path / "empty.txt"
    empty.write_text("# only comments\n")
    with pytest.raises(collector.CollectionError, match="is empty"):
        collector.read_universe(empty)


# ------------------------------------------------------------- the real one


def test_tests_do_not_write_to_the_production_ledger(tmp_path):
    """The collector defaults to production; every test here overrides it."""
    from core import ledger_activation

    assert ledger_activation.ledger_path(None) == forecast_ledger.DEFAULT_PATH
    assert (tmp_path / "forecasts.sqlite3") != forecast_ledger.DEFAULT_PATH
    assert collector.DEFAULT_LOG_DIR != tmp_path
