"""The last two retained capabilities: the quote board, and the book's curve.

Both were found by the second parity audit, which diffed `core.*` calls rather
than comparing tabs. What each one needs pinned is different:

**The board** is defined by what it must *not* do. `core.quotes` exists
because reading two numbers off a dozen symbols through `live.fetch` would
parse a decade of bars each and hit the network to do it. So the test that
matters is that no download happens — not that the numbers are right, which
`app/tests` already covers.

**The curve** is defined by three caveats that are not visible in the line:
it is only defined where every holding traded, it assumes today's share counts
throughout, and an empty one must stay empty rather than become a stub.
"""

from __future__ import annotations

import types

import pandas as pd
import pytest

from core import holdings, live, quotes

from .conftest import synthetic_bars


# --------------------------------------------------------------- the board


def test_the_board_never_downloads(client, monkeypatch):
    """The property the whole `core.quotes` module exists for.

    `live.fetch` is replaced with something that fails the test if it is
    called at all, rather than merely counted -- a board that downloaded once
    per symbol would still "work" and would be the exact mistake the module
    was written to avoid.
    """
    def forbidden(*args, **kwargs):
        raise AssertionError("the watchlist called live.fetch")

    monkeypatch.setattr(live, "fetch", forbidden)

    response = client.get("/api/watchlist", params={"symbol": "AAPL"})

    assert response.status_code == 200
    assert response.json()["quotes"]


def test_the_board_leads_with_the_symbol_being_looked_at(client):
    body = client.get("/api/watchlist", params={"symbol": "NVDA"}).json()

    assert body["active"] == "NVDA"
    assert body["quotes"][0]["symbol"] == "NVDA"


def test_the_quick_picks_mean_a_fresh_clone_still_has_a_board(client):
    """They come last so an empty cache still shows something, which was their
    original job in the sidebar."""
    body = client.get("/api/watchlist", params={"symbol": ""}).json()

    names = [row["symbol"] for row in body["quotes"]]
    assert names, "an empty cache must still produce a board"
    assert set(names) & set(live.QUICK_PICKS)


def test_an_uncached_symbol_is_listed_rather_than_dropped(client, monkeypatch):
    """"Not downloaded yet" and "no such symbol" are different states, and only
    one of them is worth hiding. A quote-less row stays selectable."""
    monkeypatch.setattr(quotes, "read_quote", lambda symbol, interval="1d": None)

    body = client.get("/api/watchlist", params={"symbol": "AAPL"}).json()

    assert body["quotes"], "rows must survive having no quote"
    for row in body["quotes"]:
        assert row["last"] is None
        assert row["cached"] is False


def test_every_row_carries_its_asset_class_and_currency(client):
    """Derived from the ticker's own suffix -- the only asset-class fact
    available without a fundamentals call."""
    body = client.get("/api/watchlist", params={"symbol": "BTC-USD"}).json()

    by_symbol = {row["symbol"]: row for row in body["quotes"]}
    assert by_symbol["BTC-USD"]["asset"] == quotes.asset_class("BTC-USD")
    assert by_symbol["BTC-USD"]["currency"] == quotes.currency("BTC-USD")


def test_the_board_honours_its_limit(client):
    body = client.get("/api/watchlist", params={"symbol": "AAPL", "limit": 3}).json()

    assert len(body["quotes"]) <= 3


def test_the_board_lists_each_symbol_once(client):
    """`watchlist_symbols` concatenates three sources that overlap."""
    body = client.get("/api/watchlist", params={"symbol": "AAPL"}).json()

    names = [row["symbol"] for row in body["quotes"]]
    assert len(names) == len(set(names))


def test_the_board_writes_nothing(client, isolated_ledger, isolated_runs):
    before = sorted(p.name for p in isolated_runs.iterdir())

    client.get("/api/watchlist", params={"symbol": "AAPL"})

    assert not isolated_ledger.exists()
    assert sorted(p.name for p in isolated_runs.iterdir()) == before


# ---------------------------------------------------------------- the curve


@pytest.fixture
def two_holdings(monkeypatch, isolated_holdings):
    """A saved book of two positions, priced from two synthetic series."""
    frames = {
        "AAA": synthetic_bars(rows=300, seed=4),
        "BBB": synthetic_bars(rows=300, seed=5),
    }

    def fake_fetch(symbol, period="1y", interval="1d", force=False):
        key = str(symbol).strip().upper()
        if key not in frames:
            raise live.FetchError(f"no data for {key}")
        return frames[key].copy(), types.SimpleNamespace(is_fresh=True)

    monkeypatch.setattr(live, "fetch", fake_fetch)
    monkeypatch.setattr("core.ultimate.scan", lambda symbols, **kwargs: {})

    holdings.save([
        holdings.Holding(symbol="AAA", quantity=10, unit_cost=100.0),
        holdings.Holding(symbol="BBB", quantity=5, unit_cost=100.0),
    ])
    return frames


def test_the_book_has_a_value_over_time(client, two_holdings):
    body = client.get("/api/portfolio").json()
    curve = body["curve"]

    assert curve is not None
    assert len(curve["dates"]) == len(curve["value"]) == curve["bars"]
    assert all(v > 0 for v in curve["value"])
    assert curve["cost_basis"] == body["summary"]["cost_basis"]


def test_the_curve_is_the_module_s_own_arithmetic(client, two_holdings):
    """Computed here from `holdings.history` directly and compared."""
    saved = holdings.load()
    expected = holdings.history(saved, {s: f.copy() for s, f in two_holdings.items()})

    curve = client.get("/api/portfolio").json()["curve"]

    assert curve["bars"] == len(expected)
    assert curve["value"][-1] == pytest.approx(float(expected.sum(axis=1).iloc[-1]))


def test_the_curve_names_the_holding_that_limits_it(client, monkeypatch,
                                                    isolated_holdings):
    """One recent listing can shrink the common window to almost nothing, and
    the curve is defined only where every holding traded. Which one did that is
    the useful half of the caption."""
    long = synthetic_bars(rows=300, seed=6)
    short = synthetic_bars(rows=40, seed=7)
    short["date"] = pd.date_range(long["date"].iloc[-40], periods=40, freq="D")
    frames = {"LONG": long, "SHORT": short}

    monkeypatch.setattr(live, "fetch", lambda symbol, period="1y", interval="1d",
                        force=False: (frames[str(symbol).upper()].copy(),
                                      types.SimpleNamespace(is_fresh=True)))
    monkeypatch.setattr("core.ultimate.scan", lambda symbols, **kwargs: {})

    holdings.save([
        holdings.Holding(symbol="LONG", quantity=1, unit_cost=100.0),
        holdings.Holding(symbol="SHORT", quantity=1, unit_cost=100.0),
    ])

    curve = client.get("/api/portfolio").json()["curve"]

    assert curve["limited_by"] == "SHORT"
    assert curve["bars"] <= 40


def test_the_curve_says_it_assumes_today_s_quantities(client, two_holdings):
    """It is a what-if on the current book, not a record of what was held --
    and nothing in the line itself says so."""
    curve = client.get("/api/portfolio").json()["curve"]

    assert curve["assumes_today_s_quantities"] is True


def test_an_empty_book_loads_and_has_no_curve(client, isolated_holdings,
                                              monkeypatch):
    """Regression, and not for the curve.

    `Valuation.table()` built `pd.DataFrame([])`, which has no columns, and
    then sorted it by "Value" -- so an empty book raised KeyError and
    `GET /api/portfolio` was a 500 for anyone who had not recorded a trade
    yet. Found while adding the curve; the first request a new user makes is
    exactly this one.
    """
    monkeypatch.setattr("core.ultimate.scan", lambda symbols, **kwargs: {})
    holdings.save([])

    response = client.get("/api/portfolio")

    assert response.status_code == 200, "an empty book must not be a crash"
    body = response.json()
    assert body["positions"] == []
    assert body["curve"] is None
    assert body["summary"]["market_value"] == 0


def test_an_empty_book_still_has_the_shape_of_a_holdings_table():
    """The columns survive having no rows, so a page can render its headers."""
    empty = holdings.value([], {}).table()

    assert list(empty.columns) == ["Symbol", "Units", "Unit cost", "Cost basis",
                                   "Last", "Value", "P&L", "P&L %", "Weight %"]
    assert empty.empty


def test_holdings_that_never_overlap_produce_no_curve(client, monkeypatch,
                                                      isolated_holdings):
    """`history` returns an empty frame rather than silently plotting a stub."""
    early = synthetic_bars(rows=50, seed=8)
    late = synthetic_bars(rows=50, seed=9)
    late["date"] = pd.date_range("2030-01-01", periods=50, freq="D")
    frames = {"EARLY": early, "LATE": late}

    monkeypatch.setattr(live, "fetch", lambda symbol, period="1y", interval="1d",
                        force=False: (frames[str(symbol).upper()].copy(),
                                      types.SimpleNamespace(is_fresh=True)))
    monkeypatch.setattr("core.ultimate.scan", lambda symbols, **kwargs: {})

    holdings.save([
        holdings.Holding(symbol="EARLY", quantity=1, unit_cost=100.0),
        holdings.Holding(symbol="LATE", quantity=1, unit_cost=100.0),
    ])

    assert client.get("/api/portfolio").json()["curve"] is None


def test_the_curve_costs_no_extra_download(client, monkeypatch, two_holdings):
    """`holdings.history` takes the frames the endpoint already fetched. One
    fetch per holding, not two."""
    calls: list[str] = []
    original = live.fetch

    def counting(symbol, period="1y", interval="1d", force=False):
        calls.append(str(symbol).upper())
        return original(symbol, period=period, interval=interval)

    monkeypatch.setattr(live, "fetch", counting)

    client.get("/api/portfolio")

    assert sorted(calls) == ["AAA", "BBB"], f"refetched: {calls}"
