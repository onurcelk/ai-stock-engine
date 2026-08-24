"""Drift-based Monte Carlo, ported from simulation/monte-carlo-drift.ipynb.

Each path is a geometric random walk seeded with the series' own historic
drift and volatility, which is why the fan spreads with the square root of
time rather than linearly.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd


@dataclasses.dataclass
class SimulationResult:
    paths: pd.DataFrame  # one column per simulated path
    last_price: float
    daily_volatility: float
    drift: float

    @property
    def endings(self) -> np.ndarray:
        return self.paths.iloc[-1].to_numpy()

    def summary(self) -> dict[str, float]:
        endings = self.endings
        return {
            "mean": float(endings.mean()),
            "median": float(np.median(endings)),
            "p5": float(np.percentile(endings, 5)),
            "p95": float(np.percentile(endings, 95)),
            "prob_up": float((endings > self.last_price).mean() * 100),
        }


def run(
    close: pd.Series,
    days: int = 30,
    simulations: int = 100,
    seed: int | None = None,
) -> SimulationResult:
    rng = np.random.default_rng(seed)

    returns = close.pct_change().dropna()
    daily_vol = float(returns.std())
    variance = float(returns.var())
    # GBM log-drift implied by the arithmetic mean return: half the variance is
    # subtracted exactly once, converting between the simple-return and log
    # conventions (E[ln(1+r)] ≈ μ − σ²/2). The ported notebook subtracted it a
    # second time, compounding to μ − σ² and biasing every fan downward.
    # Fixed 2026-08-24 with owner sign-off — the one deliberate deviation from
    # simulation/monte-carlo-drift.ipynb, pinned by test_montecarlo.py's
    # test_drift_is_the_gbm_log_drift.
    drift = float(returns.mean()) - variance / 2

    last_price = float(close.iloc[-1])

    # Vectorised over paths: shocks is (days, simulations).
    shocks = drift + daily_vol * rng.standard_normal((days, simulations))
    walk = np.vstack([np.zeros((1, simulations)), np.cumsum(shocks, axis=0)])
    paths = last_price * np.exp(walk)

    return SimulationResult(
        paths=pd.DataFrame(paths),
        last_price=last_price,
        daily_volatility=daily_vol,
        drift=drift,
    )
