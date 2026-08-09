# V4 Charter — a new research programme on horizon-matched slow information

**Written 2026-08-09. CHARTER ONLY. Committed before any V4 measurement exists.**

No V4 study has been run. No feature was built, no target was constructed, no forward
return at any horizon was read, no backtest was executed, no data was fetched, no model
was fitted, and no exam cutoff was opened. Every number in this document is one of:

* **(V3)** — quoted verbatim from a completed, committed V3 artefact;
* **(STRUCT)** — a rank-versus-rank structural property computed from a completed V3
  feature panel with **no target attached**, quoted from `alpha/V4_FORMULATION_REVIEW.md`;
* **(ARITH)** — arithmetic on (V3) and (STRUCT) values, derived in-line so it can be
  checked.

**V3 is closed and is not touched by this document.** No V3 pre-registration, family
module, result, report, registry entry, exam artefact or production adapter is edited,
amended, reinterpreted, rescored or superseded here. Exam sealed at
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. Production weight
`0.0`.

The design basis accepted here is `alpha/V4_FORMULATION_REVIEW.md` (commit `21a81d0`),
which is likewise not edited by this charter.

---

## 0. What this document is, and what it is not

**It is:** the constituting instrument of a new research programme, V4, created under the
master roadmap's own §21 clause that *"Reconsidering the formulation is a new programme
with a new directive, commissioned deliberately, not a continuation"*, and under §27F,
which reserves that commissioning to the account holder rather than to an executing
session. That commissioning has now occurred on the record.

**It is not:** an authorisation to run anything. V4-SUE is authorised to *proceed to its
power gate*, and to nothing beyond it. §6 and §9 govern what happens next. This charter
does not start the gate.

---

## 1. Relationship to V3 — stated without hedging

| Statement | Status |
|---|---|
| V3 is **CLOSED** | Affirmed. `reports/PROGRESS_V3.md`, `alpha/V3_FAMILY3_REPORT.md` §8 |
| Family 1 (EDGAR fundamentals / SUE) | **REJECTED.** Unchanged |
| Family 2 (Form 4 insider purchases) | **REJECTED.** Unchanged |
| Family 3 (13F holdings change) | **REJECTED.** Unchanged |
| V3 budget slots | **3 of 3 SPENT. 0 remain.** Unchanged |
| Re-running any V3 family **under V3** | **PROHIBITED.** No Family 1′, 2′ or 3′ exists or may exist |
| Any V3 threshold, result, tally, interval, decision or interpretation | **UNCHANGED.** Nothing is rescored |
| The 72-cutoff exam | **SEALED**, digest `b55e065f4c9f9173…`. Not opened, not read, not rebuilt |
| Production weight | **0.0.** `alpha/adapter.py` untouched |
| Amendment A1 | Stands as written; prospective from Family 3 onward; changes no completed result |

**V4 is a separate programme with a materially different scientific question.** The
distinction does **not** rest on a new λ, a new carrier, a new learner, or a cosmetic
re-parameterisation. It rests on a **change of dependent variable** (§2), which V3 never
measured and, by its own §8 prohibition on adding a second horizon, could not have
measured.

V4 inherits from V3 exactly three things and nothing else: the point-in-time discipline,
the statistical machinery (`alpha/stats.py`, `alpha/examset.py`), and the standard of
honesty. It inherits no slots, no permissions, and no benefit of the doubt.

---

## 2. The V4 question

### 2.1 What V3 asked

> Does filing-derived information add incremental cross-sectional predictive value over
> B3 at a **5-session** horizon, through a **weak bounded tilt** (λ = 0.25), by an amount
> ≥ +0.007 IC?

Answered three times. Answer: no. **(V3)** Family 1 +0.00090, Family 2 −0.00096,
Family 3 −0.00339.

### 2.2 What V4 asks — the primary hypothesis, stated so it can fail

> **H1 (V4 primary).** Economically slow, filing-timestamped information contains
> incremental cross-sectional predictive information over the B3 regime-switched momentum
> incumbent at a **pre-registered 20-session horizon** which it does not contain at 5
> sessions — such that an arm of materially greater ranking authority,
> `rank_pct(B3) + 0.50·(rank_pct(feature) − 0.5)`, scored against **20-session forward
> alpha**, exceeds B3's own within-cutoff Spearman IC by **≥ +0.0095 in native 20-session
> units**, with the 95% moving-block bootstrap interval of the paired per-cutoff
> difference lying **entirely above zero**, positive breadth in both chronological halves,
> and survival with `BEAR_TREND` cutoffs removed.

**H0 (the null V4 must be able to accept).** Slow filing-derived information decays no
more than √H-proportionally between 5 and 20 sessions, so lengthening the horizon buys
only the cost reduction and no informational gain; the incremental contrast at 20D is
inside its own resolution, exactly as at 5D.

**What falsifies H1:** any of the four criteria in §5 failing. Specifically and in
advance: if the feature's **standalone** 20D IC does not exceed its pure √(H/5)
extrapolation from 5D by enough to reach the §7 threshold, H1 is **false**, and the
correct recorded conclusion is that free point-in-time filing data on this universe
cannot beat B3 at any horizon this history can test — **not** that a third horizon should
be tried.

### 2.3 The change of dependent variable is the science, not a tuning step

This must be unambiguous, because it is the entire basis on which V4 is admissible.

* `alpha_5d` and 20-session forward alpha are **different random variables**, not two
  estimators of one. The V4 target is not a smoothed, re-weighted or re-scaled version of
  the V3 target; it is a different outcome over a different window.
* The horizon was fixed **before any 20D quantity was computed**, on economic and
  structural grounds set out in `V4_FORMULATION_REVIEW.md` §1: quarterly-cadence
  information, 13F holdings **(V3)** median 92 / p90 128 days stale on arrival, tested
  against a five-session window. The choice of 20 rather than 40 or 60 was made on the
  **statistical-instrument** ground that 40D and 60D would require re-deriving the
  bootstrap block length — a change to a tested instrument — not on any performance
  observation.
* **No 20D predictive number exists anywhere in the V3 record.** V3 §8 forbade adding a
  second horizon, and none was added. There is therefore no 20D result to have peeked at,
  and no possibility that 20D was selected because it looked better.
* The horizon change makes a **new, independently falsifiable prediction** — superlinear
  decay — that is logically independent of V3's hypothesis. H1 can be false while V3's
  hypothesis is true, and vice versa. Two hypotheses that can disagree are not the same
  hypothesis.

**The λ change from 0.25 to 0.50 carries none of this justification and is not asked to.**
It is secondary (§5.3). If the horizon change were removed, V4 would collapse into a
prohibited Family 1′ and would not be admissible.

---

## 3. The §21 supersession boundary

### 3.1 V3 §21 is not deleted, amended, or reinterpreted

Master roadmap §21 and V3 pre-registration §8/§2.9 remain in force **exactly as written**.
They continue to prohibit, permanently:

* any Family 1′, 2′ or 3′ **within V3**;
* re-testing a rejected V3 family with another feature, learner, carrier, model or horizon
  **as a V3 study**;
* a fourth V3 family;
* any change to a completed V3 result, threshold or decision.

Nothing below relaxes any of that. A reader who wants to know what V3 concluded should
read V3, and will find it unaltered.

### 3.2 What this charter authorises, prospectively

V4 — a distinct programme with its own budget, its own gates and its own stopping
rules — may reuse a **previously studied information source** only where **all six**
conditions hold, each verifiable before any measurement:

| # | Condition | Status for V4-SUE |
|---|---|---|
| 1 | The target horizon is **materially different** and pre-registered before measurement | **MET.** 20 sessions, fixed in §5 of this charter, committed before any 20D quantity is computed |
| 2 | The arm architecture is **materially different** and pre-registered before measurement | **MET.** λ = 0.50, Spearman(arm, B3) 0.9191 and 26.7% of the traded book reordered **(STRUCT)**, versus 0.9758 and 14.4% at V3's λ = 0.25 |
| 3 | **No V3 result is rescored or reinterpreted** | **MET.** No V3 file is read for re-evaluation, edited or re-run. V3 numbers appear here only as quoted priors |
| 4 | **No sign is flipped based on a V3 outcome** | **MET.** SUE's sign is **+1 by economic prior**, fixed in `V3_PREREGISTRATION.md` §6.1 before Family 1 ran, and carried through unchanged. A negative V3 outcome would not have licensed a flip and none is made |
| 5 | **No V3 hyperparameter is optimised from V3 results** | **MET, with disclosure — see §3.3** |
| 6 | The V4 study receives **its own fresh budget and stopping rule** | **MET.** §8 and §9. V4 draws nothing from V3's exhausted three slots |

**Any candidate failing any one of these six is not admissible to V4.** The conditions are
conjunctive and are not weighed against each other.

### 3.3 The one place contamination could enter, disclosed rather than glossed

`alpha/V3_FAMILY1_REPORT.md` §3 contains a **λ sensitivity curve**, reported as a
diagnostic under V3 §6.1. That curve was computed **with the target attached**. Selecting
λ = 0.50 *because a point on that curve looked favourable* would be promoting a diagnostic
to an arm — prohibited by §0.1 — and would contaminate V4 with a V3 outcome.

That is not how λ = 0.50 was chosen, and the record supports the distinction:

* λ = 0.50 was derived in `V4_FORMULATION_REVIEW.md` §2.5–§2.6 from a **resolution
  ceiling**: it is the *maximum* authority the §2.6 half-width gate can still admit at a
  20-session horizon **(ARITH** on **(V3)** half-width anchors**)**. Equal weight
  (λ = 1.00) is preferred on every other ground and is excluded solely because its
  estimated 20D half-width ≈ 0.0160 exceeds the MDE. The binding input is a variance, not
  a performance number.
* The V3 λ curve reported a **null across its whole range** — "no setting of the dial
  rescues it" **(V3)**. A curve that is flat and null in every direction carries no
  information favouring 0.50 over any other value. There is nothing there to have selected
  on.
* Had that curve shown a favourable λ, selecting it would have been inadmissible and this
  charter would have had to fix λ on a rule independent of it, or not reuse SUE at all.

**No point on any λ curve, V3's or V4's, may be promoted to an arm. λ = 0.50 is fixed in
§5 and is never scanned.**

### 3.4 Why this is a new hypothesis and not a disguised V3 rerun

Four arguments, of which the fourth is the decisive one.

**(a) Different dependent variable.** §2.3. A test of a different outcome variable is a
different test, in the same way that a drug trial with a different endpoint is a different
trial. V3's answer is untouched because V3's question is untouched.

**(b) V3 could not have answered it.** No 20D number exists in the record. This is not a
second look at data already seen; it is a first look at data never read. There is nothing
to re-score because nothing was scored.

**(c) The prediction is independently falsifiable and can come out either way.** H1
asserts superlinear decay. That assertion is *not implied* by V3's hypothesis and is *not
refuted* by V3's result. §2.2's falsifier is stated in advance and is severe: √H scaling
alone is not enough to pass.

**(d) Identifiability — the argument that makes reuse necessary rather than merely
tolerable.** §21 requires, on the failure of all three families, the conclusion that
*the formulation* is wrong. That conclusion is itself a hypothesis, and a programme that
wishes to test it must **vary the formulation while holding the information fixed**. If
V4 changed both — new horizon *and* a source no V3 family touched — a null would be
uninterpretable (was the formulation still wrong, or was the new source simply empty?) and
a pass would be equally uninterpretable (did the horizon matter, or did we merely find a
better factor?). **Reuse is not a loophole around §21; it is the only design under which
§21's own mandated conclusion is falsifiable at all.** Substituting fresh information
would confound exactly the two effects V4 exists to separate.

If any of (a)–(d) failed, the correct action would be to record that V4 reuse is not
scientifically admissible and stop. They do not fail. **Reuse of SUE is authorised**,
subject to §4, §6 and §7.

---

## 4. First V4 candidate: SUE, and only SUE

### 4.1 Authorised

**`sue`** — time-series standardized unexpected earnings on `NetIncomeLoss`, seasonal
difference over the year-ago quarter, scaled by the standard deviation of the last 8 such
surprises (minimum 4), Q4 derived as FY − (Q1+Q2+Q3), winsorised per cutoff at 1/99,
acceptance-time point-in-time door. **The construction is carried over unchanged from
`V3_PREREGISTRATION.md` §3 and may not be modified.** Changing the feature definition
would make V4 a new-feature study rather than a new-formulation study and would destroy
the identifiability argument in §3.4(d).

### 4.2 Rationale — from completed V3 evidence only

1. **It is the only V3 information family whose standalone interval excluded zero.**
   **(V3)** IC +0.01305, 95% CI [+0.00263, +0.02339], hit rate 0.576, both chronological
   halves positive (+0.01100 / +0.01509), turnover 0.091, coverage 0.930.
2. **Its failure mode was "real but not incremental" at the V3 formulation** — the one
   failure mode a formulation change can in principle reverse. Families 2 and 3 failed as
   *absent*, and amplifying absence yields absence.
3. **It is therefore the only source carrying affirmative prior evidence strong enough to
   justify spending a slot on a new formulation.** At the §7 threshold it stands at ≈ 82%
   of the bar **(ARITH)** — close enough that a horizon effect of plausible size could
   close the gap, and far enough that the test is not a foregone conclusion.

### 4.3 The adverse prior, recorded now rather than discovered later

**(V3)** SUE's long-short spread at 5D did **not** clear zero: +0.00051,
CI [−0.00081, +0.00158]. An IC that excludes zero alongside a spread that does not is the
signature of a factor ranking the **middle** of the cross-section rather than its tails —
which is where a portfolio must trade. Roadmap §10 and V3 §6.2 make **net-of-cost spread
advantage primary from the first measurement**, and V4 does not relax that. This is
written here, before measurement, so that a 20D spread that again fails to clear zero is
recognised as a predicted adverse outcome and not re-described as a technicality.

### 4.4 Not authorised

* **13F (Family 3) — NOT authorised for V4.** It is the most horizon-sensitive source and
  therefore the most interesting in principle, but **(V3)** its standalone IC is −0.00659
  with a CI spanning zero: no evidence of a signal to amplify. It is **not**
  pre-authorised as Slot 2 and acquires no standing from this charter. §8.3 governs
  whether it may ever be considered.
* **Form 4 (Family 2) — NOT authorised, at any horizon or architecture, under its current
  construction.** Its defect is structural and formulation-invariant: **(V3)** 86% of names
  tied at exactly zero, **no name reached the bottom quintile at any of 316 cutoffs**, and
  the long-short spread was undefined everywhere. A longer horizon and a stronger tilt do
  not create a short book. Only a materially different, demonstrably two-sided
  construction of insider information could ever be considered, and this charter does not
  contemplate one.
* **No new information family may be introduced into V4.** V4 is a formulation study, not
  a feature search. There is no open-ended candidate pipeline.

---

## 5. The frozen V4 primary formulation

Fixed here, before any measurement. Nothing in this table may be changed after a V4 result
exists; corrections follow the record's convention — appended, dated, original wording
left visible.

| # | Element | Specification — FROZEN |
|---|---|---|
| 1 | **Target** | Within-cutoff Spearman IC on **20-session forward alpha** (asset return − SPY return over 20 sessions), built by the existing tested instrument `alpha/targets.py` with `horizon=20`. The column must be named for its horizon and never conflated with `alpha_5d` |
| 2 | **Primary horizon** | **20 sessions. One only.** No second horizon is run, reported as an arm, or added later |
| 3 | **Primary arm** | `rank_pct(B3) + 0.50·(rank_pct(sue) − 0.5)`. **λ = 0.50 fixed**, never scanned; no point on any λ curve is promotable to an arm |
| 4 | **Feature** | `sue`, construction frozen per §4.1 |
| 5 | **Sign** | **+1, by economic prior**, carried unchanged from `V3_PREREGISTRATION.md` §6.1. Never estimated from data; never flipped on any outcome |
| 6 | **Incumbent** | **B3** regime-switched momentum. Not modified, not swapped, not re-tuned |
| 7 | **Mandatory baselines** | **B1** 12-1 momentum, **B2** 5-day reversal, **B3** (incumbent), and **standalone SUE rank** (Arm 0 — required by §7's screen and not optional) |
| 8 | **Arms declared** | **Two** (Arm 0 standalone, Arm 1 the λ = 0.50 combination). One primary contrast: Arm 1 − B3. Holm–Bonferroni across the two |
| 9 | **MDE** | **+0.0095 IC in native 20-session units** versus B3. Re-derived from the frozen 5 bps cost model at 13 rebalances/year. **Never lowered.** It may be *raised* only by the mechanical exception in §5.1 |
| 10 | **Criterion direction** | **Amendment A1 logic: favourable side only.** `bool(lo > 0.0)`. An interval lying entirely *below* zero is a FAIL of this criterion, not a pass |
| 11 | **CONTINUE rule** | All four: (1) Arm 1 − B3 ≥ +0.0095 native 20D; (2) 95% block-bootstrap CI excludes zero **on the favourable side**; (3) breadth > 0.50 **and** both chronological halves positive; (4) survives with `BEAR_TREND` removed. **Anything less is REJECT** |
| 12 | **PIT rule** | Acceptance-time door (`alpha/filings.py`, tested). Unchanged, not approximated, not relaxed |
| 13 | **Coverage / continuity gate** | ≥ 0.80 of the point-in-time cross-section, and the feature must permit forming **both** book tails at every cutoff — the Family 2 lesson, made a gate |
| 14 | **Economic significance** | Net-of-cost spread advantage at 5 bps is **primary from the first measurement**. Added turnover ≤ 30 pp or the MDE rises |
| 15 | **Noise control** | 30 paired within-cutoff permutations of `sue`. Fails if the median exceeds +0.002 (5D-equivalent scale, restated in native 20D units at gate time) or if > 10% of draws clear the CONTINUE threshold. A single draw never aborts a run |
| 16 | **Sample** | The 316 development cutoffs, **less those whose 20-session forward window runs past the end of the price history**. The actual usable count is determined mechanically at gate time and is the count the power gate must use |

### 5.1 The only permitted movement in the MDE

The MDE may be **raised** — never lowered — if the cost re-derivation at gate time shows
the 13-rebalances/year assumption understates cost, or if §5 item 14's turnover ceiling is
breached. The MDE may be **lowered only** if a purely mechanical, pre-measurement
re-derivation of the frozen cost model demonstrates that the review's ≈ +0.0095
approximation was arithmetically wrong — the correction must be published *before* the
power gate is run and must not depend on any 20D predictive quantity. No other route
exists.

---

## 6. The power gate — blocking, and it must be run before any slot is spent

**No V4 slot may be spent before a fresh, exact §2.6 power gate for this exact design
passes.** The review's estimate is **≈ 1.03× margin** — 0.0092 estimated half-width
against a 0.0095 MDE **(ARITH)**. That is marginal by any reading, and an extrapolation
rather than a measurement.

### 6.1 What the gate must do

1. **Estimate the achieved half-width for the frozen design** — λ = 0.50 arm, paired
   against B3, on the actual usable 20D cutoff count (§5 item 16) — using the existing
   variance and autocorrelation machinery in `alpha/stats.py`
   (`block_bootstrap_ci`, `paired_difference`, `newey_west`), **reused, not rewritten**.
2. **Do so without reading any V4 predictive outcome.** The gate is permitted to touch
   variance and dependence structure. It is **not** permitted to compute, report or
   inspect the Arm 1 − B3 point estimate, the standalone 20D IC, or any other predictive
   quantity. If the only way to obtain the half-width is to compute the effect, the gate
   must be structured so the effect is not read by any human or written into any file that
   is read before the gate verdict is recorded.
3. **Explicitly account for 20-session overlapping returns.** At 5-session cutoff spacing
   a 20-session window overlaps **three neighbours on each side**. Effective independent
   sample size is materially below the nominal cutoff count.
4. **Do not reuse `BLOCK_LENGTH = 4` blindly.** Four cutoffs span 20 sessions, which
   equals the horizon but does **not** span the full ±3-neighbour dependence range that a
   20-session window induces on a 5-session grid; the textbook prescription would be a
   block of at least 5, and arguably 7, cutoffs. `V4_FORMULATION_REVIEW.md` §1.5 asserted
   that 4 "spans exactly that"; **this charter does not accept that assertion and requires
   it to be established or replaced.** The gate must either justify 4 on the measured
   autocorrelation of the paired difference series, or adopt the statistically justified
   longer block — and must **document the choice and its reason before any predictive
   result is read.**
5. **Compare the achieved half-width against the frozen MDE of +0.0095 native 20D.**

### 6.2 The verdict, and what follows from it

* **PASS** — achieved half-width ≤ +0.0095 native 20D. V4-SUE may then proceed to its own
  pre-registration (§9.4) and, after that document is committed, to Slot 1.
* **FAIL** — achieved half-width > +0.0095. **V4-SUE MUST NOT RUN.** The result is
  recorded as *"not resolvable on this history at this horizon"*, which is a real finding
  and is reported as one.

**A failed gate may not be answered by weakening anything.** Not the MDE, not the arm, not
the CI rule, not the criterion direction, not the horizon, not the block length, not the
coverage gate, not the universe, and not by adding cutoffs from outside the frozen
development set. A gate that can be argued past is not a gate — this is the rule whose
absence, on the record's own account, cost four studies.

**Expected outcome, stated in advance so a failure is not a surprise:** if the justified
block length exceeds 4, the achieved half-width will exceed the 0.0092 extrapolation, and
a ≈ 1.03× margin cannot absorb much widening. **This gate is more likely to fail than to
pass.** That is a legitimate outcome of a correctly specified programme, and the charter
records it now so that a FAIL cannot later be reframed as a technicality.

---

## 7. The standalone-strength pre-screen

The most useful thing `V4_FORMULATION_REVIEW.md` produced is a bar V3 never computed:
**how strong a new source must be, standalone, for a fixed combination architecture to
beat the incumbent by the MDE.** V4 formalises it as a standing admission test.

### 7.1 What it is, and what it is not

**It IS** a design/power screen: pre-measurement arithmetic on the *frozen architecture*
and *prior* evidence, answering "what would this source have to be worth for this design
to work?"

**It is NOT** a predictive pretest. It does not read a V4 forward return, it does not
estimate the candidate's 20D IC, and its threshold may **never** be revised using realized
V4 target performance.

### 7.2 The mechanical threshold, recomputed for the frozen λ = 0.50 arm

For two near-orthogonal rank signals — V3 measured |ρ| between its features and
`z__ret_12_1` at 0.0726–0.1313 **(V3)** — the arm `u_B3 + λ·u_f` has IC approximately
`(r_B3 + λ·r_f)/√(1 + λ²)`. Requiring that to exceed `r_B3 + MDE` gives, exactly:

```
r_f  >  [ (√(1+λ²) − 1)·r_B3  +  √(1+λ²)·MDE ] / λ
```

At **λ = 0.50** (√1.25 = 1.11803): `r_f > 0.23607·r_B3 + 2.23607·MDE`.

| Quantity | Value | Provenance |
|---|---|---|
| B3 IC at 5D | +0.02241 | **(V3)** |
| B3 IC at 20D, pre-registered √(H/5) scaling | +0.04482 | **(ARITH)**, assumption fixed in §7.3 |
| MDE, native 20D | +0.0095 | frozen, §5 |
| **Required standalone SUE IC at 20D** | **≈ +0.0318 native** (≈ +0.0159 5D-equivalent) | **(ARITH)** |
| Review's reference value, 5D formulation, equal weight | ≈ 0.0192 (5D MDE) / ≈ 0.0164 (20D-adjusted MDE) | quoted, preserved |

The review's ≈ 0.0192 / ≈ 0.0164 reference values are **preserved as stated** and are
consistent with the exact recomputation: the requirement is nearly flat in λ across
[0.5, 1.0] — 0.0165 at λ = 0.50 versus 0.0164 at equal weight in 5D-equivalent units
**(ARITH)** — and rises steeply below it, to ≈ 0.0234 at V3's λ = 0.25. **The λ = 0.50 arm
therefore sits close to the most favourable point of the authority/resolution trade-off,
which is an independent confirmation of §2.6's choice made on variance grounds alone.**

### 7.3 The admissibility rule, fixed before measurement

Let **R** = required standalone 20D IC (≈ +0.0318 native, above) and **P** = the
candidate's √(H/5) extrapolation from its measured 5D standalone IC, i.e. the value
implied if the horizon buys nothing informational — the H0 of §2.2.

For SUE: **P = 2 × 0.01305 = +0.0261 native (ARITH)**, hence **R / P ≈ 1.22**.

> **Pre-registered screen rule: a source may be admitted to a V4 slot only if R / P ≤ 1.5.**

That is: the horizon hypothesis is required to be true by no more than 50% beyond pure
√H scaling. A candidate needing more than that is asking for a decay profile no plausible
economic mechanism delivers, and the slot must not be spent. **The 1.5 factor is a
judgement, and it is fixed here, before any measurement, which is the only condition under
which such a factor means anything.** It is not adjusted afterwards.

**SUE at R / P ≈ 1.22 PASSES the screen.**

Two constraints on this arithmetic, binding:

* **r_B3 at 20D is taken at its √H-scaled value of +0.04482 by pre-registration.** Its
  realized 20D value cannot be known without reading 20D returns, and will be measured as
  a mandatory baseline during the study itself. **The realized value may not be
  substituted back into §7.2 to relax R after the fact.** If the realized B3 20D IC is
  lower, that is a finding to report, not a licence to lower the bar.
* **The screen does not replace the power gate, and passing it confers nothing.** §6 is
  the blocking gate; §7 is an admission test that a candidate must also pass. Both, or no
  slot.

### 7.4 Standing application

Every future V4 candidate — should Slot 2 ever open — must pass §7.3 with its own R and P
computed the same way, before its slot is spent. This is the screening failure V3 is
diagnosed as having: it never asked what a candidate would have to be worth.

---

## 8. The V4 research budget

### 8.1 The budget

> **V4 budget: at most TWO confirmatory information studies. Slot 2 is conditional and is
> not pre-authorised.**

* **Slot 1 — SUE under the frozen V4 formulation.** Authorised to proceed to §6's gate.
* **Slot 2 — conditional, and empty.** No source occupies it. It may be opened only under
  §8.3.

V4 draws no slots from V3. V3's three remain spent and closed.

### 8.2 If Slot 1 fails cleanly under adequate power

**The default interpretation is fixed here:** changing the formulation did **not** rescue
the only positively evidenced V3 information source. Combined with V3's three rejections,
the honest reading is that **free point-in-time filing data on this universe does not
contain incremental information over B3 of a size this history can resolve, at either the
fast or the slow end of the tested horizon range.** The correct response is to record that
and stop — not to open Slot 2 by default, and not to look for a third horizon.

### 8.3 The only evidence that justifies spending Slot 2

Slot 2 may be opened **only if all four** hold:

1. **Slot 1 established that the V4 formulation itself is viable** — i.e. the horizon
   change demonstrably did something measurable, shown by SUE's **standalone** 20D IC
   materially exceeding its √H extrapolation P = +0.0261 **(ARITH)**. A flat or
   sub-√H standalone result means the formulation is dead and no second source can revive
   it.
2. **Slot 1's failure, if it failed, was diagnosed as source-specific rather than
   formulation-specific** — and the diagnosis is recorded in the registry before Slot 2 is
   proposed.
3. **A separately pre-registered scientific reason exists for the specific new source**,
   written as its own falsifiable hypothesis, not as "the next one on the list".
4. **The candidate passes §7.3's screen and §6's power gate on its own numbers.**

If Slot 1 *passes*, Slot 2 is not thereby justified either: a pass routes to §9.3, not to
more sources.

**13F is not pre-authorised** and gains no standing from this charter. **There is no
open-ended feature search in V4.**

---

## 9. Stopping rules, fixed prospectively

### 9.1 If V4-SUE fails the admissibility or power gate

* **Do not run it.** The slot is recorded as *not spent on a study* and the outcome
  recorded as "not resolvable on this history at this horizon".
* **Do not modify the formulation to make it runnable.** No MDE reduction, no λ increase,
  no horizon substitution, no block-length shortening, no universe expansion, no coverage
  relaxation, no swap of the incumbent.
* Report and stop.

### 9.2 If V4-SUE runs and fails the confirmatory CONTINUE rule

The family is REJECTED, the slot is SPENT, and:

* **No SUE′.** The source is not re-tested in V4 under any variant.
* **No alternative horizon.** Not 10D, not 40D, not 60D, not a blend, not "as a
  diagnostic".
* **No λ scan**, and no promotion of any point on any λ curve to an arm.
* **No sign flip**, at any horizon, on any outcome.
* **No learner substitution.** V4 is an information-only test; a fitted model is not an
  answer to an information null (§2.9).
* **No re-specification of the target** (volatility-adjusted, sector-neutral, residual,
  winsorised differently, or otherwise).
* **No sub-universe, sector, regime or period restriction** to make a result survive.

### 9.3 If V4-SUE passes

* **STOP BEFORE PRODUCTION.** A passing information test is the beginning of the ladder in
  roadmap §22, not the end of it.
* **Do not open the exam.** §10.
* **Do not raise production weight.** It remains `0.0`.
* **Require explicit authorization for the next phase.** The next phase is commissioned by
  the account holder, in writing, as a separate decision — the same discipline that
  produced this charter.

### 9.4 Sequencing requirement

The order is fixed and may not be reordered: **charter committed (this document) → power
gate §6 → pre-screen §7 recorded → V4-SUE pre-registration committed as its own document
→ first fit.** No measurement of a V4 predictive quantity may occur before the fourth step
is complete and committed.

---

## 10. Exam policy

### 10.1 The sealed exam is not automatically reusable, and the reason is concrete

The 72-cutoff exam is sealed at digest `b55e065f4c9f9173…`. Whether it can remain a valid
final test after the research question, horizon and architecture changed is a question the
charter must answer prospectively, and the answer is **no, not as constituted**.

`alpha/examset.py` fixes the split's separation guarantee as
`MIN_SEPARATION = HORIZON + EMBARGO = 10 sessions`, with `HORIZON = 5`. Exam cutoffs sit
every 6th grid step, i.e. 30 sessions apart, and development cutoffs within 10 sessions of
an exam cutoff were purged. **This is a configuration fact, readable from the selection
rule, and establishing it requires opening nothing.**

At a **20-session** horizon the required separation is 25 sessions, not 10. A development
cutoff 15 sessions before an exam cutoff — retained under the existing rule — has an
outcome window `[t, t+20]` that **overlaps the exam window `[t+15, t+35]` by five
sessions**. The split's core guarantee, that no development observation shares outcome
data with an exam observation, **does not hold at 20D.** The exam is not contaminated by
anything done so far; it is simply **not constituted for this horizon**.

A second, lesser point: at 20D the exam's resolution is at best comparable to the
development set's (exam cutoffs are 30 sessions apart and therefore non-overlapping, which
partly offsets the smaller count), so a **≈ 1.0× margin against the +0.0095 MDE
(ARITH)** is the optimistic reading and roughly 2× too wide is the pessimistic one. Even
setting the separation defect aside, the existing exam would be a marginal final test for
a 20D question.

### 10.2 The policy

* **Default and operative position: the exam stays SEALED throughout V4 development.**
  Not opened, not scored, not inspected, not rebuilt, not re-cut, not counted, not used to
  choose anything. Digest unchanged.
* **The exam is not reused automatically for V4** and is not assumed valid for a 20D
  target.
* **If V4 ever reaches a stage requiring a final untouched test, a new exam definition
  would be required**, constituted for the 20-session horizon with a separation of at
  least `20 + EMBARGO` sessions, frozen and hashed before any V4 result is read against
  it. **That is stated here prospectively and nothing more.** No such exam is designed,
  built, specified in detail, inspected, or costed now. Doing so would itself be a design
  decision taken with V4 development results in view.
* Building a new exam is a **separate authorisation**, contingent on §9.3 and on the
  account holder's explicit instruction.

---

## 11. Prohibited in V4, restated so this document stands alone

* Opening, scoring, inspecting, modifying or rebuilding the 72 exam cutoffs.
* Raising production weight above `0.0` or modifying `alpha/adapter.py`.
* Editing, amending, rescoring or reinterpreting any V3 artefact.
* Lowering the MDE, weakening the CI rule, or changing the criterion direction after any
  result is seen.
* Adding a second horizon, a third arm, a second feature, or a fitted learner.
* Promoting a diagnostic, a λ point, a rung or a noise-control draw to an arm.
* Restricting any result to a regime, sector, year or sub-universe to make it survive.
* Flipping any sign on any outcome.
* Reporting development numbers as alpha.
* Purchasing data, trialling a paid provider, or silently substituting a lower-quality
  free source (§27B).
* `git push` (§27A — `origin` is a third party's public repository).

---

## 12. Recording

* **This charter is committed before any V4 measurement exists.** It is the only file this
  session adds.
* The V4-SUE study requires **its own pre-registration document**, committed before the
  first fit, fixing anything this charter leaves to gate time (usable cutoff count,
  justified block length, restated noise-control thresholds in native 20D units).
* Results, if any, are written to `alpha/out/` with per-cutoff series so every headline
  number is re-derivable from per-cutoff data.
* The registry entry records: hypothesis, source, target/horizon, arms, MDE, achieved
  half-width, result with its half-width, stability, net of costs, decision, and the
  diagnosis — **did the information fail, or the target, horizon, PIT quality, coverage,
  economics, or the power?**
* Every run is logged, **including aborted and superseded ones** (§2.7).

---

## 13. Preservation statement

Nothing in V3 was edited by this charter: no pre-registration, no family module, no
completed result, no report, no registry entry, no exam artefact, no production adapter.
`alpha/V4_FORMULATION_REVIEW.md` was not modified. **No predictive measurement of any kind
was performed. No data was fetched. No forward return at any horizon was read. The exam
remains sealed at `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.
Production weight remains `0.0`. Nothing was pushed.**

**V4-SUE is not authorised to run by this document.** It is authorised only to proceed to
the §6 power gate, and the gate does not start until the account holder says so.
