"""HT-1: the tournament cannot see the future, and cannot be confused with evidence.

Two different things are guarded, and only one of them is about arithmetic.

The first is **point-in-time safety across a roster of twenty-seven
candidates**. Every previous study in this repository proved this for one
engine; HT-1 asks it of seven Pine ports, ten technical sources, three rule
agents, four reconstructed RL policies and three recurrent architectures, and a
single leaking candidate would contaminate a leaderboard that reads as though
every row were comparable. The load-bearing test is
`test_rewriting_the_future_changes_no_call`: it multiplies every bar after the
cutoff by 3.5 and requires every call to be **identical**. It does not inspect
the truncation — it demonstrates the answer cannot depend on the future, which
is the same proof discipline as
`test_validation.py::test_future_cannot_change_the_verdict`.

The second matters more to the repository than to the leaderboard: these rows
must stay **out** of every record that can promote something. A tournament row
cannot enter the prospective ledger, a frozen signal cannot be edited after its
outcome is known, and the Pine studies registered for this study carry
`EXPERIMENTAL`, so `assert_record_admissible` refuses any production record
naming one. Those are research-record failures rather than measurement bugs, so
they are asserted rather than left to review.

Hermetic: frames are built in `tmp_path`, `app/cache/` is never read, no
network, and the fast suite trains nothing.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import indicators, model_registry, pine, tournament  # noqa: E402


# ------------------------------------------------------------------- fixtures


def ohlc(rows: int = 700, seed: int = 11, start: str = "2016-01-01") -> pd.DataFrame:
    """A deterministic OHLC frame long enough to clear the 500-bar floor."""
    rng = np.random.default_rng(seed)
    steps = rng.standard_normal(rows) * 0.6
    close = 100 + np.cumsum(steps)
    close = np.maximum(close, 5.0)
    spread = np.abs(rng.standard_normal(rows)) * 0.5 + 0.1
    return pd.DataFrame({
        "date": pd.bdate_range(start, periods=rows, tz="UTC"),
        "open": close - rng.standard_normal(rows) * 0.2,
        "high": close + spread,
        "low": close - spread,
        "close": close,
        "volume": np.full(rows, 10_000.0) + rng.integers(0, 500, rows),
    })


@pytest.fixture
def frames() -> dict[str, pd.DataFrame]:
    return {"AAA": ohlc(seed=11), "BBB": ohlc(seed=12), "CCC": ohlc(seed=13)}


@pytest.fixture
def grid(frames):
    return tournament.build_grid(frames)


@pytest.fixture
def cells(frames, grid):
    return tournament.admissible_cells(frames, grid)


@pytest.fixture
def store_path(tmp_path) -> Path:
    return tmp_path / "tournament.sqlite3"


def rewrite_future(frame: pd.DataFrame, cutoff: pd.Timestamp,
                   factor: float = 3.5) -> pd.DataFrame:
    """Every bar after the cutoff, multiplied. The past is left untouched."""
    changed = frame.copy(deep=True)
    after = changed["date"] > cutoff
    assert after.any(), "the rewrite must actually change something"
    for column in ("open", "high", "low", "close"):
        changed.loc[after, column] = changed.loc[after, column] * factor
    return changed


# ------------------------------------------- 1. the future cannot be consulted


def test_rewriting_the_future_changes_no_closed_form_call(frames, cells):
    """The load-bearing proof, for families P, T and R.

    Twenty calls per cell, and every one of them must be bit-identical after
    every future bar is multiplied by 3.5. A candidate that moves is reading
    ahead, and would be removed from the roster rather than repaired.
    """
    cell = cells[len(cells) // 2]
    frame = frames[cell.symbol]

    honest = tournament.closed_form_calls(tournament.truncate(frame, cell.cutoff))
    rewritten = tournament.closed_form_calls(
        tournament.truncate(rewrite_future(frame, cell.cutoff), cell.cutoff))

    assert honest, "the roster produced no calls at all"
    assert set(honest) == set(rewritten)
    moved = {k: (honest[k], rewritten[k]) for k in honest
             if honest[k] != rewritten[k]}
    assert not moved, f"these candidates read the future: {moved}"


def test_rewriting_the_future_changes_no_incumbent_call(frames, cells):
    cell = cells[len(cells) // 2]
    frame = frames[cell.symbol]
    honest = tournament.incumbent_calls(tournament.truncate(frame, cell.cutoff))
    rewritten = tournament.incumbent_calls(
        tournament.truncate(rewrite_future(frame, cell.cutoff), cell.cutoff))
    assert honest == rewritten


@pytest.mark.slow
def test_rewriting_the_future_changes_no_rl_call(frames, grid, cells):
    """Family A, whose policies are *trained* — so this is the real question.

    An agent trained on the whole series and replayed from bar zero moves 47–71%
    of its past signals when the future is rewritten; that is the measurement
    that made the repository's nineteen RL agents PIT-INADMISSIBLE. This asserts
    the reconstruction repairs it.
    """
    symbol = "AAA"
    frame = frames[symbol]
    cutoff = grid[len(grid) // 2]

    honest = tournament.rl_stances(frame, grid)
    rewritten = tournament.rl_stances(rewrite_future(frame, cutoff), grid)

    for candidate, series in honest.items():
        past = series.loc[series.index <= cutoff]
        other = rewritten[candidate].loc[rewritten[candidate].index <= cutoff]
        pd.testing.assert_series_equal(past, other, check_names=False)


def test_the_neural_payload_cannot_contain_the_future(frames, cells):
    """Amendment 2 §1 — family N's real point-in-time proof, and it needs no model.

    The worker process is handed **a list of 500 floats and nothing else**: no
    frame, no dates, no object a bar after the cutoff could travel inside. The
    future is not excluded by a comparison, it is absent from the address
    space. That is why this test is fast, exact, and does not depend on
    TensorFlow behaving reproducibly.
    """
    for cell in cells[:8]:
        truncated = tournament.truncate(frames[cell.symbol], cell.cutoff)
        payload = [float(v) for v in
                   truncated["close"].iloc[-tournament.NEURAL_TRAIN_BARS:]]
        expected = frames[cell.symbol]["close"].iloc[
            cell.position + 1 - tournament.NEURAL_TRAIN_BARS:cell.position + 1]
        assert payload == [float(v) for v in expected]
        assert len(payload) == tournament.NEURAL_TRAIN_BARS
        assert truncated["date"].max() == cell.cutoff


@pytest.mark.slow
def test_rewriting_the_future_changes_no_deterministic_neural_call(frames, cells):
    """Amendment 2 §2 — the equality proof, for the two architectures that hold it.

    GRU and Vanilla RNN are bit-identical across separate processes, so the
    original §3.2 proof applies to them unchanged. LSTM is excluded here and
    covered by the bounded check below; excluding it is Amendment 2's declared
    treatment, not a convenience.
    """
    cell = cells[len(cells) // 2]
    frame = frames[cell.symbol]
    honest = tournament.neural_calls(tournament.truncate(frame, cell.cutoff))
    rewritten = tournament.neural_calls(
        tournament.truncate(rewrite_future(frame, cell.cutoff), cell.cutoff))

    for candidate in ("neural.gru", "neural.vanilla_rnn"):
        assert honest[candidate] == rewritten[candidate], candidate


@pytest.mark.slow
def test_the_deterministic_architectures_really_are_reproducible(frames, cells):
    """The premise the test above rests on, asserted rather than assumed."""
    cell = cells[len(cells) // 2]
    truncated = tournament.truncate(frames[cell.symbol], cell.cutoff)
    runs = [tournament.neural_calls(truncated) for _ in range(3)]
    for candidate in ("neural.gru", "neural.vanilla_rnn"):
        assert (runs[0][candidate] == runs[1][candidate]
                == runs[2][candidate]), candidate


@pytest.mark.slow
def test_lstm_noise_under_a_rewrite_stays_inside_its_own_noise_band(frames, cells):
    """Amendment 2 §3 — characterises the noise. Does **not** prove causality.

    LSTM is not reproducible, so an equality test on it would fail for a reason
    that has nothing to do with look-ahead. What can be checked is that
    rewriting the future moves it no more than re-running it does.
    """
    cell = cells[len(cells) // 2]
    frame = frames[cell.symbol]
    truncated = tournament.truncate(frame, cell.cutoff)

    repeats = [tournament.neural_calls(truncated)["neural.lstm"]["1d"][1]
               for _ in range(3)]
    rewritten = tournament.neural_calls(
        tournament.truncate(rewrite_future(frame, cell.cutoff), cell.cutoff)
    )["neural.lstm"]["1d"][1]

    band = max(repeats) - min(repeats)
    assert abs(rewritten - np.mean(repeats)) <= max(band, 0.5) * 3


def test_a_truncated_frame_never_reaches_past_its_cutoff(frames, cells):
    for cell in cells[:12]:
        truncated = tournament.truncate(frames[cell.symbol], cell.cutoff)
        assert truncated["date"].max() == cell.cutoff
        assert len(truncated) == cell.position + 1


def test_the_fingerprint_refuses_a_frame_holding_the_future(frames, cells):
    """The second, independent mechanism: it checks the frame, not the caller."""
    from core import forecast_ledger

    cell = cells[0]
    with pytest.raises(forecast_ledger.ForecastIntegrityError):
        forecast_ledger.fingerprint_frame(frames[cell.symbol],
                                          cutoff_at=cell.cutoff)


def test_closed_form_candidates_are_causal(frames, cells):
    """Equality *is* causality: truncate-then-read must equal read-then-index.

    A mismatch would mean a candidate's value at the cutoff bar depends on bars
    that come after it. The study always computes on the truncated frame — this
    is a property test, never a shortcut the sweep takes.
    """
    cell = cells[len(cells) // 2]
    frame = frames[cell.symbol]
    truncated = tournament.truncate(frame, cell.cutoff)

    for key, source in indicators.SOURCES.items():
        on_truncated = float(source.read(truncated).iloc[-1])
        on_full = float(source.read(frame).iloc[cell.position])
        assert on_truncated == pytest.approx(on_full, abs=1e-9, nan_ok=True), key

    for key in pine.INDICATORS:
        on_truncated = float(
            indicators.stance(pine.signals(key, truncated)).iloc[-1])
        on_full = float(
            indicators.stance(pine.signals(key, frame)).iloc[cell.position])
        assert on_truncated == on_full, key


# --------------------------------------------- 2. frozen before it was scored


def test_predict_writes_no_outcome(frames, store_path):
    tournament.predict("closed_form", path=store_path, frames=frames)
    with sqlite3.connect(store_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 0


def test_score_writes_no_signal(frames, store_path):
    tournament.predict("closed_form", path=store_path, frames=frames)
    with sqlite3.connect(store_path) as connection:
        before = connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    tournament.score(path=store_path, frames=frames)
    with sqlite3.connect(store_path) as connection:
        after = connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        outcomes = connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    assert after == before
    assert outcomes > 0


def test_a_frozen_signal_cannot_be_modified(frames, store_path):
    tournament.predict("closed_form", path=store_path, frames=frames)
    with sqlite3.connect(store_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE signals SET call = 1.0")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM signals")


def test_a_second_predict_pass_writes_nothing_new(frames, store_path):
    first = tournament.predict("closed_form", path=store_path, frames=frames)
    with sqlite3.connect(store_path) as connection:
        after_first = connection.execute(
            "SELECT COUNT(*) FROM signals").fetchone()[0]
    tournament.predict("closed_form", path=store_path, frames=frames)
    with sqlite3.connect(store_path) as connection:
        after_second = connection.execute(
            "SELECT COUNT(*) FROM signals").fetchone()[0]
    assert first.rows > 0
    assert after_first == after_second


def test_the_store_admits_no_other_study(store_path):
    """The CHECK is the guarantee; the label is not."""
    tournament.TournamentStore(store_path).close()
    with sqlite3.connect(store_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO signals (signal_id, study_id, candidate, family,"
                " symbol, cutoff_at, horizon, call, last_price, position,"
                " input_fingerprint, frozen_at) VALUES"
                " ('x', 'AMS-1', 'c', 'f', 'AAA', 't', '1d', 1.0, 1.0, 1,"
                " 'fp', 'now')")


def test_no_ledger_is_created_by_a_tournament(frames, store_path, tmp_path):
    tournament.predict("closed_form", path=store_path, frames=frames)
    tournament.score(path=store_path, frames=frames)
    assert not (tmp_path / "forecast_ledger.sqlite3").exists()
    assert not (tmp_path / "replay_study.sqlite3").exists()
    assert not (tmp_path / "replay_ledger.sqlite3").exists()


# ------------------------------------------------- 3. the grid and the cells


def test_every_admitted_cell_satisfies_the_declared_rule(frames, cells):
    for cell in cells:
        dates = frames[cell.symbol]["date"]
        assert dates.iloc[cell.position] == cell.cutoff
        assert cell.position + 1 >= tournament.MIN_HISTORY_BARS
        assert cell.position + tournament.MAX_BARS_AHEAD < len(dates)


def test_the_grid_is_one_set_of_dates_for_every_symbol(frames, grid, cells):
    """Symbols read on the same day are one draw — so the grid is dates."""
    assert len(set(grid)) == len(grid)
    assert set(c.cutoff for c in cells) <= set(grid)
    spacing = pd.Series(sorted(grid)).diff().dropna()
    assert (spacing > pd.Timedelta(0)).all()


def test_a_symbol_that_did_not_trade_a_grid_date_is_skipped_not_snapped(frames, grid):
    holed = {name: frame.copy() for name, frame in frames.items()}
    dropped = grid[len(grid) // 2]
    holed["AAA"] = holed["AAA"].loc[holed["AAA"]["date"] != dropped].reset_index(
        drop=True)
    cells = tournament.admissible_cells(holed, grid)
    assert not any(c.symbol == "AAA" and c.cutoff == dropped for c in cells)
    assert any(c.symbol == "BBB" and c.cutoff == dropped for c in cells)


# ------------------------------------------------------ 4. scoring arithmetic


def test_the_realised_return_is_the_two_closes(frames, store_path):
    tournament.predict("closed_form", path=store_path, frames=frames)
    tournament.score(path=store_path, frames=frames)
    store = tournament.TournamentStore(store_path)
    try:
        frame = store.performance()
    finally:
        store.close()

    sample = frame.iloc[0]
    bars = tournament.HORIZON_BARS[sample["horizon"]]
    closes = frames[sample["symbol"]]["close"]
    position = int(frames[sample["symbol"]]["date"].searchsorted(sample["cutoff_at"]))
    expected = closes.iloc[position + bars] / closes.iloc[position] - 1.0
    assert sample["realised_return"] == pytest.approx(expected, abs=1e-12)


def test_a_hold_carries_no_accuracy(frames, store_path):
    tournament.predict("closed_form", path=store_path, frames=frames)
    tournament.score(path=store_path, frames=frames)
    store = tournament.TournamentStore(store_path)
    try:
        frame = store.performance()
    finally:
        store.close()
    holds = frame.loc[frame["call"] == 0.0]
    assert len(holds), "the fixture produced no abstentions to check"
    assert holds["directional_correct"].isna().all()


def test_a_call_is_correct_exactly_when_its_sign_matches(frames, store_path):
    tournament.predict("closed_form", path=store_path, frames=frames)
    tournament.score(path=store_path, frames=frames)
    store = tournament.TournamentStore(store_path)
    try:
        frame = store.performance()
    finally:
        store.close()
    called = frame.loc[frame["directional_correct"].notna()]
    expected = ((called["call"] > 0) & (called["realised_return"] > 0)) | (
        (called["call"] < 0) & (called["realised_return"] < 0))
    assert (called["directional_correct"].astype(bool) == expected).all()


# -------------------------------------------------- 5. the gate has teeth


def _synthetic_scored(accuracy: float, n_cutoffs: int = 40,
                      per_cutoff: int = 12, seed: int = 3) -> pd.DataFrame:
    """A candidate with a known directional accuracy against a 50% baseline."""
    rng = np.random.default_rng(seed)
    rows = []
    cutoffs = pd.date_range("2018-01-01", periods=n_cutoffs, freq="25D", tz="UTC")
    for cutoff in cutoffs:
        for i in range(per_cutoff):
            realised = float(rng.standard_normal()) * 0.02
            correct = rng.random() < accuracy
            call = 1.0 if (realised > 0) == correct else -1.0
            rows.append({
                "candidate": "technical.rsi", "family": "technical",
                "symbol": f"S{i}", "cutoff_at": cutoff, "horizon": "1w",
                "call": call, "magnitude": None, "last_price": 100.0,
                "realised_return": realised,
                "directional_correct": float(correct),
                "matured_at": cutoff + pd.Timedelta(days=7),
            })
    return pd.DataFrame(rows)


def test_a_candidate_under_the_call_floor_is_unresolved():
    frame = _synthetic_scored(0.99, n_cutoffs=8, per_cutoff=5)
    board = tournament.leaderboard(frame)
    assert board["Calls"].iloc[0] < tournament.MIN_CALLS
    assert board["Verdict"].iloc[0] == "UNRESOLVED"
    assert not board["Beats baseline"].iloc[0]


def test_a_coin_flip_candidate_does_not_beat_the_baseline():
    board = tournament.leaderboard(_synthetic_scored(0.50))
    assert board["Verdict"].iloc[0] == "REJECT"


def test_an_overwhelming_candidate_does_beat_the_baseline():
    """The gate must be *passable*, or it is not measuring anything."""
    board = tournament.leaderboard(_synthetic_scored(0.95))
    assert board["Calls"].iloc[0] >= tournament.MIN_CALLS
    assert board["Verdict"].iloc[0] == "BEATS BASELINE"
    assert board["Adv CI low"].iloc[0] > 0


def test_the_baseline_is_computed_on_identical_rows():
    """Not the all-cells up-rate: the up-rate on the rows the candidate called."""
    frame = _synthetic_scored(0.60)
    board = tournament.leaderboard(frame)
    called = frame.loc[frame["directional_correct"].notna()]
    assert board["Baseline accuracy"].iloc[0] == pytest.approx(
        float((called["realised_return"] > 0).mean()))


def test_holm_correction_is_applied_over_the_whole_family():
    strong = _synthetic_scored(0.95)
    weak = _synthetic_scored(0.52, seed=9)
    weak["candidate"] = "technical.macd"
    board = tournament.leaderboard(pd.concat([strong, weak], ignore_index=True))
    assert set(board["Family size"]) == {2}
    verdicts = dict(zip(board["Candidate"], board["Verdict"]))
    assert verdicts["technical.rsi"] == "BEATS BASELINE"
    assert verdicts["technical.macd"] == "REJECT"


def test_reference_arms_are_never_ranked_or_gated():
    frame = _synthetic_scored(0.95)
    frame["candidate"] = "reference.always_buy"
    board = tournament.leaderboard(frame)
    assert board["Verdict"].iloc[0] == "REFERENCE"
    assert not board["Beats baseline"].iloc[0]
    assert board["Family size"].iloc[0] == 0


# ------------------------------------------------ 6. the challenger's refusals


def test_the_split_is_chronological_and_sixty_forty():
    cutoffs = pd.date_range("2018-01-01", periods=88, freq="25D", tz="UTC")
    selection, validation = tournament.split_cutoffs(cutoffs)
    assert len(selection) == 53 and len(validation) == 35
    assert max(selection) < min(validation)


def test_no_challenger_is_built_from_fewer_than_two_survivors():
    challenger = tournament.build_challenger(_synthetic_scored(0.95))
    assert not challenger.built
    assert "fewer than two" in challenger.reason


def test_an_agent_only_survivor_set_is_barred_by_ams1(monkeypatch):
    """§0.1: the one construction HT-1 may not build, whatever it measures."""
    board = pd.DataFrame({
        "Candidate": ["rule.turtle", "rl.policy_gradient"],
        "Horizon": ["1w", "1w"],
        "Beats baseline": [True, True],
    })
    monkeypatch.setattr(tournament, "leaderboard", lambda frame: board)
    challenger = tournament.build_challenger(_synthetic_scored(0.95))
    assert not challenger.built
    assert "AMS-1" in challenger.reason and "11.3" in challenger.reason


# --------------------------------------------- 7. redundancy is a diagnostic


def test_two_identical_candidates_are_one_effective_opinion():
    index = pd.MultiIndex.from_product([["AAA"], pd.date_range(
        "2018-01-01", periods=60, freq="25D", tz="UTC")])
    rng = np.random.default_rng(5)
    calls = rng.choice([-1.0, 0.0, 1.0], size=60)
    matrix = pd.DataFrame({
        "technical.rsi": calls,
        "technical.macd": calls,                       # a literal clone
        "technical.adx": rng.choice([-1.0, 0.0, 1.0], size=60),
    }, index=index)
    result = tournament.redundancy(matrix)
    assert result["n_near_clones"] == 1
    assert result["effective_opinions"] == 2
    assert result["n_candidates"] == 3


# ----------------------------------------- 8. the roster and the frozen record


def test_the_roster_is_the_declared_twenty_seven_plus_two_references():
    assert len(tournament.RANKED) == 27
    assert len(tournament.CANDIDATES) == 29
    by_family: dict[str, int] = {}
    for key in tournament.RANKED:
        family = tournament.CANDIDATES[key].family
        by_family[family] = by_family.get(family, 0) + 1
    assert by_family == {
        tournament.PINE: 7, tournament.TECHNICAL: 10, tournament.RULE: 3,
        tournament.RL: 4, tournament.NEURAL: 3,
    }


def test_the_frozen_constants_match_the_preregistration():
    """A guard against a constant drifting away from the committed protocol."""
    assert tournament.GRID_STRIDE_BARS == 25
    assert tournament.MIN_HISTORY_BARS == 500
    assert tournament.MAX_BARS_AHEAD == 25
    assert tournament.HORIZON_BARS == {"1d": 1, "1w": 5, "5w": 25}
    assert tournament.MIN_CALLS == 200
    assert tournament.MIN_INDEPENDENT_CUTOFFS == 20
    assert tournament.GATE_ALPHA == 0.05
    assert tournament.NEAR_CLONE_RHO == 0.90
    assert tournament.SELECTION_FRACTION == 0.60
    assert tournament.SEED == 42
    assert tournament.NEURAL_TRAIN_BARS == 500
    assert tournament.NEURAL_EPOCHS == 60


def test_the_study_reuses_ams1s_frozen_objects_rather_than_copying_them():
    """Drift protection: the reconstruction is AMS-1's, not a second copy."""
    _, ams1, stats = tournament._alpha()
    assert tournament.SEED == ams1.AGENT_SEED
    assert tournament.NEURAL_TRAIN_BARS == ams1.TRAIN_BARS
    assert stats.BLOCK_LENGTH == 4 and stats.BOOTSTRAP_DRAWS == 10_000


def test_the_five_week_horizon_never_entered_the_engine():
    """HR-1's first trap, re-asserted because HT-1 uses the same horizon."""
    from core import ultimate

    assert "5w" not in {horizon.key for horizon in ultimate.HORIZONS}


def test_no_pine_study_is_an_ultimate_source():
    assert set(pine.INDICATORS) & set(indicators.SOURCES) == set()


# ----------------------------------------------- 9. the registry is a lock


def test_every_pine_study_is_registered():
    registered = {
        spec.model_id for spec in model_registry.specs()
        if spec.family == model_registry.PINE_STUDY
    }
    assert registered == {f"pine.{key}" for key in pine.INDICATORS}


def test_a_pine_study_can_never_reach_a_production_forecast():
    """Registration is a refusal, not a promotion."""
    for spec in model_registry.specs():
        if spec.family == model_registry.PINE_STUDY:
            assert spec.production_status == model_registry.EXPERIMENTAL
            assert spec.production_status not in model_registry.PRODUCTION_ADMISSIBLE


def test_registering_the_pine_studies_moved_no_existing_version():
    """The census grew; no identity changed. `version` hashes each spec's own
    module, and no existing spec's module was edited."""
    specs = {spec.model_id: spec for spec in model_registry.specs()}
    assert specs["ensemble.ultimate"].version_module == "app.core.ultimate"
    for key in indicators.SOURCES:
        assert specs[f"technical.{key}"].version_module == "app.core.indicators"
    for key in pine.INDICATORS:
        assert specs[f"pine.{key}"].version_module == "app.core.pine"


def test_the_technical_census_is_still_exactly_the_ultimate_sources():
    """The new family must not have leaked into `G_TECHNICAL`."""
    technical = {
        spec.record_key for spec in model_registry.specs()
        if spec.family == model_registry.TECHNICAL_INDICATOR
    }
    assert technical == set(indicators.SOURCES)
