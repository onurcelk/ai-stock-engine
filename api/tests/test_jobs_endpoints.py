"""Phase 6 over HTTP: starting a job, polling it, and the four ways it ends.

`api/tests/test_jobs.py` covers the registry. This covers the layer on top of
it -- status codes, validation, and the two answers that only exist at the HTTP
boundary: `410` for an id from a process that has since restarted, and `404`
for one this process simply never minted.

The real training bodies are replaced with instant stand-ins wherever the point
is the plumbing rather than the model. Where the point *is* the body, the test
inspects its source instead of running it: an LSTM fold takes minutes and
belongs behind `--runslow`, and `test_jobs_slow.py` runs it there.
"""

from __future__ import annotations

import inspect

import pytest

from api import jobs as jobs_module
from api.routers import jobs as jobs_router


def _finish(client, response, timeout: float = 10.0) -> dict:
    """Poll a started job to a terminal state, exactly as the page will."""
    job_id = response.json()["id"]
    import threading
    waiter = threading.Event()
    for _ in range(int(timeout / 0.01)):
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["state"] in ("completed", "failed"):
            return body
        waiter.wait(0.01)
    raise AssertionError(f"job {job_id} never finished")


@pytest.fixture
def instant(monkeypatch, jobs_registry):
    """Replace the three job bodies with work that returns immediately.

    Patched at `forecast.*` / the agent class rather than at the router, so the
    router's own argument-passing still runs -- what is skipped is the training,
    not the wiring.
    """
    from core import agents, backtest, forecast, runs
    import numpy as np
    import pandas as pd

    class _Fold:
        index, train_end = 0, 100
        dates = pd.Series(pd.date_range("2024-01-01", periods=3))
        actual = np.array([1.0, 2.0, 3.0])
        predicted = np.array([1.1, 2.1, 3.1])
        naive = np.array([1.0, 1.0, 1.0])
        accuracy = naive_accuracy = directional = mae = 50.0
        beats_naive = True

    class _Walk:
        folds = [_Fold()]
        horizon, model = 30, "LSTM"
        accuracies = directionals = naive_accuracies = maes = np.array([50.0])
        folds_beating_naive, win_rate_pct = 1, 100.0

        def summary(self):
            return {"mean_accuracy": 50.0, "std_accuracy": 0.0,
                    "worst_accuracy": 50.0, "best_accuracy": 50.0,
                    "mean_naive": 50.0, "mean_directional": 50.0,
                    "std_directional": 0.0, "mean_mae": 1.0,
                    "win_rate_pct": 100.0}

        def table(self):
            return pd.DataFrame([{"Fold": 1, "Accuracy %": 50.0}])

    class _Projection:
        model, horizon = "LSTM", 5
        path = np.array([101.0, 102.0, 103.0, 104.0, 105.0])
        last_price, final, move_pct, direction = 100.0, 105.0, 5.0, 1
        last_date = pd.Timestamp("2024-01-01")

    def fake_walk(close, dates, *, progress=None, **kwargs):
        if progress:
            progress(0, 0, 1, 0.01, 99.0)
        return _Walk()

    def fake_project(close, dates, *, progress=None, **kwargs):
        if progress:
            progress(0, 0, 1, 0.01, 99.0)
        return _Projection()

    class _Learner:
        def __init__(self, close, **kwargs):
            self.close = close

        def train(self, iterations, on_progress=None):
            if on_progress:
                on_progress(0, iterations, 1.5)
            return agents.TrainingReport(iterations=iterations, rewards=[1.5],
                                         seconds=0.01)

        def signals(self):
            import pandas as pd
            return pd.Series(0.0, index=self.close.index)

        def close_session(self):
            pass

    monkeypatch.setattr(forecast, "walk_forward", fake_walk)
    monkeypatch.setattr(forecast, "project", fake_project)
    monkeypatch.setitem(agents.REGISTRY, "Evolution strategy", _Learner)
    return {"walk": _Walk, "projection": _Projection}


# ----------------------------------------------------------------- starting up


def test_starting_a_walkforward_returns_202_and_an_id(client, instant):
    response = client.post("/api/jobs/walkforward", json={"symbol": "AAPL"})

    assert response.status_code == 202
    body = response.json()
    assert body["id"].startswith("job_")
    assert body["kind"] == "walkforward"
    assert body["state"] in ("queued", "running")
    assert body["duplicate"] is False
    assert "result" not in body, "the accept response must not carry a result"

    finished = _finish(client, response)
    assert finished["state"] == "completed"
    assert finished["result"]["summary"]["mean_directional"] == 50.0
    assert finished["result"]["run_id"], "a finished walk-forward is saved to History"


def test_a_walkforward_run_lands_in_the_history_endpoint(client, instant, isolated_runs):
    _finish(client, client.post("/api/jobs/walkforward", json={"symbol": "AAPL"}))

    runs_body = client.get("/api/runs?kind=walkforward").json()
    assert runs_body["total"] == 1
    assert runs_body["runs"][0]["settings"]["model"] == "LSTM"


def test_starting_a_projection_returns_the_path(client, instant):
    finished = _finish(client, client.post("/api/jobs/project", json={"symbol": "AAPL"}))

    assert finished["state"] == "completed"
    assert len(finished["result"]["path"]) == 5
    assert finished["result"]["move_pct"] == 5.0


def test_starting_an_agent_backtests_and_saves_it(client, instant, isolated_runs):
    finished = _finish(client, client.post("/api/jobs/agent", json={
        "symbol": "AAPL", "agent": "Evolution strategy", "iterations": 5}))

    assert finished["state"] == "completed"
    result = finished["result"]
    assert result["agent"] == "Evolution strategy"
    assert result["run_id"]
    assert "return_pct" in result["metrics"]
    assert "buy_hold_pct" in result["metrics"], "the agent must be scored against holding"

    assert client.get("/api/runs?kind=agent").json()["total"] == 1


def test_progress_is_visible_while_a_job_runs(client, instant):
    finished = _finish(client, client.post("/api/jobs/walkforward", json={"symbol": "AAPL"}))
    assert finished["progress"]["fraction"] == 1.0
    assert finished["progress"]["message"], "a finished job keeps its last message"


# ------------------------------------------------------------------ validation


def test_an_unknown_agent_is_refused_before_anything_is_queued(client, instant):
    response = client.post("/api/jobs/agent", json={
        "symbol": "AAPL", "agent": "Telepathy"})

    assert response.status_code == 400
    assert "Unknown agent" in response.json()["detail"]
    assert client.get("/api/jobs").json()["jobs"] == []


def test_an_unknown_sizing_mode_is_refused(client, instant):
    response = client.post("/api/jobs/agent", json={
        "symbol": "AAPL", "agent": "Evolution strategy", "sizing": "martingale"})
    assert response.status_code == 400
    assert "Unknown sizing" in response.json()["detail"]


def test_a_series_too_short_for_two_folds_is_a_bad_request(client, instant):
    """Refused at the boundary, not discovered as a failed job ten minutes in."""
    response = client.post("/api/jobs/walkforward", json={
        "symbol": "AAPL", "horizon": 200, "folds": 5})

    assert response.status_code == 400
    assert "two folds" in response.json()["detail"]


def test_out_of_range_settings_are_rejected_by_the_schema(client, instant):
    assert client.post("/api/jobs/walkforward",
                       json={"symbol": "AAPL", "epochs": 0}).status_code == 422
    assert client.post("/api/jobs/agent",
                       json={"symbol": "AAPL", "agent": "Evolution strategy",
                             "iterations": 10_000}).status_code == 422


def test_a_symbol_with_no_bars_is_a_bad_request(client, instant, monkeypatch):
    from core import live

    def refuse(symbol, period="1y", interval="1d", force=False):
        raise live.FetchError("no data")

    monkeypatch.setattr(live, "fetch", refuse)
    response = client.post("/api/jobs/walkforward", json={"symbol": "NOSUCH"})
    assert response.status_code == 400


# ------------------------------------------------------------------- failures


def test_a_job_whose_body_raises_is_reported_as_failed_not_as_a_500(
        client, instant, monkeypatch):
    from core import forecast

    def explode(close, dates, *, progress=None, **kwargs):
        raise RuntimeError("the rollout diverged")

    monkeypatch.setattr(forecast, "walk_forward", explode)

    started = client.post("/api/jobs/walkforward", json={"symbol": "AAPL"})
    assert started.status_code == 202

    finished = _finish(client, started)
    assert finished["state"] == "failed"
    assert "the rollout diverged" in finished["error"]
    assert finished["result"] is None


# ------------------------------------------------------------ duplicate jobs


def test_the_same_request_twice_returns_the_same_job(client, instant):
    body = {"symbol": "AAPL", "epochs": 3}
    first = client.post("/api/jobs/walkforward", json=body).json()
    second = client.post("/api/jobs/walkforward", json=body).json()

    # Either the first is still in flight (the same id, flagged) or it already
    # finished, in which case asking again is a legitimately new job. Both are
    # correct; what must never happen is two live jobs for one request.
    if second["duplicate"]:
        assert second["id"] == first["id"]
    else:
        assert client.get(f"/api/jobs/{first['id']}").json()["state"] in (
            "completed", "failed")


# --------------------------------------------------------------- polling


def test_polling_an_id_from_a_previous_process_is_410_and_says_why(client, instant):
    response = client.get("/api/jobs/job_0123456789ab_0001")

    assert response.status_code == 410
    detail = response.json()["detail"]
    assert "restarted" in detail
    assert "start it again" in detail


def test_polling_an_id_this_process_never_minted_is_404(client, instant):
    assert client.get("/api/jobs/nonsense").status_code == 404
    assert client.get(
        f"/api/jobs/job_{jobs_module.BOOT_ID}_4242").status_code == 404


def test_listing_jobs_omits_results_and_names_the_boot(client, instant):
    _finish(client, client.post("/api/jobs/walkforward", json={"symbol": "AAPL"}))

    body = client.get("/api/jobs").json()
    assert len(body["jobs"]) == 1
    assert "result" not in body["jobs"][0], "the list must stay small"
    assert body["boot"] == jobs_module.BOOT_ID


# ------------------------------------------------------------ the catalogue


def test_the_agent_catalogue_is_the_registry_itself(client):
    from core import agents

    body = client.get("/api/agents").json()

    assert [entry["name"] for entry in body["agents"]] == list(agents.REGISTRY)
    assert len(body["agents"]) == 19, "all 19 registered agents, not a subset"
    for entry in body["agents"]:
        assert entry["default_iterations"] == agents.DEFAULT_ITERATIONS[entry["name"]]
    assert set(body["sizing_modes"]) == set(__import__(
        "core.backtest", fromlist=["SIZING_MODES"]).SIZING_MODES)


# ------------------------------------------------------- wiring, not behaviour


@pytest.mark.parametrize("endpoint, called", [
    (jobs_router.start_walkforward, "forecast.walk_forward("),
    (jobs_router.start_project, "forecast.project("),
    (jobs_router.start_agent, "agents.REGISTRY["),
])
def test_each_endpoint_delegates_rather_than_reimplementing(endpoint, called):
    assert called in inspect.getsource(endpoint)


@pytest.mark.parametrize("endpoint", [
    jobs_router.start_walkforward,
    jobs_router.start_project,
    jobs_router.start_agent,
])
def test_every_body_carries_the_progress_callback_it_already_had(endpoint):
    source = inspect.getsource(endpoint)
    assert "progress=" in source or "on_progress=" in source


def test_the_agent_body_always_closes_its_tensorflow_session():
    """A leaked graph accumulates; the tab wraps its own call the same way."""
    source = inspect.getsource(jobs_router.start_agent)
    assert "finally:" in source
    assert "close_session()" in source
