"""The output layer (§0, §22-26). Everything V2 is allowed to say out loud.

§0 is the reason this file exists at all: "new prediction fields go through an
adapter/output layer. Validation logic itself is never touched." Nothing under
`validation/` or `app/` imports this module, and this module imports nothing
from either — the coupling runs one way, from a caller that already has both.

What it exposes (§24-26): predicted alpha, rank percentile, model evidence, and
evidence strength. What it refuses to expose:

* **`target_price`.** §24 calls it fabricated, and the V1 study measured it:
  consensus price targets lost to "the price will not move" 62% of the time.
  A rank has no price in it, and inventing one from a rank would be inventing
  a number, not deriving one.
* **A confidence score.** §23. V1's was miscalibrated badly enough to be worse
  than silence — its 90-100 band scored 40% — and §23's rule is that no
  confidence is published until the IC signal underneath it is established.
  It is not established. `evidence_strength` is a coarse ordinal label, not a
  probability, and it is deliberately not a number between 0 and 100.

The decision cascade is HOLD-by-default and fails closed at every step. It is
the V1 `ModelEvidence` principle applied to a ranker: a reason to act has to
survive every gate, and any gate that cannot be evaluated is a HOLD, never a
shrug-and-proceed.

**As of 2026-08-08 this layer emits HOLD for every symbol on every date**, and
that is the correct output rather than a bug: `alpha/out/exam_scores.json`
records weight 0, so the first gate in the cascade never opens. The cascade
below the first gate is written and tested anyway, because a gate you have
never seen run is a gate you do not know the behaviour of.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
EXAM_SCORES = OUT_DIR / "exam_scores.json"

# §25's cascade, in order. Each is a reason to stay in HOLD.
WEAK_ALPHA = 0.0            # predicted alpha must be strictly the right side of 0
EXTREME_RANK = 0.20         # top or bottom quintile — the §16-17 tradeable band
VALIDATED_REGIMES: frozenset[str] = frozenset()   # empty: none has been validated


class Action:
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


@dataclasses.dataclass(frozen=True)
class ModelEvidence:
    """The §22 gate, as data. Weight is 0 unless all seven criteria passed."""

    weight: float
    passed_all_criteria: bool
    criteria: dict
    n_cutoffs: int
    mean_ic: float | None
    spread: float | None
    source: str
    note: str

    @property
    def strength(self) -> str:
        """A coarse ordinal, not a probability (§23).

        Four buckets and no arithmetic. The moment this returns something a
        caller can multiply by a position size, it is a confidence score, and
        §23 says there is not one until the IC underneath it is established.
        """
        if not self.passed_all_criteria or self.weight <= 0.0:
            return "NONE"
        if self.n_cutoffs < 100:
            return "WEAK"
        if self.mean_ic is not None and self.mean_ic >= 0.05:
            return "MODERATE"
        return "WEAK"


def load_evidence(path: pathlib.Path | None = None) -> ModelEvidence:
    """Read the frozen exam verdict. Absent or unreadable means weight 0.

    Failing closed on a missing file is the point: a deploy that lost its
    scores file should go quiet, not fall back to trusting the model.
    """
    path = path or EXAM_SCORES
    if not path.exists():
        return ModelEvidence(0.0, False, {}, 0, None, None, str(path),
                             "no exam scores on disk — failing closed to HOLD")
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return ModelEvidence(0.0, False, {}, 0, None, None, str(path),
                             f"exam scores unreadable ({error}) — failing closed to HOLD")

    criteria = blob.get("criteria", {})
    passed = bool(blob.get("passed_all_seven", False))
    return ModelEvidence(
        weight=float(blob.get("production_weight", 0.0)) if passed else 0.0,
        passed_all_criteria=passed,
        criteria={k: bool(v.get("passed")) for k, v in criteria.items()},
        n_cutoffs=int(blob.get("n_cutoffs", 0)),
        mean_ic=(blob.get("ic") or {}).get("mean"),
        spread=(blob.get("spread") or {}).get("mean"),
        source=str(path),
        note=blob.get("production_weight_note", ""),
    )


@dataclasses.dataclass(frozen=True)
class AlphaView:
    """One symbol on one date, as the UI is allowed to see it.

    Deliberately absent: `target_price`, `confidence`, `expected_move`,
    `price_path`. Deliberately present but unpopulated: the §26 cost fields,
    reserved now so adding costs later is a change of value rather than a
    change of schema.
    """

    symbol: str
    cutoff: str
    action: str
    reason: str
    predicted_alpha: float | None
    rank_percentile: float | None
    horizon_sessions: int
    evidence_weight: float
    evidence_strength: str
    evidence_criteria: dict
    # §26 — reserved, not populated. Costs and turnover are evaluated only once
    # a signal survives everything above, and nothing has.
    gross_alpha: float | None = None
    net_alpha: float | None = None
    turnover: float | None = None
    cost_model: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def decide(predicted_alpha: float | None, rank_percentile: float | None,
           evidence: ModelEvidence, regime: str | None = None,
           historical_spread: float | None = None) -> tuple[str, str]:
    """§25's cascade, in the order §25 writes it. Returns `(action, reason)`.

    insufficient evidence -> weak alpha -> non-extreme rank ->
    non-positive historical spread -> out-of-validated-regime -> HOLD;
    else LONG/SHORT.

    Every branch that cannot be evaluated returns HOLD. There is no path
    through this function that reaches LONG or SHORT on missing data.
    """
    if evidence.weight <= 0.0 or not evidence.passed_all_criteria:
        return Action.HOLD, ("insufficient model evidence: "
                             + (evidence.note or "weight 0 under §22"))

    if predicted_alpha is None or not np.isfinite(predicted_alpha):
        return Action.HOLD, "no predicted alpha for this symbol on this date"
    if abs(predicted_alpha) <= WEAK_ALPHA:
        return Action.HOLD, f"weak alpha ({predicted_alpha:+.5f})"

    if rank_percentile is None or not np.isfinite(rank_percentile):
        return Action.HOLD, "no cross-sectional rank — a rank needs a cross-section"
    extreme = rank_percentile >= 1.0 - EXTREME_RANK or rank_percentile <= EXTREME_RANK
    if not extreme:
        return Action.HOLD, (f"rank {rank_percentile:.2f} is not in the outer "
                             f"{EXTREME_RANK:.0%} of the cross-section")

    if historical_spread is None or not np.isfinite(historical_spread):
        return Action.HOLD, "no measured top-bottom spread to stand on"
    if historical_spread <= 0.0:
        return Action.HOLD, f"historical spread is non-positive ({historical_spread:+.5f})"

    if regime is None or regime not in VALIDATED_REGIMES:
        return Action.HOLD, (f"regime {regime!r} is not in the validated set "
                             f"{sorted(VALIDATED_REGIMES) or '(empty — none validated)'}")

    # Direction comes from the rank, not from the sign of a small number: the
    # rank is what the model was scored on, and it is the quantity criterion 3
    # measured. Both legs are equally sized by construction (§16-17).
    if rank_percentile >= 1.0 - EXTREME_RANK:
        return Action.LONG, (f"top {EXTREME_RANK:.0%} by predicted alpha "
                             f"({predicted_alpha:+.5f}), all §22 criteria passed")
    return Action.SHORT, (f"bottom {EXTREME_RANK:.0%} by predicted alpha "
                          f"({predicted_alpha:+.5f}), all §22 criteria passed")


def view(symbol: str, cutoff: str, predicted_alpha: float | None,
         rank_percentile: float | None, evidence: ModelEvidence,
         regime: str | None = None, historical_spread: float | None = None,
         horizon_sessions: int = 5) -> AlphaView:
    """Build the single object the presentation layer is allowed to render."""
    action, reason = decide(predicted_alpha, rank_percentile, evidence,
                            regime=regime, historical_spread=historical_spread)
    return AlphaView(
        symbol=symbol,
        cutoff=cutoff,
        action=action,
        reason=reason,
        predicted_alpha=_finite(predicted_alpha),
        rank_percentile=_finite(rank_percentile),
        horizon_sessions=horizon_sessions,
        evidence_weight=evidence.weight,
        evidence_strength=evidence.strength,
        evidence_criteria=dict(evidence.criteria),
    )


def _finite(value: float | None) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


def views_from_exam(path: pathlib.Path | None = None) -> list[AlphaView]:
    """Render every frozen exam prediction through the cascade.

    Useful as a demonstration that the layer runs end to end on real numbers,
    and as the thing to point at when someone asks what V2 would have shown a
    user on those dates. The answer, today, is HOLD on all 5,899 of them.
    """
    predictions_path = (path or OUT_DIR / "exam_predictions.json")
    if not predictions_path.exists():
        return []
    blob = json.loads(predictions_path.read_text(encoding="utf-8"))
    evidence = load_evidence()
    return [view(row["symbol"], row["cutoff"], row.get("predicted"),
                 row.get("rank_pct"), evidence)
            for row in blob.get("predictions", [])]


def main() -> None:
    evidence = load_evidence()
    rendered = views_from_exam()
    actions: dict[str, int] = {}
    for item in rendered:
        actions[item.action] = actions.get(item.action, 0) + 1

    print(f"evidence   weight {evidence.weight}  strength {evidence.strength}  "
          f"({evidence.n_cutoffs} cutoffs)")
    print(f"           {evidence.note}")
    print(f"criteria   {evidence.criteria}")
    print(f"rendered   {len(rendered):,} exam predictions -> {actions or '{}'}")
    if rendered:
        print(f"example    {rendered[0].to_dict()}")


if __name__ == "__main__":
    main()
