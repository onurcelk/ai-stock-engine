"""The V2.1 evaluation protocol: the fixed benchmark hierarchy and the nine gates.

`V2_1_PREREGISTRATION.md` §3-4 in code. Two things distinguish it from V2's
`walkforward.Evaluation.criteria`, which is left untouched because it records a
finished experiment:

**The benchmark is not selected.** V2 chose its baseline as the simple factor
with the largest |mean development IC|, which is a rule that maximises in-sample
effect size — and duly picked 5-day reversal, the factor that led on development
and reverted on the exam, while 12-1 momentum beat the model out of sample.
Here the hierarchy is fixed in advance: 12-1 momentum at sign +1 from economic
prior, 5-day reversal at the sign V2 froze, and a regime-switched combination
that is reported but gates nothing.

**The gates test stability, cost and both benchmarks.** V2's criteria 2 and 4
were the same number, so criterion 4 could not fail on its own; its regime check
gated on buckets holding one or two cutoffs; and its cost fields were reserved
and never populated. Criterion 4 now also requires the sign to hold across both
halves of the exam, criterion 7 gates only on buckets with enough cutoffs to
mean something, and criterion 9 charges the book for trading.

Nothing here reads the exam set or decides which arm is evaluated. It takes a
prediction series and a panel and computes numbers. Which prediction series
reaches it is `alpha.develop`'s decision, frozen before the exam is opened.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import models, stats, walkforward

# --- §4 thresholds. Criteria 1, 2, 3 and 8 carry their V2 numbers unchanged.
THRESHOLD_MEAN_IC = 0.03
THRESHOLD_HIT_RATE = 0.55
THRESHOLD_SIGN_STABILITY = 0.60
THRESHOLD_MIN_CUTOFFS = 50
MIN_REGIME_CUTOFFS = 8              # §4.1 — a bucket smaller than this is reported, not gated

# --- §4.1 cost model. One-way, in basis points, charged on measured turnover.
COST_BPS = 5.0
COST_SENSITIVITY_BPS = (5.0, 10.0, 20.0)
QUINTILE = 0.2

# --- §5 intervals. The pre-registered figure is block 4; the rest are the
# --- sensitivity that makes the choice visible rather than load-bearing.
BLOCK_SENSITIVITY = (1, 2, 4, 8)


# ----------------------------------------------------------------------
# §3 — the benchmark hierarchy. Fixed, ordered, and not chosen from data.
# ----------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Benchmark:
    key: str
    label: str
    factor: str
    sign: int
    gate: bool
    provenance: str


BENCHMARKS = (
    Benchmark("b1_momentum_12_1", "12-1 momentum", "mom_12_1", +1, True,
              "sign +1 by economic prior; not estimated from any data"),
    Benchmark("b2_reversal_5d", "5-day reversal", "mom_5d", -1, True,
              "sign -1 as frozen on V2's development set (out/development.json); "
              "not re-estimated. Disclosed in §2.6: that development set includes "
              "dates now in the V2.1 exam, which favours the benchmark and so "
              "raises the model's bar rather than lowering it"),
    Benchmark("b3_regime_switched", "regime-switched momentum", "", 0, False,
              "mom_12_1 in BULL_TREND/SIDEWAYS, -mom_5d in BEAR_TREND, switched on "
              "the pre-cutoff regime tag; nothing fitted. Reported, never a gate"),
)

BEAR = "BEAR_TREND"


def benchmark_scores(frame: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    """One prediction column per benchmark, on the same (cutoff, symbol) index.

    Feature-side only: each column is a within-cutoff percentile of a pre-cutoff
    return, times a sign that was fixed before any of this ran.
    """
    ranks = models.simple_factor_scores(frame)
    out: dict[str, pd.Series] = {}

    for benchmark in BENCHMARKS:
        if benchmark.key == "b3_regime_switched":
            continue
        if benchmark.factor not in ranks.columns:
            continue
        out[benchmark.key] = ranks[benchmark.factor] * benchmark.sign

    if {"mom_12_1", "mom_5d"} <= set(ranks.columns):
        trend = _trend_by_row(frame, regimes)
        out["b3_regime_switched"] = ranks["mom_12_1"].where(
            trend != BEAR, -ranks["mom_5d"])

    return pd.DataFrame(out, index=frame.index)


def _trend_by_row(frame: pd.DataFrame, regimes: pd.DataFrame) -> pd.Series:
    """Broadcast the per-cutoff trend tag across the cross-section."""
    if regimes is None or not len(regimes) or "trend" not in regimes.columns:
        return pd.Series("", index=frame.index, dtype=object)
    tags = regimes["trend"].reindex(frame.index.get_level_values(0))
    return pd.Series(tags.to_numpy(), index=frame.index, dtype=object)


# ----------------------------------------------------------------------
# §4.1 — turnover and the cost adjustment
# ----------------------------------------------------------------------

def leg_membership(frame: pd.DataFrame, prediction: str,
                   fraction: float = QUINTILE) -> dict[pd.Timestamp, tuple[set, set]]:
    """The names in the long and short legs at each cutoff, in prediction order."""
    out: dict[pd.Timestamp, tuple[set, set]] = {}
    for cutoff, block in frame.groupby(level=0):
        clean = block[[prediction]].dropna()
        count = int(len(clean) * fraction)
        if count < 3:
            continue
        ordered = clean.sort_values(prediction)
        names = ordered.index.get_level_values(1)
        out[cutoff] = (set(names[-count:]), set(names[:count]))
    return out


def turnover(frame: pd.DataFrame, prediction: str,
             fraction: float = QUINTILE) -> pd.DataFrame:
    """Per-cutoff share of each leg replaced since the previous scored cutoff.

    The first scored cutoff has nothing to compare against, so it is charged
    full turnover — the book has to be built. Names that leave the eligible
    cross-section between cutoffs count as turnover, which overstates it
    slightly; that error runs against the model and is left in.
    """
    legs = leg_membership(frame, prediction, fraction)
    rows = []
    previous: tuple[set, set] | None = None
    for cutoff in sorted(legs):
        long_now, short_now = legs[cutoff]
        if previous is None:
            long_turn = short_turn = 1.0
        else:
            long_turn = len(long_now - previous[0]) / max(len(long_now), 1)
            short_turn = len(short_now - previous[1]) / max(len(short_now), 1)
        rows.append({"cutoff": cutoff, "turnover_long": long_turn,
                     "turnover_short": short_turn,
                     "turnover_total": long_turn + short_turn})
        previous = (long_now, short_now)
    if not rows:
        return pd.DataFrame(columns=["turnover_long", "turnover_short", "turnover_total"])
    return pd.DataFrame(rows).set_index("cutoff")


def net_spread(spread: pd.Series, turnover_total: pd.Series,
               bps: float = COST_BPS) -> pd.Series:
    """Gross quintile spread less `turnover x cost`, per cutoff (§4.1)."""
    cost = turnover_total.reindex(spread.index).fillna(2.0) * (bps / 10_000.0)
    return spread - cost


# ----------------------------------------------------------------------
# §4 — the assessment
# ----------------------------------------------------------------------

@dataclasses.dataclass
class Assessment:
    """One arm's numbers under the V2.1 protocol, and the nine gates over them."""

    name: str
    evaluation: walkforward.Evaluation
    versus: dict[str, stats.Series]         # benchmark key -> paired IC difference
    benchmark_ic: dict[str, stats.Series]
    turnover: pd.DataFrame
    net: stats.Series
    halves: dict[str, dict]

    # ---------------------------------------------------------------- gates

    def criteria(self) -> dict[str, dict]:
        ic = self.evaluation.ic
        spread = self.evaluation.spread
        ic_low, ic_high = ic.bootstrap_ci()
        spread_low, spread_high = spread.bootstrap_ci()
        hit = stats.Series(f"{self.name} IC>0", (ic.clean > 0).astype(float), null=0.5)
        hit_low, hit_high = hit.bootstrap_ci()
        net_low, net_high = self.net.bootstrap_ci()

        out = {
            "1_mean_ic": {
                "value": _round(ic.mean, 5), "threshold": f"> {THRESHOLD_MEAN_IC}, CI excludes 0",
                "ci": [_round(ic_low, 5), _round(ic_high, 5)], "gate": True,
                "passed": bool(ic.mean > THRESHOLD_MEAN_IC and ic_low > 0)},
            "2_ic_hit_rate": {
                "value": _round(ic.hit_rate, 4),
                "threshold": f"> {THRESHOLD_HIT_RATE}, CI excludes 0.5",
                "ci": [_round(hit_low, 4), _round(hit_high, 4)], "gate": True,
                "passed": bool(ic.hit_rate > THRESHOLD_HIT_RATE and hit_low > 0.5)},
            "3_top_minus_bottom": {
                "value": _round(spread.mean, 5), "threshold": "> 0, CI excludes 0",
                "ci": [_round(spread_low, 5), _round(spread_high, 5)], "gate": True,
                "passed": bool(spread.mean > 0 and spread_low > 0)},
            "4_sign_stability": self._sign_stability(),
            "7_no_regime_collapse": self._regime_gate(),
            "8_effective_sample": {
                "value": ic.n, "threshold": f">= {THRESHOLD_MIN_CUTOFFS} independent cutoffs",
                "gate": True, "passed": bool(ic.n >= THRESHOLD_MIN_CUTOFFS)},
            "9_cost_adjusted_spread": {
                "value": _round(self.net.mean, 5),
                "threshold": f"> 0 at {COST_BPS:g} bps one-way, CI excludes 0",
                "ci": [_round(net_low, 5), _round(net_high, 5)], "gate": True,
                "passed": bool(self.net.n and self.net.mean > 0 and net_low > 0)},
            "10_turnover": {
                "value": self.turnover_summary(), "threshold": "reported", "gate": False,
                "passed": True},
            "11_cost_sensitivity": {
                "value": self.cost_sensitivity(), "threshold": "reported", "gate": False,
                "passed": True},
            "12_independent_cutoffs": {
                "value": ic.n, "threshold": "reported", "gate": False, "passed": True},
        }
        out.update(self._benchmark_gates())
        return dict(sorted(out.items(), key=_criterion_order))

    def _sign_stability(self) -> dict:
        """§4.1: hit rate AND a positive mean in both chronological halves."""
        ic = self.evaluation.ic
        first, second = self.halves["first"], self.halves["second"]
        rate_ok = bool(ic.hit_rate >= THRESHOLD_SIGN_STABILITY)
        halves_ok = bool(first["n"] and second["n"]
                         and first["mean_ic"] > 0 and second["mean_ic"] > 0)
        return {
            "value": {"hit_rate": _round(ic.hit_rate, 4),
                      "first_half_mean_ic": _round(first["mean_ic"], 5),
                      "second_half_mean_ic": _round(second["mean_ic"], 5)},
            "threshold": (f"IC > 0 in >= {THRESHOLD_SIGN_STABILITY:.0%} of cutoffs "
                          "AND mean IC > 0 in both halves"),
            "gate": True, "passed": rate_ok and halves_ok}

    def _regime_gate(self) -> dict:
        """§4.1: gate on buckets with enough cutoffs; report the rest."""
        table = self.evaluation.regime_ic
        gating, reported = {}, {}
        for regime, row in table.iterrows():
            entry = {"n_cutoffs": int(row["n_cutoffs"]), "mean_ic": _round(row["mean_ic"], 5)}
            if int(row["n_cutoffs"]) >= MIN_REGIME_CUTOFFS:
                gating[str(regime)] = entry
            else:
                reported[str(regime)] = entry
        passed = bool(gating) and all(
            v["mean_ic"] is not None and v["mean_ic"] > 0 for v in gating.values())
        return {
            "value": {"gating": gating, "below_minimum_reported_only": reported},
            "threshold": f"mean IC > 0 in every bucket with >= {MIN_REGIME_CUTOFFS} cutoffs",
            "gate": True, "passed": passed}

    def _benchmark_gates(self) -> dict[str, dict]:
        """Criteria 5 and 6 — beat both gating benchmarks; report the third."""
        out = {}
        numbering = {"b1_momentum_12_1": "5_beats_12_1_momentum",
                     "b2_reversal_5d": "6_beats_5d_reversal",
                     "b3_regime_switched": "12b_versus_regime_switched"}
        for benchmark in BENCHMARKS:
            series = self.versus.get(benchmark.key)
            key = numbering[benchmark.key]
            if series is None or not series.n:
                out[key] = {"value": None, "threshold": "> 0, CI excludes 0",
                            "gate": benchmark.gate, "passed": not benchmark.gate,
                            "note": f"no paired cutoffs against {benchmark.label}"}
                continue
            low, high = series.bootstrap_ci()
            out[key] = {
                "value": _round(series.mean, 5),
                "benchmark": benchmark.label,
                "benchmark_mean_ic": _round(self.benchmark_ic[benchmark.key].mean, 5),
                "threshold": "> 0, CI excludes 0" if benchmark.gate else "reported",
                "ci": [_round(low, 5), _round(high, 5)],
                "gate": benchmark.gate,
                "passed": (bool(series.mean > 0 and low > 0) if benchmark.gate else True)}
        return out

    # --------------------------------------------------------------- reports

    def turnover_summary(self) -> dict:
        if self.turnover.empty:
            return {}
        return {"mean_long": _round(float(self.turnover["turnover_long"].mean()), 4),
                "mean_short": _round(float(self.turnover["turnover_short"].mean()), 4),
                "mean_total": _round(float(self.turnover["turnover_total"].mean()), 4),
                "n_cutoffs": int(len(self.turnover))}

    def cost_sensitivity(self) -> dict:
        """§4.1 criterion 11 — net spread at 5, 10 and 20 bps one-way."""
        spread = self.evaluation.per_cutoff["spread"]
        total = (self.turnover["turnover_total"] if not self.turnover.empty
                 else pd.Series(dtype=float))
        out = {}
        for bps in COST_SENSITIVITY_BPS:
            series = stats.Series(f"{self.name} net spread @{bps:g}bps",
                                  net_spread(spread, total, bps), null=0.0)
            low, high = series.bootstrap_ci()
            out[f"{bps:g}bps"] = {"mean": _round(series.mean, 5),
                                  "ci": [_round(low, 5), _round(high, 5)],
                                  "excludes_zero": bool(series.excludes_null())}
        return out

    def interval_sensitivity(self) -> dict:
        """§5 — the same mean IC under four bootstrap block lengths."""
        values = self.evaluation.ic.clean.to_numpy(dtype=float)
        out = {}
        for block in BLOCK_SENSITIVITY:
            low, high = stats.block_bootstrap_ci(values, block=block)
            out[f"block_{block}"] = [_round(low, 5), _round(high, 5)]
        out["newey_west_se"] = _round(self.evaluation.ic.newey_west_se, 5)
        out["naive_se"] = _round(self.evaluation.ic.naive_se, 5)
        return out

    def verdict(self) -> tuple[bool, list[str]]:
        criteria = self.criteria()
        failed = [k for k, v in criteria.items() if v.get("gate") and not v["passed"]]
        return (not failed), failed

    def record(self) -> dict:
        criteria = self.criteria()
        passed, failed = self.verdict()
        return {
            "protocol": "V2.1",
            "arm": self.name,
            "n_cutoffs": self.evaluation.ic.n,
            "ic": self.evaluation.ic.row(),
            "spread": self.evaluation.spread.row(),
            "top_quintile": self.evaluation.top.row(),
            "bottom_quintile": self.evaluation.bottom.row(),
            "net_spread": self.net.row(),
            "benchmarks": {k: v.row() for k, v in self.benchmark_ic.items()},
            "versus_benchmarks": {k: v.row() for k, v in self.versus.items()},
            "regime_ic": self.evaluation.regime_ic.to_dict(orient="index"),
            "halves": self.halves,
            "interval_sensitivity": self.interval_sensitivity(),
            "criteria": criteria,
            "gates_passed": bool(passed),
            "failed_gates": failed,
            "production_weight": 0.0,
            "production_weight_note": (
                "Weight stays 0 until every gate passes on the frozen V2.1 exam set "
                "under this protocol with the Holm-Bonferroni correction applied "
                "across the arms run. This field is not a result."),
        }


def _criterion_order(item: tuple[str, dict]) -> tuple[int, str]:
    """Sort 1, 2, ... 12 numerically rather than lexically."""
    head = item[0].split("_", 1)[0]
    digits = "".join(c for c in head if c.isdigit())
    return (int(digits) if digits else 99, item[0])


def _round(value, places: int):
    if value is None:
        return None
    value = float(value)
    return None if not np.isfinite(value) else round(value, places)


def _halves(ic: pd.Series) -> dict[str, dict]:
    """Chronological split of the scored cutoffs — criterion 4's second half."""
    clean = ic.dropna().sort_index()
    middle = (len(clean) + 1) // 2
    out = {}
    for label, block in (("first", clean.iloc[:middle]), ("second", clean.iloc[middle:])):
        out[label] = {
            "n": int(len(block)),
            "mean_ic": _round(block.mean(), 5) if len(block) else None,
            "hit_rate": _round((block > 0).mean(), 4) if len(block) else None,
            "from": str(pd.Timestamp(block.index[0]).date()) if len(block) else None,
            "to": str(pd.Timestamp(block.index[-1]).date()) if len(block) else None,
        }
    return out


def assess(panel, predictions: pd.Series, name: str,
           target: str = "alpha_5d") -> Assessment:
    """Score one arm's predictions under the V2.1 protocol.

    `panel` must already be sliced to the cutoffs being scored. Which cutoffs
    those are is the caller's decision and is deliberately not made here — this
    function has no idea whether it is looking at development or at the exam.
    """
    evaluation = walkforward.evaluate(panel, predictions, name, target=target)

    scored = evaluation.ic.clean.index
    frame = panel.frame[panel.frame.index.get_level_values(0).isin(pd.DatetimeIndex(scored))]
    scores = benchmark_scores(frame, panel.regimes)

    benchmark_ic: dict[str, stats.Series] = {}
    versus: dict[str, stats.Series] = {}
    for benchmark in BENCHMARKS:
        if benchmark.key not in scores.columns:
            continue
        block = frame[[target]].copy()
        block["prediction"] = scores[benchmark.key]
        series = stats.ic_by_cutoff(block, "prediction", target)
        benchmark_ic[benchmark.key] = stats.Series(benchmark.label, series, null=0.0)
        versus[benchmark.key] = stats.paired_difference(
            evaluation.ic.clean, series, f"{name} IC - {benchmark.label} IC")

    marks = frame.copy()
    marks["prediction"] = predictions.reindex(marks.index)
    turns = turnover(marks[marks["prediction"].notna()], "prediction")
    net = stats.Series(f"{name} net spread @{COST_BPS:g}bps",
                       net_spread(evaluation.per_cutoff["spread"],
                                  turns["turnover_total"] if not turns.empty
                                  else pd.Series(dtype=float)),
                       null=0.0)

    return Assessment(name=name, evaluation=evaluation, versus=versus,
                      benchmark_ic=benchmark_ic, turnover=turns, net=net,
                      halves=_halves(evaluation.ic.clean))
