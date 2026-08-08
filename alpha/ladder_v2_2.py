"""V2.2 — change the carrier and nothing else. Development cutoffs only.

`V2_2_PREREGISTRATION.md` in code. `alpha/ladder.py` and `alpha/develop.py` are
left untouched: they record finished experiments, and rewriting either to also
mean V2.2 would make the three indistinguishable in a diff a year from now. The
feature lists are *imported* from `ladder.py` rather than retyped, so "exactly
V2.1-C's 35 columns" is enforced by the import graph instead of by a promise.

The defect V2.2 exists to fix, measured on V2.1's own development set:

    rank the cross-section by ret_12_1 directly        mean IC  +0.02115
    fit a GBM on ret_12_1 alone, then rank its output  mean IC  +0.00053

Every V2 and V2.1 arm passed its factors through that second path. §2 names the
four steps between a raw feature and a position in the ranking — input transform,
training target, output combination, rank — and the three arms fix three of them
in structurally different ways:

    V2.2-A   rank-preserving input.  z__ of the 9 stock-level columns, rank
             target, model output ranked. Isolates the *input* against V2.1-D,
             which was the same 35 columns and the same rank target on raw levels.
    V2.2-B   factor plus bounded learned adjustment. Residual target, and
             `final = z__ret_12_1 + lambda * u`. At lambda = 0.5 a wholesale sign
             inversion of momentum is impossible by construction (§3.2), not by
             hope; `carrier.order_bound_violations` proves it on the output.
    V2.2-C   contextual momentum with no sign reversal. `monotonic_cst = +1` on
             the momentum rank, 0 on the other 34 columns.

Three properties of this file matter more than the rest of it.

**It cannot see the exam.** Cutoffs come from `examset.development_only()`, which
slices to the frozen development list and then asserts no exam cutoff survived.
`walk_forward` trains out of that panel's own cutoffs, so no exam date is a
training candidate at any refit for any arm or rung.

**The rungs and the grid diagnose; they never choose.** §4 says so and §6.4 puts
the price on breaking it: the Holm family is the k=3 arms, and promoting a rung or
a lambda variant would make it 5. `select_arm` reads `ARMS` and nothing else.

**Selection runs before the gate.** As in V2.1: the arm is chosen on mean
development IC among the *eligible* arms, and only then asked whether it beat the
benchmarks, so the choice cannot be made by the gate.

Run:  python -m alpha.ladder_v2_2                # everything
      python -m alpha.ladder_v2_2 --only V2.2-B  # one arm, grid and rungs still run
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

from . import (build_panel, carrier, develop, examset, ladder, models, pitdata,
               protocol, stats, walkforward)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
JSON_PATH = OUT_DIR / "v2_2_development.json"
PICKLE_PATH = OUT_DIR / "v2_2_development.pkl"

PREREGISTRATION = "alpha/V2_2_PREREGISTRATION.md"
FAMILY_SIZE = 3                     # §6.4 — fixed before the first fit, not after

# ----------------------------------------------------------------------
# §3 — the columns. Imported from the V2.1 ladder, not retyped: the arms must be
# "exactly V2.1-C's 35 columns", and a copy of a list is a thing that drifts.
# ----------------------------------------------------------------------

BASE = "ret_12_1"
Z_BASE = f"{carrier.RANK_PREFIX}{BASE}"

# The 9 stock-level columns that get the §2.1 rank transform: momentum plus the
# eight V2.1-C added. They vary across the cross-section, so a within-cutoff rank
# is meaningful for them.
STOCK_LEVEL = ladder.MOMENTUM + ladder.STOCK_LEVEL

# The 26 columns that take one value for the whole cross-section at a cutoff.
# §2.1: these are deliberately NOT rank-transformed — a within-cutoff rank would
# map every name to 0.5 and annihilate them. They pass through as raw levels and
# the tree splits on them *across* cutoffs, which is the only way a
# cutoff-constant column can carry information at all.
MARKET_CONTEXT = ladder.MARKET_CONTEXT

RANKED_STOCK_LEVEL = tuple(f"{carrier.RANK_PREFIX}{c}" for c in STOCK_LEVEL)
ARM_COLUMNS = RANKED_STOCK_LEVEL + MARKET_CONTEXT           # 35

# §3.2 — the training target for arm B, derived on the training slice only.
RESID_TARGET = "y_resid"

# §3.2 — fixed here, before any V2.2 number exists. An equal-weight blend is the
# neutral prior between a factor with a known ~+0.021 out-of-sample IC and a
# learned tilt of unknown value.
LAMBDA = 0.50
# Reported as a sensitivity curve. NOT arms, and not re-selectable: §3.2 says in
# terms that if 0.25 or 1.00 scores better than 0.50 that is reported and 0.50
# stays the arm.
LAMBDA_CURVE = (0.00, 0.25, 0.50, 1.00)

# §6.1 — the two eligibility conditions, both fixed before the first fit.
G1_FLOOR = -0.005
MIN_SCORED_CUTOFFS = 200

# §6.3 — G4's breadth floor.
BREADTH_FLOOR = 0.55

# §6.3 — the two benchmarks the selected arm has to beat. B3 is a *gate* in V2.2
# where V2.1 only reported it: on V2.1's development set the hand-specified rule
# scored +0.02836 with the only benchmark CI excluding zero, so it is the real
# incumbent.
GATE_BENCHMARKS = ("b1_momentum_12_1", "b3_regime_switched")


# ----------------------------------------------------------------------
# One carrier = one path from raw feature to ranked position
# ----------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Carrier:
    """A column list, a training target, an output combination, and nothing else.

    Every field that is not one of those four is inherited from V2.1-C/D
    unchanged — learner, hyperparameters, walk-forward, purge, embargo, cutoff
    grid, scoring target. That is what makes a V2.2-minus-V2.1 difference
    attributable to the carrier: the carrier is the only thing that differs.
    """

    name: str
    columns: tuple[str, ...]
    train_target: str
    combination: str                # "prediction" | "blend"
    monotone: str | None            # column constrained non-decreasing, or None
    note: str
    lam: float = 0.0
    arm: bool = False               # §6.2 — eligible to be *selected*

    def fitter(self):
        target, monotone = self.train_target, self.monotone

        def fit(train: pd.DataFrame, columns: list[str]) -> models.Fit | None:
            frame, column = _training_frame(train, columns, target)
            if monotone is not None:
                return carrier.fit_monotone(frame, list(columns), column, monotone)
            return models.fit_model_a(frame, list(columns), target=column)

        return fit

    def score(self, panel, prediction: pd.Series) -> pd.Series:
        """§3 output combination: the number that actually gets ranked."""
        if self.combination != "blend":
            return prediction
        # Masked to the cutoffs the model actually predicted. Without the mask,
        # lambda = 0 would silently score the ~60 warm-up cutoffs no fit ever
        # reached, and the lambda curve would compare different samples.
        return carrier.blend(panel.frame[Z_BASE], prediction,
                             self.lam).where(prediction.notna())


def _training_frame(train: pd.DataFrame, columns: list[str],
                    target: str) -> tuple[pd.DataFrame, str]:
    """The training slice and the name of the column to regress onto.

    §3.2's residual target is computed **here**, from the training slice, rather
    than added to the panel once: `y_resid = target_rank - rank_pct(ret_12_1)`.
    Both terms are within-cutoff quantities, so a slice that carries whole
    cutoffs gives the identical number either way — but computing it on the slice
    is the version that stays correct if a future caller hands over a subset, and
    it keeps the panel free of a column no scorer should see.
    """
    if target != RESID_TARGET:
        return train, target
    needed = list(dict.fromkeys(list(columns) + ["target_rank", BASE]))
    frame = train[needed].copy()
    frame[RESID_TARGET] = frame["target_rank"] - carrier.rank_pct(frame, BASE)
    return frame, RESID_TARGET


# --- §3 the three arms. k = 3, fixed now.

ARMS = (
    Carrier("V2.2-A", ARM_COLUMNS, "target_rank", "prediction", None,
            "rank-preserving input: z__ of the 9 stock-level columns + 26 raw "
            "context, trained on the within-cutoff rank. Isolates the input side "
            "of the carrier against V2.1-D, which was the same 35 columns and the "
            "same target on raw levels",
            arm=True),
    Carrier("V2.2-B", ARM_COLUMNS, RESID_TARGET, "blend", None,
            "factor plus bounded learned adjustment: residual target, "
            "final = z__ret_12_1 + 0.50 * u. The model may tilt momentum, never "
            "replace it — §3.2's order bound makes an inversion impossible",
            lam=LAMBDA, arm=True),
    Carrier("V2.2-C", ARM_COLUMNS, "target_rank", "prediction", Z_BASE,
            "contextual momentum with no sign reversal: monotonic_cst = +1 on the "
            "momentum rank, 0 on the other 34. Context may flatten or steepen the "
            "momentum slope, never reverse it",
            arm=True),
)

# --- §4.1 the mandatory one-feature sanity test. The test the whole study turns
# --- on: inserting a learner between the factor and the ranker must not cost
# --- material information. These are rungs, not arms — `arm=False`.

RUNGS = (
    Carrier("S1-A", (Z_BASE,), "target_rank", "prediction", None,
            "A's carrier on ret_12_1 alone"),
    Carrier("S1-B", (Z_BASE,), RESID_TARGET, "blend", None,
            "B's carrier on ret_12_1 alone", lam=LAMBDA),
    Carrier("S1-C", (Z_BASE,), "target_rank", "prediction", Z_BASE,
            "C's carrier on ret_12_1 alone"),
)

RUNG_FOR_ARM = {"V2.2-A": "S1-A", "V2.2-B": "S1-B", "V2.2-C": "S1-C"}

# --- §4.2 the 2x2 carrier grid. One feature, four cells, decomposing the
# --- +0.02115 -> +0.00053 collapse into an input effect and a target effect.
# --- The grid diagnoses; it does not choose.

GRID = (
    Carrier("raw_level__winsorised_level", (BASE,), "target_train", "prediction", None,
            "this cell IS V2.1-A — re-run here to check the pipeline reproduces "
            "the frozen +0.00053 across a module boundary"),
    Carrier("raw_level__rank", (BASE,), "target_rank", "prediction", None,
            "the target effect alone: raw level in, within-cutoff rank out"),
    Carrier("z_rank__winsorised_level", (Z_BASE,), "target_train", "prediction", None,
            "the input effect alone: rank in, winsorised level out"),
)
# The fourth cell, (input = z__ rank, target = rank), is `S1-A` by construction —
# same columns, same target, same fitter, same cutoffs. It is reused rather than
# re-fitted, and `test_the_grid_reuses_s1_a_for_its_fourth_cell` pins that.
GRID_FOURTH_CELL = "z_rank__rank"

ALL_CARRIERS = {c.name: c for c in ARMS + RUNGS + GRID}


# ----------------------------------------------------------------------
# Running one carrier
# ----------------------------------------------------------------------

@dataclasses.dataclass
class Result:
    spec: Carrier
    record: dict
    prediction: pd.Series           # the raw model output
    final: pd.Series                # after the §3 output combination
    ic: pd.Series                   # per-cutoff, NaNs dropped
    assessment: protocol.Assessment
    diagnostics: carrier.Diagnostics


def run_carrier(spec: Carrier, panel, calendar, quiet: bool = False) -> Result:
    """Walk forward over the development cutoffs, combine, score, diagnose."""
    missing = [c for c in spec.columns if c not in panel.frame.columns]
    if missing:
        raise SystemExit(f"{spec.name}: the panel has no column {missing}. The "
                         "pre-registered column list is not negotiable — rebuild "
                         "the panel rather than editing the list.")

    print(f"\n=== {spec.name} — {spec.note}")
    print(f"    {len(spec.columns)} features, target `{spec.train_target}`, "
          f"output `{spec.combination}`"
          + (f" (lambda {spec.lam:.2f})" if spec.combination == "blend" else "")
          + (f", monotone +1 on {spec.monotone}" if spec.monotone else ""))

    started = time.time()
    run = walkforward.walk_forward(panel, calendar, list(spec.columns),
                                   fit_fn=spec.fitter(), name=spec.name,
                                   verbose=not quiet)
    elapsed = time.time() - started

    final = spec.score(panel, run.predictions)
    assessment = protocol.assess(panel, final, spec.name)
    ic = assessment.evaluation.ic.clean
    diagnostics = carrier.diagnose(final, panel.frame[BASE], spec.name)

    print(f"    mean IC {assessment.evaluation.ic.mean:+.5f}  "
          f"hit {assessment.evaluation.ic.hit_rate:.1%}  "
          f"({assessment.evaluation.ic.n} cutoffs, {len(run.fits)} refits, {elapsed:.0f}s)")
    summary = diagnostics.summary()
    rho = summary.get("spearman_vs_factor", {})
    print(f"    vs factor: rho {_fmt(rho.get('mean'))} "
          f"(neg on {_pct(rho.get('share_negative'))} of cutoffs)  "
          f"inversions {summary.get('inversions', {}).get('total')}  "
          f"univariate {summary.get('is_univariate_in_factor')}  "
          f"collapsed {summary.get('collapsed_cutoffs')}")

    record = assessment.record()
    record.update({
        "preregistration": PREREGISTRATION,
        "note": spec.note,
        "n_features": len(spec.columns),
        "feature_columns": list(spec.columns),
        "train_target": spec.train_target,
        "output_combination": spec.combination,
        "lambda": spec.lam if spec.combination == "blend" else None,
        "monotone_increasing_on": spec.monotone,
        "scored_against": "alpha_5d",
        "is_arm": spec.arm,
        "seconds": round(elapsed, 1),
        "refits": run.fits,
        "carrier_diagnostics": summary,
        "gates_are_diagnostic_here": (
            "V2_2_PREREGISTRATION.md §6.3 gates the *selected arm* on development. "
            "The nine V2.1 criteria below are the same arithmetic run on the same "
            "slice and decide nothing here; §8 keeps the exam sealed either way."),
    })
    # A development slice has no gates. Leaving a field called "gates_passed" in
    # a development artefact invites being quoted as a verdict.
    record["diagnostic_gates_passed"] = record.pop("gates_passed")
    record["diagnostic_failed_gates"] = record.pop("failed_gates")

    return Result(spec, record, run.predictions, final, ic, assessment, diagnostics)


# ----------------------------------------------------------------------
# §2.2 / §4.1 — S0, the no-model rung
# ----------------------------------------------------------------------

def s0_scores(panel) -> pd.Series:
    """§2.2: `S0 = z__ret_12_1`. No model, no fit, no walk-forward.

    Rank-identical to Benchmark 1 by construction — `centred_rank` is the same
    `groupby(cutoff).rank(pct=True)` that `models.simple_factor_scores` uses, less
    a constant — so ranking by it must reproduce Benchmark 1's IC to the last
    digit. `main` asserts that rather than hoping for it.
    """
    return panel.frame[Z_BASE]


def ic_of(panel, score: pd.Series, target: str = "alpha_5d") -> pd.Series:
    frame = panel.frame[[target]].copy()
    frame["prediction"] = score.reindex(frame.index)
    return stats.ic_by_cutoff(frame, "prediction", target).dropna()


# ----------------------------------------------------------------------
# §6.1 — carrier integrity, an eligibility condition
# ----------------------------------------------------------------------

def carrier_integrity(rung_ic: pd.Series, s0_ic: pd.Series, rung: str) -> dict:
    """G1: paired mean per-cutoff IC of `S1-x` minus `S0` >= -0.005.

    The threshold's justification, fixed before the fact: `S0` is ~ +0.021, so
    -0.005 permits about a quarter of the factor's signal to be lost to the
    discretisation a histogram learner necessarily introduces — <= 255 bins
    produce ties, and ties cost Spearman IC — while rejecting anything resembling
    V2.1-A, which lost -0.0206, or 98% of the factor.
    """
    series = stats.paired_difference(rung_ic, s0_ic, f"{rung} IC - S0 IC")
    low, high = series.bootstrap_ci()
    # S0 spans all 316 development cutoffs; a rung only scores the ones a fit
    # reached, so the two headline means are not comparable and the paired figure
    # is the only one that is. Both ends of the pair are reported on the *paired*
    # sample so the table cannot be misread — S0 is ~+0.021 there and ~+0.010 over
    # all 316, and quoting the wrong one would make every rung look better than it is.
    paired = rung_ic.index.intersection(s0_ic.index)
    return {
        "rung": rung,
        "criterion": "paired mean per-cutoff IC of the one-feature rung minus S0",
        "threshold": f">= {G1_FLOOR}",
        "value": _round(series.mean, 5),
        "ci": [_round(low, 5), _round(high, 5)],
        "n_cutoffs": series.n,
        "rung_mean_ic_on_paired_cutoffs": _round(float(rung_ic.reindex(paired).mean()), 5),
        "s0_mean_ic_on_paired_cutoffs": _round(float(s0_ic.reindex(paired).mean()), 5),
        "passed": bool(series.n and series.mean >= G1_FLOOR),
    }


def eligibility(arm: str, integrity: dict, n_scored: int) -> dict:
    """§6.1 both conditions. A failure is reported in full, not worked around."""
    enough = bool(n_scored >= MIN_SCORED_CUTOFFS)
    return {
        "arm": arm,
        "g1_carrier_integrity": integrity,
        "scored_cutoffs": {"value": n_scored, "threshold": f">= {MIN_SCORED_CUTOFFS}",
                           "passed": enough},
        "eligible": bool(integrity["passed"] and enough),
        "consequence": ("eligible for selection" if integrity["passed"] and enough else
                        "carrier-defective: reported in full, not eligible for "
                        "selection whatever its IC (§6.1)"),
    }


# ----------------------------------------------------------------------
# §6.2 — selection
# ----------------------------------------------------------------------

# Ties go to the structurally safer arm: B's order bound is provable, C's is
# conditional on the constraint binding, A's is not guaranteed at all.
SAFETY_ORDER = ("V2.2-B", "V2.2-C", "V2.2-A")


def select_arm(records: dict[str, dict], eligible: dict[str, dict]) -> str | None:
    """Highest mean development IC among the **eligible arms**. Arms only.

    Rungs and grid cells are absent from this function's inputs by construction:
    it reads `is_arm`, and §4 forbids promoting a diagnostic to an arm.
    """
    order = {name: index for index, name in enumerate(SAFETY_ORDER)}
    candidates = [name for name, record in records.items()
                  if record.get("is_arm") and eligible.get(name, {}).get("eligible")]
    if not candidates:
        return None

    def key(name: str):
        mean = records[name]["ic"]["mean"]
        mean = mean if mean is not None and np.isfinite(mean) else -9.0
        return (-mean, order.get(name, 99))

    return sorted(candidates, key=key)[0]


# ----------------------------------------------------------------------
# §6.3 — the gate. Four conditions, all of which must hold for the selected arm.
# ----------------------------------------------------------------------

def _halves(values: pd.Series) -> dict[str, dict]:
    clean = values.dropna().sort_index()
    middle = (len(clean) + 1) // 2
    out = {}
    for label, block in (("first", clean.iloc[:middle]), ("second", clean.iloc[middle:])):
        out[label] = {"n": int(len(block)),
                      "mean": _round(block.mean(), 5) if len(block) else None}
    return out


def gate(assessment: protocol.Assessment) -> dict:
    """§6.3 G2-G5, against **both** Benchmark 1 and Benchmark 3.

    The bar's difficulty was disclosed in the pre-registration before any V2.2
    number existed: on 255 cutoffs the block-bootstrap half-width of the paired
    difference is ~0.034 against B1 and ~0.033 against B3, so G2 and G3 require a
    point advantage of roughly that size. V2.1-D managed +0.013 and +0.006.
    """
    per_benchmark: dict[str, dict] = {}
    for key in GATE_BENCHMARKS:
        series = assessment.versus.get(key)
        if series is None or not series.n:
            per_benchmark[key] = {"n_cutoffs": 0, "mean": None, "ci": [None, None],
                                  "share_positive": None, "halves": {},
                                  "beats": False, "breadth": False, "stable": False}
            continue
        low, high = series.bootstrap_ci()
        halves = _halves(series.clean)
        per_benchmark[key] = {
            "n_cutoffs": series.n,
            "mean": _round(series.mean, 5),
            "ci": [_round(low, 5), _round(high, 5)],
            "share_positive": _round(series.hit_rate, 4),
            "halves": halves,
            "beats": bool(series.mean > 0 and np.isfinite(low) and low > 0),
            "breadth": bool(series.hit_rate >= BREADTH_FLOOR),
            "stable": bool(halves["first"]["n"] and halves["second"]["n"]
                           and (halves["first"]["mean"] or 0) > 0
                           and (halves["second"]["mean"] or 0) > 0),
        }

    b1 = per_benchmark[GATE_BENCHMARKS[0]]
    b3 = per_benchmark[GATE_BENCHMARKS[1]]
    gates = {
        "G2_beats_12_1_momentum": {
            "threshold": "paired mean IC difference > 0, 95% block-bootstrap CI excludes 0",
            "value": b1["mean"], "ci": b1["ci"], "passed": b1["beats"]},
        "G3_beats_regime_switched_momentum": {
            "threshold": "paired mean IC difference > 0, 95% block-bootstrap CI excludes 0",
            "value": b3["mean"], "ci": b3["ci"], "passed": b3["beats"]},
        "G4_breadth": {
            "threshold": f"paired difference > 0 on >= {BREADTH_FLOOR:.0%} of scored "
                         "cutoffs, against both benchmarks",
            "value": {"vs_b1": b1["share_positive"], "vs_b3": b3["share_positive"]},
            "passed": bool(b1["breadth"] and b3["breadth"])},
        "G5_stability": {
            "threshold": "paired mean difference > 0 in each chronological half, "
                         "against both benchmarks",
            "value": {"vs_b1": b1["halves"], "vs_b3": b3["halves"]},
            "passed": bool(b1["stable"] and b3["stable"])},
    }
    passed = all(entry["passed"] for entry in gates.values())
    return {
        "arm": assessment.name,
        "gates": gates,
        "passed": passed,
        "versus_benchmarks": per_benchmark,
        "consequence": (
            "every gate holds — §8 applies: V2.2 stops and reports, the V2.1 exam "
            "stays sealed, and V2_2_EXAM_DECISION.md must be written before any "
            "exam date is touched" if passed else
            "the gate is closed. The carrier diagnosis is V2.2's contribution; "
            "production stays at weight 0 / HOLD (§9.1)"),
    }


# ----------------------------------------------------------------------
# §3.2 — the lambda sensitivity curve. Reported, never selected on.
# ----------------------------------------------------------------------

def lambda_curve(panel, prediction: pd.Series, base: pd.Series) -> dict:
    """Arm B's carrier at lambda in {0, 0.25, 0.50, 1.00}, on B's own cutoffs.

    No refit: lambda is an output-combination parameter, so the same predictions
    serve every point on the curve. §3.2: if 0.25 or 1.00 scores better than 0.50
    that is reported and **does not become the arm** — re-choosing lambda after
    seeing ICs is exactly the tuning the pre-registration exists to forbid.
    """
    mask = prediction.notna()
    out = {}
    for lam in LAMBDA_CURVE:
        final = carrier.blend(base, prediction, lam).where(mask)
        series = stats.Series(f"B @lambda={lam:.2f}", ic_of(panel, final), null=0.0)
        violations = carrier.order_bound_violations(base.where(mask), final, lam)
        out[f"{lam:.2f}"] = {
            "mean_ic": _round(series.mean, 5),
            "n_cutoffs": series.n,
            "hit_rate": _round(series.hit_rate, 4),
            "order_bound_violations": int(violations),
            "is_the_arm": lam == LAMBDA,
        }
    return out


# ----------------------------------------------------------------------

def _fmt(value) -> str:
    return "     n/a" if value is None else f"{value:+.5f}"


def _fmt_ci(ci) -> str:
    if not ci or ci[0] is None:
        return "n/a"
    return f"[{ci[0]:+.5f}, {ci[1]:+.5f}]"


def _pct(value) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _round(value, places: int):
    if value is None:
        return None
    value = float(value)
    return None if not np.isfinite(value) else round(value, places)


def frozen_v2_1_arm_ic(arm: str = "V2.1-A") -> float | None:
    """The frozen V2.1 mean IC, read for comparison and never written to."""
    if not ladder.JSON_PATH.exists():
        return None
    record = json.loads(ladder.JSON_PATH.read_text(encoding="utf-8"))
    return (record.get("arms", {}).get(arm, {}).get("ic", {}) or {}).get("mean")


def check_rank_transform_asymmetry(panel) -> dict:
    """§2.1's design decision, measured on the panel rather than asserted.

    The 26 market-context columns must be cutoff-constant (so ranking them would
    destroy them) and the 9 stock-level columns must not (so ranking them is
    meaningful). If that ever flips, the arms are a different experiment.
    """
    context = carrier.constant_within_cutoff(panel.frame, MARKET_CONTEXT)
    stock = carrier.constant_within_cutoff(panel.frame, STOCK_LEVEL)
    varying_context = sorted(c for c, is_constant in context.items() if not is_constant)
    constant_stock = sorted(c for c, is_constant in stock.items() if is_constant)
    if varying_context:
        raise SystemExit(
            f"these MARKET_CONTEXT columns vary within a cutoff: {varying_context}. "
            "§2.1 leaves them un-ranked because they are cutoff-constant; if they "
            "are not, that decision has to be re-made in the open.")
    if constant_stock:
        raise SystemExit(
            f"these stock-level columns are constant within a cutoff: {constant_stock}. "
            "Rank-transforming them maps every name to 0.5 and destroys them.")
    return {
        "market_context_columns": len(MARKET_CONTEXT),
        "all_market_context_cutoff_constant": True,
        "market_context_rank_transformed": False,
        "stock_level_columns": len(STOCK_LEVEL),
        "all_stock_level_varying": True,
        "stock_level_rank_transformed": True,
        "note": ("§2.1: a within-cutoff rank of a cutoff-constant column is 0.5 for "
                 "every name, so context passes through raw and the tree splits on "
                 "it across cutoffs. Pre-registered asymmetry, not an oversight."),
    }


def widen(panel):
    """Add the §2.1 `z__` columns to a copy of the panel. Stock-level only.

    The 26 context columns are deliberately absent from `STOCK_LEVEL`, so a
    `z__mkt_...` column cannot come into existence by accident.
    """
    frame, added = carrier.add_rank_columns(panel.frame, STOCK_LEVEL)
    if list(added) != list(RANKED_STOCK_LEVEL):
        raise RuntimeError(f"rank transform produced {added}, expected "
                           f"{list(RANKED_STOCK_LEVEL)}")
    return dataclasses.replace(panel, frame=frame)


# ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="V2.2 ladder — development only")
    parser.add_argument("--only", nargs="*", default=None,
                        help="run a subset of the arms, e.g. --only V2.2-B. The "
                             "family size for the multiplicity correction stays 3, "
                             "and the rungs and grid still run — they are what the "
                             "arms are interpreted against.")
    parser.add_argument("--quiet", action="store_true", help="suppress per-refit lines")
    args = parser.parse_args(argv)

    if (OUT_DIR / "v2_1_exam_predictions.json").exists():
        raise SystemExit(
            "out/v2_1_exam_predictions.json exists. §1.1 of V2_2_PREREGISTRATION.md "
            "says it must not come into existence during V2.2 — stop and explain it "
            "in V2_2_EXPERIMENT_LOG.md before running anything.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, _v2_development, _v2_exam = build_panel.load()
    exam_set = examset.load()

    # §1.2 — the one line that keeps the exam sealed. `development_only` slices to
    # the frozen development list and then asserts no exam cutoff survived, rather
    # than trusting the slice: `slice_cutoffs` takes a keep-list and would not
    # complain if the wrong list were handed to it.
    panel = examset.development_only(panel, exam_set)
    calendar = pitdata.load_calendar()

    print(f"protocol   V2.2, exam digest {exam_set.digest[:16]}… (not read below)")
    print(f"panel      {len(panel.frame):,} rows  ·  {len(panel.cutoffs)} development "
          f"cutoffs  ·  {panel.cutoffs[0].date()} .. {panel.cutoffs[-1].date()}")
    print(f"arms       {len(ARMS)} pre-registered, family size k={FAMILY_SIZE}; "
          f"{len(RUNGS)} rungs + {len(GRID) + 1} grid cells, none selectable")
    print(f"see        {PREREGISTRATION}")

    asymmetry = check_rank_transform_asymmetry(panel)
    print(f"§2.1       {asymmetry['market_context_columns']} context columns "
          f"cutoff-constant (un-ranked), {asymmetry['stock_level_columns']} "
          f"stock-level columns varying (ranked)")

    panel = widen(panel)

    # --- §2.2 / §4.1 S0. The identity check comes before anything is fitted: if
    # --- ranking by z__ret_12_1 does not reproduce Benchmark 1 exactly, the
    # --- pipeline is wrong and V2.2 stops.
    s0 = s0_scores(panel)
    s0_ic = ic_of(panel, s0)
    benchmark_1 = protocol.benchmark_scores(panel.frame, panel.regimes)["b1_momentum_12_1"]
    b1_ic = ic_of(panel, benchmark_1)
    identity = float((s0_ic - b1_ic.reindex(s0_ic.index)).abs().max())
    if not (identity < 1e-12 and len(s0_ic) == len(b1_ic)):
        raise SystemExit(
            f"S0 is not rank-identical to Benchmark 1: max |IC difference| "
            f"{identity:.3e} over {len(s0_ic)} vs {len(b1_ic)} cutoffs. §2.2 makes "
            "this an assertion, not a hope — the pipeline is wrong.")
    print(f"§2.2       S0 == Benchmark 1 exactly: mean IC "
          f"{s0_ic.mean():+.5f} over {len(s0_ic)} cutoffs "
          f"(max |diff| {identity:.1e})")

    wanted = set(args.only) if args.only else None
    if wanted and (unknown := wanted - {arm.name for arm in ARMS}):
        raise SystemExit(f"no such arm: {sorted(unknown)}")

    results: dict[str, Result] = {}
    for spec in RUNGS + GRID:
        results[spec.name] = run_carrier(spec, panel, calendar, quiet=args.quiet)
    for spec in ARMS:
        if wanted is not None and spec.name not in wanted:
            continue
        results[spec.name] = run_carrier(spec, panel, calendar, quiet=args.quiet)

    # --- §4.1 the one-feature sanity test, and §6.1 G1 over it.
    print("\n=== §4.1 one-feature sanity test — does inserting a learner cost information?")
    print(f"    {'S0':<8} {s0_ic.mean():+.5f} over all {len(s0_ic)} development "
          "cutoffs (no model; rank by z__ret_12_1)")
    print(f"    {'':<8} every rung below is compared to S0 on the rung's own scored "
          "cutoffs, which is the only comparable figure")
    integrity: dict[str, dict] = {}
    for name in ("S1-A", "S1-B", "S1-C"):
        if name not in results:
            continue
        verdict = carrier_integrity(results[name].ic, s0_ic, name)
        integrity[name] = verdict
        print(f"    {name:<8} {_fmt(verdict['rung_mean_ic_on_paired_cutoffs'])} vs S0 "
              f"{_fmt(verdict['s0_mean_ic_on_paired_cutoffs'])} on the same "
              f"{verdict['n_cutoffs']} cutoffs  ->  paired {_fmt(verdict['value'])} "
              f"CI {_fmt_ci(verdict['ci'])}  "
              f"{'OK' if verdict['passed'] else f'FAILS G1 (>= {G1_FLOOR})'}")

    # --- §4.2 the grid.
    grid = {
        "raw_level__winsorised_level": _round(results["raw_level__winsorised_level"].ic.mean(), 5),
        "raw_level__rank": _round(results["raw_level__rank"].ic.mean(), 5),
        "z_rank__winsorised_level": _round(results["z_rank__winsorised_level"].ic.mean(), 5),
        GRID_FOURTH_CELL: _round(results["S1-A"].ic.mean(), 5),
    }
    # The grid cells all score the same cutoffs, so S0 is quoted on that sample —
    # the number the four cells have to be read against.
    grid_index = results["raw_level__winsorised_level"].ic.index
    s0_on_grid = _round(float(s0_ic.reindex(s0_ic.index.intersection(grid_index)).mean()), 5)

    frozen_a = frozen_v2_1_arm_ic("V2.1-A")
    print("\n=== §4.2 the 2x2 carrier grid (one feature, ret_12_1)")
    print(f"    {'':<18} {'target = winsorised level':>26} {'target = within-cutoff rank':>28}")
    print(f"    {'input = raw level':<18} {_fmt(grid['raw_level__winsorised_level']):>26} "
          f"{_fmt(grid['raw_level__rank']):>28}")
    print(f"    {'input = z__ rank':<18} {_fmt(grid['z_rank__winsorised_level']):>26} "
          f"{_fmt(grid[GRID_FOURTH_CELL]):>28}")
    print(f"    S0 (no model, same {len(grid_index)} cutoffs) {_fmt(s0_on_grid)}   "
          f"frozen V2.1-A {_fmt(frozen_a)}   "
          f"top-left cell here {_fmt(grid['raw_level__winsorised_level'])}")

    # --- §3.2 the lambda curve, on arm B if it ran, else on the S1-B rung.
    curves = {}
    for name in ("V2.2-B", "S1-B"):
        if name in results:
            curves[name] = lambda_curve(panel, results[name].prediction, s0)
    if curves:
        print("\n=== §3.2 lambda sensitivity (reported; 0.50 is the arm and stays the arm)")
        for name, curve in curves.items():
            for lam, entry in curve.items():
                mark = " <- the arm" if entry["is_the_arm"] else ""
                print(f"    {name:<8} lambda {lam}  mean IC {_fmt(entry['mean_ic'])}  "
                      f"order-bound violations {entry['order_bound_violations']}{mark}")

    # --- §6.1 eligibility, then §6.2 selection, then §6.3 the gate. In that order.
    arm_records = {name: results[name].record for name in results if results[name].spec.arm}
    eligible = {
        name: eligibility(name, integrity.get(RUNG_FOR_ARM[name], {
            "rung": RUNG_FOR_ARM[name], "passed": False, "value": None,
            "ci": [None, None], "n_cutoffs": 0,
            "criterion": "paired mean per-cutoff IC of the one-feature rung minus S0",
            "threshold": f">= {G1_FLOOR}"}), results[name].assessment.evaluation.ic.n)
        for name in arm_records}

    print("\n=== §6.1 eligibility")
    for name, verdict in eligible.items():
        print(f"    {name:<8} G1 {_fmt(verdict['g1_carrier_integrity']['value'])}  "
              f"{verdict['scored_cutoffs']['value']} cutoffs  -> "
              f"{'ELIGIBLE' if verdict['eligible'] else 'CARRIER-DEFECTIVE'}")

    holm = stats.holm_bonferroni({n: r["ic"]["p_boot"] for n, r in arm_records.items()})
    for name, verdict in holm.items():
        if name in arm_records:
            arm_records[name]["multiplicity_on_development"] = verdict

    selected = select_arm(arm_records, eligible)
    gate_verdict = (gate(results[selected].assessment) if selected else
                    {"arm": None, "passed": False, "gates": {},
                     "consequence": "no eligible arm was run; nothing to gate"})

    print(f"\n=== §6.2 selected arm: {selected or 'none'} "
          f"(highest mean development IC among the eligible arms)")
    print(f"=== §6.3 gate: {'PASSED' if gate_verdict['passed'] else 'CLOSED'}")
    for key, entry in gate_verdict.get("gates", {}).items():
        value = entry["value"]
        shown = _fmt(value) if isinstance(value, (int, float)) or value is None else str(value)
        print(f"    {key:<36} {'pass' if entry['passed'] else 'fail'}  {shown}"
              + (f"  CI {_fmt_ci(entry.get('ci'))}" if entry.get("ci") else ""))
    print(f"           {gate_verdict['consequence']}")

    # --- §7 the BEAR warning, recorded in advance because the pattern has now
    # --- appeared twice. Diagnostic only; it may not select, explain or restrict.
    bear = {}
    for name, result in results.items():
        table = result.assessment.evaluation.regime_ic
        if len(table):
            bear[name] = {str(k): _round(v, 5) for k, v in table["mean_ic"].items()}

    record = {
        "protocol": "V2.2",
        "stage": "carrier ladder / development",
        "preregistration": PREREGISTRATION,
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "exam_set_digest": exam_set.digest,
        "exam_predictions_exist": False,
        "development_cutoffs": len(panel.cutoffs),
        "rows": int(len(panel.frame)),
        "first_cutoff": str(panel.cutoffs[0].date()),
        "last_cutoff": str(panel.cutoffs[-1].date()),
        "refit_sessions": walkforward.REFIT_SESSIONS,
        "min_train_cutoffs": walkforward.MIN_TRAIN_CUTOFFS,
        "family_size": FAMILY_SIZE,
        "learner_params": {k: v for k, v in models.MODEL_A_PARAMS.items()},
        "rank_transform_asymmetry": asymmetry,
        "s0": {
            "definition": "z__ret_12_1 = rank_pct(ret_12_1) - 0.5, no model",
            "mean_ic": _round(float(s0_ic.mean()), 5),
            "n_cutoffs": int(len(s0_ic)),
            "rank_identical_to_benchmark_1": True,
            "max_abs_ic_difference": identity,
            "sample_note": (
                "S0 needs no fit, so it scores every development cutoff. Every arm "
                "and rung scores only the cutoffs a fit reached — the walk-forward "
                "needs 60 training cutoffs before it predicts anything — so the two "
                "headline means are over different samples and are not comparable. "
                "The G1 figures in one_feature_sanity_test are paired and carry S0's "
                "mean on the paired sample beside them."),
        },
        "one_feature_sanity_test": integrity,
        "carrier_grid": {
            "cells": grid,
            "s0_mean_ic_on_the_same_cutoffs": s0_on_grid,
            "n_cutoffs": int(len(grid_index)),
            "frozen_v2_1_a_mean_ic": frozen_a,
            "reproduces_frozen_v2_1_a": (
                None if frozen_a is None or grid["raw_level__winsorised_level"] is None
                else bool(abs(grid["raw_level__winsorised_level"] - frozen_a) < 1e-4)),
            "fourth_cell_note": (
                f"{GRID_FOURTH_CELL} is S1-A by construction — same columns, target, "
                "fitter and cutoffs — and is reused rather than re-fitted"),
            "note": ("§4.2: the grid decomposes the +0.02115 -> +0.00053 collapse into "
                     "an input effect and a target effect. It diagnoses; it does not "
                     "choose. The arms' carrier is fixed in §3 by prior argument."),
        },
        "lambda_sensitivity": curves,
        "lambda_note": ("§3.2: lambda = 0.50 is the arm. If 0.25 or 1.00 scores better "
                        "that is reported and does not become the arm. Promoting a "
                        "lambda variant would make the Holm family 5, not 3."),
        "arms": arm_records,
        "rungs": {name: results[name].record for name in results
                  if not results[name].spec.arm},
        "eligibility": eligible,
        "holm_bonferroni_on_development": holm,
        "selected_arm": selected,
        "gate": gate_verdict,
        "regime_ic": bear,
        "regime_note": (
            "§7: diagnostic only. Regime breakdowns may not select an arm, explain a "
            "failure, restrict a conclusion to a bucket or justify an interaction. V2's "
            "development edge lived in BEAR_TREND and inverted to SIDEWAYS on its exam, "
            "so a V2.2 arm that concentrates in BEAR_TREND is a warning signal, not "
            "evidence of robustness."),
        "exam_may_be_opened": False,
        "exam_note": (
            "§8: the V2.1 exam is not opened by this stage even if every gate passes. "
            "V2_2_EXAM_DECISION.md has to be written first, and it has to answer "
            "whether a paper frozen for a V2.1 arm tests a V2.2 arm at all, what the "
            "family size for the exam correction is, and the resolution problem — the "
            "72-cutoff exam's half-width against B1 is ~0.065, three times V2.1-D's "
            "edge."),
        "production_weight": 0.0,
        "production_weight_note": (
            "Unchanged and not a result of this stage. §1.4 fixes it at 0 / HOLD and "
            "nothing in V2.2 can move it; alpha/adapter.py is not modified."),
    }
    JSON_PATH.write_text(json.dumps(develop._jsonable(record), indent=2), encoding="utf-8")
    pd.to_pickle({
        "ic_series": {name: result.ic for name, result in results.items()},
        "s0_ic": s0_ic,
        "predictions": {name: result.prediction.dropna() for name, result in results.items()},
        "final_scores": {name: result.final.dropna() for name, result in results.items()},
        "diagnostics": {name: result.diagnostics.per_cutoff for name, result in results.items()},
    }, PICKLE_PATH)
    print(f"\nfroze      {JSON_PATH}")
    print(f"froze      {PICKLE_PATH}")


if __name__ == "__main__":
    main()
