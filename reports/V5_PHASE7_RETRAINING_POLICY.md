# V5 Phase 7 — Retraining & Promotion Policy

**Verdict: `PHASE 7 POLICY ADOPTED. NOTHING PROMOTED, NOTHING DEMOTED`.**

This phase writes policy and builds the gate that enforces it. It promotes no
model, demotes no model, changes no production weight, and touches no
methodology surface. No outcome file was opened; `app/forecast_ledger.sqlite3`
still does not exist, and that fact is what makes this the right moment to
write the policy rather than the wrong one.

| | |
|---|---|
| Roadmap ACTIVE PHASE | **Phase 7 — Retraining & Promotion Policy** |
| Deliverable | this file + `app/core/promotion.py` + `app/tests/test_promotion.py` |
| STOP/GO gate | *"No automatic production promotion without explicit evidence gate."* **Met** — see §7 and §11 |
| Production weight changed | **None.** `alpha/adapter.py` untouched |
| Models promoted / demoted / retired | **0 / 0 / 0** |
| Exam | Sealed. Not accessed |

---

## 1. The finding that shapes the whole policy

**This system does not retrain. It recomputes.**

Not one component in the repository persists a trained artefact. There is no
checkpoint, no saved weight file, no serialised fit anywhere on the production
path. `model_registry` states it component by component:

| Component | Status | What the registry says it does |
|---|---|---|
| 10 technical indicators, 3 rule agents | PRODUCTION | *"none — nothing is fitted, so nothing is refitted"* |
| `ensemble.ultimate` | PRODUCTION | *"recomputed on every evaluation. No versioned artefact, no promotion or rollback rule (Phase 7)"* |
| 3 neural projections | CHALLENGER | *"retrained from scratch whenever the UI fingerprint changes; no checkpoint is persisted and no promotion rule exists yet (Phase 7)"* |
| 19 RL agents | EXPERIMENTAL | *"user-triggered only; no checkpoint is written or reloaded, so no version survives the session"* |

That changes what Phase 7 is for. Half the conventional retraining vocabulary —
checkpoint rollback, artefact promotion, model registries of saved fits —
addresses a hazard this repository does not have.

The hazard it **does** have is sharper, and it is exactly the one the phase goal
names: *"make adaptation controlled rather than continuous overfitting."*
`ensemble.ultimate` is the single production component that genuinely adapts,
and it re-derives its source weights **from the tail holdout at every
evaluation** — unbounded frequency, no version, no record, no gate. Phase 0
logged it at severity 3 for a related reason: historical weights are
reconstructed, not remembered.

So the policy below constrains **re-derivation**, not checkpoint loading.

---

## 2. The nine definitions the roadmap requires

### 2.1 Rolling vs expanding training window — **EXPANDING**

Any component ever fitted on the forecast ledger uses an **expanding** window.

The reason is Phase 9's, and it is not the usual one. Phase 9 established that
this programme's binding constraint is **independent dates**, and that they
cannot be bought at any price — only accumulated, at roughly 29 dates to a
100 bp resolution and 115 to 50 bp. A rolling window **discards the scarcest
asset the programme owns.**

A rolling window is justified only by non-stationarity large enough to outweigh
that cost — and detecting non-stationarity of that size requires resolution the
programme does not have and will not have for years. The burden therefore sits
on any future proposal for a rolling window, which must carry its own
preregistered gate. Expanding is the default precisely because it is the option
that does not throw away dates.

### 2.2 Retraining frequency — **BOUNDED BY MATURITY, NOT BY THE CLOCK**

A fitted component that holds or seeks production status may refit **at most
once per maturity batch** — that is, only after at least one new *independent*
cutoff has matured and been scored. Refits are never triggered by clock time, by
a UI interaction, by a page load, or by a cache fingerprint.

This is the rule that bites hardest on the current code: `ensemble.ultimate`
recomputes on every evaluation, and three neural challengers refit on every
fingerprint change. Neither is compliant. §4 records that honestly rather than
claiming the policy already holds.

### 2.3 Minimum new observations — **ONE NEW INDEPENDENT CUTOFF TO REFIT; FIFTY TO RESTATE STATUS**

Two different questions, two different bars:

- **To refit at all:** ≥ 1 new independent cutoff since the last fit. This stops
  a refit that consumes no new information, which is all a refit on a re-read of
  the same data can be.
- **To change a status on the strength of a fit:** `MIN_INDEPENDENT_CUTOFFS = 50`,
  taken verbatim from `ROADMAP.md`'s own preregistered criterion (*"no regime
  collapse, and ≥ 50 independent cutoffs"*) rather than reinvented.

"Independent" is enforced, not asserted: cutoffs whose forecast windows overlap
are collapsed before they are counted (§3).

### 2.4 Frozen vs retuned hyperparameters — **FROZEN**

Hyperparameters are **frozen**, and are retuned only under a dated amendment in
the relevant preregistration — never automatically, never as part of a refit,
and never by a search run against the ledger.

The precedent already exists: `alpha/models.py::MODEL_A_PARAMS` is frozen by
CLAUDE.md §1.2 and §8. This extends the same rule to every fitted component in
the V5 path. The reason is arithmetic: an automatic hyperparameter search over a
record of 50 cutoffs is mining, and the programme has spent four phases
establishing that a record that size cannot resolve a main effect, let alone a
search over a parameter grid.

**A refit re-estimates parameters. It never re-selects hyperparameters.** That
sentence is the whole rule.

### 2.5 Model versioning — **IDENTITY IS STABLE, VERSION IS THE SOURCE HASH**

Already built, in Phase 3, and unchanged here:

- `model_id` survives retraining; `version` is the sha256 of the exact source in
  use, and `frozen_version` covers external identifiers.
- `version_key` names the `ForecastRecord.model_versions` entry carrying it, so
  any frozen forecast resolves back to versioned identities without guessing.
- `POLICY_VERSION` in `promotion.py` versions the policy itself, so a promotion
  records which thresholds it was decided under.

**What is not built: a versioned *fitted artefact*.** There is none to version —
see §1 — and §4.2 specifies what building one would require rather than
half-building it now.

### 2.6 Challenger promotion rule — **SEVEN GATES, ALL OF THEM**

`promotion.evaluate_promotion`. Detail in §3.

### 2.7 Degradation rule — **ASYMMETRIC, DELIBERATELY**

`promotion.evaluate_degradation`. A model is degraded only when the evidence is
**resolvable and points against it**. An unresolvable record returns
`INSUFFICIENT_EVIDENCE`, never `DEGRADED`.

The asymmetry is the point, and it is the same distinction Phase 6 drew between
an admissibility block and a null result: *"we cannot tell"* is not a finding of
harm. Making it one would let a thin record demote a model, which is the
mirror image of letting a thin record promote one.

### 2.8 Retirement rule — **HUMAN ACT, THREE TRIGGERS, NEVER DELETION**

A component moves to RETIRED only by a human commit, and only on one of:

1. `DEGRADED` at two consecutive **resolvable** evaluations — one is a result,
   two is a pattern, and both must have cleared the resolution floor;
2. a point-in-time defect discovered in it, which is immediate and needs no
   performance evidence at all;
3. closure of the information family it belongs to.

Retirement means *"not callable by V5 production or scoring"* and **never**
deletion of historical research material — the registry's existing wording,
preserved because it is already right.

### 2.9 Rollback behaviour — **REVERT THE COMMIT**

Production status lives in `model_registry` **source**. Changing it is a human
edit in a reviewable commit, so rolling back a promotion is reverting that
commit. There is no checkpoint to restore, because no fit is persisted (§1).

This is not a workaround. For this repository it is strictly better than an
artefact store: the rollback is reviewable, atomic with the code that produced
it, and recorded in the same history that already carries every preregistration
and gate. The one condition under which it stops being sufficient is stated in
§4.2 — if a fitted artefact is ever persisted, rollback needs an artefact store,
and until then it does not.

---

## 3. The gate, in detail

`promotion.evaluate_promotion` returns a `Verdict`. Every gate must pass, and
each carries the number behind it so a promotion commit can quote its own
arithmetic.

| Gate | Passes when |
|---|---|
| **G1 registered** | the model exists in the Phase 3 registry |
| **G2 challenger** | its status is CHALLENGER — promotion is not a route into production from EXPERIMENTAL, REJECTED or RETIRED |
| **G3 point-in-time** | `pit_status` is PIT-ADMISSIBLE. **No amount of evidence buys production weight for a leaking model** |
| **G4 evidence exists** | the ledger holds scored, matured rows for this model at this horizon |
| **G5 resolution** | ≥ 50 **independent** cutoffs |
| **G6 breadth** | ≥ 5 symbols |
| **G7 skill** | the cutoff-clustered advantage over its **own declared baseline** has a lower bound above zero |

Three properties are worth drawing out.

**The counting unit is the cutoff, never the row.** Rows within a cutoff are
averaged first, so a symbol-rich day contributes one number and the interval
reflects the spread *between days*. This is the lesson that cost the programme
Phase 5(a) and Phase 6, and `test_breadth_does_not_manufacture_draws` fixes it in
place: adding 100× the symbols to each cutoff leaves the half-width unchanged.

**Overlapping cutoffs are collapsed before they are counted.** A forecast made on
Monday for a week ahead and one made on Tuesday for the same week are not two
draws — they resolve against overlapping price paths. `independent_cutoffs` takes
the largest non-overlapping set by greedy earliest-finishing selection, which is
optimal for interval scheduling and so is a true maximum rather than an estimate.
Sixty daily cutoffs at a weekly horizon are **nine** draws, not sixty, and a test
asserts exactly that.

**G7 measures against the baseline the forecast itself declared.** The threshold
is a lower bound above zero rather than a positive margin, because the baselines
here are already strong: the entire PIT-1 record failed to beat
`always_bullish`. "Beats its declared baseline, resolvably" is a real bar.

### 3.1 What the gate says today

Every model. The ledger is empty, so:

```
neural.lstm @ 5x1d: BLOCK
  [PASS] G1 registered
  [PASS] G2 challenger
  [PASS] G3 point-in-time
  [FAIL] G4 evidence exists — 0 scored rows
  [FAIL] G5 resolution — 0 independent cutoffs against a floor of 50
  [FAIL] G6 breadth — 0 symbols against a floor of 5
  [FAIL] G7 skill — lower bound nan against a floor of +0.000000
```

**A missing ledger is not a neutral state — it is a failed gate.** BLOCK is the
correct verdict for a repository whose ledger has never been written to, and
`test_an_empty_ledger_blocks_rather_than_abstains` holds it there.

---

## 4. Honest accounting of what is *not* compliant

Phase 7 writes the policy. It does not retrofit the code to satisfy it, and
pretending otherwise would be the failure mode this repository exists to avoid.

### 4.1 Two live components violate §2.2 today

| Component | Violation |
|---|---|
| `ensemble.ultimate` | re-derives weights **on every evaluation**; §2.2 allows once per maturity batch |
| `neural.*` (×3) | refit on **every UI fingerprint change**; same rule |

Neither is repaired here, for a reason that is not laziness: repairing them
changes the production prediction path, and the correct order is policy first,
then a change made deliberately against a written rule. That is what
*"write policy before automating retraining"* means, and it is the first task on
Phase 7's own list.

Recorded so the gap is visible rather than implied. Both are additionally
constrained by the fact that neither currently **fits on the ledger at all** —
they fit on price frames — so §2.2 binds them prospectively rather than today.

### 4.2 Versioned fitted artefacts — specified, not built

The roadmap task *"add versioned model artefacts"* is **not done**, and the
version identity described in §2.5 is not a substitute for it.

What would be required, if a component ever persists a fit: a content-addressed
artefact store keyed by `(model_id, source version, training window, data
fingerprint)`; a record of that key on every `ForecastRecord` that used it; and
a rollback path that restores an artefact rather than reverting a commit. None
of it is built, because building an artefact store for training that does not
happen would be infrastructure ahead of a need — and the moment a need appears
is the moment §2.9's commit-revert rollback stops being sufficient, which is a
condition, not a guess.

### 4.3 The incumbent would not pass its own gate

`ensemble.ultimate` holds PRODUCTION and there is no evidence for it either way.
`promotion.GRANDFATHERED` records this as a **debt**, in its own words,
separately from the thirteen closed-form components — which are listed for a
different reason entirely: nothing is fitted in them, so there is nothing to
retrain, no version to roll back to, and no fit that can degrade. The gate is
simply the wrong instrument for those, and a test asserts the two reasons never
collapse into one blanket excuse.

**Phase 7 does not demote the incumbent.** Whether it keeps production weight is
a Phase 11 decision.

---

## 5. The structural enforcement

A policy that lives only in a document is a suggestion. This one has a
mechanism:

```python
promotion.assert_production_is_declared()
```

Every PRODUCTION model must appear in either `GRANDFATHERED` (with a stated
reason) or `PROMOTED` (naming the commit whose verdict passed). A model that
acquires PRODUCTION status without an entry in one of them **fails the test
suite**. `PROMOTED` is currently empty, and it is meant to be: nothing in this
repository has ever been promoted on evidence.

`GRANDFATHERED` is enumerated by hand rather than derived from model family —
deliberately, because deriving it would auto-absorb the next production
component, which is precisely the drift the gate exists to prevent.

Two further invariants are tested: that the gate **decides and never acts** (no
verdict can change a status), and that the enforcement is itself capable of
failing — an invariant that cannot fail guarantees nothing.

---

## 6. Why these thresholds are trustworthy, and why that is temporary

Every threshold in this policy was declared while **the ledger was empty**.

`app/forecast_ledger.sqlite3` does not exist. No forecast has ever been frozen.
A threshold written now cannot have been chosen to fit a result, because there
is no result to fit it to. That is the strongest form CLAUDE.md §5.2's
temporal-ordering discipline can take, and it is available **exactly once** — the
first outcome written to that ledger ends it permanently.

Any later change to `MIN_INDEPENDENT_CUTOFFS`, `MIN_SYMBOLS` or
`MIN_ADVANTAGE_LOWER_BOUND` is therefore a threshold change made **after** seeing
data, and must be treated as one: a dated amendment, with `POLICY_VERSION`
bumped, and the reason stated before the number is moved. Loosening one to admit
a model that just failed is the specific move CLAUDE.md §3.2 forbids.

---

## 7. STOP / GO gate

> No automatic production promotion without explicit evidence gate.

**MET**, in three independent ways, each sufficient alone:

1. **There is no automatic path.** Status lives in registry source; changing one
   is a human commit. No function in this codebase writes a production status.
2. **The gate exists and blocks by default.** `evaluate_promotion` returns BLOCK
   for every model today, and an absent record fails rather than abstains.
3. **The absence of a gate is a test failure.** `assert_production_is_declared`
   turns "a model quietly acquired production status" from a thing a reviewer
   might notice into a thing the suite catches.

---

## 8. What this document does not conclude

- **It does not endorse the incumbent.** §4.3. The grandfathering is a recorded
  debt, not a verdict.
- **It does not promote, demote or retire anything.** 0 / 0 / 0.
- **It does not claim the code is compliant.** §4.1 names two live violations.
- **It does not assert any model's skill.** No outcome was read. Every number in
  §3.1 is a count of an empty set.
- **It does not authorise switching the ledger on.** Phase 9 §6 identified that
  as the one action that manufactures independent dates; this policy is its
  precondition, not its trigger. The decision remains the programme owner's.

---

## 9. Phase 7 task status

- [x] **Write policy before automating retraining** — §2, and nothing was
      automated. This is the task's stated order and it was followed.
- [ ] **Add versioned model artefacts** — **NOT DONE.** Identity and source-hash
      versioning exist from Phase 3; a persisted fitted artefact does not exist
      to version, and §4.2 specifies what building one would require rather than
      half-building it. Recorded as incomplete rather than reinterpreted.
- [x] **Add deterministic retraining tests where possible** — 23 tests, all
      hermetic, building their own frames; no ledger, no cache, no network.
- [x] **Prevent newly trained models from entering production automatically** —
      §5. Structural, and the enforcement is itself tested for failability.
- [x] **Require challenger evaluation before promotion** — §3. Seven gates,
      all mandatory, blocking by default.

**`PHASE 7 POLICY ADOPTED. NOTHING PROMOTED, NOTHING DEMOTED`**
