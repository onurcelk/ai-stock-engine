"""Drift-based Monte Carlo.

The UI offers a "Reproducible" checkbox, so the seeding contract is the thing
worth pinning down: same seed, same fan; no seed, a different one.
"""

from __future__ import annotations

import numpy as np
import pytest

from core import montecarlo


def test_same_seed_reproduces_the_same_paths(bundled_close):
    first = montecarlo.run(bundled_close, days=30, simulations=50, seed=42)
    second = montecarlo.run(bundled_close, days=30, simulations=50, seed=42)
    assert np.array_equal(first.paths.to_numpy(), second.paths.to_numpy())


def test_different_seeds_diverge(bundled_close):
    first = montecarlo.run(bundled_close, days=30, simulations=50, seed=1)
    second = montecarlo.run(bundled_close, days=30, simulations=50, seed=2)
    assert not np.array_equal(first.paths.to_numpy(), second.paths.to_numpy())


def test_shape_and_starting_point(bundled_close):
    days, simulations = 30, 50
    result = montecarlo.run(bundled_close, days=days, simulations=simulations, seed=0)

    # One extra row: every path starts at the last observed price.
    assert result.paths.shape == (days + 1, simulations)
    assert result.last_price == pytest.approx(float(bundled_close.iloc[-1]))
    assert np.allclose(result.paths.iloc[0].to_numpy(), result.last_price)
    assert len(result.endings) == simulations


def test_prices_stay_positive(bundled_close):
    """It is a geometric walk, so no path may cross zero."""
    result = montecarlo.run(bundled_close, days=252, simulations=200, seed=7)
    assert (result.paths.to_numpy() > 0).all()


def test_summary_percentiles_are_ordered(bundled_close):
    summary = montecarlo.run(bundled_close, days=60, simulations=500, seed=3).summary()
    assert summary["p5"] <= summary["median"] <= summary["p95"]
    assert 0.0 <= summary["prob_up"] <= 100.0


def test_spread_widens_with_horizon(bundled_close):
    """The fan should spread with the square root of time, not stay flat."""
    short = montecarlo.run(bundled_close, days=10, simulations=400, seed=5)
    long = montecarlo.run(bundled_close, days=200, simulations=400, seed=5)
    assert long.endings.std() > short.endings.std()
