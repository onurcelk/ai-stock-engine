# V2.1 pre-registration — the exam, not the model

**Written 2026-08-08, after the V2 study closed and before any V2.1 model
exists.** No V2.1 feature set has been built, no V2.1 model has been fitted, and
no return, outcome or IC has been computed on any date under any rule described
below.

This document does not supersede `PREREGISTRATION.md`. That file records a
completed experiment and is not edited. This one records the *next* experiment's
validation protocol, which is the only thing being changed at this stage.

---

## 0. Why there is a V2.1 at all

V2 returned a null and the production verdict stands: **weight 0, action HOLD.**
Nothing here reopens it. But V2 exposed one defect that is not a modelling
defect and cannot be fixed by a better model:

> The frozen exam paper was 12 dates. Criterion 7 of §8 requires ≥ 50
> independent cutoffs. The exam therefore could not pass, *by construction*,
> whatever a model did — and its IC interval spanned [−0.063, +0.239], which has
> no power against any plausible effect size.

Two further defects were exposed at the same time:

* the baseline was selected by |mean development IC|, which chose 5-day
  reversal — the factor with the largest development effect and essentially
  none out of sample — rather than the factor with the strongest economic prior;
* the regime with the best IC inverted between development (BEAR) and exam
  (SIDEWAYS), and the aggregate number gave no warning that it would.

V2.1 fixes the exam. It does not fix the model, add features, or touch
production. The purpose of this stage is to make the *next* positive number, if
one occurs, hard to dismiss.

---

## 1. What carries over from V2 unchanged

Restated so that a difference between the two studies is visible as a
difference rather than as an omission.

| Item | Value | Same as V2? |
|---|---|---|
| Universe | point-in-time S&P 500 members, `alpha/membership.py` | yes |
| Eligibility | ≥252 sessions history, ≥\$3M median 60-day dollar volume, ≥\$3 close, ≤5 sessions stale | yes |
| Prediction horizon | 5 trading sessions | yes |
| Target | `alpha_5d = R_asset − R_SPY` | yes |
| Winsorisation | 1st/99th percentile within cutoff, training target only | yes |
| Study start | 2016-01-04 | yes |
| Cutoff grid | every 5th session — spacing == horizon, so outcome windows never overlap | yes |
| Embargo | 5 sessions on top of the horizon | yes |
| Walk-forward | expanding, train only on cutoffs with `T′ + 5 + 5 ≤ T` | yes |
| Refit cadence | 65 sessions of staleness | yes |
| Minimum training cutoffs | 60 | yes |
| Regime definition | `features.regime_state`, deterministic, pre-cutoff | yes |
| Primary metric | per-cutoff Spearman IC vs `alpha_5d` | yes |
| Interval | moving-block bootstrap, block 4, 10,000 draws | yes |
| Production weight | **0** | yes |

Everything in §2 onward is what changes.

---

## 2. The frozen exam set

### 2.1 Selection rule

Deterministic, content-blind, and stated in full so that it can be re-derived
from the session calendar alone:

1. Build the cutoff grid: every 5th session of the SPY calendar from
   **2016-01-04** to the last session with a complete 5-session outcome ahead
   of it. Call these `g[0], g[1], …` in date order.
2. **Warm-up.** The first **504 sessions** of the grid — `g[0] … g[99]`, roughly
   two years — are development-only and can never be exam cutoffs. This exists
   so that the first exam cutoff already has ≥60 admissible development cutoffs
   behind it, which is the minimum training size inherited from V2. Fixing it in
   *sessions* rather than in *cutoffs* keeps the definition non-circular: the
   development set depends on the exam set, so the exam set may not be defined
   in terms of the development set.
3. **Systematic selection.** The exam is every **6th** grid cutoff at or after
   the warm-up boundary: `g[100], g[106], g[112], …`. Consecutive exam cutoffs
   are therefore **30 sessions** apart.
4. **Development** is every remaining grid cutoff whose outcome window is at
   least `HORIZON + EMBARGO = 10` sessions clear of every exam cutoff's outcome
   window. Concretely, a grid cutoff is dropped from development when it is an
   exam cutoff or lies within 5 sessions of one.

Nothing in this rule reads a return, an outcome, a target, or an IC. It reads
the trading calendar and nothing else.

### 2.2 Why systematic and not random or stratified

A systematic every-6th sample over calendar time is uniform in calendar time,
so its coverage of market conditions is proportional to how often those
conditions actually occurred, without anybody choosing what "coverage" should
mean. A stratified sample would require deciding the strata and their quotas,
and each of those decisions is a place a preference can enter. A random sample
would need a seed, and a seed is a knob. Systematic sampling has no knob except
the step and the offset, and both are fixed here, in advance, in public.

The step and the warm-up were chosen by calendar arithmetic against one
requirement — **at least 60 exam cutoffs, with a development set that stays
several times larger** — evaluated over steps 5–8 and warm-ups of 1.5, 2 and
2.5 years. Regime *counts* under each candidate were inspected, because §2 of
the directive asks the exam to span bull, bear and sideways periods. Regime tags
are computed from pre-cutoff SPY and VIX closes and are not outcomes. **No
return, no target and no IC was computed for any candidate.**

### 2.3 Expected size

Under the rule above the grid is 532 cutoffs and the split is **72 exam / 316
development**. Both numbers are properties of the calendar, and the freeze
script recomputes and records them rather than trusting this paragraph.

72 clears the ≥60 requirement with 12 cutoffs of margin, which matters because a
cutoff that fails to produce a cross-section wide enough to score is dropped at
scoring time.

### 2.4 Independence

**One independent observation is one cutoff date.** Not one stock-date: 460
names ranked on one morning share that morning, and treating them as 460 draws
is the error the V1 report was built around refusing.

Independence of the exam cutoffs is guaranteed structurally, not assumed:

* outcome windows are 5 sessions long and consecutive exam cutoffs are 30
  sessions apart, so **every pair of exam outcome windows is separated by at
  least 25 clear sessions**;
* no exam outcome window overlaps any other exam outcome window, at any lag;
* no exam outcome window overlaps or touches any development outcome window —
  the ±5-session drop in rule 4 guarantees at least 5 clear sessions between
  them.

This is the strong form: the mechanical serial correlation that overlapping
windows create is **absent**, not corrected for. The intervals in §5 exist for
the market's own persistence, which remains.

### 2.5 Immutability

The exam set is written once to `alpha/out/v2_1_exam_set.json` together with a
SHA-256 digest of the cutoff list. `examset.freeze()` refuses to overwrite an
existing file, and `examset.load()` recomputes the digest and refuses to return
a set whose contents no longer match it. Re-freezing requires deleting the file,
which is a deliberate act a person has to explain in `EXPERIMENT_LOG.md`.

### 2.6 Disclosed limitation — the exam is not novel data

The V2.1 exam dates lie inside 2016–2026, and V2's development ladder ran over
that same window. Aggregate knowledge formed during V2 — chiefly *"the
stock-level relative tier is a null and all the movement is in market
context"* — was therefore formed partly on dates that are now exam dates.

This cannot be removed. There is no later history to hold out; the data ends
today. What is done about it instead:

* the exam is fully out-of-sample with respect to **every model that will be
  evaluated on it**, because no V2.1 model exists yet and this file freezes the
  protocol before one does;
* the tier definitions, the benchmark hierarchy, the criteria and the thresholds
  are all fixed **in this document**, so nothing from the exam can enter them;
* the one V2 conclusion that will shape V2.1 — start from 12-1 momentum plus
  market context — is stated here explicitly as an inherited prior rather than
  smuggled in as a discovery.

A V2.1 pass is therefore evidence about a model, not evidence about a feature
family. It is weaker than a pass on genuinely unseen history would be, and any
report must say so in those words.

Second limitation, inherited and restated: the sign of Benchmark 2 (§3) was
fixed on V2's development set, which includes dates now in the V2.1 exam. That
biases the *benchmark* in its own favour on the exam, which makes the model's
bar harder, not easier. It is disclosed rather than corrected.

Third, inherited from V2 §2: residual survivorship. 127 of 781 ever-members have
no bars at all; index coverage is ~85% in 2016 and 100% today, so early exam
cutoffs are missing roughly 15% of the true cross-section, biased toward names
later acquired or delisted.

---

## 3. Benchmark hierarchy — pre-committed

V2's rule ("the factor with the largest |mean development IC|") is **retired**.
It is retired for a stated methodological reason, before any V2.1 number exists:
it is a selection rule that maximises in-sample effect size, and on V2 it duly
selected the factor with the largest development effect (5-day reversal,
−0.00955) which then delivered −0.0008 on the exam, while the factor with the
strongest economic prior (12-1 momentum, +0.00599 on development) beat the model
out of sample. A rule that reliably picks the weakest available opponent is not
a benchmark rule.

The replacement is a fixed hierarchy. No selection happens at any point.

### Benchmark 1 — 12-1 momentum (`mom_12_1`, sign `+1`) — **primary**

The 252-session return excluding the most recent 21 sessions, ranked within
cutoff. Sign is `+1` by economic prior — cross-sectional momentum — and is
**not** estimated from any data, development or otherwise.

This is the bar. The V2.1 research question is stated against it:

> Does market context add predictive information beyond a simple 12-1 momentum
> factor, and can a learned model beat that factor consistently out of sample?

### Benchmark 2 — 5-day reversal (`mom_5d`, sign `−1`) — **secondary**

Retained because it was V2's benchmark and dropping it after it turned out to be
weak would be the mirror image of the error being fixed. The sign `−1` is the
one V2 froze on its development set (`out/development.json`); it is copied here
verbatim and is not re-estimated.

### Benchmark 3 — regime-switched momentum — **reported, not a gate**

Rank by `mom_12_1` when the pre-cutoff regime tag is `BULL_TREND` or
`SIDEWAYS`; rank by `−mom_5d` when it is `BEAR_TREND`. The switch reads
`features.regime_state`, which is a deterministic function of pre-cutoff SPY and
VIX closes. Nothing in it is fitted.

The prior is the documented momentum-crash effect: cross-sectional momentum
inverts in bear-market rebounds. It is included because "does the learned model
beat a simple *context* rule" is precisely the V2.1-B question and a
context-free benchmark cannot ask it.

It is **not** a gate: a two-state hand-specified switch is more elaborate than
an economic prior strictly licenses, and gating on it would let a benchmark
design choice decide the study.

---

## 4. Criteria — fixed now

Primary metric unchanged: **per-cutoff Spearman IC between the prediction and
realised `alpha_5d`**, aggregated across cutoffs. Judged against the
**block-bootstrap** interval, as in V2.

Nine gates. All nine must pass **on the exam set** for production weight to
exceed 0. Three further quantities are measured and reported but gate nothing,
because no threshold for them can be justified in advance.

| # | Criterion | Threshold | Gate |
|---|---|---|---|
| 1 | Mean Spearman IC | > 0.03 and 95% bootstrap CI excludes 0 | yes |
| 2 | IC hit rate | > 55% of cutoffs and 95% CI excludes 50% | yes |
| 3 | Top-minus-bottom quintile spread | > 0 and 95% CI excludes 0 | yes |
| 4 | Sign stability | IC > 0 in ≥ 60% of cutoffs **and** mean IC > 0 in both chronological halves of the exam | yes |
| 5 | Beats Benchmark 1 (12-1 momentum) | paired per-cutoff IC difference > 0, 95% CI excludes 0 | yes |
| 6 | Beats Benchmark 2 (5-day reversal) | paired per-cutoff IC difference > 0, 95% CI excludes 0 | yes |
| 7 | No regime collapse | mean IC > 0 in every regime bucket holding ≥ 8 exam cutoffs | yes |
| 8 | Effective sample | ≥ 50 independent cutoffs scored | yes |
| 9 | Cost-adjusted spread | net spread > 0 at 5 bps one-way, 95% CI excludes 0 | yes |
| 10 | Turnover | measured and reported | no |
| 11 | Cost sensitivity | net spread at 5 / 10 / 20 bps one-way | no |
| 12 | Independent-cutoff count and the full per-regime and per-half tables | reported | no |

### 4.1 What changed from V2's seven, and why — each with its reason

Recorded here because §7 of the directive requires the reason to predate the
result.

**Criterion 4 was redundant and is now a real test.** In V2, criteria 2 and 4
were both computed from `ic.hit_rate`; criterion 4 could not fail unless
criterion 2 already had. Meanwhile V2's actual instability — the favourite
regime inverting between samples — was invisible to both. Criterion 4 now also
requires the mean IC to be positive in each chronological half of the exam. With
72 cutoffs each half holds ~36, which is enough to notice a sign flip.

**Criterion 5 is now a fixed benchmark, not a selected one.** Reason in §3.

**Criterion 6 is new: the model must also beat 5-day reversal.** V2 required
superiority over one baseline, selected to be the strongest in sample. Requiring
superiority over both members of a fixed hierarchy is strictly harder and cannot
be gamed by the selection rule, because there is no selection rule.

**Criterion 7 (was 6) gains a minimum bucket size.** V2 required mean IC > 0 in
*every* regime bucket. On a 12-date exam that included buckets holding one or
two cutoffs, where the criterion is a coin flip in both directions — it can fail
on noise and, worse, it can *pass* on noise. Buckets with ≥ 8 exam cutoffs gate;
smaller buckets are reported in full and gate nothing. This is a relaxation of
the letter and a tightening of the substance, and it is written down before any
V2.1 IC exists so that it cannot be a response to one.

The minimum was set at 8 with the frozen set's regime counts already known
(`BULL_TREND` 53, `BEAR_TREND` 10, `SIDEWAYS` 9; `HIGH_VOL` 36, `LOW_VOL` 36).
That is disclosed rather than hidden because it cuts the awkward way: 8 is the
largest round number that leaves **every** bucket gating. A threshold of 12
would have excused the model from ever working in a bear market. The counts are
a property of the calendar, not of any result.

**Criterion 8 (was 7) keeps the threshold of 50.** Not raised to 60 even though
the exam is built to 72. Raising a threshold after building an exam that clears
it would be as much a post-hoc move as lowering one.

**Criterion 9 is new: costs.** V2 reserved the cost fields in the adapter and
never populated them. A +0.0026 gross spread — V2-F's exam figure — is 26 basis
points per 5 sessions, which two-sided trading costs can consume entirely. A
gross-only bar is not a bar.

Cost model, fixed now: a balanced long-short quintile book, rebalanced at every
scored cutoff, charged `(turnover_long + turnover_short) × c` per rebalance with
`c = 5 bps` one-way. Turnover is measured as the fraction of each leg's names
that change between consecutive scored cutoffs; where it cannot be measured (the
first cutoff) it is assumed to be 1.0. 5 bps one-way is fair-to-optimistic for
S&P 500 names at moderate size, which is why 10 and 20 bps are reported beside
it as criterion 11 rather than argued about.

**No threshold in §8 of the V2 pre-registration is lowered.** Criteria 1, 2, 3
and 8 carry their V2 numbers unchanged.

---

## 5. Statistical methodology

**The independent unit is the cutoff date.** Stated again because it is the
single assumption most of the arithmetic rests on. Cross-sectional width enters
only through the precision of each cutoff's own IC, never as a sample size.

**Intervals.** Three are reported for every headline number, as in V2, so the
correction is visible rather than asserted:

* `naive` — i.i.d., what pretending cutoffs are independent would give;
* `newey_west` — HAC, Bartlett kernel, 4 lags;
* `block_bootstrap` — moving block, **block length 4 cutoffs**, 10,000
  resamples, percentile interval.

**Pre-registered decisions are judged against the block bootstrap.** It is the
widest of the three and it makes no distributional assumption.

**Why block length 4.** At the exam's 30-session spacing, four cutoffs span
about six months. The dependence a block must absorb here is not mechanical —
§2.4 removes overlap entirely — but the market's own regime persistence, which
runs in months. Six months is generous for that. Block lengths 1, 2 and 8 are
reported as a sensitivity so that the choice is visible and its effect
measurable; the pre-registered figure is block 4.

**Sidedness.** All p-values and intervals are **two-sided**. A learned model's
sign is not known a priori, and a one-sided test is the cheapest way to turn a
null into a finding. Criteria phrased as "> 0 and the CI excludes 0" are
therefore a 2.5% one-sided test in effect, which is stricter than a 5% one-sided
test, and that is intentional.

**Multiplicity.** Holm–Bonferroni across the arms actually run, applied to each
arm's criterion-1 bootstrap p-value. An arm that clears a threshold on its raw
p-value but not its adjusted one is reported as **not passing**. If *k* arms are
run, *k* is the family size — not the number that looked promising.

**Model selection for the exam.** Exactly one arm goes to the exam, chosen on
the development set by the same rule V2 used: highest mean development IC,
frozen in the development record before the exam is opened. Spending the frozen
dates on several arms would spend them several times.

---

## 6. Regime policy

The regime definition is `features.regime_state`, unchanged from V2:
`BULL_TREND` / `BEAR_TREND` / `SIDEWAYS` from SPY's close against its 50- and
200-session means, and `HIGH_VOL` / `LOW_VOL` from VIX against its trailing
252-session median. It is deterministic, computed from pre-cutoff data, and will
not be re-specified, re-thresholded or re-bucketed for V2.1.

Regime results are **diagnostic, never explanatory**. Specifically ruled out in
advance:

* reporting an aggregate failure as a success confined to one regime;
* restricting production to a regime chosen because the exam liked it;
* adding a regime interaction after seeing a per-regime table.

The question a regime table is allowed to answer is the one V2 got wrong:
**does the sign and magnitude hold across regimes, or is the aggregate a bet on
one of them?** A model whose edge lives in a single regime bucket has not
demonstrated alpha; it has demonstrated a regime bet, and criterion 7 exists to
say so.

---

## 7. Leakage rules

The development process must be able to run start to finish **without reading
any exam result**. Concretely, the exam may not influence: feature selection,
feature engineering, target construction, baseline selection, model selection,
hyperparameters, regime definitions, thresholds, or stopping criteria.

Enforced, not merely intended:

* `alpha/examset.py` is the only source of exam dates, it returns dates and
  pre-cutoff metadata, and it never returns an outcome;
* the development stage slices the panel to development cutoffs before it looks
  at anything, exactly as `alpha/develop.py` does today;
* the scoring stage stays a separate process from the prediction stage and
  refuses to overwrite a frozen prediction file;
* `app/tests/test_alpha_v2_1.py` asserts every invariant in §2.4 and §7, and the
  leakage tests inherited from `test_alpha.py` continue to run.

---

## 8. What is *not* decided by this document

The research ladder — V2.1-A (12-1 momentum only), V2.1-B (+ market context),
V2.1-C (+ justified additions), V2.1-D (learned nonlinear model) — is sketched
in the directive and is **not** pre-registered here. It will be pre-registered
in its own document before it is run, because the arms, their feature lists and
the family size for §5's multiplicity correction all need to be fixed before the
first fit, and none of them is needed to freeze an exam.

No model is evaluated on the V2.1 exam at this stage. The exam becomes
immutable first.

---

## 9. Production

Unchanged and untouched.

* `alpha/adapter.py` is not modified.
* Production weight remains **0**.
* Production action remains **HOLD**.
* The evidence thresholds, the HOLD cascade and the output schema are not
  modified.

Weight may exceed 0 only after all nine gates of §4 pass on the V2.1 exam set,
under this protocol, with the multiplicity correction of §5 applied. Absent or
insufficient validation is HOLD, and that behaviour is tested.

---

## 10. Failure rule

Unchanged in spirit from V2 §10, and it binds this document too. If the
selection rule in §2 cannot produce 60 independent cutoffs on the available
history, the correct outcome is to **report the maximum defensible number** and
say so — not to shorten the embargo, shrink the warm-up below what the training
minimum requires, or count overlapping windows as independent.

A protocol that is too weak to detect the effect being looked for is a finding
about the protocol, and V2 is the precedent: it reported exactly that about its
own exam rather than quietly dropping criterion 7.
