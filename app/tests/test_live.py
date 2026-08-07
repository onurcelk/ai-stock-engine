"""The live-data layer and its disk cache.

Nothing here touches the network. `temp_cache` redirects `live.CACHE_DIR` into
tmp_path and `offline` makes any download attempt raise, which is what makes the
cache's behaviour observable: the interesting question is not "can it download"
but "what does it serve when it cannot".
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from core import live


def write_cache(frame: pd.DataFrame, symbol="AAPL", interval="1d"):
    live._write_cache(symbol, interval, frame)


def make_stale(symbol="AAPL", interval="1d", days=2):
    """Backdate a cache entry so fetch() stops treating it as fresh."""
    _csv, meta_path = live._paths(symbol, interval)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["fetched_at"] = (
        dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def daily_frame():
    dates = pd.bdate_range("2020-01-01", periods=400)
    return pd.DataFrame({
        "date": dates,
        "close": [100.0 + i * 0.1 for i in range(len(dates))],
        "volume": [1_000.0] * len(dates),
    })


# ---------------------------------------------------------------- filenames


@pytest.mark.parametrize("symbol, stem", [
    ("AAPL", "AAPL"),
    ("BRK.B", "BRK.B"),          # dots are legal in filenames
    ("EURUSD=X", "EURUSD_X"),    # '=' is not
    ("BTC-USD", "BTC-USD"),
    ("brk.b", "BRK.B"),          # case-normalised
])
def test_symbols_map_to_safe_filenames(symbol, stem):
    assert live._safe(symbol) == stem


# -------------------------------------------------------------- cache round-trip


def test_cache_round_trip(temp_cache, daily_frame):
    write_cache(daily_frame)
    found = live.read_cache("AAPL", "1d")

    assert found is not None
    frame, entry = found
    assert len(frame) == len(daily_frame)
    assert entry.symbol == "AAPL"
    assert entry.interval == "1d"
    assert entry.is_fresh  # just written
    assert entry.rows == len(daily_frame)


def test_missing_cache_returns_none(temp_cache):
    assert live.read_cache("NOSUCH", "1d") is None


def test_corrupt_cache_returns_none_rather_than_exploding(temp_cache, daily_frame):
    """A half-written or hand-edited cache file must not break the app."""
    write_cache(daily_frame)
    csv_path, _meta = live._paths("AAPL", "1d")
    csv_path.write_text("this is not a csv", encoding="utf-8")
    assert live.read_cache("AAPL", "1d") is None


def test_cache_entry_age_description(temp_cache, daily_frame):
    write_cache(daily_frame)
    _frame, entry = live.read_cache("AAPL", "1d")
    entry.fetched_at = dt.datetime.now() - dt.timedelta(minutes=30)
    assert entry.describe_age().endswith("min ago")
    entry.fetched_at = dt.datetime.now() - dt.timedelta(hours=5)
    assert entry.describe_age().endswith("h ago")
    entry.fetched_at = dt.datetime.now() - dt.timedelta(days=3)
    assert entry.describe_age().endswith("d ago")
    assert not entry.is_fresh


# ------------------------------------------------------------------ trimming


def test_slice_to_period_trims_a_wider_cache(daily_frame):
    """The bug this exists to prevent: a '1y' request served from a 'max' cache.

    The cache deliberately keeps the widest range ever downloaded, so without
    this every tab would quietly get decades when it asked for one year.
    """
    trimmed = live.slice_to_period(daily_frame, "1mo")
    assert len(trimmed) < len(daily_frame)
    span = (trimmed["date"].iloc[-1] - trimmed["date"].iloc[0]).days
    assert span <= 31
    # The most recent bar is always kept.
    assert trimmed["date"].iloc[-1] == daily_frame["date"].iloc[-1]


def test_slice_to_period_max_is_a_no_op(daily_frame):
    assert len(live.slice_to_period(daily_frame, "max")) == len(daily_frame)


def test_slice_to_period_never_returns_empty(daily_frame):
    """A window shorter than the gap between bars must not wipe the frame."""
    two_rows = daily_frame.head(2)
    assert len(live.slice_to_period(two_rows, "5d")) >= 1


# --------------------------------------------------------------- interval rules


def test_intraday_periods_are_constrained():
    """Yahoo refuses intraday requests older than 730 days."""
    assert live.periods_for("1h") == live.INTRADAY_PERIODS
    assert live.periods_for("1d") == live.DAILY_PERIODS
    assert "10y" not in live.periods_for("4h")
    assert "10y" in live.periods_for("1d")


def test_default_period_matches_interval():
    assert live.default_period("1h") in live.INTRADAY_PERIODS
    assert live.default_period("1d") in live.DAILY_PERIODS


def test_every_interval_has_a_fallback_bar_count():
    for interval in live.INTERVALS.values():
        assert interval in live.PERIODS_PER_YEAR


# ------------------------------------------------------------- error taxonomy


def test_offline_falls_back_to_cache(temp_cache, offline, daily_frame):
    """A network failure with a usable cached copy must not raise."""
    write_cache(daily_frame)
    make_stale()  # so fetch() actually attempts a download

    frame, entry = live.fetch("AAPL", period="1y", interval="1d")
    assert len(frame) > 0
    assert offline, "the download should have been attempted"


def test_offline_without_cache_raises(temp_cache, offline):
    with pytest.raises(live.FetchError):
        live.fetch("NOSUCH", period="1y", interval="1d")


def test_request_errors_are_never_served_from_cache(temp_cache, monkeypatch,
                                                    daily_frame):
    """A bad symbol or impossible range must not be answered with stale data.

    Returning yesterday's daily bars when someone asked for five years of
    hourly ones answers a different question than the one asked.
    """
    write_cache(daily_frame)
    make_stale()

    def bad_symbol(symbol, period, interval):
        raise live.UnknownSymbol("no such thing")

    monkeypatch.setattr(live, "_download", bad_symbol)
    with pytest.raises(live.UnknownSymbol):
        live.fetch("AAPL", period="1y", interval="1d")


def test_error_hierarchy_lets_the_ui_distinguish_them():
    assert issubclass(live.RequestError, live.FetchError)
    assert issubclass(live.UnknownSymbol, live.RequestError)
    assert issubclass(live.InvalidRange, live.RequestError)


def test_empty_symbol_is_rejected(temp_cache):
    with pytest.raises(live.FetchError, match="Enter a ticker"):
        live.fetch("   ")


# ------------------------------------------------------------------ inventory


def test_cache_entries_lists_what_is_stored(temp_cache, daily_frame):
    write_cache(daily_frame, "AAPL", "1d")
    write_cache(daily_frame, "MSFT", "1d")
    entries = live.cache_entries()
    assert {e.symbol for e in entries} == {"AAPL", "MSFT"}


def test_clear_cache_removes_files(temp_cache, daily_frame):
    write_cache(daily_frame, "AAPL", "1d")
    write_cache(daily_frame, "MSFT", "1d")

    assert live.clear_cache("AAPL", "1d") == 2  # csv + meta
    assert live.read_cache("AAPL", "1d") is None
    assert live.read_cache("MSFT", "1d") is not None

    live.clear_cache()
    assert live.cache_entries() == []
