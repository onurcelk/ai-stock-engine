# HR-1 — Historical point-in-time replay for the Ultimate incumbent

**Date:** 2026-08-16
**Registered as:** HR-1 (`reports/EXPERIMENT_REGISTRY.md` §20)
**Status:** BUILT AND RUN. **12,873 Ultimate forecasts replayed and scored.**
**Commit:** `a8aca87`
**Scope:** diagnostics only. **No promotion, no demotion, no production weight moved.**
**The incumbent was not modified.** `app/core/ultimate.py` is byte-identical and
its source hash is unchanged — see §5.

---

## 0. What was asked, and the one-line answer

Pick a historical cutoff, run Ultimate as if that date were today on data
truncated to that date, freeze the call, advance by the horizon, read the
realised outcome, score it. Repeat across many cutoffs and symbols to obtain
hundreds of observations without waiting months.

It is built, it ran, and the first result on the currently frozen incumbent is
in §7. **It does not beat its declared baseline at any of the three horizons.**

---

## 1. The problem this solves, and the one it deliberately does not

Phase 9 established that the programme's binding constraint is *independent
dates*, that no dataset supplies them, and that the only free compounding source
is the prospective ledger — which accumulates one cutoff per trading day and
needs 50. That finding is about **production validation** and it stands
unaltered.

It says nothing about **model development**. Deciding whether a change to the
engine helps is a different question from deciding whether the engine may hold
production weight, and it has always been answerable from history. The
programme had no instrument for it, so every question about the engine queued
behind a year of waiting.

The division of labour, stated once:

```
historical PIT replay  ->  fast evidence for model development
prospective ledger     ->  final independent production validation
```

A change that looks good in replay has earned a prospective test. It has not
earned production weight. **HR-1 must never be cited as though it had.**

---

## 2. Why these rows can never be promotion evidence

Unchanged from RR-2, and doing more of it changes nothing:

1. Prices are back-adjusted for corporate actions that post-date each cutoff
   (AB-1 §2). A prospective row escapes this because its cutoff *is* the
   present; a replay walks back into it.
2. The symbol universe is the one someone watches **today**, so it is
   survivorship-selected relative to 2017.
3. The intraday depth is whatever the feed still serves.
4. **Whoever runs the study already knows what the market did**, and can re-run
   it with a different universe, horizon, or window until it flatters.

(4) is the one no code can fix, and it is why the separation is a database file
rather than a column.

### 2.1 Four locks, carried over and extended

| Lock | Where |
|---|---|
| Study rows are `RETROSPECTIVE_REPLAY`; the prospective table's CHECK constraint rejects them | `forecast_ledger.py` schema |
| They live in a third file, `app/replay_study.sqlite3`, whose CHECK admits nothing else | `ReplayLedger` |
| `promotion.evidence_for` drops replays **before** measuring and reports how many | `promotion.py` |
| `research_view.n_independent_cutoffs` ignores them | `research_view.py` |

Verified after the real run: the gate counts **0 rows** and excludes **12,873**
at every horizon.

---

## 3. How historical cutoffs are generated

`replay_study.historical_cutoffs` walks backwards from the newest bar that still
has a full horizon ahead of it, stepping by `stride_bars`.

**Two constraints, both structural.** A cutoff must have a future to be scored
against — a cutoff within `bars_ahead` of the series end would freeze a forecast
that can never resolve, and an unscoreable row still looks like coverage on a
count. And it must have a past the engine will read: `min_history` is derived
from `ultimate.evaluate_frame`'s own admission test
(`max(min_bars, WARMUP + bars + MIN_SAMPLES × 2)`), read rather than reinvented.

**The default stride is the horizon length.** Consecutive windows then touch but
do not overlap, so every cutoff is an independent draw under
`promotion.independent_cutoffs` rather than being collapsed by it. A shorter
stride is permitted and yields more rows; those rows resolve against overlapping
price paths, so they are more *observations* and not more *draws*. Both numbers
are reported. A test asserts the default gives `independent == generated` and
that a stride of 5 gives strictly fewer draws than rows.

### 3.1 The majority calendar, and why it is not one symbol's bars

Symbols read on the same day are one draw, so the grid is a set of **dates**
applied to every symbol, not a per-symbol construction.

The dates come from the universe's **majority calendar** — those at least half
the symbols traded. Two simpler rules were implemented, tested against the real
30-symbol universe, and both picked the wrong calendar:

- *Deepest history* picks `BTC-USD`, which trades seven days a week. Its grid is
  spaced 25 **calendar** days, so consecutive equity windows — 25 *trading* days
  long — overlap, and the independence property is lost. Measured: 134 cutoffs
  generated, of which only a fraction survive as draws.
- *Most-shared calendar* picks whichever ticker listed most recently: a
  hundred-bar series is trivially contained in every longer one, so it scores
  perfect containment on almost no dates. Measured: grid of length 0–2.

A majority calendar has neither failure mode, needs no threshold, is read off
the bars (a bar exists exactly when the market traded, so it is never wrong
about a holiday or a half-day), and degenerates correctly — on an all-crypto
universe it is every day. Four tests cover these cases.

**Note on horizon semantics.** A horizon in this repository is *a number of bars
at a stated interval, not a calendar duration* (`outcome_ledger.maturity_spec`).
So `5w` is 25 daily bars: ~35 calendar days for an equity, 25 for a 24/7 asset.
This is pre-existing and consistent — the live ledger's `1w` already means 5
bars for both — and it is recorded here rather than silently inherited.

---

## 4. How point-in-time safety is guaranteed

Three independent mechanisms, none of which relies on the others.

1. **Truncation at the door.** The engine is handed a fetcher that slices to
   `dates <= cutoff`. It is `replay._truncating_fetcher`, the same function the
   RR-2 recovery path uses — deliberately not a second implementation.
2. **The fingerprint refuses.** `fingerprint_frame(frame, cutoff_at=...)` raises
   if a single bar past the cutoff survives into what is frozen. This checks the
   *stored record*, not the call that produced it.
3. **Ordering is enforced by the record.** `ForecastRecord.__post_init__` already
   refuses `last_bar > cutoff` or `cutoff > generated_at`.

### 4.1 The test that matters

`test_changing_the_future_cannot_change_a_historical_forecast` multiplies every
bar after the cutoff by 3.5 and re-freezes. The `forecast_id` — a digest over
the whole payload — is **identical**. This is the study's analogue of
`test_future_cannot_change_the_verdict`: it does not inspect the truncation, it
demonstrates that the answer does not depend on the future.

A second test spies on the outermost fetcher, the one `ultimate.evaluate`
actually calls, and asserts every frame handed over ends at or before its
cutoff. An earlier draft spied inside the memoising fetcher and passed
vacuously — the memo legitimately holds the full series. The layer matters, and
the test now sits at the right one.

---

## 5. The incumbent was not modified

This is the property the whole design turns on.

`ultimate.evaluate` already accepts `horizons=`, and a `Horizon` is an inert
description of which bars to read. So the five-week horizon is **defined in
`replay_study.py` and passed in**, never added to `ultimate.HORIZONS`.

Adding it to the engine would have changed `app/core/ultimate.py`, whose sha256
*is* the model identity every frozen forecast records. Every live forecast
frozen afterwards would have carried a different engine version than the 118
already accumulated, and `outcome_ledger.model_key` would have pooled them.

Verified on the real run: all 12,873 study rows and the live engine carry
`sha256:e629405d1b6b23c513853cd81336bfcd78a44d0c0e1a84b4604ac44d6fb8f97a`.
`MIN_T`, `MIN_CONFIDENCE` and `FAMILY_CAP` are untouched, as
`EXPERIMENT_REGISTRY.md` §3.5 requires.

`4h` is deliberately excluded from `STUDY_HORIZONS`: the feed serves ~2 years of
hourly bars, and PIT-1 measured the 4-hour after-close case **inverted** at
p = 0.009 — a finding to respect, not to re-open with a bigger sample.

---

## 6. HR-1.1 — two engine versions may never pool

Found while building this, and it is a defect in the existing code rather than a
consequence of the study.

`outcome_ledger.model_key` attributes a score to the registry **identity**,
which is stable across versions by design. Its own docstring says so and defers
the decision: *"Phase 4 must decide which it wants rather than inherit one."*
It was never decided, so the default was to pool — silently.

That is not a conservative default. `ensemble.ultimate` versions itself by the
sha256 of its own source, so editing one comment starts a second engine under
one identity, and a record spanning the edit reports a mixture as one number
with nothing in the output naming the problem.

**The fix.**

- `promotion.evidence_for` gains `model_version=`. Given a frame with more than
  one version and no name, it raises `PooledVersionsError`.
- Gate **`V0` one engine per measurement** in `evaluate_promotion` *and*
  `evaluate_degradation`. It refuses **before** any statistic is computed, the
  ordering G0 uses. It binds demotion for the reason D0 does: a rule that stops
  a mixture from promoting a model but lets one demote its rival has a door in
  it.
- `Evidence` carries `model_version` and `n_model_versions`.
- `replay_study.summarise_study` groups by `model_version`, so the reporting
  layer cannot pool either.
- `POLICY_VERSION` 2 → 3. No threshold moved. `PROMOTED` was still empty, so
  this was declared before it could admit or exclude any result — the same
  guarantee Phase 7's thresholds and RR-1's gate claim.

Unlike G0, V0 can be *satisfied* rather than only obeyed: naming a version
measures that version, which is what the study does.

---

## 7. The first evaluation of the frozen Ultimate incumbent

Engine `sha256:e629405d…6fb8f97a` — the version running in production today.
28 of 30 universe symbols (`CBRS` and `SPCX` listed too recently to clear the
history floor). Baseline is the one each forecast declared: zero-return for
error, always-bullish for direction.

| Horizon | Scored | Directional calls | Independent cutoffs | Accuracy | 95% CI | Baseline acc. | MAE advantage | Beats baseline |
|---|---|---|---|---|---|---|---|---|
| `1d` | 5,512 | 1,699 | 200 | **0.4797** | [0.4560, 0.5035] | 0.5023 | −0.0108 ± 0.0062 | **No** |
| `1w` | 5,246 | 777 | 200 | **0.5006** | [0.4656, 0.5357] | 0.5364 | −0.0206 ± 0.0132 | **No** |
| `5w` | 2,115 | 221 | 88 | **0.5068** | [0.4413, 0.5720] | 0.5705 | −0.0477 ± 0.0499 | **No** |

Date range 2017-11-09 → 2026-07-10. Total **12,873** scored forecasts.

### 7.1 What this says

**The incumbent does not beat its declared baseline at any horizon, and at `1d`
and `1w` the MAE interval sits entirely below zero.** At `1d` the directional
interval also sits below 50%. This is now a *resolved* statement rather than an
unresolvable one: at 200 independent cutoffs the intervals are narrow enough to
exclude the modest edge PIT-1's 12 cutoffs could not.

**The abstention is intact and is the engine's best feature.** HOLD share is
0.859 at `1d`, 0.889 at `1w`, 0.927 at `5w`. PIT-1 measured 74.3% and called the
abstention correct; this is the same behaviour at four times the resolution.

**Acting is worse than abstaining.** Accuracy on calls the engine actually acted
on — BUY/SELL/STRONG — is 0.4685 (`1d`), 0.4870 (`1w`), 0.4710 (`5w`): *below*
the all-calls figure at every horizon. The confidence veto is not selecting the
better calls.

**The always-bullish baseline beats it on direction at every horizon**, by 2.3,
3.6 and 6.4 points. Consistent with PIT-1, where 0 of 9 components beat
always-predicting-up.

### 7.2 What this does **not** say

- **It is not a demotion.** `ensemble.ultimate` holds PRODUCTION under
  `GRANDFATHERED`; whether it keeps production weight is a Phase 11 decision.
  D1 requires 50 independent cutoffs **of prospective evidence**, and the study
  supplies none.
- **It is not a finding about the market.** It is a finding about this engine on
  a back-adjusted, survivorship-selected reconstruction.
- **It licenses no change to the engine.** Tuning a threshold against these
  numbers would be fitting to a retrospective sample — the specific act
  `EXPERIMENT_REGISTRY.md` §3.5 forbids for `MIN_T`, `MIN_CONFIDENCE` and
  `FAMILY_CAP`.

What it *is*: the first quantitative statement about the incumbent at usable
resolution, and a working instrument for the next one.

---

## 8. What was added

| Path | What |
|---|---|
| `app/core/replay_study.py` | New. Horizons, cutoff generation, majority calendar, sweep, scoring, summaries, CLI |
| `app/tests/test_replay_study.py` | New. 38 tests, organised by the six required properties |
| `app/core/outcome_ledger.py` | `maturity_spec` reads a replay's frozen bar mapping |
| `app/core/promotion.py` | `PooledVersionsError`, `versions_present`, `V0`, `Evidence.model_version`, `POLICY_VERSION` 3 |
| `app/core/research_view.py` | `StudyState`, `load_study`, study panels, `study_vs_live` |
| `app/streamlit_app.py` | Research tab section — see §9 |
| `.gitignore` | `app/replay_study.sqlite3`, `app/study_logs/` |

Storage is a **third** database file. The prospective ledger and the RR-2 replay
ledger are unchanged and untouched; a study row cannot enter either, by CHECK
constraint.

Run it with `python -m core.replay_study --horizon 5w --cutoffs 200`, or
`--score-only` to score what is already frozen.

---

## 9. Where the results appear

Pro → **Research** tab → *"Research — historical PIT replay"*, between the
forecast history and the prediction explanation.

Four metrics (replayed & scored, independent cutoffs, symbols, engine versions),
then: accuracy by engine version and horizon; the BUY/HOLD/SELL breakdown; the
engine-versions panel; and the study-against-live comparison, whose last column
is `Counts toward promotion` — False for the study, True for the ledger.

A standing warning sits above every number, and it is **not** a sample-size
caveat: what disqualifies these rows is retrospection, not resolution, so the
warning says that instead of quoting `n`. HOLD carries no accuracy, by design —
counting an abstention as a wrong answer would misread the one behaviour this
engine was built to have.

`load_study` checks the file exists before constructing anything, so opening the
tab starts no record. A test asserts it.

---

## 10. Tests

38 new, organised by the six required properties. Suite **1065 → 1103**
(69 skipped, unchanged); slow suite **1171 passed**; leak detector run
explicitly, **1 passed**.

1. **No future data.** Future bars rewritten ×3.5 leave the `forecast_id`
   identical; the outermost fetcher never yields a bar past the cutoff; every
   stored record's last bar equals its declared cutoff.
2. **Frozen before scored.** The store is empty before the scoring pass; payloads
   are unchanged after it; `UPDATE` raises; a second sweep writes nothing.
3. **Correct horizon.** Parametrised over `1d`/`1w`/`5w`: the maturity bar is
   exactly `bars_ahead` positions after the anchor *in the original frame*, and
   the realised return equals the two closes' ratio to 1e-9. `5w` lands 33–39
   calendar days out.
4. **Cannot be confused.** The prospective table rejects a study row; study
   provenance is present and identity-covered; a genuine RR-2 recovery is
   accepted by `assert_replay` and **refused** by `assert_study`; the promotion
   gate counts zero.
5. **Versions cannot pool.** A two-version frame raises; naming a version
   partitions it exactly; promotion BLOCKs and degradation returns
   INSUFFICIENT_EVIDENCE, both with `evidence is None`; a one-version frame is
   unaffected.
6. **Live ledger unchanged.** No prospective ledger is created; the three
   default paths differ; live freezing keeps its class, guards and idempotency;
   study and live rows carry the **same** engine version; `5w` is absent from
   `ultimate.HORIZONS` and from the registry.

---

## 11. Traps for a future session

1. **Do not add `5w` to `ultimate.HORIZONS`.** It would change the engine's
   source hash and split the live record. The horizon is passed in for exactly
   this reason (§5).
2. **Do not tune the engine against §7.** It is a retrospective sample. §7.2.
3. **Do not merge the three ledgers** into one file with a status column. The
   separate CHECK constraints are the guarantee, not the labels.
4. **Do not weaken `V0`** on the view that pooling is the conservative default.
   §6 states why it is not.
5. **The study is regenerable; the prospective ledger is not.** Deleting
   `app/replay_study.sqlite3` costs an afternoon. The rule about
   `app/forecast_ledger.sqlite3` is unchanged and absolute.
6. **A study row's `generated_at` is the reconstruction time**, so
   `assert_prospective` would refuse it. That is correct.
7. **Windows holds a SQLite file lock** — `ForecastLedger._connect` never closes.
   Tests that unlink a study ledger need `gc.collect()` first.
