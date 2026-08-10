# V4 Programme — execution progress and closure

Tracks execution of `alpha/V4_CHARTER.md` (2026-08-09), the constituting instrument of
the V4 programme. The analogue of `reports/PROGRESS_V3.md`, and versioned from the first
day for the same reason: an untracked record makes every claim about it unfalsifiable.

**Programme opened 2026-08-09 (charter). Closed 2026-08-10.** Everything below has been
run and committed locally. **Nothing has been pushed** — `origin` is a third party's
public repository (§27A).

---

## The one thing that matters if you read nothing else

**V4-SUE was REJECTED. Slot 1 of 2 is SPENT. Slot 2 is BARRED and UNSPENT under charter
§8.3. V4 is CLOSED.**

**The horizon hypothesis was disconfirmed, not left untested.** V3 closed with the horizon
listed as *"a live, UNRESOLVED possibility"* — every family had been tested at 5 sessions
against sources that are quarterly-to-event and 45–135 days stale, and §2.9/§21 barred
re-testing them, so V3 **could not distinguish "no information" from "wrong horizon."**
V4 existed to settle that one question, and it settled it.

| | 5 sessions (V3-1) | 20 sessions (V4-1) |
|---|---|---|
| λ | 0.25 | **0.50** |
| Standalone SUE IC | **+0.01305**, CI [+0.00263, +0.02339] — **cleared zero** | **+0.00426**, CI [−0.01000, +0.01971] — **does not clear zero** |
| √(H/5) extrapolation P | — | **+0.0261** |
| Arm 1 − B3 | +0.00090, hw 0.00229 | **−0.00106**, hw **0.00537** |
| MDE | +0.007 | **+0.0095** native 20D |
| Decision | REJECT | **REJECT** |

**Standalone SUE at 20 sessions came in at +0.00426 against a pre-registered √H
extrapolation of P = +0.0261** — roughly a sixth of the value implied if the longer horizon
bought *nothing at all* informationally. The pre-registered threshold `P − h0 = +0.01124`
was not reached, and the shortfall against P (0.02184) **exceeds the diagnostic's own
half-width of 0.01486**, so this is a resolved failure, not an ambiguous one.

**H1 asserted superlinear decay — that a slower target would unlock information absent at
5D. The measurement points the other way: the longer horizon did not unlock information,
it appears to have diluted it.** Arm 1 at 20D scores **+0.00740 against B3's +0.00846** —
adding SUE made the incumbent worse.

---

## What failed, and what did not

**Not the power.** Achieved half-width **0.005372** against a frozen MDE of **+0.0095** —
a **1.77× margin**, corroborated by three independent dependence corrections (block
bootstrap 0.005372, Newey–West 0.005308, closed-form 0.005796). This is the best-resolved
study the programme has run against its own MDE.

**Not the point-in-time quality.** The acceptance-time door (`alpha/filings.py`) is
unchanged and tested; 51.8% of 10-K/10-Q filings are accepted after the 16:00 ET close of
the date they are stamped with, and the leaking `filed <= cutoff` rule was never used.

**Not the coverage.** SUE coverage **0.9299** against a 0.80 gate.

**Not the book tails.** **313 of 313 cutoffs (100%)** could form both tails. Family 2's
defect — 86% of names tied at zero, no name reaching the bottom quintile at any cutoff —
was turned into a pre-registered gate for V4, and the gate passed.

**Not the target.** The same instrument resolves B3 at +0.00846 and B2 at +0.01089 on the
20-session horizon. It measures signal when signal is present.

**Not the procedure.** Noise control **PASS**: 30 paired within-cutoff permutations,
median −0.00130, sd 0.00137, **0 of 30** draws reaching the MDE.

**Economics failed, but downstream.** Net spread advantage **−0.000965** — the eighth
consecutive tilt this programme has measured that does not pay for its own trading. It
failed to pay because it was ≈ 0, not because costs consumed a real effect. The adverse
prior was recorded in charter §4.3 **before** measurement and was confirmed.

**The information failed, and the formulation-rescue hypothesis failed with it.** The
charter §12 diagnosis is recorded in full at `reports/EXPERIMENT_REGISTRY.md` §8.4.

---

## What this does not establish

**It does not establish that filing data contains no information.** V3-1's standalone SUE
at 5D — IC +0.01305, CI [+0.00263, +0.02339], hit rate 0.576, both halves positive,
turnover 0.091 — disproves that, and remains the only factor either programme produced
whose own interval cleared zero.

The correct reading is narrower and firmer than V3's was: **on this universe, against this
incumbent, at both the fast and the slow end of the horizon range this history can test,
free point-in-time filing data does not contain incremental information of a size worth
acting on — and the horizon was not the reason.**

---

## Execution record

| Step | Charter § | Commit | State |
|---|---|---|---|
| Formulation review — design only, no measurement | — | `21a81d0` | DONE |
| V4 charter — new programme, not a V3 continuation | §0 | `6717111` | DONE |
| Power gate part 1 — block length **FROZEN at L = 7 before any half-width** | §6.1(4) | `ee8fe3f` | DONE |
| Power gate part 2 — half-width 0.005372 vs MDE 0.0095, margin **1.77×** | §6.2 | `fdda61a` | **PASS** |
| §7 standalone-strength screen — R/P ≈ 1.22 vs ceiling 1.5 | §7.3 | `fdda61a` | **PASS** |
| V4-SUE pre-registration — committed **before** any uncentred 20D predictive quantity | §9.4 | `5718f83` | DONE |
| §2.1 pre-measurement clarification — `targets.realise` vs direct `forward_return` | §12 | `aedf891` | DONE |
| **Phase 5 information-only test** | §5 | `f941480` | **REJECT — slot 1 spent** |
| Registry backfill and this closure record | §12 | *this commit* | DONE |

**Sequencing held.** Charter §9.4 fixes the order as *charter → power gate → pre-screen
recorded → pre-registration committed → first fit*, and the git history above shows it in
that order. The power gate was committed in **two parts on purpose**, so the block length
could not have been chosen to make the gate pass — and the §4.6 sensitivity table then
showed the verdict was invariant across every candidate length, which is only publishable
because the freeze was committed first.

**How the effect was kept out of the gate.** Charter §6.1(2) forbids the gate to inspect
any predictive point estimate. Enforcement was structural, not a promise: the paired series
was **centred immediately**, and only the centred series reached any downstream computation
or artefact. A percentile bootstrap interval shifts one-for-one with a constant, so its
width is exactly invariant to centring — the half-width is identical while the effect is
discarded before anything can read it.

**One charter prediction was wrong, and is left standing in the record as written.** §6.2
predicted the gate was *"more likely to fail than to pass."* It passed, because the
formulation review's ≈ 0.0092 extrapolation overstated the true half-width by 1.71× — it
charged √4 for the horizon assuming cutoffs are lost at 20D, but 313 of 316 survive and the
measured variance inflation is 2.7578, not 4. **The charter was not edited and nothing was
loosened to produce the PASS.**

---

## Budget and prohibitions

> ## V4 Slot 1: SPENT. V4 Slot 2: BARRED and UNSPENT. V4 is CLOSED.

Charter §8.3 permits Slot 2 only if **all four** conditions hold. They are conjunctive.
**Condition 1 fails on the pre-registered numbers and is dispositive alone:** it requires
SUE's standalone 20D IC to *materially exceed* P = +0.0261, and the observed value is
**+0.00426**. The charter fixed the consequence in advance — *"A flat or sub-√H standalone
result means the formulation is dead and no second source can revive it."* Condition 2
fails too: §8.4 diagnoses a **formulation-level** failure, not a source-specific one, and a
source-specific diagnosis may not be manufactured to open the slot.

Charter §8.2 therefore governs in its pre-registered wording: *"the correct response is to
record that and stop — not to open Slot 2 by default, and not to look for a third horizon."*

**Barred permanently (charter §9.2, §11):**

* **No SUE′** — no variant of the source at any horizon, λ, sign or construction. **SUE is
  closed at every horizon**, rejected at 5D under λ = 0.25 and at 20D under λ = 0.50.
* **No third horizon** — not 10D, not 40D, not 60D, not a blend, **not "as a diagnostic."**
* **No λ change, no λ scan**, and no promotion of any point on any λ curve to an arm.
* **No sign flip**, at any horizon, on any outcome.
* **No new information family.** V4 is a formulation study, not a feature search. 13F
  acquired no standing from the charter and acquires none now; Form 4 remains barred at any
  horizon or architecture under its current construction.
* **No learner substitution.** A fitted model is not an answer to an information null (§2.9).
* **No re-specification of the target**, and no sub-universe, sector, regime or period
  restriction to make a result survive.
* **No V3 artefact edited, rescored or reinterpreted.**

---

## Status

| | |
|---|---|
| **V4 budget** | **Slot 1 SPENT (V4-SUE, REJECT). Slot 2 BARRED and UNSPENT.** Programme **CLOSED** |
| **V3** | **CLOSED, unchanged.** Families 1/2/3 REJECTED, 3 of 3 slots spent. No V3 artefact touched by V4 |
| **V2 → V2.3** | **ABANDONED, unchanged.** Production weight 0, action HOLD |
| Exam | **SEALED**, `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, 72 cutoffs, **never opened**. Also **not constituted for a 20-session horizon** — charter §10.1, sharpened at gate time from a 5-session to a **10-session** development/exam window overlap |
| Production | weight **0.0**, `alpha/adapter.py` **untouched** |
| Thresholds / criteria / benchmarks / budget / stopping rules modified | **None** |
| Pushed | **No** (§27A) |

**Any further work requires a new directive from the account holder, commissioned
deliberately as its own programme.** It is not a continuation of V4, and it may not be
opened by an executing session (charter §0, §9.3, roadmap §27F).

---

## Artefacts

| File | Content |
|---|---|
| `alpha/V4_FORMULATION_REVIEW.md` | Design basis, no measurement |
| `alpha/V4_CHARTER.md` | The constituting instrument; frozen formulation, budget, stopping rules |
| `reports/V4_SUE_POWER_GATE.md` | §6 gate in two committed parts; block-length freeze, dependence structure, verdict |
| `alpha/V4_SUE_PREREGISTRATION.md` | Study pre-registration; committed before the first fit |
| `alpha/V4_SUE_RESULT.md` | The result and its four failed criteria |
| `reports/EXPERIMENT_REGISTRY.md` §8 | Registry entry `V4-1`, the **§12 diagnosis (§8.4)**, and the Slot 2 bar (§8.5) |
| `alpha/out/v4_sue_power_gate.json` / `.pkl` | Gate record; the `.pkl` carries the **centred** series only and no effect |
| `alpha/out/v4_sue_development.json` / `.pkl` | Full statistics and per-cutoff series — every headline number is re-derivable from per-cutoff data |
| `alpha/v4_sue_config.py` / `v4_sue_study.py` | Frozen constants, and the study that imports every one of them |
| `app/tests/test_alpha_v4_sue.py` | Study tests |

Reproduce with `./.venv/Scripts/python.exe -W ignore -m alpha.v4_sue_study`.
