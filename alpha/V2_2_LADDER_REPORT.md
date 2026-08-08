# V2.2 — the carrier ladder. Result.

**Run 2026-08-08 on the 316 frozen V2.1 development cutoffs. The 72 exam cutoffs
were not opened. Production stays at weight 0, action HOLD.**

Protocol: [`V2_2_PREREGISTRATION.md`](V2_2_PREREGISTRATION.md), accepted before the
first fit. Record: `out/v2_2_development.json` / `.pkl`. Log:
[`V2_2_EXPERIMENT_LOG.md`](V2_2_EXPERIMENT_LOG.md). Code: `carrier.py`,
`ladder_v2_2.py`. Tests: `app/tests/test_alpha_v2_2.py`.

143,675 rows, 316 development cutoffs, 2016-01-04 to 2026-07-28. Every arm and
rung scored 255 of them — the walk-forward needs 60 training cutoffs before it
predicts anything — except `S1-C`, which scored 210 for the reason in §3. 34
refits each. `S0` needs no fit and scores all 316; **every comparison below is
paired on a common sample**, and where a headline mean appears beside a paired
figure the paired one is the one that means something.

---

## The verdict

**The §6.3 gate closed.** The selected arm, V2.2-B, beat 12-1 momentum with an
interval excluding zero (G2) and did so on 58.8% of cutoffs (G4) — but it did not
beat the hand-specified regime-switching rule (G3, −0.00480, CI [−0.01682,
+0.00534]) and it was below that rule in both chronological halves (G5). Two of
four gates failed, so the gate is closed, and §9.1's outcome applies: V2.2's
contribution is the carrier diagnosis.

**Two of the three arms were disqualified before their IC was read**, by the §6.1
eligibility condition that was written before any V2.2 number existed. They are
the two with the highest mean IC. That is the pre-registration working, and §4
below argues it was right.

| | mean dev IC | Holm p | vs B1 momentum | vs B3 regime rule | eligible? |
|---|---|---|---|---|---|
| **V2.2-A** rank input | **+0.03241** | 0.0015 ✓ | +0.01126 [−0.02162, +0.04822] | +0.00405 [−0.02744, +0.03849] | **no** — G1 −0.02495 |
| **V2.2-B** bounded tilt | +0.02356 | 0.06929 | **+0.00241 [+0.00069, +0.00434]** | −0.00480 [−0.01682, +0.00534] | **yes** — G1 −0.00018 |
| **V2.2-C** monotone | +0.02723 | 0.0072 ✓ | +0.00608 [−0.02491, +0.03949] | −0.00113 [−0.03040, +0.02970] | **no** — G1 −0.00696 |
| B1 — 12-1 momentum | +0.02115 | — | — | — | benchmark |
| B3 — regime-switched rule | **+0.02836** | — | — | — | benchmark |

Holm significance is against a null of **zero IC**, which is the weak question.
Against the benchmarks — the question §0 asks — only one interval in this table
excludes zero, and it belongs to the arm Holm calls insignificant.

---

## 1. The finding that outranks the verdict: the 2×2 grid refutes its own premise

§4.2 expected the +0.02115 → +0.00053 collapse to decompose into an input effect
and a target effect. It does not. **All four cells are near zero.**

| one feature, `ret_12_1` | target = winsorised level | target = within-cutoff rank |
|---|---|---|
| **input = raw level** | **+0.00053** (is V2.1-A) | +0.00225 |
| **input = `z__` rank** | −0.00551 | −0.00381 (is `S1-A`) |

Rank by `z__ret_12_1` with no model, on the same 255 cutoffs: **+0.02115**.

The top-left cell reproduced the frozen V2.1-A figure to five decimals across a
module boundary, so the pipeline is the same pipeline. And then the fix did not
fix it: transforming the input makes it *worse*, transforming the target removes
the sign inversion and adds nothing, and doing both leaves it below zero.

What the grid does explain is the **sign**, and it is the target that owns it —
read as within-cutoff Spearman of the score against its own input:

| | target = level | target = rank |
|---|---|---|
| **input = raw level** | **−0.198** (neg on 87.8%) | +0.029 (neg on 40.4%) |
| **input = `z__` rank** | **−0.251** (neg on 94.9%) | −0.044 (neg on 66.7%) |

A level target makes the map decreasing. A rank target makes it **directionless**
— not increasing. V2.1's report attributed the collapse to a learner that "fit a
predominantly decreasing map". That measurement was right; the interpretation was
the special case. Correcting the sign does not recover the factor, because the
learner never had the factor's ordering to begin with.

### Why — measured, not inferred

Over the 143,673 development rows, the pooled relationship the learner is asked to
fit is this:

* pooled Spearman of `z__ret_12_1` against `target_rank`: **+0.01117**;
* `E[target_rank | z]` across 20 equal-size buckets of `z` spans **0.02304** —
  from about 0.489 at the bottom of momentum to about 0.512 at the top;
* the standard error of a leaf mean at `min_samples_leaf = 100`, with
  `sd(target_rank) = 0.2887`, is **0.02887**.

**The learner's noise floor is wider than the entire signal it is being asked to
resolve.** Its ordering of steps is therefore set by sampling noise, and ranking
by noise scores zero. `S1-A` cut the cross-section into a median of 245 steps and
ordered them at −0.044 against its own input; that is the number a coin produces.

This is not a bug in the carrier. It is a mismatch between a factor whose
cross-sectional signal is ~2% of a rank and a learner whose leaf resolution is ~3%
of a rank. **Any fix that routes the factor *through* the learner meets the same
wall.** Only a fix that carries the factor *around* it survives — which is §2.

---

## 2. The one carrier that preserves the factor is the one that cannot destroy it

§4.1's one-feature sanity test, the test the pre-registration said the whole study
turns on. Each rung against `S0` on the rung's own cutoffs:

| rung | its IC | `S0` on the same cutoffs | paired, G1 (≥ −0.005) | verdict |
|---|---|---|---|---|
| `S1-A` unconstrained, rank target | −0.00381 | +0.02115 (255) | **−0.02495** [−0.05273, +0.00233] | fails |
| `S1-B` residual target + blend | +0.02097 | +0.02115 (255) | **−0.00018** [−0.00050, +0.00012] | **passes** |
| `S1-C` monotone-constrained | +0.00725 | +0.01421 (210) | **−0.00696** [−0.01467, +0.00164] | fails |

`S1-B` retains **99.1%** of the factor, and its loss interval is ±0.0003 — three
orders of magnitude tighter than the other two, because there is almost nothing
stochastic left in the path. It passes for a structural reason, not a lucky one:
`final = z__ret_12_1 + λ·u` carries the factor **arithmetically**, and the model
can only displace a name by at most λ = 0.5 in rank units. §3.2's order bound held
on the real output — **zero violations** at λ = 0.00, 0.25 and 0.50, on arm B's
frozen predictions and on `S1-B`'s.

The lesson, stated plainly because it is the transferable part of this study:
**putting the factor into the learner's input is not enough. It has to be in the
output combination.** V2.2-A is the arm that does the former and only the former,
and its rung lost 98% of the factor exactly as V2.1-A did.

---

## 3. Arm C collapsed, as §3.3 disclosed in advance

§3.3 pre-registered the risk that a monotone-constrained learner facing a pooled
relationship that runs against its constraint does not merely flatten — it
collapses to a constant. That happened, and it is reported as the substantive
finding §3.3 said it would be:

* `S1-C` produced a **constant** prediction on 26 cutoffs and scored only **210**
  of 255 — the other 45 dropped out for having fewer than three distinct values;
* where it did not collapse, it produced a median of **5 distinct values** across a
  cross-section of 426–502 names. A five-step staircase.
* the constraint itself held perfectly: **zero inversions** against `ret_12_1`,
  Spearman +0.799, never negative on any cutoff.

So the constraint delivered exactly what it promised and the delivery cost
two-thirds of the factor. +0.00725 against `S0`'s +0.01421 on the same 210 dates.

**A threshold that was justified against the wrong mechanism, and is not being
moved.** G1's −0.005 allowance was justified in §6.1 as room for "the
discretisation a histogram learner necessarily introduces (≤255 bins produce
ties)". The binding limit turned out not to be `max_bins = 255` but
`max_leaf_nodes = 31` under the constraint, which yields five steps rather than
255. `S1-C`'s honest discretisation loss is −0.00696, which the threshold rejects.
§9 names lowering a threshold as a forbidden response to a result, so the
threshold stands and arm C is carrier-defective on the record. What the number
means is written here instead: **C's carrier is not V2.1-A's pathology, it is a
resolution failure**, and the two are being reported under one label because that
is what the pre-registered rule does.

---

## 4. The eligibility rule discarded the two highest-IC arms, and it was right to

V2.2-A at +0.03241 is the highest development IC any arm in V2, V2.1 or V2.2 has
produced short of V2.1-D's +0.03426. V2.2-C at +0.02723 is third. Both clear Holm
at k = 3 against a null of zero. Both were excluded by a rule fixed before any of
these numbers existed.

The rule was right, and the evidence is in the same table:

* against **12-1 momentum**, A's advantage is +0.01126 with CI [−0.02162,
  +0.04822] and C's is +0.00608 with CI [−0.02491, +0.03949]. Neither excludes
  zero. This is V2.1-D's number and V2.1-D's interval, again.
* against the **regime rule**, A is +0.00405 and C is −0.00113. Neither excludes
  zero.
* the regime profile is V2's, for the third time: A earns **+0.0629** in
  `BEAR_TREND` against +0.0270 in `BULL_TREND`; C earns **+0.0629** against
  +0.0143 in `SIDEWAYS`. §7 requires this to be called what it is — **a warning
  signal, not evidence of robustness** — because V2's development edge lived in
  `BEAR_TREND` and inverted to `SIDEWAYS` on its exam.

An arm that is significantly better than nothing, indistinguishable from momentum,
and concentrated in the bucket that has already betrayed one out-of-sample test is
not a candidate. G1 removed both before their ICs could be argued about, which is
what an eligibility condition is for.

---

## 5. What the 34 columns beyond momentum are actually worth: +0.0024 in IC

Arm B's λ curve is the cleanest measurement this project has produced, because at
λ = 0 the arm **is** momentum and every other point differs from it by the learned
tilt alone.

| λ | V2.2-B, 35 features | `S1-B`, momentum only | order-bound violations |
|---|---|---|---|
| 0.00 | +0.02115 | +0.02115 | 0 |
| 0.25 | +0.02200 | +0.02109 | 0 |
| **0.50 — the arm** | **+0.02356** | +0.02097 | 0 |
| 1.00 | +0.02105 | −0.00169 | 0 |

Read the two columns against each other. With only momentum as input the tilt is
pure noise and gets worse as λ grows, ending at −0.0017 when the learner is given
full authority. With all 35 columns it adds **+0.00241** at λ = 0.5 — and that is
precisely the G2 figure, because B at λ = 0 is Benchmark 1 by construction.

**So: the entire feature set beyond 12-1 momentum — 8 stock-level ranks and 26
market-context columns — is worth +0.0024 of Spearman IC, about one ninth of
momentum's own +0.0212.** Real, with an interval of [+0.00069, +0.00434] that
excludes zero, and far too small to matter.

λ = 0.50 also happens to be the maximum of the curve. It was fixed before the
first fit and would have stayed the arm had it not been; that it is, is luck, and
§3.2 forbids treating it as vindication.

---

## 6. A methodological result worth more than the verdict: bounded arms are ~19× better powered

§6.3 disclosed, from V2.1's frozen record, that the block-bootstrap half-width of
a paired difference against B1 on 255 cutoffs is ≈**0.034**, and stated that G2
would therefore need a point advantage of roughly that size. That estimate was
computed from **unconstrained** arms, and it does not apply to a bounded one:

| arm | vs B1, half-width | within-cutoff ρ against momentum |
|---|---|---|
| V2.2-A | 0.0349 | −0.009 |
| V2.2-C | 0.0322 | +0.089 |
| **V2.2-B** | **0.0018** | **+0.9935** |

B is 99.35% correlated with momentum inside every cutoff, so the paired difference
against momentum is a nearly deterministic quantity and its interval collapses.
**A carrier that constrains an arm to a bounded tilt of its benchmark buys about
19× the resolution against that benchmark** — which is why B's +0.00241 is
significant while A's +0.01126, nearly five times larger, is not.

This bears directly on §8's resolution problem. The ≈0.065 half-width computed for
the 72-cutoff exam was scaled from unconstrained dispersion. For a bounded-tilt
arm measured against its own base, the exam's resolution is far better than that
figure suggests. **This does not open the exam** — §8 and §1.6 are unconditional,
and the gate is closed regardless — but it is the first concrete answer to a
question `V2_2_EXAM_DECISION.md` would have had to confront, and it belongs on the
record now rather than being rediscovered later.

The same constraint shows up in the book: **B replaces 18.6% / 17.3% of its legs
per week against A's 71.0% / 71.4% and C's 70.1% / 70.4%** — a quarter of the
trading. §6.5 predicted B would trade less; it trades four times less. Costs at 5
bps take B's gross quintile spread from +0.00199 to +0.00181, against A's +0.00399
→ +0.00328.

---

## 7. The gate, in full

Selected arm: **V2.2-B**, on highest mean development IC among the eligible arms
(the only eligible arm, as it happens; §6.2's tie-break toward B never had to run).

| gate | threshold | value | verdict |
|---|---|---|---|
| **G2** beats B1 momentum | > 0, 95% CI excludes 0 | +0.00241, CI [+0.00069, +0.00434] | **pass** |
| **G3** beats B3 regime rule | > 0, 95% CI excludes 0 | −0.00480, CI [−0.01682, +0.00534] | **fail** |
| **G4** breadth | > 0 on ≥ 55% of cutoffs, both benchmarks | 58.8% vs B1, 56.9% vs B3 | pass |
| **G5** stability | > 0 in each half, both benchmarks | vs B1 +0.00378 / +0.00103; **vs B3 −0.00929 / −0.00028** | **fail** |

G3 is the gate that matters and the one V2.1 declined to impose. A three-line rule
with nothing fitted — 12-1 momentum in bull and sideways markets, minus 5-day
reversal in bear ones — scores **+0.02836**, and no arm in this study beat it. C
came closest at −0.00113.

For completeness, V2.1's nine criteria run diagnostically on the same development
slice: B fails seven of them, including criterion 1 (mean IC +0.02356 against a
0.03 threshold) and criterion 7 (`BEAR_TREND` −0.026, `LOW_VOL` −0.008). Those
gate nothing here — §6.3's four are V2.2's gate — and they are recorded because an
arm that fails them on development will not pass them on an exam.

B's own interval under the other block lengths, for the §5 sensitivity: block 1
[−0.00523, +0.05263], block 2 [−0.00470, +0.05046], block 4 (the pre-registered
one) [−0.00167, +0.05016], block 8 [−0.00166, +0.04892]. The choice of block is
not load-bearing.

---

## 8. What is now closed, and what V2.2 leaves open

**Closed.**

1. *Was V2's null caused by a broken carrier?* Partly, and less than V2.1's report
   implied. The carrier did invert the factor's sign. Fixing the sign recovers
   nothing, because the learner never resolved the factor's ordering. §1.
2. *Can a rank transform on both sides fix it?* No. All four cells of the 2×2 sit
   within 0.0023 of zero against a factor worth +0.0212. §1.
3. *Can the factor be preserved through a learner at all?* Only by not routing it
   through one. The residual-target-plus-bounded-blend carrier keeps 99.1%; the
   two that pass the factor through the model keep 2% and 34%. §2.
4. *What is the 35-column feature set worth over plain momentum?* **+0.0024 of
   IC**, interval [+0.00069, +0.00434]. Real and negligible. §5.
5. *Does anything in V2/V2.1/V2.2 beat a hand-specified regime rule?* No. Nine
   arms across three studies; the best margin over B3 is V2.1-D's +0.0059 with a
   CI spanning zero, and V2.2's best is −0.00113. §7.

**Open, and not opened here.**

The 72 exam cutoffs. Digest still
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`;
`out/v2_1_exam_predictions.json` does not exist. §8 of the pre-registration keeps
it sealed even on a pass, and the gate did not pass.

**What a V2.3 would have to be, if there is one.** Not a fourth arm on these
features — §5 measures their total worth at +0.0024 and no carrier changes that.
The one thing V2.2 learned that points anywhere is §6: an arm constrained to a
bounded tilt of a known benchmark is an order of magnitude more resolvable than a
free one. That is an argument about *how to measure*, not about what to measure,
and it does not by itself supply a hypothesis worth 316 cutoffs.

---

## 9. Production

Weight **0**, action **HOLD**, unchanged. `alpha/adapter.py` was not modified and
`ladder_v2_2.py` does not import it. Nothing in this report is an input to the
production cascade, and §1.4 fixed that before the study ran.

**Test status (verified 2026-08-08):** `pytest -q --runslow` — **587 passed**, none
skipped (544 as before + 43 V2.2). Per file: 29 `test_alpha.py`, 28
`test_alpha_v2_1.py`, 17 `test_alpha_v2_1_ladder.py`, 43 `test_alpha_v2_2.py`.

```bash
./.venv/Scripts/python.exe -W ignore -m alpha.ladder_v2_2 --quiet   # ~4 min, development only
./.venv/Scripts/python.exe -W ignore -m alpha.v2_1_exam predict     # still refuses: §5.2 gate is closed
```
