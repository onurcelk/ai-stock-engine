# V2.1 experiment log

Every V2.1 run, in order, with what it produced and what it cost. V2's log
(`EXPERIMENT_LOG.md`) records a finished study and is not edited; this is a new
file so that the two are never confused.

The rule this log exists to enforce: **deleting `out/v2_1_exam_set.json` and
re-freezing is a deliberate act, and it gets an entry here explaining why,
written before the re-freeze.** An exam set that can be quietly rebuilt after a
result is not an exam set.

---

## 2026-08-08 — stage 0: freeze the exam set

`python -m alpha.examset freeze`

First and only freeze. Written before any V2.1 model, feature set or fit
existed. Pre-registration (`V2_1_PREREGISTRATION.md`) was written first.

```
grid       532 cutoffs, 2016-01-04 .. 2026-07-28
warm-up    100 grid cutoffs (504 sessions), development-only
exam       every 6th -> 72 cutoffs, 30 sessions apart
developmnt 316 cutoffs (>= 10 sessions from any exam date)
digest     b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0
```

Independence, verified at freeze time rather than assumed: min gap = max gap =
30 sessions, 25 clear sessions between adjacent outcome windows, no duplicates,
`all_windows_disjoint = true`.

Metadata for all 72 cutoffs is computed from a `PriceView` truncated at the
cutoff — regime tag, VIX level and percentile, trailing SPY returns, eligible
cross-section width, index coverage. No outcome of any kind is stored.

Cost: ~90 s, dominated by `universe.eligible_at` running once per exam cutoff.

**Nothing was rebuilt.** All 72 exam cutoffs and all 316 development cutoffs are
already rows in `out/panel.pkl`, which was built over the same 5-session grid
during V2. Checked before freezing, asserted afterwards by
`test_every_frozen_exam_cutoff_exists_in_the_built_panel`.

### Design decisions taken here, and what they cost

* **Step 6 rather than 5, 7 or 8.** Swept over steps 5–8 × warm-ups of 378/504/
  630 sessions, on cutoff counts and pre-cutoff regime tags only. Step 5 yields
  87 exam / 271 development; step 8 yields 54 exam / 370 development, which
  fails the ≥ 60 requirement. Step 6 is the point where the exam clears 60 with
  margin and development stays 4.4× larger.
* **Warm-up in sessions, not in cutoffs.** The development set is defined in
  terms of the exam set, so defining the exam set in terms of the development
  set would close the loop. 504 sessions leaves 100 development cutoffs before
  the first exam date against a training minimum of 60.
* **Purge at ±10 sessions, not V2's ±10-with-a-different-meaning.** V2 dropped
  development cutoffs within `HORIZON + EMBARGO` of an exam date, which on a
  12-date exam cost 48 cutoffs. The same blanket rule against 72 exam dates
  would have cost 264. The rule is restated as the invariant it was always
  meant to express — *every development outcome window stays ≥ 5 clear sessions
  from every exam outcome window* — which drops 2 neighbours per exam date
  rather than 4, costs 144, and is the same guarantee.
* **Study start left at 2016-01-04.** Moving it to 2015-01-05, the earliest date
  with 253 sessions of history behind it, would add ~50 grid points at the front
  of a warm-up that is already 40 cutoffs longer than it needs to be. It would
  also change a V2 constant. Not done.

---

## 2026-08-08 — stage 0b: the protocol

`alpha/protocol.py`, with `app/tests/test_alpha_v2_1.py` (28 tests).

The nine gates, the fixed benchmark hierarchy, turnover, the cost adjustment and
the interval sensitivity. Exercised only on synthetic panels: **no V2.1 arm has
been scored on the frozen exam, and none will be until the ladder is
pre-registered.**

Full suite with `--runslow` re-run to confirm no regression against V2.

---

## 2026-08-08 — stage 1: the ladder pre-registration

`alpha/V2_1_LADDER_PREREGISTRATION.md`, written before the first V2.1 fit.

Fixes the four arms and their exact column lists, the family size **k = 4**, the
learner (unchanged `models.MODEL_A_PARAMS`), the rule that picks the single arm
sent to the exam, and the gate that decides whether the exam opens at all.

Two decisions taken here that narrow `V2_1_PREREGISTRATION.md` §5, both recorded
with their reasons before any number existed:

* **V2.1-A is not eligible to be the exam arm.** An arm given only `ret_12_1` is
  Benchmark 1 up to non-monotonicity, so it scores a paired difference of ~0
  against it and cannot pass criterion 5. Sending it would spend 72 irreplaceable
  dates confirming an identity.
* **A development gate on opening the exam**: the selected arm must beat
  Benchmark 1 on development, paired, with the 95% block-bootstrap CI excluding
  0. Development has 316 cutoffs against the exam's 72; an arm that cannot clear
  the study's central bar with four times the power will not clear it on the
  exam, and opening it anyway consumes a non-renewable asset for a foregone
  conclusion. The gate is one of nine criteria, so it is strictly weaker than the
  exam and cannot let through anything the exam would not also judge.

Also fixed here: the exam arm's criterion-1 p-value is corrected at **k = 4**,
not k = 1, because it is the maximum of four development ICs.

---

## 2026-08-08 — stage 1b: the ladder on development

`python -m alpha.ladder`  (~2.5 min, 34 refits per arm, 143,675 rows ×
316 development cutoffs, 255 scored)

Preceded by one smoke run, `python -m alpha.ladder --only V2.1-A`, which wrote a
single-arm `out/v2_1_development.json` that the full run then replaced. Recorded
because the file it wrote is the one `v2_1_exam.py` reads its configuration from,
and a partial version of it existed for about four minutes. No exam date was
touched by either run.

```
arm      feat   mean IC   95% block CI          hit    vs 12-1 momentum
V2.1-A      1  +0.00053  [-0.00839, +0.00890]  48.2%  -0.02061 [-0.05457, +0.01165]
V2.1-B     27  +0.01845  [+0.00199, +0.03787]  55.3%  -0.00269 [-0.03612, +0.03332]
V2.1-C     35  +0.03080  [+0.01114, +0.05490]  61.2%  +0.00965 [-0.02256, +0.04633]
V2.1-D     35  +0.03426  [+0.01772, +0.05556]  58.4%  +0.01312 [-0.01862, +0.05006]

benchmarks, same 255 cutoffs, nothing fitted
B1 12-1 momentum   +0.02115  [-0.00469, +0.04808]
B2 5-day reversal  +0.00872  [-0.01268, +0.02808]
B3 regime-switched +0.02836  [+0.00307, +0.05467]   <- the only one excluding 0
```

**§5.1 selected V2.1-D. §5.2 gate CLOSED** (+0.01312, CI [−0.01862, +0.05006]).
**The 72 exam cutoffs were not opened and no prediction file was written.**
`python -m alpha.v2_1_exam predict` was run once to confirm the seal holds; it
exited 1 with the §5.2 refusal and wrote nothing.

Full write-up in `V2_1_LADDER_REPORT.md`. The three findings that outrank the
verdict:

* **A learned univariate map destroys the factor it was given.** V2.1-A scored
  +0.00053 where ranking by `ret_12_1` directly scores +0.02115. Measured, not
  inferred: within a cutoff A's prediction is a step function of `ret_12_1`
  (distinct values == runs when sorted by it, 115–219 of a 426–502 cross-section)
  and its within-cutoff Spearman against `ret_12_1` averages **−0.198**, negative
  on 224 of 255 cutoffs. The learner fit a decreasing map on the pooled level and
  then ranked with it. Every V2 arm carried its factors through the same step.
* **A→B is a recovery, not an addition.** +0.01792 with a CI excluding zero, but
  B ends at +0.01845 against raw momentum's +0.02115. Context is genuinely used —
  B's within-cutoff correlation with momentum ranges −0.99 to +0.99, i.e. it
  flips the factor — and flipping it does not beat holding it.
* **A three-line hand-specified rule (B3) is within noise of the 35-feature
  model.** D beats it by +0.0059, CI [−0.02451, +0.04076].

Regime, on development: C and D earn +0.076 / +0.066 in the 27 BEAR cutoffs and
+0.001 / −0.002 in the 24 SIDEWAYS ones. That is V2's pathology with V2's
favourite bucket, and V2's exam is the reason it is reported as a warning.

Power, for the record: the gate interval's half-width is ≈0.0343 on 255 cutoffs,
so resolving D's +0.0131 edge would need ~1,750 non-overlapping weekly cutoffs —
about 35 years. Ten years of history cannot settle an edge this small against
momentum.

### Not done, and named in advance as not-to-be-done

No threshold lowered, no benchmark swapped into the gate, no relaxation to
"mean > 0", no fifth arm, no hyperparameter search, no exam opened "just to see".
`adapter.py`, `develop.py`, `exam.py`, `PREREGISTRATION.md` and
`V2_1_PREREGISTRATION.md` are unmodified. Production weight 0, action HOLD.

`pytest -q --runslow`: **544 passed** (527 + 17 in
`app/tests/test_alpha_v2_1_ladder.py`).

---

## Not yet run

* any scoring at all on the 72 frozen exam cutoffs — the set is still sealed,
  digest `b55e065f…` unchanged;
* the follow-up the report argues for: a monotone-preserving carrier from factor
  to cross-sectional rank, and an arm pre-registered against Benchmark 3 rather
  than against Benchmark 1.
