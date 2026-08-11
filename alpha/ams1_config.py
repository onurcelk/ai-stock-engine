"""Frozen constants for AMS-1, the agent meta-signal study.

Every value here is fixed by `alpha/AGENT_META_PREREGISTRATION.md`, which is
committed before any AMS-1 forward return is read. The module exists so the
study cannot quietly disagree with its own protocol: `ams1_meta.py` and
`ams1_score.py` import these names and define none of their own.

`HORIZON` and `EMBARGO` are re-exported from `alpha/dataset.py` through
`singlename_config`, so a change there cannot leave this study running on a
stale copy of the horizon it claims to inherit.

Changing anything in this file after a result exists is a protocol breach, not a
refactor (CLAUDE.md §1.2).
"""

from __future__ import annotations

import pathlib

from . import singlename_config as sn

# ----------------------------------------------------------------------
# §1 — inherited, never re-chosen
# ----------------------------------------------------------------------

HORIZON = sn.HORIZON                    # 5 sessions
EMBARGO = sn.EMBARGO                    # 5 sessions
HORIZON_LABEL = "5D"
TARGET_RETURN = sn.TARGET_RETURN        # asset_return — absolute, not alpha_5d
UP_STRICTLY_POSITIVE = sn.UP_STRICTLY_POSITIVE
PROB_CLIP = sn.PROB_CLIP
WINSOR_TAIL = sn.WINSOR_TAIL

#: Re-exported, not re-chosen. Every AMS-1 calibration uses the same
#: low-capacity learner Single-Name Phase 1 used, on the same settings, so the
#: comparison against the incumbents is like for like.
LOGISTIC_PARAMS = sn.LOGISTIC_PARAMS
RIDGE_PARAMS = sn.RIDGE_PARAMS

MIN_TRAIN_CUTOFFS = sn.MIN_TRAIN_CUTOFFS    # 100, same walk-forward warm-up

# ----------------------------------------------------------------------
# §2 — the admissible roster. Frozen by the Stage 1 audit, on measured
# point-in-time and cost grounds, BEFORE any outcome was read.
# ----------------------------------------------------------------------

FAMILIES = ("A_RULE", "D_POLICY_GRADIENT", "E_EVOLUTIONARY")

AGENTS = {
    "A_RULE": ("Turtle", "Moving average crossover", "Signal rolling"),
    "D_POLICY_GRADIENT": ("Policy gradient",),
    "E_EVOLUTIONARY": ("Evolution strategy", "Neuro-evolution",
                       "Neuro-evolution (novelty search)"),
}

#: One family, one vote — §M2. A family's vote is the sign of the mean of its
#: admissible agents' stances, so `E_EVOLUTIONARY`'s three implementations
#: cannot outvote `D_POLICY_GRADIENT`'s one. A mean of exactly zero is a
#: genuine abstention and votes 0; the rule is deterministic and has no tie
#: that resolves by anything other than arithmetic.
FAMILY_VOTE_RULE = "sign(mean(admissible agent stances in the family))"

#: A family needs at least this many of its agents available to cast a vote.
MIN_AGENTS_PER_FAMILY = 1

#: A row needs all three families present to receive a consensus state. Frozen
#: so the ladder's states always mean the same thing.
MIN_FAMILIES = 3

# ----------------------------------------------------------------------
# §3 — the consensus ladder. Boundaries chosen from the *arithmetic* of three
# ternary votes, not from any hit rate.
# ----------------------------------------------------------------------

#: M3, the family net vote, takes values in {-1, -2/3, -1/3, 0, 1/3, 2/3, 1}
#: when all three families vote. The ladder collapses that to five ordered
#: states; the two extremes are unanimity, which is the object the thesis is
#: actually about.
LADDER = ("strong bearish", "moderate bearish", "mixed",
          "moderate bullish", "strong bullish")

STRONG_THRESHOLD = 1.0                  # |M3| == 1 -> unanimous
MIXED_THRESHOLD = 0.0                   # M3 == 0 -> no net direction

#: Abstention rule for H4 / Gate 6. Frozen before outcomes: predict only where
#: the families are unanimous; treat everything else as NO EDGE. The second,
#: looser threshold is reported as a pre-declared sensitivity, not as a search.
ABSTAIN_KEEP = ("unanimous",)           # primary
ABSTAIN_KEEP_LOOSE = ("unanimous", "two_thirds")

# ----------------------------------------------------------------------
# §4 — baselines
# ----------------------------------------------------------------------

BASELINES = {
    "B0": "walk-forward base rate (Single-Name S1)",
    "B1": "12-1 momentum rank, walk-forward logistic (Single-Name S2)",
    "B2": "B3 rank, walk-forward logistic (Single-Name S3)",
    "B3": "B3 x market state (Single-Name S4) — the strongest Phase 1 incumbent",
    "B4": "naive raw agent majority vote, walk-forward logistic",
    "B5": "equal-weight family majority vote, walk-forward logistic",
}

#: The incumbent AMS-1 must beat. Named before any AMS-1 number existed: SN-1
#: reported S4 as its best probabilistic arm, and §9.4 of the registry recorded
#: its resolution. If S4's fit is unavailable at a cutoff the comparison falls
#: back to S1, which is what `singlename.apply_arm` already does.
PRIMARY_INCUMBENT = "S4"

# ----------------------------------------------------------------------
# §5 — power and uncertainty. Frozen BEFORE any half-width is computed.
# ----------------------------------------------------------------------

#: Cutoffs are spaced one horizon apart so outcome windows are adjacent and
#: non-overlapping; what remains is the market's own persistence, and the
#: programme's standing allowance for it is `alpha/stats.py::BLOCK_LENGTH` — 4
#: cutoffs, ~one month. Inherited unchanged rather than re-derived, because
#: AMS-1 runs on exactly the grid that constant was written for.
BLOCK_LENGTH_CUTOFFS = 4
BOOTSTRAP_DRAWS = 10_000

#: Marginal properties of the target, from `alpha/source_probe.py` — measured
#: with no feature and no conditioning, and already committed at 4a966a2.
RETURN_SD = 0.04526
RETURN_RHO = 0.2916
UP_VAR = 0.24783
UP_RHO = 0.1778
BLOCK_INFLATION = 1.077

BASE_UP_RATE = 0.537                    # the unconditional 5D up-rate

#: Minimum geometry for a ladder state to be reportable as a result rather than
#: as a diagnostic. Frozen before the buckets were counted.
MIN_BUCKET_ROWS = 2_000
MIN_BUCKET_CUTOFFS = 100
MIN_BUCKET_SYMBOLS = 50

# ----------------------------------------------------------------------
# §6 — acceptance gates. Numeric, frozen, and not adjustable after a result.
# ----------------------------------------------------------------------

#: Gate 2 / Gate 4 / Gate 5. SN-1's measured paired log-loss half-width against
#: S1 was 0.00096 (registry §9.4), which is the resolution any probabilistic
#: claim on this panel has. An improvement smaller than that is not a result.
MIN_LOGLOSS_GAIN = 0.001

#: Gate 3. Spearman of P(up) against the five ordered ladder states.
MIN_LADDER_SPEARMAN = 0.90

#: Gate 6. Abstention has to leave a usable book behind.
MIN_ABSTAIN_COVERAGE = 0.10

#: Gate 7.
MIN_SYMBOLS = 100
MIN_CUTOFFS = 100

#: Gate 9. The prize: a credible sub-50% conditional up-rate.
SUB_50 = 0.50

# ----------------------------------------------------------------------
# §7 — multiplicity. The bounded, pre-declared diagnostic set.
# ----------------------------------------------------------------------

#: Leave-one-family-out is a diagnostic, run once per family. With three
#: families that is three comparisons, and with the six meta-signals and the
#: five ladder states the study's pre-declared family of tests is small and
#: fixed. Holm correction is applied across the nine primary gate statistics.
MULTIPLICITY = "Holm-Bonferroni across the primary gate statistics"
PRIMARY_TESTS = 9

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
SIGNALS_PATH = OUT_DIR / "ams1_signals.pkl"
PREDICTIONS_PATH = OUT_DIR / "ams1_predictions.pkl"
POWER_PATH = OUT_DIR / "ams1_power_gate.json"
RESULT_PATH = OUT_DIR / "ams1_result.json"

PREREGISTRATION = "alpha/AGENT_META_PREREGISTRATION.md"
MODEL_VERSION = "ams1-agent-meta-signal"
