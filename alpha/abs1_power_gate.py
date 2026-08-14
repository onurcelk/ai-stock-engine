"""ABS-1 Gate 1 — power, computed from signal geometry alone.

Pre-registration: `alpha/V5_ABSTENTION_PREREGISTRATION.md`, frozen and committed
2026-08-14 before this file existed. This module is committed BEFORE it is run
(CLAUDE.md §3.2, §5.2).

Two-process separation (CLAUDE.md §2.2) is structural here, not advisory: this
module opens `validation/out/predictions.json` and **nothing else**. That file
holds the prediction side of the frozen PIT-1 record — no realised return, no
outcome, no bar after any cutoff. `validation/out/calls.csv` is never opened,
and the gate's verdict cannot depend on an outcome because it never sees one.

Run:  python -m alpha.abs1_power_gate
"""

from __future__ import annotations

import json
import math
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "validation" / "out" / "predictions.json"
OUT = ROOT / "alpha" / "out" / "abs1_power_gate.json"

# --------------------------------------------------------------- frozen inputs

# §3 of the pre-registration. Boundaries are read off `ultimate.FULL_BREADTH = 3`,
# which is committed code predating this study. They are not fitted and may not
# move after a result is seen.
BANDS: list[tuple[str, float, float]] = [
    ("A", -1.0, 0.0),        # coverage == 0, structural abstention
    ("B", 0.0, 1.0 / 3.0),
    ("C", 1.0 / 3.0, 2.0 / 3.0),
    ("D", 2.0 / 3.0, 1.0),
]

# §6 minimum geometry for a band to count as a result rather than a diagnostic.
MIN_ROWS, MIN_DATES, MIN_SYMBOLS = 25, 6, 8

# §6 detectability threshold, anchored on the record's own largest observed
# selection effect: PIT-1 §8, consensus 53.7% when it leaned against 61.2% on
# the subset it promoted to an actionable call.
MDE_THRESHOLD_PP = 7.5

# The clustered design effect, taken from PIT-1's own *published* interval and
# not recomputed from any outcome. `validation/REPORT.md` §8: consensus
# aggregate n = 134, accuracy 53.7%, 95% CI [40.6, 66.8] clustered by cutoff.
#
#   published half-width      = (66.8 - 40.6) / 2                  = 13.10 pp
#   unclustered half-width    = 1.96 * sqrt(.537 * .463 / 134)     =  8.44 pp
#   inflation                 = 13.10 / 8.44                       =  1.552
#   DEFF                      = inflation^2                        =  2.409
#
# Backing an intra-cluster correlation out of that, at PIT-1's mean cluster size
# of 134/12 = 11.17 rows per cutoff, lets the design effect be re-derived at each
# band's own cluster size rather than assumed constant:
#
#   DEFF = 1 + (mbar - 1) * ICC   ->   ICC = (2.409 - 1) / (11.17 - 1) = 0.1386
PIT1_N, PIT1_ACC, PIT1_DATES = 134, 0.537, 12
PIT1_CI_LOW_PP, PIT1_CI_HIGH_PP = 40.6, 66.8

# --------------------------------------------------------- specification notes
#
# The pre-registration fixed the 7.5 pp threshold but left two details to the
# implementation. Both are settled HERE, in code committed before the run, so
# that neither can be chosen after seeing a number. Recorded as an appended,
# dated §6.1 in the pre-registration itself.
#
# 1. MDE convention. "Minimum detectable effect" is reported at the standard
#    two-sided 5% / 80% power convention, factor (1.96 + 0.8416) = 2.8016. The
#    bare 1.96 half-width is also emitted, but GATE 1 IS DECIDED ON THE
#    80%-POWER FIGURE, which is the stricter of the two.
#
# 2. Worst-case variance. Accuracy is unknown before outcomes are read, so
#    p = 0.5 is used, which maximises binomial variance. This makes the MDE as
#    large as it can honestly be at a given geometry.
Z_ALPHA, Z_POWER = 1.959964, 0.841621

# 3. Geometry is an UPPER BOUND on the scoreable rows: a horizon can be
#    available and lean at the cutoff yet drop out of `calls.csv` for want of a
#    complete outcome window. The gate therefore runs on more rows than the
#    study would have, so its MDE is optimistic — it errs toward PASSING.
#    Consequence, declared in advance and binding:
#      * a FAIL on this geometry is CONCLUSIVE, because the real geometry is
#        never better than this one;
#      * a PASS must be re-verified against the actual scoreable row count
#        before Gate 2 is computed, using the join key only and never the
#        `correct` column.


def design_effect(mean_cluster_size: float, icc: float) -> float:
    return 1.0 + max(0.0, mean_cluster_size - 1.0) * icc


def pit1_icc() -> tuple[float, float, float]:
    """Re-derive PIT-1's design effect and ICC from its published interval."""
    published_hw = (PIT1_CI_HIGH_PP - PIT1_CI_LOW_PP) / 2.0
    unclustered_hw = 100.0 * Z_ALPHA * math.sqrt(
        PIT1_ACC * (1.0 - PIT1_ACC) / PIT1_N)
    deff = (published_hw / unclustered_hw) ** 2
    mbar = PIT1_N / PIT1_DATES
    icc = (deff - 1.0) / (mbar - 1.0)
    return published_hw, deff, icc


def band_of(coverage: float) -> str:
    for name, low, high in BANDS:
        if low < coverage <= high or (name == "A" and coverage <= 0.0):
            return name
    return "D"


def se_pp(rows: int, dates: int, icc: float) -> float:
    """Clustered standard error of an accuracy, in percentage points, at p=0.5."""
    if rows <= 0 or dates <= 0:
        return float("inf")
    deff = design_effect(rows / dates, icc)
    return 100.0 * math.sqrt(0.25 / rows * deff)


def collect(payload: dict) -> dict[str, dict]:
    """Band every available horizon verdict in the frozen prediction record."""
    bands: dict[str, dict] = {
        name: {"rows": 0, "dates": set(), "symbols": set(), "horizons": defaultdict(int)}
        for name, _, _ in BANDS
    }
    for record in payload["predictions"]:
        for horizon in record["consensus"]["by_horizon"]:
            if not horizon.get("available"):
                continue
            # §3/§4: a row is "spoken" when the engine named a direction.
            # Band A is the structural abstention and holds the rest.
            coverage = float(horizon.get("coverage", 0.0))
            spoken = float(horizon.get("score", 0.0)) != 0.0
            name = band_of(coverage) if spoken else "A"
            entry = bands[name]
            entry["rows"] += 1
            entry["dates"].add(record["cutoff"])
            entry["symbols"].add(record["symbol"])
            entry["horizons"][horizon["horizon"]] += 1
    return bands


def main() -> int:
    payload = json.loads(PREDICTIONS.read_text())
    published_hw, deff, icc = pit1_icc()
    bands = collect(payload)

    rows_out = []
    for name, _, _ in BANDS:
        entry = bands[name]
        rows, dates, symbols = entry["rows"], len(entry["dates"]), len(entry["symbols"])
        meets = (rows >= MIN_ROWS and dates >= MIN_DATES and symbols >= MIN_SYMBOLS)
        rows_out.append({
            "band": name,
            "rows": rows,
            "dates": dates,
            "symbols": symbols,
            "rows_per_date": round(rows / dates, 2) if dates else None,
            "design_effect": round(design_effect(rows / dates, icc), 3) if dates else None,
            "half_width_pp": round(se_pp(rows, dates, icc) * Z_ALPHA, 2) if dates else None,
            "meets_minimum_geometry": meets,
            "by_horizon": dict(entry["horizons"]),
        })

    lookup = {r["band"]: r for r in rows_out}
    b, d = lookup["B"], lookup["D"]
    se_diff = math.sqrt(
        se_pp(b["rows"], b["dates"], icc) ** 2 + se_pp(d["rows"], d["dates"], icc) ** 2)
    mde_80 = (Z_ALPHA + Z_POWER) * se_diff
    hw_diff = Z_ALPHA * se_diff

    geometry_ok = all(lookup[n]["meets_minimum_geometry"] for n in ("B", "C", "D"))
    mde_ok = mde_80 <= MDE_THRESHOLD_PP
    verdict = "PASS" if (geometry_ok and mde_ok) else "FAIL"

    result = {
        "study": "ABS-1",
        "preregistration": "alpha/V5_ABSTENTION_PREREGISTRATION.md",
        "computed_from": "validation/out/predictions.json",
        "outcomes_read": False,
        "pit1_anchor": {
            "published_half_width_pp": round(published_hw, 2),
            "design_effect": round(deff, 3),
            "icc": round(icc, 4),
        },
        "minimum_geometry": {
            "rows": MIN_ROWS, "dates": MIN_DATES, "symbols": MIN_SYMBOLS},
        "bands": rows_out,
        "primary_contrast": {
            "contrast": "D - B",
            "se_pp": round(se_diff, 2),
            "half_width_pp": round(hw_diff, 2),
            "mde_pp_80_power": round(mde_80, 2),
            "threshold_pp": MDE_THRESHOLD_PP,
            "geometry_ok": geometry_ok,
            "mde_ok": mde_ok,
        },
        "gate_1_power": verdict,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    print(f"ABS-1 Gate 1 — power. Outcomes read: NO. Source: {PREDICTIONS.name}")
    print(f"PIT-1 anchor: half-width {published_hw:.2f} pp, "
          f"DEFF {deff:.3f}, ICC {icc:.4f}")
    print(f"{'band':>5} {'rows':>6} {'dates':>6} {'syms':>5} {'rows/date':>10} "
          f"{'DEFF':>6} {'half-width':>11} {'geometry':>9}")
    for r in rows_out:
        print(f"{r['band']:>5} {r['rows']:>6} {r['dates']:>6} {r['symbols']:>5} "
              f"{str(r['rows_per_date']):>10} {str(r['design_effect']):>6} "
              f"{str(r['half_width_pp']) + ' pp':>11} "
              f"{'yes' if r['meets_minimum_geometry'] else 'NO':>9}")
    print(f"\nD - B contrast: half-width {hw_diff:.2f} pp, "
          f"MDE(80% power) {mde_80:.2f} pp against a {MDE_THRESHOLD_PP} pp threshold")
    print(f"geometry B/C/D meets minimum: {geometry_ok}; MDE within threshold: {mde_ok}")
    print(f"\nGATE 1 (POWER): {verdict}")
    if verdict == "FAIL":
        print("Per §7 the verdict is ABS-1 VERDICT: NOT ANSWERABLE IN THIS HARNESS.")
        print("calls.csv is not opened. No accuracy is computed.")
    print(f"\nwritten: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
