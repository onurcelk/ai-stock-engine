# V5 Phase 3 Unified Model Registry

**Date:** 2026-08-14
**Phase:** PHASE 3 — Unified Model Registry
**Decision:** GO
**Implementation:** `app/core/model_registry.py`, `app/tests/test_model_registry.py`
**Touched:** `app/core/outcome_ledger.py` (`model_key` identity, one added column)

---

## 1. Result

**GO.**

Forty-five predictive components are now registered, each with a declared
identity, version, family, target, horizon set, required features, training
cutoff, retraining policy, point-in-time status and production status. Fourteen
carry production authority, three are challengers, nineteen are barred as
experimental for a point-in-time defect, three are retired from the V5
execution graph, and six closed research programmes are registered as rejected
so they cannot be reopened as new work.

The gate — *model outputs can be compared under one scoring framework* — is met
in the strict sense rather than the descriptive one. Every registered model
declares an `output_kind` and a `score_class`, and `METRICS_BY_SCORE_CLASS`
maps each score class onto the exact `outcome_ledger.summarise` columns it may
be read on. The production ensemble and the neural challenger both emit
`return_pct`, so both admit the same five metrics and can be ranked against one
another. Signal-only constituents admit a strict subset — directional accuracy
alone — which is a declared limit rather than a silent one.

The full fast suite passed with **904 passed, 63 skipped**: the 876-pass Phase 2
baseline plus 28 new tests, with nothing weakened and no existing assertion
relaxed.

---

## 2. What the Registry Is For

Phase 1 froze what a forecast said. Phase 2 scored it. Neither could say what
made it.

A frozen `ForecastRecord` stores a constituent's output under a bare key such as
`trend_ma`, and `outcome_ledger.model_key` attributed every incumbent horizon to
the placeholder string `ultimate_ensemble`. There was no object that knew
`trend_ma` is a production technical source, that `Q-learning` may never reach a
production verdict, or that the V2.3 carrier was refused and closed. Those facts
lived in prose across four reports and one audit module.

Phase 3 makes them a data structure with tests attached.

### 2.1 Authorisation for the one behavioural change

`outcome_ledger.model_key` now returns registry identity instead of the
placeholder string. This is not a silent methodology change: the Phase 2
completion record instructed it in terms — *"`model_key()` in `outcome_ledger`
is a placeholder identity that Phase 3 should replace with real registry
identity; keep the scoring API stable when it does."*

The API is stable. `model_key(record) -> str` keeps its signature; every
Phase 2 function keeps its behaviour; the only additions are a `model_version`
column on `performance_frame` and a different string in `model_key`. No target,
feature, model parameter, exam set, walk-forward or point-in-time module was
touched, so no preregistration amendment is required under §1.2.

---

## 3. Common Interface

Every component is described by one frozen `ModelSpec`. The fields Phase 3
required, plus the ones the ledger needs to resolve a record:

| Field | Meaning |
|---|---|
| `model_id` | Stable identity. Survives retraining. |
| `label` | Canonical name. Matches `agents_audit.FAMILY_OF` where that inventory covers the model. |
| `family` | Architecture, never performance. `A_RULE`–`F_CURIOSITY_RL` are the agent audit's frozen taxonomy; `G`–`J` extend it. |
| `implementation` | The exact callable. |
| `version` | sha256 of the source in use, or a frozen external identifier for closed work. |
| `training_cutoff` | Where the cutoff comes from. Concrete values are per-forecast and live on the record. |
| `target` | What the model claims to predict. |
| `horizons` | Horizon keys. A `{braced}` entry is a pattern resolved per forecast. |
| `required_features` / `optional_features` | Split by what the code does when a column is absent. |
| `retraining_policy` | What triggers a refit, and what is persisted. |
| `pit_status` | `PIT-ADMISSIBLE` / `PIT-CONDITIONAL` / `PIT-INADMISSIBLE` / `PIT-NOT-APPLICABLE`. |
| `production_status` | `PRODUCTION` / `CHALLENGER` / `EXPERIMENTAL` / `REJECTED` / `RETIRED`. |
| `output_kind` | `signal_score` / `return_pct` / `cross_sectional_score`. |
| `score_class` | Which metrics the model may be read on. |
| `record_key` | The `model_predictions` key it appears under, or `None` if it never reaches the ledger. |
| `version_key` | The `model_versions` entry carrying its version. |
| `source_path` | The call that produces a whole record, for the two models that produce one. |
| `evidence` | Where the standing comes from. |

`ModelSpec.__post_init__` refuses the shape that would let a barred model into
a forecast: a spec whose status is not production-admissible may not declare a
`record_key`. That is checked at construction, not at use.

### 3.1 Two output kinds, one framework

The honest difficulty is that constituents do not all predict the same object.
A technical source emits a unitless stance in `[-1, 1]`; the ensemble and the
neural projection emit a percentage move. Collapsing those into one number would
have manufactured comparability rather than establishing it.

`METRICS_BY_SCORE_CLASS` states the resolution instead:

| Score class | Admissible metrics |
|---|---|
| `RETURN_AND_DIRECTIONAL` | `directional_accuracy`, `mae`, `rmse`, `mae_skill`, `mae_advantage` |
| `DIRECTIONAL_ONLY` | `directional_accuracy` |
| `NOT_SCOREABLE_HERE` | none — belongs to the alpha panel, not the forecast ledger |

One framework, two admissible metric sets, declared per model.
`test_declared_metrics_exist_in_the_phase_2_summary` runs a real frozen
forecast through Phase 2 and asserts every declared column actually exists.

---

## 4. Inventory

### 4.1 Production — 14

The incumbent ensemble and its constituents.

| Model | Family | Output | PIT |
|---|---|---|---|
| `ensemble.ultimate` | `H_ENSEMBLE` | `return_pct` | `PIT-CONDITIONAL` |
| `technical.trend_ma` · `trend_slope` · `macd` · `adx` · `rsi` · `roc` · `bollinger` · `donchian` · `obv` · `structure` | `G_TECHNICAL` | `signal_score` | `PIT-CONDITIONAL` |
| `rule_agent.turtle` · `crossover` · `rolling` | `A_RULE` | `signal_score` | `PIT-CONDITIONAL` |

`PIT-CONDITIONAL` is the accurate status and it is not a euphemism: these
components are causal on the frame they are handed, but they carry no cutoff
contract of their own. Historical use is safe only through
`validation.pit.fetcher`, which truncates before the frame arrives.

Required features are recorded from the transitive column use of each
implementation, and split by what the code does when a column is absent. ADX and
OBV return NaN and fall silent without `high`/`low` and `volume` respectively,
so those are required; the rest substitute `close` and keep speaking, so theirs
are optional. Nothing here was assumed from the indicator's name.

The three rule agents carry a standing note: the app sizes their windows as a
percentage of whatever series is on screen, so their shape changes as history
grows, while `alpha/agents_audit.py` freezes the same proportions at 252 bars
for study use. The registry records the app's live parameterisation and names
the frozen variant as a separate research object.

### 4.2 Challengers — 3

| Model | Family | Output | PIT |
|---|---|---|---|
| `neural.lstm` · `neural.gru` · `neural.vanilla_rnn` | `I_NEURAL_SEQUENCE` | `return_pct` | `PIT-ADMISSIBLE` |

`forecast.project` only. Every input is available at forecast time, which is
why these are the one family with an unqualified `PIT-ADMISSIBLE`. Their
credibility comes from `forecast.walk_forward`, which measures the same
architecture on windows it did not see; the projection itself carries no
accuracy.

They are `CHALLENGER`, and `PRODUCTION_ADMISSIBLE` deliberately includes
`CHALLENGER`: the neural evidence is already folded into the incumbent verdict
when the user enables it, and Phase 1 forces that record to declare the
challenger's version. Barring it would have made the guard describe a system
that does not exist.

### 4.3 Experimental — 19

All nineteen trainable agents in `agents.REGISTRY`, across five families
(`B_VALUE_RL` ×8, `C_ACTOR_CRITIC` ×4, `E_EVOLUTIONARY` ×3,
`F_CURIOSITY_RL` ×3, `D_POLICY_GRADIENT` ×1).

**Phase 3 asked for an inventory of admissible RL models. There are none.**

Every one is `PIT-INADMISSIBLE`, and for a structural reason rather than a
measured one: `train()` optimises over the whole series the agent was
constructed with, and the trained policy is then replayed from bar zero. That
is the construction the repository's own agent audit rules inadmissible. No RL
agent declares a `record_key`, so none can appear in a frozen forecast at all.

Their `score_class` records that a stance is directionally scoreable in
principle. It does not license using one.

### 4.4 Retired — 3

| Model | Why |
|---|---|
| `retired.forecast_single_split` (`forecast.run`) | Fits its scaler on the whole series including the held-out window. Reachable from the UI as a chart; Phase 1 refuses to freeze it. |
| `retired.realtime_flask_agent` | Standalone Flask trader, loads `model.pkl` with no recorded provenance. |
| `retired.stacking` | Separate TensorFlow experiments, isolated until explicitly admitted through this registry. |

Retirement means *not callable by V5 production or scoring*. It is not deletion
of historical research material.

### 4.5 Rejected — 6 closed programmes

Registered at programme granularity, with every number quoted from the
append-only record rather than recomputed here.

| Model | Standing |
|---|---|
| `closed.v2_v2_3_cross_sectional` | 13 arms. Architecture ABANDONED, production weight 0, action HOLD. |
| `closed.pit1_single_name` | 0 of 9 components beat always-up, unanimous sign. |
| `closed.v3_family_programme` | 3 of 3 families REJECTED, 3 of 3 slots spent, CLOSED under §21. |
| `closed.v4_sue` | §6 power gate PASSED and the study still REJECTED. Slot 1 spent, Slot 2 barred, V4 CLOSED. |
| `closed.ams1_agent_meta` | REJECT, and the direction was the opposite of the hypothesis. |
| `blocked.family10_material_events` | Admissibility FAIL on power. Not implemented, slot NOT spent. |

`closed.pit1_single_name` deserves emphasis for Phase 4. It is the closest prior
result to V5's own object — single-name point-in-time direction — and it
refused all nine components against always-up. Phase 4 must treat it as the
prior, not as a fresh question.

`closed.ams1_agent_meta` constrains Phase 5 directly: any proposal to weight by
cross-family agent agreement reopens a refused result whose measured direction
was monotone in the wrong direction.

---

## 5. Preventing a Rejected Model From Affecting Production

Three mechanisms, in increasing strength.

**1. Construction.** A spec whose status is not production-admissible cannot
declare a `record_key`. There is no shape in which a rejected model has a
ledger identity.

**2. `assert_not_reopened(model_id)`.** The callable form of CLAUDE.md §1.3.
It raises for every `REJECTED` entry, quoting the notes and the evidence, so a
later phase that routes a closed design back toward production fails instead of
arguing.

**3. `assert_record_admissible(record)`.** The one that matters. Given a frozen
forecast it resolves the record's owner by `source_path`, checks the record's
declared status against the owner's registered status, resolves every
constituent, and refuses if any is `EXPERIMENTAL`, `REJECTED` or `RETIRED`. It
then calls `resolve_versions`, which raises unless every constituent's version
is present on the record.

`test_a_rejected_model_cannot_reach_a_production_forecast` folds a same-series
RL stance into a real frozen production record under a new constituent key. The
registry does not know it, and the record is refused rather than scored as if
the incumbent had said it. The failure is `UnregisteredModelError`, which is the
intended behaviour for anything unknown: a model the registry has never seen is
loud, not permitted.

---

## 6. Identity, Version, and Drift

`model_id` is stable across retraining. `version` is the sha256 of the exact
source in use — the same `_module_version` string Phase 1 already freezes into
`ForecastRecord.model_versions`, deliberately the same function so that a
registry version and a ledger version are either the same string or a genuine
disagreement, never two conventions that merely look different.

`version_key` names which `model_versions` entry carries a component's version:
`technical_sources`, `rule_agents`, `ultimate_ensemble`, `neural_challenger`.
That is what makes *"ensure every output identifies model version"* checkable:
`resolve_versions(record)` returns `{model_id: version}` for every constituent
and raises when one is missing.
`test_every_constituent_output_identifies_its_version` asserts it on a real
frozen record; `test_a_forecast_that_hides_a_version_is_refused` asserts the
refusal.

`version_drift(record)` reports models whose recorded version differs from the
code in use now. It is a **diagnostic and never a gate**. An old record *should*
disagree with today's source — that is what versioning is for. Phase 4 uses
drift to decide which records are comparable, not to reject them, and
`test_version_drift_is_reported_and_never_gated` asserts a drifted record stays
admissible.

---

## 7. The Census Cannot Drift

The inventory is built from the application's own registries, not from a
hand-maintained list:

- neural specs from `forecast.MODELS`,
- RL specs from `agents.REGISTRY`, with family assigned from the implementing
  module,
- production horizons from `ultimate.HORIZONS`.

Four tests close the remaining gaps. `test_every_technical_source_is_registered`
asserts the registered technical set equals `indicators.SOURCES` exactly;
`test_every_trainable_agent_is_registered` does the same for `agents.REGISTRY`;
`test_registered_horizons_match_the_production_engine` binds registry horizons
to the engine's; and `test_registry_families_agree_with_the_frozen_agent_audit`
asserts the reproduced taxonomy matches `alpha/agents_audit.FAMILY_OF` by name.

The families are copied rather than imported because `alpha` imports
`app.core`, and the dependency arrow must not point both ways. The test is what
keeps the two copies honest.

Adding a source to `indicators.SOURCES` without registering it now fails the
suite rather than quietly entering a production forecast.

---

## 8. Tests

28 new tests in `app/tests/test_model_registry.py`.

**Census — 6.** Technical sources, trainable agents, recurrent architectures,
production horizons, agreement with the frozen agent audit, identity
uniqueness.

**Metadata — 4.** Every spec declares the required fields; version is the exact
source in use; specs are frozen; a barred model cannot declare a ledger key.

**Statuses — 5.** Production is exactly the ensemble and its constituents; every
trainable agent is barred with a PIT reason; closed programmes are rejected with
evidence and refuse reopening; the leaky single-split forecaster is retired; an
unregistered model is never silently accepted.

**One scoring framework — 2.** Incumbent and challenger admit the same metrics
and signal-only constituents admit a strict subset; declared metrics exist as
real columns in the Phase 2 summary.

**Record resolution — 5.** A frozen incumbent resolves to registry identity; a
frozen challenger resolves to its architecture; every constituent identifies its
version; a forecast that hides a version is refused; drift is reported and never
gated.

**Guards — 5.** A clean production forecast is admissible; a challenger forecast
is admissible; a rejected model cannot reach a production forecast; a record
cannot claim a status its model does not hold; the guard names the evidence when
it refuses.

**Separation — 1.** The registry imports nothing from the outcome side, checked
on the import graph rather than the text, because the module's own docstring
explains what it replaced in `outcome_ledger`.

Suite: **904 passed, 63 skipped** (Phase 2 baseline 876 + 28).
`test_future_cannot_change_the_verdict` was run explicitly and passes.

---

## 9. Deliberate Limits

**No model was measured.** Phase 3 assigns standing from the existing record,
not from a new result. Every `EXPERIMENTAL` status here is a point-in-time
ruling; every `REJECTED` status quotes a prior gate. Nothing was promoted,
demoted, retired or reopened on the strength of a number computed in this phase.

**Model-assisted incumbent forecasts are not separated by identity.** A record
whose readings include neural evidence still resolves to `ensemble.ultimate`
and carries the ensemble's version, so it pools with pure technical forecasts
under the default grouping. `constituent_ids(record)` exposes the difference and
Phase 4 must use it when the distinction matters. Inventing a second ensemble
identity would have been a naming decision presented as a modelling one.

**Identity pools across versions by design.** `model_key` is the stable id; the
version is a separate `model_version` column. Phase 4 must decide explicitly
whether to group by identity or by identity and version, rather than inherit
whichever one a single key happened to encode.

**Rule-agent parameterisation is live, not frozen.** The registered windows are
the app's percentage-of-series sizing. The frozen 252-bar variant in
`agents_audit` is a different object and is named as such, not merged.

**`PIT-CONDITIONAL` is not `PIT-ADMISSIBLE`.** All fourteen production
components depend on the caller having truncated the frame. The registry
records that dependency; it does not enforce it. `validation.pit` remains the
only data door.

**Retirement is not deletion.** `retired.forecast_single_split` remains
reachable from the UI as a chart. The registry bars it from evidence; it does
not remove it from the application.

**No probability anywhere.** No registered model emits a calibrated
`probability_positive`, so the Brier and calibration columns Phase 2 built stay
empty. Confidence is not a probability and no registry field invites the
substitution.

---

## 10. Notes for Phase 4

1. `closed.pit1_single_name` is the prior for single-name direction. Nine
   components, zero beat always-up, unanimous sign. Phase 4's compact candidate
   set should be justified against that result, not against silence.
2. The strongest admissible candidates by registered standing are:
   `ensemble.ultimate` (production incumbent), the three `neural.*` challengers,
   and the trivial baselines Phase 2 already constructs
   (`zero_return`, `always_bullish`). **There is no admissible RL candidate** —
   Phase 4 should record that rather than manufacture one, and reopening the
   question means building a PIT-safe training protocol first, which is Phase 7
   work and not a Phase 4 shortcut.
3. Rank by `score_class`. Only `RETURN_AND_DIRECTIONAL` models may be compared
   on MAE or RMSE; the ten technical sources and three rule agents admit
   directional accuracy alone.
4. The Phase 2 interval caveat stands unchanged: Wilson and normal intervals
   are nominal and assume independent observations, which overlapping horizons
   on one series violate. They describe performance. They are not a significance
   test and Phase 4 must not use them as one.
5. Use `version_drift` to decide comparability across records, and never to
   reject one.
6. Call `assert_record_admissible` on any record entering an evaluation. It is
   cheap and it is the only thing standing between a smuggled constituent and a
   scored production claim.

---

## 11. STOP / GO Gate

### Gate Question

Can model outputs be compared under one scoring framework?

### Decision

**GO**

### Basis

- Every predictive component in the repository has one registered identity,
  version, PIT status and production status.
- The census is built from the application's own registries and bound to them
  by tests, so it cannot drift silently.
- Every score class maps onto named `outcome_ledger.summarise` columns, and a
  test proves those columns exist on a real scored forecast.
- The production incumbent and the neural challengers share an output kind and
  therefore a metric set, so they are directly rankable.
- Signal-only constituents are comparable on a declared subset, stated rather
  than assumed.
- Rejected, retired and experimental models cannot reach a production forecast,
  enforced at construction, at status resolution and at record admission.
- Every constituent output resolves to a version, and a record that hides one
  is refused.
- No model was measured, promoted or reopened in this phase.

---

## 12. Phase 3 Completion Summary

- Status: `COMPLETE`
- Result: `GO`
- Next active phase: `PHASE 4 — Baseline + Challenger Evaluation`
- Models registered: 45 (14 production, 3 challenger, 19 experimental, 3
  retired, 6 rejected)
- Measurements performed: none
- Closed programmes reopened: none
- Sealed exam artifacts accessed: no
