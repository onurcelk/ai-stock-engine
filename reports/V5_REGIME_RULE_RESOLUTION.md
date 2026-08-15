# RR-1 — Resolution of the §2.5 / Phase-6-gate contradiction

**Status: RESOLVED, 2026-08-15. Documentation act. No data touched, no
measurement, no model promoted or demoted.**

**Verdict: `§2.5 TAKES PRECEDENCE. THE PHASE 6 GATE AS WRITTEN IS VOID.`**

**Commit: `cbeaa1e`** — this document, the registry append and the roadmap
update together. Like Phases 6 and 9 this chain carries a single hash, and for
the same reason: it gates no study and computes nothing, so there is no
measurement for an earlier commit to precede (CLAUDE.md §5.2). What *is*
temporally load-bearing here is §4's claim that the replacement gate was written
while its domain was empty — `git log` shows this commit precedes any forecast
ledger, exactly as `e1d2947` precedes any scored outcome. Hash recorded in the
follow-up commit, per the convention used at `2105d4f`, `41a0273`, `23aaed8`,
`73903c0`, `19c620d`.

This document settles a conflict between two live programme rules. It was
requested by the programme owner on 2026-08-15 as option (c) of
`reports/V5_PHASE6_REGIME_EVAL.md` §6, which recorded the conflict and
deliberately declined to decide it. It changes no closed decision — §5 below
checks that claim case by case rather than asserting it.

---

## 1. The two rules, quoted

**Rule A — §2.5, "no regime collapse."** Its substance is criterion 6 of the
seven fixed in advance by `alpha/PREREGISTRATION.md` §8:

> | 6 | No regime collapse | mean IC > 0 in each of BULL / BEAR / SIDEWAYS and in HIGH_VOL and LOW_VOL |

`reports/EXPERIMENT_REGISTRY.md` has since applied it as a **disqualifier** four
times, and the sharpest statement of it is §827:

> Regime-concentrated results are a disqualifier under roadmap §2.5 and **may
> not be restricted to in order to survive.**

**Rule B — the Phase 6 STOP/GO gate** of `V5_ADAPTIVE_PREDICTION_ROADMAP.md`:

> Only validated regime effects may influence ensemble weights or model
> selection.

**The conflict.** A finding that skill is concentrated in one regime is, under
Rule A, grounds to disqualify the model; under Rule B, grounds to condition
ensemble weights on the regime. The same evidence licenses action under one rule
and forbids it under the other, so a Phase 6 run without a resolution could read
whichever rule its result happened to satisfy. That is precisely the latitude a
preregistration exists to remove.

---

## 2. The resolution

The two rules are genuinely contradictory **as positioned**, and they are not
reconciled by claiming they were always about different things. They are
reconciled by imposing an order on them, and by voiding the half of Rule B that
cannot survive that order.

**The mechanical separation.** Rule A is a gate on a *single model's
eligibility*. Rule B, in its surviving form, is a rule about *allocation among
models that have already passed Rule A*.

- **Rule A is evaluated first, on every candidate, unconditionally.** A model
  whose primary metric is not positive in **every** declared regime is
  disqualified. There is no appeal to Rule B, because Rule B has not been
  reached.
- **Rule B operates only on the survivors.** Among models that are already
  positive in every regime, relative weight may depend on regime — because
  every model being weighted works everywhere, and the weighting is choosing
  *how much* of each, never *whether* there is an effect at all.

The consequence that closes the conflict, stated as a rule in its own right:

> **Regime conditioning may refine a result. It may never originate one.**

A regime-conditional finding can never be a primary finding. If the
unconditional claim fails, the study is over, and the regime split is not
consulted. This is the mechanical form of §827's *"may not be restricted to in
order to survive"* — under it, restricting to a regime is unreachable, because
survival is decided before the split is read.

### 2.1 The five conditions, numbered for citation

Any future regime conditioning must satisfy **all** of these. Failing one ends
it; there is no aggregate or on-balance judgement.

**RR-1.1 — Unconditional bar first.** The model clears its primary metric
unconditionally, with its interval excluding zero, *before* any regime split is
computed. The unconditional result is the finding; the regime split is a
property of it.

**RR-1.2 — Positive in every declared regime.** Criterion 6 in its original
sense. Not "positive on average across regimes", not "positive in most" — in
each. A model positive in three regimes and negative in one has collapsed and is
disqualified, however large the three.

**RR-1.3 — Regime construction frozen before any outcome is read.** The regime
definition, its parameters, and its boundaries are committed as code before the
split is run, on the `f53aa96 → 660ce25 → ade0305` pattern that ABS-1
established. A boundary chosen after seeing performance is boundary-mining and
voids the study.

**RR-1.4 — Power declared per arm, not for the study.** A regime split
partitions cutoffs, not rows, so the contrast is between-cluster and each arm
carries its own effective *n*. The ≥ 50 independent-cutoff criterion
(`alpha/PREREGISTRATION.md` §8 criterion 7) binds the **unconditional** stage;
each regime arm needs its own count sufficient for its own declared MDE,
computed in a gate committed before the split is run. Independent cutoffs are
counted the way `app/core/promotion.py` counts them — overlapping forecast
windows collapsed first — not as raw rows.

**RR-1.5 — Multiplicity across regimes.** The number of regimes is declared in
advance and the significance criterion accounts for them, under the registry's
standing rule that arm counts are fixed before the first fit. Testing five
regimes at nominal 5% is a ~23% family-wise error rate and is not a result.

---

## 3. Why precedence goes this way

**The programme's purpose decides it.** Regime conditioning is the canonical
post-hoc rescue in quantitative finance: when an unconditional result fails,
segmenting until a favourable sub-period appears is always available, and it is
always tempting. A programme built to resist post-hoc rescue cannot hold a rule
that licenses the most common form of it. If Rule B had precedence, every model
this programme has ever rejected would have had a route back.

**The record shows the failure mode is real, not hypothetical.** In all four
registry applications the unconditional result was null or negative and the
regime-restricted subset was the only positive one — and in every case the
positive regime was BEAR or BEAR_TREND. The same shape appears a fifth time at
registry §171 (V2.1 arms, edge concentrated in `BEAR_TREND` at +0.0756 and
+0.0658). Five occurrences, one direction. A rule that fires five times the same
way is describing a property of the procedure, not a coincidence.

**The statistics agree independently of the philosophy.** A regime split
multiplies the number of estimated quantities while dividing the sample that
estimates them. On the V5 record the unconditional two-group contrast already
measures an MDE of **29.15 pp** against a 7.5 pp threshold of interest
(`reports/V5_PHASE5A_ABSTENTION.md`); each regime arm gets a fraction of that.
PIT-1's own regime splits are the illustration — SPY-direction 50.0 (n = 26) /
**65.7 (n = 35)** / 49.3 (n = 73). The 65.7 is exactly the number this rule
exists to refuse, and it sits inside a record already published under *"checked,
no effect found."*

**This holds at any sample size, and that matters.** RR-1.1 and RR-1.2 are not
power provisions that lapse once enough cutoffs accumulate. RR-1.4 is the power
provision. The precedence in RR-1.1 is a statement about what kind of claim the
programme is willing to make, and it binds on a 12-cutoff record and a
1,200-cutoff record identically.

---

## 4. What happens to Phase 6

**The gate as written is void.** *"Only validated regime effects may influence
ensemble weights or model selection"* is struck as a licence. It cannot be
repaired by defining "validated", because the wording's defect is not vagueness
— it is that it grants regime evidence standing to *originate* a promotion
decision, which §2.5 forbids.

**The phase is not struck, and the question is not closed.** Phase 6 keeps its
recorded status: **INADMISSIBLE AS WRITTEN — not entered**, with the question
open on a record that could resolve it. Its replacement gate is:

> **Phase 6 STOP/GO (RR-1).** Regime conditioning may influence ensemble weights
> only for models that have already cleared their unconditional bar (RR-1.1) and
> are positive in every declared regime (RR-1.2), on a frozen construction
> (RR-1.3), with per-arm power declared in advance (RR-1.4) and multiplicity
> accounted for (RR-1.5). A regime-conditional effect may never be a primary
> finding.

**The domain of that gate is empty today, and saying so is the point.** No model
in `app/core/model_registry.py` clears RR-1.1: the 19 trainable agents are
PIT-INADMISSIBLE, six components are REJECTED, three RETIRED, and
`ensemble.ultimate` holds PRODUCTION by history rather than by evidence
(`promotion.GRANDFATHERED`, reason `_INCUMBENT_DEBT`). A gate with an empty
domain is not a dead letter — it is a gate that will still be there when the
domain is not empty, written before anyone knew what the first candidate would
look like. That is the same guarantee Phase 7 §6 claims for its thresholds, and
it is available for the same reason: nothing has been measured yet.

**Two of the three Phase 6 grounds are untouched.** Ground 1 (the question was
already asked on PIT-1, which is CLOSED) and Ground 3 (12 dates are not 12
independent regime draws) stand exactly as recorded. This document resolves
Ground 2 only. Phase 6 remains blocked on the other two, and RR-1.4 now makes
Ground 3 a standing requirement rather than a one-time observation.

---

## 5. Retroactivity check — required, and performed case by case

A resolution that retroactively changed a closed decision would be inadmissible
under CLAUDE.md §1.1. Each application of §2.5 in the frozen record is checked
below against RR-1, individually.

| Where | What was decided | Under RR-1 | Changed? |
|---|---|---|---|
| Registry §347 | The V3 results-table template row: *"Stability \| halves, yearly, regime — concentration disqualifies (§2.5)"* | A template, not a decision. RR-1.2 is the same requirement stated the same way | **No** |
| Registry §429 (V3-1, SUE 5D) | **REJECT**, all four CONTINUE criteria failed; regime concentration +0.11317 BEAR vs +0.00075 BULL cited among the stability failures | Unconditional result +0.00090, CI [−0.00140, +0.00317] spans zero → fails RR-1.1 → the split is never reached. Still REJECT, and now for a reason that precedes the regime evidence rather than resting on it | **No** |
| Registry §643 (V4-1, SUE 20D) | **REJECT**, all four fail; *"the only positive regime is the one §2.5 disqualifies"* | Unconditional −0.00106, CI [−0.00610, +0.00464] → fails RR-1.1. Still REJECT | **No** |
| Registry §827 (S4 regime bucket) | **No promotion.** S4's entire separation from S3 comes from BULL_TREND/LOW_VOL, where the walk-forward fit inverts B3's ranking | The textbook RR-1.1 case: the bucket exists only inside the restriction. Still refused | **No** |
| Registry §171 (V2.1 arms) | **REJECT** on power; edge concentrated in `BEAR_TREND`, *"recorded then as a caveat. Under roadmap §2.5 it is now a disqualifier"* | Rejected on power at half-widths ~0.034 against effects ~0.013, independent of the regime finding. Still REJECT | **No** |

**Five applications, five unchanged decisions.** RR-1 is strictly no weaker than
the rule it clarifies: in each case the model now fails *earlier* in the
sequence, never later. There is no configuration of evidence in the frozen
record that RR-1 admits and §2.5 refused.

---

## 6. What this document does not do

- **It does not measure anything.** No outcome, no return, no bar, no accuracy,
  no regime constructed, no split computed. Every number quoted here is copied
  from a committed report.
- **It does not correct any frozen record.** `alpha/PREREGISTRATION.md` was read
  and not modified; it belongs to a closed programme. The registry is appended
  to, per its own rule, with the original wording of all five applications
  intact.
- **It does not reopen V2-E.** Regime/VIX/breadth as a cross-sectional feature
  family is REJECT and stays REJECT. RR-1 makes that closure firmer, not
  negotiable.
- **It does not unblock Phase 6.** Grounds 1 and 3 are untouched, and the new
  gate's domain is empty.
- **It does not conclude that skill is regime-independent.** PIT-1's null is a
  statement about a 12-cutoff instrument as much as about the engine.

---

## 7. A dissent, recorded

An independent review was obtained before this disposition was fixed, under
CLAUDE.md §7.2, with the reviewer given the two rules, the record and the power
figures but **not** this document's conclusion. It agreed on every substantive
point — that the rules are genuinely contradictory as positioned, that §2.5 must
take absolute precedence, that a regime-conditional effect may never stand as a
primary finding, and that the retroactivity check comes out clean — and reached
the two-gate separation in §2 independently.

**It disagreed on one thing: it argued Phase 6 should be struck permanently**
rather than narrowed, on the grounds that any surviving form leaves a backdoor
for post-hoc rescue, and that the programme has already rejected a regime feature
family and abandoned the architecture it belonged to.

That dissent is not adopted, for two stated reasons. First,
`reports/V5_PHASE6_REGIME_EVAL.md` §5 is a committed finding that *"does not
conclude that Phase 6 is wrong to exist — the question is well-posed and would
matter on a record that could resolve it"*; striking the phase here would have
this document silently override that audit. Second, the backdoor concern is
answered mechanically rather than by deletion: under RR-1.1 regime conditioning
cannot originate a result, so there is no rescue for it to perform. Deleting the
phase would also remove the written rule, leaving a future reader with a record
that had reached 50 cutoffs and no committed guidance — which is the worse
failure mode of the two.

The dissent is recorded because it may prove right. If a future session finds
itself arguing that RR-1's conditions are too strict, that argument should be
read against this paragraph.

---

## 8. Available follow-up, deliberately not done here

**RR-1 is prose, and it could be structural.** `app/core/promotion.py` already
makes Phase 7's policy enforceable — every PRODUCTION model must be declared or
the suite fails — and the same treatment is available here: a gate clause
rejecting any promotion whose supporting evidence is regime-conditional, plus a
test asserting it. That would carry RR-1 into enforcement the way
`MIN_INDEPENDENT_CUTOFFS` carries Phase 5(a)'s lesson.

It is not done in this document because the owner scoped this as a documentation
act, and because it changes code on a research-integrity surface. It is recorded
as available rather than performed. Note that it has no urgency while the gate's
domain is empty, and that it should be built *before* the domain becomes
non-empty rather than after.

---

## 9. Examined

Per the standing rule in `V5_ADAPTIVE_PREDICTION_ROADMAP.md` §0.

1. **Baseline suite:** **942 passed, 69 skipped — green**, run before any edit on
   a clean tree, matching the Phase 8 record exactly.
2. **Final suite:** **942 passed, 69 skipped. Delta 0.** This document changes no
   code. The files written are `reports/V5_REGIME_RULE_RESOLUTION.md` (new), an
   append to `reports/EXPERIMENT_REGISTRY.md`, and the roadmap update.
3. **Leak detector:** **no prediction path touched** — nothing executable was
   added or modified. Run anyway —
   `app/tests/test_validation.py::test_future_cannot_change_the_verdict`
   **1 passed**.
4. **Methodology surfaces (§1.2):** **none touched.** No targets, features, model
   params, examset, ladder or `validation/pit.py`. `alpha/` was not modified at
   all — `alpha/PREREGISTRATION.md` was read only. No amendment required or made.
5. **Frozen records:** **read** — `alpha/PREREGISTRATION.md` (§8),
   `reports/EXPERIMENT_REGISTRY.md` (§171, §347, §429, §643, §827),
   `reports/V5_PHASE6_REGIME_EVAL.md`, `reports/V5_PHASE5A_ABSTENTION.md`,
   `ROADMAP.md`. **None was modified.** `reports/EXPERIMENT_REGISTRY.md` was
   **appended to** with a new dated §13 recording this resolution, under its own
   standing rule that corrections are appended and keep the original wording
   visible. No existing row was altered and no §2 index row was rewritten.
6. **Closed programmes:** **this document's whole subject is a rule applied to
   closed work**, which is why §5 checks every application individually. Nothing
   was reopened, re-scored or re-tested. V2-E stays REJECT, V2 stays ABANDONED,
   V3 stays 3/3 CLOSED, V4 slot 1 stays SPENT, PIT-1 stays CLOSED. RR-1 is
   strictly no weaker than the rule it clarifies.
7. **Measurement:** **none.** No computation of any kind was run against data.
   Every figure is quoted from a committed report.
8. **Sealed exam accessed:** **no.**
