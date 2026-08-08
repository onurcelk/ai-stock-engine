"""Stage 1 of V2.1 — the four-rung ladder, on development cutoffs only.

`V2_1_LADDER_PREREGISTRATION.md` in code. `alpha/develop.py` is left untouched:
it records a finished experiment (V2's §27 ladder) and rewriting it to also mean
V2.1 would make the two indistinguishable in a diff a year from now.

The arms, fixed before the first fit, family size **k = 4**:

    V2.1-A   ret_12_1 alone.
    V2.1-B   + the 26 cutoff-constant market-context columns.
    V2.1-C   + eight stock-level columns, each justified individually in §3.3.
    V2.1-D   C's features, trained on the within-cutoff rank instead of the level.

All four run; there is no internal gate, because the object of interest is the
A->B->C->D deltas and a delta needs both ends.

Two properties of this file matter more than the rest of it.

**It cannot see the exam.** Cutoffs come from `examset.development_only()`,
which slices to the frozen development list and then asserts that no exam cutoff
survived. `walk_forward` then trains out of that panel's own cutoffs, so no exam
date is a training candidate at any refit for any arm.

**Its nine gates are diagnostics.** `protocol.assess` is the same arithmetic the
exam will run, and running it here does not make development an exam.
`V2_1_PREREGISTRATION.md` §4 gates on the exam set. The one development number
with authority is the §5.2 gate: does the selected arm beat 12-1 momentum, with
a bootstrap CI that excludes zero, over 316 cutoffs. If that closes, the exam
stays sealed and this file's output is the study's result.

Run:  python -m alpha.ladder              # all four arms
      python -m alpha.ladder --only V2.1-B
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

from . import (build_panel, develop, examset, models, pitdata, protocol,
               stats, walkforward)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
JSON_PATH = OUT_DIR / "v2_1_development.json"
PICKLE_PATH = OUT_DIR / "v2_1_development.pkl"

PREREGISTRATION = "alpha/V2_1_LADDER_PREREGISTRATION.md"
FAMILY_SIZE = 4                     # §4 — fixed before the first fit, not after

# ----------------------------------------------------------------------
# §3 — the feature lists. Written out column by column rather than derived from
# a prefix rule, because a prefix rule is a thing that quietly changes meaning
# when someone adds a feature, and these lists are pre-registered.
# ----------------------------------------------------------------------

MOMENTUM = ("ret_12_1",)

# The 26 columns that take one value for the whole cross-section at a cutoff.
# `test_market_context_is_constant_within_a_cutoff` verifies that claim against
# the built panel rather than trusting this comment.
MARKET_CONTEXT = (
    "mkt_spy_ret_5d", "mkt_spy_ret_20d", "mkt_spy_ret_60d", "mkt_spy_rsi14",
    "mkt_spy_rvol_20d", "mkt_spy_sma50_dist", "mkt_spy_sma200_dist",
    "mkt_qqq_ret_5d", "mkt_qqq_ret_20d", "mkt_qqq_ret_60d", "mkt_qqq_rsi14",
    "mkt_qqq_rvol_20d", "mkt_qqq_sma50_dist", "mkt_qqq_sma200_dist",
    "vix_level", "vix_percentile", "vix_change_5d",
    "index_breadth_above_sma20", "index_breadth_above_sma50", "index_advance_share",
    "watchlist_breadth_proxy_above_sma20", "watchlist_breadth_proxy_advance_share",
    "regime_bull", "regime_bear", "regime_sideways", "regime_high_vol",
)

# §3.3. Eight, each with a reason in the pre-registration table. The nine
# overnight_/intraday_ columns V2 filed under "context" are stock-level, so
# three of them live here and the arm that carries them is labelled accordingly.
STOCK_LEVEL = (
    "ret_5d", "ret_20d",
    "rvol_20d", "rvol_60d",
    "sma200_dist",
    "overnight_mean_20d", "intraday_mean_20d", "overnight_share_60d",
)

# Named so a test can assert the exclusion is the pre-registered one rather than
# an oversight. V2 measured this tier over 423 cutoffs: +0.00837 -> +0.00846.
EXCLUDED_RELATIVE_TIER_NOTE = (
    "the 47-column relative/percentile tier and beta_market/beta_sector are "
    "excluded by §3.3: V2 measured them over 423 development cutoffs and mean IC "
    "moved from +0.00837 to +0.00846, which is a well-powered null")


@dataclasses.dataclass(frozen=True)
class Arm:
    """One rung. A column list, a training target, and nothing else that varies."""

    name: str
    columns: tuple[str, ...]
    train_target: str
    note: str
    candidate: bool             # §5.1 — eligible to be the arm sent to the exam

    def fitter(self):
        target = self.train_target
        return lambda train, columns: models.fit_model_a(train, columns, target=target)


ARMS = (
    Arm("V2.1-A", MOMENTUM, "target_train",
        "12-1 momentum alone; the floor, and Benchmark 1 up to non-monotonicity",
        candidate=False),
    Arm("V2.1-B", MOMENTUM + MARKET_CONTEXT, "target_train",
        "+ 26 cutoff-constant market-context columns; tests whether context says "
        "when to flatten or flip momentum",
        candidate=True),
    Arm("V2.1-C", MOMENTUM + MARKET_CONTEXT + STOCK_LEVEL, "target_train",
        "+ 8 justified stock-level columns; the first arm whose within-cutoff "
        "function is multivariate",
        candidate=True),
    Arm("V2.1-D", MOMENTUM + MARKET_CONTEXT + STOCK_LEVEL, "target_rank",
        "C's features trained on the within-cutoff percentile (pointwise ranker, "
        "NOT LambdaRank); scored on alpha_5d like every other arm",
        candidate=True),
)

ARMS_BY_NAME = {arm.name: arm for arm in ARMS}


# ----------------------------------------------------------------------
# Running one rung
# ----------------------------------------------------------------------

def run_arm(arm: Arm, panel, calendar) -> tuple[dict, pd.Series, protocol.Assessment]:
    """Walk forward over the development cutoffs and assess under the V2.1 protocol."""
    missing = [c for c in arm.columns if c not in panel.frame.columns]
    if missing:
        raise SystemExit(f"{arm.name}: the panel has no column {missing}. The "
                         "pre-registered feature list is not negotiable — rebuild "
                         "the panel rather than editing the list.")

    print(f"\n=== {arm.name} — {arm.note}")
    print(f"    {len(arm.columns)} features, target `{arm.train_target}`")
    started = time.time()
    run = walkforward.walk_forward(panel, calendar, list(arm.columns),
                                   fit_fn=arm.fitter(), name=arm.name)
    elapsed = time.time() - started

    assessment = protocol.assess(panel, run.predictions, arm.name)
    criteria = assessment.criteria()
    ic = assessment.evaluation.ic

    print(f"    mean IC {ic.mean:+.5f}  hit {ic.hit_rate:.1%}  "
          f"spread {assessment.evaluation.spread.mean:+.5f}  "
          f"({ic.n} cutoffs, {len(run.fits)} refits, {elapsed:.0f}s)")
    for key in ("5_beats_12_1_momentum", "6_beats_5d_reversal",
                "12b_versus_regime_switched"):
        entry = criteria.get(key, {})
        print(f"    {key:<28} {_fmt(entry.get('value'))}  "
              f"CI {_fmt_ci(entry.get('ci'))}")

    record = assessment.record()
    record.update({
        "preregistration": PREREGISTRATION,
        "note": arm.note,
        "n_features": len(arm.columns),
        "feature_columns": list(arm.columns),
        "train_target": arm.train_target,
        "scored_against": "alpha_5d",
        "exam_candidate": arm.candidate,
        "seconds": round(elapsed, 1),
        "refits": run.fits,
        "gates_are_diagnostic_here": (
            "V2_1_PREREGISTRATION.md §4 gates on the exam set. These nine are the "
            "same arithmetic run on development and decide nothing; the only "
            "development number with authority is the §5.2 gate."),
    })
    # `gates_passed` on a development slice is a diagnostic and the key name
    # invites being read as a verdict. Rename it here rather than leaving a
    # field called "gates_passed" sitting in a development artefact.
    record["diagnostic_gates_passed"] = record.pop("gates_passed")
    record["diagnostic_failed_gates"] = record.pop("failed_gates")

    return record, run.predictions.dropna(), assessment


def _fmt(value) -> str:
    return "     n/a" if value is None else f"{value:+.5f}"


def _fmt_ci(ci) -> str:
    if not ci or ci[0] is None:
        return "n/a"
    return f"[{ci[0]:+.5f}, {ci[1]:+.5f}]"


# ----------------------------------------------------------------------
# The A->B->C->D deltas (§6.2) — paired, so the day cancels
# ----------------------------------------------------------------------

DELTAS = (("V2.1-A", "V2.1-B"), ("V2.1-B", "V2.1-C"), ("V2.1-C", "V2.1-D"))


def rung_deltas(ic_series: dict[str, pd.Series]) -> dict[str, dict]:
    """Each step of the ladder as a paired per-cutoff IC difference.

    The point of a ladder is the steps, not the rungs: two arms scored on the
    same cutoffs differ by their columns and by nothing else, so differencing
    them removes the day, the universe and the market.
    """
    out = {}
    for lower, upper in DELTAS:
        if lower not in ic_series or upper not in ic_series:
            continue
        series = stats.paired_difference(ic_series[upper], ic_series[lower],
                                         f"{upper} IC - {lower} IC")
        low, high = series.bootstrap_ci()
        out[f"{lower}->{upper}"] = {
            **series.row(),
            "ci": [_round(low, 5), _round(high, 5)],
            "moves_the_number": bool(series.n and series.excludes_null()),
        }
    return out


def _round(value, places: int):
    if value is None:
        return None
    value = float(value)
    return None if not np.isfinite(value) else round(value, places)


# ----------------------------------------------------------------------
# §5 — selection and the gate on opening the exam
# ----------------------------------------------------------------------

GATE_BENCHMARK = "b1_momentum_12_1"


def select_exam_arm(records: dict[str, dict]) -> str | None:
    """§5.1: highest mean development IC among the candidate arms {B, C, D}.

    A is excluded by pre-registration, not by its number: §2 establishes that an
    arm given only `ret_12_1` is Benchmark 1 up to non-monotonicity, and an arm
    that *is* the benchmark scores a paired difference of ~0 against it. Sending
    it to the exam would spend 72 irreplaceable dates confirming an identity.

    Ties go to the simpler arm, which is why the ladder order breaks them.
    """
    order = {arm.name: index for index, arm in enumerate(ARMS)}
    candidates = [name for name in records if ARMS_BY_NAME[name].candidate]
    if not candidates:
        return None

    def key(name: str):
        mean = records[name]["ic"]["mean"]
        mean = mean if mean is not None and np.isfinite(mean) else -9.0
        return (-mean, order[name])

    return sorted(candidates, key=key)[0]


def gate(record: dict) -> dict:
    """§5.2: does this arm beat 12-1 momentum on development, CI excluding 0?

    Deliberately weaker than the exam demands — one of nine criteria, not nine.
    It cannot let through anything the exam would not also judge, and it cannot
    be satisfied by an arm the exam would pass. What it can do is refuse to
    spend 72 non-renewable dates re-deriving a conclusion 316 cutoffs already
    reached with four times the power.
    """
    versus = (record.get("criteria") or {}).get("5_beats_12_1_momentum") or {}
    value, ci = versus.get("value"), versus.get("ci") or [None, None]
    passed = bool(value is not None and value > 0 and ci[0] is not None and ci[0] > 0)
    return {
        "criterion": "development paired IC difference vs Benchmark 1 (12-1 momentum, +1)",
        "threshold": "> 0 and 95% block-bootstrap CI excludes 0",
        "value": value,
        "ci": ci,
        "n_cutoffs": record.get("n_cutoffs"),
        "passed": passed,
        "consequence": ("the exam may be opened on this arm" if passed else
                        "the exam stays sealed; the ladder's result is a null and "
                        "production stays at weight 0 / HOLD (§5.2)"),
    }


# ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="V2.1 ladder — development only")
    parser.add_argument("--only", nargs="*", default=None,
                        help="run a subset, e.g. --only V2.1-A V2.1-B. The family "
                             "size for the multiplicity correction stays 4.")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, _v2_development, _v2_exam = build_panel.load()
    exam_set = examset.load()

    # The one line that keeps §7. `development_only` slices to the frozen
    # development list and asserts no exam cutoff survived, rather than trusting
    # the slice — `slice_cutoffs` takes a keep-list and would not complain.
    panel = examset.development_only(panel, exam_set)
    calendar = pitdata.load_calendar()

    print(f"protocol   V2.1, exam digest {exam_set.digest[:16]}… (not read below)")
    print(f"panel      {len(panel.frame):,} rows  ·  {len(panel.cutoffs)} development "
          f"cutoffs  ·  {panel.cutoffs[0].date()} .. {panel.cutoffs[-1].date()}")
    print(f"arms       {len(ARMS)} pre-registered, family size k={FAMILY_SIZE}")
    print(f"see        {PREREGISTRATION}")

    wanted = set(args.only) if args.only else None
    if wanted and (unknown := wanted - set(ARMS_BY_NAME)):
        raise SystemExit(f"no such arm: {sorted(unknown)}")

    records: dict[str, dict] = {}
    ic_series: dict[str, pd.Series] = {}
    predictions: dict[str, pd.Series] = {}

    for arm in ARMS:
        if wanted is not None and arm.name not in wanted:
            continue
        record, prediction, assessment = run_arm(arm, panel, calendar)
        records[arm.name] = record
        ic_series[arm.name] = assessment.evaluation.ic.clean
        predictions[arm.name] = prediction

    # §6.2 — the steps, which is what a ladder is for.
    deltas = rung_deltas(ic_series)
    print("\n=== ladder deltas (paired per-cutoff IC difference)")
    for step, entry in deltas.items():
        print(f"    {step:<20} {entry['mean']:+.5f}  CI {_fmt_ci(entry['ci'])}  "
              f"{'moves the number' if entry['moves_the_number'] else 'null'}")

    # §4 — Holm over the family of four, whatever subset actually ran.
    holm = stats.holm_bonferroni({k: v["ic"]["p_boot"] for k, v in records.items()})
    for name, verdict in holm.items():
        if name in records:
            records[name]["multiplicity_on_development"] = verdict

    # §5 — selection, then the gate. In that order: the arm is chosen on mean
    # development IC and only then asked whether it beat the benchmark, so the
    # choice cannot be made by the gate.
    selected = select_exam_arm(records)
    gate_verdict = gate(records[selected]) if selected else {
        "passed": False, "consequence": "no candidate arm was run"}

    print(f"\n=== §5.1 exam candidate: {selected or 'none'} "
          f"(highest mean development IC among B/C/D; A excluded by pre-registration)")
    print(f"=== §5.2 gate: {'OPEN' if gate_verdict['passed'] else 'CLOSED'} — "
          f"vs 12-1 momentum {_fmt(gate_verdict.get('value'))} "
          f"CI {_fmt_ci(gate_verdict.get('ci'))}")
    print(f"           {gate_verdict['consequence']}")

    record = {
        "protocol": "V2.1",
        "stage": "ladder / development",
        "preregistration": PREREGISTRATION,
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "exam_set_digest": exam_set.digest,
        "development_cutoffs": len(panel.cutoffs),
        "rows": int(len(panel.frame)),
        "first_cutoff": str(panel.cutoffs[0].date()),
        "last_cutoff": str(panel.cutoffs[-1].date()),
        "refit_sessions": walkforward.REFIT_SESSIONS,
        "min_train_cutoffs": walkforward.MIN_TRAIN_CUTOFFS,
        "family_size": FAMILY_SIZE,
        "arms": records,
        "ladder_deltas": deltas,
        "holm_bonferroni_on_development": holm,
        "excluded_features_note": EXCLUDED_RELATIVE_TIER_NOTE,
        "exam_configuration": {
            "arm": selected,
            "feature_columns": records[selected]["feature_columns"] if selected else None,
            "train_target": records[selected]["train_target"] if selected else None,
            "chosen_by": ("highest mean development IC among the candidate arms "
                          "{V2.1-B, V2.1-C, V2.1-D}; V2.1-A excluded by §5.1"),
            "family_size_for_exam_correction": FAMILY_SIZE,
            "gate": gate_verdict,
            "exam_may_be_opened": bool(gate_verdict["passed"]),
        },
        "production_weight": 0.0,
        "production_weight_note": (
            "Unchanged and not a result of this stage. Weight moves off 0 only "
            "after all nine gates of V2_1_PREREGISTRATION.md §4 pass on the frozen "
            "exam set with the k=4 correction of the ladder pre-registration §4."),
    }
    JSON_PATH.write_text(json.dumps(develop._jsonable(record), indent=2), encoding="utf-8")
    pd.to_pickle({"ic_series": ic_series, "predictions": predictions,
                  "deltas": deltas}, PICKLE_PATH)
    print(f"\nfroze      {JSON_PATH}")
    print(f"froze      {PICKLE_PATH}")


if __name__ == "__main__":
    main()
