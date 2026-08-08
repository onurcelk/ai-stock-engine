"""Stage 1 — the §27 experiment ladder, run on development cutoffs only.

The exam paper does not exist as far as this file is concerned. `build_panel`
froze both halves into one pickle because a row is not a result, but the first
thing `main` does is slice to the development cutoffs and throw the rest away,
and nothing downstream of that slice can see an exam date. That is the whole
discipline of §19 expressed as three lines of code, and it is deliberately at
the top of the file where it can be checked.

What runs, in order (§27, and §14's correction that A′ comes *before* B):

    A′    six simple factors, ranked within cutoff. Measured first. The best
          one by |mean IC| — and its sign — are frozen here, on development
          data, and become the reference every later gate is judged against.
    V2-A  absolute features only.
    V2-B  + relative and percentile features.
    V2-E  + regime / VIX / breadth / overnight context.
    V2-F  the V2-E feature set trained on the volatility-scaled target.
    V2-C  pointwise ranker — built only if A or B passed criteria 1-5 on dev.
    V2-D  sector-neutral ranker — built only if V2-C passed.

V2-F is scored against `alpha_5d` like everything else. Training on a
vol-scaled target is a change to the model; scoring it on a vol-scaled target
would be a change to the yardstick, and §10 rules out switching the headline
metric after the fact. Its IC against its own training target is reported
alongside as a diagnostic, clearly labelled as one.

Output: `alpha/out/development.json` (the record) and `development.pkl` (the
per-cutoff series, for the report and for `alpha.exam` to read the frozen
choices out of). Neither is allowed to be edited to match a later result.

Run:  python -m alpha.develop            # everything
      python -m alpha.develop --probe    # time a single fit and stop
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

from . import build_panel, dataset, models, pitdata, stats, walkforward

# The prose in this study uses §, ′ and · throughout; a Windows console defaults
# to cp1252 and dies on all three. Widen the stream rather than transliterate
# the names, so "Model A′" is the same string in the log and in the JSON.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
JSON_PATH = OUT_DIR / "development.json"
PICKLE_PATH = OUT_DIR / "development.pkl"

# ----------------------------------------------------------------------
# Tier membership. The panel holds all 100 columns; an experiment is defined
# by which of them it is allowed to look at.
# ----------------------------------------------------------------------

RELATIVE_SUFFIXES = ("__vs_spy", "__vs_sector", "__pct")
CONTEXT_PREFIXES = ("overnight_", "intraday_", "mkt_", "vix_", "index_breadth",
                    "index_advance_", "watchlist_breadth_proxy_", "regime_")
# Both betas are estimated against SPY (and against a SPY-orthogonalised sector
# series), so they are market-relative quantities and belong to the V2-B tier.
# Putting them in V2-A would let the "absolute only" arm quietly carry a
# relative feature, which is the one thing the A-vs-B contrast exists to isolate.
RELATIVE_EXTRA = ("beta_market", "beta_sector")

TIERS = {
    "V2-A": ("absolute",),
    "V2-B": ("absolute", "relative"),
    "V2-E": ("absolute", "relative", "context"),
    "V2-F": ("absolute", "relative", "context"),
    "V2-C": ("absolute", "relative", "context"),
    "V2-D": ("absolute", "relative", "context"),
}


def tier_of(column: str) -> str:
    if column.endswith(RELATIVE_SUFFIXES) or column in RELATIVE_EXTRA:
        return "relative"
    if column.startswith(CONTEXT_PREFIXES):
        return "context"
    return "absolute"


def columns_for(panel: dataset.Panel, tiers: tuple[str, ...]) -> list[str]:
    return [c for c in panel.feature_columns if tier_of(c) in tiers]


# ----------------------------------------------------------------------
# Experiment definition
# ----------------------------------------------------------------------

@dataclasses.dataclass
class Experiment:
    """One rung of the §27 ladder: a feature tier set, a target, and a fitter."""

    name: str
    tiers: tuple[str, ...]
    train_target: str
    note: str
    gated: bool = False

    def fitter(self):
        target = self.train_target
        return lambda train, columns: models.fit_model_a(train, columns, target=target)


UNGATED = [
    Experiment("V2-A", TIERS["V2-A"], "target_train",
               "absolute features, winsorised alpha_5d regression"),
    Experiment("V2-B", TIERS["V2-B"], "target_train",
               "+ relative (vs SPY, vs PIT sector) and cross-sectional percentile"),
    Experiment("V2-E", TIERS["V2-E"], "target_train",
               "+ regime / VIX / index breadth / overnight-intraday split"),
    Experiment("V2-F", TIERS["V2-F"], "target_vol_scaled",
               "V2-E features, volatility-scaled target; scored on alpha_5d"),
]


def _sector_rank_fitter():
    """Model C's target is built per fit, because it needs the training slice's sectors."""
    return lambda train, columns: models.fit_model_c(train, columns, gate_passed=True)


GATED = [
    Experiment("V2-C", TIERS["V2-C"], "target_rank",
               "pointwise cross-sectional ranker (NOT LambdaRank — lightgbm absent)",
               gated=True),
    Experiment("V2-D", TIERS["V2-D"], "target_sector_rank",
               "sector-neutral ranker: percentile within PIT sector, not universe",
               gated=True),
]


# ----------------------------------------------------------------------
# Running one rung
# ----------------------------------------------------------------------

def run_experiment(experiment: Experiment, panel: dataset.Panel, calendar,
                   baseline_ic: pd.Series, baseline_name: str
                   ) -> tuple[dict, walkforward.Run, walkforward.Evaluation]:
    """Walk forward, evaluate, and judge against the frozen simple-factor baseline."""
    columns = columns_for(panel, experiment.tiers)
    fitter = _sector_rank_fitter() if experiment.name == "V2-D" else experiment.fitter()

    print(f"\n=== {experiment.name} — {experiment.note}")
    print(f"    {len(columns)} features, target `{experiment.train_target}`")
    started = time.time()
    run = walkforward.walk_forward(panel, calendar, columns, fit_fn=fitter,
                                   name=experiment.name)
    elapsed = time.time() - started

    evaluation = walkforward.evaluate(panel, run.predictions, experiment.name)

    # Criterion 5 is paired, so it is measured only on cutoffs where both the
    # model and the baseline produced a number. Differencing removes the day.
    versus = stats.paired_difference(evaluation.ic.clean, baseline_ic,
                                     f"{experiment.name} IC − {baseline_name} IC")
    criteria = evaluation.criteria(versus)
    passed, failed = evaluation.verdict(versus)

    print(f"    mean IC {evaluation.ic.mean:+.5f}  hit {evaluation.ic.hit_rate:.1%}  "
          f"spread {evaluation.spread.mean:+.5f}  "
          f"vs {baseline_name} {versus.mean:+.5f}  "
          f"({evaluation.ic.n} cutoffs, {len(run.fits)} refits, {elapsed:.0f}s)")
    print(f"    verdict: {'PASS' if passed else 'FAIL'}"
          + ("" if passed else f" — failed {', '.join(failed)}"))

    record = {
        "name": experiment.name,
        "note": experiment.note,
        "tiers": list(experiment.tiers),
        "n_features": len(columns),
        "train_target": experiment.train_target,
        "scored_against": "alpha_5d",
        "seconds": round(elapsed, 1),
        "refits": run.fits,
        "n_evaluated_cutoffs": evaluation.ic.n,
        "ic": evaluation.ic.row(),
        "spread": evaluation.spread.row(),
        "top_quintile": evaluation.top.row(),
        "bottom_quintile": evaluation.bottom.row(),
        "versus_simple_factor": versus.row(),
        "regime_ic": evaluation.regime_ic.to_dict(orient="index"),
        "criteria": criteria,
        "passed_all_seven": bool(passed),
        "failed_criteria": failed,
        "passed_gate_criteria_1_to_5": _gate_criteria_pass(criteria),
    }
    if experiment.train_target == "target_vol_scaled":
        diagnostic = walkforward.evaluate(panel, run.predictions,
                                          f"{experiment.name} (own target)",
                                          target="target_vol_scaled")
        record["diagnostic_ic_vs_own_target"] = diagnostic.ic.row()

    return record, run, evaluation


GATE_CRITERIA = ("1_mean_ic", "2_ic_hit_rate", "3_top_minus_bottom",
                 "4_sign_stability", "5_beats_simple_factor")


def _gate_criteria_pass(criteria: dict) -> bool:
    """§8's gate on the ranker: criteria 1-5, on development data."""
    return all(criteria[k]["passed"] for k in GATE_CRITERIA if k in criteria)


# ----------------------------------------------------------------------
# Model A′ — measured first, and the reference for every gate (§14, §18)
# ----------------------------------------------------------------------

def measure_simple_factors(panel: dataset.Panel
                           ) -> tuple[dict, str, int, pd.Series, dict[str, pd.Series]]:
    """Six factors, one IC series each; then the frozen choice of factor and sign."""
    print("\n=== Model A′ — six simple factors, measured before anything is fitted")
    by_factor = walkforward.evaluate_simple_factors(panel)
    best, sign = models.choose_best_simple_factor(by_factor)

    rows = {}
    for name, series in sorted(by_factor.items()):
        wrapped = stats.Series(f"A′ {name}", series, null=0.0)
        rows[name] = wrapped.row()
        marker = " <-- chosen" if name == best else ""
        print(f"    {name:<16} mean IC {wrapped.mean:+.5f}  hit {wrapped.hit_rate:.1%}  "
              f"n={wrapped.n}{marker}")

    print(f"    frozen baseline: {best}, sign {sign:+d} "
          f"(chosen on development data only; the exam set gets no vote)")
    baseline_ic = by_factor[best] * sign if best else pd.Series(dtype=float)
    return rows, best, sign, baseline_ic, by_factor


# ----------------------------------------------------------------------
# Timing probe
# ----------------------------------------------------------------------

def probe(panel: dataset.Panel, calendar) -> None:
    """Fit once on the largest training slice there will ever be, and report the cost.

    Worth doing before launching four walk-forwards: the last refit of an
    experiment trains on nearly the whole development panel, so this is an
    upper bound on per-fit cost and the only honest basis for a runtime
    estimate.
    """
    cutoffs = panel.cutoffs
    usable = dataset.training_cutoffs(cutoffs, cutoffs[-1], calendar)
    columns = columns_for(panel, ("absolute", "relative", "context"))
    level0 = panel.frame.index.get_level_values(0)
    train = panel.frame[level0.isin(pd.DatetimeIndex(usable))]

    print(f"probe: largest training slice is {len(train):,} rows x {len(columns)} features "
          f"({len(usable)} cutoffs)")
    started = time.time()
    fit = models.fit_model_a(train, columns)
    elapsed = time.time() - started
    if fit is None:
        print("probe: the fit returned None — too few usable rows. Check the panel.")
        return
    print(f"probe: one fit took {elapsed:.1f}s on {fit.trained_on:,} usable rows")

    refits = 1 + (len(cutoffs) - walkforward.MIN_TRAIN_CUTOFFS) // 13
    print(f"probe: ~{refits} refits per experiment, average slice ~55% of this one")
    print(f"probe: estimate ~{refits * elapsed * 0.55 / 60:.0f} min per experiment, "
          f"~{4 * refits * elapsed * 0.55 / 60:.0f} min for the four ungated arms")


# ----------------------------------------------------------------------

def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return str(value.date())
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true",
                        help="time a single fit on the largest training slice and stop")
    parser.add_argument("--only", nargs="*", default=None,
                        help="run a subset, e.g. --only V2-A V2-B")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, development, exam = build_panel.load()

    # The one line that keeps §19. Everything below sees development cutoffs only.
    panel = panel.slice_cutoffs(development)
    del exam

    calendar = pitdata.load_calendar()

    counts = pd.Series([tier_of(c) for c in panel.feature_columns]).value_counts()
    print(f"panel      {len(panel.frame):,} rows  ·  {len(panel.cutoffs)} development cutoffs")
    print(f"features   {len(panel.feature_columns)} total  ·  "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    if args.probe:
        probe(panel, calendar)
        return

    factor_rows, best_factor, sign, baseline_ic, factor_ic = measure_simple_factors(panel)
    baseline_name = f"A′ {best_factor}({sign:+d})"

    wanted = set(args.only) if args.only else None
    results: dict[str, dict] = {}
    series: dict[str, pd.Series] = {"baseline_ic": baseline_ic}
    predictions: dict[str, pd.Series] = {}

    for experiment in UNGATED:
        if wanted is not None and experiment.name not in wanted:
            continue
        record, run, evaluation = run_experiment(experiment, panel, calendar,
                                                 baseline_ic, baseline_name)
        results[experiment.name] = record
        series[experiment.name] = evaluation.ic.clean
        predictions[experiment.name] = run.predictions.dropna()

    # §8 / §14 / §27: the ranker is built only if A or B cleared criteria 1-5.
    # Strictly A or B — not E — because that is what was pre-registered, and
    # widening the gate after seeing E's number is the move §10 rules out.
    gate_sources = {k: results[k]["passed_gate_criteria_1_to_5"]
                    for k in ("V2-A", "V2-B") if k in results}
    gate_passed = any(gate_sources.values())
    print(f"\n=== §14 gate on the ranker: "
          + ", ".join(f"{k} {'pass' if v else 'fail'}" for k, v in gate_sources.items())
          + f"  ->  {'OPEN' if gate_passed else 'CLOSED'}")

    if gate_passed:
        for experiment in GATED:
            if wanted is not None and experiment.name not in wanted:
                continue
            record, run, evaluation = run_experiment(experiment, panel, calendar,
                                                     baseline_ic, baseline_name)
            results[experiment.name] = record
            series[experiment.name] = evaluation.ic.clean
            predictions[experiment.name] = run.predictions.dropna()
    else:
        print("    V2-C and V2-D are not built. Not built-and-caveated — not built.")

    # §8 multiplicity, across the experiments actually run.
    holm = stats.holm_bonferroni({k: v["ic"]["p_boot"] for k, v in results.items()})
    for name, verdict in holm.items():
        if name in results:
            results[name]["multiplicity"] = verdict

    # The exam configuration, frozen here so `alpha.exam` reads it rather than
    # choosing. One arm goes to the exam paper: predicting all of them there
    # would spend the frozen dates several times over.
    def _mean_ic(entry: dict) -> float:
        value = entry["ic"]["mean"]
        return value if value is not None and np.isfinite(value) else -9.0

    ranked = sorted(results.items(), key=lambda kv: _mean_ic(kv[1]), reverse=True)
    primary = ranked[0][0] if ranked else None
    print(f"\n=== exam configuration frozen: {primary} "
          f"(highest development mean IC; chosen before the exam ran)")

    record = {
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "development_cutoffs": len(panel.cutoffs),
        "rows": int(len(panel.frame)),
        "refit_sessions": walkforward.REFIT_SESSIONS,
        "min_train_cutoffs": walkforward.MIN_TRAIN_CUTOFFS,
        "simple_factors": factor_rows,
        "baseline": {"factor": best_factor, "sign": sign,
                     "chosen_on": "development cutoffs only"},
        "experiments": results,
        "gate_criteria_1_to_5": gate_sources,
        "ranker_gate_open": gate_passed,
        "holm_bonferroni": holm,
        "exam_configuration": {
            "experiment": primary,
            "tiers": results[primary]["tiers"] if primary else None,
            "train_target": results[primary]["train_target"] if primary else None,
            "baseline_factor": best_factor,
            "baseline_sign": sign,
            "chosen_by": "highest mean development IC, frozen before the exam",
        },
    }
    JSON_PATH.write_text(json.dumps(_jsonable(record), indent=2), encoding="utf-8")
    pd.to_pickle({"ic_series": series, "predictions": predictions,
                  "simple_factor_ic": factor_ic}, PICKLE_PATH)
    print(f"\nfroze      {JSON_PATH}")
    print(f"froze      {PICKLE_PATH}")


if __name__ == "__main__":
    main()
