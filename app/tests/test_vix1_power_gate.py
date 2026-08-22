"""VIX1 power gate: the realised-vol arithmetic and pass/fail boundary.
Not a test of any predictive claim -- VIX1_PREREGISTRATION.md SS5 is explicit
that this gate touches variance only."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import vix1_power_gate as gate_module


def test_realised_vol_of_a_flat_series_is_zero():
    assert gate_module._realised_vol(np.zeros(10)) == 0.0


def test_realised_vol_scales_with_dispersion():
    low = gate_module._realised_vol(np.array([0.001, -0.001, 0.001, -0.001, 0.001]))
    high = gate_module._realised_vol(np.array([0.05, -0.05, 0.05, -0.05, 0.05]))
    assert high > low


def test_realised_vol_of_too_few_points_is_nan():
    assert np.isnan(gate_module._realised_vol(np.array([0.01])))


def test_gate_result_pass_fail_boundary():
    passing = gate_module.GateResult(window=5, n_flags=100, n_cutoffs=50,
                                      block=4, half_width_points=2.9)
    failing = gate_module.GateResult(window=5, n_flags=100, n_cutoffs=50,
                                      block=4, half_width_points=3.1)
    unresolved = gate_module.GateResult(window=5, n_flags=0, n_cutoffs=0,
                                         block=0, half_width_points=float("nan"))
    assert passing.passes is True
    assert failing.passes is False
    assert unresolved.passes is False


def test_too_few_cutoffs_reports_no_half_width(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(gate_module, "_flag_rows", lambda window: pd.DataFrame({
        "symbol": ["AAA"], "cutoff": [pd.Timestamp("2020-01-01")], "advantage": [1.0],
    }))

    results = gate_module.gate(min_cutoffs=20)
    for result in results:
        assert not result.passes
        assert np.isnan(result.half_width_points)
