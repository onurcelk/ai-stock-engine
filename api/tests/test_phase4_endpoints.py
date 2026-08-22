"""Phase 4: Monte Carlo, History and the ported studies.

Hermetic throughout -- `conftest.py`'s `client` fixture redirects the holdings
files and the saved-runs folder, and replaces `live.fetch` with a deterministic
synthetic series, so nothing here reads production state or the network.

The assertions that matter most are the delegation ones and the slicing one.
The first say these endpoints call the same `core` functions the Streamlit tabs
call rather than reimplementing them; the second pins the rule an indicator is
only correct under -- computed on the whole series, sliced afterwards.
"""

from __future__ import annotations

import types

import pandas as pd
import pytest

from core import live, montecarlo, pine, runs

from .conftest import synthetic_bars


# ------------------------------------------------------------- Monte Carlo


def test_montecarlo_returns_a_summary_and_paths(client):
    response = client.get("/api/montecarlo/AAPL?days=20&simulations=50&seed=42")
    assert response.status_code == 200
    body = response.json()

    assert body["symbol"] == "AAPL"
    assert body["days"] == 20
    assert set(body["summary"]) == {"mean", "median", "p5", "p95", "prob_up"}
    # `montecarlo.run` stacks a zero row before the walk, so a path covers the
    # starting bar plus each simulated day.
    assert len(body["median_path"]) == 21
    assert all(len(path) == 21 for path in body["paths"])


def test_montecarlo_delegates_and_invents_nothing(client, monkeypatch):
    """The endpoint must call `montecarlo.run`, not restate the random walk."""
    calls = []
    original = montecarlo.run

    def spy(close, days=30, simulations=100, seed=None):
        calls.append((len(close), days, simulations, seed))
        return original(close, days=days, simulations=simulations, seed=seed)

    monkeypatch.setattr(montecarlo, "run", spy)
    client.get("/api/montecarlo/AAPL?days=15&simulations=40&seed=1")

    assert len(calls) == 1
    _, days, simulations, seed = calls[0]
    assert (days, simulations, seed) == (15, 40, 1)


def test_montecarlo_never_ships_the_whole_matrix(client):
    """2,000 paths is half a million floats. The tab draws 120 and so does this."""
    response = client.get("/api/montecarlo/AAPL?days=252&simulations=2000&seed=3")
    body = response.json()
    assert body["simulations"] == 2000
    assert len(body["paths"]) == 120
    assert body["paths_drawn"] == 120


def test_montecarlo_is_reproducible_when_seeded(client):
    first = client.get("/api/montecarlo/AAPL?days=10&simulations=30&seed=99").json()
    second = client.get("/api/montecarlo/AAPL?days=10&simulations=30&seed=99").json()
    assert first["summary"] == second["summary"]
    assert first["median_path"] == second["median_path"]


@pytest.mark.parametrize("query", [
    "days=0", "days=999", "simulations=1", "simulations=99999", "bins=1",
])
def test_montecarlo_refuses_what_the_tab_would_never_offer(client, query):
    assert client.get(f"/api/montecarlo/AAPL?{query}").status_code == 422


def test_montecarlo_needs_more_than_one_bar(client, monkeypatch):
    one_row = synthetic_bars().head(1)
    monkeypatch.setattr(
        live, "fetch",
        lambda s, period="1y", interval="1d": (one_row, types.SimpleNamespace(is_fresh=True)))
    response = client.get("/api/montecarlo/AAPL")
    assert response.status_code == 400
    assert "two bars" in response.json()["detail"]


# ----------------------------------------------------------------- History


def test_runs_listing_is_empty_when_nothing_is_saved(client):
    body = client.get("/api/runs").json()
    assert body["runs"] == []
    assert body["total"] == 0
    assert body["kinds"] == dict(runs.KIND_LABELS)


def test_runs_listing_omits_payloads(client):
    runs.save(runs.AGENT, "AAPL", {"epochs": 5}, {"win_rate": 0.6},
              {"equity": [1, 2, 3]})
    body = client.get("/api/runs").json()

    assert body["total"] == 1
    assert "payload" not in body["runs"][0]
    assert body["runs"][0]["metrics"] == {"win_rate": 0.6}
    assert body["runs"][0]["kind_label"] == "Trading agent"


def test_a_single_run_carries_its_payload(client):
    saved = runs.save(runs.FORECAST, "MSFT", {"seed": 1}, {"accuracy": 0.5},
                      {"actual": [1, 2]})
    body = client.get(f"/api/runs/{saved.id}").json()
    assert body["payload"] == {"actual": [1, 2]}


def test_runs_can_be_filtered_by_kind(client):
    runs.save(runs.AGENT, "AAPL", {}, {})
    runs.save(runs.FORECAST, "MSFT", {}, {})

    assert client.get("/api/runs?kind=agent").json()["total"] == 1
    assert client.get("/api/runs?kind=forecast").json()["total"] == 1
    assert client.get("/api/runs").json()["total"] == 2


def test_an_unknown_kind_is_refused(client):
    response = client.get("/api/runs?kind=nonsense")
    assert response.status_code == 400
    assert "Unknown kind" in response.json()["detail"]


def test_a_missing_run_is_a_404(client):
    assert client.get("/api/runs/nope").status_code == 404
    assert client.delete("/api/runs/nope").status_code == 404


def test_deleting_a_run_removes_only_that_one(client):
    first = runs.save(runs.AGENT, "AAPL", {}, {})
    runs.save(runs.AGENT, "MSFT", {}, {})

    assert client.delete(f"/api/runs/{first.id}").status_code == 200
    remaining = client.get("/api/runs").json()
    assert remaining["total"] == 1
    assert remaining["runs"][0]["label"] == "MSFT"


def test_clearing_every_run_needs_an_explicit_confirmation(client):
    runs.save(runs.AGENT, "AAPL", {}, {})

    refused = client.post("/api/runs/clear")
    assert refused.status_code == 400
    assert "confirm=true" in refused.json()["detail"]
    assert client.get("/api/runs").json()["total"] == 1

    cleared = client.post("/api/runs/clear?confirm=true")
    assert cleared.status_code == 200
    assert cleared.json() == {"removed": 1}
    assert client.get("/api/runs").json()["total"] == 0


# ----------------------------------------------------------------- Studies


def test_the_catalogue_lists_every_ported_study(client):
    body = client.get("/api/studies").json()
    keys = {study["key"] for study in body["studies"]}
    assert keys == set(pine.INDICATORS)
    # Every study says which pane it belongs in and what it needs.
    for study in body["studies"]:
        assert study["pane"] in {pine.OVERLAY, pine.OSCILLATOR}
        assert study["requires"]


def test_a_study_returns_the_lines_it_declares(client):
    body = client.get("/api/studies/AAPL?keys=wavetrend").json()
    assert "wavetrend" in body["studies"]
    for line in pine.INDICATORS["wavetrend"].lines:
        assert line in body["studies"]["wavetrend"]
    assert len(body["dates"]) == body["bars"]


def test_an_unknown_study_is_refused(client):
    response = client.get("/api/studies/AAPL?keys=not_a_study")
    assert response.status_code == 400
    assert "Unknown study" in response.json()["detail"]


def test_a_close_only_series_reports_what_it_cannot_draw(client, monkeypatch):
    """A study the data cannot support is absent and explained, never a crash."""
    close_only = synthetic_bars()[["date", "close"]]
    monkeypatch.setattr(
        live, "fetch",
        lambda s, period="1y", interval="1d": (close_only,
                                               types.SimpleNamespace(is_fresh=True)))

    body = client.get("/api/studies/AAPL?keys=supertrend").json()
    assert body["studies"] == {}
    assert "supertrend" in body["unsupported"]
    assert "high" in body["unsupported"]["supertrend"]


def test_a_study_is_computed_on_the_whole_series_then_sliced(client):
    """The rule the Overview tab states in its own comment.

    An indicator fitted to the window on screen would change its reading every
    time the range changed. Asking for the last 60 bars must return exactly the
    last 60 values of the full-series computation, not a fresh fit to 60 bars.
    """
    full = client.get("/api/studies/AAPL?keys=wavetrend").json()
    windowed = client.get("/api/studies/AAPL?keys=wavetrend&bars=60").json()

    assert windowed["bars"] == 60
    for line in pine.INDICATORS["wavetrend"].lines:
        assert windowed["studies"]["wavetrend"][line] == \
            full["studies"]["wavetrend"][line][-60:]


def test_stats_come_straight_from_data_describe(client):
    from core import data

    body = client.get("/api/stats/AAPL").json()
    expected = data.describe(synthetic_bars())

    assert body["stats"]["rows"] == expected["rows"]
    assert body["stats"]["high"] == pytest.approx(expected["high"])
    assert body["stats"]["volatility_pct"] == pytest.approx(expected["volatility_pct"])


def test_no_phase4_endpoint_writes_to_the_book(client):
    """Monte Carlo, History and Studies are read-only with respect to holdings."""
    from core import holdings

    client.get("/api/montecarlo/AAPL?days=10&simulations=20&seed=1")
    client.get("/api/studies/AAPL?keys=wavetrend")
    client.get("/api/runs")
    client.get("/api/stats/AAPL")

    assert holdings.load() == []
    assert holdings.load_ledger() == []


def test_the_synthetic_series_is_what_the_endpoints_actually_read(client, stub_bars):
    """Guards the fixture itself: if `live.fetch` ever stopped being the one
    door these endpoints read through, this suite would silently start hitting
    the network instead of failing."""
    body = client.get("/api/ohlcv/AAPL").json()
    assert len(body["bars"]) == len(stub_bars)
    assert body["bars"][-1]["close"] == pytest.approx(float(stub_bars["close"].iloc[-1]))


def test_pandas_is_imported_for_the_fixture_contract():
    """The synthetic series must stay a DataFrame with the OHLCV contract every
    `core` function assumes; a fixture that drifted from it would make every
    other test here meaningless."""
    frame = synthetic_bars()
    assert isinstance(frame, pd.DataFrame)
    assert set(frame.columns) == {"date", "open", "high", "low", "close", "volume"}
    assert (frame["high"] >= frame["low"]).all()
