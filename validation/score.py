"""Stage 2 — reveal the outcomes and score the frozen predictions.

Reads `out/predictions.json` and `out/model.jsonl`, never writes them. Flattens
every prediction into one row per (cutoff, symbol, system, scoring window) so
that every table below is a groupby on the same audited frame, saved to
`out/calls.csv` for anyone who wants to check a number by hand.

Two distinctions run through all of it, because they are the ones that decide
whether a forecasting system is real:

* **Lean vs. acted.** Most of this engine's output is HOLD. Scoring only the
  bars where it named a direction measures the direction-naming; scoring every
  bar measures the product. Both appear, never blended.
* **Right vs. better than trivial.** Every accuracy is reported next to the
  paired difference against buy-and-hold, trend continuation and a moving
  average on the same rows. On a tape that rose, being right is cheap.

Run:  python -m validation.score
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import metrics, outcomes, pit, schedule

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

# Which scoring window each system's call is actually *about*. Scoring a
# four-hour call against a six-month outcome is not a measurement of the call.
NATIVE_WINDOW = {
    "consensus": "1w",
    "consensus_4h": "4h",
    "consensus_1d": "1d",
    "consensus_1w": "1w",
    "agent_turtle": "1w",
    "agent_crossover": "1w",
    "agent_rolling": "1w",
    "agent_combined": "1w",
    "model_lstm": "1w",
    "consensus_with_model": "1w",
}

BASELINES = ["buy_and_hold", "trend_continuation", "sma_direction",
             "golden_cross", "random"]

CRYPTO = {"BTC-USD", "ETH-USD"}
FX = {"EURUSD=X"}
FUNDS = {"SPY", "QQQ", "VOO", "SLV"}


def asset_class(symbol: str) -> str:
    if symbol in CRYPTO:
        return "crypto"
    if symbol in FX:
        return "fx"
    if symbol in FUNDS:
        return "fund"
    return "equity"


# ----------------------------------------------------------------- flattening


def _call(base: dict, system: str, direction, *, action=None, confidence=None,
          score=None, predicted_return=None, predicted_price=None,
          detail: str = "") -> dict:
    row = dict(base)
    row.update({
        "system": system,
        "predicted_direction": int(direction) if direction is not None else 0,
        "action": action,
        "confidence": confidence,
        "score": score,
        "predicted_return_pct": predicted_return,
        "predicted_price": predicted_price,
        "detail": detail,
        "native_window": NATIVE_WINDOW.get(system, "1w"),
    })
    return row


def collect_calls(predictions: dict, models: list[dict]) -> list[dict]:
    """Every system's call at every cutoff, before any outcome is attached."""
    by_key = {(m["cutoff"], m["symbol"]): m for m in models}
    calls: list[dict] = []

    for record in predictions["predictions"]:
        base = {
            "cutoff": record["cutoff"],
            "cutoff_label": record["cutoff_label"],
            "cutoff_kind": record["cutoff_kind"],
            "symbol": record["symbol"],
            "asset_class": asset_class(record["symbol"]),
        }

        consensus = record.get("consensus", {})
        if "failed" not in consensus:
            calls.append(_call(
                base, "consensus", consensus["direction"],
                action=consensus["action"], confidence=consensus["confidence"],
                score=consensus["score"],
                predicted_return=consensus.get("expected_move_pct"),
                predicted_price=consensus.get("target_price"),
                detail=f"lead horizon {consensus.get('lead_horizon')}, "
                       f"{consensus['alignment']}",
            ))
            for horizon in consensus.get("by_horizon", []):
                if not horizon.get("available"):
                    continue
                calls.append(_call(
                    base, f"consensus_{horizon['horizon']}",
                    int(np.sign(horizon["score"])),
                    action=horizon["action"], confidence=horizon["confidence"],
                    score=horizon["score"],
                    predicted_return=horizon["expected_move_pct"],
                    predicted_price=horizon["target_price"],
                    detail=f"{horizon['sources_counted']} sources counted",
                ))

        agents = record.get("agents", {})
        if agents.get("available"):
            for key, agent in agents["agents"].items():
                calls.append(_call(base, key, agent["direction"],
                                   action=agent["signal"],
                                   detail=f"held since {agent['held_since']}"))
            calls.append(_call(base, "agent_combined",
                               agents["combined"]["direction"],
                               action=agents["combined"]["signal"],
                               detail=f"votes {agents['combined']['votes']}"))

        found = by_key.get((record["cutoff"], record["symbol"]))
        forecast = (found or {}).get("forecast", {})
        if forecast.get("available"):
            walk = forecast["walk_forward"]
            calls.append(_call(
                base, "model_lstm", forecast["direction"],
                action="up" if forecast["direction"] > 0 else "down",
                # The forecaster's own confidence is the only one it has: how
                # often it got the direction right on folds it never trained on.
                confidence=walk["mean_directional_pct"],
                score=forecast["predicted_move_pct"],
                predicted_return=forecast["predicted_move_pct"],
                predicted_price=forecast["predicted_price"],
                detail=f"walk-forward {walk['mean_directional_pct']:.0f}% over "
                       f"{walk['samples']} bars",
            ))
            with_model = forecast["consensus_with_model"]
            calls.append(_call(
                base, "consensus_with_model", with_model["direction"],
                action=with_model["action"], confidence=with_model["confidence"],
                score=with_model["score"],
                detail=f"model weight {with_model['model_weight_pct']}",
            ))
    return calls


def attach_outcomes(calls: list[dict], revealed: dict) -> pd.DataFrame:
    """Cross every call with every scoring window that actually happened."""
    lookup = {(row["cutoff"], row["symbol"]): row for row in revealed["rows"]}
    windows = list(schedule.OUTCOME_BARS) + ["4h"]
    rows = []

    for call in calls:
        found = lookup.get((call["cutoff"], call["symbol"]))
        if found is None:
            continue
        for window in windows:
            outcome = (found.get("outcomes") or {}).get(window)
            if outcome is None:
                continue
            bench = (found.get("benchmark") or {}).get(window)
            row = dict(call)
            row.update({
                "window": window,
                "is_native": window == call["native_window"],
                "window_bars": outcome["bars"],
                "start_price": outcome["start_price"],
                "actual_price": outcome["end_price"],
                "actual_return_pct": outcome["return_pct"],
                "actual_direction": outcome["direction"],
                "max_favourable_pct": outcome["max_favourable_pct"],
                "max_adverse_pct": outcome["max_adverse_pct"],
                "benchmark_return_pct": bench["return_pct"] if bench else None,
                "volatility_pct": found.get("volatility_pct"),
            })
            rows.append(row)

        # The baselines answer the same question on the same rows.
        for name in BASELINES:
            for window in schedule.OUTCOME_BARS:
                outcome = (found.get("outcomes") or {}).get(window)
                guess = (found.get("baselines") or {}).get(window, {}).get(name)
                if outcome is None or guess is None:
                    continue
                bench = (found.get("benchmark") or {}).get(window)
                rows.append({
                    **{k: call[k] for k in ("cutoff", "cutoff_label",
                                            "cutoff_kind", "symbol", "asset_class")},
                    "system": f"baseline_{name}", "predicted_direction": int(guess),
                    "action": None, "confidence": None, "score": None,
                    "predicted_return_pct": None, "predicted_price": None,
                    "detail": "", "native_window": window, "window": window,
                    "is_native": True, "window_bars": outcome["bars"],
                    "start_price": outcome["start_price"],
                    "actual_price": outcome["end_price"],
                    "actual_return_pct": outcome["return_pct"],
                    "actual_direction": outcome["direction"],
                    "max_favourable_pct": outcome["max_favourable_pct"],
                    "max_adverse_pct": outcome["max_adverse_pct"],
                    "benchmark_return_pct": bench["return_pct"] if bench else None,
                    "volatility_pct": found.get("volatility_pct"),
                })

    frame = pd.DataFrame(rows)
    # Baselines are emitted once per call, so the same guess appears as many
    # times as there were systems. Collapse to one row per symbol/date/window.
    is_baseline = frame["system"].str.startswith("baseline_")
    frame = pd.concat([
        frame[~is_baseline],
        frame[is_baseline].drop_duplicates(
            subset=["cutoff", "symbol", "system", "window"]),
    ], ignore_index=True)

    frame["has_lean"] = frame["predicted_direction"] != 0
    frame["actionable"] = frame.apply(_is_actionable, axis=1)
    frame["correct"] = np.where(
        frame["has_lean"] & (frame["actual_direction"] != 0),
        (frame["predicted_direction"] == frame["actual_direction"]).astype(float),
        np.nan,
    )
    # Return earned by taking the call's side — the number that pays for lunch.
    frame["directional_return_pct"] = np.where(
        frame["has_lean"],
        frame["predicted_direction"] * frame["actual_return_pct"], np.nan)
    frame["excess_vs_benchmark_pct"] = (frame["actual_return_pct"]
                                        - frame["benchmark_return_pct"])
    return frame


def _is_actionable(row: pd.Series) -> bool:
    """Did the system tell a user to do something, in its own vocabulary?"""
    if row["predicted_direction"] == 0:
        return False
    action = row["action"]
    if isinstance(action, str) and action.upper() in {"HOLD", "SPLIT", "NO POSITION"}:
        return False
    return True


# -------------------------------------------------------------------- reports


def directional_table(frame: pd.DataFrame, systems: list[str],
                      window: str | None = None, *, actioned_only: bool = False,
                      label: str = "") -> pd.DataFrame:
    rows = []
    for system in systems:
        subset = frame[frame["system"] == system]
        if window is not None:
            subset = subset[subset["window"] == window]
        else:
            subset = subset[subset["is_native"]]
        total = len(subset)
        if actioned_only:
            subset = subset[subset["actionable"]]
        scored = subset.dropna(subset=["correct"])
        if scored.empty:
            rows.append({"system": system, "scored": 0, "of": total,
                         "coverage %": 0.0, "accuracy %": None})
            continue
        est = metrics.accuracy(scored["correct"], scored["cutoff"])
        ret = metrics.estimate(scored["directional_return_pct"], scored["cutoff"])
        low, high = est.ci95
        rows.append({
            "system": system,
            "scored": est.n,
            "of": total,
            "coverage %": round(est.n / total * 100, 1) if total else 0.0,
            "accuracy %": round(est.value, 1),
            "95% CI": f"[{low:.1f}, {high:.1f}]",
            "naive CI±": round(1.96 * est.naive_se, 1),
            "p vs 50%": round(est.p_value, 3),
            "mean return %": round(ret.value, 2),
            "return p": round(ret.p_value, 3),
        })
    return pd.DataFrame(rows).assign(view=label or ("native" if window is None else window))


def baseline_comparison(frame: pd.DataFrame, system: str,
                        window: str = "1w") -> pd.DataFrame:
    """Paired accuracy difference against each trivial rule, same rows only."""
    left = frame[(frame["system"] == system) & (frame["window"] == window)]
    left = left.dropna(subset=["correct"]).set_index(["cutoff", "symbol"])
    rows = []
    for name in BASELINES:
        right = frame[(frame["system"] == f"baseline_{name}")
                      & (frame["window"] == window)]
        right = right.dropna(subset=["correct"]).set_index(["cutoff", "symbol"])
        common = left.index.intersection(right.index)
        if len(common) == 0:
            continue
        diff = metrics.paired(left.loc[common, "correct"],
                              right.loc[common, "correct"],
                              left.loc[common].reset_index()["cutoff"].values)
        low, high = diff.ci95
        rows.append({
            "baseline": name,
            "n": diff.n,
            f"{system} %": round(left.loc[common, "correct"].mean() * 100, 1),
            "baseline %": round(right.loc[common, "correct"].mean() * 100, 1),
            "difference pts": round(diff.value, 1),
            "95% CI": f"[{low:.1f}, {high:.1f}]",
            "p": round(diff.p_value, 3),
        })
    return pd.DataFrame(rows)


def versus_long(frame: pd.DataFrame, systems: list[str]) -> pd.DataFrame:
    """Every system against always-predicting-up, at its own horizon.

    The single most important comparison in the study. Most of these systems
    lean bullish most of the time, and the study window rose, so a large part
    of any hit rate here is the tape rather than the model. Differencing
    against a permanent long on the same rows removes exactly that.
    """
    rows = []
    for system in systems:
        subset = frame[(frame["system"] == system) & frame["is_native"]]
        subset = subset.dropna(subset=["correct"])
        if subset.empty:
            continue
        # Buy-and-hold is "up" on every row, so its correctness on these same
        # rows is simply whether the row went up.
        always_long = (subset["actual_direction"] > 0).astype(float)
        diff = metrics.paired(subset["correct"], always_long, subset["cutoff"])
        low, high = diff.ci95
        rows.append({
            "system": system,
            "window": subset["window"].iloc[0],
            "n": diff.n,
            "bullish leans %": round(float((subset["predicted_direction"] > 0).mean() * 100), 1),
            "accuracy %": round(float(subset["correct"].mean() * 100), 1),
            "always-long %": round(float(always_long.mean() * 100), 1),
            "difference pts": round(diff.value, 1),
            "95% CI": f"[{low:.1f}, {high:.1f}]",
            "p": round(diff.p_value, 3),
        })
    return pd.DataFrame(rows)


def confidence_calibration(frame: pd.DataFrame, system: str,
                           window: str = "1w") -> pd.DataFrame:
    subset = frame[(frame["system"] == system) & (frame["window"] == window)]
    subset = subset.dropna(subset=["correct", "confidence"])
    if subset.empty:
        return pd.DataFrame()
    edges = [0, 10, 20, 30, 50, 70, 90, 100.01]
    names = ["0–10", "10–20", "20–30", "30–50", "50–70", "70–90", "90–100"]
    bucket = pd.cut(subset["confidence"], bins=edges, labels=names, right=False)
    rows = []
    for name, group in subset.groupby(bucket, observed=True):
        est = metrics.accuracy(group["correct"], group["cutoff"])
        ret = metrics.estimate(group["directional_return_pct"], group["cutoff"])
        rows.append({
            "confidence band": name,
            "n": len(group),
            "mean stated %": round(group["confidence"].mean(), 1),
            "accuracy %": round(est.value, 1),
            "95% CI±": round(1.96 * est.se, 1) if est.se == est.se else None,
            "mean return %": round(ret.value, 2),
        })
    return pd.DataFrame(rows)


def signal_strength(frame: pd.DataFrame, system: str,
                    window: str = "1w") -> pd.DataFrame:
    subset = frame[(frame["system"] == system) & (frame["window"] == window)]
    subset = subset.dropna(subset=["correct", "score"])
    if subset.empty:
        return pd.DataFrame()
    magnitude = subset["score"].abs()
    bucket = pd.cut(magnitude, bins=[0, 15, 40, 100.01],
                    labels=["weak (<15)", "act (15–40)", "strong (40+)"],
                    right=False)
    rows = []
    for name, group in subset.groupby(bucket, observed=True):
        est = metrics.accuracy(group["correct"], group["cutoff"])
        ret = metrics.estimate(group["directional_return_pct"], group["cutoff"])
        excess = metrics.estimate(
            group["predicted_direction"] * group["excess_vs_benchmark_pct"],
            group["cutoff"])
        rows.append({
            "signal band": name,
            "n": len(group),
            "accuracy %": round(est.value, 1),
            "mean return %": round(ret.value, 2),
            "vs SPY pts": round(excess.value, 2),
            "return p": round(ret.p_value, 3),
        })
    return pd.DataFrame(rows)


def price_error(frame: pd.DataFrame, systems: list[str]) -> pd.DataFrame:
    rows = []
    for system in systems:
        subset = frame[(frame["system"] == system) & frame["is_native"]]
        subset = subset.dropna(subset=["predicted_price", "actual_price"])
        subset = subset[subset["predicted_price"] > 0]
        if subset.empty:
            continue
        absolute = (subset["predicted_price"] - subset["actual_price"]).abs()
        percentage = absolute / subset["actual_price"] * 100
        signed = (subset["predicted_price"] - subset["actual_price"]) / subset["actual_price"] * 100
        naive = (subset["start_price"] - subset["actual_price"]).abs() / subset["actual_price"] * 100
        rows.append({
            "system": system,
            "n": len(subset),
            "MAE $": round(float(absolute.mean()), 3),
            "MAPE %": round(float(percentage.mean()), 3),
            "median APE %": round(float(percentage.median()), 3),
            "signed bias %": round(float(signed.mean()), 3),
            "naive MAPE %": round(float(naive.mean()), 3),
            "beats naive": f"{float((percentage < naive).mean() * 100):.0f}%",
        })
    return pd.DataFrame(rows)


def money(frame: pd.DataFrame, systems: list[str],
          window: str = "1w") -> pd.DataFrame:
    """What taking the call was worth against just being long, paired per row.

    Accuracy and profit are different questions and can disagree: being right
    on many small moves and wrong on a few large ones is a good hit rate and a
    losing strategy. This is the money view of Step 10.
    """
    rows = []
    for system in systems:
        subset = frame[(frame["system"] == system) & (frame["window"] == window)]
        subset = subset.dropna(subset=["directional_return_pct"])
        if subset.empty:
            continue
        taken = metrics.estimate(subset["directional_return_pct"], subset["cutoff"])
        # Buy-and-hold on exactly the rows the system had an opinion on.
        held = metrics.estimate(subset["actual_return_pct"], subset["cutoff"])
        diff = metrics.paired(subset["directional_return_pct"] / 100,
                              subset["actual_return_pct"] / 100, subset["cutoff"])
        low, high = diff.ci95
        rows.append({
            "system": system,
            "n": len(subset),
            "taking the call %": round(taken.value, 2),
            "long the same rows %": round(held.value, 2),
            "difference pts": round(diff.value, 2),
            "95% CI": f"[{low:.2f}, {high:.2f}]",
            "p": round(diff.p_value, 3),
            "hit rate %": round(float(subset["correct"].mean() * 100), 1),
        })
    return pd.DataFrame(rows)


def return_error(frame: pd.DataFrame, systems: list[str], *,
                 leaning_only: bool = False) -> pd.DataFrame:
    rows = []
    for system in systems:
        subset = frame[(frame["system"] == system) & frame["is_native"]]
        if leaning_only:
            subset = subset[subset["has_lean"]]
        subset = subset.dropna(subset=["predicted_return_pct", "actual_return_pct"])
        if subset.empty:
            continue
        error = subset["predicted_return_pct"] - subset["actual_return_pct"]
        correlation = (subset["predicted_return_pct"].corr(subset["actual_return_pct"])
                       if len(subset) > 2 else float("nan"))
        rows.append({
            "system": system,
            "n": len(subset),
            "mean predicted %": round(float(subset["predicted_return_pct"].mean()), 3),
            "mean actual %": round(float(subset["actual_return_pct"].mean()), 3),
            "mean abs error pts": round(float(error.abs().mean()), 3),
            "mean signed error pts": round(float(error.mean()), 3),
            "corr(pred, actual)": round(float(correlation), 3),
            "median |predicted| %": round(float(subset["predicted_return_pct"].abs().median()), 3),
            "median |actual| %": round(float(subset["actual_return_pct"].abs().median()), 3),
            "size ratio": round(float(subset["predicted_return_pct"].abs().median()
                                      / max(subset["actual_return_pct"].abs().median(), 1e-9)), 3),
        })
    return pd.DataFrame(rows)


def systematic(frame: pd.DataFrame, system: str, window: str = "1w") -> dict:
    """Step 8 — the failure modes, looked for rather than waited for."""
    subset = frame[(frame["system"] == system) & (frame["window"] == window)]
    leaning = subset[subset["has_lean"]].dropna(subset=["correct"])
    out: dict[str, object] = {}
    if leaning.empty:
        return out

    bullish = leaning[leaning["predicted_direction"] > 0]
    bearish = leaning[leaning["predicted_direction"] < 0]
    out["bull_share_pct"] = round(len(bullish) / len(leaning) * 100, 1)
    out["actual_up_share_pct"] = round(
        float((leaning["actual_direction"] > 0).mean() * 100), 1)
    out["bull_accuracy_pct"] = (round(float(bullish["correct"].mean() * 100), 1)
                                if len(bullish) else None)
    out["bear_accuracy_pct"] = (round(float(bearish["correct"].mean() * 100), 1)
                                if len(bearish) else None)
    out["abstention_pct"] = round(
        float((~subset["has_lean"]).mean() * 100), 1)
    out["hold_pct"] = round(float((~subset["actionable"]).mean() * 100), 1)

    with_vol = leaning.dropna(subset=["volatility_pct"])
    if len(with_vol) >= 30:
        tercile = pd.qcut(with_vol["volatility_pct"], 3,
                          labels=["calm", "middling", "turbulent"])
        out["by_volatility"] = {
            str(name): {
                "n": len(group),
                "accuracy %": round(float(group["correct"].mean() * 100), 1),
                "mean vol %": round(float(group["volatility_pct"].mean()), 1),
                "mean return %": round(float(group["directional_return_pct"].mean()), 2),
            }
            for name, group in with_vol.groupby(tercile, observed=True)
        }

    out["by_asset_class"] = {
        str(name): {"n": len(group),
                    "accuracy %": round(float(group["correct"].mean() * 100), 1),
                    "mean return %": round(float(group["directional_return_pct"].mean()), 2)}
        for name, group in leaning.groupby("asset_class")
    }
    out["by_cutoff"] = {
        str(name): {"n": len(group),
                    "accuracy %": round(float(group["correct"].mean() * 100), 1),
                    "mean return %": round(float(group["directional_return_pct"].mean()), 2)}
        for name, group in leaning.groupby("cutoff")
    }
    by_symbol = leaning.groupby("symbol")["correct"].agg(["count", "mean"])
    by_symbol = by_symbol[by_symbol["count"] >= 4].sort_values("mean")
    out["worst_symbols"] = {s: f"{r['mean']*100:.0f}% of {int(r['count'])}"
                            for s, r in by_symbol.head(5).iterrows()}
    out["best_symbols"] = {s: f"{r['mean']*100:.0f}% of {int(r['count'])}"
                           for s, r in by_symbol.tail(5).iloc[::-1].iterrows()}
    return out


def headline(frame: pd.DataFrame, systems: list[str]) -> pd.DataFrame:
    """Step 9 — the summary table, one row per system, at its own horizon."""
    rows = []
    for system in systems:
        subset = frame[(frame["system"] == system) & frame["is_native"]]
        scored = subset.dropna(subset=["correct"])
        if scored.empty:
            continue
        est = metrics.accuracy(scored["correct"], scored["cutoff"])
        acted = scored[scored["actionable"]]
        confident = scored[scored["confidence"] >= 50] if "confidence" in scored else scored
        priced = scored.dropna(subset=["predicted_price"])
        priced = priced[priced["predicted_price"] > 0]
        returns = scored.dropna(subset=["predicted_return_pct"])
        rows.append({
            "system": system,
            "predictions": len(subset),
            "leaned": est.n,
            "acted on": len(acted),
            "directional %": round(est.value, 1),
            "p": round(est.p_value, 3),
            "acted %": round(float(acted["correct"].mean() * 100), 1) if len(acted) else None,
            "high-conf %": (round(float(confident["correct"].mean() * 100), 1)
                            if len(confident) else None),
            "high-conf n": len(confident),
            "return err pts": (round(float((returns["predicted_return_pct"]
                                            - returns["actual_return_pct"]).abs().mean()), 2)
                               if len(returns) else None),
            "price MAPE %": (round(float(((priced["predicted_price"] - priced["actual_price"]).abs()
                                          / priced["actual_price"] * 100).mean()), 2)
                             if len(priced) else None),
            "mean return %": round(float(scored["directional_return_pct"].mean()), 2),
        })
    return pd.DataFrame(rows)


def adds_value(frame: pd.DataFrame, left: str, right: str,
               window: str = "1w") -> pd.DataFrame:
    """Paired accuracy difference between two of our own systems (Step 6)."""
    a = frame[(frame["system"] == left) & (frame["window"] == window)]
    b = frame[(frame["system"] == right) & (frame["window"] == window)]
    a = a.dropna(subset=["correct"]).set_index(["cutoff", "symbol"])
    b = b.dropna(subset=["correct"]).set_index(["cutoff", "symbol"])
    common = a.index.intersection(b.index)
    if len(common) == 0:
        return pd.DataFrame()
    diff = metrics.paired(a.loc[common, "correct"], b.loc[common, "correct"],
                          a.loc[common].reset_index()["cutoff"].values)
    low, high = diff.ci95
    return pd.DataFrame([{
        "comparison": f"{left} vs {right}",
        "n": diff.n,
        "left %": round(float(a.loc[common, "correct"].mean() * 100), 1),
        "right %": round(float(b.loc[common, "correct"].mean() * 100), 1),
        "difference pts": round(diff.value, 1),
        "95% CI": f"[{low:.1f}, {high:.1f}]",
        "p": round(diff.p_value, 3),
    }])


def gap_confound() -> pd.DataFrame:
    """How much of the "4 hours ahead" outcome is really the overnight gap.

    Cutoffs are chosen at daily granularity, so the last hourly bar before one
    is always a session close and every 4-hour window therefore straddles an
    overnight gap — a third of them a full weekend. That is a legitimate use of
    the product (checking the app after the close) but it is *not* a random
    intraday sample, and any claim about the 4-hour horizon has to be qualified
    by it. Measured here rather than hand-waved.
    """
    rows = []
    for entry in schedule.cutoffs():
        cutoff = entry["date"]
        for symbol in pit.cached_symbols("1h"):
            hourly = pit.full_history(symbol, "1h")
            if hourly is None:
                continue
            here = outcomes._index_at(hourly["date"], cutoff)
            if here is None or here + 4 >= len(hourly):
                continue
            close = hourly["close"]
            start, overnight, end = (float(close.iloc[here]),
                                     float(close.iloc[here + 1]),
                                     float(close.iloc[here + 4]))
            rows.append({
                "weekday": cutoff.day_name()[:3],
                "gap_pct": (overnight / start - 1) * 100,
                "total_pct": (end / start - 1) * 100,
            })
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    share = (frame["gap_pct"].abs()
             / frame["total_pct"].abs().replace(0, np.nan)).median()
    return pd.DataFrame([{
        "windows": len(frame),
        "starting on a Friday": int((frame["weekday"] == "Fri").sum()),
        "median |gap| %": round(float(frame["gap_pct"].abs().median()), 3),
        "median |4-bar move| %": round(float(frame["total_pct"].abs().median()), 3),
        "gap share of the move": round(float(share), 2),
        "gap sign = move sign": f"{float((np.sign(frame['gap_pct']) == np.sign(frame['total_pct'])).mean() * 100):.0f}%",
    }])


def model_influence(frame: pd.DataFrame, models: list[dict]) -> pd.DataFrame:
    """Did folding the forecast into the consensus change anything at all?

    `ModelEvidence` weights the forecaster by its own walk-forward directional
    edge and drops it when that edge is inside its own noise. If that gate
    fires every time, the "Include the forecast" toggle is a minute of training
    that moves no number — worth knowing precisely, not approximately.
    """
    a = frame[(frame["system"] == "consensus") & (frame["window"] == "1w")]
    b = frame[(frame["system"] == "consensus_with_model") & (frame["window"] == "1w")]
    a = a.set_index(["cutoff", "symbol"])
    b = b.set_index(["cutoff", "symbol"])
    common = a.index.intersection(b.index)
    if len(common) == 0:
        return pd.DataFrame()

    changed_action = (a.loc[common, "action"] != b.loc[common, "action"]).sum()
    changed_score = (~np.isclose(a.loc[common, "score"].astype(float),
                                 b.loc[common, "score"].astype(float))).sum()
    weights = [w for row in models if row.get("forecast", {}).get("available")
               for w in row["forecast"]["consensus_with_model"]["model_weight_pct"].values()]
    directional = [row["forecast"]["walk_forward"]["mean_directional_pct"]
                   for row in models if row.get("forecast", {}).get("available")]
    return pd.DataFrame([{
        "paired verdicts": len(common),
        "actions changed": int(changed_action),
        "scores changed": int(changed_score),
        "horizon-slots where model carried weight":
            f"{sum(1 for w in weights if w > 0)} of {len(weights)}",
        "walk-forward directional, mean %": round(float(np.mean(directional)), 1) if directional else None,
        "walk-forward directional, best %": round(float(np.max(directional)), 1) if directional else None,
        "runs above 50%": f"{sum(1 for d in directional if d > 50)} of {len(directional)}",
    }])


def ledger(frame: pd.DataFrame, symbol: str = "SPY",
           window: str = "1w") -> pd.DataFrame:
    """Step 6's table in the shape it was asked for, for one symbol."""
    subset = frame[(frame["symbol"] == symbol) & (frame["window"] == window)]
    rows = []
    for cutoff, group in subset.groupby("cutoff"):
        indexed = group.set_index("system")

        def read(system: str, field: str, default=None):
            return indexed.loc[system, field] if system in indexed.index else default

        actual = read("consensus", "actual_direction")
        row = {
            "test date": cutoff,
            "price then": round(float(read("consensus", "start_price") or 0), 2),
            "actual %": round(float(read("consensus", "actual_return_pct") or 0), 2),
            "actual direction": {1: "UP", -1: "DOWN", 0: "flat"}.get(actual, "—"),
        }
        for system, name in [("consensus", "forecast"), ("agent_combined", "agent"),
                             ("model_lstm", "LSTM")]:
            direction = read(system, "predicted_direction")
            correct = read(system, "correct")
            row[f"{name} call"] = (read(system, "action") if system != "model_lstm"
                                   else ("UP" if direction == 1 else "DOWN"
                                         if direction == -1 else "-"))
            # A HOLD can still carry a signed score. The lean column is what
            # `correct` is scored against, so showing the action alone would
            # make a "HOLD ... yes" row look like a contradiction.
            row[f"{name} lean"] = {1: "up", -1: "down", 0: "none"}.get(direction, "-")
            row[f"{name} ok"] = ("-" if correct is None or correct != correct
                                 else "yes" if correct == 1 else "no")
        rows.append(row)
    return pd.DataFrame(rows)


def regimes(frame: pd.DataFrame, system: str, window: str = "1w") -> pd.DataFrame:
    """Accuracy split by what the market did over the same window (Step 8)."""
    subset = frame[(frame["system"] == system) & (frame["window"] == window)]
    subset = subset.dropna(subset=["correct", "benchmark_return_pct"])
    if subset.empty:
        return pd.DataFrame()
    regime = pd.cut(subset["benchmark_return_pct"], bins=[-100, -1, 1, 100],
                    labels=["market fell >1%", "market flat", "market rose >1%"])
    rows = []
    for name, group in subset.groupby(regime, observed=True):
        est = metrics.accuracy(group["correct"], group["cutoff"])
        rows.append({
            "regime": name,
            "n": len(group),
            "accuracy %": round(est.value, 1),
            "bullish calls %": round(float((group["predicted_direction"] > 0).mean() * 100), 1),
            "mean return %": round(float(group["directional_return_pct"].mean()), 2),
        })
    return pd.DataFrame(rows)


def horizon_grid(frame: pd.DataFrame, systems: list[str]) -> pd.DataFrame:
    """Accuracy of each system at every window, native or not.

    The off-diagonal entries are the honest answer to "how did the six-month
    prediction do": there wasn't one, and here is what happens if you hold a
    one-week call for six months anyway.
    """
    rows = []
    for system in systems:
        row: dict[str, object] = {"system": system}
        for window in list(schedule.OUTCOME_BARS) + ["4h"]:
            subset = frame[(frame["system"] == system) & (frame["window"] == window)]
            scored = subset.dropna(subset=["correct"])
            if scored.empty:
                row[window] = None
                continue
            est = metrics.accuracy(scored["correct"], scored["cutoff"])
            mark = "*" if est.significant else ""
            row[window] = f"{est.value:.0f}%{mark} ({est.n})"
        rows.append(row)
    return pd.DataFrame(rows)


def per_cutoff_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Step 6's comparison, one row per experiment."""
    rows = []
    for (cutoff, label), group in frame[frame["window"] == "1w"].groupby(
            ["cutoff", "cutoff_label"], sort=True):
        row = {"cutoff": cutoff, "label": label}
        market = group[group["symbol"] == "SPY"]["actual_return_pct"]
        row["SPY 1w %"] = round(float(market.iloc[0]), 2) if len(market) else None
        row["symbols up %"] = round(
            float((group.drop_duplicates(subset=["symbol"])["actual_direction"] > 0)
                  .mean() * 100), 0)
        for system, name in [("consensus", "consensus"),
                             ("agent_combined", "agents"),
                             ("model_lstm", "LSTM")]:
            scored = group[group["system"] == system].dropna(subset=["correct"])
            row[f"{name} n"] = len(scored)
            row[f"{name} %"] = (round(float(scored["correct"].mean() * 100), 0)
                                if len(scored) else None)
        rows.append(row)
    return pd.DataFrame(rows)


def worked_examples(frame: pd.DataFrame, n: int = 8) -> pd.DataFrame:
    """Step 7 — individual predictions, priced out from the historical date."""
    subset = frame[(frame["system"] == "consensus") & (frame["window"] == "1w")
                   & frame["actionable"]].dropna(subset=["correct"])
    subset = subset.sort_values("confidence", ascending=False).head(n)
    return pd.DataFrame([{
        "cutoff": r["cutoff"],
        "symbol": r["symbol"],
        "call": r["action"],
        "confidence %": round(r["confidence"], 0),
        "price then": round(r["start_price"], 2),
        "target": round(r["predicted_price"], 2) if r["predicted_price"] else None,
        "predicted %": round(r["predicted_return_pct"], 2) if r["predicted_return_pct"] else None,
        "actual price": round(r["actual_price"], 2),
        "actual %": round(r["actual_return_pct"], 2),
        "direction": "CORRECT" if r["correct"] == 1 else "WRONG",
        "target error pts": (round(r["predicted_return_pct"] - r["actual_return_pct"], 2)
                             if r["predicted_return_pct"] is not None else None),
    } for _, r in subset.iterrows()])


# ----------------------------------------------------------------------- main


def show(title: str, table) -> None:
    print(f"\n### {title}")
    if isinstance(table, pd.DataFrame):
        print(table.to_string(index=False) if len(table) else "  (nothing to report)")
    else:
        print(json.dumps(table, indent=2, default=str))


def main() -> None:
    predictions = json.loads((pit.OUT_DIR / "predictions.json").read_text(encoding="utf-8"))
    model_path = pit.OUT_DIR / "model.jsonl"
    models = [json.loads(line) for line in
              model_path.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if model_path.exists() else []

    revealed = outcomes.build(predictions)
    frame = attach_outcomes(collect_calls(predictions, models), revealed)
    frame.to_csv(pit.OUT_DIR / "calls.csv", index=False)

    consensus_systems = ["consensus", "consensus_4h", "consensus_1d", "consensus_1w"]
    agent_systems = ["agent_turtle", "agent_crossover", "agent_rolling", "agent_combined"]
    model_systems = ["model_lstm", "consensus_with_model"]
    everything = consensus_systems + agent_systems + model_systems

    print("=" * 100)
    print("POINT-IN-TIME VALIDATION")
    print("=" * 100)
    print(f"predictions frozen : {predictions['generated_at']}")
    print(f"last bar available : {predictions['as_of_last_bar']}")
    print(f"cutoffs            : {len(predictions['cutoffs'])}")
    print(f"symbols            : {len(predictions['symbols'])}")
    print(f"frozen predictions : {len(predictions['predictions'])}")
    print(f"LSTM experiments   : {len(models)}")
    print(f"scored rows        : {len(frame):,}")

    show("Coverage of the outcome windows",
         frame.drop_duplicates(subset=["cutoff", "symbol", "window"])
              .groupby("window").size().rename("symbol-dates scoreable")
              .reset_index())

    show("HEADLINE — every system at its own horizon (Step 9)",
         headline(frame, everything))

    show("Directional accuracy at each system's own horizon — every bar it leaned",
         directional_table(frame, everything))
    show("Directional accuracy — only bars it actually told you to act on",
         directional_table(frame, everything, actioned_only=True, label="acted"))
    show("Baseline directions, for reference",
         directional_table(frame, [f"baseline_{b}" for b in BASELINES], window="1w"))
    show("Against always-predicting-up, on identical rows (the decisive test)",
         versus_long(frame, everything))

    show("Every system at every window (accuracy, n) — * = p < 0.05 clustered",
         horizon_grid(frame, everything + [f"baseline_{b}" for b in BASELINES]))

    for system in ["consensus", "agent_combined", "model_lstm", "consensus_with_model"]:
        show(f"{system} vs the trivial rules (paired, 1-week window)",
             baseline_comparison(frame, system))

    show("Confidence calibration — consensus, 1 week", confidence_calibration(frame, "consensus"))
    show("Confidence calibration — consensus 1d horizon at 1 day",
         confidence_calibration(frame, "consensus_1d", window="1d"))
    show("Signal strength — consensus, 1 week", signal_strength(frame, "consensus"))
    show("Signal strength — consensus 1d horizon at 1 day",
         signal_strength(frame, "consensus_1d", window="1d"))

    show("Price-target error, at each system's own horizon",
         price_error(frame, consensus_systems + ["model_lstm"]))
    show("Return-prediction error, at each system's own horizon",
         return_error(frame, consensus_systems + ["model_lstm"]))
    show("Return-prediction error — only bars where a direction was named",
         return_error(frame, consensus_systems + ["model_lstm"], leaning_only=True))

    show("The money view — taking the call vs staying long, same rows (1 week)",
         money(frame, everything))
    show("The money view at 1 month", money(frame, everything, window="1m"))

    show("Does one part add anything to another? (paired, 1-week window)",
         pd.concat([adds_value(frame, "consensus", "agent_combined"),
                    adds_value(frame, "consensus", "agent_crossover"),
                    adds_value(frame, "consensus_with_model", "consensus"),
                    adds_value(frame, "model_lstm", "consensus")],
                   ignore_index=True))

    show("What the neural forecast changed once folded in", model_influence(frame, models))
    show("Caveat on the 4-hour window: how much of it is the overnight gap",
         gap_confound())

    show("Accuracy by market regime — consensus", regimes(frame, "consensus"))
    show("Accuracy by market regime — agent_combined", regimes(frame, "agent_combined"))

    show("Per-experiment comparison (Step 6)", per_cutoff_table(frame))
    show("SPY ledger, one row per test date (Step 6, requested shape)",
         ledger(frame, "SPY"))
    show("Worked examples — the eight most confident actionable calls (Step 7)",
         worked_examples(frame))

    for system in ["consensus", "agent_combined", "model_lstm"]:
        show(f"Systematic errors — {system}", systematic(frame, system))

    print(f"\nWrote {pit.OUT_DIR / 'calls.csv'}")


if __name__ == "__main__":
    main()
