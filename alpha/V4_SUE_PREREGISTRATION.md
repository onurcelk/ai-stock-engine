# V4-SUE — pre-registration. Slot 1 of the V4 budget.

**Written 2026-08-10, before the first fit and before any uncentred 20D predictive
quantity has been inspected.** This document is fixed. It is not edited after a result
exists; corrections are appended, dated, and leave the original wording visible — the
convention `V2_3_PREREGISTRATION.md` established.

Commissioned under `alpha/V4_CHARTER.md` (commit `6717111`). Authorised to proceed by the
passed power gate in `reports/V4_SUE_POWER_GATE.md` (block-length freeze `ee8fe3f`,
verdict `fdda61a`). **This spends V4 budget slot 1 of 2 when it runs — and it has not run.**

**Standing state at the moment of writing.** V3 CLOSED; Families 1/2/3 REJECTED; all three
V3 slots spent. Exam sealed at `b55e065f4c9f9173…` and **not valid as constituted for a
20-session question** (gate record §3.1). Production weight `0.0`. Nothing pushed. No V4
predictive point estimate has been computed into any inspected variable: the gate's paired
series was centred on formation and only the centred series was ever read.

---

## 1. The scientific question, frozen

### 1.1 Primary hypothesis

> **SUE contains incremental cross-sectional predictive information over B3 at the frozen
> 20-session horizon, under the frozen λ = 0.50 arm, of at least +0.0095 in native 20D
> IC.**

Formally: the mean paired per-cutoff difference `IC(Arm 1) − IC(B3)` on 20-session forward
alpha, over the 313 usable development cutoffs, is ≥ +0.0095, with a 95% L = 7 moving-block
bootstrap interval lying entirely above zero, positive breadth in both chronological
halves, and survival with `BEAR_TREND` removed.

**What falsifies it:** any one of the four criteria in §3. There is no fifth path to
CONTINUE.

### 1.2 This is a confirmatory test of the V4 formulation

**It is NOT:**

* **a new feature search** — one feature, frozen, no candidate pipeline;
* **a λ study** — λ = 0.50 is fixed, no curve is scanned, no curve point is promotable;
* **a horizon study** — one horizon, 20 sessions, no second horizon at any status
  including "diagnostic";
* **a learner study** — no model is fitted; this is an information-only test (§2.9);
* **a rescue of V3 Family 1** — Family 1 remains REJECTED under V3 at 5D through λ = 0.25,
  its result is not rescored, and nothing here changes it. V4 asks a different question of
  a different dependent variable, on the six-condition boundary in charter §3.2.

### 1.3 What each outcome means, stated before the result exists

| Outcome | Reading |
|---|---|
| All four criteria pass | The V4 formulation change worked: slow filing information is incrementally predictive at 20D where it was not at 5D |
| Any criterion fails | REJECT. Charter §8.2's default interpretation applies: changing the formulation did not rescue the only positively evidenced V3 information source |

---

## 2. The design, frozen in every element

All constants are encoded in `alpha/v4_sue_config.py`, committed with this document, so
the study module cannot drift from this text by a typo.

### 2.1 Target

**20-session forward alpha:** a name's 20-session forward return minus SPY's 20-session
forward return over the identical window. Built by `targets.realise(..., horizon=20)` —
the existing tested instrument, reused and not rewritten. Within-cutoff **Spearman IC** is
the metric, unchanged.

**One horizon only.** Measured: `corr(alpha_5d, alpha_20d) = 0.4962`, confirming a distinct
dependent variable sharing only its first five sessions.

### 2.2 Feature — carried unchanged from V3, in every particular

`sue`, time-series standardized unexpected earnings. **No element may be modified:**

| Element | Frozen value |
|---|---|
| Accounting field | `NetIncomeLoss` |
| Seasonal differencing | versus the year-ago quarter |
| Standardisation window | sd of the last **8** such surprises |
| Minimum history | **4** surprises |
| Q4 construction | FY − (Q1 + Q2 + Q3) |
| Winsorisation | per cutoff at the **1st/99th** percentile, before ranking |
| PIT rule | EDGAR **acceptance time**, `accepted (ET) < 16:00 ET` on the cutoff date, enforced in `alpha/filings.py` and by event replay in `alpha/filings_features.py` |
| Missing values | **NaN, never filled.** A name without a defined SUE is excluded from that cutoff's ranking. It is not imputed to the median, which would be a silent bet |

`staleness_days` remains a diagnostic and **may not become an input**, exactly as V3 §3
declared.

### 2.3 Sign

**`+1`, fixed by the original economic prior** (higher surprise → higher forward alpha),
set in `V3_PREREGISTRATION.md` §6.1 before Family 1 ran. **Never estimated from data.
Never flipped, at any stage, on any outcome.**

### 2.4 The two arms — two, and no third exists in this study

| Arm | Definition |
|---|---|
| **Arm 0 — standalone** | `rank_pct(sue)`, within-cutoff percentile, times sign +1 |
| **Arm 1 — bounded combination (primary)** | `rank_pct(B3) + 0.50 · (rank_pct(sue) − 0.5)` |

B3 is rank-transformed first, so the tilt's authority is a fixed fraction of the base
rather than an accident of B3's regime-dependent scale — the V3 construction, unchanged.

**λ = 0.50 is fixed. No λ curve is scanned. No point on any λ curve, V3's or a new one,
may be promoted to an arm.**

### 2.5 Incumbent and baselines

**Incumbent: B3** regime-switched momentum. Not modified, not swapped, not re-tuned.

**Mandatory baselines, all four:** **B1** 12-1 momentum, **B2** 5-day reversal, **B3**, and
**standalone SUE** (Arm 0 — required, not optional).

### 2.6 Sample

| | |
|---|---|
| Cutoffs | the **313** mechanically established usable development cutoffs |
| Excluded | the **3** whose 20-session window runs past the price calendar: 2026-07-14, 2026-07-21, 2026-07-28. **These are not restored under any circumstance** |
| Added | **none.** No new cutoffs, no history extension, no universe expansion |
| Exam | **the 72 exam cutoffs are not read, not scored, not inspected.** Disjointness is asserted in code before any scoring |
| Universe | the panel's point-in-time index membership, unchanged |

### 2.7 Bootstrap

Moving-block bootstrap, `alpha/stats.py`, **`BLOCK_LENGTH = 7`**, 10,000 draws. Frozen in
the gate record §2.4 and committed before any half-width existed. Newey–West with 6 lags
as a cross-check only.

**The block length is not shortened, lengthened or otherwise changed after a result is
seen.** A half-width computed at any other L is not a result of this study.

### 2.8 MDE

**+0.0095 native 20D IC versus B3.** Never lowered. Achieved half-width **0.005372**,
margin **1.77×** (gate record §4.5).

---

## 3. The CONTINUE rule — all four required

| # | Criterion | Encoding |
|---|---|---|
| **1** | Mean paired `Arm 1 − B3` **≥ +0.0095** | `bool(mean >= 0.0095)` |
| **2** | The 95% L = 7 block-bootstrap CI lies **entirely on the favourable side of zero** | `bool(lo > 0.0)` |
| **3** | **Breadth > 0.50** and **both chronological halves** of the paired contrast positive | `bool(hit_rate > 0.50 and both_halves_positive)` |
| **4** | The paired effect remains positive and **qualifying** with `BEAR_TREND` cutoffs removed | `bool(ex_bear_mean >= 0.0095)` |

**Anything less is REJECT.**

Criterion 2 uses **Amendment A1 logic**: an interval lying entirely *below* zero is a
**FAIL**, not a pass. The direction-blind form `lo > 0 or hi < 0` is not used.

Halves convention, frozen: the series is split at `(n + 1) // 2` with the odd cutoff going
to the **first** half — the V3 `_halves` convention, unchanged, giving 157 / 156.

**No intermediate status exists.** There is no "promising", no "near miss", no
"directionally supportive", no "worth another look". A positive point estimate with an
interval spanning zero is REJECT — that is exactly V2.1-D's +0.01312, and treating it as
promising is what bought three more studies.

---

## 4. The standalone horizon diagnostic — mandatory, and non-overriding

V4's hypothesis is specifically that the longer horizon reveals information not expressed
at 5D. Arm 0's standalone 20D IC is therefore recorded as a **mandatory diagnostic** and
compared against a benchmark fixed here:

> **P = +0.0261 native 20D** — SUE's pure √(H/5) extrapolation from its completed V3 5D
> standalone result of +0.01305. This is the value implied if the horizon buys scaling and
> **no** informational gain.

Interpretation, pre-registered, using the standalone estimate's own achieved half-width
`h₀` as the yardstick so the bands are mechanical rather than eyeballed:

| Standalone 20D IC | Reading |
|---|---|
| **> P + h₀** | Materially above P — evidence **supporting** the horizon mechanism |
| **within P ± h₀** | Approximately P — **no informational gain** from the horizon, only scaling |
| **< P − h₀** | Below P — evidence **against** the horizon mechanism |

**This diagnostic may not override the primary Arm 1 − B3 decision in either direction.** A
standalone result above P does not rescue a failed primary contrast, and one below P does
not veto a passing one. It answers *why*, not *whether*.

**P is not changed after realized 20D B3 or SUE values are seen.** Charter §7.3 forbids
substituting a realized value into the screen, and the same prohibition governs P here.

---

## 5. Economic significance — primary from the first measurement

### 5.1 What is reported

Using the frozen portfolio convention (top-minus-bottom **quintile**, `QUINTILE = 0.2`,
mean forward alpha per cutoff, minimum 25 names — the V3 `_spread_series` function,
unchanged):

* **gross spread advantage** versus B3, per cutoff, with its own CI and half-width;
* **added turnover** versus B3;
* **transaction-cost adjustment** at the frozen **5 bps** assumption;
* **net spread advantage** = gross − cost drag.

**Gross and net are reported separately and are never blended into a single headline.**

### 5.2 A cost-accounting consistency point, settled before measurement

The MDE's cost model assumes **13 rebalances/year** — a 20-session holding period. But the
cutoff grid is 5 sessions, so turnover measured between *consecutive* cutoffs implies ~52
rebalances/year and would overstate the cost the MDE priced.

Frozen resolution: **both** are reported, and the one applied to the net figure is the one
the MDE was derived under.

| Turnover measure | Role |
|---|---|
| Consecutive-cutoff (5-session stride) | reported, comparable with the V3 record |
| **20-session stride (`HOLDING_CUTOFF_STRIDE = 4`)** | **the cost adjustment applied to the net figure**, matching the 13/year model behind the MDE |

This changes no threshold. It makes the cost accounting consistent with the MDE that was
already frozen, and it is declared here rather than chosen after seeing a number.

### 5.3 The adverse prior, recorded before measurement

**(V3)** SUE's 5D long-short spread did **not** clear zero: +0.00051, CI [−0.00081,
+0.00158] — the signature of a factor that ranks the middle of the cross-section rather
than its tails, which is where a portfolio must trade.

> **Declared now: a second failure to generate tail-level economic value at 20D is
> adverse evidence against the family, even if rank IC is positive.** It will be recorded
> as such in the diagnosis and not re-described as a technicality, a "rank-level success",
> or a portfolio-construction problem to be solved later.

The 5 bps assumption is a **research stress test, not a claim about the account holder's
actual brokerage fees.** It is not changed after a result is seen.

---

## 6. Multiplicity

**Two declared arms, one primary contrast, one target, one horizon** — declared here,
before the first computation.

**Holm–Bonferroni across the two arm-level primary contrasts** (Arm 0 − B3 and Arm 1 − B3),
using the frozen `stats.holm_bonferroni`. Both **raw** and **Holm-adjusted** p-values are
reported side by side.

**A statistically significant negative result is evidence against the hypothesis, not a
PASS.** Significance is not the criterion; the four-part rule in §3 is, and criterion 2 is
direction-aware by Amendment A1.

---

## 7. Noise control — powered as a gate, not a gesture

**30 paired within-cutoff permutations** of SUE. Each draw replaces `sue` with a random
permutation of the SUE values **within each cutoff**, preserving the cross-sectional
distribution and destroying only the identity-to-value mapping.

**Preserved in every draw:** cutoff structure, the cross-sectional distribution of SUE,
B3, the sample of 313, and the bootstrap procedure at L = 7. **Destroyed:** only the
identity-to-SUE mapping.

### 7.1 The threshold, restated in native 20D units mechanically

V3's limit was a median of **+0.002** against a CONTINUE threshold of **+0.010** — a ratio
of **0.20**. That ratio is dimensionless and horizon-free, so it carries across directly:

> **`NOISE_MEDIAN_LIMIT = +0.0019` native 20D** = 0.20 × the frozen MDE of +0.0095.

**Why this restatement and not the alternative.** Scaling instead by the achieved
half-width ratio (0.005372 / 0.00229 = 2.346) would give +0.00469. That was rejected as a
**§2.11 gesture**: projecting V3's noise-draw sd of 0.00096 to 20D by the same ratio gives
≈ 0.00225, so the median of 30 draws has a standard error of ≈ 0.000515 — a limit of
+0.00469 sits **9.1 SE** above a zero median and could essentially never fire. The chosen
+0.0019 sits **3.7 SE** above zero: strict enough to catch a genuine artefact, loose enough
that it cannot fire on sampling noise. That is exactly the balance §2.11 demands.

For reference, V3 Family 1's actual noise control ran median **−0.00045**, sd 0.00096, with
**0.0%** of draws above threshold.

### 7.2 The firing rule

The control fails, and **the study is void**, if either:

* the **median** of the 30 draws exceeds **+0.0019** (native 20D), or
* more than **10%** of draws (i.e. ≥ 4 of 30) reach the CONTINUE threshold of **+0.0095**.

**A single draw's result is never grounds to abort.** The sampling spread of the control is
reported next to its median.

---

## 8. Required reported diagnostics

Every item below is reported whatever the outcome. A point estimate without its resolution
is not a result (§2.6).

**Primary contrast:** Arm 1 − B3 point estimate · 95% L = 7 CI · half-width · n · breadth ·
chronological halves · full regime decomposition · ex-`BEAR_TREND` result.

**Standalone:** SUE 20D IC and CI · comparison against **P = +0.0261** under §4's bands.

**Relative:** Arm 1 vs B1 · Arm 1 vs B2 · Arm 0 vs B1 and B3.

**Economic:** turnover on both strides (§5.2) · gross spread advantage with CI · cost drag ·
net spread advantage.

**Inference:** raw p-values · Holm-adjusted p-values · Newey–West cross-check.

**Controls:** noise-control distribution (median, sd, exceedance share, full spread) ·
**SUE coverage** · **book-tail formability** — that both quintile tails can be formed at
every cutoff, the Family 2 lesson made a reported gate. Coverage floor **0.80**; the gate
run measured 0.9299 on the 20D rows and both tails formable.

Results are written to `alpha/out/v4_sue_development.json` and `.pkl` with **per-cutoff
series**, so every headline number is re-derivable from per-cutoff data rather than from a
summary — the property that let the V2.3 audit check itself.

---

## 9. Prohibited from the moment this document is committed

* no second horizon, and **no 5D / 10D / 40D / 60D diagnostic** at any status;
* no alternative target — not volatility-adjusted, sector-neutral, residual, or
  differently winsorised;
* no λ scan, no λ change, no promotion of a curve point to an arm;
* no sign flip;
* no feature modification, no new accounting field, no second SUE construction;
* no new learner, no fitted model, no third arm;
* no benchmark substitution and no modification of B3;
* no sector-neutral rescue, no regime-only rescue, no favourable-period subset;
* no dropping of weak cutoffs and no restoration of the 3 excluded ones;
* no threshold reduction — not the MDE, not the CI rule, not the coverage floor;
* no alternate bootstrap block length;
* no new data source and no data purchase (§27B);
* **no SUE′** under any name;
* **the old exam is not inspected**, and **no new exam is designed yet**;
* production weight is not raised and `alpha/adapter.py` is not modified;
* **no `git push`** (§27A — `origin` is a third party's public repository).

---

## 10. Decision consequences, fixed prospectively

### 10.1 If V4-SUE REJECTS

**V4 Slot 1 is SPENT. This alpha-research line stops.**

Do **not**: open Slot 2 by default · try 13F · try another horizon · try another λ · try
another filing source · create a V4-SUE′ · create V5 as an automatic continuation.

Charter §8.3's four conditions are the *only* route to Slot 2, and a clean failure under
adequate power satisfies none of them by default — §8.3(1) requires the standalone 20D IC
to materially exceed P, which §4 measures.

**Required deliverable on rejection:** a final comparative diagnosis across **V1 → V4** —
what was tested, what was resolvable, and what the four programmes jointly establish about
free point-in-time data on this universe — together with a recommendation to **transition
to direct single-name product validation** (roadmap Phase 7b), which is a different
research object from cross-sectional alpha and is not blocked by this result.

### 10.2 If V4-SUE PASSES

**Stop before** production, before any learner or model fitting, before exam construction,
and before exam opening.

Production weight remains **`0.0`**. A new 20-session untouched exam — which the sealed
72-cutoff exam cannot serve, per gate record §3.1 — requires **separate explicit
authorization** and is not designed, specified or costed as part of this study.

---

## 11. Recording

* This document and `alpha/v4_sue_config.py` are committed **before** the study module
  exists and before any uncentred 20D predictive quantity is inspected.
* The study module, when authorised, imports its constants from `v4_sue_config.py` rather
  than restating them.
* `reports/EXPERIMENT_REGISTRY.md` receives the full entry on completion: hypothesis,
  source, target/horizon, arms, MDE, achieved half-width, result with its half-width,
  stability, net of costs, decision, and the diagnosis — **did the information fail, or
  the target, the horizon, the PIT quality, the coverage, the economics, or the power?**
* Every run is logged, **including aborted and superseded ones** (§2.7).

**V4-SUE is not authorised to run by this document.** It is pre-registered and awaiting
separate explicit authorization to execute.

---

## Pre-measurement clarification — 2026-08-10

**Added before the first fit, before any uncentred 20D predictive quantity exists.**

§2.1 states the target is "Built by `targets.realise(..., horizon=20)`". The
implementation instead calls `pitdata.PriceBook.forward_return(cutoff, 20, symbols)` and
`pitdata.PriceBook.forward_return(cutoff, 20, ["SPY"])` directly, computing
`alpha_20d = asset_return − spy_return` per cutoff. The reason is that
`targets.realise()` (line 165 of `alpha/targets.py`) hardcodes the output column name as
`"alpha_5d"` regardless of the `horizon` parameter passed to it.

The return computation is mathematically identical: `targets.realise()` calls the same two
`book.forward_return()` methods (lines 153–154 of `alpha/targets.py`) and performs the
same subtraction (line 165). The direct construction avoids only the misleading column
name.

**This clarification changes no hypothesis, threshold, sample, feature, target definition,
statistic, arm, decision rule, or any other element of this pre-registration.** The
dependent variable remains 20-session forward alpha = asset return minus SPY return over
the identical 20-session window.
