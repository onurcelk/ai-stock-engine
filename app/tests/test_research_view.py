"""Phase 8 — the research surfaces read stored evidence and create nothing.

The load path is tested against a ledger that does not exist, because that is
the repository's actual state and the one the surfaces must survive.  Nothing
here touches `app/forecast_ledger.sqlite3`, the network, or a cache.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.core import model_registry, promotion, research_view


# ---------------------------------------------------------------- no side effects


def test_loading_an_absent_ledger_does_not_create_one(tmp_path):
    """Opening a tab must not start a research record.

    `ForecastLedger.__init__` creates its SQLite file, so a load path that
    constructed one to check whether it held anything would manufacture the
    very artefact whose absence Phase 7 §6 and Phase 9 §6 rest on.
    """
    missing = tmp_path / "not_here.sqlite3"

    state = research_view.load(missing)

    assert not missing.exists(), "reading the record must not create it"
    assert state.exists is False
    assert state.forecasts == ()
    assert state.outcomes == ()
    assert state.performance.empty


def test_the_repository_ledger_is_never_touched_by_a_load(tmp_path):
    state = research_view.load(tmp_path / "absent.sqlite3")

    assert state.n_independent_cutoffs == 0
    assert state.thin is True


# ------------------------------------------------------------- empty states


@pytest.fixture
def empty(tmp_path):
    return research_view.load(tmp_path / "absent.sqlite3")


def test_every_surface_renders_on_an_empty_record(empty):
    """None of these may raise, and none may invent a number."""
    assert not research_view.production_panel(empty).empty, (
        "production identity comes from the registry and exists without a "
        "ledger — it is the one panel that is never empty")
    assert research_view.active_weights(empty).empty
    assert research_view.quality(empty).empty
    assert research_view.rolling(empty).empty
    assert research_view.calibration(empty).empty
    assert research_view.history(empty).empty
    assert not research_view.leaderboard(empty).empty
    assert not research_view.pipeline().empty


def test_the_empty_state_says_why_it_is_empty(empty):
    warning = research_view.sample_size_warning(empty)

    assert warning is not None
    assert "ever been frozen" in warning, (
        "an empty panel must distinguish 'nothing measured' from 'measured "
        "and bad'")


def test_history_keeps_its_columns_when_there_is_no_history(empty):
    frame = research_view.history(empty)

    assert list(frame.columns) == list(research_view.HISTORY_COLUMNS), (
        "an empty table with no columns tells the reader nothing about what "
        "would have been shown")


# ------------------------------------------------------------- leaderboard


def test_unscored_models_stay_on_the_leaderboard(empty):
    """Hiding them would answer a question nobody asked."""
    board = research_view.leaderboard(empty)

    assert (board["n"] == 0).all()
    assert set(board["Status"]) <= set(model_registry.STATUSES)
    assert model_registry.ULTIMATE_ENSEMBLE in set(board["Identity"])


def test_the_leaderboard_only_lists_models_that_could_be_scored(empty):
    """A component with no ledger key cannot appear in a frozen forecast."""
    board = research_view.leaderboard(empty)
    listed = set(board["Identity"])

    for spec in model_registry.specs():
        if spec.record_key is None:
            assert spec.model_id not in listed, (
                f"{spec.model_id} cannot reach the ledger and must not be "
                "presented as if it could be scored")


# --------------------------------------------------------------- pipeline


def test_rejected_models_remain_visible(empty):
    """A rejection that disappears from the app is one nobody learns from."""
    pipeline = research_view.pipeline()

    assert "Rejected" in set(pipeline["Outcome"])
    assert "Retired" in set(pipeline["Outcome"])


def test_promotion_requirements_show_the_gate_not_a_summary(empty):
    requirements = research_view.promotion_requirements(empty)

    assert not requirements.empty
    assert (requirements["Decision"] == promotion.BLOCK).all(), (
        "on an empty ledger every challenger must be blocked")
    # The failing gates must be nameable, not merely counted.
    assert "G5 resolution" in set(requirements["Gate"])
    assert not requirements.loc[requirements["Gate"] == "G5 resolution",
                                "Met"].any()


def test_the_warning_threshold_is_the_promotion_threshold():
    """The number the user sees and the number the gate enforces are one."""
    assert research_view.MIN_CUTOFFS == promotion.MIN_INDEPENDENT_CUTOFFS


# -------------------------------------------------- counting, on real shapes


def _performance(cutoffs: int, symbols: int, *, span_days: int = 7,
                 spacing_days: int = 14) -> pd.DataFrame:
    start = pd.Timestamp("2026-01-05", tz="UTC")
    rows = []
    for index in range(cutoffs):
        cutoff = start + pd.Timedelta(days=spacing_days * index)
        for symbol in range(symbols):
            rows.append({
                "model_key": model_registry.ULTIMATE_ENSEMBLE,
                "horizon": "1d",
                "symbol": f"SYM{symbol}",
                "cutoff_at": cutoff,
                "matured_at": cutoff + pd.Timedelta(days=span_days),
                "predicted_return": 0.01,
                "realised_return": 0.02,
                "predicted_direction": "bullish",
                "directional_correct": True,
                "error": -0.01,
                "probability_positive": None,
                "baseline_relative_absolute_error": 0.001,
            })
    return pd.DataFrame(rows)


def _state(frame: pd.DataFrame, tmp_path) -> research_view.ResearchState:
    """A state as `load` would build it — outcomes never exist without the
    forecasts they score, so the placeholder tuples are sized to the frame."""
    placeholders = tuple(range(len(frame)))
    return research_view.ResearchState(
        ledger_path=tmp_path / "absent.sqlite3", exists=True,
        forecasts=placeholders, outcomes=placeholders, performance=frame)


def test_symbols_on_one_day_are_one_draw(tmp_path):
    narrow = _state(_performance(10, 2), tmp_path)
    wide = _state(_performance(10, 200), tmp_path)

    assert wide.n_independent_cutoffs == narrow.n_independent_cutoffs == 10, (
        "breadth must not inflate the draw count the user is shown")


def test_overlapping_forecasts_are_collapsed_before_counting(tmp_path):
    state = _state(_performance(30, 4, spacing_days=1, span_days=7), tmp_path)

    assert state.n_independent_cutoffs < 30


def test_a_thin_record_is_flagged_thin_and_a_deep_one_is_not(tmp_path):
    thin = _state(_performance(10, 4), tmp_path)
    deep = _state(_performance(60, 4), tmp_path)

    assert thin.thin is True
    assert deep.thin is False
    assert "independent cutoff" in research_view.sample_size_warning(thin)
    assert research_view.sample_size_warning(deep) is None


def test_a_frozen_but_unscored_record_says_so(tmp_path):
    state = research_view.ResearchState(
        ledger_path=tmp_path / "a.sqlite3", exists=True,
        forecasts=("placeholder",), outcomes=(), performance=pd.DataFrame())

    warning = research_view.sample_size_warning(state)

    assert "none matured" in warning, (
        "frozen-but-unmatured is a third state, and confusing it with "
        "'nothing frozen' would misreport progress")


def test_history_lists_newest_first(tmp_path):
    state = _state(_performance(5, 2), tmp_path)

    table = research_view.history(state)

    assert len(table) == 10
    assert table["Forecast date"].is_monotonic_decreasing
