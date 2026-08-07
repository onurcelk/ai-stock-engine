"""Loading arbitrary price CSVs into one shape.

`normalise` is the widest-blast-radius function in the app: every tab, the
backtester, every agent and the live cache all read what it returns. The
bundled CSVs come in four different layouts, so most of these tests are about
the shapes it has to absorb.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from core import data


def test_every_bundled_dataset_loads():
    """All four layouts in dataset/ must survive the normaliser."""
    names = data.list_datasets()
    assert len(names) >= 17

    for name in names:
        frame = data.load(name)
        assert not frame.empty, name
        assert list(frame.columns[:2]) == ["date", "close"], name
        assert frame["date"].is_monotonic_increasing, name
        assert frame["close"].notna().all(), name


def test_goog_year_is_listed_first():
    """Every notebook in the repo defaults to it, so the UI should too."""
    assert data.list_datasets()[0] == "GOOG-year"


@pytest.mark.parametrize("date_name", ["Date", "datetime", "TIMESTAMP", "time"])
def test_date_column_aliases(date_name):
    raw = pd.DataFrame({date_name: ["2024-01-02", "2024-01-03"], "Close": [1.0, 2.0]})
    assert len(data.normalise(raw)) == 2


@pytest.mark.parametrize("close_name", ["Close", "Price", "Adj Close", "value"])
def test_close_column_aliases(close_name):
    raw = pd.DataFrame({"Date": ["2024-01-02", "2024-01-03"], close_name: [1.0, 2.0]})
    frame = data.normalise(raw)
    assert frame["close"].tolist() == [1.0, 2.0]


def test_headerless_two_column_file_falls_back_to_position():
    """The FX files have a title string and 'unnamed: 1' as their header."""
    raw = pd.DataFrame({"some title": ["2024-01-02", "2024-01-03"],
                        "unnamed: 1": ["1.5", "1.6"]})
    frame = data.normalise(raw)
    assert frame["close"].tolist() == [1.5, 1.6]


def test_currency_and_thousands_separators_are_stripped():
    raw = pd.DataFrame({"date": ["2024-01-02", "2024-01-03"],
                        "close": ["$1,234.50", "$1,240.00"]})
    assert data.normalise(raw)["close"].tolist() == [1234.50, 1240.00]


def test_rows_are_sorted_and_unparseable_ones_dropped():
    raw = pd.DataFrame({
        "date": ["2024-01-03", "not a date", "2024-01-02"],
        "close": [2.0, 3.0, 1.0],
    })
    frame = data.normalise(raw)
    assert frame["close"].tolist() == [1.0, 2.0]
    assert frame["date"].is_monotonic_increasing


def test_optional_ohlcv_carried_through_when_present(synthetic_ohlcv):
    frame = data.normalise(synthetic_ohlcv)
    for column in ("open", "high", "low", "volume"):
        assert column in frame.columns


def test_timezone_aware_dates_are_made_naive():
    """Intraday bars arrive tz-aware; storing them would break the CSV cache."""
    raw = pd.DataFrame({
        "datetime": pd.to_datetime(["2024-01-02 09:30", "2024-01-02 10:30"],
                                   utc=True).tz_convert("America/New_York"),
        "close": [1.0, 2.0],
    })
    frame = data.normalise(raw)
    assert frame["date"].dt.tz is None


def test_single_column_is_rejected():
    with pytest.raises(ValueError, match="at least two columns"):
        data.normalise(pd.DataFrame({"close": [1.0, 2.0]}))


def test_all_unparseable_is_rejected():
    raw = pd.DataFrame({"date": ["nope", "also nope"], "close": ["x", "y"]})
    with pytest.raises(ValueError, match="no rows survived"):
        data.normalise(raw)


def test_load_upload_reads_a_file_handle():
    handle = io.BytesIO(b"Date,Close\n2024-01-02,1.0\n2024-01-03,2.0\n")
    assert len(data.load_upload(handle)) == 2


def test_missing_dataset_raises():
    with pytest.raises(FileNotFoundError):
        data.load("not-a-real-dataset")


# --------------------------------------------------------------- annualisation


@pytest.mark.parametrize("freq, periods, expected, tolerance", [
    ("B", 500, 252, 12),      # weekday bars -> trading days
    ("D", 500, 365, 12),      # calendar bars -> crypto/FX
    ("W", 200, 52, 3),
])
def test_periods_per_year_is_measured_not_assumed(freq, periods, expected, tolerance):
    """Sharpe and volatility are wrong if this is wrong."""
    dates = pd.Series(pd.date_range("2020-01-01", periods=periods, freq=freq))
    assert abs(data.periods_per_year(dates) - expected) <= tolerance


def test_periods_per_year_handles_degenerate_input():
    assert data.periods_per_year(pd.Series(pd.to_datetime(["2024-01-01"]))) == 252
    same = pd.Series(pd.to_datetime(["2024-01-01"] * 5))
    assert data.periods_per_year(same) == 252


def test_describe_reports_the_overview_numbers(bundled):
    stats = data.describe(bundled)
    assert stats["rows"] == len(bundled)
    assert stats["high"] >= stats["last"] >= stats["low"]
    expected_change = (stats["last"] - stats["first"]) / stats["first"] * 100
    assert stats["change_pct"] == pytest.approx(expected_change)
    assert stats["volatility_pct"] > 0
