# V2.1 Research Ladder — Preregister Before Any Fit

The V2.1 validation setup is now complete and frozen.

We have:

* 72 frozen exam cutoffs
* 316 development cutoffs
* a fixed exam artifact
* fixed benchmark hierarchy
* nine production gates
* leakage tests
* 527 passing tests
* production weight = 0
* production action = HOLD

The new exam has NOT been evaluated by any model.

This instruction starts the next stage: preregister the V2.1 research ladder and then run development-only experiments.

## ABSOLUTE RULE

The frozen V2.1 exam must remain completely untouched.

Do NOT:

* score any model on the exam yet
* inspect exam predictions
* inspect exam IC
* inspect exam returns
* use exam performance for feature selection
* use exam performance for model selection
* modify the frozen exam dates
* regenerate the exam artifact
* change any V2.1 gate after seeing development results
* change the benchmark hierarchy
* change the thresholds after seeing development results

The exam may be opened exactly once, after development research is complete and one arm has been selected according to the preregistered rule.

---

# OBJECTIVE

The research question is now:

> Does market context add predictive information beyond simple 12-1 cross-sectional momentum, and can a learned nonlinear model consistently outperform that benchmark out of sample?

V2 already established that adding large numbers of stock-relative/percentile features to the absolute feature set produced essentially no improvement.

Therefore this experiment must NOT become another uncontrolled feature hunt.

The research ladder should test whether:

1. simple 12-1 momentum works;
2. market context adds information to it;
3. carefully justified additional information adds anything beyond momentum + context;
4. a learned nonlinear model extracts additional information beyond those simpler models.

---

# 1. CREATE V2_1_EXPERIMENT_PREREGISTRATION.md FIRST

Before fitting ANY model, create:

`alpha/V2_1_EXPERIMENT_PREREGISTRATION.md`

It must contain the complete ladder, feature families, model definitions, metrics, selection rule, family size for multiplicity correction, and stopping rules.

Do not fit anything until this file exists.

The preregistration must be immutable after the first fit.

Add a test or equivalent guard making accidental post-fit edits detectable.

---

# 2. PRE-REGISTER EXACTLY FOUR PRIMARY ARMS

Use the following conceptual ladder.

## V2.1-A — 12-1 momentum baseline

This is deliberately simple.

Prediction:

`mom_12_1`

No learned model.

This establishes the economic benchmark inside development.

Do NOT optimize its parameters.

Do NOT tune the lookback.

The factor is exactly the existing `ret_12_1` definition.

Evaluate:

* mean Spearman IC
* IC hit rate
* top-bottom spread
* turnover
* cost-adjusted spread

This is the primary reference.

---

## V2.1-B — momentum + market context

Add the already-established market-context information that V2 found useful.

Use only the existing, pre-defined context features.

At minimum document exactly which existing features belong to this family, such as:

* market regime
* VIX
* breadth
* overnight/intraday decomposition
* market-level volatility/context

Do NOT add new context features opportunistically.

Do NOT tune the context feature list after seeing results.

The model architecture should be fixed before fitting.

Prefer a simple regularized model first.

The purpose of B is specifically:

> Does market context add information to 12-1 momentum?

---

## V2.1-C — momentum + context + justified additions

This arm may add a small, explicitly justified feature family.

The additions must be based on an economic hypothesis, not on development correlation mining.

Potential families may include:

* volatility / risk
* liquidity
* price-volume structure
* medium-term trend
* market-relative information

But choose the exact family BEFORE fitting and document:

* why it should contain information
* which exact features are included
* which features are excluded
* why the family is small enough to avoid uncontrolled search

Do NOT create hundreds of variants.

If there is no sufficiently justified additional family, C may be defined as a null/holdout arm rather than inventing features.

---

## V2.1-D — learned nonlinear model

Use a single pre-specified nonlinear model family.

Prefer the existing available stack and avoid introducing unnecessary dependencies.

For example:

* LightGBM if already available
* otherwise XGBoost if already available
* otherwise a carefully regularized tree ensemble already supported by the environment

Do NOT turn this into a hyperparameter sweep.

At most define a very small fixed hyperparameter configuration in the preregistration.

The model must be a pointwise cross-sectional predictor/ranker unless there is a strong existing reason to change the target formulation.

Do not call it LambdaRank unless the actual implementation is LambdaRank.

---

# 3. IMPORTANT: NO FEATURE SEARCH

Do NOT do:

* hundreds of feature combinations
* recursive feature elimination
* unbounded feature selection
* correlation-based feature hunting
* selecting features because they improve development IC
* trying many lookback periods and keeping the best
* trying many targets and keeping the best
* trying many model architectures and keeping the best
* regime-specific tuning
* threshold optimization

The purpose is to test hypotheses, not mine the development set.

If a feature family is tested, it must be defined before the fit.

---

# 4. MODEL TRAINING PROTOCOL

All learned arms must use walk-forward training.

At each cutoff:

* train only on information available before that cutoff
* respect the existing purge/embargo rules
* never train on future cutoffs
* never use exam observations
* never use future membership
* never use future feature values
* never use future targets

Do not alter the existing point-in-time universe implementation.

Do not alter the 5-session target.

Do not change the 72-date exam.

---

# 5. DEVELOPMENT METRICS

For every arm report:

### Primary

* mean Spearman IC
* block-bootstrap 95% CI
* IC hit rate
* top-bottom quintile spread
* paired IC difference versus 12-1 momentum
* paired IC difference versus 5-day reversal

### Stability

* sign stability
* first-half mean IC
* second-half mean IC
* bull mean IC
* bear mean IC
* sideways mean IC
* high-vol mean IC
* low-vol mean IC

### Trading realism

* turnover
* gross spread
* net spread at 5 bps
* net spread at 10 bps
* net spread at 20 bps

Do NOT optimize for any metric after seeing the result.

---

# 6. MULTIPLICITY

The primary hypothesis family is exactly the four preregistered arms:

* V2.1-A
* V2.1-B
* V2.1-C
* V2.1-D

Do not add extra arms after seeing development results.

Use the preregistered multiplicity correction.

If Holm-Bonferroni is used, define exactly which p-values enter the family before fitting.

Do not selectively correct only favorable comparisons.

---

# 7. DEVELOPMENT SELECTION RULE

This is extremely important.

After all four arms have completed development evaluation, select exactly ONE arm for the frozen exam.

The selection rule must be:

1. First, require the arm to satisfy the development quality gates.
2. Among arms that satisfy the development gates, select the simplest arm that passes.
3. If multiple arms pass equally, prefer the lower-complexity model.
4. If no arm passes the development gates, DO NOT OPEN THE EXAM.

Do NOT select based merely on highest mean IC.

Do NOT select based on the prettiest regime table.

Do NOT select based on the lowest p-value alone.

Do NOT select based on exam expectations.

If the development result is ambiguous, stop.

---

# 8. CRITICAL QUESTION: SHOULD A FAILING MODEL GO TO EXAM?

The exam exists to measure a preregistered candidate, not to rescue a failed model.

Therefore:

If no arm meets the preregistered development criteria, the V2.1 exam remains unopened.

If exactly one or more arms meet the development criteria, choose according to the fixed simplicity rule above.

Record the selection BEFORE running exam scoring.

---

# 9. DEVELOPMENT GATES

Use the same core thresholds as the V2.1 validation protocol unless there is a documented reason that a development-only gate must differ.

Do not lower them.

At minimum require:

* mean IC > 0.03
* CI excludes 0
* IC hit rate > 55%
* CI excludes 50%
* positive top-bottom spread with CI excluding 0
* sign stability ≥ 60%
* positive mean IC in both chronological halves
* positive mean IC in sufficiently populated regimes
* positive cost-adjusted spread

Most importantly:

### A learned model must demonstrate incremental information over 12-1 momentum.

A model that has positive IC but does not beat 12-1 momentum should NOT be considered a successful alpha model.

---

# 10. INTERPRET V2.1-A CORRECTLY

V2.1-A is not intended to "prove" momentum.

It is a benchmark.

If 12-1 momentum performs strongly on development, that does not invalidate the experiment.

It simply raises the bar for B/C/D.

The key question becomes:

> Does context or nonlinear learning provide incremental information beyond this simple factor?

---

# 11. CONTEXT ARM INTERPRETATION

V2 found:

V2-A ≈ V2-B

but:

V2-E > V2-A

Therefore V2.1-B is particularly important.

If B fails to improve materially over A, record:

> market context did not provide stable incremental information once 12-1 momentum was included.

If B improves, do NOT immediately assume it is genuine.

It must survive:

* development gates
* benchmark comparison
* regime stability
* cost analysis
* frozen exam

---

# 12. NONLINEAR MODEL INTERPRETATION

V2.1-D is not successful merely because:

`D > C`

It must demonstrate:

`D > 12-1 momentum`

and preferably:

`D > B/C`

with statistically credible paired improvement.

A nonlinear model that merely reproduces momentum is not additional alpha.

---

# 13. EXAM RULE

The new exam is sacred.

Do NOT open it until:

* the preregistration exists
* the four arms are frozen
* the development results are complete
* the selection rule is applied
* exactly one arm has been selected
* the selection decision is written to the experiment log

Then:

1. fit the selected arm using only development data;
2. generate exam predictions;
3. freeze those predictions;
4. score them;
5. run the nine preregistered gates;
6. produce the V2.1 report.

No second attempt.

No alternate model.

No alternate benchmark.

No threshold change.

No post-hoc regime.

No date removal.

---

# 14. DO NOT CHANGE PRODUCTION

Do not modify:

`alpha/adapter.py`

Do not change:

* production weight
* HOLD logic
* evidence strength
* production thresholds
* schema

Even if development looks excellent, production remains unchanged until the frozen exam has been successfully passed.

---

# 15. TESTING REQUIREMENTS

Before the first fit:

Run:

`pytest -q --runslow`

Confirm all tests pass.

Add tests for:

* preregistration exists before fit
* exact four-arm family
* exact feature membership per arm
* no exam access during development
* no future target leakage
* benchmark definitions are fixed
* no post-hoc feature family insertion
* no post-hoc hyperparameter insertion
* selection rule is deterministic
* only one arm can be selected for exam
* production remains HOLD

Maintain all previous V2/V2.1 tests.

---

# 16. REQUIRED DELIVERABLES

Before fitting:

1. `alpha/V2_1_EXPERIMENT_PREREGISTRATION.md`
2. updated experiment protocol implementation
3. tests proving the preregistered ladder is fixed
4. a clear feature inventory for A/B/C/D

Then run development.

After development:

5. `alpha/V2_1_EXPERIMENT_LOG.md`
6. development comparison table
7. selected-arm decision

Only if the development gate passes:

8. open the 72-date exam exactly once
9. generate frozen predictions
10. score the exam
11. produce:
    `alpha/V2_1_REPORT.md`

---

# 17. REPORTING STANDARD

The final report must clearly separate:

### What was preregistered

from

### What happened

Do not hide failed experiments.

Do not hide weak arms.

Do not report only the best model.

Report:

* all four development arms
* all relevant confidence intervals
* all benchmark comparisons
* all regime results
* all cost results
* selection decision
* exam result if and only if the development gate permits opening it
* every failure
* every bug discovered
* every deviation, if any

---

# 18. STOP CONDITIONS

STOP immediately and report if:

* the exam artifact changes
* any exam result is accidentally read during development
* a feature was added after seeing an arm's result
* a hyperparameter was changed after seeing a result
* the benchmark was changed after seeing a result
* a development criterion was relaxed
* the preregistration was modified after the first fit
* training data accidentally contains exam observations

Do not "fix and continue" silently.

Record the incident and stop.

---

# FINAL INSTRUCTION

The goal is not to produce a positive result.

The goal is to determine whether:

**12-1 momentum → context → nonlinear learning**

adds progressively more genuinely out-of-sample information.

If the answer is no, that is a successful scientific result.

Start by creating and validating the V2.1 experiment preregistration.

Then run the development ladder.

Do NOT touch the frozen 72-date exam unless the preregistered development selection rule explicitly permits exactly one arm to proceed.

Do not modify production.

At the end of this task, report exactly:

1. what was preregistered;
2. what tests passed;
3. development results for A/B/C/D;
4. whether an arm qualified for the exam;
5. if not, STOP with the exam unopened;
6. if yes, name the selected arm but do not score the exam until the selection is recorded in the experiment log.
