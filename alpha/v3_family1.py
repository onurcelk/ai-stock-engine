"""V3 Family 1 — the information-only test. Runs exactly `V3_PREREGISTRATION.md`.

Phase 5 of master roadmap v2 (§7): **does this information contain predictive
signal at all?** No learner is fitted here, by design (§2.9) — a family that
fails its simple tests is not re-tested with a bigger model.

Two arms, fixed in the pre-registration before this file existed:

* **Arm 0** — `rank_pct(sue)`, sign +1 by economic prior. The simplest possible
  version of the new information (§2.3, last row).
* **Arm 1** — `z__b3 + 0.25 * (rank_pct(sue) - 0.5)`. The incumbent plus a
  bounded tilt. B3 is rank-transformed first so the tilt's authority is a fixed
  fraction of the base rather than an accident of B3's regime-dependent scale.

The primary contrast is **Arm 1 minus B3**, paired per cutoff. Everything else
is a declared secondary or a diagnostic.

Nothing in this module reads the 72 exam cutoffs: the cutoff list comes from
`examset.load().development` and is asserted disjoint from the exam before any
scoring happens.

Writes `alpha/out/v3_family1_development.json` (summary) and `.pkl` (per-cutoff
series), so every headline number is re-derivable from per-cutoff data rather
than from a summary — the property that let the V2.3 audit check itself.
"""

from __future__ import annotations

import json
import pickle
import sys
import time

import numpy as np
import pandas as pd

from . import carrier, examset, protocol, stats

PANEL = "alpha/out/panel.pkl"
SUE_PANEL = "alpha/out/sue_panel.pkl"
OUT_JSON = "alpha/out/v3_family1_development.json"
OUT_PKL = "alpha/out/v3_family1_development.pkl"

LAMBDA = 0.25             # pre-registered, fixed, not scanned as an arm
SUE_SIGN = +1             # economic prior, not estimated
WINSOR = 0.01             # per-cutoff tails, declared in the pre-registration
NOISE_DRAWS = 30          # §2.11 — paired, and enough of them
COST_BPS = 5.0            # the record's pre-registered cost assumption

TARGET = "alpha_5d"
BEAR = "BEAR_TREND"

#: The four-part CONTINUE rule of V3_PREREGISTRATION.md §6.3.
THRESHOLD = 0.010
NOISE_MEDIAN_LIMIT = 0.002
NOISE_EXCEEDANCE_LIMIT = 0.10


def _winsorise(values: pd.Series, limit: float = WINSOR) -> pd.Series:
    lo = values.groupby(level=0).transform(lambda s: s.quantile(limit))
    hi = values.groupby(level=0).transform(lambda s: s.quantile(1.0 - limit))
    return values.clip(lower=lo, upper=hi)


def _ic_series(prediction: pd.Series, target: pd.Series) -> pd.Series:
    frame = pd.DataFrame({"p": prediction, "y": target}).dropna()
    out = {}
    for cutoff, group in frame.groupby(level=0):
        out[cutoff] = stats.spearman_ic(group["p"], group["y"])
    return pd.Series(out).dropna().sort_index()


def _spread_series(prediction: pd.Series, target: pd.Series,
                   quantile: float = 0.2) -> pd.Series:
    """Top-minus-bottom quintile mean forward alpha, per cutoff."""
    frame = pd.DataFrame({"p": prediction, "y": target}).dropna()
    out = {}
    for cutoff, group in frame.groupby(level=0):
        if len(group) < 25:
            continue
        rank = group["p"].rank(pct=True)
        top = group.loc[rank > 1 - quantile, "y"].mean()
        bottom = group.loc[rank <= quantile, "y"].mean()
        out[cutoff] = float(top - bottom)
    return pd.Series(out).dropna().sort_index()


def _turnover(prediction: pd.Series, quantile: float = 0.2) -> float:
    """Mean share of the long book replaced between consecutive cutoffs."""
    frame = prediction.dropna()
    books, cutoffs = {}, sorted(frame.index.get_level_values(0).unique())
    for cutoff in cutoffs:
        group = frame.loc[cutoff]
        rank = group.rank(pct=True)
        books[cutoff] = set(group.index[rank > 1 - quantile])
    changes = []
    for before, after in zip(cutoffs, cutoffs[1:]):
        a, b = books[before], books[after]
        if a:
            changes.append(len(b - a) / len(a))
    return float(np.mean(changes)) if changes else float("nan")


def _describe(series: pd.Series, name: str, null: float = 0.0) -> dict:
    wrapped = stats.Series(name, series, null=null)
    lo, hi = wrapped.bootstrap_ci()
    return {
        "what": name, "n_cutoffs": wrapped.n,
        "mean": round(wrapped.mean, 5), "median": round(wrapped.median, 5),
        "sd": round(wrapped.sd, 5), "hit_rate": round(wrapped.hit_rate, 4),
        "boot_lo": round(lo, 5), "boot_hi": round(hi, 5),
        "half_width": round((hi - lo) / 2.0, 5),
        "nw_se": round(wrapped.newey_west_se, 5),
        "p_boot": round(stats.block_bootstrap_p(
            wrapped.clean.to_numpy(dtype=float), null=null), 5),
        "excludes_null": bool(lo > null or hi < null),
    }


def _halves(series: pd.Series) -> dict:
    series = series.dropna().sort_index()
    half = (len(series) + 1) // 2            # odd cutoff goes to the FIRST half
    first, second = series.iloc[:half], series.iloc[half:]
    return {
        "first": {"n": len(first), "mean": round(float(first.mean()), 5),
                  "from": str(first.index[0].date()), "to": str(first.index[-1].date())},
        "second": {"n": len(second), "mean": round(float(second.mean()), 5),
                   "from": str(second.index[0].date()), "to": str(second.index[-1].date())},
        "both_positive": bool(first.mean() > 0 and second.mean() > 0),
    }


def _regime_split(series: pd.Series, regimes: pd.DataFrame) -> dict:
    trend = regimes["trend"].reindex(series.index)
    out = {}
    for tag in ("BULL_TREND", "BEAR_TREND", "SIDEWAYS"):
        chunk = series[trend == tag].dropna()
        out[tag] = {"n": len(chunk),
                    "mean": round(float(chunk.mean()), 5) if len(chunk) else None}
    ex_bear = series[trend != BEAR].dropna()
    out["EX_BEAR"] = _describe(ex_bear, "ex-bear")
    return out


def build_arms(frame: pd.DataFrame, sue: pd.Series,
               benchmarks: pd.DataFrame) -> dict[str, pd.Series]:
    """The two pre-registered arms, plus the base they are measured against."""
    sue_rank = sue.groupby(level=0).rank(pct=True, na_option="keep")
    b3_rank = benchmarks["b3_regime_switched"].groupby(
        level=0).rank(pct=True, na_option="keep")
    return {
        "Arm0_sue_rank": SUE_SIGN * sue_rank,
        "Arm1_b3_plus_sue": b3_rank + LAMBDA * (SUE_SIGN * sue_rank - 0.5),
        "_b3_rank": b3_rank,
    }


def run(quiet: bool = False) -> dict:
    started = time.time()
    panel = pickle.load(open(PANEL, "rb"))
    frame = panel["frame"]
    regimes = panel["regimes"]

    exam = {pd.Timestamp(c) for c in examset.load().cutoffs}
    development = pd.DatetimeIndex(sorted(examset.load().development))
    assert not (exam & set(development)), "exam cutoff reached the development list"

    keep = frame.index.get_level_values("cutoff").isin(development)
    frame = frame.loc[keep]
    contamination = len(exam & set(frame.index.get_level_values("cutoff").unique()))
    assert contamination == 0, f"exam contamination: {contamination}"

    sue_panel = pickle.load(open(SUE_PANEL, "rb"))["feature"]
    sue = _winsorise(sue_panel["sue"].reindex(frame.index))

    benchmarks = protocol.benchmark_scores(frame, regimes)
    target = frame[TARGET]
    arms = build_arms(frame, sue, benchmarks)

    ic: dict[str, pd.Series] = {}
    for name, prediction in arms.items():
        ic[name] = _ic_series(prediction, target)
    for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
        ic[key] = _ic_series(benchmarks[key], target)

    base = ic["b3_regime_switched"]
    primary = stats.paired_difference(ic["Arm1_b3_plus_sue"], base, "Arm1 - B3")

    report: dict = {
        "protocol": "V3",
        "family": "1 - reported fundamentals (time-series SUE)",
        "stage": "Phase 5 information-only",
        "preregistration": "alpha/V3_PREREGISTRATION.md",
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "exam_set_digest": examset.load().digest,
        "exam_contamination": contamination,
        "development_cutoffs": int(len(development)),
        "rows": int(len(frame)),
        "lambda": LAMBDA, "sue_sign": SUE_SIGN, "winsor": WINSOR,
        "target": TARGET, "horizon_sessions": 5,
        "sue_coverage": round(float(sue.notna().mean()), 4),
        "arms": {}, "benchmarks": {}, "primary": {}, "noise_control": {},
    }

    for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
        report["benchmarks"][key] = _describe(ic[key], key)

    p_values = {}
    for name in ("Arm0_sue_rank", "Arm1_b3_plus_sue"):
        prediction = arms[name]
        spread = _spread_series(prediction, target)
        entry = {
            "ic": _describe(ic[name], f"{name} IC"),
            "spread": _describe(spread, f"{name} top-bottom spread"),
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

    # ---- net of costs: the primary economic metric from the first measurement
    base_spread = _spread_series(arms["_b3_rank"], target)
    for name in ("Arm0_sue_rank", "Arm1_b3_plus_sue"):
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

    # ---- the §7 noise control: 30 paired draws, shuffled within cutoff
    rng = np.random.default_rng(20260809)
    draws = []
    for _ in range(NOISE_DRAWS):
        shuffled = sue.groupby(level=0, group_keys=False).apply(
            lambda s: pd.Series(rng.permutation(s.to_numpy()), index=s.index))
        fake = build_arms(frame, shuffled, benchmarks)["Arm1_b3_plus_sue"]
        fake_ic = _ic_series(fake, target)
        draws.append(float(stats.paired_difference(fake_ic, base, "noise").values.mean()))
    draws = np.array(draws)
    report["noise_control"] = {
        "draws": NOISE_DRAWS,
        "paired": True,
        "median": round(float(np.median(draws)), 5),
        "mean": round(float(draws.mean()), 5),
        "sd": round(float(draws.std(ddof=1)), 5),
        "share_above_threshold": round(float((draws >= THRESHOLD).mean()), 4),
        "median_limit": NOISE_MEDIAN_LIMIT,
        "exceedance_limit": NOISE_EXCEEDANCE_LIMIT,
        "passed": bool(np.median(draws) <= NOISE_MEDIAN_LIMIT
                       and (draws >= THRESHOLD).mean() <= NOISE_EXCEEDANCE_LIMIT),
    }

    # ---- the four-part CONTINUE rule, evaluated mechanically
    lo, hi = stats.block_bootstrap_ci(primary.clean.to_numpy(dtype=float))
    arm1 = report["arms"]["Arm1_b3_plus_sue"]["versus"]["b3_regime_switched"]
    criteria = {
        "1_effect_at_least_0.010": bool(primary.mean >= THRESHOLD),
        "2_ci_excludes_zero": bool(lo > 0.0 or hi < 0.0),
        "3_breadth_and_halves": bool(primary.hit_rate > 0.50
                                     and arm1["halves"]["both_positive"]),
        "4_survives_ex_bear": bool(arm1["regimes"]["EX_BEAR"]["mean"] >= THRESHOLD),
    }
    report["primary"] = {
        "contrast": "Arm1_b3_plus_sue - b3_regime_switched",
        "n_cutoffs": primary.n,
        "mean": round(primary.mean, 5),
        "ci": [round(lo, 5), round(hi, 5)],
        "half_width": round((hi - lo) / 2.0, 5),
        "breadth": round(primary.hit_rate, 4),
        "threshold": THRESHOLD,
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
    print("V3 Family 1 - information-only test (Phase 5)")
    print("  cutoffs %d  rows %d  SUE coverage %.3f  %.1fs"
          % (report["development_cutoffs"], report["rows"],
             report["sue_coverage"], report["seconds"]))
    print("  exam contamination %d  digest %s"
          % (report["exam_contamination"], report["exam_set_digest"][:16]))
    print()
    print("%-22s %9s %9s %19s %8s" % ("", "mean IC", "half-w", "95% CI", "hit"))
    for key, entry in report["benchmarks"].items():
        print("%-22s %+9.5f %9.5f  [%+.5f,%+.5f] %7.3f"
              % (key, entry["mean"], entry["half_width"],
                 entry["boot_lo"], entry["boot_hi"], entry["hit_rate"]))
    for name, entry in report["arms"].items():
        ic = entry["ic"]
        print("%-22s %+9.5f %9.5f  [%+.5f,%+.5f] %7.3f"
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
    print()
    primary = report["primary"]
    print("PRIMARY  %s" % primary["contrast"])
    print("  mean %+.5f  half-width %.5f  CI [%+.5f,%+.5f]  breadth %.4f  n %d"
          % (primary["mean"], primary["half_width"], primary["ci"][0],
             primary["ci"][1], primary["breadth"], primary["n_cutoffs"]))
    for key, value in primary["criteria"].items():
        print("  %-28s %s" % (key, "PASS" if value else "FAIL"))
    print("  DECISION: %s" % primary["decision"])


if __name__ == "__main__":
    sys.exit(0 if run(quiet="--quiet" in sys.argv) else 0)
