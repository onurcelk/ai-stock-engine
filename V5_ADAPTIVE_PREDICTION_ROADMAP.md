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
   - **record the Examined block (see below)**,
   - set the next active phase,
   - commit the roadmap update together with the phase result when appropriate.

### Per-Phase Examination Record — standing rule

Every phase, without exception, examines the eight items below and writes the
answers into its own **Examined** block in its Completion Record. This is not a
summary of the phase's work; it is the evidence that the phase's work did not
damage anything, and it must be answerable from this file alone after `/clear`.

An item that was not checked is recorded as `not checked`, and an item nobody
recorded at the time is recorded as `not recorded`. Neither is silently
omitted, and neither is backfilled from memory or inference.

| # | Item | What is recorded |
|---|---|---|
| 1 | **Baseline suite** | `pytest` pass/skip counts *before* any edit, and whether the baseline was green. Never edit on a red suite. |
| 2 | **Final suite** | `pytest` pass/skip counts after the change, and the delta against the baseline. A drop in passes is a regression and blocks the phase. |
| 3 | **Leak detector** | Whether the phase touched a prediction path, and the explicit result of `app/tests/test_validation.py::test_future_cannot_change_the_verdict`. |
| 4 | **Methodology surfaces** | Which of the CLAUDE.md §1.2 surfaces were touched (targets, features, model params, examset, ladder, `validation/pit.py`), and the amendment authorising it — or `none touched`. |
| 5 | **Frozen records** | Which append-only records were *read* (`alpha/*_PREREGISTRATION.md`, `alpha/*_EXPERIMENT_LOG.md`, `reports/EXPERIMENT_REGISTRY.md`), and confirmation that none was modified. |
| 6 | **Closed programmes** | Which closed or rejected work this phase could plausibly reopen, and why it does not. `none` is a valid answer but must be stated. |
| 7 | **Measurement** | What was measured, or the explicit statement that nothing was. Narrative must follow measurement, never precede it. |
| 8 | **Sealed exam** | Whether any sealed exam artifact was accessed. Expected answer: `no`. |

Two rules about the block itself:

- **It is written before the phase is declared COMPLETE**, not after, so a
  failing item stops the phase rather than being explained away in hindsight.
- **It is never edited to match a later belief.** If a later phase finds an
  Examined entry was wrong, append a dated correction under §6's rule and cite
  the correcting commit. The original wording stays visible.

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
- [x] **PHASE 4 — Baseline + Challenger Evaluation**
- [ ] **PHASE 5 — Adaptive Ensemble** — **BLOCKED**, premise contradicted by the
      record; awaiting a scope decision between the two reformulations in
      `reports/V5_PHASE4_CHALLENGER_EVAL.md` §10.2
- [ ] **PHASE 6 — Regime-Aware Evaluation**
- [ ] **PHASE 7 — Retraining & Promotion Policy**
- [ ] **PHASE 8 — Research & Learning UI**
- [ ] **PHASE 9 — Data Gap Analysis**
- [ ] **PHASE 10 — V5 Integrated Validation**
- [ ] **PHASE 11 — Production Decision**

**ACTIVE PHASE:** PHASE 5 — **BLOCKED.** Do not begin Phase 5 as written. Read
`reports/V5_PHASE4_CHALLENGER_EVAL.md` §10.1–§10.2 first and obtain a scope
decision from the programme owner.

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
- Examined: *(backfilled 2026-08-14 under the §0 standing rule, from the Phase 0 record and `reports/V5_PHASE0_ARCHITECTURE_AUDIT.md` only — nothing was reconstructed from memory.)*
  1. Baseline suite: **not recorded.**
  2. Final suite: **not recorded.** No code was changed, so no delta exists.
  3. Leak detector: no prediction path touched — the phase was a read-only audit. `app/tests/test_validation.py` was *read* as evidence (audit §7.1) but its result was **not recorded**.
  4. Methodology surfaces (§1.2): none touched.
  5. Frozen records: none modified. Which append-only records were read was **not itemised**; audit §2.2 records that sealed exam artifacts were not opened.
  6. Closed programmes: none reopened. Legacy and closed paths were classified `UNUSED` / retire-from-graph (audit §13) without being re-tested.
  7. Measurement: **none.** Audit §17: "Phase 1 implementation performed by this audit: none".
  8. Sealed exam accessed: **no** (audit §2.2, §17).
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
- Examined: *(backfilled 2026-08-14 under the §0 standing rule, from the Phase 1 record and `reports/V5_PHASE1_FORECAST_LEDGER.md` §7 only.)*
  1. Baseline suite: **not recorded.**
  2. Final suite: **848 passed, 63 skipped.** Delta against baseline is unavailable because the baseline was not recorded.
  3. Leak detector: no model behaviour changed — the phase wrapped existing outputs. `app/tests/test_validation.py` was run explicitly at completion as one of four files (`96 passed`); the named test's individual result was **not itemised**. A Phase 1 analogue was added: invariance when all unseen future prices are rewritten.
  4. Methodology surfaces (§1.2): none touched.
  5. Frozen records: none modified. Reads **not itemised**.
  6. Closed programmes: none reopened. The ledger admits no RL/evolutionary agent and no `forecast.run` output (report §3).
  7. Measurement: **none.** The phase established that a forecast can be frozen, reloaded, and proven unchanged; it produced no predictive result.
  8. Sealed exam accessed: **no.**
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
- Examined: *(backfilled 2026-08-14 under the §0 standing rule, from the Phase 2 record and `reports/V5_PHASE2_SCORING_MEMORY.md` only.)*
  1. Baseline suite: **848 passed, 63 skipped** (the Phase 1 result, cited as this phase's baseline).
  2. Final suite: **876 passed, 63 skipped.** Delta **+28 passes**, 0 skips changed, nothing weakened.
  3. Leak detector: no prediction path touched — scoring is a separate process that never writes forecasts. The named test's individual result was **not separately recorded**; it is inside the passing fast suite.
  4. Methodology surfaces (§1.2): none touched.
  5. Frozen records: none modified. Reads **not itemised**.
  6. Closed programmes: none reopened.
  7. Measurement: **mechanism only.** Scoring was demonstrated as a pure function of a frozen record plus realised prices, with `ultimate.evaluate` and `forecast.project` patched to raise. No predictive claim was produced.
  8. Sealed exam accessed: **no.**
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
- Commit: `26c65f8` (`v5 phase 3 unified model registry: GO`)
- Examined: *(recorded during the phase, the first under the §0 standing rule.)*
  1. Baseline suite: **876 passed, 63 skipped** — green, run before any edit, matching the Phase 2 record exactly.
  2. Final suite: **904 passed, 63 skipped.** Delta **+28 passes**, 0 skips changed, no existing assertion relaxed.
  3. Leak detector: no prediction path touched — the registry reads and classifies, it does not predict. `app/tests/test_validation.py::test_future_cannot_change_the_verdict` was run **explicitly and individually: 1 passed.**
  4. Methodology surfaces (§1.2): **none touched.** No target, feature, model parameter, exam set, walk-forward, or `validation/pit.py` change, so no amendment was required. One behavioural change outside that list — `outcome_ledger.model_key` now returns registry identity — was authorised in terms by the Phase 2 completion note.
  5. Frozen records: `reports/EXPERIMENT_REGISTRY.md` was **read** (§2, §6, §7, §8) along with `reports/PROGRESS_V3.md`, `reports/PROGRESS_V4.md`, `reports/V4_SUE_POWER_GATE.md`, `reports/FAMILY10_ADMISSIBILITY.md`, `reports/AGENT_META_SIGNAL_RESULT.md`. **None was modified.** Every number quoted into the registry was copied from them, never recomputed.
  6. Closed programmes: this phase deliberately touched all of them, and registered them as `REJECTED` so they stay closed. Nothing was reopened, re-tested, or re-scored. `assert_not_reopened` is the callable form of that bar; six programmes are covered.
  7. Measurement: **none.** Every status was assigned from the existing record. No model was promoted, demoted, retired, or reopened on the strength of a number computed in this phase.
  8. Sealed exam accessed: **no.**
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

- [x] Define the exact production target. (§3 of the report)
- [x] Define metrics matching displayed app claims. (§4)
- [x] Evaluate all candidates on identical PIT splits. — **discharged from the
      frozen PIT-1 record, not re-run.** Re-running it reopens a closed
      programme; see §2. (§6.1)
- [x] Compare every candidate against baseline. — same basis. (§6.2, §6.4)
- [x] Separate single-name metrics from cross-sectional metrics. — separated.
      Single-name is fully covered; **cross-sectional has never been measured for
      this engine and remains open**, needing its own preregistration. (§7)
- [x] Reject complexity with no incremental evidence. (§8)

## Required Deliverable

`reports/V5_PHASE4_CHALLENGER_EVAL.md`

## STOP / GO Gate

Proceed only with candidates that either:

1. beat the baseline with credible OOS evidence, or
2. add complementary information that may justify ensemble testing.

## Completion Record

- Status: COMPLETE
- Result: **STOP on route 1 for every candidate.** Phase 4 was executed as an
  evidence synthesis over the frozen record, with **no new measurement**: the
  88-cutoff design first drafted for this phase was found to be a higher-powered
  re-run of the CLOSED `PIT-1` programme (same object, harness, code paths,
  baselines and clustered statistics), the conflict was flagged under CLAUDE.md
  §1.3 before any forecast was frozen, and the programme owner directed synthesis
  rather than re-measurement. On PIT-1's frozen numbers every candidate is below
  `always_bullish` on identical rows and the single individually significant
  difference is negative (−22.4 pts [−40.0, −4.9], p = 0.017); both
  return-emitting candidates lose to no-change on level and carry no magnitude
  information (corr −0.011 and −0.073); the neural challenger changed **zero**
  verdicts across 257 of 257 gated horizon-slots; confidence is non-monotone and
  inverts at the top band; and the RL slot is structurally empty. No candidate was
  promoted or demoted and no production weight changed.
- Commit: `cb5d2eb` (`v5 phase 4 baseline and challenger evaluation: STOP, no
  candidate advances`)
- Examined: *(recorded during the phase, under the §0 standing rule.)*
  1. Baseline suite: **904 passed, 63 skipped** — green, run before any edit,
     matching the Phase 3 record exactly.
  2. Final suite: **904 passed, 63 skipped.** Delta **0** — the phase changed no
     code, only documentation. No assertion relaxed.
  3. Leak detector: **no prediction path touched.** No module was added or
     modified. `app/tests/test_validation.py::test_future_cannot_change_the_verdict`
     was run **explicitly and individually: 1 passed.**
  4. Methodology surfaces (§1.2): **none touched.** No target, feature, model
     parameter, exam set, walk-forward or `validation/pit.py` change, so no
     amendment was required.
  5. Frozen records: **read** — `reports/EXPERIMENT_REGISTRY.md` (§2, §5),
     `validation/REPORT.md` (§1–§20), `reports/SINGLE_NAME_PHASE1.md`. **None was
     modified.** Every number quoted into the Phase 4 report was copied from them,
     never recomputed. `reports/EXPERIMENT_REGISTRY.md` was **appended to** — a new
     §12 registering the aborted design, under the registry's own rule that a run
     which aborted gets a row saying so. No existing wording was altered, and no
     row was inserted into the §2 index.
  6. Closed programmes: **this phase exists because of one.** The drafted design
     would have reopened `closed.pit1_single_name`; it was refused and not run.
     `closed.ams1_agent_meta` is named as foreclosing agent-agreement weighting in
     Phase 5. The V2/V3/V4 cross-sectional record is recorded as a *different
     target*, so §7.2's open cross-sectional question does not reopen it. Nothing
     was re-tested, re-scored or reopened.
  7. Measurement: **none.** No forecast was frozen, no outcome resolved, no ledger
     written, no estimate produced. Three exploratory probes ran *before* the
     conflict was identified — one timed `ultimate.evaluate`, three timed
     `forecast.project` fits, two coverage probes over 6 symbols × 12 cutoffs. All
     called the prediction side only; **none read a realised return, an outcome, or
     any bar after its cutoff.** None is used as evidence. They are recorded in the
     report §2.1 and in registry §12. The one fact carried forward from them (§7.3
     — a neutral verdict is an abstention with `coverage == 0`, never a cancelled
     signal) involves no forward return.
  8. Sealed exam accessed: **no.**
- Notes for Phase 5: **Phase 5 as written cannot be entered.** It presupposes
  constituents with differing measurable OOS usefulness to reallocate weight
  between; the record supplies none — combined agent accuracy 50.2% (n = 325,
  −8.9 pts vs always-long), best single agent −2.2 pts [−16.9, +12.6] and long 55%
  of the time in a rising market, worst agent the fading variant and short most of
  the time in the same market, i.e. both measuring drift in opposite directions.
  Agent-agreement weighting is foreclosed by `closed.ams1_agent_meta`, whose
  measured direction was the reverse of the hypothesis. Two admissible
  reformulations are set out in report §10.2 — **(a)** weight-to-abstain, testing
  whether the existing `coverage`/`agreement` gating identifies in advance where
  calls are worth acting on (the one validated property of the system), and
  **(b)** skipping to Phase 9 Data Gap Analysis, since the engine reads price and
  volume only and the resolution arithmetic says the instrument cannot see effects
  of the size that information plausibly carries. Recommendation: **(b) with (a)
  as a cheap prerequisite.** Either needs a preregistration committed before
  measurement. Carry forward unchanged: cluster by cutoff date; `known_as_of()` is
  the only admissible slice for a weight; declare the abstained/spoken split before
  any MAE comparison; no `probability_positive` exists anywhere, so Brier, log loss
  and calibration error are not computable and confidence is never substituted for
  a probability; the Phase 2 nominal-interval caveat stands; and PIT-1's three
  residual look-aheads are unrepaired, so **this harness cannot support a
  believable positive result** until they are. `app/streamlit_app.py` and
  `app/tests/test_ui.py` keep their pre-existing uncommitted modifications and were
  not touched.

---

# PHASE 5 — Adaptive Ensemble

> **BLOCKED — do not begin this phase as written.** Phase 4 found its premise
> contradicted by the frozen record: there is no set of constituents with
> differing, measurable out-of-sample usefulness to reallocate weight between.
> Read `reports/V5_PHASE4_CHALLENGER_EVAL.md` §10.1–§10.2 and obtain a scope
> decision from the programme owner before doing anything below. Reweighting
> components that are collectively indistinguishable from the market's drift
> produces a different number, not a better forecast.

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
- Examined: (mandatory — fill the eight items from §0 before declaring COMPLETE)
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
- Examined: (mandatory — fill the eight items from §0 before declaring COMPLETE)
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
- Examined: (mandatory — fill the eight items from §0 before declaring COMPLETE)
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
- Examined: (mandatory — fill the eight items from §0 before declaring COMPLETE)
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
- Examined: (mandatory — fill the eight items from §0 before declaring COMPLETE)
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
- Examined: (mandatory — fill the eight items from §0 before declaring COMPLETE)
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
- Examined: (mandatory — fill the eight items from §0 before declaring COMPLETE)
- Notes:

---

# 4. Resume Prompt

After `/clear`, use only this short prompt:

> Read `V5_ADAPTIVE_PREDICTION_ROADMAP.md`. Treat it as the persistent project state. Check git status/history, identify the ACTIVE PHASE and first unchecked task, then continue that phase only. Read historical reports only when the active phase requires exact evidence. Do not redo completed work. Record the baseline suite result before your first edit — it is item 1 of the mandatory Examined block in §0. At the end, update the roadmap checkboxes, result, commit hash, **the Examined block**, and ACTIVE PHASE.

---

# 5. Phase Completion Template

At the end of every phase, update its record:

```text
Status: COMPLETE / REJECTED / BLOCKED
Result: <1–4 sentence decision>
Commit: <hash>
Examined:
  1. Baseline suite: <passed/skipped before any edit; green?>
  2. Final suite: <passed/skipped after; delta>
  3. Leak detector: <prediction path touched? explicit test result>
  4. Methodology surfaces (§1.2): <which, and the authorising amendment — or none touched>
  5. Frozen records: <which append-only records were read; none modified>
  6. Closed programmes: <what this could reopen, and why it does not — or none>
  7. Measurement: <what was measured, or "none">
  8. Sealed exam accessed: <no>
Notes: <only information required by the next phase>
```

The **Examined** block is mandatory and is filled from the standing rule in
§0. It is written before the phase is declared COMPLETE.

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
