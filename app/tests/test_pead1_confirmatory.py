"""PEAD-1 confirmatory: the four-criterion CONTINUE/REJECT arithmetic,
including the market-relative control unique to this study."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from alpha import filings_features, pead1_confirmatory as confirmatory


def _result(**overrides):
    base = dict(
        n_events=1000, n_weeks=647, advantage_bp=45.0, ci_low_bp=5.0, ci_high_bp=90.0,
        breadth=0.6, first_half_positive=True, second_half_positive=True,
        market_advantage_bp=30.0, market_ci_low_bp=2.0, net_of_cost_bp=40.0,
        noise_median_bp=2.0, noise_exceedance=0.03,
    )
    base.update(overrides)
    return confirmatory.Result(**base)


def test_all_four_criteria_met_continues():
    assert _result().verdict == "CONTINUE"


def test_advantage_below_mde_rejects():
    assert _result(advantage_bp=38.9).verdict == "REJECT"


def test_ci_low_not_above_zero_rejects():
    assert _result(ci_low_bp=0.0).verdict == "REJECT"


def test_low_breadth_rejects():
    assert _result(breadth=0.5).verdict == "REJECT"


def test_a_negative_half_rejects():
    assert _result(first_half_positive=False).verdict == "REJECT"


def test_market_relative_control_failing_rejects_even_with_a_clean_raw_result():
    """A result driven entirely by SUE-sorted firms tracking the market must
    not confirm PEAD-1 -- criterion 4 exists specifically for this."""
    assert _result(market_ci_low_bp=-1.0).verdict == "REJECT"


def test_noise_control_failure_rejects():
    assert _result(noise_median_bp=15.0).verdict == "REJECT"
    assert _result(noise_exceedance=0.5).verdict == "REJECT"


def test_event_rows_handles_tz_aware_price_history(monkeypatch):
    """Regression test: `_load_price` returns tz-aware (UTC) dates, and an
    earlier draft crashed comparing a tz-aware scalar against SPY's
    (tz-stripped) numpy datetime64 array. Must run to completion and produce
    rows without raising."""
    events = {
        "AAA": filings_features.FirmEvents(
            valid_from=np.array(["2020-01-05"], dtype="datetime64[ns]"),
            sue=np.array([2.0]),
            period_end=np.array(["2019-12-31"], dtype="datetime64[ns]"),
            accepted=np.array(["2020-01-05"], dtype="datetime64[ns]"),
        )
    }
    prices = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=200, tz="UTC"),
        "close": np.linspace(100, 120, 200),
    })
    spy = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=200, tz="UTC"),
        "close": np.linspace(300, 320, 200),
    })
    monkeypatch.setattr(confirmatory.gate_module, "_load_events", lambda: events)
    monkeypatch.setattr(confirmatory.gate_module, "_load_price", lambda symbol: prices)
    monkeypatch.setattr(confirmatory, "_spy_frame", lambda: spy)

    rows = confirmatory._event_rows(window=5)
    assert not rows.empty
    assert {"symbol", "week", "sign", "advantage", "market_advantage"} <= set(rows.columns)


def test_recovering_firm_return_from_signed_advantage_is_exact():
    """advantage = firm_return * sign, and sign in {-1, +1}, so
    advantage * sign recovers firm_return exactly -- the identity the noise
    control's un-signing step in pead1_confirmatory.measure relies on."""
    for sign in (1.0, -1.0):
        firm_return = 0.0234
        advantage = firm_return * sign
        assert advantage * sign == pytest.approx(firm_return)
