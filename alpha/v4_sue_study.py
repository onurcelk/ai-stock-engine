"""V4-SUE — the confirmatory information-only test at a 20-session horizon.

Runs exactly `alpha/V4_SUE_PREREGISTRATION.md`.  V4 charter §9.4 sequencing:
charter committed -> power gate passed -> pre-registration committed -> THIS.

Two arms, fixed in the pre-registration before this file existed:

* **Arm 0** -- `rank_pct(sue)`, sign +1 by economic prior.
* **Arm 1** -- `rank_pct(B3) + 0.50 * (rank_pct(sue) - 0.5)`.  lambda = 0.50
  fixed, never scanned.

The primary contrast is **Arm 1 minus B3**, paired per cutoff.  The target is
**20-session forward alpha** (asset return - SPY return over 20 sessions), a
different dependent variable from V3's `alpha_5d`.

Nothing in this module reads the 72 exam cutoffs: the cutoff list comes from
`examset.load().development`, is asserted disjoint from the exam, and is then
filtered to the 313 usable cutoffs whose 20-session forward window fits within
the price history.

Writes `alpha/out/v4_sue_development.json` (summary) and `.pkl` (per-cutoff
series), so every headline number is re-derivable from per-cutoff data.

All frozen constants are imported from `alpha/v4_sue_config.py`, committed
before this file exists.  Nothing is restated here.
"""

from __future__ import annotations

import json
import pickle
import sys
import time

import numpy as np
import pandas as pd

from . import examset, pitdata, protocol, stats, targets
from . import v4_sue_config as cfg

PANEL = "alpha/out/panel.pkl"
SUE_PANEL = "alpha/out/sue_panel.pkl"
OUT_JSON = "alpha/out/v4_sue_development.json"
OUT_PKL = "alpha/out/v4_sue_development.pkl"

BEAR = "BEAR_TREND"


# ---------------------------------------------------------------------------
# helpers -- identical to v3_family1 except where the frozen block length /
# Newey-West lags differ (L=7, NW=6 vs V3's L=4, NW=4).  Each call passes
# the V4 constants explicitly rather than relying on stats module defaults.
# ---------------------------------------------------------------------------

def _winsorise(values: pd.Series, limit: float = cfg.WINSOR) -> pd.Series:
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
                   quantile: float = cfg.QUINTILE) -> pd.Series:
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


def _turnover(prediction: pd.Series, quantile: float = cfg.QUINTILE,
              stride: int = 1) -> float:
    """Mean share of the long book replaced between scored cutoffs.

    stride=1 gives consecutive-cutoff (5-session) turnover, comparable with
    the V3 record.  stride=HOLDING_CUTOFF_STRIDE gives 20-session turnover,
    matching the cost model behind the MDE.  Both are reported (prereg SS5.2).
    """
    frame = prediction.dropna()
    cutoffs = sorted(frame.index.get_level_values(0).unique())
    books: dict = {}
    for cutoff in cutoffs:
        group = frame.loc[cutoff]
        rank = group.rank(pct=True)
        books[cutoff] = set(group.index[rank > 1 - quantile])
    changes = []
    for i in range(stride, len(cutoffs), stride):
        before, after = cutoffs[i - stride], cutoffs[i]
        a, b = books[before], books[after]
        if a:
            changes.append(len(b - a) / len(a))
    return float(np.mean(changes)) if changes else float("nan")


def _describe(series: pd.Series, name: str, null: float = 0.0) -> dict:
    """Summary with V4's frozen L=7 block bootstrap and NW=6 lags."""
    clean = series.dropna().sort_index()
    n = len(clean)
    if n < 4:
        return {"what": name, "n_cutoffs": n, "mean": float("nan")}
    values = clean.to_numpy(dtype=float)
    mean = float(values.mean())
    lo, hi = stats.block_bootstrap_ci(values, block=cfg.BLOCK_LENGTH,
                                      draws=cfg.BOOTSTRAP_DRAWS)
    nw_se = stats.newey_west(values, lags=cfg.NEWEY_WEST_LAGS)
    p_boot = stats.block_bootstrap_p(values, null=null, block=cfg.BLOCK_LENGTH,
                                     draws=cfg.BOOTSTRAP_DRAWS)
    return {
        "what": name, "n_cutoffs": n,
        "mean": round(mean, 5),
        "median": round(float(np.median(values)), 5),
        "sd": round(float(values.std(ddof=1)), 5),
        "hit_rate": round(float((values > null).mean()), 4),
        "boot_lo": round(lo, 5), "boot_hi": round(hi, 5),
        "half_width": round((hi - lo) / 2.0, 5),
        "nw_se": round(nw_se, 5),
        "p_boot": round(p_boot, 5),
        "excludes_null": bool(lo > null or hi < null),
    }


def _halves(series: pd.Series) -> dict:
    """Split at (n+1)//2, odd cutoff to the FIRST half -- V3 convention."""
    series = series.dropna().sort_index()
    half = (len(series) + 1) // 2
    first, second = series.iloc[:half], series.iloc[half:]
    return {
        "first": {"n": len(first), "mean": round(float(first.mean()), 5),
                  "from": str(first.index[0].date()),
                  "to": str(first.index[-1].date())},
        "second": {"n": len(second), "mean": round(float(second.mean()), 5),
                   "from": str(second.index[0].date()),
                   "to": str(second.index[-1].date())},
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


def _book_tail_check(prediction: pd.Series,
                     quantile: float = cfg.QUINTILE) -> dict:
    """Verify both quintile tails can be formed at every cutoff (prereg SS8)."""
    frame = prediction.dropna()
    cutoffs = sorted(frame.index.get_level_values(0).unique())
    both_ok, n_checked = 0, 0
    for cutoff in cutoffs:
        group = frame.loc[cutoff]
        if len(group) < 25:
            continue
        n_checked += 1
        rank = group.rank(pct=True)
        has_top = (rank > 1 - quantile).sum() >= 3
        has_bottom = (rank <= quantile).sum() >= 3
        if has_top and has_bottom:
            both_ok += 1
    return {
        "cutoffs_checked": n_checked,
        "both_tails_formable": both_ok,
        "fraction": round(both_ok / n_checked, 4) if n_checked else 0.0,
        "passed": both_ok == n_checked if n_checked else False,
    }


# ---------------------------------------------------------------------------
# arm construction
# ---------------------------------------------------------------------------

def build_arms(sue: pd.Series,
               benchmarks: pd.DataFrame) -> dict[str, pd.Series]:
    """The two pre-registered arms, plus the base they are measured against."""
    sue_rank = sue.groupby(level=0).rank(pct=True, na_option="keep")
    b3_rank = benchmarks["b3_regime_switched"].groupby(
        level=0).rank(pct=True, na_option="keep")
    return {
        "Arm0_sue_rank": cfg.SUE_SIGN * sue_rank,
        "Arm1_b3_plus_sue": b3_rank + cfg.LAMBDA * (
            cfg.SUE_SIGN * sue_rank - 0.5),
        "_b3_rank": b3_rank,
    }


# ---------------------------------------------------------------------------
# 20-session target construction
# ---------------------------------------------------------------------------

def _build_20d_target(book: pitdata.PriceBook,
                      cutoffs: list[pd.Timestamp],
                      symbols_by_cutoff: dict[pd.Timestamp, list[str]]
                      ) -> pd.Series:
    """Build alpha_20d = asset_return(20) - SPY_return(20) for each cutoff.

    Returns a Series indexed by (cutoff, symbol), ready to join to the panel.
    """
    parts = []
    for cutoff in cutoffs:
        end = book.horizon_end(cutoff, cfg.HORIZON)
        if end is None:
            continue
        syms = symbols_by_cutoff[cutoff]
        asset = book.forward_return(cutoff, cfg.HORIZON, syms)
        spy = book.forward_return(cutoff, cfg.HORIZON, ["SPY"])
        spy_ret = float(spy.get("SPY", np.nan))
        if not np.isfinite(spy_ret):
            continue
        alpha = asset - spy_ret
        alpha.name = cfg.TARGET_NAME
        idx = pd.MultiIndex.from_arrays(
            [pd.Index([cutoff] * len(alpha)), alpha.index],
            names=["cutoff", "symbol"])
        parts.append(pd.Series(alpha.values, index=idx, name=cfg.TARGET_NAME,
                               dtype=float))
    if not parts:
        raise RuntimeError("no cutoffs produced a valid 20D target")
    return pd.concat(parts)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run(quiet: bool = False) -> dict:
    """Execute the V4-SUE study. Returns the report dict, writes JSON + PKL."""
    started = time.time()

    # ---- load the panel (features + regimes, built at 5D) -----------------
    panel = pickle.load(open(PANEL, "rb"))
    frame = panel["frame"]
    regimes = panel["regimes"]

    # ---- exam separation --------------------------------------------------
    exam_set = examset.load()
    exam = {pd.Timestamp(c) for c in exam_set.cutoffs}
    development = pd.DatetimeIndex(sorted(exam_set.development))
    assert not (exam & set(development)), "exam cutoff reached the development list"

    # ---- filter to development cutoffs ------------------------------------
    keep = frame.index.get_level_values("cutoff").isin(development)
    frame = frame.loc[keep]
    contamination = len(exam & set(frame.index.get_level_values("cutoff").unique()))
    assert contamination == 0, f"exam contamination: {contamination}"

    # ---- drop the 3 cutoffs whose 20-session window runs past history -----
    dropped = {pd.Timestamp(d) for d in cfg.DROPPED_CUTOFFS}
    usable = frame.index.get_level_values("cutoff")
    frame = frame.loc[~usable.isin(dropped)]
    cutoffs_used = sorted(frame.index.get_level_values("cutoff").unique())
    assert len(cutoffs_used) == cfg.N_CUTOFFS, (
        f"expected {cfg.N_CUTOFFS} usable cutoffs, got {len(cutoffs_used)}")

    # ---- build the 20-session forward alpha target ------------------------
    book = pitdata.load_book()

    # verify mechanically that the dropped cutoffs have no 20D window
    for d in dropped:
        assert book.horizon_end(d, cfg.HORIZON) is None, (
            f"dropped cutoff {d} unexpectedly has a 20D window")

    symbols_by_cutoff = {}
    for cutoff in cutoffs_used:
        symbols_by_cutoff[cutoff] = list(
            frame.loc[cutoff].index.get_level_values(0)
            if frame.index.names[1] is None
            else frame.loc[cutoff].index)

    target_20d = _build_20d_target(book, cutoffs_used, symbols_by_cutoff)

    # join the 20D target to the panel rows
    target = target_20d.reindex(frame.index)

    # confirm distinct dependent variable
    if "alpha_5d" in frame.columns:
        both = pd.DataFrame({"a5": frame["alpha_5d"], "a20": target}).dropna()
        corr_5d_20d = round(float(both["a5"].corr(both["a20"])), 4)
    else:
        corr_5d_20d = None

    # ---- load and winsorise SUE -------------------------------------------
    sue_panel = pickle.load(open(SUE_PANEL, "rb"))["feature"]
    sue = _winsorise(sue_panel["sue"].reindex(frame.index))

    sue_coverage = round(float(sue.notna().mean()), 4)
    assert sue_coverage >= cfg.COVERAGE_FLOOR, (
        f"SUE coverage {sue_coverage} below floor {cfg.COVERAGE_FLOOR}")

    # ---- benchmarks and arms ----------------------------------------------
    benchmarks = protocol.benchmark_scores(frame, regimes)
    arms = build_arms(sue, benchmarks)

    # ---- book-tail formability gate (prereg SS8) --------------------------
    tail_check = _book_tail_check(arms["Arm1_b3_plus_sue"])
    assert tail_check["passed"], (
        f"book-tail formability failed: {tail_check['fraction']}")

    # ---- IC per cutoff for arms and benchmarks ----------------------------
    ic: dict[str, pd.Series] = {}
    for name, prediction in arms.items():
        ic[name] = _ic_series(prediction, target)
    for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
        ic[key] = _ic_series(benchmarks[key], target)

    base = ic["b3_regime_switched"]
    primary = stats.paired_difference(ic["Arm1_b3_plus_sue"], base, "Arm1 - B3")

    # ---- the report dict --------------------------------------------------
    report: dict = {
        "protocol": "V4",
        "study": "V4-SUE",
        "stage": "Phase 5 information-only, 20-session horizon",
        "preregistration": cfg.PREREGISTRATION,
        "charter": cfg.CHARTER,
        "gate_record": cfg.GATE_RECORD,
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "exam_set_digest": exam_set.digest,
        "exam_contamination": contamination,
        "development_cutoffs": int(len(cutoffs_used)),
        "rows": int(len(frame)),
        "lambda": cfg.LAMBDA,
        "sue_sign": cfg.SUE_SIGN,
        "winsor": cfg.WINSOR,
        "target": cfg.TARGET_NAME,
        "horizon_sessions": cfg.HORIZON,
        "block_length": cfg.BLOCK_LENGTH,
        "nw_lags": cfg.NEWEY_WEST_LAGS,
        "mde": cfg.MDE,
        "achieved_half_width_at_gate": cfg.ACHIEVED_HALF_WIDTH,
        "sue_coverage": sue_coverage,
        "corr_alpha5d_alpha20d": corr_5d_20d,
        "book_tail_check": tail_check,
        "arms": {},
        "benchmarks": {},
        "primary": {},
        "standalone_horizon_diagnostic": {},
        "noise_control": {},
        "economics": {},
    }

    # ---- benchmark summaries ----------------------------------------------
    for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
        report["benchmarks"][key] = _describe(ic[key], key)

    # ---- arm ICs, spreads, versus contrasts, halves, regimes --------------
    p_values = {}
    for name in ("Arm0_sue_rank", "Arm1_b3_plus_sue"):
        prediction = arms[name]
        spread = _spread_series(prediction, target)
        entry = {
            "ic": _describe(ic[name], f"{name} IC"),
            "spread": _describe(spread, f"{name} top-bottom spread"),
            "turnover_5session": round(_turnover(prediction, stride=1), 4),
            "turnover_20session": round(
                _turnover(prediction, stride=cfg.HOLDING_CUTOFF_STRIDE), 4),
            "halves_ic": _halves(ic[name]),
            "versus": {},
        }
        for key in ("b1_momentum_12_1", "b2_reversal_5d", "b3_regime_switched"):
            difference = stats.paired_difference(
                ic[name], ic[key], f"{name} - {key}")
            entry["versus"][key] = _describe(difference.values,
                                             f"{name} vs {key}")
            entry["versus"][key]["halves"] = _halves(difference.values)
            entry["versus"][key]["regimes"] = _regime_split(
                difference.values, regimes)
        p_values[name] = entry["versus"]["b3_regime_switched"]["p_boot"]
        report["arms"][name] = entry

    report["holm_bonferroni"] = stats.holm_bonferroni(p_values)

    # ---- net of costs: BOTH stride conventions (prereg SS5.2) -------------
    base_spread = _spread_series(arms["_b3_rank"], target)
    for name in ("Arm0_sue_rank", "Arm1_b3_plus_sue"):
        spread = _spread_series(arms[name], target)
        common = spread.index.intersection(base_spread.index)
        gross = (spread.reindex(common) - base_spread.reindex(common)).dropna()

        # consecutive-cutoff turnover (comparable with V3 record)
        extra_to_5s = (_turnover(arms[name], stride=1)
                       - _turnover(arms["_b3_rank"], stride=1))
        drag_5s = max(extra_to_5s, 0.0) * 2 * (cfg.COST_BPS / 10_000.0)

        # 20-session stride turnover (matches MDE's 13/year cost model)
        extra_to_20s = (_turnover(arms[name], stride=cfg.HOLDING_CUTOFF_STRIDE)
                        - _turnover(arms["_b3_rank"],
                                    stride=cfg.HOLDING_CUTOFF_STRIDE))
        drag_20s = max(extra_to_20s, 0.0) * 2 * (cfg.COST_BPS / 10_000.0)

        report["arms"][name]["net_of_cost"] = {
            "gross_spread_advantage": _describe(gross,
                                                f"{name} gross spread vs B3"),
            "stride_5session": {
                "extra_turnover": round(extra_to_5s, 4),
                "cost_drag": round(drag_5s, 6),
                "net_spread": round(float(gross.mean() - drag_5s), 6),
            },
            "stride_20session": {
                "extra_turnover": round(extra_to_20s, 4),
                "cost_drag": round(drag_20s, 6),
                "net_spread": round(float(gross.mean() - drag_20s), 6),
            },
        }

    # ---- standalone horizon diagnostic (prereg SS4) -----------------------
    arm0_ic = ic["Arm0_sue_rank"]
    arm0_desc = _describe(arm0_ic, "standalone SUE 20D IC")
    h0 = arm0_desc["half_width"] if np.isfinite(arm0_desc.get("half_width", float("nan"))) else 0.0
    standalone_mean = arm0_desc["mean"]
    if np.isfinite(standalone_mean) and np.isfinite(h0):
        if standalone_mean > cfg.P_SQRT_H + h0:
            horizon_reading = "above P -- evidence supporting the horizon mechanism"
        elif standalone_mean < cfg.P_SQRT_H - h0:
            horizon_reading = "below P -- evidence against the horizon mechanism"
        else:
            horizon_reading = "within P +/- h0 -- no informational gain from the horizon"
    else:
        horizon_reading = "insufficient data"

    report["standalone_horizon_diagnostic"] = {
        "P_sqrt_H": cfg.P_SQRT_H,
        "standalone_20d_ic": arm0_desc,
        "standalone_half_width": h0,
        "reading": horizon_reading,
    }

    # ---- noise control: 30 paired draws (prereg SS7) ----------------------
    rng = np.random.default_rng(20260810)
    draws = []
    for _ in range(cfg.NOISE_DRAWS):
        shuffled = sue.groupby(level=0, group_keys=False).apply(
            lambda s: pd.Series(rng.permutation(s.to_numpy()), index=s.index))
        fake = build_arms(shuffled, benchmarks)["Arm1_b3_plus_sue"]
        fake_ic = _ic_series(fake, target)
        draws.append(float(
            stats.paired_difference(fake_ic, base, "noise").values.mean()))
    draws_arr = np.array(draws)
    report["noise_control"] = {
        "draws": cfg.NOISE_DRAWS,
        "paired": True,
        "median": round(float(np.median(draws_arr)), 5),
        "mean": round(float(draws_arr.mean()), 5),
        "sd": round(float(draws_arr.std(ddof=1)), 5),
        "share_above_threshold": round(
            float((draws_arr >= cfg.MDE).mean()), 4),
        "median_limit": cfg.NOISE_MEDIAN_LIMIT,
        "exceedance_limit": cfg.NOISE_EXCEEDANCE_LIMIT,
        "passed": bool(
            np.median(draws_arr) <= cfg.NOISE_MEDIAN_LIMIT
            and (draws_arr >= cfg.MDE).mean() <= cfg.NOISE_EXCEEDANCE_LIMIT),
    }

    # ---- the four-part CONTINUE rule (prereg SS3, Amendment A1) -----------
    primary_values = primary.clean.to_numpy(dtype=float)
    lo, hi = stats.block_bootstrap_ci(primary_values, block=cfg.BLOCK_LENGTH,
                                      draws=cfg.BOOTSTRAP_DRAWS)
    arm1_vs_b3 = report["arms"]["Arm1_b3_plus_sue"]["versus"][
        "b3_regime_switched"]
    ex_bear_mean = arm1_vs_b3["regimes"]["EX_BEAR"]["mean"]

    criteria = {
        # C1: mean paired effect >= MDE
        "1_effect_at_least_MDE": bool(primary.mean >= cfg.MDE),
        # C2: Amendment A1 -- CI excludes zero on the FAVOURABLE side only
        "2_ci_excludes_zero_favourable": bool(lo > 0.0),
        # C3: breadth > 0.50 AND both chronological halves positive
        "3_breadth_and_halves": bool(
            primary.hit_rate > 0.50
            and arm1_vs_b3["halves"]["both_positive"]),
        # C4: survives with BEAR_TREND removed, at MDE level
        "4_survives_ex_bear": bool(
            ex_bear_mean is not None and ex_bear_mean >= cfg.MDE),
    }
    report["primary"] = {
        "contrast": "Arm1_b3_plus_sue - b3_regime_switched",
        "n_cutoffs": primary.n,
        "mean": round(primary.mean, 5),
        "ci": [round(lo, 5), round(hi, 5)],
        "half_width": round((hi - lo) / 2.0, 5),
        "breadth": round(primary.hit_rate, 4),
        "mde": cfg.MDE,
        "criteria": criteria,
        "all_passed": all(criteria.values()),
        "decision": "CONTINUE" if all(criteria.values()) else "REJECT",
    }
    report["seconds"] = round(time.time() - started, 1)

    # ---- write outputs ----------------------------------------------------
    with open(OUT_PKL, "wb") as handle:
        pickle.dump({
            "ic_series": {k: v for k, v in ic.items() if not k.startswith("_")},
            "primary": primary.values,
            "noise_draws": draws_arr,
            "target_20d": target,
            "written_at": report["written_at"],
        }, handle)
    with open(OUT_JSON, "w") as handle:
        json.dump(report, handle, indent=2, default=str)

    if not quiet:
        _print(report)
    return report


# ---------------------------------------------------------------------------
# human-readable output
# ---------------------------------------------------------------------------

def _print(report: dict) -> None:
    print("V4-SUE -- information-only test at 20-session horizon")
    print("  cutoffs %d  rows %d  SUE coverage %.3f  %.1fs"
          % (report["development_cutoffs"], report["rows"],
             report["sue_coverage"], report["seconds"]))
    print("  exam contamination %d  digest %s"
          % (report["exam_contamination"],
             report["exam_set_digest"][:16]))
    print("  target %s  horizon %d  lambda %.2f  block L=%d  MDE %+.4f"
          % (report["target"], report["horizon_sessions"],
             report["lambda"], report["block_length"], report["mde"]))
    if report["corr_alpha5d_alpha20d"] is not None:
        print("  corr(alpha_5d, alpha_20d) = %.4f"
              % report["corr_alpha5d_alpha20d"])
    print()

    print("%-22s %9s %9s %19s %8s" % ("", "mean IC", "half-w", "95% CI", "hit"))
    for key, entry in report["benchmarks"].items():
        print("%-22s %+9.5f %9.5f  [%+.5f,%+.5f] %7.3f"
              % (key, entry["mean"], entry["half_width"],
                 entry["boot_lo"], entry["boot_hi"], entry["hit_rate"]))
    for name, entry in report["arms"].items():
        ic_e = entry["ic"]
        print("%-22s %+9.5f %9.5f  [%+.5f,%+.5f] %7.3f"
              % (name, ic_e["mean"], ic_e["half_width"],
                 ic_e["boot_lo"], ic_e["boot_hi"], ic_e["hit_rate"]))
    print()

    for name, entry in report["arms"].items():
        print("%s versus:" % name)
        for key, versus in entry["versus"].items():
            eb = versus["regimes"]["EX_BEAR"]["mean"]
            print("   %-22s %+9.5f  half-w %.5f  [%+.5f,%+.5f]  ex-bear %s"
                  % (key, versus["mean"], versus["half_width"],
                     versus["boot_lo"], versus["boot_hi"],
                     ("%+.5f" % eb) if eb is not None else "n/a"))
        net = entry["net_of_cost"]
        net_20s = net["stride_20session"]
        print("   net of cost (20s stride): gross %+.5f  extra TO %+.4f  "
              "NET %+.6f"
              % (net["gross_spread_advantage"]["mean"],
                 net_20s["extra_turnover"], net_20s["net_spread"]))
    print()

    diag = report["standalone_horizon_diagnostic"]
    s = diag["standalone_20d_ic"]
    print("standalone horizon diagnostic:")
    print("  P(sqrt-H) = %+.4f  standalone 20D IC = %+.5f  "
          "half-width = %.5f"
          % (diag["P_sqrt_H"], s["mean"], diag["standalone_half_width"]))
    print("  reading: %s" % diag["reading"])
    print()

    noise = report["noise_control"]
    print("noise control: %d paired draws  median %+.5f  sd %.5f  "
          "share>=MDE: %.3f  -> %s"
          % (noise["draws"], noise["median"], noise["sd"],
             noise["share_above_threshold"],
             "PASS" if noise["passed"] else "FAIL"))
    print()

    p = report["primary"]
    print("PRIMARY  %s" % p["contrast"])
    print("  mean %+.5f  half-width %.5f  CI [%+.5f,%+.5f]  breadth %.4f  "
          "n %d  MDE %+.4f"
          % (p["mean"], p["half_width"], p["ci"][0], p["ci"][1],
             p["breadth"], p["n_cutoffs"], p["mde"]))
    for key, value in p["criteria"].items():
        print("  %-36s %s" % (key, "PASS" if value else "FAIL"))
    print("  DECISION: %s" % p["decision"])


if __name__ == "__main__":
    sys.exit(0 if run(quiet="--quiet" in sys.argv) else 0)
