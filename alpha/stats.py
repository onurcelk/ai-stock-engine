"""IC statistics that survive the autocorrelation correction of §5.

The V1 report's central statistical move was refusing to treat 30 symbols on
one date as 30 draws. Its time-series counterpart is refusing to treat 500
weekly ICs as 500 draws, and §5 says so directly: overlapping outcome windows
make consecutive errors serially correlated, so report Newey-West or
block-bootstrapped standard errors, not naive ones.

This module reports **three** intervals for every headline number, in one row,
so the reader can see the correction rather than take it on faith:

* `naive` — i.i.d., what pretending the cutoffs are independent would give;
* `newey_west` — HAC with 4 lags, correcting for residual serial dependence;
* `block_bootstrap` — moving-block bootstrap, block length 4 cutoffs (~one
  month), 10,000 resamples, which makes no distributional assumption at all.

The pre-registered thresholds in §8 of `PREREGISTRATION.md` are judged against
the **block-bootstrap** interval. It is the widest of the three here, and it is
the one chosen in advance.

The design that makes all this less load-bearing than it would otherwise be:
cutoffs are spaced exactly one horizon apart, so outcome windows are adjacent
and non-overlapping. The mechanical overlap §5 warns about is absent by
construction; what remains is the market's own persistence, which is what these
intervals are for.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

try:
    from scipy import stats as _scipy_stats
except ImportError:  # pragma: no cover — scipy ships with sklearn here
    _scipy_stats = None

BLOCK_LENGTH = 4
BOOTSTRAP_DRAWS = 10_000
NEWEY_WEST_LAGS = 4
SEED = 20260808


@dataclasses.dataclass
class Series:
    """A per-cutoff statistic and every interval we are willing to quote on it."""

    name: str
    values: pd.Series           # indexed by cutoff, one number per cutoff
    null: float = 0.0

    @property
    def clean(self) -> pd.Series:
        return self.values.dropna().sort_index()

    @property
    def n(self) -> int:
        return int(len(self.clean))

    @property
    def mean(self) -> float:
        return float(self.clean.mean()) if self.n else float("nan")

    @property
    def median(self) -> float:
        return float(self.clean.median()) if self.n else float("nan")

    @property
    def sd(self) -> float:
        return float(self.clean.std(ddof=1)) if self.n > 1 else float("nan")

    @property
    def naive_se(self) -> float:
        return self.sd / np.sqrt(self.n) if self.n > 1 else float("nan")

    @property
    def newey_west_se(self) -> float:
        return newey_west(self.clean.to_numpy(dtype=float), NEWEY_WEST_LAGS)

    def bootstrap_ci(self, level: float = 0.95) -> tuple[float, float]:
        return block_bootstrap_ci(self.clean.to_numpy(dtype=float), level=level)

    @property
    def hit_rate(self) -> float:
        """Share of cutoffs on the right side of the null — §15's IC hit rate."""
        return float((self.clean > self.null).mean()) if self.n else float("nan")

    def t_stat(self, se: float | None = None) -> float:
        se = self.newey_west_se if se is None else se
        return (self.mean - self.null) / se if se and np.isfinite(se) and se > 0 else float("nan")

    def p_value(self) -> float:
        t = self.t_stat()
        if not np.isfinite(t) or self.n < 3:
            return float("nan")
        if _scipy_stats is not None:
            return float(2 * _scipy_stats.t.sf(abs(t), self.n - 1))
        return float("nan")

    def bootstrap_p(self) -> float:
        """Two-sided bootstrap p: how often a recentred resample beats the observed."""
        return block_bootstrap_p(self.clean.to_numpy(dtype=float), self.null)

    def excludes_null(self) -> bool:
        low, high = self.bootstrap_ci()
        return bool(np.isfinite(low) and np.isfinite(high)
                    and (low > self.null or high < self.null))

    def row(self) -> dict:
        low, high = self.bootstrap_ci()
        return {
            "what": self.name,
            "n_cutoffs": self.n,
            "mean": round(self.mean, 5),
            "median": round(self.median, 5),
            "sd": round(self.sd, 5),
            "hit_rate": round(self.hit_rate, 4),
            "naive_se": round(self.naive_se, 5),
            "nw_se": round(self.newey_west_se, 5),
            "boot_lo": round(low, 5),
            "boot_hi": round(high, 5),
            "t": round(self.t_stat(), 3),
            "p_nw": round(self.p_value(), 5),
            "p_boot": round(self.bootstrap_p(), 5),
            "excludes_null": self.excludes_null(),
        }


def newey_west(values: np.ndarray, lags: int = NEWEY_WEST_LAGS) -> float:
    """HAC standard error of a sample mean, Bartlett kernel."""
    values = values[np.isfinite(values)]
    n = len(values)
    if n < 3:
        return float("nan")
    centred = values - values.mean()
    gamma0 = float(centred @ centred) / n
    total = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        gamma = float(centred[lag:] @ centred[:-lag]) / n
        total += 2.0 * (1.0 - lag / (lags + 1.0)) * gamma
    # A dependence structure can drive the HAC estimate negative in small
    # samples. Fall back to the i.i.d. figure and let the bootstrap carry the
    # interval rather than quoting a nan.
    if total <= 0:
        return float(np.std(values, ddof=1) / np.sqrt(n))
    return float(np.sqrt(total / n))


def _moving_blocks(values: np.ndarray, block: int, draws: int,
                   rng: np.random.Generator) -> np.ndarray:
    n = len(values)
    block = max(1, min(block, n))
    per_draw = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(draws, per_draw))
    offsets = np.arange(block)
    index = (starts[:, :, None] + offsets[None, None, :]).reshape(draws, -1)[:, :n]
    return values[index]


def block_bootstrap_ci(values: np.ndarray, level: float = 0.95,
                       block: int = BLOCK_LENGTH, draws: int = BOOTSTRAP_DRAWS
                       ) -> tuple[float, float]:
    """Percentile interval from a moving-block bootstrap of the mean.

    Blocks rather than single draws because resampling one cutoff at a time
    would destroy exactly the serial dependence the interval is meant to
    account for, and hand back the naive width under a more impressive name.
    """
    values = values[np.isfinite(values)]
    if len(values) < 4:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(SEED)
    means = _moving_blocks(values, block, draws, rng).mean(axis=1)
    tail = (1.0 - level) / 2.0
    return (float(np.quantile(means, tail)), float(np.quantile(means, 1.0 - tail)))


def block_bootstrap_p(values: np.ndarray, null: float = 0.0,
                      block: int = BLOCK_LENGTH, draws: int = BOOTSTRAP_DRAWS) -> float:
    values = values[np.isfinite(values)]
    if len(values) < 4:
        return float("nan")
    rng = np.random.default_rng(SEED + 1)
    observed = values.mean() - null
    centred = values - values.mean()
    means = _moving_blocks(centred, block, draws, rng).mean(axis=1)
    # +1 in both places so a p of exactly zero is impossible: 10,000 draws can
    # bound a p-value below, not demonstrate it is nil.
    return float((np.sum(np.abs(means) >= abs(observed)) + 1) / (draws + 1))


def spearman_ic(predicted: pd.Series, realised: pd.Series) -> float:
    """Rank correlation between a prediction and its outcome, one cutoff's worth."""
    frame = pd.DataFrame({"p": predicted, "y": realised}).dropna()
    if len(frame) < 10 or frame["p"].nunique() < 3 or frame["y"].nunique() < 3:
        return float("nan")
    return float(frame["p"].rank().corr(frame["y"].rank()))


def ic_by_cutoff(frame: pd.DataFrame, prediction: str, target: str) -> pd.Series:
    """One Spearman IC per cutoff — the §15 primary metric."""
    return frame.groupby(level=0).apply(
        lambda block: spearman_ic(block[prediction], block[target]))


def quintile_spread(frame: pd.DataFrame, prediction: str, target: str,
                    fraction: float = 0.2) -> pd.DataFrame:
    """Top-quintile, bottom-quintile and long-short realised alpha per cutoff (§16-17).

    The long-short leg is balanced by construction — the same number of names
    on each side — so the spread cannot be earned by net market exposure. That
    is the §17 "market-neutral" requirement: credit goes to picking within the
    cross-section, not to being long during a rally.
    """
    def one(block: pd.DataFrame) -> pd.Series:
        clean = block[[prediction, target]].dropna()
        count = int(len(clean) * fraction)
        if count < 3:
            return pd.Series({"top": np.nan, "bottom": np.nan, "spread": np.nan,
                              "n": len(clean)})
        ordered = clean.sort_values(prediction)
        bottom = float(ordered[target].iloc[:count].mean())
        top = float(ordered[target].iloc[-count:].mean())
        return pd.Series({"top": top, "bottom": bottom, "spread": top - bottom,
                          "n": len(clean)})

    return frame.groupby(level=0).apply(one)


def paired_difference(left: pd.Series, right: pd.Series, name: str) -> Series:
    """Per-cutoff difference between two systems — the §18 gate.

    Paired for the same reason `validation/metrics.py` pairs: both sides saw
    the same names on the same day, so differencing removes the day and what
    is left is the part attributable to the model.
    """
    frame = pd.DataFrame({"a": left, "b": right}).dropna()
    return Series(name, frame["a"] - frame["b"], null=0.0)


def holm_bonferroni(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Step-down multiplicity correction across the experiments actually run (§8).

    Pre-registered because seven experiments each tested at 0.05 will produce a
    "significant" result about a third of the time on pure noise, and reporting
    the raw p-value alone is how that becomes a finding.
    """
    ordered = sorted((p for p in p_values.items() if np.isfinite(p[1])), key=lambda kv: kv[1])
    m = len(ordered)
    out, running = {}, 0.0
    for rank, (name, p) in enumerate(ordered):
        adjusted = min(1.0, max(running, (m - rank) * p))
        running = adjusted
        out[name] = {"p_raw": round(p, 5), "p_holm": round(adjusted, 5),
                     "significant": adjusted < alpha}
    for name, p in p_values.items():
        out.setdefault(name, {"p_raw": None if not np.isfinite(p) else round(p, 5),
                              "p_holm": None, "significant": False})
    return out
