"""Family 3 (13F institutional holdings) §2.6 power gate. Gate-only.

Builds no feature, reads no holdings, and spends no budget slot. §2.6 requires
the gate **before** implementation, so this runs on coverage as a *parameter*
rather than on a measured 13F feature: the half-width of the pre-registered
bounded arm `rank(b3) + lambda*(rank(x) - 0.5)` is set by lambda and by how
much of the cross-section the feature covers, not by whether the feature
predicts anything (`form4_gate.halfwidth` §3.2 established this and validated
it against Family 1's measured 0.00229).

**The gate is therefore evaluated across a RANGE of coverages, 0.80 to 1.00,**
so the verdict cannot depend on a coverage figure that is not yet measured and
cannot be nudged later by a mapping decision. If every level in the range is
inside the MDE, the gate's verdict is robust to the exact number.

Reuses `form4_gate`'s estimator unchanged rather than reimplementing it, so
Family 3's gate is the same instrument as Family 2's.

ASCII stdout only.
"""

from __future__ import annotations

import json
import pickle
import sys
import time

import numpy as np

from . import form4_gate, stats  # noqa: F401

OUT_DIR = "alpha/out"

#: The smallest effect worth acting on, from the frozen cost model. Unchanged
#: from Families 1 and 2 -- NOT re-derived here, because re-deriving an MDE
#: for a family that is about to be tested is how an MDE gets softened.
MDE = 0.007

COVERAGES = (0.80, 0.85, 0.90, 0.95, 1.00)
SEED = 20260809


def main() -> int:
    started = time.time()
    frame, regimes, dev = form4_gate._development_frame()
    target = frame[form4_gate.v3_family1.TARGET]
    b3, base_ic = form4_gate._base(frame, regimes)
    print("Family 3 (13F) - Section 2.6 power gate. GATE ONLY, no feature built.")
    print("base: B3 rank, %d cutoffs, mean IC %+.5f" % (len(base_ic), base_ic.mean()))
    print("development cutoffs %d" % len(dev))

    rng = np.random.default_rng(SEED)

    print()
    print("=== step 1: the smallest effect worth acting on ===")
    print("MDE, carried unchanged from Families 1 and 2: %+.4f IC vs B3" % MDE)

    print()
    print("=== VALIDATION of the estimator against Family 1's measured value ===")
    print("Family 1 measured %.5f at coverage %.3f, lambda %.2f"
          % (form4_gate.FAMILY1_MEASURED, form4_gate.FAMILY1_COVERAGE,
             form4_gate.LAMBDA))
    validation = form4_gate._half_width_at(
        frame, b3, base_ic, target, form4_gate.FAMILY1_COVERAGE,
        "uninformative @ coverage %.3f" % form4_gate.FAMILY1_COVERAGE, rng)
    calibration = form4_gate.FAMILY1_MEASURED / validation
    print("estimator runs %.2fx of measured -> calibration factor %.2fx"
          % (validation / form4_gate.FAMILY1_MEASURED, calibration))

    print()
    print("=== step 2: achievable half-width across the coverage range ===")
    results = {}
    for coverage in COVERAGES:
        raw = form4_gate._half_width_at(
            frame, b3, base_ic, target, coverage,
            "13F availability @ coverage %.2f" % coverage, rng)
        results[coverage] = {"raw": raw, "calibrated": raw * calibration}

    print()
    print("%-14s %12s %12s %10s %s"
          % ("coverage", "raw", "calibrated", "vs MDE", "verdict"))
    worst = 0.0
    for coverage, value in results.items():
        ratio = MDE / value["calibrated"]
        worst = max(worst, value["calibrated"])
        print("%-14.2f %12.5f %12.5f %9.1fx %s"
              % (coverage, value["raw"], value["calibrated"], ratio,
                 "inside" if value["calibrated"] < MDE else "OUTSIDE"))

    passed = worst < MDE
    print()
    print("=== step 3: the verdict ===")
    print("worst calibrated half-width across the range: %.5f" % worst)
    print("MDE:                                          %.5f" % MDE)
    print("Section 2.6 verdict: %s"
          % ("PASS - the design can resolve the effect it seeks"
             if passed else "FAIL - REFUSE TO RUN"))
    print()
    print("A passed gate authorizes nothing on its own. It states only that the")
    print("design's resolution is finer than the effect sought.")

    payload = {
        "family": "3 - 13F institutional holdings",
        "mde": MDE,
        "validation": validation,
        "calibration": calibration,
        "coverages": {str(k): v for k, v in results.items()},
        "worst_calibrated": worst,
        "passed": bool(passed),
        "lambda": form4_gate.LAMBDA,
        "draws": form4_gate.DRAWS,
        "seed": SEED,
        "seconds": round(time.time() - started, 1),
    }
    with open(f"{OUT_DIR}/f13_gate.json", "w") as handle:
        json.dump(payload, handle, indent=2)
    print("\nwrote alpha/out/f13_gate.json  (%.1fs)" % payload["seconds"])
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
