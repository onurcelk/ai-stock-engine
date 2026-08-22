"""Phase 5: GET /api/research.

The first test is the one that matters. `ForecastLedger.__init__` and
`ReplayLedger.__init__` *create* their SQLite files, so an endpoint that
constructed one to find out whether it held anything would manufacture the very
artefact whose absence Phase 7 §6 and Phase 9 §6 rest on. `research_view`
guards this and its own tests cover it; this asserts the guarantee survives
being served over HTTP, which is the layer that could quietly reintroduce the
bug by reaching past `research_view.load()` for a "quick count".

The rest check that the payload keeps the warnings and the empty states, since
those are integrity features rather than presentation: a thin cell is evidence
about coverage, and the replay warning is the sentence that stops a reader
mistaking 12,000 reconstructions for a track record.
"""

from __future__ import annotations

import pytest

from core import forecast_ledger, replay_study, research_view


@pytest.fixture
def absent_ledgers(tmp_path, monkeypatch):
    """Point both records at paths that do not exist, and never create them."""
    ledger = tmp_path / "forecast_ledger.sqlite3"
    study = tmp_path / "replay_study.sqlite3"
    monkeypatch.setattr(forecast_ledger, "DEFAULT_PATH", ledger)
    monkeypatch.setattr(replay_study, "DEFAULT_STUDY_PATH", study)
    return ledger, study


def test_reading_the_page_does_not_create_a_record(client, absent_ledgers):
    """Opening a tab must not start a research record."""
    ledger, study = absent_ledgers
    assert not ledger.exists()
    assert not study.exists()

    response = client.get("/api/research")
    assert response.status_code == 200

    # The whole point: still absent afterwards.
    assert not ledger.exists(), "the endpoint created the forecast ledger"
    assert not study.exists(), "the endpoint created the replay study"


def test_an_absent_record_is_empty_by_fact_and_says_so(client, absent_ledgers):
    body = client.get("/api/research").json()

    assert body["exists"] is False
    assert body["counts"]["forecasts"] == 0
    assert body["counts"]["outcomes"] == 0
    assert body["counts"]["independent_cutoffs"] == 0
    # Not a silent zero -- the warning states that the emptiness is a fact
    # about the record rather than a filter.
    assert "does not exist" in body["warning"]
    assert body["study"]["exists"] is False
    assert "has been run" in body["study"]["warning"]


def test_the_promotion_floor_is_the_policy_number_not_a_restatement(client, absent_ledgers):
    body = client.get("/api/research").json()
    assert body["counts"]["min_cutoffs"] == research_view.MIN_CUTOFFS


def test_every_surface_is_a_frame_with_its_columns(client, absent_ledgers):
    body = client.get("/api/research").json()

    surfaces = [
        "production", "weights", "quality", "calibration", "rolling",
        "leaderboard", "history", "promotion_requirements", "pipeline",
    ]
    for name in surfaces:
        frame = body[name]
        assert set(frame) == {"columns", "rows"}, name
        assert isinstance(frame["columns"], list), name
        assert isinstance(frame["rows"], list), name

    for name in ("summary", "actions", "versions_table", "vs_live"):
        assert set(body["study"][name]) == {"columns", "rows"}, name


def test_the_pipeline_is_present_even_with_no_record(client, absent_ledgers):
    """`pipeline()` describes the declared roster, not the ledger, so it is the
    one surface that still has rows when nothing has ever been frozen."""
    body = client.get("/api/research").json()
    assert len(body["pipeline"]["rows"]) > 0
    assert "Model" in body["pipeline"]["columns"]


def test_the_endpoint_delegates_to_research_view(client, absent_ledgers, monkeypatch):
    """It must read through `research_view`, not reach for a ledger itself."""
    calls = []
    original_load = research_view.load
    original_study = research_view.load_study

    def spy_load(path=None):
        calls.append(("load", path))
        return original_load(path)

    def spy_study(path=None):
        calls.append(("load_study", path))
        return original_study(path)

    monkeypatch.setattr(research_view, "load", spy_load)
    monkeypatch.setattr(research_view, "load_study", spy_study)

    client.get("/api/research")

    assert ("load", None) in calls, "did not call research_view.load()"
    assert ("load_study", None) in calls, "did not call research_view.load_study()"
    # Called with no path: the defaults are the module's business, and passing
    # one from the API is how a test fixture's path would leak into production.
    assert all(path is None for _, path in calls)


def test_reading_research_writes_nothing_to_the_book(client, absent_ledgers):
    from core import holdings

    client.get("/api/research")
    assert holdings.load() == []
    assert holdings.load_ledger() == []
