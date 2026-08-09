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
