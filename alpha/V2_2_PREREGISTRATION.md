# V2.2 pre-registration — fix the carrier

**Written 2026-08-08, after the V2.1 ladder closed its gate and before any V2.2
model exists.** No V2.2 arm has been fitted, no V2.2 carrier has been applied to
outcome data, and no V2.2 IC has been computed on any cutoff.

**ACCEPTED 2026-08-08, before the first fit.** Reviewed and accepted with the two
amendments recorded in §12, both of which were made while §11's tests existed but
no V2.2 model had been fitted and no V2.2 IC had been computed. The acceptance and
the amendments are the first entry of `V2_2_EXPERIMENT_LOG.md`. Nothing below may
be amended from here on.

This document does not edit, supersede or reinterpret `PREREGISTRATION.md`,
`V2_1_PREREGISTRATION.md` or `V2_1_LADDER_PREREGISTRATION.md`. Those record
completed experiments. Everything they fixed that is not restated here is
inherited unchanged.

---

## 0. Why there is a V2.2

The V2.1 ladder's gate closed and its headline finding was not about the market:

| | mean IC, 255 development cutoffs |
|---|---|
| Rank the cross-section by `ret_12_1` directly | **+0.02115** |
| Fit a GBM on `ret_12_1` alone, then rank by its output | **+0.00053** |

Inserting the learner between the factor and the ranker destroyed ~98% of the
factor's cross-sectional information. The mechanism was measured: within a
cutoff, V2.1-A's prediction is provably a step function of `ret_12_1` (distinct
predicted values equal the number of runs when rows are sorted by it), and its
within-cutoff Spearman correlation against its own input averages **−0.198**,
negative on **224 of 255** cutoffs. Trained with squared error on the pooled
winsorised *level*, the learner fit a predominantly **decreasing** map — and that
map was then used to **rank**.

Every V2 and V2.1 arm passed its factors through that same carrier. So this is a
defect in the information path, not a finding about markets, and it is a
candidate explanation for V2's null as well as V2.1's.

**V2.2 changes the carrier and nothing else.** The feature set is frozen at
V2.1-C's 35 columns. No feature is added, removed or re-justified. The learner's
hyperparameters are unchanged. The universe, horizon, target, eligibility,
walk-forward, purge, embargo and cutoff grid are unchanged. If a V2.2 arm beats
V2.1-C or V2.1-D, the difference is attributable to the carrier, because the
carrier is the only thing that differs.

### The single primary question

> Can the cross-sectional information in the existing factors be preserved while
> the model learns contextual adjustments, and does that produce a material,
> stable improvement over **both** simple 12-1 momentum **and** the
> hand-specified regime-switching rule?

---

## 1. Hard constraints, restated as commitments

1. **The 72 frozen V2.1 exam cutoffs are not opened, scored, modified, deleted
   or rebuilt.** The digest stays
   `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.
   `out/v2_1_exam_predictions.json` must not come into existence during V2.2.
2. V2.2 runs on **development cutoffs only**, obtained through
   `examset.development_only()`, which slices and then asserts no exam cutoff
   survived.
3. No V2 or V2.1 artefact or pre-registration is edited.
4. Production weight stays **0**, action **HOLD**. `alpha/adapter.py` is not
   modified. Nothing in this document can change that.
5. Every threshold below is fixed here, before the first fit, and none may be
   lowered afterwards.
6. **Even if a V2.2 arm clears every gate below, the V2.1 exam is not opened.**
   Whether a paper frozen for a V2.1 arm is an appropriate test of a V2.2 arm is
   a separate question, and it gets its own pre-registration written before any
   exam date is touched. §8 states what that document will have to answer.

---

## 2. What "carrier" means, precisely

The carrier is every step between a raw feature and a position in the ranking:

```
raw feature  ->  [input transform]  ->  learner( [training target] )
             ->  [output combination]  ->  within-cutoff rank  ->  IC
```

V2.1's carrier was: raw level in, winsorised level target, model output replaces
everything, rank. Three of those four steps are candidates for the defect, and
V2.2 fixes them in three structurally different ways — one per arm.

### 2.1 The rank transform

For a stock-level column `c`, define within each cutoff

```
z__c  =  rank_pct(c)  −  0.5          ∈ [−0.5, +0.5], NaN preserved
```

`rank_pct` is `groupby(cutoff).rank(pct=True, na_option="keep")` — the same
operation `models.simple_factor_scores` already uses to build the benchmarks. It
reads only features at that cutoff and no outcome, so it introduces no leakage.

**The 26 market-context columns are NOT rank-transformed.** They take one value
for the entire cross-section at a cutoff (verified by
`test_market_context_is_constant_within_a_cutoff`), so a within-cutoff rank would
map every name to 0.5 and annihilate the column. Context passes through as a raw
level, which is correct: the tree splits on it *across* cutoffs, which is the only
way a cutoff-constant column can carry information at all.

This asymmetry is a pre-registered design decision, not an oversight, and a test
asserts it.

### 2.2 The base score

```
S0  =  z__ret_12_1
```

`S0` is **rank-identical to Benchmark 1** by construction, so ranking by `S0`
must reproduce Benchmark 1's IC exactly. That identity is an assertion, not a
hope: if it does not hold to the last digit, the pipeline is wrong and V2.2 stops.

---

## 3. The arms — three, fixed now, family size **k = 3**

Common to all three, and identical to V2.1-C/D so the comparison is clean:

| Item | Value |
|---|---|
| Cutoffs | the 316 frozen V2.1 development cutoffs, nothing else |
| Features | **exactly V2.1-C's 35 columns** — `ret_12_1` + 8 stock-level + 26 market-context. No additions. |
| Learner | `HistGradientBoostingRegressor`, `models.MODEL_A_PARAMS`, **unchanged and not tuned** |
| Walk-forward | expanding, refit at 65 sessions of staleness, min 60 training cutoffs |
| Purge/embargo | `T′ + 5 + 5 ≤ T` |
| Scoring target | `alpha_5d`, always, for every arm and every diagnostic |
| Intervals | moving-block bootstrap, block 4, 10,000 draws; block 1/2/8 reported |
| Sidedness | two-sided throughout |

Changing the model is allowed. Changing the yardstick is not: every arm is
scored on `alpha_5d` by per-cutoff Spearman IC, whatever it trained on.

### 3.1 V2.2-A — rank-preserving input

The minimal fix: stop feeding the learner pooled levels.

* **Input:** `z__` of the 9 stock-level columns (`ret_12_1`, `ret_5d`, `ret_20d`,
  `rvol_20d`, `rvol_60d`, `sma200_dist`, `overnight_mean_20d`,
  `intraday_mean_20d`, `overnight_share_60d`) + the 26 raw context columns. 35
  columns.
* **Target:** `target_rank` — the within-cutoff percentile of `alpha_5d`, already
  in the panel.
* **Output:** the model's prediction, ranked.

**Contrast this buys:** V2.1-D used *raw* stock-level inputs with the same rank
target and the same 35 columns. A − D therefore isolates the **input** side of
the carrier, cleanly, with everything else held fixed.

**What it does not guarantee.** A is still free to produce a non-monotone map,
so it does not *structurally* prevent the V2.1-A pathology — it only removes one
of its two suspected causes. That is why arms B and C exist.

### 3.2 V2.2-B — factor plus bounded learned adjustment

The structural fix: the model may not replace the factor, only tilt it.

* **Input:** identical to A's 35 columns.
* **Target:** the **residual after the base**, computed on training slices only:

  ```
  y_resid  =  target_rank  −  rank_pct(ret_12_1)         ∈ (−1, +1)
  ```

  The model is therefore asked "how much should this name out- or under-rank its
  own momentum?", never "where does this name belong".
* **Output combination:**

  ```
  u      =  rank_pct( model prediction )  −  0.5          ∈ [−0.5, +0.5]
  final  =  z__ret_12_1  +  λ · u
  ```

  Ranking the adjustment within cutoff before adding it puts both terms on
  exactly the same scale, so λ is interpretable in rank units rather than in
  whatever units the residual happened to come out in.

* **λ = 0.50, fixed here.** Rationale: an equal-weight blend is the neutral prior
  between a factor with a known ~+0.021 out-of-sample IC and a learned tilt of
  unknown value. It was not chosen from any V2.2 number, because none exists.

* **λ ∈ {0.00, 0.25, 1.00} are reported as a sensitivity curve and are NOT
  arms.** λ = 0 is an identity check: `final` must be rank-identical to
  Benchmark 1. **If λ = 0.25 or λ = 1.00 scores better than λ = 0.50, that is
  reported and does not become the arm.** Re-choosing λ after seeing ICs is
  exactly the tuning this document exists to forbid.

**The bound this buys, provable and testable.** Because `u ∈ [−0.5, +0.5]`, for
any two names *i, j*:

> `z__ret_12_1(i) − z__ret_12_1(j) > λ`  ⟹  `final(i) > final(j)`

At λ = 0.5, any two names more than 0.5 apart in momentum percentile **keep their
order no matter what the model says**. A top-decile momentum name cannot be
pushed below roughly the 40th percentile. The V2.1-A pathology — a wholesale sign
inversion of the factor — is impossible by construction, not by hope. A test
asserts the bound on the frozen predictions.

### 3.3 V2.2-C — contextual momentum with no sign reversal

The constraint fix: let context change *how much* momentum matters, never *which
way*.

* **Input and target:** identical to A.
* **Learner:** `MODEL_A_PARAMS` plus
  `monotonic_cst = +1` on `z__ret_12_1`, `0` on the other 34 columns.

The prediction is then required to be non-decreasing in the momentum rank at
fixed values of everything else. Context can flatten the momentum slope, steepen
it, or make it locally flat — but two names identical in the other 34 columns can
never be ordered against their momentum.

**What the constraint does and does not guarantee (amendment A2, §12).** sklearn's
`monotonic_cst` is a statement about the *function*: the prediction is
non-decreasing in `z__ret_12_1` **holding the other 34 columns fixed**. Inside one
cutoff the 26 context columns are fixed — they are cutoff-constant — but the eight
stock-level ranks are not. So for arm C, two names can still be ordered against
their momentum by a difference in, say, `z__rvol_20d`, and no constraint sklearn
offers prevents that. The guarantee arm C carries is exactly the prose above: two
names *identical in the other 34 columns* can never be ordered against their
momentum. A wholesale sign inversion of the kind V2.1-A produced is ruled out;
individual inversions are not. Arm C's inversion count against `ret_12_1` is
therefore **measured and reported**, not asserted to be zero. For the one-feature
rung `S1-C` there is no "everything else" to hold fixed, so there the guarantee is
unconditional and zero inversions *is* asserted.

**Verified feasible before pre-registering it:** sklearn 1.9.0's
`HistGradientBoostingRegressor` accepts `monotonic_cst` and handles NaN in a
constrained column. That was checked on synthetic data, with no outcome data of
any kind.

**Disclosed risk, found in that same synthetic check and recorded here rather
than discovered later.** When the true pooled relationship runs *against* the
constraint, the constrained learner does not merely flatten — it collapses to a
**constant**. A constant prediction has no within-cutoff ordering,
`stats.spearman_ic` returns NaN for that cutoff (fewer than 3 distinct values),
and the cutoff drops out of the sample.

Given that V2.1-A learned a decreasing map on the *level* target, a partial
collapse of C on the *rank* target is a live possibility. It is pre-registered as
an **informative outcome, not a failure to be worked around**: a C that collapses
says that once market context is conditioned on, the pooled momentum-rank →
forward-rank relationship is not monotone increasing, which is a substantive
finding and is reported as one. It is detected by two of the §5 diagnostics
(distinct predictions per cutoff, and scored-cutoff count) and by the §6
eligibility floor, and it is **not** a licence to drop the constraint and re-run.

### 3.4 What is not in V2.2

No new features, no removed features, no hyperparameter search, no additional λ,
no fourth arm, no neural network, no change to regime definitions, thresholds,
horizon, target construction, universe or eligibility, and no change to
`adapter.py`. If all three arms are null, the answer is "the carrier fix does not
produce a material improvement" — not a fourth arm.

---

## 4. Reference rungs and the diagnostic grid — none of them are arms

These are cheap, they carry no p-value, and **none of them may be selected, gated
on, or promoted to an arm.** They exist to locate the defect.

### 4.1 The mandatory one-feature sanity test

For each arm's carrier, applied to `ret_12_1` **alone**:

| Rung | Carrier |
|---|---|
| `S0` | no model. Rank by `z__ret_12_1`. Must equal Benchmark 1 exactly. |
| `S1-A` | A's carrier, one feature: unconstrained GBM on `z__ret_12_1` → `target_rank` |
| `S1-B` | B's carrier, one feature: residual target, `final = z__ret_12_1 + 0.5·u` |
| `S1-C` | C's carrier, one feature: monotone-constrained GBM → `target_rank` |

This is the test the whole study turns on: **inserting a learner between the
factor and the ranker must not cost material information.**

### 4.2 The 2×2 carrier grid — where the defect actually lives

One feature (`ret_12_1`), four cells, isolating input representation from target
representation:

| | target = winsorised level | target = within-cutoff rank |
|---|---|---|
| **input = raw level** | this cell **is V2.1-A** (+0.00053, re-reported) | |
| **input = `z__` rank** | | this cell is `S1-A` |

Four numbers that decompose the +0.02115 → +0.00053 collapse into an input effect
and a target effect. **The grid diagnoses; it does not choose.** The carrier used
by the arms is fixed in §3 by the prior argument that a within-cutoff rank metric
should be fed within-cutoff ranks on both sides — not by whichever cell scores
best.

---

## 5. Critical diagnostics — measured for every arm and every rung

All of these are computed and reported before any arm's IC is interpreted.

1. **Within-cutoff Spearman(final score, `ret_12_1`)** — mean, min, max, and the
   share of cutoffs where it is negative. V2.1-A's was −0.198 / negative on
   224 of 255.
2. **Inversion count** — sort a cutoff's rows by `ret_12_1`; count adjacent pairs
   where the score decreases. Zero for a monotone carrier, by definition.
3. **Prediction runs** — sorting by `ret_12_1`, the number of runs of constant
   score, against the number of distinct scores and the cross-section width.
   Runs == distinct proves the score is a univariate function of momentum;
   distinct ≈ width proves it is not.
4. **Correlation of the final score with the base momentum factor**, per cutoff
   and pooled.
5. **Can the model reverse the base factor?** Reported as the fraction of cutoffs
   with Spearman(final, `ret_12_1`) < 0, and — for B — the λ-bound of §3.2
   asserted directly on the frozen predictions.
6. **Raw factor ranking vs learned univariate carrier** — §4.1 and §4.2.
7. **Distinct predictions per cutoff** — the collapse detector for arm C.

---

## 6. Eligibility, selection, and the gate

### 6.1 Carrier integrity — G1, an eligibility condition

An arm is eligible for selection only if its own one-feature rung of §4.1
satisfies:

> **paired mean per-cutoff IC of `S1-x` minus `S0` ≥ −0.005**

The threshold, justified before the fact: `S0` is ≈ +0.021, so −0.005 permits
about a quarter of the factor's signal to be lost to the discretisation a
histogram learner necessarily introduces (≤255 bins produce ties, and ties cost
Spearman IC), while rejecting anything resembling V2.1-A, which lost −0.0206 —
98% of the factor.

An arm whose carrier fails G1 is **reported in full and marked
carrier-defective**, and is not eligible for selection whatever its IC.

Second eligibility condition: an arm must score **≥ 200 development cutoffs**
(V2.1's arms all scored 255). Fewer means predictions are being dropped —
the arm-C collapse of §3.3 is the anticipated cause — and the arm is reported as
carrier-defective rather than compared on a different sample.

### 6.2 Selection

**Highest mean development IC among the eligible arms.** Ties, specified though
they will not occur at five decimals, go to the structurally safer arm: **B
before C before A** (B's bound is provable, C's is conditional on the constraint
binding, A's is not guaranteed at all).

### 6.3 The gate — what counts as a V2.2 success

All four must hold for the **selected** arm, on development:

| # | Condition | Threshold |
|---|---|---|
| G2 | Beats Benchmark 1 (12-1 momentum, +1) | paired mean IC difference > 0, 95% block-bootstrap CI excludes 0 |
| G3 | Beats Benchmark 3 (regime-switched momentum) | same |
| G4 | Breadth — not a few extreme dates | the paired difference is > 0 on **≥ 55%** of scored cutoffs, against **both** B1 and B3 |
| G5 | Stability | paired mean difference > 0 in **each chronological half**, against **both** B1 and B3 |

**Benchmark 3 is a gate in V2.2, where V2.1 only reported it.** Reason, fixed
before any V2.2 number exists: on V2.1's development set B3 produced +0.02836
with the only benchmark CI excluding zero, and the best learned arm exceeded it
by +0.0059 with an interval of [−0.02451, +0.04076]. A three-line rule with no
fitted parameters is the real incumbent, and a study that will not measure itself
against the strongest free alternative is not asking the question in §0.

**The bar's difficulty, disclosed up front.** On 255 cutoffs the block-bootstrap
half-width of the paired difference is ≈**0.034** against B1 and ≈**0.033**
against B3 (measured from the frozen V2.1 record). G2 and G3 therefore require a
point advantage of roughly **+0.034** and **+0.033**. V2.1-D managed +0.013 and
+0.006. This is a hard gate and it is stated as one now, so that failing it later
cannot be reported as a surprise or answered by softening it.

### 6.4 Multiplicity

Holm–Bonferroni across the **k = 3** arms on criterion-1 bootstrap p-values.
Reference rungs, grid cells and λ sensitivities carry no p-value and are not in
the family, because none of them can be selected. Were a λ variant ever
promoted — which §3.2 forbids — the family would be 5, and that is recorded here
so the forbidden move has a visible price.

### 6.5 Costs

Unchanged from `V2_1_PREREGISTRATION.md` §4.1: a balanced long-short quintile
book, turnover measured as the fraction of each leg replaced between consecutive
scored cutoffs, charged at 5 bps one-way with 10 and 20 bps reported beside it.
Turnover and net spread are **reported for every arm and gate nothing on
development**. V2.1's arms replaced 69–72% of each leg weekly; arm B at λ < 1
should trade *less* than an unconstrained model, and whether it does is a
secondary result worth having.

---

## 7. Regimes, and the BEAR warning

Regime breakdowns are **diagnostic only**. They may not select an arm, explain a
failure, restrict a conclusion to a bucket, or justify an interaction.

Recorded in advance because the pattern has now appeared twice: V2's development
edge lived in `BEAR_TREND` and **inverted to `SIDEWAYS` on its exam**; V2.1-C and
V2.1-D earned +0.076 and +0.066 in the 27 bear cutoffs against +0.001 and −0.002
in the 24 sideways ones. **A V2.2 arm that concentrates in `BEAR_TREND` is to be
treated as a warning signal, not as evidence of robustness**, and the report must
say so in those words if it happens.

---

## 8. If an arm clears the gate

The exam is **still not opened**. What happens instead:

1. V2.2 stops and reports.
2. A separate document — `V2_2_EXAM_DECISION.md` — is written before any exam
   date is touched, and it has to answer, in advance:
   * Is a paper frozen under `V2_1_PREREGISTRATION.md` for a V2.1-family arm a
     valid test of a V2.2 arm, or does reusing it silently treat V2.2 as though
     it had been part of the original experiment?
   * What is the family size for the exam correction, given that V2.1 already
     selected one arm from four and V2.2 would select another from three?
   * **The resolution problem.** Scaled from the measured development dispersion,
     the 72-cutoff exam's block-bootstrap half-width on a paired difference
     against B1 is ≈**0.065**. Criterion 5 of `V2_1_PREREGISTRATION.md` §4
     therefore cannot be passed on that exam by *any* arm whose true edge over
     momentum is smaller than about 0.065 — which is three times V2.1-D's and
     twice the size of momentum's own IC. This is the same class of defect V2.1
     was created to fix in V2's exam (12 dates against a ≥50-cutoff criterion),
     and it must be confronted before the paper is spent, not after.
3. Production weight stays 0 until that document exists, is satisfied, and the
   exam is then passed under it.

---

## 9. Failure rule

A null is a result, and this document commits to reporting one. The outcomes,
all acceptable:

1. **The 2×2 grid shows the defect is the target, or the input, or both, and a
   fixed carrier recovers the factor — but no arm beats the benchmarks.** Then
   V2.2's contribution is the carrier diagnosis, and the honest headline is that
   the existing feature set has no material edge over momentum once it is carried
   correctly. This is the outcome the evidence so far makes most likely.
2. **A carrier fails G1.** That carrier is rejected and its arm is reported
   carrier-defective. Not re-parameterised.
3. **Arm C collapses.** Reported as the substantive finding of §3.3.
4. **An arm clears all four gates.** Then §8, and only §8.

Forbidden as responses to any of these, listed so they have to be done in the
open if at all: lowering a threshold; re-choosing λ; dropping the monotone
constraint and re-running C; adding a fourth arm; swapping B3 out of the gate;
selecting on a regime bucket; promoting a diagnostic rung to an arm; opening the
V2.1 exam.

---

## 10. Deliverables

| File | Contents |
|---|---|
| `alpha/V2_2_PREREGISTRATION.md` | this document |
| `alpha/carrier.py` | the §2 transforms, the §3 output combinations, the §5 diagnostics |
| `alpha/ladder_v2_2.py` | the three arms + the §4 rungs and grid, development only |
| `alpha/out/v2_2_development.json` / `.pkl` | the frozen development record |
| `alpha/V2_2_EXPERIMENT_LOG.md` | every V2.2 run, in order |
| `alpha/V2_2_LADDER_REPORT.md` | the result |
| `app/tests/test_alpha_v2_2.py` | regression tests for the carrier defect (§11) |

## 11. Tests that must exist before the result is trusted

* the V2.1-A pathology is **reproducible on demand** — a synthetic panel where a
  raw-level carrier inverts a monotone factor, so the defect stays visible after
  it is fixed;
* `S0` is rank-identical to Benchmark 1;
* arm B at λ = 0 is rank-identical to Benchmark 1;
* arm B's λ-bound of §3.2 holds on the frozen predictions;
* **rung `S1-C` produces zero inversions against `ret_12_1`** — unconditional,
  because the constrained column is its only input. Arm C's inversion count is
  measured and reported instead, and the guarantee that *is* provable for arm C —
  the prediction is non-decreasing in `z__ret_12_1` with the other 34 columns held
  fixed — is asserted directly by sweeping the constrained column. See §3.3 and
  amendment A2 of §12;
* the rank transform is applied to stock-level columns and **not** to the 26
  cutoff-constant context columns;
* `ladder_v2_2.py` reads its cutoffs through `examset.development_only`;
* `out/v2_1_exam_predictions.json` does not exist and the exam digest is
  unchanged;
* production stays HOLD at weight 0.

The existing 544 tests must continue to pass.

---

## 12. Amendments, and when they were made

Both were made **before the first fit** — the code and the §11 tests existed, no
V2.2 model had been fitted, no V2.2 carrier had been applied to outcome data, and
no V2.2 IC had been computed on any cutoff. That timing is the only thing that
makes them legitimate: after a result, each of them would be a way of moving a
target. Nothing below this line may be amended from here on.

**A1 — acceptance.** The header's DRAFT marker was replaced with the acceptance
above. No content changed.

**A2 — §11's fifth bullet was unprovable as worded.** It asked for a test that
"arm C produces zero inversions against `ret_12_1`". `monotonic_cst` constrains
the model's *function* — non-decreasing in `z__ret_12_1` at fixed values of the
other 34 columns — and eight of those 34 vary across the cross-section within a
cutoff, so arm C's score can invert momentum for a pair of names that differ in
volatility. The claim is provable only for the one-feature rung `S1-C`. §3.3 now
states what the constraint does and does not buy, and §11 asserts the
unconditional claim where it holds and reports the measurement where it does not.
The arm itself is unchanged: same constraint, same column, same learner. What
changed is what the study says it has proved.

Recorded here because the alternative — discovering it while writing the report —
would have left a test asserting something the design cannot deliver, and the
natural repair at that point is to weaken the test rather than the claim.
