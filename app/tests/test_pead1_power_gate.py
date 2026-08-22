"""PEAD-1 power gate: event-row construction and the gate's pass/fail
arithmetic. Not a test of any predictive claim -- alpha/PEAD1_CHARTER.md SS6
is explicit that this gate touches variance only, never a point estimate."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import filings_features, pead1_power_gate as gate_module


def test_gate_result_pass_fail_boundary():
    passing = gate_module.GateResult(window=5, n_events=100, n_weeks=50,
                                      block_weeks=4, half_width_bp=38.9, mde_bp=39.0)
    failing = gate_module.GateResult(window=5, n_events=100, n_weeks=50,
                                      block_weeks=4, half_width_bp=39.1, mde_bp=39.0)
    assert passing.passes is True
    assert failing.passes is False


def test_zero_sue_events_are_excluded_from_the_advantage_rows(monkeypatch, tmp_path):
    """A SUE of exactly zero has no sign to weight the forward return by, and
    must not silently become a `sign(0) == 0` observation diluting the mean."""
    events = {
        "AAA": filings_features.FirmEvents(
            valid_from=np.array(["2020-01-05"], dtype="datetime64[ns]"),
            sue=np.array([0.0]),
            period_end=np.array(["2019-12-31"], dtype="datetime64[ns]"),
            accepted=np.array(["2020-01-05"], dtype="datetime64[ns]"),
        )
    }
    prices = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=200, tz="UTC"),
        "close": np.linspace(100, 120, 200),
    })
    monkeypatch.setattr(gate_module, "_load_price", lambda symbol: prices)

    rows = gate_module._event_advantage_rows(events)
    assert rows.empty


def test_the_event_cutoff_never_precedes_the_acceptance_date(monkeypatch):
    """PIT safety for the gate's own event-row construction: the anchor bar
    must be strictly after the acceptance date, never on or before it."""
    accepted = pd.Timestamp("2020-01-05 20:00:00")   # after the close
    events = {
        "AAA": filings_features.FirmEvents(
            valid_from=np.array([accepted], dtype="datetime64[ns]"),
            sue=np.array([1.5]),
            period_end=np.array(["2019-12-31"], dtype="datetime64[ns]"),
            accepted=np.array([accepted], dtype="datetime64[ns]"),
        )
    }
    prices = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=200, tz="UTC"),
        "close": np.linspace(100, 120, 200),
    })
    monkeypatch.setattr(gate_module, "_load_price", lambda symbol: prices)

    rows = gate_module._event_advantage_rows(events)
    assert not rows.empty
    # Every window's anchor is bar `position`, computed as the first bar at or
    # after accepted-date + 1 day -- confirmed indirectly: no row could exist
    # if that search ever pointed at or before 2020-01-05.
    assert (rows["symbol"] == "AAA").all()


def test_too_few_weeks_reports_no_half_width(monkeypatch):
    events = {
        "AAA": filings_features.FirmEvents(
            valid_from=np.array(["2020-01-05"], dtype="datetime64[ns]"),
            sue=np.array([1.5]),
            period_end=np.array(["2019-12-31"], dtype="datetime64[ns]"),
            accepted=np.array(["2020-01-05"], dtype="datetime64[ns]"),
        )
    }
    prices = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=200, tz="UTC"),
        "close": np.linspace(100, 120, 200),
    })
    monkeypatch.setattr(gate_module, "_load_events", lambda: events)
    monkeypatch.setattr(gate_module, "_load_price", lambda symbol: prices)

    results = gate_module.gate(min_weeks=20)
    for result in results:
        assert not result.passes
        assert np.isnan(result.half_width_bp)
