"""The options premium screen: what it says, and what it must never say.

The arithmetic here is a division and would be dull to guard on its own. What
is worth guarding is the boundary around it, because this is the one surface
in the desk whose data *cannot* be replayed:

**The warning is part of the payload.** `reports/OPTIONS1_ADMISSIBILITY.md` §3
established that no free source serves options data point-in-time, so a yield
column with no caveat is read as a backtested return and can never be made
into one. If a refactor drops the string, these tests fail.

**Nothing writes.** A premium screen is not a prospective forecast and must
not be recordable as one -- the forecast ledger is append-only and never
regenerable, and its value rests on every row being replayable against real
subsequent prices, which an expired option's quote can never be.

The network is never touched: `core.options` takes its ticker by injection and
every test below drives it with a hand-built chain.
"""

from __future__ import annotations

import datetime as dt
import pathlib

import pandas as pd
import pytest

from core import options


class FakeTicker:
    """Two expiries of quotes, shaped the way yfinance shapes them."""

    def __init__(self, spot: float = 100.0, expiries=("2026-09-18",
                                                      "2026-10-16")):
        self._spot = spot
        self.options = tuple(expiries)
        self.fast_info = {"last_price": spot}

    def option_chain(self, expiry: str):
        calls = pd.DataFrame({
            "contractSymbol": ["C95", "C105"],
            "strike": [95.0, 105.0],
            "bid": [7.0, 1.0], "ask": [7.4, 1.2], "lastPrice": [7.2, 1.1],
            "impliedVolatility": [0.31, 0.28],
            "openInterest": [1200, 40], "volume": [300, 5],
        })
        puts = pd.DataFrame({
            "contractSymbol": ["P95", "P90", "P80"],
            "strike": [95.0, 90.0, 80.0],
            "bid": [2.0, 1.0, 0.0], "ask": [2.2, 1.1, 0.05],
            "lastPrice": [2.1, 1.05, 0.02],
            "impliedVolatility": [0.33, 0.36, 0.44],
            "openInterest": [800, 150, 3], "volume": [90, 12, 0],
        })
        return type("Quoted", (), {"calls": calls, "puts": puts})()


@pytest.fixture
def fake():
    return FakeTicker()


@pytest.fixture
def quoted(fake):
    return options.chain("TEST", ticker=fake)


# ------------------------------------------------------------------ the chain


def test_the_nearest_expiry_is_the_default(quoted):
    assert quoted.expiry == dt.date(2026, 9, 18)
    assert quoted.spot == 100.0


def test_an_unlisted_expiry_is_refused_by_name(fake):
    """Silently substituting the nearest one would price a different trade."""
    with pytest.raises(options.FetchError, match="no 2027-01-15 expiry"):
        options.chain("TEST", "2027-01-15", ticker=fake)


def test_a_symbol_with_no_options_is_not_a_crash():
    with pytest.raises(options.UnknownSymbol, match="no listed options"):
        options.chain("TEST", ticker=FakeTicker(expiries=()))


# ----------------------------------------------------------------- the screen


def _screen(quoted, **kwargs):
    """The screen with the OTM default off unless a test asks for it.

    Most tests below check arithmetic on a named strike, and half those strikes
    are in the money. Turning the product default off here keeps those tests
    about the arithmetic; the default itself gets its own tests at the end.
    """
    today = kwargs.pop("today", dt.date(2026, 8, 24))
    kwargs.setdefault("out_of_the_money_only", False)
    return options.premium_screen(quoted, today=today, **kwargs)


def test_the_put_screen_prices_collateral_at_the_strike(quoted):
    """A cash-secured put ties up the strike, not the spot."""
    table = _screen(quoted, kind=options.CASH_SECURED_PUT)
    row = table[table["strike"] == 95.0].iloc[0]

    assert row["premium"] == pytest.approx(2.1)          # mid of 2.0 / 2.2
    assert row["static_yield"] == pytest.approx(2.1 / 95.0)


def test_the_call_screen_prices_collateral_at_the_shares(quoted):
    table = _screen(quoted, kind=options.COVERED_CALL)
    row = table[table["strike"] == 105.0].iloc[0]

    assert row["premium"] == pytest.approx(1.1)
    assert row["static_yield"] == pytest.approx(1.1 / 100.0)


def test_annualising_uses_the_days_actually_left(quoted):
    table = _screen(quoted, today=dt.date(2026, 8, 24))
    days = (dt.date(2026, 9, 18) - dt.date(2026, 8, 24)).days
    row = table.iloc[0]
    assert row["days_to_expiry"] == days
    assert row["static_yield_annualised"] == pytest.approx(
        row["static_yield"] / (days / 365.0))


def test_expiry_day_does_not_annualise_to_infinity(quoted):
    """Zero days left is a division by zero wearing a yield's name."""
    table = _screen(quoted, today=dt.date(2026, 9, 18))
    assert table["days_to_expiry"].eq(0).all()
    assert table["static_yield_annualised"].notna().all()
    assert (table["static_yield_annualised"] < 1e6).all()


def test_a_strike_with_no_bid_is_flagged_rather_than_priced_as_live(quoted):
    """`lastPrice` on an untraded strike can be days old. Say so."""
    table = _screen(quoted, kind=options.CASH_SECURED_PUT)
    dead = table[table["strike"] == 80.0]
    assert len(dead) == 1
    assert bool(dead.iloc[0]["is_stale"]) is True

    live_row = table[table["strike"] == 95.0].iloc[0]
    assert bool(live_row["is_stale"]) is False


def test_open_interest_filters_without_reordering(quoted):
    table = _screen(quoted, kind=options.CASH_SECURED_PUT,
                    min_open_interest=100)
    assert set(table["strike"]) == {95.0, 90.0}
    assert table["static_yield_annualised"].is_monotonic_decreasing


def test_cushion_points_away_from_assignment_on_both_sides(quoted):
    """Out-of-the-money is positive cushion whichever side you sold."""
    puts = _screen(quoted, kind=options.CASH_SECURED_PUT)
    calls = _screen(quoted, kind=options.COVERED_CALL)

    # Spot 100: the 90 put and the 105 call are both out of the money.
    assert puts[puts["strike"] == 90.0].iloc[0]["cushion"] > 0
    assert calls[calls["strike"] == 105.0].iloc[0]["cushion"] > 0
    # ... and the 95 call is in the money, so it has none.
    assert calls[calls["strike"] == 95.0].iloc[0]["cushion"] < 0


def test_an_unknown_screen_is_refused(quoted):
    with pytest.raises(ValueError, match="unknown screen"):
        _screen(quoted, kind="naked_straddle")


# ------------------------------------------------------- the caveat and the API


def test_the_payload_cannot_be_built_without_the_warning(quoted):
    payload = options.screen_payload(
        quoted, _screen(quoted), options.CASH_SECURED_PUT)
    assert payload["WARNING"] == options.WARNING
    assert payload["backtestable"] is False
    assert "backtest" in payload["WARNING"].lower()


def test_no_column_claims_to_be_a_realised_return(quoted):
    """The screen ranks quotes. A return column would say it ranks strategies."""
    columns = set(_screen(quoted).columns)
    forbidden = {"return", "realised_return", "pnl", "hit_rate", "win_rate",
                 "expected_return", "sharpe", "drawdown", "probability"}
    assert not (columns & forbidden), columns & forbidden
    # Anything yield-shaped has to carry the assumption in its own name.
    assert all(name.startswith("static_")
               for name in columns if "yield" in name)


def test_the_kinds_endpoint_states_what_it_cannot_do(client):
    body = client.get("/api/options/kinds").json()
    assert body["backtestable"] is False
    assert body["WARNING"] == options.WARNING
    assert {k["key"] for k in body["kinds"]} == {
        options.CASH_SECURED_PUT, options.COVERED_CALL}


def test_naked_and_spread_structures_are_not_offered(client):
    """Both need a margin model, and a margin model needs history that is gone."""
    keys = {k["key"] for k in client.get("/api/options/kinds").json()["kinds"]}
    assert not any("naked" in key or "spread" in key for key in keys)


def test_an_unknown_kind_is_a_400_naming_the_ones_that_exist(client):
    response = client.get("/api/options/AAPL/screen", params={"kind": "nope"})
    assert response.status_code == 400
    assert options.CASH_SECURED_PUT in response.json()["detail"]


def test_the_router_reaches_no_writing_module():
    """A GET that wrote is the exact defect Phase 6a existed to remove."""
    source = (pathlib.Path(__file__).resolve().parents[1]
              / "routers" / "options.py").read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]          # past the module docstring
    for forbidden in ("holdings", "ledger_activation", "forecast_ledger",
                      "runs.save"):
        assert forbidden not in body, f"options router reaches {forbidden}"


def test_the_router_declares_no_write_methods():
    from ..routers import options as router_module

    methods = set()
    for route in router_module.router.routes:
        methods |= set(getattr(route, "methods", ()))
    assert methods <= {"GET", "HEAD", "OPTIONS"}, methods


# ------------------------------------------------ the out-of-the-money default


def test_in_the_money_strikes_are_dropped_by_default(quoted):
    """Ranking purely by yield puts the worst trade on the board at the top.

    An in-the-money put quotes a huge premium *because* it is nearly certain to
    be assigned, and on expiry day that annualises into the thousands of
    percent. It is real arithmetic and a useless answer: selling it is a
    synthetic long, not premium harvesting.
    """
    table = options.premium_screen(quoted, kind=options.COVERED_CALL,
                                   today=dt.date(2026, 8, 24))
    # Spot 100, so the 95 call is in the money and must not be here.
    assert set(table["strike"]) == {105.0}
    assert (table["cushion"] > 0).all()


def test_the_default_can_be_turned_off_and_hides_nothing(quoted):
    """A visible switch, not a silent filter."""
    table = options.premium_screen(quoted, kind=options.COVERED_CALL,
                                   out_of_the_money_only=False,
                                   today=dt.date(2026, 8, 24))
    assert set(table["strike"]) == {95.0, 105.0}
    # And the row that was hidden says for itself which side of the money it is
    # on, so the reader never depends on the filter to find out.
    assert table[table["strike"] == 95.0].iloc[0]["cushion"] < 0


def test_the_payload_says_which_way_the_switch_was_set(quoted):
    """A table whose filter is invisible is a table you cannot interpret."""
    table = options.premium_screen(quoted, today=dt.date(2026, 8, 24))
    payload = options.screen_payload(quoted, table, options.CASH_SECURED_PUT)
    assert payload["out_of_the_money_only"] is True

    payload = options.screen_payload(
        quoted, table, options.CASH_SECURED_PUT, out_of_the_money_only=False)
    assert payload["out_of_the_money_only"] is False
