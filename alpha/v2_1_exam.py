"""Stage 2 of V2.1 — the 72 frozen cutoffs, opened once, under the nine gates.

`alpha/exam.py` is left untouched: it is the record of V2's twelve-date paper
and a finished experiment. This is the V2.1 paper, and the two must stay
distinguishable.

Two entry points, separate on purpose:

    python -m alpha.v2_1_exam predict     writes out/v2_1_exam_predictions.json
    python -m alpha.v2_1_exam score       reads it, writes out/v2_1_exam_scores.json

`predict` refuses to overwrite an existing predictions file. Regenerating a
frozen prediction after its outcome is known is the one failure this study is
built to make impossible, so re-running means deleting the file on purpose and
explaining it in `V2_1_EXPERIMENT_LOG.md`.

**Nothing here chooses anything, and nothing here may run on its own judgement.**
The arm, its feature list and its training target are read out of
`out/v2_1_development.json`, where `alpha.ladder` froze them. So is the §5.2
gate verdict — and if that gate is closed, `predict` refuses to run at all. A
closed gate is the study's result, not a suggestion; opening the exam "just to
see" is ruled out in writing in `V2_1_LADDER_PREREGISTRATION.md` §5.2.

Training uses **development cutoffs only**, with the same horizon-plus-embargo
boundary as the ladder. Exam rows are never in a training slice, and no outcome
column reaches the predictions payload — asserted, not intended.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

from . import (build_panel, develop, examset, ladder, models, pitdata,
               protocol, walkforward)

# stderr as well as stdout: the §5.2 refusal is raised as SystemExit, so the one
# message that most needs to be legible on a Windows console goes out on stderr.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
PREDICTIONS_PATH = OUT_DIR / "v2_1_exam_predictions.json"
SCORES_PATH = OUT_DIR / "v2_1_exam_scores.json"

# Outcome-derived columns. Asserted absent from the predictions payload, so a
# future edit that helpfully "includes the target for convenience" fails loudly.
OUTCOME_COLUMNS = ("alpha_5d", "asset_return", "spy_return", "sector_return",
                   "sector_relative", "residual_alpha", "target_train",
                   "target_rank", "target_vol_scaled", "quintile", "horizon_end")


def _frozen_configuration() -> dict:
    if not ladder.JSON_PATH.exists():
        raise SystemExit(f"no {ladder.JSON_PATH} — run: python -m alpha.ladder\n"
                         "The exam does not choose its own configuration.")
    record = json.loads(ladder.JSON_PATH.read_text(encoding="utf-8"))
    configuration = record.get("exam_configuration") or {}
    if not configuration.get("arm"):
        raise SystemExit("v2_1_development.json has no frozen exam_configuration.")
    if not configuration.get("exam_may_be_opened"):
        gate = configuration.get("gate") or {}
        raise SystemExit(
            "the §5.2 gate is CLOSED — the exam stays sealed.\n"
            f"  {gate.get('criterion')}\n"
            f"  threshold {gate.get('threshold')}\n"
            f"  measured  {gate.get('value')} CI {gate.get('ci')} "
            f"over {gate.get('n_cutoffs')} development cutoffs\n"
            "A closed gate is the ladder's result. Opening the exam anyway, "
            "swapping the gate's benchmark, or relaxing it to 'mean > 0' are each "
            "ruled out in V2_1_LADDER_PREREGISTRATION.md §5.2.")
    return configuration


# ----------------------------------------------------------------------
# Stage 2a — predict
# ----------------------------------------------------------------------

def predict() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if PREDICTIONS_PATH.exists():
        raise SystemExit(
            f"{PREDICTIONS_PATH} already exists — delete it to re-run the V2.1 exam.\n"
            "That is a deliberate act and it gets an entry in "
            "V2_1_EXPERIMENT_LOG.md, written before the re-run.")

    configuration = _frozen_configuration()
    exam_set = examset.load()
    panel, _v2_development, _v2_exam = build_panel.load()
    calendar = pitdata.load_calendar()

    columns = list(configuration["feature_columns"])
    target = configuration["train_target"]
    name = configuration["arm"]

    missing = [c for c in exam_set.cutoffs if c not in set(panel.cutoffs)]
    if missing:
        raise SystemExit(f"{len(missing)} exam cutoffs have no rows in the panel — "
                         "rebuild it. This is the bug that crashed V2's first exam run.")

    print(f"protocol   V2.1, exam digest {exam_set.digest}")
    print(f"arm        {name} — {len(columns)} features, target `{target}`")
    print(f"training   development cutoffs only ({len(exam_set.development)} available)")
    print(f"dates      {len(exam_set.cutoffs)} frozen cutoffs, "
          f"{exam_set.cutoffs[0].date()} .. {exam_set.cutoffs[-1].date()}")

    fitter = lambda train, cols: models.fit_model_a(train, cols, target=target)  # noqa: E731
    run = walkforward.walk_forward(panel, calendar, columns, fit_fn=fitter, name=name,
                                   restrict_test_to=exam_set.cutoffs,
                                   train_pool=exam_set.development)

    leaked = sorted(set(run.evaluated_cutoffs) - set(exam_set.cutoffs))
    if leaked:
        raise RuntimeError(f"predictions cover non-exam cutoffs: {leaked[:5]}")

    # The three benchmarks, feature-side only: each is a within-cutoff rank of a
    # pre-cutoff return times a sign fixed before any of this ran. Computed here
    # so the numbers the scorer compares against are the ones frozen with the
    # predictions rather than recomputed after the outcome is known.
    exam_block = panel.frame[panel.frame.index.get_level_values(0).isin(exam_set.index)]
    benchmarks = protocol.benchmark_scores(exam_block, panel.regimes)

    rows = []
    for (cutoff, symbol), value in run.predictions.dropna().items():
        row = {"cutoff": str(pd.Timestamp(cutoff).date()), "symbol": symbol,
               "predicted": float(value)}
        for key in benchmarks.columns:
            row[key] = _finite(benchmarks[key].get((cutoff, symbol)))
        rows.append(row)

    frame = pd.DataFrame(rows)
    frame["rank_pct"] = frame.groupby("cutoff")["predicted"].rank(pct=True)

    leaked_columns = [c for c in OUTCOME_COLUMNS if c in frame.columns]
    if leaked_columns:
        raise RuntimeError(f"predictions payload carries outcome columns: {leaked_columns}")

    payload = {
        "protocol": "V2.1",
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "preregistration": [ladder.PREREGISTRATION, "alpha/V2_1_PREREGISTRATION.md"],
        "exam_set_digest": exam_set.digest,
        "configuration": configuration,
        "n_features": len(columns),
        "feature_columns": columns,
        "refits": run.fits,
        "cutoffs": [str(c.date()) for c in exam_set.cutoffs],
        "development_cutoffs_available": len(exam_set.development),
        "predictions": frame.to_dict(orient="records"),
    }
    PREDICTIONS_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nfroze      {len(frame):,} predictions over "
          f"{frame['cutoff'].nunique()} cutoffs -> {PREDICTIONS_PATH}")
    print("           scoring is a separate process: python -m alpha.v2_1_exam score")


def _finite(value) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


# ----------------------------------------------------------------------
# Stage 2b — score
# ----------------------------------------------------------------------

def score() -> None:
    if not PREDICTIONS_PATH.exists():
        raise SystemExit(f"no {PREDICTIONS_PATH} — run: python -m alpha.v2_1_exam predict")

    payload = json.loads(PREDICTIONS_PATH.read_text(encoding="utf-8"))
    exam_set = examset.load()
    if payload.get("exam_set_digest") != exam_set.digest:
        raise RuntimeError(
            "the frozen exam set has changed since these predictions were written: "
            f"{payload.get('exam_set_digest')} -> {exam_set.digest}")

    panel, _v2_development, _v2_exam = build_panel.load()
    panel = panel.slice_cutoffs(exam_set.cutoffs)
    name = payload["configuration"]["arm"]

    predictions = pd.DataFrame(payload["predictions"])
    predictions["cutoff"] = pd.to_datetime(predictions["cutoff"])
    predictions = predictions.set_index(["cutoff", "symbol"]).sort_index()

    assessment = protocol.assess(panel, predictions["predicted"], name)
    criteria = assessment.criteria()
    passed, failed = assessment.verdict()

    # §4 of the ladder pre-registration: the arm on the exam is the maximum of
    # four development ICs, so it carries the family of four. With one p-value
    # Holm and Bonferroni coincide.
    family = int(payload["configuration"].get("family_size_for_exam_correction",
                                              ladder.FAMILY_SIZE))
    raw_p = assessment.evaluation.ic.bootstrap_p()
    adjusted = min(1.0, family * raw_p) if np.isfinite(raw_p) else float("nan")
    multiplicity = {
        "family_size": family,
        "p_raw": _round(raw_p, 5),
        "p_adjusted": _round(adjusted, 5),
        "significant_at_0.05": bool(np.isfinite(adjusted) and adjusted < 0.05),
        "rule": ("the exam arm is the maximum of four development ICs, so k=4 "
                 "(ladder pre-registration §4); with one p-value Holm = Bonferroni"),
    }
    verdict = bool(passed and multiplicity["significant_at_0.05"])

    ic = assessment.evaluation.ic
    print(f"protocol   V2.1, exam digest {exam_set.digest[:16]}…")
    print(f"exam       {name}, {ic.n} scored cutoffs, {len(predictions):,} predictions")
    print(f"           mean IC {ic.mean:+.5f}  hit {ic.hit_rate:.1%}  "
          f"spread {assessment.evaluation.spread.mean:+.5f}  "
          f"net@5bps {assessment.net.mean:+.5f}")
    for key, value in criteria.items():
        mark = ("PASS" if value["passed"] else "FAIL") if value.get("gate") else "    "
        print(f"           {mark}  {key:<28} {_short(value['value'])}")
    print(f"           Holm k={family}: p_raw {multiplicity['p_raw']} -> "
          f"p_adj {multiplicity['p_adjusted']}")

    record = {
        "protocol": "V2.1",
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "predictions_written_at": payload["written_at"],
        "preregistration": payload["preregistration"],
        "exam_set_digest": exam_set.digest,
        "configuration": payload["configuration"],
        "n_predictions": int(len(predictions)),
        **assessment.record(),
        "per_cutoff": {str(pd.Timestamp(k).date()): _row(v)
                       for k, v in assessment.evaluation.per_cutoff.iterrows()},
        "multiplicity": multiplicity,
        "all_nine_gates_passed": bool(passed),
        "verdict_after_multiplicity": verdict,
        "failed_gates": failed,
        "production_weight": 0.0,
        "production_weight_note": (
            "0 unless every gate passed AND the Holm-corrected p-value clears 0.05. "
            "Even then, V2_1_PREREGISTRATION.md §2.6 stands: these dates lie inside "
            "the window V2's development ladder ran over, so a pass is evidence "
            "about a model, not about a feature family."),
    }
    SCORES_PATH.write_text(json.dumps(develop._jsonable(record), indent=2), encoding="utf-8")
    print(f"\nverdict    {'PASS' if verdict else 'FAIL'} — "
          f"failed {', '.join(failed) if failed else 'no gate'}"
          + ("" if multiplicity["significant_at_0.05"] else
             f"; not significant after the k={family} correction"))
    print(f"wrote      {SCORES_PATH}")


def _round(value, places: int):
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), places)


def _short(value):
    if isinstance(value, dict):
        return "{…}"
    return value


def _row(series: pd.Series) -> dict:
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else v)
            for k, v in series.items()
            if k in ("ic", "top", "bottom", "spread", "n", "trend", "vol")}


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    action = argv[0] if argv else ""
    if action == "predict":
        predict()
    elif action == "score":
        score()
    else:
        raise SystemExit(
            "usage: python -m alpha.v2_1_exam {predict|score}\n"
            "  predict  fit on development cutoffs, write v2_1_exam_predictions.json\n"
            "  score    read that file, join outcomes, write v2_1_exam_scores.json")


if __name__ == "__main__":
    main()
