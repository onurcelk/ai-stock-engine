"""PEAD-1 confirmatory measurement -- alpha/PEAD1_PREREGISTRATION.md.

Run only after the power gate passed (reports/PEAD1_POWER_GATE.md) and this
pre-registration was committed. Unlike the gate, this module DOES read and
report the point estimate -- that is what a confirmatory measurement is.
Every quantity it reports was fixed in the pre-registration before this
module's first run: the 5-session window, the CONTINUE rule, the controls,
and the noise-control procedure.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import pead1_power_gate as gate_module
from . import stats

WINDOW = 5
MDE_BP = 39.0
BLOCK = 4                    # fixed by the gate, §2.5 of the pre-registration
NOISE_DRAWS = 30
NOISE_MEDIAN_CEILING_BP = 10.0
NOISE_EXCEEDANCE_CEILING = 0.10


def _spy_frame() -> pd.DataFrame:
    frame = pd.read_csv(gate_module.CACHE_DIR / "SPY.csv")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise", utc=True)
    return frame[["date", "close"]].dropna().sort_values("date").reset_index(drop=True)


def _event_rows(window: int = WINDOW) -> pd.DataFrame:
    """One row per event: symbol, week, firm return, SPY return, sue sign."""
    events = gate_module._load_events()
    spy = _spy_frame()
    spy_dates = spy["date"].to_numpy()
    spy_close = spy["close"].to_numpy()

    rows: list[dict] = []
    prices: dict[str, pd.DataFrame] = {}
    for symbol, firm_events in events.items():
        if symbol not in prices:
            try:
                prices[symbol] = gate_module._load_price(symbol)
            except FileNotFoundError:
                continue
        price = prices[symbol]
        dates = price["date"]
        closes = price["close"].to_numpy()
        total = len(price)

        for valid_from, sue in zip(firm_events.valid_from, firm_events.sue):
            if not np.isfinite(sue) or sue == 0.0:
                continue
            cutoff_date = pd.Timestamp(valid_from).normalize() + pd.Timedelta(days=1)
            position = int(np.searchsorted(dates.values, np.datetime64(cutoff_date)))
            if position + window >= total:
                continue
            anchor = closes[position]
            matured = closes[position + window]
            if not (np.isfinite(anchor) and anchor > 0 and np.isfinite(matured)):
                continue
            firm_return = matured / anchor - 1.0

            anchor_date = dates.iloc[position]
            spy_pos = int(np.searchsorted(spy_dates, np.datetime64(anchor_date)))
            if spy_pos + window >= len(spy_close):
                continue
            spy_anchor, spy_matured = spy_close[spy_pos], spy_close[spy_pos + window]
            if not (np.isfinite(spy_anchor) and spy_anchor > 0 and np.isfinite(spy_matured)):
                continue
            spy_return = spy_matured / spy_anchor - 1.0

            week = pd.Timestamp(anchor_date).tz_localize(None).to_period("W").start_time
            sign = float(np.sign(sue))
            rows.append({
                "symbol": symbol, "week": week, "sign": sign,
                "advantage": firm_return * sign,
                "market_advantage": (firm_return - spy_return) * sign,
            })
    return pd.DataFrame(rows)


@dataclasses.dataclass(frozen=True)
class Result:
    n_events: int
    n_weeks: int
    advantage_bp: float
    ci_low_bp: float
    ci_high_bp: float
    breadth: float
    first_half_positive: bool
    second_half_positive: bool
    market_advantage_bp: float
    market_ci_low_bp: float
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
    def criterion_4(self) -> bool:
        return np.isfinite(self.market_ci_low_bp) and self.market_ci_low_bp > 0.0

    @property
    def noise_passes(self) -> bool:
        return (self.noise_median_bp <= NOISE_MEDIAN_CEILING_BP
                and self.noise_exceedance <= NOISE_EXCEEDANCE_CEILING)

    @property
    def verdict(self) -> str:
        return ("CONTINUE" if (self.criterion_1 and self.criterion_2
                               and self.criterion_3 and self.criterion_4
                               and self.noise_passes) else "REJECT")


def measure(*, seed: int = 20260822) -> Result:
    raw = _event_rows()
    per_week = raw.groupby("week").agg(
        advantage=("advantage", "mean"),
        market_advantage=("market_advantage", "mean"),
    ).sort_index()

    values = per_week["advantage"].to_numpy(dtype=float)
    market_values = per_week["market_advantage"].to_numpy(dtype=float)
    n_weeks = len(values)

    mean_bp = float(values.mean() * 1e4)
    ci_low, ci_high = stats.block_bootstrap_ci(values, block=BLOCK,
                                                draws=stats.BOOTSTRAP_DRAWS)

    midpoint = n_weeks // 2
    first_half_positive = bool(values[:midpoint].mean() > 0) if midpoint else False
    second_half_positive = bool(values[midpoint:].mean() > 0) if midpoint else False
    breadth = float((values > 0).mean())

    market_mean_bp = float(market_values.mean() * 1e4)
    market_ci_low, _ = stats.block_bootstrap_ci(market_values, block=BLOCK,
                                                 draws=stats.BOOTSTRAP_DRAWS)

    net_of_cost_bp = mean_bp - 5.0     # one round trip per event, 5bp nominal

    rng = np.random.default_rng(seed)
    permuted_means = []
    signs = raw["sign"].to_numpy()
    unsigned_firm_return = raw["advantage"].to_numpy() * signs   # recover firm_return
    weeks = raw["week"].to_numpy()
    for _ in range(NOISE_DRAWS):
        shuffled_signs = rng.permutation(signs)
        shuffled_advantage = unsigned_firm_return * shuffled_signs
        permuted = pd.Series(shuffled_advantage, index=weeks).groupby(level=0).mean()
        permuted_means.append(float(permuted.mean() * 1e4))
    permuted_means = np.array(permuted_means)
    noise_median_bp = float(np.median(permuted_means))
    noise_exceedance = float((permuted_means >= MDE_BP).mean())

    return Result(
        n_events=len(raw), n_weeks=n_weeks,
        advantage_bp=mean_bp, ci_low_bp=float(ci_low * 1e4), ci_high_bp=float(ci_high * 1e4),
        breadth=breadth, first_half_positive=first_half_positive,
        second_half_positive=second_half_positive,
        market_advantage_bp=market_mean_bp, market_ci_low_bp=float(market_ci_low * 1e4),
        net_of_cost_bp=net_of_cost_bp,
        noise_median_bp=noise_median_bp, noise_exceedance=noise_exceedance,
    )


def main() -> int:
    result = measure()
    print(f"Events: {result.n_events}  Independent weeks: {result.n_weeks}")
    print(f"Advantage:            {result.advantage_bp:+.1f} bp  "
          f"95% CI [{result.ci_low_bp:+.1f}, {result.ci_high_bp:+.1f}]  "
          f"(criterion 1: {result.criterion_1}, criterion 2: {result.criterion_2})")
    print(f"Breadth: {result.breadth:.3f}  "
          f"first half positive: {result.first_half_positive}  "
          f"second half positive: {result.second_half_positive}  "
          f"(criterion 3: {result.criterion_3})")
    print(f"Market-relative advantage: {result.market_advantage_bp:+.1f} bp  "
          f"CI low {result.market_ci_low_bp:+.1f}  (criterion 4: {result.criterion_4})")
    print(f"Net of cost: {result.net_of_cost_bp:+.1f} bp")
    print(f"Noise control: median {result.noise_median_bp:+.1f} bp, "
          f"exceedance {result.noise_exceedance:.3f}  (passes: {result.noise_passes})")
    print()
    print(f"PEAD-1 VERDICT: {result.verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
