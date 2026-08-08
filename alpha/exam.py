"""Stage 2 — the exam paper. Twelve frozen dates, opened once.

Two entry points, and they are separate on purpose:

    python -m alpha.exam predict     writes out/exam_predictions.json
    python -m alpha.exam score       reads it and writes out/exam_scores.json

`predict` refuses to overwrite an existing predictions file. That is the same
rule as `validation/predict.py`, and it exists because regenerating a frozen
prediction after its outcome is known is the one failure this whole study is
built to make impossible. Re-running requires deliberately deleting the file,
which is a thing a person does on purpose and then has to explain.

Nothing here chooses anything. The feature set, the training target, the
baseline factor and the baseline's sign are all read out of
`out/development.json`, where they were frozen before these dates were touched.
If that file is missing, this refuses to run rather than picking a default —
a default chosen at exam time is a choice made on exam data.

Training uses **development cutoffs only**, with the same horizon-plus-embargo
boundary as development: a model predicting 2026-05-07 is fitted on cutoffs
whose outcome windows closed at least ten sessions earlier. Exam rows are never
in a training slice, and their outcome columns are never read on the predict
side — `Fit.predict` reindexes to the feature columns and can see nothing else.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

from . import build_panel, develop, models, pitdata, stats, walkforward

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
PREDICTIONS_PATH = OUT_DIR / "exam_predictions.json"
SCORES_PATH = OUT_DIR / "exam_scores.json"

# Outcome-derived columns. Asserted absent from the predictions payload, so a
# future edit that helpfully "includes the target for convenience" fails loudly.
OUTCOME_COLUMNS = ("alpha_5d", "asset_return", "spy_return", "sector_return",
                   "sector_relative", "residual_alpha", "target_train",
                   "target_rank", "target_vol_scaled", "quintile", "horizon_end")


def _frozen_configuration() -> dict:
    if not develop.JSON_PATH.exists():
        raise SystemExit(f"no {develop.JSON_PATH} — run: python -m alpha.develop\n"
                         "The exam does not choose its own configuration.")
    record = json.loads(develop.JSON_PATH.read_text(encoding="utf-8"))
    configuration = record.get("exam_configuration") or {}
    if not configuration.get("experiment"):
        raise SystemExit("development.json has no frozen exam_configuration.")
    return configuration


# ----------------------------------------------------------------------
# Stage 2a — predict
# ----------------------------------------------------------------------

def predict() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if PREDICTIONS_PATH.exists():
        raise SystemExit(
            f"{PREDICTIONS_PATH} already exists — delete it to re-run the exam.\n"
            "Regenerating a frozen prediction after its outcome is known is the "
            "one thing this study is built to prevent.")

    configuration = _frozen_configuration()
    panel, development, exam = build_panel.load()
    calendar = pitdata.load_calendar()

    tiers = tuple(configuration["tiers"])
    columns = develop.columns_for(panel, tiers)
    target = configuration["train_target"]
    name = configuration["experiment"]

    print(f"exam       {name} — {len(columns)} features {tiers}, target `{target}`")
    print(f"training   development cutoffs only ({len(development)} available)")
    print(f"dates      {len(exam)} frozen cutoffs, "
          f"{exam[0].date()} .. {exam[-1].date()}")

    if name == "V2-D":
        fitter = develop._sector_rank_fitter()
    else:
        fitter = lambda train, cols: models.fit_model_a(train, cols, target=target)  # noqa: E731

    run = walkforward.walk_forward(panel, calendar, columns, fit_fn=fitter, name=name,
                                   restrict_test_to=exam, train_pool=development)

    # Model A′, at the factor and sign frozen on development data. Computed on
    # the feature side only — it is a within-cutoff rank of a pre-cutoff return.
    factor = configuration["baseline_factor"]
    sign = int(configuration["baseline_sign"])
    exam_block = panel.frame[panel.frame.index.get_level_values(0).isin(pd.DatetimeIndex(exam))]
    baseline_scores = models.simple_factor_scores(exam_block)[factor] * sign

    rows = []
    for (cutoff, symbol), value in run.predictions.dropna().items():
        rows.append({"cutoff": str(pd.Timestamp(cutoff).date()), "symbol": symbol,
                     "predicted": float(value),
                     "baseline": _finite(baseline_scores.get((cutoff, symbol)))})

    # Rank percentile within cutoff — the §24-26 presentation field, computed
    # here so the number that reaches the adapter is the number that was scored.
    frame = pd.DataFrame(rows)
    frame["rank_pct"] = frame.groupby("cutoff")["predicted"].rank(pct=True)

    leaked = [c for c in OUTCOME_COLUMNS if c in frame.columns]
    if leaked:
        raise RuntimeError(f"predictions payload carries outcome columns: {leaked}")

    payload = {
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "configuration": configuration,
        "n_features": len(columns),
        "feature_columns": columns,
        "refits": run.fits,
        "cutoffs": [str(c.date()) for c in exam],
        "development_cutoffs_available": len(development),
        "predictions": frame.to_dict(orient="records"),
    }
    PREDICTIONS_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nfroze      {len(frame):,} predictions over "
          f"{frame['cutoff'].nunique()} cutoffs -> {PREDICTIONS_PATH}")
    print("           scoring is a separate process: python -m alpha.exam score")


def _finite(value) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


# ----------------------------------------------------------------------
# Stage 2b — score
# ----------------------------------------------------------------------

def score() -> None:
    if not PREDICTIONS_PATH.exists():
        raise SystemExit(f"no {PREDICTIONS_PATH} — run: python -m alpha.exam predict")

    payload = json.loads(PREDICTIONS_PATH.read_text(encoding="utf-8"))
    panel, _development, exam = build_panel.load()
    panel = panel.slice_cutoffs(exam)
    name = payload["configuration"]["experiment"]

    predictions = pd.DataFrame(payload["predictions"])
    predictions["cutoff"] = pd.to_datetime(predictions["cutoff"])
    predictions = predictions.set_index(["cutoff", "symbol"]).sort_index()

    evaluation = walkforward.evaluate(panel, predictions["predicted"], name)

    baseline = panel.frame[["alpha_5d"]].copy()
    baseline["prediction"] = predictions["baseline"]
    baseline_ic = stats.ic_by_cutoff(baseline, "prediction", "alpha_5d")
    baseline_name = (f"A′ {payload['configuration']['baseline_factor']}"
                     f"({int(payload['configuration']['baseline_sign']):+d})")
    versus = stats.paired_difference(evaluation.ic.clean, baseline_ic,
                                     f"{name} IC − {baseline_name} IC")

    criteria = evaluation.criteria(versus)
    passed, failed = evaluation.verdict(versus)

    print(f"exam       {name}, {evaluation.ic.n} scored cutoffs, "
          f"{len(predictions):,} predictions")
    print(f"           mean IC {evaluation.ic.mean:+.5f}  "
          f"hit {evaluation.ic.hit_rate:.1%}  "
          f"spread {evaluation.spread.mean:+.5f}  "
          f"vs {baseline_name} {versus.mean:+.5f}")
    for key, value in criteria.items():
        print(f"           {'PASS' if value['passed'] else 'FAIL'}  {key:<22} "
              f"{value['value']}")

    # §8's criterion 7 asks for >= 50 independent cutoffs. The exam paper is 12
    # dates, fixed in V1 and not expandable without un-freezing it. So criterion
    # 7 cannot be met here by construction, and §9's "all seven on the exam set"
    # therefore holds production weight at 0 regardless of what the other six
    # say. That is a defect in the pre-registration, not a result — it is
    # reported as one rather than quietly dropped or redefined.
    sample_note = (
        f"Criterion 7 requires >= {walkforward.THRESHOLD_MIN_CUTOFFS} cutoffs; the "
        f"exam paper is {evaluation.ic.n}. It cannot pass on this set. Under §9 that "
        "holds production weight at 0 by construction. Reported, not relaxed: the "
        "twelve dates were frozen by V1 and cannot be extended without un-freezing "
        "them. The other six criteria are still reported on their own terms, and "
        "the development set is where criterion 7 was actually testable.")

    six = {k: v for k, v in criteria.items() if k != "7_effective_sample"}
    record = {
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "predictions_written_at": payload["written_at"],
        "configuration": payload["configuration"],
        "n_cutoffs": evaluation.ic.n,
        "n_predictions": int(len(predictions)),
        "ic": evaluation.ic.row(),
        "spread": evaluation.spread.row(),
        "top_quintile": evaluation.top.row(),
        "bottom_quintile": evaluation.bottom.row(),
        "baseline": {"name": baseline_name,
                     "ic": stats.Series(baseline_name, baseline_ic).row()},
        "versus_simple_factor": versus.row(),
        "regime_ic": evaluation.regime_ic.to_dict(orient="index"),
        "per_cutoff": {str(k.date()): _row(v)
                       for k, v in evaluation.per_cutoff.iterrows()},
        "criteria": criteria,
        "passed_all_seven": bool(passed),
        "failed_criteria": failed,
        "passed_six_excluding_sample_size": all(v["passed"] for v in six.values()),
        "criterion_7_note": sample_note,
        "production_weight": 0.0 if not passed else 0.0,
        "production_weight_note": (
            "0 under §9 in every branch reachable from a 12-date exam. Raising it "
            "would require a larger frozen exam set, agreed in advance."),
    }
    SCORES_PATH.write_text(json.dumps(develop._jsonable(record), indent=2),
                           encoding="utf-8")
    print(f"\nverdict    {'PASS' if passed else 'FAIL'} — "
          f"failed {', '.join(failed) if failed else 'nothing'}")
    print(f"           {sample_note}")
    print(f"wrote      {SCORES_PATH}")


def _row(series: pd.Series) -> dict:
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else v)
            for k, v in series.items() if k in ("ic", "top", "bottom", "spread",
                                                "n", "trend", "vol")}


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    action = argv[0] if argv else ""
    if action == "predict":
        predict()
    elif action == "score":
        score()
    else:
        raise SystemExit("usage: python -m alpha.exam {predict|score}\n"
                         "  predict  fit on development cutoffs, write exam_predictions.json\n"
                         "  score    read that file, join outcomes, write exam_scores.json")


if __name__ == "__main__":
    main()
