"""The market scan: what it reads, what it refuses, and what it must not hide.

Four properties, and the last two are the ones worth having:

**It runs the engine, not a cheaper copy.** A scan row and the Signal page's
card for the same symbol at the same horizon have to be the same number, or the
page is a second opinion pretending to be the first one.

**It narrows the horizon without touching the engine.** `ultimate.py` is
version-identified by its own sha256 in the forecast ledger, so the scan pays
for its per-horizon loop in `api/routers/scan.py`. A test that the engine file
is unchanged belongs to the cutover suite; what belongs here is that the
narrowing produced exactly the horizon asked for.

**Nothing is filtered away.** HOLDs, unreadable symbols and outright failures
all come back, each with its reason. A screen that returned only its winners
would have no denominator, and eight buys out of twelve is a different fact
from eight out of two hundred.

**The 4-hour caveat travels with the payload.** PIT-1 measured that horizon
inverted after the close (p = 0.009). Carrying that in the response rather than
in the frontend is what stops a later refactor of the page from dropping it.
"""

from __future__ import annotations

import threading


def _finish(client, response, timeout: float = 30.0) -> dict:
    """Poll a started job to a terminal state, exactly as the page will."""
    job_id = response.json()["id"]
    waiter = threading.Event()
    for _ in range(int(timeout / 0.01)):
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["state"] in ("completed", "failed"):
            return body
        waiter.wait(0.01)
    raise AssertionError(f"job {job_id} never finished")


def _scan(client, **body) -> dict:
    started = client.post("/api/jobs/scan", json=body)
    assert started.status_code == 202, started.text
    finished = _finish(client, started)
    assert finished["state"] == "completed", finished["error"]
    return finished["result"]


# ------------------------------------------------------------------- options


def test_options_offer_every_engine_horizon(client):
    body = client.get("/api/scan/options").json()
    from core import ultimate

    assert [h["key"] for h in body["horizons"]] == [h.key for h in ultimate.HORIZONS]
    assert body["default_horizon"] == "4h"
    assert body["buy_actions"] == [ultimate.BUY, ultimate.STRONG_BUY]


def test_options_name_both_kinds_of_list(client):
    """The desk's own lists, and the market lists it can go and fetch."""
    body = client.get("/api/scan/options").json()
    keys = {u["key"] for u in body["universes"]}
    assert {"watchlist", "book", "cache", "picks"} <= keys
    assert {"sp500", "nasdaq", "nyse", "lse"} <= keys

    picks = next(u for u in body["universes"] if u["key"] == "picks")
    from core import live
    assert picks["symbols"] == list(live.QUICK_PICKS)
    assert picks["market"] is False


def test_market_lists_are_offered_without_their_symbols_inlined(client):
    """Thousands of tickers have no business in a page-load payload."""
    body = client.get("/api/scan/options").json()
    for row in body["universes"]:
        if row["market"]:
            assert row["symbols"] == []
            # `count` is None until the list has been downloaded -- the honest
            # answer, since a GET here never fetches one.
            assert row["count"] is None or isinstance(row["count"], int)


def test_a_page_load_never_downloads_a_listing(client, monkeypatch):
    """`GET /api/scan/options` must not reach the network, ever."""
    from core import universes

    def explode(*_args, **_kwargs):
        raise AssertionError("the options endpoint downloaded a listing")

    monkeypatch.setattr(universes, "_read", explode)
    assert client.get("/api/scan/options").status_code == 200


def test_the_four_hour_caveat_is_served_before_a_scan_is_run(client):
    """A warning that only arrives with the results is a warning shown too late."""
    body = client.get("/api/scan/options").json()
    four_hour = next(h for h in body["horizons"] if h["key"] == "4h")
    assert any("inverted" in c.lower() for c in four_hour["caveats"])
    assert any("p = 0.009" in c for c in four_hour["caveats"])


# ---------------------------------------------------------------- the reading


def test_a_scan_reads_every_symbol_it_was_given(client):
    result = _scan(client, symbols=["AAA", "BBB", "CCC"], horizon="4h")

    # A set, not a list: the table is ordered by call, which
    # `test_the_strongest_calls_sort_first` is the assertion for.
    assert {r["symbol"] for r in result["rows"]} == {"AAA", "BBB", "CCC"}
    assert result["scanned"] == 3
    assert result["symbols"] == ["AAA", "BBB", "CCC"]


def test_the_row_is_the_horizon_that_was_asked_for(client):
    """Narrowing must produce that horizon's own reading, at its own interval."""
    result = _scan(client, symbols=["AAA"], horizon="4h")

    assert result["horizon"]["key"] == "4h"
    row = result["rows"][0]
    assert row["interval"] == "1h"          # what the 4-hour horizon fetches
    assert row["bars_used"] == 4            # four hourly bars ahead


def test_a_scan_row_matches_the_signal_endpoint_for_the_same_symbol(client):
    """The property that makes a scan worth acting on: one engine, one answer."""
    result = _scan(client, symbols=["AAA"], horizon="4h")
    row = result["rows"][0]

    verdict = client.get("/api/signal/AAA").json()["verdict"]
    four_hour = next(h for h in verdict["horizons"] if h["horizon"]["key"] == "4h")

    assert row["action"] == four_hour["action"]
    assert row["score"] == four_hour["score"]
    assert row["confidence"] == four_hour["confidence"]


def test_holds_are_returned_rather_than_filtered_away(client):
    """The denominator is the point. Every symbol asked for comes back."""
    result = _scan(client, symbols=["AAA", "BBB"], horizon="4h")

    assert len(result["rows"]) == 2
    assert sum(result["counts"].values()) == result["readable"]
    assert set(result["counts"]) == {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"}
    # `buys` is a convenience list, not a filter applied to `rows`.
    assert set(result["buys"]) <= {r["symbol"] for r in result["rows"]}


def test_the_strongest_calls_sort_first(client):
    from api.routers.scan import ACTION_RANK

    result = _scan(client, symbols=["AAA", "BBB", "CCC"], horizon="4h")
    ranks = [(ACTION_RANK[r["action"]], r["score"]) for r in result["rows"]]
    assert ranks == sorted(ranks, reverse=True)


def test_the_caveat_travels_with_the_result(client):
    result = _scan(client, symbols=["AAA"], horizon="4h")
    assert any("inverted" in c.lower() for c in result["caveats"])


def test_a_daily_scan_carries_its_own_caveat_not_the_four_hour_one(client):
    result = _scan(client, symbols=["AAA"], horizon="1d")
    assert result["horizon"]["key"] == "1d"
    assert not any("inverted" in c.lower() for c in result["caveats"])
    assert any("always-predicting-up" in c for c in result["caveats"])


# -------------------------------------------------------------- what it refuses


def test_an_unknown_horizon_is_a_bad_request(client):
    response = client.post("/api/jobs/scan", json={"symbols": ["AAA"],
                                                   "horizon": "3m"})
    assert response.status_code == 400
    assert "3m" in response.json()["detail"]


def test_an_unknown_universe_is_a_bad_request(client):
    response = client.post("/api/jobs/scan", json={"universe": "russell3000"})
    assert response.status_code == 400
    assert "russell3000" in response.json()["detail"]


def test_an_empty_universe_says_so_rather_than_scanning_nothing(client):
    """An empty book is a real state; a job that succeeds with no rows is not
    an answer to "what should I buy"."""
    response = client.post("/api/jobs/scan", json={"universe": "book"})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_a_typed_list_wins_over_a_universe(client):
    result = _scan(client, universe="picks", symbols=["ZZZ"], horizon="4h")
    assert [r["symbol"] for r in result["rows"]] == ["ZZZ"]
    assert result["universe"] == "custom"


def test_symbols_are_capped(client, monkeypatch):
    """The cap is a guard against a malformed request, not a policy.

    Asserted against a lowered cap rather than the real 5,000: running a
    five-thousand-symbol job to prove a slice would put two minutes on the
    suite for one assertion.
    """
    from api.routers import scan as scan_router

    monkeypatch.setattr(scan_router, "MAX_SYMBOLS", 5)
    many = [f"S{i}" for i in range(12)]
    started = client.post("/api/jobs/scan", json={"symbols": many,
                                                  "horizon": "4h"})
    assert started.status_code == 202
    result = _finish(client, started)["result"]
    assert result["scanned"] == 5


# ------------------------------------------------------------ what it must not do


def test_a_scan_does_not_write_to_the_forecast_ledger(client, isolated_ledger):
    """A scan reads dozens of symbols nobody chose one at a time. Recording
    those as prospective forecasts would flood the one record whose entire
    value is that a person chose each cutoff."""
    _scan(client, symbols=["AAA", "BBB"], horizon="4h")
    assert not isolated_ledger.exists()


# ------------------------------------------------------- the market universes


def test_a_market_universe_is_fetched_inside_the_job(client, monkeypatch):
    """The listing download belongs to the job, not to the request handler.

    A request handler that downloaded would make `POST /api/jobs/scan` block on
    a third-party file before it could hand back an id -- and the id is the
    whole point of a job.
    """
    from core import universes

    calls = []

    def fake_fetch(key, *, force=False):
        calls.append(key)
        return universes.Listing(key, ["AAA", "BBB"], None, "test", {})

    monkeypatch.setattr(universes, "fetch", fake_fetch)
    monkeypatch.setattr(universes, "cached", lambda key: None)

    started = client.post("/api/jobs/scan", json={"universe": "nasdaq",
                                                  "horizon": "4h"})
    assert started.status_code == 202
    assert calls == []              # nothing downloaded to answer the POST

    result = _finish(client, started)["result"]
    assert calls == ["nasdaq"]      # the job did it
    assert {r["symbol"] for r in result["rows"]} == {"AAA", "BBB"}
    assert result["source"] == "NASDAQ"


def test_a_listing_that_cannot_be_built_fails_the_job_with_its_reason(client,
                                                                     monkeypatch):
    from core import universes

    def refuse(key, *, force=False):
        raise universes.UniverseError("the FTSE page layout has changed")

    monkeypatch.setattr(universes, "fetch", refuse)
    monkeypatch.setattr(universes, "cached", lambda key: None)

    started = client.post("/api/jobs/scan", json={"universe": "lse"})
    finished = _finish(client, started)
    assert finished["state"] == "failed"
    assert "layout has changed" in finished["error"]
