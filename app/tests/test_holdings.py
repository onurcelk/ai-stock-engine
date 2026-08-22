"""Positions, and the arithmetic of changing them.

The valuation half of this module was already exercised through the portfolio
tab; the trading half is new and is the only code in the app that writes a
number someone might reconcile against a broker statement. Average-cost basis,
commission in the basis on a buy and out of the realised on a sell, and a
refusal to go short.

The last test in this file is the one that matters most: every path resolves
its store at call time, because binding it at import time is what let a
headless run write a position into the real holdings file.
"""

from __future__ import annotations

import json
import threading

import pandas as pd
import pytest

from core import holdings


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Redirect both files into a scratch directory for the whole test."""
    book = tmp_path / "holdings.json"
    ledger = tmp_path / "transactions.json"
    monkeypatch.setattr(holdings, "STORE", book)
    monkeypatch.setattr(holdings, "LEDGER", ledger)
    return book, ledger


# ------------------------------------------------------------------- buying


def test_a_buy_opens_a_position():
    book, transaction = holdings.buy([], "aapl", 10, 100.0)
    assert len(book) == 1
    assert book[0].symbol == "AAPL"          # normalised on the way in
    assert book[0].quantity == 10
    assert book[0].unit_cost == pytest.approx(100.0)
    assert transaction.side == holdings.BUY
    assert transaction.cash == pytest.approx(-1_000.0)


def test_commission_lands_in_the_cost_basis():
    """P&L should mean what a statement means: what you clear, not what price did."""
    book, _ = holdings.buy([], "AAPL", 10, 100.0, fee=5.0)
    assert book[0].unit_cost == pytest.approx(100.5)
    assert book[0].cost_basis == pytest.approx(1_005.0)


def test_a_second_buy_re_averages():
    book, _ = holdings.buy([], "AAPL", 10, 100.0)
    book, _ = holdings.buy(book, "AAPL", 30, 200.0)
    assert book[0].quantity == 40
    assert book[0].unit_cost == pytest.approx(175.0)


def test_buying_leaves_the_original_book_alone():
    """The UI holds the old list across a rerun; mutating it in place would
    double-count the trade the moment Streamlit replays the script."""
    original = [holdings.Holding("AAPL", 10, 100.0)]
    holdings.buy(original, "AAPL", 10, 200.0)
    assert original[0].quantity == 10
    assert original[0].unit_cost == 100.0


# ------------------------------------------------------------------ selling


def test_a_partial_sell_books_the_difference_and_keeps_the_basis():
    book, _ = holdings.buy([], "AAPL", 10, 100.0)
    book, transaction = holdings.sell(book, "AAPL", 4, 150.0)
    assert book[0].quantity == 6
    assert book[0].unit_cost == pytest.approx(100.0)   # average cost, unchanged
    assert transaction.realised == pytest.approx(200.0)
    assert transaction.cash == pytest.approx(600.0)


def test_commission_comes_out_of_the_realised():
    book, _ = holdings.buy([], "AAPL", 10, 100.0)
    _, transaction = holdings.sell(book, "AAPL", 10, 110.0, fee=7.5)
    assert transaction.realised == pytest.approx(92.5)


def test_selling_everything_removes_the_position():
    book, _ = holdings.buy([], "AAPL", 2.5, 40.0)
    book, _ = holdings.sell(book, "AAPL", 2.5, 50.0)
    assert book == []


def test_selling_more_than_held_is_refused():
    """Quietly turning a typo into a short is the worst way to find out."""
    book, _ = holdings.buy([], "AAPL", 5, 100.0)
    with pytest.raises(ValueError, match="does not go short"):
        holdings.sell(book, "AAPL", 6, 100.0)


def test_selling_something_unheld_is_refused():
    with pytest.raises(ValueError, match="do not hold"):
        holdings.sell([], "AAPL", 1, 100.0)


def test_a_loss_is_booked_as_a_loss():
    book, _ = holdings.buy([], "AAPL", 10, 100.0)
    _, transaction = holdings.sell(book, "AAPL", 10, 80.0)
    assert transaction.realised == pytest.approx(-200.0)


# ---------------------------------------------------------------- validation


@pytest.mark.parametrize("kwargs,message", [
    (dict(symbol="", quantity=1, price=10.0), "Enter a symbol"),
    (dict(symbol="AAPL", quantity=0, price=10.0), "greater than zero"),
    (dict(symbol="AAPL", quantity=-3, price=10.0), "greater than zero"),
    (dict(symbol="AAPL", quantity=1, price=0.0), "Price has to be"),
    (dict(symbol="AAPL", quantity=1, price=10.0, fee=-1), "cannot be negative"),
])
def test_bad_tickets_are_refused_before_anything_is_written(kwargs, message):
    with pytest.raises(ValueError, match=message):
        holdings.buy([], **kwargs)


def test_fractional_shares_are_allowed():
    book, _ = holdings.buy([], "BTC-USD", 0.00042, 90_000.0)
    assert book[0].quantity == pytest.approx(0.00042)


# -------------------------------------------------------------------- ledger


def test_a_trade_persists_to_both_files(store):
    book_path, ledger_path = store
    holdings.execute(holdings.BUY, "AAPL", 10, 100.0, fee=2.0)

    assert [h.symbol for h in holdings.load()] == ["AAPL"]
    ledger = holdings.load_ledger()
    assert len(ledger) == 1 and ledger[0].side == holdings.BUY
    assert json.loads(book_path.read_text(encoding="utf-8"))["holdings"]
    assert json.loads(ledger_path.read_text(encoding="utf-8"))["transactions"]


def test_a_refused_trade_writes_nothing(store):
    holdings.execute(holdings.BUY, "AAPL", 5, 100.0)
    with pytest.raises(ValueError):
        holdings.execute(holdings.SELL, "AAPL", 50, 100.0)

    assert holdings.load()[0].quantity == 5
    assert len(holdings.load_ledger()) == 1


def test_realised_and_fees_total_across_the_ledger(store):
    holdings.execute(holdings.BUY, "AAPL", 10, 100.0, fee=1.0)
    holdings.execute(holdings.SELL, "AAPL", 5, 120.0, fee=2.0)
    holdings.execute(holdings.SELL, "AAPL", 5, 90.0, fee=2.0)

    ledger = holdings.load_ledger()
    # Basis is 100.1 after the buy-side commission.
    assert holdings.realised_total(ledger) == pytest.approx(
        5 * (120 - 100.1) - 2 + 5 * (90 - 100.1) - 2)
    assert holdings.fees_total(ledger) == pytest.approx(5.0)


def test_the_ledger_survives_a_corrupt_file(store):
    _, ledger_path = store
    ledger_path.write_text("{not json", encoding="utf-8")
    assert holdings.load_ledger() == []


def test_a_malformed_row_does_not_lose_the_rest(store):
    _, ledger_path = store
    ledger_path.write_text(json.dumps({"transactions": [
        {"at": "2026-01-01T10:00:00", "side": "buy", "symbol": "AAPL",
         "quantity": 1, "price": 10.0},
        {"side": "buy"},                                  # missing everything
    ]}), encoding="utf-8")
    assert [t.symbol for t in holdings.load_ledger()] == ["AAPL"]


def test_the_ledger_reads_back_oldest_first(store):
    holdings.execute(holdings.BUY, "AAPL", 1, 100.0)
    holdings.execute(holdings.BUY, "MSFT", 1, 200.0)
    assert [t.symbol for t in holdings.load_ledger()] == ["AAPL", "MSFT"]


def test_the_ledger_table_shows_newest_first_and_hides_buy_realised(store):
    holdings.execute(holdings.BUY, "AAPL", 10, 100.0)
    holdings.execute(holdings.SELL, "AAPL", 10, 110.0)
    table = holdings.ledger_table(holdings.load_ledger())
    assert list(table["Side"]) == ["SELL", "BUY"]
    assert pd.isna(table.loc[1, "Realised"])


def test_an_empty_ledger_still_has_columns():
    assert list(holdings.ledger_table([]).columns)[:3] == ["When", "Side", "Symbol"]


# ----------------------------------------------------- the trade confirmation


@pytest.mark.parametrize("price,shown", [
    (100.0, "100"),              # nothing after the point worth printing
    (4.5, "4.5"),
    (211.3049, "211.3049"),
    (1_000.0, "1,000"),          # the thousands separator survives the trim
    (0.00001, "0.00001"),        # sub-cent: four places would round this to 0
    (0.000004231, "0.00000423"),
])
def test_a_confirmation_quotes_the_price_it_filled_at(price, shown):
    _, transaction = holdings.buy([], "SHIB-USD", 1_000, price)
    assert transaction.describe().endswith(f"@ {shown}")


def test_a_sub_cent_fill_is_not_confirmed_as_free():
    """The bug this exists for: `@ 0` on a trade that had a price.

    Four fixed places make "0.0000" of a sub-cent fill, and trimming the
    trailing zeros off that leaves a confirmation quoting zero. The trim also
    used to bind to the whole assembled sentence rather than the number.
    """
    _, transaction = holdings.buy([], "SHIB-USD", 1_000_000, 0.00001)
    confirmation = transaction.describe()
    assert not confirmation.endswith("@ 0")
    assert confirmation == "BUY 1e+06 SHIB-USD @ 0.00001"


def test_execute_rejects_an_unknown_side(store):
    with pytest.raises(ValueError, match="Unknown side"):
        holdings.execute("short", "AAPL", 1, 100.0)


# ------------------------------------------------------------ the store path


def test_every_path_resolves_the_store_at_call_time(tmp_path, monkeypatch):
    """The guard against a test run writing into someone's real portfolio.

    Defaulting these to `STORE` in the signature binds the value at import,
    so monkeypatching the module attribute had no effect and a headless run
    of the portfolio tab wrote a live position to disk. This is that bug.
    """
    redirected = tmp_path / "elsewhere.json"
    monkeypatch.setattr(holdings, "STORE", redirected)
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "elsewhere-ledger.json")

    holdings.execute(holdings.BUY, "AAPL", 1, 100.0)

    assert redirected.exists()
    assert holdings.load()[0].symbol == "AAPL"
    assert not (tmp_path.parent / "holdings.json").exists()


def test_position_lookup_is_case_and_space_insensitive():
    book = [holdings.Holding("AAPL", 1, 100.0)]
    assert holdings.position(book, " aapl ") is not None


# ---------------------------------------------------------- concurrency


def test_concurrent_buys_do_not_clobber_each_other(store):
    """The race `execute()` used to be exposed to: N threads each buying 1
    unit must leave the book at N, not at 1 (the last writer winning) or
    anywhere else a lost update could land. Guards against a regression of
    the `_EXECUTE_LOCK` fix -- without it, this test is flaky-to-failing
    under load, which is exactly the bug it exists to catch.
    """
    threads = [
        threading.Thread(target=holdings.execute,
                          args=(holdings.BUY, "AAPL", 1, 100.0))
        for _ in range(20)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    book = holdings.load()
    assert len(book) == 1
    assert book[0].quantity == pytest.approx(20)
    assert len(holdings.load_ledger()) == 20
    assert holdings.position(book, "MSFT") is None
