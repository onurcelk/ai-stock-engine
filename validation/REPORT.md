# Historical Forecast Validation — Point-in-Time Backtest

**Study run:** 2026-08-07 · **Last bar available:** 2026-08-07
**Frozen predictions:** 360 (30 symbols × 12 historical cutoffs), plus 96 neural-forecast experiments · **Scored rows:** 20,999
**Harness:** `validation/` · **Raw output:** `validation/out/report_raw.txt`, `validation/out/calls.csv`

---

## 1. Executive summary

The system was run as if it were twelve different days in the past, on thirty
symbols, with no access to any bar after the date being simulated. Its
predictions were written to disk before any outcome was read. This report scores
them.

**The finding: no component demonstrated predictive value beyond a trivial rule,
and one component was measurably worse than a coin flip.**

| Claim | Verdict |
|---|---|
| The consensus indicator predicts direction better than chance | **Not demonstrated.** 53.7% on the bars it leaned (95% CI 40.6–66.8, p = 0.54) |
| ...better than simply assuming "up" | **No.** −8.2 points against always-long on identical rows (p = 0.38) |
| Its confidence means something | **No.** Accuracy is non-monotonic in confidence; the 90–100% band went 2 for 5 |
| Its price targets beat "price won't move" | **No.** MAPE 5.59% vs the no-change forecast's 5.59%; it wins 38% of the time |
| Its expected-return numbers carry information | **No.** Correlation with realised return −0.004; the magnitudes are ~8× too small |
| The 4-hour horizon predicts direction | **It predicts the opposite**, at least overnight. 27.8% overall, 20.8% on calls it told you to act on (p = 0.009) — see the gap caveat in §8 |
| The trading agents add value | **No.** Best agent 56.9% (p = 0.077), and −0.16 points/week vs just being long |
| The LSTM forecast predicts direction | **Not demonstrated.** 59.4% (n = 96, p = 0.25) — but it says "up" 72% of the time and always-long scored 64.6% on the same rows |
| The LSTM's price path is usable | **No.** MAPE 11.5% against the no-change forecast's 3.8%; median predicted 5-day move 8.7% against a realised 2.6% |
| The neural forecast adds value to the consensus | **No — it contributed exactly zero.** Gated out of all 257 horizon-slots across 96 experiments; not one action or score changed |
| The system knows when it doesn't know | **Yes.** It abstained on 74.3% of symbol-dates, which on this evidence was the correct output |

The last row is the one genuinely positive result, and it is not a small one.
`ultimate.py` is built to say HOLD when nothing clears significance, and this
study is what that machinery was protecting against: on 456 point-in-time
predictions, the sources it declined to trust were in fact not worth trusting —
most sharply the neural forecaster, which it gated out 257 times out of 257 and
which then went on to lose to always-long. The system's caution is calibrated
even though its confidence is not.

**What this study cannot say:** twelve cutoffs is twelve effectively
independent market draws. Every interval here is wide enough to contain both
"no skill" and "modest skill." The honest reading is *not proven to work*,
which is different from *proven not to work* — except for the 4-hour horizon
read after the close, where the interval sits below 50% and the evidence of
active harm is the strongest single result in the study.

The one result that does not depend on sample size is the last row but one:
the neural forecast changed **zero** verdicts, and that is a count, not an
estimate.

---

## 2. Methodology

### The simulation

For each historical cutoff date *T*, the system's world was truncated at *T*:

* `pit.fetcher(T)` reads the local bar cache, drops every row after *T*, and
  only then applies the lookback trim — so a "10y" request at a 2022 cutoff
  returns the ten years ending in 2022, which is what production would have
  had, rather than the ten years ending today with a hole cut in it.
* The **production code paths run unmodified**: `ultimate.evaluate()`,
  `forecast.walk_forward()`, `forecast.project()`, `ultimate.agent_sources()`.
  Nothing was reimplemented for the study and no hyperparameter was retuned;
  the LSTM settings are the ones hard-coded in `streamlit_app.py` (LSTM, 3
  folds, 30 epochs, 64 units, 5-bar horizon, 1,250 bars).
* Every indicator, calibration, scaler and agent window is therefore computed
  from pre-*T* bars alone, because that is all any of them was handed.

### Why the no-look-ahead claim is testable rather than asserted

Three mechanisms, described in `validation/README.md`:

1. **One data door.** The prediction stage has exactly one way to read prices.
2. **Two processes.** `predict.py` writes `out/predictions.json` and never
   reads it back; `score.py` reads it and never writes it; re-running stage 1
   over an existing file is refused. No prediction can be revised after its
   outcome is known, because the code that sees outcomes cannot reach the code
   that makes predictions.
3. **A test that fails if it leaks.**
   `app/tests/test_validation.py::test_future_cannot_change_the_verdict` builds
   two price series identical up to the cutoff and violently different after
   it, and asserts both produce the same verdict to the last decimal. It
   passes. So does the rest of the suite (410 passed, 60 skipped).

### Statistics

Thirty symbols read on one day are **not** thirty independent observations —
on 2022-03-08 nearly every name was being scored against the same index move.
Every interval in this report is therefore **clustered by cutoff date**: the
point estimate is the plain mean, the standard error counts the twelve dates.
Naive binomial intervals are 2–6× narrower and are shown alongside in
`report_raw.txt` so the difference is visible rather than claimed.

Comparisons against baselines are **paired on identical rows**, so the common
market move cancels rather than adding noise to both sides.

### Scoring windows

Every system is scored at its **own** horizon and, separately, at all others.
The distinction matters more than usual here: **this system has no six-month
forecast.** Its longest native horizon is one week. Section 8 reports the
six-month outcomes the procedure asked for, but they measure what happens when
a one-week call is held for six months, not a six-month prediction.

---

## 3. Historical test dates

Four named dates from the procedure, plus eight drawn at random (seed 20260807)
from the window where five years of prior history and a full six-month outcome
both exist — 2021-08-08 onward, ending 126 sessions before the last bar.

| Cutoff | Kind | Market context (SPY, next week) | Symbols up, next week |
|---|---|---|---|
| 2022-03-08 | random | +2.38% | 50% |
| 2022-10-10 | random | +1.89% | 65% |
| 2024-08-13 | random | +3.07% | 85% |
| 2024-09-05 | random | +1.72% | 73% |
| 2024-12-10 | random | +0.25% | 70% |
| 2025-03-27 | random | −5.36% | 7% |
| 2025-06-23 | random | +2.95% | 82% |
| 2025-11-28 | random | +0.34% | 75% |
| 2026-02-06 | **6 months ago** | −1.28% | 32% |
| 2026-05-07 | **3 months ago** | +2.27% | 71% |
| 2026-07-07 | **1 month ago** | +0.55% | 50% |
| 2026-07-24 | **2 weeks ago** | +1.10% | 43% |

Two cutoffs (2022-03-08, 2022-10-10) sit inside the 2022 bear market and one
(2025-03-27) immediately precedes a 5% weekly drawdown, so the sample is not
purely a bull-market study — but ten of the twelve following weeks were up, and
that asymmetry is why every comparison below is paired against always-long.

The universe is the 30 symbols in the local cache: 22 single names, 4 funds
(SPY, QQQ, VOO, SLV), 2 crypto pairs, 1 FX pair, plus a few recent listings
(CBRS, SPCX, SNDK, NBIS) that the engine correctly declined to read at the
older cutoffs.

---

## 4. Information available at each cutoff

Recorded per experiment in `out/predictions.json` under `information_set`.

| | |
|---|---|
| Daily bars | up to 10 years ending at the cutoff — 2,514 for the deepest names, fewer for recent listings |
| Hourly bars | up to 2 years ending at the cutoff, **and only for cutoffs after 2024-08** — Yahoo serves ~730 days of intraday history, so the six earliest cutoffs have none |
| Columns | date, close, open, high, low, volume (close-only for the FX pair) |
| Not available to the system, and not used | news, sentiment, fundamentals, analyst revisions, earnings dates, macro releases — this engine reads price and volume only |

Scoreable coverage after outcomes were revealed:

| Window | 4 h | 1 d | 1 w | 1 m | 3 m | 6 m |
|---|---|---|---|---|---|---|
| Symbol-dates | 262 | 331 | 331 | 301 | 271 | 218 |

### Residual look-ahead, disclosed rather than hidden

1. **Adjusted prices.** The cache holds split- and dividend-adjusted bars, so
   an adjustment made after a cutoff is baked into the level before it. Splits
   are a pure rescaling and leave returns untouched; dividend adjustment shifts
   historical returns by the yield — small for this universe, not removable
   without re-downloading unadjusted history.
2. **Universe selection.** These are symbols a live user chose to watch *today*.
   Nothing that delisted or that nobody kept watching is in the sample.
3. **Intraday depth.** A 2026-02 cutoff has ~18 months of hourly bars where
   production would have had 24. The engine reports the shortfall as an
   unavailable horizon; nothing is interpolated.

None of these can be repaired inside this harness, and all three would have to
be fixed before a *positive* result could be believed. They do not undermine
the negative results below, which are the ones this study actually produced.

---

## 5. Original Forecast predictions (Step 2)

The consensus verdict from `ultimate.evaluate()` was recorded in full for all
360 experiments: action, score, confidence, alignment, agreement, coverage,
weighted edge, expected move, target price, and every source's reading with its
measured hit rate, effective sample size, t-statistic and weight — including
the sources that were weighted at zero and why.

The headline shape of what it produced:

| | |
|---|---|
| Named a direction (score ≠ 0) | 134 of 331 scoreable symbol-dates — **40.5%** |
| Told the user to act (not HOLD) | 85 — **25.7%** |
| Stayed HOLD | **74.3%** |
| Split of actionable calls | 51.5% bullish / 48.5% bearish |
| Median predicted move, when it leaned | 0.33% over a week |

The 4-hour horizon was readable on 211 symbol-dates and leaned on 36; the
1-day horizon leaned on 95 of 318; the 1-week horizon on 62 of 316.

### The neural forecaster

Run separately on 8 symbols (SPY, QQQ, AAPL, MSFT, NVDA, AMZN, TSLA, BTC-USD)
at all 12 cutoffs — 96 experiments, ~45 s each — because it costs a full
training run per prediction. Settings are production's, untouched: LSTM, 3
walk-forward folds, 30 epochs, 64 units, 5-bar horizon, 1,250 daily bars.

Each experiment produced both halves the app produces:

* a **projection** past the cutoff — the prediction, with no accuracy attached;
* a **walk-forward** over the pre-cutoff series — three rolling-origin folds it
  never trained on, which is the only track record available at prediction
  time and the number `ModelEvidence` weights it by.

What it predicted, before any outcome was known:

| | |
|---|---|
| Direction "up" | **72% of 96 experiments** |
| Mean predicted 5-day move | **+7.70%** (median +6.26%, range −20.7% to **+69.2%**) |
| Walk-forward directional accuracy | mean **49.9%**, median 50.0%, range 20–80% |
| Runs whose walk-forward beat a coin flip | 48 of 96 |
| Folds beating the naive "no change" forecast | **36 of 288** |
| Mean walk-forward accuracy vs naive | 89.60% vs **96.76%** |

The last three rows are the important ones, and they were visible *at
prediction time* without any knowledge of the future: on its own held-out
folds, this model was a coin flip on direction and lost to assuming no change
on level, in 87% of folds. Everything in section 8 follows from that.

---

## 6. Original Agent predictions (Step 3)

Three rule-based agents, read through `ultimate.agent_sources()` — the same
objects the app folds into its verdict — each reporting the standing position
implied by its last signal, with the window it was given (sized from the
pre-cutoff series length) and the date it last flipped.

| Agent | Long at cutoff | Never abstains |
|---|---|---|
| Turtle (channel breakout, faded) | 28.3% | yes |
| MA crossover | 55.4% | yes |
| Signal rolling (momentum flip) | 58.5% | yes |
| **Combined (majority vote)** | 46.8% | yes |

Two things the agents structurally cannot supply, recorded as unavailable
rather than estimated (validation rule 10):

* **a price target** — they emit a position, not a level;
* **an expected return** — they carry no magnitude at all.

Their "confidence" is likewise undefined, so they are absent from the
calibration analysis in section 11.

---

## 7. Actual subsequent market outcomes (Step 4)

Revealed only after `predictions.json` was written. Across all scoreable rows:

| Window | n | Mean return | Median \|return\| | Share that rose |
|---|---|---|---|---|
| 4 hours | 262 | +0.02% | 1.59% | **49.2%** |
| 1 day | 331 | +0.36% | 1.89% | **50.5%** |
| 1 week | 331 | +1.99% | 3.34% | **58.3%** |
| 1 month | 301 | +5.75% | 7.59% | **59.1%** |
| 3 months | 271 | +19.99% | 13.74% | **65.7%** |
| 6 months | 218 | +45.16% | 24.17% | **70.6%** |

The rising base rate is the single most important fact for interpreting every
accuracy number below: a system that simply said "up" every time would have
scored 58% at one week and 71% at six months. **That is the bar, not 50%** —
and it is why every comparison in section 15 is paired against always-long
rather than against chance.

Note the two shortest windows are genuine coin flips (49.2% and 50.5%), which
makes the 4-hour result in section 8 harder to explain away as a drift effect:
there was no drift to be on the wrong side of.

---

## 8. Forecast vs actual (Steps 5 and 12) — directional accuracy

At each system's own horizon, scored on the bars where it named a direction.
Intervals are clustered by cutoff date.

| System | Leaned | of | Coverage | Accuracy | 95% CI | p vs 50% |
|---|---|---|---|---|---|---|
| Consensus (aggregate) | 134 | 331 | 40.5% | **53.7%** | [40.6, 66.8] | 0.543 |
| Consensus — 4 hours | 36 | 211 | 17.1% | **27.8%** | [4.8, 50.7] | 0.056 |
| Consensus — 1 day | 95 | 318 | 29.9% | **50.5%** | [30.1, 71.0] | 0.956 |
| Consensus — 1 week | 62 | 316 | 19.6% | **56.5%** | [43.1, 69.8] | 0.310 |
| Turtle agent | 325 | 325 | 100% | 44.6% | [33.2, 56.0] | 0.320 |
| MA crossover agent | 325 | 325 | 100% | **56.9%** | [49.1, 64.7] | 0.077 |
| Signal rolling agent | 325 | 325 | 100% | 50.2% | [43.1, 57.2] | 0.963 |
| Combined agents | 325 | 325 | 100% | 50.2% | [46.0, 54.3] | 0.936 |
| **LSTM forecast** | 96 | 96 | 100% | **59.4%** | [42.4, 76.3] | 0.250 |

Restricted to calls the system actually told a user to act on:

| System | Acted | Accuracy | 95% CI | p |
|---|---|---|---|---|
| Consensus | 85 | **61.2%** | [49.6, 72.7] | 0.056 |
| Consensus — 4 hours | 24 | **20.8%** | [1.6, 40.0] | **0.009** |
| Consensus — 1 day | 47 | 51.1% | [24.0, 78.2] | 0.933 |
| Consensus — 1 week | 48 | 54.2% | [39.0, 69.3] | 0.557 |

Two readings deserve emphasis.

**The consensus's actionable calls hit 61.2%, and that is the study's most
favourable number for the system.** It is also not significant at the 5% level
once the correlation between symbols is accounted for (p = 0.056), it rests on
85 calls across 12 dates, and — decisively — it does not survive section 15's
comparison against always-long.

**The 4-hour horizon is inverted.** 27.8% overall and 20.8% on the calls it
promoted to BUY/SELL. Its two 100%-confidence STRONG SELL calls (SPY and VOO on
2024-12-10) were both followed by a +0.9% four-hour rise. This is not a wide
interval around 50%; it is a narrow interval well below it, and it is the
strongest single result in the study.

> **Caveat, and it is a real one.** Cutoffs are chosen at daily granularity, so
> the last hourly bar before one is always a session close and **every 4-hour
> window in this study straddles an overnight gap** — 80 of 262 of them a full
> weekend. Measured: the median absolute gap is 1.29% against a median absolute
> 4-bar move of 1.59%, so **the gap is 77% of the move and its sign matches the
> window's 82% of the time.** What was tested is therefore "the 4-hour call as
> read after the close", which is a common way to use the product but is not a
> random intraday sample. The engine calibrates that horizon on all hourly
> bars, most of which are intraday. The result should be read as *this horizon
> is inverted overnight*, not *at every hour of the day* — and the fix in §20 is
> written accordingly.

### Held past its own horizon (the six-month question)

The procedure asked for six-month comparisons. The system has no six-month
forecast, so what follows is what happens if you hold its one-week call for
longer. `*` marks p < 0.05, clustered.

| System | 1 d | 1 w | 1 m | 3 m | 6 m |
|---|---|---|---|---|---|
| Consensus | 46% (134) | 54% (134) | 44% (122) | 49% (111) | 60% (84) |
| Consensus 4 h | 33%* (36) | 56% (36) | 47% (30) | 43% (28) | 47% (19) |
| Consensus 1 d | 51% (95) | 55% (95) | 45% (88) | 54% (82) | 60% (65) |
| Consensus 1 w | 50% (62) | 56% (62) | 39% (57) | 52% (52) | 66%* (38) |
| Combined agents | 51% (324) | 50% (325) | 46% (297) | 53% (269) | 50% (216) |
| LSTM forecast | 43% (96) | 59% (96) | 59% (88) | 59% (80) | 52% (65) |
| **Always long** | 51% (324) | **59% (325)** | **59% (297)** | **66% (269)** | **70% (216)** |

The one starred positive — the 1-week horizon reading 66% at six months — is
almost certainly the tape: always-long scored 70% on the same rows. Accuracy
that *rises* with holding period on a system whose horizon is five days is a
measurement of the market's drift, not of the model.

---

## 9. Agent vs actual (Step 5, agents)

| Agent | Accuracy (1 w) | Return from taking its side | Bullish share | Actual up-share |
|---|---|---|---|---|
| Turtle | 44.6% | **−1.42%/week** | 28.3% | 59.1% |
| MA crossover | 56.9% | **+1.98%/week** (p = 0.016) | 55.4% | 59.1% |
| Signal rolling | 50.2% | +0.12%/week | 58.5% | 59.1% |
| Combined | 50.2% | −0.02%/week | 46.8% | 59.1% |

The MA crossover agent is the only component in the whole study with a
positive, nominally significant weekly return. Section 15 explains why that is
not evidence of skill: it is long 55% of the time in a market that rose, and
against a permanent long on the same rows it is **−0.16 points/week (p = 0.88)**
— i.e. indistinguishable from just holding, with the extra trading.

The turtle agent is the mirror image: it is the notebook's *fading* variant, so
it is short most of the time (28.3% long) in a rising market, and it loses
1.42%/week. Both are measuring the drift, in opposite directions.

---

### The LSTM against actual

96 experiments, all scoreable, no abstentions.

| | |
|---|---|
| Directional accuracy at 5 days | **59.4%** [42.4, 76.3], p = 0.250 |
| Always-long on the same 96 rows | **64.6%** |
| Paired difference | **−5.2 points** [−21.3, 10.8], p = 0.490 |
| Bullish share of its calls | **71.9%** |
| Accuracy when bullish / bearish | 66.7% / **40.7%** |
| Return from taking its side, per week | +0.44% against +1.44% for holding (−1.00 pts, p = 0.236) |
| At the 1-day window | **43%** (n = 96) |
| At the 4-hour window | **38%** (n = 80) |

The 59.4% looks like the best directional number in the study and is not one.
It says "up" nearly three times in four; the rows it was scored on rose 64.6%
of the time; and against a permanent long on those identical rows it is 5.2
points **behind**. Its bullish calls are right two-thirds of the time and its
bearish calls four-tenths — the signature of a model that has learned the drift
and adds nothing to it. Held one day rather than five it drops to 43%, below
chance.

### The LSTM's price path

| | n | MAE $ | MAPE | Median APE | Signed bias | No-change MAPE | Beats no-change |
|---|---|---|---|---|---|---|---|
| LSTM, 5 bars | 96 | 1046.67 | **11.48%** | 8.71% | **+6.50%** | **3.77%** | **23%** |

| | Mean predicted | Mean actual | Mean \|error\| | corr | Median \|pred\| | Median \|actual\| | Size ratio |
|---|---|---|---|---|---|---|---|
| LSTM | +7.70% | +1.44% | 11.59 pts | **−0.073** | 8.71% | 2.65% | **3.29×** |

The forecaster's price path is **three times worse than assuming the price will
not move**, and it beats that null in fewer than a quarter of experiments. Its
error is systematically positive (+6.5%): it over-predicts the level. Where the
consensus under-states moves by ~8×, the LSTM over-states them by ~3.3×, and
its predicted magnitude correlates −0.07 with what happened. Its single largest
projection was **+69.2% over five trading days**.

This is the most concrete finding for a user: **the projected price line in the
forecast tab should not be read as a price.**

---

## 10. Forecast vs Agent (Step 6)

| Comparison | n | Left | Right | Difference | 95% CI | p |
|---|---|---|---|---|---|---|
| Consensus vs combined agents | 133 | 53.4% | 52.6% | +0.8 pts | [−16.9, 18.4] | 0.927 |
| Consensus vs MA crossover | 133 | 53.4% | 59.4% | −6.0 pts | [−15.3, 3.3] | 0.184 |
| LSTM vs consensus | 49 | 61.2% | 51.0% | +10.2 pts | [−13.0, 33.5] | 0.355 |
| Consensus **with** the LSTM vs without | 96 | — | — | **exactly 0** | — | — |

No difference is distinguishable from zero, and the last row is not an
approximation.

### The combined system: what folding the forecast in actually changed

| | |
|---|---|
| Paired verdicts compared | 96 |
| Actions changed | **0** |
| Scores changed | **0** |
| Horizon-slots where the model carried any weight | **0 of 257** |

`ModelEvidence` weights the forecaster by its own walk-forward directional edge
and drops it when that edge sits inside its own noise. Across 96 experiments
and 257 horizon-slots the gate fired **every single time** — mean walk-forward
directional accuracy was 49.9%, so there was no edge to weight. The
"Include the forecast" toggle costs about a minute of training per symbol and,
on this evidence, is guaranteed not to move a number.

This is the engine working exactly as designed. `ultimate.py`'s docstring says
"this repo's walk-forward found the LSTM below a coin flip on direction"; this
study measured 49.9% across 288 independent folds and 59.4% on 96 genuine
out-of-sample predictions that lose to always-long. The gate was right.

The one caveat worth flagging: because `consensus_with_model` is identical to
`consensus`, it doubles as a read of the consensus on the 8-symbol megacap and
index subset — and there it is **−22.4 points against always-long (n = 49,
p = 0.017)**, the only significant underperformance of a trivial rule in the
study. On the large, liquid names the consensus was measurably worse than
holding.

Per experiment (share of that date's leaned calls that were right):

| Cutoff | SPY next week | Consensus | Combined agents |
|---|---|---|---|
| 2022-03-08 | +2.38% | 45% (11) | 38% (26) |
| 2022-10-10 | +1.89% | **10% (10)** | 54% (26) |
| 2024-08-13 | +3.07% | 67% (9) | 54% (26) |
| 2024-09-05 | +1.72% | 62% (8) | 46% (26) |
| 2024-12-10 | +0.25% | 30% (10) | 50% (26) |
| 2025-03-27 | −5.36% | 50% (12) | 59% (27) |
| 2025-06-23 | +2.95% | 33% (9) | 50% (28) |
| 2025-11-28 | +0.34% | **86% (14)** | 39% (28) |
| 2026-02-06 | −1.28% | 50% (14) | 54% (28) |
| 2026-05-07 | +2.27% | 64% (14) | 54% (28) |
| 2026-07-07 | +0.55% | 73% (11) | 46% (28) |
| 2026-07-24 | +1.10% | 58% (12) | 57% (28) |

The spread from 10% to 86% across dates, on samples of 8–14, is exactly the
between-cluster variance that makes the naive ±8.5-point interval on the pooled
figure a fiction and the clustered ±13-point interval the real one.

### SPY, in the shape the procedure asked for

| Test date | Price then | Actual 1 w | Actual dir | Forecast call | Lean | ✓ | Agent | Lean | ✓ | LSTM | ✓ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-03-08 | 391.66 | +2.38% | UP | SELL | down | ✗ | short/flat | down | ✗ | UP | ✓ |
| 2022-10-10 | 342.67 | +1.89% | UP | STRONG SELL | down | ✗ | long | up | ✓ | UP | ✓ |
| 2024-08-13 | 529.50 | +3.07% | UP | HOLD | up | ✓ | long | up | ✓ | UP | ✓ |
| 2024-09-05 | 536.90 | +1.72% | UP | HOLD | none | — | long | up | ✓ | DOWN | ✗ |
| 2024-12-10 | 590.67 | +0.25% | UP | SELL | down | ✗ | long | up | ✓ | DOWN | ✗ |
| 2025-03-27 | 559.21 | −5.36% | DOWN | HOLD | up | ✗ | long | up | ✗ | UP | ✗ |
| 2025-06-23 | 593.57 | +2.95% | UP | HOLD | up | ✓ | short/flat | down | ✗ | DOWN | ✗ |
| 2025-11-28 | 677.77 | +0.34% | UP | BUY | up | ✓ | short/flat | down | ✗ | DOWN | ✗ |
| 2026-02-06 | 686.97 | −1.28% | DOWN | BUY | up | ✗ | long | up | ✗ | DOWN | ✓ |
| 2026-05-07 | 729.70 | +2.27% | UP | STRONG BUY | up | ✓ | long | up | ✓ | DOWN | ✗ |
| 2026-07-07 | 747.71 | +0.55% | UP | BUY | up | ✓ | short/flat | down | ✗ | UP | ✓ |
| 2026-07-24 | 738.93 | +1.10% | UP | BUY | up | ✓ | long | up | ✓ | UP | ✓ |

On SPY specifically: forecast 6/11 scoreable, agents 6/12, LSTM 6/12.
**Always-long would have been 10/12.** The two STRONG SELLs, in March and
October 2022, were the consensus's two most confident calls and both were
followed by a rise. Note also that all three components disagree with each
other constantly — on eight of twelve dates at least one says up while another
says down — which is why the combined figures sit so close to 50%.

---

## 11. Confidence calibration (Step 5)

The consensus's confidence is a 0–100 number produced by three multiplied gates.
If it means anything, accuracy should rise with it.

**Consensus, one-week window:**

| Confidence band | n | Mean stated | Accuracy | Return from taking it |
|---|---|---|---|---|
| 0–10 | 16 | 7.8 | 56.2% | −0.67% |
| 10–20 | 22 | 14.1 | **36.4%** | −0.64% |
| 20–30 | 30 | 26.5 | 53.3% | −2.74% |
| 30–50 | 35 | 35.6 | 57.1% | +0.38% |
| 50–70 | 15 | 64.8 | 66.7% | +1.04% |
| 70–90 | 11 | 84.6 | 63.6% | +1.40% |
| **90–100** | **5** | **95.0** | **40.0%** | **−0.50%** |

**1-day horizon, scored at one day:**

| Confidence band | n | Mean stated | Accuracy |
|---|---|---|---|
| 0–10 | 23 | 7.4 | 34.8% |
| 10–20 | 24 | 13.6 | 62.5% |
| 20–30 | 12 | 25.4 | 58.3% |
| 30–50 | 13 | 37.4 | 38.5% |
| 50–70 | 11 | 63.2 | 45.5% |
| 70–90 | 9 | 75.8 | 77.8% |
| 90–100 | 3 | 100.0 | 33.3% |

**Not calibrated.** There is a hint of a rising trend in the middle of the
one-week table (36% → 53% → 57% → 67% → 64%) that collapses entirely at the
top band, where the system is most certain and least right — 2 of 5 at a stated
95%. The one-day table has no monotone structure at all.

Aggregated: predictions at ≥50% stated confidence were right **61.3%** of the
time (n = 31) against a stated ~70%. The direction of the miscalibration is
overconfidence, and it is worst exactly where it matters most.

The bands the procedure named (50–60, 60–70, …) are too thinly populated to
report separately — 31 predictions total above 50% confidence across 12 dates.
Reported as bands of 20 instead; the finer split is in `calls.csv` for anyone
who wants it.

---

## 12. Signal-strength accuracy (Step 5)

Does a bigger score mean a better call?

**Consensus, one week:**

| Band | n | Accuracy | Return from taking it | vs SPY |
|---|---|---|---|---|
| weak (\|score\| < 15) | 41 | 43.9% | −0.58% | −0.15 pts |
| act (15–40) | 77 | 58.4% | −0.45% | −0.49 pts |
| strong (40+) | 16 | 56.2% | −0.39% | −0.07 pts |

**1-day horizon at one day:**

| Band | n | Accuracy | Return |
|---|---|---|---|
| weak | 36 | 44.4% | +0.22% |
| act | 42 | 47.6% | +0.12% |
| strong (40+) | 17 | **70.6%** | +0.66% |

Weak signals are worse than chance in both tables, which is at least the right
sign — the engine's ACT_BAND of 15 is doing something. But strength does not
buy accuracy beyond that threshold: the strong band is no better than the act
band at one week, and the one 70.6% reading rests on 17 calls across a handful
of dates. **Every band produces a negative directional return at one week**,
including the strongest, which is the finding that matters: a stronger signal
did not mean a better-paid one.

---

## 13. Return-prediction accuracy (Step 5)

Restricted to rows where a direction was named, at each system's own horizon.

| System | n | Mean predicted | Mean actual | Mean \|error\| | Signed error | corr | Median \|pred\| | Median \|actual\| | Size ratio |
|---|---|---|---|---|---|---|---|---|---|
| Consensus | 134 | −0.005% | +1.529% | 4.46 pts | −1.53 pts | **−0.011** | 0.325% | 2.723% | **0.12** |
| Consensus 4 h | 36 | −0.121% | +0.328% | 3.77 pts | −0.45 pts | −0.252 | 0.271% | 1.500% | 0.18 |
| Consensus 1 d | 95 | +0.045% | +0.630% | 2.41 pts | −0.59 pts | +0.118 | 0.209% | 1.496% | 0.14 |
| Consensus 1 w | 62 | +0.048% | +0.771% | 3.82 pts | −0.72 pts | +0.061 | 0.853% | 2.419% | 0.35 |

Two independent failures:

1. **No correlation.** The predicted return carries essentially no information
   about the realised one (−0.01 for the aggregate; the largest magnitude in
   the table, −0.25 at four hours, has the *wrong sign*).
2. **Systematically too small.** The median predicted move is 12–35% of the
   median realised move. `expected_move_pct` is `score/100 × typical_move`, so a
   score of 25 on a symbol whose typical weekly move is 3% produces a 0.75%
   forecast — arithmetically incapable of naming a large move even when one is
   coming. The numbers are internally consistent and externally uninformative.

The signed error is consistently negative, i.e. the system **under-predicted
the upside** at every horizon — a direct consequence of point 2 in a market
that rose.

---

## 14. Price-target accuracy (Step 5)

Against the only honest yardstick: "the price will be what it is now."

| System | n | MAE $ | MAPE | Median APE | Signed bias | No-change MAPE | Beats no-change |
|---|---|---|---|---|---|---|---|
| Consensus | 321 | 84.03 | 5.592% | 3.172% | −1.225% | 5.590% | **38%** |
| Consensus 4 h | 211 | 41.35 | 2.534% | 1.574% | −0.362% | 2.512% | **4%** |
| Consensus 1 d | 318 | 64.51 | 2.821% | 1.780% | −0.208% | 2.818% | **14%** |
| Consensus 1 w | 316 | 85.32 | 5.583% | 3.088% | −1.328% | 5.555% | **9%** |

The MAPEs look respectable in isolation and are **worse than doing nothing** in
every case. That is what section 13 predicted: a target that sits 0.3% from
the current price inherits the no-change forecast's error almost exactly, and
then adds a small biased tilt that loses more often than it wins. The 4-hour
targets beat no-change 4% of the time.

This is not a defect in the price target so much as a warning about reading it.
`ultimate.py` does not claim to forecast a price; `target_price` is a
presentation of the score. This study confirms it should not be read as a
forecast.

---

## 15. Baseline comparison (Step 10)

### Against always-predicting-up, on identical rows

The decisive test, because most of these systems lean bullish most of the time
and the study window rose.

| System | Window | n | Bullish leans | Accuracy | Always-long | Difference | 95% CI | p |
|---|---|---|---|---|---|---|---|---|
| Consensus | 1 w | 134 | 51.5% | 53.7% | 61.9% | **−8.2 pts** | [−28.1, 11.7] | 0.383 |
| Consensus 4 h | 4 h | 36 | 41.7% | 27.8% | 47.2% | **−19.4 pts** | [−63.6, 24.7] | 0.332 |
| Consensus 1 d | 1 d | 95 | 60.0% | 50.5% | 54.7% | −4.2 pts | [−35.6, 27.2] | 0.774 |
| Consensus 1 w | 1 w | 62 | 58.1% | 56.5% | 59.7% | −3.2 pts | [−19.0, 12.6] | 0.662 |
| Turtle | 1 w | 325 | 28.3% | 44.6% | 59.1% | **−14.5 pts** | [−38.5, 9.6] | 0.212 |
| MA crossover | 1 w | 325 | 55.4% | 56.9% | 59.1% | −2.2 pts | [−16.9, 12.6] | 0.753 |
| Signal rolling | 1 w | 325 | 58.5% | 50.2% | 59.1% | −8.9 pts | [−20.6, 2.7] | 0.121 |
| Combined agents | 1 w | 325 | 46.8% | 50.2% | 59.1% | −8.9 pts | [−25.5, 7.6] | 0.260 |
| LSTM forecast | 1 w | 96 | 71.9% | 59.4% | 64.6% | −5.2 pts | [−21.3, 10.8] | 0.490 |
| Consensus, megacap subset | 1 w | 49 | 65.3% | 51.0% | 73.5% | **−22.4 pts** | **[−40.0, −4.9]** | **0.017** |

**Every single component is below always-long.** Only the last row reaches
significance, and it is the consensus measured on the eight large, liquid names
the forecaster subset covers. Elsewhere the gaps are individually
inconclusive — but the sign is unanimous across nine independent systems, which
is itself informative: nine coin flips landing the same way is a 1-in-256 event.

### Against the other trivial rules — consensus, one week, paired

| Baseline | n | Consensus | Baseline | Difference | 95% CI | p |
|---|---|---|---|---|---|---|
| Buy and hold | 133 | 53.4% | 62.4% | −9.0 pts | [−29.0, 11.0] | 0.342 |
| Trend continuation | 133 | 53.4% | 57.1% | −3.8 pts | [−22.1, 14.6] | 0.661 |
| 50-bar MA direction | 133 | 53.4% | 54.9% | −1.5 pts | [−25.7, 22.7] | 0.894 |
| Golden cross | 133 | 53.4% | 56.4% | −3.0 pts | [−15.6, 9.6] | 0.611 |
| **An actual coin flip** | 133 | 53.4% | 56.4% | −3.0 pts | [−20.1, 14.1] | 0.706 |

The seeded coin flip beat the consensus on this sample. That is luck — a coin
flip's expectation is 50% and it drew 56.4% — but it is a useful calibration of
how much the differences in this table are worth.

### The money view — taking the call vs staying long

| System | Window | n | Taking the call | Long the same rows | Difference | p |
|---|---|---|---|---|---|---|
| Consensus | 1 w | 134 | −0.49% | +1.53% | −2.02 pts | 0.252 |
| Combined agents | 1 w | 325 | −0.02% | +2.15% | −2.17 pts | 0.133 |
| MA crossover | 1 w | 325 | +1.98% | +2.15% | −0.16 pts | 0.878 |
| LSTM forecast | 1 w | 96 | +0.44% | +1.44% | −1.00 pts | 0.236 |
| Consensus | **1 m** | 122 | −2.76% | +4.30% | **−7.06 pts** | **0.015** |
| Consensus 1 w | **1 m** | 57 | −2.54% | +3.92% | **−6.46 pts** | **0.007** |
| Combined agents | **1 m** | 297 | −0.92% | +5.96% | **−6.88 pts** | **0.003** |
| Turtle | **1 m** | 297 | −2.15% | +5.96% | **−8.11 pts** | **0.010** |
| MA crossover | **1 m** | 297 | +1.24% | +5.96% | **−4.72 pts** | **0.008** |

At the one-month window the underperformance is significant for every system
tested. The caveat is real and should be stated plainly: **in a market that
rose, any system that is ever flat or short must underperform being long, and
that is partly what this table shows.** It is not, however, only that — a
system with genuine directional skill would be flat or short in front of the
falls, and these were not.

---

## 16. Systematic errors and weaknesses (Step 8)

Checked against the procedure's list. Findings first, unavailable checks last.

**Confirmed weaknesses**

* **Overconfidence at the top.** The 90–100 confidence band was right 40% of
  the time (2 of 5). §11.
* **The bull/bear asymmetry, in every component without exception.** Each one
  is far better on its bullish calls than its bearish ones:

  | | Bullish accuracy | Bearish accuracy |
  |---|---|---|
  | Consensus | 65.2% | **41.5%** |
  | MA crossover agent | 64.4% | 47.6% |
  | Turtle agent | 56.5% | **39.9%** |
  | LSTM forecast | 66.7% | **40.7%** |

  The consensus is not "too bullish" in its call distribution — 51.5% of its
  leans were bullish against a 61.9% up-rate, so if anything it is too
  bearish. The problem is that the bearish calls are the wrong ones. The LSTM
  *is* too bullish: 71.9% bullish leans against a 64.6% up-rate.
* **Magnitude is wrong in both directions, depending on component.** The
  consensus under-states: median predicted move 12–35% of the median realised
  one. The LSTM over-states: 3.3× too large, with a single projection of
  +69.2% over five days. §13.
* **The 4-hour horizon is anti-predictive** overnight. 27.8% overall, 20.8%
  acted. §8. The LSTM is 38% at the same window.
* **Price targets lose to no-change.** Consensus by a hair, the LSTM by 3×. §14.
* **The forecaster is a drift-follower.** 72% bullish, 49.9% walk-forward
  directional, 36 of 288 folds beating no-change — measurable *before* any
  outcome, which is why the consensus correctly gave it zero weight 257 times
  out of 257.

**Checked, no effect found**

* **Volatility regime.** Accuracy by pre-cutoff 60-day volatility tercile is
  flat for the consensus: calm 54.5%, middling 53.3%, turbulent 52.3%. It does
  not degrade in turbulence — it does not do much of anything in any regime.
  (The turtle agent *does* degrade: −0.27% / −1.74% / −2.79% per week by
  tercile.)
* **Market direction.** Consensus accuracy by what SPY did over the same week:
  market fell >1% → 50.0% (n = 26); flat → 65.7% (n = 35); rose >1% → 49.3%
  (n = 73). Best in quiet markets, no better than chance in either trend. It
  did **not** fail specifically during the drawdowns.
* **Weak signals.** Confirmed unreliable — 43.9% at one week, below chance,
  which is why the engine's HOLD band exists.

**Cannot be assessed with this data (validation rule 10)**

* **Earnings proximity** — no earnings calendar is available to the harness.
* **Major news events** — the engine reads no news, and none was joined in.
* **Sector effects** — 22 single names across too few sectors to split.

**By symbol** (consensus, ≥4 leaned calls): worst ORCL 17% of 6, TSLA 33% of 6,
GOOGL 38% of 8, T 40% of 10, NVDA 50% of 10. Best SLV 100% of 5, AMZN 75% of 4,
VOO 67% of 9, ETH-USD 67% of 6, BTC-USD 60% of 5. On samples of 4–10 across ≤12
dates this is noise, and it is reported to show that no symbol-level pattern
survived rather than to claim one did.

---

## 17. Best-performing conditions

Ranked by what the evidence actually supports, not by headline number:

1. **When it stays quiet.** The 74.3% of symbol-dates the consensus declined to
   call are its best contribution. Nothing in this study suggests it should have
   called them.
2. **Funds and index products.** Consensus 62.2% on funds (n = 37) vs 48.8% on
   single equities (n = 84). Consistent with the design — more sources clear
   significance on a diversified series — but not significant on this sample.
3. **Flat markets.** 65.7% when SPY moved less than ±1% over the week (n = 35).
4. **The 1-week horizon over the 1-day and 4-hour ones.** 56.5% vs 50.5% vs
   27.8%. Longer is better here, monotonically — and the same holds for the
   LSTM: 59% at a week, 43% at a day, 38% at four hours.

## 18. Worst-performing conditions

1. **The 4-hour horizon read after the close, at any confidence.** 27.8%, and
   its 100%-confidence calls were wrong. This is the one component the study
   would recommend switching off — with the overnight-gap caveat in §8.
2. **Bearish calls.** 41.5% for the consensus, 39.9% for the turtle agent.
3. **Highest-confidence calls.** 40% in the 90–100 band.
4. **Single-name equities.** 48.8%.
5. **The neural forecaster's price path**, everywhere. It beat the no-change
   forecast in 23% of experiments and 36 of 288 walk-forward folds.
6. **October 2022** — the consensus went 1 for 10 as the bear-market bottom
   formed, having read STRONG SELL on QQQ and SPY at 100% and 93% confidence
   into a +1.9% week and the start of a multi-year advance.

---

## 19. Overall performance score (Step 9)

| Metric | Result |
|---|---|
| Number of historical tests | 12 cutoffs × 30 symbols = **360 frozen predictions**, plus 96 LSTM experiments |
| Scoreable symbol-dates (1 week) | 331 |
| Consensus directional accuracy (leaned) | **53.7%** (n = 134, p = 0.54) |
| Consensus directional accuracy (acted) | **61.2%** (n = 85, p = 0.056) |
| Consensus vs always-long, paired | **−8.2 pts** (p = 0.38) |
| High-confidence (≥50) accuracy | **61.3%** (n = 31) against a stated ~70% |
| Average return-prediction error | **4.46 points** on a median 2.7% actual move |
| Average price-target error (MAPE) | **5.59%**, vs 5.59% for assuming no change |
| Combined-agent accuracy | **50.2%** (n = 325, p = 0.94) |
| Best single agent (MA crossover) | **56.9%** (p = 0.077); −0.16 pts/week vs long |
| **Forecast (LSTM) accuracy** | **59.4%** (n = 96, p = 0.25); **−5.2 pts** vs always-long |
| **Forecast price MAPE** | **11.48%**, vs **3.77%** for assuming no change |
| **Combined system (consensus + forecast)** | **Bit-identical to the consensus** — 0 of 96 verdicts changed |
| Abstention rate | **74.3%** HOLD |
| Systems beating always-long on their own horizon | **0 of 9** |

Per period (share of that cutoff's leaned consensus calls that were correct):
10% · 30% · 33% · 45% · 50% · 50% · 58% · 62% · 64% · 67% · 73% · 86%.

### The one-line score

On the procedure's own distinction: the system **predicts correctly** about as
often as the market rises, and it **does not predict correctly with meaningful
confidence and better performance than a simple baseline** on any measurement
taken here.

---

## 20. Final assessment

### Does the system demonstrate genuine predictive power?

**No — on this evidence it does not, and the distinction the procedure asked for
is exactly where it fails.**

*"The system predicted this correctly"* is true often enough: 53.7% of leans,
61.2% of actionable calls, 59.4% for the neural forecaster, 86% on its best day.

*"The system predicted this correctly with a meaningful level of confidence and
better performance than a simple baseline"* is not supported by a single
measurement in this study:

* its confidence does not track accuracy, and inverts at the top band;
* it is below always-long on all nine systems measured — significantly so on
  the megacap subset;
* it is below a seeded coin flip on this sample;
* its price targets lose to assuming no change, and the neural forecaster's
  lose by a factor of three;
* its expected returns correlate −0.01 with what happened (the LSTM's, −0.07);
* taking its calls underperformed holding by 7 points a month, significantly;
* its four-hour horizon, read after the close, predicts the opposite of what
  occurs;
* and the neural forecast it can optionally include changed **nothing** — not
  one action, not one score, across 96 experiments.

### The one thing that came out well

The engine's refusal to speak is calibrated even though its confidence is not.
It said HOLD on 74.3% of symbol-dates, and on the 25.7% it did call, its edge
over a trivial rule was zero. The machinery in `ultimate.py` — significance
gating, effective sample sizes, family caps, three multiplied confidence gates —
was built on the premise that most symbols on most days have no readable edge.
**This study is independent confirmation of that premise**, obtained the only
way it can be: by making predictions before the outcomes existed.

The sharpest instance is the neural forecaster. `ModelEvidence` refuses to
weight a forecast whose walk-forward directional edge sits inside its own
noise. Across 96 point-in-time experiments the forecaster's walk-forward
accuracy averaged 49.9%, and the gate fired 257 times out of 257 — so the
consensus never once acted on it. When the forecaster's live predictions were
finally scored, they came in at 59.4% and **5.2 points behind always-long**.
The gate was right, every time, using only information available at prediction
time. A system that can identify its own useless component and quietly refuse
to use it is doing something most cannot.

That is a real result, and it argues for keeping the gates rather than loosening
them.

### What the study cannot conclude

Twelve cutoffs is a small number of independent market draws. The clustered
intervals are wide: the consensus's true accuracy could plausibly be anywhere
from 41% to 67%. This is a **failure to demonstrate skill**, not a
demonstration of its absence — with one exception, the 4-hour horizon read
after the close, where the interval sits below 50% and the acted-only p-value
is 0.009.

A stronger study would need many more cutoff dates (the binding constraint —
adding symbols buys almost nothing), unadjusted price history, and a universe
assembled as of each cutoff rather than today.

### Concrete recommendations

1. **Suppress the 4-hour horizon for calls read after the close, and re-measure
   it intraday before trusting it at all.** It is the only component with
   evidence of active harm (20.8% on acted calls, p = 0.009), but every window
   tested straddled an overnight gap, so what is established is that it is
   inverted *overnight*. The cheap, safe change is to stop the 4-hour horizon
   contributing when the last bar is a session close. The right follow-up is a
   study with intraday cutoffs.
   (`calibrate()` deliberately drops anti-predictive sources rather than
   flipping them — the same discipline applies here: drop it, do not invert it
   on a fit of 36 observations.)
2. **Stop presenting `target_price` and the projected price path as forecasts.**
   The consensus target loses to no-change 62–96% of the time by horizon; the
   LSTM path loses 77% of the time and by 3× on MAPE, with a worst case of
   +69.2% projected over five days. Both are renderings of an internal number
   and should be labelled as such, not drawn as a price.
3. **Do not raise confidence out of the 90–100 band without re-deriving it.**
   The top band is the least accurate one measured (2 of 5).
4. **Remove the "Include the forecast" toggle, or label it honestly.** It costs
   ~45 s of training per symbol and, in 96 of 96 experiments, changed nothing:
   0 actions, 0 scores, 0 of 257 horizon-slots weighted. Either way, the
   forecast tab's own walk-forward panel should lead with the number that
   predicts this — folds beating naive, 36 of 288 here — rather than with the
   96%-looking `accuracy()` figure, which is dominated by price level and reads
   high for anything that stays near the last price.
5. **Keep the HOLD floor and the significance gates exactly where they are.**
   They are the parts that work, and this study is the evidence for them.

---

*Every number above is reproducible from `validation/out/calls.csv`
(one row per cutoff × symbol × system × window) and `validation/out/report_raw.txt`.
Re-run with `python -m validation.predict && python -m validation.model &&
python -m validation.score`.*
