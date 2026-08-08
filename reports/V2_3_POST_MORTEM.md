# V2.3 Post-Mortem — the bounded-adjustment architecture, and the four-study line that produced it

**Date: 2026-08-08. Status: closed.** V2.3's §6 gate closed, its pre-registered
abandonment criterion 6 is met in exact form (with 4-with-5 met independently), and
per §9 the architecture ends. No V2.4 is proposed in this document.

*Independently audited 2026-08-08; the closure decision was confirmed by
re-derivation. See `reports/V2_3_FINAL_DECISION_AUDIT.md` and
`reports/PROGRAMME_STATUS_V2_3.md`.*

Primary record: [`alpha/V2_3_LADDER_REPORT.md`](Stock-Prediction-Models/alpha/V2_3_LADDER_REPORT.md).
This file is the retrospective — what was believed, what the belief chain got
wrong, what the process got right, and what is now settled well enough that it
should not be re-tested.

**State of the world, unchanged by all of it:** production weight **0**, action
**HOLD**. The 72 V2.1 exam cutoffs have never been opened; digest
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`,
`out/v2_1_exam_predictions.json` does not exist. `pytest -q --runslow` — 625 passed.

---

## 1. The one-paragraph version

Four pre-registered studies, eleven fitted arms, and a full rebuild of the
validation protocol produced **no model that beats 12-1 cross-sectional momentum
with a confidence interval excluding zero**, and **no model that beats a
three-line hand-coded regime rule at all**. The single apparent exception —
V2.2-B's +0.00241 over momentum, the only positive interval in the family — was
destroyed by V2.3's controlled test, which showed it to be the residue of a model
99.2% collinear with momentum inside every cutoff. When the collinearity was
removed and the model was given 5.8× more real authority, the advantage inverted
to −0.00052. **The architecture failed on its hypotheses, not on its plumbing:**
both V2.3 arms passed every eligibility check the design could impose.

---

## 2. The belief chain, and where each link broke

Each study diagnosed the previous null and fixed it. Every diagnosis was correct
about the mechanism it named. **None of the fixes produced alpha**, and that is
the finding — the failures were not a sequence of unrelated mistakes converging on
a solution, they were a sequence of correct repairs to a system with no signal to
carry.

| Study | Diagnosis of the prior null | Was the diagnosis right? | Did the fix pay? |
|---|---|---|---|
| **V2** | Feature coverage is too thin; exam is too small (12 dates) | Yes on both | **No.** 47 relative/percentile features moved mean IC from +0.0084 to +0.0085 |
| **V2.1** | The exam and the benchmark were wrong; rebuild to 72 cutoffs with 12-1 momentum as the bar | Yes — and it exposed a real defect: a GBM on `ret_12_1` alone scored +0.00053 against the factor's own +0.02115, ρ −0.198 with its own input | **No.** Best arm +0.01312 over momentum, CI [−0.01862, +0.05006] |
| **V2.2** | The carrier destroys the factor; route it around the learner | Yes, and it measured *why*: `E[target_rank \| z__ret_12_1]` spans **0.023** while a leaf mean at `min_samples_leaf=100` has SE **0.029** — the learner's noise floor is wider than the signal | **No.** All four cells of the 2×2 grid land within 0.0023 of zero. One arm (B) showed +0.00241 |
| **V2.3** | V2.2-B's tilt is a copy of its own base; delete the base from the inputs and give the adjustment real authority | Yes — ρ̄ 0.9923 → 0.6981, effective λ 0.0619 → 0.3580 | **No, and backwards.** +0.00241 → **−0.00052**. More authority made it worse |

**The chain terminates cleanly.** V2.2's measurement (noise floor > signal) already
implied that no carrier routing a factor of this strength through this learner can
work. V2.3 tested the one remaining escape — carry the factor *around* the learner
and let the learner supply only a bounded tilt — and the tilt was worth nothing.

---

## 3. What we got wrong, as distinct from what failed

Failures of hypothesis are the point of the exercise. These are the reasoning
errors, and they are the transferable part.

### 3.1 We mistook a measurement artefact for a methodological gain

`V2_3_RESEARCH_DESIGN.md` §6 reported that a bounded-tilt arm is **~19× better
powered** against its own benchmark than an unconstrained one, and banked it as a
free improvement in how to test — a result about method, expected to carry
forward into the exam-resolution calculation.

It was the collinearity. An arm that is 99.2% correlated with its base inside
every cutoff has almost no paired variance against that base, which is the same
statement as "it barely differs from it."

| arm | effective λ | half-width vs its own base |
|---|---|---|
| V2.2-B | 0.0619 | **0.00182** |
| V2.3-A | 0.3580 | **0.00827** |
| V2.2-A (unconstrained, for scale) | — | 0.03492 |

Real authority rose 5.8×; the interval widened 4.5×. Near-proportional.
**Resolution and authority are the same dial.** An arm can be precisely measured or
it can be free to differ from its base; it cannot be both, and a power advantage
that appears for free should be read as a warning that the arm is not doing
anything.

*(The ladder report §3, experiment log entry 2 and `PROGRESS.md` item 3 originally
rounded both figures to "4.5×". The authority ratio is 0.3580/0.0619 = 5.8; the
resolution ratio is 0.00827/0.00182 = 4.5. All three were corrected in place on
2026-08-08 after the independent decision audit, each with the original wording
preserved in a note. The conclusion is unaffected.)*

### 3.2 We took a post-processed number as evidence about a fitted model

The design pass measured a **+0.00604 "orthogonal component"** in V2.2-B by
projecting its existing predictions off the base, and that number is what made the
architecture look promising enough to fund V2.3.

It did not survive being learned. A model trained to predict a residual *without
seeing the base* produces a different — and worse — adjustment than the orthogonal
projection of a model that did see it.

**The design pass's §3.1 refused to make post-processing an arm**, on exactly the
grounds that a post-processed number is already known and proves nothing about a
fitted model. That refusal was correct and is the single best decision in the
study. The error was continuing to reason from the number after declining to test
it directly.

### 3.3 We projected resolution from a mismatched probe

§6.2 predicted a B3-based arm would resolve to ≈**0.0039** against B3. Measured:
**0.00796** — optimistic by 2×, because the probe reused a model still 99%
collinear with a *different* base, so it barely moved this one.

Corrected figures, for any future document that needs them:

| paired difference | half-width @255 | scaled @72 |
|---|---|---|
| V2.3-A vs B1 | 0.00827 | 0.01556 |
| V2.3-A vs B3 | 0.01324 | 0.02492 |
| V2.3-B vs B1 | 0.01496 | 0.02815 |
| **V2.3-B vs B3** | **0.00796** | **0.01498** |
| V2.3-B net spread vs own base | 0.00099 | 0.00186 |

### 3.4 We wrote a sanity control without power discipline, and it nearly stopped the study on noise

§4's noise control specified **one** seeded Gaussian draw compared on **unpaired**
means, with the instruction that any gain ends the study. The pre-registered seed
landed ~2σ high and produced a +0.00123 "gain" — on pure noise, with its own
interval spanning zero. The first ladder run aborted on it.

Over 30 draws, paired per cutoff:

| base | mean paired difference | sd across draws | share of draws above base |
|---|---|---|---|
| `z__ret_12_1` | **−0.00202** | 0.00137 | **3%** |
| `z__b3` | **−0.00278** | 0.00138 | **0%** |

The single-draw spread (0.00137) is comparable to the effect (0.00202), so one
draw could never settle it. **A sanity control needs the same power discipline as a
gate**: pair it, and use enough draws that its sampling spread is small against
the effect it is meant to detect.

This produced the study's only protocol departure, made after the first fit. It is
disclosed in the report §7.2 and log entry 3; the pre-registered single draw is
still computed and reported verbatim, gain and all; the stop condition moved to
the powered statistic, which is *stricter*. A test pins the conditions under which
the departure stays defensible — if a single-draw gain is ever **significant**, the
powered version is no defence and the study must stop.

### 3.5 We let one regime bucket carry four consecutive studies without acting on it

`BEAR_TREND` has been the only bucket in which any arm improves on its base in
**V2, V2.1, V2.2 and V2.3**. It is 27 cutoffs, 17 of them (63%) in 2022. V2's
development edge lived there and **inverted out of sample** — BEAR on development,
SIDEWAYS on the exam, negative in each other's favourite.

This was visible from V2's report onward and was recorded each time as a caveat
rather than treated as a disqualifier. It became a formal abandonment criterion
only in V2.3 (§9 criterion 5). It should have been one two studies earlier: a
result that lives entirely in 17 weeks of one bear market is a single observation,
not a factor.

### 3.6 A pre-registered threshold was mis-calibrated and was correctly left alone

V2.2's G1/H1a floor of −0.005 was justified as room for `max_bins=255` ties, but
the binding limit is `max_leaf_nodes=31` under the monotone constraint, giving a
five-step staircase and a −0.00696 honest loss. V2.2-C was disqualified as
carrier-defective by a number that was wrong for the stated reason.

It was carried into V2.3 verbatim rather than corrected mid-line. **That was the
right call** — the explanation belongs in the report, not in a lowered threshold —
but it is worth naming as a real cost of pre-registration paid knowingly.

---

## 4. What the process got right

This matters as much as the errors, because the process is the only asset the four
studies produced that has value going forward.

* **The exam was never opened.** Four studies, four closed gates, seventy-two
  cutoffs still sealed at the original digest. `v2_1_exam.py predict` enforces the
  seal in code and exits 1. Every tempting move after a null — open it anyway, swap
  the benchmark, relax the gate to "mean > 0", add a fifth arm, report development
  numbers as alpha — is ruled out **in writing, in advance**, in
  `V2_1_LADDER_PREREGISTRATION.md` §5.2.
* **Abandonment criteria were fixed before the first fit and then honoured.** V2.3
  §9 named six; **criterion 6 is met in its exact pre-registered form** —
  "collinearity removed and still no advantage over base" — and criteria 4-with-5
  are met independently. Either ground alone ends the architecture. That is the
  sharpest test the design could construct, and the architecture failed the test it
  named for itself. There is no argument left to have. *(Clarified 2026-08-08 after
  the independent decision audit: this bullet originally counted criterion 2 as a
  third ground. Criterion 2's operative clause is satisfied — V2.3-B did not
  separate from B3, point estimate −0.00120 — but its precision premise of a ≈0.004
  half-width was not reached (0.00796 achieved, see §3.3), so its economic argument
  does not run and it should not be cited as a formally satisfied precision
  condition. Cite criterion 6.)*
* **The controlled contrast was genuinely controlled.** V2.3-A and V2.2-B share
  base, target, learner, hyperparameters, λ, cutoffs and 34 of 35 inputs. The 35th
  is the base. Target identity was asserted bit-identical before any fit. One
  deleted column, one measured consequence.
* **Code was extended additively and the prior record stayed intact.** `carrier.py`
  gained a `Collinearity` dataclass and function; no existing function was touched,
  and the evidence is that all 43 V2.2 tests pass unchanged against the extended
  module. `out/v2_2_development.json` still reports V2.2-B at +0.02356.
* **The departure was disclosed loudly rather than buried.** Report §7.2, log entry
  3, a test pinning its validity conditions, and the superseded number still
  printed verbatim in the frozen artefact.
* **Two arms with the highest mean ICs in the project (+0.03241, +0.02723) were
  correctly disqualified** by a floor set before anyone saw them.
* **Tests grew with each study and none were edited to pass:** 499 → 544 → 587 →
  **625**, none skipped.

---

## 5. What is now settled

These should be treated as answered. Re-testing them is not cheap scepticism, it
is spending the same power twice.

1. **Stock-level cross-sectional features do not rank the cross-section.** 18
   absolute features: +0.0084. Adding 47 relative/percentile features: +0.0085.
   Well-powered null over 423 cutoffs.
2. **A learned map cannot carry a factor of this strength.**
   `E[target_rank | z__ret_12_1]` spans 0.023; the leaf-mean SE is 0.029. Any
   carrier routing the factor through the learner meets this wall. The V2.1
   "decreasing map" defect was a symptom, not the disease.
3. **A factor must be in the output combination, not merely the input.** The
   bounded-blend rung keeps 99.1% of the factor; the pass-through rungs keep 2% and
   34%.
4. **V2.2-B's +0.00241 was not a diluted signal awaiting authority.** Authority ×5.8
   → advantage −0.00052.
5. **A bounded contextual adjustment does not improve on the hand-coded regime
   rule.** −0.00120 against B3, at the project's best resolution against that rule
   (half-width 0.00796), point estimate negative, both chronological halves
   negative, breadth 45.1%.
6. **The whole feature set is worth +0.0005 to +0.0014 of IC** over one momentum
   rank, carried correctly (V2.2 measured +0.0024 through a collinear carrier; the
   two agree the number is between zero and half a hundredth).
7. **No tilt pays for its own trading.** Net advantage over own base +0.00028 and
   +0.00002, both intervals spanning zero, turnover up 36–56%.
8. **The bounded blend does not manufacture IC from rank mechanics.** 30 noise
   draws: 0–3% exceedance, mean paired −0.00202 / −0.00278.
9. **Power is the binding constraint, not cleverness.** Resolving V2.1-D's edge
   over momentum needs ~1,750 non-overlapping weekly cutoffs (~35 years).
   Resolving V2.3-B's −0.00120 against B3 needs ~11,000. Ten years of history
   cannot settle questions of this size — **the effects are absent, not
   under-measured.**

**The strongest thing in the project remains a three-line hand-specified regime
switch with nothing fitted (B3, +0.02836) — the only benchmark whose CI excludes
zero.** Eleven fitted arms have not beaten it.

---

## 6. The boundary of the claim

Stated for the record so the result is not over-read, and explicitly **not** a
research proposal — §9 ends the architecture and this document proposes no V2.4.

What has been refuted is narrow and specific: **that a gradient-boosted learner, on
this 34–35 column feature set, over this universe and this 10-year window, adds
cross-sectional information to 12-1 momentum or to a regime-switched version of
it** — tested through four carrier designs, with the factor in the input, in the
target, around the learner, and as a bounded tilt on a decoupled adjustment.

What has *not* been tested is everything outside that: other data (fundamentals,
flows, holdings, news), other horizons, other universes, longer history, and
non-cross-sectional formulations. Those are untouched, not vindicated. Nothing in
four studies suggests they would fare better, and the power arithmetic in §5.9
applies to any of them that hopes to resolve an effect of this size on this
history.

---

## 7. Where things stand

**Production:** weight 0, HOLD. `alpha/adapter.py` was not modified by V2.3 and
`ladder_v2_3.py` does not import it.

**Exam:** 72 cutoffs sealed, never opened, scored or inspected. Digest
`b55e065f…` unchanged. `out/v2_1_exam_predictions.json` does not exist.

**Superseded documents:** `V2_3_RESEARCH_DESIGN.md` §6 (the 19× power gain) and
§6.2 (the ≈0.0039 resolution probe) are superseded by the measurement — use §3.1
and §3.3 above. Nothing else in the record is retracted.

**Reproduce:**

```bash
cd "Stock-Prediction-Models"
./.venv/Scripts/python.exe -W ignore -m alpha.ladder_v2_3 --quiet   # ~5 min, development only
./.venv/Scripts/python.exe -W ignore -m alpha.v2_1_exam predict     # still refuses: §5.2 gate is closed
```

**Documents, in reading order:**
[`V2_3_LADDER_REPORT.md`](Stock-Prediction-Models/alpha/V2_3_LADDER_REPORT.md) ·
[`V2_3_EXPERIMENT_LOG.md`](Stock-Prediction-Models/alpha/V2_3_EXPERIMENT_LOG.md) ·
[`V2_3_PREREGISTRATION.md`](Stock-Prediction-Models/alpha/V2_3_PREREGISTRATION.md) ·
[`V2_3_RESEARCH_DESIGN.md`](Stock-Prediction-Models/alpha/V2_3_RESEARCH_DESIGN.md) ·
[`PROGRESS.md`](PROGRESS.md)

---

## 8. The verdict on the programme, not just the study

V2.3 is the cleanest failure in the line, and that is a compliment to it. It was
the only study that stated in advance the exact result that would end its own
architecture, produced that exact result, and stopped. The three prior nulls each
left a plausible excuse; this one removed the last of them and then declined to
invent a new one.

The programme's output is not a model. It is a sealed exam, a pre-registration
discipline that held under four consecutive disappointments, 625 tests, and a
short list of things that are now known to be false. **Failure was pre-registered
as a first-class outcome, and this is that outcome, reported as one.**
