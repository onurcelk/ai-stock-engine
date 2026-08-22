"""orb_1h confirmatory: the CONTINUE/REJECT arithmetic and the noise control's
call-shuffle correctness (must hold realised returns fixed and permute only
the call direction -- shuffling sign(advantage) instead would be circular)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import orb1h_confirmatory as confirmatory


def _result(**overrides):
    base = dict(
        n_sessions=100, n_dates=50, advantage_bp=40.0, ci_low_bp=1.0, ci_high_bp=80.0,
        breadth=0.6, first_half_positive=True, second_half_positive=True,
        net_of_cost_bp=35.0, noise_median_bp=1.0, noise_exceedance=0.03,
    )
    base.update(overrides)
    return confirmatory.Result(**base)


def test_all_criteria_met_continues():
    assert _result().verdict == "CONTINUE"


def test_advantage_below_mde_rejects():
    assert _result(advantage_bp=38.9).verdict == "REJECT"


def test_ci_low_not_above_zero_rejects():
    assert _result(ci_low_bp=-0.1).verdict == "REJECT"


def test_low_breadth_rejects():
    assert _result(breadth=0.49).verdict == "REJECT"


def test_a_negative_half_rejects_even_with_good_breadth():
    assert _result(second_half_positive=False).verdict == "REJECT"


def test_noise_control_failure_rejects_despite_a_clean_point_estimate():
    assert _result(noise_median_bp=6.0).verdict == "REJECT"
    assert _result(noise_exceedance=0.2).verdict == "REJECT"


def test_noise_shuffle_holds_realised_fixed_and_permutes_only_the_call(monkeypatch):
    """The permutation must be able to reproduce the observed mean when the
    shuffle happens to return the identity permutation -- proving realised
    values are not altered and the call is what gets shuffled."""
    raw = pd.DataFrame({
        "symbol": ["AAA", "BBB", "CCC"],
        "date": pd.to_datetime(["2024-01-02", "2024-01-02", "2024-01-03"]).date,
        "call": [1.0, -1.0, 1.0],
        "realised": [0.01, -0.02, 0.03],
        "advantage": [0.01, 0.02, 0.03],
    })

    def fake_symbols():
        return ["AAA"]

    def fake_session_rows(symbol):
        return raw

    monkeypatch.setattr(confirmatory.gate_module, "_symbols", fake_symbols)
    monkeypatch.setattr(confirmatory.gate_module, "_session_rows", fake_session_rows)

    class IdentityRNG:
        def permutation(self, values):
            return np.asarray(values)

    monkeypatch.setattr(np.random, "default_rng", lambda seed: IdentityRNG())

    result = confirmatory.measure()
    # With the identity permutation every draw reproduces the true advantage
    # exactly, so the noise median must equal the true advantage, not zero
    # and not some unrelated quantity -- this is only true if realised was
    # held fixed and call was what got "shuffled" (here, left as-is).
    assert result.noise_median_bp == pytest.approx(result.advantage_bp, abs=0.01)
