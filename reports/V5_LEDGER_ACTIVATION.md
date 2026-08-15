# V5 forecast ledger — switched on

**Date:** 2026-08-15
**Authorised by:** programme owner, explicitly, after AB-1 was implemented,
tested and committed
**Status:** `THE RECORD HAS STARTED. 86 FORECASTS, 30 SYMBOLS, 0 OUTCOMES.`
**Scope:** deterministic incumbent only

The one decision the programme had been waiting on since Phase 9 is taken. This
document records what was switched on, what was deliberately left off, and the
two defects activation exposed before any evidence was accumulated.

---

## 1. What now happens, and when

`app/core/ledger_activation.py` is the boundary. `read_ultimate` in
`streamlit_app.py` — the memoised live-ticker path, and the only place the app
reads a live symbol — now calls `evaluate_and_freeze` instead of
`ultimate.evaluate`.

Freezing rides on the **cache miss**, not beside it. The engine therefore runs
once and the frozen record is of the verdict the user was actually shown, rather
than of a second evaluation nobody saw. Concretely:

| Event | Ledger |
|---|---|
| Live ticker read, bars unchanged since last freeze | nothing written (idempotent) |
| Live ticker read, a new bar has arrived | one record per available horizon |
| Re-render inside the 10-minute cache TTL | engine not re-run, nothing written |
| Bundled CSV or uploaded file | never frozen — `evaluate_offline` is unreachable from this module |
| Model/forecast toggle on | **not frozen**, and the UI says so |
| Ledger write fails | forecast still returned, error shown in red |

The unit of accumulation is the **input fingerprint**, not the clock.
`forecast_id` digests `generated_at`, so it could not serve as the idempotency
key — re-reading a symbol would mint a fresh identity every time and fill the
ledger with rows carrying no new information and no new date. One frozen
forecast per symbol, per horizon, per distinct set of consumed bars.

---

## 2. Scope: incumbent only, and why that is not merely caution

Only `PRODUCTION_INCUMBENT` records are written. Challenger freezing stays off
because Phase 7 §9 records versioned fitted artefacts as **NOT DONE**: a neural
challenger's weights are not persisted, so its record could never be reproduced
from the artefact that produced it. The deterministic incumbent has no fitted
state — its source hash *is* the model.

This bites in a place worth naming. A **model-assisted incumbent verdict** —
what the user gets with the forecast toggle on — blends a neural reading into
the ensemble. That verdict is not the deterministic incumbent, so it is not
frozen. Freezing a model-free verdict instead would be worse than freezing
nothing: the record would not be of the forecast the user was shown.

---

## 3. Two defects activation exposed, both before any evidence accumulated

Neither was in the plan. Both would have contaminated the record silently.

### 3.1 The test suite created the production ledger

Running `pytest --runslow` created `app/forecast_ledger.sqlite3` with **six
records** — AAPL, MSFT, NVDA — carrying `cutoff_at` **2023-08-11** under
`generated_at` **2026-08-15**. UI fixtures feed bundled CSV bars through a
patched live fetch, and the freeze path accepted them.

These were not merely synthetic. They were **backfilled**: forecasts on
three-year-old bars whose outcomes are long since observable, and once written
they are indistinguishable from honest rows. This is the single worst thing that
could enter this ledger, and it happened on the first full run.

The contaminated file was deleted before it was ever committed. Phase 8's
`test_opening_the_research_tab_does_not_start_a_record` is what caught it —
the guarantee-protecting test earned its keep on the day the guarantee was
being spent.

**The fix is structural, not test isolation.** `forecast_ledger.assert_prospective`
refuses any record whose last observed bar trails its generation by more than
`MAX_CUTOFF_LAG = 7 days`. A live feed's last bar is hours to a long weekend
old; a backfill is months to years. Seven days sits in the empty space between,
so the guard costs no honest freeze and catches the whole class. A test would
have protected the test suite; this protects the ledger from anything.

### 3.2 Constructing a ledger to discover you must not write to it

`ForecastLedger.__init__` creates its file — the trap Phase 8 documented. The
first activation draft opened a ledger, *then* checked what to write, so a
refusal still left the artefact behind.

`forecast_ledger.generate_incumbent_records` now separates running the engine
from writing. `evaluate_and_freeze` generates, checks prospectivity, and opens a
ledger only when there is something admissible to put in it. Asserted by
`test_a_stale_cutoff_is_refused_and_creates_no_ledger`, which requires the
destination not to exist after a refusal.

---

## 4. What was actually frozen

Run 2026-08-15 against the live feed, over the 30 symbols in the local cache —
the watchlist at freeze time, which is the point-in-time universe by
construction rather than by assumption.

| | |
|---|---|
| Records frozen | **86** |
| Symbols | **30** (`EURUSD_X` delisted, no horizon available) |
| Horizons | 4h, 1d, 1w — 3 each, except CBRS and SPCX at 4h only |
| Schema | v2 throughout, 8 basis probes on every record |
| `production_or_challenger` | `PRODUCTION_INCUMBENT` on all 86 |
| Cutoffs | 2026-08-14 → 2026-08-15 |
| Maximum cutoff lag | **1.56 days** — genuinely live |
| Outcomes | **0**, and the table does not yet exist |

Zero outcomes is correct and will stay correct for a while: no outcome can exist
for a forecast made now until its horizon elapses. **This is one independent
date.** Phase 9's arithmetic wants roughly 50.

---

## 5. What was deliberately not done

- **No backfill.** Not from `app/cache/`, not from bundled CSVs, not from
  PIT-1's 12 cutoffs. Every record was generated now against bars that end now.
- **No challenger, RL, or model-assisted freezing.** §2.
- **No outcome scoring run.** Nothing has matured; there is nothing to score.
- **No promotion or demotion.** `promotion.PROMOTED` is still `{}` and the
  Phase 7 gate still BLOCKs every model, correctly, on 1 independent cutoff
  against a floor of 20.
- **Phases 10 and 11 not entered.** Both need a record with resolution. One date
  is not resolution.

---

## 6. Risks a future session must not rediscover

**The ledger is gitignored** (`.gitignore:10`, a Phase 1 decision). The
accumulated evidence therefore exists on **one machine, with no backup and no
version history**. Every prospective date is unreproducible by construction —
that is exactly what makes them valuable, and it means losing the file loses
evidence that cannot be regenerated at any price. This is now the single most
fragile asset in the programme. Backing it up is not a research decision and
needs no preregistration.

**Accumulation depends on the app being used.** The ledger gains a row when a
live ticker is read and its bars have moved. A week nobody opens the app is a
week with no new dates. If steady accumulation matters, a scheduled headless
freeze is the obvious mechanism — but it is a change to how evidence is
generated, so it should be a declared decision rather than a convenience.

**`MAX_CUTOFF_LAG` will refuse a genuinely stale feed**, loudly, in red. That is
intended. If it ever fires on live data, the data is the problem.

---

## 7. Verification

- **Baseline:** 952 passed, 69 skipped — green, before any edit this session.
- **Final:** **990 passed, 69 skipped** — delta **+38** (20 AB-1, 18 activation).
- **Slow suite:** **1059 passed** before activation; `test_ui.py` **47 passed**
  after, with the ledger present.
- **Leak detector:** `test_future_cannot_change_the_verdict` — **1 passed**,
  run explicitly after activation.
- **Ledger integrity:** 86 records before the suite, 86 after. Tests do not
  write to it.
- **Two UI tests re-aimed, not weakened.** Both asserted the ledger's *absence*,
  a premise the owner deliberately spent.
  `test_opening_the_research_tab_does_not_start_a_record` becomes
  `..._does_not_write_to_the_record` and now asserts the stronger, surviving
  invariant — rendering must not change the record — plus the no-manufacture
  property on a path that does not exist.
  `..._says_why_it_is_empty` becomes `..._says_why_it_is_thin` and asks
  `research_view` which of its states applies rather than hard-coding the first
  one, so it keeps working as evidence accumulates.
- **Methodology surfaces (CLAUDE.md §1.2):** none touched.
- **Sealed exam:** not accessed.
- **Nothing measured.** No outcome, return, accuracy or promotion.
