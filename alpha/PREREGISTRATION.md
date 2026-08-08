# V2 pre-registration

**Written 2026-08-08, before any model was fitted and before any IC number
existed.** Directive §15 and §21 require the success thresholds to be fixed in
advance, because the failure mode they exist to prevent — reading a marginal
result and then deciding what "good" meant — is invisible after the fact.

What had been run when this file was written: the universe download, the
point-in-time membership reconstruction, and the eligibility counts in §2
below. Those are properties of the data, not results of an experiment. No
target had been computed, no feature matrix built, no model fitted.

---

## 1. Question

At a cutoff *T*, using only information available at *T*, can a model rank a
cross-section of liquid US equities by their next-5-session return **in excess
of SPY**, better than the best simple momentum/relative-strength factor?

Not "can it predict direction". Direction was the V1 question and the V1 answer
was no.

---

## 2. Universe

Liquid US equities that were **S&P 500 constituents as of the cutoff**,
membership reconstructed from the index change log (`alpha/membership.py`).
Excluded: crypto, FX, broad-market and commodity ETFs (§2).

Eligibility at *T*, all computed from pre-cutoff bars:

| Filter | Threshold |
|---|---|
| Index member as of *T* | reconstructed, not current |
| Daily bars available | on disk covering *T* |
| History behind *T* | ≥ 252 sessions |
| Median dollar volume, trailing 60 sessions | ≥ \$3,000,000 |
| Last close | ≥ \$3 |
| Sessions since last print | ≤ 5 |

Resulting cross-section width, measured before any experiment:

| Cutoff | Index members | Priceable | Eligible | Coverage |
|---|---|---|---|---|
| 2016-06-01 | 506 | 431 | 410 | 85.2% |
| 2018-06-01 | 506 | 448 | 439 | 88.5% |
| 2020-03-16 | 506 | 458 | 453 | 90.5% |
| 2022-03-08 | 506 | 475 | 471 | 93.9% |
| 2024-08-13 | 504 | 492 | 488 | 97.6% |
| 2026-07-24 | 503 | 503 | 500 | 100.0% |

This is the §2 fix, taken as option (a): 410–500 names per cross-section rather
than 22. The universe-size caveat that would otherwise have blocked the ranker
is therefore **addressed, not accepted**. The V1 22-name watchlist is retained
as a secondary universe for the like-for-like comparison in deliverable 6, and
any result on it carries the §2 "methodology signal, not production evidence"
label.

**Residual survivorship, disclosed:** 127 of 781 ever-members have no Yahoo
bars at all. Coverage is 85% in 2016 and 100% today, so early cutoffs are
missing ~15% of the true cross-section, biased toward names that were later
acquired or delisted. This is a real limitation and it is stated in every
report rather than netted out.

---

## 3. Target

Primary (§4):

```
future_asset_return_5d = Close[T+5] / Close[T] - 1
future_spy_return_5d   = SPY[T+5]   / SPY[T]   - 1
alpha_5d               = future_asset_return_5d - future_spy_return_5d
```

Horizon: **5 trading sessions**, on the SPY calendar. The 4-hour after-close
horizon is excluded from V2 entirely (§3). The 1-day horizon is not optimised
in this pass.

Winsorised at the 1st/99th percentile **within each cutoff date** before
training, so a single-name blow-up cannot dominate squared error. IC is computed
on the un-winsorised target.

Secondary targets, used only where the experiment sequence says so:
sector-relative return (§1C), cross-sectional percentile rank (§5), and
volatility-scaled excess return (§6, V2-F only).

Residual alpha (§1D) uses β estimated on a **252-session rolling window ending
at T-1**, minimum 120 observations, shrunk toward 1.0 by
`w = τ²/(τ² + se(β)²)` with `τ = 0.5`. Sector beta is estimated against the
sector series orthogonalised to SPY, so the two loadings are not fighting over
the same variance. No expanding window is used anywhere.

---

## 4. Sector

Sector returns are the **leave-one-out equal-weighted mean return of the
eligible index members in the same GICS sector at that cutoff**, not a sector
ETF. Members are point-in-time, so the peer group changes as the index does,
and leave-one-out means no name is ever compared against a group containing
itself.

**Disclosed leakage channel (§1):** sector *labels* are today's GICS assignment
applied backwards. Membership is point-in-time; classification is not. See
`membership.sector_drift_note()`. Sector-relative features and the
sector-relative target inherit this error.

---

## 5. Cutoff schedule, embargo, and the exam paper

**Cutoffs:** every 5th session from 2016-01-04 to the last date with a complete
5-session outcome. With H = 5, a 5-session spacing makes consecutive outcome
windows exactly adjacent and **non-overlapping**, which is §5 option (a).

**Exam paper:** the 12 frozen V1 cutoffs (2022-03-08, 2022-10-10, 2024-08-13,
2024-09-05, 2024-12-10, 2025-03-27, 2025-06-23, 2025-11-28, 2026-02-06,
2026-05-07, 2026-07-07, 2026-07-24). Per §19 these are **never touched during
development**. They are evaluated exactly once, after development is closed,
and reported whatever they say.

**Purge and embargo (§5, §20):** development cutoffs falling within ±10
sessions of any exam cutoff are dropped, so no development fit ever trains on a
window that overlaps or abuts an exam outcome.

**Walk-forward (§19):** expanding window. For a test cutoff *T*, training uses
only cutoffs *T′* with `T′ + 5 + 5 ≤ T` — the horizon plus a 5-session embargo.
Refit every 13 cutoffs (quarterly). Minimum 60 training cutoffs before the
first prediction is made, so the first evaluated development cutoff is in 2017.

---

## 6. Features

**V2-A — absolute only.** Momentum (1/3/5/10/20/60d returns), trend
(`close/SMA20 − 1`, `/SMA50`, `/SMA200`, continuous), RSI(14), volume ratio and
volume surprise, realised volatility (5/20/60d).

**V2-B — adds relative and percentile.** Every V2-A family also as a spread vs
SPY, a spread vs the leave-one-out sector, and a within-cutoff cross-sectional
percentile. Absolute features are **retained**, not replaced (§7-8).

**V2-E — adds context.** SPY/QQQ trend and vol, VIX level / percentile /
change, deterministic regime state, `watchlist_breadth_proxy`, and the
overnight/intraday decomposition of §9.

**Denominator guard (§7-8 correction):** every ratio feature divides by
`max(denominator, floor)` with a floor of 1e-8 in return units and a
\$3M/session floor on volume enforced upstream by the eligibility filter. Any
feature that is still non-finite becomes NaN; the model handles NaN natively
and NaN is never imputed with a cross-sectional mean, which would leak.

**Breadth (§11 correction):** breadth over the 22-name V1 watchlist is named
`watchlist_breadth_proxy` in the schema and is reported as a proxy. Breadth over
the full point-in-time index cross-section is named `index_breadth` and is the
real series.

---

## 7. Models

**Model A — alpha regression.** `sklearn.ensemble.HistGradientBoostingRegressor`
(lightgbm/xgboost are not installed in this environment; this is the same
histogram-binned GBDT algorithm). Hyperparameters fixed here and **not tuned**
(§14 "do not over-tune"):

```
loss=squared_error, max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
min_samples_leaf=100, l2_regularization=1.0, max_bins=255,
early_stopping=False, random_state=0
```

**Model A′ — simple factor baselines, run before Model B (§14).** Six factors,
each ranked within cutoff: 5d, 20d and 60d momentum; 12-1 momentum (252d
excluding the last 21d); 20d relative strength vs SPY; 20d relative strength vs
sector. Each is evaluated at its **natural positive sign**. The "best simple
factor" used for the gate is chosen by |mean IC| **on the development set
only**, its sign fixed there, and applied unchanged to the exam set. Choosing
either the factor or its sign on exam data is forbidden.

**Model B — LambdaRank cross-sectional ranker**, and **Model C — sector-neutral
ranker**, only if the §8 gate passes.

---

## 8. Success thresholds — fixed now (§15)

Primary metric: **Spearman IC between predicted and realised `alpha_5d`, per
cutoff**, then aggregated across cutoffs.

Statistics: cutoffs are non-overlapping by construction; on top of that every
interval is reported with a **moving-block bootstrap** (block length 4 cutoffs
≈ one month, 10,000 resamples) and a **Newey–West** standard error with 4 lags.
The naive i.i.d. interval is printed alongside so the difference is visible, in
the same style as the V1 report's naive-vs-clustered columns.

A model is declared to have **demonstrated alpha** only if **all** of:

| # | Criterion | Threshold |
|---|---|---|
| 1 | Mean Spearman IC | > 0.03, 95% block-bootstrap CI excludes 0 |
| 2 | IC hit rate | > 55% of cutoffs, 95% CI excludes 50% |
| 3 | Top-minus-bottom quintile spread | > 0, 95% CI excludes 0 |
| 4 | Sign stability | mean IC > 0 in ≥ 60% of cutoffs |
| 5 | Beats best simple factor | paired per-cutoff IC difference vs Model A′, 95% CI excludes 0 |
| 6 | No regime collapse | mean IC > 0 in each of BULL / BEAR / SIDEWAYS and in HIGH_VOL and LOW_VOL |
| 7 | Effective sample | ≥ 50 independent (non-overlapping) cutoffs |

Criterion 5 is the bar §18 calls "the single most important in the whole
directive". It is not relaxed if results are disappointing.

**Gate on the ranker (§14, §27):** Model B / V2-C is only built if Model A or
the V2-B feature set passes criteria 1–5 **on the development set**. If neither
does, the ranker is not built, and the report says so.

**Multiplicity:** seven experiments are planned. p-values are reported raw and
with a Holm–Bonferroni adjustment across the experiments actually run. Passing
a threshold only on the raw p-value is reported as not passing.

---

## 9. ModelEvidence gating (§22)

Production weight > 0 requires all seven criteria above **on the exam set**,
not the development set. Anything else is weight 0 and the production action
stays HOLD. This is the same bar that gated the V1 LSTM out 257 times out of
257; it is not lowered because the architecture is newer.

Confidence (§23) is not built in this pass and no confidence number is exposed.

---

## 10. Failure rule (§28-29)

If mean IC is ≈ 0, or the top-minus-bottom spread is ≈ 0, or the model does not
beat the best simple factor, the correct outcome is **to record that and stop**.
Specifically, the following are ruled out in advance:

* adding features, models or ensembling in an attempt to rescue a failed gate;
* re-running the exam dates after seeing them;
* relaxing any threshold in §8;
* reporting a raw p-value as a pass when the adjusted one fails;
* switching the headline metric to one that happens to look better.

A negative result is a complete deliverable. The V1 report is the standard: it
concluded its own neural forecaster was a no-op and said so.

---

## 11. Experiment sequence (§27)

| ID | Change | Gate to proceed |
|---|---|---|
| V2-A | Absolute features, alpha_5d regression | — |
| V2-B | + relative and percentile features | — |
| V2-C | LambdaRank ranker | A or B passes §8.1–8.5 on dev |
| V2-D | Sector-neutral ranking | V2-C passes |
| V2-E | + regime / VIX / breadth / overnight | — |
| V2-F | Volatility-scaled target | — |
| V2-G | Ensemble + ModelEvidence + production integration | §9 satisfied on exam |

Model A′ (simple factors) is measured first and is the reference for every gate.
