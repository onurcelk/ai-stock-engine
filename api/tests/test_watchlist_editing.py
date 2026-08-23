"""The board became editable: what that must and must not change.

`core.quotes` derives a board -- the symbol on screen, the cache, the quick
picks -- and that stays the default. What is new is a curated list that
overrides it once somebody edits one, and the whole point of the pair is that
the two states are distinguishable:

* a board nobody has touched still shows the picks, so a fresh clone is useful;
* a board somebody **emptied** stays empty, instead of refilling itself from
  the cache on the next read and reading as a button that did not work.

Everything else the endpoint already guaranteed still holds through the
mutations: they re-price through the same cache-only read, so none of them
downloads either.
"""

from __future__ import annotations

from core import live, quotes, watchlist


def _symbols(body: dict) -> list[str]:
    return [row["symbol"] for row in body["quotes"]]


# ------------------------------------------------------------ the two modes


def test_an_untouched_board_is_the_derived_default(client):
    body = client.get("/api/watchlist", params={"symbol": "AAPL"}).json()

    assert body["mode"] == "auto"
    assert body["saved"] == []
    assert _symbols(body) == quotes.watchlist_symbols("AAPL", "1d", 14)
    assert not any(row["saved"] for row in body["quotes"])


def test_adding_a_symbol_makes_the_board_custom_and_keeps_the_rest(client):
    """The first add seeds from what was on screen, rather than replacing it.

    An add that dropped the other twelve rows would be indistinguishable from
    a bug, and would make the first click the most destructive one.
    """
    before = _symbols(client.get("/api/watchlist", params={"symbol": "AAPL"}).json())

    body = client.post("/api/watchlist", params={"symbol": "AAPL"},
                       json={"symbol": "TSLA"}).json()

    assert body["mode"] == "custom"
    assert "TSLA" in body["saved"]
    assert set(before) <= set(body["saved"]) | {"AAPL"}


def test_adding_the_same_symbol_twice_is_not_an_error_or_a_duplicate(client):
    client.post("/api/watchlist", json={"symbol": "TSLA"})
    body = client.post("/api/watchlist", json={"symbol": "tsla"}).json()

    assert body["saved"].count("TSLA") == 1


def test_a_blank_symbol_is_refused(client):
    assert client.post("/api/watchlist", json={"symbol": "  "}).status_code == 400


def test_removing_works_on_a_derived_board_too(client):
    """Materialise-then-remove, or the row is back on the next read."""
    client.get("/api/watchlist", params={"symbol": "AAPL"})

    body = client.delete("/api/watchlist/AAPL", params={"symbol": "NVDA"}).json()

    assert body["mode"] == "custom"
    assert "AAPL" not in body["saved"]

    again = client.get("/api/watchlist", params={"symbol": "NVDA"}).json()
    assert "AAPL" not in again["saved"]


def test_an_emptied_board_stays_empty(client):
    """The distinction the two modes exist for.

    `clear` keeps the board custom, so the next read does not hand it back the
    cache and the quick picks.
    """
    client.post("/api/watchlist/clear", params={"symbol": "AAPL"})

    body = client.get("/api/watchlist", params={"symbol": "AAPL"}).json()

    assert body["mode"] == "custom"
    assert body["saved"] == []
    # The symbol on screen still shows: it is what the page is about, and it
    # is the row the add button acts on.
    assert _symbols(body) == ["AAPL"]


def test_reset_hands_the_board_back_to_the_default(client):
    client.post("/api/watchlist", json={"symbol": "TSLA"})

    body = client.post("/api/watchlist/reset", params={"symbol": "AAPL"}).json()

    assert body["mode"] == "auto"
    assert _symbols(body) == quotes.watchlist_symbols("AAPL", "1d", 14)


def test_the_symbol_on_screen_leads_a_custom_board(client):
    client.post("/api/watchlist", json={"symbol": "TSLA"})

    body = client.get("/api/watchlist", params={"symbol": "NVDA"}).json()

    assert _symbols(body)[0] == "NVDA"


def test_rows_say_whether_they_are_on_the_saved_list(client):
    client.post("/api/watchlist/clear")
    body = client.post("/api/watchlist", params={"symbol": "NVDA"},
                       json={"symbol": "TSLA"}).json()

    flags = {row["symbol"]: row["saved"] for row in body["quotes"]}
    assert flags["TSLA"] is True
    assert flags["NVDA"] is False


# ----------------------------------------------- what must not have changed


def test_no_mutation_downloads(client, monkeypatch):
    """Every write re-prices through `quotes.board`, which is cache-only."""
    def forbidden(*args, **kwargs):
        raise AssertionError("a watchlist write called live.fetch")

    monkeypatch.setattr(live, "fetch", forbidden)

    assert client.post("/api/watchlist", json={"symbol": "TSLA"}).status_code == 200
    assert client.delete("/api/watchlist/TSLA").status_code == 200
    assert client.post("/api/watchlist/clear").status_code == 200
    assert client.post("/api/watchlist/reset").status_code == 200


def test_reading_the_board_still_writes_nothing(client, isolated_watchlist):
    client.get("/api/watchlist", params={"symbol": "AAPL"})

    assert not isolated_watchlist.exists()


# ------------------------------------------------------------- the store


def test_a_corrupt_store_falls_back_to_the_default(tmp_path):
    """Showing the default is recoverable; showing nothing looks broken."""
    path = tmp_path / "watchlist.json"
    path.write_text("{not json", encoding="utf-8")

    assert watchlist.saved(path) is None


def test_none_and_empty_are_different_answers(tmp_path):
    path = tmp_path / "watchlist.json"

    assert watchlist.saved(path) is None
    watchlist.clear(path)
    assert watchlist.saved(path) == []


def test_the_store_caps_the_board(tmp_path):
    path = tmp_path / "watchlist.json"
    watchlist.save([f"SYM{i}" for i in range(watchlist.MAX_SYMBOLS + 10)], path)

    assert len(watchlist.saved(path)) == watchlist.MAX_SYMBOLS
