"""The TradingView-style price chart.

The interesting logic is the rangebreaks: collapsing weekends is what makes an
equity chart look continuous, but doing it to a 24/7 series would hide real
bars. The chart decides from the data rather than from a setting, so these
tests feed it both shapes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from core import charts


@pytest.fixture
def equity_hourly():
    """Weekday bars inside a 9:30-16:00 session."""
    stamps = [
        day + pd.Timedelta(hours=h)
        for day in pd.bdate_range("2024-01-01", periods=40)
        for h in (9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5)
    ]
    dates = pd.DatetimeIndex(stamps)
    close = 100 + np.cumsum(np.random.default_rng(0).standard_normal(len(dates)))
    return pd.DataFrame({
        "date": dates, "open": close, "high": close + 1,
        "low": close - 1, "close": close, "volume": 1_000.0,
    })


# ------------------------------------------------------------- session breaks


def test_equity_daily_hides_weekends_only(synthetic_ohlcv):
    figure = charts.price_chart(synthetic_ohlcv, symbol="AAPL", interval_label="1d")
    breaks = figure.layout.xaxis.rangebreaks
    assert len(breaks) == 1
    assert list(breaks[0].bounds) == ["sat", "mon"]


@pytest.mark.parametrize("interval", ["1h", "4h"])
def test_equity_intraday_also_hides_the_overnight_session(equity_hourly, interval):
    figure = charts.price_chart(equity_hourly, symbol="AAPL", interval_label=interval)
    breaks = figure.layout.xaxis.rangebreaks
    assert len(breaks) == 2
    patterns = {b.pattern for b in breaks}
    assert "hour" in patterns


@pytest.mark.parametrize("interval", ["1d", "1h", "4h"])
def test_crypto_keeps_every_bar(crypto_ohlcv, interval):
    """A 24/7 series has real Saturday bars; collapsing them would hide data."""
    figure = charts.price_chart(crypto_ohlcv, symbol="BTC-USD", interval_label=interval)
    assert len(figure.layout.xaxis.rangebreaks) == 0


def test_weekend_detection_reads_the_data(synthetic_ohlcv, crypto_ohlcv):
    assert not charts._trades_on_weekends(synthetic_ohlcv["date"])
    assert charts._trades_on_weekends(crypto_ohlcv["date"])


# -------------------------------------------------------------------- shapes


def test_ohlc_series_draws_candles(synthetic_ohlcv):
    figure = charts.price_chart(synthetic_ohlcv, symbol="AAPL", interval_label="1d")
    assert "candlestick" in {trace.type for trace in figure.data}


@pytest.mark.parametrize("name", ["BTC-sentiment", "eur-myr", "usd-myr"])
def test_close_only_series_falls_back_to_a_line(name):
    """The FX rate files and the sentiment feed carry no OHLC columns."""
    from core import data

    frame = data.load(name)
    assert not charts.has_ohlc(frame)
    figure = charts.price_chart(frame, symbol=name, interval_label="1d")
    types = {trace.type for trace in figure.data}
    assert "scatter" in types
    assert "candlestick" not in types


def test_ohlc_detection_agrees_with_the_bundled_data(bundled):
    """GOOG-year does have OHLC, so it must draw candles, not a line."""
    assert charts.has_ohlc(bundled)


def test_volume_pane_appears_only_when_there_is_volume(synthetic_ohlcv):
    with_volume = charts.price_chart(synthetic_ohlcv, symbol="X", interval_label="1d")
    assert "bar" in {trace.type for trace in with_volume.data}

    flat = synthetic_ohlcv.copy()
    flat["volume"] = 0.0
    without = charts.price_chart(flat, symbol="X", interval_label="1d")
    assert "bar" not in {trace.type for trace in without.data}


def test_overlays_and_markers_are_drawn(synthetic_ohlcv):
    bands = pd.DataFrame({
        "upper": synthetic_ohlcv["close"].rolling(20).max(),
        "lower": synthetic_ohlcv["close"].rolling(20).min(),
    })
    figure = charts.price_chart(
        synthetic_ohlcv, symbol="AAPL", interval_label="1d",
        overlays=bands, buys=[30, 60], sells=[45],
    )
    names = {trace.name for trace in figure.data}
    assert {"upper", "lower", "Buy", "Sell"} <= names


# ---------------------------------------------------------------- range bar


def test_window_slices_from_the_latest_bar_backwards(synthetic_ohlcv):
    """Every range key is backward from the end, so the last bar always shows."""
    for key in ("1M", "3M", "6M"):
        sliced = charts.window(synthetic_ohlcv, key)
        assert sliced["date"].iloc[-1] == synthetic_ohlcv["date"].iloc[-1]
        assert len(sliced) < len(synthetic_ohlcv)


def test_window_all_is_the_whole_series(synthetic_ohlcv):
    assert len(charts.window(synthetic_ohlcv, "All")) == len(synthetic_ohlcv)


def test_window_ytd_starts_in_january(crypto_ohlcv):
    sliced = charts.window(crypto_ohlcv, "YTD")
    end = crypto_ohlcv["date"].iloc[-1]
    assert sliced["date"].iloc[0].year == end.year


def test_window_ignores_a_request_it_cannot_draw():
    """One bar is a dot, not a chart — fall back rather than render nonsense.

    Weekly bars are the case that reaches this: a one-day lookback lands
    inside the gap between two of them and catches only the last.
    """
    weekly = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=52, freq="7D"),
        "close": np.linspace(100, 150, 52),
    })
    assert len(charts.window(weekly, "1D")) == len(weekly)
    assert "1D" not in charts.usable_ranges(weekly)


def test_usable_ranges_drops_what_the_series_cannot_show(synthetic_ohlcv):
    """A year of daily bars has no intraday "1D" and no "5Y" that isn't "All"."""
    offered = charts.usable_ranges(synthetic_ohlcv)
    assert "1D" not in offered
    assert "5Y" not in offered
    assert "All" in offered
    assert offered == [key for key in charts.RANGE_KEYS if key in offered]


def test_usable_ranges_never_offers_a_second_name_for_all(synthetic_ohlcv):
    """Two buttons that draw the same chart are one button too many."""
    whole = len(synthetic_ohlcv)
    for key in charts.usable_ranges(synthetic_ohlcv):
        if key != "All":
            assert len(charts.window(synthetic_ohlcv, key)) < whole


def test_usable_ranges_keeps_everything_on_a_long_history():
    dates = pd.bdate_range("2014-01-01", periods=3_000)
    frame = pd.DataFrame({"date": dates, "close": np.linspace(10, 400, len(dates))})
    assert set(charts.usable_ranges(frame)) == set(charts.RANGE_KEYS) - {"1D"}


def test_a_windowed_frame_still_charts(synthetic_ohlcv):
    """The app charts the slice, not the full frame — that is what rescales y."""
    view = charts.window(synthetic_ohlcv, "3M")
    figure = charts.price_chart(view, symbol="AAPL", interval_label="D")
    assert "candlestick" in {trace.type for trace in figure.data}


# ------------------------------------------------------------------- palette


def test_price_chart_uses_the_dark_canvas(synthetic_ohlcv):
    figure = charts.price_chart(synthetic_ohlcv, symbol="AAPL", interval_label="1d")
    assert figure.layout.paper_bgcolor == charts.BACKGROUND
    assert figure.layout.plot_bgcolor == charts.BACKGROUND


def test_apply_dark_matches_a_plain_figure_to_the_same_palette():
    """Without this the price chart is a dark island on a light page."""
    figure = charts.apply_dark(go.Figure())
    assert figure.layout.paper_bgcolor == charts.BACKGROUND
    assert figure.layout.plot_bgcolor == charts.BACKGROUND
    assert figure.layout.font.color == charts.TEXT
    assert figure.layout.xaxis.gridcolor == charts.GRID
    assert figure.layout.yaxis.gridcolor == charts.GRID


def test_streamlit_theme_matches_the_chart_canvas(repo_root):
    """The page background must equal BACKGROUND or the chart reads as a patch."""
    config = (repo_root / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert charts.BACKGROUND.lower() in config.lower()
    assert charts.TEXT.lower() in config.lower()


def test_config_keeps_tradingview_interactions():
    assert charts.CONFIG["scrollZoom"] is True
    assert charts.CONFIG["displaylogo"] is False


def test_short_series_still_renders():
    """The UI warns below 40 rows but must not crash."""
    frame = pd.DataFrame({
        "date": pd.bdate_range("2024-01-01", periods=3),
        "close": [100.0, 101.0, 99.0],
    })
    assert charts.price_chart(frame, symbol="X", interval_label="1d") is not None
