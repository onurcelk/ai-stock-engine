"""The API's one data door: intervals, bundled datasets, and the date window.

Three of the parity gaps were not missing engine capability. `live.fetch` has
always taken every interval in `live.INTERVALS`, `data.load` has always read
the bundled CSVs, and trimming a frame to two dates is two comparisons. What
was missing was a way to *ask*, so this pins the asking.

The window is deliberately a trim of a fetched series rather than a fetch
parameter: `period` decides what is downloaded and cached, `start`/`end` decide
what is looked at. A test below pins that distinction, because collapsing them
would re-download on every slider move and cache a hundred overlapping ranges.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi import HTTPException

from core import data, live

from api import bars

from .conftest import synthetic_bars


# ------------------------------------------------------------------ catalogue


def test_the_catalogue_offers_every_interval_the_engine_supports(client):
    body = client.get("/api/sources").json()

    assert [i["code"] for i in body["intervals"]] == list(live.INTERVALS.values())
    assert len(body["intervals"]) == 5, "1h, 4h, 1d, 1wk, 1mo"
    for entry in body["intervals"]:
        assert entry["periods"] == live.periods_for(entry["code"])
        assert entry["intraday"] == (entry["code"] in live.INTRADAY)


def test_intraday_and_daily_offer_different_periods(client):
    """Not decoration. Yahoo will not serve five years of hourly bars, so a
    selector offering that produces a failure nobody can diagnose."""
    body = client.get("/api/sources").json()
    by_code = {i["code"]: i for i in body["intervals"]}

    assert by_code["1h"]["periods"] != by_code["1d"]["periods"]
    assert "max" in by_code["1d"]["periods"]
    assert "max" not in by_code["1h"]["periods"]


def test_the_catalogue_lists_the_bundled_datasets(client):
    body = client.get("/api/sources").json()

    assert body["datasets"] == data.list_datasets()
    assert body["datasets"], "the offline fallback needs something to fall back to"


# -------------------------------------------------------------- the date window


def test_trim_keeps_a_closed_window(stub_bars):
    frame = stub_bars
    windowed = bars.trim(frame, "2024-02-01", "2024-03-01")

    assert len(windowed) < len(frame)
    assert windowed["date"].dt.date.min() >= dt.date(2024, 2, 1)
    assert windowed["date"].dt.date.max() <= dt.date(2024, 3, 1)


def test_trim_accepts_one_open_end(stub_bars):
    frame = stub_bars

    assert len(bars.trim(frame, "2024-02-01", None)) < len(frame)
    assert len(bars.trim(frame, None, "2024-02-01")) < len(frame)
    assert len(bars.trim(frame, None, None)) == len(frame)


def test_an_end_before_its_start_is_refused(stub_bars):
    with pytest.raises(HTTPException) as raised:
        bars.trim(stub_bars, "2024-06-01", "2024-01-01")

    assert raised.value.status_code == 400
    assert "after end" in raised.value.detail


def test_a_date_that_is_not_a_date_is_refused(stub_bars):
    with pytest.raises(HTTPException) as raised:
        bars.trim(stub_bars, "last tuesday", None)

    assert raised.value.status_code == 400
    assert "ISO date" in raised.value.detail


def test_a_window_with_too_few_bars_is_refused_with_the_count(stub_bars):
    """An empty-looking backtest reported as a result is worse than a refusal."""
    with pytest.raises(HTTPException) as raised:
        bars.resolve("AAPL", start="2024-01-01", end="2024-01-02")

    assert raised.value.status_code == 400
    assert "Widen the dates" in raised.value.detail


def test_the_window_trims_rather_than_refetching(stub_bars, monkeypatch):
    """`period` decides what is downloaded; `start`/`end` decide what is read.

    Pinned by counting fetches: a window must not become a second download, or
    every slider move would hit the network and the cache would fill with
    overlapping ranges.
    """
    calls = []
    original = live.fetch

    def counting(symbol, period="1y", interval="1d", force=False):
        calls.append((period, interval))
        return original(symbol, period=period, interval=interval)

    monkeypatch.setattr(live, "fetch", counting)

    bars.resolve("AAPL", period="5y", start="2024-02-01", end="2024-06-01")

    assert len(calls) == 1
    assert calls[0] == ("5y", "1d"), "the window must not change what is fetched"


# ------------------------------------------------------------------- datasets


def test_a_bundled_dataset_can_be_read_without_the_network(monkeypatch):
    """The offline path. `live.fetch` is made to fail outright, which is the
    situation whose error message has always recommended a bundled dataset."""
    def unreachable(*args, **kwargs):
        raise live.FetchError("Yahoo is unreachable")

    monkeypatch.setattr(live, "fetch", unreachable)

    frame, label = bars.resolve(dataset=data.list_datasets()[0])

    assert len(frame) > bars.MIN_BARS
    assert "CSV" in label
    assert {"date", "close"} <= set(frame.columns)


def test_an_unknown_dataset_names_the_ones_that_exist(monkeypatch):
    with pytest.raises(HTTPException) as raised:
        bars.resolve(dataset="not-a-dataset")

    assert raised.value.status_code == 400
    assert data.list_datasets()[0] in raised.value.detail


def test_a_strategy_can_be_scored_on_a_bundled_dataset(client, monkeypatch):
    """End to end, with the network refused -- the fallback actually working."""
    def unreachable(*args, **kwargs):
        raise live.FetchError("Yahoo is unreachable")

    monkeypatch.setattr(live, "fetch", unreachable)

    name = data.list_datasets()[0]
    response = client.get("/api/strategies/IGNORED",
                          params={"key": "crossover", "dataset": name})

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == f"{name} · CSV"
    assert body["metrics"]["return_pct"] is not None


def test_a_strategy_honours_the_date_window(client):
    whole = client.get("/api/strategies/AAPL", params={"key": "crossover"}).json()
    window = client.get("/api/strategies/AAPL", params={
        "key": "crossover", "start": "2024-03-01", "end": "2024-08-01"}).json()

    assert window["settings"]["bars"] < whole["settings"]["bars"]
    assert len(window["dates"]) == window["settings"]["bars"]
    assert window["dates"][0][:7] >= "2024-03"
    assert window["dates"][-1][:7] <= "2024-08"


def test_reading_bars_writes_nothing(client, isolated_ledger, isolated_runs):
    before = sorted(p.name for p in isolated_runs.iterdir())

    client.get("/api/sources")
    client.get("/api/strategies/AAPL", params={"key": "turtle",
                                               "start": "2024-02-01"})

    assert not isolated_ledger.exists()
    assert sorted(p.name for p in isolated_runs.iterdir()) == before


# ------------------------------------------------------------- bring your own


def _csv_bytes(rows: int = 120) -> bytes:
    frame = synthetic_bars(rows=rows)[["date", "open", "high", "low", "close", "volume"]]
    return frame.to_csv(index=False).encode("utf-8")


def test_an_uploaded_csv_is_scored(client, monkeypatch):
    """The other half of working offline: bring your own file.

    `live.fetch` is made to fail so nothing can quietly fall back to it.
    """
    def unreachable(*args, **kwargs):
        raise live.FetchError("Yahoo is unreachable")

    monkeypatch.setattr(live, "fetch", unreachable)

    response = client.post("/api/strategies/upload?key=crossover&name=mine.csv",
                           content=_csv_bytes())

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "mine.csv · upload"
    assert body["metrics"]["return_pct"] is not None
    assert len(body["equity"]) == len(body["dates"])


def test_an_upload_is_scored_by_the_same_code_as_a_live_series(client):
    """Same file through the upload route and the same bars through the live
    stub must produce the same number, or there are two scorers."""
    frame = synthetic_bars(rows=120)
    payload = frame[["date", "open", "high", "low", "close", "volume"]].to_csv(
        index=False).encode("utf-8")

    uploaded = client.post("/api/strategies/upload?key=crossover",
                           content=payload).json()

    from api.routers import strategies as strategies_router
    direct = strategies_router.score(frame, "direct", "crossover")

    assert uploaded["metrics"]["return_pct"] == pytest.approx(
        direct["metrics"]["return_pct"])
    assert uploaded["buys"] == direct["buys"]


def test_a_study_runs_on_an_upload_when_the_columns_are_there(client):
    body = client.post("/api/strategies/upload?key=supertrend",
                       content=_csv_bytes()).json()

    assert body["kind"] == "study"
    assert body["bands"], "an OHLC upload supports an overlay study"


def test_an_empty_or_unreadable_upload_is_refused(client):
    assert client.post("/api/strategies/upload?key=crossover",
                       content=b"").status_code == 400

    bad = client.post("/api/strategies/upload?key=crossover",
                      content=b"header only, no rows")
    assert bad.status_code == 400
    assert "Could not read" in bad.json()["detail"]


def test_an_upload_with_too_few_bars_is_refused(client):
    response = client.post("/api/strategies/upload?key=crossover",
                           content=_csv_bytes(rows=3))

    assert response.status_code == 400
    assert "usable bars" in response.json()["detail"]


def test_an_oversized_upload_is_refused_rather_than_read(client):
    from api.routers import strategies as strategies_router

    payload = b"x" * (strategies_router.MAX_UPLOAD_BYTES + 1)
    response = client.post("/api/strategies/upload?key=crossover", content=payload)

    assert response.status_code == 413


def test_an_upload_is_never_stored(client, tmp_path, isolated_runs):
    """Parsed, scored, dropped. Keeping someone's file would serve no purpose."""
    before = sorted(p.name for p in isolated_runs.iterdir())
    client.post("/api/strategies/upload?key=turtle", content=_csv_bytes())

    assert sorted(p.name for p in isolated_runs.iterdir()) == before
    assert not list(tmp_path.glob("*.csv"))
