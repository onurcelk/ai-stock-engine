"""Multi-symbol baskets.

`align` carries the design decision worth guarding: holdings are joined on an
inner index, so a basket is only defined where every member actually traded.
Forward-filling would invent prices that never existed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import portfolio


@pytest.fixture
def frames():
    """Two symbols with deliberately different histories."""
    long_dates = pd.bdate_range("2020-01-01", periods=300)
    short_dates = long_dates[100:]  # listed later
    return {
        "AAA": pd.DataFrame({"date": long_dates,
                             "close": np.linspace(100.0, 200.0, len(long_dates))}),
        "BBB": pd.DataFrame({"date": short_dates,
                             "close": np.linspace(50.0, 60.0, len(short_dates))}),
    }


def test_align_is_an_inner_join(frames):
    prices = portfolio.align(frames)
    assert list(prices.columns) == ["AAA", "BBB"]
    # Limited by the most recently listed holding, not the longest history.
    assert len(prices) == len(frames["BBB"])
    assert not prices.isna().any().any()
    assert prices.index.is_monotonic_increasing


def test_align_of_nothing_is_empty():
    assert portfolio.align({}).empty


@pytest.mark.parametrize("weights, expected", [
    ({"A": 50, "B": 50}, {"A": 50.0, "B": 50.0}),
    ({"A": 1, "B": 3}, {"A": 25.0, "B": 75.0}),
    ({"A": 0, "B": 0}, {"A": 50.0, "B": 50.0}),      # degenerate -> equal split
    ({"A": -10, "B": 10}, {"A": 0.0, "B": 100.0}),   # negatives clamped
])
def test_normalise_weights(weights, expected):
    assert portfolio.normalise_weights(weights) == pytest.approx(expected)


def test_weights_always_total_one_hundred(frames):
    normalised = portfolio.normalise_weights({"AAA": 3, "BBB": 7})
    assert sum(normalised.values()) == pytest.approx(100.0)


def test_build_starts_at_the_initial_capital(frames):
    prices = portfolio.align(frames)
    book = portfolio.build(prices, {"AAA": 50, "BBB": 50}, initial_money=10_000)

    assert book.equity.iloc[0] == pytest.approx(10_000)
    assert len(book.equity) == len(prices)
    assert book.rebalanced == 0


def test_rising_basket_gains(frames):
    prices = portfolio.align(frames)
    book = portfolio.build(prices, {"AAA": 50, "BBB": 50}, initial_money=10_000)
    assert book.equity.iloc[-1] > book.equity.iloc[0]


def test_rebalancing_is_recorded_and_changes_the_path(frames):
    prices = portfolio.align(frames)
    held = portfolio.build(prices, {"AAA": 50, "BBB": 50}, rebalance_every=0)
    rebalanced = portfolio.build(prices, {"AAA": 50, "BBB": 50}, rebalance_every=20)

    assert rebalanced.rebalanced > 0
    assert not np.allclose(held.equity.to_numpy(), rebalanced.equity.to_numpy())


def test_drift_shows_up_in_final_weights(frames):
    """AAA doubles while BBB barely moves, so AAA must end overweight."""
    prices = portfolio.align(frames)
    book = portfolio.build(prices, {"AAA": 50, "BBB": 50}, rebalance_every=0)
    assert book.final_weights["AAA"] > book.weights["AAA"]
    assert sum(book.final_weights.values()) == pytest.approx(100.0, abs=0.01)


def test_correlations_use_returns_not_prices(frames):
    """Price correlation mostly measures shared trend, which is misleading."""
    prices = portfolio.align(frames)
    matrix = portfolio.correlations(prices)
    assert list(matrix.columns) == ["AAA", "BBB"]
    assert matrix.loc["AAA", "AAA"] == pytest.approx(1.0)
    assert (matrix.to_numpy() <= 1.0 + 1e-9).all()
    assert (matrix.to_numpy() >= -1.0 - 1e-9).all()


def test_per_symbol_stats_covers_every_holding(frames):
    prices = portfolio.align(frames)
    stats = portfolio.per_symbol_stats(prices, bars_per_year=252)
    assert len(stats) == len(prices.columns)


def test_fetch_many_reports_failures_without_raising(monkeypatch):
    """One bad symbol must not take the whole basket down."""
    from core import live

    good = pd.DataFrame({"date": pd.bdate_range("2024-01-01", periods=10),
                         "close": np.arange(10.0) + 100})

    def fake_fetch(symbol, period="5y", interval="1d", force=False):
        if symbol == "BAD":
            raise live.UnknownSymbol("no such symbol")
        return good, None

    monkeypatch.setattr(live, "fetch", fake_fetch)
    frames, errors = portfolio.fetch_many(["AAA", "BAD", "aaa"], period="1y",
                                          interval="1d")
    assert set(frames) == {"AAA"}      # duplicate ignored, case-normalised
    assert set(errors) == {"BAD"}
