"""PEAD-1 confirmatory: the four-criterion CONTINUE/REJECT arithmetic,
including the market-relative control unique to this study."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import pead1_confirmatory as confirmatory


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


def test_recovering_firm_return_from_signed_advantage_is_exact():
    """advantage = firm_return * sign, and sign in {-1, +1}, so
    advantage * sign recovers firm_return exactly -- the identity the noise
    control's un-signing step in pead1_confirmatory.measure relies on."""
    for sign in (1.0, -1.0):
        firm_return = 0.0234
        advantage = firm_return * sign
        assert advantage * sign == pytest.approx(firm_return)
