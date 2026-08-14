# V5 Adaptive Prediction Engine — Roadmap & State

> **Purpose:** This file is the persistent memory and execution tracker for V5.
> After `/clear`, read this file first and continue from the first unchecked phase.
> Do not rely on chat history when this file contains the needed state.

---

## 0. Operating Protocol

### Start / Resume Rule

At the beginning of a fresh Claude Code context:

1. Read this file.
2. Read only the files explicitly referenced by the **ACTIVE PHASE**.
3. Check `git status` and recent relevant commits.
4. Continue from the first unchecked phase.
5. Do **not** restart completed research.
6. Do **not** begin a later phase until the current phase meets its STOP/GO gate.
7. At the end of the phase:
   - update this file,
   - tick completed tasks with `[x]`,
   - record result,
   - record commit hash,
   - set the next active phase,
   - commit the roadmap update together with the phase result when appropriate.

### Token Discipline

- This file is the primary context capsule.
- Do not reread all historical reports unless the active phase requires them.
- Prefer targeted file reads/searches.
- Do not restate the entire project history in every response.
- Keep terminal reports concise.
- Preserve detailed evidence in repository reports, not chat.
- One major phase per context/session is preferred.
- After a phase is committed, `/clear` is safe.

### Scientific Rules

- Point-in-time data only.
- No look-ahead leakage.
- Historical forecasts must be frozen before outcomes are observed.
- No hypothesis changes after seeing results.
- Strong trivial baselines are mandatory.
- Report uncertainty and sample size.
- No symbol/horizon cherry-picking.
- No repeated mining until something passes.
- Research and production remain separate.
- Complexity earns no production weight by itself.
- HOLD / abstain is valid.
- Negative results must remain visible.
- Never weaken an existing validation rule to make V5 pass.

---

# 1. V5 Objective

Build an adaptive prediction engine that can demonstrate, with point-in-time evidence, whether it learns useful information about future stock returns.

Target application output remains conceptually:

- Symbol
- BUY / HOLD / SELL
- Expected return
- Probability positive
- Confidence
- Horizon

V5 must connect this output to a complete learning loop:

`Data → PIT features → Models → Forecast → Frozen forecast ledger → Outcome → Scoring → Performance memory → Adaptive weighting / retraining → New forecast`

The system must be able to answer:

> “Is the production prediction system genuinely better than its baseline, and why?”

---

# 2. Current Research Context Capsule

Use existing repository evidence as source of truth.

Known programme conclusions entering V5:

- Many candidate feature families have already failed clean PIT evaluation.
- Cross-sectional predictive value and single-name predictive value are different research objects.
- Existing research discipline is valuable and must be preserved.
- Existing ML/RL complexity must not be assumed useful without OOS evidence.
- The next priority is not indicator proliferation.
- The key missing concept to investigate is a durable forecast → outcome → error → learning loop.
- Existing validation, PIT, forecasting, scoring, and agent infrastructure should be reused where valid.

Do not treat this summary as a substitute for repository evidence when exact values are required.

---

# 3. Global V5 Phase Tracker

- [x] **PHASE 0 — Architecture Audit**
- [x] **PHASE 1 — Forecast Ledger**
- [x] **PHASE 2 — Outcome Scoring & Performance Memory**
- [x] **PHASE 3 — Unified Model Registry**
- [ ] **PHASE 4 — Baseline + Challenger Evaluation**
- [ ] **PHASE 5 — Adaptive Ensemble**
- [ ] **PHASE 6 — Regime-Aware Evaluation**
- [ ] **PHASE 7 — Retraining & Promotion Policy**
- [ ] **PHASE 8 — Research & Learning UI**
- [ ] **PHASE 9 — Data Gap Analysis**
- [ ] **PHASE 10 — V5 Integrated Validation**
- [ ] **PHASE 11 — Production Decision**

**ACTIVE PHASE:** PHASE 4

---

# PHASE 0 — Architecture Audit

## Goal

Determine what the application actually does today from raw data to displayed forecast.

## Tasks

- [x] Trace the real prediction execution path.
- [x] Identify all production-used models/agents.
- [x] Identify implemented but unused models.
- [x] Identify TensorFlow/neural training paths.
- [x] Identify RL training/reward paths.
- [x] Identify retraining behaviour.
- [x] Determine whether historical forecasts are persisted.
- [x] Determine whether predictions are immutable after generation.
- [x] Determine whether forecasts are later matched to realised outcomes.
- [x] Trace confidence calculation.
- [x] Trace ensemble/model weighting.
- [x] Verify PIT safety of all production-relevant paths.
- [x] Identify duplicated/dead prediction paths.
- [x] Mark components: `EXISTS / PARTIAL / MISSING / UNSAFE / UNUSED`.

## Required Deliverable

Create:

`reports/V5_PHASE0_ARCHITECTURE_AUDIT.md`

It must contain:

1. Current system map
2. Current learning map
3. Critical gaps ranked by severity
4. Components worth keeping
5. Components to isolate/retire
6. Minimum V5 architecture proposal

## STOP / GO Gate

**GO** only when the actual execution path is understood well enough to add forecast memory without guessing.

## Completion Record

- Status: COMPLETE
- Result: GO. The live execution path is fully mapped: the default Ultimate signal combines ten deterministic technical sources and three rule-based agents, with an optional on-demand recurrent neural forecast. The application has mutable training-run history but no immutable production forecast ledger or live forecast-to-outcome join; the separate validation package provides reusable PIT truncation, freeze-before-score, and overwrite-refusal patterns.
- Commit: PENDING — read-only preparation; record the applying commit hash when this audit and roadmap update are committed.
- Notes: Phase 1 should wrap existing incumbent/challenger outputs in an immutable forecast record without changing model behaviour. Keep `app/runs` as separate mutable UI history; store confidence separately from `probability_positive`; isolate same-series RL and leaky single-split neural paths from production evidence; do not implement scoring, adaptive weighting, retraining, or Phase 1 UI work yet.

---

# PHASE 1 — Forecast Ledger

## Goal

Create one immutable point-in-time record for every production/challenger forecast.

## Minimum Fields

- `forecast_id`
- `generated_at`
- `cutoff_at`
- `symbol`
- `horizon`
- `price_at_cutoff`
- `predicted_direction`
- `predicted_return`
- `probability_positive`
- `confidence`
- `model_predictions`
- `model_weights`
- `model_versions`
- `feature/data version`
- `regime_state`
- `baseline_prediction`

## Tasks

- [x] Design schema.
- [x] Reuse existing prediction persistence if safe.
- [x] Make forecast records immutable.
- [x] Add version identifiers.
- [x] Add tests proving no post-outcome rewrite.
- [x] Add tests proving no future data enters stored forecast.

## Required Deliverable

- Forecast ledger implementation
- Schema documentation
- Tests
- Short report: `reports/V5_PHASE1_FORECAST_LEDGER.md`

## STOP / GO Gate

**GO** only if a forecast can be generated, frozen, reloaded later, and proven unchanged.

## Completion Record

- Status: COMPLETE
- Result: GO. The new SQLite forecast ledger generates and freezes one immutable record per available incumbent horizon, reloads canonical payloads with integrity verification, and serializes explicitly versioned genuine forward neural challengers. Exact consumed frames are cutoff-validated and fingerprinted; duplicate/replacement inserts, updates, deletes, identity tampering, and post-cutoff data are rejected. The complete fast suite passed with 848 tests passed and 63 skipped.
- Commit: `d04956f` (`v5 phase 1 forecast ledger: GO`)
- Notes: Phase 2 must store outcomes and scores separately by `forecast_id`; it must never rewrite the Phase 1 `forecasts` table or introduce outcome reads into `forecast_ledger.py`. `probability_positive`, `regime_state`, and `baseline_prediction` remain null unless supplied from admissible forecast-time evidence. The existing modified `app/streamlit_app.py` and `app/tests/test_ui.py` were not touched; UI adoption remains outside Phase 1.

---

# PHASE 2 — Outcome Scoring & Performance Memory

## Goal

Close the loop between historical forecast and realised outcome.

## Outcome Fields

Where appropriate:

- realised return
- realised direction
- absolute error
- squared error
- directional correctness
- Brier contribution
- calibration result
- baseline result
- baseline-relative score
- market-relative outcome
- sector-relative outcome

## Tasks

- [x] Match matured forecasts to outcomes.
- [x] Never overwrite original forecast fields.
- [x] Implement horizon-aware scoring.
- [x] Maintain sample counts.
- [x] Add rolling and expanding performance summaries.
- [x] Measure by model and horizon first.
- [x] Add symbol/sector breakdown only when sample size is sufficient.
- [x] Add calibration metrics where probabilities exist.
- [x] Add baseline-relative metrics.

## Required Deliverable

`reports/V5_PHASE2_SCORING_MEMORY.md`

## STOP / GO Gate

**GO** only if historical predictions can be objectively scored without regeneration.

## Completion Record

- Status: COMPLETE
- Result: GO. The new `app/core/outcome_ledger.py` matches matured forecasts to realised bars in a separate append-only `outcomes` table keyed by `forecast_id`, scores them horizon-aware against a declared baseline, and builds rolling/expanding performance memory in which every point estimate carries its sample size and interval. Scoring is a pure function of a frozen record plus realised prices — it was demonstrated with `ultimate.evaluate` and `forecast.project` patched to raise, which is the Phase 2 gate. The complete fast suite passed with 876 tests passed and 63 skipped, the 848-pass Phase 1 baseline plus 28 new tests, with nothing weakened.
- Commit: `bcf7347` (`v5 phase 2 outcome scoring and performance memory: GO`)
- Notes for Phase 3: `model_key()` in `outcome_ledger` is a placeholder identity (`ultimate_ensemble`, or the challenger's `neural_challenger` version) that Phase 3 should replace with real registry identity; keep the scoring API stable when it does. The reported Wilson/normal intervals are **nominal and assume independent observations** — overlapping horizons on one series violate that, so they describe performance but are not a significance test and must not be used as one by Phase 4 or Phase 10. Performance memory becomes known at `matured_at`, never at `cutoff_at`: Phase 5 must build weights through `known_as_of()`. `probability_positive`, Brier, and calibration remain null because no production path emits a probability, and confidence must never be substituted for one. Sector-relative outcomes stay unavailable pending a PIT sector map (Phase 9 candidate). No weight, status, or promotion was changed. `app/streamlit_app.py` and `app/tests/test_ui.py` keep their pre-existing uncommitted modifications and were not touched.

---

# PHASE 3 — Unified Model Registry

## Goal

Give every predictive component the same interface and accountability.

## Required Metadata

Each model should expose, where relevant:

- model ID
- model family
- version
- training cutoff
- target
- horizon
- required features
- retraining policy
- PIT status
- production status

## Tasks

- [x] Inventory existing rule-based models.
- [x] Inventory admissible RL models.
- [x] Inventory neural/ML models.
- [x] Define common prediction interface.
- [x] Separate `PRODUCTION / CHALLENGER / EXPERIMENTAL / REJECTED / RETIRED`.
- [x] Ensure every output identifies model version.
- [x] Prevent rejected models from silently affecting production.

## Required Deliverable

`reports/V5_PHASE3_MODEL_REGISTRY.md`

## STOP / GO Gate

**GO** only if model outputs can be compared under one scoring framework.

## Completion Record

- Status: COMPLETE
- Result: GO. The new `app/core/model_registry.py` registers 45 predictive components — 14 PRODUCTION, 3 CHALLENGER, 19 EXPERIMENTAL, 3 RETIRED, 6 REJECTED — each with declared identity, source-hash version, family, target, horizons, required features, training cutoff, retraining policy, PIT status and production status. Model outputs are comparable under one framework because every model declares an `output_kind` and a `score_class` that maps onto named `outcome_ledger.summarise` columns: the incumbent ensemble and the neural challengers share `return_pct` and are directly rankable, while signal-only constituents admit directional accuracy alone. The census is built from `indicators.SOURCES`, `agents.REGISTRY`, `forecast.MODELS` and `ultimate.HORIZONS` and bound to them by tests, so it cannot drift. The complete fast suite passed with 904 tests passed and 63 skipped, the 876-pass Phase 2 baseline plus 28 new tests, with nothing weakened.
- Commit: PENDING — record the applying commit hash when this registry, its tests, and the roadmap update are committed.
- Notes for Phase 4: **There is no admissible RL candidate.** All 19 trainable agents are PIT-INADMISSIBLE for a structural reason (whole-series training, replay from bar zero) and none carries a `record_key`, so none can appear in a frozen forecast; reopening that means building a PIT-safe training protocol, which is Phase 7 work and not a Phase 4 shortcut. `closed.pit1_single_name` — 9 components, 0 beat always-up, unanimous sign — is the prior for single-name direction and the candidate set must be justified against it. `closed.ams1_agent_meta` constrains Phase 5: weighting by cross-family agent agreement reopens a refused result. Rank by `score_class`: only `RETURN_AND_DIRECTIONAL` models may be compared on MAE/RMSE. `outcome_ledger.model_key` now returns registry identity (authorised in terms by the Phase 2 completion record) and `performance_frame` carries a separate `model_version` column, so Phase 4 must choose explicitly whether to group by identity or by identity and version. A model-assisted incumbent record still resolves to `ensemble.ultimate`; use `constituent_ids(record)` when that distinction matters. Call `assert_record_admissible` on any record entering an evaluation. The Phase 2 interval caveat is unchanged: nominal intervals, not a significance test. `app/streamlit_app.py` and `app/tests/test_ui.py` keep their pre-existing uncommitted modifications and were not touched.

---

# PHASE 4 — Baseline + Challenger Evaluation

## Goal

Establish the models that actually deserve further attention.

## Rules

Do not add large numbers of new models.

Start with a compact set:

- strongest existing simple baseline
- strongest existing admissible rule-based model
- strongest existing admissible ML/neural candidate
- strongest existing admissible RL candidate
- at most a small number of justified new challengers

## Tasks

- [ ] Define the exact production target.
- [ ] Define metrics matching displayed app claims.
- [ ] Evaluate all candidates on identical PIT splits.
- [ ] Compare every candidate against baseline.
- [ ] Separate single-name metrics from cross-sectional metrics.
- [ ] Reject complexity with no incremental evidence.

## Required Deliverable

`reports/V5_PHASE4_CHALLENGER_EVAL.md`

## STOP / GO Gate

Proceed only with candidates that either:

1. beat the baseline with credible OOS evidence, or
2. add complementary information that may justify ensemble testing.

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# PHASE 5 — Adaptive Ensemble

## Goal

Allow model influence to depend on demonstrated OOS usefulness.

Conceptually:

`final_prediction(t) = Σ prediction_i(t) × weight_i(t)`

All information used to determine `weight_i(t)` must exist before time `t`.

## Investigate

- recent OOS performance
- long-run OOS performance
- calibration
- horizon
- model disagreement
- forecast stability
- validated regime information

## Safety

- use shrinkage
- require minimum sample sizes
- avoid performance chasing
- fall back toward strong baseline when evidence is weak
- cap unstable weights
- never optimise weights on future outcomes

## Tasks

- [ ] Pre-register ensemble weighting rule before final evaluation.
- [ ] Implement PIT-safe historical weight reconstruction.
- [ ] Compare static vs adaptive ensemble.
- [ ] Compare both against production baseline.
- [ ] Test stability.

## Required Deliverable

`reports/V5_PHASE5_ADAPTIVE_ENSEMBLE.md`

## STOP / GO Gate

Adaptive weighting must add credible OOS value over the simple baseline/static alternative.

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# PHASE 6 — Regime-Aware Evaluation

## Goal

Determine whether model skill genuinely depends on market environment.

## Candidate Regime Inputs

Only where PIT-safe and available:

- realised volatility
- trend state
- breadth
- dispersion
- drawdown state
- correlation state
- risk-on/risk-off proxies
- VIX or equivalent

## Tasks

- [ ] Define a small number of regime hypotheses.
- [ ] Freeze regime construction before testing model-performance interaction.
- [ ] Measure model performance by regime.
- [ ] Require adequate sample size.
- [ ] Reject regime conditioning if it adds no robust information.

## Required Deliverable

`reports/V5_PHASE6_REGIME_EVAL.md`

## STOP / GO Gate

Only validated regime effects may influence ensemble weights or model selection.

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# PHASE 7 — Retraining & Promotion Policy

## Goal

Make adaptation controlled rather than continuous overfitting.

## Define

- rolling vs expanding training window
- retraining frequency
- minimum new observations
- frozen vs retuned hyperparameters
- model versioning
- challenger promotion rule
- degradation rule
- retirement rule
- rollback behaviour

## Tasks

- [ ] Write policy before automating retraining.
- [ ] Add versioned model artefacts.
- [ ] Add deterministic retraining tests where possible.
- [ ] Prevent newly trained models from entering production automatically.
- [ ] Require challenger evaluation before promotion.

## Required Deliverable

`reports/V5_PHASE7_RETRAINING_POLICY.md`

## STOP / GO Gate

No automatic production promotion without explicit evidence gate.

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# PHASE 8 — Research & Learning UI

## Goal

Make the state of the research visible inside the Streamlit application.

## Minimum UI Sections

### Production

- production model / ensemble
- active model versions
- model weights
- active horizons
- last retraining date

### Forecast Quality

- directional accuracy
- probability calibration
- regression error where applicable
- baseline-relative performance
- sample size
- rolling performance

### Model Leaderboard

- model
- status
- horizon
- recent OOS score
- long-run OOS score
- baseline-relative score
- current weight

### Forecast History

For each matured prediction show:

- forecast date
- symbol
- horizon
- predicted return/direction
- predicted probability
- realised return
- error
- correctness

### Prediction Explanation

For current forecast show:

- final forecast
- baseline
- constituent model predictions
- weights
- disagreement
- confidence
- regime if validated
- reliability / sample support

### Research Pipeline

- active experiment
- completed experiments
- rejected experiments
- accepted challengers
- rejection reason
- promotion requirements

## Tasks

- [ ] Build UI from stored evidence, not recomputed hindsight.
- [ ] Add empty-state handling.
- [ ] Add sample-size warnings.
- [ ] Keep research and production visually distinct.

## Required Deliverable

Working Streamlit UI + `reports/V5_PHASE8_UI.md`

## STOP / GO Gate

The user should be able to understand whether the system is improving without reading terminal logs.

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# PHASE 9 — Data Gap Analysis

## Goal

Only now decide whether more data is needed.

## Rank Candidate Data Families By

1. expected incremental information
2. PIT availability
3. historical depth
4. cost
5. implementation effort
6. leakage risk
7. relevance to our exact prediction target

## Candidate Families

- earnings surprises
- analyst revisions
- options-implied expectations
- volatility term structure
- liquidity/order-flow proxies
- corporate actions/events
- sector/industry relative information
- macro data

## Rules

- Do not recommend indicator proliferation.
- RSI/MACD/Bollinger/etc. are transformations, not automatically new information.
- Prefer genuinely distinct information families.
- Prefer free sources unless paid data solves a specific demonstrated gap.

## Required Deliverable

`reports/V5_PHASE9_DATA_GAP_ANALYSIS.md`

## STOP / GO Gate

Any new dataset must have a precise hypothesis and measurable expected role.

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# PHASE 10 — V5 Integrated Validation

## Goal

Evaluate V5 as a complete forecasting system.

## Required Comparisons

At minimum compare:

- trivial baseline
- current pre-V5 production system
- best standalone challenger
- static ensemble
- adaptive ensemble
- adaptive + regime logic, only if Phase 6 passed

## Metrics

Use metrics aligned with actual app claims.

Potential metrics:

- directional accuracy
- Brier score
- log loss
- calibration error
- MAE
- RMSE
- baseline-relative performance
- IC/rank IC only where cross-sectional ranking is explicitly evaluated

## Tasks

- [ ] Pre-register final comparison.
- [ ] Freeze test/exam data.
- [ ] Run integrated PIT evaluation.
- [ ] Report uncertainty.
- [ ] Report sample sizes.
- [ ] Report failures as prominently as wins.
- [ ] Test whether confidence is meaningful.

## Required Deliverable

`reports/V5_PHASE10_INTEGRATED_VALIDATION.md`

## STOP / GO Gate

V5 may only be called better if it demonstrates credible OOS improvement on metrics corresponding to its actual forecast claims.

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# PHASE 11 — Production Decision

## Goal

Make an explicit final decision.

Choose exactly one:

- `PROMOTE V5`
- `LIMITED PROMOTION`
- `KEEP CURRENT PRODUCTION`
- `HOLD — INSUFFICIENT EVIDENCE`

## Required Deliverable

`reports/V5_FINAL_DECISION.md`

Must include:

- production configuration
- model versions
- weights
- supported horizons
- unsupported claims
- known weaknesses
- retraining rule
- next scheduled research question
- rollback procedure

## Completion Record

- Status: PENDING
- Result:
- Commit:
- Notes:

---

# 4. Resume Prompt

After `/clear`, use only this short prompt:

> Read `V5_ADAPTIVE_PREDICTION_ROADMAP.md`. Treat it as the persistent project state. Check git status/history, identify the ACTIVE PHASE and first unchecked task, then continue that phase only. Read historical reports only when the active phase requires exact evidence. Do not redo completed work. At the end, update the roadmap checkboxes, result, commit hash, and ACTIVE PHASE.

---

# 5. Phase Completion Template

At the end of every phase, update its record:

```text
Status: COMPLETE / REJECTED / BLOCKED
Result: <1–4 sentence decision>
Commit: <hash>
Notes: <only information required by the next phase>
```

Then:

1. tick the phase `[x]` in the Global V5 Phase Tracker,
2. change `ACTIVE PHASE`,
3. commit the state update.

---

# 6. Context Refresh Rule

A `/clear` should normally happen after a major phase commit.

The next context should need only:

1. this roadmap,
2. the active phase's referenced files,
3. relevant git history,
4. exact reports explicitly required by that phase.

The roadmap should contain conclusions, not raw logs.

If a later phase discovers that an earlier recorded conclusion is wrong, do not silently edit history. Add a dated correction note and reference the correcting commit.
