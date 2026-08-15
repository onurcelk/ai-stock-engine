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
- [x] **PHASE 5 — Adaptive Ensemble** — **CLOSED in both forms.** As written:
      BLOCKED, premise contradicted by the record. As reformulation (a)
      weight-to-abstain: ran as ABS-1 and returned
      **NOT ANSWERABLE IN THIS HARNESS** on the power gate
- [ ] **PHASE 6 — Regime-Aware Evaluation** — **INADMISSIBLE AS WRITTEN, not
      entered** (2026-08-14). Audited on request and blocked at entry on three
      independent grounds: the only record that could answer it is PIT-1, which
      is CLOSED and already reports a regime null; regime conditioning is both a
      rejected family (`V2-E`) and a §2.5 disqualifier, contradicting this
      phase's own STOP/GO gate; and a regime split partitions 12 cutoffs that are
      not 12 independent draws. Nothing measured. The question stays **open** on
      a record that could resolve it. See `reports/V5_PHASE6_REGIME_EVAL.md`
- [ ] **PHASE 7 — Retraining & Promotion Policy**
- [ ] **PHASE 8 — Research & Learning UI**
- [x] **PHASE 9 — Data Gap Analysis** — **COMPLETE** (2026-08-15).
      `NO NEW DATASET AUTHORISED. THE GAP IS DATES, NOT DATA`. All eight
      candidate families already carry a disposition in two frozen surveys, and
      none is both un-surveyed and admissible. The calibrated resolution model
      shows why no family could help: on the V5 record adding *infinitely many*
      symbols narrows the interval **3.8%**, while 12 → 50 dates narrows it
      **51%**. The one free, PIT-by-construction, compounding source of dates is
      the Phase 1 forecast ledger, which has never been switched on.
      See `reports/V5_PHASE9_DATA_GAP_ANALYSIS.md`
- [ ] **PHASE 10 — V5 Integrated Validation**
- [ ] **PHASE 11 — Production Decision**

**ACTIVE PHASE:** **PHASE 7 — Retraining & Promotion Policy.** Read
`reports/V5_PHASE9_DATA_GAP_ANALYSIS.md` §6 first; nothing else is required.

**Superseded, kept visible.** Until 2026-08-15 the ACTIVE PHASE was PHASE 9 —
Data Gap Analysis, taken **out of order** and ahead of Phases 6, 7 and 8, on the
standing Phase 4 §10.2(b) recommendation: Phase 5 is closed in both forms, and
the binding constraint on this programme is resolution, not model choice. Phases
6, 7 and 8 were deferred behind the question of whether any dataset exists that
this instrument could resolve. **Phase 9 has now answered that question: none
does, and none could — the shortfall is independent dates, which no dataset
supplies.** The deferral therefore expires on its own terms rather than being
overridden.

**Why Phase 7 and not Phase 10.** Phase 10 (V5 Integrated Validation) needs a
record to validate on, and Phase 9 established that the existing 12-cutoff record
cannot resolve anything worth validating. Phase 7 is a **policy** phase — "write
policy before automating retraining" — so it requires no resolution, costs no
data, and is the precondition for the only accumulation route Phase 9 authorises:
its gate, *"no automatic production promotion without explicit evidence gate"*, is
exactly what must govern what gets frozen into the forecast ledger and under what
versioning. Phase 8 (Research & Learning UI) follows and now has a defined
empty-state story to build against. Phase 6 remains open and unentered.

**Reaffirmed 2026-08-14 after a Phase 6 admissibility audit.** The programme
owner asked to start Phase 6 out of this order. Phase 6 was audited rather than
entered and returned `INADMISSIBLE AS WRITTEN` — see
`reports/V5_PHASE6_REGIME_EVAL.md`. The audit strengthens the case for the
existing ordering rather than competing with it: regime conditioning asks the
same 12 draws to support two or three accuracy estimates instead of one, so it
*multiplies* the resolution requirement. ACTIVE PHASE is therefore unchanged at
**Phase 9**. One item is now available to be settled independently and for free,
with no data touched: the §2.5 versus Phase-6-gate contradiction recorded at the
Phase 6 STOP/GO gate below, which blocks every future Phase 6 on every record.

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
>
> **Closed 2026-08-14.** The block above stands and its wording is unchanged.
> The owner chose reformulation §10.2(a), which ran as ABS-1 and returned
> `NOT ANSWERABLE IN THIS HARNESS` at its power gate. Phase 5 is closed in both
> forms. See the Completion Record below and `reports/V5_PHASE5A_ABSTENTION.md`.

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

The five tasks below belong to Phase 5 **as written** and were **never
started**. The phase was blocked before them and is now closed; they are left
unticked deliberately, as the record that they were not done.

- [ ] Pre-register ensemble weighting rule before final evaluation.
- [ ] Implement PIT-safe historical weight reconstruction.
- [ ] Compare static vs adaptive ensemble.
- [ ] Compare both against production baseline.
- [ ] Test stability.

### Tasks actually executed — reformulation (a), weight-to-abstain

- [x] Obtain the programme owner's scope decision between §10.2(a) and (b).
- [x] Pre-register the abstention study before any statistic existed.
- [x] Commit the power-gate computation before running it.
- [x] Compute Gate 1 from signal geometry alone, reading no outcome.
- [x] Apply the pre-registered verdict rule to the gate result.

## Required Deliverable

`reports/V5_PHASE5_ADAPTIVE_ENSEMBLE.md` — **not produced.** The phase it
belonged to was never entered. The deliverable of the executed reformulation is
`reports/V5_PHASE5A_ABSTENTION.md`.

## STOP / GO Gate

Adaptive weighting must add credible OOS value over the simple baseline/static alternative.

**Never reached.** No weighting was constructed, so nothing was available to
put against this gate.

## Completion Record

- Status: **CLOSED in both forms.** Not COMPLETE — nothing was demonstrated.
- Result: Phase 5 **as written** stayed blocked: Phase 4 found its premise
  contradicted by the frozen record and no constituent set with differing
  measurable OOS usefulness exists to reallocate weight between. On 2026-08-14
  the programme owner chose reformulation **(a) weight-to-abstain** from
  `reports/V5_PHASE4_CHALLENGER_EVAL.md` §10.2. That reformulation was
  pre-registered as **ABS-1** and run to its first gate only.
  **`ABS-1 VERDICT: NOT ANSWERABLE IN THIS HARNESS`** — Gate 1 (power) failed.
  The `D − B` coverage contrast resolves to an MDE of **29.15 pp at 80% power**
  against a pre-registered **7.5 pp** threshold, and the intermediate band C
  holds **7 rows across 5 dates**, failing minimum geometry on all three counts.
  Per §7 of the pre-registration the study did not run: `calls.csv` was never
  opened and **no accuracy was computed**. The failure is conclusive rather than
  provisional, because §6.1 fixed in advance that the geometry is an upper bound
  on the scoreable rows and therefore errs toward passing. One prediction-side
  structural finding stands: the coverage gate is **effectively bimodal** —
  120 spoken rows at one family's breadth, 66 at full breadth, 7 in between — so
  coverage is not a continuous dial and no future design may treat it as one.
- Commit: `f53aa96` (pre-registration, before any statistic), `660ce25` (gate
  code, before it was run), `ade0305` (result and roadmap update, after the
  measurement). The temporal ordering of those three hashes is the verifiable
  form of "declared in advance" (CLAUDE.md §5.2).
- Examined: *(recorded during the phase, under the §0 standing rule.)*
  1. Baseline suite: **904 passed, 63 skipped** — green, run before any edit,
     matching the Phase 3 and Phase 4 records exactly.
  2. Final suite: **904 passed, 63 skipped.** Delta **0**. The one new module,
     `alpha/abs1_power_gate.py`, is a standalone analysis entry point and adds
     no test; no existing assertion was relaxed.
  3. Leak detector: **no prediction path touched.** The new module reads a
     frozen JSON artifact and computes geometry; it predicts nothing.
     `app/tests/test_validation.py::test_future_cannot_change_the_verdict` was
     run **explicitly and individually: 1 passed.**
  4. Methodology surfaces (§1.2): **none touched.** No target, feature, model
     parameter, exam set, walk-forward or `validation/pit.py` change, so no
     amendment was required.
  5. Frozen records: **read** — `validation/REPORT.md` (§5, §8, §11, and the
     conclusions), `reports/V5_PHASE4_CHALLENGER_EVAL.md` (§6, §7, §10),
     `reports/SINGLE_NAME_PHASE1.md` §3F (quoted via Phase 4),
     `alpha/AGENT_META_PREREGISTRATION.md` (read for house format only).
     **None was modified.** `validation/out/predictions.json` was read;
     `validation/out/calls.csv` had only its header and its `system`/`window`
     label sets read, and **no outcome value in it was ever read**. Every number
     quoted was copied, never recomputed — including PIT-1's published interval,
     from which the design effect was re-derived. ABS-1's own pre-registration
     was **appended to** with a dated §6.1 before the gate ran; the original §6
     wording is unaltered.
  6. Closed programmes: **PIT-1 is the one at risk, and it was not reopened.**
     ABS-1's admissibility rests on a single narrow ground, fixed in its §1
     before anything was computed: PIT-1's *"the engine's refusal to speak is
     calibrated"* is an assertion the closed record **never measured**, and
     testing an unmeasured assertion is not re-testing an established result. No
     candidate was re-evaluated, no arm resurrected, no threshold moved, no
     cutoff or symbol added. `closed.ams1_agent_meta` was checked against ABS-1's
     `agreement` diagnostic and the two were found to be different objects; the
     diagnostic carried no verdict and was never computed.
  7. Measurement: **geometry only, and no outcome.** What was measured is the
     row/date/symbol geometry of four coverage bands and the resolution that
     geometry implies, computed from the prediction side of the frozen record.
     No accuracy, no MAE, no baseline comparison, no interval on any outcome, no
     forecast frozen, no ledger written. The gate's own output records
     `outcomes_read: false`. No model was promoted, demoted, retired or
     reopened, and no production weight changed.
  8. Sealed exam accessed: **no.**
- Notes for Phase 9: **the binding constraint on this programme is resolution,
  not model choice.** Twelve independent cutoff dates cannot resolve a 7.5 pp
  effect — the figure that killed ABS-1 and the same constraint behind every
  wide interval in Phase 4. Phase 9's gate (*"any new dataset must have a
  precise hypothesis and measurable expected role"*) should therefore be applied
  with a **resolution requirement attached**: a candidate family must be asked
  not only what it would predict but whether any obtainable sample could show
  it. Carry forward unchanged: PIT-1's three residual look-aheads are
  **unrepaired**, so this harness still cannot support a believable positive
  result, and a repaired harness is the precondition for any future prospective
  study — adding cutoffs to PIT-1's grid remains the re-run refused under §1.3.
  `reports/V5_PHASE5A_ABSTENTION.md` §6 records a qualification a future reader
  of Phase 4 §10.2 needs: calibrated gating was described there as "the one
  validated property of this system", and on the evidence now available that is
  too strong — the property was asserted, never tested, and the only test
  designed for it could not be run. That is **not** a correction to PIT-1 under
  §1.1 and must not be appended to `validation/REPORT.md` as one; PIT-1's claim
  has not been contradicted, only left unsupported. `app/streamlit_app.py` and
  `app/tests/test_ui.py` keep their pre-existing uncommitted modifications and
  were not touched.

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

> **Contradiction, recorded 2026-08-14, unresolved.** This gate treats a
> validated regime effect as grounds to condition ensemble weights. Roadmap
> §2.5, as applied four times in `reports/EXPERIMENT_REGISTRY.md` (§347, §429,
> §643, §827), treats a regime-concentrated effect as a **disqualifier** that
> "may not be restricted to in order to survive". The same finding licenses
> action under one rule and forbids it under the other. Resolving this is a
> programme-owner decision and it is a precondition for entering Phase 6 on any
> record. See `reports/V5_PHASE6_REGIME_EVAL.md` §3.2.
>
> **Still open after Phase 9 (2026-08-15).** Phase 9 was entered and completed
> without touching this, by design — it is not a data question. It is now the
> **only** free, unblocked item left in the programme that requires no data, no
> resolution and no accumulation: settling it costs one documentation act and
> unblocks Phase 6 on every future record, including the one Phase 9 recommends
> building. Left open here rather than decided, for the same reason as before.

## Completion Record

- Status: **INADMISSIBLE AS WRITTEN — not entered.** Not COMPLETE and not
  CLOSED: the question is well-posed and remains open on a record that could
  resolve it. Nothing was measured, so nothing was concluded about regimes.
- Result: `PHASE 6 VERDICT: INADMISSIBLE AS WRITTEN`. Deliverable
  `reports/V5_PHASE6_REGIME_EVAL.md` is an **admissibility audit**, committed
  before any regime construction code existed. Three independent grounds, each
  sufficient alone:
  **(1) The question was already asked on the only record that can answer it.**
  `app/forecast_ledger.sqlite3` does not exist — no live forecast has ever been
  frozen — so the frozen PIT-1 record is Phase 6's sole dataset, and
  `validation/REPORT.md` already reports regime-split accuracy on it under
  *"Checked, no effect found"*: 60-day volatility tercile 54.5 / 53.3 / 52.3,
  and SPY-direction 50.0 (n = 26) / 65.7 (n = 35) / 49.3 (n = 73). PIT-1 is
  CLOSED. Re-splitting a closed null on a fresh regime variable is "one more
  carrier", foreclosed by `ROADMAP.md`'s standing exclusions.
  **(2) Regime conditioning is both a rejected family and a disqualifier.**
  `V2-E` (+ regime/VIX/breadth) is REJECT in the registry, and §2.5 makes regime
  concentration disqualifying — which contradicts this phase's own STOP/GO gate.
  See the note above.
  **(3) Power: a regime split partitions cutoffs, not rows.** The contrast is
  between-cluster, so effective n is the cutoff count. ABS-1's best-case contrast
  on this record — 12 dates each side — measured MDE **29.15 pp** against a
  7.5 pp anchor; a regime split gives each arm a fraction of that. Worse, the 12
  dates are not 12 independent regime draws: six of eleven adjacent gaps are
  ≤ 90 days and two are ≤ 23 days (2024-08-13/2024-09-05 at 23 d;
  2026-07-07/2026-07-24 at 17 d), so a 60-day trailing regime window reads
  overlapping data at those spacings. `ROADMAP.md`'s own preregistered criterion
  asked for "no regime collapse, and ≥ 50 independent cutoffs". **No regime MDE
  is asserted** — under CLAUDE.md §7.3 that number may only come from a gate
  committed before it is run.
- Commit: `a992942` — `reports/V5_PHASE6_REGIME_EVAL.md` and this roadmap
  update, committed together and **before** any regime construction code
  exists, so the audit cannot have been written around a number (CLAUDE.md
  §5.2). There is no earlier hash in this phase's chain because there was no
  measurement to gate: unlike Phase 5(a)'s `f53aa96` → `660ce25` → `ade0305`,
  Phase 6 produced no preregistration and no gate code, which is itself the
  finding. Hash recorded in the follow-up commit, per the convention used at
  `2105d4f`, `62b5f2b`, `0c5000e`.
- Examined:
  1. Baseline suite: **904 passed, 65 skipped — green** (`pytest`, before this
     phase). Re-measured at the start of this phase rather than inherited,
     because the working tree carried uncommitted UI edits from earlier in the
     same session.
  2. Final suite: **904 passed, 65 skipped. Delta 0.** This phase edited no
     code. The only files it wrote are `reports/V5_PHASE6_REGIME_EVAL.md` (new)
     and this roadmap entry.
  3. Leak detector: this phase touched **no prediction path**. Run anyway —
     `app/tests/test_validation.py::test_future_cannot_change_the_verdict`
     **1 passed**.
  4. Methodology surfaces: **none touched.** No targets, features, model params,
     examset, ladder or `validation/pit.py`. No amendment required or made.
  5. Frozen records: **read** — `validation/REPORT.md`,
     `reports/EXPERIMENT_REGISTRY.md` (§2, §347, §429, §643, §827),
     `alpha/V5_ABSTENTION_PREREGISTRATION.md`, `reports/V5_PHASE5A_ABSTENTION.md`,
     `ROADMAP.md`. **None was modified, and none was appended to.** Every number
     quoted into the Phase 6 report was copied from them, never recomputed.
  6. Closed programmes: **this phase exists because of two.** Phase 6 as written
     would have re-split PIT-1 (CLOSED) on a new regime variable after its null,
     and its subject overlaps `V2-E` (REJECT, V2 ABANDONED). Both are named in
     the report and **neither was reopened** — no accuracy was recomputed, no arm
     resurrected, no threshold moved.
  7. Measurement: **none on any outcome.** One prediction-side computation ran:
     the calendar spacing of the 12 cutoff dates, read from
     `validation/out/predictions.json`, which contains no realised return and no
     bar after any cutoff. `validation/out/calls.csv` was **not opened**. No
     regime was constructed, no performance split, no accuracy computed.
  8. Sealed exam accessed: **no.**
- Notes for whoever takes this next: the three grounds are separable — repairing
  one leaves the other two standing, and **(2) is free to resolve and blocks
  every future Phase 6 on every record**, so it is worth settling regardless of
  what happens to the programme. Report §6 sets out three admissible options:
  **(a)** Phase 6 reduced to a frozen regime construction plus a power gate,
  stopping before any outcome — this yields the frozen regime artifact Phase 7
  and Phase 10 need anyway, but §4.1 indicates what it will find; **(b)** defer
  to Phase 9, the standing recommendation, now reinforced because regime
  conditioning *multiplies* the resolution requirement rather than reducing it —
  if 12 cutoffs cannot resolve a 7.5 pp main effect they cannot resolve an
  interaction; **(c)** resolve the §2.5 contradiction as a documentation act.
  Recommendation: **(b) with (c) as a free prerequisite.** If Phase 9 proceeds,
  its gate should carry an explicit **independent-draw count** requirement
  anchored on `ROADMAP.md`'s ≥ 50 cutoffs, not merely a hypothesis and a role.
  `app/streamlit_app.py` and `app/tests/test_ui.py` were modified earlier in
  this session in a separate non-research task (a bar-interval P&L metric on the
  portfolio tab); they touch no research path and their tests pass. That work is
  committed separately at `a50a189`, deliberately **not** folded into this
  phase's commit, so the research record carries no code change. Earlier phases
  recorded these files as untouched; that wording described their state at the
  time and is not amended here.

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

- Status: **COMPLETE** (2026-08-15). The gate was applied and **no candidate
  cleared it**, which is a completed analysis, not a blocked one.
- Result: `PHASE 9 VERDICT: NO NEW DATASET AUTHORISED. THE GAP IS DATES, NOT
  DATA`. Deliverable `reports/V5_PHASE9_DATA_GAP_ANALYSIS.md`. Three findings,
  each sufficient alone:
  **(1) All eight candidate families already carry a disposition** in two frozen
  surveys (`reports/INFORMATION_AUDIT.md`, `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md`,
  the latter having ranked ten families). Three were tested and REJECTED
  (earnings surprise `V3-1`/`V4-1`; sector-relative `V2-B`; vol/regime `V2-E`),
  two are blocked on paid data with no free PIT vintage (analyst revisions,
  options-implied — **verified 2026-08-11**), two are vetoed as derivable from
  `alpha/cache` or cutoff-constant (vol term structure; macro, which `V2.1-B`
  measured at −0.00269), and the strongest — corporate events, the survey's own
  winner after ranking ten — was opened as Family 10 and **FAILED its power
  gate**, with a half-width that floors at 49.0 bp as n → ∞. **0 of 8 are both
  un-surveyed and admissible.** The failures cluster on power and availability,
  not on information content.
  **(2) The constraint is arithmetic and no family moves it.** The survey's
  calibrated model `hw = 1.077 · 1.96 · √(V·[ρ+(1−ρ)/k]/D)` was re-evaluated and
  reproduces **both** published anchors exactly — 39.0 bp at k=230/D=177 and
  35 bp / 3.0 pp at D=215 — so it is an instrument, not an assumption. Read at
  the V5 record's own geometry (**D=12, k=30**) it gives **154.8 bp / 13.74 pp**,
  corroborated within ~5% by ABS-1's independently derived 29.15 pp two-band MDE.
  Because the bracket tends to ρ as k → ∞, on that record **infinite breadth buys
  3.8%** while **12 → 50 dates buys 51%**. A data family is a column and some
  names; neither is the axis the interval lives on.
  **(3) The gate therefore cannot be cleared by anything.** A "measurable
  expected role" is a claim relative to resolution, and every candidate's
  plausible effect sits below it. Criteria 2–7 separate the candidates cleanly;
  criterion 1 collapses all eight identically, and criterion 1 is what the gate
  is written on.
  **What is authorised is not a purchase.** The gap is independent dates, and the
  repository already owns the only free source of them: `app/forecast_ledger.sqlite3`
  **does not exist** — Phase 1 built the ledger and Phase 2 the outcome scorer,
  both COMPLETE and tested, and no live forecast has ever been frozen into them.
  A frozen forward forecast is free, PIT **by construction rather than by repair**,
  immune to every veto above, and the only asset that compounds. It is also slow:
  at V5's k=30, **~29 dates → 100 bp, ~115 → 50 bp, ~189 → 39 bp** (≈ 0.6 / 2.2 /
  3.6 years at weekly spacing). No expenditure shortens that.
- Commit: hash recorded in the follow-up commit, per the convention used at
  `2105d4f`, `41a0273`, `62b5f2b`.
- Examined:
  1. Baseline suite: **904 passed, 65 skipped — green**, run before any edit and
     on a clean tree immediately after the Phase 6 commits.
  2. Final suite: **904 passed, 65 skipped. Delta 0.** This phase edited no code.
     The only files written are `reports/V5_PHASE9_DATA_GAP_ANALYSIS.md` (new)
     and this roadmap.
  3. Leak detector: this phase touched **no prediction path**. Run anyway —
     `app/tests/test_validation.py::test_future_cannot_change_the_verdict`
     **1 passed**.
  4. Methodology surfaces: **none touched.** No targets, features, model params,
     examset, ladder or `validation/pit.py`. No amendment required or made.
  5. Frozen records: **read** — `reports/EXPERIMENT_REGISTRY.md` (§2, §6–§12),
     `reports/INFORMATION_AUDIT.md`, `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md`.
     **None was modified, and none was appended to.** Every disposition and every
     model input was copied from them, never refitted.
  6. Closed programmes: **this phase's entire subject matter is closed work**, and
     that is why the verdict is the conservative one. It re-ranks nothing into
     admissibility, re-runs no failed gate at a friendlier parameter, and revisits
     no spent slot. V3 (3/3, CLOSED), V4 (slot 1 spent, slot 2 BARRED) and
     Family-10 (unspent, power FAIL) are **unchanged**. Registry §10.3's bars on a
     shorter block, an enlarged item set and another horizon are undisturbed;
     424B5 and GDELT stay WATCHLIST.
  7. Measurement: **nothing measured on any outcome, and no data ingested.** No
     network call, no source opened, no family panel built. One computation ran:
     the published resolution formula re-evaluated at stated (D, k) pairs, using
     inputs quoted from `ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §1. It reads no outcome
     and **gates nothing** — any actual study still needs its own §2.6 gate,
     computed and committed before it is run.
  8. Sealed exam accessed: **no.**
- Notes for whoever takes this next: the deliverable filename is
  `reports/V5_PHASE9_DATA_GAP_ANALYSIS.md` as this section specifies — note it
  differs from the shorter `V5_PHASE9_DATA_GAP.md` used in passing elsewhere.
  Phase 9 explicitly **does not** resolve the §2.5 versus Phase-6-gate
  contradiction recorded at the Phase 6 STOP/GO gate; that stays open and remains
  the programme owner's. The three prior nulls (SN-1 39 bp, Family-10 49 bp floor,
  AMS-1 31 bp) should be read alongside §4.4 of the report: the resolution at
  which each of them independently found nothing is ~3.6 years of accumulation
  away at V5's breadth. That is the honest size of the prize, and it argues for
  writing Phase 7's policy well rather than quickly — it governs what is frozen,
  and a badly specified freeze cannot be re-run, because the dates only happen
  once.

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
