"""The engine's evidence, served for drawing.

Three properties are worth guarding and the third is the one that matters:

**The catalogue is `indicators.SOURCES` itself**, not a second list that could
drift from it. A source added to the engine appears on the chart without this
router being touched, which is the same guarantee `/api/studies` gives for
`pine.INDICATORS`.

**The window cannot change the reading.** A source computed on whatever range
happens to be on screen would move every time the range buttons are pressed.
The values for a given bar must be identical whether 60 bars were asked for or
600.

**Silence is reported, not drawn.** A source that cannot read a series returns
zeros by the engine's own convention. Sent as a flat line, that is
indistinguishable from a measured neutral -- which is a different and much
stronger claim. It has to arrive as `silent` with a reason instead.
"""

from __future__ import annotations

from core import indicators


def test_the_catalogue_is_the_engines_own_source_list(client):
    body = client.get("/api/evidence").json()
    assert {s["key"] for s in body["sources"]} == set(indicators.SOURCES)
    # Including the four added on 2026-08-24, which is the point of the page.
    assert {"vwap_reversion", "vix_reversion", "opening_range",
            "pead"} <= set(indicators.SOURCES)


def test_every_source_declares_the_same_scale(client):
    """One pane, one axis. That only works if the levels really are shared."""
    body = client.get("/api/evidence").json()
    for source in body["sources"]:
        assert source["levels"] == [-1.0, 0.0, 1.0]
        assert source["pane"] == "oscillator"


def test_every_family_in_use_is_described(client):
    """The picker groups by family, so an undescribed one is a blank heading."""
    body = client.get("/api/evidence").json()
    used = {source["family"] for source in body["sources"]}
    assert used <= set(body["families"])


def test_readings_stay_inside_the_declared_scale(client, stub_bars):
    body = client.get("/api/evidence/AAPL",
                      params={"keys": "rsi,bollinger,vwap_reversion"}).json()
    assert body["sources"], body
    for key, values in body["sources"].items():
        assert all(-1.0 <= v <= 1.0 for v in values), key
        assert len(values) == body["bars"]


def test_the_window_cannot_change_the_reading(client, stub_bars):
    """Sliced after computing, never fitted to what is on screen."""
    whole = client.get("/api/evidence/AAPL",
                       params={"keys": "rsi"}).json()
    window = client.get("/api/evidence/AAPL",
                        params={"keys": "rsi", "bars": 60}).json()

    assert window["bars"] == 60
    assert window["sources"]["rsi"] == whole["sources"]["rsi"][-60:]
    assert window["dates"] == whole["dates"][-60:]


def test_a_source_with_no_opinion_is_silent_rather_than_flat(client, stub_bars):
    """`opening_range` cannot read a daily frame -- one bar is not a range.

    A flat line at zero would read as "measured neutral all year", which is a
    claim nobody made. It has to come back as silence, with a reason.
    """
    body = client.get("/api/evidence/AAPL",
                      params={"keys": "opening_range"}).json()
    assert "opening_range" not in body["sources"]
    assert "opening_range" in body["silent"]
    assert "not computable" in body["silent"]["opening_range"]


def test_silence_and_drawing_are_mutually_exclusive(client, stub_bars):
    body = client.get("/api/evidence/AAPL",
                      params={"keys": "rsi,opening_range,macd"}).json()
    assert not (set(body["sources"]) & set(body["silent"]))
    assert set(body["sources"]) | set(body["silent"]) == {
        "rsi", "opening_range", "macd"}


def test_an_unknown_source_is_a_400_that_names_the_real_ones(client, stub_bars):
    response = client.get("/api/evidence/AAPL", params={"keys": "not_a_source"})
    assert response.status_code == 400
    assert "not_a_source" in response.json()["detail"]
    assert "rsi" in response.json()["detail"]


def test_asking_for_nothing_draws_nothing(client, stub_bars):
    body = client.get("/api/evidence/AAPL").json()
    assert body["sources"] == {}
    assert body["silent"] == {}


def test_dates_line_up_with_every_series(client, stub_bars):
    """Two arrays the frontend zips. A length mismatch is a silent misdraw."""
    body = client.get("/api/evidence/AAPL",
                      params={"keys": "rsi,macd,trend_ma", "bars": 120}).json()
    for values in body["sources"].values():
        assert len(values) == len(body["dates"])


def test_the_router_reaches_no_writing_module():
    """Drawing a source is not recording a forecast."""
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "routers" / "evidence.py").read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]
    for forbidden in ("holdings", "ledger_activation", "forecast_ledger",
                      "runs.save"):
        assert forbidden not in body, f"evidence router reaches {forbidden}"


def test_the_router_declares_no_write_methods():
    from ..routers import evidence as router_module

    methods = set()
    for route in router_module.router.routes:
        methods |= set(getattr(route, "methods", ()))
    assert methods <= {"GET", "HEAD", "OPTIONS"}, methods
