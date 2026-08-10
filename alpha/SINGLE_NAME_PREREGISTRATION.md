# Single-Name Phase 1 — Pre-Registration

**Written 2026-08-11. PRE-REGISTRATION ONLY. Committed BEFORE any single-name
probability, expected return, calibration curve, abstention count or verdict exists.**

Nothing in this document is a result. Every number quoted below is either

* **(FROZEN)** — a constant already in the repository, quoted with its source line, or
* **(FEATURE-SIDE)** — a count computed from the (cutoff × symbol) panel's *index and
  feature columns only*, with no forward return, target, outcome or label read.

No forward return has been read at the time of writing. No model has been fitted. No
probability has been produced. No exam cutoff has been opened.

---

## 0. Standing, and what this study is not

### 0.1 Standing

This study is commissioned by the account holder's `MISSION` directive (2026-08-10),
"FIRST DELIVERABLE": *architecture + development harness + incumbent baselines*, with the
explicit instruction **"Do not spend another new-feature research budget slot yet."**

It is admissible under the master roadmap **§9b — Phase 7b, Single-name re-validation**,
which is a standing, already-scoped, *blocking* phase of the programme:

> Nothing reaches the application on cross-sectional evidence alone (§1.1). Anything
> surviving Phase 7 is re-scored **per symbol, on its own terms** … Scored against
> **always-predict-up** and **no-change** (§2.3), on the actual up-rate of the period
> rather than against 50% … Abstention is counted, not hidden.

### 0.2 What this study does not do — stated so it can be checked

| | |
|---|---|
| New information family | **NONE.** No source is ingested. No feature is constructed. Every input is a column that already exists in `alpha/out/panel.pkl`, built 2026-08-08 |
| V3 / V4 budget slot | **NONE SPENT.** V3 is CLOSED (3/3), V4 is CLOSED (slot 1 spent, slot 2 barred). Neither is reopened, reinterpreted or rescored |
| Rejected arm revived | **NO.** SUE, Form 4 and 13F are not read. No λ, sign, carrier, learner or horizon of any rejected arm is varied |
| Horizon | **UNCHANGED at 5 sessions.** No second horizon is introduced |
| B3 | **UNCHANGED.** `alpha/protocol.py` is not modified |
| Sealed exam | **NOT TOUCHED.** The 72 V2.1 cutoffs are not loaded, scored, inspected or used for any selection |
| Production weight | **UNCHANGED at 0.0.** `alpha/adapter.py` is not modified |
| Cross-sectional claim | **NONE MADE.** This study asks an *absolute*, per-symbol question that the cross-sectional programme never asked |

**The dependent variable is different from every prior study in this repository.** V2→V2.3,
V3 and V4 all scored *cross-sectional rank against `alpha_5d`* (return in excess of SPY).
This study scores **`P(asset_return > 0)` and `E[asset_return]`** — the raw, absolute
5-session forward return of a single name, which is a different random variable and is
the one the application would have to report. No cross-sectional result is affected by
anything measured here, in either direction.

---

## 1. Frozen constants

Every constant below is fixed by this document and lives in `alpha/singlename_config.py`.
None may be changed after any result is seen.

### 1.1 Horizon — inherited, not chosen

| | |
|---|---|
| **Primary horizon** | **`H = 5` sessions** |
| Source | `alpha/targets.py::HORIZON = 5` **(FROZEN)** — "sessions — the §3 primary horizon" |
| Confirmed by | Account-holder ruling, commit `65c0039`, *"horizon 5D … IN FORCE"* |
| Secondary horizons | **NONE.** V4 §9.2 bars a third horizon permanently. No 10D, 20D, 40D or 60D quantity is computed anywhere in this study, not even as a diagnostic |

### 1.2 Target — absolute, not relative

```
asset_return(T, s) = Close[T + 5](s) / Close[T](s) - 1        # panel column `asset_return`
direction(T, s)    = 1 if asset_return(T, s) > 0 else 0
```

Source: `alpha/pitdata.py::PriceBook.forward_return`, materialised into the panel by
`alpha/dataset.py::build`. Ties (`asset_return == 0.0`) count as **0 (not up)**, fixed
here in advance.

`alpha_5d`, `sector_relative`, `residual_alpha`, `target_train`, `target_rank`,
`target_vol_scaled` and `quintile` are **not** used as targets anywhere in this study.

### 1.3 Incumbent — B3, bit-identical

```
b3_raw  = rank_pct(mom_12_1)  where trend != BEAR_TREND
        = -rank_pct(mom_5d)   where trend == BEAR_TREND
b3_rank = rank_pct(b3_raw)     within the cutoff
```

Source: `alpha/protocol.py::benchmark_scores`, key `b3_regime_switched` **(FROZEN)** —
"mom_12_1 in BULL_TREND/SIDEWAYS, -mom_5d in BEAR_TREND, switched on the pre-cutoff
regime tag; nothing fitted". The second rank is the same rank-transform V3 Families 1–3
and V4-SUE applied (`alpha/v3_family1.py:149`), carried over unchanged so that "B3" means
the same object it has always meant.

`protocol.py` is imported, never edited.

### 1.4 Development / exam split

| | |
|---|---|
| Split authority | `alpha/examset.py`, V2.1 protocol §2.1 |
| Exam | **72 cutoffs**, digest `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. **SEALED.** Never loaded by this study except through `examset.development_only`, whose only effect is to *remove* them |
| Development | **316 cutoffs (FEATURE-SIDE)**, 2016-01-04 … 2026-07-28, each ≥ `HORIZON + EMBARGO = 10` sessions clear of every exam outcome window |
| Development rows | **143,675 (FEATURE-SIDE)** |
| Distinct symbols | **594 (FEATURE-SIDE)** |
| Cross-section per cutoff | min 400, median 454, max 502 **(FEATURE-SIDE)** |

### 1.5 Walk-forward, purge and embargo

At evaluation cutoff `T`, the admissible training cutoffs are exactly those returned by
`alpha/dataset.py::training_cutoffs` **(FROZEN)**:

```
T' is admissible  <=>  position(T') + HORIZON + EMBARGO <= position(T)
HORIZON = 5, EMBARGO = 5   (alpha/dataset.py)
```

so a training row's 5-session outcome window closed at least 5 sessions before `T`. No
random split, no K-fold, no shuffle, no future cutoff, ever.

| | |
|---|---|
| `MIN_TRAIN_CUTOFFS` | **100** — the minimum number of admissible prior development cutoffs before a prediction may be emitted. Chosen to match the existing `examset.WARMUP_SESSIONS = 504` warm-up expressed in grid cutoffs (`504 // 5 = 100`), not tuned |
| Evaluation window | the resulting **215 cutoffs (FEATURE-SIDE)**, first evaluation cutoff **2018-01-26**, last **2026-07-28**. Verified by `python -m alpha.singlename --describe`, which reads the calendar and the admissibility rule and no outcome |
| `CONFORMAL_CUTOFFS` | **20** — the most recent admissible cutoffs are withheld from every fit and used only as the conformal calibration block |
| Fit set at `T` | admissible cutoffs excluding the last 20 |
| Calibration set at `T` | those last 20 admissible cutoffs |
| Window | **expanding** (all admissible history), not rolling. Fixed here; no window-length search is performed |

### 1.6 Statistical instrument — unchanged

| | |
|---|---|
| Unit of observation | the **cutoff**, not the symbol-date. 454 names on one Tuesday are not 454 draws |
| Per-cutoff statistic | the cross-sectional mean of the metric at that cutoff |
| Interval | moving-block bootstrap of the mean, `alpha/stats.py`, **block length 4 cutoffs**, 10,000 draws, seed 20260808 **(FROZEN)** |
| Cross-check | Newey-West, 4 lags |
| Reported with every point estimate | its 95% half-width. A point estimate without its resolution is not a result (roadmap §2.6) |

Block length **4** is `alpha/stats.py::BLOCK_LENGTH`, the value used for every 5-session
study in this repository. It is not re-derived, because the horizon is not changed.

---

## 2. Architecture — three layers, declared before implementation

### 2.1 Layer 1 — market state (`alpha/market_state.py`)

Interpretable, point-in-time, **no fitted parameters**, computed from panel columns that
`alpha/features.py::context_block` already produced from a truncated `PriceView`.

| Field | Definition | Source column |
|---|---|---|
| `trend` | `BULL_TREND` / `SIDEWAYS` / `BEAR_TREND` | `alpha/features.py::regime_state`, via `panel.regimes` |
| `vol` | `HIGH_VOL` / `LOW_VOL` (VIX vs its trailing 252-session median) | same |
| `vix_level`, `vix_percentile` | as-of level and 252-session percentile | `vix_level`, `vix_percentile` |
| `breadth_sma50` | share of index members above their 50-session SMA | `index_breadth_above_sma50` |
| `advance_share` | share of index members up on the session | `index_advance_share` |
| `spy_ret_20d`, `spy_ret_60d` | index momentum | `mkt_spy_ret_20d`, `mkt_spy_ret_60d` |
| `dispersion_20d` | cross-sectional standard deviation of `ret_20d` at the cutoff | computed from the cutoff's own cross-section |
| `risk_score` | `mean(1{spy_ret_60d > 0}, breadth_sma50, 1 - vix_percentile, 1{trend == BULL_TREND})`, in `[0, 1]` | composite of the above |

`risk_score` is a **frozen arithmetic composite declared before it was computed**. It is
a context label. It is **not** claimed to carry alpha, is not fitted, is not tuned, and
nothing in §3 or §4 selects on it.

**Only `(trend, vol)` enters a scored baseline** (S4, §3.5). Every other field is carried
into the output object as context and is not used for any selection, fit or threshold.

### 2.2 Layer 2 — cross-sectional edge

**Unchanged and not re-opened.** The incumbent is B3 (§1.3). No candidate cross-sectional
signal is proposed, tested or fitted in Phase 1. Layer 2's output into Layer 3 is exactly
`b3_rank` and nothing else.

### 2.3 Layer 3 — single-name forecast (`alpha/singlename.py`)

For each `(T, symbol)` the harness emits the object in §6, containing `P(r_5 > 0)`,
`E[r_5]`, a prediction interval, a cross-sectional percentile, a decision and a reason.

---

## 3. The five incumbents — S0 … S4

All five are fitted **only** on admissible prior development data (§1.5). All five emit a
probability in `[0, 1]` and an expected return in return units.

Probabilities are clipped to `[0.001, 0.999]` before log loss, so that a degenerate
baseline scores badly rather than infinitely. The clip is declared here, in advance, and
applies identically to every arm.

### 3.1 S0 — always up

```
p_up = 1.0        (clipped to 0.999 for log loss)
E[r] = 0.0
```

The trivial directional baseline of roadmap §2.3. Its accuracy is the period's own
up-rate. Its probabilistic scores are expected to be poor; that is the point of including
it, and it will be reported without apology in both roles.

### 3.2 S1 — unconditional prior

```
p_up = mean(direction) over all admissible prior rows
E[r] = mean(asset_return) over all admissible prior rows      (winsorised, §3.6)
```

No feature. The honest "what does history alone say" baseline, and the one S3 must beat
to demonstrate that B3 carries *any* absolute directional information.

### 3.3 S2 — 12-1 momentum

```
x    = rank_pct(ret_12_1) within the cutoff, centred at 0.5
p_up = sigmoid(a + b * x),  (a, b) from logistic regression on admissible prior rows
E[r] = c + d * x,           (c, d) from ridge regression on admissible prior rows
```

### 3.4 S3 — B3

Identical to S2 with `x = b3_rank - 0.5` (§1.3).

### 3.5 S4 — B3 conditioned on market state

The S3 fit is repeated **separately within each `(trend, vol)` bucket**, using only that
bucket's admissible prior rows.

```
bucket(T) = (trend(T), vol(T))                       # 6 possible buckets
if prior cutoffs in bucket >= MIN_BUCKET_CUTOFFS:  use the bucket fit
else:                                              fall back to the pooled S3 fit
MIN_BUCKET_CUTOFFS = 20        # frozen here, before any bucket count was compared to it
```

The fallback is not a tuning knob: `BEAR_TREND / LOW_VOL` holds **4 cutoffs (FEATURE-SIDE)**
in the evaluation window, and a bucket that thin cannot support its own logistic. The rule
is stated before any bucket-level result exists.

Bucket occupancy across the whole development set, from the regime tags alone **(FEATURE-SIDE)**:
`BULL/LOW 156 · BULL/HIGH 94 · BEAR/HIGH 31 · SIDEWAYS/HIGH 21 · SIDEWAYS/LOW 10 · BEAR/LOW 4`.

### 3.6 Fitting — fixed, low capacity, no search

| | |
|---|---|
| Direction | `sklearn.linear_model.LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=0)` |
| Magnitude | `sklearn.linear_model.Ridge(alpha=1.0, random_state=None)` |
| Design matrix | **one** centred feature. No interactions, no polynomials, no additional columns |
| Magnitude target | `asset_return` **winsorised per cutoff at 1%** using `alpha/targets.py::winsorise` **(FROZEN)**, so one takeover bid cannot own the fit |
| Regularisation search | **NONE.** `C` and `alpha` are fixed at 1.0 here and are not tuned, not scanned, and not selected on any development result |
| Missing features | **NOT IMPUTED** (CLAUDE.md §6.2). A row whose feature is NaN is emitted as `NO_EDGE` with `p_up = S1`, `E[r] = S1` and is counted in coverage denominators |

### 3.7 Uncertainty — split conformal, time-ordered

At `T`, on the 20-cutoff conformal block (§1.5), which no fit has seen:

```
residual  = asset_return - E[r]
interval  = [ E[r] + q_05(residual), E[r] + q_95(residual) ]      # nominal 90%, asymmetric
```

Nominal coverage **90%**, frozen here. Empirical coverage is reported; it is a
diagnostic, not a gate. No bootstrap, no parametric assumption, no symmetry assumption.

---

## 4. Decision rule and abstention — thresholds frozen before any result

```
BUY   if p_up >= 0.55  and  E[r] >= +0.0025
SELL  if p_up <= 0.45  and  E[r] <= -0.0025
else  HOLD  (call = "NO_EDGE" when the row has no usable feature, "HOLD" otherwise)
```

`0.55 / 0.45` is a symmetric ±5 percentage-point band around a coin flip. `0.0025` is
25 basis points over five sessions — chosen as a round, economically minimal edge that is
of the order of a round-trip cost on a liquid US large cap, **not** derived from any
realised return in this sample.

**These thresholds are not tuned and will not be re-chosen.** A threshold sweep is
computed and reported as a **pre-declared diagnostic curve only**. Roadmap §0.1 forbids
promoting any point on a curve to an arm; no point on the sweep may become the rule, in
this study or in a later one, without a fresh pre-registration.

**Pre-declared secondary variant (declared now, so it cannot be introduced later):** the
same rule with an added uncertainty gate that drops rows whose prediction-interval width
is in the widest decile of that cutoff's cross-section. It is reported alongside, and it
is *not* the primary.

Reported for the primary rule: coverage · accuracy on covered calls · Brier and log loss
on covered calls · mean realised return by call · symbol breadth · stability by
chronological half and by trend regime.

---

## 5. Metrics, and the frozen Phase 1 verdict rule

### 5.1 Metrics

**Direction:** accuracy · balanced accuracy · log loss · Brier · ROC-AUC (secondary).
**Calibration:** 10 fixed probability bins with edges at `0.0, 0.1, …, 1.0` · reliability
table · expected calibration error (ECE, sample-weighted) · realised hit rate per bin.
**Return:** MAE · RMSE · Pearson and Spearman correlation of predicted vs realised ·
sign accuracy · realised return by predicted-return decile.
**Economic discrimination:** all of the above split by confidence tier
`low = |p_up - 0.5| < 0.02`, `medium = 0.02 … 0.05`, `high = >= 0.05` — **tiers frozen
here, before any predicted probability existed** — and on the abstained rows.

Every headline number is computed per cutoff, then aggregated across cutoffs, with the
§1.6 block-bootstrap interval.

### 5.2 The verdict rule — frozen before any result

`reports/SINGLE_NAME_PHASE1.md` must end with exactly one of
`PHASE 1 VERDICT: ADVANCE` or `PHASE 1 VERDICT: DO NOT ADVANCE`.

**ADVANCE requires all four of G1–G4. Any failure is DO NOT ADVANCE.**

| Gate | Requirement |
|---|---|
| **G1 — B3 carries absolute directional information** | The best of S3/S4 beats **S1** on log loss, and the 95% block-bootstrap interval of the paired per-cutoff log-loss difference lies **entirely below zero** |
| **G2 — the probability means something** | The best arm's **ECE ≤ 0.02**, and realised hit rate is monotone in the probability bin: Spearman(bin index, realised hit rate) **≥ +0.5** over bins holding ≥ 30 evaluation cutoffs each |
| **G3 — abstention adds** | Accuracy on covered calls exceeds accuracy over all rows, paired per-cutoff 95% interval **entirely above zero**, at coverage **≥ 5%** of symbol-dates and breadth **≥ 100** distinct symbols |
| **G4 — it beats always-up on its own terms** | Accuracy on covered calls exceeds **S0's accuracy on the same rows**, paired per-cutoff 95% interval **entirely above zero** (roadmap §9b: a signal that beats the cross-section but not always-up is a portfolio-construction result, not a stock prediction) |

Partial passes are recorded gate by gate and still produce **DO NOT ADVANCE**. No gate
may be weakened, re-scoped, or re-run on a subset after a result is seen (CLAUDE.md §3.2).

### 5.3 Resolution / MDE — reported, not gated

Question F of the directive is answered by measuring, on the development set, the 95%
block-bootstrap half-width of the paired per-cutoff difference for each headline metric.
That half-width **is** the minimum detectable effect at this sample size: a candidate
improvement smaller than it cannot be distinguished from zero by this instrument,
whatever its point estimate.

This is a measurement, not a gate: Phase 1 spends no budget slot, ingests no new
information family, and therefore does not trigger the roadmap §2.6 pre-study power gate,
which governs new-family studies. The measured half-widths are the input to whether any
*future* family study is worth authorising.

---

## 6. Output schema

```python
{
  "symbol": str, "cutoff": "YYYY-MM-DD", "horizon": "5D",
  "market_state": {"regime": str, "trend": str, "vol": str, "risk_score": float,
                   "vix_percentile": float, "breadth_sma50": float,
                   "dispersion_20d": float},
  "relative":    {"score": float, "percentile": float},          # b3_rank, and its pct
  "absolute":    {"prob_up": float, "expected_return": float,
                  "prediction_interval": [float, float]},
  "decision":    {"call": "BUY|HOLD|SELL|NO_EDGE", "confidence": str, "reason": str},
  "model":       {"version": "single-name-phase1", "calibration_version": str,
                  "arm": "S0|S1|S2|S3|S4"}
}
```

`relative` and `absolute` are **separate branches and are never merged** (directive Phase
8). A high `relative.percentile` with a negative `absolute.expected_return` is a valid,
expected state and must render as "strong relative, unattractive absolute", never as BUY.

Nothing in this schema is connected to live trading. `alpha/adapter.py` production weight
stays **0.0**.

---

## 7. Process discipline

1. **This document is committed before `alpha/singlename.py` reads a single forward
   return.** The predictive fit is a separate, later commit.
2. Prediction and scoring are two processes. `alpha/singlename.py` writes
   `alpha/out/single_name_predictions.pkl` and **refuses to overwrite it**;
   `alpha/singlename_score.py` reads that file and never writes it. Same contract as
   `validation/predict.py` / `validation/score.py`.
3. Past labels reach the fit only through `PastOutcomes`, an object that raises if asked
   for any row whose outcome window had not closed `EMBARGO` sessions before the
   requested cutoff. The guarantee is enforced by a test, not by convention.
4. Determinism: identical inputs produce a bit-identical prediction file. Enforced by a
   test.
5. No existing test is deleted, skipped or weakened.

---

## 8. What a failure means, fixed in advance

If G1 fails, B3 — the strongest object this programme has produced — carries no absolute
directional information at 5 sessions, and Layer 3 has no cross-sectional input worth
calibrating. The correct conclusion is that the single-name product is blocked on
**information**, not on architecture, and the recorded response is to stop, not to try a
larger model on the same input (roadmap §2.9, §0.1 "No V2.4").

If G1–G2 pass but G3–G4 fail, the honest description is roadmap §9b's: a
**portfolio-construction result, not a stock prediction**. That must be written in those
words and must not be presented as a partial success.

A negative result is an acceptable result.

---

## 9. Phase 1 repository audit and dependency map

Produced before any code in this study was written, per the directive's Phase 1.

### 9.1 Audit findings

| Question | Answer |
|---|---|
| Git status | clean; branch `streamlit-app`; HEAD `0d75b53`. `origin` is a **third party's** repository — never pushed |
| Charter / roadmap | `ai stock prediction master roadmap.md` (outside the worktree), `alpha/V4_CHARTER.md`, `reports/PROGRAMME_STATUS_V2_3.md`, `reports/PROGRESS_V3.md`, `reports/PROGRESS_V4.md` |
| Frozen constants | `targets.HORIZON=5`, `targets.BETA_WINDOW=252`, `targets.WINSOR=0.01`, `dataset.SPACING=5`, `dataset.EMBARGO=5`, `dataset.STUDY_START=2016-01-04`, `examset.EXAM_STEP=6`, `examset.WARMUP_SESSIONS=504`, `stats.BLOCK_LENGTH=4`, `stats.SEED=20260808`, `models.MODEL_A_PARAMS` |
| B3 | `alpha/protocol.py::benchmark_scores`, key `b3_regime_switched` |
| Dev / exam split | `alpha/examset.py` — 72 exam cutoffs (digest `b55e065f…`), 316 development cutoffs |
| PIT panel | `alpha/out/panel.pkl`, built 2026-08-08: 249,029 rows, 540 cutoffs, 100 feature columns + 12 outcome/target columns. Development slice: 143,675 rows, 316 cutoffs, 594 symbols |
| Test count at audit | **718 collected · 655 passed · 63 skipped** (fast suite), green before any edit |
| Prediction interfaces | `validation/pit.fetcher` · `validation/predict.run` · `validation/score.main` · `validation/metrics.estimate/paired` · `alpha/pitdata.PriceBook.view` · `alpha/protocol.benchmark_scores` · `alpha/stats.Series/paired_difference` · `alpha/adapter.decide` (production weight 0.0) |

### 9.2 Dependency map — what this study adds and what it only reads

```
                    alpha/cache/*.csv          (vendor bars, untracked)
                            |
                    alpha/pitdata.PriceBook    THE DATA DOOR - truncates at cutoff
                            |
                    alpha/dataset.build  ->  alpha/out/panel.pkl        [READ ONLY]
                            |
                    alpha/examset.development_only   removes the 72 sealed cutoffs
                            |
      +---------------------+------------------------+
      |                     |                        |
 alpha/protocol       alpha/market_state       alpha/singlename
 benchmark_scores      (NEW - Layer 1)         (NEW - Layer 3)
 -> b3_rank            -> trend/vol/context    -> PastOutcomes  [THE LABEL DOOR]
 [READ ONLY]           reads panel columns     -> fit_arms S0..S4
                       only                    -> conformal interval
                                               -> decide  (BUY/HOLD/SELL/NO_EDGE)
                                                     |
                                    alpha/out/single_name_predictions.pkl
                                       FROZEN - no outcome column, no overwrite
                                                     |
                                            alpha/singlename_score   (NEW)
                                            joins labels, computes G1..G4
                                                     |
                                    alpha/out/single_name_scores.json
                                    reports/SINGLE_NAME_PHASE1.md
```

**Modified: nothing.** `protocol.py`, `dataset.py`, `targets.py`, `examset.py`, `stats.py`,
`adapter.py`, `pitdata.py` and every existing test are imported or left alone, never
edited. The study is additive: four new modules
(`market_state.py`, `singlename.py`, `singlename_score.py`, `singlename_config.py`),
one new test file, one pre-registration, one report.

---

*End of pre-registration. Committed before any single-name measurement exists.*
