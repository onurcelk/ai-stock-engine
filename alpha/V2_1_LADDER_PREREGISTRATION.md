# V2.1 ladder pre-registration — the arms, before the first fit

**Written 2026-08-08, after `V2_1_PREREGISTRATION.md` froze the exam set and
before any V2.1 model was fitted.** At the time of writing, no V2.1 arm exists,
no V2.1 fit has been run, and no IC has been computed for any V2.1 arm on any
cutoff, development or exam.

`V2_1_PREREGISTRATION.md` §8 says the ladder is *not* pre-registered by that
document and must get its own before it runs, "because the arms, their feature
lists and the family size for §5's multiplicity correction all need to be fixed
before the first fit". This is that document. It does not edit, supersede or
reinterpret anything in `V2_1_PREREGISTRATION.md`; the exam set, the benchmark
hierarchy, the nine gates, the intervals and the production rule are all
inherited unchanged and are not restated here except where a number is needed.

---

## 1. The question

Fixed in `V2_1_PREREGISTRATION.md` §3 and repeated verbatim so the arms can be
read against it:

> Does market context add predictive information beyond a simple 12-1 momentum
> factor, and can a learned model beat that factor consistently out of sample?

---

## 2. The mechanism this ladder is actually testing

This section exists because the answer to "what could arm B possibly do?" is
much narrower than it looks, and stating the narrow version in advance stops a
null being reported later as a surprise.

The primary metric is **Spearman IC within a cutoff**. Spearman IC is invariant
to any strictly monotone transform of the prediction inside that cutoff.

Of the 35 columns V2 calls its context tier, **26 are constant across the
cross-section at a given cutoff** — every `mkt_spy_*`, `mkt_qqq_*`, `vix_*`,
`regime_*`, `index_breadth_*`, `index_advance_share` and
`watchlist_breadth_proxy_*` column takes one value for all ~470 names on that
morning. (This is a property of `features.context_block`, which computes one
number per cutoff and broadcasts it. It is verified rather than assumed:
`test_market_context_is_constant_within_a_cutoff`.)

The consequence, stated before any fit:

* Within one cutoff, a model given `ret_12_1` plus cutoff-constant context can
  only produce a **univariate function of `ret_12_1`**, because every other
  input it has is the same number for every row.
* If that function is monotone increasing, the arm's within-cutoff ordering —
  and therefore its IC — is **identical to ranking by `ret_12_1`**, which is
  Benchmark 1.
* So arm B can differ from Benchmark 1 in exactly one way: by making the
  momentum→score map **non-monotone at some cutoffs**, and in the limit by
  **inverting it**.

Arm B therefore tests one hypothesis and not a vague one:

> **Does market context tell you when to flatten or flip cross-sectional
> momentum?**

That is the documented momentum-crash effect, it is the same hypothesis
Benchmark 3 (regime-switched momentum) hand-specifies, and B versus Benchmark 3
is consequently the direct *learned-versus-hand-specified* comparison. It is
reported for every arm even though Benchmark 3 gates nothing.

Arm C breaks the univariate restriction by adding stock-level columns, so from C
onward the within-cutoff function is genuinely multivariate and the reordering
is not limited to monotonicity changes.

**A linear learner would make arm B identically equal to arm A** — cutoff-constant
terms enter as a per-cutoff intercept and cancel in the ranking. The learner is
therefore required to be interaction-capable, which the pre-registered
`HistGradientBoostingRegressor` is. This is a constraint on the ladder, recorded
here, not a result.

---

## 3. The arms — four, fixed now

All four run. There is **no internal gate** between them, and the reason is
recorded: the object of interest is the A→B→C→D *deltas*, and a delta needs both
of its ends to exist. V2's §14 gate was a gate on building a *different kind* of
model (a ranker) after a regression had proven itself; that is not what A→C is.
Fixing all four in advance also fixes the family size, which a conditional
ladder cannot do — V2 ran four arms out of a possible seven and its Holm
correction had to be taken over the four that happened.

The learner, the target and the walk-forward are **identical across A, B and C**,
so the only thing that differs between those three is the column list. D changes
exactly one further thing, named in §3.4.

### Common to every arm

| Item | Value | Source |
|---|---|---|
| Cutoffs | the 316 frozen V2.1 **development** cutoffs, and nothing else | `examset.development_only()` |
| Learner | `HistGradientBoostingRegressor`, `models.MODEL_A_PARAMS` | V2 `PREREGISTRATION.md` §7, **not tuned, not re-tuned** |
| Training target | `target_train` (winsorised `alpha_5d`) for A, B, C | V2 |
| Scoring target | `alpha_5d`, always, for every arm | `V2_1_PREREGISTRATION.md` §4 |
| Walk-forward | expanding, refit at 65 sessions of staleness, min 60 training cutoffs | `walkforward.py`, V2 |
| Purge/embargo | `T′ + 5 + 5 ≤ T` | `dataset.training_cutoffs` |
| Intervals | moving-block bootstrap, block 4, 10,000 draws | `V2_1_PREREGISTRATION.md` §5 |

No hyperparameter is searched at any point in this ladder. If a fit fails for a
mechanical reason the arm is reported as not run, not re-parameterised.

### 3.1 V2.1-A — 12-1 momentum only

**Features (1):** `ret_12_1`

The directive's rung A, taken literally. Its purpose is not to win: it is the
floor, and it is the anchor that says the machinery reproduces the benchmark
when given only the benchmark's information. A's IC is expected to sit on top of
Benchmark 1's, differing only where the learned univariate map is non-monotone.
If A and Benchmark 1 diverge materially, that is a finding about the pipeline
and is reported as one.

**A is not eligible to be the exam arm.** See §5.

### 3.2 V2.1-B — 12-1 momentum + market context

**Features (27):** `ret_12_1` plus the 26 cutoff-constant market-context columns:

```
index_advance_share            mkt_spy_ret_5d      mkt_qqq_ret_5d
index_breadth_above_sma20      mkt_spy_ret_20d     mkt_qqq_ret_20d
index_breadth_above_sma50      mkt_spy_ret_60d     mkt_qqq_ret_60d
regime_bull                    mkt_spy_rsi14       mkt_qqq_rsi14
regime_bear                    mkt_spy_rvol_20d    mkt_qqq_rvol_20d
regime_sideways                mkt_spy_sma50_dist  mkt_qqq_sma50_dist
regime_high_vol                mkt_spy_sma200_dist mkt_qqq_sma200_dist
vix_level
vix_percentile
vix_change_5d
watchlist_breadth_proxy_above_sma20
watchlist_breadth_proxy_advance_share
```

This is V2's context tier **minus** the nine `overnight_*` / `intraday_*`
columns. Those are per-symbol quantities that V2's `develop.CONTEXT_PREFIXES`
happened to bundle with market context; they are not market context, they vary
across the cross-section, and putting them here would let the "market context
only" arm quietly carry stock-level information — which is the one thing the
A-vs-B contrast exists to isolate. They move to arm C, where they are
stock-level features and are labelled as such.

`watchlist_breadth_proxy_*` is retained under its V2 name and remains a proxy
over an arbitrary 22-name list, not breadth. It is kept for continuity with V2's
context tier rather than because it has a prior.

The A→B delta is the headline number of this ladder.

### 3.3 V2.1-C — + a justified stock-level block

**Features (35):** everything in B, plus exactly eight stock-level columns.

Each one has to carry its own reason, written before the fit:

| Column | Why it is allowed in |
|---|---|
| `ret_5d` | Benchmark 2's raw input. Short-term reversal is the other end of the return term structure from 12-1 momentum, and criterion 6 requires the model to beat it — a model that has never seen it is being asked to clear a bar blindfolded. |
| `ret_20d` | The middle of that term structure. One-month reversal is a separately documented effect from both 5-day reversal and 12-1 momentum, and the 5/20/252 triple is the standard way to let a model find where the sign changes. |
| `rvol_20d`, `rvol_60d` | Momentum crashes are volatility-conditional (Daniel–Moskowitz). B's VIX term is cutoff-constant, so it can only express "the market is volatile"; these give the same interaction a **stock-level** handle, which is what distinguishes a crash-aware model from a market-timing one. |
| `sma200_dist` | The stock-level analogue of the trend tag in B — is *this name* above its own 200-session mean. Makes "regime" a property of the security as well as of the index. |
| `overnight_mean_20d`, `intraday_mean_20d`, `overnight_share_60d` | §9's overnight/intraday decomposition. V1's entire 4-hour result was 77% overnight and inverted when read after the close; V2's only positive finding was that its signal lived in the tier containing these. This is the one stock-level block V2 gave an actual reason to keep. |

**Deliberately excluded, with reasons, so the exclusions are as pre-registered as
the inclusions:**

* **The 47-column relative / `__vs_spy` / `__vs_sector` / `__pct` tier, and
  `beta_market` / `beta_sector`.** V2 measured this over 423 development
  cutoffs: mean IC moved from **+0.00837 to +0.00846**. That is a well-powered
  null, not an inconclusive result, and re-adding 47 columns to see what happens
  is precisely the feature-generation move the directive rules out.
* `ret_1d`, `ret_3d`, `ret_10d` — interpolations between `ret_5d` and `ret_20d`
  with no separate prior.
* `sma20_dist`, `sma50_dist`, `rsi14` — oscillators and shorter trend distances
  that are near-collinear with the return windows already present, with no prior
  distinguishing them from noise.
* `rvol_5d`, `pre_vol_20d` — near-duplicates of `rvol_20d`; `pre_vol_20d` is the
  same 20-session realised volatility computed over 21 bars for the V2-F
  denominator.
* `volratio_20`, `vol_surprise`, `log_dollar_volume` — liquidity and volume
  surprise. A defensible case exists for the size/liquidity dimension, but it is
  a *different* hypothesis from the one in §1, and admitting it here would make
  a positive C an ambiguous result. Excluded on those grounds, not on evidence.

C is 35 features, not 100. A ladder whose top rung is "everything" cannot
attribute anything.

### 3.4 V2.1-D — the same information, ranked

**Features (35):** identical to C. **Training target:** `target_rank` — the
within-cutoff percentile of `alpha_5d` — instead of `target_train`.
**Scored on `alpha_5d`**, like every other arm.

The one change, and its reason: the metric is a rank correlation *within* a
cutoff, while A/B/C minimise squared error on a level whose variance is
dominated by how the whole market moved that week. Training on the within-cutoff
percentile targets the quantity actually being measured. This is the pointwise
ranker V2 specified as Model B/C and never built, because V2's §14 gate closed —
so it has never been run on anything.

It is a **pointwise** surrogate for a listwise ranker. `lightgbm`'s `lambdarank`
is not installed here and nothing is being installed to chase a number. Any
report of D says "pointwise ranker", not "ranker".

Changing the target is a change to the model. Changing the *scoring* target
would be a change to the yardstick, and is not done — the same rule V2 applied
to V2-F.

### 3.5 What is not in this ladder

No V2.1-E. No neural network, no transformer, no LSTM, no hyperparameter search,
no regime re-definition, no threshold change, no alternative horizon, no
alternative target construction, no change to the universe or the eligibility
filter, and no change to `alpha/adapter.py`. If all four arms are null, the
answer is "null", not "a fifth arm".

---

## 4. Family size and multiplicity

**k = 4.** Fixed here, before the first fit, and it does not become 3 if an arm
disappoints or 5 if a fifth idea occurs later.

* **On development:** Holm–Bonferroni across all four arms' criterion-1
  bootstrap p-values, as `stats.holm_bonferroni` implements it.
* **On the exam:** the single arm that reaches the exam carries the correction
  for the selection that put it there. Its criterion-1 bootstrap p-value is
  multiplied by **4**, not by 1, because it is the maximum of four development
  ICs. With one p-value, Holm and Bonferroni coincide, so this is
  `p_adj = min(1, 4p)`.

That second rule is the strict reading of `V2_1_PREREGISTRATION.md` §5 ("If *k*
arms are run, *k* is the family size — not the number that looked promising"),
and it is written down now because the lenient reading — one arm on the exam,
therefore k = 1 — is available and would be indefensible after the fact.

---

## 5. Which arm goes to the exam, and when the exam opens

Two decisions, both fixed here.

### 5.1 Selection

**The exam arm is the arm with the highest mean development IC among {B, C, D}.**

Ties, which will not occur at five decimal places but are specified anyway, go to
the simpler arm: B before C before D.

**A is excluded from the candidate pool.** Not because of anything it does — it
has not been run — but because §2 establishes that A is, up to non-monotonicity,
Benchmark 1 itself. Criterion 5 requires the exam arm to beat Benchmark 1 with a
paired difference whose CI excludes 0; an arm that *is* the benchmark scores a
paired difference of approximately zero by construction. Sending it to the exam
spends 72 irreplaceable dates to confirm an identity. A is reported in full on
development and is not a candidate.

This is a narrowing of `V2_1_PREREGISTRATION.md` §5's "highest mean development
IC". It is recorded as a deviation, with its reason, before any number exists.

### 5.2 The gate on opening the exam

The exam is opened **only if** the selected arm clears, on the development set:

> paired per-cutoff IC difference against **Benchmark 1 (12-1 momentum, sign +1)**
> is **> 0 with its 95% block-bootstrap CI excluding 0**.

Nothing else gates. Rationale, and both halves of it matter:

* This is the development analogue of **criterion 5**, which §18 of the V2
  directive calls "the single most important bar in the whole directive" and
  which V2 failed twice. It is a *necessary* condition for the exam verdict.
* Development has **316 cutoffs against the exam's 72** — over four times the
  sample. An arm that cannot clear this bar with four times the power will not
  clear it on the exam. Opening the exam anyway would consume a non-renewable
  asset to obtain a foregone conclusion.

The gate is deliberately **weaker** than the exam demands: it is one of nine
criteria, not nine. It cannot let through anything the exam would not also have
to judge, and it cannot be satisfied by an arm the exam would pass.

**If the gate closes, that is the result.** The exam set stays sealed, the
ladder is reported as a null, production stays at weight 0 / HOLD, and the 72
frozen cutoffs remain available for a future arm under a future
pre-registration. The following are ruled out in advance as responses to a
closed gate, in the same terms `V2_1_PREREGISTRATION.md` §0 rules out its own
list:

* opening the exam anyway "just to see";
* replacing Benchmark 1 with Benchmark 2 or 3 in the gate;
* relaxing "CI excludes 0" to "mean > 0";
* selecting a fifth arm, or re-running any arm with different features or
  parameters, and calling the result the same ladder;
* reporting the best development arm's exam-free numbers as evidence of alpha.

---

## 6. What is measured on development, and what it is allowed to decide

Every arm is scored on the development set under the **full V2.1 protocol**
(`protocol.assess` — all nine gates, both gating benchmarks, Benchmark 3,
turnover, the cost adjustment, the half-sample split, the regime table and the
block-length sensitivity).

Those nine gates are **diagnostics on development and gates only on the exam.**
`V2_1_PREREGISTRATION.md` §4 says "all nine must pass **on the exam set** for
production weight to exceed 0", and running the same arithmetic on development
does not make development an exam. A development pass is not a pass. The one
development number with authority over anything is the §5.2 gate.

Recorded in the development artefact before the exam is opened:

1. every arm's full assessment;
2. the A→B, B→C and C→D deltas, as paired per-cutoff IC differences;
3. every arm against all three benchmarks;
4. the Holm correction over k = 4;
5. the selected exam arm, the §5.2 gate verdict, and the reason;
6. the exact feature list each arm was given.

---

## 7. Leakage

Unchanged from `V2_1_PREREGISTRATION.md` §7 and enforced the same way. Three
things specific to this stage:

* `alpha/ladder.py` obtains its cutoffs from `examset.development_only()`, which
  slices to the frozen development list and then **asserts** that no exam cutoff
  survived, rather than trusting the slice.
* The walk-forward's training pool is the development panel's own cutoffs. No
  exam cutoff is a training candidate, at any refit, for any arm.
* Scoring the exam is a separate process from predicting it
  (`alpha/v2_1_exam.py predict` / `score`), and `predict` refuses to overwrite an
  existing prediction file. Regenerating a frozen prediction once its outcome is
  known is the failure the whole study is built to prevent.

---

## 8. Production

Unchanged, and this document does not have the authority to change it.
`alpha/adapter.py` is not modified. Production weight remains **0** and the
action remains **HOLD** until all nine gates of `V2_1_PREREGISTRATION.md` §4
pass on the frozen exam set with the §4 correction of *this* document applied.
No result of this ladder — on development or on the exam — moves production by
itself.

---

## 9. Failure rule

Inherited, and it binds this document too. A null is a result. The four
outcomes, all of them acceptable, none of them requiring a fifth arm:

1. **B ≈ A ≈ Benchmark 1.** Market context adds nothing to momentum in the
   cross-section. Gate closes, exam stays sealed. This is a clean answer to §1.
2. **B > A but the gate does not clear.** Context moves the number without
   beating the benchmark. Reported as a direction, not a finding.
3. **The gate clears and the exam fails some of the nine.** Reported gate by
   gate, weight stays 0.
4. **The gate clears and the exam passes all nine, Holm-corrected at k = 4.**
   Then, and only then, the production question is reopened — and even then
   under `V2_1_PREREGISTRATION.md` §2.6's disclosure that a V2.1 pass is
   evidence about a model, not about a feature family, because the exam dates
   lie inside the window V2's development ladder ran over.

The prediction recorded before the fit, so that agreement is not read as
insight: outcome 1 or 2 is the more likely, on the strength of V2's null and of
§2's observation that arm B has exactly one degree of freedom with which to
differ from the benchmark.
