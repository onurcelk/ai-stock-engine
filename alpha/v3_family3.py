"""V3 Family 3 — the information-only test. Runs exactly
`alpha/V3_FAMILY3_PREREGISTRATION.md`.

Phase 5 of master roadmap v2 (§7). No learner is fitted (§2.9).

**This run spends budget slot 3 of 3 — the LAST slot (§21).** If it rejects,
the family-testing programme ends; there is no fourth family and no Family 3'.

Two arms, fixed in §8 of the pre-registration before this file existed:

* **Arm 0** — `rank_pct(inst_holdings_change)`, sign **+1** by economic prior.
* **Arm 1** — `rank_pct(b3) + 0.25 * (rank_pct(x) - 0.5)`.

Primary contrast: **Arm 1 minus B3**, paired per cutoff.

Scoring helpers are imported from `alpha/v3_family1.py` so protocol identity
with Families 1 and 2 is a property of the code, not a claim.

**CRITERION 2 IS NOT INHERITED.** `v3_family1.py` and `v3_family2.py` encode it
as the direction-blind `bool(lo > 0.0 or hi < 0.0)`. Amendment A1 (commit
`830aafc`) requires the interval to exclude zero **on the favourable side**, so
it is written out fresh here as `bool(lo > 0.0)`. Those two modules are left
unmodified so their recorded results stay reproducible.

Writes `alpha/out/v3_family3_development.json` and `.pkl`.
"""

from __future__ import annotations

import json
import pickle
import sys
import time

import numpy as np
import pandas as pd

from . import examset, protocol, stats
from .v3_family1 import (COST_BPS, NOISE_DRAWS, NOISE_EXCEEDANCE_LIMIT,
                         NOISE_MEDIAN_LIMIT, THRESHOLD, _describe, _halves,
                         _ic_series, _regime_split, _spread_series, _turnover)

PANEL = "alpha/out/panel.pkl"
FEATURE_PANEL = "alpha/out/f13_panel.pkl"
OUT_JSON = "alpha/out/v3_family3_development.json"
OUT_PKL = "alpha/out/v3_family3_development.pkl"

LAMBDA = 0.25
FEATURE_SIGN = +1
FEATURE = "change"
TARGET = "alpha_5d"
HORIZON = 5


def build_arms(feature: pd.Series, benchmarks: pd.DataFrame) -> dict[str, pd.Series]:
    feature_rank = feature.groupby(level=0).rank(pct=True, na_option="keep")
    b3_rank = benchmarks["b3_regime_switched"].groupby(
        level=0).rank(pct=True, na_option="keep")
    return {
        "Arm0_holdings_rank": FEATURE_SIGN * feature_rank,
        "Arm1_b3_plus_holdings": b3_rank + LAMBDA * (FEATURE_SIGN * feature_rank - 0.5),
        "_b3_rank": b3_rank,
    }


def run(quiet: bool = False) -> dict:
    started = time.time()
    panel = pickle.load(open(PANEL, "rb"))
    frame, regimes = panel["frame"], panel["regimes"]

    exam = {pd.Timestamp(c) for c in examset.load().cutoffs}
    development = pd.DatetimeIndex(sorted(examset.load().development))
    assert not (exam & set(development)), "exam cutoff reached the development list"
    frame = frame.loc[frame.index.get_level_values("cutoff").isin(development)]
    contamination = len(exam & set(frame.index.get_level_values("cutoff").unique()))
    assert contamination == 0, f"exam contamination: {contamination}"

    # NOT winsorised: §2 of the pre-registration fixes none.
    feature = pickle.load(open(FEATURE_PANEL, "rb"))["feature"][FEATURE]
    feature = feature.reindex(frame.index)

    benchmarks = protocol.benchmark_scores(frame, regimes)
    target = frame[TARGET]
    arms = build_arms(feature, benchmarks)

    ic: dict[str, pd.Series] = {}
    for name, prediction in arms.items():
        ic[name] = _ic_series(prediction, target)
    for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
        ic[key] = _ic_series(benchmarks[key], target)

    base = ic["b3_regime_switched"]
    primary = stats.paired_difference(ic["Arm1_b3_plus_holdings"], base, "Arm1 - B3")

    report: dict = {
        "protocol": "V3",
        "family": "3 - 13F institutional holdings",
        "stage": "Phase 5 information-only",
        "preregistration": "alpha/V3_FAMILY3_PREREGISTRATION.md",
        "amendment": "A1 830aafc62274c6cac29574f3bf2e7458090ed0c8",
        "budget_slot_spent": 3,
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "exam_set_digest": examset.load().digest,
        "exam_contamination": contamination,
        "development_cutoffs": int(len(development)),
        "rows": int(len(frame)),
        "lambda": LAMBDA, "feature_sign": FEATURE_SIGN, "winsor": None,
        "target": TARGET, "horizon_sessions": HORIZON,
        "feature_defined": round(float(feature.notna().mean()), 4),
        "arms": {}, "benchmarks": {}, "primary": {}, "noise_control": {},
    }

    for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
        report["benchmarks"][key] = _describe(ic[key], key)

    p_values = {}
    for name in ("Arm0_holdings_rank", "Arm1_b3_plus_holdings"):
        prediction = arms[name]
        entry = {
            "ic": _describe(ic[name], f"{name} IC"),
            "spread": _describe(_spread_series(prediction, target),
                                f"{name} top-bottom spread"),
            "turnover": round(_turnover(prediction), 4),
            "halves_ic": _halves(ic[name]),
            "versus": {},
        }
        for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
            difference = stats.paired_difference(ic[name], ic[key], f"{name} - {key}")
            entry["versus"][key] = _describe(difference.values, f"{name} vs {key}")
            entry["versus"][key]["halves"] = _halves(difference.values)
            entry["versus"][key]["regimes"] = _regime_split(difference.values, regimes)
        p_values[name] = entry["versus"]["b3_regime_switched"]["p_boot"]
        report["arms"][name] = entry

    report["holm_bonferroni"] = stats.holm_bonferroni(p_values)

    base_spread = _spread_series(arms["_b3_rank"], target)
    for name in ("Arm0_holdings_rank", "Arm1_b3_plus_holdings"):
        spread = _spread_series(arms[name], target)
        common = spread.index.intersection(base_spread.index)
        gross = (spread.reindex(common) - base_spread.reindex(common)).dropna()
        extra_turnover = _turnover(arms[name]) - _turnover(arms["_b3_rank"])
        drag = max(extra_turnover, 0.0) * 2 * (COST_BPS / 10_000.0)
        report["arms"][name]["net_of_cost"] = {
            "gross_spread_advantage": _describe(gross, f"{name} gross spread vs B3"),
            "extra_turnover": round(extra_turnover, 4),
            "cost_drag_per_cutoff": round(drag, 6),
            "net_spread_advantage": round(float(gross.mean() - drag), 6),
        }

    # ---- §2.11 noise control: 30 paired draws, shuffled within cutoff
    rng = np.random.default_rng(20260809)
    draws = []
    for _ in range(NOISE_DRAWS):
        shuffled = feature.groupby(level=0, group_keys=False).apply(
            lambda s: pd.Series(rng.permutation(s.to_numpy()), index=s.index))
        fake = build_arms(shuffled, benchmarks)["Arm1_b3_plus_holdings"]
        draws.append(float(stats.paired_difference(
            _ic_series(fake, target), base, "noise").values.mean()))
    draws = np.array(draws)
    report["noise_control"] = {
        "draws": NOISE_DRAWS, "paired": True,
        "median": round(float(np.median(draws)), 5),
        "mean": round(float(draws.mean()), 5),
        "sd": round(float(draws.std(ddof=1)), 5),
        "share_above_threshold": round(float((draws >= THRESHOLD).mean()), 4),
        "median_limit": NOISE_MEDIAN_LIMIT,
        "exceedance_limit": NOISE_EXCEEDANCE_LIMIT,
        "passed": bool(np.median(draws) <= NOISE_MEDIAN_LIMIT
                       and (draws >= THRESHOLD).mean() <= NOISE_EXCEEDANCE_LIMIT),
    }

    # ---- the four-part CONTINUE rule. Criterion 2 is A1's, written out fresh.
    lo, hi = stats.block_bootstrap_ci(primary.clean.to_numpy(dtype=float))
    arm1 = report["arms"]["Arm1_b3_plus_holdings"]["versus"]["b3_regime_switched"]
    criteria = {
        "1_effect_at_least_0.010": bool(primary.mean >= THRESHOLD),
        # Amendment A1: favourable side only. NOT `lo > 0 or hi < 0`.
        "2_ci_excludes_zero_favourably": bool(lo > 0.0),
        "3_breadth_and_halves": bool(primary.hit_rate > 0.50
                                     and arm1["halves"]["both_positive"]),
        "4_survives_ex_bear": bool(arm1["regimes"]["EX_BEAR"]["mean"] >= THRESHOLD),
    }
    report["primary"] = {
        "contrast": "Arm1_b3_plus_holdings - b3_regime_switched",
        "n_cutoffs": primary.n,
        "mean": round(primary.mean, 5),
        "ci": [round(lo, 5), round(hi, 5)],
        "half_width": round((hi - lo) / 2.0, 5),
        "breadth": round(primary.hit_rate, 4),
        "threshold": THRESHOLD,
        "criterion_2_rule": "A1: bool(lo > 0.0) - favourable side only",
        "criteria": criteria,
        "all_passed": all(criteria.values()),
        "decision": "CONTINUE" if all(criteria.values()) else "REJECT",
    }
    report["seconds"] = round(time.time() - started, 1)

    with open(OUT_PKL, "wb") as handle:
        pickle.dump({"ic_series": ic, "primary": primary.values,
                     "noise_draws": draws, "written_at": report["written_at"]}, handle)
    with open(OUT_JSON, "w") as handle:
        json.dump(report, handle, indent=2)

    if not quiet:
        _print(report)
    return report


def _print(report: dict) -> None:
    print("V3 Family 3 - information-only test (Phase 5). SPENDS SLOT 3 OF 3 - THE LAST.")
    print("  cutoffs %d  rows %d  feature defined %.3f  %.1fs"
          % (report["development_cutoffs"], report["rows"],
             report["feature_defined"], report["seconds"]))
    print("  exam contamination %d  digest %s"
          % (report["exam_contamination"], report["exam_set_digest"][:16]))
    print()
    print("%-26s %9s %9s %19s %8s" % ("", "mean IC", "half-w", "95% CI", "hit"))
    for key, entry in report["benchmarks"].items():
        print("%-26s %+9.5f %9.5f  [%+.5f,%+.5f] %7.3f"
              % (key, entry["mean"], entry["half_width"],
                 entry["boot_lo"], entry["boot_hi"], entry["hit_rate"]))
    for name, entry in report["arms"].items():
        ic = entry["ic"]
        print("%-26s %+9.5f %9.5f  [%+.5f,%+.5f] %7.3f"
              % (name, ic["mean"], ic["half_width"],
                 ic["boot_lo"], ic["boot_hi"], ic["hit_rate"]))
    print()
    for name, entry in report["arms"].items():
        print("%s versus:" % name)
        for key, versus in entry["versus"].items():
            print("   %-22s %+9.5f  half-w %.5f  [%+.5f,%+.5f]  ex-bear %+.5f"
                  % (key, versus["mean"], versus["half_width"],
                     versus["boot_lo"], versus["boot_hi"],
                     versus["regimes"]["EX_BEAR"]["mean"]))
        net = entry["net_of_cost"]
        print("   net of cost: gross %+.5f  extra turnover %+.4f  NET %+.6f"
              % (net["gross_spread_advantage"]["mean"], net["extra_turnover"],
                 net["net_spread_advantage"]))
    print()
    noise = report["noise_control"]
    print("noise control: %d paired draws  median %+.5f  sd %.5f  share>=%.3f: %.3f  -> %s"
          % (noise["draws"], noise["median"], noise["sd"], THRESHOLD,
             noise["share_above_threshold"], "PASS" if noise["passed"] else "FAIL"))
    holm = report["holm_bonferroni"]
    print("Holm-Bonferroni: " + "  ".join(
        "%s p_raw %.4f p_holm %.4f %s" % (k, v["p_raw"], v["p_holm"],
                                          "SIG" if v["significant"] else "ns")
        for k, v in holm.items()))
    print()
    primary = report["primary"]
    print("PRIMARY  %s" % primary["contrast"])
    print("  mean %+.5f  half-width %.5f  CI [%+.5f,%+.5f]  breadth %.4f  n %d"
          % (primary["mean"], primary["half_width"], primary["ci"][0],
             primary["ci"][1], primary["breadth"], primary["n_cutoffs"]))
    print("  criterion 2 rule: %s" % primary["criterion_2_rule"])
    for key, value in primary["criteria"].items():
        print("  %-34s %s" % (key, "PASS" if value else "FAIL"))
    print("  DECISION: %s" % primary["decision"])


if __name__ == "__main__":
    run(quiet="--quiet" in sys.argv)
    sys.exit(0)
