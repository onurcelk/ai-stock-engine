# ABS-1 — Weight-to-Abstain Study: pre-registration

**Frozen 2026-08-14, committed BEFORE any ABS-1 statistic existed, before any
coverage band was counted against an outcome, and before the power gate was
computed.** This document may not be edited afterwards, only appended to with
dated corrections (CLAUDE.md §1.1).

> **The question.** Does the engine's forecast-time `coverage` gate identify, in
> advance, the symbol-dates where its calls are worth acting on?

This is V5 Phase 5 in the reformulation the Phase 4 report set out at
`reports/V5_PHASE4_CHALLENGER_EVAL.md` §10.2(a), chosen by the programme owner
on 2026-08-14. Phase 5 **as written** — adaptive reweighting of constituents —
is not entered and is not rescued by this document.

**What ABS-1 is not.** It is not a re-evaluation of any candidate's skill. No
arm is resurrected, no threshold is moved, no model is promoted or demoted, and
no candidate is compared against a baseline for the purpose of establishing
skill. Every such comparison in this repository is CLOSED and stays closed.
ABS-1 asks a question about a **property of the gating machinery**, not about
the value of anything the machinery gates.

---

## §0 Standing

| | |
|---|---|
| Prior results | **Unchanged.** PIT-1 is CLOSED. Production weight 0.0. Every V5 Phase 4 candidate is STOP on route 1. No candidate advances on the strength of anything below |
| Budget | ABS-1 spends **no information-family slot**. It opens no external data source, adds no symbol, adds no cutoff, and trains nothing |
| Exam | **SEALED.** Not loaded, not scored, not inspected. ABS-1 never touches an exam artifact |
| Data | The frozen PIT-1 artifacts only: `validation/out/predictions.json` (prediction side) and `validation/out/calls.csv` (outcome side) |
| Code | ABS-1 **reads** `app/core/ultimate.py`'s arithmetic to derive its bands. It modifies no CLAUDE.md §1.2 methodology surface and requires no amendment |

## §1 The claim under test, and why testing it is not reopening PIT-1

`validation/REPORT.md`, under *"The one thing that came out well"*, states:

> *"The engine's refusal to speak is calibrated even though its confidence is
> not. It said HOLD on 74.3% of symbol-dates, and on the 25.7% it did call, its
> edge over a trivial rule was zero."*

**That sentence asserts a property it does not measure.** An abstention rate of
74.3% is a fact about how often the engine declines; it is not evidence that it
declines in the right places. The second clause — zero edge where it spoke — is
if anything evidence *against* the claim. Nowhere in PIT-1 is the abstention
decision related to the quality of the rows it selects.

This matters for §1.3 of CLAUDE.md. ABS-1 does not re-test a result PIT-1
established; it tests an assertion PIT-1 **left unmeasured** and that a later
phase (`reports/V5_PHASE4_CHALLENGER_EVAL.md` §10.2) then relied upon. The
distinction is recorded here because it is the whole basis for ABS-1 being
admissible, and if it is wrong, ABS-1 is inadmissible and must not run.

**Specifically not re-opened:**

| PIT-1 result | Status under ABS-1 |
|---|---|
| Every candidate below `always_bullish` on identical rows | **Final.** Not recomputed, not appealed |
| Consensus acted-calls 61.2% [49.6, 72.7], p = 0.056 | **Final.** Quoted as a prior, never re-derived |
| Confidence bands non-monotone, top band 2 of 5 | **Final.** ABS-1 bands a *different variable* (§3) |
| Score bands: `ACT_BAND` separates sign, `STRONG_BAND` adds nothing | **Final.** Not re-banded |
| The three residual look-aheads are unrepaired | **Carried forward.** See §9 |

## §2 The honest weakness of this design, declared in advance

**The outcomes in this dataset are already revealed and have already been
analysed along other axes.** ABS-1 is a *re-analysis of a frozen record*, not a
prospective study. It has the form of a preregistration — statistic, bands,
gates and verdict rule fixed before computation — but it cannot have the force
of one, because the data it will touch is not new.

Two consequences, both binding:

1. **ABS-1 may not produce a positive claim of skill.** The strongest verdict
   available to it is *"the gate's selection property is consistent with the
   record and is worth testing prospectively"*. It may not be written up as a
   demonstration that abstention works.
2. **ABS-1 runs once.** One statistic, one set of bands, one pass. If the gate
   in §6 fails, the study does not run and no substitute statistic is
   attempted. There is no second look at this dataset under this question.

## §3 The banded variable — boundaries are arithmetic, not fitted

The variable is `HorizonVerdict.coverage`, the third of the three multiplied
gates in `ultimate.evaluate_frame`. It is **not** `confidence`, which PIT-1
already banded: confidence is the product `skill_gate × accord_gate ×
coverage_gate`, so banding it confounds three separate questions. ABS-1 isolates
the coverage term.

From the code (`app/core/ultimate.py`, `evaluate_frame`):

```text
breadth       = min(1, families_firing / FULL_BREADTH)     FULL_BREADTH = 3
scale         = breadth / max(total, REFERENCE_WEIGHT)     REFERENCE_WEIGHT = 6
coverage_gate = min(1, total * scale)
```

so for surviving weight `total >= 6` the coverage gate collapses to `breadth`
alone and takes only the values `{1/3, 2/3, 1}`; below 6 it is
`(total/6) x breadth`. **The variable is near-discrete by construction and its
natural boundaries are the breadth fractions.** The four ordered bands are
therefore:

```text
A  coverage == 0            no family cleared significance — structural abstention
B  0 < coverage <= 1/3      one family's worth of breadth
C  1/3 < coverage <= 2/3    two families' worth
D  2/3 < coverage <= 1      full breadth
```

**No boundary was placed by looking at a hit rate and none may be moved after
one is seen.** They are read off `FULL_BREADTH = 3`, which is committed code
that predates this study.

Band A is definitionally empty of directional calls: `reports/V5_PHASE4_CHALLENGER_EVAL.md`
§7.3 records, from the prediction side only, that every neutral verdict had
`coverage == 0` and zero live sources. Band A is therefore reported as a
diagnostic and carries no accuracy statistic. **The primary statistic uses bands
B, C and D**, which are exactly the rows on which the engine named a direction.

## §4 Unit of observation and the join

One observation is a `(cutoff, symbol, horizon)` triple.

| | |
|---|---|
| Prediction side | `validation/out/predictions.json` → `predictions[].consensus.by_horizon[]`, fields `coverage`, `agreement`, `score`, `confidence`, `available` |
| Outcome side | `validation/out/calls.csv`, rows where `system` ∈ {`consensus_4h`, `consensus_1d`, `consensus_1w`}, joined on `(cutoff, symbol)` and the horizon implied by the system label |
| Direction named | `score != 0`, the same `has_lean` definition PIT-1 used |
| Correctness | the frozen `correct` column. **ABS-1 does not recompute a single outcome** |
| Clustering | **by cutoff date, always.** 30 symbols read on one day are one draw |

Rows are scored at each system's own native window, matching PIT-1. No horizon
is re-windowed and no window is re-derived.

## §5 Hypotheses

* **H1 coverage monotonicity** — directional accuracy rises monotonically across
  bands B → C → D. *The central hypothesis, and the direction is declared here.*
* **H2 decision value** — the engine's accuracy **minus** `always_bullish`
  accuracy on the identical rows rises across B → C → D. H1 without H2 is a
  statement about which rows drift, not about whether the gate is useful.
* **H3 abstention selection** — `always_bullish` accuracy on band-A rows differs
  from its accuracy on bands B–D. This is the one test of *where* the engine
  declines to speak, as opposed to how often. **Two-sided**: the record supplies
  no prior for the sign, and inventing one after the fact is forbidden.

`agreement` is a **pre-declared secondary diagnostic**, banded on the same
arithmetic. It may not be promoted to a primary statistic and no verdict rests
on it.

## §6 Gate 1 — Power, computed from signal geometry alone, before any outcome

Computed by `alpha/abs1_power_gate.py` from `validation/out/predictions.json`
**only**. That file contains no realised return, no outcome and no bar after any
cutoff, so the gate is computed in strict two-process separation (CLAUDE.md
§2.2): the gate code never opens `calls.csv`.

Uncertainty instrument: **accuracy half-width clustered by cutoff date**, the
same instrument PIT-1 used, with the same design-effect inflation. Cutoffs, not
symbol-dates, are the independent unit.

### Minimum geometry for a band to count as a result rather than a diagnostic

**25 spoken rows, 6 distinct cutoff dates, 8 distinct symbols.** A band below any
of the three is reported as a diagnostic and is excluded from the H1 trend, on
the same principle that excluded AMS-1's `mixed` state.

### The detectability threshold, and its anchor

**Gate 1 passes only if the minimum detectable difference (MDE) on the
`D − B` accuracy gap is ≤ 7.5 percentage points.**

The anchor is the record's own largest observed selection effect for this
machinery, and it is not invented here. PIT-1 §8 measured consensus accuracy at
**53.7%** on all rows where it leaned and **61.2%** on the subset it promoted to
an actionable call — a **7.5 pp** selection effect, and the largest this gating
has ever shown. An instrument that cannot resolve 7.5 pp cannot see an effect of
the size this system is capable of producing, and a study run on it would
measure its own noise.

The secondary anchor is `reports/SINGLE_NAME_PHASE1.md` §3F, which measured this
instrument's resolution directly and found an unpaired accuracy claim must clear
**2.6 pp** to escape its own noise. 7.5 pp is the looser of the two and is the
one that binds.

```text
GATE 1 (POWER): computed by alpha/abs1_power_gate.py, committed before it is run
```

### §6.1 Specification appended 2026-08-14, before the gate was run

Appended under CLAUDE.md §1.1. The original §6 wording above is unaltered. This
settles three details §6 left to the implementation, and it is committed in
`alpha/abs1_power_gate.py` **before that module is executed**, so none of them
can be chosen after seeing a number.

1. **MDE convention.** Reported at the standard two-sided 5% / 80% power
   convention, factor `1.96 + 0.8416 = 2.8016`. The bare 1.96 half-width is
   emitted alongside it, but **Gate 1 is decided on the 80%-power figure**,
   which is the stricter of the two.
2. **Worst-case variance.** Accuracy is unknown before outcomes are read, so
   `p = 0.5` is used throughout, maximising binomial variance and making the MDE
   as large as it can honestly be at a given geometry.
3. **The geometry is an upper bound.** A horizon can be available and lean at
   its cutoff yet drop out of `calls.csv` for want of a complete outcome window,
   so the gate runs on at least as many rows as the study would have and its MDE
   therefore errs toward **passing**. Binding consequence: a **FAIL is
   conclusive**, because the real geometry is never better than this one; a
   **PASS must be re-verified** against the actual scoreable row count before
   Gate 2 is computed, using the join key only and never the `correct` column.

The clustered design effect is re-derived from PIT-1's own *published* interval
(`validation/REPORT.md` §8: n = 134, 53.7%, [40.6, 66.8]) rather than recomputed
from any outcome — the same quote-don't-recompute rule Phase 4 worked under.
Backing an intra-cluster correlation out of that published half-width lets the
design effect be re-derived at each band's own cluster size instead of assumed
constant.

## §7 Acceptance gates — numeric, frozen, not adjustable after a result

| # | gate | threshold |
|---|---|---|
| **1** | **Power** | §6: bands B, C, D each clear the minimum geometry, **and** the `D − B` MDE ≤ 7.5 pp |
| **2** | **Monotonicity** | accuracy is non-decreasing B → C → D, and `D − B` exceeds its own clustered half-width |
| **3** | **Decision value** | the paired `engine − always_bullish` difference is non-decreasing B → C → D, and is positive in band D with its clustered interval excluding 0 |
| **4** | **Abstention selection** | H3's band-A vs bands-B–D difference exceeds its own clustered half-width |
| **5** | **Breadth** | ≥ 6 cutoff dates and ≥ 8 symbols in every band entering Gates 2–4 |

**Multiplicity.** Holm-Bonferroni across Gates 2, 3 and 4. The diagnostic set is
small and fixed: the four `agreement` bands, and the per-horizon split of the
primary table. Nothing else is searched.

**Verdict rule.**

* `ABS-1 VERDICT: PROSPECTIVELY WORTH TESTING` requires Gates 1, 2, 3 and 5.
  Per §2 this is the ceiling; it is **not** a finding that abstention works.
* `ABS-1 VERDICT: NOT SUPPORTED` if Gate 1 passes and Gates 2 or 3 fail.
* `ABS-1 VERDICT: NOT ANSWERABLE IN THIS HARNESS` if Gate 1 fails. The study
  does not run, no accuracy is computed, and `calls.csv` is not opened.

Gate 4 is reported in all three cases where Gate 1 permits it, and never
converts a failure elsewhere into a pass.

## §8 What each failure means, fixed in advance

**If Gate 1 fails** — the question is well-posed and the instrument cannot
resolve it. The correct conclusion is *not* that the gate lacks selection value;
it is that 12 cutoffs cannot answer this. The remedy is more **independent
cutoff dates**, which this harness cannot supply: adding them to PIT-1's grid is
the re-run that Phase 4 §2 already refused under §1.3. Any future attempt is a
new study on a repaired harness, and §9's three look-aheads bind it.

**If Gates 2 or 3 fail with Gate 1 passed** — the coverage gate does not order
call quality at this resolution. PIT-1's *"refusal to speak is calibrated"*
sentence must then be recorded as **unsupported by the only test made of it**,
by dated correction under CLAUDE.md §1.1, with the original wording left visible.
Phase 5 in every form is then closed and the programme proceeds to Phase 9.

**A claim that may not be made after a null:** that a different gate, a
different band count, or `confidence` instead of `coverage` would have shown it.
Confidence was already banded by PIT-1 and was non-monotone. Re-banding after a
null is mining.

## §9 Constraints carried forward unchanged

* PIT-1's **three residual look-aheads are unrepaired**. Until they are, this
  harness cannot support a believable positive result — only a believable
  negative one. §7's verdict ceiling exists because of this.
* Intervals from `outcome_ledger` are **nominal and assume independence**, which
  overlapping horizons violate. ABS-1 does not use them. It clusters by cutoff.
* No `probability_positive` exists anywhere in this engine. Brier, log loss and
  calibration error are **not computable** for any statistic in this document,
  and confidence is never substituted for a probability.
* `assert_record_admissible` is called on any record entering the evaluation.
* The abstained / spoken split is declared in §3 and §4, **before** measurement,
  satisfying `reports/V5_PHASE4_CHALLENGER_EVAL.md` §7.3.
* `closed.ams1_agent_meta` forecloses weighting by cross-family agent agreement.
  ABS-1's `agreement` diagnostic is *within-horizon weight concordance* from
  `ultimate.evaluate_frame`, not AMS-1's cross-family agent vote, and it is a
  diagnostic that carries no verdict. If that distinction is judged too fine,
  the diagnostic is dropped and the primary statistic is unaffected.

## §10 If ABS-1 advances

Stop at `ABS-1 PROSPECTIVELY WORTH TESTING`. Do **not** promote, do not reweight,
do not change a production threshold, and do not enter Phase 5 as originally
written. The next step is a prospective abstention study on a repaired harness,
preregistered separately, and Phase 9 Data Gap Analysis remains the programme
owner's standing recommendation regardless of this study's outcome.
