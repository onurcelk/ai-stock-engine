"""AMS-1 scorer: reads predictions and outcomes, never writes a prediction.

The other half of the two-process separation. `ams1_run.py` wrote
`ams1_predictions.pkl` before any outcome was joined to it; this module reads
that file and the labels, and produces the tables the pre-registration named.

Every interval is a **paired, per-cutoff, moving-block bootstrap** at
`alpha/stats.py`'s own block length — 4 cutoffs, ~one month — which is the
instrument the programme has always judged its thresholds against and is
inherited here rather than re-derived.
"""

from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from . import ams1_config as cfg
from . import ams1_meta as meta
from . import singlename, stats

ARMS = {
    "B0_base_rate": "B0_prob",
    "B1_momentum": "B1_prob",
    "B2_b3": "B2_prob",
    "B3_b3_market_state": "B3_prob",
    "B4_raw_vote": "B4_prob",
    "B5_family_buckets": "B5_prob",
    "AMS_family_calibrated": "AMS_prob",
    "AMS_incremental": "AMSI_prob",
}


def joined() -> pd.DataFrame:
    """Predictions with their outcomes attached. The only join in the study."""
    predictions = pd.read_pickle(cfg.PREDICTIONS_PATH)
    data = singlename.load(verbose=False)
    labels = data.labels.loc[data.labels.index.intersection(predictions.index)]
    frame = predictions.join(labels[["asset_return", "direction"]], how="inner")
    return frame[frame["direction"].notna()]


def log_loss(prob: pd.Series, actual: pd.Series) -> pd.Series:
    p = prob.clip(cfg.PROB_CLIP, 1.0 - cfg.PROB_CLIP)
    return -(actual * np.log(p) + (1.0 - actual) * np.log(1.0 - p))


def brier(prob: pd.Series, actual: pd.Series) -> pd.Series:
    return (prob - actual) ** 2


def per_cutoff(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """One row per cutoff for one arm. The unit every interval is taken over."""
    work = pd.DataFrame({
        "logloss": log_loss(frame[column], frame["direction"]),
        "brier": brier(frame[column], frame["direction"]),
        "hit": ((frame[column] >= 0.5).astype(float)
                == frame["direction"]).astype(float),
    }, index=frame.index)
    return work.groupby(level=0).mean()


def interval(values: pd.Series) -> dict:
    """Mean and 95% moving-block bootstrap interval over the per-cutoff series."""
    clean = values.dropna()
    if len(clean) < 4:
        return {"n": int(len(clean)), "mean": float("nan"),
                "lo": float("nan"), "hi": float("nan")}
    lo, hi = stats.block_bootstrap_ci(clean.to_numpy(dtype=float),
                                      block=cfg.BLOCK_LENGTH_CUTOFFS,
                                      draws=cfg.BOOTSTRAP_DRAWS)
    return {"n": int(len(clean)), "mean": float(clean.mean()),
            "lo": float(lo), "hi": float(hi),
            "half_width": float((hi - lo) / 2)}


def paired(frame: pd.DataFrame, left: str, right: str, metric: str) -> dict:
    """`right - left` per cutoff. Positive means `left` scores better on a loss."""
    a = per_cutoff(frame, ARMS[left])[metric]
    b = per_cutoff(frame, ARMS[right])[metric]
    got = interval(b - a)
    got.update(left=left, right=right, metric=metric,
               excludes_zero=bool(np.isfinite(got.get("lo", np.nan))
                                  and (got["lo"] > 0 or got["hi"] < 0)))
    return got


def ladder_table(frame: pd.DataFrame, state_column: str = "state") -> pd.DataFrame:
    """The primary monotonicity table."""
    rows = []
    total = len(frame)
    for state in cfg.LADDER:
        block = frame[frame[state_column] == state]
        if block.empty:
            rows.append({"state": state, "n": 0})
            continue
        per_date = block.groupby(level=0)["direction"].mean()
        per_date_ret = block.groupby(level=0)["asset_return"].mean()
        up = interval(per_date)
        ret = interval(per_date_ret)
        rows.append({
            "state": state,
            "n": int(len(block)),
            "coverage": round(len(block) / total, 4),
            "cutoffs": int(block.index.get_level_values(0).nunique()),
            "symbols": int(block.index.get_level_values(1).nunique()),
            "p_up": round(float(block["direction"].mean()), 4),
            "p_up_lo": round(up["lo"], 4), "p_up_hi": round(up["hi"], 4),
            "mean_return_bp": round(1e4 * float(block["asset_return"].mean()), 1),
            "ret_lo_bp": round(1e4 * ret["lo"], 1),
            "ret_hi_bp": round(1e4 * ret["hi"], 1),
            "brier": round(float(brier(frame.loc[block.index, "AMS_prob"],
                                       block["direction"]).mean()), 5),
            "logloss": round(float(log_loss(frame.loc[block.index, "AMS_prob"],
                                            block["direction"]).mean()), 5),
        })
    return pd.DataFrame(rows)


def monotonicity(table: pd.DataFrame) -> dict:
    """Spearman of P(up) against the ordered states, plus the extreme gap.

    Only states meeting §7's minimum geometry enter the statistic. That rule is
    §7's own — "minimum geometry for a ladder state to count as a **result**
    rather than a diagnostic" — and it is applied here rather than invented
    later because the geometry was known before any outcome was read: a family
    almost never abstains, so `mixed` (net vote exactly 0) holds 20 rows on 2
    dates and would otherwise inject pure noise into a five-point rank
    correlation.
    """
    live = table[(table["n"] >= cfg.MIN_BUCKET_ROWS)
                 & (table["cutoffs"] >= cfg.MIN_BUCKET_CUTOFFS)
                 & (table["symbols"] >= cfg.MIN_BUCKET_SYMBOLS)].copy()
    if len(live) < 3:
        return {"spearman": float("nan"), "states": int(len(live))}
    order = pd.Series(range(len(live)), index=live.index, dtype=float)
    rho = float(order.corr(live["p_up"].astype(float), method="spearman"))
    strictly = bool(live["p_up"].is_monotonic_increasing)
    return {"spearman": round(rho, 4), "states": int(len(live)),
            "strictly_increasing": strictly,
            "extreme_gap_pp": round(100 * float(live["p_up"].iloc[-1]
                                                - live["p_up"].iloc[0]), 3)}


def abstention(frame: pd.DataFrame, arm: str = "AMS_family_calibrated") -> dict:
    """Predict only where the families are unanimous; everything else is NO EDGE."""
    column = ARMS[arm]
    keep = frame["state"].isin(["strong bearish", "strong bullish"])
    out = {}
    for label, block in (("all", frame), ("retained", frame[keep]),
                         ("abstained", frame[~keep])):
        if block.empty:
            out[label] = {"n": 0}
            continue
        cut = per_cutoff(block, column)
        out[label] = {
            "n": int(len(block)),
            "coverage": round(len(block) / len(frame), 4),
            "cutoffs": int(block.index.get_level_values(0).nunique()),
            "symbols": int(block.index.get_level_values(1).nunique()),
            "accuracy": round(float(cut["hit"].mean()), 4),
            "brier": round(float(cut["brier"].mean()), 5),
            "logloss": round(float(cut["logloss"].mean()), 5),
            "p_up": round(float(block["direction"].mean()), 4),
            "mean_return_bp": round(1e4 * float(block["asset_return"].mean()), 1),
        }
    if out["retained"].get("n") and out["all"].get("n"):
        gain = interval(per_cutoff(frame[keep], column)["logloss"]
                        .reindex(sorted(frame.index.get_level_values(0).unique()))
                        - per_cutoff(frame, column)["logloss"])
        out["logloss_change_retained_minus_all"] = gain
    return out


def leave_one_family_out(frame: pd.DataFrame, stances: pd.DataFrame) -> dict:
    """Is the consensus distributed, or is one family carrying all of it?

    Diagnostic only. It never becomes an ensemble: no family is dropped from the
    primary construction on the strength of what this shows.
    """
    out = {}
    for dropped in cfg.FAMILIES:
        kept = {f: names for f, names in cfg.AGENTS.items() if f != dropped}
        columns = [n for names in kept.values() for n in names
                   if n in stances.columns]
        block = stances.loc[frame.index, columns]
        votes = pd.DataFrame({
            f: np.sign(block[[n for n in names if n in block.columns]]
                       .mean(axis=1, skipna=True))
            for f, names in kept.items()})
        net = votes.mean(axis=1, skipna=True).where(votes.notna().sum(axis=1) == 2)
        unanimous = net.abs() >= 1.0
        rows = frame[unanimous.fillna(False)]
        bullish = rows[net[unanimous.fillna(False)] > 0]
        bearish = rows[net[unanimous.fillna(False)] < 0]
        out[dropped] = {
            "unanimous_n": int(len(rows)),
            "bullish_n": int(len(bullish)),
            "bullish_p_up": round(float(bullish["direction"].mean()), 4)
            if len(bullish) else None,
            "bearish_n": int(len(bearish)),
            "bearish_p_up": round(float(bearish["direction"].mean()), 4)
            if len(bearish) else None,
        }
    return out


def stability(frame: pd.DataFrame) -> dict:
    """Halves of the development period, so a regime inversion cannot hide."""
    cutoffs = sorted(frame.index.get_level_values(0).unique())
    middle = cutoffs[len(cutoffs) // 2]
    out = {}
    for label, block in (("first_half", frame[frame.index.get_level_values(0) < middle]),
                         ("second_half", frame[frame.index.get_level_values(0) >= middle])):
        strong_up = block[block["state"] == "strong bullish"]
        strong_down = block[block["state"] == "strong bearish"]
        out[label] = {
            "cutoffs": int(block.index.get_level_values(0).nunique()),
            "strong_bullish_n": int(len(strong_up)),
            "strong_bullish_p_up": round(float(strong_up["direction"].mean()), 4)
            if len(strong_up) else None,
            "strong_bearish_n": int(len(strong_down)),
            "strong_bearish_p_up": round(float(strong_down["direction"].mean()), 4)
            if len(strong_down) else None,
        }
    return out


def reliability(frame: pd.DataFrame, arm: str = "AMS_family_calibrated") -> dict:
    """Calibration: does a stated 70% actually come in near 70%?"""
    column = ARMS[arm]
    bins = np.arange(0.0, 1.01, 0.05)
    binned = pd.cut(frame[column], bins, include_lowest=True)
    table = frame.groupby(binned, observed=True).agg(
        n=("direction", "size"), stated=(column, "mean"),
        observed=("direction", "mean"))
    table = table[table["n"] > 0]
    ece = float((table["n"] / table["n"].sum()
                 * (table["stated"] - table["observed"]).abs()).sum())
    return {"ece": round(ece, 5),
            "bins": [{"stated": round(float(r.stated), 4),
                      "observed": round(float(r.observed), 4), "n": int(r.n)}
                     for r in table.itertuples()]}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values over the primary gate statistics."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted, running = {}, 0.0
    for rank, (key, value) in enumerate(items):
        running = max(running, (m - rank) * value)
        adjusted[key] = min(1.0, running)
    return adjusted


def report() -> dict:
    """Every table and gate the pre-registration named, in one artefact."""
    frame = joined()
    stances = pd.read_pickle(cfg.SIGNALS_PATH)
    table = ladder_table(frame, "state")
    raw_table = ladder_table(frame, "raw_state")
    mono = monotonicity(table)

    bull = frame[frame["state"] == "strong bullish"].groupby(level=0)["direction"].mean()
    bear = frame[frame["state"] == "strong bearish"].groupby(level=0)["direction"].mean()
    gap = interval((bull - bear).dropna())
    bull_ret = frame[frame["state"] == "strong bullish"].groupby(level=0)["asset_return"].mean()
    bear_ret = frame[frame["state"] == "strong bearish"].groupby(level=0)["asset_return"].mean()
    gap_ret = interval((bull_ret - bear_ret).dropna())

    gates = {}
    g2 = paired(frame, "B3_b3_market_state", "AMS_family_calibrated", "logloss")
    gates["2_probabilistic"] = dict(
        g2, passed=bool(g2["excludes_zero"] and -g2["mean"] >= cfg.MIN_LOGLOSS_GAIN))
    g4 = paired(frame, "B4_raw_vote", "AMS_family_calibrated", "logloss")
    gates["4_family_beats_raw"] = dict(
        g4, passed=bool(g4["excludes_zero"] and g4["mean"] < 0))
    g5 = paired(frame, "B3_b3_market_state", "AMS_incremental", "logloss")
    gates["5_incremental"] = dict(
        g5, passed=bool(g5["excludes_zero"] and -g5["mean"] >= cfg.MIN_LOGLOSS_GAIN))
    gates["3_monotonicity"] = dict(
        mono, gap=gap,
        passed=bool(np.isfinite(mono.get("spearman", np.nan))
                    and mono["spearman"] >= cfg.MIN_LADDER_SPEARMAN
                    and gap["lo"] > 0))
    abst = abstention(frame)
    gates["6_abstention"] = dict(
        abst, passed=bool(abst["retained"]["logloss"] < abst["all"]["logloss"]
                          and abst["retained"]["coverage"] >= cfg.MIN_ABSTAIN_COVERAGE))
    extremes = table[table["state"].isin(["strong bearish", "strong bullish"])]
    gates["7_breadth"] = {
        "min_symbols": int(extremes["symbols"].min()),
        "min_cutoffs": int(extremes["cutoffs"].min()),
        "passed": bool(extremes["symbols"].min() >= cfg.MIN_SYMBOLS
                       and extremes["cutoffs"].min() >= cfg.MIN_CUTOFFS)}
    stab = stability(frame)
    inverted = [half for half, got in stab.items()
                if got["strong_bullish_p_up"] is not None
                and got["strong_bullish_p_up"] > got["strong_bearish_p_up"]]
    gates["8_stability"] = dict(stab, halves_favouring_hypothesis=len(inverted),
                                passed=len(inverted) == 2)
    bear_rate = float(frame[frame["state"] == "strong bearish"]["direction"].mean())
    bear_ci = interval(bear)
    gates["9_bearish"] = {
        "p_up_strong_bearish": round(bear_rate, 4),
        "ci": [round(bear_ci["lo"], 4), round(bear_ci["hi"], 4)],
        "passed": bool(bear_ci["hi"] < cfg.SUB_50)}

    arms = {name: {k: round(float(v), 5) for k, v in
                   per_cutoff(frame, column).mean().items()}
            for name, column in ARMS.items()}

    payload = {
        "scored_at": dt.datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(frame)),
        "cutoffs": int(frame.index.get_level_values(0).nunique()),
        "symbols": int(frame.index.get_level_values(1).nunique()),
        "base_up_rate": round(float(frame["direction"].mean()), 4),
        "base_return_bp": round(1e4 * float(frame["asset_return"].mean()), 1),
        "arms": arms,
        "family_ladder": table.to_dict("records"),
        "raw_ladder": raw_table.to_dict("records"),
        "monotonicity": mono,
        "extreme_gap_p_up": gap,
        "extreme_gap_return_bp": {k: (round(1e4 * v, 1) if isinstance(v, float) else v)
                                  for k, v in gap_ret.items()},
        "gates": gates,
        "leave_one_family_out": leave_one_family_out(frame, stances),
        "reliability": reliability(frame),
        "verdict": "ADVANCE" if all(
            gates[k]["passed"] for k in ("2_probabilistic", "3_monotonicity",
                                         "4_family_beats_raw", "5_incremental",
                                         "7_breadth", "8_stability")) else "REJECT",
    }
    cfg.RESULT_PATH.write_text(json.dumps(payload, indent=1, default=str),
                               encoding="utf-8")
    return payload


def main() -> int:
    payload = report()
    print(f"rows {payload['rows']:,}  cutoffs {payload['cutoffs']}  "
          f"symbols {payload['symbols']}  base up-rate {payload['base_up_rate']}")
    print("\ngates:")
    for name, got in payload["gates"].items():
        print(f"  {name:22s} {'PASS' if got['passed'] else 'FAIL'}")
    print(f"\nAMS-1 VERDICT: {payload['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
