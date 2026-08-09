"""Statistics for the validation, with the correlation problem taken seriously.

Thirty symbols read on the same day are not thirty independent observations.
On 2022-03-08 almost every name in this universe was being scored against the
same index move, so a system that was simply long everything is right on all
thirty at once or wrong on all thirty at once. Treating that as n = 30 makes a
coin flip look significant, and it is the same mistake `ultimate.calibrate`
already guards against with its effective sample size.

So every interval here is **clustered by cutoff date**. The point estimate is
the plain mean over all predictions; the standard error is the cluster-robust
one, which counts the twelve dates rather than the 360 rows. It is between two
and six times wider than the naive binomial figure, and both are reported so
the difference is visible rather than asserted.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pandas as pd

try:
    from scipy import stats as _scipy_stats
except ImportError:  # pragma: no cover - scipy ships with sklearn here
    _scipy_stats = None


@dataclasses.dataclass
class Estimate:
    """A proportion or a mean, with an honest interval around it."""

    value: float
    n: int
    clusters: int
    se: float             # cluster-robust
    naive_se: float       # what pretending the rows are independent would give
    null: float = 0.0

    @property
    def t_stat(self) -> float:
        return (self.value - self.null) / self.se if self.se > 0 else 0.0

    @property
    def p_value(self) -> float:
        """Two-sided, on t with (clusters - 1) degrees of freedom."""
        if self.se <= 0 or self.clusters < 2:
            return float("nan")
        df = self.clusters - 1
        if _scipy_stats is not None:
            return float(2 * _scipy_stats.t.sf(abs(self.t_stat), df))
        return float(2 * (1 - 0.5 * (1 + math.erf(abs(self.t_stat) / math.sqrt(2)))))

    @property
    def ci95(self) -> tuple[float, float]:
        if self.clusters < 2:
            return (float("nan"), float("nan"))
        critical = (float(_scipy_stats.t.ppf(0.975, self.clusters - 1))
                    if _scipy_stats is not None else 1.96)
        return (self.value - critical * self.se, self.value + critical * self.se)

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def describe(self, unit: str = "%", digits: int = 1) -> str:
        low, high = self.ci95
        return (f"{self.value:.{digits}f}{unit} "
                f"[{low:.{digits}f}, {high:.{digits}f}] "
                f"n={self.n} p={self.p_value:.3f}")

    def row(self, label: str) -> dict:
        low, high = self.ci95
        return {
            "what": label,
            "value": round(self.value, 3),
            "n": self.n,
            "clusters": self.clusters,
            "se": round(self.se, 3),
            "naive_se": round(self.naive_se, 3),
            "ci_low": round(low, 3),
            "ci_high": round(high, 3),
            "p": round(self.p_value, 4) if self.p_value == self.p_value else None,
        }


def estimate(values: pd.Series, clusters: pd.Series, null: float = 0.0) -> Estimate:
    """Mean of `values` with a cluster-robust standard error.

    The usual CRVE for a sample mean: sum the within-cluster deviations first,
    square *that*, and only then average. When every row in a cluster moves
    together the sums stay large and the interval widens accordingly, which is
    the whole point.
    """
    frame = pd.DataFrame({"x": pd.to_numeric(values, errors="coerce"),
                          "g": clusters}).dropna()
    n = len(frame)
    if n == 0:
        return Estimate(float("nan"), 0, 0, float("nan"), float("nan"), null)

    mean = float(frame["x"].mean())
    groups = frame.groupby("g")["x"]
    count = groups.ngroups
    naive_se = float(frame["x"].std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")

    if count < 2:
        return Estimate(mean, n, count, float("nan"), naive_se, null)

    deviations = groups.apply(lambda s: float((s - mean).sum()))
    correction = count / (count - 1)
    variance = correction * float((deviations ** 2).sum()) / (n ** 2)
    return Estimate(mean, n, count, float(np.sqrt(variance)), naive_se, null)


def accuracy(correct: pd.Series, clusters: pd.Series) -> Estimate:
    """Directional accuracy in percent, tested against a coin flip."""
    return estimate(pd.to_numeric(correct, errors="coerce") * 100.0,
                    clusters, null=50.0)


def paired(a: pd.Series, b: pd.Series, clusters: pd.Series) -> Estimate:
    """Difference between two systems scored on the same rows, tested against zero.

    Paired rather than two-sample because both sides saw the same symbols on
    the same days: the market move is common to both and differencing removes
    it, which is far more powerful than comparing two noisy levels.
    """
    frame = pd.DataFrame({"a": pd.to_numeric(a, errors="coerce"),
                          "b": pd.to_numeric(b, errors="coerce"),
                          "g": clusters}).dropna()
    return estimate((frame["a"] - frame["b"]) * 100.0, frame["g"], null=0.0)


def brier(predicted_up: pd.Series, actual_up: pd.Series) -> float:
    """Mean squared error of a probability forecast. Lower is better; 0.25 is a coin."""
    frame = pd.DataFrame({"p": predicted_up, "y": actual_up}).dropna()
    if frame.empty:
        return float("nan")
    return float(((frame["p"] - frame["y"]) ** 2).mean())
