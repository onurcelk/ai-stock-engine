# Phase 1 schema amendment — AB-1 basis probes

**Date:** 2026-08-15
**Amends:** `reports/V5_PHASE1_FORECAST_LEDGER.md` (Phase 1, COMPLETE, GO)
**Authorised by:** programme owner, 2026-08-15, selecting AB-1 Policy A
**Schema:** `forecast_ledger.SCHEMA_VERSION` 1 → 2;
`outcome_ledger.OUTCOME_SCHEMA_VERSION` 1 → 2
**Declared while `app/forecast_ledger.sqlite3` did not exist.**

---

## 1. What changed and why

`reports/V5_ADJUSTMENT_BASIS_FINDING.md` established that under **prospective**
operation the live feed's `auto_adjust=True` (`app/core/live.py:236`) makes a
frozen anchor price a moving target: a split or dividend after the freeze
back-adjusts the whole pre-action history, and the anchor bar stops reading what
it read. Phase 2's anchor guard then refused to score — correctly, but the
refusals fall on dividend payers and long horizons, which is a hole correlated
with a known return factor.

Policy A closes it by freezing enough information to tell a **legitimate uniform
rescaling** apart from **a single bar being tampered with**, which a single
stored price can never do.

### 1.1 Forecast ledger, v1 → v2

One new field, `ForecastRecord.basis_probes`: the trailing
`BASIS_PROBE_COUNT = 8` `(iso_date, close)` pairs of the exact consumed frame,
on the adjustment basis prevailing at freeze time. Read from the same frame
`fingerprint_frame` hashes, so they describe exactly the bars the forecast saw.

Eight rather than one is the entire point. A back-adjustment multiplies *every*
pre-action bar by one constant; corruption moves one bar. Uniformity across
several probes is the only observable that separates them.

### 1.2 Outcome ledger, v1 → v2

`reconcile_basis` runs before scoring:

1. Anchor matches the frozen price → `factor = 1.0`, `corporate_action = False`,
   and the arithmetic is **bit-for-bit what it was before AB-1**. This is the
   overwhelmingly common case and costs one comparison.
2. Anchor differs → each probe's ratio `observed / frozen` is computed, the
   factor is their **median**, and the maximum relative deviation from it —
   including the anchor's own — must not exceed `BASIS_UNIFORMITY_REL_TOL`.
   Uniform → a corporate action, reconciled, scored on the fresh basis.
3. Not uniform, or the record carries no probes → **`OutcomeIntegrityError`**,
   exactly as before.

The realised return is then computed as
`(price_at_maturity / scoring_anchor - 1) * 100`, with both prices on one basis.

Five new `OutcomeRecord` fields make the arithmetic auditable from the record
alone: `scoring_anchor_price`, `basis_factor`, `corporate_action`,
`basis_probe_count`, `basis_max_deviation`. `notes["basis_status"]` is
`UNCHANGED_BASIS` or `CORPORATE_ACTION_RECONCILED`, so reconciliations are
**countable** — AB-1's complaint about the old behaviour was precisely that
dropped observations left nothing to count.

---

## 2. Every hard constraint, and where it is met

| Constraint | How |
|---|---|
| Do not weaken the anchor guard | Equality path still `rel_tol=1e-9`. A mismatch it cannot explain still raises. |
| Do not widen its tolerance | `1e-9` unchanged. `BASIS_UNIFORMITY_REL_TOL` is a **separate** constant on a path that did not previously exist. |
| Keep `test_realised_anchor_must_match_the_frozen_price` | Kept, unmodified, passing. A single-bar 5% bump is non-uniform and still raises. |
| No global `auto_adjust=False` | Untouched. No fetch behaviour changed anywhere. |
| No silent skip | There is no `except OutcomeLedgerError` anywhere in the tree. Reconciliation **produces a correct outcome** instead of skipping; what it cannot explain still raises. |
| Explicit, testable, countable | 20 tests in `app/tests/test_ab1_adjustment_basis.py`; five fields plus `basis_status` on every outcome. |
| PIT guarantees intact | Probes are read from the already-cutoff-validated frame and are all at or before the cutoff, asserted by `test_probes_never_reach_beyond_the_cutoff`. Leak detector run explicitly: 1 passed. |
| Frozen records not rewritten | No `.md` record altered; appends only. No stored payload is mutated — the ledger's immutability triggers are untouched. |
| Backward compatibility | v1 records load, and `identity_payload` excludes v2-only fields for them, so no already-frozen id moves. Asserted by `test_v1_records_keep_their_original_identity`. |
| No silent field-meaning change | `price_at_cutoff` keeps its exact meaning. The new basis lives in new fields; `scoring_anchor_price` is what changed role, and it is new. |

---

## 3. The one judgement call

`BASIS_UNIFORMITY_REL_TOL = 1e-4`, and it is a genuine trade-off rather than a
derived constant.

A real back-adjustment is uniform in exact arithmetic, so the spread is purely
the provider's float rounding — unknown in advance because the ledger has never
run against live data. Too tight re-opens the hole AB-1 exists to close, as
rounding noise would refuse legitimate actions. Too loose lets a small tamper
pass as an action.

`1e-4` sits well below the whole-percentage-point corruption the guard is for
and well above plausible float noise. Two tests pin both sides. The constant is
documented in-source as **the one place to revisit if live data ever refuses**,
and revisiting it needs an amendment, because loosening trades tamper
sensitivity for coverage.

---

## 4. Known boundary, stated rather than discovered later

**The anchor guard is not a general history-integrity check.** If the anchor bar
still reads what it read at freeze, scoring proceeds regardless of what happened
to bars further back. That is pre-AB-1 behaviour which AB-1 did not change, and
it does not affect the return: the anchor and the maturity price are the only
two prices the arithmetic touches. The frozen `input_fingerprint` is what covers
the consumed frame. Pinned by
`test_guard_only_speaks_when_the_anchor_itself_moved` so it is never reported as
a bug or quietly "fixed".

---

## 5. Verification

- **Baseline:** 952 passed, 69 skipped — green, before any edit.
- **Final:** 972 passed, 69 skipped — **delta +20**, no test removed or relaxed.
- **Leak detector:** `test_future_cannot_change_the_verdict` — **1 passed**,
  run explicitly.
- **Methodology surfaces (CLAUDE.md §1.2):** **none touched.** No target,
  feature, model parameter, exam set, ladder or `validation/pit.py` change. The
  Phase 1 ledger schema is not on that list; this document is the amendment the
  owner's instruction required regardless.
- **Sealed exam:** not accessed.
- **Ledger:** `app/forecast_ledger.sqlite3` verified **absent** throughout AB-1
  implementation and at the AB-1 commit.
- **Nothing measured.** No model promoted, demoted, retired or reopened.
