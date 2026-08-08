# V2.1 Validation Setup

**What was built:** a frozen, independent, 72-cutoff exam set and the protocol
that will judge a model against it. **What was not built:** a model. No V2.1
feature set exists, no V2.1 fit has been run, and nothing has been evaluated on
the new exam. That is the intended state of this stage.

**Production is unchanged.** `alpha/adapter.py` was not modified. Weight remains
**0**; the action remains **HOLD**.

Pre-registration: [`V2_1_PREREGISTRATION.md`](V2_1_PREREGISTRATION.md), written
before the exam set was constructed. V2's record —
[`PREREGISTRATION.md`](PREREGISTRATION.md), [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md),
[`V2_REPORT.md`](V2_REPORT.md) and every artifact under `out/` — is untouched.

---

## 1. The set

| | |
|---|---|
| Protocol | V2.1 |
| Artifact | `alpha/out/v2_1_exam_set.json` |
| SHA-256 of the cutoff list | `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0` |
| Frozen | 2026-08-08, before any V2.1 model existed |
| **Frozen exam cutoffs** | **72** |
| **Development cutoffs** | **316** |
| Grid the two are drawn from | 532 cutoffs |
| Exam date range | 2017-12-27 … 2026-06-22 |
| Development date range | 2016-01-04 … 2026-07-28 |
| Prediction horizon | 5 trading sessions |
| Target | `alpha_5d = R_asset − R_SPY` |
| Grid spacing | 5 sessions (= horizon, so no window overlaps another) |
| Exam spacing | 30 sessions |
| Embargo | 5 sessions, on top of the horizon |
| Purge rule | every development cutoff is ≥ 10 sessions from every exam cutoff |
| Universe | point-in-time S&P 500, 436–502 eligible names per exam cutoff (median 471) |
| Index coverage | 87.9% – 100% (median 94.2%) |

### The selection rule

Deterministic, and it reads the trading calendar and nothing else:

1. grid = every 5th session from 2016-01-04 with a full 5-session outcome ahead;
2. the first **504 sessions** of the grid (100 cutoffs) are development-only —
   the warm-up, so the earliest exam date already has ≥ 60 training cutoffs
   behind it;
3. exam = every **6th** grid cutoff from there on;
4. development = every remaining grid cutoff ≥ 10 sessions from any exam cutoff.

No return, outcome, target or IC is read at any point in this rule. The step and
warm-up were chosen against one requirement — ≥ 60 exam cutoffs with a
development set several times larger — over a sweep of steps 5–8 and warm-ups of
1.5/2/2.5 years, judged on cutoff counts and on regime tags, which are computed
from pre-cutoff SPY and VIX closes.

### Independence

**One independent observation is one cutoff date**, not one stock-date. 460
names ranked on one morning share that morning.

Independence is structural rather than assumed:

* exam outcome windows are 5 sessions long, and consecutive exam cutoffs are
  **exactly 30 sessions apart** — min gap = max gap = 30, verified;
* **25 clear sessions** separate every pair of adjacent exam outcome windows;
* no exam window overlaps any other exam window at any lag;
* no exam window overlaps *or touches* any development window.

The mechanical serial correlation that overlapping windows create is **absent by
construction**, not corrected after the fact. The intervals in §4 exist for the
market's own persistence, which remains.

---

## 2. Distribution of the frozen set

Systematic sampling in calendar time, so the mix is the market's own mix over
2016–2026 rather than a quota anyone chose.

**Trend regime** (`features.regime_state`, SPY vs its 50/200-session means)

| Regime | Exam cutoffs | Share |
|---|---|---|
| BULL_TREND | 53 | 73.6% |
| BEAR_TREND | 10 | 13.9% |
| SIDEWAYS | 9 | 12.5% |

**Volatility regime** (VIX vs its trailing 252-session median)

| Regime | Exam cutoffs |
|---|---|
| HIGH_VOL | 36 |
| LOW_VOL | 36 |

VIX level across the set: min 10.5, median 17.9, max 46.8 — so the COVID
dislocation and the 2018 and 2022 volatility episodes are all inside the exam.

**By year:** 2017 (1), 2018 (8), 2019 (8), 2020 (9), 2021 (8), 2022 (9),
2023 (8), 2024 (8), 2025 (9), 2026 (4).

**By half** — criterion 4 splits the exam chronologically:

| Half | Cutoffs | Range | Trend mix |
|---|---|---|---|
| First | 36 | 2017-12-27 … 2022-03-01 | 28 bull / 3 bear / 5 sideways |
| Second | 36 | 2022-04-12 … 2026-06-22 | 25 bull / 7 bear / 4 sideways |

Both halves contain all three trend states, so a sign flip between them is a
finding about the model rather than about which regimes landed where.

Every trend bucket holds ≥ 8 cutoffs, which is the minimum at which criterion 7
gates. All three therefore gate; none is excused.

---

## 3. Benchmarks

V2's rule — "the simple factor with the largest |mean development IC|" — is
retired, for a reason that predates any V2.1 number: it maximises in-sample
effect size, and it duly selected 5-day reversal (−0.00955 on development,
−0.0008 on the exam) while 12-1 momentum (+0.00599 on development) went on to
beat the model out of sample. It is replaced by a fixed hierarchy with no
selection step.

| | Benchmark | Definition | Sign | Provenance | Gate |
|---|---|---|---|---|---|
| B1 | 12-1 momentum | within-cutoff percentile of `ret_12_1` | +1 | economic prior; not estimated from data | **yes** — the primary bar |
| B2 | 5-day reversal | within-cutoff percentile of `ret_5d` | −1 | the sign V2 froze on its development set | **yes** |
| B3 | regime-switched momentum | B1 in BULL/SIDEWAYS, −`mom_5d` rank in BEAR | — | pre-cutoff regime tag; nothing fitted | no — reported |

The question the exam is built to answer:

> Does market context add predictive information beyond a simple 12-1 momentum
> factor, and can a learned model beat that factor consistently out of sample?

---

## 4. Statistical methodology

* **Independent unit:** the cutoff date. Cross-sectional width enters only
  through the precision of each cutoff's own IC, never as a sample size.
* **Primary metric:** per-cutoff Spearman IC against `alpha_5d`.
* **Intervals:** naive i.i.d., Newey–West (Bartlett, 4 lags) and moving-block
  bootstrap (block 4 cutoffs, 10,000 draws) are all reported. Pre-registered
  decisions are judged against the **block bootstrap**.
* **Why block 4:** at 30-session exam spacing, four cutoffs span about six
  months, which is generous for the regime persistence that is the only
  dependence left once overlap is removed. Blocks 1, 2, 4 and 8 are reported
  side by side as a sensitivity, so the choice is visible and its effect
  measurable.
* **Sidedness:** two-sided throughout. "> 0 with a 95% CI excluding 0" is a 2.5%
  one-sided test in effect, which is stricter than a 5% one-sided test.
* **Multiplicity:** Holm–Bonferroni across the arms actually run, on each arm's
  criterion-1 bootstrap p-value. Clearing a raw p-value but not the adjusted one
  is reported as **not passing**.
* **Arms on the exam:** exactly one, chosen on development by highest mean
  development IC and frozen before the exam is opened.

### The nine gates

All nine must pass on the exam set for production weight to exceed 0.

| # | Criterion | Threshold |
|---|---|---|
| 1 | Mean Spearman IC | > 0.03, 95% bootstrap CI excludes 0 |
| 2 | IC hit rate | > 55%, CI excludes 50% |
| 3 | Top-minus-bottom quintile spread | > 0, CI excludes 0 |
| 4 | Sign stability | IC > 0 in ≥ 60% of cutoffs **and** mean IC > 0 in both halves |
| 5 | Beats 12-1 momentum | paired per-cutoff IC difference > 0, CI excludes 0 |
| 6 | Beats 5-day reversal | same test |
| 7 | No regime collapse | mean IC > 0 in every bucket with ≥ 8 cutoffs |
| 8 | Effective sample | ≥ 50 independent cutoffs |
| 9 | Cost-adjusted spread | net > 0 at 5 bps one-way, CI excludes 0 |

Reported but gating nothing: turnover (10), cost sensitivity at 5/10/20 bps
(11), and the independent-cutoff count with the full per-regime and per-half
tables (12).

**No V2 threshold was lowered** — criteria 1, 2, 3 and 8 carry V2's numbers
unchanged, and a test asserts it. Four things changed, each for a stated
methodological reason recorded before any V2.1 number existed:

* criterion 4 was redundant (V2 computed it and criterion 2 from the same
  `hit_rate`) and now also requires the sign to hold across both halves;
* criterion 5's benchmark is fixed rather than selected;
* criterion 6 is new — the model must beat *both* members of the hierarchy;
* criterion 7 gates only on buckets with ≥ 8 cutoffs, because on V2's 12-date
  exam it gated on buckets of one and two, where the check is a coin flip in
  both directions;
* criterion 9 is new — V2 reserved cost fields in the adapter and never
  populated them, and a 26 bp gross spread is not obviously a positive one.

---

## 5. Design note — is 72 cutoffs actually adequate?

Partly. The honest answer has a number in it, and the number is not flattering.

**What it fixes.** V2's exam could not pass criterion 7/8 at all: 12 < 50, by
construction, whatever a model did. Its IC interval spanned [−0.063, +0.239].
72 cutoffs clears the sample-size criterion with 22 to spare and shrinks that
interval by a factor of √6.

**What it does not fix.** Using the per-cutoff IC dispersion V2 actually
measured over 423 development cutoffs (sd 0.117 for the absolute-feature arm,
0.197 for the widest), the standard error of a mean IC over 72 cutoffs is
0.014–0.023. Criterion 1 requires the 95% CI to exclude 0, so it demands an
*observed* mean IC of roughly 0.027–0.046 — the CI condition binds harder than
the 0.03 threshold does. Reading that as power:

| Arm's per-cutoff IC sd | SE at n=72 | Observed mean IC needed | True mean IC for 80% power |
|---|---|---|---|
| 0.117 (V2-A) | 0.0138 | 0.027 | **0.039** |
| 0.197 (V2-F) | 0.0232 | 0.046 | **0.065** |

For comparison, the same arithmetic on V2's 12-date exam gives a minimum
detectable effect of **0.159** — an effect size no equity cross-sectional signal
plausibly has. So V2.1 improves the detectable effect by roughly 2.4×, and lands
in a range where a genuinely strong signal (mean IC ≥ 0.04, low dispersion)
would be found and a marginal one (mean IC ≈ 0.01–0.02, the region V2's arms
actually occupied) still would not.

**That residual is a property of the data, not of the protocol.** The densest
defensible alternative — every 5th grid cutoff instead of every 6th — yields 87
exam cutoffs and improves the minimum detectable effect only from 0.065 to
0.059, while costing 45 development cutoffs and pushing exam dates 25 rather
than 30 sessions apart. The binding constraint is that ten and a half years of
non-overlapping weekly cross-sections is 532 observations in total, and an exam
cannot be larger than the history it is cut from. Extending the study start
earlier is not available: the price cache begins 2014-01-02 and the deepest
feature needs 253 sessions behind the cutoff.

**Two things make that limit less damaging than it looks.**

First, the criteria are conjunctive. A model has to clear nine gates, several of
which — sign stability across halves, positive IC in all three trend buckets,
beating both benchmarks, surviving costs — are not more powerful versions of the
same test but different tests, and a fluke that clears one is unlikely to clear
all nine.

Second, the non-overlapping design is doing real work rather than decorative
work, and V2's own numbers show it: on 423 development cutoffs the block-4
bootstrap half-width was 0.0184 against a naive 0.0187 for V2-F, and 0.0104
against 0.0112 for V2-A. The bootstrap and the i.i.d. interval agree to within a
few percent — which is what "the mechanical autocorrelation has been removed by
construction" looks like when it is true. Power calculated from the naive SE is
therefore approximately right rather than optimistic.

**Where it is weakest.** Criteria 5 and 6 are the hardest, not the easiest. One
might expect pairing to help — both sides saw the same names on the same day, so
differencing removes the day — but on V2's development set the paired difference
was *noisier* than the raw IC (sd 0.194–0.253 against 0.117–0.197), because a
simple factor's per-cutoff IC is itself volatile and not strongly correlated
with the model's. Beating 12-1 momentum with a CI that excludes zero over 72
cutoffs needs a true edge of roughly 0.06 mean IC over the benchmark. That is a
high bar. It is also the right bar, and it is being written down before anyone
knows whether it will be met.

**Conclusion.** 72 independent cutoffs is the maximum defensible number under
the current methodology and history, and it is reported as such per §10 of the
pre-registration. It is adequate to make a strong result credible and adequate
to make a weak result honestly inconclusive. It is not adequate to certify a
marginal effect, and no report may present a marginal V2.1 result as if it were.

---

## 6. Leakage controls, and the tests that hold them

| Control | Mechanism | Test |
|---|---|---|
| Exam dates come from one place | `examset.load()`, digest-verified | `test_load_detects_an_edited_exam_set` |
| Exam set is immutable | `freeze()` refuses to overwrite; SHA-256 over the cutoff list | `test_freeze_refuses_to_overwrite_a_frozen_exam` |
| Construction is reproducible | calendar arithmetic only, no seed, no random draw | `test_exam_construction_is_deterministic` |
| No duplicate cutoffs | — | `test_the_exam_set_has_no_duplicates` |
| Exam cutoffs are independent | 30-session spacing vs a 5-session horizon | `test_exam_cutoffs_are_independent_under_the_horizon` |
| No dev window overlaps an exam window | ≥ 10-session separation, both directions | `test_no_development_window_overlaps_an_exam_window` |
| Exam cutoffs never enter training | `dataset.training_cutoffs` boundary, checked at every exam date | `test_training_never_sees_an_exam_cutoff` |
| No training target overlaps an exam target | outcome-window arithmetic | `test_no_training_target_window_overlaps_the_exam_target_window` |
| `develop` cannot use the exam by accident | `examset.development_only()` checks rather than trusts | `test_development_only_refuses_a_panel_carrying_exam_cutoffs` |
| No exam result reaches development | `examset` carries dates and pre-cutoff metadata only; source asserted free of outcome columns and of `forward_return` | `test_the_exam_set_carries_no_outcome_of_any_kind` |
| Warm-up delivers a real training sample | ≥ `MIN_TRAIN_CUTOFFS` behind the first exam date | `test_the_warmup_leaves_enough_training_cutoffs_for_the_first_exam_date` |
| ≥ 60 exam cutoffs | 72 | `test_the_frozen_exam_has_at_least_sixty_independent_cutoffs` |
| Every exam cutoff has rows | all 72 present in the built panel | `test_every_frozen_exam_cutoff_exists_in_the_built_panel` |
| The artifact matches its own rule | rule re-derived, digest re-checked | `test_the_frozen_exam_matches_the_rule_that_claims_to_have_produced_it` |
| Regime coverage | all three trend states, both volatility states, every bucket ≥ 8 | `test_the_frozen_exam_spans_more_than_one_market_condition` |
| Benchmarks are not selected | hierarchy fixed; `choose_best_simple_factor` absent from `protocol.py` | `test_the_benchmark_hierarchy_is_fixed_not_selected` |
| The primary benchmark is alive | `mom_12_1` was dead for a whole V2 run | `test_the_primary_benchmark_is_alive` |
| No threshold was lowered | asserted against `walkforward`'s constants | `test_no_v2_threshold_was_lowered` |
| Sign instability is caught | a model that works then stops fails criterion 4 | `test_sign_stability_catches_an_edge_that_lives_in_one_half` |
| Tiny regime buckets do not gate | | `test_a_regime_bucket_too_small_to_mean_anything_does_not_gate` |
| Costs are charged on measured turnover | | `test_turnover_is_measured_not_assumed`, `test_costs_can_turn_a_positive_gross_spread_negative` |
| Production stays HOLD | absent evidence is HOLD; the record's weight is 0 | `test_production_stays_hold_under_the_v2_1_protocol` |
| V2's record is unedited | `PREREGISTRATION.md` never mentions V2.1; the 12 V2 exam dates are still 12 | `test_v2_1_did_not_edit_the_v2_record` |

The V2 leakage suite (`app/tests/test_alpha.py`, 29 tests) continues to run
unchanged and still covers the guarantees V2.1 inherits: features and
predictions bit-identical under a rewritten future, membership as-of-cutoff, the
training embargo, leave-one-out sector peers, no all-NaN feature column, and the
adapter's HOLD cascade.

### Test status, verified 2026-08-08

```
pytest -q --runslow        527 passed in 224s
```

499 before this stage, **28 added**, none removed, none modified, no regression.
`app/tests/test_alpha_v2_1.py` alone: 28 passed in 14 s. Four of the 28 read the
real frozen artifact and `out/panel.pkl` and skip when those are absent; on this
machine all four ran.

---

## 7. Disclosed limitations

1. **The exam is not novel data.** The 72 cutoffs lie inside 2016–2026, and V2's
   development ladder ran over that window. The aggregate conclusion V2 reached
   — the stock-level relative tier is a null, all the movement is in market
   context — was formed partly on dates that are now exam dates. There is no
   later history to hold out. The exam is fully out-of-sample with respect to
   every model that will be evaluated on it, and in-sample with respect to one
   published null result. A V2.1 pass is evidence about a model, not evidence
   about a feature family, and must be reported in those words.
2. **Benchmark 2's sign was fixed on a superset of the exam dates.** That
   favours the benchmark and so raises the model's bar. Disclosed rather than
   corrected.
3. **Residual survivorship**, inherited from V2: 127 of 781 ever-members have no
   bars at all; index coverage runs 88% at the earliest exam cutoff to 100% at
   the latest, so early exam dates are missing roughly 12% of the true
   cross-section, biased toward names later acquired or delisted.
4. **Sector labels are not point-in-time.** Membership is reconstructed as-of
   cutoff; GICS sector is today's assignment applied backwards. See
   `membership.sector_drift_note()`.
5. **Two of V2's twelve exam dates (2025-06-23, 2026-07-07) are V2.1 development
   cutoffs.** Their outcomes were observed once, during V2's exam scoring. They
   are now training data, which is the correct place for a date whose outcome
   has been seen. One V2 exam date (2026-05-07) is also a V2.1 exam date; the
   other nine are off the 5-session grid and appear in neither set.
6. **The study window excludes 2008–09 and 2011.** Bear-market coverage rests on
   2018 Q4, 2020 and 2022.

---

## 8. What happens next — and what must not

**Next**, and not started here: a separate pre-registration for the research
ladder (V2.1-A momentum only → V2.1-B + market context → V2.1-C + justified
additions → V2.1-D learned nonlinear model), fixing the arms, their feature
lists and the family size for the multiplicity correction **before the first
fit**. Then development, on development cutoffs only. Then one arm, chosen on
development, goes to the exam once.

**Must not**, and each of these is ruled out in writing before any number
exists:

* evaluating any model on the V2.1 exam before the ladder is pre-registered;
* re-freezing `v2_1_exam_set.json` after seeing a result;
* lowering any threshold in §4;
* adding a benchmark, a regime split or a metric after seeing the exam;
* reporting a raw p-value as a pass when the Holm-adjusted one fails;
* moving production off HOLD on anything less than all nine gates.

---

## 9. How to reproduce

```bash
cd "Stock-Prediction-Models"
./.venv/Scripts/python.exe -W ignore -m alpha.examset show     # the frozen set
./.venv/Scripts/python.exe -W ignore -m alpha.examset freeze   # refuses: already frozen
./venv/Scripts/python.exe -m pytest app/tests/test_alpha_v2_1.py -q
```

`.venv` carries the scientific stack; `./venv` is the one with pytest. The exam
set was built from the existing `alpha/out/panel.pkl` — every V2.1 cutoff,
exam and development, is already a row in it, so no rebuild was needed and none
was done.
