"""POST /api/portfolio/trade and /api/portfolio/ledger/clear.

Hermetic: every test redirects `holdings.STORE`/`LEDGER` via the
`isolated_holdings`/`client` fixtures in `conftest.py`, so none of this
touches app/holdings.json or app/transactions.json. None of these tests
touch the network either -- unlike GET /api/portfolio, the trade endpoints
never call `live.fetch` or `ultimate.scan`.
"""

from __future__ import annotations

import threading

from core import holdings


def test_a_buy_opens_a_position(client):
    response = client.post("/api/portfolio/trade", json={
        "side": "buy", "symbol": "aapl", "quantity": 10, "price": 100.0,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["side"] == "buy"
    assert body["symbol"] == "AAPL"

    book = holdings.load()
    assert len(book) == 1
    assert book[0].symbol == "AAPL"
    assert book[0].quantity == 10


def test_a_trade_appears_in_the_ledger(client):
    client.post("/api/portfolio/trade", json={
        "side": "buy", "symbol": "AAPL", "quantity": 10, "price": 100.0,
    })
    assert len(holdings.load_ledger()) == 1


def test_selling_more_than_held_is_rejected(client):
    client.post("/api/portfolio/trade", json={
        "side": "buy", "symbol": "AAPL", "quantity": 10, "price": 100.0,
    })
    response = client.post("/api/portfolio/trade", json={
        "side": "sell", "symbol": "AAPL", "quantity": 999, "price": 100.0,
    })
    assert response.status_code == 400
    assert "does not go short" in response.json()["detail"]
    # The refused trade must not have touched the book.
    assert holdings.load()[0].quantity == 10


def test_a_zero_quantity_is_rejected_by_validation(client):
    response = client.post("/api/portfolio/trade", json={
        "side": "buy", "symbol": "AAPL", "quantity": 0, "price": 100.0,
    })
    assert response.status_code == 422
    assert holdings.load() == []


def test_an_unknown_side_is_rejected_by_validation(client):
    response = client.post("/api/portfolio/trade", json={
        "side": "short", "symbol": "AAPL", "quantity": 1, "price": 100.0,
    })
    assert response.status_code == 422


def test_clear_ledger_empties_it_but_not_the_holdings(client):
    client.post("/api/portfolio/trade", json={
        "side": "buy", "symbol": "AAPL", "quantity": 10, "price": 100.0,
    })
    response = client.post("/api/portfolio/ledger/clear")
    assert response.status_code == 200
    assert response.json() == {"cleared": True}
    assert holdings.load_ledger() == []
    assert len(holdings.load()) == 1          # positions are untouched


def test_concurrent_trades_through_the_api_do_not_clobber_each_other(client):
    """The end-to-end version of `test_concurrent_buys_do_not_clobber_each_other`
    in app/tests/test_holdings.py -- through the actual HTTP layer this phase
    added, not just the underlying function.
    """
    def buy_one():
        client.post("/api/portfolio/trade", json={
            "side": "buy", "symbol": "AAPL", "quantity": 1, "price": 100.0,
        })

    threads = [threading.Thread(target=buy_one) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    book = holdings.load()
    assert len(book) == 1
    assert book[0].quantity == 20
    assert len(holdings.load_ledger()) == 20
