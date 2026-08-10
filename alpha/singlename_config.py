"""Frozen constants for the Single-Name Phase 1 study.

Every value here is fixed by `alpha/SINGLE_NAME_PREREGISTRATION.md`, which was
committed before any single-name probability existed. The module exists so that
the study cannot quietly disagree with its own protocol: `singlename.py` and
`singlename_score.py` import these names and define none of their own.

Two of them are re-exported rather than redefined — `HORIZON` and `EMBARGO` come
from `alpha/dataset.py`, so a change there cannot leave this study running on a
stale copy of the horizon it claims to inherit.

Changing anything in this file after a result exists is a protocol breach, not a
refactor (CLAUDE.md §1.2).
"""

from __future__ import annotations

import pathlib

from . import dataset

# ----------------------------------------------------------------------
# §1.1 / §1.2 — horizon and target. Inherited, never re-chosen.
# ----------------------------------------------------------------------

HORIZON = dataset.HORIZON               # 5 sessions — alpha/targets.py::HORIZON
EMBARGO = dataset.EMBARGO               # 5 sessions
HORIZON_LABEL = "5D"

TARGET_RETURN = "asset_return"          # absolute forward return, NOT alpha_5d
#: A return of exactly 0.0 counts as *not up*. Fixed in §1.2 before any label was read.
UP_STRICTLY_POSITIVE = True

# ----------------------------------------------------------------------
# §1.5 — walk-forward geometry
# ----------------------------------------------------------------------

MIN_TRAIN_CUTOFFS = 100                 # 504 warm-up sessions / 5-session spacing
CONFORMAL_CUTOFFS = 20                  # most recent admissible cutoffs, withheld from fits

# ----------------------------------------------------------------------
# §3 — the five incumbents
# ----------------------------------------------------------------------

ARMS = ("S0", "S1", "S2", "S3", "S4")

ARM_LABELS = {
    "S0": "always up",
    "S1": "unconditional prior",
    "S2": "12-1 momentum",
    "S3": "B3",
    "S4": "B3 x market state",
}

PROB_CLIP = 0.001                       # probabilities clipped to [0.001, 0.999]
MIN_BUCKET_CUTOFFS = 20                 # S4 fallback threshold, §3.5

LOGISTIC_PARAMS = dict(C=1.0, solver="lbfgs", max_iter=1000, random_state=0)
RIDGE_PARAMS = dict(alpha=1.0)
WINSOR_TAIL = 0.01                      # alpha/targets.py::WINSOR

FEATURE_S2 = "ret_12_1"                 # ranked within the cutoff, then centred at 0.5
FEATURE_S3 = "b3_rank"                  # alpha/protocol.py b3_regime_switched, ranked

# ----------------------------------------------------------------------
# §3.7 — uncertainty
# ----------------------------------------------------------------------

INTERVAL_LEVEL = 0.90                   # nominal two-sided coverage
INTERVAL_LOW_Q = 0.05
INTERVAL_HIGH_Q = 0.95

# ----------------------------------------------------------------------
# §4 — decision rule. Frozen before any probability existed; never tuned.
# ----------------------------------------------------------------------

BUY_PROB = 0.55
SELL_PROB = 0.45
MIN_EDGE = 0.0025                       # 25 bp over five sessions

#: Reported as a diagnostic curve only. No point on it may become the rule (§4).
THRESHOLD_SWEEP = (0.50, 0.52, 0.54, 0.55, 0.56, 0.58, 0.60, 0.65)

#: §4 secondary variant: drop the widest decile of prediction intervals per cutoff.
UNCERTAINTY_GATE_QUANTILE = 0.90

# ----------------------------------------------------------------------
# §5.1 — metrics
# ----------------------------------------------------------------------

CALIBRATION_BINS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
CONFIDENCE_TIERS = (("low", 0.0, 0.02), ("medium", 0.02, 0.05), ("high", 0.05, 1.0))

# ----------------------------------------------------------------------
# §5.2 — the verdict gates. Frozen before any result.
# ----------------------------------------------------------------------

G2_MAX_ECE = 0.02
G2_MIN_MONOTONE_SPEARMAN = 0.5
G2_MIN_BIN_CUTOFFS = 30
G3_MIN_COVERAGE = 0.05
G3_MIN_SYMBOLS = 100

# ----------------------------------------------------------------------
# Paths — §7 two-process separation
# ----------------------------------------------------------------------

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
PREDICTIONS_PATH = OUT_DIR / "single_name_predictions.pkl"
SCORES_PATH = OUT_DIR / "single_name_scores.json"
SERIES_PATH = OUT_DIR / "single_name_series.pkl"

MODEL_VERSION = "single-name-phase1"
PREREGISTRATION = "alpha/SINGLE_NAME_PREREGISTRATION.md"
