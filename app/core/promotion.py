"""The evidence gate every production status change must pass.

Phase 3 gave each component an identity and a status.  It could not say how a
status is allowed to *change*, and said so — `model_registry` records
"no promotion rule exists yet (Phase 7)" against the ensemble and against every
neural challenger.  This module is that rule.

Four things are worth stating plainly, because the tests enforce them.

* **Nothing here promotes anything.**  Every public function returns a
  `Verdict` and mutates nothing.  A status lives in `model_registry` source, so
  changing one is a human edit in a reviewable commit — which is also the whole
  of the rollback story: reverting a promotion is reverting that commit, and no
  checkpoint store is needed because no model in this repository persists a
  trained artefact in the first place.

* **The counting unit is the cutoff, never the row.**  Thirty symbols read on
  one day are one draw.  This is the lesson that cost the programme Phase 5(a)
  and Phase 6, and it is the reason `Evidence` reports `n_independent_cutoffs`
  alongside `n_rows` and gates on the former.  Cutoffs whose forecast windows
  overlap are not independent, so they are collapsed before they are counted.

* **Every threshold below was declared while the ledger was empty.**
  `app/forecast_ledger.sqlite3` does not exist; no forecast has ever been
  frozen.  A threshold written now cannot have been chosen to fit a result,
  because there is no result to fit it to.  That is the strongest form the
  temporal-ordering discipline of CLAUDE.md §5.2 can take, and it is available
  exactly once.

* **The incumbent is grandfathered, not endorsed.**  `ensemble.ultimate` holds
  PRODUCTION by history, and it would not pass the gate below — there is no
  evidence either way.  Phase 7 does not demote it; that is a production
  decision and belongs to Phase 11.  `GRANDFATHERED` records the debt.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from . import model_registry, outcome_ledger


#: Bumped whenever a threshold changes.  A promotion records the version it was
#: decided under, so a later reader can tell which policy applied.
POLICY_VERSION = 1

_Z = 1.959963984540054  # two-sided 95%, the same convention as outcome_ledger


# ------------------------------------------------------------------ thresholds
#
# Each one carries its provenance.  None was chosen by looking at a return.

#: `ROADMAP.md`'s own preregistered criterion — "no regime collapse, and >= 50
#: independent cutoffs" — reused verbatim rather than reinvented.  Phase 9 §4.2
#: prices it: at 50 cutoffs and 30 symbols the record resolves ~75.9 bp, against
#: 154.8 bp at 12.  It is a floor for saying anything at all, not a promise.
MIN_INDEPENDENT_CUTOFFS = 50

#: A diversity floor, explicitly **not** a resolution requirement.  Phase 9 §4.3
#: measured that on this geometry infinite breadth buys 3.8%, so breadth cannot
#: rescue an interval.  What it does guard is a single-name fluke being read as
#: a general result, which is why the number is small and does not scale.
MIN_SYMBOLS = 5

#: Skill must clear zero on a cutoff-clustered interval, in the model's own
#: favour, against the baseline the forecast itself declared.  Zero rather than
#: a positive margin because the baselines here are already strong: the whole
#: PIT-1 record failed to beat `always_bullish`, so "beats its declared
#: baseline, resolvably" is a real bar and not a formality.
MIN_ADVANTAGE_LOWER_BOUND = 0.0

#: Two different reasons a PRODUCTION model has not passed the gate, and they
#: are not the same kind of thing.  The first is a statement that the gate is
#: the wrong instrument; the second is an admission of debt.
_NOTHING_IS_FITTED = (
    "Closed form — no parameters are fitted from data, so there is nothing to "
    "retrain, no version to roll back to, and no fit that can degrade. The "
    "promotion gate measures whether a *fitted* candidate earned its status; "
    "for this component the registry's own retraining policy is 'nothing is "
    "fitted, so nothing is refitted'. It is listed rather than exempted so "
    "that adding a fourteenth production component stays a deliberate act."
)
_INCUMBENT_DEBT = (
    "Incumbent since before the V5 programme began, and the one production "
    "component that genuinely adapts: its source weights are re-derived from "
    "the tail holdout at every evaluation. It holds PRODUCTION by history, not "
    "by evidence — the forecast ledger is empty, so the gate below can neither "
    "pass nor fail it. Phase 7 does not demote it; whether the incumbent keeps "
    "production weight is a Phase 11 decision. Recorded here so the debt is "
    "visible rather than implied."
)

#: Models holding PRODUCTION without having passed the gate, each with the
#: reason it is tolerated.  Enumerated by hand rather than derived from family,
#: deliberately: deriving it would auto-absorb the next production component
#: and that is exactly the drift the gate exists to prevent.  A model may be
#: added here **only** by a commit that states why; the suite fails if a
#: PRODUCTION model appears in neither this mapping nor `PROMOTED`.
GRANDFATHERED: dict[str, str] = {
    "technical.adx": _NOTHING_IS_FITTED,
    "technical.bollinger": _NOTHING_IS_FITTED,
    "technical.donchian": _NOTHING_IS_FITTED,
    "technical.macd": _NOTHING_IS_FITTED,
    "technical.obv": _NOTHING_IS_FITTED,
    "technical.roc": _NOTHING_IS_FITTED,
    "technical.rsi": _NOTHING_IS_FITTED,
    "technical.structure": _NOTHING_IS_FITTED,
    "technical.trend_ma": _NOTHING_IS_FITTED,
    "technical.trend_slope": _NOTHING_IS_FITTED,
    "rule_agent.crossover": _NOTHING_IS_FITTED,
    "rule_agent.rolling": _NOTHING_IS_FITTED,
    "rule_agent.turtle": _NOTHING_IS_FITTED,
    model_registry.ULTIMATE_ENSEMBLE: _INCUMBENT_DEBT,
}

#: Models that reached PRODUCTION by passing `evaluate_promotion`.  Empty, and
#: it is meant to be: nothing has ever been promoted on evidence in this
#: repository.  Each future entry is `model_id -> the commit that promoted it`.
PROMOTED: dict[str, str] = {}


# ------------------------------------------------------------------- decisions

PROMOTE = "PROMOTE"
HOLD = "HOLD"
BLOCK = "BLOCK"
DEGRADED = "DEGRADED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PromotionError(RuntimeError):
    """A status change was attempted outside the gate."""


@dataclasses.dataclass(frozen=True)
class Gate:
    """One named condition, its verdict, and the number behind it."""

    name: str
    passed: bool
    detail: str


@dataclasses.dataclass(frozen=True)
class Evidence:
    """What the outcome ledger supports about one model at one horizon.

    Every statistic is computed **across independent cutoffs**: rows within a
    cutoff are averaged first, so a symbol-rich day contributes one number and
    the interval reflects the spread between days rather than between symbols.
    """

    model_id: str
    horizon: str
    n_rows: int
    n_cutoffs: int
    n_independent_cutoffs: int
    n_symbols: int
    first_cutoff: pd.Timestamp | None
    last_cutoff: pd.Timestamp | None
    advantage: float
    advantage_half_width: float
    directional_accuracy: float

    @property
    def advantage_lower_bound(self) -> float:
        """The favourable end of the interval — what a claim must clear."""
        if not math.isfinite(self.advantage) or not math.isfinite(
                self.advantage_half_width):
            return float("nan")
        return self.advantage - self.advantage_half_width

    @property
    def advantage_upper_bound(self) -> float:
        if not math.isfinite(self.advantage) or not math.isfinite(
                self.advantage_half_width):
            return float("nan")
        return self.advantage + self.advantage_half_width


@dataclasses.dataclass(frozen=True)
class Verdict:
    """A decision, the gates behind it, and the evidence they read."""

    model_id: str
    horizon: str
    decision: str
    gates: tuple[Gate, ...]
    evidence: Evidence | None
    policy_version: int = POLICY_VERSION

    @property
    def passed(self) -> bool:
        return all(gate.passed for gate in self.gates)

    @property
    def failed_gates(self) -> tuple[Gate, ...]:
        return tuple(gate for gate in self.gates if not gate.passed)

    def explain(self) -> str:
        """One line per gate — what a promotion commit message quotes."""
        head = f"{self.model_id} @ {self.horizon}: {self.decision}"
        body = "\n".join(
            f"  [{'PASS' if gate.passed else 'FAIL'}] {gate.name} — {gate.detail}"
            for gate in self.gates)
        return f"{head}\n{body}" if body else head


# -------------------------------------------------------------- independence


def independent_cutoffs(windows: Sequence[tuple[pd.Timestamp, pd.Timestamp]]
                        ) -> tuple[pd.Timestamp, ...]:
    """The largest set of cutoffs whose forecast windows do not overlap.

    A forecast made on Monday for a week ahead and one made on Tuesday for the
    same week are not two draws: they resolve against overlapping price paths.
    Phase 6 measured this on the frozen record — two of its twelve cutoffs sat
    17 and 23 days apart against a 60-day construction window — and counted the
    record as materially fewer than twelve draws for that reason.

    Greedy earliest-finishing selection, which is optimal for interval
    scheduling, so this is the true maximum rather than an approximation.
    """
    ordered = sorted(windows, key=lambda pair: (pair[1], pair[0]))
    kept: list[pd.Timestamp] = []
    frontier: pd.Timestamp | None = None
    for start, end in ordered:
        if frontier is None or start >= frontier:
            kept.append(start)
            frontier = end
    return tuple(kept)


def _half_width(values: Sequence[float]) -> float:
    """Normal-approximation half-width.  Never meaningful below two draws."""
    array = np.asarray([v for v in values if v is not None and np.isfinite(v)],
                       dtype=float)
    if array.size < 2:
        return float("nan")
    return float(_Z * array.std(ddof=1) / math.sqrt(array.size))


def evidence_for(
    frame: pd.DataFrame,
    model_id: str,
    horizon: str,
    *,
    as_of: dt.datetime | pd.Timestamp | None = None,
) -> Evidence:
    """Cutoff-clustered evidence for one model at one horizon.

    `frame` is an `outcome_ledger.performance_frame`.  When `as_of` is given the
    frame is first restricted to outcomes that had *matured* by then, because
    performance becomes knowable at maturity and not at the cutoff — using the
    cutoff would read outcomes that had not happened yet.
    """
    empty = Evidence(
        model_id=model_id, horizon=horizon, n_rows=0, n_cutoffs=0,
        n_independent_cutoffs=0, n_symbols=0, first_cutoff=None,
        last_cutoff=None, advantage=float("nan"),
        advantage_half_width=float("nan"), directional_accuracy=float("nan"),
    )
    if frame is None or frame.empty:
        return empty

    if as_of is not None:
        frame = outcome_ledger.known_as_of(frame, as_of)
        if frame.empty:
            return empty

    rows = frame.loc[(frame["model_key"] == model_id)
                     & (frame["horizon"] == horizon)]
    if rows.empty:
        return empty

    # One window per cutoff: from the cutoff to the last maturity it produced.
    spans = rows.groupby("cutoff_at").agg(matured_at=("matured_at", "max"))
    windows = [(cutoff, spans.at[cutoff, "matured_at"]) for cutoff in spans.index]
    keep = set(independent_cutoffs(windows))
    independent = rows.loc[rows["cutoff_at"].isin(keep)]

    # Average within a cutoff first.  This is the clustering, and it is the
    # whole reason the interval below is honest.
    per_cutoff = independent.groupby("cutoff_at").agg(
        advantage=("baseline_relative_absolute_error", "mean"),
        directional=("directional_correct", "mean"),
    )
    advantages = per_cutoff["advantage"].tolist()
    directionals = [v for v in per_cutoff["directional"].tolist()
                    if v is not None and np.isfinite(v)]

    return Evidence(
        model_id=model_id,
        horizon=horizon,
        n_rows=int(len(rows)),
        n_cutoffs=int(rows["cutoff_at"].nunique()),
        n_independent_cutoffs=int(len(keep)),
        n_symbols=int(independent["symbol"].nunique()),
        first_cutoff=rows["cutoff_at"].min(),
        last_cutoff=rows["cutoff_at"].max(),
        advantage=float(np.mean(advantages)) if advantages else float("nan"),
        advantage_half_width=_half_width(advantages),
        directional_accuracy=(float(np.mean(directionals)) if directionals
                              else float("nan")),
    )


# ------------------------------------------------------------------ the gates


def evaluate_promotion(
    model_id: str,
    frame: pd.DataFrame,
    horizon: str,
    *,
    as_of: dt.datetime | pd.Timestamp | None = None,
) -> Verdict:
    """Whether a CHALLENGER may become PRODUCTION.  Decides; never acts.

    Every gate must pass.  A missing ledger is not a neutral state — it fails
    G3 and the decision is BLOCK, which is the correct behaviour for a
    repository whose ledger has never been written to.
    """
    try:
        spec = model_registry.get(model_id)
    except model_registry.ModelRegistryError as error:
        gate = Gate("G1 registered", False, str(error))
        return Verdict(model_id, horizon, BLOCK, (gate,), None)

    gates: list[Gate] = [
        Gate("G1 registered", True,
             f"{spec.model_id} is registered, status {spec.production_status}"),
        Gate("G2 challenger", spec.production_status == model_registry.CHALLENGER,
             f"promotion applies to CHALLENGER models; this is "
             f"{spec.production_status}"),
        Gate("G3 point-in-time",
             spec.pit_status == model_registry.PIT_ADMISSIBLE,
             f"PIT status is {spec.pit_status}; only PIT-ADMISSIBLE models "
             "may hold production weight"),
    ]

    evidence = evidence_for(frame, model_id, horizon, as_of=as_of)
    gates.append(Gate(
        "G4 evidence exists", evidence.n_rows > 0,
        f"{evidence.n_rows} scored rows"
        + ("" if evidence.n_rows else " — the ledger holds nothing for this "
                                      "model at this horizon")))
    gates.append(Gate(
        "G5 resolution",
        evidence.n_independent_cutoffs >= MIN_INDEPENDENT_CUTOFFS,
        f"{evidence.n_independent_cutoffs} independent cutoffs "
        f"(of {evidence.n_cutoffs} recorded) against a floor of "
        f"{MIN_INDEPENDENT_CUTOFFS}"))
    gates.append(Gate(
        "G6 breadth", evidence.n_symbols >= MIN_SYMBOLS,
        f"{evidence.n_symbols} symbols against a floor of {MIN_SYMBOLS}"))

    lower = evidence.advantage_lower_bound
    gates.append(Gate(
        "G7 skill vs declared baseline",
        bool(math.isfinite(lower) and lower > MIN_ADVANTAGE_LOWER_BOUND),
        f"cutoff-clustered advantage {evidence.advantage:+.6f} "
        f"± {evidence.advantage_half_width:.6f}, lower bound {lower:+.6f} "
        f"against a floor of {MIN_ADVANTAGE_LOWER_BOUND:+.6f}"))

    decision = PROMOTE if all(gate.passed for gate in gates) else BLOCK
    return Verdict(model_id, horizon, decision, tuple(gates), evidence)


def evaluate_degradation(
    model_id: str,
    frame: pd.DataFrame,
    horizon: str,
    *,
    as_of: dt.datetime | pd.Timestamp | None = None,
) -> Verdict:
    """Whether a PRODUCTION model has lost the right to its status.

    Deliberately asymmetric with `evaluate_promotion`: a model is degraded only
    when the evidence is resolvable *and* points against it.  An unresolvable
    record returns INSUFFICIENT_EVIDENCE rather than DEGRADED, because "we
    cannot tell" is not a finding of harm — the same distinction Phase 6 drew
    between an admissibility block and a null result.
    """
    evidence = evidence_for(frame, model_id, horizon, as_of=as_of)

    resolvable = evidence.n_independent_cutoffs >= MIN_INDEPENDENT_CUTOFFS
    gates = [Gate(
        "D1 resolution",
        resolvable,
        f"{evidence.n_independent_cutoffs} independent cutoffs against a floor "
        f"of {MIN_INDEPENDENT_CUTOFFS}")]

    upper = evidence.advantage_upper_bound
    against = bool(math.isfinite(upper) and upper < 0.0)
    gates.append(Gate(
        "D2 worse than its declared baseline, resolvably",
        against,
        f"cutoff-clustered advantage {evidence.advantage:+.6f} "
        f"± {evidence.advantage_half_width:.6f}, upper bound {upper:+.6f}"))

    if not resolvable:
        decision = INSUFFICIENT_EVIDENCE
    elif against:
        decision = DEGRADED
    else:
        decision = HOLD
    return Verdict(model_id, horizon, decision, tuple(gates), evidence)


# ------------------------------------------------------------- the invariant


def undeclared_production_models() -> tuple[str, ...]:
    """PRODUCTION models accounted for by neither `GRANDFATHERED` nor `PROMOTED`.

    This is the structural form of the Phase 7 gate: a model cannot acquire
    production status quietly, because acquiring it without an entry in one of
    those two mappings fails the suite.  Returning an empty tuple is the
    invariant, not a coincidence.
    """
    declared = set(GRANDFATHERED) | set(PROMOTED)
    return tuple(sorted(
        spec.model_id for spec in model_registry.by_status(model_registry.PRODUCTION)
        if spec.model_id not in declared))


def assert_production_is_declared() -> None:
    """Raise unless every PRODUCTION model is grandfathered or gate-promoted."""
    undeclared = undeclared_production_models()
    if undeclared:
        raise PromotionError(
            "production status held without a Phase 7 declaration: "
            + ", ".join(undeclared)
            + ". Add an entry to promotion.PROMOTED naming the commit that "
              "passed evaluate_promotion, or to promotion.GRANDFATHERED "
              "stating why the debt is tolerated.")


def policy() -> dict[str, Any]:
    """The active policy as data — for the Phase 8 UI and for reports."""
    return {
        "policy_version": POLICY_VERSION,
        "min_independent_cutoffs": MIN_INDEPENDENT_CUTOFFS,
        "min_symbols": MIN_SYMBOLS,
        "min_advantage_lower_bound": MIN_ADVANTAGE_LOWER_BOUND,
        "grandfathered": dict(GRANDFATHERED),
        "promoted": dict(PROMOTED),
        "undeclared": undeclared_production_models(),
    }
