"""The multi-symbol portfolio builder over HTTP.

The largest gap the parity audit found, because it is the only thing in the app
that answers how holdings behave *together* — two series that each look strong
but move in lockstep are one bet, not two.

What is pinned here is the wiring and the four things that could quietly go
wrong, not the allocation arithmetic (`app/tests` already scores
`core.portfolio` directly):

  1. The numbers are `portfolio.build`'s, computed independently and compared.
  2. Drift is reported. Without rebalancing the winners grow into a larger
     share, and that is a finding rather than a rendering detail.
  3. A basket whose members barely overlap is refused with the reason, because
     `align` inner-joins and five bars presented as a result is a lie.
  4. It writes nothing — least of all the saved book, which is a different
     thing that this endpoint must never touch.
"""

from __future__ import annotations

import inspect
import types

import pandas as pd
import pytest

from core import holdings, live, portfolio

from api.routers import basket as basket_router

from .conftest import synthetic_bars


@pytest.fixture
def three_symbols(monkeypatch):
    """Three genuinely different series, so correlation means something.

    `conftest.stub_bars` returns one frame for every symbol, which would make
    every correlation exactly 1.0 and quietly turn the diversification test
    into a tautology.
    """
    frames = {
        "AAA": synthetic_bars(rows=300, seed=1),
        "BBB": synthetic_bars(rows=300, seed=2),
        "CCC": synthetic_bars(rows=300, seed=3),
    }

    def fake_fetch(symbol, period="1y", interval="1d", force=False):
        key = str(symbol).strip().upper()
        if key not in frames:
            raise live.FetchError(f"no data for {key}")
        return frames[key].copy(), types.SimpleNamespace(is_fresh=True)

    monkeypatch.setattr(live, "fetch", fake_fetch)
    return frames


# -------------------------------------------------------------------- options


def test_the_options_come_from_the_module(client):
    body = client.get("/api/basket/options").json()

    assert [r["label"] for r in body["rebalance"]] == list(portfolio.REBALANCE)
    assert {r["label"]: r["bars"] for r in body["rebalance"]} == portfolio.REBALANCE
    assert body["max_holdings"] == portfolio.MAX_HOLDINGS


# --------------------------------------------------------------------- scoring


def test_a_basket_is_built_and_scored(client, three_symbols):
    body = client.get("/api/basket", params={"symbols": "AAA,BBB,CCC"}).json()

    assert body["symbols"] == ["AAA", "BBB", "CCC"]
    assert len(body["equity"]) == len(body["dates"]) == body["bars"]
    assert body["metrics"]["final_value"] > 0
    assert len(body["per_symbol"]) == 3
    assert set(body["rebased"]) == {"AAA", "BBB", "CCC"}


def test_the_numbers_are_the_module_s_own(client, three_symbols):
    """Computed here from `core.portfolio` directly and compared.

    This is the assertion that fails if the router ever grows its own
    allocation arithmetic.
    """
    prices = portfolio.align({s: f.copy() for s, f in three_symbols.items()})
    expected = portfolio.build(prices, {s: 100 / 3 for s in three_symbols},
                               initial_money=10_000.0, rebalance_every=0)

    body = client.get("/api/basket", params={"symbols": "AAA,BBB,CCC"}).json()

    assert body["metrics"]["roi_pct"] == pytest.approx(expected.roi_pct)
    assert body["metrics"]["sharpe"] == pytest.approx(expected.sharpe)
    assert body["metrics"]["max_drawdown_pct"] == pytest.approx(
        expected.max_drawdown_pct)
    assert body["equity"][-1] == pytest.approx(expected.final_value)


def test_equal_weights_by_default_and_explicit_weights_when_given(
        client, three_symbols):
    equal = client.get("/api/basket", params={"symbols": "AAA,BBB,CCC"}).json()
    assert all(w == pytest.approx(100 / 3) for w in equal["weights"].values())

    tilted = client.get("/api/basket", params={
        "symbols": "AAA,BBB,CCC", "weights": "50,25,25"}).json()
    assert tilted["weights"]["AAA"] == pytest.approx(50.0)


def test_weights_are_rescaled_to_a_hundred(client, three_symbols):
    """`normalise_weights` is the module's own behaviour, not this layer's."""
    body = client.get("/api/basket", params={
        "symbols": "AAA,BBB,CCC", "weights": "2,1,1"}).json()

    assert sum(body["weights"].values()) == pytest.approx(100.0)
    assert body["weights"]["AAA"] == pytest.approx(50.0)


def test_rebalancing_changes_the_outcome_and_is_counted(client, three_symbols):
    drifting = client.get("/api/basket", params={"symbols": "AAA,BBB,CCC"}).json()
    rebalanced = client.get("/api/basket", params={
        "symbols": "AAA,BBB,CCC", "rebalance_every": 21}).json()

    assert drifting["rebalanced"] == 0
    assert rebalanced["rebalanced"] > 0
    assert drifting["metrics"]["roi_pct"] != rebalanced["metrics"]["roi_pct"]


def test_drift_is_reported_against_the_target(client, three_symbols):
    """Where the money ended up, next to where it was aimed. Without this the
    basket looks like it still holds the weights it was given."""
    body = client.get("/api/basket", params={"symbols": "AAA,BBB,CCC"}).json()

    assert set(body["final_weights"]) == set(body["weights"])
    assert sum(body["final_weights"].values()) == pytest.approx(100.0)
    assert body["drift_pct"] == pytest.approx(
        max(abs(body["final_weights"][s] - body["weights"][s])
            for s in body["weights"]))
    assert body["heaviest"] in body["symbols"]


def test_correlation_and_its_verdict_travel_together(client, three_symbols):
    body = client.get("/api/basket", params={"symbols": "AAA,BBB,CCC"}).json()

    assert body["correlation"]["symbols"] == ["AAA", "BBB", "CCC"]
    assert len(body["correlation"]["matrix"]) == 3
    # The diagonal is 1 by definition; the verdict is the module's own words.
    for i, row in enumerate(body["correlation"]["matrix"]):
        assert row[i] == pytest.approx(1.0)
    assert body["diversification"]["verdict"]

    matrix = portfolio.correlations(portfolio.align(
        {s: f.copy() for s, f in three_symbols.items()}))
    average, verdict = portfolio.diversification_note(matrix)
    assert body["diversification"]["average"] == pytest.approx(average)
    assert body["diversification"]["verdict"] == verdict


def test_a_single_holding_has_no_correlation_to_report(client, three_symbols):
    """One holding has nothing to diversify against, so the block is absent
    rather than a 1x1 matrix presented as a finding."""
    body = client.get("/api/basket", params={"symbols": "AAA"}).json()

    assert body["correlation"] is None
    assert body["diversification"] is None


def test_the_window_and_the_interval_reach_the_basket(client, three_symbols):
    whole = client.get("/api/basket", params={"symbols": "AAA,BBB"}).json()
    window = client.get("/api/basket", params={
        "symbols": "AAA,BBB", "start": "2024-03-01", "end": "2024-08-01"}).json()

    assert window["bars"] < whole["bars"]
    assert window["dates"][0][:7] >= "2024-03"


# -------------------------------------------------------------------- refusals


def test_a_symbol_that_fails_is_skipped_and_named(client, three_symbols):
    """One bad ticker must not lose the whole basket -- `fetch_many`'s own
    contract, surfaced rather than swallowed."""
    body = client.get("/api/basket", params={"symbols": "AAA,NOPE,BBB"}).json()

    assert body["symbols"] == ["AAA", "BBB"]
    assert "NOPE" in body["skipped"]
    assert sum(body["weights"].values()) == pytest.approx(100.0)


def test_too_many_holdings_is_refused(client, three_symbols):
    too_many = ",".join(f"S{i}" for i in range(portfolio.MAX_HOLDINGS + 1))
    response = client.get("/api/basket", params={"symbols": too_many})

    assert response.status_code == 400
    assert str(portfolio.MAX_HOLDINGS) in response.json()["detail"]


def test_no_symbols_is_refused(client):
    assert client.get("/api/basket", params={"symbols": " , "}).status_code == 400


def test_a_weight_per_symbol_or_none_at_all(client, three_symbols):
    response = client.get("/api/basket", params={
        "symbols": "AAA,BBB,CCC", "weights": "50,50"})

    assert response.status_code == 400
    assert "one per symbol" in response.json()["detail"]


def test_holdings_that_barely_overlap_are_refused_with_the_reason(
        client, monkeypatch):
    """`align` inner-joins, so a basket of two series that share four bars is
    defined on four bars. That is refused, not served."""
    early = synthetic_bars(rows=100)
    late = synthetic_bars(rows=100)
    late["date"] = pd.date_range(early["date"].iloc[-4], periods=100, freq="D")

    frames = {"AAA": early, "BBB": late}

    def fake_fetch(symbol, period="1y", interval="1d", force=False):
        return frames[str(symbol).strip().upper()].copy(), types.SimpleNamespace(
            is_fresh=True)

    monkeypatch.setattr(live, "fetch", fake_fetch)

    response = client.get("/api/basket", params={"symbols": "AAA,BBB"})

    assert response.status_code == 400
    assert "barely overlap" in response.json()["detail"]


def test_every_symbol_failing_is_refused_rather_than_served_empty(
        client, three_symbols):
    response = client.get("/api/basket", params={"symbols": "NOPE,ALSONOPE"})

    assert response.status_code == 400
    assert "None of those symbols" in response.json()["detail"]


# ------------------------------------------------------- it touches no records


def test_the_basket_router_cannot_write(client, three_symbols, isolated_ledger,
                                        isolated_runs, isolated_holdings):
    """The hypothetical basket and the book you actually hold are different
    things, and Streamlit keeps them apart for the same reason."""
    holdings.save([])
    before = holdings.STORE.read_text(encoding="utf-8")

    client.get("/api/basket", params={"symbols": "AAA,BBB,CCC",
                                      "rebalance_every": 21})

    assert holdings.STORE.read_text(encoding="utf-8") == before
    assert not holdings.LEDGER.exists(), "the basket wrote a transaction ledger"
    assert not isolated_ledger.exists(), "the basket wrote a forecast ledger"
    assert not list(isolated_runs.iterdir()), "the basket filed a History run"


def test_the_router_imports_no_writer():
    """Structural, from the parsed tree so the docstring may name what it bans."""
    import ast

    tree = ast.parse(inspect.getsource(basket_router))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported.update(a.name.split(".")[-1] for a in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[-1])

    assert "holdings" not in imported
    assert "ledger_activation" not in imported
    assert "runs" not in imported


def test_the_router_delegates_rather_than_reimplementing():
    source = inspect.getsource(basket_router)

    for called in ("portfolio.fetch_many(", "portfolio.align(", "portfolio.build(",
                   "portfolio.per_symbol_stats(", "portfolio.correlations(",
                   "portfolio.diversification_note("):
        assert called in source, f"{called} is not delegated to"
    assert "np.zeros" not in source, "allocation arithmetic belongs in core"
