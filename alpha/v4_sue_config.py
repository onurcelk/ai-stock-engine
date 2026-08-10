"""V4-SUE — the frozen study constants. NON-PREDICTIVE CONFIGURATION ONLY.

Every value here is fixed by `alpha/V4_SUE_PREREGISTRATION.md` and, upstream of
it, by `alpha/V4_CHARTER.md` §5 and the passed power gate in
`reports/V4_SUE_POWER_GATE.md`. This module exists so the study cannot drift
from its pre-registration by a typo: the study module imports these names rather
than restating them.

**Nothing in this file is a result.** No return, no IC, no point estimate, no
forward window is read here. It is committed before the first fit, and changing
any value after a result exists is a protocol violation, not a bug fix.
"""

from __future__ import annotations

# ---- the question -----------------------------------------------------------
HORIZON = 20                    # sessions. One only. Charter §5 item 2
TARGET_NAME = "alpha_20d"       # asset 20-session return minus SPY's

# ---- the feature ------------------------------------------------------------
FEATURE = "sue"                 # construction carried unchanged from V3 §3
SUE_SIGN = +1                   # economic prior, fixed before Family 1 ran
WINSOR = 0.01                   # per-cutoff 1st/99th, unchanged

# ---- the arms ---------------------------------------------------------------
LAMBDA = 0.50                   # fixed. Never scanned. No curve point promotable
INCUMBENT = "b3_regime_switched"

# ---- the sample -------------------------------------------------------------
N_CUTOFFS = 313                 # mechanically established, gate record §3
DROPPED_CUTOFFS = ("2026-07-14", "2026-07-21", "2026-07-28")  # windows past history

# ---- the statistics ---------------------------------------------------------
BLOCK_LENGTH = 7                # FROZEN in the gate record §2.4, commit ee8fe3f
BOOTSTRAP_DRAWS = 10_000        # unchanged from the record
NEWEY_WEST_LAGS = 6             # cross-check only; spans the q=3 overlap

# ---- the decision rule ------------------------------------------------------
MDE = 0.0095                    # native 20D IC vs B3. Never lowered
ACHIEVED_HALF_WIDTH = 0.005372  # measured at the gate; margin 1.77x

# ---- the standalone horizon diagnostic --------------------------------------
P_SQRT_H = 0.0261               # SUE's sqrt(H/5) extrapolation from V3's +0.01305
                                # Never recomputed from a realized 20D value

# ---- the noise control ------------------------------------------------------
NOISE_DRAWS = 30                # paired, within-cutoff permutations of SUE
NOISE_MEDIAN_LIMIT = 0.0019     # native 20D. 0.20 x MDE, the V3 ratio preserved
NOISE_EXCEEDANCE_LIMIT = 0.10   # share of draws reaching the MDE

# ---- the economics ----------------------------------------------------------
COST_BPS = 5.0                  # research stress test, not a brokerage quote
QUINTILE = 0.2                  # top/bottom book fraction, frozen convention
HOLDING_CUTOFF_STRIDE = 4       # 4 x 5 sessions = the 20-session holding period
                                # the MDE's 13-rebalances/year cost model assumes
COVERAGE_FLOOR = 0.80           # charter §5 item 13

# ---- provenance -------------------------------------------------------------
CHARTER = "alpha/V4_CHARTER.md"                     # commit 6717111
GATE_RECORD = "reports/V4_SUE_POWER_GATE.md"        # commits ee8fe3f, fdda61a
PREREGISTRATION = "alpha/V4_SUE_PREREGISTRATION.md"
EXAM_DIGEST = "b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0"
