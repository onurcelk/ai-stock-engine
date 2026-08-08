# V2 Alpha Directive — execution progress

Tracks execution of [V2_Alpha_Directive_Corrected.md](V2_Alpha_Directive_Corrected.md).
**Complete as of 2026-08-08.** Everything below has been run and verified.

**Where the work lives:** `Stock-Prediction-Models/alpha/` — a new package,
separate from the frozen `validation/` (directive §0).

---

## The one thing that matters if you read nothing else

**V2 did not demonstrate alpha. Production weight is 0 and the action stays
HOLD.** The full §27 ladder ran; nothing cleared the §8 gate on development, so
V2-C and V2-D were never built; the best arm failed the twelve frozen exam
dates too. The output adapter emits HOLD on all 5,899 exam predictions, which
is the correct output rather than a defect.

Read [`alpha/V2_REPORT.md`](Stock-Prediction-Models/alpha/V2_REPORT.md) first.
`alpha/PREREGISTRATION.md` has not been edited since it was written, before the
first fit.

Three findings outrank the verdict:

1. **Stock-level cross-sectional features contributed nothing.** 18 absolute
   features scored +0.0084 mean IC; adding 47 relative and percentile features
   moved it to +0.0085. All the signal is in the market-context tier.
2. **The edge is a regime bet whose favourite regime flipped between samples** —
   BEAR on development, SIDEWAYS on the exam, negative in the other's favourite.
3. **Plain 12-1 momentum beat the model on the exam dates** (+0.85%/week
   long-short vs +0.46%). Neither is significant; the point is that criterion 5
   failed again on fresh data.

---

## Status by directive section

| § | Requirement | State |
|---|---|---|
| 0 | `validation/` frozen, V2 in an adapter layer | **Held and verified.** The only file changed outside `alpha/` is the new `app/tests/test_alpha.py`. `alpha/adapter.py` imports nothing from `validation` or `app` — asserted by a test. |
| 1 | Alpha targets A/B/C/D, rolling shrunk β, as-of-cutoff sector | Built. Sector *membership* is point-in-time; sector *labels* are not — disclosed. |
| 2 | Don't mix asset classes; universe too thin at 22 names | **Fixed via option (a).** PIT S&P 500 membership; 410–500 eligible equities per cutoff. |
| 3 | Kill the 4-hour horizon; primary = 5 sessions | Done. |
| 4 | `alpha_5d = R_asset − R_SPY` | Done, scorer-side only. |
| 5 | Cross-sectional rank target; embargo/purge; NW or block-bootstrap SEs | Done. Cutoffs spaced 5 = horizon, so windows are non-overlapping by construction, plus NW and moving-block bootstrap on top. |
| 6 | Don't vol-scale yet | Raw excess return is the V2-A/B/E target; vol-scaled is V2-F only. |
| 7–8 | Absolute + relative + sector + percentile; denominator floors | Done. 100 features. **Result: the relative tier added +0.0001 IC.** |
| 9 | Overnight/intraday decomposition | Built, in V2-E. Part of the only tier that moved the number. |
| 10–11 | Regime, VIX, breadth; breadth-proxy naming | Built. `index_breadth_*` real, `watchlist_breadth_proxy_*` labelled a proxy. |
| 12 | Sector-relative flagship feature | Leave-one-out mean of PIT sector peers. |
| 13 | LSTM out of the primary path | Held. |
| 14 | A → A′ → B → C, A′ *before* B as a gate | Held. **The gate closed and B/C were not built.** |
| 15 | Spearman IC primary; numeric thresholds pre-registered | Measured. |
| 16–17 | Balanced long/short quintile spread | Equal names per side by construction. |
| 18 | Must beat the best simple factor | **Failed** on development (CI [−0.0029, +0.0455]) and again on the exam. |
| 19 | Walk-forward; 12 frozen dates untouched | Held. Opened once, after development closed. |
| 20 | 50–100+ cutoffs | 484 development (423 evaluated) + 12 exam. |
| 21 | Pre-registration | `alpha/PREREGISTRATION.md`, unedited. |
| 22 | ModelEvidence numeric gate | Seven criteria evaluated on both sets. Weight 0. |
| 23 | No confidence score yet | Held — none computed or exposed. |
| 24–26 | Presentation, HOLD-by-default, cost fields | `alpha/adapter.py`. Cost fields reserved, unpopulated. |
| 27 | V2-A → … → V2-G with gates | A/B/E/F run; **C/D/G not built** (gates closed). |
| 28–29 | Failure is a first-class outcome | This is that outcome. |
| 30 | Deliverables 1–6 | **All six addressed**; deliverable 2 (the ranker) is "not built, gate closed", which is the honest state, not an omission. |

---

## What exists

```
alpha/
  membership.py     PIT S&P 500 reconstruction from the index change log
  download.py       fetches to alpha/cache (NOT app/cache)
  pitdata.py        the V2 data door + load_calendar()
  universe.py       eligibility at T
  targets.py        alpha_5d, sector-relative, residual, shrunk betas
  features.py       100 features in three tiers
  dataset.py        panel builder, cutoff schedule, purge + embargo
  stats.py          Spearman IC, block bootstrap, Newey-West, Holm-Bonferroni
  models.py         Model A (GBM), Model A' (6 factors), gated B and C
  walkforward.py    walk-forward + the 7 §8 criteria
  build_panel.py    stage 0 — freeze the panel
  develop.py        stage 1 — the §27 ladder, development cutoffs only
  exam.py           stage 2 — predict / score, two processes
  compare.py        deliverable 6 — one yardstick, identical dates
  adapter.py        §24-26 output layer, HOLD-by-default
  PREREGISTRATION.md  EXPERIMENT_LOG.md  V2_REPORT.md
  out/              panel.pkl, development.json, exam_predictions.json,
                    exam_scores.json, comparison.json,
                    run1_dead_ret_12_1/ (the archived buggy run)
app/tests/test_alpha.py   29 tests
```

**Test status (verified 2026-08-08):** `app/tests` full suite with `--runslow`
— **499 passed**, no regressions. `test_alpha.py` — 29 passed.

Two new guard tests, both written against bugs that actually happened:

* `test_no_feature_is_dead_on_a_full_history` — no feature column may be NaN
  for every symbol.
* `test_the_built_panel_covers_every_exam_cutoff` — the panel must contain
  every exam date, and development must not widen.

---

## How to re-run

```bash
cd "Stock-Prediction-Models"
./.venv/Scripts/python.exe -W ignore -m alpha.build_panel   # ~3 min
./.venv/Scripts/python.exe -W ignore -m alpha.develop       # ~4 min
./.venv/Scripts/python.exe -W ignore -m alpha.exam predict  # refuses to overwrite
./.venv/Scripts/python.exe -W ignore -m alpha.exam score
./.venv/Scripts/python.exe -W ignore -m alpha.compare
./.venv/Scripts/python.exe -W ignore -m alpha.adapter
```

Use `.venv` (scientific stack); `./venv` is the one with pytest. Per-fit cost
is ~5 s on 220k rows × 100 features — the pre-run estimate of 15–20 min per
experiment was wrong by an order of magnitude.

`alpha.exam predict` refuses to overwrite `out/exam_predictions.json`. Deleting
it to re-run is a deliberate act that has to be explained.

---

## Two bugs found and fixed (both now tested)

1. **`ret_12_1` was identically NaN for a whole development run** — guard read
   `len(close) > 253` while the slice capped the frame at 253 rows. Four dead
   features, every model silently fitted on 96, and `mom_12_1` — the factor
   that turned out to matter most in the final comparison — untested. Run 1
   archived at `alpha/out/run1_dead_ret_12_1/` so the fix's effect is checkable.
   It flipped criteria 1–3 from fail to pass; the verdict was FAIL both times.
2. **Eight of the twelve exam dates were not in the panel** — built over a
   5-session grid the V1 dates know nothing about. Caught by a crash before any
   exam number was scored. Development was unchanged (484 cutoffs, 221,519
   rows) so it was not re-run.

---

## Decisions recorded so they are not re-litigated

* **Refit cadence.** Pre-registered as "every 13 cutoffs (quarterly)",
  implemented as 65 sessions of staleness — identical on the weekly development
  schedule, and correct on the exam schedule where a cutoff-count rule would
  predict 2026 with a model trained through 2022.
* **All-NaN feature columns are dropped at fit time, not imputed.** A
  cross-sectional mean would be computed from the same cutoff it fills.
* **The §14 gate was left as written** (V2-A *or* V2-B), not widened to "any
  arm", even though V2-E/V2-F cleared parts of the bar and widening it would
  have opened the ranker.
* **The exam was run once on a configuration that had already failed
  development**, because §19 built it to be opened once after development
  closes and deliverable 6 needs identical dates. Reported as a measurement,
  not a second chance.

---

## The honest next steps (from §9 of the report)

1. **Fix the exam set before fixing the model.** 12 dates cannot support
   criterion 7 (≥ 50 cutoffs), so §9 holds weight at 0 by construction. A
   frozen exam of 60+ non-overlapping cutoffs, agreed in advance, is the
   highest-value change available and is not a modelling change.
2. **Choose the simple-factor baseline by economic prior, not |mean IC|.** The
   current rule picked 5-day reversal, which led on development and reverted on
   the exam; 12-1 momentum is the harder and more honest bar.
3. **Stop asking stock-level features to rank the cross-section.** V2-A vs
   V2-B is a well-powered null over 423 cutoffs.
4. **Do not fund the regime-conditional edge on this evidence.**

---

## What came next — V2.1 (2026-08-08)

Steps 1 and 2 above are done. Nothing else in this file changed; V2 remains a
completed experiment and its artifacts are untouched.

* [`alpha/V2_1_PREREGISTRATION.md`](Stock-Prediction-Models/alpha/V2_1_PREREGISTRATION.md) —
  the new protocol, written before the exam set was built.
* [`alpha/V2_1_VALIDATION_SETUP.md`](Stock-Prediction-Models/alpha/V2_1_VALIDATION_SETUP.md) —
  the report and the statistical-adequacy note. **Read this one first.**
* [`alpha/V2_1_EXPERIMENT_LOG.md`](Stock-Prediction-Models/alpha/V2_1_EXPERIMENT_LOG.md) —
  every V2.1 run, starting with the one freeze.
* `alpha/examset.py`, `alpha/protocol.py`, `alpha/out/v2_1_exam_set.json`,
  `app/tests/test_alpha_v2_1.py`.

**72 frozen exam cutoffs** (was 12), 30 sessions apart, 316 development cutoffs,
nine gates with 12-1 momentum as the primary benchmark. No V2.1 model exists and
nothing has been scored on the new exam. Production is still weight 0, HOLD.

---

## The V2.1 research ladder — run 2026-08-08

* [`alpha/V2_1_LADDER_PREREGISTRATION.md`](Stock-Prediction-Models/alpha/V2_1_LADDER_PREREGISTRATION.md) —
  four arms, exact column lists, family size k=4, written before the first fit.
* [`alpha/V2_1_LADDER_REPORT.md`](Stock-Prediction-Models/alpha/V2_1_LADDER_REPORT.md) —
  the result. **Read this one.**
* `alpha/ladder.py`, `alpha/v2_1_exam.py`, `alpha/out/v2_1_development.json`,
  `app/tests/test_alpha_v2_1_ladder.py`.

**The pre-registered gate closed. The 72 exam cutoffs were never opened.**
V2.1-D (best arm, mean development IC +0.03426 over 255 cutoffs, Holm-significant
at k=4) beat 12-1 momentum by +0.01312 with a bootstrap CI of [−0.01862,
+0.05006]. The gate required that interval to exclude zero. Production weight 0,
HOLD, unchanged.

Three findings outrank the verdict:

1. **A learned univariate map destroys the factor it is given.** V2.1-A — a GBM
   on `ret_12_1` alone — scored +0.00053 where ranking by `ret_12_1` directly
   scores +0.02115. Its within-cutoff correlation with its own input averages
   −0.198 and is negative on 224 of 255 cutoffs: it fit a *decreasing* step
   function on the pooled level, then ranked with it. **Every V2 arm carried its
   factors through the same step.** This is a pipeline defect, not a market fact.
2. **Market context flips momentum but does not beat it.** A→B is the only
   ladder step whose CI excludes zero (+0.01792), but B ends at +0.01845 against
   momentum's +0.02115 — a recovery of what arm A destroyed, not an addition.
3. **A three-line hand-specified rule is within noise of the 35-feature model.**
   Regime-switched momentum (Benchmark 3, nothing fitted) scores +0.02836 with
   the only benchmark CI that excludes zero; D beats it by +0.0059, CI
   [−0.02451, +0.04076].

The edge is still a regime bet, in the same bucket V2's was (BEAR +0.066 vs
SIDEWAYS −0.002 for D) — and V2's inverted out of sample. Power, measured:
resolving an edge of D's size over momentum would need ~1,750 non-overlapping
weekly cutoffs, about 35 years. Ten years of history cannot settle it.

**Test status (verified 2026-08-08):** `pytest -q --runslow` — **544 passed**
(499 V2 + 28 V2.1 protocol + 17 V2.1 ladder).

```bash
./.venv/Scripts/python.exe -W ignore -m alpha.ladder          # ~2.5 min, development only
./.venv/Scripts/python.exe -W ignore -m alpha.v2_1_exam predict   # refuses: §5.2 gate is closed
```

---

## V2.2 — fix the carrier — run 2026-08-08

* [`alpha/V2_2_PREREGISTRATION.md`](Stock-Prediction-Models/alpha/V2_2_PREREGISTRATION.md) —
  three arms, k=3, λ = 0.50, the G1 eligibility floor and the four gates, all fixed
  before the first fit. §12 records its two pre-fit amendments.
* [`alpha/V2_2_LADDER_REPORT.md`](Stock-Prediction-Models/alpha/V2_2_LADDER_REPORT.md) —
  the result. **Read this one.**
* [`alpha/V2_2_EXPERIMENT_LOG.md`](Stock-Prediction-Models/alpha/V2_2_EXPERIMENT_LOG.md) —
  every V2.2 run, including the inert re-run and why it is logged.
* `alpha/carrier.py`, `alpha/ladder_v2_2.py`, `alpha/out/v2_2_development.json`,
  `app/tests/test_alpha_v2_2.py`.

**The gate closed. The 72 exam cutoffs were never opened.** V2.2 changed only the
carrier — the 35 columns, the learner and its hyperparameters, the walk-forward,
the purge, the embargo and the cutoff grid are V2.1-C's, unchanged. Production is
still weight 0, HOLD.

Five findings outrank the verdict:

1. **The 2×2 grid refuted its own premise.** All four cells of (raw level | rank
   input) × (winsorised level | rank target) land within 0.0023 of zero against a
   factor worth +0.02115. Neither the input fix nor the target fix recovers
   anything. A level target makes the learned map *decreasing* (ρ −0.198 against
   its own input); a rank target makes it *directionless* (ρ −0.044). V2.1's
   "it fit a decreasing map" was the special case.
2. **Why, measured.** `E[target_rank | z__ret_12_1]` spans **0.023** across the
   whole momentum range; a leaf mean at `min_samples_leaf = 100` has a standard
   error of **0.029**. The learner's noise floor is wider than the signal it is
   asked to resolve, so any carrier that routes the factor *through* the learner
   meets the same wall.
3. **Only carrying the factor *around* the learner preserves it.** The
   residual-target-plus-bounded-blend rung keeps **99.1%** of the factor
   (−0.00018, CI [−0.00050, +0.00012]); the two rungs that pass it through the
   model keep 2% and 34%. Putting a factor in the input is not enough — it has to
   be in the output combination.
4. **The 35-column feature set is worth +0.0024 of IC over plain momentum**, CI
   [+0.00069, +0.00434] — real, and about a ninth of momentum's own +0.0212. Read
   straight off arm B's λ curve, where λ = 0 *is* 12-1 momentum by construction.
5. **A bounded-tilt arm is ~19× better powered against its own benchmark.** B's
   paired half-width against momentum is 0.0018 where the unconstrained arms' is
   0.032–0.035, because B is 99.35% correlated with momentum inside every cutoff.
   It also trades a quarter as much (18% of each leg weekly against ~71%).

The two arms with the highest mean IC (+0.03241 and +0.02723) were both
**carrier-defective** under the pre-registered G1 floor and never entered
selection — correctly: neither beats 12-1 momentum with an interval excluding
zero, and both concentrate in `BEAR_TREND` (+0.063), the bucket V2's edge lived in
before it inverted out of sample. No arm in V2, V2.1 or V2.2 has beaten the
three-line hand-specified regime rule (+0.02836).

**Test status (verified 2026-08-08):** `pytest -q --runslow` — **587 passed**, none
skipped (544 as before + 43 V2.2).

```bash
./.venv/Scripts/python.exe -W ignore -m alpha.ladder_v2_2 --quiet   # ~4 min, development only
./.venv/Scripts/python.exe -W ignore -m alpha.v2_1_exam predict     # still refuses: §5.2 gate is closed
```

---

## V2.3 — the adjustment must not re-encode its base — run 2026-08-08

* [`alpha/V2_3_RESEARCH_DESIGN.md`](Stock-Prediction-Models/alpha/V2_3_RESEARCH_DESIGN.md) —
  the design pass over V2.2's frozen artefacts that produced the two arms. **Its §6
  claim about bounded arms being better powered is superseded by the result below.**
* [`alpha/V2_3_PREREGISTRATION.md`](Stock-Prediction-Models/alpha/V2_3_PREREGISTRATION.md) —
  two arms, k=2, λ = 0.50 carried over, every V2.2 threshold verbatim, two gates
  added (H1b collinearity ceiling, G6 cost), six abandonment criteria.
* [`alpha/V2_3_LADDER_REPORT.md`](Stock-Prediction-Models/alpha/V2_3_LADDER_REPORT.md) —
  the result. **Read this one.**
* [`alpha/V2_3_EXPERIMENT_LOG.md`](Stock-Prediction-Models/alpha/V2_3_EXPERIMENT_LOG.md) —
  every V2.3 run, including the aborted one and the one post-fit protocol change.
* `alpha/ladder_v2_3.py`, `alpha/carrier.py` (extended additively),
  `alpha/out/v2_3_development.json`, `app/tests/test_alpha_v2_3.py`.

**The gate closed. All five gates failed for both arms. Both arms were eligible —
H1a, H1b and H1c all passed — so the architecture failed on its hypotheses, not on
its carrier.** The 72 exam cutoffs were never opened. Production is still weight 0,
HOLD.

**Both pre-registered hypotheses are refuted, one of them backwards:**

1. **Deleting the base from the learner's inputs fixed the collinearity and made
   the result worse.** mean |ρ(u, base)| 0.9923 → **0.6981**; effective λ
   0.0619 → **0.3580**, a 5.8× increase in real authority. Mean IC
   +0.02356 → **+0.02063**; advantage over momentum +0.00241 (CI excluding zero)
   → **−0.00052** (CI [−0.00890, +0.00764]). The design pass's +0.00604 "orthogonal
   component" was a property of post-processing a collinear model and did not
   survive being learned.
2. **A bounded adjustment on top of the regime rule subtracts from it.** V2.3-B
   scored +0.02716 against its own base B3's +0.02836 — **−0.00120**, CI
   [−0.00939, +0.00653], at the best resolution the project has achieved against
   that rule (half-width 0.00796). Its +0.00602 over momentum is **entirely
   inherited from B3's hand-coded bear switch**, not learned.
3. **The bounded architecture's power advantage was the collinearity, not a free
   gain.** V2.2-B: half-width 0.00182 at effective λ 0.062. V2.3-A: 0.00827 at
   effective λ 0.358. 5.8× the authority costs 4.5× the resolution — resolution and
   authority are the same dial. [*corrected 2026-08-08 after the independent
   decision audit; originally read "4.5× the authority", contradicting item 1 above*]
4. **The 34 columns are worth +0.0005 to +0.0014 of IC** over a single momentum
   rank, measured against both bases by the one-feature rungs.
5. **No tilt pays for its own trading.** Net spread advantage over own base is
   +0.00028 and +0.00002, both intervals spanning zero, while turnover rises 36–56%
   over the base.

`BEAR_TREND` is again the only bucket where either arm improves on its base — the
fourth study running, on 27 cutoffs of which 17 are 2022.

**Abandonment criterion 6 of §9 is met in its exact pre-registered form** — the
collinearity was removed and no advantage appeared — **and criteria 4-with-5 are met
independently.** Either ground alone ends the architecture. Criterion 2's operative
clause is satisfied with a negative point estimate, but its precision premise
(≈0.004 half-width; 0.00796 achieved) was not, so it is **not** relied upon —
clarified 2026-08-08 after the independent decision audit. **Per §9, V2.3 stops and
reports the failure mechanism. No V2.4 is proposed.**

One protocol departure, disclosed: §4's noise control specified a single seeded
draw, which produced a non-significant apparent gain and stopped the first run. Over
30 draws the blend destroys IC (paired −0.00202 / −0.00278; 3% / 0% of draws above
base). The single draw is still reported verbatim; the stop condition moved to the
powered statistic. Logged as entry 3 of the V2.3 experiment log.

**Test status (verified 2026-08-08):** `pytest -q --runslow` — **625 passed**, none
skipped (587 as before + 38 V2.3).

```bash
./.venv/Scripts/python.exe -W ignore -m alpha.ladder_v2_3 --quiet   # ~5 min, development only
./.venv/Scripts/python.exe -W ignore -m alpha.v2_1_exam predict     # still refuses: §5.2 gate is closed
```
