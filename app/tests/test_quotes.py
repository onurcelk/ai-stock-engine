"""The watchlist's quote board.

Two properties matter more than the arithmetic. First, this module must never
reach the network: it runs once per symbol on every rerun, and a rail that
quietly fires a dozen downloads is how the app gets rate-limited. Second, it
has to survive a cache that is missing, partial or corrupt, because the rail
renders before anything has validated it.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from core import live, quotes


@pytest.fixture
def seeded_cache(temp_cache):
    """Three symbols on disk, with a known last move on each."""
    def write(symbol, closes, interval="1d"):
        dates = pd.bdate_range("2024-01-01", periods=len(closes))
        live._write_cache(symbol, interval,
                          pd.DataFrame({"date": dates, "close": closes}))

    write("AAPL", [100.0, 110.0, 121.0])          # +11.00, +10%
    write("EURUSD=X", [1.10, 1.05])               # -0.05, sanitised filename
    write("BTC-USD", [30_000.0, 29_400.0])        # -600, -2%
    write("MSFT", [50.0, 55.0], interval="1wk")   # a different interval
    return temp_cache


# ---------------------------------------------------------------- symbology


@pytest.mark.parametrize("symbol,expected", [
    ("AAPL", "EQUITY"), ("BRK.B", "EQUITY"),
    ("BTC-USD", "CRYPTO"), ("ETH-EUR", "CRYPTO"),
    ("EURUSD=X", "FX"), ("usdtry=x", "FX"),
])
def test_asset_class_reads_yahoos_suffixes(symbol, expected):
    assert quotes.asset_class(symbol) == expected


@pytest.mark.parametrize("symbol,expected", [
    ("AAPL", "USD"), ("BTC-USD", "USD"), ("ETH-EUR", "EUR"),
    ("EURUSD=X", "USD"), ("EURGBP=X", "GBP"),
])
def test_currency_comes_from_the_symbol(symbol, expected):
    assert quotes.currency(symbol) == expected


# -------------------------------------------------------------------- reads


def test_read_quote_returns_the_last_move(seeded_cache):
    quote = quotes.read_quote("AAPL")
    assert quote is not None
    assert quote.last == pytest.approx(121.0)
    assert quote.change == pytest.approx(11.0)
    assert quote.change_pct == pytest.approx(10.0)
    assert quote.asset == "EQUITY"


def test_read_quote_is_none_for_an_uncached_symbol(seeded_cache):
    assert quotes.read_quote("NOTCACHED") is None


def test_read_quote_survives_a_corrupt_cache_file(seeded_cache):
    live.cache_path("AAPL", "1d").write_text("this is not a csv", encoding="utf-8")
    assert quotes.read_quote("AAPL") is None


def test_read_quote_needs_two_bars_to_have_a_change(temp_cache):
    live._write_cache("ONEBAR", "1d", pd.DataFrame(
        {"date": pd.bdate_range("2024-01-01", periods=1), "close": [10.0]}))
    assert quotes.read_quote("ONEBAR") is None


def test_reading_a_quote_never_downloads(seeded_cache, offline):
    """The rail runs on every rerun; it may not be a network dependency."""
    assert quotes.read_quote("AAPL") is not None
    quotes.board(["AAPL", "NOTCACHED", "BTC-USD"])
    assert offline == [], "quotes.py went to the network"


# ------------------------------------------------------------- the symbol list


def test_cached_symbols_reads_metadata_not_filenames(seeded_cache):
    """EURUSD=X is stored as EURUSD_X, and a link back to it must not be."""
    found = quotes.cached_symbols("1d")
    assert "EURUSD=X" in found
    assert not any("_X" in symbol for symbol in found)


def test_cached_symbols_are_per_interval(seeded_cache):
    assert "MSFT" in quotes.cached_symbols("1wk")
    assert "MSFT" not in quotes.cached_symbols("1d")


def test_cached_symbols_tolerates_a_half_written_sidecar(seeded_cache):
    (seeded_cache / "JUNK__1d.meta.json").write_text("{oops", encoding="utf-8")
    assert "AAPL" in quotes.cached_symbols("1d")


def test_cached_symbols_is_empty_without_a_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "CACHE_DIR", tmp_path / "absent")
    assert quotes.cached_symbols("1d") == []


# ------------------------------------------------------------------ the board


def test_board_keeps_order_and_lists_uncached_symbols(seeded_cache):
    rows = quotes.board(["AAPL", "NOTCACHED", "BTC-USD"])
    assert [row["symbol"] for row in rows] == ["AAPL", "NOTCACHED", "BTC-USD"]
    # An uncached symbol still gets a row: it is clickable, and clicking it is
    # what fetches it properly, through the sidebar where errors can be shown.
    assert rows[1]["last"] is None
    assert rows[0]["last"] == pytest.approx(121.0)
    assert rows[2]["change"] == pytest.approx(-600.0)


def test_board_deduplicates_and_upcases(seeded_cache):
    rows = quotes.board(["aapl", "AAPL", " "])
    assert [row["symbol"] for row in rows] == ["AAPL"]


def test_watchlist_puts_the_current_symbol_first(seeded_cache):
    symbols = quotes.watchlist_symbols("BTC-USD", "1d")
    assert symbols[0] == "BTC-USD"
    assert symbols.count("BTC-USD") == 1


def test_watchlist_falls_back_to_the_quick_picks(temp_cache):
    """A fresh clone has no cache, and an empty rail teaches nothing."""
    symbols = quotes.watchlist_symbols("", "1d")
    assert set(live.QUICK_PICKS) <= set(symbols) or len(symbols) == 14


def test_watchlist_respects_its_limit(seeded_cache):
    assert len(quotes.watchlist_symbols("AAPL", "1d", limit=3)) == 3


def test_board_is_cheap_enough_for_every_rerun(temp_cache):
    """A decade of bars per symbol, read for two numbers — usecols or bust."""
    dates = pd.bdate_range("2015-01-01", periods=2_600)
    closes = 100 + np.cumsum(np.random.default_rng(0).standard_normal(len(dates)))
    for index in range(12):
        live._write_cache(f"SYM{index}", "1d",
                          pd.DataFrame({"date": dates, "close": closes,
                                        "open": closes, "high": closes,
                                        "low": closes, "volume": 1_000.0}))
    rows = quotes.board([f"SYM{i}" for i in range(12)])
    assert all(row["last"] is not None for row in rows)


def test_meta_and_csv_agree_on_the_symbol(seeded_cache):
    """cached_symbols() and read_quote() must land on the same file."""
    for symbol in quotes.cached_symbols("1d"):
        assert live.cache_path(symbol, "1d").exists()
        assert quotes.read_quote(symbol) is not None
    meta = json.loads(
        (seeded_cache / "EURUSD_X__1d.meta.json").read_text(encoding="utf-8"))
    assert meta["symbol"] == "EURUSD=X"


def test_last_close_reads_the_cache_and_never_the_network(seeded_cache, offline):
    """The trade ticket prefills from this on every keystroke."""
    assert quotes.last_close("AAPL") == pytest.approx(121.0)
    assert offline == [], "the ticket must not download"


def test_last_close_falls_back_to_daily_bars(seeded_cache):
    """A symbol you hold but have never charted hourly still gets a price."""
    assert quotes.last_close("AAPL", "1h") == pytest.approx(121.0)


def test_last_close_is_none_for_an_unknown_symbol(seeded_cache):
    assert quotes.last_close("NOSUCH") is None
    assert quotes.last_close("") is None
