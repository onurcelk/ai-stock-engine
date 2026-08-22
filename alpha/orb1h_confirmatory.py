"""orb_1h confirmatory measurement -- alpha/HT2_TOURNAMENT_PREREGISTRATION.md
Amendment 2.

Run only after the power gate passed (reports/ORB1H_POWER_GATE.md) and
Amendment 2 was committed. Reads and reports the point estimate for the
first time -- the gate touched variance only.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import orb1h_power_gate as gate_module
from . import stats

MDE_BP = 39.0
BLOCK = 4                   # fixed by the gate
NOISE_DRAWS = 30
NOISE_MEDIAN_CEILING_BP = 5.0
NOISE_EXCEEDANCE_CEILING = 0.10


@dataclasses.dataclass(frozen=True)
class Result:
    n_sessions: int
    n_dates: int
    advantage_bp: float
    ci_low_bp: float
    ci_high_bp: float
    breadth: float
    first_half_positive: bool
    second_half_positive: bool
    net_of_cost_bp: float
    noise_median_bp: float
    noise_exceedance: float

    @property
    def criterion_1(self) -> bool:
        return self.advantage_bp >= MDE_BP

    @property
    def criterion_2(self) -> bool:
        return np.isfinite(self.ci_low_bp) and self.ci_low_bp > 0.0

    @property
    def criterion_3(self) -> bool:
        return (self.breadth > 0.50 and self.first_half_positive
                and self.second_half_positive)

    @property
    def noise_passes(self) -> bool:
        return (self.noise_median_bp <= NOISE_MEDIAN_CEILING_BP
                and self.noise_exceedance <= NOISE_EXCEEDANCE_CEILING)

    @property
    def verdict(self) -> str:
        return ("CONTINUE" if (self.criterion_1 and self.criterion_2
                               and self.criterion_3 and self.noise_passes)
                else "REJECT")


def measure(*, seed: int = 20260822) -> Result:
    raw = pd.concat([gate_module._session_rows(s) for s in gate_module._symbols()],
                     ignore_index=True)
    per_date = raw.groupby("date")["advantage"].mean().sort_index()
    values = per_date.to_numpy(dtype=float)
    n_dates = len(values)

    mean_bp = float(values.mean() * 1e4)
    ci_low, ci_high = stats.block_bootstrap_ci(values, block=BLOCK,
                                                draws=stats.BOOTSTRAP_DRAWS)

    midpoint = n_dates // 2
    first_half_positive = bool(values[:midpoint].mean() > 0) if midpoint else False
    second_half_positive = bool(values[midpoint:].mean() > 0) if midpoint else False
    breadth = float((values > 0).mean())

    net_of_cost_bp = mean_bp - 5.0

    rng = np.random.default_rng(seed)
    dates = raw["date"].to_numpy()
    calls = raw["call"].to_numpy()
    realised = raw["realised"].to_numpy()
    permuted_means = []
    for _ in range(NOISE_DRAWS):
        shuffled_calls = rng.permutation(calls)
        permuted = pd.Series(realised * shuffled_calls, index=dates).groupby(level=0).mean()
        permuted_means.append(float(permuted.mean() * 1e4))
    permuted_means = np.array(permuted_means)
    noise_median_bp = float(np.median(permuted_means))
    noise_exceedance = float((permuted_means >= MDE_BP).mean())

    return Result(
        n_sessions=len(raw), n_dates=n_dates,
        advantage_bp=mean_bp, ci_low_bp=float(ci_low * 1e4), ci_high_bp=float(ci_high * 1e4),
        breadth=breadth, first_half_positive=first_half_positive,
        second_half_positive=second_half_positive, net_of_cost_bp=net_of_cost_bp,
        noise_median_bp=noise_median_bp, noise_exceedance=noise_exceedance,
    )


def main() -> int:
    result = measure()
    print(f"Sessions with a call: {result.n_sessions}  Independent dates: {result.n_dates}")
    print(f"Advantage:            {result.advantage_bp:+.1f} bp  "
          f"95% CI [{result.ci_low_bp:+.1f}, {result.ci_high_bp:+.1f}]  "
          f"(criterion 1: {result.criterion_1}, criterion 2: {result.criterion_2})")
    print(f"Breadth: {result.breadth:.3f}  "
          f"first half positive: {result.first_half_positive}  "
          f"second half positive: {result.second_half_positive}  "
          f"(criterion 3: {result.criterion_3})")
    print(f"Net of cost: {result.net_of_cost_bp:+.1f} bp")
    print(f"Noise control: median {result.noise_median_bp:+.1f} bp, "
          f"exceedance {result.noise_exceedance:.3f}  (passes: {result.noise_passes})")
    print()
    print(f"orb_1h VERDICT: {result.verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
