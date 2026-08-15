# AB-1 — Adjustment-basis drift: a prospective-only hazard in outcome scoring

**Date:** 2026-08-15
**Status:** FINDING. Nothing measured, no code changed, no model moved.
**Verdict:** `THE LEDGER MUST NOT BE SWITCHED ON UNTIL THE CORPORATE-ACTION
POLICY IS DECLARED. THE POLICY COSTS NO DATA AND MUST BE DECLARED WHILE THE
LEDGER IS EMPTY.`

This document exists because the roadmap's §3 claim — *"there is now genuinely
nothing left that does not require the one decision"* — is **false**. One item
remains, it needs no data, and it is a precondition of the decision rather than
a consequence of it.

---

## 1. How this was found, and what started it

A session asked to "execute the next phase" correctly found none available and
put the ledger decision to the owner. In building the argument for that
decision, it advanced a claim that does not appear anywhere in the frozen
record:

> Going prospective repairs all three of PIT-1's residual look-aheads — not by
> fixing the harness, but by removing the need for it.

That claim contradicts a Phase 5 carry-forward note (*"a repaired harness is the
precondition for any future prospective study"*), so it was tested against the
code rather than the prose. **The forecast-side half of the claim survived. The
test also uncovered a hazard that runs the other way**, and the hazard is the
more important half of this document.

---

## 2. The forecast-side claim: upheld

`validation/pit.py:18-30` and `validation/REPORT.md:160-175` disclose three
residual look-aheads. All three are artefacts of **retrospection** — of asking
today's data what it looked like at a past cutoff. Each dissolves when the
cutoff is *now*:

| Disclosed look-ahead | Why it exists retrospectively | Prospectively |
|---|---|---|
| Adjusted prices | Post-cutoff splits/dividends baked into a pre-cutoff level | No post-cutoff action has occurred yet at freeze time |
| Universe selection | Symbols a user watches *today*, applied backwards | The watchlist at freeze time **is** the PIT universe |
| Intraday depth | An 18-month hourly window where production had 24 | Depth at freeze time **is** production depth |

The Phase 5 note is right that these cannot be repaired *inside* the harness.
It is wrong to conclude that repairing the harness is a precondition for
prospective work — the prospective path does not use the harness. This is a
disagreement with a frozen note, stated openly and left for the owner to weigh;
it is **not** a correction to `validation/REPORT.md` under CLAUDE.md §1.1 and
must not be appended there as one. PIT-1's disclosures remain exactly true of
PIT-1.

---

## 3. The hazard: adjustment-basis drift between freeze and maturity

Prospection removes three look-aheads and introduces one failure mode that
retrospection never had.

The live data path fetches back-adjusted bars:

- `app/core/live.py:236` — `auto_adjust=True` (yfinance 1.5.2)

`auto_adjust=True` **back-adjusts the entire history** whenever a split or
dividend occurs. So a bar's recorded close is not a fixed quantity; it is a
function of every corporate action that has happened *up to the moment of
download*.

Now trace one forecast through a prospective loop:

1. **At freeze (time `T`)** the ledger stores `price_at_cutoff` — the anchor
   close on the adjustment basis prevailing at `T`.
2. **Between `T` and maturity** the symbol goes ex-dividend, or splits.
3. **At maturity (`T+h`)** the scorer re-downloads. Every bar, *including the
   anchor bar*, now carries a different adjustment basis.

The frozen anchor and the freshly-downloaded anchor no longer agree.

### 3.1 What the code does about it

It fails closed, loudly. `app/core/outcome_ledger.py:353-358`:

```python
anchor_close = float(frame["close"].iloc[anchor])
if not math.isclose(anchor_close, record.price_at_cutoff, rel_tol=1e-9, abs_tol=1e-9):
    raise OutcomeIntegrityError(
        f"realised anchor price {anchor_close} does not match the frozen "
        f"{record.price_at_cutoff} for {record.forecast_id}"
    )
```

`rel_tol=1e-9` is orders of magnitude tighter than any dividend or split
effect. **Any corporate action inside the forecast window trips this guard.**

This is good design and the credit belongs to Phase 2. The guard is what stands
between the programme and silent corruption, because the line it protects,
`app/core/outcome_ledger.py:376`, computes the return on a **mixed basis**:

```python
realised_return = (price_at_maturity / record.price_at_cutoff - 1.0) * 100.0
```

The numerator is fresh, the denominator is frozen. Without the guard, a 2-for-1
split would book a −50% realised return on a flat position. The guard means
that number is never produced.

### 3.2 Why the guard is nonetheless a problem

**A refusal is not a neutral outcome.** `resolve_outcome` has a designed,
graceful "no outcome yet" path — it returns `None` when the horizon has not
elapsed. Adjustment drift does not take that path. It raises, and it raises on a
**systematically non-random subset of forecasts**: those on dividend-paying
symbols, and those at longer horizons.

That subset is not noise. Dividend yield is one of the most studied
cross-sectional return characteristics there is. A scored record that
systematically omits dividend payers is biased along a known factor, and nothing
in the current code counts, reports, or records the omission.

The bias is also **worst exactly where the programme needs dates most**. A 4-hour
or 1-day window rarely spans an ex-dividend date; 1-week, 1-month, 3-month and
6-month windows routinely do. Phase 9's arithmetic wants independent dates at
longer horizons — which is the regime where the drop-out rate is highest.

### 3.3 Why nobody caught it

The guard is tested — `app/tests/test_outcome_ledger.py:192`,
`test_realised_anchor_must_match_the_frozen_price`, which multiplies the anchor
close by 1.05 and asserts the refusal. The test is correct and passes.

But its framing is **tamper detection**: a 5% bump standing in for corrupted or
substituted data. A legitimate re-adjustment producing the same mismatch was
never contemplated, because under retrospective operation it cannot happen — the
cache is downloaded once and every read sees one basis. The scenario is
**created by prospection**, and prospection has never been switched on.

### 3.4 The one piece of good news

`resolve_outcome` is called from tests only. **No batch scorer exists yet.**

This matters, because the obvious way to write one is a loop with
`try/except OutcomeLedgerError: continue` — which converts a loud refusal into a
silent, factor-correlated hole. That code has not been written, so the defect can
be designed out rather than found later in an accumulated record.

---

## 4. Arguments against this finding, and why they do not dispose of it

Written adversarially against the finding, since no independent reviewer is
available for this programme.

**"This is just the adjusted-prices look-ahead already disclosed in PIT-1."**
No — it is the mirror image, with a different mechanism and a different remedy.
Retrospectively, adjustment produces a *silent bias in the level*.
Prospectively, it produces a *loud refusal to score*. One corrupts numbers, the
other deletes rows. The disclosure at `validation/REPORT.md:162` covers the
first and says nothing about the second.

**"Dividend effects are small — the report itself says so for this universe."**
The size of the effect is irrelevant here. `rel_tol=1e-9` does not care whether
the drift is 3% or 0.3%; it refuses either way. The magnitude would matter if
the failure were a biased number. The failure is a missing row.

**"Splits are rare and dividends are quarterly, so the drop-out is small."**
For a quarterly payer at a weekly horizon, roughly 4 windows per year per symbol
span an ex-dividend date — a low rate per symbol, but concentrated entirely on
dividend payers and entirely absent on non-payers. A small *overall* rate that
is 100% correlated with a return factor is precisely the dangerous shape. At 3-
and 6-month horizons, most windows on a quarterly payer contain an action.

**"The guard is doing its job; failing closed is correct."**
Agreed, and this finding does not propose weakening it. CLAUDE.md §2.3's
principle applies by analogy: the fix is never to relax the assertion. The fix
is to decide what a legitimate mismatch *means* and give it a designed path,
distinct from both "not matured" and "integrity violation."

**"This can be handled when the batch scorer is written."**
It could, but by then the ledger would be accumulating. The policy would be
chosen with partial results visible — exactly the property Phase 7 §6 went to
some trouble to avoid, and a guarantee available only once.

---

## 5. What this finding does not claim

- It does **not** claim the guard is wrong, or that any test should be relaxed.
- It does **not** claim a leak. Nothing here lets future information reach a
  forecast; the forecast side is untouched and §2 argues it is *improved*.
- It does **not** measure anything. No outcome, return, bar, or accuracy was
  read. No forecast was frozen. No model was promoted, demoted, or reopened.
- It does **not** claim the drop-out rate. That would require either a ledger or
  a dividend calendar, and the first does not exist while the second is
  unnecessary for the decision at hand.
- It does **not** reopen a closed programme. PIT-1 stays CLOSED and its
  disclosures stay true of it; this concerns a prospective path PIT-1 never ran.

---

## 6. The options, for the owner

Ordered by this document's preference. All are cheap, none needs data, and each
must be **committed before the ledger exists** to carry Phase 7 §6's guarantee.

**(a) Freeze the unadjusted anchor alongside the adjusted one.** Store the raw
close and the adjustment factor at freeze time, and reconcile at maturity by
re-deriving the basis rather than comparing levels. Strongest option: it makes
the scored return correct across corporate actions instead of merely refusing
when one occurs. Cost: a Phase 1 schema field, which is a methodology surface
and needs an amendment.

**(b) Give legitimate drift its own designed outcome path.** Keep the guard,
but distinguish "anchor mismatch consistent with a corporate action" from
"anchor mismatch consistent with tampering," and record the former as a declared,
counted, reportable non-outcome rather than an exception. Cheaper than (a).
Does not fix the return; it makes the hole visible and auditable instead of
silent. Requires the drop-out count to surface in the Phase 8 Research tab.

**(c) Declare the bias and proceed.** Record that dividend payers drop out of
the scored set, count them, and treat every accumulated statistic as conditional
on non-payment. Honest, cheapest, and materially weakens what the record can
ever support. Recorded here as admissible so that choosing it is a decision
rather than a default.

**(d) Fetch unadjusted bars for scoring.** Rejected on inspection, recorded so
it is not re-derived: `auto_adjust=False` changes the basis of the *whole*
pipeline, including every indicator and every frozen fingerprint, and would make
the prospective path inconsistent with all existing evidence. The cure is worse.

**Recommendation: (a), with (b) as the fallback if the Phase 1 amendment is
judged too invasive.** Both preserve the guard. Neither weakens a test.

---

## 7. Consequence for the one decision

The roadmap's standing recommendation — that switching the ledger on is the only
free, PIT-by-construction, compounding source of independent dates — **is
unchanged and is strengthened by §2**. This finding does not argue against
switching it on.

It argues about **order**. Switching the ledger on today begins accumulating a
record with an undeclared, factor-correlated hole in it, and the policy that
closes the hole would then be chosen with results in view. Declaring the policy
first costs days, needs no data, and is the difference between a record that can
support a positive result and one that cannot.

**The revised recommendation is therefore: settle AB-1, then switch the ledger
on.** The scope caveat from the same session stands independently — versioned
fitted artefacts remain NOT DONE (Phase 7 §9), so challenger forecasts are not
reproducible from the artefact that made them, and the incumbent is the safe
initial scope.

---

## 8. Status of this document

- **Nothing measured.** No outcome, return, bar, or accuracy read.
- **No code changed.** This session modified no `.py` file.
- **Ledger.** `app/forecast_ledger.sqlite3` verified absent before and after.
- **Suite.** 952 passed, 69 skipped, green, before and after — delta 0.
- **Frozen records read, none modified:** `validation/REPORT.md`,
  `validation/pit.py`, `reports/V5_PHASE7_RETRAINING_POLICY.md`.
  `reports/EXPERIMENT_REGISTRY.md` appended as §15 under its own rule.
- **Declared while the ledger was empty**, which is why it is worth writing now.
