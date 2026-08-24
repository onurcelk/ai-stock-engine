"""One identity, one status, and one accountability record per predictive component.

Phase 1 froze what a forecast said.  Phase 2 scored it.  Neither could say
*what* made the forecast: the ledger stores a component's output under a bare
key such as `trend_ma`, and `outcome_ledger.model_key` attributed every
incumbent horizon to the placeholder string `ultimate_ensemble`.  This module
supplies the missing half — a declared identity, version, point-in-time status
and production status for every predictive component in the repository,
including the ones that must never reach production.

Four properties are worth stating because the tests enforce them:

* **The census cannot drift.**  Every key in `indicators.SOURCES`, every key in
  `agents.REGISTRY` and every horizon in `ultimate.HORIZONS` must appear here.
  Adding a source without registering it fails the suite rather than quietly
  entering a production forecast.

* **Identity and version are separate.**  `model_id` survives retraining;
  `version` is the sha256 of the exact source in use — the same string Phase 1
  already freezes into `ForecastRecord.model_versions`.

* **Every output identifies its version.**  `version_key` names the entry of
  `ForecastRecord.model_versions` that carries a component's version, so a
  frozen record can be resolved back to versioned identities without guessing.

* **Status has teeth.**  `assert_record_admissible` resolves every constituent
  of a frozen forecast and refuses the record if any of them is EXPERIMENTAL,
  REJECTED or RETIRED.  That is the mechanism preventing a rejected model from
  silently affecting production.

This module reads.  It does not train, predict, promote or retire anything —
Phase 7 owns promotion, and no status here was chosen by looking at a return.
"""

from __future__ import annotations

import dataclasses
import functools
import importlib
import re
from collections.abc import Iterable, Mapping
from typing import Any

from .forecast_ledger import (
    CHALLENGER as RECORD_CHALLENGER,
    PRODUCTION_INCUMBENT as RECORD_PRODUCTION_INCUMBENT,
    ForecastRecord,
    _module_version,
)


REGISTRY_SCHEMA_VERSION = 1

# ------------------------------------------------------------------ statuses

#: Carries production authority now.
PRODUCTION = "PRODUCTION"
#: Admissible, measured, and permitted to stand beside production for
#: comparison — but not yet promoted.  Phase 4 evaluates these.
CHALLENGER = "CHALLENGER"
#: Implemented and runnable, but disqualified from production evidence — here,
#: always because of a point-in-time defect rather than a measured result.
EXPERIMENTAL = "EXPERIMENTAL"
#: Measured and refused against its own pre-registered gate.  A rejected entry
#: is never reopened, re-tested with another learner, target or horizon.
REJECTED = "REJECTED"
#: Removed from the V5 execution graph.  Retained as historical material, not
#: callable by production or by scoring.
RETIRED = "RETIRED"

STATUSES = (PRODUCTION, CHALLENGER, EXPERIMENTAL, REJECTED, RETIRED)

#: The only statuses whose output may reach a production forecast.  A
#: challenger is included deliberately: the neural evidence is already folded
#: into the incumbent verdict when the user enables it, and Phase 1 forces that
#: record to declare the challenger's version.
PRODUCTION_ADMISSIBLE = frozenset({PRODUCTION, CHALLENGER})

# ---------------------------------------------------------------- pit status

#: Causal by construction; reads nothing after the bar it is evaluated on.
PIT_ADMISSIBLE = "PIT-ADMISSIBLE"
#: Causal only on a frame that was truncated before it was handed over.  The
#: component itself has no cutoff contract — `validation.pit.fetcher` does.
PIT_CONDITIONAL = "PIT-CONDITIONAL"
#: Reads, fits or replays across information it would not have had.
PIT_INADMISSIBLE = "PIT-INADMISSIBLE"
#: Not a forecaster; the question does not arise.
PIT_NOT_APPLICABLE = "PIT-NOT-APPLICABLE"

# --------------------------------------------------------- output semantics

#: Unitless stance in [-1, 1].  A direction with a strength, not a return.
SIGNAL_SCORE = "signal_score"
#: A predicted percentage move over the horizon.  `1.25` means `+1.25%`.
RETURN_PCT = "return_pct"
#: A cross-sectional ranking score.  Comparable across names at one cutoff,
#: not interpretable as a single name's expected return.
CROSS_SECTIONAL_SCORE = "cross_sectional_score"

#: Only the sign of the call can be scored.
DIRECTIONAL_ONLY = "DIRECTIONAL_ONLY"
#: Both the sign and the magnitude can be scored.
RETURN_AND_DIRECTIONAL = "RETURN_AND_DIRECTIONAL"
#: Belongs to a different measurement object (the alpha panel), and is not
#: scoreable by `outcome_ledger` at all.
NOT_SCOREABLE_HERE = "NOT_SCOREABLE_HERE"

#: Which `outcome_ledger.summarise` columns each score class may be read on.
#: This is what makes "one scoring framework" a checkable claim rather than a
#: description: two models are comparable exactly when their score classes
#: admit the same metric.
METRICS_BY_SCORE_CLASS: dict[str, tuple[str, ...]] = {
    DIRECTIONAL_ONLY: ("directional_accuracy",),
    RETURN_AND_DIRECTIONAL: (
        "directional_accuracy", "mae", "rmse", "mae_skill", "mae_advantage",
    ),
    NOT_SCOREABLE_HERE: (),
}

# ------------------------------------------------------------------ families

#: A_RULE through F_CURIOSITY_RL are `alpha/agents_audit.py`'s frozen taxonomy,
#: reproduced by name so the two inventories can be compared literally (see
#: `test_model_registry.py`).  They are not imported, because `alpha` imports
#: `app.core` and the arrow must not point both ways.  G through J extend that
#: taxonomy to the components the agent audit never covered.
RULE = "A_RULE"
VALUE_RL = "B_VALUE_RL"
ACTOR_CRITIC = "C_ACTOR_CRITIC"
POLICY_GRADIENT = "D_POLICY_GRADIENT"
EVOLUTIONARY = "E_EVOLUTIONARY"
CURIOSITY_RL = "F_CURIOSITY_RL"
TECHNICAL_INDICATOR = "G_TECHNICAL"
ENSEMBLE = "H_ENSEMBLE"
NEURAL_SEQUENCE = "I_NEURAL_SEQUENCE"
CROSS_SECTIONAL_ML = "J_CROSS_SECTIONAL_ML"
#: Community TradingView studies ported in `pine.py`.  A family of their own
#: rather than `G_TECHNICAL`, and the separation is load-bearing twice over: the
#: census test asserts `G_TECHNICAL` is *exactly* `indicators.SOURCES`, and a
#: Pine study is chart furniture that has never been anything else.
PINE_STUDY = "K_PINE_STUDY"

#: Implementing module -> family, for the agents built from `agents.REGISTRY`.
#: Architecture assigns the family; nothing here was chosen by performance.
_RL_FAMILY_BY_MODULE = {
    "qlearning": VALUE_RL,
    "deepq": VALUE_RL,
    "actorcritic": ACTOR_CRITIC,
    "policygradient": POLICY_GRADIENT,
    "evolution": EVOLUTIONARY,
    "neuroevolution": EVOLUTIONARY,
    "curiosity": CURIOSITY_RL,
}

#: The identity every incumbent forecast is attributed to.
ULTIMATE_ENSEMBLE = "ensemble.ultimate"


class ModelRegistryError(RuntimeError):
    """Base error for a model whose identity or standing cannot be resolved."""


class UnregisteredModelError(ModelRegistryError):
    """A prediction was produced by something the registry does not know."""


class RejectedModelError(ModelRegistryError):
    """A model without production standing appears in a production forecast."""


class ModelVersionError(ModelRegistryError):
    """A forecast does not identify the version of a model that made it."""


# ------------------------------------------------------------------- version


@functools.lru_cache(maxsize=None)
def _source_version(module_path: str) -> str:
    """Version un-packaged prediction code by the exact source in use.

    Deliberately the same function Phase 1 freezes into a record, so a
    registry version and a ledger version are the same string or a genuine
    disagreement — never two conventions that merely look different.
    """
    return _module_version(importlib.import_module(module_path))


# ---------------------------------------------------------------------- spec


@dataclasses.dataclass(frozen=True)
class ModelSpec:
    """What one predictive component is, and what it is allowed to do.

    `record_key` is the key this component appears under in
    `ForecastRecord.model_predictions`; `version_key` is the entry of
    `model_versions` that carries its version.  Both are `None` for components
    that never reach the ledger, which is itself a statement: an
    EXPERIMENTAL or RETIRED model with no `record_key` cannot appear in a
    frozen forecast at all.
    """

    model_id: str
    label: str
    family: str
    implementation: str
    target: str
    horizons: tuple[str, ...]
    required_features: tuple[str, ...]
    training_cutoff: str
    retraining_policy: str
    pit_status: str
    production_status: str
    output_kind: str
    score_class: str
    version_module: str | None = None
    frozen_version: str | None = None
    record_key: str | None = None
    version_key: str | None = None
    source_path: str | None = None
    optional_features: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if (self.version_module is None) == (self.frozen_version is None):
            raise ValueError(
                f"{self.model_id}: set exactly one of version_module or frozen_version"
            )
        if self.production_status not in STATUSES:
            raise ValueError(f"{self.model_id}: unknown status {self.production_status}")
        if self.score_class not in METRICS_BY_SCORE_CLASS:
            raise ValueError(f"{self.model_id}: unknown score class {self.score_class}")
        if self.pit_status not in {
            PIT_ADMISSIBLE, PIT_CONDITIONAL, PIT_INADMISSIBLE, PIT_NOT_APPLICABLE
        }:
            raise ValueError(f"{self.model_id}: unknown PIT status {self.pit_status}")
        if self.output_kind not in {SIGNAL_SCORE, RETURN_PCT, CROSS_SECTIONAL_SCORE}:
            raise ValueError(f"{self.model_id}: unknown output kind {self.output_kind}")
        if self.record_key is not None and self.version_key is None:
            raise ValueError(
                f"{self.model_id}: a component that reaches the ledger must name "
                "the model_versions entry carrying its version"
            )
        # A model barred from production must not also claim a production path.
        if (self.production_status not in PRODUCTION_ADMISSIBLE
                and self.record_key is not None):
            raise ValueError(
                f"{self.model_id}: {self.production_status} models have no ledger key"
            )

    @property
    def version(self) -> str:
        """The exact implementation in use, or a frozen external identifier."""
        if self.frozen_version is not None:
            return self.frozen_version
        # __post_init__ guarantees exactly one of the two is set.
        return _source_version(str(self.version_module))

    @property
    def production_admissible(self) -> bool:
        return self.production_status in PRODUCTION_ADMISSIBLE

    @property
    def metrics(self) -> tuple[str, ...]:
        """`outcome_ledger.summarise` columns this model may be read on."""
        return METRICS_BY_SCORE_CLASS[self.score_class]

    def describe(self) -> dict[str, Any]:
        """A flat row for reports and for the Phase 8 leaderboard."""
        row = {field.name: getattr(self, field.name)
               for field in dataclasses.fields(self)}
        row["version"] = self.version
        return row


# ----------------------------------------------------------------- inventory


_CLOSED_FORM = "not applicable — closed form, no parameters fitted from data"
_NO_RETRAINING = "none — nothing is fitted, so nothing is refitted"

# Every technical source reads `close`.  `high`/`low` and `volume` are listed
# per source from the transitive column use of its implementation, and split
# into required and optional by what the code does when they are absent: ADX
# and OBV return NaN and go silent, while the rest substitute `close` and keep
# speaking.  See `indicators.true_range`, `directional_index`, `on_balance_volume`.
_TECHNICAL: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...], str], ...] = (
    ("trend_ma", "EMA 12/48 spread", TECHNICAL_INDICATOR,
     ("close",), ("high", "low"), "_trend_ma"),
    ("trend_slope", "EMA 50 slope", TECHNICAL_INDICATOR,
     ("close",), ("high", "low"), "_trend_slope"),
    ("macd", "MACD histogram", TECHNICAL_INDICATOR,
     ("close",), ("high", "low"), "_macd_histogram"),
    ("adx", "ADX direction", TECHNICAL_INDICATOR,
     ("close", "high", "low"), (), "_adx_direction"),
    ("rsi", "RSI 14", TECHNICAL_INDICATOR, ("close",), (), "_rsi_momentum"),
    ("roc", "20-bar return", TECHNICAL_INDICATOR, ("close",), (), "_rate_of_change"),
    ("bollinger", "Bollinger reversion", TECHNICAL_INDICATOR,
     ("close",), (), "_bollinger_reversion"),
    ("donchian", "Donchian position", TECHNICAL_INDICATOR,
     ("close",), ("high", "low"), "_donchian_position"),
    ("obv", "Volume trend", TECHNICAL_INDICATOR,
     ("close", "volume"), (), "_volume_trend"),
    ("structure", "Market structure", TECHNICAL_INDICATOR,
     ("close",), ("high", "low"), "_market_structure"),
    ("vwap_reversion", "VWAP reversion", TECHNICAL_INDICATOR,
     ("close", "volume"), ("high", "low"), "_vwap_reversion"),
    ("vix_reversion", "Vix Fix capitulation", TECHNICAL_INDICATOR,
     ("close",), ("low",), "_vix_reversion"),
    ("opening_range", "Opening range break", TECHNICAL_INDICATOR,
     ("close", "date"), ("high", "low"), "_opening_range"),
    ("pead", "Earnings drift", TECHNICAL_INDICATOR,
     ("sue", "days_since_filing"), (), "_pead_drift"),
)

#: Registry label -> (ledger key, implementation) for the three rule agents
#: that the Ultimate verdict actually folds in.  The labels are
#: `agents_audit.FAMILY_OF`'s, so the two inventories can be compared by name.
_RULE_AGENTS = (
    ("Turtle", "agent_turtle", "app/core/strategies.py::turtle"),
    ("Moving average crossover", "agent_crossover",
     "app/core/strategies.py::moving_average"),
    ("Signal rolling", "agent_rolling", "app/core/strategies.py::signal_rolling"),
)

_RULE_AGENT_NOTE = (
    "The app sizes this agent's windows as a percentage of whatever series is "
    "on screen (10% channel, 2.5%/5% moving averages), so its shape changes as "
    "history grows. `alpha/agents_audit.py` freezes the same proportions at 252 "
    "bars for study use. The registry records the app's live parameterisation; "
    "the frozen variant is a separate research object."
)


def _neural_slug(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _rl_slug(name: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", name.lower())).strip("_")


def _technical_specs(horizons: tuple[str, ...]) -> list[ModelSpec]:
    return [
        ModelSpec(
            model_id=f"technical.{key}",
            label=label,
            family=family,
            implementation=f"app/core/indicators.py::{function}",
            target="sign of the forward return over the horizon it is scored at",
            horizons=horizons,
            required_features=required,
            optional_features=optional,
            training_cutoff=_CLOSED_FORM,
            retraining_policy=_NO_RETRAINING,
            # Causal on the frame it is handed; historical use needs that frame
            # truncated first, which is `validation.pit.fetcher`'s job.
            pit_status=PIT_CONDITIONAL,
            production_status=PRODUCTION,
            output_kind=SIGNAL_SCORE,
            score_class=DIRECTIONAL_ONLY,
            version_module="app.core.indicators",
            record_key=key,
            version_key="technical_sources",
            evidence=("reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §3.3",),
        )
        for key, label, family, required, optional, function in _TECHNICAL
    ]


def _rule_agent_specs(horizons: tuple[str, ...]) -> list[ModelSpec]:
    return [
        ModelSpec(
            model_id=f"rule_agent.{key.removeprefix('agent_')}",
            label=label,
            family=RULE,
            implementation=implementation,
            target="standing position implied by the agent's last event, scored "
                   "on the sign of the forward return",
            horizons=horizons,
            required_features=("close",),
            training_cutoff=_CLOSED_FORM,
            retraining_policy=_NO_RETRAINING,
            pit_status=PIT_CONDITIONAL,
            production_status=PRODUCTION,
            output_kind=SIGNAL_SCORE,
            score_class=DIRECTIONAL_ONLY,
            version_module="app.core.strategies",
            record_key=key,
            version_key="rule_agents",
            evidence=("reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §3.4",
                      "alpha/agents_audit.py::rule_specs"),
            notes=_RULE_AGENT_NOTE,
        )
        for label, key, implementation in _RULE_AGENTS
    ]


def _pine_specs(horizons: tuple[str, ...]) -> list[ModelSpec]:
    """The seven ported TradingView studies, registered so they cannot drift.

    Registering them is a **lock, not a promotion**.  `EXPERIMENTAL` is the
    status a component carries when it is runnable but disqualified from
    production evidence, and `assert_record_admissible` refuses any record
    naming one — so the effect of this entry is that a Pine study *cannot*
    reach a production forecast without the refusal being explicit and visible.

    They are deliberately **not** in `indicators.SOURCES`.  `ultimate.evaluate`
    consumes that dict wholesale, so adding one would change the live
    incumbent's evidence set while the ensemble's version — the sha256 of
    `ultimate.py` — stayed put, and the prospective record would split across
    two engines wearing one version string.  Promotion to weighted evidence
    needs an owner decision and a pre-registration amendment, not an import.
    """
    from . import pine

    return [
        ModelSpec(
            model_id=f"pine.{key}",
            label=indicator.name,
            family=PINE_STUDY,
            implementation=f"app/core/pine.py::signals (study={key!r})",
            target="sign of the forward return over the horizon it is scored "
                   "at; the study's own published trading rule, read as a "
                   "standing position",
            horizons=horizons,
            required_features=indicator.requires,
            training_cutoff=_CLOSED_FORM,
            retraining_policy=_NO_RETRAINING,
            # Causal on the frame it is handed; historical use needs that frame
            # truncated first, exactly as for the technical sources.
            pit_status=PIT_CONDITIONAL,
            production_status=EXPERIMENTAL,
            output_kind=SIGNAL_SCORE,
            score_class=DIRECTIONAL_ONLY,
            version_module="app.core.pine",
            # No `record_key`, and the registry enforces that rather than
            # trusting it: a status outside PRODUCTION_ADMISSIBLE may not also
            # name a ledger path. A Pine study has no route into a frozen
            # forecast, and this is where that is made structural.
            evidence=("app/core/pine.py",
                      "alpha/HT1_TOURNAMENT_PREREGISTRATION.md §4.1"),
            notes="Chart furniture, and measured as a candidate by HT-1. "
                  "EXPERIMENTAL for standing, not for a measured result: it "
                  "has never held production weight and this entry does not "
                  "give it any.",
        )
        for key, indicator in pine.INDICATORS.items()
    ]


def _neural_specs(model_names: Iterable[str]) -> list[ModelSpec]:
    """The forward projection only.  `forecast.run` is registered separately."""
    return [
        ModelSpec(
            model_id=f"neural.{_neural_slug(name)}",
            label=f"{name} forward projection",
            family=NEURAL_SEQUENCE,
            implementation=f"app/core/forecast.py::project (model={name!r})",
            target="close-to-close % move from the last observed bar to the "
                   "end of the projected path",
            # Braced entries are patterns resolved per forecast: the ledger
            # freezes the concrete `<steps>x<interval>` horizon on the record.
            horizons=("{steps}x{interval}",),
            required_features=("close",),
            training_cutoff="the last bar of the input frame; frozen per "
                            "forecast at metadata.training.training_last_bar",
            retraining_policy="retrained from scratch whenever the UI "
                              "fingerprint changes; no checkpoint is persisted "
                              "and no promotion rule exists yet (Phase 7)",
            pit_status=PIT_ADMISSIBLE,
            production_status=CHALLENGER,
            output_kind=RETURN_PCT,
            score_class=RETURN_AND_DIRECTIONAL,
            version_module="app.core.forecast",
            record_key="model",
            version_key="neural_challenger",
            source_path="app.core.forecast.project",
            evidence=("reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §3.5, §7.3",
                      "reports/V5_PHASE1_FORECAST_LEDGER.md"),
            notes="Its own credibility comes from `forecast.walk_forward`, "
                  "which measures the same architecture on windows it did not "
                  "see. The projection itself carries no accuracy.",
        )
        for name in model_names
    ]


def _rl_specs(registry: Mapping[str, Any]) -> list[ModelSpec]:
    """Built from `agents.REGISTRY` so the census is a count, not a selection."""
    specs = []
    for name, klass in registry.items():
        module = klass.__module__.rsplit(".", 1)[-1]
        specs.append(ModelSpec(
            model_id=f"rl.{_rl_slug(name)}",
            label=name,
            family=_RL_FAMILY_BY_MODULE[module],
            implementation=f"app/core/agents/{module}.py::{klass.__name__}",
            target="per-bar trade action; `signals()` emits +1/-1/0 with SELL "
                   "gated on inventory",
            horizons=(),
            required_features=("close",),
            training_cutoff="none — `train()` optimises over the WHOLE series "
                            "the agent was constructed with, and the trained "
                            "policy is then replayed from bar zero",
            retraining_policy="user-triggered only; no checkpoint is written "
                              "or reloaded, so no version survives the session",
            pit_status=PIT_INADMISSIBLE,
            production_status=EXPERIMENTAL,
            output_kind=SIGNAL_SCORE,
            score_class=DIRECTIONAL_ONLY,
            version_module=klass.__module__,
            evidence=("alpha/agents_audit.py::rl_specs",
                      "reports/AGENT_META_AUDIT.md",
                      "reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §4.3, §7.4"),
            notes="EXPERIMENTAL for a point-in-time defect, not for a measured "
                  "result: same-series training and replay is the construction "
                  "the repository's own audit rules inadmissible. Its score "
                  "class records that a stance is directionally scoreable in "
                  "principle — it does not license using one.",
        ))
    return specs


def _ensemble_spec(horizons: tuple[str, ...]) -> ModelSpec:
    return ModelSpec(
        model_id=ULTIMATE_ENSEMBLE,
        label="Ultimate consensus",
        family=ENSEMBLE,
        implementation="app/core/ultimate.py::evaluate",
        target="expected % move over the horizon, as horizon score x median "
               "absolute historical move",
        horizons=horizons,
        required_features=("close",),
        optional_features=("high", "low", "volume"),
        training_cutoff="no trained parameters; source weights are re-derived "
                        "from the tail holdout of each input frame at every "
                        "evaluation, so the effective cutoff is the frame's "
                        "last bar",
        retraining_policy="recomputed on every evaluation. No versioned "
                          "artefact, no promotion or rollback rule (Phase 7). "
                          "Historical weights are therefore reconstructed, not "
                          "remembered — Phase 0 severity 3",
        pit_status=PIT_CONDITIONAL,
        production_status=PRODUCTION,
        output_kind=RETURN_PCT,
        score_class=RETURN_AND_DIRECTIONAL,
        version_module="app.core.ultimate",
        record_key="ensemble",
        version_key="ultimate_ensemble",
        source_path="app.core.ultimate.evaluate",
        evidence=("reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §3.2, §3.6",
                  "reports/V5_PHASE1_FORECAST_LEDGER.md"),
        notes="`confidence` is an evidence-strength gate, not a probability. "
              "`probability_positive` stays null until a calibrated probability "
              "exists; confidence must never be substituted for one.",
    )


#: Isolated or retired paths.  Retirement means "not callable by V5 production
#: or scoring", never deletion of historical research material.
_RETIRED: tuple[ModelSpec, ...] = (
    ModelSpec(
        model_id="retired.forecast_single_split",
        label="Single-split recurrent forecast",
        family=NEURAL_SEQUENCE,
        implementation="app/core/forecast.py::run",
        target="reconstruction of a window that already exists",
        horizons=(),
        required_features=("close",),
        training_cutoff="none — the scaler is fitted on the whole series, "
                        "including the held-out window",
        retraining_policy="none — retained for notebook compatibility only",
        pit_status=PIT_INADMISSIBLE,
        production_status=RETIRED,
        output_kind=RETURN_PCT,
        score_class=NOT_SCOREABLE_HERE,
        version_module="app.core.forecast",
        evidence=("reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §7.3, severity 7",),
        notes="Reachable from the UI as a chart. Its single-split metrics are "
              "not production evidence and Phase 1 refuses to freeze them.",
    ),
    ModelSpec(
        model_id="retired.realtime_flask_agent",
        label="Standalone realtime Flask trader",
        family=EVOLUTIONARY,
        implementation="realtime-agent/app.py",
        target="live trade actions from a pickled evolution-strategy policy",
        horizons=(),
        required_features=("close",),
        training_cutoff="unknown — loads model.pkl with no recorded provenance",
        retraining_policy="none",
        pit_status=PIT_INADMISSIBLE,
        production_status=RETIRED,
        output_kind=SIGNAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="external:realtime-agent/app.py",
        evidence=("reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §13.2, severity 8",),
        notes="Independent of the Streamlit application and of this registry. "
              "Not part of the V5 execution graph.",
    ),
    ModelSpec(
        model_id="retired.stacking",
        label="TensorFlow stacking experiments",
        family=CROSS_SECTIONAL_ML,
        implementation="stacking/model.py",
        target="stacked ensemble of notebook forecasters",
        horizons=(),
        required_features=("close",),
        training_cutoff="unknown",
        retraining_policy="none",
        pit_status=PIT_INADMISSIBLE,
        production_status=RETIRED,
        output_kind=CROSS_SECTIONAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="external:stacking/model.py",
        evidence=("reports/V5_PHASE0_ARCHITECTURE_AUDIT.md §13.2",),
        notes="Isolated from V5 until explicitly admitted through this registry.",
    ),
)


#: Closed research programmes, registered at programme granularity.  Each entry
#: exists so that a later phase cannot reintroduce a refused design as new work
#: — `assert_not_reopened` is the check, and CLAUDE.md §1.3 is the rule.  No
#: number here was recomputed by this module; every one is quoted from the
#: append-only record named in `evidence`.
_CLOSED: tuple[ModelSpec, ...] = (
    ModelSpec(
        model_id="closed.v2_v2_3_cross_sectional",
        label="V2 -> V2.3 cross-sectional feature programme (13 arms)",
        family=CROSS_SECTIONAL_ML,
        implementation="alpha/models.py::MODEL_A_PARAMS + alpha/features.py",
        target="cross-sectional 5-session forward return / rank",
        horizons=("5d",),
        required_features=("point-in-time index membership panel, 100 features",),
        training_cutoff="expanding walk-forward, first refit 2017-03-21, last "
                        "refit 2026-05-21",
        retraining_policy="none — architecture ABANDONED, production weight 0",
        pit_status=PIT_ADMISSIBLE,
        production_status=REJECTED,
        output_kind=CROSS_SECTIONAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="closed:V2-A,V2-B,V2-E,V2-F,V2.1-A..D,V2.2-A..C,V2.3-A,V2.3-B",
        evidence=("reports/EXPERIMENT_REGISTRY.md §2, §3",
                  "reports/V2_3_POST_MORTEM.md"),
        notes="CLOSED. No entry may be reopened, re-tested with a larger model, "
              "a different learner, a different target, another horizon, or "
              "another carrier.",
    ),
    ModelSpec(
        model_id="closed.pit1_single_name",
        label="PIT-1 single-name point-in-time backtest (9 components)",
        family=ENSEMBLE,
        implementation="validation/",
        target="single-name directional call at a frozen cutoff",
        horizons=(),
        required_features=("close",),
        training_cutoff="12 frozen cutoffs",
        retraining_policy="none — REJECTED",
        pit_status=PIT_ADMISSIBLE,
        production_status=REJECTED,
        output_kind=SIGNAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="closed:PIT-1",
        evidence=("reports/EXPERIMENT_REGISTRY.md §2",
                  "reports/SINGLE_NAME_PHASE1.md"),
        notes="0 of 9 components beat always-up, unanimous sign. This is the "
              "closest prior result to V5's own object and Phase 4 must treat "
              "it as the prior, not as a fresh question.",
    ),
    ModelSpec(
        model_id="closed.v3_family_programme",
        label="V3 information-family programme (3 families, 3 arms)",
        family=CROSS_SECTIONAL_ML,
        implementation="alpha/ladder*.py + alpha/filings_features.py",
        target="cross-sectional 5-session alpha, B3 carrier + 0.25 tilt",
        horizons=("5d",),
        required_features=("SUE / Form 4 / 13F filing panels",),
        training_cutoff="development window ending 2026-08-09",
        retraining_policy="none — 3 of 3 slots spent, programme CLOSED under §21",
        pit_status=PIT_ADMISSIBLE,
        production_status=REJECTED,
        output_kind=CROSS_SECTIONAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="closed:V3-1,V3-2,V3-3",
        evidence=("reports/EXPERIMENT_REGISTRY.md §6, §7, §8",
                  "reports/PROGRESS_V3.md"),
        notes="All three REJECTED. No Family 1'/2'/3', no fourth family, no "
              "re-test at another horizon and no sign flip.",
    ),
    ModelSpec(
        model_id="closed.v4_sue",
        label="V4-SUE earnings-surprise programme",
        family=CROSS_SECTIONAL_ML,
        implementation="alpha/filings_features.py (SUE)",
        target="cross-sectional alpha, B3 carrier + SUE tilt",
        horizons=("5d", "20d"),
        required_features=("point-in-time reported fundamentals",),
        training_cutoff="development window ending 2026-08-10",
        retraining_policy="none — Slot 1 SPENT, Slot 2 BARRED, V4 CLOSED",
        pit_status=PIT_ADMISSIBLE,
        production_status=REJECTED,
        output_kind=CROSS_SECTIONAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="closed:V4-1",
        evidence=("reports/PROGRESS_V4.md", "reports/V4_SUE_POWER_GATE.md",
                  "reports/EXPERIMENT_REGISTRY.md §8"),
        notes="Its §6 power gate PASSED and the study still REJECTED — rejected "
              "at every horizon tested. Slot 2 is barred and unspent.",
    ),
    ModelSpec(
        model_id="closed.ams1_agent_meta",
        label="AMS-1 cross-family trading-agent consensus",
        family=ENSEMBLE,
        implementation="alpha/ams1_run.py, alpha/ams1_score.py",
        target="single-name 5-session direction from agreement across agent "
               "families",
        horizons=("5d",),
        required_features=("close",),
        training_cutoff="development set only; the sealed exam was not loaded",
        retraining_policy="none — REJECTED, no information-family slot spent",
        pit_status=PIT_ADMISSIBLE,
        production_status=REJECTED,
        output_kind=SIGNAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="closed:AMS-1",
        evidence=("reports/AGENT_META_SIGNAL_RESULT.md",
                  "reports/AGENT_META_AUDIT.md"),
        notes="The direction was the opposite of the hypothesis: P(up) is "
              "perfectly monotone downwards across consensus states. Any Phase "
              "5 proposal to weight by agent agreement reopens this.",
    ),
    ModelSpec(
        model_id="blocked.family10_material_events",
        label="Family 10 8-K material events",
        family=CROSS_SECTIONAL_ML,
        implementation="not implemented — pilot only",
        target="cross-sectional alpha from 8-K material-event items",
        horizons=("5d",),
        required_features=("SEC 8-K item panel",),
        training_cutoff="not run",
        retraining_policy="none — admissibility FAIL on power; family slot NOT spent",
        pit_status=PIT_ADMISSIBLE,
        production_status=REJECTED,
        output_kind=CROSS_SECTIONAL_SCORE,
        score_class=NOT_SCOREABLE_HERE,
        frozen_version="blocked:FAMILY10",
        evidence=("reports/FAMILY10_ADMISSIBILITY.md",
                  "reports/FAMILY10_STAGE3_POWER.md"),
        notes="Blocked before measurement by its own pre-registered power gate. "
              "A failed gate is a result: the family is not implemented, and "
              "the design is not resurrected at a different block length.",
    ),
)


@functools.lru_cache(maxsize=1)
def _specs() -> tuple[ModelSpec, ...]:
    """Build the census once.

    Lazily, because `app.core.agents` imports nineteen agent classes and costs
    about two seconds — a price the ledger and the scoring path should not pay
    at import time.
    """
    from . import agents, forecast, ultimate

    horizons = tuple(horizon.key for horizon in ultimate.HORIZONS)
    return (
        _ensemble_spec(horizons),
        *_technical_specs(horizons),
        *_pine_specs(horizons),
        *_rule_agent_specs(horizons),
        *_neural_specs(forecast.MODELS),
        *_rl_specs(agents.REGISTRY),
        *_RETIRED,
        *_CLOSED,
    )


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, ModelSpec]:
    index: dict[str, ModelSpec] = {}
    for spec in _specs():
        if spec.model_id in index:
            raise ModelRegistryError(f"duplicate model id: {spec.model_id}")
        index[spec.model_id] = spec
    return index


def specs() -> tuple[ModelSpec, ...]:
    """Every registered component, in inventory order."""
    return _specs()


def get(model_id: str) -> ModelSpec:
    try:
        return _index()[model_id]
    except KeyError:
        raise UnregisteredModelError(f"no registered model {model_id!r}") from None


def by_status(status: str) -> tuple[ModelSpec, ...]:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    return tuple(spec for spec in _specs() if spec.production_status == status)


def production_models() -> tuple[ModelSpec, ...]:
    return by_status(PRODUCTION)


def table() -> list[dict[str, Any]]:
    """The whole registry as rows — for reports and the Phase 8 UI."""
    return [spec.describe() for spec in _specs()]


# ---------------------------------------------------------- record resolution


@functools.lru_cache(maxsize=1)
def _by_record_key() -> dict[str, tuple[ModelSpec, ...]]:
    index: dict[str, list[ModelSpec]] = {}
    for spec in _specs():
        if spec.record_key is not None:
            index.setdefault(spec.record_key, []).append(spec)
    return {key: tuple(value) for key, value in index.items()}


def _disambiguate_neural(candidates: tuple[ModelSpec, ...],
                         prediction: Mapping[str, Any] | None) -> ModelSpec:
    """Pick which recurrent architecture produced a prediction, by its name.

    `ultimate.ModelEvidence` labels itself "LSTM forecast" while
    `forecast.Projection` carries the bare "LSTM", so the suffix is stripped
    before matching.  An unrecognised name raises rather than falling back:
    the point of the registry is that an unknown model is loud.
    """
    if prediction is None:
        raise UnregisteredModelError(
            "resolving a neural constituent needs its prediction payload"
        )
    name = str(prediction.get("name", "")).strip()
    slug = _neural_slug(name.removesuffix("forecast").strip())
    for candidate in candidates:
        if candidate.model_id == f"neural.{slug}":
            return candidate
    raise UnregisteredModelError(f"unregistered neural model name: {name!r}")


def resolve_constituent(
    key: str, prediction: Mapping[str, Any] | None = None,
) -> ModelSpec:
    """The registered model behind one `model_predictions` entry."""
    candidates = _by_record_key().get(key)
    if not candidates:
        raise UnregisteredModelError(
            f"forecast constituent {key!r} is not a registered model"
        )
    if len(candidates) == 1:
        return candidates[0]
    return _disambiguate_neural(candidates, prediction)


def _version_key(spec: ModelSpec) -> str:
    """Which `model_versions` entry carries this model's version."""
    if spec.version_key is None:
        raise ModelVersionError(
            f"{spec.model_id} does not appear in the forecast ledger, so it "
            "carries no recorded version"
        )
    return spec.version_key


def record_spec(record: ForecastRecord) -> ModelSpec:
    """The model a whole frozen forecast is attributed to.

    Dispatch is on `source_path`, the field Phase 1 froze to say which call
    produced the record — not on the status word, which says what the record
    claims rather than what made it.
    """
    candidates = tuple(
        spec for spec in _specs() if spec.source_path == record.source_path
    )
    if not candidates:
        raise UnregisteredModelError(
            f"no registered model produces {record.source_path!r}"
        )
    if len(candidates) == 1:
        return candidates[0]
    return _disambiguate_neural(candidates, record.model_predictions.get("model"))


def record_version(record: ForecastRecord) -> str:
    """The version the record itself declares for the model that made it."""
    spec = record_spec(record)
    version = record.model_versions.get(_version_key(spec))
    if not version:
        raise ModelVersionError(
            f"{record.forecast_id} does not declare a version for {spec.model_id}"
        )
    return str(version)


def constituent_ids(record: ForecastRecord) -> dict[str, str]:
    """`model_predictions` key -> registered model id, for every constituent."""
    return {
        key: resolve_constituent(
            key, prediction if isinstance(prediction, Mapping) else None
        ).model_id
        for key, prediction in record.model_predictions.items()
    }


def resolve_versions(record: ForecastRecord) -> dict[str, str]:
    """Registered model id -> the version this record declares for it.

    Raises when a constituent's version is absent: a forecast whose output
    cannot be traced to a version is not evidence about a model.
    """
    versions: dict[str, str] = {}
    for key, prediction in record.model_predictions.items():
        spec = resolve_constituent(
            key, prediction if isinstance(prediction, Mapping) else None
        )
        version_key = _version_key(spec)
        declared = record.model_versions.get(version_key)
        if not declared:
            raise ModelVersionError(
                f"{record.forecast_id} does not identify a version for "
                f"{spec.model_id} (expected model_versions[{version_key!r}])"
            )
        versions[spec.model_id] = str(declared)
    return versions


def version_drift(record: ForecastRecord) -> dict[str, tuple[str, str]]:
    """Models whose recorded version differs from the code in use now.

    A diagnostic, never a gate.  An old record *should* disagree with today's
    source; that is what versioning is for.  Phase 4 uses this to decide which
    records are comparable, not to reject them.
    """
    drift = {}
    for model_id, recorded in resolve_versions(record).items():
        current = get(model_id).version
        if recorded != current:
            drift[model_id] = (recorded, current)
    return drift


# ------------------------------------------------------------------- guards


def assert_production_admissible(model_id: str) -> ModelSpec:
    """Refuse a model that has no standing to influence a production forecast."""
    spec = get(model_id)
    if not spec.production_admissible:
        raise RejectedModelError(
            f"{spec.model_id} is {spec.production_status} and may not affect "
            f"production. Evidence: {', '.join(spec.evidence) or 'see registry'}"
        )
    return spec


def assert_not_reopened(model_id: str) -> None:
    """Refuse to treat a closed programme's design as new work.

    CLAUDE.md §1.3: closed programmes stay closed.  This is the callable form
    of that rule, so a later phase that tries to route a rejected design back
    into production fails instead of arguing.
    """
    spec = get(model_id)
    if spec.production_status == REJECTED:
        raise RejectedModelError(
            f"{spec.model_id} was REJECTED and is closed: {spec.notes} "
            f"Evidence: {', '.join(spec.evidence)}"
        )


def assert_record_admissible(record: ForecastRecord) -> ModelSpec:
    """Every model behind this frozen forecast has standing and a version.

    Three failures are possible and all three are loud:

    1. the record was produced by something unregistered,
    2. it claims a status its own model does not hold,
    3. one of its constituents is EXPERIMENTAL, REJECTED or RETIRED.

    (3) is the one that matters: it is what stops a same-series RL stance or a
    refused research arm from reaching a production verdict unnoticed.
    """
    owner = record_spec(record)
    expected = {
        RECORD_PRODUCTION_INCUMBENT: PRODUCTION,
        RECORD_CHALLENGER: CHALLENGER,
    }.get(record.production_or_challenger)
    if expected is None:
        raise ModelRegistryError(
            f"unknown record status {record.production_or_challenger!r}"
        )
    if owner.production_status != expected:
        raise RejectedModelError(
            f"{record.forecast_id} is filed as {record.production_or_challenger} "
            f"but {owner.model_id} is {owner.production_status}"
        )
    for key, model_id in constituent_ids(record).items():
        spec = get(model_id)
        if not spec.production_admissible:
            raise RejectedModelError(
                f"{record.forecast_id} constituent {key!r} resolves to "
                f"{spec.model_id}, which is {spec.production_status} and has no "
                "production standing"
            )
    resolve_versions(record)  # raises unless every output identifies a version
    return owner
