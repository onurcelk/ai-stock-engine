# V2 alpha study — report

**2026-08-08.** Deliverable 6 of §30. Companion documents: `PREREGISTRATION.md`
(written before any model was fitted, unedited since), `EXPERIMENT_LOG.md`
(every run including the wrong ones), and the frozen artefacts in `alpha/out/`.

---

## Verdict

**V2 did not demonstrate alpha. Production weight is 0 and the production
action stays HOLD.**

The full ladder was run. Nothing passed the §8 gate on development, so the
ranker (V2-C) and the sector-neutral ranker (V2-D) were **not built**. The best
arm was taken to the twelve frozen exam dates and failed there too. The output
adapter is written and wired, and it emits HOLD on all 5,899 exam predictions —
which is the correct output, not a defect.

Three findings are worth more than the verdict:

1. **Stock-level cross-sectional features contributed nothing.** V2-A
   (18 absolute features) scored a mean IC of +0.0084; adding 47 relative and
   percentile features (V2-B) moved it to +0.0085. Everything the model has
   comes from the *market context* tier — regime, VIX, breadth, the
   overnight/intraday split — which lifted it to +0.0238. That is a direct
   answer to §7-8 and it points the opposite way from the assumption behind the
   question.

2. **The edge is a regime bet, and the regime it likes flipped between
   samples.** On development, V2-F's IC was +0.081 in BEAR_TREND and −0.021 in
   SIDEWAYS. On the exam it was +0.435 in SIDEWAYS and −0.082 in BULL_TREND. A
   conditional edge that changes which condition it prefers between two
   disjoint samples is noise with a narrative attached.

3. **A one-line factor did better than the model on the exam dates.** Plain
   12-1 momentum returned +0.85%/week long-short against V2-F's +0.46%. Neither
   is significant, and the comparison cuts against V2 rather than for momentum.
   Details in §5 below.

---

## 1. What was built

`alpha/`, a new package. Nothing under `validation/` or `app/` was modified —
verified: the only file changed outside `alpha/` during this work is the new
test file `app/tests/test_alpha.py`. Full suite: **499 passed**, no regressions.

| § | requirement | how it was met |
|---|---|---|
| 2 | universe too thin at 22 names | **fixed, not caveated.** Point-in-time S&P 500 membership reconstructed from the index change log; 410–500 eligible equities per cutoff. Crypto, FX and ETFs excluded. |
| 3-4 | kill the 4-hour horizon; target = excess return | 5 sessions only. `alpha_5d = R_asset − R_SPY`, computed scorer-side. |
| 5 | overlapping windows | cutoffs spaced 5 sessions = the horizon, so outcome windows are **non-overlapping by construction** (§5 option a), with Newey–West and moving-block bootstrap applied on top. |
| 12 | sector-relative flagship | leave-one-out mean of point-in-time sector peers, not a sector ETF. |
| 14 | A → A′ → B → C, A′ as a gate | A′ measured first; B and C take an explicit `gate_passed` argument and return `None` when it is false. |
| 19-20 | walk-forward, 12 frozen dates untouched | 532 scheduled cutoffs → 484 development + 12 exam, with development purged within ±10 sessions of any exam date. |
| 21 | pre-registration | `PREREGISTRATION.md`, written before the first fit and unedited since. |
| 23 | no confidence score | none is computed or exposed. |
| 24-26 | presentation, HOLD-by-default, cost fields | `alpha/adapter.py`. |

Panel: 249,029 rows × 100 features over 540 cutoffs. Development slice:
221,519 rows, 484 cutoffs, of which 423 were evaluated (the first 60 are
consumed by the minimum training window).

---

## 2. Development results

Baseline first, as §14 requires. Six simple factors, each ranked within cutoff:

| factor | mean IC | hit rate |
|---|---|---|
| mom_5d | −0.00955 | 49.6% |
| mom_20d | −0.00848 | 50.6% |
| mom_60d | −0.00898 | 50.2% |
| mom_12_1 | **+0.00599** | 53.1% |
| rs_vs_spy_20d | −0.00848 | 50.6% |
| rs_vs_sector_20d | −0.00462 | 52.1% |

Every short-horizon factor is **negative**: at a 5-session horizon this
cross-section is a reversal effect, not a momentum effect. Only 12-1 momentum —
the one factor that deliberately skips the last month — is positive. The
pre-registered rule picks the baseline by |mean IC| and fixes its sign on
development, giving **`mom_5d` at sign −1** (buy last week's losers, mean IC
+0.00955). See §6 for why that rule turned out to be the wrong one.

The ladder, 423 evaluated cutoffs, all scored on Spearman IC vs `alpha_5d`:

| experiment | features | mean IC | 95% CI | hit | spread | vs baseline | verdict |
|---|---|---|---|---|---|---|---|
| V2-A absolute | 18 | +0.00837 | [−0.0017, +0.0191] | 50.8% | +0.00118 | −0.00278 | FAIL |
| V2-B + relative | 65 | +0.00846 | [−0.0040, +0.0210] | 51.3% | +0.00090 | −0.00268 | FAIL |
| V2-E + context | 100 | +0.02381 | [+0.0056, +0.0445] | 53.4% | +0.00210 | +0.01267 | FAIL |
| V2-F vol-scaled target | 100 | +0.03179 | [+0.0140, +0.0507] | 57.0% | +0.00257 | +0.02064 | FAIL |

Holm–Bonferroni across the four arms: V2-F p = 0.0032 and V2-E p = 0.0477 are
significant; V2-A and V2-B are not.

V2-F, the best arm, against the seven pre-registered criteria:

| # | criterion | value | threshold | |
|---|---|---|---|---|
| 1 | mean Spearman IC | +0.03179, CI [+0.0140, +0.0507] | > 0.03, CI excludes 0 | **pass** |
| 2 | IC hit rate | 56.97%, CI [0.525, 0.619] | > 55%, CI excludes 50% | **pass** |
| 3 | top−bottom spread | +0.00257, CI [+0.0004, +0.0047] | > 0, CI excludes 0 | **pass** |
| 4 | sign stability | 56.97% | ≥ 60% | fail |
| 5 | **beats best simple factor** | +0.02064, CI [−0.0029, +0.0455] | CI excludes 0 | **fail** |
| 6 | no regime collapse | SIDEWAYS −0.0205 | > 0 in every regime | fail |
| 7 | effective sample | 423 cutoffs | ≥ 50 | pass |

Criterion 5 is the one §18 calls "the single most important bar in the whole
directive", and it is the one that failed by the least comfortable margin: the
model out-scores 5-day reversal by 2 IC points on average, but the interval
does not clear zero. It was not relaxed.

**The gate stayed closed.** §8 opens the ranker only if V2-A *or* V2-B clears
criteria 1–5. Both failed. V2-E and V2-F did clear parts of the bar, so
widening the gate to "any arm" would have opened it — which is precisely the
move §10 rules out in advance. V2-C and V2-D were not built.

---

## 3. Exam results — twelve dates, opened once

Configuration read from `development.json`, not chosen here: V2-F, 100
features, volatility-scaled training target, baseline `mom_5d` at sign −1.
5,899 predictions, 7 refits, trained on development cutoffs only.

| statistic | mean | 95% CI | hit rate | p |
|---|---|---|---|---|
| Spearman IC | +0.05769 | [−0.0633, +0.2389] | 58.3% | 0.498 |
| top−bottom spread | +0.00462 | [−0.0123, +0.0293] | 41.7% | 0.655 |
| IC − baseline | +0.06979 | [−0.0916, +0.3988] | **33.3%** | 0.635 |

All seven criteria fail.

**Read the mean against the hit rate.** +0.058 sounds like a result; it is two
dates. 2025-03-27 scored +0.63 and 2025-06-23 scored +0.40, both
SIDEWAYS/HIGH_VOL. Drop those two and the remaining ten average **−0.034**. The
quintile spread was positive on 5 of 12 dates, and the model beat the simple
reversal factor on **4 of 12** — a positive mean produced by a minority of
dates pulling hard, which is the V1 report's "30 symbols on one date are not 30
draws" moved onto the time axis.

**Criterion 7 cannot pass on this set, and that is a defect in the
pre-registration.** It asks for ≥ 50 independent cutoffs; the exam paper is 12,
frozen by V1 and not extendable without un-freezing it. Under §9 that holds
production weight at 0 regardless of the other six. Recorded rather than
dropped or redefined. It is academic here — criteria 1–6 fail on their own
terms — but a 12-date exam gives the block bootstrap almost no power: the IC
interval spans [−0.063, +0.239], which would fail to exclude zero for very
nearly any true effect size. **A future exam set must be sized to the criteria
it will be judged against.**

---

## 4. The exam dates are not a representative sample

Worth knowing before reading anything above. On the twelve exam cutoffs the
average eligible constituent underperformed SPY by **−0.62% per 5 sessions**.
Over the 484 development cutoffs the same figure is **−0.02%**.

These twelve weeks are ones in which cap-weighted SPY beat the average member
by roughly thirty times the typical margin — the mega-cap concentration of
2022–2026, sampled at twelve points chosen by V1 for reasons that had nothing
to do with this. A balanced long-short spread is neutral to that tilt, which is
why §16-17 required one; every long-only number below is dominated by it.

---

## 5. Deliverable 6 — V1, V2, momentum and the trivial rule, identical dates

One yardstick for all contenders: realised `alpha_5d`. V1's own metric
(directional accuracy on absolute return) has no cross-sectional analogue, so
V1 is re-scored here using the sign of its frozen 1-week action. "Versus SPY"
needs no column because it is inside the target: `alpha_5d` is already the
return in excess of SPY, so a mean of zero *is* the SPY line.

§30's deliverable 6 asks for six contenders. Five are here. **The V2 ranker is
missing because it was never built** — the §14 gate closed on development and
§10 forbids opening it to produce a row for a comparison table.

| contender | mean | 95% CI | hit | p |
|---|---|---|---|---|
| **mom_12_1 long-short** | **+0.00849** | [+0.0034, +0.0210] | 58.3% | 0.136 |
| V2-F long-short | +0.00462 | [−0.0123, +0.0293] | 41.7% | 0.655 |
| A′ mom_5d(−1) long-short | −0.00076 | [−0.0214, +0.0055] | 41.7% | 0.950 |
| V2-F long-only | −0.00202 | [−0.0115, +0.0127] | 41.7% | 0.761 |
| mom_12_1 long-only | −0.00088 | [−0.0053, +0.0069] | 41.7% | 0.805 |
| A′ mom_5d(−1) long-only | −0.00600 | [−0.0147, −0.0040] | 25.0% | 0.389 |
| Always long (equal weight) | −0.00617 | [−0.0094, −0.0009] | 25.0% | 0.005 |
| V1 consensus 1w (acted calls) | +0.01394 | [−0.0017, +0.0218] | 66.7% | 0.070 |

Reading it honestly:

* **12-1 momentum is the best long-short line, at 1.8× V2-F.** Its percentile
  interval excludes zero while its recentred bootstrap p is 0.136 — the two
  disagree because n = 12 with a block length of 4 leaves the resampling
  distribution badly discrete. The conservative reading is the right one: **not
  significant**. It is also one of eight contenders on this table, and by the
  same multiplicity logic §8 applies to V2's own arms, one crossing out of
  eight is unremarkable. The claim is not "momentum works"; the claim is that
  **V2-F did not beat a one-line factor**, which is criterion 5 failing again
  on fresh data.

* **The baseline-selection rule picked the wrong baseline.** §7 chooses the
  reference factor by |mean IC| on development, which selected `mom_5d` at sign
  −1 — a reversal effect that was the strongest thing on development and then
  returned −0.0008 on the exam. The factor with an actual economic prior, 12-1
  momentum, was passed over for having a smaller absolute IC. Had criterion 5
  been measured against 12-1 momentum, V2-F would have failed it by more. This
  is a real weakness in the pre-registration and it is reported as one; the
  rule was **not** changed after the fact.

* **The V1 row cannot carry weight and is included because §30 asks for it.**
  13 of V1's 30 symbols are in V2's universe at all — the other 17 are crypto,
  FX, ETFs or non-members, which is the §2 asset-class problem V2 removed. On
  143 shared (cutoff, symbol) pairs V1 abstained on **80.4%**, leaving 28 acted
  calls spread over 12 dates. Its +1.4% mean with a 66.7% hit rate is the most
  attractive number on the table and it means very little: p = 0.07 on a
  sample that small, on the names V1 was hand-picked around. V1's own report
  already concluded its consensus had no edge, and nothing here revises that.

* **Always-long is significantly negative** (p = 0.005), which is §4's sampling
  tilt, not a finding about the strategy.

---

## 6. Two bugs, both found and both recorded

Full detail in `EXPERIMENT_LOG.md`. Summarised because a study that only
reports its clean runs is not reporting.

**`ret_12_1` was identically NaN for an entire development run.** Its guard
read `len(close) > 253` while the line above capped the frame at 253 rows, so
it never fired. Four of the hundred features were dead, every model was
silently fitted on 96, and `mom_12_1` — the factor that turned out to matter
most in §5 — was never tested. The only symptom was `n=0` in the A′ table.
Fixed, the panel rebuilt, and the whole ladder re-run; run 1 is archived at
`alpha/out/run1_dead_ret_12_1/` so the effect of the fix is checkable rather
than asserted. It moved V2-F from +0.0295 to +0.0318 and flipped criteria 1–3
from fail to pass; criteria 4, 5 and 6 failed in both runs and the verdict is
FAIL in both.

**Eight of the twelve exam dates were not in the panel.** The panel was built
over a 5-session grid anchored at 2016-01-04; the exam dates come from V1 and
know nothing about that grid. Caught by a crash on an empty cross-section
before any exam prediction had been scored, so no exam number was ever seen
under the broken version. Fixed by building over the union; the development set
was unchanged (484 cutoffs, 221,519 rows before and after) so development was
not re-run.

Both are now guarded by tests: `test_no_feature_is_dead_on_a_full_history` and
`test_the_built_panel_covers_every_exam_cutoff`.

---

## 7. Disclosed limitations

Carried from `PREREGISTRATION.md`, and none of them netted out of the numbers
above.

1. **Sector labels are not point-in-time.** Membership is; GICS classification
   is today's, applied backwards. The 2018 Communication Services rebuild moved
   ~two dozen large names at once, so pre-2018-09 cutoffs file some names under
   a sector they were not yet in. Same class of issue as V1's adjusted prices.
2. **Residual survivorship.** Index coverage is 85% in 2016 rising to 100%
   today; the missing 15% is biased toward names later acquired or delisted.
3. **The index change log is Wikipedia's, not S&P's.**
4. **Model B is a pointwise ranker, not LambdaRank.** lightgbm is not installed;
   the implementation regresses onto the per-cutoff percentile rank. It was
   never built here anyway — the gate closed — but any future report must say
   "pointwise ranker", not "LambdaRank was tested".
5. **Prices are auto-adjusted**, same as V1.
6. **The 12-date exam has almost no statistical power** (§3).
7. **The exam dates are not a representative sample of weeks** (§4).

---

## 8. Production status

`alpha/adapter.py` is the §0 output layer. It imports nothing from `validation`
or `app` — asserted by a test — so validation logic is untouched.

It exposes predicted alpha, rank percentile, model evidence and a coarse
ordinal evidence strength. It does **not** expose `target_price` (§24: V1's
price targets lost to "the price will not move" 62% of the time) or any
confidence score (§23: V1's 90–100 confidence band scored 40%). Those fields
are absent from the schema rather than set to null, because a field that exists
is a field a template eventually renders. The §26 cost fields — gross alpha,
net alpha, turnover, cost model — are reserved and unpopulated, so adding costs
later is a change of value rather than a change of schema.

The decision cascade is HOLD-by-default and fails closed at every step:
insufficient evidence → weak alpha → non-extreme rank → non-positive historical
spread → out-of-validated-regime → HOLD. A missing scores file is HOLD. A
missing rank is HOLD. `VALIDATED_REGIMES` is empty, because none has been
validated.

Run over the frozen exam predictions today: **5,899 in, 5,899 HOLD out**,
weight 0, strength NONE. The gates below the first one are exercised by tests
rather than by production, because a gate nobody has watched run is a gate whose
behaviour is unknown.

---

## 9. What this rules out, and what would change the answer

§10 of the pre-registration ruled these out in advance, and they stay ruled
out: adding features or models to rescue a failed gate; re-running the exam
dates after seeing them; relaxing any threshold in §8; reporting a raw p-value
as a pass where the adjusted one fails; switching the headline metric.

What the evidence would actually support doing next, if anything:

* **Fix the exam set before fixing the model.** Twelve dates cannot support the
  criteria they are judged against. A frozen exam of 60+ non-overlapping
  cutoffs, agreed in advance, would make a future §9 verdict mean something.
  This is the highest-value change on the list and it is not a modelling change.
* **Choose the baseline by prior, not by |mean IC|.** The current rule selected
  a factor that led on development and reverted on the exam. A pre-committed
  factor with an economic prior — 12-1 momentum — is a harder and more honest
  bar.
* **Stop asking stock-level features to rank the cross-section.** V2-A vs V2-B
  is a clean, well-powered null over 423 cutoffs: 47 relative and percentile
  features added +0.0001 IC. That question has been answered.
* **Do not fund a regime-conditional edge on this evidence.** The regime that
  the edge preferred inverted between development and exam. That is the single
  most likely thing on this page to be pure sample noise.

The V1 report concluded that its own neural forecaster was a no-op and said so.
This one concludes that its ranker did not beat a one-line momentum factor, and
says so. A negative result is a complete deliverable.
