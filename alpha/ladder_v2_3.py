"""V2.3 — the adjustment must not re-encode its own base. Development only.

`V2_3_PREREGISTRATION.md` in code. `ladder.py` and `ladder_v2_2.py` are left
untouched: they record finished experiments. The column lists are *imported* from
them rather than retyped, so "V2.1-C's 35 columns minus the base" is enforced by
the import graph instead of by a promise.

The finding this study exists to act on, measured on V2.2's frozen artefacts:

    within-cutoff Spearman(V2.2-B's adjustment, its own base) = -0.9923
    negative on 255 of 255 cutoffs

V2.2-B's residual target was `target_rank - rank_pct(ret_12_1)` while
`rank_pct(ret_12_1)` was *also* an input. The pooled signal is +0.011 Spearman, so
the learner's best pooled answer was very nearly `-base`, and `rank_series`
re-encoded it at full amplitude. lambda = 0.50 therefore delivered about **0.062**
rank units of new authority rather than 0.50, and V2.2-B's +0.00241 advantage
decomposes into +0.00604 from the orthogonal component and -0.00363 of dilution.

Two arms follow, and they are the only two:

    V2.3-A   the same carrier as V2.2-B with `z__ret_12_1` removed from the inputs.
             A minus V2.2-B is exactly one deleted column, so the delta is
             attributable to the collinearity channel and to nothing else.
    V2.3-B   the same carrier with **Benchmark 3** as the base and the residual
             taken against B3. lambda = 0 *is* B3, which turns the incumbent into
             the null and makes G3 -- the gate V2.2 failed -- a comparison against
             the arm's own base, at roughly 3x the resolution.

Three properties of this file matter more than the rest of it.

**It cannot see the exam.** Cutoffs come from `examset.development_only()`, which
slices to the frozen development list and then asserts no exam cutoff survived.
The run refuses to start if `out/v2_1_exam_predictions.json` exists.

**The rungs, the lambda curve and the noise control can never be chosen.**
`select_arm` reads `is_arm`, and §6.1 puts the price on breaking it: the Holm
family is the k=2 arms.

**Eligibility runs before selection, and selection before the gate.** An arm whose
adjustment is still collinear with its base is carrier-defective under H1b
whatever its IC, because at rho = 0.99 the advertised lambda is a material
misstatement of what the arm actually does.

Run:  python -m alpha.ladder_v2_3
      python -m alpha.ladder_v2_3 --only V2.3-B   # rungs and diagnostics still run
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd

from . import (build_panel, carrier, develop, examset, ladder, ladder_v2_2,
               models, pitdata, protocol, stats, walkforward)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
JSON_PATH = OUT_DIR / "v2_3_development.json"
PICKLE_PATH = OUT_DIR / "v2_3_development.pkl"

PREREGISTRATION = "alpha/V2_3_PREREGISTRATION.md"
FAMILY_SIZE = 2                     # §6.1 — fixed before the first fit, not after

# ----------------------------------------------------------------------
# §2-3 — the bases and the inputs
# ----------------------------------------------------------------------

MOMENTUM = "ret_12_1"
BASE_B1 = f"{carrier.RANK_PREFIX}{MOMENTUM}"        # z__ret_12_1  == Benchmark 1
BASE_B3 = f"{carrier.RANK_PREFIX}b3"                # z__b3        == Benchmark 3
B3_KEY = "b3_regime_switched"
B1_KEY = "b1_momentum_12_1"

# The 8 non-momentum stock-level columns, rank-transformed. Imported from the V2.1
# ladder so a V2.3 input cannot drift from V2.1-C's list without the V2.1 module
# changing, which its own tests forbid.
STOCK_LEVEL = ladder.STOCK_LEVEL                    # 8, excludes ret_12_1
MARKET_CONTEXT = ladder.MARKET_CONTEXT              # 26, cutoff-constant, un-ranked

RANKED_STOCK_LEVEL = tuple(f"{carrier.RANK_PREFIX}{c}" for c in STOCK_LEVEL)
INPUT_COLUMNS = RANKED_STOCK_LEVEL + MARKET_CONTEXT  # 34 — the base is NOT here

# Every stock-level column that gets a `z__`: the 8 inputs plus momentum, which is
# V2.3-A's base and deliberately not an input.
RANK_TRANSFORMED = (MOMENTUM,) + STOCK_LEVEL

# §4 — the one-feature rung's single input. The base cannot be an input, so the
# rung uses the first stock-level rank in the pre-registered order after momentum.
RUNG_COLUMN = f"{carrier.RANK_PREFIX}ret_20d"

RESID_TARGET = "y_resid"

# §1.7 — carried over from V2_2_PREREGISTRATION.md §3.2 with its original
# neutral-prior argument, NOT re-derived from V2.2's lambda curve.
LAMBDA = 0.50
LAMBDA_CURVE = (0.00, 0.25, 0.50, 1.00)

# §5 — eligibility. All three fixed before the first fit.
H1A_FLOOR = ladder_v2_2.G1_FLOOR                    # -0.005, carried over verbatim
H1B_CEILING = 0.90
MIN_SCORED_CUTOFFS = ladder_v2_2.MIN_SCORED_CUTOFFS  # 200, carried over

# §6 — the gate. G2/G3/G4/G5 are V2.2 §6.3 verbatim; G6 is new.
BREADTH_FLOOR = ladder_v2_2.BREADTH_FLOOR           # 0.55, carried over
GATE_BENCHMARKS = ladder_v2_2.GATE_BENCHMARKS       # (B1, B3), carried over
COST_BPS = protocol.COST_BPS                        # 5.0, from V2.1 §4.1
COST_REPORTED_BPS = protocol.COST_SENSITIVITY_BPS   # 5, 10, 20

EXAM_CUTOFFS_FOR_POWER = 72         # §6.2 — for the scaled half-width only
NOISE_SEED = 20260808               # the §4 noise-blend control, as pre-registered
NOISE_DRAWS = 30                    # the powered version — see `noise_control`

BEAR = protocol.BEAR


# ----------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Arm:
    """A base, an input list, a residual target and a bounded output. That is all.

    Everything not named here is inherited from V2.2-B unchanged: learner,
    hyperparameters, walk-forward, purge, embargo, cutoff grid, lambda, scoring
    target, bootstrap. That is what makes a V2.3-minus-V2.2 difference
    attributable to the base and the input list.
    """

    name: str
    base: str                       # the panel column holding the centred base rank
    benchmark: str                  # the benchmark key that base is identical to
    note: str
    is_arm: bool = True
    columns: tuple[str, ...] = INPUT_COLUMNS
    lam: float = LAMBDA

    def fitter(self):
        base = self.base

        def fit(train: pd.DataFrame, columns: list[str]) -> models.Fit | None:
            frame = _training_frame(train, columns, base)
            return models.fit_model_a(frame, list(columns), target=RESID_TARGET)

        return fit

    def score(self, panel, prediction: pd.Series) -> pd.Series:
        """§2: `final = base + lambda * u`, masked to the cutoffs a fit reached."""
        return carrier.blend(panel.frame[self.base], prediction,
                             self.lam).where(prediction.notna())


def _training_frame(train: pd.DataFrame, columns: list[str], base: str) -> pd.DataFrame:
    """§2.3's residual target, derived on the training slice only.

    `y_resid = target_rank - rank_pct(base)`. Both terms are within-cutoff, so a
    slice carrying whole cutoffs gives identical values; computing it here keeps
    the panel free of a column no scorer should ever see.

    `rank_pct` of a centred rank is that rank again, so for `base = z__ret_12_1`
    this is bit-identical to V2.2-B's `target_rank - rank_pct(ret_12_1)`. That
    identity is what makes A-minus-V2.2-B one deleted column and nothing else, and
    `test_alpha_v2_3.py` asserts it rather than trusting this comment.
    """
    needed = list(dict.fromkeys(list(columns) + ["target_rank", base]))
    frame = train[needed].copy()
    frame[RESID_TARGET] = frame["target_rank"] - carrier.rank_pct(frame, base)
    return frame


ARMS = (
    Arm("V2.3-A", BASE_B1, B1_KEY,
        "V2.2-B's carrier with z__ret_12_1 deleted from the inputs. Tests whether "
        "the +0.00241 was diluted by the adjustment re-encoding its own base"),
    Arm("V2.3-B", BASE_B3, B3_KEY,
        "the same carrier based on Benchmark 3, residual taken against B3. lambda=0 "
        "is B3, so the incumbent becomes the null and G3 becomes a comparison "
        "against the arm's own base"),
)

RUNGS = (
    Arm("S1-A", BASE_B1, B1_KEY, "A's carrier on one input, z__ret_20d",
        is_arm=False, columns=(RUNG_COLUMN,)),
    Arm("S1-B", BASE_B3, B3_KEY, "B's carrier on one input, z__ret_20d",
        is_arm=False, columns=(RUNG_COLUMN,)),
)

RUNG_FOR_ARM = {"V2.3-A": "S1-A", "V2.3-B": "S1-B"}
BASE_FOR_ARM = {arm.name: arm.base for arm in ARMS}

# §5.1 — ties go to B, because a tie means B matched A's IC over the harder null.
SAFETY_ORDER = ("V2.3-B", "V2.3-A")


# ----------------------------------------------------------------------
# Running one arm or rung
# ----------------------------------------------------------------------

@dataclasses.dataclass
class Result:
    spec: Arm
    record: dict
    prediction: pd.Series
    final: pd.Series
    ic: pd.Series
    assessment: protocol.Assessment
    diagnostics: carrier.Diagnostics
    collinearity: carrier.Collinearity


def run_arm(spec: Arm, panel, calendar, quiet: bool = False) -> Result:
    missing = [c for c in spec.columns if c not in panel.frame.columns]
    if missing:
        raise SystemExit(f"{spec.name}: the panel has no column {missing}. The "
                         "pre-registered column list is not negotiable.")
    if spec.base in spec.columns:
        raise SystemExit(
            f"{spec.name}: its own base {spec.base} is among its inputs. That is the "
            "defect V2.3 exists to remove (V2_3_PREREGISTRATION.md §3).")

    print(f"\n=== {spec.name} — {spec.note}")
    print(f"    base `{spec.base}` (== {spec.benchmark}), {len(spec.columns)} inputs, "
          f"target `{RESID_TARGET}`, output base + {spec.lam:.2f}*u")

    started = time.time()
    run = walkforward.walk_forward(panel, calendar, list(spec.columns),
                                   fit_fn=spec.fitter(), name=spec.name,
                                   verbose=not quiet)
    elapsed = time.time() - started

    final = spec.score(panel, run.predictions)
    assessment = protocol.assess(panel, final, spec.name)
    ic = assessment.evaluation.ic.clean
    base = panel.frame[spec.base]
    u = carrier.rank_series(run.predictions)

    diagnostics = carrier.diagnose(final, panel.frame[MOMENTUM], spec.name)
    coll = carrier.collinearity(u, base, spec.name, spec.lam)
    violations = carrier.order_bound_violations(base.where(run.predictions.notna()),
                                                final, spec.lam)

    csum = coll.summary()
    print(f"    mean IC {assessment.evaluation.ic.mean:+.5f}  "
          f"hit {assessment.evaluation.ic.hit_rate:.1%}  "
          f"({assessment.evaluation.ic.n} cutoffs, {len(run.fits)} refits, {elapsed:.0f}s)")
    print(f"    H1b  mean|rho(u, base)| {_fmt(csum.get('mean_abs_rho'))}  "
          f"(signed {_fmt(csum.get('mean_signed_rho'))})  "
          f"effective lambda {_fmt(csum.get('effective_lambda'))} of {spec.lam:.2f}  "
          f"-> {'OK' if csum.get('mean_abs_rho', 1.0) <= H1B_CEILING else 'FAILS'}")
    print(f"    order-bound violations {violations}")

    record = assessment.record()
    record.update({
        "preregistration": PREREGISTRATION,
        "note": spec.note,
        "base_column": spec.base,
        "base_equals_benchmark": spec.benchmark,
        "n_inputs": len(spec.columns),
        "input_columns": list(spec.columns),
        "base_is_an_input": False,
        "train_target": f"{RESID_TARGET} = target_rank - rank_pct({spec.base})",
        "output_combination": f"base + {spec.lam:.2f}*rank(prediction)",
        "lambda": spec.lam,
        "scored_against": "alpha_5d",
        "is_arm": spec.is_arm,
        "seconds": round(elapsed, 1),
        "refits": run.fits,
        "carrier_diagnostics": diagnostics.summary(),
        "collinearity": csum,
        "order_bound_violations": int(violations),
        "gates_are_diagnostic_here": (
            "V2_3_PREREGISTRATION.md §6 gates the selected arm on development. The "
            "nine V2.1 criteria below are the same arithmetic on the same slice and "
            "decide nothing here; §8 keeps the exam sealed either way."),
    })
    record["diagnostic_gates_passed"] = record.pop("gates_passed")
    record["diagnostic_failed_gates"] = record.pop("failed_gates")

    return Result(spec, record, run.predictions, final, ic, assessment,
                  diagnostics, coll)


# ----------------------------------------------------------------------
# Scoring helpers
# ----------------------------------------------------------------------

def ic_of(panel, score: pd.Series, target: str = "alpha_5d") -> pd.Series:
    frame = panel.frame[[target]].copy()
    frame["prediction"] = score.reindex(frame.index)
    return stats.ic_by_cutoff(frame, "prediction", target).dropna()


def net_spread_of(panel, score: pd.Series, bps: float = COST_BPS) -> pd.Series:
    """Per-cutoff net quintile spread of a book built from `score`.

    Turnover comes from realised leg membership — `protocol.leg_membership` takes
    the top and bottom quintile *by this score* — so G6 charges the book for the
    trading the score actually causes, not for a proxy.
    """
    marks = panel.frame.copy()
    marks["prediction"] = score.reindex(marks.index)
    marks = marks[marks["prediction"].notna()]
    if marks.empty:
        return pd.Series(dtype=float)
    turns = protocol.turnover(marks, "prediction")
    spread = stats.quintile_spread(marks, "prediction", "alpha_5d")["spread"]
    total = turns["turnover_total"] if not turns.empty else pd.Series(dtype=float)
    return protocol.net_spread(spread, total)


def turnover_of(panel, score: pd.Series) -> pd.DataFrame:
    marks = panel.frame.copy()
    marks["prediction"] = score.reindex(marks.index)
    marks = marks[marks["prediction"].notna()]
    return protocol.turnover(marks, "prediction") if not marks.empty else pd.DataFrame()


def paired(left: pd.Series, right: pd.Series, name: str) -> dict:
    series = stats.paired_difference(left, right, name)
    # One bootstrap, reused. `Series.bootstrap_ci` runs 10,000 draws per call and
    # this function is called for every arm at every lambda.
    low, high = series.bootstrap_ci()
    finite = bool(np.isfinite(low) and np.isfinite(high))
    return {
        "what": name,
        "mean": _round(series.mean, 5),
        "ci": [_round(low, 5), _round(high, 5)],
        "half_width": _round((high - low) / 2.0, 5) if finite else None,
        "sd": _round(series.sd, 5),
        "n_cutoffs": series.n,
        "share_positive": _round(series.hit_rate, 4),
        "halves": _halves(series.clean),
        "excludes_zero": bool(series.n and finite and (low > 0 or high < 0)),
        # The gate's condition, in one place: positive mean AND an interval that
        # excludes zero from above. A positive mean with a CI spanning zero is the
        # shape V2.1-D had, and it is not a pass.
        "beats": bool(series.n and series.mean > 0 and finite and low > 0),
    }


def _halves(values: pd.Series) -> dict:
    clean = values.dropna().sort_index()
    middle = (len(clean) + 1) // 2
    out = {}
    for label, block in (("first", clean.iloc[:middle]), ("second", clean.iloc[middle:])):
        out[label] = {"n": int(len(block)),
                      "mean": _round(block.mean(), 5) if len(block) else None}
    return out


# ----------------------------------------------------------------------
# §5 eligibility
# ----------------------------------------------------------------------

def h1a(rung_ic: pd.Series, base_ic: pd.Series, rung: str) -> dict:
    """Carrier integrity, carried over from V2.2 §6.1 verbatim at -0.005."""
    series = stats.paired_difference(rung_ic, base_ic, f"{rung} IC - its S0 IC")
    low, high = series.bootstrap_ci()
    common = rung_ic.index.intersection(base_ic.index)
    return {
        "rung": rung,
        "criterion": "paired mean per-cutoff IC of the one-feature rung minus its own S0",
        "threshold": f">= {H1A_FLOOR}",
        "value": _round(series.mean, 5),
        "ci": [_round(low, 5), _round(high, 5)],
        "n_cutoffs": series.n,
        "rung_mean_ic_on_paired_cutoffs": _round(float(rung_ic.reindex(common).mean()), 5),
        "s0_mean_ic_on_paired_cutoffs": _round(float(base_ic.reindex(common).mean()), 5),
        "passed": bool(series.n and series.mean >= H1A_FLOOR),
    }


def h1b(coll: carrier.Collinearity) -> dict:
    """§5's new condition: the adjustment may not be a copy of its own base.

    Justified by what lambda must *mean*, not by any IC. Only the component of `u`
    orthogonal to the base can move the ranking in a way the base did not, and its
    share of `u`'s dispersion is sqrt(1 - rho^2). At rho = 0.90 the arm delivers
    >= 44% of its nominal lambda; at V2.2-B's 0.992 it delivered 12%. 0.90 is the
    point beyond which "lambda = 0.50" is a material misstatement of what the arm
    does.
    """
    summary = coll.summary()
    value = summary.get("mean_abs_rho")
    return {
        "criterion": "mean of |within-cutoff Spearman(u, base)| over scored cutoffs",
        "threshold": f"<= {H1B_CEILING}",
        "value": value,
        "signed_mean": summary.get("mean_signed_rho"),
        "share_of_cutoffs_above_ceiling": summary.get("share_abs_above_0.90"),
        "nominal_lambda": summary.get("nominal_lambda"),
        "effective_lambda": summary.get("effective_lambda"),
        "effective_share_of_nominal": summary.get("effective_share_of_nominal"),
        "n_cutoffs": summary.get("n_cutoffs"),
        "passed": bool(value is not None and value <= H1B_CEILING),
        "reference_v2_2_b": 0.9923,
    }


def eligibility(arm: str, integrity: dict, collinear: dict, n_scored: int) -> dict:
    enough = bool(n_scored >= MIN_SCORED_CUTOFFS)
    ok = bool(integrity["passed"] and collinear["passed"] and enough)
    return {
        "arm": arm,
        "h1a_carrier_integrity": integrity,
        "h1b_collinearity_ceiling": collinear,
        "h1c_scored_cutoffs": {"value": n_scored,
                               "threshold": f">= {MIN_SCORED_CUTOFFS}",
                               "passed": enough},
        "eligible": ok,
        "consequence": ("eligible for selection" if ok else
                        "carrier-defective: reported in full, not eligible for "
                        "selection whatever its IC (§5)"),
    }


def select_arm(records: dict[str, dict], eligible: dict[str, dict]) -> str | None:
    """§5.1: highest mean development IC among the eligible **arms**."""
    order = {name: i for i, name in enumerate(SAFETY_ORDER)}
    candidates = [n for n, r in records.items()
                  if r.get("is_arm") and eligible.get(n, {}).get("eligible")]
    if not candidates:
        return None

    def key(name: str):
        mean = records[name]["ic"]["mean"]
        mean = mean if mean is not None and np.isfinite(mean) else -9.0
        return (-mean, order.get(name, 99))

    return sorted(candidates, key=key)[0]


# ----------------------------------------------------------------------
# §6 the gate
# ----------------------------------------------------------------------

def gate(result: Result, panel, benchmark_ic: dict[str, pd.Series]) -> dict:
    """§6 G2-G6 for one arm. G2-G5 are V2.2 §6.3 verbatim; G6 is new."""
    ic = result.ic
    versus = {key: paired(ic, benchmark_ic[key].reindex(ic.index), f"{result.spec.name} - {key}")
              for key in GATE_BENCHMARKS}
    b1, b3 = versus[GATE_BENCHMARKS[0]], versus[GATE_BENCHMARKS[1]]

    # G6 — against the arm's OWN base, which is the book the tilt is meant to
    # improve. Charging it against a different benchmark would ask a different
    # question: whether the base is worth holding, not whether the tilt pays.
    base_score = panel.frame[result.spec.base].where(result.prediction.notna())
    arm_net = net_spread_of(panel, result.final).reindex(ic.index)
    base_net = net_spread_of(panel, base_score).reindex(ic.index)
    cost = paired(arm_net, base_net, f"{result.spec.name} net spread - base net spread")

    cost_sensitivity = {}
    for bps in COST_REPORTED_BPS:
        a = net_spread_of(panel, result.final, bps).reindex(ic.index)
        b = net_spread_of(panel, base_score, bps).reindex(ic.index)
        cost_sensitivity[f"{bps:g}bps"] = paired(a, b, f"net @{bps:g}bps")

    gates = {
        "G2_beats_12_1_momentum": {
            "threshold": "paired mean IC difference > 0, 95% CI excludes 0",
            "value": b1["mean"], "ci": b1["ci"], "passed": b1["beats"]},
        "G3_beats_regime_switched_momentum": {
            "threshold": "paired mean IC difference > 0, 95% CI excludes 0",
            "value": b3["mean"], "ci": b3["ci"], "passed": b3["beats"]},
        "G4_breadth": {
            "threshold": f"> 0 on >= {BREADTH_FLOOR:.0%} of cutoffs, both benchmarks",
            "value": {"vs_b1": b1["share_positive"], "vs_b3": b3["share_positive"]},
            "passed": bool(b1["share_positive"] is not None
                           and b3["share_positive"] is not None
                           and b1["share_positive"] >= BREADTH_FLOOR
                           and b3["share_positive"] >= BREADTH_FLOOR)},
        "G5_stability": {
            "threshold": "paired mean > 0 in each chronological half, both benchmarks",
            "value": {"vs_b1": b1["halves"], "vs_b3": b3["halves"]},
            "passed": bool(_both_halves_positive(b1) and _both_halves_positive(b3))},
        "G6_cost": {
            "threshold": (f"net quintile spread minus the arm's own base's net spread "
                          f"> 0, 95% CI excludes 0, at {COST_BPS:g} bps one-way"),
            "value": cost["mean"], "ci": cost["ci"], "passed": cost["beats"],
            "sensitivity": cost_sensitivity},
    }
    passed = all(entry["passed"] for entry in gates.values())
    return {
        "arm": result.spec.name,
        "gates": gates,
        "passed": passed,
        "versus_benchmarks": versus,
        "cost_versus_own_base": cost,
        "consequence": (
            "every gate holds — §8 applies: V2.3 stops and reports, the V2.1 exam "
            "stays sealed, and V2_3_EXAM_DECISION.md must be written before any exam "
            "date is touched" if passed else
            "the gate is closed. §9: V2.3 stops and reports the failure mechanism; "
            "it does not propose a V2.4. Production stays at weight 0 / HOLD"),
    }


def _both_halves_positive(entry: dict) -> bool:
    h = entry.get("halves") or {}
    first, second = h.get("first") or {}, h.get("second") or {}
    return bool(first.get("n") and second.get("n")
                and (first.get("mean") or 0) > 0 and (second.get("mean") or 0) > 0)


# ----------------------------------------------------------------------
# §4 diagnostics that gate nothing
# ----------------------------------------------------------------------

def lambda_curve(panel, spec: Arm, prediction: pd.Series,
                 benchmark_ic: dict[str, pd.Series]) -> dict:
    """The arm's carrier at four lambdas. Reported; never selected on.

    No refit — lambda is an output-combination parameter, so one set of predictions
    serves every point. §9 names re-choosing lambda as a forbidden response.
    """
    base = panel.frame[spec.base]
    mask = prediction.notna()
    out = {}
    for lam in LAMBDA_CURVE:
        final = carrier.blend(base, prediction, lam).where(mask)
        ic = ic_of(panel, final)
        out[f"{lam:.2f}"] = {
            "mean_ic": _round(float(ic.mean()), 5),
            "n_cutoffs": int(len(ic)),
            "vs_b1": paired(ic, benchmark_ic[B1_KEY].reindex(ic.index), "vs b1")["mean"],
            "vs_b3": paired(ic, benchmark_ic[B3_KEY].reindex(ic.index), "vs b3")["mean"],
            "turnover": _round(float(turnover_of(panel, final)["turnover_total"].mean()), 4),
            "net_spread_5bps": _round(float(net_spread_of(panel, final).mean()), 5),
            "order_bound_violations": int(
                carrier.order_bound_violations(base.where(mask), final, lam)),
            "is_the_arm": lam == spec.lam,
        }
    return out


def _noise(panel, mask: pd.Series, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(size=len(panel.frame)),
                     index=panel.frame.index).where(mask)


def noise_control(panel, spec: Arm, mask: pd.Series, cache: dict) -> dict:
    """§4: a bounded blend must DESTROY IC when the adjustment is uninformative.

    The direct test that the construction cannot manufacture IC through
    tie-breaking or rank mechanics.

    **Two versions are reported, and the reason is a defect in §4 found when the
    control first ran.** §4 specifies one seeded draw and a comparison of *means*.
    That statistic has no power: the noise blend and the base are highly correlated,
    so the sampling spread of a single draw's mean IC (sd ≈ 0.0014 at lambda = 0.50,
    measured below) is larger than the effect being looked for, and the difference
    was never paired. On the pre-registered seed the blend appeared to *gain*
    +0.0012 — with its own paired CI spanning zero — which under §4's literal
    wording is a stop condition. It is a fluctuation.

    So the single pre-registered draw is reported **verbatim, gain and all**, and
    the verdict is taken from a properly powered version: `NOISE_DRAWS` independent
    draws at the arm's own lambda, differenced against the base per cutoff. That
    version is an addition made **after the first fit** and is logged as such in
    `V2_3_EXPERIMENT_LOG.md`. It makes the control stricter, not weaker — a
    construction that manufactured IC would show it on most draws, and the stop
    condition below is exactly that.

    Cached by (base, scored-cutoff count): the control depends on the base and the
    sample, not on the model, so two arms sharing a base share the answer.
    """
    key = (spec.base, int(mask.sum()))
    if key in cache:
        return cache[key]

    base = panel.frame[spec.base]
    base_ic = ic_of(panel, base.where(mask))
    base_mean = _round(float(base_ic.mean()), 5)

    # (i) §4 as written: one seeded draw. Reported exactly, including its gain.
    single = _noise(panel, mask, NOISE_SEED)
    at_lambda = {}
    for lam in (0.25, 0.50, 1.00):
        ic = ic_of(panel, carrier.blend(base, single, lam).where(mask))
        entry = paired(ic, base_ic.reindex(ic.index), f"noise @{lam:.2f} - base")
        at_lambda[f"{lam:.2f}"] = {
            "mean_ic": _round(float(ic.mean()), 5),
            "paired_vs_base": entry["mean"],
            "ci": entry["ci"],
            "gained_on_base": bool((entry["mean"] or 0.0) > 0),
            "gain_is_significant": bool(entry["beats"]),
        }

    # (ii) the powered version, at the arm's lambda.
    diffs = []
    for draw in range(NOISE_DRAWS):
        ic = ic_of(panel, carrier.blend(base, _noise(panel, mask, NOISE_SEED + 1 + draw),
                                        spec.lam).where(mask))
        diffs.append(float((ic - base_ic.reindex(ic.index)).mean()))
    array = np.array(diffs, dtype=float)
    share_above = float((array > 0).mean())

    out = {
        "base_mean_ic": base_mean,
        "preregistered_single_draw": {
            "seed": NOISE_SEED,
            "at_lambda": at_lambda,
            "note": ("§4 as written. Under-powered: one draw, unpaired means. Reported "
                     "verbatim because the pre-registration asked for it."),
        },
        "powered": {
            "draws": NOISE_DRAWS,
            "lambda": spec.lam,
            "mean_paired_difference": _round(float(array.mean()), 5),
            "sd_across_draws": _round(float(array.std(ddof=1)), 5),
            "min": _round(float(array.min()), 5),
            "max": _round(float(array.max()), 5),
            "share_of_draws_above_base": _round(share_above, 4),
            "added_after_the_first_fit": True,
        },
        # The stop condition, on the powered statistic: a construction that
        # manufactured IC from rank mechanics would gain on most draws, not on one.
        "destroys_ic": bool(share_above <= 0.5 and array.mean() < 0),
        "verdict": ("the bounded blend destroys IC when the adjustment is "
                    "uninformative, as it must" if share_above <= 0.5 and array.mean() < 0
                    else "the blend gains on the base across independent draws — the "
                         "construction may be manufacturing IC and V2.3 stops"),
    }
    cache[key] = out
    return out


def bear_decomposition(ic: pd.Series, benchmark_ic: dict[str, pd.Series],
                       trend: pd.Series) -> dict:
    """§4: B3 is bit-identical to B1 outside BEAR_TREND, so `vs B3` lives there.

    Verified on the panel rather than assumed: if a future regime definition made
    B3 differ off bear, this decomposition would stop summing and the note below
    would be wrong.
    """
    out = {}
    for key in GATE_BENCHMARKS:
        diff = (ic - benchmark_ic[key].reindex(ic.index)).dropna()
        tags = trend.reindex(diff.index)
        out[key] = {"overall": _round(float(diff.mean()), 5),
                    "by_trend": {str(t): {"n": int((tags == t).sum()),
                                          "mean": _round(float(diff[tags == t].mean()), 5)}
                                 for t in sorted(tags.dropna().unique())}}
    b1_off = (benchmark_ic[B1_KEY] - benchmark_ic[B3_KEY]).reindex(ic.index)
    off_bear = b1_off[trend.reindex(ic.index) != BEAR].abs().max()
    out["b3_identical_to_b1_off_bear"] = bool(np.isfinite(off_bear) and off_bear < 1e-12)
    return out


def power(paired_entry: dict, n_exam: int = EXAM_CUTOFFS_FOR_POWER) -> dict:
    """§6.2 — reported before the verdict so a power failure is legible as one."""
    hw, n = paired_entry.get("half_width"), paired_entry.get("n_cutoffs") or 0
    if hw is None or not n:
        return {"half_width_development": None}
    scaled = hw * np.sqrt(n / n_exam)
    mean = abs(paired_entry.get("mean") or 0.0)
    return {
        "half_width_development": hw,
        "n_development_cutoffs": n,
        f"half_width_scaled_to_{n_exam}_cutoffs": _round(scaled, 5),
        "minimum_detectable_advantage_on_development": hw,
        "cutoffs_needed_to_resolve_the_observed_effect": (
            int(round(n * (hw / mean) ** 2)) if mean > 0 else None),
    }


# ----------------------------------------------------------------------

def _fmt(value) -> str:
    return "    n/a" if value is None else f"{value:+.5f}"


def _fmt_ci(ci) -> str:
    if not ci or ci[0] is None:
        return "n/a"
    return f"[{ci[0]:+.5f}, {ci[1]:+.5f}]"


def _round(value, places: int):
    if value is None:
        return None
    value = float(value)
    return None if not np.isfinite(value) else round(value, places)


def widen(panel):
    """Add the §2.2 `z__` columns and the §2.1 B3 base. Stock-level only, plus B3."""
    frame, added = carrier.add_rank_columns(panel.frame, RANK_TRANSFORMED)
    expected = [f"{carrier.RANK_PREFIX}{c}" for c in RANK_TRANSFORMED]
    if list(added) != expected:
        raise RuntimeError(f"rank transform produced {added}, expected {expected}")

    scores = protocol.benchmark_scores(frame, panel.regimes)
    if B3_KEY not in scores.columns:
        raise SystemExit("the panel cannot produce b3_regime_switched — V2.3-B's base "
                         "does not exist and the study cannot run")
    frame[BASE_B3] = carrier.rank_series(scores[B3_KEY])
    return dataclasses.replace(panel, frame=frame), scores


def check_asymmetry(panel) -> dict:
    """§2.2's design decision, measured on every development cutoff."""
    context = carrier.constant_within_cutoff(panel.frame, MARKET_CONTEXT)
    stock = carrier.constant_within_cutoff(panel.frame, RANK_TRANSFORMED)
    varying = sorted(c for c, k in context.items() if not k)
    constant = sorted(c for c, k in stock.items() if k)
    if varying:
        raise SystemExit(f"these MARKET_CONTEXT columns vary within a cutoff: {varying}")
    if constant:
        raise SystemExit(f"these stock-level columns are cutoff-constant: {constant}")
    return {"market_context_columns": len(MARKET_CONTEXT),
            "all_market_context_cutoff_constant": True,
            "market_context_rank_transformed": False,
            "rank_transformed_stock_level_columns": len(RANK_TRANSFORMED),
            "all_varying": True,
            "note": ("§2.2: a within-cutoff rank of a cutoff-constant column is 0.5 for "
                     "every name. Pre-registered asymmetry, unchanged from V2.2 §2.1.")}


def frozen_v2_2_b():
    """V2.2-B's frozen series, read for the paired contrast. Never written to."""
    json_path, pickle_path = ladder_v2_2.JSON_PATH, ladder_v2_2.PICKLE_PATH
    if not (json_path.exists() and pickle_path.exists()):
        return None
    record = json.loads(json_path.read_text(encoding="utf-8"))
    blob = pd.read_pickle(pickle_path)
    arm = record.get("arms", {}).get("V2.2-B")
    if arm is None or "V2.2-B" not in blob.get("ic_series", {}):
        return None
    return {"mean_ic": arm["ic"]["mean"],
            "collinearity_rho": 0.9923,
            "ic_series": blob["ic_series"]["V2.2-B"],
            "prediction": blob["predictions"]["V2.2-B"]}


# ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="V2.3 ladder — development only")
    parser.add_argument("--only", nargs="*", default=None,
                        help="run a subset of the arms. The family size stays 2 and "
                             "the rungs still run.")
    parser.add_argument("--quiet", action="store_true", help="suppress per-refit lines")
    args = parser.parse_args(argv)

    for forbidden in ("v2_1_exam_predictions.json", "v2_3_exam_predictions.json"):
        if (OUT_DIR / forbidden).exists():
            raise SystemExit(
                f"out/{forbidden} exists. §1.1 of V2_3_PREREGISTRATION.md says it must "
                "not come into existence — stop and explain it in "
                "V2_3_EXPERIMENT_LOG.md before running anything.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, _dev, _exam = build_panel.load()
    exam_set = examset.load()

    # §1.2 — the one line that keeps the exam sealed. `development_only` slices to
    # the frozen development list and then asserts no exam cutoff survived.
    panel = examset.development_only(panel, exam_set)
    calendar = pitdata.load_calendar()

    print(f"protocol   V2.3, exam digest {exam_set.digest[:16]}… (not read below)")
    print(f"panel      {len(panel.frame):,} rows  ·  {len(panel.cutoffs)} development "
          f"cutoffs  ·  {panel.cutoffs[0].date()} .. {panel.cutoffs[-1].date()}")
    print(f"arms       {len(ARMS)} pre-registered, family size k={FAMILY_SIZE}; "
          f"{len(RUNGS)} rungs, none selectable")
    print(f"inputs     {len(INPUT_COLUMNS)} columns = V2.1-C's 35 minus the base")
    print(f"see        {PREREGISTRATION}")

    asymmetry = check_asymmetry(panel)
    print(f"§2.2       {asymmetry['market_context_columns']} context columns "
          f"cutoff-constant (un-ranked), "
          f"{asymmetry['rank_transformed_stock_level_columns']} stock-level ranked")

    panel, scores = widen(panel)
    trend = protocol._trend_by_row(panel.frame, panel.regimes).groupby(level=0).first()

    # --- §2.1 the two identity checks, before anything is fitted.
    benchmark_ic = {key: ic_of(panel, scores[key]) for key in (B1_KEY, B3_KEY)}
    identities = {}
    for base, key in ((BASE_B1, B1_KEY), (BASE_B3, B3_KEY)):
        base_ic = ic_of(panel, panel.frame[base])
        gap = float((base_ic - benchmark_ic[key].reindex(base_ic.index)).abs().max())
        if not (gap < 1e-12 and len(base_ic) == len(benchmark_ic[key])):
            raise SystemExit(
                f"§2.1 identity failed: ranking {base} does not reproduce {key} "
                f"(max |IC difference| {gap:.3e} over {len(base_ic)} vs "
                f"{len(benchmark_ic[key])} cutoffs). The pipeline is wrong; V2.3 stops.")
        identities[base] = {"equals": key, "mean_ic": _round(float(base_ic.mean()), 5),
                            "n_cutoffs": int(len(base_ic)),
                            "max_abs_ic_difference": gap, "rank_identical": True}
        print(f"§2.1       {base} == {key} exactly: mean IC "
              f"{base_ic.mean():+.5f} over {len(base_ic)} cutoffs "
              f"(max |diff| {gap:.1e})")

    wanted = set(args.only) if args.only else None
    if wanted and (unknown := wanted - {a.name for a in ARMS}):
        raise SystemExit(f"no such arm: {sorted(unknown)}")

    results: dict[str, Result] = {}
    for spec in RUNGS:
        results[spec.name] = run_arm(spec, panel, calendar, quiet=args.quiet)
    for spec in ARMS:
        if wanted is not None and spec.name not in wanted:
            continue
        results[spec.name] = run_arm(spec, panel, calendar, quiet=args.quiet)

    # --- §5 H1a over the rungs.
    print("\n=== §5 H1a carrier integrity — does the carrier destroy its own base?")
    integrity = {}
    for arm in ARMS:
        rung = RUNG_FOR_ARM[arm.name]
        if rung not in results:
            continue
        base_ic = ic_of(panel, panel.frame[arm.base])
        verdict = h1a(results[rung].ic, base_ic, rung)
        integrity[rung] = verdict
        print(f"    {rung:<6} {_fmt(verdict['rung_mean_ic_on_paired_cutoffs'])} vs its S0 "
              f"{_fmt(verdict['s0_mean_ic_on_paired_cutoffs'])} on the same "
              f"{verdict['n_cutoffs']} cutoffs -> paired {_fmt(verdict['value'])} "
              f"CI {_fmt_ci(verdict['ci'])}  "
              f"{'OK' if verdict['passed'] else f'FAILS H1a (>= {H1A_FLOOR})'}")

    # --- §5 eligibility, then §5.1 selection, then §6 the gate. In that order.
    arm_records = {n: r.record for n, r in results.items() if r.spec.is_arm}
    eligible = {}
    for name in arm_records:
        rung = RUNG_FOR_ARM[name]
        eligible[name] = eligibility(
            name,
            integrity.get(rung, {"rung": rung, "passed": False, "value": None,
                                 "ci": [None, None], "n_cutoffs": 0,
                                 "criterion": "not run", "threshold": f">= {H1A_FLOOR}"}),
            h1b(results[name].collinearity),
            results[name].assessment.evaluation.ic.n)

    print("\n=== §5 eligibility")
    for name, v in eligible.items():
        print(f"    {name:<8} H1a {_fmt(v['h1a_carrier_integrity']['value'])}  "
              f"H1b mean|rho| {_fmt(v['h1b_collinearity_ceiling']['value'])} "
              f"(<= {H1B_CEILING})  H1c {v['h1c_scored_cutoffs']['value']} cutoffs  -> "
              f"{'ELIGIBLE' if v['eligible'] else 'CARRIER-DEFECTIVE'}")

    holm = stats.holm_bonferroni({n: r["ic"]["p_boot"] for n, r in arm_records.items()})
    for name, verdict in holm.items():
        if name in arm_records:
            arm_records[name]["multiplicity_on_development"] = verdict

    # --- §4 diagnostics for every arm, before any verdict is read.
    curves, noise, bears, powers, gates = {}, {}, {}, {}, {}
    noise_cache: dict = {}
    for name, result in results.items():
        curves[name] = lambda_curve(panel, result.spec, result.prediction, benchmark_ic)
        noise[name] = noise_control(panel, result.spec, result.prediction.notna(),
                                    noise_cache)
        bears[name] = bear_decomposition(result.ic, benchmark_ic, trend)
        if not noise[name]["destroys_ic"]:
            raise SystemExit(
                f"§4 noise control failed for {name} over {NOISE_DRAWS} draws: "
                f"{noise[name]['verdict']}")

    print("\n=== §4 noise control — the blend must destroy IC when the adjustment is noise")
    for name in results:
        entry = noise[name]
        single = entry["preregistered_single_draw"]["at_lambda"]["0.50"]
        powered = entry["powered"]
        print(f"    {name:<8} base {_fmt(entry['base_mean_ic'])}  |  pre-registered single "
              f"draw @0.50 {_fmt(single['paired_vs_base'])} CI {_fmt_ci(single['ci'])}"
              f"{'  (a GAIN, not significant)' if single['gained_on_base'] else ''}")
        print(f"    {'':<8} powered ({powered['draws']} draws) paired "
              f"{_fmt(powered['mean_paired_difference'])}  sd {powered['sd_across_draws']:.5f}  "
              f"range [{powered['min']:+.5f}, {powered['max']:+.5f}]  "
              f"{powered['share_of_draws_above_base']:.0%} of draws above base  -> "
              f"{'destroys IC' if entry['destroys_ic'] else 'FAILS'}")

    for name, result in results.items():
        if not result.spec.is_arm:
            continue
        gates[name] = gate(result, panel, benchmark_ic)
        powers[name] = {k: power(v) for k, v in gates[name]["versus_benchmarks"].items()}
        powers[name]["own_base_net_spread"] = power(gates[name]["cost_versus_own_base"])
        arm_records[name]["gate"] = gates[name]
        arm_records[name]["power"] = powers[name]
        arm_records[name]["lambda_curve"] = curves[name]
        arm_records[name]["noise_control"] = noise[name]
        arm_records[name]["bear_decomposition"] = bears[name]

    print("\n=== §6.2 measured power (reported before the verdict)")
    for name in arm_records:
        for key, entry in powers[name].items():
            print(f"    {name:<8} {key:<22} half-width {_fmt(entry.get('half_width_development'))}"
                  f"  -> @72 {_fmt(entry.get('half_width_scaled_to_72_cutoffs'))}"
                  f"  needs ~{entry.get('cutoffs_needed_to_resolve_the_observed_effect')} cutoffs")

    selected = select_arm(arm_records, eligible)
    verdict = (gates[selected] if selected else
               {"arm": None, "passed": False, "gates": {},
                "consequence": "no eligible arm was run; nothing to gate"})

    print(f"\n=== §5.1 selected arm: {selected or 'none'} "
          f"(highest mean development IC among the eligible arms)")
    print(f"=== §6 gate: {'PASSED' if verdict['passed'] else 'CLOSED'}")
    for key, entry in verdict.get("gates", {}).items():
        value = entry["value"]
        shown = _fmt(value) if isinstance(value, (int, float)) or value is None else str(value)
        print(f"    {key:<36} {'pass' if entry['passed'] else 'fail'}  {shown}"
              + (f"  CI {_fmt_ci(entry.get('ci'))}" if entry.get("ci") else ""))
    print(f"           {verdict['consequence']}")

    # --- the central mechanistic contrast: A minus V2.2-B is one deleted column.
    reference = frozen_v2_2_b()
    contrast = None
    if reference is not None and "V2.3-A" in results:
        a = results["V2.3-A"]
        contrast = {
            "what": ("V2.3-A minus V2.2-B, paired per cutoff. The two differ by exactly "
                     "one input column (z__ret_12_1) — same base, same target, same "
                     "learner, same lambda, same cutoffs."),
            "v2_2_b_mean_ic": reference["mean_ic"],
            "v2_3_a_mean_ic": _round(float(a.ic.mean()), 5),
            "paired": paired(a.ic, reference["ic_series"].reindex(a.ic.index),
                             "V2.3-A IC - V2.2-B IC"),
            "collinearity_v2_2_b_mean_abs_rho": reference["collinearity_rho"],
            "collinearity_v2_3_a_mean_abs_rho": a.collinearity.summary().get("mean_abs_rho"),
            "effective_lambda_v2_2_b": _round(
                LAMBDA * np.sqrt(max(0.0, 1 - reference["collinearity_rho"] ** 2)), 4),
            "effective_lambda_v2_3_a": a.collinearity.summary().get("effective_lambda"),
        }
        print("\n=== the collinearity contrast: V2.3-A minus V2.2-B (one deleted column)")
        print(f"    mean|rho(u, base)|   V2.2-B {contrast['collinearity_v2_2_b_mean_abs_rho']:.4f}"
              f"  ->  V2.3-A {contrast['collinearity_v2_3_a_mean_abs_rho']:.4f}")
        print(f"    effective lambda     V2.2-B {contrast['effective_lambda_v2_2_b']:.4f}"
              f"  ->  V2.3-A {contrast['effective_lambda_v2_3_a']:.4f}  (nominal {LAMBDA:.2f})")
        print(f"    mean IC              V2.2-B {contrast['v2_2_b_mean_ic']:+.5f}"
              f"  ->  V2.3-A {contrast['v2_3_a_mean_ic']:+.5f}"
              f"  paired {_fmt(contrast['paired']['mean'])} "
              f"CI {_fmt_ci(contrast['paired']['ci'])}")

    record = {
        "protocol": "V2.3",
        "stage": "bounded-adjustment ladder / development",
        "preregistration": PREREGISTRATION,
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "exam_set_digest": exam_set.digest,
        "exam_predictions_exist": False,
        "exam_may_be_opened": False,
        "development_cutoffs": len(panel.cutoffs),
        "rows": int(len(panel.frame)),
        "first_cutoff": str(panel.cutoffs[0].date()),
        "last_cutoff": str(panel.cutoffs[-1].date()),
        "refit_sessions": walkforward.REFIT_SESSIONS,
        "min_train_cutoffs": walkforward.MIN_TRAIN_CUTOFFS,
        "family_size": FAMILY_SIZE,
        "lambda": LAMBDA,
        "learner_params": dict(models.MODEL_A_PARAMS),
        "input_columns": list(INPUT_COLUMNS),
        "n_inputs": len(INPUT_COLUMNS),
        "rank_transform_asymmetry": asymmetry,
        "base_identities": identities,
        "benchmark_mean_ic": {k: _round(float(v.mean()), 5) for k, v in benchmark_ic.items()},
        "h1a_carrier_integrity": integrity,
        "arms": arm_records,
        "rungs": {n: r.record for n, r in results.items() if not r.spec.is_arm},
        "eligibility": eligible,
        "holm_bonferroni_on_development": holm,
        "selected_arm": selected,
        "gate": verdict,
        "lambda_curves": curves,
        "lambda_note": ("§1.7: lambda = 0.50 is carried over from V2.2 §3.2 with its "
                        "original neutral-prior argument and is NOT re-derived from "
                        "V2.2's curve. No lambda variant is an arm; promoting one is "
                        "forbidden by §9."),
        "noise_controls": noise,
        "bear_decomposition": bears,
        "collinearity_contrast_with_v2_2_b": contrast,
        "regime_note": (
            "§7: diagnostic only. May not select an arm, explain a failure, restrict a "
            "conclusion to a bucket or justify an interaction. For V2.3-B a bear "
            "concentration is inherited from B3's own switch rather than learned, and "
            "the report must separate the two."),
        "exam_note": (
            "§8: the V2.1 exam is not opened by this stage even if every gate passes. "
            "V2_3_EXAM_DECISION.md must be written first and must answer to the "
            "corrected resolution figures (~0.0034 against B1 for a B1-bounded arm, "
            "~0.0074 against B3 for a B3-bounded one) and to the fact that the frozen "
            "exam holds 10 BEAR_TREND cutoffs of 72, so G3 there would rest on 10 dates."),
        "production_weight": 0.0,
        "production_weight_note": (
            "Unchanged and not a result of this stage. §1.4 fixes it at 0 / HOLD; "
            "alpha/adapter.py is not modified and this module does not import it."),
    }
    JSON_PATH.write_text(json.dumps(develop._jsonable(record), indent=2), encoding="utf-8")
    pd.to_pickle({
        "ic_series": {n: r.ic for n, r in results.items()},
        "benchmark_ic": benchmark_ic,
        "predictions": {n: r.prediction.dropna() for n, r in results.items()},
        "final_scores": {n: r.final.dropna() for n, r in results.items()},
        "collinearity": {n: r.collinearity.per_cutoff for n, r in results.items()},
        "diagnostics": {n: r.diagnostics.per_cutoff for n, r in results.items()},
    }, PICKLE_PATH)
    print(f"\nfroze      {JSON_PATH}")
    print(f"froze      {PICKLE_PATH}")


if __name__ == "__main__":
    main()
