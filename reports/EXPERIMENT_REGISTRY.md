# Experiment Registry

**The permanent, append-only record of every experiment this programme runs.**
Opened 2026-08-09 under master roadmap v2 §3.3. Seeded from the frozen V2 → V2.3
record so it begins as a true history rather than an empty form.

**Rules (roadmap §2.7, §26).**

* Every experiment is registered **before the first fit**, with its hypothesis, its
  arm count and its pre-registered resolution and MDE (§2.6) filled in.
* **The number of arms and hypotheses is declared in advance** and the significance
  criterion accounts for them.
* **No failed run is ever silently discarded.** A run that aborted, was superseded, or
  departed from its protocol gets a row saying so.
* Nothing here is edited to match a later belief. Corrections are appended, dated, and
  keep the original wording visible.

---

## 1. Verification stamp — Phase 1 §3.1, executed 2026-08-09

`V2_3_REPRODUCTION_CHECKLIST.md` checks 1–6 re-run at commit `db97386`, branch
`streamlit-app`, interpreter `./venv` (the one that has pytest). **All six pass with
the recorded values.** No re-audit was performed; the 2026-08-08 independent audit
stands.

| # | Check | Expected | Observed | |
|---|---|---|---|---|
| 1 | Exam seal recomputes | `b55e065f…`, 72 cutoffs, 316 development | `b55e065f4c9f9173…`, 72 cutoffs 2017-12-27 .. 2026-06-22, 316 development | **pass** |
| 2 | Exam refuses to open | §5.2 refusal, exit 1; both exam files absent | refusal printed quoting +0.01312 CI [−0.01862, +0.05006]; exit 1; `v2_1_exam_predictions.json` and `v2_1_exam_scores.json` absent | **pass** |
| 3 | Production weight | `0.0`, all seven criteria False | `weight 0.0`, `passed_all False`, all seven False | **pass** |
| 4 | V2.3-B vs B3 re-derived | −0.00120, breadth 0.451, halves −0.00034 / −0.00206 | 255 cutoffs, B3 +0.02836, V2.3-B +0.02716, **−0.00120**, CI [−0.00922, +0.00642], breadth 0.451, halves −0.00034 / −0.00206 | **pass** |
| 5 | Exam contamination | 0 across ten series | `TOTAL EXAM CONTAMINATION: 0`, overlap 0 on all ten | **pass** |
| 6 | Test suite | 625 passed, none skipped | `625 passed in 170.27s`, exit 0 | **pass** |

Check 4's CI endpoints differ from the report's `[−0.00939, +0.00653]` in the fourth
decimal. That is Monte-Carlo spread between bootstrap seeds and is expected; the point
estimate, breadth and both halves match exactly, which is what the check tests.

**No §27D contradiction was found.** One documentation discrepancy — not a contradiction
in frozen evidence — is recorded at §4 below.

---

## 2. Index

Decision codes: **REJECT** · **CONTINUE** · **INCONCLUSIVE**.
"Resolution" is the achieved 95% block-bootstrap half-width of the arm's paired
difference against the named benchmark. "MDE" is the smallest effect the study
pre-committed to being able to see.

| ID | Date | Study | Arm | Primary result | Resolution | Decision |
|---|---|---|---|---|---|---|
| `V2-A` | 2026-08 | V2 | 18 absolute features | IC **+0.00837**, CI [−0.00174, +0.01914] | 0.01901 vs A′ | **REJECT** |
| `V2-B` | 2026-08 | V2 | + 47 relative/percentile | IC **+0.00846**, CI [−0.00402, +0.02102] | 0.01847 vs A′ | **REJECT** |
| `V2-E` | 2026-08 | V2 | + regime/VIX/breadth (exploratory tier) | IC +0.02381, CI [+0.00558, +0.04455] | 0.02194 vs A′ | **REJECT** |
| `V2-F` | 2026-08 | V2 | vol-scaled target (exploratory tier) | IC +0.03179, CI [+0.01402, +0.05073] | 0.02416 vs A′ | **REJECT** |
| `V2.1-A` | 2026-08 | V2.1 | momentum alone (floor) | vs B1 **−0.02061** | 0.03311 vs B1 | **REJECT** |
| `V2.1-B` | 2026-08 | V2.1 | + 26 context columns | vs B1 −0.00269 | 0.03472 vs B1 | **REJECT** |
| `V2.1-C` | 2026-08 | V2.1 | + 8 stock-level columns | vs B1 +0.00965 | 0.03445 vs B1 | **REJECT** |
| `V2.1-D` | 2026-08 | V2.1 | C's features, rank target | vs B1 **+0.01312** — best of family | 0.03434 vs B1 | **REJECT** — gate §5.2 closed |
| `V2.2-A` | 2026-08 | V2.2 | rank-preserving input | vs B1 +0.01126 | 0.03492 vs B1 | **REJECT** — G1 disqualified |
| `V2.2-B` | 2026-08 | V2.2 | bounded tilt, λ=0.50 | vs B1 **+0.00241, CI [+0.00069, +0.00434]** | **0.00183** vs B1 | **INCONCLUSIVE** → refuted by V2.3-A |
| `V2.2-C` | 2026-08 | V2.2 | monotone constraint | vs B1 +0.00608 | 0.03220 vs B1 | **REJECT** — G1 disqualified |
| `V2.3-A` | 2026-08 | V2.3 | B's carrier, momentum deleted from inputs | vs B1 **−0.00052** | 0.00827 vs B1 | **REJECT** |
| `V2.3-B` | 2026-08 | V2.3 | same carrier based on B3 | vs B3 **−0.00120** | 0.00796 vs B3 | **REJECT** |
| `PIT-1` | 2026-08-07 | `validation/` | single-name point-in-time backtest, 9 components | 0 of 9 beat always-up, unanimous sign | 12 cutoffs — see §5 | **REJECT** |

**Architecture verdict:** the V2 → V2.3 line is **CLOSED** and the architecture
**ABANDONED**. Production weight 0, action HOLD. No entry above may be reopened,
re-tested with a larger model, or promoted (roadmap §0.1).

### 2.1 The one number this table exists to make unmissable

Of the **22 arm-versus-benchmark comparisons** in rows `V2.1-A` … `V2.3-B`, exactly
**one** has a confidence interval excluding zero: V2.2-B versus 12-1 momentum,
`+0.00241 [+0.00069, +0.00434]`. And that one was produced by an arm **99.2% collinear
with its own base** — V2.3 then showed the interval was narrow *because the arm barely
differed from momentum*, not because the effect was solid. Removing the collinearity
inverted it to −0.00052.

In every other comparison **the half-width is larger than the point estimate**, usually
by 3–30×. That is roadmap §2.6 stated as a measurement rather than a principle: these
studies were not close to being able to see what they were looking for.

---

## 3. The seeded record — one block per study

Shared across all four studies unless a block says otherwise:

| | |
|---|---|
| Universe | US index members, reconstructed point-in-time (`alpha/membership.py`); median cross-section **465**, min 400, max 502 |
| Panel | `alpha/out/panel.pkl` — 249,029 rows, 100 features, 540 cutoffs, 2016-01-04 .. 2026-07-28; fingerprint `panel_meta.json` |
| Horizon | **5 sessions**; cutoff spacing 5 sessions; embargo 5 sessions — non-overlapping by construction |
| Walk-forward | chronological, purge + embargo, `min_train_cutoffs = 60`, refit every 5 cutoffs (65 refit sessions) |
| Model | `HistGradientBoostingRegressor`, `MODEL_A_PARAMS` — squared_error, max_iter 300, lr 0.05, max_leaf_nodes 31, min_samples_leaf 100, l2 1.0, max_bins 255, early_stopping False, **random_state 0** |
| Intervals | moving-block bootstrap, `BLOCK_LENGTH = 4` cutoffs (`alpha/stats.py`); Newey-West cross-check |
| Training period | expands: first refit 2017-03-21 on 24,825 rows / 60 cutoffs → last refit 2026-05-21 on 140,173 rows / 309 cutoffs |
| **Pre-registered MDE** | **none, in any of the four studies.** Roadmap §2.6 did not exist. This is the defect the whole V3 roadmap is built around |

---

### 3.1 V2 — *does a wider cross-sectional feature set rank the cross-section?*

`alpha/PREREGISTRATION.md` · `alpha/V2_REPORT.md` · `alpha/EXPERIMENT_LOG.md`
Record: `alpha/out/development.json`, `.pkl`.
**484 development cutoffs, 423 evaluated, 221,519 rows.** Target `alpha_5d`; baseline
selected by the pre-registered rule as **Model A′ = `mom_5d`, sign −1**, chosen on
development cutoffs only. Four arms, Holm–Bonferroni across the family.

| Arm | Features | Train target | Mean IC | 95% CI | Hit | vs A′ | Half-width | Gate 1–5 |
|---|---|---|---|---|---|---|---|---|
| V2-A | 18 absolute | `target_train` | +0.00837 | [−0.00174, +0.01914] | 50.8% | −0.00278 | 0.01901 | **fail** |
| V2-B | 65 (+ relative, percentile) | `target_train` | +0.00846 | [−0.00402, +0.02102] | 51.3% | −0.00268 | 0.01847 | **fail** |
| V2-E | 100 (+ context) | `target_train` | +0.02381 | [+0.00558, +0.04455] | 53.4% | +0.01267 | 0.02194 | not gated |
| V2-F | 100, vol-scaled | `target_vol_scaled` | +0.03179 | [+0.01402, +0.05073] | 57.0% | +0.02064 | 0.02416 | not gated |

**Result.** Adding 47 relative and percentile features moved mean IC from +0.00837 to
+0.00846 — **+0.00009**, on a well-powered null over 423 cutoffs. The pre-registered
gate covered **V2-A and V2-B only**; both failed criteria 1–5, so the gate stayed shut.
V2-E and V2-F were **additional feature tiers explored in the same run**, not gated
arms; V2-F cleared criteria 1–3 and Holm at p = 0.0032. Widening the gate to "any arm"
would have opened it, and the pre-registration's refusal to do that is the single
decision that kept the programme honest.

V2-F was nonetheless taken to V2's own **12-date exam** and failed there too, and did
not beat a one-line factor (criterion 5). The V2 report records its own weakness: the
gate was measured against `mom_5d`, and against 12-1 momentum V2-F would have failed by
more. That is why V2.1 rebuilt the benchmark hierarchy.

**Decision: REJECT** all four. **Reason:** the information failed, not the model — a
five-fold increase in feature count bought +0.00009 IC.

**Superseded run, retained deliberately:** `alpha/out/run1_dead_ret_12_1/` — a V2 run
made with a dead `ret_12_1` column. Its `development.json` is committed so the effect of
the fix stays checkable (it moved V2-F from +0.0295 to +0.0318 and flipped criteria 1–3).
Its `.pkl` is excluded; SHA-256 in `V2_3_EVIDENCE_MANIFEST.md` §4.

---

### 3.2 V2.1 — *rebuilt on frozen cutoffs against 12-1 momentum. Does any arm beat it?*

`alpha/V2_1_PREREGISTRATION.md` · `alpha/V2_1_LADDER_PREREGISTRATION.md` ·
`alpha/V2_1_VALIDATION_SETUP.md` · `alpha/V2_1_LADDER_REPORT.md`.
Record: `alpha/out/v2_1_development.json`, `.pkl`, `v2_1_exam_set.json`.
**316 development cutoffs (255 evaluated), 143,675 rows.** Family size 4, declared in
advance. **72 cutoffs frozen and sealed before the first fit**, digest
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.

| Arm | Features | Train target | Mean IC | 95% CI | vs B1 | hw | vs B3 | hw |
|---|---|---|---|---|---|---|---|---|
| V2.1-A | 1 | `target_train` | +0.00053 | [−0.00839, +0.00890] | −0.02061 | 0.03311 | −0.02783 | 0.03206 |
| V2.1-B | 27 | `target_train` | +0.01845 | [+0.00199, +0.03787] | −0.00269 | 0.03472 | −0.00991 | 0.03325 |
| V2.1-C | 35 | `target_train` | +0.03080 | [+0.01114, +0.05490] | +0.00965 | 0.03445 | +0.00243 | 0.03402 |
| **V2.1-D** | 35 | `target_rank` | **+0.03426** | [+0.01772, +0.05556] | **+0.01312** | 0.03434 | +0.00590 | 0.03263 |

**Result.** The best arm, V2.1-D, beat 12-1 momentum by +0.01312 with a CI of
[−0.01862, +0.05006] — **spanning zero**. The §5.2 exam gate required the interval to
exclude zero. **It closed, and the 72-cutoff exam was sealed unopened.** It is still
sealed; check 2 above re-verified the refusal is enforced in code.

Two findings that outlived the study:

* **V2.1-A scored +0.00053 while ranking on `ret_12_1` directly scores far higher.** Arm
  A is provably a step function of `ret_12_1` alone, so the learner was destroying the
  factor's ordering, not adding to it. This is the observation the whole V2.2 carrier
  programme was built on.
* Every arm's edge concentrated in `BEAR_TREND` (V2.1-C +0.0756, V2.1-D +0.0658 on 27
  cutoffs) — recorded then as a caveat. Under roadmap §2.5 it is now a **disqualifier**.

**Decision: REJECT** all four. **Reason:** power. Half-widths of ~0.034 against effects
of ~0.013; resolving V2.1-D's edge would need ~1,750 cutoffs (~35 years).

---

### 3.3 V2.2 — *does routing the factor around the learner preserve it?*

`alpha/V2_2_PREREGISTRATION.md` · `alpha/V2_2_LADDER_REPORT.md`.
Record: `alpha/out/v2_2_development.json`, `.pkl`. **Family size 3**, declared in
advance; §6.1 eligibility rule (G1 carrier integrity) applied **before any IC was read**.

| Arm | Carrier | Mean IC | vs B1 | hw | vs B3 | hw | Eligible |
|---|---|---|---|---|---|---|---|
| V2.2-A | rank-preserving input | +0.03241 | +0.01126 | 0.03492 | +0.00405 | 0.03297 | **no** — G1 −0.02495 |
| **V2.2-B** | bounded tilt, `z__ret_12_1 + 0.50·u` | +0.02356 | **+0.00241 [+0.00069, +0.00434]** | **0.00183** | −0.00480 | 0.01108 | **yes** — G1 −0.00018 |
| V2.2-C | monotone constraint | +0.02723 | +0.00608 | 0.03220 | −0.00113 | 0.03005 | **no** — G1 −0.00696 |

**Result.** The §6.3 gate opened: V2.2-B beat 12-1 momentum with an interval excluding
zero — the only such interval the programme ever produced. It was **+0.00241**: real and
negligible. Against B3 it was **−0.00480**. Answers recorded at the time: a rank
transform on both sides does not fix the carrier (all four 2×2 cells within 0.0023 of
zero against a factor worth +0.0212); the factor survives only by **not being routed
through the learner** (the bounded carrier keeps 99.1%, the two that pass it through the
model keep 2% and 34%).

**The methodological claim that turned out to be the trap.** §6 of the V2.2 report
banked bounded arms as **~19× better powered** and treated it as a free methodological
win. It was collinearity: ρ(V2.2-B, base) = **0.9935**. Roadmap §2.12 now reads this the
other way round — *resolution and authority are the same dial*, and a power gain that
arrives for free is evidence the arm is doing nothing.

**Decision: A and C REJECT** (disqualified by the pre-registered eligibility rule before
their IC was read — the rule discarded the two highest-IC arms and was right to).
**B INCONCLUSIVE at the time; refuted by V2.3-A.**

---

### 3.4 V2.3 — *with the collinearity removed, does a bounded tilt add anything?*

`alpha/V2_3_PREREGISTRATION.md` (§9 abandonment criteria, fixed before the first fit) ·
`alpha/V2_3_RESEARCH_DESIGN.md` · `alpha/V2_3_LADDER_REPORT.md`.
Record: `alpha/out/v2_3_development.json` (`f082de28…`), `.pkl` (`62d1af61…`).
**Family size 2**, λ = 0.50, 34 inputs (the base is never an input, asserted structurally
per arm and per rung).

| Arm | Base | Mean IC | vs B1 | hw | vs B3 | hw | ρ̄(u, base) | Authority |
|---|---|---|---|---|---|---|---|---|
| V2.3-A | 12-1 momentum | +0.02063 | **−0.00052** | 0.00827 | −0.00773 | 0.01324 | 0.6981 | 0.3580 |
| V2.3-B | B3 regime rule | +0.02716 | +0.00602 | 0.01496 | **−0.00120** | 0.00796 | 0.7033 | — |

**Result. Null, and backwards. All five gates failed for both arms.** V2.2-B's +0.00241
was not a diluted signal awaiting authority: with the collinearity removed and real
authority raised **5.8×**, it inverted to −0.00052. The bounded adjustment **subtracts**
from the hand-coded regime rule. The best advantage available anywhere on either λ curve
is **+0.00045** against a measured resolution of **0.00827** — below the study's ability
to see. Both arms passed every eligibility check the design could impose: **the
architecture failed on its hypotheses, not its plumbing.**

Costs (G6, the gate V2.2 lacked) failed for both: net advantage **+0.00028** and
**+0.00002**, intervals spanning zero, turnover up 36–56%. No tilt pays for its own
trading.

**Abandonment.** §9 criterion 6 is met in its exact pre-registered form (ρ̄ ≤ 0.90
achieved, still no advantage over base) and **alone ends the architecture**; criteria 4
and 5 are met jointly and independently. **Criterion 2 is not relied upon** — its
operative clause is satisfied and its point estimate negative, but its precision premise
(≈0.004 half-width) was not reached; 0.00796 was achieved. Clarified 2026-08-08 after
the independent audit. **Cite criterion 6.**

**Protocol departure, recorded not hidden.** The §4 noise control specified **one**
seeded draw on **unpaired** means, with any gain ending the study. The seed landed ~2σ
high and produced a +0.00123 "gain" on pure noise; **the first ladder run aborted on
it.** The study departed from its own protocol to re-run the control paired, over 30
draws: the blend then **destroys** IC (−0.00202 / −0.00278; 3% / 0% of draws above base).
The single-draw spread (0.00137) was comparable to the effect the control was meant to
detect. Roadmap §2.11 generalises this: *a control that can fire on noise is not a
control.*

**Decision: REJECT both. Architecture ABANDONED.** No V2.4 (roadmap §0.1).

---

### 3.5 `PIT-1` — the single-name point-in-time backtest (separate study)

`validation/README.md` · `validation/REPORT.md`. Harness `validation/`; raw output
`validation/out/`. **Run 2026-08-07.** This is a **different study with a different
question, a different object and a different baseline** from V2 → V2.3, and its results
are **not merged into that record** (roadmap §3.2).

| | |
|---|---|
| Question | if this system had been running on a date in the past, how good would its predictions have turned out to be? |
| Design | 30 symbols × 12 historical cutoffs; **360 frozen predictions** + 96 neural-forecast experiments; 20,999 scored rows |
| Leakage control | one data door (`pit.fetcher`), two processes (`predict.py` never reads its output; `score.py` never writes), and `test_future_cannot_change_the_verdict` |
| Baselines | always-predict-up, no-change, buy-and-hold, trend continuation, 50-bar MA, golden cross, a coin flip |
| Intervals | clustered by cutoff date |
| **Effective n** | **12** — twelve effectively independent market draws. No number of extra symbols relaxes this |

**Result: 0 of 9 components beat always-predicting-up on its own horizon, unanimous
sign.** Consensus 53.7% directional (p = 0.54); best rule agent 56.9% (p = 0.077); LSTM
59.4% but 72% bullish against a 64.6% up-rate. Price targets and the LSTM path lose to
"price won't move" (MAPE 5.59% vs 5.59%; 11.5% vs 3.8%). The 4-hour horizon is
**inverted** when read after the close — 20.8% on acted calls, p = 0.009 — scoped to
after-close reads because every scored window straddles an overnight gap.

**The result that does not depend on sample size:** the neural forecast changed **zero**
verdicts. The significance gate fired **257 of 257** horizon-slots across 96 experiments.
That is a count, not an estimate — adding it is provably a no-op, not a weak effect.

**Vindicated, and now protected:** the HOLD floor and the significance gates. The system
abstained on **74.3%** of symbol-dates, and on the calls it did make its edge over a
trivial rule was zero — so the abstention was the correct output.
**`MIN_T`, `MIN_CONFIDENCE` and `FAMILY_CAP` in `app/core/ultimate.py` are not to be
loosened on the strength of a fit** (roadmap §3.2, §18).

**Decision: REJECT** the V1 per-stock engine as a source of predictive value.
**Reason:** the information failed *and* the study is resolution-bound at 12 cutoffs.
Every interval is wide enough to contain both no skill and modest skill; the honest
reading is *not proven to work*, which is not the same as *proven not to work* — except
the 4-hour after-close case, where the interval sits below 50%.

**Preservation:** decided 2026-08-09, see `reports/VALIDATION_EVIDENCE_MANIFEST.md`.

---

## 4. A documentation discrepancy, recorded rather than resolved by choice

The programme record states **"eleven fitted arms"**
(`PROGRAMME_STATUS_V2_3.md` §1 and §3, `V2_3_POST_MORTEM.md` §1,
`V2_3_LADDER_REPORT.md` §9). The frozen artefacts contain **thirteen** named fitted
arms: V2 four, V2.1 four, V2.2 three, V2.3 two.

The reading that reconciles it: V2's pre-registered **gate covers V2-A and V2-B only**
(`development.json` → `gate_criteria_1_to_5` contains exactly those two keys), so V2
contributes **two** gated arms and V2-E / V2-F are additional feature tiers from the
same run. 2 + 4 + 3 + 2 = **11**. The same convention gives **nine** at V2.2 time
(2 + 4 + 3), which is what `V2_2_LADDER_REPORT.md` §"closed questions" 5 says.

**This registry lists all thirteen**, because §2.7 forbids silently dropping a run and
V2-E / V2-F were genuinely fitted and genuinely scored. The two counts are consistent
once the convention is stated; it simply was never stated.

**This is not a §27D contradiction.** No frozen artefact disagrees with another, no
result changes, and nothing in the closure decision depends on the count. It is
recorded here so the next reader does not have to re-derive it, and **no prose in the
frozen reports was edited** to make the number agree.

---

## 5. How to add a V3 entry

Copy the block below into §6 **before the first fit**, and do not fill in `Result` or
`Decision` until the run is complete. An entry whose `Resolution / MDE` line is empty is
a **blocked study** — roadmap §2.6 forbids running it.

```
### V3-<n> — <one-line hypothesis>

| Field | |
|---|---|
| ID / date | |
| Hypothesis | stated as something that can fail |
| Information source | + admissibility check against §2.10 clauses 1-4 |
| Target / horizon | + why, per TARGET_DESIGN.md |
| Universe | |
| Features | exact construction, timestamp semantics |
| Model / hyperparameters / seeds | |
| Training / validation / test periods | |
| Baselines | B3 AND 12-1 momentum AND, if single-name, always-up and no-change |
| Arms declared | count, fixed before the first fit |
| **Resolution / MDE (§2.6)** | smallest effect worth acting on; achievable half-width; **verdict: runnable / NOT runnable** |
| Primary metric | fixed in writing before any result is inspected |
| Secondary metrics | |
| Result | point estimate **with its achieved half-width** |
| Stability | halves, yearly, regime — concentration disqualifies (§2.5) |
| Net of costs | the primary economic metric, from the first measurement |
| Decision | CONTINUE / REJECT / INCONCLUSIVE |
| Reason | did the *information* fail, or the target, PIT quality, sample size, economics, or **power**? |
| Family slot | which of the three §21 slots this spends |
| Commit / artefact hashes | |
```

---

## 6. V3 experiments

**Family budget (§21): 3 slots. Spent: 0. Remaining: 3.** Families frozen in
`INFORMATION_AUDIT.md` §5: (1) EDGAR fundamentals + filing-timestamped drift,
(2) Form 4 insider transactions, (3) 13F holdings, reserve.

### 6.1 Pre-study §2.6 power gate — Family 1, computed 2026-08-09 (roadmap §29 step 4)

Computed **before any implementation**, as §29 step 4 requires. This is the go/no-go
arithmetic; the full preregistration (`alpha/V3_PREREGISTRATION.md`) still fixes exact
thresholds, arms and multiplicity before the first fit, and repeats this gate with the
design's actual cutoff count.

**Step 1 — smallest effect worth acting on, derived from the cost model, not from hope.**
From the frozen record: the per-cutoff top-bottom spread runs at **≈ 0.10 × IC**
(measured 0.091–0.105 across V2.1-C/D, V2.3-A/B), and the cost drag of running a fitted
tilt at the record's turnover was **0.0002–0.0007 per week** (same arms, at the
pre-registered 5 bps). For the *net-of-cost* advantage over B3 to be economically
meaningful — taken here as **≥ +0.0004/week on the spread portfolio (~2%/year)** after
paying its own added turnover (~0.0003/week) — the gross spread advantage must be
≥ ~0.0007/week, i.e. an IC advantage over B3 of

> **MDE ≈ +0.007 IC — the smallest effect worth acting on.**

**Step 2 — half-width the planned design achieves.** Phase 5 information-only tests fit
no learner, so no training warm-up is needed: **255–316 usable development cutoffs**
(316 if filings coverage holds to 2016; the record's 255 if it does not). Using the
record's measured calibration (0.00827 at 255 paired cutoffs, √-scaled; the same
moving-block machinery in `alpha/stats.py` will produce the exact number in the
preregistration):

> **Achievable half-width ≈ 0.0074–0.0083 IC** for the paired bounded-combination
> contrast against B3 — the decisive test-7 design.
> A *standalone* new factor paired against B3 (low correlation) resolves only ~0.03; the
> family's decisive claim must therefore be formulated as **the increment of adding the
> information to the incumbent**, which is the design the record already calibrates.

**Step 3 — verdict.**

| | |
|---|---|
| MDE (economic floor) | +0.007 IC vs B3 |
| Achievable half-width | 0.0074–0.0083 IC |
| MDE vs half-width | **at the margin — a true effect of exactly 0.007 is not reliably distinguishable from zero** |
| **Gate verdict** | **RUNNABLE, conditionally:** the preregistration must hypothesize an effect **≥ +0.010 IC vs B3** — comfortably above both the economic floor and the resolution — or the study may not run. Literature priors for filing-timestamped drift (rank IC ~0.01–0.03 at discovery, decayed since) plausibly support 0.010; they do not support treating 0.007 as the target |
| Recorded | here, and to be restated verbatim in `alpha/V3_PREREGISTRATION.md` before the first fit |

For scale: the hypothesized 0.010 is **~7–20× what the entire V2 feature set was worth**
(+0.0005–0.0014). That is what §2.6 demands, and it is a falsifiable bet — if Family 1's
information is worth what V2's was, the study will return a clean, well-resolved null
and the slot is spent honestly.

### 6.2 Registered V3 studies

#### V3-1 — Family 1: point-in-time reported fundamentals (time-series SUE)

| Field | |
|---|---|
| ID / date | `V3-1` · 2026-08-09 |
| Hypothesis | PIT reported earnings, timestamped at EDGAR acceptance, contain incremental cross-sectional information over 12-1 momentum **and over B3**, of a size this history can resolve |
| Information source | SEC EDGAR XBRL `companyfacts` joined to `submissions` acceptance times. §2.10: clause 1 **pass**, clause 2 **pass** (87 facts without a timestamp dropped, not approximated), clause 3 **pass** (ρ̄ 0.2533 vs momentum, threshold 0.30, fixed before measurement), clause 4 **pass conditionally** |
| Target / horizon | Target A, `alpha_5d`, **5 sessions** — the single primary horizon, fixed on priors |
| Universe | PIT index membership, median cross-section 465; SUE coverage **0.930** |
| Features | `sue` — seasonal difference of `NetIncomeLoss` vs the year-ago quarter, scaled by the sd of the last 8 surprises (min 4); Q4 derived; winsorised 1%/99% per cutoff. `staleness_days` diagnostic only, never an input |
| Model / seeds | **none — information-only test** (§2.9). Noise control seed 20260809 |
| Periods | 316 development cutoffs, 2016-01-04 … 2026-07-28. **Exam contamination 0**, asserted in code |
| Baselines | B3 (incumbent), B1 12-1 momentum, B2 reversal, and the raw factor alone |
| Arms declared | **2**, before the first fit. λ = 0.25 fixed, not scanned as an arm |
| **Resolution / MDE (§2.6)** | MDE +0.007 (economic floor); hypothesized ≥ +0.010; **achieved half-width 0.00229** — 3× better than the 0.0074 predicted, itself the §2.12 collinearity warning |
| Primary metric | paired per-cutoff IC difference, Arm 1 − B3 |
| **Result** | **+0.00090, CI [−0.00140, +0.00317], half-width 0.00229, breadth 0.5032, n 316.** Coverage-matched: +0.00124. λ curve maximum anywhere: **+0.00127** |
| Secondary | **Arm 0 raw SUE: IC +0.01305, CI [+0.00263, +0.02339] — excludes zero**, hit 0.576, halves both positive, turnover 0.091. But vs B3 **−0.00937**, and spread +0.00051 CI [−0.00081, +0.00158] |
| Stability | halves −0.00005 / +0.00185 (**not both positive**); vs-B1 advantage **+0.11317 in BEAR** against +0.00075 BULL — disqualifying concentration (§2.5) |
| Net of costs | Arm 1 **−0.000065**, Arm 0 −0.001461. Both negative; turnover *fell* |
| Noise control | **PASS** — 30 paired draws, median −0.00045, sd 0.00096, 0.0% above threshold |
| Multiplicity | Holm across 2 arms: p_holm 0.678 both |
| **Decision** | **REJECT** — all four CONTINUE criteria failed |
| Reason | **The information failed**, not the power, the PIT quality or the implementation. SUE is a genuine standalone factor but is **not incremental to a regime-switched momentum rule** and does not rank the tradeable tails |
| Family slot | **Slot 1 of 3 — SPENT.** No Family 1′; not re-tested with a learner, feature or horizon (§2.9, §21) |
| Artefacts | `alpha/out/v3_family1_development.json` / `.pkl`, `v3_family1_ceiling.json`, `alpha/V3_FAMILY1_REPORT.md`, prereg at `5a8b92e` |

**Family budget after V3-1: 3 slots, 1 spent, 2 remaining.**

### 6.3 Family 2 (Form 4) — §2.6 power gate computed 2026-08-09. **PASS. Slot 2 UNSPENT.**

Gate-only. **Family 2 is not implemented and not run; no slot was spent; no
pre-registered criterion, threshold, abandonment rule or budget was modified.** Full
record: `reports/FAMILY2_POWER_GATE.md`.

| §2.6 step | Value |
|---|---|
| 1 — smallest effect worth acting on | **+0.007 IC vs B3**, carried unchanged from §6.1 |
| 2 — achievable half-width, 316 cutoffs, Form 4 universe, paired vs B3 | **0.00205** (90d availability; 0.00388 at 30d, 0.00185 at 180d) |
| 3 — half-width exceeds effect sought? | **No** → **PASS** |

Universe measured from the filing **index only** (912,564 Form 4 filings, 614 of 619
issuers; 65.5% accepted after the 16:00 ET close). Availability is 0.959 of the
cross-section at a 90-day lookback — not the binding constraint. No Form 4 XML was
parsed and no transaction content was read.

**Two findings that constrain any future Family 2 preregistration:**

* **The design must be the bounded combination against B3.** A **standalone-factor**
  formulation resolves only **0.01949** — Family 1's measured Arm 0 half-width on the
  same cutoffs — which **exceeds the +0.007 MDE by 2.8× and therefore FAILS §2.6.**
* **The §2.12 "free power gain" warning was checked and does not apply.** An oracle tilt
  (perfect foresight) through the same arm attains **+0.21230** over B3 at λ = 0.25, so
  the design has ~30× headroom and the narrow half-width is genuine power, not
  collinearity. A real feature would need to be 3.3% as good as perfect foresight to
  clear the floor. *This also retroactively confirms Family 1's +0.00090 was an
  information null, not an arm that could not express an effect.*

**Still outstanding before Family 2 could run:** §2.10 clause-3 admissibility (not
evaluated here), the feature construction and lookback window, its turnover — and
explicit authorization. **A passed power gate authorizes nothing.**

---

## 7. Backfill — completed studies registered after the fact, 2026-08-10

**Nothing above this line is edited.** §6 stops at the Family 2 power gate because the
registry was not updated when Families 2 and 3 ran on 2026-08-09 or when V4-SUE ran on
2026-08-10. The three entries below are **appended now**, on 2026-08-10, from the frozen
result artefacts named in each block.

**This is a record-keeping defect and is recorded as one.** Roadmap §2.7 requires an
experiment to be registered *before the first fit*; these three were registered in their
own pre-registration documents before their first fits — `alpha/V3_FAMILY2_PREREGISTRATION.md`
(`bd0c7aa`), `alpha/V3_FAMILY3_PREREGISTRATION.md` (`5cb409f`), `alpha/V4_SUE_PREREGISTRATION.md`
(`5718f83`), each committed before the code that implemented it — but the **index entry**
here was not made at the time. The git history, not this file, is what establishes the
temporal ordering, and it does establish it.

**No number below is new.** Every value is transcribed from a committed artefact and
was verified against it (§7.5). No result, threshold, criterion, decision or budget is
altered by this backfill.

### 7.1 V3-2 — Family 2: Form 4 insider open-market purchases

| Field | |
|---|---|
| ID / date | `V3-2` · run 2026-08-09 · **registered 2026-08-10 (backfill)** |
| Hypothesis | Insider open-market purchases, as a market-cap-normalised 90-day purchase intensity timestamped at EDGAR acceptance, contain incremental cross-sectional information over B3 at 5 sessions of **≥ +0.010 IC** |
| Information source | SEC EDGAR Form 4. §2.10: clause 1 **pass**, clause 2 **pass** (0 filings admitted without an acceptance timestamp), clause 3 **pass** (mean ρ **−0.1310** vs `z__ret_12_1`, ceiling 0.30, fixed before measurement), clause 4 **pass**. Records: `reports/FAMILY2_ELIGIBILITY.md`, `reports/FAMILY2_ADMISSIBILITY.md`, `reports/FAMILY2_POWER_GATE.md` |
| Target / horizon | `alpha_5d`, **5 sessions** (§10.1), unchanged from V3-1 |
| Universe | PIT index membership, 143,675 rows. **19,347 open-market purchases, 561 of 619 issuers**, 42 quarterly archives |
| Features | scale-normalised 90-day open-market purchase intensity. **No winsorisation** — §2 fixes none, unlike Family 1's 1/99. Feature **defined 0.9952**, but **non-zero only 0.1351**, median **62 names** per cutoff — the 13.6% figure the §21 diagnosis quotes as this family's effective coverage |
| Model / seeds | **none — information-only test** (§2.9) |
| Periods | **316 development cutoffs**, exam contamination **0**, digest `b55e065f4c9f9173` |
| Baselines | B3 (incumbent) +0.02241, B1 12-1 momentum +0.01000, B2 reversal +0.00675, and the raw factor alone |
| Arms declared | **2**, before the first fit. λ = **0.25** fixed, not scanned. Sign **+1**, economic prior, not estimated |
| **Resolution / MDE (§2.6)** | MDE **+0.007** (economic floor); hypothesized ≥ +0.010; **achieved half-width 0.00092** — the tightest interval the programme has produced, and **predicted in advance as a warning, not an achievement** (§2.12) |
| Primary metric | paired per-cutoff IC difference, Arm 1 − B3 |
| **Result** | **−0.00096, CI [−0.00187, −0.00004], half-width 0.00092, breadth 0.4177, n = 316** |
| Secondary | **Arm 0 raw insider rank: IC −0.00547, CI [−0.01278, +0.00151], hit 0.478** — spans zero, so *no signal*, **not** an inverted signal. Arm 1 IC +0.02146 |
| Stability | halves **−0.00094 / −0.00097** (neither positive); ex-bear **−0.00115** |
| Net of costs | gross spread advantage **−0.00006**, **net −0.000058**, on +0.3 pp extra turnover. The **sixth** consecutive tilt that does not pay for its own trading |
| Noise control | **PASS** — 30 paired within-cutoff draws, median −0.00046, sd 0.00046, **0.0%** above threshold |
| Multiplicity | Holm across 2 arms: **p_holm 0.0752 both — neither significant** |
| **Decision** | **REJECT.** Criteria 1, 3, 4 **FAIL**. Criterion 2 recorded **"PASS" mechanically in the wrong direction** — the interval excludes zero *entirely below* it. **Reported exactly as written and NOT amended** (§3.1 of the report). The honest count is **four failures, one disguised** |
| Reason | **The information failed, and at the root** — unlike Family 1 it never cleared zero standalone. Not the power (0.00092), not the PIT door (77.3% of Form 4s would have leaked under `filed <= cutoff`; that rule was never used), not the coverage in the sense that mattered |
| Structural finding | **The feature cannot form a short book.** 86% of names tied at zero; under the pre-registered average-tie rule the lowest percentile rank any name receives is a median **0.4308**. **No name reaches the bottom quintile at any of the 316 cutoffs**, so Arm 0's long-short spread is **undefined everywhere, n = 0 of 316** |
| Correction to a pre-commitment | §10.3 pre-committed effective n = 312; that holds for **Arm 0's own IC** but the primary contrast ran at **n = 316** (an all-zero cutoff collapses Arm 1 to B3, giving an exact zero that is retained). Rescaling to 312 moves the primary −0.00096 → −0.00097. **No criterion changes** |
| Family slot | **Slot 2 of 3 — SPENT.** No Family 2′: not with sales, role weighting, another window, another horizon, **and not with the sign flipped** (§2.9, §21) |
| Commit / artefacts | prereg `bd0c7aa`, account-holder rulings `65c0039`, result `baabc01`. `alpha/out/v3_family2_development.json` / `.pkl`, `alpha/V3_FAMILY2_REPORT.md` |

**Family budget after V3-2: 3 slots, 2 spent, 1 remaining.**

### 7.2 V3-3 — Family 3: 13F institutional holdings change

| Field | |
|---|---|
| ID / date | `V3-3` · run 2026-08-09 · **registered 2026-08-10 (backfill)** |
| Hypothesis | Quarter-on-quarter change in institutional holdings, from 13F filings, contains incremental cross-sectional information over B3 at 5 sessions of **≥ +0.010 IC** |
| Information source | SEC 13F bulk archives — **45 archives, 20,687,226 event rows, 11,661 distinct filers**, 573 of 619 issuers mapped (**map rate 0.926**). §2.10: clause 1 **pass**, clause 2 **pass**, clause 3 **pass by the widest margin of the three families**, clause 4 **pass** |
| Point-in-time door | **`FILING_DATE < cutoff` — stricter than acceptance time.** The bulk sets carry no acceptance timestamp and §2.1 forbids approximating one, so the rule can only ever *delay* information: **it cannot leak.** Measured staleness of Q1 at the cutoff: **median 92 days, p90 128** |
| Mapping integrity | 13F carries **no issuer CIK**, so a CUSIP bridge was required. It **failed validation three times** before passing — stripped leading zeros, CUSIP-keyed collisions that put Meta on JPMorgan's CUSIP, and a left-justified CUSIP caught only by the **modulus-10 check digit**. Final validation **14 hand-checked mega-caps, 14 correct, 0 wrong, 0 absent**; the build **refuses to emit a feature** if that check fails |
| Target / horizon | `alpha_5d`, **5 sessions** |
| Universe | PIT index membership. Coverage **0.8556** defined (20,750 NaN, **never filled**, §5); per cutoff mean 0.8534, min 0.8014; names per cutoff median **394**, min 323 |
| Features | quarter-on-quarter holdings change, continuous, **no tie block** — unlike Family 2 |
| Model / seeds | **none — information-only test** (§2.9) |
| Periods | **316 development cutoffs**, exam contamination **0**, digest `b55e065f4c9f9173` |
| Baselines | B3 +0.02241, B1 +0.01000, B2 +0.00675, and the raw factor alone |
| Arms declared | **2**, before the first fit. λ = **0.25** fixed. Sign **+1**, economic prior |
| §2.10 clause 3 | vs `z__ret_12_1`: mean \|ρ\| **0.0726** against a 0.30 ceiling; highest against any of the 34 inputs **0.0780** against a 0.50 ceiling. **Nothing reaches a sixth of its ceiling** — genuinely orthogonal information |
| **Resolution / MDE (§2.6)** | MDE **+0.007**; gate calibrated 0.00352 (coverage 0.80) to 0.00158 (1.00); **achieved half-width 0.00279** |
| Primary metric | paired per-cutoff IC difference, Arm 1 − B3 |
| **Result** | **−0.00339, CI [−0.00631, −0.00073], half-width 0.00279, breadth 0.4494, n = 316** |
| Secondary | **Arm 0 raw holdings rank: IC −0.00659, CI [−0.01465, +0.00051], hit 0.475** — spans zero, so *no signal*, not an inverted one. Long-short spread −0.00064, CI [−0.00141, +0.00014]. Arm 1 IC +0.01903 |
| Stability | halves **−0.00253 / −0.00424**; regimes BULL −0.00417, BEAR −0.00031, SIDEWAYS −0.00059, **EX-BEAR −0.00377**. **Negative everywhere — no regime rescues it, and none was sought** |
| Net of costs | gross spread advantage −0.00015, **net −0.000148**, on +0.3 pp extra turnover. The **seventh** consecutive tilt that does not pay for its own trading |
| Noise control | **PASS** — 30 paired draws, median −0.00142, sd 0.00118, **0.0%** above threshold |
| Multiplicity | Holm: Arm 0 p_raw 0.0136 → p_holm 0.0272; Arm 1 p_raw 0.0169 → p_holm 0.0272. **Both "significant" — and both significantly NEGATIVE. Significance here is evidence against the family, not for it** |
| **Decision** | **REJECT — all four CONTINUE criteria FAIL** |
| Amendment A1 | **First study run under A1, and it changed a criterion's recorded value on first use.** Criterion 2 now reads "excludes zero **on the favourable side**", `bool(lo > 0.0)`. The interval excludes zero *entirely below* it, so the old direction-blind wording would have recorded PASS; **A1 turned it into the FAIL it always was.** A1 was committed at `830aafc`, **prospectively, before Family 3's data was touched**, on Family 2's recommendation, and changed no completed result |
| Reason | **The information failed** — absent and orthogonal. **The cleanest test of the three**: good coverage, continuous distribution, the strictest door, the lowest correlation with anything already known, and the answer was still nothing |
| Family slot | **Slot 3 of 3 — SPENT.** No Family 3′, including a sign flip; **no fourth family** |
| Commit / artefacts | prereg `5cb409f`, A1 `830aafc`, result `7602e99`. `alpha/out/v3_family3_development.json` / `.pkl`, `alpha/out/f13_gate.json`, `alpha/edgar/f13_meta.json`, `alpha/edgar/f13_cusip_map.json`, `alpha/V3_FAMILY3_REPORT.md` |

**Family budget after V3-3: 3 slots, 3 spent, 0 remaining. PROGRAMME CLOSED under §21.**

### 7.3 V3 index addendum

Appended rather than merged into §2's table, so that no existing row is touched.

| ID | Date | Study | Arm | Primary result | Resolution | Decision |
|---|---|---|---|---|---|---|
| `V3-1` | 2026-08-09 | V3 Family 1 | B3 + 0.25 SUE tilt | vs B3 **+0.00090**, CI [−0.00140, +0.00317] | 0.00229 vs B3 | **REJECT** |
| `V3-2` | 2026-08-09 | V3 Family 2 | B3 + 0.25 insider tilt | vs B3 **−0.00096**, CI [−0.00187, −0.00004] | 0.00092 vs B3 | **REJECT** |
| `V3-3` | 2026-08-09 | V3 Family 3 | B3 + 0.25 13F tilt | vs B3 **−0.00339**, CI [−0.00631, −0.00073] | 0.00279 vs B3 | **REJECT** |

**V3 verdict: 3 of 3 slots spent, 3 of 3 families REJECTED. The programme is CLOSED under
§21.** No fourth family, no Family 1′/2′/3′, no re-test of a rejected family at another
horizon, learner, carrier or feature. The comparative diagnosis §21 requires is in
`alpha/V3_FAMILY3_REPORT.md` §8 and `reports/PROGRESS_V3.md`.

**The three failed differently, and that is V3's most useful output.** Family 1 was **real
but not incremental** (its own IC cleared zero and it still could not add to B3); Families
2 and 3 were **absent** (neither standalone interval cleared zero). A family can fail
because its information is redundant or because it is not there; V3 saw one of the former
and two of the latter.

---

## 8. V4 experiments

**V4 is a separate programme with its own budget, constituted by `alpha/V4_CHARTER.md`
(`6717111`) under the master roadmap's own §21 clause that reconsidering the *formulation*
is a new programme with a new directive, and under §27F, which reserves that commissioning
to the account holder.** V4 inherits from V3 exactly three things: the point-in-time
discipline, the statistical machinery, and the standard of honesty. **It inherits no slots
and no permissions.** No V3 result is rescored, reinterpreted or edited by anything in
this section.

**V4 budget (charter §8): at most TWO confirmatory studies. Slot 2 is conditional and was
never pre-authorised.**

### 8.1 Pre-study gates — V4-SUE, computed 2026-08-10 before any slot was spent

Full record: `reports/V4_SUE_POWER_GATE.md`, **committed in two parts deliberately** —
the block-length freeze (`ee8fe3f`) **before** any half-width existed, the half-width and
verdict (`fdda61a`) appended after. The git history is the evidence that the ordering held.

| Gate | Value | Verdict |
|---|---|---|
| Block length, frozen before any half-width | **L = 7** — reproduces the record's own H = 5 persistence allowance on top of mechanical overlap q = 3; `n^(1/3)` = 313^(1/3) = 6.79 gives the same value independently | **FROZEN** |
| Usable cutoffs, determined mechanically | **313** of 316 (3 dropped: 2026-07-14/21/28, windows past the end of price history) | — |
| Measured autocorrelation of the paired difference | +0.5244 / +0.2812 / +0.0733 at lags 1–3, then noise — **matches the predicted 0.75 / 0.50 / 0.25 shared-window structure exactly** | — |
| Effective independent n | **113.5** (variance inflation 2.7578), against a nominal 313. **Nominal n is not evidence** | — |
| **§6 power gate** | achieved half-width **0.005372** vs frozen MDE **+0.0095** — margin **1.77×**. Newey–West cross-check 0.005308 (within 1.2%) | **PASS** |
| **§7 standalone-strength screen** | R ≈ +0.0318 native 20D required; P = 2 × 0.01305 = **+0.0261**; **R / P ≈ 1.22** against a pre-registered ceiling of 1.5 | **PASS** |

**The charter predicted this gate would fail, and was wrong for an identifiable reason.**
§6.2 stated *"This gate is more likely to fail than to pass."* The formulation review's
≈ 0.0092 extrapolation overstated the true half-width by **1.71×**: it charged √4 for the
horizon on the assumption that cutoffs are lost at 20D, but **313 of 316 survive** and the
measured variance inflation is **2.7578, not 4**. **The charter was not edited. Nothing was
loosened to produce the PASS** — the estimate that moved was an estimate of the instrument,
measured for the first time, in the direction the charter did not expect.

**A sharper number recorded at gate time and not acted on:** the charter §10.1 estimated
the 20D development/exam window overlap at 5 sessions; the true nearest retained neighbour
is **10 sessions** away, so the overlap is **10 sessions — half the outcome window**. This
strengthens the charter's conclusion that the sealed exam is **not constituted for a 20D
horizon**, and changes none of its decisions.

### 8.2 V4-1 — V4-SUE: does a 20-session horizon rescue filing-derived SUE?

| Field | |
|---|---|
| ID / date | `V4-1` · run **2026-08-10T16:07:19** · registered 2026-08-10 |
| Hypothesis (charter §2.2, H1) | Economically slow, filing-timestamped information contains incremental cross-sectional information over B3 at a pre-registered **20-session** horizon **which it does not contain at 5 sessions** — such that `rank_pct(B3) + 0.50·(rank_pct(sue) − 0.5)`, scored against 20-session forward alpha, exceeds B3's own IC by **≥ +0.0095 native 20D**, with the interval entirely above zero, both halves positive, and survival ex-bear |
| H0 it had to be able to accept | Slow filing information decays no more than √H-proportionally between 5 and 20 sessions, so the longer horizon buys only cost reduction and no informational gain |
| Information source | **The same `sue` as V3 Family 1, construction frozen and unmodified** (charter §4.1). Reuse is not a loophole around §21: §3.4(d) requires **varying the formulation while holding the information fixed**, or a null is uninterpretable |
| Target / horizon | **`alpha_20d`** — asset minus SPY over 20 sessions, built by the existing tested instrument `targets.realise(..., horizon=20)`. **`corr(alpha_5d, alpha_20d) = 0.4962`**, confirming these are distinct dependent variables sharing only their first five sessions |
| Universe | 142,178 rows across 313 cutoffs. **SUE coverage 0.9299** vs the ≥ 0.80 gate. **Book-tail formability 313/313 (100%)** — the Family 2 lesson made a gate, and it passed |
| Model / seeds | **none — information-only test** (§2.9). A fitted learner is not an answer to an information null |
| Periods | **313 development cutoffs**, 2016-01-04 … 2026-07-07. Exam contamination **0**, asserted before scoring. Digest `b55e065f4c9f9173` |
| Baselines | **B3 +0.00846** (hw 0.02940), B1 12-1 momentum −0.00029 (hw 0.03228), B2 reversal +0.01089 (hw 0.01591), Arm 0 standalone SUE +0.00426 (hw 0.01486) — all at 20 sessions |
| Arms declared | **2**, before the first fit. λ = **0.50 fixed, never scanned**; no point on any λ curve promotable to an arm. Sign **+1**, carried unchanged from `V3_PREREGISTRATION.md` §6.1, never estimated |
| **Resolution / MDE (§2.6)** | MDE **+0.0095 native 20D**, frozen, never lowered. **Achieved half-width 0.00537** — margin 1.77×. **This is a well-resolved null, not an underpowered one** |
| Primary metric | paired per-cutoff IC difference, Arm 1 − B3 |
| **Result** | **−0.00106, CI [−0.00610, +0.00464], half-width 0.00537, breadth 0.4760, n = 313.** p_boot 0.698, p_holm 1.000 |
| Criteria | **All four FAIL.** C1 −0.00106 < +0.0095; C2 lo = −0.00610 (A1 favourable-side logic); C3 breadth 0.476 and first half −0.00341 / second +0.00130; C4 ex-bear −0.00182 |
| **Standalone horizon diagnostic — the decisive number** | **Standalone SUE 20D IC +0.00426, half-width 0.01486, CI [−0.01000, +0.01971], hit 0.5623**, against the pre-registered √(H/5) extrapolation **P = +0.0261**. The pre-registered threshold `P − h0 = +0.01124` was **not reached.** The observed value falls below P **by 0.02184, which exceeds its own half-width** — so this is a resolved shortfall, not an ambiguous one |
| Secondary | Arm 1 IC **+0.00740**, **below B3's +0.00846** — adding SUE at λ = 0.50 *reduced* the signal. Arm 0 halves −0.0061 / +0.0147 (not both positive) |
| Stability | halves −0.00341 / +0.00130 (**not both positive**); regimes BULL −0.00251, BEAR +0.00497, SIDEWAYS +0.00364, **EX-BEAR −0.00182**. The only positive regime is the one §2.5 disqualifies |
| Net of costs | gross spread advantage vs B3 **−0.00096**, CI [−0.00219, +0.00050]; **net −0.000965** at both the 5- and 20-session stride; extra turnover **−0.0015** (20s stride). Arm 0 net **−0.002893**. **The adverse prior recorded in charter §4.3 before measurement was confirmed** |
| Noise control | **PASS** — 30 paired within-cutoff draws, median −0.00130, mean −0.00166, sd 0.00137, **0.0% (0 of 30)** at or above the MDE, against a median limit of **+0.0019** and a 10% exceedance limit. **The null is not an artefact of the procedure** |
| Multiplicity | Holm across 2 arms: **p_holm 1.000 both — neither significant** |
| **Decision** | **REJECT** — all four CONTINUE criteria failed |
| Reason (charter §12 diagnosis) | **See §8.4. The information failed, and the horizon hypothesis was disconfirmed rather than left untested.** Not the power (1.77× margin), not the PIT door, not the coverage (0.9299), not the target, not the book-tail formability (313/313), not the procedure (noise control passed) |
| Budget slot | **V4 Slot 1 of 2 — SPENT.** **SUE is CLOSED at every horizon**: rejected at 5D under λ = 0.25 (V3-1) and at 20D under λ = 0.50 (V4-1). No variant, modification, re-sign or re-horizon may be proposed |
| Preregistration compliance | Result generated by `alpha/v4_sue_study.py`, which imports every constant from `alpha/v4_sue_config.py`, committed at `5718f83` **before the study module existed**. A pre-measurement clarification (`targets.realise` vs direct `forward_return`) was committed at `aedf891` **before execution**. **No constant, threshold or decision rule was modified after results were seen** |
| Commit / artefacts | formulation review `21a81d0`, charter `6717111`, gate `ee8fe3f` + `fdda61a`, prereg `5718f83`, clarification `aedf891`, result `f941480`. `alpha/out/v4_sue_development.json` / `.pkl`, `alpha/out/v4_sue_power_gate.json` / `.pkl`, `alpha/V4_SUE_RESULT.md`, tests `app/tests/test_alpha_v4_sue.py` |

### 8.3 V4 index addendum

| ID | Date | Study | Arm | Primary result | Resolution | Decision |
|---|---|---|---|---|---|---|
| `V4-1` | 2026-08-10 | V4-SUE, 20-session horizon | B3 + 0.50 SUE tilt | vs B3 **−0.00106**, CI [−0.00610, +0.00464] | **0.00537** vs B3, MDE 0.0095 | **REJECT** |

### 8.4 The charter §12 diagnosis — stated explicitly

Charter §12 requires the registry entry to answer: *did the information fail, or the
target, horizon, PIT quality, coverage, economics, or the power?* The answer, in full:

> **The information failed, and — for the first time in this programme — the horizon and
> formulation hypothesis was DISCONFIRMED rather than left untested.**
>
> V3's §21 diagnosis (`alpha/V3_FAMILY3_REPORT.md` §8) listed the horizon as **"a live,
> UNRESOLVED possibility"**: every family had run at 5D against sources that are
> quarterly-to-event and 45–135 days stale, and §2.9/§21 barred re-testing them, so that
> programme **could not distinguish "no information" from "wrong horizon."** V4 was
> constituted to settle exactly that question by varying the formulation while holding the
> information fixed (charter §3.4(d)). **It settled it.**
>
> **The decisive measurement is the standalone diagnostic, not the primary contrast.**
> SUE's standalone 20-session IC came in at **+0.00426, half-width 0.01486, 95% CI
> [−0.01000, +0.01971]**, against the pre-registered √(H/5) extrapolation from its V3 5D
> standalone of **P = +0.0261** — the value implied if the longer horizon bought *nothing*
> informational, i.e. the H0 of charter §2.2. The pre-registered admissibility threshold
> was `P − h0 = +0.01124`. **The observed +0.00426 does not reach it.** The shortfall
> against P is **0.02184, larger than the diagnostic's own half-width**, so this is a
> resolved failure to reach the H0 line and not an ambiguous one.
>
> **H1 asserted superlinear decay — that the longer horizon would unlock information absent
> at 5D. The measurement points the other way: the 20-session horizon did not unlock
> information; it appears to have diluted it.** Charter §2.2 fixed this reading in advance:
> *"if the feature's standalone 20D IC does not exceed its pure √(H/5) extrapolation from
> 5D by enough to reach the §7 threshold, H1 is false, and the correct recorded conclusion
> is that free point-in-time filing data on this universe cannot beat B3 at any horizon
> this history can test — not that a third horizon should be tried."* **That is the recorded
> conclusion.**
>
> **What did not fail, each excluded on a measurement rather than an assertion:**
>
> * **Power — NOT the failure.** Achieved half-width **0.005372** against a frozen MDE of
>   **+0.0095**, a **1.77× margin**, corroborated by three independent dependence
>   corrections (block bootstrap 0.005372, Newey–West 0.005308, closed-form 0.005796). The
>   gate was frozen and passed before the slot was spent.
> * **Point-in-time quality — NOT the failure.** The acceptance-time door
>   (`alpha/filings.py`) is unchanged and tested; **51.8% of 10-K/10-Q filings are accepted
>   after the 16:00 ET close of the date they are stamped with**, and the leaking
>   `filed <= cutoff` rule was never used.
> * **Coverage — NOT the failure.** **0.9299** against a 0.80 gate.
> * **Book-tail formability — NOT the failure.** **313 of 313 cutoffs (100%)** could form
>   both tails. The Family 2 defect that made a short leg impossible was made a gate here,
>   and the gate passed.
> * **The target — NOT the failure.** The same within-cutoff Spearman IC on 20-session
>   forward alpha resolves B3 at **+0.00846** and B2 at **+0.01089**; the instrument
>   measures signal when signal is present.
> * **The procedure — NOT the failure.** Noise control **PASS**: 30 paired within-cutoff
>   permutations, median −0.00130, **0 of 30** draws reaching the MDE.
> * **Economics — a real failure, but downstream.** Net spread advantage **−0.000965**;
>   the eighth consecutive tilt that does not pay for its own trading. It failed to pay
>   because it was ≈ 0, not because costs consumed a real effect.
>
> **What this does NOT establish.** It does not establish that filing data contains no
> information — V3-1's standalone SUE at 5D (+0.01305, CI [+0.00263, +0.02339]) disproves
> that, and it remains the only factor this programme has produced whose own interval
> cleared zero. The correct reading is narrower and firmer than V3's was: **on this
> universe, against this incumbent, at both the fast and the slow end of the horizon range
> this history can test, free point-in-time filing data does not contain incremental
> information of a size worth acting on — and the horizon was not the reason.**

### 8.5 V4 Slot 2 — BARRED and UNSPENT

**Slot 2 is not opened, was never occupied by any source, and is now barred from opening.**

Charter §8.3 permits Slot 2 only if **all four** conditions hold. **Condition 1 fails on
the pre-registered numbers**, which is dispositive on its own:

| §8.3 condition | Status |
|---|---|
| 1 — Slot 1 established that the V4 formulation is viable, shown by SUE's **standalone** 20D IC **materially exceeding** P = +0.0261 | **FAILS.** Observed **+0.00426** — roughly a **sixth** of P, and short of the `P − h0 = +0.01124` threshold by more than the diagnostic's own half-width. The charter fixed the consequence in advance: *"A flat or sub-√H standalone result means the formulation is dead and no second source can revive it"* |
| 2 — the failure was diagnosed as source-specific rather than formulation-specific | **FAILS.** §8.4 diagnoses it as **formulation-level**: the horizon mechanism itself was disconfirmed. A source-specific diagnosis is not available on this evidence and may not be manufactured to open the slot |
| 3 — a separately pre-registered scientific reason for a specific new source | **Not met.** None exists, and none may now be written, conditions 1 and 2 having failed |
| 4 — the candidate passes §7.3's screen and §6's power gate on its own numbers | **Moot.** Conditions are **conjunctive** and are not weighed against each other |

**Charter §8.2 therefore governs, in its pre-registered wording:** changing the formulation
did not rescue the only positively evidenced V3 information source, and *"the correct
response is to record that and stop — not to open Slot 2 by default, and not to look for a
third horizon."*

> ### Budget: V4 Slot 1 SPENT. V4 Slot 2 BARRED and UNSPENT. V4 is CLOSED.

**Barred permanently under charter §9.2 and §11, restated here so this section stands alone:**

* **No SUE′** — no variant of the source at any horizon, λ, sign or construction.
* **No third horizon** — not 10D, not 40D, not 60D, not a blend, **not "as a diagnostic."**
* **No λ change and no λ scan**; no point on any λ curve may be promoted to an arm.
* **No sign flip**, at any horizon, on any outcome.
* **No new information family.** V4 is a formulation study, not a feature search; there is
  no open-ended candidate pipeline. 13F acquired no standing from the charter and acquires
  none now. Form 4 remains barred at any horizon or architecture under its construction.
* **No learner substitution.** A fitted model is not an answer to an information null (§2.9).
* **No re-specification of the target**, and **no sub-universe, sector, regime or period
  restriction** to make a result survive.
* **No V3 artefact is edited, rescored or reinterpreted.** V3 stands exactly as recorded.
* The **72-cutoff exam remains SEALED** at
  `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, never opened,
  and is **not constituted for a 20-session horizon** in any case (charter §10.1, sharpened
  at gate time to a 10-session overlap).
* **Production weight remains 0.0**; `alpha/adapter.py` untouched.
* **Nothing is pushed** — `origin` is a third party's public repository (§27A).

**Any further work requires a new directive from the account holder, commissioned
deliberately as its own programme. It is not a continuation of V4, and it may not be
opened by an executing session.**

### 8.6 Verification of this backfill

Every figure in §7 and §8 was transcribed from a committed artefact and re-read from that
artefact on 2026-08-10 before being written here. Sources: `alpha/out/v3_family2_development.json`
and `alpha/V3_FAMILY2_REPORT.md`; `alpha/out/v3_family3_development.json` and
`alpha/V3_FAMILY3_REPORT.md`; `alpha/out/v4_sue_development.json`, `alpha/V4_SUE_RESULT.md`
and `reports/V4_SUE_POWER_GATE.md`. **No study was re-run, no artefact was regenerated, and
no value was recomputed.**

---

## 9. Single-Name Phase 1 (SN-1) — 2026-08-11

Appended 2026-08-11. Commissioned by the account holder's `MISSION` directive (2026-08-10)
and admissible under master roadmap **§9b, Phase 7b — single-name re-validation**, which is
a standing blocking phase, not a new family study.

### 9.1 Registry entry

| Field | Value |
|---|---|
| ID | **SN-1** |
| Date | 2026-08-11 |
| Hypothesis | The incumbent cross-sectional signal B3, calibrated walk-forward and optionally conditioned on market state, produces a useful **absolute** single-name forecast of `P(r₅ > 0)` and `E[r₅]` |
| Information source | **None new.** `alpha/out/panel.pkl` (built 2026-08-08), existing columns only |
| Target | **`asset_return`** — absolute 5-session forward return. **Not** `alpha_5d`. A different dependent variable from every prior study in this repository |
| Horizon | **5 sessions** (`targets.HORIZON`). No second horizon computed anywhere |
| Model | S0 always-up · S1 unconditional prior · S2 12-1 momentum · S3 B3 · S4 B3 × (trend, vol). Logistic `C=1.0` + Ridge `alpha=1.0`, one centred feature, no regularisation search |
| Seeds / instrument | `stats.SEED = 20260808`, block length 4 cutoffs, 10,000 draws, Newey-West 4 lags |
| Sample | 215 development cutoffs, 2018-01-26 … 2026-07-28 · 101,137 symbol-dates · 580 symbols · realised up-rate 0.5370 |
| Pre-registration | `alpha/SINGLE_NAME_PREREGISTRATION.md`, commit `616e41a`, **before any measurement** |
| Gates | G1 **FAIL** · G2 **FAIL** · G3 **FAIL** · G4 **FAIL** |
| **Decision** | **DO NOT ADVANCE.** No candidate is eligible for the exam |
| Budget slots spent | **0.** No information family was tested. V3 (3/3 spent) and V4 (slot 1 spent, slot 2 barred) are unchanged and remain CLOSED |
| Exam | **SEALED**, `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, not loaded, not scored, not inspected |
| Production | weight **0.0**, `alpha/adapter.py` untouched |
| Report | `reports/SINGLE_NAME_PHASE1.md` |

### 9.2 The finding, in one paragraph

Across all 101,137 symbol-dates **no arm ever emitted `p_up < 0.5`**, and **zero SELL calls
were produced**. B3's cross-sectional rank moves the absolute directional probability by
about ±2 points around a 53.7% unconditional drift, so every arm makes the same directional
call as always-up on every row and the paired accuracy contrast is identically zero. The
best probabilistic contrast anywhere is S4 − S1 on log loss, **−0.00024 against a half-width
of 0.00096**. Calibration in aggregate is adequate (ECE 0.01799) but has no resolution: 98.1%
of the probability mass falls in one 0.1-wide bin, and the residual bias is **overconfidence**
that widens with the probability (−0.017 in the main bin, −0.048 in the tail).

### 9.3 What is barred as a consequence

* **No larger model on the same input.** M0 and M1 both failed; M2 requires validated
  independent alpha features and the programme has none. Roadmap §2.9 and §0.1 ("No V2.4")
  govern directly.
* **No threshold rescue.** The §4 sweep reached 57.5% accuracy at 8.8% coverage. It is a
  diagnostic curve computed after the fact; no point on it may become the rule without a
  fresh pre-registration (roadmap §0.1, CLAUDE.md §3.2).
* **No promotion of the S4 regime bucket.** S4's entire separation from S3 comes from
  BULL_TREND/LOW_VOL, where the walk-forward fit **inverts** B3's ranking. Regime-concentrated
  results are a disqualifier under roadmap §2.5 and may not be restricted to in order to
  survive.
* **No claim that the decile spread is a stock prediction.** The +0.00656 [+0.00220, +0.01005]
  top-minus-bottom decile spread is a *within-cutoff* contrast. Roadmap §9b: a signal that
  beats the cross-section but not always-up is a portfolio-construction result and must be
  described as one.
* **No new information family** is authorised by this result, and none was tested by it.

### 9.4 Measured resolution, carried forward

| Contrast | 95% half-width | Reusable as |
|---|---:|---|
| Log loss vs S1 | **0.00096** | the probabilistic MDE for any future single-name candidate |
| Brier vs S1 | **0.00047** | ditto |
| Mean 5D return on the covered book | **0.00390** | the economic MDE — **39 bp per 5 sessions** |
| Directional accuracy, level | **0.02628** | the bar for any unpaired accuracy claim |

These are measurements on the development set at n = 215 cutoffs, not thresholds, and they
are what a future §2.6 power gate for a single-name study should be computed against.

---

## 10. Family 10 admissibility pilot (F10-PILOT) — 2026-08-11

Appended 2026-08-11. Commissioned by the account holder after
`reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` returned `OPEN ONE FAMILY` at `4a966a2`.
Registered here under §2.7 because **no failed run is ever silently discarded** — and a
pre-slot admissibility pilot that returns FAIL is exactly the kind of run that would
otherwise leave no trace.

### 10.1 Registry entry

| Field | Value |
|---|---|
| ID | **F10-PILOT** |
| Date | 2026-08-11 |
| Kind | **Admissibility pilot, not a study.** Four blocking stages, each committed before the next |
| Hypothesis under test | Not tested. The pilot asks only whether SEC 8-K adverse-event items are *scientifically admissible* as the next family |
| Information source | SEC EDGAR bulk `submissions` archive, already on disk. **No new source opened** |
| Event definition | 8-K carrying ≥1 of `1.02, 1.03, 2.04, 2.05, 2.06, 3.01, 3.02, 4.02` and **not** `2.02`. Frozen; nothing added, removed or split |
| Target | **None read.** No forward return, no post-event return, no sign fitted |
| Horizon | 5 sessions, inherited from `targets.HORIZON`. No second horizon anywhere |
| Sample | **1,682 issuer-events**, 477 CIKs, 485 historical securities, 1,221 sessions, 2016-01-04 … 2026-07-31 |
| Stage 1 — survivorship / identity | **PASS**, `cc2613b` |
| Stage 2 — §2.10 clause 3 | **PASS**, `e02d857`. 0.0437 vs 12-1, 0.0432 vs B3, 0.0458 worst of 34 |
| Stage 3a — block length | **L = 24 sessions frozen BEFORE any half-width**, `b75a70e` |
| Stage 3b — §2.6 power gate | **FAIL**, `ac2505e`. 57.8 bp against the 39 bp hurdle fixed at `4a966a2` |
| Stage 4 — PIT mutation proof | **NOT REACHED.** Stage 3 blocks |
| **Decision** | **`FAMILY10 ADMISSIBILITY: FAIL` — POWER.** The family is not implemented |
| Budget slots spent | **0.** V3 remains 3/3 spent and CLOSED; V4 slot 1 spent, slot 2 BARRED; both unchanged |
| Exam | **SEALED**, `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. Not loaded, not scored, not inspected — only its cutoff *dates* were read, which is calendar arithmetic |
| Production | weight **0.0**, `alpha/adapter.py` untouched |
| Report | `reports/FAMILY10_ADMISSIBILITY.md`, with stage records `FAMILY10_STAGE1_PANEL.md`, `FAMILY10_STAGE2_INDEPENDENCE.md`, `FAMILY10_STAGE3_POWER.md` |
| Tests | 768 → 840 collected, 777 passed, 63 skipped, **0 failed**. No existing test weakened |

### 10.2 The finding, in one paragraph

The family is admissible on **identity** and on **independence**, both strongly. It is not
**resolvable**. Point-in-time reconstruction on CIK identity retains 133 securities that are
not current index members and 70 issuers that are no longer SEC registrants — and shows that
a present-day-symbol panel would have deleted **42.4% of item 3.01 (delisting)** against
**5.6% of item 3.02 (dilution)**, a loss that rises monotonically with how adverse the event
is. That repair works. What does not survive is power: at a block length derived from the
dependence structure of event-time sampling (**L = 24 sessions, D = 111 blocks**) the primary
687-event development-safe sample resolves **57.8 bp per 5 sessions** against the **39 bp**
economic hurdle the source survey fixed before the pilot began, and the half-width **floors at
49.0 bp as n → ∞** — so 39 bp is unreachable at that block length for *any* event count.

### 10.3 What is barred as a consequence

* **No shorter block to rescue the gate.** The family clears 39 bp at exactly one length,
  L = 5, which allows nothing for market persistence and contradicts `alpha/stats.py`'s own
  standard. Re-running at L = 5 would be optimising the block length for a favourable MDE,
  which the commissioning directive and roadmap §2.6 both forbid.
* **No "the effect might be huge."** Power must be justified before outcomes are seen, and
  **61.1% of these filings are accepted after the close** (measured), so only residual drift
  is capturable.
* **No item-set enlargement to buy events.** The eight items are frozen and item 2.02 is
  barred structurally as the rejected V4-SUE family's information.
* **No re-test at another horizon.** V4 already disconfirmed the horizon hypothesis and
  barred slot 2; roadmap §2.9 and §21 govern.
* **No claim that Stage 4 would have passed.** It was not run and nothing here should be read
  as if it had been.

### 10.4 Measured resolution, carried forward

The half-width floor is a property of the **study window and the target**, not of this family.
Any future absolute-return candidate on this universe must clear its own claim against these
**before** a panel is built for it:

| Block length | Independent blocks | Half-width floor as n → ∞ |
|---:|---:|---:|
| 5 sessions | 532 | 22.4 bp |
| 10 sessions | 266 | 31.6 bp |
| **24 sessions** | **111** | **49.0 bp** |

This supersedes nothing in §9.4 — SN-1's 39 bp remains the measured economic MDE of the
Phase 1 covered book. It adds the constraint SN-1 could not see: what an *event-time* design
can resolve once its blocks are counted honestly.

---

## 11. Agent Meta-Signal Study (AMS-1) — 2026-08-11

Appended 2026-08-11. Commissioned by the account holder to test the repository's
**original multi-agent thesis** directly: does agreement among algorithmically distinct
trading-agent families identify situations where a single-name 5-session prediction
becomes materially more reliable?

### 11.1 Registry entry

| Field | Value |
|---|---|
| ID | **AMS-1** |
| Date | 2026-08-11 |
| Hypothesis | Cross-family trading-agent agreement alters the conditional distribution of the 5-session single-name return enough to support calibrated selective prediction |
| Information source | **None new.** The repository's own trading agents, reconstructed point-in-time |
| Target | **`asset_return`** — absolute 5-session forward return |
| Horizon | **5 sessions.** No second horizon computed anywhere |
| Roster | 7 agents in 3 families: `A_RULE` (3), `D_POLICY_GRADIENT` (1), `E_EVOLUTIONARY` (3). 15 RL agents excluded on measured reconstruction cost |
| Sample | 19,173 scored rows · 100 symbols · **215 evaluation cutoffs** · base up-rate 0.5435 |
| Pre-registration | `alpha/AGENT_META_PREREGISTRATION.md`, commit `229990c`, **before any forward return** |
| Stage 1 | `c493a5b` — `AMS-1 ADMISSIBILITY: PASS` |
| Gates | 1 **PASS** · 2 FAIL · 3 FAIL · 4 FAIL · 5 FAIL · 6 PASS · 7 PASS · 8 FAIL · 9 FAIL |
| **Decision** | **`AMS-1 VERDICT: REJECT`** |
| Budget slots spent | **0.** No information family was tested. V3 (3/3) and V4 (slot 1 spent, slot 2 barred) remain CLOSED and unchanged; Family-10 remains unspent |
| Exam | **SEALED**, `b55e065f…`, not loaded, not scored, not inspected |
| Production | weight **0.0**, `alpha/adapter.py` untouched |
| Report | `reports/AGENT_META_SIGNAL_RESULT.md`, audit `reports/AGENT_META_AUDIT.md` |
| Tests | 840 → 900 collected, 837 passed, 63 skipped, **0 failed** |

### 11.2 The finding, in one paragraph

Across the four populated consensus states `P(up)` is **perfectly monotone downwards**
(Spearman **−1.00**): unanimous SELL is followed by an up-move **56.3%** of the time and
unanimous BUY **53.0%**, with mean returns of **+35.3 bp** and **−0.3 bp**. The extreme
gap is **−1.10 pp** against a paired interval of **[−4.34, +1.82]**, so the inversion is
not significant either — the correct reading is that the agents carry **no directional
information** and what little structure exists points the wrong way. Every arm's log loss
sits within 0.001 of every other, no arm ever emits a probability below 0.5, and the whole
probability range across 19,173 rows is 0.542–0.562. Family aggregation neither helps nor
hurts (**−0.000031** [−0.00027, +0.00015]) because the Stage 1 audit measured that there is
nothing to aggregate: **zero of 231 agent pairs are near-clones**, mutual information runs
0.015–0.060 bits of a possible 1.585, and pairwise correlations run −0.09 to +0.08.

### 11.3 What is barred as a consequence

* **No sign flip.** The inversion may not be traded, reported as a signal, or used to
  define a contrarian arm. It is not significant, and flipping a sign after a negative
  result is the retrofit CLAUDE.md §3.2 exists to prevent.
* **No claim that the excluded agents would have rescued it.** §10 of the pre-registration
  fixed this in advance, and four of the fifteen are degenerate at the repository's own
  default iterations (`Actor-critic` emits BUY on 98.5% of bars; `Actor-critic duel
  recurrent` emits nothing).
* **No AMS-2.** The pre-registration named AMS-2 as the follow-up *on ADVANCE only*.
* **No re-run at another horizon.** AMS-1 computed one horizon by design; a horizon study
  needs its own charter and its own power gate computed first.
* **No promotion of Gate 6.** Abstention's log-loss gain is an artefact of the retained
  rows drifting up more, not of better discrimination: retained accuracy 0.5527 against a
  retained base rate of 0.5497, and the paired change is **−0.0023 [−0.0053, +0.0004]**.

### 11.4 Carried forward

Three independent designs have now measured the same wall on free daily price data at a
5-session horizon for single names:

| study | design | resolution reached | result |
|---|---|---|---|
| SN-1 | weekly grid, B3-based | 39 bp / 3.0 pp | no probability below 0.5 |
| Family-10 | event time, 8-K adverse items | floor **49 bp** at L=24 | unreachable hurdle |
| **AMS-1** | agent consensus | **31 bp / 3.0 pp** | nothing above it |

AMS-1 reached the **sharpest** resolution of the three — 316 dates buy more than 177 — and
still found nothing. That is the strongest form the null has taken in this programme.

**A product finding, recorded because it is actionable outside the research record:**
three families agree unanimously on 28.3% of rows; seven agents agree unanimously on 1.2%.
A surface that displays "18 of 22 agents agree" as a confidence signal is counting
coincidence, not evidence — and this repository's Trading-agents tab does exactly that.
