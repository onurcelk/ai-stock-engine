# V2.1 ladder — result

**Run 2026-08-08 on the 316 frozen development cutoffs. The exam was not
opened.** Pre-registration: `V2_1_LADDER_PREREGISTRATION.md`, written before the
first fit. Protocol: `V2_1_PREREGISTRATION.md`. Artefacts:
`out/v2_1_development.json`, `out/v2_1_development.pkl`.

---

## The verdict

**The §5.2 gate closed. The 72 frozen exam cutoffs remain sealed and unread.
Production stays at weight 0, action HOLD.**

The best arm, V2.1-D, beat 12-1 momentum by **+0.01312** mean per-cutoff IC over
255 scored development cutoffs, with a 95% block-bootstrap interval of
**[−0.01862, +0.05006]**. The gate required that interval to exclude zero. It
does not, so the exam was not opened — which is outcome 2 of the four listed in
§9 of the pre-registration, and the one it named as more likely.

This is `V2_1_LADDER_PREREGISTRATION.md` §5.2 executing as written, not a
judgement call made after seeing the number. `alpha/v2_1_exam.py predict` reads
the gate verdict out of the frozen development record and refuses to run; that
refusal was exercised and no prediction file exists.

---

## What the four arms did

255 of the 316 development cutoffs were scored — the first 61 fall inside the
60-cutoff training minimum. Every arm saw the same 255 cutoffs, the same
universe and the same outcomes, so the differences between them are differences
in columns and in the training target and in nothing else.

| Arm | Features | Mean IC | 95% block CI | Hit | Spread | Net @5bps | vs 12-1 mom | 95% CI |
|---|---|---|---|---|---|---|---|---|
| V2.1-A | 1 | +0.00053 | [−0.00839, +0.00890] | 48.2% | +0.00025 | −0.00047 | **−0.02061** | [−0.05457, +0.01165] |
| V2.1-B | 27 | +0.01845 | [+0.00199, +0.03787] | 55.3% | +0.00208 | +0.00139 | −0.00269 | [−0.03612, +0.03332] |
| V2.1-C | 35 | +0.03080 | [+0.01114, +0.05490] | 61.2% | +0.00280 | +0.00210 | +0.00965 | [−0.02256, +0.04633] |
| V2.1-D | 35 | **+0.03426** | [+0.01772, +0.05556] | 58.4% | +0.00359 | +0.00287 | +0.01312 | [−0.01862, +0.05006] |

The three benchmarks, on the same 255 cutoffs, none of them fitted:

| Benchmark | Mean IC | 95% block CI | Hit | Gates? |
|---|---|---|---|---|
| B1 — 12-1 momentum, sign +1 | +0.02115 | [−0.00469, +0.04808] | 56.5% | yes |
| B2 — 5-day reversal, sign −1 | +0.00872 | [−0.01268, +0.02808] | 50.6% | yes |
| B3 — regime-switched momentum | **+0.02836** | [+0.00307, +0.05467] | 57.6% | no, reported |

Ladder deltas, paired per cutoff so the day cancels:

| Step | Δ mean IC | 95% block CI | |
|---|---|---|---|
| A → B | +0.01792 | [+0.00106, +0.03878] | excludes zero |
| B → C | +0.01234 | [−0.00814, +0.03390] | null |
| C → D | +0.00347 | [−0.01301, +0.01994] | null |

Holm–Bonferroni over the pre-registered family of four, on criterion-1 bootstrap
p-values: D `p_holm` 0.0036, C 0.0195, B 0.0928, A 0.899.

---

## 1. The finding that outranks the verdict: a learned map destroys the factor

**V2.1-A scored +0.00053. Ranking by `ret_12_1` directly — the same information,
no model — scored +0.02115.** Handing a gradient-boosted tree one feature and
asking it to predict next week's excess return made that feature *worse than
useless*: arm A's mean IC is indistinguishable from zero, its hit rate is 48.2%,
and it loses to its own input by 2.1 IC points.

The mechanism is measured, not surmised. Spearman IC is invariant to monotone
transforms, so a univariate model can only lose signal by being **non-monotone**.
Within each cutoff:

* the number of distinct predicted values equals the number of *runs* when rows
  are sorted by `ret_12_1` — 115 to 219 distinct values across a 426–502 name
  cross-section. Arm A is provably a **step function of `ret_12_1` alone**;
* the within-cutoff Spearman correlation between arm A's prediction and
  `ret_12_1` averages **−0.198** and is **negative on 224 of 255 cutoffs**.

So the learner, minimising squared error on the pooled winsorised level, fit a
predominantly *decreasing* step function of 12-1 momentum — and then applied it
to rank a cross-section, where the level it was optimising is not what is being
measured. §3.1 of the pre-registration said in advance that a material A/B1
divergence would be "a finding about the pipeline and is reported as one". It is
one, and it applies retroactively to V2: **every V2 arm carried its
cross-sectional factors through the same lossy step**, which is a candidate
explanation for why V2's 100-feature models struggled to beat a free factor.

## 2. The A→B delta is a recovery, not an addition

A → B is the only step of the ladder whose interval excludes zero (+0.01792,
[+0.00106, +0.03878]), and reading it as "market context adds information to
momentum" would be wrong.

B ends at **+0.01845**. Raw 12-1 momentum is **+0.02115**. B does not reach its
own benchmark, let alone beat it (−0.00269, CI [−0.03612, +0.03332]). The
context columns bought back most of what the univariate map in arm A threw
away, and stopped there.

The mechanism behaved exactly as §2 of the pre-registration predicted. Arm B is
also provably univariate in `ret_12_1` within a cutoff (43–160 distinct
predictions, runs identical to distinct), but where arm A's map is stuck at a
mean correlation of −0.198 with momentum, arm B's ranges from **−0.99 to +0.99**
across cutoffs — market context *is* being used, and it is being used in the one
way available to it: to decide when to run momentum forwards and when to run it
backwards. The narrow question B was built to ask has an answer:

> **Market context does tell the model when to flip momentum. Doing so does not
> beat simply holding momentum.**

## 3. A free two-line rule is within noise of the 35-feature model

Benchmark 3 — rank by `mom_12_1` outside bear markets, by `−mom_5d` inside them,
nothing fitted, three lines of code — scores **+0.02836** with a CI that
**excludes zero**. Benchmark 1's does not, and neither B's nor C's beats it.

The best learned arm exceeds it by +0.0059 with an interval of [−0.02451,
+0.04076]. Thirty-five columns, 34 refits and a gradient-boosted tree are, on
this evidence, statistically indistinguishable from a hand-specified switch that
encodes the momentum-crash prior directly. B3 gates nothing by pre-registered
design — a hand-specified benchmark should not decide a study — but as a
*measurement* it is the most uncomfortable number in this report.

## 4. The edge is still a regime bet, and it is the same regime as last time

Per-regime mean IC on development, buckets at or above the 8-cutoff gating
minimum:

| Arm | BEAR (27) | BULL (204) | SIDEWAYS (24) | HIGH_VOL (126) | LOW_VOL (129) |
|---|---|---|---|---|---|
| V2.1-B | +0.0064 | +0.0202 | +0.0177 | +0.0276 | +0.0095 |
| V2.1-C | **+0.0756** | +0.0284 | +0.0010 | +0.0423 | +0.0196 |
| V2.1-D | **+0.0658** | +0.0344 | **−0.0025** | +0.0364 | +0.0322 |

C and D earn two to three times their aggregate IC in the 27 bear-market cutoffs
and roughly nothing in the 24 sideways ones — D is negative there, which would
fail criterion 7 outright if this were the exam. This is V2's pathology
reproduced, with the same favourite: V2's development edge also lived in BEAR,
and on V2's exam **the favourite inverted to SIDEWAYS and the model went negative
in bear markets.** A per-regime table that looks like V2's development table is
a warning, not a reassurance, and §6 of the protocol forbids using it as an
explanation for anything.

Chronological halves: D decays from +0.04314 to +0.02532, C is steadier at
+0.03310 → +0.02847. Both stay positive, so criterion 4's new half-sample test
would pass on sign; D's hit rate of 58.4% would fail it on rate.

## 5. Costs

Turnover is high and it was measured, not assumed: the long and short quintiles
each replace about **69–72% of their names every five sessions** (mean total
1.38–1.43 legs per rebalance). At the pre-registered 5 bps one-way that leaves D
at +0.00287 net with a CI excluding zero; at 20 bps it is +0.00072 and the
interval covers zero. C fails the cost gate at every level. A book turning over
70% weekly is where the gap between a backtest and a fill lives, and 5 bps for
S&P 500 names is fair-to-optimistic rather than conservative.

---

## What this study can and cannot settle

The gate's interval on the paired difference has a half-width of ≈0.0343 on 255
cutoffs. For D's observed edge of +0.0131 to clear it, the sample would have to
grow by a factor of about **6.9 — roughly 1,750 non-overlapping weekly cutoffs,
or about 35 years of history.** Ten years of S&P 500 data cannot resolve an edge
of this size over 12-1 momentum, and no rearrangement of the cutoffs changes
that.

That is a statement about the effect size relative to the available history, and
it is the honest boundary of this whole line of work: **the question "does this
model beat momentum" is not answerable at this sample size for an edge this
small.** It is answerable for a large edge, and no arm produced one.

---

## What was *not* done

* **The exam was not opened.** No V2.1 model has been scored on the 72 frozen
  cutoffs. `out/v2_1_exam_predictions.json` does not exist. The exam set's digest
  is unchanged: `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.
* No threshold was lowered, no benchmark swapped, no gate relaxed to "mean > 0",
  no fifth arm added, no hyperparameter searched. Each of those was named in
  advance in §5.2 as a forbidden response to this exact outcome.
* `alpha/adapter.py`, `alpha/develop.py`, `alpha/exam.py`, `PREREGISTRATION.md`
  and `V2_1_PREREGISTRATION.md` are unmodified.
* Production weight 0, action HOLD, unchanged.

---

## Honest next steps

Ordered by what the evidence actually supports, not by what is interesting.

1. **Fix the carrier before adding anything to it.** §1 is a pipeline defect, not
   a market finding: a monotone-preserving path from feature to cross-sectional
   rank (rank-transform the inputs, fit on the within-cutoff rank target, or
   simply blend a factor score rather than replacing it) is a cheap change with
   a measurable effect, and it is testable entirely on development cutoffs. Arm
   D already moves one step in that direction and is the best arm.
2. **Take Benchmark 3 seriously as a candidate, not as a foil.** A rule with two
   states and no fitted parameters produced the only benchmark IC whose interval
   excludes zero. If anything in this program deserves an exam slot, it is a
   pre-registered arm built to beat *that*.
3. **Do not fund the regime-conditional edge.** Twice now the edge has lived in
   the bear bucket on development, and the one time it was tested out of sample
   it inverted.
4. **Do not spend the 72 dates on a marginal arm.** They are worth one clean
   question. The arithmetic above says that question has to be about an effect
   materially larger than +0.013, or it cannot be answered at all.

The exam set stays frozen and unread, and remains available to a future
pre-registered arm.
