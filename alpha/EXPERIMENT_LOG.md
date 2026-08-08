# V2 experiment log

Deliverable 4 of §30. Every run that was executed, in the order it happened,
including the ones that were wrong. The point of keeping the wrong ones is that
"we found a bug and fixed it" is only checkable if the numbers from before the
fix are still on the page.

Nothing in `PREREGISTRATION.md` has been edited since it was written on
2026-08-08, before any model was fitted. Where a result misses a pre-registered
threshold it is recorded as a miss and reported against the original threshold.

---

## Run 0 — panel build (2026-08-08 01:27)

`python -m alpha.build_panel`. 245,098 rows, 100 features, 532 cutoffs
(484 development + 12 exam), 2016-01-04 .. 2026-07-28. ~172 s.

Frozen to `alpha/out/panel.pkl`, metadata in `panel_meta.json`.

---

## Run 1 — development ladder, first execution

`python -m alpha.develop`. Archived in full at
`alpha/out/run1_dead_ret_12_1/` (json, pickle, log, panel metadata).

**This run is superseded.** It is kept because it is where the bug below was
found, and because its numbers are the control for the claim that fixing the
bug was not a results-driven change.

### Model A′ — the six simple factors

| factor | mean IC | hit rate | n |
|---|---|---|---|
| mom_5d | −0.00955 | 49.6% | 484 |
| mom_20d | −0.00848 | 50.6% | 484 |
| mom_60d | −0.00898 | 50.2% | 484 |
| mom_12_1 | **nan** | **nan** | **0** |
| rs_vs_spy_20d | −0.00848 | 50.6% | 484 |
| rs_vs_sector_20d | −0.00462 | 52.1% | 484 |

All five live factors have **negative** mean IC against 5-session excess
return. At this horizon the cross-section is a short-term *reversal* effect,
not a momentum effect. The pre-registration anticipated this possibility by
fixing the sign on development data (§7); the frozen baseline came out as
`mom_5d` with sign **−1**, i.e. buy last week's losers, mean IC +0.00955.

### The bug: `mom_12_1` returned n = 0

`features.absolute_block` computed `ret_12_1` behind `if len(close) > 253`,
while the line above it sliced the frame to `close = view.close.iloc[-DEEPEST:]`
with `DEEPEST = 253`. The guard therefore could never fire. `ret_12_1` was
identically NaN at every cutoff for every symbol, and so were the three columns
derived from it (`ret_12_1__vs_spy`, `__vs_sector`, `__pct`).

Consequences, all silent:

* 4 of the 100 features were dead. All-NaN columns are dropped at fit time (a
  deliberate choice — imputing a cross-sectional mean would leak), so every
  model in run 1 was fitted on 96 features while reporting 100.
* 12-1 momentum — the classic cross-sectional momentum factor and the one A′
  baseline that is not a short-horizon effect — was never actually tested.
* Nothing raised. The only visible symptom was `n=0` in the A′ table.

Found by reading that `n=0`. Fixed in `features.py` by tying the guard to the
same constant as the slice (`len(close) >= DEEPEST`, indexing `close.iloc[-DEEPEST]`).

**Why this is a correctness fix and not a threshold move.** It restores a
pre-registered feature that was supposed to be there and never was; it changes
no threshold, no metric, no target and no gate. The direction of its effect on
the results was unknown when it was made, and run 1's numbers are archived so
the effect is checkable in both directions rather than asserted.

Guarded going forward by `test_no_feature_is_dead_on_a_full_history` in
`app/tests/test_alpha.py`, which fails if any feature column is NaN for every
symbol on a view with 900 bars of history behind it.

### Run 1 results (superseded, 423 evaluated cutoffs, baseline A′ mom_5d(−1))

| experiment | features | mean IC | 95% block-bootstrap CI | hit | spread | vs A′ | verdict |
|---|---|---|---|---|---|---|---|
| V2-A absolute | 18 | +0.00850 | [−0.0026, +0.0199] | 51.5% | +0.00104 | −0.00265 | FAIL |
| V2-B + relative | 65 | +0.00740 | [−0.0057, +0.0202] | 51.1% | +0.00096 | −0.00374 | FAIL |
| V2-E + context | 100 | +0.02627 | [+0.0081, +0.0461] | — | — | +0.01512 | FAIL |
| V2-F vol-scaled target | 100 | +0.02949 | [+0.0121, +0.0479] | 56.0% | +0.00265 | +0.01835 | FAIL |

Holm–Bonferroni across the four: V2-F p = 0.0032, V2-E p = 0.0189 (both
significant); V2-A and V2-B not significant.

The §14 gate on the ranker is written against **V2-A or V2-B** specifically.
Both failed criteria 1–5, so the gate closed and **V2-C and V2-D were not
built** — not built and caveated, not built.

---

## Run 2 — development ladder, after the `ret_12_1` fix

Panel rebuilt 2026-08-08 (`python -m alpha.build_panel`, 245,098 rows, 100
features, ~172 s), then `python -m alpha.develop`. This is the run of record
for development.

### Model A′ — now with all six factors alive

| factor | mean IC | hit rate | n |
|---|---|---|---|
| mom_5d | −0.00955 | 49.6% | 484 |
| mom_20d | −0.00848 | 50.6% | 484 |
| mom_60d | −0.00898 | 50.2% | 484 |
| **mom_12_1** | **+0.00599** | **53.1%** | **484** |
| rs_vs_spy_20d | −0.00848 | 50.6% | 484 |
| rs_vs_sector_20d | −0.00462 | 52.1% | 484 |

12-1 momentum is the only factor of the six with a *positive* mean IC against
5-session excess return, and every short-horizon factor is negative. That is
the standard cross-sectional picture — momentum over a year, reversal over a
week — and it was invisible in run 1 because the momentum factor was the dead
column. It changes no conclusion, because the frozen baseline is chosen by
**|mean IC|** and 0.00955 > 0.00599: the baseline is still `mom_5d` at sign
**−1**, unchanged from run 1, so criterion 5 is directly comparable across both
runs.

### Run 2 results (423 evaluated cutoffs, baseline A′ mom_5d(−1))

| experiment | features | mean IC | 95% CI | hit | spread | spread CI | vs A′ | verdict |
|---|---|---|---|---|---|---|---|---|
| V2-A absolute | 18 | +0.00837 | [−0.0017, +0.0191] | 50.8% | +0.00118 | [−0.0002, +0.0026] | −0.00278 | FAIL |
| V2-B + relative | 65 | +0.00846 | [−0.0040, +0.0210] | 51.3% | +0.00090 | [−0.0007, +0.0025] | −0.00268 | FAIL |
| V2-E + context | 100 | +0.02381 | [+0.0056, +0.0445] | 53.4% | +0.00210 | [−0.0002, +0.0045] | +0.01267 | FAIL |
| V2-F vol-scaled target | 100 | +0.03179 | [+0.0140, +0.0507] | 57.0% | +0.00257 | [+0.0004, +0.0047] | +0.02064 | FAIL |

Holm–Bonferroni across the four: V2-F p = 0.0032, V2-E p = 0.0477 (both
significant); V2-A p = 0.233, V2-B p = 0.233 (not).

Criterion-by-criterion for V2-F, the best arm:

| # | criterion | value | threshold | verdict |
|---|---|---|---|---|
| 1 | mean Spearman IC | +0.03179, CI [+0.0140, +0.0507] | > 0.03, CI excludes 0 | **pass** |
| 2 | IC hit rate | 56.97%, CI [0.525, 0.619] | > 55%, CI excludes 50% | **pass** |
| 3 | top−bottom spread | +0.00257, CI [+0.0004, +0.0047] | > 0, CI excludes 0 | **pass** |
| 4 | sign stability | 57.0% | ≥ 60% | fail |
| 5 | beats best simple factor | +0.02064, CI [−0.0029, +0.0455] | CI excludes 0 | **fail** |
| 6 | no regime collapse | SIDEWAYS −0.0205 | > 0 in every regime | fail |
| 7 | effective sample | 423 cutoffs | ≥ 50 | pass |

**Effect of the fix.** V2-F moved from +0.02949 to +0.03179 and crossed the
pre-registered 0.03 line; criteria 1, 2 and 3 went from fail to pass. Criteria
4, 5 and 6 failed in both runs, and the overall verdict is FAIL in both. The
fix changed how *close* the result is, not what it is.

**The §14 gate stayed closed.** It is written against V2-A or V2-B, and both
failed criteria 1–5 in both runs. V2-C and V2-D were **not built**. The
temptation here is obvious — V2-E and V2-F did clear parts of the bar, so
widening the gate to "any arm" would open the ranker — and that is precisely
the move §10 rules out in advance. The gate was left as written.

### Where the signal actually lives

V2-A and V2-B are indistinguishable from zero. Everything the model has comes
from the **context tier** (§10-12): regime state, VIX, index breadth, and the
overnight/intraday decomposition. Adding relative and percentile features to
absolute ones bought nothing at all (+0.00837 → +0.00846). That is a direct
answer to §7-8's question and it points the opposite way from the usual
assumption: on this universe and horizon, cross-sectional *stock* features
carry no rank information, and what little there is comes from knowing what
kind of week the market is having.

The regime table says the same thing from the other side. V2-F's IC is +0.081
in BEAR_TREND, +0.030 in BULL_TREND and **−0.021 in SIDEWAYS**. A model whose
edge is conditional on the regime, and inverted in one of them, is not a
ranking model with a regime tilt; it is a regime bet wearing a ranking model.

---

## Run 3 — the exam paper, opened once (2026-08-08)

### A second bug, found before any exam number existed

`alpha.exam predict` crashed on an empty cross-section. `build_panel` built the
panel over `dataset.schedule(book)` — every 5th session from 2016-01-04 — while
the twelve exam dates come from V1 and know nothing about that grid. **Eight of
the twelve were not in the panel at all**; the four that were had landed on it
by coincidence.

Fixed by building over `schedule ∪ exam` (`build_panel.panel_cutoffs`). The
development set is defined by the schedule alone and did not change: 484
cutoffs and 221,519 rows before and after, so run 2's development record stands
and was not re-run.

Found by a crash, before a single exam prediction had been scored, so no exam
number was ever seen under the broken version. Guarded by
`test_the_built_panel_covers_every_exam_cutoff`.

### The run

`python -m alpha.exam predict` then `python -m alpha.exam score`, as two
processes. Configuration read from `development.json`, not chosen here: V2-F,
100 features, `target_vol_scaled`, baseline `mom_5d` at sign −1. 5,899
predictions over 12 cutoffs, 7 refits, training on development cutoffs only.

**Note on running the exam at all.** V2-F had already failed its development
verdict, and §10 says a failed gate is where you stop. The exam was still run
once, because §19 built it to be opened exactly once after development closes
and deliverable 6 needs V1 and V2 measured on identical dates. It is reported
as a measurement, not as a second chance: nothing was reconfigured after seeing
development, and nothing will be reconfigured after seeing this.

### Exam results — V2-F, 12 cutoffs

| statistic | mean | 95% block-bootstrap CI | hit rate | p |
|---|---|---|---|---|
| Spearman IC | +0.05769 | [−0.0633, +0.2389] | 58.3% | 0.498 |
| top−bottom spread | +0.00462 | [−0.0123, +0.0293] | 41.7% | 0.655 |
| IC − A′ mom_5d(−1) | +0.06979 | [−0.0916, +0.3988] | **33.3%** | 0.635 |

Baseline A′ on the same dates: mean IC −0.01209, hit rate 41.7%.

All seven criteria fail. Per-cutoff:

| cutoff | IC | spread | regime |
|---|---|---|---|
| 2022-03-08 | +0.2719 | +0.0322 | SIDEWAYS / HIGH_VOL |
| 2022-10-10 | +0.0400 | −0.0058 | BEAR_TREND / HIGH_VOL |
| 2024-08-13 | −0.1973 | −0.0138 | BULL_TREND / HIGH_VOL |
| 2024-09-05 | −0.1280 | −0.0146 | BULL_TREND / HIGH_VOL |
| 2024-12-10 | +0.0620 | +0.0063 | BULL_TREND / LOW_VOL |
| 2025-03-27 | **+0.6292** | +0.0944 | SIDEWAYS / HIGH_VOL |
| 2025-06-23 | **+0.4036** | +0.0381 | SIDEWAYS / HIGH_VOL |
| 2025-11-28 | +0.0015 | −0.0069 | BULL_TREND / LOW_VOL |
| 2026-02-06 | −0.1493 | −0.0228 | BULL_TREND / HIGH_VOL |
| 2026-05-07 | −0.0759 | −0.0267 | BULL_TREND / LOW_VOL |
| 2026-07-07 | +0.0393 | +0.0117 | BULL_TREND / LOW_VOL |
| 2026-07-24 | −0.2046 | −0.0366 | BULL_TREND / HIGH_VOL |

**Read the mean against the hit rate before believing it.** Mean IC +0.058
sounds like a result. It is two dates: 2025-03-27 (+0.63) and 2025-06-23
(+0.40), both SIDEWAYS/HIGH_VOL. Drop them and the remaining ten average
**−0.0340**. The quintile spread was positive on 5 of 12 dates, and the model beat
the simple reversal factor on **4 of 12** — a mean of +0.070 produced by a
minority of dates pulling hard. This is the same shape as the V1 finding that
30 symbols on one date are not 30 draws, moved to the time axis.

The regime story from development also **inverted**: development had the edge
in BEAR_TREND (+0.081) and negative in SIDEWAYS (−0.021); the exam has it
+0.435 in SIDEWAYS and −0.082 in BULL_TREND. A conditional edge that swaps
which condition it likes between two disjoint samples is noise with a story
attached.

### Criterion 7 cannot pass, and that is a defect in the pre-registration

§8 criterion 7 requires ≥ 50 independent cutoffs. The exam paper is 12 dates,
fixed by V1 and not extendable without un-freezing it. So criterion 7 fails on
this set by construction, and §9's "all seven on the exam set" holds production
weight at 0 no matter what the other six say.

Recorded as a defect rather than dropped or redefined. It is also academic
here: criteria 1–6 fail on their own terms. But a future exam set should be
sized to the criteria it will be judged against, and 12 dates gives a block
bootstrap almost no power — the IC interval on this run spans [−0.063, +0.239],
which would fail to exclude zero for very nearly any true effect size.

---

## Status against §27

| ID | state |
|---|---|
| V2-A | run, FAIL |
| V2-B | run, FAIL |
| V2-C | **not built** — gate closed (A and B both failed criteria 1–5 on dev) |
| V2-D | **not built** — depends on V2-C |
| V2-E | run, FAIL |
| V2-F | run, FAIL on dev; taken to the exam; FAIL on exam |
| V2-G | **not built** — §9 not satisfied; production weight is 0 |
