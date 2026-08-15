# RR-1 made structural — the regime rule now lives in code

**Date:** 2026-08-15
**Status:** COMPLETE. Code changed, nothing measured, nothing promoted or demoted.
**Authorised by:** the programme owner, explicitly, at the decision point recorded
in `V5_ADAPTIVE_PREDICTION_ROADMAP.md` §3. The owner was offered this item, the
forecast ledger, both, or a hold, and chose **this item alone**. The forecast
ledger was **not** switched on.
**Implements:** `reports/V5_REGIME_RULE_RESOLUTION.md` §8, *"Available follow-up,
deliberately not done here."*
**Not a phase.** This spends no phase and no budget slot. It is the engineering
half of a rule that was already settled as RR-1.
**Commit:** `21c7eff`. Tree clean before the edits and after them.

---

## 1. What was missing

RR-1 settled the §2.5 / Phase-6-gate contradiction on 2026-08-15 and produced a
rule:

> **Regime conditioning may refine a result. It may never originate one.**

That rule was **prose**. Nothing in the repository could refuse a promotion
decided on regime-restricted evidence; the only thing standing between the
programme and the exact failure mode the registry records five times was a
document somebody would have to remember to read.

The repository already had the pattern for fixing that. `MIN_INDEPENDENT_CUTOFFS`
carries Phase 5(a)'s lesson — breadth is not resolution — into a gate that
actually fires, and `assert_production_is_declared` makes Phase 7's policy
structural rather than advisory. RR-1 §8 named the same treatment as available
and did not perform it, because the owner had scoped that session as a
documentation act.

Its one time-ordering note was the reason to do it now rather than later:

> it should be built *before* the domain becomes non-empty rather than after.

That is the same guarantee Phase 7 §6 claims for its thresholds, and it is
available for the same reason and only once: `PROMOTED` is empty, no forecast has
ever been frozen, and a rule written today cannot have been chosen to admit a
result because there is no result to admit.

---

## 2. What was built

Two gates and a constant, in `app/core/promotion.py`.

**`UNCONDITIONAL`** — the only evidence scope a status change may be decided on.
Both public evaluators take a keyword-only `evidence_scope`, defaulting to it.

**`G0 unconditional evidence`** in `evaluate_promotion`. Evaluated **before the
registry lookup and before any statistic is computed**. If the scope names a
regime, the function returns `BLOCK` carrying G0 alone, with `evidence` left
`None`.

**`D0 unconditional evidence`** in `evaluate_degradation`. Same check, returning
`INSUFFICIENT_EVIDENCE`.

### 2.1 Why the control flow, not just the verdict

The regime-conditional path never reaches `evidence_for`. This is RR-1's ordering
— *"survival is decided before the split is read"* — expressed as control flow
rather than as a comment, and it has a second, practical effect: a `BLOCK` that
still reported a cutoff-clustered advantage would be **publishing the
regime-conditional number it had just refused to act on**, and a reader would
quote it. PIT-1's 65.7% on n = 35 is precisely such a number, and it already sits
inside a record published under *"checked, no effect found."* `evidence is None`
is the point, not an omission. `test_the_regime_gate_is_reached_before_any_statistic_is_computed`
asserts it.

### 2.2 Why degradation too, which RR-1 §8 did not ask for

RR-1 §8 named promotion only. D0 is an extension beyond its literal wording, and
it is recorded as one rather than smuggled in.

The reason: a rule that binds promotion and leaves demotion open is a rule with a
door in it. A regime-restricted subset that cannot promote a model would still be
able to **demote its rival**, which is the same post-hoc rescue facing the other
way and reaches the same place — a production weight moved on evidence that
exists only inside a restriction. Binding one direction only would have created
that asymmetry rather than left it alone.

The asymmetry `evaluate_degradation` already had is preserved. A regime-scoped
demotion returns `INSUFFICIENT_EVIDENCE`, never `DEGRADED`, on the function's own
existing reasoning: refusing to read the evidence is not a finding of harm, the
same distinction Phase 6 drew between an admissibility block and a null result.

### 2.3 Absence is not a scope

`evidence_scope=None`, `""`, or a non-string raises `PromotionError`. Defaulting
an unstated scope to unconditional would be a silent bet of exactly the kind
CLAUDE.md §6.2 forbids for missing data. The honest call is still the short one —
`evaluate_promotion(model, frame, horizon)` is unconditional — so declaring a
regime is an extra, deliberate act, which is the asymmetry the gate wants.

### 2.4 `POLICY_VERSION` 1 → 2

No threshold moved. The version was bumped anyway because a new gate is a larger
policy change than a threshold is, and a later reader of a promotion record must
be able to tell whether RR-1 was in force when it was decided. `PROMOTED` was
empty under both versions, so nothing was decided under version 1 that this
reopens.

---

## 3. What this gate does not catch, stated plainly

**It catches the declared case.** A caller that restricts evidence to a regime
and says so is refused.

**It does not catch a caller that filters the frame and then declares
`UNCONDITIONAL`.** No column in `outcome_ledger.performance_frame` records the
regime a row was drawn under, so nothing in this module could detect that. Adding
one would change a Phase 2 surface and was not authorised here.

This limit is the same one `GRANDFATHERED` lives with, and it is tolerable for
the same reason: it does not make the honest path checkable *and* the dishonest
path invisible. It makes the dishonest path a **false statement in a reviewable
commit**, which is what this repository's other integrity surfaces rely on too.
Recorded here so a future session does not mistake G0 for a leak detector.

---

## 4. Effect on the programme today: none, and that is expected

The gate's domain is empty and stays empty until a model clears RR-1.1. No model
in `app/core/model_registry.py` does: 19 trainable agents are PIT-INADMISSIBLE,
six components REJECTED, three RETIRED, and `ensemble.ultimate` holds PRODUCTION
by history rather than by evidence. `PROMOTED` is still `{}`.

Nothing was promoted, demoted, retired or reopened. Phase 6 is still
**INADMISSIBLE AS WRITTEN, not entered** — Grounds 1 and 3 stand untouched.
Phases 10 and 11 are still entry-blocked. The one owner decision in roadmap §3 —
whether to switch the forecast ledger on — is **unchanged and unaddressed**; this
item was never a substitute for it.

---

## 5. Examined

Per the standing rule in `V5_ADAPTIVE_PREDICTION_ROADMAP.md` §0.

1. **Baseline suite:** **942 passed, 69 skipped — green**, run before any edit on
   a clean tree, matching the Phase 8 and RR-1 records exactly.
2. **Final suite:** **952 passed, 69 skipped. Delta +10 passed, 0 skipped** — the
   new RR-1 tests in `app/tests/test_promotion.py`: seven test functions, one of
   them parametrised four ways, for ten collected items. No test was removed,
   weakened or skipped, and no existing assertion was relaxed. One existing test,
   `test_the_policy_is_reportable_as_data`, was *extended* — it now also asserts
   the reported scope and policy version.
3. **Leak detector:** the phase **did not touch a prediction path** —
   `promotion.py` reads scored outcomes and returns verdicts; it produces no
   forecast. Run explicitly anyway:
   `app/tests/test_validation.py::test_future_cannot_change_the_verdict`
   **1 passed**.
4. **Methodology surfaces (§1.2):** **none touched.** No targets, features, model
   params, examset, ladder or `validation/pit.py`. `alpha/` was not modified at
   all. `app/core/promotion.py` is a Phase 7 surface, not a §1.2 surface, and it
   is modified here under explicit owner authorisation recorded in §Authorised-by
   above. No preregistration amendment is required, because no experiment's
   protocol changed — the gate constrains what a *future* result may license.
5. **Frozen records:** **read** — `reports/V5_REGIME_RULE_RESOLUTION.md` (§2,
   §2.1, §4, §8, §9), `reports/EXPERIMENT_REGISTRY.md` (§13),
   `V5_ADAPTIVE_PREDICTION_ROADMAP.md` (§0, §3, §3.1). **None was modified.**
   `reports/EXPERIMENT_REGISTRY.md` was **appended to** with a dated §14 under its
   own standing rule. No existing row was altered.
6. **Closed programmes:** **none reopened.** This changes what evidence may
   license a promotion in future; it re-derives nothing and re-tests nothing.
   RR-1 §5 already checked all five retroactive applications of §2.5 and found
   them unchanged; G0 is strictly no weaker than the rule it enforces, so that
   check does not need redoing. V2-E stays REJECT, V2 ABANDONED, V3 3/3 CLOSED,
   V4 slot 1 SPENT, PIT-1 CLOSED.
7. **Measurement:** **none.** No computation of any kind was run against market
   data. The only numbers produced were test counts. The performance frames in
   `test_promotion.py` are synthetic and built in-test, as its module docstring
   requires.
8. **Sealed exam accessed:** **no.**

**Ledger:** `app/forecast_ledger.sqlite3` **still does not exist.** Verified
before and after. Every guarantee resting on its absence — Phase 7 §6, Phase 9
§6, Phase 8's no-manufacture test, and now §1 of this document — is intact.
