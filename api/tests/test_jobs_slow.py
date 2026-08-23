"""Phase 6, end to end with the real models. `--runslow` only.

Everything else in the Phase 6 suite substitutes an instant stand-in for the
training, because states, duplicates and guards do not depend on what the model
computes. That leaves one thing unproven: that the arguments this layer passes
are the arguments `forecast.walk_forward`, `forecast.project` and a real agent
actually take. A stand-in accepting `**kwargs` cannot fail that way, and a
signature drifting is exactly the sort of break that would otherwise surface
only when a person clicked the button.

So these three run the real thing at its smallest honest setting -- one epoch,
two folds, five iterations -- and assert only that it completed and produced
the shape the page reads. They are not measurements of anything and no result
here is evidence about any model.
"""

from __future__ import annotations

import threading

import pytest


pytestmark = pytest.mark.slow


def _finish(client, response, timeout: float = 600.0) -> dict:
    job_id = response.json()["id"]
    waiter = threading.Event()
    for _ in range(int(timeout / 0.05)):
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["state"] in ("completed", "failed"):
            return body
        waiter.wait(0.05)
    raise AssertionError(f"job {job_id} never finished")


def test_a_real_walk_forward_runs_through_the_job_layer(client, isolated_runs):
    started = client.post("/api/jobs/walkforward", json={
        "symbol": "AAPL", "folds": 2, "horizon": 30, "epochs": 1,
        "size_layer": 16, "num_layers": 1,
    })
    assert started.status_code == 202

    finished = _finish(client, started)
    assert finished["state"] == "completed", finished["error"]
    result = finished["result"]
    assert len(result["table"]) == 2
    assert "mean_directional" in result["summary"]
    assert client.get(f"/api/runs/{result['run_id']}").status_code == 200


def test_a_real_projection_runs_through_the_job_layer(client):
    started = client.post("/api/jobs/project", json={
        "symbol": "AAPL", "horizon": 5, "epochs": 1, "size_layer": 16,
    })
    assert started.status_code == 202

    finished = _finish(client, started)
    assert finished["state"] == "completed", finished["error"]
    assert len(finished["result"]["path"]) == 5
    assert finished["result"]["last_price"] > 0


def test_a_real_agent_trains_and_is_backtested_through_the_job_layer(
        client, isolated_runs):
    started = client.post("/api/jobs/agent", json={
        "symbol": "AAPL", "agent": "Evolution strategy", "iterations": 5,
        "window_size": 10, "layer_size": 32,
    })
    assert started.status_code == 202

    finished = _finish(client, started)
    assert finished["state"] == "completed", finished["error"]
    result = finished["result"]
    assert len(result["rewards"]) == 5
    assert len(result["equity"]) == len(result["dates"])
    assert client.get(f"/api/runs/{result['run_id']}").status_code == 200


def test_a_real_agent_run_still_cannot_move_the_book(client, isolated_runs, tmp_path):
    """The guard, exercised against a real training rather than a stub."""
    from core import holdings

    before = holdings.load()

    finished = _finish(client, client.post("/api/jobs/agent", json={
        "symbol": "AAPL", "agent": "Evolution strategy", "iterations": 5,
        "window_size": 10, "layer_size": 32,
    }))
    assert finished["state"] == "completed", finished["error"]

    assert holdings.load() == before
    assert not holdings.STORE.exists(), "a training run wrote a holdings file"
