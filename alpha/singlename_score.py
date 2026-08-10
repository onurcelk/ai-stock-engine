"""Single-Name Phase 1 scoring. SCORER SIDE — reads outcomes, writes no prediction.

The mirror of `alpha/singlename.py`, and the same two-process contract
`validation/predict.py` / `validation/score.py` already enforce: this module
opens the frozen prediction file, joins the outcomes it was not allowed to see,
and computes every number in `reports/SINGLE_NAME_PHASE1.md`. It never writes to
`single_name_predictions.pkl`.

Every headline figure is computed **per cutoff first** and aggregated across
cutoffs afterwards, with the moving-block bootstrap interval from
`alpha/stats.py`. 454 names on one Tuesday are one observation of the market's
week, not 454 observations, and the difference between those two readings is
the difference between a result and an artefact.

The four gates G1-G4 are read out of `singlename_config.py` and evaluated
mechanically at the end. They were frozen in §5.2 of the pre-registration before
any of this ran, so the code below decides nothing — it only reports whether the
pre-registered conditions hold.

Run:  python -m alpha.singlename_score
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from . import singlename, stats
from . import singlename_config as cfg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COVERED = ("BUY", "SELL")


# ----------------------------------------------------------------------
# Row-level primitives
# ----------------------------------------------------------------------

def log_loss(prob: pd.Series, actual: pd.Series) -> pd.Series:
    p = prob.clip(cfg.PROB_CLIP, 1.0 - cfg.PROB_CLIP)
    return -(actual * np.log(p) + (1.0 - actual) * np.log(1.0 - p))


def brier(prob: pd.Series, actual: pd.Series) -> pd.Series:
    return (prob - actual) ** 2


def directional(prob: pd.Series) -> pd.Series:
    """The row's directional call from its probability: up at or above a coin flip."""
    return (prob >= 0.5).astype(float)


def call_correct(calls: pd.Series, actual: pd.Series) -> pd.Series:
    """1 / 0 on covered calls, NaN where the arm declined to call."""
    correct = pd.Series(np.nan, index=calls.index, dtype=float)
    correct[calls == "BUY"] = actual[calls == "BUY"]
    correct[calls == "SELL"] = 1.0 - actual[calls == "SELL"]
    return correct


def _auc(prob: pd.Series, actual: pd.Series) -> float:
    """Rank-based ROC-AUC. Secondary diagnostic only (§5.1)."""
    frame = pd.DataFrame({"p": prob, "y": actual}).dropna()
    positives, negatives = frame["y"].sum(), (1 - frame["y"]).sum()
    if positives < 1 or negatives < 1:
        return float("nan")
    ranks = frame["p"].rank()
    return float((ranks[frame["y"] == 1].sum() - positives * (positives + 1) / 2)
                 / (positives * negatives))


# ----------------------------------------------------------------------
# Per-cutoff metric series
# ----------------------------------------------------------------------

def per_cutoff(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    """One row per cutoff: every §5.1 metric for one arm, averaged across the cross-section."""
    prob = frame[f"p_up_{arm}"]
    expected = frame[f"er_{arm}"]
    actual = frame["direction"]
    realised = frame["asset_return"]
    calls = frame[f"call_{arm}"]

    work = pd.DataFrame({
        "prob": prob, "expected": expected, "actual": actual, "realised": realised,
        "calls": calls,
        "hit": (directional(prob) == actual).astype(float),
        "logloss": log_loss(prob, actual),
        "brier": brier(prob, actual),
        "abs_err": (expected - realised).abs(),
        "sq_err": (expected - realised) ** 2,
        "sign_hit": (np.sign(expected) == np.sign(realised)).astype(float),
        "covered": calls.isin(COVERED).astype(float),
        "call_hit": call_correct(calls, actual),
        "in_interval": ((realised >= frame[f"lo_{arm}"])
                        & (realised <= frame[f"hi_{arm}"])).astype(float),
    })

    def one(block: pd.DataFrame) -> pd.Series:
        covered = block[block["covered"] == 1.0]
        buys = block[block["calls"] == "BUY"]
        sells = block[block["calls"] == "SELL"]
        ups = block[block["actual"] == 1.0]
        downs = block[block["actual"] == 0.0]
        return pd.Series({
            "n": float(len(block)),
            "accuracy": block["hit"].mean(),
            "balanced_accuracy": np.nanmean([
                (directional(ups["prob"]) == 1.0).mean() if len(ups) else np.nan,
                (directional(downs["prob"]) == 0.0).mean() if len(downs) else np.nan]),
            "log_loss": block["logloss"].mean(),
            "brier": block["brier"].mean(),
            "auc": _auc(block["prob"], block["actual"]),
            "mae": block["abs_err"].mean(),
            "rmse": float(np.sqrt(block["sq_err"].mean())),
            "sign_accuracy": block["sign_hit"].mean(),
            "up_rate": block["actual"].mean(),
            "mean_return": block["realised"].mean(),
            "interval_coverage": block["in_interval"].mean(),
            "coverage": block["covered"].mean(),
            "n_covered": float(len(covered)),
            "covered_accuracy": covered["call_hit"].mean() if len(covered) else np.nan,
            "covered_up_rate": covered["actual"].mean() if len(covered) else np.nan,
            "covered_log_loss": covered["logloss"].mean() if len(covered) else np.nan,
            "covered_brier": covered["brier"].mean() if len(covered) else np.nan,
            "covered_return": covered["realised"].mean() if len(covered) else np.nan,
            "buy_return": buys["realised"].mean() if len(buys) else np.nan,
            "sell_return": sells["realised"].mean() if len(sells) else np.nan,
            "n_buy": float(len(buys)),
            "n_sell": float(len(sells)),
            "pred_realised_corr": (block["expected"].corr(block["realised"])
                                   if block["expected"].nunique() > 2 else np.nan),
            "pred_realised_spearman": (block["expected"].corr(block["realised"],
                                                              method="spearman")
                                       if block["expected"].nunique() > 2 else np.nan),
        })

    return work.groupby(level=0).apply(one)


def describe(series: pd.Series, name: str) -> dict:
    """A point estimate with the resolution it was measured at (roadmap §2.6)."""
    row = stats.Series(name, series).row()
    low, high = row["boot_lo"], row["boot_hi"]
    row["half_width"] = (round((high - low) / 2.0, 6)
                         if np.isfinite(low) and np.isfinite(high) else None)
    return row


def paired(left: pd.Series, right: pd.Series, name: str) -> dict:
    return describe(stats.paired_difference(left, right, name).values, name)


# ----------------------------------------------------------------------
# Calibration (§5.1)
# ----------------------------------------------------------------------

def reliability(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    """The §5.1 reliability table on the ten fixed bins. Pooled across cutoffs."""
    prob = frame[f"p_up_{arm}"]
    bins = pd.cut(prob, bins=list(cfg.CALIBRATION_BINS), include_lowest=True)
    grouped = pd.DataFrame({"p": prob, "y": frame["direction"],
                            "cutoff": frame.index.get_level_values(0)}).groupby(
        bins, observed=False)
    table = pd.DataFrame({
        "n": grouped["y"].size(),
        "cutoffs": grouped["cutoff"].nunique(),
        "mean_predicted": grouped["p"].mean(),
        "realised_hit_rate": grouped["y"].mean(),
    })
    table["gap"] = table["realised_hit_rate"] - table["mean_predicted"]
    return table


def expected_calibration_error(table: pd.DataFrame) -> float:
    """Sample-weighted ECE over the fixed bins."""
    used = table[table["n"] > 0]
    if used.empty:
        return float("nan")
    weight = used["n"] / used["n"].sum()
    return float((weight * used["gap"].abs()).sum())


def monotonicity(table: pd.DataFrame, min_cutoffs: int = cfg.G2_MIN_BIN_CUTOFFS) -> dict:
    """§5.2 G2: is realised accuracy monotone in the predicted probability bin?"""
    used = table[(table["cutoffs"] >= min_cutoffs) & table["realised_hit_rate"].notna()]
    if len(used) < 3:
        return {"bins_used": int(len(used)), "spearman": None,
                "note": f"fewer than 3 bins hold >= {min_cutoffs} cutoffs"}
    index = pd.Series(np.arange(len(used), dtype=float), index=used.index)
    rho = float(index.corr(used["realised_hit_rate"], method="spearman"))
    return {"bins_used": int(len(used)), "spearman": round(rho, 4), "note": ""}


# ----------------------------------------------------------------------
# Diagnostics (§4, §5.1)
# ----------------------------------------------------------------------

def by_confidence(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    """Economic discrimination by the frozen confidence tiers, plus the abstained rows."""
    tier = frame[f"tier_{arm}"].where(frame[f"call_{arm}"].isin(COVERED), "abstained")
    grouped = pd.DataFrame({
        "tier": tier,
        "hit": (directional(frame[f"p_up_{arm}"]) == frame["direction"]).astype(float),
        "logloss": log_loss(frame[f"p_up_{arm}"], frame["direction"]),
        "brier": brier(frame[f"p_up_{arm}"], frame["direction"]),
        "realised": frame["asset_return"],
    }).groupby("tier")
    return pd.DataFrame({
        "n": grouped.size(),
        "accuracy": grouped["hit"].mean(),
        "log_loss": grouped["logloss"].mean(),
        "brier": grouped["brier"].mean(),
        "mean_return": grouped["realised"].mean(),
    })


def return_deciles(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    """Realised outcome by within-cutoff predicted-return decile (§5.1)."""
    decile = frame.groupby(level=0)[f"er_{arm}"].transform(
        lambda block: pd.qcut(block.rank(method="first"), 10, labels=False,
                              duplicates="drop") if block.nunique() > 10 else np.nan)
    grouped = pd.DataFrame({"decile": decile, "realised": frame["asset_return"],
                            "up": frame["direction"]}).dropna(
        subset=["decile"]).groupby("decile")
    return pd.DataFrame({"n": grouped.size(), "mean_return": grouped["realised"].mean(),
                         "up_rate": grouped["up"].mean()})


def threshold_sweep(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    """§4's pre-declared diagnostic curve. No point on it may become the rule."""
    prob = frame[f"p_up_{arm}"]
    expected = frame[f"er_{arm}"]
    rows = []
    for threshold in cfg.THRESHOLD_SWEEP:
        buy = (prob >= threshold) & (expected >= cfg.MIN_EDGE)
        sell = (prob <= 1.0 - threshold) & (expected <= -cfg.MIN_EDGE)
        covered = buy | sell
        correct = pd.Series(np.nan, index=frame.index)
        correct[buy] = frame.loc[buy, "direction"]
        correct[sell] = 1.0 - frame.loc[sell, "direction"]
        rows.append({
            "threshold": threshold,
            "coverage": float(covered.mean()),
            "n_covered": int(covered.sum()),
            "accuracy": float(correct.mean()) if covered.any() else np.nan,
            "mean_return": float(frame.loc[buy, "asset_return"].mean()) if buy.any() else np.nan,
            "symbols": int(frame[covered].index.get_level_values(1).nunique()),
        })
    return pd.DataFrame(rows).set_index("threshold")


def uncertainty_gated(frame: pd.DataFrame, arm: str) -> dict:
    """§4's pre-declared secondary variant: drop the widest decile of intervals."""
    width = frame[f"hi_{arm}"] - frame[f"lo_{arm}"]
    cap = width.groupby(level=0).transform(
        lambda block: block.quantile(cfg.UNCERTAINTY_GATE_QUANTILE))
    keep = width <= cap
    covered = frame[f"call_{arm}"].isin(COVERED) & keep
    correct = call_correct(frame[f"call_{arm}"].where(covered), frame["direction"])
    return {
        "coverage": float(covered.mean()),
        "n_covered": int(covered.sum()),
        "accuracy": float(correct.mean()) if covered.any() else None,
        "symbols": int(frame[covered].index.get_level_values(1).nunique()),
        "mean_return_on_buys": float(
            frame.loc[covered & (frame[f"call_{arm}"] == "BUY"), "asset_return"].mean())
        if (covered & (frame[f"call_{arm}"] == "BUY")).any() else None,
    }


def stability(frame: pd.DataFrame, arm: str) -> dict:
    """Chronological halves and trend regimes — pre-defined diagnostics, not selection."""
    cutoffs = sorted(frame.index.get_level_values(0).unique())
    midpoint = cutoffs[len(cutoffs) // 2]
    out: dict[str, dict] = {}

    for name, mask in (("first_half", frame.index.get_level_values(0) < midpoint),
                       ("second_half", frame.index.get_level_values(0) >= midpoint)):
        out[name] = _slice_summary(frame[mask], arm)
    for trend, block in frame.groupby("trend"):
        out[f"trend:{trend}"] = _slice_summary(block, arm)
    return out


def _slice_summary(block: pd.DataFrame, arm: str) -> dict:
    if block.empty:
        return {}
    series = per_cutoff(block, arm)
    covered = block[f"call_{arm}"].isin(COVERED)
    return {
        "cutoffs": int(len(series)),
        "rows": int(len(block)),
        "up_rate": round(float(block["direction"].mean()), 4),
        "accuracy": round(float(series["accuracy"].mean()), 4),
        "log_loss": round(float(series["log_loss"].mean()), 5),
        "coverage": round(float(covered.mean()), 4),
        "covered_accuracy": (round(float(call_correct(
            block[f"call_{arm}"], block["direction"]).mean()), 4)
            if covered.any() else None),
    }


# ----------------------------------------------------------------------
# The frozen gates (§5.2)
# ----------------------------------------------------------------------

def gates(frame: pd.DataFrame, series: dict[str, pd.DataFrame], best: str) -> dict:
    """Evaluate G1-G4 exactly as §5.2 states them. Decides nothing new."""
    out: dict[str, dict] = {}

    g1 = paired(series[best]["log_loss"], series["S1"]["log_loss"],
                f"log loss {best} - S1")
    out["G1"] = {
        "requirement": f"{best} log loss below S1, 95% interval entirely below zero",
        "difference": g1,
        "passed": bool(np.isfinite(g1["boot_hi"]) and g1["boot_hi"] < 0.0),
    }

    table = reliability(frame, best)
    ece = expected_calibration_error(table)
    mono = monotonicity(table)
    out["G2"] = {
        "requirement": f"ECE <= {cfg.G2_MAX_ECE} and monotonicity Spearman "
                       f">= {cfg.G2_MIN_MONOTONE_SPEARMAN}",
        "ece": round(ece, 5) if np.isfinite(ece) else None,
        "monotonicity": mono,
        "passed": bool(np.isfinite(ece) and ece <= cfg.G2_MAX_ECE
                       and mono["spearman"] is not None
                       and mono["spearman"] >= cfg.G2_MIN_MONOTONE_SPEARMAN),
    }

    covered = frame[f"call_{best}"].isin(COVERED)
    coverage = float(covered.mean())
    breadth = int(frame[covered].index.get_level_values(1).nunique())
    g3 = paired(series[best]["covered_accuracy"], series[best]["accuracy"],
                f"{best} covered accuracy - all-row accuracy")
    out["G3"] = {
        "requirement": f"covered accuracy above all-row accuracy, interval above zero, "
                       f"coverage >= {cfg.G3_MIN_COVERAGE}, breadth >= {cfg.G3_MIN_SYMBOLS}",
        "coverage": round(coverage, 5),
        "symbols": breadth,
        "difference": g3,
        "passed": bool(coverage >= cfg.G3_MIN_COVERAGE and breadth >= cfg.G3_MIN_SYMBOLS
                       and np.isfinite(g3["boot_lo"]) and g3["boot_lo"] > 0.0),
    }

    g4 = paired(series[best]["covered_accuracy"], series[best]["covered_up_rate"],
                f"{best} covered accuracy - always-up on the same rows")
    out["G4"] = {
        "requirement": "covered accuracy above the always-up rate on the same rows, "
                       "95% interval entirely above zero",
        "difference": g4,
        "passed": bool(np.isfinite(g4["boot_lo"]) and g4["boot_lo"] > 0.0),
    }

    out["verdict"] = ("ADVANCE" if all(out[g]["passed"] for g in ("G1", "G2", "G3", "G4"))
                      else "DO NOT ADVANCE")
    return out


# ----------------------------------------------------------------------
# The run
# ----------------------------------------------------------------------

def load_predictions() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not cfg.PREDICTIONS_PATH.exists():
        raise SystemExit("no frozen predictions — run: python -m alpha.singlename")
    blob = pd.read_pickle(cfg.PREDICTIONS_PATH)
    return blob["predictions"], blob["states"]


def joined(predictions: pd.DataFrame, data: singlename.SingleNameData) -> pd.DataFrame:
    """The one join between the two processes. Outcomes enter here and nowhere earlier."""
    labels = data.labels[["asset_return", "direction"]]
    frame = predictions.join(labels, how="inner")
    missing = len(predictions) - len(frame)
    if missing:
        print(f"note        {missing} predictions had no outcome row and were dropped")
    return frame


def report(frame: pd.DataFrame) -> dict:
    series = {arm: per_cutoff(frame, arm) for arm in cfg.ARMS}
    cutoffs = sorted(frame.index.get_level_values(0).unique())

    summary = {}
    for arm in cfg.ARMS:
        block = series[arm]
        summary[arm] = {
            "label": cfg.ARM_LABELS[arm],
            "accuracy": describe(block["accuracy"], f"{arm} accuracy"),
            "balanced_accuracy": describe(block["balanced_accuracy"], f"{arm} balanced acc"),
            "log_loss": describe(block["log_loss"], f"{arm} log loss"),
            "brier": describe(block["brier"], f"{arm} brier"),
            "auc": describe(block["auc"], f"{arm} auc"),
            "mae": describe(block["mae"], f"{arm} mae"),
            "rmse": describe(block["rmse"], f"{arm} rmse"),
            "sign_accuracy": describe(block["sign_accuracy"], f"{arm} sign acc"),
            "pred_realised_corr": describe(block["pred_realised_corr"], f"{arm} corr"),
            "pred_realised_spearman": describe(block["pred_realised_spearman"],
                                               f"{arm} spearman"),
            "interval_coverage": describe(block["interval_coverage"], f"{arm} interval cov"),
            "coverage": round(float(frame[f"call_{arm}"].isin(COVERED).mean()), 5),
            "vs_S1_log_loss": paired(block["log_loss"], series["S1"]["log_loss"],
                                     f"{arm} - S1 log loss"),
            "vs_S0_accuracy": paired(block["accuracy"], series["S0"]["accuracy"],
                                     f"{arm} - S0 accuracy"),
            "vs_S1_brier": paired(block["brier"], series["S1"]["brier"],
                                  f"{arm} - S1 brier"),
        }

    # §5.2 "the best of S3/S4", on log loss. Both were pre-registered; no third
    # candidate is admitted and no other metric is consulted for this choice.
    best = min(("S3", "S4"), key=lambda a: float(series[a]["log_loss"].mean()))

    calibration = {}
    for arm in ("S1", "S2", "S3", "S4"):
        table = reliability(frame, arm)
        calibration[arm] = {
            "ece": round(expected_calibration_error(table), 5),
            "monotonicity": monotonicity(table),
            "table": _table(table),
        }

    return {
        "protocol": cfg.PREREGISTRATION,
        "model_version": cfg.MODEL_VERSION,
        "horizon_sessions": cfg.HORIZON,
        "target": cfg.TARGET_RETURN,
        "scored_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "sample": {
            "cutoffs": len(cutoffs),
            "first_cutoff": str(cutoffs[0].date()),
            "last_cutoff": str(cutoffs[-1].date()),
            "rows": int(len(frame)),
            "symbols": int(frame.index.get_level_values(1).nunique()),
            "up_rate": round(float(frame["direction"].mean()), 5),
            "mean_return": round(float(frame["asset_return"].mean()), 6),
            "exam_cutoffs_touched": 0,
        },
        "arms": summary,
        "best_probabilistic_arm": best,
        "calibration": calibration,
        "confidence": {arm: _table(by_confidence(frame, arm)) for arm in ("S3", "S4")},
        "return_deciles": {arm: _table(return_deciles(frame, arm)) for arm in ("S3", "S4")},
        "abstention": {
            arm: {
                "primary": {
                    "coverage": round(float(frame[f"call_{arm}"].isin(COVERED).mean()), 5),
                    "n_covered": int(frame[f"call_{arm}"].isin(COVERED).sum()),
                    "n_buy": int((frame[f"call_{arm}"] == "BUY").sum()),
                    "n_sell": int((frame[f"call_{arm}"] == "SELL").sum()),
                    "symbols": int(frame[frame[f"call_{arm}"].isin(COVERED)]
                                   .index.get_level_values(1).nunique()),
                    "covered_accuracy": describe(series[arm]["covered_accuracy"],
                                                 f"{arm} covered accuracy"),
                    "covered_return": describe(series[arm]["covered_return"],
                                               f"{arm} covered return"),
                    "buy_return": describe(series[arm]["buy_return"], f"{arm} buy return"),
                },
                "uncertainty_gated": uncertainty_gated(frame, arm),
                "threshold_sweep": _table(threshold_sweep(frame, arm)),
            } for arm in ("S3", "S4")
        },
        "stability": {arm: stability(frame, arm) for arm in ("S3", "S4")},
        "resolution": {
            "block_length_cutoffs": stats.BLOCK_LENGTH,
            "bootstrap_draws": stats.BOOTSTRAP_DRAWS,
            "note": "half-width of the 95% moving-block bootstrap interval on the paired "
                    "per-cutoff difference. An improvement smaller than this cannot be "
                    "distinguished from zero at this sample size.",
            "mde": {
                "accuracy_vs_S0": summary[best]["vs_S0_accuracy"]["half_width"],
                "log_loss_vs_S1": summary[best]["vs_S1_log_loss"]["half_width"],
                "brier_vs_S1": summary[best]["vs_S1_brier"]["half_width"],
            },
        },
        "gates": gates(frame, series, best),
    }


def _table(frame: pd.DataFrame) -> list[dict]:
    out = frame.reset_index()
    out.columns = [str(c) for c in out.columns]
    return json.loads(out.to_json(orient="records", double_precision=6))


def main() -> None:
    predictions, _ = load_predictions()
    data = singlename.load(verbose=False)
    frame = joined(predictions, data)

    result = report(frame)
    cfg.SCORES_PATH.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    pd.to_pickle({arm: per_cutoff(frame, arm) for arm in cfg.ARMS}, cfg.SERIES_PATH)

    sample = result["sample"]
    print(f"scored      {sample['rows']:,} rows over {sample['cutoffs']} development "
          f"cutoffs ({sample['first_cutoff']} .. {sample['last_cutoff']})")
    print(f"up-rate     {sample['up_rate']:.4f}  ·  mean 5D return "
          f"{sample['mean_return']:+.5f}")
    print()
    print("%-4s %-22s %9s %9s %9s %9s %9s" %
          ("arm", "what", "accuracy", "logloss", "brier", "auc", "coverage"))
    for arm in cfg.ARMS:
        row = result["arms"][arm]
        print("%-4s %-22s %9.4f %9.4f %9.4f %9s %9.4f" % (
            arm, row["label"], row["accuracy"]["mean"], row["log_loss"]["mean"],
            row["brier"]["mean"],
            "%.4f" % row["auc"]["mean"] if np.isfinite(row["auc"]["mean"]) else "n/a",
            row["coverage"]))
    print()
    for name in ("G1", "G2", "G3", "G4"):
        gate = result["gates"][name]
        print(f"{name}  {'PASS' if gate['passed'] else 'FAIL'}  {gate['requirement']}")
    print(f"\nPHASE 1 VERDICT: {result['gates']['verdict']}")
    print(f"wrote       {cfg.SCORES_PATH}")


if __name__ == "__main__":
    main()
