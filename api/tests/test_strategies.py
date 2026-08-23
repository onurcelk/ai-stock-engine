"""The instant agents over HTTP: three fixed rules and seven ported studies.

These are the half of the Trading-agents tab that never needed a background
job, and the last functional gap between the Streamlit app and the new API.
What is pinned here is mostly *not* arithmetic -- `app/tests` already scores
`strategies.*`, `pine.signals` and `backtest.run` directly, and repeating those
assertions through a router would only test the router twice. What this file
pins is the wiring and the four properties that could quietly go wrong:

  1. The catalogue is the registry itself, so a study added to the engine
     appears without anyone editing the API.
  2. The endpoint delegates -- no signal maths restated in the router.
  3. Nothing here writes. Not the book, not the ledger, not a History run.
  4. A study the series cannot support is refused with the reason, not served
     as a silently empty result.
"""

from __future__ import annotations

import inspect

import pytest

from core import backtest, pine, strategies

from api.routers import strategies as strategies_router


# ------------------------------------------------------------- the catalogue


def test_the_catalogue_offers_every_rule_and_every_study(client):
    body = client.get("/api/strategies").json()

    assert [entry["key"] for entry in body["studies"]] == list(pine.INDICATORS)
    assert len(body["studies"]) == 7, "all seven ported studies"
    assert [entry["key"] for entry in body["rules"]] == list(strategies_router.RULES)
    assert len(body["rules"]) == 3, "turtle, crossover, rolling"
    assert set(body["sizing_modes"]) == set(backtest.SIZING_MODES)


def test_every_study_carries_its_published_rule(client):
    """A study traded on a rule nobody stated is not a ported study.

    The words come from `pine.SIGNAL_RULES`, not from this layer, so the tab
    and the page describe each study identically.
    """
    body = client.get("/api/strategies").json()

    for entry in body["studies"]:
        assert entry["rule"] == pine.SIGNAL_RULES[entry["key"]]
        assert entry["source"], "a port with no cited source is not a port"
        assert entry["params"] == [], "studies take their published defaults"


def test_every_rule_states_what_it_does(client):
    body = client.get("/api/strategies").json()

    for entry in body["rules"]:
        assert entry["rule"].strip(), f"{entry['key']} describes no rule"
        assert entry["params"], "a fixed rule with no parameters is a study"


def test_rule_defaults_scale_with_the_series(client):
    """The tab's sliders start on a fraction of the series length, so a channel
    on 250 bars is not the same channel on 2500. The API resolves that, rather
    than the page reimplementing the arithmetic."""
    short = client.get("/api/strategies", params={"bars": 250}).json()
    long = client.get("/api/strategies", params={"bars": 2500}).json()

    def window(body):
        rule = next(r for r in body["rules"] if r["key"] == "turtle")
        return next(p for p in rule["params"] if p["name"] == "window")["default"]

    assert window(short) < window(long)
    assert window(short) == 25 and window(long) == 250


# ------------------------------------------------------------------ scoring


@pytest.mark.parametrize("key", list(strategies_router.RULES))
def test_every_rule_scores(client, key):
    body = client.get("/api/strategies/AAPL", params={"key": key}).json()

    assert body["kind"] == "rule"
    assert body["key"] == key
    assert len(body["equity"]) == len(body["dates"])
    assert body["metrics"]["return_pct"] is not None
    assert body["final_value"] > 0


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_every_study_scores(client, key):
    body = client.get("/api/strategies/AAPL", params={"key": key}).json()

    assert body["kind"] == "study"
    assert body["rule"] == pine.SIGNAL_RULES[key]
    assert len(body["equity"]) == len(body["dates"])
    assert body["settings"]["bars"] > 0


def test_an_overlay_study_returns_its_lines_and_an_oscillator_does_not(client):
    """`pine.bands` is None for an oscillator by design -- nothing it draws
    belongs on a price axis. The response says so rather than inventing one."""
    overlay = client.get("/api/strategies/AAPL", params={"key": "supertrend"}).json()
    oscillator = client.get("/api/strategies/AAPL", params={"key": "squeeze"}).json()

    assert overlay["bands"], "an overlay study must return its lines"
    assert set(overlay["bands"]) == set(pine.INDICATORS["supertrend"].lines)
    assert oscillator["bands"] is None


def test_the_scored_signal_is_the_engine_s_own(client, stub_bars):
    """The endpoint's numbers are `backtest.run` on `pine.signals`, exactly.

    Computed here independently and compared, which is the assertion that would
    actually fail if the router ever grew its own copy of a rule.
    """
    frame = stub_bars
    expected = backtest.run(
        frame["close"], pine.signals("supertrend", frame), frame["date"],
        periods_per_year=252,
    )
    body = client.get("/api/strategies/AAPL", params={"key": "supertrend"}).json()

    assert body["metrics"]["return_pct"] == pytest.approx(expected.roi_pct)
    assert body["buys"] == expected.buys
    assert body["sells"] == expected.sells


def test_a_rule_honours_the_parameters_it_is_given(client, stub_bars):
    frame = stub_bars
    expected = backtest.run(
        frame["close"], strategies.turtle(frame["close"], 20, follow_breakout=True),
        frame["date"], periods_per_year=252,
    )
    body = client.get("/api/strategies/AAPL", params={
        "key": "turtle", "window": 20, "follow_breakout": True}).json()

    assert body["settings"]["window"] == 20
    assert body["settings"]["follow_breakout"] is True
    assert body["metrics"]["return_pct"] == pytest.approx(expected.roi_pct)


def test_sizing_reaches_the_backtester(client):
    """Fixed units and all-in must not produce the same number, or the control
    is decorative -- and the tab's own caveat about sizing would be wrong."""
    fixed = client.get("/api/strategies/AAPL", params={
        "key": "crossover", "sizing": "fixed_units"}).json()
    all_in = client.get("/api/strategies/AAPL", params={
        "key": "crossover", "sizing": "all_in"}).json()

    assert fixed["metrics"]["return_pct"] != all_in["metrics"]["return_pct"]


def test_costs_reach_the_backtester(client):
    free = client.get("/api/strategies/AAPL", params={"key": "crossover"}).json()
    charged = client.get("/api/strategies/AAPL", params={
        "key": "crossover", "fee_pct": 0.5, "slippage_pct": 0.5}).json()

    assert free["metrics"]["fees_paid"] == 0
    assert charged["metrics"]["fees_paid"] > 0
    assert charged["metrics"]["return_pct"] < free["metrics"]["return_pct"]


# ----------------------------------------------------------------- refusals


def test_an_unknown_strategy_is_refused_by_name(client):
    response = client.get("/api/strategies/AAPL", params={"key": "not-a-strategy"})

    assert response.status_code == 400
    assert "not-a-strategy" in response.json()["detail"]


def test_a_crossover_that_cannot_cross_is_refused(client):
    """Streamlit warns and carries on; an API has to decide. A short window at
    or above the long one describes no crossover at all, so it is a bad
    request rather than a result that means nothing."""
    response = client.get("/api/strategies/AAPL", params={
        "key": "crossover", "short_window": 50, "long_window": 20})

    assert response.status_code == 400
    assert "shorter" in response.json()["detail"]


def test_an_unknown_sizing_mode_is_refused(client):
    response = client.get("/api/strategies/AAPL", params={
        "key": "crossover", "sizing": "martingale"})

    assert response.status_code == 400


def test_a_study_the_series_cannot_support_is_refused_with_the_reason(
        client, monkeypatch):
    """Close-only series support none of the OHLC studies. That is a fact about
    the data, and the caller is told which columns are missing rather than
    handed an empty result."""
    import types as _types

    from core import live

    from .conftest import synthetic_bars

    close_only = synthetic_bars()[["date", "close"]]

    def fake_fetch(symbol, period="1y", interval="1d", force=False):
        return close_only.copy(), _types.SimpleNamespace(is_fresh=True)

    monkeypatch.setattr(live, "fetch", fake_fetch)

    response = client.get("/api/strategies/AAPL", params={"key": "supertrend"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "high" in detail and "low" in detail


# ------------------------------------------------- nothing here writes anything


def test_the_router_cannot_reach_the_book_or_the_ledger():
    """Structural, and the point of the phase.

    A behavioural test only proves a write did not happen for the inputs it
    tried. This module importing no writer at all is what makes a write
    impossible rather than merely absent -- the same argument
    `test_signal_write_boundary.py` makes for the read path.

    Read from the parsed tree rather than by grepping the text, so the
    docstring above is free to *name* the modules it promises not to import.
    A prose ban that the prose itself trips is not a guarantee, it is a typo
    waiting to be silenced with a rephrase.
    """
    import ast

    tree = ast.parse(inspect.getsource(strategies_router))
    forbidden = {"holdings", "ledger_activation", "forecast_ledger"}

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[-1] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.update(alias.name.split(".")[-1] for alias in node.names)
            if node.module:
                imported.add(node.module.split(".")[-1])

    assert not (imported & forbidden), (
        f"the strategies router imports a writer: {sorted(imported & forbidden)}")

    # And no call reaches a saver by attribute, whatever it was imported as.
    calls = {
        f"{ast.unparse(node.func.value)}.{node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
    }
    for banned in ("runs.save", "holdings.save", "holdings.execute"):
        assert banned not in calls, f"the router calls {banned}"


def test_scoring_a_strategy_writes_nothing(client, isolated_ledger, isolated_runs):
    """The behavioural half, over every kind of thing this router serves."""
    before = sorted(p.name for p in isolated_runs.iterdir())

    for key in [*strategies_router.RULES, *pine.INDICATORS]:
        assert client.get("/api/strategies/AAPL", params={"key": key}).status_code == 200

    assert not isolated_ledger.exists(), "scoring a strategy created a ledger"
    assert sorted(p.name for p in isolated_runs.iterdir()) == before


def test_the_router_delegates_rather_than_reimplementing():
    """Every signal must come from the engine, never from this file."""
    source = inspect.getsource(strategies_router)

    for called in ("strategies.turtle(", "strategies.moving_average(",
                   "strategies.signal_rolling(", "pine.signals(", "backtest.run("):
        assert called in source, f"{called} is not delegated to"
