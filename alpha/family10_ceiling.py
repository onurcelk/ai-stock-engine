"""Family 10 Stage 2: the §2.10 clause-3 correlation ceiling for the event dummy.

**FEATURE-vs-FEATURE ONLY. The target is never read in this module**, and the
assertion that enforces it is in the code rather than in this docstring: the
panel's outcome columns are dropped by name before anything is computed, and
`_feature_frame` raises if one survives.

The question clause 3 exists to ask:

> Is this family merely rediscovering price, momentum or B3 information that was
> already in the panel *before* the event?

Thresholds, carried unchanged from `alpha/V3_PREREGISTRATION.md` §2.1 and
`alpha/V3_FAMILY2_PREREGISTRATION.md` §8 — the same numbers Family 1 and Family
2 were judged against, and fixed long before this family existed:

```
vs z__ret_12_1          mean|rho|  <=  0.30
vs each 34-set column   mean|rho|  <=  0.50
```

B3 is not in the 34-column set. It is `b3_regime_switched`, which *is*
regime-switched 12-1 momentum, so it is held to the **momentum** ceiling of
0.30 rather than the looser input ceiling. That is the strictest available
reading and it is chosen before the number is seen.

**The representation.** The cutoff grid is spaced `HORIZON` sessions apart, so
the sessions partition exactly: every session belongs to one cutoff's window.

```
adverse_8k_event(T, symbol) = 1  iff the issuer had an eligible adverse event
                                    whose information session falls in the
                                    HORIZON sessions ending at T
```

Nothing about that mapping can see past *T*: the information session is already
the first session on which `alpha/filings.py`'s door opens, so a dummy set at
*T* is set from facts accepted before *T*'s close.

**On sparsity, stated before the numbers.** The dummy is binary and rare —
roughly five names in a ~450-name cross-section. A Spearman correlation between
a 1%-prevalence indicator and a continuous feature is **bounded well below 1 by
construction**, so a small value is partly mechanical and cannot on its own be
read as evidence of independence. The charter's metric decides the gate because
the charter's metric is what was frozen; alongside it this module reports the
**rank-biserial correlation** (equivalently 2·AUC−1) of each feature's
within-cutoff percentile rank between event and non-event names. That statistic
is a location shift and is *not* attenuated by prevalence, so it can only make
the family look **more** dependent, never less. It is a disclosure, not a
substitute, and it is reported whichever way it comes out.

Run:  python -m alpha.family10_ceiling
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import pickle

import numpy as np
import pandas as pd

from . import carrier, examset, family10_panel, protocol
from . import singlename_config as cfg

PANEL_PKL = cfg.OUT_DIR / "panel.pkl"
DEVELOPMENT_JSON = cfg.OUT_DIR / "v2_3_development.json"
EVENTS = cfg.OUT_DIR / "family10_events.parquet"
OUT_PATH = cfg.OUT_DIR / "family10_ceiling.json"

#: Frozen in V3_PREREGISTRATION.md §2.1 before Family 1 ran. Not adjustable here.
CEILING_MOMENTUM = 0.30
CEILING_INPUT = 0.50

MIN_CROSS_SECTION = 50          # same minimum as v3_build_insider.per_cutoff_spearman

#: Every column in `panel.pkl` that is or is derived from a forward outcome.
#: Dropped by name, and their absence asserted, so this module cannot read one
#: even by accident.
OUTCOME_COLUMNS = ("asset_return", "spy_return", "sector_return", "alpha_5d",
                   "sector_relative", "residual_alpha", "target_train",
                   "target_rank", "target_vol_scaled", "quintile", "horizon_end")


def _feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """The panel with every outcome column removed, and proof that none remain."""
    kept = frame.drop(columns=[c for c in OUTCOME_COLUMNS if c in frame.columns])
    leaked = [c for c in OUTCOME_COLUMNS if c in kept.columns]
    if leaked:
        raise RuntimeError(f"outcome columns reached the ceiling stage: {leaked}")
    return kept


def event_dummy(events: pd.DataFrame, cutoffs: list[pd.Timestamp],
                calendar: pd.DatetimeIndex, index: pd.MultiIndex,
                horizon: int = family10_panel.HORIZON) -> pd.Series:
    """`adverse_8k_event` on the panel's own (cutoff, symbol) index.

    Each event's information session is assigned to the first cutoff at or after
    it that is within `horizon` sessions — which, on a grid spaced `horizon`
    apart, is exactly the cutoff whose window contains the session. An event in
    the run-up to a cutoff that is not on the grid (the exam neighbourhood, the
    warm-up) simply has no home and is dropped; the count is reported.
    """
    grid = pd.DatetimeIndex(sorted(cutoffs))
    grid_position = calendar.searchsorted(grid, side="left")
    session_position = calendar.searchsorted(
        pd.DatetimeIndex(events["session"]), side="left")

    slot = np.searchsorted(grid_position, session_position, side="left")
    inside = slot < len(grid)
    distance = np.where(inside, grid_position[np.clip(slot, 0, len(grid) - 1)]
                        - session_position, horizon + 1)
    keep = inside & (distance < horizon)

    assigned = events.loc[keep].assign(cutoff=grid[slot[keep]])
    pairs = set()
    for row in assigned.itertuples():
        for ticker in str(row.tickers).split("|"):
            if ticker:
                pairs.add((row.cutoff, ticker))

    dummy = pd.Series(0.0, index=index, name="adverse_8k_event")
    hit = [p for p in pairs if p in dummy.index]
    dummy.loc[hit] = 1.0
    dummy.attrs["events_assigned"] = int(keep.sum())
    dummy.attrs["events_off_grid"] = int((~keep).sum())
    dummy.attrs["pairs_built"] = len(pairs)
    dummy.attrs["pairs_on_panel"] = len(hit)
    return dummy


def panel_reach(events: pd.DataFrame, cutoffs: list[pd.Timestamp],
                calendar: pd.DatetimeIndex, index: pd.MultiIndex,
                horizon: int = family10_panel.HORIZON) -> dict:
    """How many events land on a name the research panel actually carries.

    Index membership is necessary but not sufficient: `alpha/universe.py` also
    requires bars on disk, 252 sessions of history, $3M median dollar volume and
    a $3 price. A historically eligible issuer whose bars Yahoo no longer serves
    is in the membership set and *not* in the panel — `alpha/membership.py`'s
    disclosed limit 4. That gap is a second survivorship channel, and it is
    measured per item here for the same reason the first one was: a uniform loss
    costs power, a loss concentrated on the severe items costs the hypothesis.
    """
    grid = pd.DatetimeIndex(sorted(cutoffs))
    grid_position = calendar.searchsorted(grid, side="left")
    session_position = calendar.searchsorted(
        pd.DatetimeIndex(events["session"]), side="left")
    slot = np.searchsorted(grid_position, session_position, side="left")
    inside = slot < len(grid)
    distance = np.where(inside, grid_position[np.clip(slot, 0, len(grid) - 1)]
                        - session_position, horizon + 1)
    keep = inside & (distance < horizon)

    assigned = events.loc[keep].assign(cutoff=grid[slot[keep]])
    cells = set(index)
    on_panel = [any((row.cutoff, ticker) in cells
                    for ticker in str(row.tickers).split("|") if ticker)
                for row in assigned.itertuples()]
    assigned = assigned.assign(on_panel=on_panel)

    per_item = {}
    for code in family10_panel.ADVERSE_ITEMS:
        mask = assigned["items"].str.split(",").map(lambda v: code in v)
        total = int(mask.sum())
        reached = int((mask & assigned["on_panel"]).sum())
        per_item[code] = {"assigned": total, "on_panel": reached,
                          "lost_share": round(1 - reached / total, 4) if total else None}

    return {"events_total": int(len(events)),
            "assigned_to_a_development_cutoff": int(keep.sum()),
            "off_grid": int((~keep).sum()),
            "on_panel": int(assigned["on_panel"].sum()),
            "off_panel": int((~assigned["on_panel"]).sum()),
            "reach_share": round(float(assigned["on_panel"].mean()), 4),
            "by_item": per_item,
            "top_off_panel_symbols": assigned.loc[~assigned["on_panel"], "ticker"]
                                    .value_counts().head(10).to_dict()}


def per_cutoff_spearman(x: pd.Series, y: pd.Series,
                        minimum: int = MIN_CROSS_SECTION) -> pd.Series:
    """The charter's metric, identical to `v3_build_insider.per_cutoff_spearman`."""
    out = []
    for _, group in pd.DataFrame({"x": x, "y": y}).groupby(level="cutoff"):
        group = group.dropna()
        if (len(group) >= minimum and group["x"].nunique() > 1
                and group["y"].nunique() > 1):
            out.append(group["x"].rank().corr(group["y"].rank()))
    return pd.Series(out, dtype=float)


def rank_biserial(dummy: pd.Series, feature: pd.Series) -> dict:
    """2·AUC−1 between event and non-event names, pooled over cutoffs.

    Computed on each feature's **within-cutoff percentile rank**, so a cutoff
    with a market-wide move cannot masquerade as an event effect. Unlike a
    correlation, this is a location shift: it answers "where in the
    cross-section do event names sit?" and its scale does not shrink as events
    get rarer. Reported because a near-zero Spearman on a 1%-prevalence dummy is
    partly an artefact of the prevalence, and the pilot may not bank on that.
    """
    frame = pd.DataFrame({"d": dummy, "f": feature}).dropna()
    ranked = frame.groupby(level="cutoff")["f"].rank(pct=True)
    treated, control = ranked[frame["d"] > 0], ranked[frame["d"] == 0]
    if treated.empty or control.empty:
        return {"n_event": int(len(treated)), "auc": float("nan"),
                "rank_biserial": float("nan"), "mean_percentile_event": float("nan"),
                "mean_percentile_other": float("nan")}
    # Mean percentile of the treated group *is* the AUC when the control group
    # spans the unit interval uniformly, which within-cutoff pct ranks do.
    auc = float(treated.mean())
    return {"n_event": int(len(treated)), "n_other": int(len(control)),
            "auc": round(auc, 4), "rank_biserial": round(2 * auc - 1, 4),
            "mean_percentile_event": round(float(treated.mean()), 4),
            "mean_percentile_other": round(float(control.mean()), 4)}


def summarise(rho: pd.Series) -> dict:
    if rho.empty:
        return {"n_cutoffs": 0, "mean_rho": float("nan"),
                "mean_abs_rho": float("nan"), "p95_abs_rho": float("nan"),
                "max_abs_rho": float("nan")}
    return {"n_cutoffs": int(len(rho)), "mean_rho": round(float(rho.mean()), 4),
            "mean_abs_rho": round(float(rho.abs().mean()), 4),
            "p95_abs_rho": round(float(rho.abs().quantile(0.95)), 4),
            "max_abs_rho": round(float(rho.abs().max()), 4)}


def main() -> int:
    from . import pitdata

    panel = pickle.load(open(PANEL_PKL, "rb"))
    frame = _feature_frame(panel["frame"])

    # The split is the V2.1 sealed one, taken from `examset` — **not**
    # `panel["development"]`, which is the older V1 twelve-date split and does
    # not exclude the 72 sealed cutoffs. `v3_build_insider` asserts the same
    # thing for the same reason; a first pass of this module used the panel's
    # key and measured on 484 cutoffs, 72 of which were the exam's.
    sealed = examset.load()
    development = [pd.Timestamp(c) for c in sealed.development]
    exam = {pd.Timestamp(c) for c in sealed.cutoffs}
    assert not (set(development) & exam), "exam contamination in the development set"

    calendar = pitdata.load_calendar().calendar
    events = pd.read_parquet(EVENTS)

    dev_frame = frame.loc[frame.index.get_level_values("cutoff").isin(development)]
    columns = json.load(open(DEVELOPMENT_JSON, encoding="utf-8"))["input_columns"]
    assert "z__ret_12_1" not in columns, "12-1 must be measured separately"

    needed = ["ret_12_1"] + [c[len(carrier.RANK_PREFIX):] for c in columns
                             if c.startswith(carrier.RANK_PREFIX)]
    dev_frame, _ = carrier.add_rank_columns(dev_frame, tuple(dict.fromkeys(needed)))
    missing = [c for c in columns if c not in dev_frame.columns]
    assert not missing, f"34-column set incomplete: {missing}"

    benchmarks = protocol.benchmark_scores(dev_frame, panel["regimes"])
    dev_frame = dev_frame.assign(b3_rank=benchmarks["b3_regime_switched"]
                                 .groupby(level=0).rank(pct=True, na_option="keep"))

    dummy = event_dummy(events, development, calendar, dev_frame.index)
    contaminated = [c for c in dummy.index.get_level_values("cutoff").unique()
                    if c in exam]
    assert not contaminated, "exam cutoffs reached the clause-3 frame"
    print(f"exam contamination: {len(contaminated)} cutoffs (must be 0); "
          f"sealed digest {sealed.digest[:16]}… never opened")

    reach = panel_reach(events, development, calendar, dev_frame.index)
    per_cutoff = dummy.groupby(level="cutoff").sum()
    prevalence = dummy.groupby(level="cutoff").mean()

    print(f"\npanel reach: {reach['events_total']:,} events -> "
          f"{reach['assigned_to_a_development_cutoff']:,} on a development "
          f"cutoff -> {reach['on_panel']:,} on a name the panel carries "
          f"({reach['reach_share']:.1%})")
    print("  loss by item: " + "  ".join(
        f"{c}:{v['lost_share']:.1%}" for c, v in reach["by_item"].items()
        if v["lost_share"] is not None))

    print("=== Family 10 Stage 2 - Section 2.10 clause 3 ===")
    print(f"development cutoffs {len(development)}  panel rows {len(dev_frame):,}")
    print(f"events assigned to a development cutoff "
          f"{dummy.attrs['events_assigned']:,}  off-grid "
          f"{dummy.attrs['events_off_grid']:,}")
    print(f"(cutoff, symbol) event cells on the panel "
          f"{int(dummy.sum()):,} of {dummy.attrs['pairs_built']:,} built")
    print(f"prevalence per cutoff: mean {prevalence.mean():.4f}  "
          f"median {prevalence.median():.4f}  max {prevalence.max():.4f}")
    print(f"event names per cutoff: mean {per_cutoff.mean():.2f}  "
          f"median {per_cutoff.median():.0f}  max {per_cutoff.max():.0f}  "
          f"cutoffs with none {int((per_cutoff == 0).sum())}")

    print(f"\nceilings, frozen in V3_PREREGISTRATION.md 2.1 before Family 1 ran:")
    print(f"  vs z__ret_12_1 and B3   mean|rho| <= {CEILING_MOMENTUM:.2f}")
    print(f"  vs each 34-set column   mean|rho| <= {CEILING_INPUT:.2f}")

    results = {}
    for name, ceiling in (("z__ret_12_1", CEILING_MOMENTUM),
                          ("b3_rank", CEILING_MOMENTUM)):
        stats = summarise(per_cutoff_spearman(dummy, dev_frame[name]))
        stats.update(ceiling=ceiling, passed=bool(stats["mean_abs_rho"] <= ceiling),
                     rank_biserial=rank_biserial(dummy, dev_frame[name]))
        results[name] = stats
        print(f"\n{name:16s} mean {stats['mean_rho']:+.4f}  "
              f"mean|rho| {stats['mean_abs_rho']:.4f}  "
              f"p95 {stats['p95_abs_rho']:.4f}  n={stats['n_cutoffs']}  -> "
              f"{'PASS' if stats['passed'] else 'BREACH'}")
        print(f"{'':16s} rank-biserial {stats['rank_biserial']['rank_biserial']:+.4f}  "
              f"(event names sit at percentile "
              f"{stats['rank_biserial']['mean_percentile_event']:.4f} vs "
              f"{stats['rank_biserial']['mean_percentile_other']:.4f})")

    rows = []
    for column in columns:
        stats = summarise(per_cutoff_spearman(dummy, dev_frame[column]))
        stats.update(column=column, biserial=rank_biserial(dummy, dev_frame[column]))
        rows.append(stats)
    rows.sort(key=lambda r: -r["mean_abs_rho"] if np.isfinite(r["mean_abs_rho"])
              else 1)
    measurable = [r for r in rows if r["n_cutoffs"] > 0]
    constant = [r["column"] for r in rows if r["n_cutoffs"] == 0]
    breaches = [r for r in measurable if r["mean_abs_rho"] > CEILING_INPUT]

    print(f"\nagainst the 34-column set: {len(measurable)} stock-level columns "
          f"measurable, {len(constant)} cutoff-constant (no within-cutoff "
          f"variance, so no cross-sectional correlation exists)")
    for row in measurable[:8]:
        print(f"  {row['column']:26s} mean|rho| {row['mean_abs_rho']:.4f}  "
              f"mean {row['mean_rho']:+.4f}  rank-biserial "
              f"{row['biserial']['rank_biserial']:+.4f}")
    worst = measurable[0] if measurable else None
    print(f"\nhighest of all measurable columns: "
          f"{worst['mean_abs_rho']:.4f} ({worst['column']}) -> "
          f"{'PASS' if not breaches else f'BREACH ({len(breaches)})'}")

    strongest = max((abs(r["biserial"]["rank_biserial"]) for r in measurable),
                    default=float("nan"))
    print(f"strongest rank-biserial anywhere in the 34-column set: {strongest:.4f}")

    verdict = (results["z__ret_12_1"]["passed"] and results["b3_rank"]["passed"]
               and not breaches)
    print(f"\nCLAUSE 3 VERDICT: {'PASS' if verdict else 'BREACH'}")

    payload = {
        "measured_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "Feature-vs-feature only. No forward return, target or outcome "
                "column was read; OUTCOME_COLUMNS are dropped and their absence "
                "asserted before any statistic is computed.",
        "development_cutoffs": len(development),
        "sealed_exam_cutoffs": len(exam),
        "exam_contamination": len(contaminated),
        "exam_digest": sealed.digest,
        "panel_rows": int(len(dev_frame)),
        "panel_reach": reach,
        "representation": "adverse_8k_event = 1 for an eligible issuer whose "
                          "information session falls in the HORIZON sessions "
                          "ending at the cutoff",
        "events_assigned": dummy.attrs["events_assigned"],
        "events_off_grid": dummy.attrs["events_off_grid"],
        "event_cells": int(dummy.sum()),
        "prevalence": {"mean": round(float(prevalence.mean()), 5),
                       "median": round(float(prevalence.median()), 5),
                       "max": round(float(prevalence.max()), 5),
                       "names_per_cutoff_mean": round(float(per_cutoff.mean()), 3),
                       "names_per_cutoff_max": int(per_cutoff.max()),
                       "cutoffs_with_no_event": int((per_cutoff == 0).sum())},
        "ceilings": {"momentum_and_b3": CEILING_MOMENTUM,
                     "input_columns": CEILING_INPUT,
                     "source": "V3_PREREGISTRATION.md 2.1 / "
                               "V3_FAMILY2_PREREGISTRATION.md 8, unchanged"},
        "momentum": results["z__ret_12_1"],
        "b3": results["b3_rank"],
        "input_columns": measurable,
        "cutoff_constant_columns": constant,
        "breaches": [r["column"] for r in breaches],
        "worst_input_column": worst,
        "strongest_rank_biserial": round(float(strongest), 4),
        "clause_3_passed": bool(verdict),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
