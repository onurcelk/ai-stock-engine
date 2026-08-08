# V2.3 — the bounded-adjustment ladder. Result.

**Run 2026-08-08 on the 316 frozen V2.1 development cutoffs. The 72 exam cutoffs
were not opened. Production stays at weight 0, action HOLD.**

Protocol: [`V2_3_PREREGISTRATION.md`](V2_3_PREREGISTRATION.md), accepted before the
first fit. Design: [`V2_3_RESEARCH_DESIGN.md`](V2_3_RESEARCH_DESIGN.md). Record:
`out/v2_3_development.json` / `.pkl`. Log:
[`V2_3_EXPERIMENT_LOG.md`](V2_3_EXPERIMENT_LOG.md). Code: `carrier.py` (extended
additively), `ladder_v2_3.py`. Tests: `app/tests/test_alpha_v2_3.py`.

143,675 rows, 316 development cutoffs, 2016-01-04 to 2026-07-28. Both arms and both
rungs scored 255 of them, 34 refits each. Every comparison is paired on a common
sample.

---

## The verdict

**The §6 gate closed. All five gates failed for the selected arm, and all five
failed for the other one too.** Neither arm was disqualified on eligibility — both
passed H1a, H1b and H1c — so this is a clean failure of the hypotheses, not a
carrier defect. The architecture was given its fair test and did not survive it.

**Both pre-registered hypotheses are refuted, and one of them is refuted by a
result that runs in the opposite direction to the prediction.**

| | V2.3-A | V2.3-B | selected arm's gate |
|---|---|---|---|
| base | `z__ret_12_1` (= B1, +0.02115) | `z__b3` (= B3, +0.02836) | |
| **mean development IC** | +0.02063 | **+0.02716** | |
| IC 95% CI | [−0.00371, +0.04527] | [+0.00293, +0.05192] | |
| Holm p (k = 2) | 0.09909 | 0.0566 — **not significant** | |
| **advantage over its own base** | **−0.00052** | **−0.00120** | |
| H1a carrier integrity | −0.00189 **pass** | −0.00170 **pass** | |
| **H1b mean \|ρ(u, base)\|** | **0.6981 pass** | **0.7033 pass** | |
| H1c scored cutoffs | 255 pass | 255 pass | |
| **eligible** | **yes** | **yes** | |
| **G2** vs B1 | −0.00052, CI [−0.00890, +0.00764] | +0.00602, CI [−0.00820, +0.02172] | **fail** |
| **G3** vs B3 | −0.00773, CI [−0.02175, +0.00474] | −0.00120, CI [−0.00939, +0.00653] | **fail** |
| **G4** breadth vs B1 / B3 | 45.9% / 44.7% | 44.7% / 45.1% | **fail** (needs ≥ 55%) |
| **G5** stability vs B1 (halves) | −0.00043 / −0.00061 | +0.01273 / **−0.00075** | **fail** |
| **G6** cost vs own base @5bps | +0.00028, CI [−0.00089, +0.00145] | +0.00002, CI [−0.00098, +0.00100] | **fail** |
| turnover (both legs) | 0.4629 | 0.6173 | |
| net spread @5bps | +0.00187 | +0.00233 | |

Selected arm: **V2.3-B**, on highest mean development IC among the eligible arms.
§5.1's tie-break toward B never had to run.

---

## 1. V2.3-A: the collinearity was fixed, and the result got worse

This is the study's central contrast and it is as clean as a single deleted column
can make it. V2.3-A and V2.2-B share their base, their target, their learner, their
hyperparameters, their λ, their cutoffs and 34 of their 35 inputs. The 35th is
`z__ret_12_1`, the base itself.

| | V2.2-B | V2.3-A | change |
|---|---|---|---|
| mean \|ρ(u, base)\| | **0.9923** | **0.6981** | the channel is largely closed |
| effective λ, `λ·√(1−ρ̄²)` | 0.0619 | **0.3580** | **5.8× more real authority** |
| share of cutoffs with \|ρ\| > 0.90 | ~100% | **2.0%** | |
| mean development IC | **+0.02356** | **+0.02063** | **−0.00293**, CI [−0.01139, +0.00515] |
| advantage over B1 | **+0.00241**, CI [+0.00069, +0.00434] | **−0.00052**, CI [−0.00890, +0.00764] | the only positive interval in the family is gone |

**The mechanism was repaired and the effect disappeared.** Deleting the base from
the inputs did exactly what it was predicted to do — the adjustment stopped being a
copy of momentum, and λ went from delivering 12% of its nominal authority to
delivering 72% — and the arm then scored *below* V2.2-B and below plain momentum.

So the +0.00604 "orthogonal component" measured in the design pass did **not**
survive being learned. That number came from post-processing V2.2-B's existing
predictions, and `V2_3_RESEARCH_DESIGN.md` §3.1 refused to make it an arm precisely
because a post-processed number is already known and proves nothing about a fitted
model. That refusal was correct: a model trained to predict a residual without
seeing the base produces a different, and worse, adjustment than the orthogonal
projection of a model that did see it.

The honest reading of V2.2-B's +0.00241 is now available and it is not flattering.
At ρ̄ = 0.9923 the arm was, to within 0.8% of its adjustment's dispersion, a
monotone reshuffling of momentum. Its advantage was a **very small, very
well-measured residue** of a near-identity, and when the identity was broken the
residue did not scale up — it inverted.

---

## 2. V2.3-B: the incumbent base was adopted, and nothing was added to it

Making B3 the base worked as designed in one respect: λ = 0 reproduced B3 exactly,
so G3 became a comparison against the arm's own book, and it is the best-powered
G3 the project has run.

| | value |
|---|---|
| base (B3) mean IC | **+0.02836** |
| V2.3-B mean IC | **+0.02716** |
| **advantage over B3** | **−0.00120**, CI [−0.00939, +0.00653] |
| half-width of that comparison | **0.00796** (V2.2-B's against B3 was 0.01108) |
| advantage over B1 | +0.00602, CI [−0.00820, +0.02172] |

**The adjustment subtracted from the strongest free rule.** Not significantly — the
interval spans zero — but the point estimate is negative, the breadth is 45.1%, and
both chronological halves are negative (−0.00034, −0.00206). There is no reading of
these numbers in which a bounded contextual adjustment adds information to B3.

Its +0.00602 against B1 is **entirely inherited**, and the bear decomposition shows
it exactly. B3 is bit-identical to B1 outside `BEAR_TREND` (verified: max
\|difference\| = 0.0 on all 228 non-bear cutoffs), so:

| V2.3-B versus | BEAR (27) | BULL (204) | SIDEWAYS (24) | overall |
|---|---|---|---|---|
| B1 | **+0.08234** | −0.00230 | −0.00911 | +0.00602 |
| B3 | +0.01420 | −0.00230 | −0.00911 | −0.00120 |

Of the +0.08234 against B1 in bear, **+0.06814 is B3's own switch** — a hand-coded
rule with nothing fitted — and +0.01420 is the learned adjustment. §7 requires this
to be said plainly: **V2.3-B's apparent edge over momentum is the regime rule it
was built on, not the model built on top of it.**

And §7's warning applies for the fourth consecutive study: `BEAR_TREND` is the only
bucket in which either arm improves on its base. V2.3-A vs B1 is +0.01684 in bear,
−0.00230 in bull and −0.00489 in sideways. V2's development edge lived in bear and
inverted out of sample; V2.1-C/D, V2.2-A/C and now both V2.3 arms all concentrate
there. Those 27 cutoffs are 63% 2022.

---

## 3. The finding that outranks both: authority and resolution are the same dial

`V2_3_RESEARCH_DESIGN.md` §6 reported that a bounded-tilt arm is ~19× better
powered against its own benchmark than an unconstrained one, and treated that as a
methodological gain to carry forward. **V2.3 shows the gain was not free — it was
the collinearity.**

| arm | effective λ | half-width vs its base |
|---|---|---|
| V2.2-B | 0.0619 | **0.00182** |
| V2.3-A | 0.3580 | **0.00827** |
| V2.2-A (unconstrained, for scale) | — | 0.03492 |

**5.8× more real authority bought 4.5× less resolution.** [*Corrected 2026-08-08
after the final decision audit; this sentence originally read "4.5× more real
authority". The authority ratio is 0.3580/0.0619 = 5.8×; the resolution ratio is
0.00827/0.00182 = 4.5×. No underlying value changed and the conclusion is
unaffected.*] The paired variance of an
arm against its base is a monotone function of how far the arm is allowed to move
from it, and the "bounded arms are better powered" observation is just that
statement read from the other end. An arm can be precisely measured or it can be
free to differ; it cannot be both.

The same correction applies to the design pass's forward-looking numbers. §6.2
predicted a B3-based arm would have a half-width of ≈0.0039 against B3, from a
mismatched probe. The measured value is **0.00796** — the probe was optimistic by a
factor of two, because it reused a model whose adjustment was still 99% collinear
with a *different* base and therefore barely moved this one. The corrected
resolution figures, for any future document:

| paired difference | half-width @255 | scaled @72 |
|---|---|---|
| V2.3-A vs B1 | 0.00827 | 0.01556 |
| V2.3-A vs B3 | 0.01324 | 0.02492 |
| V2.3-B vs B1 | 0.01496 | 0.02815 |
| V2.3-B vs B3 | 0.00796 | 0.01498 |
| V2.3-B net spread vs own base | 0.00099 | 0.00186 |

Resolving V2.3-B's observed −0.00120 against B3 would need ~11,000 cutoffs. The
question is not under-powered; the effect is absent.

---

## 4. The λ curves: both arms are past their own optimum at the pre-registered λ

Reported, never selected on. λ = 0.50 was carried over from V2.2 §3.2 with its
original neutral-prior argument and was not re-derived.

| λ | V2.3-A IC | vs B1 | turnover | | V2.3-B IC | vs B3 | turnover |
|---|---|---|---|---|---|---|---|
| 0.00 | +0.02115 | 0 | 0.2970 | | +0.02836 | 0 | 0.4542 |
| 0.25 | **+0.02159** | **+0.00045** | 0.3364 | | **+0.02866** | **+0.00030** | 0.4940 |
| **0.50 — the arm** | +0.02063 | −0.00052 | 0.4629 | | +0.02716 | −0.00120 | 0.6173 |
| 1.00 | +0.01061 | −0.01053 | 0.6909 | | +0.01214 | −0.01622 | 0.7872 |

Interpretable, and it says the same thing twice. **The maximum advantage over base
available anywhere on either curve is +0.00045.** With the collinearity removed,
the same nominal λ now delivers 5.8× the real authority, so λ = 0.50 overshoots
where for V2.2-B it sat near the optimum. Turnover rises monotonically in λ on both
curves. Order-bound violations are zero at every λ ≤ 0.50 on both arms.

That λ = 0.25 is marginally best on both curves changes nothing and may not be
acted on: §9 names re-choosing λ as forbidden, and +0.00045 is not a finding.

---

## 5. What the 34 columns are worth, measured a second way

The one-feature rungs are the cheapest measurement in the study and they are
brutal. Each is its arm's carrier with a **single** input, `z__ret_20d`.

| | inputs | mean IC | vs B1 | vs B3 | turnover |
|---|---|---|---|---|---|
| `S1-A` | 1 | +0.01925 | −0.00189 | −0.00911 | 0.7966 |
| **V2.3-A** | **34** | +0.02063 | −0.00052 | −0.00773 | 0.4629 |
| `S1-B` | 1 | +0.02666 | +0.00552 | −0.00170 | 0.8561 |
| **V2.3-B** | **34** | +0.02716 | +0.00602 | −0.00120 | 0.6173 |

**Adding 33 columns to a single momentum rank moved the IC by +0.0014 and +0.0005.**
V2.2 §5 measured the feature set's total worth over momentum at +0.0024 through a
collinear carrier; V2.3 measures it at +0.0005 through a decoupled one, against the
harder base. The two studies now agree that the number is somewhere between zero
and half a hundredth of a Spearman IC.

---

## 6. Costs: the tilt does not pay for its own trading

G6 is the gate V2.2 lacked, and it fails for both arms — as V2.2-B would have.

| arm | turnover | its base's turnover | gross spread | net @5bps | **net advantage over own base** |
|---|---|---|---|---|---|
| V2.3-A | 0.4629 | 0.2970 (B1) | +0.00210 | +0.00187 | **+0.00028**, CI [−0.00089, +0.00145] |
| V2.3-B | 0.6173 | 0.4542 (B3) | +0.00264 | +0.00233 | **+0.00002**, CI [−0.00098, +0.00100] |

Decoupling the adjustment raised turnover by **56%** over momentum and **36%** over
the regime rule, and bought nothing. The 10 and 20 bps figures are identical to
five decimals — the advantage is so small that the cost differential barely moves
it. V2.3-B's net advantage over its own base is **+0.00002**, which is two parts in
a hundred thousand of weekly spread.

---

## 7. Verification, and the one departure from the pre-registration

### 7.1 The invariants

| check | result |
|---|---|
| base identities | `z__ret_12_1` == B1 and `z__b3` == B3, **max \|per-cutoff IC difference\| = 0.0** for both, asserted before any fit |
| order bound | **0 violations** for both arms at λ = 0.00, 0.25, 0.50 |
| the base is never an input | asserted structurally per arm and per rung; 34 inputs = V2.1-C's 35 minus the base |
| V2.3-A's target == V2.2-B's target | bit-identical, asserted — which is what makes §1 a controlled contrast |
| exam sealed | digest `b55e065f…` unchanged; `out/v2_1_exam_predictions.json` does not exist; the ladder refuses to start if it does |
| development only | cutoffs via `examset.development_only`; no exam cutoff in any scored series |
| V2.2 record untouched | `out/v2_2_development.json` still reports V2.2-B at +0.02356; **all 43 V2.2 tests pass unchanged** against the extended `carrier.py` |
| production | weight 0, HOLD; `ladder_v2_3.py` does not import `adapter` |

`pytest -q --runslow` — **625 passed**, none skipped (587 as before + 38 V2.3).

### 7.2 The noise control misfired, and this is the one place V2.3 departed from its own protocol

**Disclosed prominently because it is a departure from an accepted pre-registration,
made after the first fit.**

§4 specified: blend the base with **one** seeded Gaussian draw at λ = 0.50; "if this
control ever produces a gain, the construction is manufacturing IC and V2.3 stops."
On the pre-registered seed it produced a gain — **+0.00123** for the B1 base and
+0.00059 for B3 — and the ladder stopped.

The control was mis-specified in two ways. It compared *unpaired* means, and it used
a single draw. Measured across 30 independent draws:

| base | mean paired difference | sd across draws | range | share of draws above base |
|---|---|---|---|---|
| `z__ret_12_1` | **−0.00202** | 0.00137 | [−0.00579, +0.00041] | **3%** |
| `z__b3` | **−0.00278** | 0.00138 | [−0.00652, −0.00056] | **0%** |

The single-draw spread (0.00137) is comparable to the effect (0.00202), so one draw
cannot resolve the question — and the pre-registered seed landed about 2σ into the
upper tail. Its own paired interval spans zero: [−0.00241, +0.00512] for B1,
[−0.00302, +0.00445] for B3. **The gain was never significant on its own terms.**

What was done: the single pre-registered draw is reported **verbatim, gain and all**,
in the frozen record and above; the stop condition was moved to the powered
statistic (mean paired difference < 0 **and** ≤ 50% of draws above base), which both
bases pass decisively. This makes the control **stricter**, not weaker — a
construction that manufactured IC from rank mechanics would show it on most draws,
not on one — but it is still a change made after seeing a result, and it is logged
as entry 3 of `V2_3_EXPERIMENT_LOG.md` with the numbers that justify it.

A test pins the conditions under which that departure stays defensible: if the
single-draw gain ever becomes *significant*, the powered version is no defence and
the study must stop instead. It is not significant here.

The bounded blend does not manufacture IC. That was the question, and it is
answered.

---

## 8. Against the abandonment criteria of §9

`V2_3_PREREGISTRATION.md` §9 fixed six criteria before the first fit, of which any
one of 1, 2, 3 or 6 ends the architecture and 4 and 5 together end it.

| # | criterion | met? |
|---|---|---|
| 1 | both arms fail H1b | **no** — both passed at ρ̄ ≈ 0.70 |
| 2 | **V2.3-B cannot separate from B3** at the improved resolution | **substance yes, precision premise not met** — −0.00120, CI [−0.00939, +0.00653], half-width **0.00796**. The point estimate is negative. See the clarification below |
| 3 | an arm beats its base on IC and fails G6 | **no** — neither arm beats its base |
| 4 | **G5 decay repeats** | **YES** — V2.3-B vs B1 goes +0.01273 → −0.00075, a sign flip; V2.3-A is negative in both halves |
| 5 | **the advantage concentrates in `BEAR_TREND` again** | **YES** — bear is the only bucket where either arm improves on its base, for the fourth study running |
| 6 | **ρ̄ ≤ 0.90 achieved and still no advantage over base** | **YES** — ρ̄ = 0.6981 and 0.7033, advantage −0.00052 and −0.00120 |

**Criterion 6 is met in its exact pre-registered form: the collinearity was removed
and no advantage appeared.** That was the sharpest test the design could construct,
and it is the one the architecture failed.

### Clarification added 2026-08-08, after the independent decision audit

*Retrospective interpretation only. No pre-registration, threshold, seed, artefact
or result is changed by this note.*

**Criterion 2 must not be relied on as a formally satisfied precision condition.**
As written in `V2_3_PREREGISTRATION.md` §9, it conditions on "the improved
resolution (half-width ≈0.004 on 255 cutoffs)", and reasons from there that "an
effect below 0.004 IC is beneath any plausible economic threshold at 5 bps". The
measured half-width was **0.00796 — twice as wide as the premise.** The table above
originally marked the criterion met while citing the achieved figure, which did not
make the gap visible. So:

* criterion 2's **operative clause is satisfied** — V2.3-B did not separate from B3,
  and its point estimate is **negative** (−0.00120), so no positive effect is being
  concealed by insufficient resolution at the point estimate;
* criterion 2's **economic argument does not run at 0.00796**, and it should not be
  cited as though it does;
* **criterion 6 is satisfied exactly as pre-registered and is alone sufficient to
  end the architecture under §9** (ρ̄ = 0.6981 and 0.7033, both ≤ 0.90, with
  advantage over base −0.00052 and −0.00120);
* **criteria 4 and 5 are jointly sufficient** and are independently confirmed.

**The decision therefore rests on two independent sufficient grounds — criterion 6,
and criteria 4-with-5 — with or without criterion 2.** Where a future document needs
to cite a ground for abandonment, cite criterion 6.

**Per §9, V2.3 stops and reports the failure mechanism. It does not propose a
V2.4.**

---

## 9. What is now closed

1. *Was V2.2-B's +0.00241 a diluted signal waiting for more authority?* **No.**
   Authority was multiplied by 5.8 and the advantage went from +0.00241 to
   −0.00052. §1.
2. *Can a bounded contextual adjustment improve on the hand-specified regime rule?*
   **No**, at the best resolution the project has achieved against that rule
   (half-width 0.00796). The point estimate is negative. §2.
3. *Is the bounded architecture better powered, as a free methodological gain?*
   **No.** Resolution and authority are the same dial; V2.2-B's 19× advantage was
   the collinearity that was destroying its signal. §3.
4. *What is the 34-column feature set worth over a single momentum rank, carried
   correctly?* **+0.0005 to +0.0014 of IC.** §5.
5. *Does any tilt of any base pay for its own trading?* **No.** Net advantage over
   own base is +0.00028 and +0.00002, both intervals spanning zero, while turnover
   rises 36–56%. §6.
6. *Does the bounded blend manufacture IC through rank mechanics?* **No** — 30 draws
   of pure noise destroy IC at 0–3% exceedance. §7.2.

Across V2, V2.1, V2.2 and V2.3 — eleven fitted arms, four pre-registrations — **no
model has beaten 12-1 momentum with an interval excluding zero except V2.2-B, whose
advantage is now understood as the residue of a near-identity, and none has beaten
the three-line regime rule at all.**

---

## 10. Production

Weight **0**, action **HOLD**, unchanged. `alpha/adapter.py` was not modified and
`ladder_v2_3.py` does not import it. The 72 exam cutoffs were not opened, scored or
inspected; digest
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, and
`out/v2_1_exam_predictions.json` does not exist.

```bash
./.venv/Scripts/python.exe -W ignore -m alpha.ladder_v2_3 --quiet   # ~5 min, development only
./.venv/Scripts/python.exe -W ignore -m alpha.v2_1_exam predict     # still refuses: §5.2 gate is closed
```
