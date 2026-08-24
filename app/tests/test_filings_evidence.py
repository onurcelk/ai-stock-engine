"""SUE as frame columns, and the drift source that reads them.

The point-in-time question is the whole test. `_pead_drift` is arithmetic on
two columns and could hardly be wrong; what *can* be wrong is when those
columns are allowed to know something. A restatement accepted in March must
not reach back into January, and a bar must not read a filing accepted after
its own close — both are checked directly rather than argued.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core import filings_evidence, indicators


def frame_with(sue, age, rows: int | None = None) -> pd.DataFrame:
    rows = rows if rows is not None else len(np.atleast_1d(sue))
    return pd.DataFrame({
        "date": pd.bdate_range("2024-01-02", periods=rows),
        "close": np.linspace(100.0, 110.0, rows),
        "sue": sue,
        "days_since_filing": age,
    })


# ------------------------------------------------------------- the source


def test_drift_takes_the_sign_of_the_surprise():
    beat = indicators.SOURCES["pead"].read(frame_with(2.0, 5.0, rows=30))
    miss = indicators.SOURCES["pead"].read(frame_with(-2.0, 5.0, rows=30))
    assert beat.iloc[-1] > 0
    assert miss.iloc[-1] < 0


def test_drift_decays_to_nothing_across_the_window():
    """A surprise is a claim about the weeks after it, not a standing opinion."""
    fresh = indicators.SOURCES["pead"].read(frame_with(2.0, 1.0, rows=30)).iloc[-1]
    middle = indicators.SOURCES["pead"].read(frame_with(2.0, 30.0, rows=30)).iloc[-1]
    stale = indicators.SOURCES["pead"].read(frame_with(2.0, 90.0, rows=30)).iloc[-1]

    assert fresh > middle > 0
    assert stale == 0.0, "a year-old surprise must not still be voting"


def test_drift_refuses_a_filing_from_the_future():
    """A negative age is a leak wearing a column name. Silence, not trust."""
    reading = indicators.SOURCES["pead"].read(frame_with(2.0, -3.0, rows=30))
    assert (reading == 0.0).all()


def test_drift_is_silent_without_the_columns():
    plain = frame_with(2.0, 5.0, rows=30).drop(columns=["sue", "days_since_filing"])
    assert (indicators.SOURCES["pead"].read(plain) == 0.0).all()


def test_drift_is_silent_when_the_surprise_is_undefined():
    """NaN means absent. It must not become a zero-sized opinion or a crash."""
    reading = indicators.SOURCES["pead"].read(frame_with(np.nan, 5.0, rows=30))
    assert (reading == 0.0).all()


# --------------------------------------------------------------- the columns


class FakeEvents:
    """A SUE step function with two acceptances, built by hand."""

    def __init__(self):
        self.valid_from = np.array(["2024-02-01T09:00", "2024-05-01T09:00"],
                                   dtype="datetime64[ns]")
        self.sue = np.array([1.5, -2.5])
        self.period_end = self.valid_from.copy()
        self.accepted = self.valid_from.copy()


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(filings_evidence, "available", lambda: True)
    monkeypatch.setattr(filings_evidence, "_events", lambda symbol: FakeEvents())


def test_a_bar_reads_only_acceptances_before_its_own_close(patched):
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-15", "2024-02-01", "2024-03-15",
                                "2024-05-01", "2024-06-03"]),
        "close": 100.0,
    })
    out = filings_evidence.attach(frame, "TEST")

    # Before the first acceptance there is nothing to know.
    assert np.isnan(out["sue"].iloc[0])
    # Accepted 09:00, read at that day's 16:00 close: knowable.
    assert out["sue"].iloc[1] == pytest.approx(1.5)
    assert out["sue"].iloc[2] == pytest.approx(1.5)
    # The second acceptance supersedes it, from its own day onward and not before.
    assert out["sue"].iloc[3] == pytest.approx(-2.5)
    assert out["sue"].iloc[4] == pytest.approx(-2.5)


def test_truncating_the_frame_cannot_change_an_earlier_bar(patched):
    """The leak-detector property, at the level of this door.

    Bar t's columns must be identical whether or not the frame continues past
    it -- including across the later acceptance, which is the one place a
    naive implementation would let March reach into February.
    """
    frame = pd.DataFrame({
        "date": pd.bdate_range("2024-01-02", periods=150),
        "close": 100.0,
    })
    full = filings_evidence.attach(frame, "TEST")

    for position in (10, 25, 60, 88, 149):
        truncated = filings_evidence.attach(frame.iloc[: position + 1], "TEST")
        here, there = full["sue"].iloc[position], truncated["sue"].iloc[-1]
        assert (np.isnan(here) and np.isnan(there)) or here == pytest.approx(there)

        age_here = full["days_since_filing"].iloc[position]
        age_there = truncated["days_since_filing"].iloc[-1]
        assert ((np.isnan(age_here) and np.isnan(age_there))
                or age_here == pytest.approx(age_there))


def test_the_columns_match_the_replays_own_as_of(patched):
    """`attach` vectorises `FirmEvents.as_of`. It must agree with it exactly."""
    events = FakeEvents()
    frame = pd.DataFrame({
        "date": pd.bdate_range("2024-01-02", periods=120),
        "close": 100.0,
    })
    out = filings_evidence.attach(frame, "TEST")

    for position, stamp in enumerate(frame["date"]):
        edge = dt.datetime.combine(stamp.date(), dt.time(16, 0))
        expected, _ = events_as_of(events, edge)
        got = out["sue"].iloc[position]
        assert (np.isnan(expected) and np.isnan(got)) or got == pytest.approx(expected)


def events_as_of(events, edge):
    position = np.searchsorted(events.valid_from, np.datetime64(edge)) - 1
    if position < 0:
        return float("nan"), None
    return float(events.sue[position]), pd.Timestamp(events.accepted[position])


def test_a_frame_without_the_cache_comes_back_untouched(monkeypatch):
    """No cache is "we could not look", which is not "we looked and found none".

    A column of NaN would be the second claim. Returning the frame unchanged
    is the first, and the ledger's input fingerprint then records which of the
    two actually happened.
    """
    monkeypatch.setattr(filings_evidence, "available", lambda: False)
    frame = pd.DataFrame({"date": pd.bdate_range("2024-01-02", periods=10),
                          "close": 100.0})
    out = filings_evidence.attach(frame, "AAPL")
    assert "sue" not in out.columns
    assert out is frame


def test_an_unknown_symbol_leaves_the_frame_alone():
    frame = pd.DataFrame({"date": pd.bdate_range("2024-01-02", periods=10),
                          "close": 100.0})
    assert "sue" not in filings_evidence.attach(frame, "NOTATICKER").columns
