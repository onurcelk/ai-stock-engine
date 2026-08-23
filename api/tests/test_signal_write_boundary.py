"""The line between reading a signal and recording one (2026-08-23).

`app/forecast_ledger.sqlite3` is append-only and never regenerable, and its
value rests on one claim: a person chose every cutoff in it. A `GET` that froze
a forecast could not support that claim, because a GET is issued by things that
are not people -- a prefetch, a StrictMode double-invoke in development, an
end-to-end replay, an uptime check. This file pins the three guards that now
stand between those and the record, each covering what the one before cannot:

  1. **Method.** The read is a GET and cannot write; the freeze is a POST.
  2. **Destination.** `ledger_activation.writes_blocked` refuses a *production*
     write from a test run or a process with writes switched off, whatever
     method asked.
  3. **Fixture.** `conftest.isolated_ledger` points the default somewhere
     scratch, so the suite is hermetic by construction and guard 2 never has to
     fire in it.

Guard 2 defends `ledger_activation.PRODUCTION_PATH`, a constant resolved at
import, rather than whatever `forecast_ledger.DEFAULT_PATH` currently holds --
otherwise it would refuse the tests that redirect correctly and wave through
the one that forgot. It is exercised two ways: against the real path as a pure
comparison that opens nothing, and against a scratch stand-in for the tests
that need a refusal to travel back through HTTP.
"""

from __future__ import annotations

import datetime as dt
import types

import numpy as np
import pandas as pd
import pytest

from core import forecast_ledger, ledger_activation, live


ROWS = 900


@pytest.fixture
def recent_bars(monkeypatch):
    """A synthetic series whose last bar is yesterday, so a freeze can succeed.

    `conftest.stub_bars` ends in 2024, which `assert_prospective` correctly
    refuses as a backfill; that guard is not what this file is testing, so the
    series is moved up to the present rather than the guard being turned off.
    """
    rng = np.random.default_rng(11)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.011, ROWS)))
    spread = close * rng.uniform(0.004, 0.02, ROWS)
    open_ = close + rng.normal(0, 1, ROWS) * close * 0.003
    end = pd.Timestamp(dt.date.today()) - pd.Timedelta(days=1)
    frame = pd.DataFrame({
        "date": pd.date_range(end=end, periods=ROWS, freq="D"),
        "open": open_,
        "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread,
        "close": close,
        "volume": rng.integers(1_000_000, 9_000_000, ROWS).astype(float),
    })

    def fake_fetch(symbol, period="1y", interval="1d", force=False):
        if not str(symbol).strip():
            raise live.FetchError("no symbol")
        return frame.copy(), types.SimpleNamespace(is_fresh=True)

    monkeypatch.setattr(live, "fetch", fake_fetch)
    return frame


# ------------------------------------------------------- 1. the method guard


def test_reading_a_signal_does_not_create_a_ledger(client, isolated_ledger, recent_bars):
    """The guarantee. A GET must leave no record behind -- not an empty one."""
    assert not isolated_ledger.exists()

    response = client.get("/api/signal/AAPL")
    assert response.status_code == 200

    assert not isolated_ledger.exists(), "GET /api/signal created the forecast ledger"


def test_reading_a_signal_reports_no_freeze_rather_than_an_empty_one(
        client, isolated_ledger, recent_bars):
    """`freeze: null` says no freeze was attempted.

    A `FreezeReport` with `active: false` would read as "the ledger is off",
    which is a different and untrue claim -- the ledger is on, this route just
    does not write to it.
    """
    body = client.get("/api/signal/AAPL").json()

    assert body["freeze"] is None
    assert body["verdict"]["symbol"] == "AAPL"
    assert body["verdict"]["action"]


def test_repeated_page_loads_stay_read_only(client, isolated_ledger, recent_bars):
    """Ten loads, as a mounting/remounting page would issue them."""
    for _ in range(10):
        assert client.get("/api/signal/AAPL").status_code == 200
    assert not isolated_ledger.exists()


def test_the_read_route_refuses_a_write_by_construction():
    """No route in the signal router reaches a freeze except the POST.

    Source-level, in the same spirit as
    `test_collector.py::test_the_collector_delegates_and_invents_nothing`: a
    behavioural test only proves the freeze does not happen for the inputs it
    tried, and the input that matters here is "whatever someone changes next".
    """
    import inspect

    from api.routers import signal as signal_router

    source = inspect.getsource(signal_router.get_signal)
    assert "active=False" in source, "the read path must decline freezing explicitly"
    assert "provenance" not in source, "the read path must not carry a write's metadata"


# --------------------------------------------------------- the write, working


def test_freezing_is_a_post_and_records_a_forecast(client, isolated_ledger, recent_bars):
    response = client.post("/api/signal/AAPL/freeze")
    assert response.status_code == 200
    body = response.json()

    assert body["freeze"]["frozen_ids"], body["freeze"]["summary"]
    assert isolated_ledger.exists()

    records = forecast_ledger.ForecastLedger(isolated_ledger).list()
    assert records
    for record in records:
        assert record.production_or_challenger == forecast_ledger.PRODUCTION_INCUMBENT
        assert record.source_path == "app.core.ultimate.evaluate"


def test_a_second_freeze_on_the_same_bars_adds_nothing(client, isolated_ledger, recent_bars):
    """Idempotent by input fingerprint -- a double-clicked button is not a date."""
    first = client.post("/api/signal/AAPL/freeze").json()
    second = client.post("/api/signal/AAPL/freeze").json()

    assert first["freeze"]["frozen_ids"]
    assert second["freeze"]["frozen_ids"] == []
    assert second["freeze"]["skipped_horizons"]

    assert len(forecast_ledger.ForecastLedger(isolated_ledger).list()) == len(
        first["freeze"]["frozen_ids"])


def test_a_symbol_that_cannot_be_read_freezes_nothing(client, isolated_ledger, monkeypatch):
    """An engine that produced no readable horizon must record no forecast."""
    def refuse(symbol, period="1y", interval="1d", force=False):
        raise live.FetchError(f"no data for {symbol}")

    monkeypatch.setattr(live, "fetch", refuse)

    body = client.post("/api/signal/NOSUCH/freeze").json()

    assert body["freeze"]["frozen_ids"] == []
    assert not isolated_ledger.exists()


# --------------------------------------------------------------- 2. provenance


def test_every_frozen_record_says_which_surface_asked(client, isolated_ledger, recent_bars):
    """The record can now answer "who wrote this", instead of leaving it to be
    inferred from a timestamp and a default symbol."""
    client.post("/api/signal/AAPL/freeze")

    records = forecast_ledger.ForecastLedger(isolated_ledger).list()
    assert records
    for record in records:
        provenance = record.metadata.get("provenance")
        assert provenance, "a record frozen through the API carries no provenance"
        assert provenance["source"] == forecast_ledger.SOURCE_API
        assert provenance["source"] in forecast_ledger.KNOWN_SOURCES


def test_provenance_must_name_a_source():
    """A provenance block with no source looks like an answer and is not one."""
    with pytest.raises(ValueError, match="non-empty source"):
        forecast_ledger._incumbent_records(
            verdict=None, input_frames={}, provenance={"note": "no source here"})


def test_all_three_surfaces_stamp_their_own_source():
    """Streamlit, the collector and the API each label themselves, distinctly.

    Read from source for Streamlit because importing `streamlit_app` boots a
    Streamlit script, which this suite has no business doing; the collector is
    importable, so it is inspected the same way `test_collector.py` inspects
    it. The point of the third assertion is that the three labels differ --
    provenance that collapsed to one value would answer nothing.
    """
    import inspect
    import pathlib

    from core import collector

    assert "SOURCE_COLLECTOR" in inspect.getsource(collector.collect)

    app = pathlib.Path(collector.__file__).resolve().parents[1] / "streamlit_app.py"
    assert "SOURCE_STREAMLIT" in app.read_text(encoding="utf-8")

    sources = {forecast_ledger.SOURCE_API, forecast_ledger.SOURCE_STREAMLIT,
               forecast_ledger.SOURCE_COLLECTOR}
    assert len(sources) == 3
    assert sources == set(forecast_ledger.KNOWN_SOURCES)


# ------------------------------------------------------- 3. the destination guard


def test_a_test_run_may_not_write_to_the_production_ledger():
    """Named on purpose, opened never.

    This is the guard that would have caught the failure
    `forecast_ledger.assert_prospective`'s docstring records having already
    happened -- a UI test freezing into the real record. It is asserted against
    the real default path because a scratch path would not exercise it.
    """
    blocked = ledger_activation.writes_blocked(ledger_activation.PRODUCTION_PATH)

    assert blocked is not None
    assert "test run" in blocked
    # And the constant really is the file at risk, not a stand-in for it.
    assert ledger_activation.PRODUCTION_PATH.name == "forecast_ledger.sqlite3"
    assert ledger_activation.PRODUCTION_PATH.parent.name == "app"


def test_the_guard_leaves_scratch_paths_alone(tmp_path):
    """A hermetic test writing to its own file must not be refused."""
    assert ledger_activation.writes_blocked(tmp_path / "forecast_ledger.sqlite3") is None


@pytest.mark.parametrize("setting", ["0", "off", "false", "NO"])
def test_the_switch_blocks_writes_for_a_browser_run(monkeypatch, tmp_path, setting):
    """`FORECAST_LEDGER_WRITES=off`, the switch an end-to-end run sets.

    `PYTEST_CURRENT_TEST` is removed first so the switch is what is being
    measured rather than the test detector standing in for it. A scratch path
    stands in for production, so this never names the real file.
    """
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    stand_in = (tmp_path / "forecast_ledger.sqlite3").resolve()
    monkeypatch.setattr(ledger_activation, "PRODUCTION_PATH", stand_in)

    monkeypatch.setenv(ledger_activation.WRITES_ENV_VAR, setting)
    blocked = ledger_activation.writes_blocked(stand_in)
    assert blocked and "switched off" in blocked

    monkeypatch.setenv(ledger_activation.WRITES_ENV_VAR, "on")
    assert ledger_activation.writes_blocked(stand_in) is None
    assert not stand_in.exists(), "checking the guard must not create a ledger"


def test_a_blocked_freeze_still_returns_the_reading(client, monkeypatch, tmp_path, recent_bars):
    """Refusing to record must never cost the caller their answer.

    `evaluate_and_freeze`'s own contract, kept end to end: the reading comes
    back, and the refusal is reported as `excluded` -- deliberately declined --
    rather than as an error or, worse, as silence.
    """
    # A stand-in for production: the guard is pointed at the same file the
    # endpoint will write to, so it fires, and the real ledger is never named.
    production = (tmp_path / "stands_in_for_production.sqlite3").resolve()
    monkeypatch.setattr(forecast_ledger, "DEFAULT_PATH", production)
    monkeypatch.setattr(ledger_activation, "PRODUCTION_PATH", production)

    body = client.post("/api/signal/AAPL/freeze").json()

    assert body["verdict"]["symbol"] == "AAPL"
    assert body["freeze"]["excluded"], "a blocked write must say so"
    assert body["freeze"]["frozen_ids"] == []
    assert body["freeze"]["error"] is None, "declining is not failing"
    assert not production.exists(), "the blocked write created the ledger anyway"


# ----------------------------------------------------- the offline read path


def test_a_signal_can_be_read_from_a_bundled_dataset(client, isolated_ledger,
                                                     monkeypatch):
    """The offline path for the app's primary page.

    `live.fetch` is made to fail, which is the situation whose error message
    has always recommended a bundled dataset -- so this is the recommendation
    actually working rather than pointing at a Streamlit sidebar.
    """
    from core import data

    def unreachable(*args, **kwargs):
        raise live.FetchError("Yahoo is unreachable")

    monkeypatch.setattr(live, "fetch", unreachable)

    name = data.list_datasets()[0]
    response = client.get("/api/signal/IGNORED", params={"dataset": name})

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["action"]
    assert body["freeze"] is None
    assert not isolated_ledger.exists(), "reading a dataset recorded a forecast"


def test_an_offline_read_declines_the_horizons_the_file_cannot_express(
        client, monkeypatch):
    """A daily CSV answers 1 day and 1 week and declines 4 hours. Declining is
    the honest answer; interpolating one would invent a reading."""
    from core import data

    body = client.get("/api/signal/IGNORED",
                      params={"dataset": data.list_datasets()[0]}).json()

    horizons = body["verdict"]["horizons"]
    assert horizons, "a daily file must still answer something"
    assert any(not h["available"] for h in horizons), (
        "a daily file cannot express every horizon and must say so")


def test_an_unknown_dataset_is_a_bad_request(client):
    response = client.get("/api/signal/IGNORED", params={"dataset": "nope"})

    assert response.status_code == 400
    assert "Unknown dataset" in response.json()["detail"]


def test_freezing_offers_no_dataset_option(client, isolated_ledger, recent_bars):
    """Recording a 2017 CSV as a *prospective* forecast is exactly what
    `assert_prospective` exists to refuse, so the option does not exist. A
    dataset parameter on the POST is ignored, not honoured."""
    import inspect

    from api.routers import signal as signal_router

    assert "dataset" not in inspect.signature(signal_router.freeze_signal).parameters
