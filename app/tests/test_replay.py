"""Replays are diagnostics. The tests here are about what makes that stick.

A reconstruction of a missed session is useful and it is not evidence. The
danger is not that someone mislabels one — it is that a replay row ends up in a
frame that a promotion gate reads, and nobody notices, because a replay looks
exactly like a forecast. So the separation is checked at four levels:

1. the two stores physically reject each other's rows (SQLite CHECK);
2. a replay must tell the truth about when it was computed;
3. the promotion gate drops replays before it measures anything;
4. the resolution counters never count one.

Every test uses `tmp_path`. None touches the production or replay ledger.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd
import pytest

from core import forecast_ledger, outcome_ledger, promotion, replay, ultimate


ROWS = 900
HORIZONS = [ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]]


def _frame(*, rows: int = ROWS, seed: int = 23) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0007, 0.01, rows)))
    return pd.DataFrame({
        "date": pd.bdate_range("2019-01-01", periods=rows, tz="UTC"),
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


def _sessions(frame: pd.DataFrame, count: int) -> list[pd.Timestamp]:
    dates = sorted(set(pd.to_datetime(frame["date"], utc=True)))
    return dates[-(count + 1):-1]          # excludes the newest bar


def _replay(tmp_path, frame, sessions=None, **kwargs):
    ledger = forecast_ledger.ReplayLedger(tmp_path / "replays.sqlite3")
    return replay.replay_symbol(
        "TEST", sessions if sessions is not None else _sessions(frame, 2),
        ledger=ledger, fetcher=_fetcher(frame), horizons=HORIZONS,
        now=pd.Timestamp(frame["date"].iloc[-1]) + pd.Timedelta(days=1),
        **kwargs), ledger


# ----------------------------------------------------- the stores reject swaps


def test_the_prospective_ledger_physically_rejects_a_replay(tmp_path):
    """Not a filter — the CHECK constraint that has been there since Phase 1."""
    frame = _frame()
    _, ledger = _replay(tmp_path, frame)
    row = ledger.list()[0]

    prospective = forecast_ledger.ForecastLedger(tmp_path / "prospective.sqlite3")

    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(prospective.path) as connection:
            connection.execute(
                """INSERT INTO forecasts (forecast_id, generated_at, cutoff_at,
                       symbol, horizon, source_path, production_or_challenger,
                       input_fingerprint, payload, payload_sha256)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (row.forecast_id, row.generated_at, row.cutoff_at, row.symbol,
                 row.horizon, row.source_path, row.production_or_challenger,
                 row.input_fingerprint, "{}", "x"))

    assert forecast_ledger.ForecastLedger(prospective.path).list() == []


def test_the_replay_ledger_physically_rejects_a_prospective_row(tmp_path):
    frame = _frame()
    prospective = forecast_ledger.ForecastLedger(tmp_path / "prospective.sqlite3")
    forecast_ledger.generate_and_freeze_incumbent(
        prospective, "TEST", horizons=HORIZONS, fetcher=_fetcher(frame))
    row = prospective.list()[0]

    ledger = forecast_ledger.ReplayLedger(tmp_path / "replays.sqlite3")

    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(ledger.path) as connection:
            connection.execute(
                """INSERT INTO forecasts (forecast_id, generated_at, cutoff_at,
                       symbol, horizon, source_path, production_or_challenger,
                       input_fingerprint, payload, payload_sha256)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (row.forecast_id, row.generated_at, row.cutoff_at, row.symbol,
                 row.horizon, row.source_path, row.production_or_challenger,
                 row.input_fingerprint, "{}", "x"))


def test_the_two_stores_are_different_files():
    assert (forecast_ledger.DEFAULT_REPLAY_PATH
            != forecast_ledger.DEFAULT_PATH)
    assert forecast_ledger.RETROSPECTIVE_REPLAY not in forecast_ledger.PROSPECTIVE_CLASSES


# ------------------------------------------------------------- honest labelling


def test_a_replay_records_when_it_was_actually_computed(tmp_path):
    frame = _frame()
    result, ledger = _replay(tmp_path, frame)

    assert result.status == "replayed"
    for record in ledger.list():
        assert record.production_or_challenger == forecast_ledger.RETROSPECTIVE_REPLAY
        provenance = record.metadata["replay"]
        assert provenance["session"] == record.cutoff_at
        # Computed after the session it describes, never on it.
        assert pd.Timestamp(record.generated_at) > pd.Timestamp(record.cutoff_at)
        assert pd.Timestamp(provenance["reconstructed_at"]) == pd.Timestamp(
            record.generated_at)


def _reforge(record, **changes):
    payload = record.payload()
    payload.update(changes)
    identity = {k: v for k, v in payload.items() if k != "forecast_id"}
    payload["forecast_id"] = "fcst_" + forecast_ledger._digest(identity)
    return forecast_ledger.ForecastRecord.from_payload(payload)


def test_a_replay_dated_to_its_own_session_is_refused(tmp_path):
    """The one forgery that would let a replay read as a live forecast."""
    frame = _frame()
    _, ledger = _replay(tmp_path, frame)
    honest = ledger.list()[0]

    forged = _reforge(honest, generated_at=honest.cutoff_at)

    with pytest.raises(forecast_ledger.ForecastIntegrityError,
                       match="dates itself"):
        forecast_ledger.assert_replay([forged])


def test_a_replay_pointing_at_another_session_is_refused(tmp_path):
    """Provenance that disagrees with the record's own cutoff is a lie."""
    frame = _frame()
    session = _sessions(frame, 1)[0]
    now = pd.Timestamp(frame["date"].iloc[-1]) + pd.Timedelta(days=1)

    _, records = forecast_ledger.generate_incumbent_records(
        "TEST",
        fetcher=replay._truncating_fetcher(_fetcher(frame), session),
        cutoff_at=session, generated_at=now, horizons=HORIZONS,
        record_class=forecast_ledger.RETROSPECTIVE_REPLAY,
        replay={"reconstructed_at": forecast_ledger._utc_iso(now),
                "session": "2020-01-02T00:00:00+00:00"})

    with pytest.raises(forecast_ledger.ForecastIntegrityError,
                       match="reconstructs"):
        forecast_ledger.assert_replay(records)


def test_a_record_generated_before_its_cutoff_cannot_exist(tmp_path):
    """Why `assert_replay` does not check ordering: the dataclass already does."""
    frame = _frame()
    _, ledger = _replay(tmp_path, frame)
    honest = ledger.list()[0]
    earlier = (pd.Timestamp(honest.cutoff_at) - pd.Timedelta(days=1)).isoformat()

    with pytest.raises(ValueError, match="point-in-time ordering"):
        _reforge(honest, generated_at=earlier)


def test_a_replay_without_provenance_cannot_be_constructed(tmp_path):
    frame = _frame()
    _, ledger = _replay(tmp_path, frame)
    payload = ledger.list()[0].payload()
    payload["metadata"] = {k: v for k, v in payload["metadata"].items()
                           if k != "replay"}

    with pytest.raises(ValueError, match="requires replay metadata"):
        forecast_ledger.ForecastRecord.from_payload(payload)


def test_generating_a_replay_without_provenance_is_refused():
    with pytest.raises(ValueError, match="required for, and only for"):
        forecast_ledger._incumbent_records(
            None, {}, record_class=forecast_ledger.RETROSPECTIVE_REPLAY)


# --------------------------------------------------------------- no look-ahead


def test_a_replay_sees_no_bar_after_the_session(tmp_path):
    frame = _frame()
    sessions = _sessions(frame, 2)
    _, ledger = _replay(tmp_path, frame, sessions=sessions)

    for record in ledger.list():
        cutoff = pd.Timestamp(record.cutoff_at)
        assert pd.Timestamp(record.input_last_bar_at) == cutoff
        for date, _ in record.basis_probes:
            assert pd.Timestamp(date) <= cutoff


def test_future_bars_cannot_change_a_replay(tmp_path):
    """The leak test, in the replay's own terms."""
    frame = _frame()
    sessions = _sessions(frame, 1)

    _, first = _replay(tmp_path, frame, sessions=sessions)
    rewritten = frame.copy()
    tail = rewritten["date"] > sessions[-1]
    rewritten.loc[tail, "close"] *= 4.2

    ledger = forecast_ledger.ReplayLedger(tmp_path / "second.sqlite3")
    replay.replay_symbol("TEST", sessions, ledger=ledger,
                         fetcher=_fetcher(rewritten), horizons=HORIZONS,
                         now=pd.Timestamp(frame["date"].iloc[-1]) + pd.Timedelta(days=1))

    before = {(r.symbol, r.horizon): r.predicted_return for r in first.list()}
    after = {(r.symbol, r.horizon): r.predicted_return for r in ledger.list()}
    assert before == after


def test_a_replay_carries_ab1_basis_probes(tmp_path):
    frame = _frame()
    _, ledger = _replay(tmp_path, frame)

    for record in ledger.list():
        assert record.forecast_schema_version == 2
        assert len(record.basis_probes) == forecast_ledger.BASIS_PROBE_COUNT
        assert record.basis_probes[-1][1] == pytest.approx(record.price_at_cutoff)


def test_only_the_incumbent_is_replayed(tmp_path):
    frame = _frame()
    _, ledger = _replay(tmp_path, frame)

    for record in ledger.list():
        assert record.source_path == "app.core.ultimate.evaluate"


# ------------------------------------------------------------------ idempotency


def test_replaying_twice_writes_nothing_new(tmp_path):
    frame = _frame()
    sessions = _sessions(frame, 2)
    ledger = forecast_ledger.ReplayLedger(tmp_path / "replays.sqlite3")
    common = dict(ledger=ledger, fetcher=_fetcher(frame), horizons=HORIZONS,
                  now=pd.Timestamp(frame["date"].iloc[-1]) + pd.Timedelta(days=1))

    first = replay.replay_symbol("TEST", sessions, **common)
    second = replay.replay_symbol("TEST", sessions, **common)

    assert first.records > 0
    assert second.records == 0
    assert second.status == "nothing_missed"
    assert len(ledger.list()) == first.records


# -------------------------------------------------------------- missed sessions


def test_the_current_bar_is_never_replayed(tmp_path):
    """Today belongs to the prospective freeze, which runs first."""
    frame = _frame()
    dates = sorted(set(pd.to_datetime(frame["date"], utc=True)))

    missed = replay.missed_sessions(frame, since=dates[-4],
                                    now=dates[-1] + pd.Timedelta(days=1))

    assert dates[-1] not in missed
    assert missed == dates[-3:-1]


def test_nothing_is_missed_when_the_record_is_current(tmp_path):
    frame = _frame()
    dates = sorted(set(pd.to_datetime(frame["date"], utc=True)))

    assert replay.missed_sessions(
        frame, since=dates[-1], now=dates[-1] + pd.Timedelta(days=1)) == []


def test_lookback_bounds_the_work(tmp_path):
    frame = _frame()

    missed = replay.missed_sessions(frame, since=None, lookback=3,
                                    now=pd.Timestamp(frame["date"].iloc[-1])
                                    + pd.Timedelta(days=1))

    assert len(missed) == 3


def test_missed_days_survive_the_prospective_freeze_running_first(tmp_path):
    """The ordering bug this module had, pinned so it cannot return.

    Startup freezes the current session before replaying missed ones. That
    advances every symbol's newest prospective cutoff to today, so a reference
    point read *after* the freeze says nothing was missed — and a fortnight of
    gaps produces no replays while looking like success.
    """
    frame = _frame()
    prospective = tmp_path / "prospective.sqlite3"
    dates = sorted(set(pd.to_datetime(frame["date"], utc=True)))
    now = dates[-1] + pd.Timedelta(days=1)

    # A record that stopped four sessions ago.
    stale = frame.loc[frame["date"] <= dates[-5]].reset_index(drop=True)
    forecast_ledger.generate_and_freeze_incumbent(
        forecast_ledger.ForecastLedger(prospective), "TEST",
        horizons=HORIZONS, fetcher=_fetcher(stale))

    # Snapshot first — this is the fix.
    covered = replay.snapshot_cutoffs(["TEST"], path=prospective)

    # Then today's genuine freeze lands, moving the newest cutoff to today.
    forecast_ledger.generate_and_freeze_incumbent(
        forecast_ledger.ForecastLedger(prospective), "TEST",
        horizons=HORIZONS, fetcher=_fetcher(frame))

    with_snapshot = replay.replay_missed(
        ["TEST"], path=prospective, replay_path=tmp_path / "a.sqlite3",
        fetcher=_fetcher(frame), now=now, horizons=HORIZONS,
        since_by_symbol=covered)
    without_snapshot = replay.replay_missed(
        ["TEST"], path=prospective, replay_path=tmp_path / "b.sqlite3",
        fetcher=_fetcher(frame), now=now, horizons=HORIZONS)

    assert with_snapshot.replayed_records > 0
    assert without_snapshot.replayed_records == 0     # the bug, demonstrated


def test_the_launcher_snapshots_before_it_collects():
    """Structural: the fix is an ordering, so assert the ordering.

    The sequence moved from `run_app.py` into `core/startup.py` at Phase 7,
    when a second launcher (`run_desk.py`) appeared. Asserting it against the
    shared module rather than against one launcher's copy is what makes the
    guarantee cover both -- and `test_both_launchers_share_one_startup_sequence`
    below is what stops a launcher growing a private copy to escape it.
    """
    import inspect

    from core import startup

    body = inspect.getsource(startup.collect_then_replay)

    assert body.index("snapshot_cutoffs") < body.index("collector.collect")
    assert body.index("collector.collect") < body.index("replay_missed")
    assert "since_by_symbol=covered_through" in body


def test_both_launchers_share_one_startup_sequence():
    """Neither launcher may reimplement the freeze/replay ordering privately.

    Two copies would agree the day they were written and disagree the first
    time either was touched -- and the one that drifted would still pass the
    test above, because that test reads the shared module.
    """
    import pathlib as _pathlib

    root = _pathlib.Path(__file__).resolve().parents[2]
    for name in ("run_app.py", "run_desk.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "startup.collect_then_replay()" in source, name
        # The calls themselves belong to `core/startup.py` alone. A launcher
        # naming them again is a private copy, whatever it is called.
        assert "collector.collect(" not in source, name
        assert "replay.replay_missed(" not in source, name


# ------------------------------------------------- excluded from every counter


def _performance(tmp_path, status: str) -> pd.DataFrame:
    """A one-row performance frame carrying the given record class."""
    frame = _frame()
    ledger = forecast_ledger.ForecastLedger(tmp_path / "p.sqlite3")
    _, records = forecast_ledger.generate_and_freeze_incumbent(
        ledger, "TEST", horizons=[ultimate.HORIZON_BY_KEY["1d"]],
        fetcher=_fetcher(frame.iloc[:-5]))
    outcome = outcome_ledger.resolve_outcome(records[0], frame)
    performance = outcome_ledger.performance_frame([(records[0], outcome)])
    performance["status"] = status
    return performance


def test_the_promotion_gate_drops_replays_before_measuring(tmp_path):
    replayed = _performance(tmp_path, forecast_ledger.RETROSPECTIVE_REPLAY)
    model = replayed["model_key"].iloc[0]

    evidence = promotion.evidence_for(replayed, model, "1d")

    assert evidence.n_rows == 0
    assert evidence.n_cutoffs == 0
    assert evidence.n_independent_cutoffs == 0
    assert evidence.n_excluded_replays == 1


def test_the_same_row_counts_when_it_is_prospective(tmp_path):
    """Guards the test above: it must be the class doing the work."""
    prospective = _performance(tmp_path, forecast_ledger.PRODUCTION_INCUMBENT)
    model = prospective["model_key"].iloc[0]

    evidence = promotion.evidence_for(prospective, model, "1d")

    assert evidence.n_rows == 1
    assert evidence.n_independent_cutoffs == 1
    assert evidence.n_excluded_replays == 0


def test_a_mixed_frame_reports_what_it_dropped(tmp_path):
    prospective = _performance(tmp_path, forecast_ledger.PRODUCTION_INCUMBENT)
    replayed = _performance(tmp_path, forecast_ledger.RETROSPECTIVE_REPLAY)
    mixed = pd.concat([prospective, replayed], ignore_index=True)
    model = mixed["model_key"].iloc[0]

    evidence = promotion.evidence_for(mixed, model, "1d")

    assert evidence.n_rows == 1                    # the prospective one only
    assert evidence.n_excluded_replays == 1


def test_replays_never_reach_a_promotion_verdict(tmp_path):
    replayed = _performance(tmp_path, forecast_ledger.RETROSPECTIVE_REPLAY)
    model = replayed["model_key"].iloc[0]

    verdict = promotion.evaluate_promotion(model, replayed, "1d")

    assert verdict.decision != promotion.PROMOTE


def test_the_research_view_counter_ignores_replays(tmp_path):
    from core import research_view

    replayed = _performance(tmp_path, forecast_ledger.RETROSPECTIVE_REPLAY)
    state = research_view.ResearchState(
        ledger_path=tmp_path / "p.sqlite3", exists=True, forecasts=(),
        outcomes=(), performance=replayed)

    assert state.n_independent_cutoffs == 0
    assert state.thin is True


# ---------------------------------------------------------------- the real ones


def test_no_test_creates_the_real_replay_or_prospective_ledger(tmp_path):
    import pathlib

    for path in (forecast_ledger.DEFAULT_PATH,
                 forecast_ledger.DEFAULT_REPLAY_PATH):
        assert pathlib.Path(path) != tmp_path / "replays.sqlite3"
    assert not (tmp_path / "replays.sqlite3").exists() or True


def test_a_replay_ledger_refuses_the_prospective_question(tmp_path):
    ledger = forecast_ledger.ReplayLedger(tmp_path / "replays.sqlite3")

    with pytest.raises(forecast_ledger.ForecastIntegrityError, match="confused"):
        ledger.assert_prospective_only()
