"""The historical replay study, and the six things that make it trustworthy.

The study exists to buy resolution quickly: hundreds of scored Ultimate calls
from ten years of history instead of a year of waiting. That speed is only
worth having if the observations are honest, so the tests below prove the six
properties the study was specified against.

1. Future data cannot enter a historical forecast.
2. A historical forecast is frozen before its outcome is read.
3. The correct future horizon is used for scoring.
4. Live and historical observations cannot be confused.
5. Different model versions cannot silently pool.
6. Live ledger behaviour is unchanged.

Every test builds its own series and its own database in `tmp_path`. Nothing
here reads the production ledger, the replay ledger, or the network.
"""

from __future__ import annotations

import dataclasses
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core import (
    forecast_ledger,
    model_registry,
    outcome_ledger,
    promotion,
    replay_study,
    ultimate,
)


ROWS = 1_400


def _frame(*, rows: int = ROWS, seed: int = 11, drift: float = 0.0006) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.011, rows)))
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


def _run(tmp_path, frame, *, symbols=("AAA",), horizon="5w", count=6, **kwargs):
    return replay_study.run_study(
        list(symbols), horizon=horizon, count=count,
        path=tmp_path / "study.sqlite3", fetcher=_fetcher(frame), **kwargs)


# ------------------------------------------------- 1. no future data, ever


def test_the_engine_never_sees_a_bar_after_the_cutoff(tmp_path):
    """The load-bearing guarantee, checked at the door the engine reads through.

    Every frame the engine is handed is captured and its last bar compared with
    the cutoff being replayed. One bar past the cutoff anywhere is a failure —
    this is the study's version of `test_future_cannot_change_the_verdict`.
    """
    frame = _frame()
    seen: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    memo = replay_study.MemoisedFetcher(_fetcher(frame))
    spec = replay_study.horizon_for("5w")
    grid = replay_study.historical_cutoffs(
        frame["date"], bars_ahead=spec.bars, count=4,
        min_history=replay_study.min_history_bars(spec))
    assert grid, "the fixture must be long enough to produce cutoffs"

    def watched(cutoff):
        """Spy on the *outermost* fetcher — what the engine is actually handed.

        Deliberately outside the truncation rather than inside it: the memo
        holds the full series and is supposed to, so observing there would
        prove nothing about what the engine saw.
        """
        door = replay_study._truncated(memo, cutoff)

        def fetch(symbol, *, period, interval, force=False):
            got, entry = door(symbol, period=period, interval=interval,
                              force=force)
            seen.append((cutoff, pd.to_datetime(got["date"], utc=True).max()))
            return got, entry
        return fetch

    ledger = forecast_ledger.ReplayLedger(tmp_path / "study.sqlite3")
    for cutoff in grid:
        _, records = forecast_ledger.generate_incumbent_records(
            "AAA", horizons=[spec],
            fetcher=watched(cutoff),
            cutoff_at=cutoff,
            generated_at=forecast_ledger._utc_iso(pd.Timestamp.now(tz="UTC")),
            record_class=forecast_ledger.RETROSPECTIVE_REPLAY,
            replay=replay_study.study_provenance(
                study_id="study_test", session=forecast_ledger._utc_iso(cutoff),
                reconstructed_at=forecast_ledger._utc_iso(
                    pd.Timestamp.now(tz="UTC")),
                horizon_key="5w", bars_ahead=spec.bars, stride_bars=spec.bars),
        )
        ledger.insert_many(records)

    assert seen, "the engine must actually have fetched something"
    for cutoff, last_bar in seen:
        assert last_bar <= cutoff, (
            f"the engine was handed a bar at {last_bar}, past its {cutoff} cutoff")


def test_a_frozen_study_record_ends_exactly_at_its_declared_cutoff(tmp_path):
    """The second lock: what was frozen, not merely what was handed over.

    `fingerprint_frame(cutoff_at=...)` raises if a single bar survives past the
    cutoff, so this asserts the property on the stored record rather than on
    the call that produced it.
    """
    frame = _frame()
    run = _run(tmp_path, frame, count=5)
    ledger = forecast_ledger.ReplayLedger(tmp_path / "study.sqlite3")

    assert run.frozen_records > 0
    for record in ledger.list():
        assert pd.Timestamp(record.input_last_bar_at) == pd.Timestamp(record.cutoff_at)
        session = record.metadata["replay"]["session"]
        assert pd.Timestamp(session) == pd.Timestamp(record.cutoff_at)


def test_changing_the_future_cannot_change_a_historical_forecast(tmp_path):
    """Rewrite every bar after the cutoff; the frozen forecast is identical.

    The strongest available form of the claim: it does not inspect the
    truncation, it demonstrates that the truncation is what the answer depends
    on. If any future bar reached the engine, the two identities would differ.
    """
    frame = _frame()
    spec = replay_study.horizon_for("5w")
    grid = replay_study.historical_cutoffs(
        frame["date"], bars_ahead=spec.bars, count=3,
        min_history=replay_study.min_history_bars(spec))
    cutoff = grid[0]

    altered = frame.copy()
    future = pd.to_datetime(altered["date"], utc=True) > cutoff
    altered.loc[future, "close"] = altered.loc[future, "close"] * 3.5
    altered.loc[future, "high"] = altered.loc[future, "high"] * 3.5
    altered.loc[future, "low"] = altered.loc[future, "low"] * 3.5

    def freeze(source: pd.DataFrame, path):
        memo = replay_study.MemoisedFetcher(_fetcher(source))
        _, records = forecast_ledger.generate_incumbent_records(
            "AAA", horizons=[spec],
            fetcher=replay_study._truncated(memo, cutoff),
            cutoff_at=cutoff, generated_at="2026-08-16T00:00:00+00:00",
            record_class=forecast_ledger.RETROSPECTIVE_REPLAY,
            replay=replay_study.study_provenance(
                study_id="s", session=forecast_ledger._utc_iso(cutoff),
                reconstructed_at="2026-08-16T00:00:00+00:00",
                horizon_key="5w", bars_ahead=spec.bars, stride_bars=spec.bars),
        )
        return records

    original = freeze(frame, tmp_path / "a.sqlite3")
    rewritten = freeze(altered, tmp_path / "b.sqlite3")

    assert [r.forecast_id for r in original] == [r.forecast_id for r in rewritten]
    assert [r.predicted_return for r in original] == [
        r.predicted_return for r in rewritten]


# --------------------------------- 2. frozen before the outcome is read


def test_the_forecast_is_frozen_and_immutable_before_it_is_scored(tmp_path):
    """Scoring cannot reach back and change what it is scoring.

    Two facts together make this structural rather than procedural: the study
    writes forecasts in one pass and outcomes in another, and the forecast
    table refuses UPDATE and DELETE by trigger. So even a scorer that wanted to
    revise a prediction could not.
    """
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=5)

    ledger = forecast_ledger.ReplayLedger(path)
    before = {r.forecast_id: r.payload_digest if hasattr(r, "payload_digest")
              else r.predicted_return for r in ledger.list()}
    store = outcome_ledger.OutcomeStore(path)
    assert store.scored_ids() == set(), "nothing may be scored before the pass runs"

    scored = replay_study.score_study(path=path, fetcher=_fetcher(frame))
    assert scored, "the study must produce matured outcomes"

    after = {r.forecast_id: r.predicted_return for r in ledger.list()}
    assert before == after

    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE forecasts SET payload = 'tampered'")


def test_scoring_writes_no_forecast_and_freezing_reads_no_outcome(tmp_path):
    """Phase 2's two-process separation, applied to the study path."""
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=5)

    ledger = forecast_ledger.ReplayLedger(path)
    frozen_before = len(ledger.list())
    replay_study.score_study(path=path, fetcher=_fetcher(frame))
    assert len(ledger.list()) == frozen_before, "scoring wrote a forecast"

    # A second sweep over the same grid adds no forecast and touches no outcome.
    outcomes_before = len(outcome_ledger.OutcomeStore(path).list())
    _run(tmp_path, frame, count=5)
    assert len(ledger.list()) == frozen_before
    assert len(outcome_ledger.OutcomeStore(path).list()) == outcomes_before


# ------------------------------------------ 3. the right future horizon


@pytest.mark.parametrize("horizon,expected_bars", [("1d", 1), ("1w", 5), ("5w", 25)])
def test_the_scored_window_is_exactly_the_declared_horizon(
        tmp_path, horizon, expected_bars):
    """5 weeks means 25 trading days after the anchor bar — proved on the frame.

    The anchor and maturity timestamps are looked up in the original series and
    their index distance compared with the horizon. This is what would catch a
    horizon scored one bar short, or scored at the wrong interval.
    """
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, horizon=horizon, count=4)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))

    dates = list(pd.to_datetime(frame["date"], utc=True))
    positions = {stamp: index for index, stamp in enumerate(dates)}
    outcomes = outcome_ledger.OutcomeStore(path).list()
    assert outcomes

    for outcome in outcomes:
        assert outcome.bars_ahead == expected_bars
        anchor = positions[pd.Timestamp(outcome.anchor_at)]
        matured = positions[pd.Timestamp(outcome.matured_at)]
        assert matured - anchor == expected_bars, (
            f"{horizon} scored {matured - anchor} bars ahead, not {expected_bars}")
        # And the arithmetic uses those two bars and no others.
        expected_return = (float(frame["close"].iloc[matured])
                           / float(frame["close"].iloc[anchor]) - 1.0) * 100.0
        assert outcome.realised_return == pytest.approx(expected_return, rel=1e-9)


def test_five_weeks_is_a_real_calendar_five_weeks(tmp_path):
    """25 trading days lands ~35 calendar days out, the study's stated case."""
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, horizon="5w", count=4)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))

    for outcome in outcome_ledger.OutcomeStore(path).list():
        span = pd.Timestamp(outcome.matured_at) - pd.Timestamp(outcome.anchor_at)
        assert pd.Timedelta(days=33) <= span <= pd.Timedelta(days=39)


def test_a_cutoff_without_a_full_horizon_ahead_is_never_generated():
    """An unscoreable cutoff is not coverage, so it is not created."""
    frame = _frame(rows=600)
    spec = replay_study.horizon_for("5w")
    grid = replay_study.historical_cutoffs(
        frame["date"], bars_ahead=spec.bars, count=50,
        min_history=replay_study.min_history_bars(spec))

    dates = list(pd.to_datetime(frame["date"], utc=True))
    for cutoff in grid:
        assert dates.index(cutoff) + spec.bars < len(dates)
        assert dates.index(cutoff) >= replay_study.min_history_bars(spec)


def test_the_default_stride_makes_every_cutoff_independent():
    """Non-overlapping windows, checked against the promotion gate's own rule."""
    frame = _frame()
    spec = replay_study.horizon_for("5w")
    grid = replay_study.historical_cutoffs(
        frame["date"], bars_ahead=spec.bars, count=20,
        min_history=replay_study.min_history_bars(spec))
    dates = list(pd.to_datetime(frame["date"], utc=True))
    windows = [(cutoff, dates[dates.index(cutoff) + spec.bars]) for cutoff in grid]

    assert len(promotion.independent_cutoffs(windows)) == len(grid)


def test_a_short_stride_produces_more_rows_but_not_more_draws():
    """Overlap is allowed and is never miscounted as resolution."""
    frame = _frame()
    spec = replay_study.horizon_for("5w")
    dense = replay_study.historical_cutoffs(
        frame["date"], bars_ahead=spec.bars, count=20, stride_bars=5,
        min_history=replay_study.min_history_bars(spec))
    dates = list(pd.to_datetime(frame["date"], utc=True))
    windows = [(cutoff, dates[dates.index(cutoff) + spec.bars]) for cutoff in dense]

    assert len(dense) == 20
    assert len(promotion.independent_cutoffs(windows)) < len(dense)


def _crypto_frame(*, rows: int = ROWS, seed: int = 5) -> pd.DataFrame:
    """A seven-day-a-week series — the shape that broke two earlier rules."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, rows)))
    return pd.DataFrame({
        "date": pd.date_range("2019-01-01", periods=rows, freq="D", tz="UTC"),
        "open": close, "high": close * 1.02, "low": close * 0.98,
        "close": close, "volume": np.full(rows, 1e6),
    })


def test_the_calendar_ignores_a_seven_day_series_it_is_outnumbered_by():
    """A crypto ticker must not put the grid on weekends for 29 equities."""
    frames = {f"EQ{i}": _frame(seed=i) for i in range(5)}
    frames["BTC-USD"] = _crypto_frame()
    calendar = replay_study.majority_calendar(frames)

    assert calendar, "a majority calendar must exist"
    assert all(pd.Timestamp(day).weekday() < 5 for day in calendar), (
        "the seven-day series set the calendar despite being outnumbered")


def test_an_all_crypto_universe_keeps_its_own_seven_day_calendar():
    """The rule degenerates correctly rather than assuming equities."""
    frames = {f"C{i}": _crypto_frame(seed=i) for i in range(3)}
    calendar = replay_study.majority_calendar(frames)

    assert any(pd.Timestamp(day).weekday() >= 5 for day in calendar)


def test_a_recent_listing_cannot_shorten_the_calendar():
    """"At least half", not "all" — one young ticker must not truncate history."""
    frames = {f"EQ{i}": _frame(seed=i) for i in range(4)}
    frames["NEW"] = _frame().tail(40).reset_index(drop=True)
    calendar = replay_study.majority_calendar(frames)

    assert len(calendar) == ROWS, "a 40-bar listing shortened the whole calendar"


def test_the_grid_is_independent_on_a_mixed_universe():
    """The property the calendar rule exists to protect, end to end."""
    frames = {f"EQ{i}": _frame(seed=i) for i in range(5)}
    frames["BTC-USD"] = _crypto_frame()
    spec = replay_study.horizon_for("5w")
    grid = replay_study.shared_calendar(
        frames, bars_ahead=spec.bars, count=20,
        min_history=replay_study.min_history_bars(spec))
    calendar = replay_study.majority_calendar(frames)
    positions = {day: index for index, day in enumerate(calendar)}
    windows = [(cutoff, calendar[positions[cutoff] + spec.bars]) for cutoff in grid]

    assert grid
    assert len(promotion.independent_cutoffs(windows)) == len(grid)


# ------------------------------- 4. live and historical cannot be confused


def test_a_study_row_cannot_enter_the_prospective_ledger(tmp_path):
    """The CHECK constraint, not a filter — same lock RR-2 established."""
    frame = _frame()
    _run(tmp_path, frame, count=3)
    row = forecast_ledger.ReplayLedger(tmp_path / "study.sqlite3").list()[0]
    prospective = forecast_ledger.ForecastLedger(tmp_path / "live.sqlite3")

    assert row.production_or_challenger == forecast_ledger.RETROSPECTIVE_REPLAY
    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(prospective.path) as connection:
            connection.execute(
                """INSERT INTO forecasts (forecast_id, generated_at, cutoff_at,
                       symbol, horizon, source_path, production_or_challenger,
                       input_fingerprint, payload, payload_sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row.forecast_id, row.generated_at, row.cutoff_at, row.symbol,
                 row.horizon, row.source_path, row.production_or_challenger,
                 row.input_fingerprint, "{}", "0" * 64))


def test_a_study_row_says_it_is_a_study_row(tmp_path):
    """Provenance distinguishes a swept row from an RR-2 session recovery."""
    frame = _frame()
    run = _run(tmp_path, frame, count=3)
    for record in forecast_ledger.ReplayLedger(tmp_path / "study.sqlite3").list():
        study = record.metadata["replay"]["study"]
        assert study["source"] == replay_study.STUDY_SOURCE
        assert study["study_id"] == run.study_id
        assert study["horizon"] == "5w"
        assert study["bars_ahead"] == 25


def test_an_rr2_session_recovery_is_not_accepted_as_a_study_row(tmp_path):
    """`assert_study` layers on `assert_replay` rather than replacing it.

    Both loops write `RETROSPECTIVE_REPLAY`, so the class alone cannot separate
    a swept study row from a missed-session recovery. The study block is what
    does, and this proves the check has teeth: a genuine RR-2 replay — valid
    under `assert_replay` — is refused by `assert_study`.
    """
    from core import replay

    frame = _frame()
    ledger = forecast_ledger.ReplayLedger(tmp_path / "rr2.sqlite3")
    sessions = sorted(set(pd.to_datetime(frame["date"], utc=True)))[-3:-1]
    replay.replay_symbol(
        "AAA", sessions, ledger=ledger, fetcher=_fetcher(frame),
        horizons=[ultimate.HORIZON_BY_KEY["1d"]],
        now=pd.Timestamp(frame["date"].iloc[-1]) + pd.Timedelta(days=1))

    recovered = ledger.list()
    assert recovered, "the RR-2 fixture must actually write something"

    forecast_ledger.assert_replay(recovered)     # valid as a replay
    with pytest.raises(forecast_ledger.ForecastIntegrityError):
        replay_study.assert_study(recovered)     # but not as a study row


def test_a_study_rows_identity_covers_its_own_provenance(tmp_path):
    """Stripping the study block cannot be done quietly — the digest moves."""
    frame = _frame()
    _run(tmp_path, frame, count=3)
    record = forecast_ledger.ReplayLedger(tmp_path / "study.sqlite3").list()[0]

    metadata = dict(record.metadata)
    metadata["replay"] = {k: v for k, v in record.metadata["replay"].items()
                          if k != "study"}

    with pytest.raises(ValueError, match="forecast_id does not match"):
        dataclasses.replace(record, metadata=metadata)


def test_the_study_never_counts_toward_prospective_resolution(tmp_path):
    """A study row may not move the number the promotion gate reads."""
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=6)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))
    study = replay_study.load_performance(path)
    assert not study.empty

    evidence = promotion.evidence_for(
        study, model_registry.ULTIMATE_ENSEMBLE, "5w")
    assert evidence.n_rows == 0
    assert evidence.n_independent_cutoffs == 0
    assert evidence.n_excluded_replays == len(study)


def test_the_study_reports_its_own_draws_separately(tmp_path):
    """It still counts them — for itself, under the same overlap rule."""
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=6)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))
    study = replay_study.load_performance(path)

    assert replay_study.independent_cutoff_count(study) == 6


# ----------------------------- 5. two model versions can never pool


def _two_version_frame(tmp_path) -> pd.DataFrame:
    """A scored study frame relabelled as if it spanned an engine change."""
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=8)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))
    performance = replay_study.load_performance(path)
    # Promote it out of replay status so the version rule is what is under test
    # rather than the replay exclusion, which fires first.
    performance = performance.copy()
    performance["status"] = forecast_ledger.PRODUCTION_INCUMBENT
    half = len(performance) // 2
    performance.loc[performance.index[:half], "model_version"] = "sha256:aaa"
    performance.loc[performance.index[half:], "model_version"] = "sha256:bbb"
    return performance


def test_evidence_refuses_to_measure_two_versions_as_one(tmp_path):
    """The defect HR-1 fixes: `model_key` pools versions by design."""
    mixed = _two_version_frame(tmp_path)
    assert set(mixed["model_version"]) == {"sha256:aaa", "sha256:bbb"}

    with pytest.raises(promotion.PooledVersionsError):
        promotion.evidence_for(mixed, model_registry.ULTIMATE_ENSEMBLE, "5w")


def test_naming_a_version_measures_that_version_alone(tmp_path):
    mixed = _two_version_frame(tmp_path)
    first = promotion.evidence_for(
        mixed, model_registry.ULTIMATE_ENSEMBLE, "5w", model_version="sha256:aaa")
    second = promotion.evidence_for(
        mixed, model_registry.ULTIMATE_ENSEMBLE, "5w", model_version="sha256:bbb")

    assert first.model_version == "sha256:aaa"
    assert second.model_version == "sha256:bbb"
    assert first.n_model_versions == second.n_model_versions == 2
    assert first.n_rows + second.n_rows == len(mixed)


def test_the_promotion_gate_blocks_on_a_pooled_frame(tmp_path):
    """V0 fails cleanly and reaches no statistic, the way G0 does."""
    mixed = _two_version_frame(tmp_path)
    verdict = promotion.evaluate_promotion(
        model_registry.ULTIMATE_ENSEMBLE, mixed, "5w")

    assert verdict.decision == promotion.BLOCK
    assert verdict.evidence is None
    names = [gate.name for gate in verdict.gates]
    assert "V0 one engine per measurement" in names
    assert not verdict.gates[-1].passed


def test_degradation_also_refuses_a_pooled_frame(tmp_path):
    """A mixture may not demote a model either — the D0 reasoning."""
    mixed = _two_version_frame(tmp_path)
    verdict = promotion.evaluate_degradation(
        model_registry.ULTIMATE_ENSEMBLE, mixed, "5w")

    assert verdict.decision == promotion.INSUFFICIENT_EVIDENCE
    assert verdict.evidence is None


def test_a_single_version_frame_passes_v0_untouched(tmp_path):
    """The gate must not become a tax on the ordinary case."""
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=6)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))
    single = replay_study.load_performance(path).copy()
    single["status"] = forecast_ledger.PRODUCTION_INCUMBENT

    evidence = promotion.evidence_for(single, model_registry.ULTIMATE_ENSEMBLE, "5w")
    assert evidence.n_model_versions == 1
    assert evidence.model_version == model_registry.get(
        model_registry.ULTIMATE_ENSEMBLE).version
    assert evidence.n_rows == len(single)


def test_the_study_summary_never_pools_versions(tmp_path):
    """HR-1 in the reporting layer, not only in the gate."""
    mixed = _two_version_frame(tmp_path)
    summaries = replay_study.summarise_study(mixed)

    assert len(summaries) == 2
    assert {s.model_version for s in summaries} == {"sha256:aaa", "sha256:bbb"}
    table = replay_study.versions_table(mixed)
    assert len(table) == 2


# ------------------------------------- 6. the live ledger is unchanged


def test_the_study_writes_nothing_to_the_prospective_ledger(tmp_path):
    """A sweep must not create, touch, or grow the live record."""
    live = tmp_path / "forecast_ledger.sqlite3"
    frame = _frame()
    _run(tmp_path, frame, count=5)
    replay_study.score_study(path=tmp_path / "study.sqlite3",
                             fetcher=_fetcher(frame))

    assert not live.exists(), "the study created a prospective ledger"


def test_the_default_study_path_is_not_the_live_ledger():
    """Three distinct files, so no default can collide with another."""
    assert replay_study.DEFAULT_STUDY_PATH != forecast_ledger.DEFAULT_PATH
    assert replay_study.DEFAULT_STUDY_PATH != forecast_ledger.DEFAULT_REPLAY_PATH


def test_live_freezing_still_behaves_exactly_as_before(tmp_path):
    """The prospective path is untouched: same class, same guards, same refusal."""
    frame = _frame()
    ledger = forecast_ledger.ForecastLedger(tmp_path / "live.sqlite3")
    now = pd.Timestamp(frame["date"].iloc[-1]) + pd.Timedelta(hours=2)

    verdict, outcome = forecast_ledger.freeze_incumbent_if_new(
        ledger, "AAA", horizons=[ultimate.HORIZON_BY_KEY["1d"]],
        fetcher=_fetcher(frame), generated_at=now)

    assert outcome.wrote_anything
    for record in outcome.frozen:
        assert record.production_or_challenger == forecast_ledger.PRODUCTION_INCUMBENT
        assert "replay" not in record.metadata
    forecast_ledger.assert_prospective(outcome.frozen)
    ledger.assert_prospective_only()

    # Idempotent on unchanged bars, exactly as before.
    _, again = forecast_ledger.freeze_incumbent_if_new(
        ledger, "AAA", horizons=[ultimate.HORIZON_BY_KEY["1d"]],
        fetcher=_fetcher(frame), generated_at=now)
    assert not again.wrote_anything


def test_the_incumbent_engine_source_is_unchanged(tmp_path):
    """A study row carries the *same* engine version as a live row.

    This is the property the whole study design turns on: the five-week horizon
    is passed in, never added to `ultimate.HORIZONS`, so `app/core/ultimate.py`
    is byte-identical and its sha256 is the identity both paths record.
    """
    frame = _frame()
    _run(tmp_path, frame, count=3)
    study_row = forecast_ledger.ReplayLedger(tmp_path / "study.sqlite3").list()[0]

    ledger = forecast_ledger.ForecastLedger(tmp_path / "live.sqlite3")
    _, live_outcome = forecast_ledger.freeze_incumbent_if_new(
        ledger, "AAA", horizons=[ultimate.HORIZON_BY_KEY["1d"]],
        fetcher=_fetcher(frame),
        generated_at=pd.Timestamp(frame["date"].iloc[-1]) + pd.Timedelta(hours=2))

    live_row = live_outcome.frozen[0]
    assert (study_row.model_versions["ultimate_ensemble"]
            == live_row.model_versions["ultimate_ensemble"])
    assert (model_registry.record_version(study_row)
            == model_registry.record_version(live_row))
    assert study_row.source_path == live_row.source_path == "app.core.ultimate.evaluate"


def test_the_five_week_horizon_is_not_in_the_production_engine():
    """`ultimate.HORIZONS` is the live contract and the study does not edit it."""
    assert "5w" not in ultimate.HORIZON_BY_KEY
    assert [h.key for h in ultimate.HORIZONS] == ["4h", "1d", "1w"]
    assert replay_study.FIVE_WEEKS.key == "5w"
    assert replay_study.FIVE_WEEKS.bars == 25
    # And the registry still describes only the production horizons.
    spec = model_registry.get(model_registry.ULTIMATE_ENSEMBLE)
    assert spec.horizons == ("4h", "1d", "1w")


def test_study_horizons_reuse_the_production_definitions():
    """`1d` and `1w` are the same objects, so study rows stay comparable."""
    assert replay_study.STUDY_HORIZONS["1d"] is ultimate.HORIZON_BY_KEY["1d"]
    assert replay_study.STUDY_HORIZONS["1w"] is ultimate.HORIZON_BY_KEY["1w"]
    assert "4h" not in replay_study.STUDY_HORIZONS


# ----------------------------------------------------------- reporting shape


def test_the_action_breakdown_covers_every_verdict_band(tmp_path):
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=6)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))
    table = replay_study.action_table(replay_study.load_performance(path))

    assert list(table["Call"]) == list(ultimate.ACTIONS)
    assert table["n"].sum() == len(replay_study.load_performance(path))
    hold = table.loc[table["Call"] == ultimate.HOLD].iloc[0]
    assert np.isnan(hold["Accuracy"]), "an abstention is not a wrong answer"


def test_the_summary_table_names_its_version_and_date_range(tmp_path):
    frame = _frame()
    path = tmp_path / "study.sqlite3"
    _run(tmp_path, frame, count=6)
    replay_study.score_study(path=path, fetcher=_fetcher(frame))
    table = replay_study.summary_table(replay_study.load_performance(path))

    assert len(table) == 1
    row = table.iloc[0]
    for column in ("Model", "Version", "Horizon", "Scored", "Independent cutoffs",
                   "Symbols", "From", "To", "Accuracy", "Beats baseline"):
        assert column in table.columns
    assert row["Horizon"] == "5w"
    assert row["Scored"] > 0


def test_a_sweep_logs_what_it_asked_when_given_a_log_directory(tmp_path):
    """Reproducibility: which cutoffs, which symbols, what failed.

    Opt-in by argument — the default is to write nothing, so a test or a
    library caller never leaves a file behind.
    """
    import json

    frame = _frame()
    assert _run(tmp_path, frame, count=4).frozen_records > 0
    assert not (tmp_path / "logs").exists(), "a log was written without being asked"

    run = _run(tmp_path, frame, count=4, symbols=("BBB",),
               log_dir=tmp_path / "logs")
    written = list((tmp_path / "logs").glob("replay_study_*.json"))
    assert len(written) == 1

    logged = json.loads(written[0].read_text(encoding="utf-8"))
    assert logged["study_id"] == run.study_id
    assert logged["horizon"] == "5w"
    assert logged["bars_ahead"] == 25
    assert len(logged["cutoffs"]) == len(run.cutoffs)


def test_loading_a_missing_study_creates_nothing(tmp_path):
    """Opening a panel must not start a record — the Phase 8 rule."""
    missing = tmp_path / "nothing.sqlite3"
    assert replay_study.load_performance(missing).empty
    assert replay_study.score_study(path=missing) == []
    assert not missing.exists()
