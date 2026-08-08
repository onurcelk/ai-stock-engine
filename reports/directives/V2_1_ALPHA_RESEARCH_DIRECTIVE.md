# V2.1 Alpha Research — Freeze a Stronger Exam Before Any Model Changes

We have completed the V2 alpha study.

The conclusion is:

* V2 did **not** demonstrate production-grade alpha.
* Production weight must remain **0**.
* Production action remains **HOLD**.
* Do not modify production behavior to force a signal.
* Do not reopen the V2 gate after seeing the results.
* Do not re-run or alter the existing 12-date V2 exam.
* Preserve all existing artifacts and reports exactly as historical records.

The V2 study nevertheless produced several important findings:

1. V2-A → V2-B added 47 stock-level relative/percentile features but mean IC only moved:
   `+0.00837 → +0.00846`
   This is effectively a null result.

2. Most of the V2 signal came from market-context features:
   regime, VIX, breadth, overnight/intraday decomposition.

3. V2-F reached:

   * mean IC +0.03179
   * IC CI [+0.0140, +0.0507]
   * hit rate 56.97%
   * spread +0.00257
     but failed:
   * sign stability
   * superiority to the baseline
   * regime stability

4. The regime preference inverted between development and exam.

5. On the frozen exam, simple 12-1 momentum outperformed V2-F:

   * 12-1 momentum long-short: +0.00849
   * V2-F long-short: +0.00462

6. The existing 12-date exam is statistically underpowered for the pre-registered criteria. Criterion 7 requires ≥50 independent cutoffs, while the exam has only 12.

7. The baseline-selection rule based on absolute development IC selected 5-day reversal, while 12-1 momentum is a more meaningful economic benchmark and performed better on the exam.

8. Two correctness bugs were found and fixed:

   * dead `ret_12_1`
   * missing exam dates in the panel
     Both now have regression tests.

The next step is therefore NOT "add more features" and NOT "make V2 pass".

The next step is to create a scientifically stronger validation protocol.

---

## PRIMARY OBJECTIVE

Before making any model improvement, create and freeze a new, adequately powered, independent exam set of at least 60 non-overlapping cutoffs.

The exam must be frozen BEFORE any new model development is evaluated against it.

This is the highest-priority task.

Do not use the new exam results to select features, models, hyperparameters, thresholds, regimes, or baselines.

---

# 1. Preserve V2 exactly

Do not rewrite history.

Keep:

* `PREREGISTRATION.md`
* `EXPERIMENT_LOG.md`
* `V2_REPORT.md`
* all existing `alpha/out/` artifacts
* the archived dead-feature run
* the existing 12-date exam results
* existing tests

The existing V2 study is a completed experiment.

If documentation needs to mention V2.1, create a new document rather than silently changing the V2 report.

Suggested:

`alpha/V2_1_PREREGISTRATION.md`

Do NOT edit the old V2 preregistration.

---

# 2. Design V2.1 before implementation

Create a short V2.1 preregistration describing:

### Development set

Use the historical universe and point-in-time methodology already established by V2.

Maintain:

* 5-session prediction horizon
* excess return target:
  `R_asset - R_SPY`
* non-overlapping 5-session outcome windows
* point-in-time universe
* no future information
* walk-forward training
* purging/embargo around exam observations

### Exam set

Create a new frozen exam containing at least:

**60 independent cutoffs**

Preferably 60–100 if the available history allows it.

The exam cutoffs must:

* be separated by at least the 5-session forecast horizon
* not overlap outcome windows
* be completely excluded from model training
* be frozen before model comparison
* cover different market conditions
* include bull, bear and sideways periods where available
* include high- and low-volatility periods where available
* not be selected because they look good for any particular strategy

Do not cherry-pick dates based on returns.

The selection rule must be deterministic and documented.

If the available historical range cannot support 60 truly independent dates under the current methodology, report the maximum defensible number instead of relaxing the independence requirement.

---

# 3. IMPORTANT: prevent exam leakage

The new exam must not influence:

* feature selection
* baseline selection
* model selection
* hyperparameter tuning
* regime definitions
* thresholds
* feature engineering
* target construction
* stopping criteria

The development process must be able to run without reading the new exam results.

Add automated tests proving:

1. exam cutoffs are excluded from training
2. no training target overlaps an exam target window
3. no exam result is imported into development
4. the frozen exam cannot accidentally be used by `develop`
5. every frozen exam cutoff exists in the built panel
6. all exam cutoffs are independent under the 5-session horizon

---

# 4. Fix the benchmark policy before seeing V2.1 results

The old baseline rule:

> choose the factor with maximum absolute development IC

should NOT be reused blindly.

Create a pre-committed benchmark hierarchy.

At minimum include:

### Benchmark 1 — 12-1 momentum

The simple cross-sectional momentum factor already implemented as:

`mom_12_1`

This should be the primary economic benchmark.

### Benchmark 2 — 5-day reversal

Keep the existing:

`mom_5d` with its development-determined reversal sign.

This is included because it was the original V2 benchmark.

### Benchmark 3 — simple market/context rule

Only if a deterministic, pre-registered rule can be defined without fitting it to the new exam.

Do not invent this benchmark from the new exam results.

The critical question for future models is:

> Does the complex model add predictive information beyond a simple 12-1 momentum factor?

---

# 5. Do NOT build a new large model yet

Before changing V2 features or architecture, create the new frozen validation framework.

Do not:

* add hundreds of features
* search hyperparameters
* add neural networks
* add transformers
* tune regimes
* tune thresholds
* optimize specifically for the existing 12-date exam
* change the production adapter

The purpose of this stage is to improve the experiment, not to improve the score.

---

# 6. Create a clean V2.1 research ladder

After the exam is frozen, prepare the development-only experiment structure.

The intended research question is:

> Can market context add information to a simple 12-1 momentum baseline, and can a learned model consistently outperform that baseline out-of-sample?

The ladder should be:

### V2.1-A

12-1 momentum only.

### V2.1-B

12-1 momentum + existing market-context features.

### V2.1-C

12-1 momentum + context + carefully justified additional features.

### V2.1-D

Learned nonlinear model using the above information.

Do not automatically implement all of these now.

First establish the preregistration and frozen exam.

Every additional model must have a clear scientific reason for existing.

---

# 7. Evaluation criteria

Keep the spirit of the original V2 criteria, but review their compatibility with a ≥60-date exam.

At minimum measure:

1. mean Spearman IC
2. confidence interval
3. IC hit rate
4. top-minus-bottom spread
5. spread confidence interval
6. superiority versus 12-1 momentum
7. superiority versus 5-day reversal
8. sign stability
9. regime stability
10. turnover
11. transaction-cost-adjusted return
12. number of independent cutoffs

Do not lower thresholds merely because a model performs poorly.

If a criterion needs modification because V2 exposed a methodological problem, document the reason BEFORE the new model is evaluated.

---

# 8. Statistical methodology

Keep the existing block-bootstrap / time-series-aware methodology where appropriate.

Explicitly document:

* what constitutes one independent observation
* block length
* why that block length is appropriate
* multiple-comparison correction
* whether p-values are one-sided or two-sided
* how confidence intervals are generated
* how multiple candidate models are handled

Avoid interpreting many stocks on one date as independent observations.

The primary independent unit should remain the cutoff/date.

---

# 9. Regime analysis

Do NOT select regimes based on the new exam.

Use the existing regime definitions initially.

However, because V2 showed that its regime edge inverted between development and exam, explicitly test:

> Does the sign and magnitude of the model remain directionally stable across regimes?

A model must not be considered robust merely because its aggregate IC is positive.

Do not allow a regime to become a post-hoc explanation for a failed model.

---

# 10. Production remains untouched

Do not change:

`alpha/adapter.py`

Do not change:

* production weight
* HOLD logic
* evidence thresholds
* production schema

Production remains:

**weight = 0**

until a future preregistered experiment demonstrates sufficient evidence.

---

# 11. Tests

Maintain the existing 499+ passing test requirement.

Add tests for the new validation protocol, especially:

* ≥60 exam cutoffs where possible
* deterministic exam construction
* no duplicate cutoffs
* no overlapping target windows
* exam dates absent from training
* no leakage from exam into development
* all exam dates present in panel
* `mom_12_1` is alive
* no feature is silently all-NaN
* production remains HOLD when validation is absent/insufficient

Run:

`pytest -q --runslow`

and report the result.

---

# 12. Deliverables for this stage

Do NOT start model optimization until these are complete.

Create:

1. `alpha/V2_1_PREREGISTRATION.md`
2. a deterministic frozen exam-set artifact
3. metadata describing every exam cutoff
4. a validation/leakage test suite
5. a short design note explaining why the exam set is statistically adequate
6. any required code changes to make the exam genuinely isolated

Then produce a concise report:

### V2.1 Validation Setup

Include:

* number of development cutoffs
* number of frozen exam cutoffs
* date range
* horizon
* purge/embargo
* regime distribution
* volatility distribution
* benchmark definitions
* independence definition
* statistical methodology
* leakage tests
* test count

Most importantly:

**Do not evaluate a new model on the new exam yet.**

The exam must first become immutable.

---

# Final instruction

Think like a quantitative researcher, not like a feature-generation assistant.

The goal is NOT to make the next experiment produce a positive number.

The goal is to make the next positive number, if it occurs, much harder to dismiss as:

* selection bias
* regime luck
* benchmark weakness
* insufficient sample size
* leakage
* overfitting
* multiple testing
* or a few extreme dates.

Do not change the production verdict.

Do not optimize against the old 12-date exam.

Do not widen any existing V2 gate.

First build and freeze the stronger V2.1 validation protocol. Then stop and report what was created before proceeding to model development.
