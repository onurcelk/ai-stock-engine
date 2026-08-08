# V2.3 pre-registration — the adjustment must not re-encode its own base

**Written 2026-08-08, after `V2_3_RESEARCH_DESIGN.md` was reviewed and before any
V2.3 code was written. ACCEPTED on review, before the first fit.** No V2.3 arm has
been fitted, no V2.3 carrier has been applied to outcome data, and no V2.3 IC has
been computed on any cutoff at the time of writing.

This document does not edit, supersede or reinterpret `PREREGISTRATION.md`,
`V2_1_PREREGISTRATION.md`, `V2_1_LADDER_PREREGISTRATION.md` or
`V2_2_PREREGISTRATION.md`. Those record completed experiments. Everything they
fixed that is not restated here is inherited unchanged.

The arms, gates, thresholds, column lists and abandonment criteria below are the
ones argued for in `V2_3_RESEARCH_DESIGN.md` §7, §8 and §9. Nothing has been added
to them and nothing has been relaxed.

---

## 0. Why there is a V2.3

V2.2-B was the first arm to preserve the factor it was given — 99.1% of it — and
it beat 12-1 momentum by +0.00241 with a bootstrap CI of [+0.00069, +0.00434]. It
failed on Benchmark 3 and on stability, and its gate closed.

The post-result analysis of the frozen V2.2 artefacts (`V2_3_RESEARCH_DESIGN.md`,
logged as entry 4 of `V2_2_EXPERIMENT_LOG.md`) found the mechanism:

> **the learned adjustment is 99.2% collinear with the base it is adjusting.**
> Within-cutoff Spearman(`u`, `z__ret_12_1`) = **−0.9923**, negative on **255 of
> 255** cutoffs.

The cause is mechanical. The target is
`y_resid = target_rank − rank_pct(ret_12_1)`, and `rank_pct(ret_12_1)` was also an
*input* (`z__ret_12_1`). Since the pooled signal is +0.011 Spearman, the best
pooled prediction of `y_resid` is very nearly `−z`, and `rank_series` re-encodes
that at full amplitude. So λ = 0.50 delivered an effective new-information
displacement of `λ·√(1−ρ²) ≈ 0.062` rank units rather than 0.50, and the +0.00241
decomposes as **+0.00604** from the orthogonal component and **−0.00363** of
dilution.

Two further findings shape the arms rather than the diagnosis:

* **The λ bound is not what blocked G3.** An oracle adjustment at λ = 0.50 reaches
  +0.370 IC on bear cutoffs against B3's +0.035. The intuitive conclusion — that
  §3.2's bound forbids matching B3's sign switch — is false.
* **All of V2.2-B's G3 failure is 27 bear cutoffs.** B3 is bit-identical to B1 on
  the other 228, so `B − B3` equals `B − B1` in bull and sideways and is −0.06112
  in bear.

### The single primary question

> With the collinearity channel removed, does a bounded contextual adjustment add
> material, stable, cost-surviving information **to 12-1 momentum**, and **to the
> hand-specified regime-switching rule**?

---

## 1. Hard constraints, restated as commitments

1. **The 72 frozen V2.1 exam cutoffs are not opened, scored, inspected, modified,
   deleted or rebuilt.** The digest stays
   `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.
   `out/v2_1_exam_predictions.json` must not come into existence during V2.3, and
   the ladder refuses to start if it exists.
2. V2.3 runs on **development cutoffs only**, obtained through
   `examset.development_only()`, which slices and then asserts no exam cutoff
   survived.
3. **No V2, V2.1 or V2.2 artefact or pre-registration is edited.** `carrier.py` is
   extended additively only; the 43 existing V2.2 tests must continue to pass
   unchanged, which is what makes "additively" checkable rather than asserted.
   Experiment logs are append-only.
4. Production weight stays **0**, action **HOLD**. `alpha/adapter.py` is not
   modified and `ladder_v2_3.py` does not import it.
5. **No new features.** The input list is V2.1-C's 35 columns minus the base;
   nothing is added, and no feature is re-justified.
6. **No new learner parameters.** `models.MODEL_A_PARAMS`, unchanged and not tuned.
7. **λ = 0.50**, carried over from `V2_2_PREREGISTRATION.md` §3.2 with its original
   neutral-prior argument. It is **not** re-derived from V2.2's λ curve, and no
   second λ is an arm.
8. **No threshold from V2.2 is altered, relaxed or recalibrated** — including
   G1/H1a's −0.005, which `V2_2_LADDER_REPORT.md` §3 records as mis-calibrated for
   a monotone staircase. It is carried over verbatim.
9. **No post-hoc orthogonalisation arm, no blended base, no fourth carrier.**
   `V2_3_RESEARCH_DESIGN.md` §3.1 gives the reason for the first: its development
   result is already a deterministic function of existing predictions, so running
   it would be theatre.
10. Every threshold below is fixed here, before the first fit, and none may be
    lowered afterwards.
11. **Even if an arm clears every gate, the V2.1 exam is not opened.**
    `V2_2_PREREGISTRATION.md` §8 is unconditional. §8 below states what a separate
    decision document would have to answer first.

---

## 2. The architecture, precisely

```
base score  b   (a within-cutoff centred rank of a fixed, unfitted benchmark)
adjustment  u = rank_pct(model prediction) − 0.5        ∈ [−0.5, +0.5]
final       = b + λ·u                                   λ = 0.50
                        ↓
              within-cutoff rank  →  Spearman IC against alpha_5d
```

The model is an **adjustment mechanism, never the owner of the ranking signal.**
Two properties are inherited from `V2_2_PREREGISTRATION.md` §3.2 and stay:

* the order bound — `b(i) − b(j) > λ ⟹ final(i) > final(j)`, asserted on the frozen
  predictions by `carrier.order_bound_violations`;
* λ = 0 reproduces the base **exactly**, asserted to the last digit.

### 2.1 The two bases

| | base column | equals |
|---|---|---|
| **V2.3-A** | `z__ret_12_1 = rank_pct(ret_12_1) − 0.5` | **Benchmark 1** exactly |
| **V2.3-B** | `z__b3 = rank_pct(b3_regime_switched) − 0.5` | **Benchmark 3** exactly |

`b3_regime_switched` is `protocol.benchmark_scores`' existing column, **unmodified**:
`mom_12_1` except in `BEAR_TREND`, where it is `−mom_5d`, switched on the
pre-cutoff regime tag. Taking its within-cutoff percentile is a monotone
transform, so ranking `z__b3` reproduces B3's IC exactly. Both identities are
asserted before any fit and the run stops if either fails.

### 2.2 The input transform, unchanged

`z__c = rank_pct(c) − 0.5` within cutoff, applied to **stock-level columns only**.
The 26 market-context columns are cutoff-constant and pass through raw, for the
reason given in `V2_2_PREREGISTRATION.md` §2.1. That asymmetry is re-verified on
every development cutoff at run time.

### 2.3 The residual target

For an arm with base column `b`:

```
y_resid = target_rank − rank_pct(b)          ∈ (−1, +1)
```

computed **on the training slice only**. Both terms are within-cutoff, so a slice
carrying whole cutoffs gives identical values; computing it on the slice keeps the
panel free of a column no scorer should see. Because `rank_pct` of a centred rank
is that rank again, V2.3-A's target is **bit-identical to V2.2-B's**, which is what
makes the A-minus-V2.2-B delta attributable to the removed input alone.

---

## 3. The arms — two, fixed now, family size **k = 2**

Common to both, and identical to V2.2-B so the comparison is clean:

| Item | Value |
|---|---|
| Cutoffs | the 316 frozen V2.1 development cutoffs, nothing else |
| Inputs | **exactly 34 columns**: the 8 non-momentum stock-level ranks + the 26 raw context columns. **The base is not among them.** |
| Learner | `HistGradientBoostingRegressor`, `models.MODEL_A_PARAMS`, unchanged and not tuned |
| Walk-forward | expanding, refit at 65 sessions of staleness, min 60 training cutoffs |
| Purge/embargo | `T′ + 5 + 5 ≤ T` |
| Output | `final = base + 0.50 · u` |
| Scoring target | `alpha_5d`, always, for every arm and every diagnostic |
| Intervals | moving-block bootstrap, block 4, 10,000 draws; blocks 1/2/8 reported |
| Sidedness | two-sided throughout |

The 34 input columns, written out rather than derived from a rule:

```
z__ret_5d  z__ret_20d  z__rvol_20d  z__rvol_60d  z__sma200_dist
z__overnight_mean_20d  z__intraday_mean_20d  z__overnight_share_60d
mkt_spy_ret_5d  mkt_spy_ret_20d  mkt_spy_ret_60d  mkt_spy_rsi14
mkt_spy_rvol_20d  mkt_spy_sma50_dist  mkt_spy_sma200_dist
mkt_qqq_ret_5d  mkt_qqq_ret_20d  mkt_qqq_ret_60d  mkt_qqq_rsi14
mkt_qqq_rvol_20d  mkt_qqq_sma50_dist  mkt_qqq_sma200_dist
vix_level  vix_percentile  vix_change_5d
index_breadth_above_sma20  index_breadth_above_sma50  index_advance_share
watchlist_breadth_proxy_above_sma20  watchlist_breadth_proxy_advance_share
regime_bull  regime_bear  regime_sideways  regime_high_vol
```

`z__ret_12_1` is **absent by design.** It is V2.3-A's base and it is what V2.2-B
re-encoded.

### 3.1 V2.3-A — deny the base as an input

* **Hypothesis.** V2.2-B's advantage was diluted because the adjustment re-encoded
  its own base. Removing that channel lets λ deliver its nominal authority, and
  the +0.00604 orthogonal component becomes reachable by a fitted model.
* **Base** `z__ret_12_1` (= B1). **Target** `target_rank − rank_pct(ret_12_1)`.
* **A minus V2.2-B is exactly one removed input column.** Same base, same target,
  same 26 context columns, same 8 other stock-level ranks, same learner, same λ.
* **Disclosed risk.** The model may reconstruct `z__ret_12_1` from `z__ret_5d` and
  `z__ret_20d`, which correlate with it. **H1b detects that and disqualifies the
  arm rather than excusing it.** A high ρ under V2.3-A is an informative outcome:
  it would say the collinearity is a property of the feature set, not of the input
  list.

### 3.2 V2.3-B — base on the incumbent

* **Hypothesis.** Nothing in V2, V2.1 or V2.2 has beaten the strongest free rule.
  Making B3 the base turns the incumbent into the null, so the question becomes
  whether a bounded contextual adjustment adds anything to the best hand-specified
  rule — and, per `V2_3_RESEARCH_DESIGN.md` §6.2, makes that question answerable at
  roughly 3× the resolution.
* **Base** `z__b3` (= B3). **Target** `target_rank − rank_pct(b3_regime_switched)`.
* **λ = 0 is B3 exactly**, so G3 becomes a comparison against the arm's own base.
* **Disclosed risk, recorded rather than fixed.** B3's own advantage over B1 is
  **not statistically established** — B3 − B1 = +0.00721, CI [−0.00329, +0.02006],
  earned on 27 bear cutoffs of which 17 are in 2022, winning 15 and losing 12. An
  arm based on B3 inherits that unvalidated switch. B3 is the incumbent whether or
  not its own margin is proven, and it is not modified.
* **Disclosed consequence for the gates.** Because B1 and B3 differ by a
  high-variance switch on 27 dates, **G2 and G3 cannot both be well-powered for one
  base.** V2.3-B is tightly coupled to B3 and therefore loosely coupled to B1, so
  its G2 interval will be wide. This is a property of the benchmark pair, stated
  here in advance so a wide G2 interval later cannot be reported as a surprise or
  answered by softening G2.

### 3.3 What is not in V2.3

No new feature; no removed context column; no hyperparameter search; no second λ;
no third arm; no post-hoc orthogonalisation arm; no blended base; no change to
regime definitions, thresholds, horizon, target construction, universe,
eligibility or cutoff grid; no change to `adapter.py`; no change to any benchmark.
If both arms are null, the answer is `§9`, not a V2.4.

**V2.2-B is a reference, not an arm.** Its frozen per-cutoff series are read from
`out/v2_2_development.pkl` for the paired A-minus-V2.2-B contrast. It is not
refitted, carries no p-value, and is not in the multiplicity family.

---

## 4. Reference rungs and diagnostics — none of them are arms

None may be selected, gated on, or promoted to an arm.

| Rung | Carrier |
|---|---|
| `S0-B1` | no model. Rank by `z__ret_12_1`. Must equal Benchmark 1 exactly. |
| `S0-B3` | no model. Rank by `z__b3`. Must equal Benchmark 3 exactly. |
| `S1-A` | A's carrier with **one** input, `z__ret_20d` — the base cannot be an input, so the one-feature rung uses the next stock-level rank in the pre-registered order. |
| `S1-B` | B's carrier with the same single input, `z__ret_20d`. |

Also computed and reported for every arm and rung, gating nothing:

* the seven §5 diagnostics of `V2_2_PREREGISTRATION.md`;
* **within-cutoff ρ(`u`, base)** — mean of the signed value and mean of `|ρ|` — and
  the implied **effective displacement `λ·√(1−ρ̄²)`** where `ρ̄` is mean `|ρ|`;
* the **λ curve** at {0.00, 0.25, 0.50, 1.00}, with order-bound violations at each;
* the **bear / non-bear decomposition** of every `vs B3` paired difference, because
  B3 is identical to B1 outside `BEAR_TREND` and that is where the whole comparison
  lives;
* the **noise-blend control**: the arm's base blended with seeded Gaussian noise at
  λ = 0.50. A bounded blend must *destroy* IC when the adjustment is uninformative;
  if this control ever produces a gain, the construction is manufacturing IC and
  V2.3 stops;
* **measured power** — the block-bootstrap half-width of each paired difference on
  the development sample and scaled to 72 cutoffs.

---

## 5. Eligibility

An arm is eligible for selection only if **all three** hold.

| | condition | threshold | justification |
|---|---|---|---|
| **H1a** | paired mean per-cutoff IC of the arm's one-feature rung minus its own `S0` | **≥ −0.005** | Unchanged from `V2_2_PREREGISTRATION.md` §6.1, carried over verbatim including its known mis-calibration. Re-deriving a threshold after it disqualified an arm is the move the protocol exists to prevent. |
| **H1b** | **mean of `|ρ(u, base)|` over scored cutoffs** | **≤ 0.90** | Derived from what λ must *mean*, not from any IC. Effective new-information displacement is `λ·√(1−ρ²)`: at ρ = 0.90 the arm delivers ≥ 44% of nominal λ; at V2.2-B's 0.992 it delivered 12%. 0.90 is the point beyond which "λ = 0.50" is a material misstatement. **V2.2-B fails this**, which is why it exists. The mean of `|ρ|` is specified rather than `|mean ρ|` so that opposite-signed cutoffs cannot cancel; the signed mean is reported beside it. |
| **H1c** | scored development cutoffs | **≥ 200** | Unchanged from `V2_2_PREREGISTRATION.md` §6.1. |

An arm failing any of these is **reported in full and marked carrier-defective**,
and is not eligible for selection whatever its IC.

### 5.1 Selection

**Highest mean development IC among the eligible arms.** Ties — specified though
they will not occur at five decimals — go to **V2.3-B before V2.3-A**, because a
tie means B achieved the same IC over the harder null.

---

## 6. The gate

All five must hold for the **selected** arm, on development.

| # | Condition | Threshold |
|---|---|---|
| **G2** | Beats Benchmark 1 (12-1 momentum, +1) | paired mean IC difference > 0, 95% block-bootstrap CI excludes 0 |
| **G3** | Beats Benchmark 3 (regime-switched momentum) | same |
| **G4** | Breadth | paired difference > 0 on **≥ 55%** of scored cutoffs, against **both** B1 and B3 |
| **G5** | Stability | paired mean difference > 0 in **each chronological half**, against **both** B1 and B3 |
| **G6** | Cost | **net quintile spread minus the arm's own base's net spread > 0, 95% CI excludes 0, at 5 bps one-way.** 10 and 20 bps reported beside it |

G2, G3, G4 and G5 are `V2_2_PREREGISTRATION.md` §6.3 verbatim.

**G6 is new, and here is why it is not a number chosen to be passable.** V2.2
measured cost and gated nothing on development. `V2_3_RESEARCH_DESIGN.md` §1.3
shows exactly what that missed: V2.2-B's IC advantage over momentum of +0.00241
became a net-spread advantage of **+0.00021 with CI [−0.00012, +0.00058]** at 5
bps — inside the noise — while trading 21% more per leg than plain momentum. The
*form* of G6 is identical to G2 and G3, sign plus interval, so no magnitude is
being chosen; 5 bps is `V2_1_PREREGISTRATION.md` §4.1's pre-existing figure,
carried over. **V2.2-B fails G6**, as it fails H1b, G3 and G5.

### 6.1 Multiplicity

Holm–Bonferroni across the **k = 2** arms on criterion-1 bootstrap p-values. Rungs,
λ points, diagnostics, the noise control and the V2.2-B reference carry no p-value
and are not in the family.

### 6.2 Power disclosure — reported, not a gate

For each arm, the measured block-bootstrap half-width of each paired difference is
reported **before** the gate verdict, so a reader can tell a power failure from an
effect failure. §3.2 already discloses that V2.3-B's G2 interval will be wide. This
adds information; it removes no requirement.

---

## 7. Regimes, and the BEAR warning in its fourth study

Regime breakdowns are **diagnostic only**. They may not select an arm, explain a
failure, restrict a conclusion to a bucket, or justify an interaction.

Recorded in advance because the pattern has now appeared in three studies: V2's
development edge lived in `BEAR_TREND` and inverted to `SIDEWAYS` on its exam;
V2.1-C/D earned +0.076 and +0.066 in bear against ≈0 in sideways; V2.2-A and
V2.2-C both earned +0.063 in bear. **A V2.3 arm that concentrates in `BEAR_TREND`
is a warning signal, not evidence of robustness**, and the report must say so in
those words if it happens. For V2.3-B this needs care: its base already switches
in bear, so a bear concentration would be inherited from B3 rather than learned,
and the report must separate the two.

---

## 8. If an arm clears the gate

The exam is **still not opened.** V2.3 stops and reports, and a separate
`V2_3_EXAM_DECISION.md` is written before any exam date is touched. It has to
answer, in advance:

* Is a paper frozen under `V2_1_PREREGISTRATION.md` for a V2.1-family arm a valid
  test of a V2.3 arm at all?
* What is the family size for the exam correction, given that V2.1 selected one arm
  from four, V2.2 one from three, and V2.3 one from two?
* **The resolution problem, restated with the correct numbers.** The ≈0.065
  half-width in `V2_2_PREREGISTRATION.md` §8 was scaled from *unconstrained* arms
  and does not apply to a bounded one. Measured: **≈0.0034** on 72 dates for a
  B1-bounded arm against B1, and **≈0.0074** for a B3-bounded arm against B3.
* **The frozen exam contains 10 `BEAR_TREND` cutoffs of 72.** Since B1 and B3 are
  identical outside bear, **G3 on the exam would be decided by 10 dates.**

Production weight stays 0 until that document exists, is satisfied, and the exam is
then passed under it.

---

## 9. Failure rule, and what would end this architecture

A null is a result and this document commits to reporting one. If both arms fail,
**V2.3 stops and reports the failure mechanism. It does not propose a V2.4.**

Forbidden as responses to any outcome, listed so they have to be done in the open
if at all: lowering a threshold; re-choosing λ; adding a third arm; swapping a
benchmark; modifying B3; selecting on a regime bucket; promoting a rung, a λ point
or the noise control to an arm; post-hoc orthogonalisation; opening the V2.1 exam.

`V2_3_RESEARCH_DESIGN.md` §9.2, carried over verbatim — **any one of 1, 2, 3 or 6
ends the architecture; 4 and 5 together end it:**

1. **Both arms fail H1b.** A model denied its own base that still reconstructs it
   to ρ̄ > 0.90 from the other 34 columns cannot be decoupled from the base with
   this feature set, and λ can never mean what it says.
2. **V2.3-B cannot separate from B3** at the improved resolution (half-width ≈0.004
   on 255 cutoffs). An effect below 0.004 IC is beneath any plausible economic
   threshold at 5 bps.
3. **An arm beats its base on IC and fails G6.** The tilt earns its IC by trading
   and the trading costs more than the tilt is worth.
4. **G5 decay repeats.** V2.2-B's halves went +0.00378 → +0.00103. A second arm
   with a second half below a third of its first is non-stationarity, not a small
   sample.
5. **The advantage concentrates in `BEAR_TREND` again** — a fourth architecture
   measuring one 2022-dominated episode.
6. **The oracle headroom is absent, not merely diluted** — ρ̄ ≤ 0.90 achieved and
   still no advantage over base, which would mean the features carry no contextual
   information and V2.2's +0.0024 was the collinear artefact rather than a signal.

---

## 10. Deliverables and the tests that must exist before the result is trusted

| File | Contents |
|---|---|
| `alpha/V2_3_PREREGISTRATION.md` | this document |
| `alpha/carrier.py` | **extended additively** — a collinearity diagnostic. No existing function changed |
| `alpha/ladder_v2_3.py` | the two arms, the rungs, the diagnostics, development only |
| `alpha/out/v2_3_development.json` / `.pkl` | the frozen development record |
| `alpha/V2_3_EXPERIMENT_LOG.md` | every V2.3 run, in order |
| `alpha/V2_3_LADDER_REPORT.md` | the result |
| `app/tests/test_alpha_v2_3.py` | the invariants below |

Tests:

* the 34 input columns are V2.1-C's 35 minus `z__ret_12_1`, and **no arm carries its
  own base as an input**;
* V2.3-A's residual target is **bit-identical** to V2.2-B's, so the A-vs-V2.2-B
  delta is one removed column;
* `z__ret_12_1` is rank-identical to Benchmark 1 and `z__b3` is rank-identical to
  Benchmark 3;
* each arm at λ = 0 is rank-identical to its own base;
* the λ-bound holds on the frozen predictions of both arms;
* the collinearity diagnostic recovers a known ρ on synthetic data, and H1b rejects
  a V2.2-B-shaped carrier (ρ̄ = 0.992) while admitting a decoupled one;
* the noise-blend control destroys IC rather than creating it;
* G6 fails on a V2.2-B-shaped net-spread difference (+0.00021, CI spanning zero);
* the rank transform is applied to stock-level columns and **not** to the 26
  cutoff-constant context columns;
* `ladder_v2_3.py` reads its cutoffs through `examset.development_only`, does not
  name the exam cutoffs, and does not import `adapter`;
* `out/v2_1_exam_predictions.json` does not exist and the exam digest is unchanged;
* the V2.2 record is untouched — `out/v2_2_development.json` still reports
  V2.2-B at +0.02356, and all 43 V2.2 tests still pass;
* production stays HOLD at weight 0.

The existing 587 tests must continue to pass.

---

## 11. Amendments

Same rule as `V2_2_PREREGISTRATION.md` §12: an amendment is legitimate **before the
first fit and not after**. Any made will be recorded here with the evidence that no
V2.3 IC existed when they were made.

*None.*
