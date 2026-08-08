"""The carrier: everything between a raw feature and a position in the ranking.

`V2_2_PREREGISTRATION.md` §2, §3 and §5 in code. Nothing in V2 or V2.1 is
modified; this is a new layer those studies did not have.

The defect this exists to fix, measured on V2.1's development set:

    rank the cross-section by ret_12_1 directly        mean IC  +0.02115
    fit a GBM on ret_12_1 alone, then rank its output  mean IC  +0.00053

The learner, minimising squared error on the pooled winsorised *level*, fit a
predominantly **decreasing** step function of momentum — within-cutoff Spearman
against its own input averaged -0.198, negative on 224 of 255 cutoffs — and that
map was then used to **rank**. Every V2 and V2.1 arm passed its factors through
that same path.

Four pieces live here:

* `centred_rank` / `add_rank_columns` — the §2.1 input transform, applied to
  stock-level columns only. Market-context columns are constant across the
  cross-section at a cutoff, so ranking them would map every name to 0.5 and
  destroy them; they pass through raw and the tree splits on them across
  cutoffs. That asymmetry is pre-registered, and `test_alpha_v2_2.py` asserts it.
* `blend` — §3.2's bounded adjustment, `z_base + lambda * u`, whose order
  guarantee is proved in `order_bound_violations`.
* `fit_monotone` — §3.3's constrained learner, which cannot invert the factor.
* `diagnose` — §5, the seven measurements that have to be reported before any
  arm's IC means anything.

Nothing here reads an exam cutoff, and nothing here chooses anything.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import models, stats

RANK_PREFIX = "z__"

# §2.1 — the transform maps a percentile onto [-0.5, +0.5] so that a base score
# and an adjustment built the same way are on one scale and lambda is readable
# in rank units.
RANK_CENTRE = 0.5


# ----------------------------------------------------------------------
# §2.1 the input transform
# ----------------------------------------------------------------------

def rank_pct(frame: pd.DataFrame, column: str) -> pd.Series:
    """Within-cutoff percentile of one column. Feature-side, no outcome read.

    The same operation `models.simple_factor_scores` uses to build the
    benchmarks, so a rank-transformed `ret_12_1` and Benchmark 1 are the same
    numbers by construction rather than by coincidence.
    """
    return frame.groupby(level=0)[column].rank(pct=True, na_option="keep")


def centred_rank(frame: pd.DataFrame, column: str) -> pd.Series:
    return rank_pct(frame, column) - RANK_CENTRE


def rank_series(values: pd.Series) -> pd.Series:
    """Centred within-cutoff rank of an arbitrary per-row series (e.g. a prediction)."""
    return values.groupby(level=0).rank(pct=True, na_option="keep") - RANK_CENTRE


def add_rank_columns(frame: pd.DataFrame, columns: tuple[str, ...]
                     ) -> tuple[pd.DataFrame, list[str]]:
    """Add `z__c` for each named column. Returns the widened frame and the new names.

    Only the columns handed in are transformed. The caller is responsible for
    handing in stock-level columns and not cutoff-constant ones, and
    `constant_within_cutoff` is provided so that responsibility can be checked
    rather than assumed.
    """
    out = frame.copy()
    added = []
    for column in columns:
        if column not in frame.columns:
            raise KeyError(f"cannot rank-transform a column the panel lacks: {column}")
        name = f"{RANK_PREFIX}{column}"
        out[name] = centred_rank(frame, column)
        added.append(name)
    return out, added


def constant_within_cutoff(frame: pd.DataFrame, columns) -> dict[str, bool]:
    """Which of these columns take a single value across the cross-section at a cutoff.

    The check that decides whether a column may be rank-transformed: a
    cutoff-constant column ranks to 0.5 everywhere and carries nothing
    afterwards.
    """
    distinct = frame[list(columns)].groupby(level=0).nunique().max()
    return {column: bool(distinct[column] <= 1) for column in columns}


# ----------------------------------------------------------------------
# §3.2 the bounded adjustment
# ----------------------------------------------------------------------

def blend(base: pd.Series, adjustment: pd.Series, lam: float) -> pd.Series:
    """§3.2: `final = base + lambda * u`, with `u` the centred rank of the adjustment.

    Ranking the adjustment within the cutoff before adding it is what makes
    lambda mean something: both terms then live on [-0.5, +0.5], so lambda is
    the maximum displacement in rank units rather than a number whose scale
    depends on what the residual regression happened to output.

    The consequence, which `order_bound_violations` checks on real predictions:
    for any two names, `base_i - base_j > lambda` implies `final_i > final_j`.
    At lambda = 0.5 two names more than half the cross-section apart in momentum
    percentile keep their order whatever the model says, so the V2.1-A pathology
    — a wholesale inversion of the factor — is impossible by construction.
    """
    if lam == 0.0:
        # Not merely an optimisation: at lambda = 0 the result must be *exactly*
        # the base, so that the identity check against Benchmark 1 is an
        # identity and not a near-miss introduced by adding 0.0 * NaN.
        return base.copy()
    return base + lam * rank_series(adjustment)


def order_bound_violations(base: pd.Series, final: pd.Series, lam: float) -> int:
    """Count pairs that break §3.2's guarantee. Must be 0.

    Checked per cutoff and without forming the full pair matrix: sort by `base`,
    and for each row ask whether any *later* row (higher base) has a final score
    lower than this row's while their base gap exceeds lambda. A suffix minimum
    of `final` makes that one pass.
    """
    frame = pd.DataFrame({"base": base, "final": final}).dropna()
    violations = 0
    for _cutoff, block in frame.groupby(level=0):
        ordered = block.sort_values("base")
        b = ordered["base"].to_numpy(dtype=float)
        f = ordered["final"].to_numpy(dtype=float)
        if len(b) < 2:
            continue
        # suffix_min[k] = min(f[k:]) — the worst final score among names with a
        # base at least as high as b[k].
        suffix_min = np.minimum.accumulate(f[::-1])[::-1]
        # The first index whose base exceeds b[i] + lam.
        cut = np.searchsorted(b, b + lam, side="right")
        has_tail = cut < len(b)
        if not has_tail.any():
            continue
        index = np.flatnonzero(has_tail)
        violations += int(np.sum(suffix_min[cut[index]] <= f[index]))
    return violations


# ----------------------------------------------------------------------
# §3.3 the constrained learner
# ----------------------------------------------------------------------

def live_columns(train: pd.DataFrame, columns: list[str], target: str) -> list[str]:
    """The columns `models.fit_model_a` will actually keep, computed the same way.

    `fit_model_a` drops columns that are entirely NaN over the training slice —
    imputing them would fill a cutoff from itself — and records the survivors on
    the `Fit`. A monotonic constraint is positional, so it has to be built
    against the survivors, not against the request. Duplicating the rule here is
    a coupling, so `fit_monotone` asserts afterwards that the two agreed.
    """
    usable = train[list(columns) + [target]].replace([np.inf, -np.inf], np.nan)
    usable = usable[usable[target].notna()]
    return [c for c in columns if usable[c].notna().any()]


def fit_monotone(train: pd.DataFrame, columns: list[str], target: str,
                 increasing: str) -> models.Fit | None:
    """§3.3: `MODEL_A_PARAMS` plus `monotonic_cst = +1` on one column, 0 elsewhere.

    sklearn 1.9 takes the constraint as a positional array and handles NaN in a
    constrained column; both were verified on synthetic data before this arm was
    pre-registered.

    The prediction is then non-decreasing in `increasing` at fixed values of
    every other column, so context may flatten or steepen the momentum slope but
    two names identical in the other 34 columns can never be ordered against
    their momentum.
    """
    live = live_columns(train, columns, target)
    if not live:
        return None
    if increasing not in live:
        raise RuntimeError(
            f"the constrained column {increasing} is all-NaN over this training "
            "slice, so the constraint would silently not be applied")

    constraint = [1 if column == increasing else 0 for column in live]
    params = {**models.MODEL_A_PARAMS, "monotonic_cst": constraint}
    fit = models.fit_model_a(train, columns, target=target, params=params)
    if fit is not None and fit.columns != live:
        raise RuntimeError(
            "the monotonic constraint was built against a different column list "
            f"than the fit used: {live} vs {fit.columns}")
    return fit


# ----------------------------------------------------------------------
# §5 the diagnostics
# ----------------------------------------------------------------------

@dataclasses.dataclass
class Diagnostics:
    """The seven §5 measurements, per cutoff and aggregated."""

    name: str
    per_cutoff: pd.DataFrame

    def summary(self) -> dict:
        table = self.per_cutoff
        if table.empty:
            return {"n_cutoffs": 0}
        rho = table["spearman_vs_factor"].dropna()
        return {
            "n_cutoffs": int(len(table)),
            "spearman_vs_factor": {
                "mean": _round(rho.mean(), 4), "min": _round(rho.min(), 4),
                "max": _round(rho.max(), 4),
                "share_negative": _round((rho < 0).mean(), 4),
                "share_below_0.99": _round((rho < 0.99).mean(), 4)},
            "inversions": {
                "total": int(table["inversions"].sum()),
                "cutoffs_with_any": int((table["inversions"] > 0).sum())},
            "runs_vs_factor": {
                "median": int(table["runs"].median()),
                "min": int(table["runs"].min()), "max": int(table["runs"].max())},
            "distinct_scores": {
                "median": int(table["distinct"].median()),
                "min": int(table["distinct"].min()), "max": int(table["distinct"].max())},
            "cross_section": {
                "min": int(table["width"].min()), "max": int(table["width"].max())},
            # Univariate in the factor means two things together: the score
            # changes only where the factor changes (runs == distinct), and it
            # cannot tell apart names that share a factor bin (distinct < width).
            # Either alone can hold for a multivariate score by accident.
            "is_univariate_in_factor": bool(
                (table["runs"] == table["distinct"]).all()
                and (table["distinct"] < table["width"]).all()),
            "collapsed_cutoffs": int((table["distinct"] <= 1).sum()),
        }


def diagnose(score: pd.Series, factor: pd.Series, name: str) -> Diagnostics:
    """§5.1-5.7 for one arm's final score against the factor it is meant to carry.

    `runs == distinct` is the sharp test for "this score is a function of the
    factor alone": sorting by the factor produces no interleaving, so every
    change in the score coincides with a change in the factor. `inversions` is
    the sharp test for "this score preserves the factor's ordering". V2.1-A
    failed the second badly while passing the first, which is exactly how a
    carrier destroys a signal while looking like it is using it.
    """
    frame = pd.DataFrame({"s": score, "f": factor}).dropna()
    rows = []
    for cutoff, block in frame.groupby(level=0):
        ordered = block.sort_values(["f", "s"])
        s = ordered["s"].to_numpy(dtype=float)
        steps = np.diff(s) if len(s) > 1 else np.array([])
        rows.append({
            "cutoff": cutoff,
            "width": len(block),
            "distinct": int(block["s"].nunique()),
            "runs": 1 + int((steps != 0).sum()) if len(s) else 0,
            "inversions": int((steps < 0).sum()),
            "spearman_vs_factor": stats.spearman_ic(block["s"], block["f"]),
        })
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.set_index("cutoff")
    return Diagnostics(name, table)


# ----------------------------------------------------------------------
# V2.3 §4 — the collinearity diagnostic. Added for V2.3; nothing above is
# changed, because everything above records a completed experiment.
# ----------------------------------------------------------------------

@dataclasses.dataclass
class Collinearity:
    """How much of a bounded adjustment is just a copy of the base it adjusts.

    The measurement V2.2 did not have and that turned out to explain its result:
    V2.2-B's adjustment had a within-cutoff Spearman of **-0.9923** against its own
    base, negative on 255 of 255 cutoffs. The target was
    `target_rank - rank_pct(ret_12_1)` and `rank_pct(ret_12_1)` was *also* an
    input, so the learner's best pooled answer was very nearly `-base` — and
    `rank_series` then re-encoded that at full amplitude.

    `effective_lambda` is why this matters rather than merely being untidy. Only
    the component of `u` orthogonal to the base can move the ranking in a way the
    base did not already, and its share of `u`'s dispersion is `sqrt(1 - rho^2)`.
    So an arm advertising `lambda = 0.50` at `rho = 0.99` is really operating at
    about 0.07 rank units of new authority. The nominal bound is honest about what
    it forbids and silent about what it delivers; this is the part it is silent
    about.
    """

    name: str
    per_cutoff: pd.Series           # signed within-cutoff Spearman(u, base)
    lam: float

    @property
    def mean_abs(self) -> float:
        clean = self.per_cutoff.dropna()
        return float(clean.abs().mean()) if len(clean) else float("nan")

    @property
    def effective_lambda(self) -> float:
        rho = self.mean_abs
        if not np.isfinite(rho):
            return float("nan")
        return float(self.lam * np.sqrt(max(0.0, 1.0 - min(1.0, rho) ** 2)))

    def summary(self) -> dict:
        clean = self.per_cutoff.dropna()
        if not len(clean):
            return {"n_cutoffs": 0}
        return {
            "n_cutoffs": int(len(clean)),
            # Both are reported on purpose. A ceiling on |mean rho| could be
            # satisfied by an arm at +0.95 on half its cutoffs and -0.95 on the
            # other half, which is maximally collinear and would read as 0.
            "mean_abs_rho": _round(self.mean_abs, 4),
            "mean_signed_rho": _round(clean.mean(), 4),
            "min_signed_rho": _round(clean.min(), 4),
            "max_signed_rho": _round(clean.max(), 4),
            "share_abs_above_0.90": _round((clean.abs() > 0.90).mean(), 4),
            "share_negative": _round((clean < 0).mean(), 4),
            "nominal_lambda": self.lam,
            "effective_lambda": _round(self.effective_lambda, 4),
            "effective_share_of_nominal": _round(
                self.effective_lambda / self.lam if self.lam else float("nan"), 4),
        }


def collinearity(adjustment: pd.Series, base: pd.Series, name: str,
                 lam: float) -> Collinearity:
    """Within-cutoff Spearman between a bounded adjustment and its base.

    Spearman rather than Pearson because the blend is scored by a rank metric, so
    what matters is whether `u` reorders names the same way the base already does,
    not whether it is an affine copy.
    """
    frame = pd.DataFrame({"u": adjustment, "b": base}).dropna()
    rows = {}
    for cutoff, block in frame.groupby(level=0):
        if len(block) < 10 or block["u"].nunique() < 3 or block["b"].nunique() < 3:
            rows[cutoff] = np.nan
            continue
        rows[cutoff] = float(block["u"].rank().corr(block["b"].rank()))
    series = pd.Series(rows, dtype=float).sort_index()
    return Collinearity(name, series, lam)


def _round(value, places: int):
    if value is None:
        return None
    value = float(value)
    return None if not np.isfinite(value) else round(value, places)
