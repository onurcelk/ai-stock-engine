# V5 Phase 5(a) — ABS-1 Weight-to-Abstain: Gate 1 result

**Verdict: `ABS-1 VERDICT: NOT ANSWERABLE IN THIS HARNESS`.**

Gate 1 (power) failed. Under §7 of the pre-registration the study does not run:
`validation/out/calls.csv` was never opened, no accuracy was computed, and no
band was counted against an outcome.

| | |
|---|---|
| Pre-registration | `alpha/V5_ABSTENTION_PREREGISTRATION.md`, frozen 2026-08-14, commit `f53aa96` |
| Gate computation | `alpha/abs1_power_gate.py`, commit `660ce25` — **committed before it was run** |
| Gate output | `alpha/out/abs1_power_gate.json` |
| Outcomes read | **None.** The gate opens `validation/out/predictions.json` and nothing else |
| Budget | No information-family slot spent. Nothing trained, no symbol or cutoff added |
| Exam | Sealed. Not accessed |

---

## 1. What was asked

Phase 5 as written — adaptive reweighting of constituents by demonstrated OOS
usefulness — was found BLOCKED by Phase 4: the frozen record supplies no set of
constituents with differing measurable usefulness to reallocate weight between.
`reports/V5_PHASE4_CHALLENGER_EVAL.md` §10.2 offered two reformulations and the
programme owner chose **(a) weight-to-abstain** on 2026-08-14.

The question: *does the engine's forecast-time `coverage` gate identify, in
advance, the symbol-dates where its calls are worth acting on?*

## 2. Why this was admissible against a closed programme

PIT-1 is CLOSED, and re-running it is the reopening Phase 4 §2 already refused.
ABS-1 was admitted on one specific ground, recorded in the pre-registration §1
before anything was computed.

`validation/REPORT.md` states, as the study's one positive finding:

> *"The engine's refusal to speak is calibrated even though its confidence is
> not. It said HOLD on 74.3% of symbol-dates, and on the 25.7% it did call, its
> edge over a trivial rule was zero."*

**That sentence asserts a property it never measures.** A 74.3% abstention rate
says how often the engine declines, not whether it declines in the right places;
the second clause is if anything evidence against the claim. Nowhere in PIT-1 is
the abstention decision related to the quality of the rows it selects. ABS-1
tested an assertion the closed record left unmeasured — not a result it
established. No candidate was re-evaluated, no arm resurrected, no threshold
moved.

Phase 4 §10.2 relied on that unmeasured sentence when it called calibrated
gating "the one validated property of this system". §6 below bears on that.

## 3. The variable, and why it is not the one PIT-1 banded

PIT-1 banded `confidence`. Confidence is the product of three gates —
`skill_gate × accord_gate × coverage_gate` — so banding it confounds three
questions. ABS-1 isolates the third term.

Bands were read off committed arithmetic in `ultimate.evaluate_frame`, not
fitted. With `FULL_BREADTH = 3` and `REFERENCE_WEIGHT = 6`, the coverage gate
collapses to `breadth` alone once surviving weight reaches 6, taking only the
values `{1/3, 2/3, 1}`. The four ordered bands follow from that and from nothing
else:

```text
A  coverage == 0          structural abstention, no direction named
B  0 < coverage <= 1/3    one family's worth of breadth
C  1/3 < coverage <= 2/3  two families' worth
D  2/3 < coverage <= 1    full breadth
```

## 4. Gate 1 — the measurement, from signal geometry alone

Computed over the 845 available horizon verdicts in the frozen prediction
record. The design effect is re-derived from PIT-1's own **published** interval
(`validation/REPORT.md` §8: n = 134, 53.7%, [40.6, 66.8] clustered by cutoff) —
quoted, never recomputed — giving a published half-width of 13.10 pp, DEFF
2.408 and an implied ICC of 0.1385 at PIT-1's mean cluster size. Each band's
design effect is then re-derived at its own cluster size rather than assumed
constant. Accuracy is unknown pre-outcome, so `p = 0.5` is used throughout,
maximising binomial variance.

| band | rows | dates | symbols | rows/date | DEFF | half-width | meets minimum geometry |
|---|---:|---:|---:|---:|---:|---:|---|
| A — abstention | 652 | 12 | 28 | 54.33 | 8.384 | 11.11 pp | yes |
| B — one family | 120 | 12 | 25 | 10.00 | 2.246 | 13.41 pp | yes |
| **C — two families** | **7** | **5** | **5** | **1.40** | 1.055 | 38.05 pp | **NO** |
| D — full breadth | 66 | 12 | 16 | 5.50 | 1.623 | 15.37 pp | yes |

Minimum geometry required 25 rows, 6 dates and 8 symbols. **Band C fails all
three.**

The primary contrast:

| | |
|---|---|
| `D − B` clustered half-width | **20.39 pp** |
| `D − B` MDE at 80% power | **29.15 pp** |
| Pre-registered threshold | **7.5 pp** |

```text
GATE 1 (POWER): FAIL
```

**The instrument is 3.9× too coarse.** To register, the full-breadth band would
have to out-perform the one-family band by 29 percentage points of directional
accuracy. Nothing in this repository's record suggests an effect within an order
of magnitude of that; the 7.5 pp threshold was itself anchored on the *largest*
selection effect this gating has ever shown (PIT-1 §8: 53.7% when it leaned
against 61.2% on calls it promoted to actionable).

**The failure is conclusive, not provisional.** §6.1 of the pre-registration
fixed, before the run, that this geometry is an *upper bound* on the scoreable
rows — a horizon can lean at its cutoff and still drop out of `calls.csv` for
want of a complete outcome window. The gate therefore ran on at least as many
rows as the study would have had, and its MDE errs toward passing. The real
geometry is never better than the one measured here. (Consistent with that: 193
spoken rows here against PIT-1's 134 scoreable leans.)

## 5. One structural finding, on the prediction side only

Recorded because it is a property of the code, established without reading any
outcome, and because it explains the gate failure rather than excusing it.

**The coverage gate is effectively bimodal.** Of the 193 rows on which the engine
named a direction, 120 sit at one family's breadth and 66 at full breadth, while
the intermediate two-family state holds **7 rows across 5 dates**. The
distribution has no middle. This is not a sampling accident — it follows from
`breadth = min(1, families_firing / 3)` combined with the significance floor:
either a single family clears it, or enough clear it that breadth saturates.

The consequence for any future study is that "coverage" cannot be treated as a
continuous dial. It is close to a binary — narrow versus broad — and a design
that assumes a graded ordering across three or more levels will find the middle
of that ordering empty, as this one did.

## 6. What this does and does not conclude

**It does not conclude that the coverage gate lacks selection value.** No
accuracy was computed. This is a statement about the instrument, not about the
engine.

**It does conclude that the question is not answerable on this record**, and the
remedy is the one thing this harness cannot supply: more *independent cutoff
dates*. Twelve is the binding constraint, exactly as it was for every Phase 4
comparison. Adding cutoffs to PIT-1's grid is the re-run Phase 4 §2 refused
under CLAUDE.md §1.3, and the three residual look-aheads PIT-1 disclosed remain
unrepaired, so a repaired harness is the precondition for any future attempt —
not a larger sample on the existing one.

**It sharpens one thing about the record.** Phase 4 §10.2 described calibrated
gating as "the one validated property of this system", inheriting PIT-1's
wording. On the evidence now available that description is too strong: the
property was asserted, never tested, and the only test designed for it could not
be run for want of resolution. This is **not** a correction to PIT-1 under
CLAUDE.md §1.1 — PIT-1's claim has not been contradicted, and appending a
correction to a frozen record on the strength of an unrun study would be its own
kind of error. It is recorded here, in this phase's own report, as a
qualification a future reader of §10.2 needs.

Pre-registration §8 fixed in advance what a Gate 1 failure means and that clause
governs: the coverage gate's selection property is **untested**, and it stays
untested until a harness exists that could test it.

## 7. What was not done

- `validation/out/calls.csv` was not opened.
- No accuracy, no MAE, no baseline comparison, no interval on any outcome.
- No substitute statistic was attempted after the gate failed. §2 of the
  pre-registration fixed one pass and no second look; re-banding on `confidence`
  or collapsing C into D to rescue the geometry is exactly the mining that
  clause forbids.
- No model promoted, demoted, retired or reopened. No production weight changed.
- No CLAUDE.md §1.2 methodology surface touched.

## 8. Recommendation to the programme owner

Phase 5 is now closed in both of its forms. As written it was blocked by Phase 4;
in reformulation (a) it is unanswerable at this resolution. The remaining
Phase 4 recommendation stands unchanged and is now the only one left:

> **(b) Phase 9 — Data Gap Analysis.** The engine reads price and volume only,
> its components measure market drift, and the resolution arithmetic says the
> instrument cannot see effects of the size the available information plausibly
> carries.

ABS-1 adds one argument for it. The binding constraint on this programme is not
which model, not which weighting, and not which gate — it is that twelve
independent market draws cannot resolve a 7.5 pp effect. Phase 9's own gate,
*"any new dataset must have a precise hypothesis and measurable expected role"*,
is the right next one to face, and a resolution requirement should be part of
what any candidate dataset is asked to justify.
