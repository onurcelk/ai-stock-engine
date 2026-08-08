# V2.3 research design — is the bounded-adjustment architecture testable?

**Written 2026-08-08, after V2.2's development result was accepted. DESIGN ONLY —
awaiting review. No V2.3 code exists, no V2.3 arm has been specified in code, and
nothing here is a pre-registration.**

This document does not edit, supersede or reinterpret `PREREGISTRATION.md`,
`V2_1_PREREGISTRATION.md`, `V2_1_LADDER_PREREGISTRATION.md` or
`V2_2_PREREGISTRATION.md`. Those record completed experiments.

**Everything numeric below was computed from frozen V2.2 development artefacts
(`out/v2_2_development.pkl`, `out/panel.pkl`) by re-scoring predictions that
already existed. No model was fitted. The 72 exam cutoffs were not scored; the
only exam data read is the frozen pre-cutoff regime/date metadata that
`examset.show()` prints, which contains no return, target or outcome.** Digest
still `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`;
`out/v2_1_exam_predictions.json` does not exist.

**Every number in this document is post-hoc and diagnostic. None of it may be
used to select an arm, a λ, a threshold or a benchmark.** Where a design choice
below could have been read off one of these curves, that is called out and the
choice is made another way or handed to review.

---

## 0. The one-paragraph answer

**Yes, the architecture is testable — but not the version V2.2 ran, and not for
the reason V2.2's report gave.** The bounded blend did not fail because the bound
was too tight: an oracle adjustment at the same λ = 0.50 reaches +0.415 IC overall
and +0.370 in bear markets, against B3's +0.035. It failed because **the learned
adjustment is 99.2% collinear with the base it is adjusting** (within-cutoff
Spearman(u, z) = −0.9923, negative on 255 of 255 cutoffs). λ = 0.50 therefore
delivered about **0.062 rank units of genuinely new authority, not 0.50** — the
bound was eight times tighter in practice than on paper, and V2.2's +0.00241 is
what leaked through. There are two distinct, cheap, pre-registerable experiments
that follow from that, and one gate V2.2 did not have that the evidence now
demands. There are also five specific ways this architecture should be abandoned,
listed in §9.

---

## 1. Why V2.2-B's residual/context component adds only +0.00241 IC

### 1.1 The three-way decomposition

`final = z + λ·u` where `z = z__ret_12_1` and `u = rank_pct(model) − 0.5`.
Scoring each piece separately over the same 255 cutoffs:

| component | mean IC |
|---|---|
| base `z` alone (= Benchmark 1, exactly) | **+0.02115** |
| adjustment `u` alone | **−0.01801** |
| `z + 0.50·u` — V2.2-B as run | **+0.02356** |
| `z + 0.50·u⊥`, `u` orthogonalised against `z` within cutoff | **+0.02719** |

The adjustment's own IC is *negative*, and the blend still improves on the base.
Both facts have one cause: **`u` is very nearly `−z`.**

* within-cutoff Spearman(`u`, `z`): mean **−0.9923**, min −0.9987, max −0.9570,
  **negative on 100% of cutoffs**.

This is mechanical, not a bug. The target is
`y_resid = target_rank − rank_pct(ret_12_1)`, and `rank_pct(ret_12_1)` is also an
*input* (`z__ret_12_1`). Since `E[target_rank | features] ≈ 0.5` — the pooled
signal is +0.011 Spearman, measured in V2.2 §1 — the best pooled prediction of
`y_resid` is very close to `0.5 − rank_pct(ret_12_1) = −z`. The model finds that,
and `rank_series` then re-encodes it at **full amplitude**, discarding the scale
information that would have made it a shrinkage.

So the decomposition of the +0.00241 is:

```
  contribution of the orthogonal (new-information) part   +0.00604
  dilution from the collinear (−z) part                   −0.00363
  ----------------------------------------------------------------
  observed advantage over B1                              +0.00241
```

**60% of the available effect was spent re-encoding the base.** That is the
finding this design turns on.

Two consequences worth stating precisely:

* **§3.2's bound is true but not what it appears to be.** "λ = 0.50 means two
  names more than half the cross-section apart in momentum keep their order" is
  correct. But the *effective* new-information displacement is
  `λ·√(1−ρ²) = 0.50 × 0.124 ≈ 0.062` rank units. The arm was far more
  conservative than it was designed to be.
* **Cross-sectional shrinkage toward zero is provably inert here** and should be
  removed from the candidate list. Every metric in this protocol — Spearman IC,
  quintile spread, leg membership, turnover — depends only on the *within-cutoff
  ordering* of the final score. Uniform shrinkage `c·final`, `0 < c < 1`, is a
  monotone transform and changes none of them. Only a *non-uniform*
  re-weighting changes anything, and that is a different mechanism with a
  different name.

### 1.2 Is the +0.00241 broad, or a handful of dates?

**Broad, and decaying.**

| measure | value |
|---|---|
| mean paired difference vs B1 | +0.00241 |
| median | +0.00226 |
| 5% symmetrically trimmed mean | +0.00179 |
| 10% symmetrically trimmed mean | +0.00170 |
| share of cutoffs positive | 58.8% |
| per-cutoff sd | 0.01510 |
| first chronological half (n=128) | **+0.00378** |
| second chronological half (n=127) | **+0.00103** |

Symmetric trimming of the outer 10% each side retains 71% of the mean, and the
median exceeds the trimmed mean — this is not an effect carried by a few extreme
dates. Asymmetric trimming looks alarming (dropping only the best 5% of cutoffs
leaves +0.00024) but that statistic is downward-biased by construction and should
not be quoted alone.

The **halves are the concern**: the second half is 27% of the first. G5 passed
against B1 only because both halves are positive. A decay of that size on 255
cutoffs is a live non-stationarity signal and V2.3 must gate on it, not just
report it.

By regime — diagnostic only, and it does not restrict any conclusion:
`BEAR_TREND` **+0.00702**, `SIDEWAYS` +0.00483, `BULL_TREND` +0.00152. The
adjustment adds most where momentum is weakest. Note this is the *opposite* of
V2/V2.1's pattern in one sense — B's own absolute IC in bear is −0.026, because
momentum's is −0.033 there — so B is not repeating the bear concentration warning
of §7; it is repairing a little of momentum's bear damage without escaping it.

### 1.3 Does it survive realistic costs? **No — not as a significant gain.**

Measured on the same 255 cutoffs, balanced long-short quintile books, turnover
from realised leg membership:

| book | turnover (total, both legs) | gross spread | net @5bps | @10bps | @20bps |
|---|---|---|---|---|---|
| B1 — 12-1 momentum | 0.2970 | +0.00174 | +0.00160 | +0.00145 | +0.00115 |
| B3 — regime rule | 0.4542 | +0.00254 | +0.00231 | +0.00209 | +0.00163 |
| **V2.2-B** | 0.3591 | +0.00199 | +0.00181 | +0.00163 | +0.00127 |

| paired net-spread difference | @5bps | @10bps | @20bps |
|---|---|---|---|
| B − B1 | +0.00021 **CI [−0.00012, +0.00058]** | +0.00018 [−0.00015, +0.00055] | +0.00012 [−0.00021, +0.00049] |
| B − B3 | −0.00051 [−0.00170, +0.00053] | −0.00046 [−0.00164, +0.00058] | −0.00037 [−0.00152, +0.00069] |

**The IC advantage does not convert into a significant net-spread advantage at any
cost level.** This corrects a framing in V2.2's report: B trades far less than
arms A and C (18.0% per leg against ~71%), but it trades **21% more per leg than
plain momentum** (0.1796 vs 0.1485), and its spread edge over momentum is inside
the noise. V2.3 needs a cost gate; §8 proposes one.

---

## 2. The λ curve, read as a diagnostic

Post-hoc, computed by re-blending V2.2-B's existing predictions at additional λ.
**No λ may be selected from this table.** It is here to answer "is there an
interpretable trade-off", and there is.

| λ | IC | vs B1 | CI-low vs B1 | breadth vs B1 | half 1 | half 2 | vs B3 | CI-low vs B3 | turnover | net@5bps |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.00 | +0.02115 | 0 | 0 | — | 0 | 0 | −0.00721 | −0.02006 | 0.2970 | +0.00160 |
| 0.10 | +0.02138 | +0.00024 | +0.00006 | 0.592 | +0.00038 | +0.00010 | −0.00698 | −0.01970 | 0.2987 | +0.00161 |
| 0.25 | +0.02200 | +0.00085 | +0.00028 | 0.588 | +0.00136 | +0.00033 | −0.00636 | −0.01890 | 0.3070 | +0.00170 |
| 0.40 | +0.02278 | +0.00163 | +0.00047 | 0.596 | +0.00255 | +0.00071 | −0.00558 | −0.01785 | 0.3301 | +0.00184 |
| **0.50** | +0.02356 | +0.00241 | **+0.00069** | 0.588 | +0.00378 | +0.00103 | −0.00480 | −0.01682 | 0.3591 | +0.00181 |
| 0.60 | +0.02455 | +0.00341 | **+0.00085** | 0.577 | +0.00543 | +0.00137 | −0.00381 | −0.01556 | 0.4079 | +0.00203 |
| 0.75 | +0.02656 | +0.00541 | +0.00038 | 0.545 | +0.00916 | +0.00164 | −0.00180 | −0.01287 | 0.5661 | +0.00239 |
| 1.00 | +0.02105 | −0.00010 | −0.03051 | 0.475 | +0.01562 | −0.01594 | −0.00731 | −0.03575 | 1.4397 | +0.00217 |

**The trade-off is interpretable and non-monotone in exactly one place.**

* IC and the point advantage over B1 rise monotonically to λ ≈ 0.75, then collapse
  at λ = 1.00 where the model is given full authority and destroys the base — the
  same cliff `S1-B` fell off (+0.02097 → −0.00169).
* **Breadth, stability and turnover all deteriorate monotonically in λ.** Breadth
  0.592 → 0.475; the second-half mean stays below the first at every λ and turns
  negative at 1.00; turnover quadruples.
* **The CI-low against B1 — the quantity G2 actually tests — peaks at λ ≈ 0.60**,
  because beyond that the variance grows faster than the mean. λ = 0.50 sits
  just below that peak.
* **`vs B3` is negative at every λ and its CI-low is negative at every λ.** No
  point on this curve passes G3.

That λ = 0.50 lands near the CI-low optimum is a coincidence worth noting and not
worth acting on: it was fixed by a neutral-prior argument before any V2.2 number
existed, and re-deriving it from this table would convert an untuned choice into a
tuned one.

### 2.1 The λ = 0.5 rank lattice — a real artefact, measured and immaterial

At λ = 0.5 with equally-spaced percentile ranks, `k + 0.5m` collides for integer
`k, m`, so the blend creates systematic ties: a median of **389 distinct final
scores across a 466-name cross-section** (17% of names collide), where `z` and `u`
each take 466 distinct values. Ties *cost* Spearman IC, so the artefact runs
against the arm. Its size:

* B as run: **+0.02356**
* B with collisions broken by `u`: +0.02359
* `z + 0.4999997·u` (off-lattice λ): +0.02349

**Immaterial — 3 × 10⁻⁵.** Documented so it is not rediscovered as a mystery. A
future arm using an off-lattice λ or an explicit tie-break loses nothing and gains
nothing.

---

## 3. Alternative adjustment mechanisms, assessed on paper

None of these were run. This is the triage the design rests on.

| candidate | verdict | reason |
|---|---|---|
| residual against raw momentum (**= V2.2-B**) | **known, and diagnosed** | ρ(u, z) = −0.992; λ delivers 12% of nominal authority; +0.00241 |
| residual against **Benchmark 3** | **recommended — V2.3-B** | makes the gate that failed (G3) well-powered; λ = 0 *is* B3, so the incumbent becomes the null |
| residual against a *blended* baseline | **reject** | a fitted or hand-set blend of B1 and B3 is a new benchmark introduced by the back door, and its weight is a second free parameter |
| residual/context with bounded output | **already the mechanism** | this is what `blend` is; nothing new to test |
| cross-sectional shrinkage toward zero | **reject — provably inert** | uniform shrinkage is a monotone within-cutoff transform; IC, quintile spread, leg membership and turnover all depend only on ordering (§1.1) |
| **deny the model the base as an input** | **recommended — V2.3-A** | directly removes the channel that produced ρ = −0.992; the model can no longer spend its output re-encoding `z` |
| learn *when* to adjust, not *what* to adjust (`λ_t = λ·g(context)`, `g ∈ [0,1]`) | **optional third arm, more speculative** | tests "the value is in knowing when momentum is unreliable" rather than in reranking names; needs a second output head and a bound argument for `g` |

The constraint the user set is preserved by all recommended options: **the model is
an adjustment mechanism, never the owner of the ranking signal.**

### 3.1 Post-processing is not an experiment

`z + 0.50·u⊥` (§1.1) scores +0.02719 on development. That number is *already
known* — it is a deterministic function of predictions that exist. Defining it as
a V2.3 "arm" and running it would be theatre. A legitimate arm must change what
the model is *trained on* or *sees*, so that its result is genuinely unknown
before the fit. That is why V2.3-A removes an input rather than post-processing an
output.

---

## 4. Benchmark 3, in full — and why it makes G3 a very unusual gate

**B3 is not modified, not weakened, and stays a gate.** What follows is anatomy.

`benchmark_scores` computes B3 as `mom_12_1` except in `BEAR_TREND`, where it is
`−mom_5d`. Verified on the panel: **`max |B3 − B1| = 0.0` on every non-bear
cutoff, and their per-cutoff ICs are bit-identical there.** So:

* **B3 differs from B1 on 27 of 255 cutoffs — 10.6%.** Everywhere else it *is* B1.
* On those 27: B1 scores **−0.03304**, the reversal leg scores **+0.03510**, so
  B3 − B1 = **+0.06814** per bear cutoff.
* Scaled: `+0.06814 × 27/255 = +0.00721`, which is exactly B3's whole margin
  (+0.02836 − +0.02115).

**Is that margin established? No.**

| | mean | 95% block-bootstrap CI | hit rate |
|---|---|---|---|
| B3 − B1, all 255 cutoffs | +0.00721 | **[−0.00329, +0.02006]** | 0.0588 |
| B3 − B1, the 27 bear cutoffs only | +0.06814 | **[−0.04000, +0.17881]** | 0.556 |

Neither interval excludes zero. B3 beats B1 on **15 cutoffs and loses on 12**, out
of 27. And those 27 dates are not spread across the sample:

`2018 ×1, 2019 ×3, 2020 ×3, 2022 ×17, 2025 ×3` — **63% of them are 2022.**

This must not be misread as licence to drop G3. Two separate claims:

* *B3's IC is significantly positive* — **true**, +0.02836 with a CI excluding
  zero, and it is the largest benchmark IC. This is what V2.1's and V2.2's reports
  said, correctly.
* *B3 significantly beats B1* — **false**, CI [−0.00329, +0.02006]. Conflating
  the two is easy and the reports do not say otherwise, but they do not say this
  either, so it is recorded here.

So G3 is a gate against a rule that is identical to B1 on 89.4% of cutoffs, whose
differential rests on 27 dates concentrated in one drawdown, and whose own
superiority is unproven. It is still the right gate — it is the strongest free
alternative that exists — but a V2.3 that fails it should know *why*.

### 4.1 Where V2.2-B fails B3, exactly

Because B3 = B1 off bear, `B − B3` decomposes with no residual:

| | `B − B1` | `B − B3` |
|---|---|---|
| BULL_TREND (204) | +0.00152 | **+0.00152** (identical) |
| SIDEWAYS (24) | +0.00483 | **+0.00483** (identical) |
| BEAR_TREND (27) | +0.00702 | **−0.06112** |
| overall | +0.00241 | −0.00480 |

**All of G3's failure is 27 bear cutoffs.** B beats B3 wherever B3 is B1, and
loses 0.061 per cutoff where B3 switches to reversal. B does not overlap with B3's
mechanism at all: B3's edge is a *sign switch on the whole cross-section*, B's
adjustment is a bounded per-name tilt that never reverses momentum.

That is the scientific question V2.3 exists to ask, and §5 shows the bound is not
what prevents answering it.

### 4.2 The bound is not the obstacle — an oracle upper bound

Replace the learned adjustment with `rank_pct(alpha_5d)` itself — the perfect
adjustment. **This reads the outcome and is not a model; it answers only "what is
the best a bounded blend could do?"**

| λ | oracle blend IC, all | on BEAR | B3 on BEAR | oracle − B3 |
|---|---|---|---|---|
| 0.25 | +0.23269 | +0.17855 | +0.03510 | +0.20433 [+0.19170, +0.21537] |
| **0.50** | **+0.41544** | **+0.36969** | +0.03510 | **+0.38708** [+0.37439, +0.39883] |
| 0.75 | +0.57120 | +0.53740 | +0.03510 | +0.54284 |
| 1.00 | +0.69862 | +0.67672 | +0.03510 | +0.67026 |

**At λ = 0.50 a bounded blend can exceed B3 in bear markets by +0.334 IC.** The
λ-bound only protects pairs more than 0.5 apart in momentum percentile, which for
a uniform cross-section is 25% of pairs — the other 75% are free to reorder. So
"the bound structurally forbids beating B3" is **false**, and V2.2-B's G3 failure
is an information failure, not an architectural one. This was checked before it
was written down, because the opposite conclusion was the intuitive one.

---

## 5. Exam resolution, recomputed for the bounded architecture

**The old ≈0.065 figure is confirmed for unconstrained arms and is 19× too
pessimistic for a bounded one.** Measured from the actual paired differences; the
72-date figure scales the measured block-4 half-width by `√(255/72)` and is
cross-checked against `1.96·sd/√72`.

| paired difference | per-cutoff sd | half-width @255 | half-width @72 (scaled / iid) |
|---|---|---|---|
| **V2.2-B vs B1** (bounded) | 0.01510 | **0.00182** | **0.00343 / 0.00349** |
| V2.2-B vs B3 (not bounded rel. to B3) | 0.09379 | 0.01108 | 0.02085 / 0.02166 |
| V2.2-A vs B1 (unconstrained) | 0.28786 | 0.03492 | **0.06571** |
| V2.2-C vs B1 (unconstrained) | 0.27021 | 0.03220 | 0.06060 |

Consequences:

* **Minimum detectable advantage over B1 on the 72 frozen dates: ≈0.0034** for a
  B1-bounded arm — against ≈0.066 for an unconstrained one. The
  `V2_2_PREREGISTRATION.md` §8 figure was correct for what it described and must
  not be reused for a bounded arm.
* V2.2-B's observed +0.00241 is **below** that 0.0034, so it would not be
  resolvable on 72 dates. It needs **≈145 cutoffs** — which development already
  has, and the exam does not.
* **Minimum detectable advantage over B3: ≈0.021** for a *B1*-bounded arm, because
  such an arm is not bounded relative to B3. An arm bounded to B3 instead would
  have its variance against B3 collapse the same way: the mismatched probe in §6.2
  measures half-width 0.0039 against B3 on 255, i.e. ≈0.0074 on 72.
* **The exam contains 10 BEAR_TREND cutoffs of 72** (53 bull, 9 sideways; frozen
  pre-cutoff metadata only). Since B1 and B3 are identical outside bear, **G3 on
  the exam would be decided by 10 dates.** Any future exam-decision document has
  to confront that directly.

**None of this opens the V2.1 exam.** The gate is closed, §8 and §1.6 of
`V2_2_PREREGISTRATION.md` are unconditional, and improved power is not a reason to
reopen a sealed paper. It is a reason to *design* the next development experiment
so that a real effect would be visible, and to write it down now so a future exam
decision is not made on a stale power figure.

---

## 6. Leakage and mechanical-artefact audit

B is the first architecture worth attacking, so it was attacked.

| check | result |
|---|---|
| **a** Purge/embargo honoured at every refit | **pass** — minimum sessions between `trained_through` and the refit cutoff = **10**, exactly `HORIZON + EMBARGO`; never less, at any of the 34 refits |
| **b** Rank transform is point-in-time | **pass** — `z__` is `groupby(cutoff).rank(pct=True)` over features only; recomputing it from the panel reproduces the stored column with max abs difference **0.0** |
| **c** No outcome column reaches the model | **pass** — the 35 arm inputs contain none of `alpha_5d, target_train, target_rank, target_vol_scaled, quintile, asset_return, spy_return, sector_return, sector_relative, residual_alpha, horizon_end` |
| **d** Residual target cannot encode the future | **pass** — `y_resid = target_rank − rank_pct(ret_12_1)` is built on the *training* slice only, and both terms are within-cutoff, so a half-sample reproduces it exactly (asserted by `test_the_residual_target_is_derived_on_the_training_slice`). It is used as a fit target on cutoffs whose outcome windows closed ≥10 sessions before the predicted cutoff — check (a) |
| **e** The blend cannot manufacture IC from ties or rank mechanics | **pass** — blending `z` with **pure Gaussian noise** gives +0.02046 (λ=0.25), +0.01908 (λ=0.50), +0.01554 (λ=1.00) against B1's +0.02115. The blend **monotonically destroys** IC when the adjustment is uninformative. It cannot create IC |
| **f** λ = 0 reproduces the factor benchmark exactly | **pass** — max abs per-cutoff IC difference **0.000e+00** |
| **g** Every comparison uses identical cutoffs | **pass** — all three arms, all six rungs and all three benchmarks share one 255-cutoff index |
| **h** Turnover comes from realised positions | **pass** — `protocol.leg_membership` takes the top and bottom quintile *by the final score* on the scored frame; it never sees a prediction, a weight or a target |
| **i** λ = 0.5 rank-lattice collisions | **artefact confirmed, immaterial** — 17% of names collide; effect on IC is 3 × 10⁻⁵, and it runs *against* the arm (§2.1) |

Check (e) is the important one. A bounded blend is exactly the kind of construction
that could produce a spurious edge by breaking ties in a favourable direction; it
does not, and the noise test is the direct evidence.

**One residual concern, not resolved and not resolvable by audit.** The regime tag
that B3 switches on, and that appears among the 26 context columns
(`regime_bull/bear/sideways/high_vol`), is computed from `features.regime_state`
on a truncated `PriceView`, so it is point-in-time. But its *thresholds* were
chosen during V1/V2 development on data that overlaps the current development set.
That is a pre-existing disclosure, unchanged by V2.3, and it inflates B3 rather
than any arm — which raises the bar rather than lowering it.

### 6.1 Not audited, because not run

The orthogonalisation of §1.1 and the B3-base probe of §6.2 are re-scorings of
existing predictions. They inherit checks (a)–(d) and (g) unchanged. They are not
arms and carry no p-value.

### 6.2 Feasibility probe: what a B3 base would look like — **not evidence**

V2.2-B's model was trained on the residual against **B1**, so pointing it at a B3
base is mismatched. This says something about *headroom and power*, nothing about
what a properly fitted arm would score.

| λ | IC | vs B3 | CI vs B3 | breadth | vs B1 | CI-low vs B1 | bear IC |
|---|---|---|---|---|---|---|---|
| 0.00 | +0.02836 | 0 | — | — | +0.00721 | −0.00329 | +0.03510 |
| 0.25 | +0.02950 | +0.00114 | [−0.00063, +0.00318] | 0.577 | +0.00835 | −0.00346 | +0.04005 |
| 0.50 | +0.03098 | +0.00262 | [−0.00106, +0.00683] | 0.584 | +0.00983 | −0.00317 | +0.04405 |
| oracle 0.50 | +0.42252 | +0.39416 | — | — | — | — | — |

Two things this establishes, both about *design* rather than result:

1. **Basing an arm on B3 makes the G3 comparison ≈3× better powered** — half-width
   0.0039 against B3, versus 0.0111 for the B1-based arm. The gate that failed
   becomes the gate that can be answered.
2. **It moves the power problem to G2.** An arm bounded to B3 differs from B1 only
   in bear, so `vs B1` inherits B3 − B1's insignificance (CI-low −0.0032 at every
   λ). **G2 and G3 cannot both be well-powered for the same base**, because B1 and
   B3 differ by a high-variance switch on 27 dates. That is a property of the
   benchmark pair, not of any arm, and V2.3 must disclose it in advance rather
   than discover it in a report.

---

## 7. The minimum viable V2.3 ladder — two arms, k = 2

Both arms hold **everything** from V2.1-C/V2.2 fixed except the one thing named:
same panel, same 316 development cutoffs, same learner and `MODEL_A_PARAMS`, same
walk-forward, purge, embargo, refit cadence, same `alpha_5d` scoring, same
`blend`, same λ = 0.50, same bootstrap.

| | **V2.3-A — deny the base as an input** | **V2.3-B — base on the incumbent** |
|---|---|---|
| **Hypothesis** | V2.2-B's advantage was diluted because the adjustment re-encoded its own base (ρ = −0.992). Removing that channel lets λ deliver its nominal authority, and the +0.00604 orthogonal component becomes reachable by a fitted model. | Nothing in V2/V2.1/V2.2 has beaten the strongest free rule. Making B3 the base turns the incumbent into the null, so the question becomes "does a bounded contextual adjustment add anything to the best hand-specified rule?" — and makes that question answerable. |
| **Base score** | `z__ret_12_1` (= B1) | `rank_pct(B3 score) − 0.5` (= B3), where B3 is `protocol.benchmark_scores`' existing column, unmodified |
| **Inputs** | **34 columns**: the 8 non-momentum stock-level ranks + 26 raw context. `z__ret_12_1` **excluded** | the same **34 columns**. The base is excluded for the same reason |
| **Training target** | `y_resid = target_rank − rank_pct(ret_12_1)`, on training slices only — unchanged from V2.2-B | `y_resid3 = target_rank − rank_pct(B3 score)`, on training slices only. Both terms within-cutoff; no outcome from the scored cutoff |
| **Output** | `final = z__ret_12_1 + 0.50·u` | `final = z__B3 + 0.50·u` |
| **What it isolates** | V2.3-A minus V2.2-B is *exactly* the removal of one input column. Everything else is identical, so the delta is attributable to the collinearity channel. | V2.3-B minus V2.3-A is *exactly* the base and the target it is measured against. |
| **λ = 0** | is B1 exactly — an assertable identity | is B3 exactly — an assertable identity |
| **Known risk** | the model may reconstruct `z` from `ret_5d`/`ret_20d`, which correlate with `ret_12_1`. The H1 collinearity ceiling below detects this and disqualifies the arm rather than excusing it | inherits B3's unvalidated bear switch (§4). Disclosed, not fixed — B3 is the incumbent whether or not its own margin is proven |

**Rejected as arms:** post-processed orthogonalisation (§3.1 — result already
known); any second λ (a λ variant is not a hypothesis); a blended base (§3); a
fourth carrier on these features (V2.2 §5 measured their total worth at +0.0024);
any new feature.

**Optional third arm, only if you want it:** `λ_t = 0.50·g(context)` where a second
head predicts `g ∈ [0,1]` from context alone — "learn *when* momentum is
unreliable, not how to rerank". Genuinely different, but it needs a bound argument
for `g` and a second output, and it would make k = 3. **My recommendation is to
leave it out of V2.3** and run it only if one of the two arms clears H1, so that
its interpretation is not confounded by a carrier that is still leaking.

### 7.1 Rungs, grid and diagnostics — none selectable

* `S0-B1` = rank by `z__ret_12_1`; `S0-B3` = rank by B3. No model. Identity checks.
* `S1-A`, `S1-B` — each arm's carrier on its **own base's rank alone as the sole
  input** (which under the "deny the base" rule means: a single non-momentum
  column, `z__ret_20d`), plus each arm's carrier on the full 34. These give H1.
* **§5-style diagnostics for every arm and rung**, extended by the two V2.2 could
  not have known to measure: **within-cutoff ρ(u, base)** and the implied
  **effective displacement `λ·√(1−ρ²)`**.
* λ curve at {0.00, 0.25, 0.50, 1.00}, reported, never selected on.
* Bear/non-bear decomposition of every `vs B3` difference, because §4.1 shows that
  is where the whole comparison lives.

---

## 8. Gates, and why each threshold is justified without being tuned to pass

**Every V2.2 gate is carried over unchanged. One is added.** Nothing is lowered,
no benchmark is swapped, no threshold is set by looking at a V2.3 number — none
exists.

| gate | condition | justification | does V2.2-B pass it? |
|---|---|---|---|
| **H1a carrier integrity** | one-feature rung's paired mean IC minus its `S0` **≥ −0.005** | **Unchanged from V2.2 §6.1**, including its known mis-calibration for a five-step monotone staircase (V2.2 report §3). Carried over verbatim rather than re-derived, because re-deriving a threshold after it disqualified an arm is the move the protocol exists to prevent | yes (−0.00018) |
| **H1b collinearity ceiling** *(new)* | within-cutoff \|ρ(u, base)\| **≤ 0.90**, mean over scored cutoffs | Derived from what λ must *mean*, not from any IC. Effective new-information displacement is `λ·√(1−ρ²)`; at ρ = 0.90 the arm delivers ≥ 44% of nominal λ, at V2.2-B's 0.992 it delivered 12%. The ceiling is the point at which "λ = 0.50" is not a material misstatement. **V2.2-B fails it**, which is the reason it exists | **no (0.992)** |
| **H1c scored cutoffs** | ≥ **200** of 255 | Unchanged from V2.2 §6.1 | yes (255) |
| **G2 vs B1** | paired mean > 0, 95% block-bootstrap CI excludes 0 | Unchanged | yes (+0.00241, CI-low +0.00069) |
| **G3 vs B3** | paired mean > 0, 95% block-bootstrap CI excludes 0 | Unchanged. §4 shows B3 is a strange benchmark; it is still the strongest free alternative, and §4.2 shows the bound does not forbid beating it | **no (−0.00480)** |
| **G4 breadth** | paired difference > 0 on ≥ **55%** of cutoffs, vs **both** benchmarks | Unchanged | yes (58.8% / 56.9%) |
| **G5 stability** | paired mean > 0 in **each chronological half**, vs both | Unchanged | vs B1 yes; **vs B3 no** |
| **G6 cost** *(new)* | net quintile spread minus the **arm's own base's** net spread > 0, CI excludes 0, at **5 bps** one-way; 10 and 20 reported | V2.2 measured cost and gated nothing on development, and §1.3 shows exactly why that was a gap: B's IC edge over momentum does not become a net-spread edge (+0.00021, CI [−0.00012, +0.00058]). The *form* is identical to G2/G3 — sign plus interval — so no number is being chosen; and 5 bps is V2.1 §4.1's pre-existing figure, carried over | **no** |
| **multiplicity** | Holm–Bonferroni across **k = 2** arms on criterion-1 bootstrap p | Two arms, two hypotheses. Rungs, grid cells, λ points and diagnostics carry no p-value and are not in the family. Adding the optional third arm makes k = 3, and that is the price of adding it |  |
| **power disclosure** *(not a gate)* | for each arm, report the measured MDE against each benchmark **before** the verdict | §5 and §6.2 show G2 and G3 cannot both be well-powered for one base. A reader must be able to tell a power failure from an effect failure. This adds information; it removes no requirement |  |

**V2.2-B fails four of these.** That is the honest state of the architecture, and
it is why the design proposes changing what the model sees rather than what the
gates require.

### 8.1 If an arm clears every gate

The V2.1 exam is **still not opened.** `V2_2_PREREGISTRATION.md` §8 is
unconditional and applies unchanged: a separate `V2_3_EXAM_DECISION.md` must be
written first, and §5 above gives it three numbers it now has to answer to — the
bounded-arm MDE of ≈0.0034 against B1, ≈0.0074 against B3 for a B3-based arm, and
the fact that **G3 on the exam would rest on 10 bear cutoffs.**

---

## 9. What stays frozen, and what would end this architecture

### 9.1 Frozen — not touched by V2.3 under any outcome

* The **72 exam cutoffs**, digest
  `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.
  `out/v2_1_exam_predictions.json` must not come into existence.
* The **316 development cutoffs**, `out/panel.pkl`, the 5-session grid, horizon 5,
  `alpha_5d`, `target_rank`, universe, eligibility, purge, embargo, refit cadence,
  `MIN_TRAIN_CUTOFFS`.
* The **learner** and `models.MODEL_A_PARAMS`. No tuning, no new model class.
* **Benchmarks B1, B2, B3** — definitions, signs, provenance. B3 is analysed in §4
  and not modified.
* **λ = 0.50**, and the λ curve as a report-only diagnostic.
* **G1/H1a's −0.005**, H1c's 200, G4's 55%, G5's form, the 5 bps cost figure,
  two-sided tests, block-4 bootstrap with 10,000 draws.
* Every V2, V2.1 and V2.2 pre-registration, report, log and artefact.
* `alpha/adapter.py`, **production weight 0, action HOLD.**
* The **feature set**: 34 columns is V2.1-C's 35 minus the base. Nothing is added.

### 9.2 Legitimate reasons to abandon the bounded-adjustment architecture

Written now, so that a bad result cannot be answered by redefining success.

1. **Both arms fail H1b.** If a model denied its own base still reconstructs it to
   ρ > 0.90 from the other 34 columns, the adjustment cannot be decoupled from the
   base with this feature set, and λ can never mean what it says. The architecture
   has no room to operate.
2. **The B3-based arm cannot separate from B3** at the ≈3× improved power
   (half-width ≈0.004 on 255 cutoffs). An effect smaller than 0.004 IC is below
   any plausible economic threshold at 5 bps — §1.3 already shows +0.0024 of IC
   buying +0.0002 of net spread inside the noise. Stop.
3. **An arm beats its base on IC and fails G6.** That would confirm §1.3 as
   structural rather than incidental: the tilt earns its IC by trading, and the
   trading costs more than the tilt is worth.
4. **G5 decay repeats.** V2.2-B's halves went +0.00378 → +0.00103. A second arm
   showing a second-half below a third of its first half is a non-stationarity
   signal, not a small sample, and two occurrences is enough.
5. **The advantage concentrates in `BEAR_TREND` again.** V2, V2.1-C, V2.1-D and
   V2.2-A/C all did. A fourth architecture doing the same means the project has
   been measuring one regime episode — mostly 2022 — for three studies, and the
   answer is that ten years of history cannot settle it.
6. **The oracle headroom disappears.** If a properly specified arm's diagnostics
   show the orthogonal component of its adjustment is not merely diluted but
   *absent* (ρ ≤ 0.90 yet no advantage over base), then the features carry no
   contextual information at all and V2.2 §5's +0.0024 was the collinear artefact
   rather than a signal.

Any one of 1, 2, 3 or 6 ends it. 4 and 5 together end it.

---

## 10. Proposed pre-registration structure

`V2_3_PREREGISTRATION.md`, to be written and reviewed **before any code**:

| § | Contents |
|---|---|
| 0 | Why there is a V2.3: the collinearity measurement, ρ = −0.992, and the three-way decomposition of §1.1. The single primary question. |
| 1 | Hard constraints as commitments — §9.1's frozen list, restated as numbered promises, plus "development cutoffs only via `examset.development_only`" and "production stays 0 / HOLD". |
| 2 | What "adjustment" means: base, input transform, target, output combination, rank. The two bases and their identity assertions (λ = 0 reproduces B1 / B3 exactly). |
| 3 | The two arms, exact column lists written out one per line, k = 2. λ = 0.50 carried over with its original argument. What is *not* in V2.3. |
| 4 | Reference rungs, the H1 sanity test, the bear/non-bear decomposition, the λ curve — none selectable, none carrying a p-value. |
| 5 | Diagnostics: V2.2's seven, plus ρ(u, base), the effective displacement `λ·√(1−ρ²)`, and the noise-blend control of §6(e). |
| 6 | Eligibility (H1a/H1b/H1c), selection, and gates G2–G6 with the multiplicity family and the power disclosure. |
| 7 | Regimes: diagnostic only, and the BEAR warning now in its fourth study. |
| 8 | If an arm clears the gate: the exam is still not opened; `V2_3_EXAM_DECISION.md` and the three numbers of §8.1. |
| 9 | Failure rule, and §9.2's abandonment criteria verbatim. |
| 10 | Deliverables and the tests that must exist before the result is trusted. |
| 11 | Amendments, with the same "before the first fit or not at all" rule V2.2 §12 used. |

### 10.1 Deliverables, if it is approved

`alpha/V2_3_PREREGISTRATION.md`; extensions to `alpha/carrier.py`
(orthogonality diagnostic, B3 base helper — additive, no V2.2 behaviour changed);
`alpha/ladder_v2_3.py`; `alpha/out/v2_3_development.json` / `.pkl`;
`alpha/V2_3_EXPERIMENT_LOG.md`; `alpha/V2_3_LADDER_REPORT.md`;
`app/tests/test_alpha_v2_3.py`. The 587 existing tests must continue to pass.

---

## Appendix — section for `V2_2_EXPERIMENT_LOG.md`

*(appended to that file as entry 4; reproduced here so this document is
self-contained)*

> **4 — 2026-08-08, post-result analysis of the frozen V2.2 artefacts. No fit.**
>
> V2.2's development result was accepted and the exam left sealed. A design pass
> then re-scored the frozen predictions in `out/v2_2_development.pkl` to answer
> six questions about the bounded-adjustment architecture. **No model was fitted,
> no arm was added, no threshold was changed, and the only exam data read was the
> frozen pre-cutoff regime metadata.** Written up as
> `alpha/V2_3_RESEARCH_DESIGN.md`. Every number produced is post-hoc and
> diagnostic and selects nothing.
>
> Four measurements change what V2.2's report concluded, and are recorded here
> because they qualify a document that must not be edited:
>
> 1. **V2.2-B's learned adjustment is 99.2% collinear with its own base** —
>    within-cutoff Spearman(u, z) = −0.9923, negative on 255 of 255 cutoffs. The
>    residual target's dominant predictable component is `−z`, and `rank_series`
>    re-encodes it at full amplitude. λ = 0.50 therefore delivered ≈0.062 rank
>    units of new authority rather than 0.50, and the +0.00241 decomposes as
>    +0.00604 from the orthogonal component and −0.00363 of dilution.
> 2. **The λ bound is not what blocked G3.** An oracle adjustment at λ = 0.50
>    reaches +0.370 IC on bear cutoffs against B3's +0.035. The intuitive
>    conclusion — that §3.2's bound structurally forbids matching B3's sign switch
>    — is wrong, and was checked before being written down.
> 3. **B3's advantage over B1 is not statistically established.** B3 is bit-identical
>    to B1 on all 228 non-bear cutoffs; its whole margin is +0.06814 on 27 bear
>    cutoffs, 17 of them in 2022, winning 15 and losing 12. B3 − B1 = +0.00721,
>    CI [−0.00329, +0.02006]. B3's *IC* is significantly positive, as the reports
>    say; B3 *beating B1* is a different claim and is unproven. G3 is unchanged and
>    remains a gate.
> 4. **V2.2-B's IC gain does not convert into a cost-adjusted gain.** Net quintile
>    spread over B1 is +0.00021 at 5 bps, CI [−0.00012, +0.00058], and B trades 21%
>    more per leg than plain momentum (0.1796 vs 0.1485) — it trades far less than
>    arms A and C, but not less than the benchmark.
>
> The exam-resolution figure of `V2_2_PREREGISTRATION.md` §8 was also recomputed:
> ≈0.066 for unconstrained arms (confirmed) against **≈0.0034** for a B1-bounded
> arm on 72 dates. This is not a reason to open the exam and the exam was not
> opened; it is a number a future exam-decision document has to use instead of the
> stale one. The frozen exam holds 10 BEAR_TREND cutoffs of 72, so G3 on the exam
> would rest on 10 dates.
>
> A leakage and artefact audit of the bounded blend passed nine checks, including
> the decisive one: blending the base with pure Gaussian noise **monotonically
> destroys** IC (+0.02046 / +0.01908 / +0.01554 at λ = 0.25 / 0.50 / 1.00 against
> B1's +0.02115), so the construction cannot manufacture IC through rank
> mechanics. The λ = 0.5 rank lattice does create ties on 17% of names; its effect
> on IC is 3 × 10⁻⁵ and runs against the arm.
>
> No V2.3 code was written. The design proposes two arms, k = 2, and six
> abandonment criteria.
