"""Direct position editing, re-authorised by owner decision 2026-08-23.

It was retired at the Phase 7 cutover, and what was wrong with it is worth
stating precisely, because the reversal keeps that part: `holdings.editable`
and `from_frame` rewrote the book with **nothing anywhere recording that
anything had changed**. The book and the ledger could then disagree, and
neither of them said which was wrong.

So the property these tests pin is not "the book can be edited" -- it is that
every edit leaves a row explaining it. Two operations, and the difference
between them and their trade-shaped neighbours is the whole design:

  adjust   sets a position outright. NOT a buy: a buy re-averages the basis
           over what was already held, so correcting a mistyped quantity with
           one turns a single error into two.
  discard  drops a row without selling it. NOT a close: a close books a
           realised figure and claims the position was sold at a price, which
           is a statement about what happened. This one realises nothing, so
           it can neither flatter nor damage the realised total.
"""

from __future__ import annotations

from core import holdings


# ------------------------------------------------------- every edit is recorded


def test_adding_a_position_writes_a_ledger_row(client):
    """The property the retirement existed to protect, kept through the reversal."""
    before = len(client.get("/api/portfolio").json()["ledger"])

    response = client.post("/api/portfolio/position", json={
        "symbol": "AAPL", "quantity": 12, "unit_cost": 41.3,
        "note": "transferred in from the old broker"})

    assert response.status_code == 200
    assert response.json()["side"] == holdings.ADJUST

    body = client.get("/api/portfolio").json()
    assert len(body["ledger"]) == before + 1
    row = next(r for r in body["positions"] if r["Symbol"] == "AAPL")
    assert row["Units"] == 12
    assert row["Unit cost"] == 41.3


def test_discarding_a_position_writes_a_ledger_row(client):
    client.post("/api/portfolio/position",
                json={"symbol": "AAPL", "quantity": 12, "unit_cost": 41.3})

    response = client.delete("/api/portfolio/position/AAPL")

    assert response.status_code == 200
    transaction = response.json()
    assert transaction["side"] == holdings.DISCARD
    # The units and basis that were dropped, so the row is enough on its own
    # to put the position back by hand.
    assert transaction["quantity"] == 12
    assert transaction["price"] == 41.3

    body = client.get("/api/portfolio").json()
    assert all(r["Symbol"] != "AAPL" for r in body["positions"])


# --------------------------------------- an adjustment is not a trade


def test_adjusting_replaces_the_basis_rather_than_re_averaging_it(client):
    """The reason this is not just a buy.

    A buy would average 10@100 with 12@41.30 and leave a basis that is neither
    number. Correcting a mistyped quantity has to mean what it says.
    """
    client.post("/api/portfolio/trade", json={
        "side": "buy", "symbol": "AAPL", "quantity": 10, "price": 100.0})

    client.post("/api/portfolio/position",
                json={"symbol": "AAPL", "quantity": 12, "unit_cost": 41.3})

    row = next(r for r in client.get("/api/portfolio").json()["positions"]
               if r["Symbol"] == "AAPL")
    assert row["Units"] == 12
    assert row["Unit cost"] == 41.3


def test_neither_operation_realises_anything(client):
    """No money moved, so the realised total may not move either.

    A discard that booked a realised figure would let anyone tidy a losing row
    off the book and improve the record by doing it.
    """
    client.post("/api/portfolio/trade", json={
        "side": "buy", "symbol": "AAPL", "quantity": 10, "price": 100.0})
    realised_before = client.get("/api/portfolio").json()["summary"]["realised"]

    client.post("/api/portfolio/position",
                json={"symbol": "AAPL", "quantity": 12, "unit_cost": 41.3})
    client.delete("/api/portfolio/position/AAPL")

    after = client.get("/api/portfolio").json()["summary"]
    assert after["realised"] == realised_before


def test_the_ledger_row_is_not_disguised_as_a_trade(client):
    """`adjust`/`discard`, never `buy`/`sell`.

    A reader of the ledger has to be able to tell a fill from a correction.
    Recording an adjustment as a buy would put a purchase that never happened
    into the one record that is supposed to explain the book.
    """
    client.post("/api/portfolio/position",
                json={"symbol": "AAPL", "quantity": 12, "unit_cost": 41.3})
    client.delete("/api/portfolio/position/AAPL")

    sides = [row["Side"] for row in client.get("/api/portfolio").json()["ledger"]]
    assert "ADJUST" in sides and "DISCARD" in sides
    assert "BUY" not in sides and "SELL" not in sides


def test_an_adjustment_moves_no_cash(client):
    transaction = holdings.Transaction(
        at=__import__("datetime").datetime.now(), side=holdings.ADJUST,
        symbol="AAPL", quantity=12, price=41.3)

    assert transaction.cash == 0.0


# ------------------------------------------------------------- refusals


def test_a_position_needs_positive_numbers(client):
    for payload in ({"symbol": "AAPL", "quantity": 0, "unit_cost": 41.3},
                    {"symbol": "AAPL", "quantity": 12, "unit_cost": 0},
                    {"symbol": "", "quantity": 12, "unit_cost": 41.3}):
        assert client.post("/api/portfolio/position", json=payload).status_code in (400, 422)


def test_discarding_something_not_held_is_refused(client):
    """Silently succeeding would hide that the caller and the book disagree."""
    response = client.delete("/api/portfolio/position/NOSUCH")

    assert response.status_code == 400
    assert "NOSUCH" in response.json()["detail"]
