# PEAD-1 Charter — reopening SUE under an event-time, absolute-return formulation

**Written 2026-08-22. CHARTER ONLY. Committed before any PEAD-1 measurement exists.**

No PEAD-1 study has been run. No feature was built, no target was constructed, no forward
return was read at any horizon, no backtest was executed, no data beyond what V3/V4 already
fetched was pulled, no model was fitted, and no exam cutoff was opened. Every number below is
one of:

* **(V3)** — quoted verbatim from a completed, committed V3 artefact;
* **(V4)** — quoted verbatim from a completed, committed V4 artefact;
* **(F10)** — quoted verbatim from the completed Family-10 admissibility pilot;
* **(SN1)** — quoted verbatim from the completed Single-Name Phase 1 study;
* **(ARITH)** — arithmetic on the above, derived in-line so it can be checked.

**V3 and V4 are closed and are not touched by this document.** No V3 or V4
pre-registration, family module, result, report, registry entry, exam artefact or
production adapter is edited, amended, reinterpreted, rescored or superseded here. Exam
sealed at `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. Production
weight `0.0`.

---

## 0. Authorisation — stated plainly, because it is the whole basis for this document

`CLAUDE.md` §1.3 requires flagging a conflict with §0.1/§21 before proceeding when a task
appears to reopen a closed programme, and states no entry may be reopened "even if the user
asks for a quick fix." This is not that. On 2026-08-22 the account holder was shown the
conflict explicitly — that PEAD is SUE, closed at every horizon V3 and V4 tested, and that
`pine.vix_fix` was already measured and rejected by HT-1 — and, presented with that
conflict, **explicitly directed reopening it**, naming the V4 charter as the precedent to
follow. That is a directive from the account holder, not a session's own initiative, and it
is the one route V4's own closure record left open: *"Any future work needs a new directive
from the account holder, not a continuation."* This charter is that directive's written
form, to the same standard V4 held itself to — not a lighter one, because reopening was
requested rather than discovered.

**It is not an authorisation to run anything.** PEAD-1 is authorised to *proceed to a power
gate that does not yet exist* (§6) and to nothing beyond it.

---

## 1. Relationship to V3 and V4 — stated without hedging

| Statement | Status |
|---|---|
| V3 Family 1 (SUE, cross-sectional, 5D, λ=0.25) | **REJECTED** for incremental value. Standalone IC +0.01305, CI excludes zero **(V3)**. Arm 1 − B3 +0.00090 **(V3)**. Unchanged |
| V4-SUE (SUE, cross-sectional, 20D, λ=0.50) | **REJECTED.** Standalone IC +0.00426, below its own √H extrapolation **(V4)**. Arm 1 − B3 −0.00106 **(V4)**. Unchanged |
| V3 budget | 3 of 3 SPENT. Unchanged |
| V4 budget | Slot 1 SPENT, slot 2 BARRED. Unchanged |
| Re-running SUE **under V3 or V4** | PROHIBITED. No Family 1′ or SUE′ exists or may exist |
| Any V3/V4 threshold, result, interval or decision | UNCHANGED. Nothing is rescored |
| The 72-cutoff exam | SEALED, unread. Not constituted for any of V3's, V4's or PEAD-1's horizon (§10) |

**PEAD-1 is a separate programme with a materially different scientific question, on the
same reasoning basis V4 used to reopen V3's SUE.** It inherits from V3/V4 exactly three
things: the point-in-time discipline (`alpha/filings.py`'s acceptance-time door), the SUE
feature construction itself (frozen, §4), and the standard of honesty. It inherits no
slots, no permissions, and no benefit of the doubt.

---

## 2. The PEAD-1 question

### 2.1 What V3 and V4 asked

> Does SUE, blended into a cross-sectional rank tilt on top of B3 and measured on a
> **5-session (V3)** or **20-session (V4)** **calendar grid**, add incremental IC ≥ a
> pre-registered MDE?

Answered twice. Answer: no at either horizon, under either architecture.

### 2.2 What PEAD-1 asks — the primary hypothesis, stated so it can fail

> **H1 (PEAD-1 primary).** SUE's information is concentrated in **event time** around the
> earnings release itself, in a way a **calendar-grid cross-sectional rank tilt cannot
> capture** — such that, conditioning on SUE's surprise tercile *at the moment a name's own
> earnings become known point-in-time*, the name's own **absolute forward return** over a
> pre-registered post-event window exceeds the single-name resolution this history can see,
> in the direction of the surprise sign, net of the always-flat and always-long-market
> controls.

**H0 (the null PEAD-1 must be able to accept).** SUE's cross-sectional nullity (V3, V4) is
not an artefact of calendar-grid sampling; the same absence holds when the same feature is
read in the one place classical PEAD literature says it should matter most — immediately
after the print.

**What falsifies H1:** the confirmatory criteria in §5, structured on the Family-10
admissibility template (identity/PIT → independence/power → economic threshold), because
PEAD-1 is an absolute-return single-name claim, not a cross-sectional IC claim, and must be
judged on the instrument built for that class of claim.

### 2.3 The change is the dependent variable and the sampling grid, not the feature

This is the entire basis on which reuse is admissible, restated from V4 §2.3's template:

* **Event-time absolute return and calendar-grid cross-sectional IC are different random
  variables**, not two estimators of one. V3 and V4 both sampled a fixed 5-session grid
  *regardless of whether a name had just reported earnings*; the overwhelming majority of
  grid cutoffs for any given name fall in calendar time with no fresh SUE information at
  all, diluted into the panel average. PEAD-1 samples only the point in time SUE actually
  changes.
* **Neither V3 nor V4 could have measured this.** Both are structurally calendar-grid
  designs; an event-time sample was never taken. There is no PEAD-1 number anywhere in the
  V3 or V4 record to have peeked at.
* **The claim is independently falsifiable in the direction that matters.** If event-time
  concentration were the whole explanation, cross-sectional dilution would predict exactly
  what V3 and V4 found: a real, tail-concentrated effect measured on a grid that samples it
  at effectively random phase, averaging toward zero. That is a specific, checkable
  mechanism — not a restatement of "try again."

### 2.4 What is carried over unchanged, and must be

`sue` — construction frozen per `V3_PREREGISTRATION.md` §3 / `V4_SUE_PREREGISTRATION.md`
§2.2, verbatim, in every particular (§4.1). **Changing the feature definition would make
this a new-feature study, not a new-formulation study, and would destroy the identifiability
argument in §2.3** — the same warning V4 §3.4(d) gave about itself.

---

## 3. The six-condition reuse test, applied to PEAD-1

Following `alpha/V4_CHARTER.md` §3.2's template exactly, adapted to name PEAD-1 in place of
V4-SUE.

| # | Condition | Status for PEAD-1 |
|---|---|---|
| 1 | The target/sampling design is **materially different** and pre-registered before measurement | **MET.** Event-time absolute return, not a calendar-grid cross-sectional IC; fixed in §5, before any event-window return is read |
| 2 | The arm architecture is **materially different** and pre-registered before measurement | **MET.** An event-conditional trigger, active only in a pre-registered window around the name's own earnings, versus an always-on cross-sectional blend |
| 3 | **No V3 or V4 result is rescored or reinterpreted** | **MET.** Neither file is read for re-evaluation, edited or re-run. Their numbers appear here only as quoted priors |
| 4 | **No sign is flipped based on a V3/V4 outcome** | **MET.** Sign is **+1 by the same economic prior** SUE has carried since `V3_PREREGISTRATION.md` §6.1: higher surprise, higher subsequent return. A negative prior result would not license a flip and none is made |
| 5 | **No V3/V4 hyperparameter is optimised from V3/V4 results** | **MET.** The feature construction is copied verbatim (§2.4); nothing about it is retuned. The event window (§5) is set from the academic PEAD literature's own documented concentration period, not from any V3/V4 number |
| 6 | The study receives **its own fresh budget and stopping rule** | **MET.** §8. PEAD-1 draws nothing from V3's exhausted three slots or V4's exhausted/barred two |

**Any candidate failing any one of these six is not admissible.** SUE, under this
formulation, passes all six.

### 3.1 Why reuse rather than a fresh source — the identifiability argument, restated

`CLAUDE.md` §1.3 and roadmap §21 require, on the failure of a formulation, that a
formulation change hold the information fixed to be interpretable — exactly V4 §3.4(d)'s
argument. **SUE is the only source in the V3/V4 record with affirmative standalone
evidence** — V3's Family 2 and Family 3 failed as *absent* (spreads undefined or
sign-wrong), which no formulation change can rescue; SUE failed as *not incremental at two
calendar-grid architectures*, which is exactly the failure mode a sampling-grid change can
in principle address. Substituting a fresh information source here would confound "was the
event-time idea right" with "did we find a better feature," which is precisely the
confound §21 exists to prevent.

---

## 4. The PEAD-1 candidate

### 4.1 Authorised

**`sue`**, construction frozen verbatim from `V3_PREREGISTRATION.md` §3, restated in
`V4_SUE_PREREGISTRATION.md` §2.2: time-series standardized unexpected earnings on
`NetIncomeLoss`, seasonal difference over the year-ago quarter, scaled by the standard
deviation of the last 8 such surprises (minimum 4), Q4 derived as FY − (Q1+Q2+Q3),
winsorised per cutoff at 1/99, EDGAR **acceptance-time** point-in-time door
(`alpha/filings.py`). **No element may be modified.**

### 4.2 Not authorised

* **13F and Form 4 — NOT authorised**, for the same reasons V4 §4.4 recorded: 13F's
  standalone interval spans zero **(V3)**; Form 4 cannot form a short book at any
  architecture **(V3)**. Neither acquires standing from this charter.
* **`pine.vix_fix` reuse is a separate charter (§0 of `OPTIONS1_ADMISSIBILITY.md`) and is
  not folded into PEAD-1.** The two reopenings share an account-holder directive but not a
  scientific question — VIX mean reversion is not a filings feature and its own reuse
  conditions are argued independently.
* **No new information family may be introduced into PEAD-1.** This is a formulation study
  on one named source, not a feature search.

---

## 5. The frozen PEAD-1 design — deferred detail, fixed skeleton

The full frozen table (in the style of V4 §5) is written as its own pre-registration
document, **after** a power gate exists (§6), per the sequencing rule in §9.4. What is fixed
**here**, before that document, because it is load-bearing for §3 and §6:

| # | Element | Specification |
|---|---|---|
| 1 | **Sampling unit** | One event per name per fiscal quarter: the first point-in-time cutoff at or after the quarter's EDGAR acceptance time, restricted to names in the point-in-time universe at that date |
| 2 | **Dependent variable** | Absolute forward return over a pre-registered post-event window (candidates: 5, 20, 60 sessions — the classical PEAD concentration range), name-level, **not** cross-sectional rank |
| 3 | **Conditioning** | SUE surprise tercile at the event, computed with the frozen construction (§4.1) and nothing else |
| 4 | **Sign** | +1, unchanged prior (§2.3) |
| 5 | **Mandatory controls** | always-flat (0% return) and always-long-market (SPY return over the identical window) — the Family-10 (F10) baseline pair, not B1/B2/B3, because this is an absolute-return not a cross-sectional-rank claim |
| 6 | **PIT rule** | Acceptance-time door, `alpha/filings.py`, unchanged, not approximated |
| 7 | **Identity** | CIK-joined to `alpha/membership.py`, following Family-10's identity lesson **(F10)** — not `company_tickers.json`, which Family-10 measured misses 120 of 720 ever-member tickers |

The window count (one of 5/20/60), the confirmatory CONTINUE rule, the noise control, and
the coverage gate are fixed in the follow-on pre-registration, **before** any event-window
return is read — not here, because doing so now, before the power gate establishes what this
history can resolve, would risk choosing a window that merely looks favourable in the
literature rather than one this instrument can see.

---

## 6. The power gate — blocking, not yet run, and the reason it is expected to be hard

**No PEAD-1 slot may be spent before a fresh §2.6-style power gate for this exact design
passes.** Unlike V4, no prior extrapolation exists for this design, because no event-time
absolute-return SUE study has ever been run. The gate must be built, not merely re-derived.

### 6.1 The reusable resolution floors this gate must be measured against

**(SN1)** Single-Name Phase 1's single-name MDE at n=215 cutoffs: covered-book 5-session
return **±0.00390 (39 bp)**. **(F10)** Family-10's reusable half-width floor table, which
applies to any event-clustered absolute-return design on this history:

| Block length | Independent blocks (F10's calibration) | Floor as n → ∞ |
|---:|---:|---:|
| 5 sessions | 532 | 22.4 bp |
| 10 sessions | 266 | 31.6 bp |
| 24 sessions | 111 | 49.0 bp |

**Earnings events cluster far more tightly than 8-K filings did.** A name reports on
essentially the same four calendar weeks every year — "earnings season" — which Family-10's
own §5 finding (event sampling buys event dates, not independent ones) predicts will be
*worse* here, not better: many names' Q-over-Q events fall in the same handful of weeks
across the whole cross-section, so pooling across names does not multiply independent
information the way it would if events were spread uniformly through the year. **The gate
must measure this directly** — via `alpha/stats.py`'s existing block-bootstrap and
independent-unit machinery, reused and not rewritten — rather than assume event count is a
usable proxy for resolution, which is the specific mistake Family-10's own history warns
against repeating.

### 6.2 What must happen before any slot is spent

1. Build the point-in-time earnings-event calendar for the universe (CIK-joined, per §5
   item 7), and compute its **independent block census** — the direct analogue of Family-10
   Stage 1/2.
2. Compute the achieved half-width at each of the three candidate windows (5/20/60 sessions,
   §5 item 2), **without reading any forward return** — variance and clustering structure
   only, per V4 §6.1.2's rule.
3. Compare against the 39 bp **(SN1)** hurdle and the block-length floor table **(F10)**.
   **If the achieved half-width exceeds 39 bp at every candidate window, PEAD-1 MUST NOT
   RUN**, and the honest reading is that event clustering, not calendar-grid dilution, is
   what actually blocks resolution of this source — a different and more useful negative
   result than V3/V4 could produce.
4. Only a window that clears the hurdle may be selected for the confirmatory
   pre-registration, and it must be selected on this **variance-only** basis, not on any
   peeked return.

**Expected outcome, stated in advance:** given the clustering argument in §6.1, this gate is
more likely to fail than to pass, and a fresh cycle should not treat that as a surprise or a
reason to relax anything. That is the discipline `alpha/V4_CHARTER.md` §6.2 modelled and
this charter adopts unchanged.

---

## 7. The standalone-strength pre-screen

Following V4 §7's template: before the gate is even built, it is worth asking what SUE would
have to be worth, standalone, for an event-time design to clear the 39 bp hurdle. **This
arithmetic is deferred to the gate document itself (§6.2 item 2–3)**, because — unlike V4's
cross-sectional IC, which has a closed-form combination formula — an absolute-return,
event-conditional design's required standalone strength depends on the base rate of large
moves in the conditioning window, which is an empirical quantity the gate must estimate
without reading forward returns. Asserting a number here without that estimate would be
exactly the kind of unearned extrapolation §6's framing warns against.

---

## 8. The PEAD-1 research budget

> **PEAD-1 budget: ONE confirmatory study.** No slot 2 exists, conditional or otherwise.
> If the power gate fails, the budget is spent on "not resolvable on this history under
> this formulation" and PEAD-1 is closed. If the gate passes and the confirmatory study
> then fails its CONTINUE rule, PEAD-1 is closed. There is no version of this study that
> reopens itself a second time.

PEAD-1 draws no slots from V3 or V4. Their three and two remain spent/barred and closed.

---

## 9. Stopping rules, fixed prospectively

### 9.1 If the power gate fails

* Do not build the event calendar into a running study. Record "not resolvable on this
  history under this formulation" and stop.
* **Do not modify the design to make it runnable.** No window substitution beyond the three
  pre-registered candidates, no hurdle reduction, no universe expansion, no block-length
  shortening chosen after seeing it fail (§6.2 exactly forbids this, the Family-10 lesson).

### 9.2 If PEAD-1 runs and fails its confirmatory rule

* REJECTED, slot SPENT.
* **No SUE″.** Not at another window, another tercile cut, another controls set.
* **No sign flip.** No promotion of a diagnostic to an arm.
* **No re-specification of the identity or PIT rule** to make a result survive.
* The correct recorded conclusion: SUE's nullity in V3 and V4 is not an artefact of the
  calendar grid; the source is absent in event time too, at the resolution this history can
  see. **This closes SUE permanently, at every formulation the account holder has now
  authorised testing.** No further reopening of SUE may be proposed by an executing session;
  a fourth attempt would require the account holder to name a formulation this charter did
  not anticipate, in writing, as a new decision.

### 9.3 If PEAD-1 passes

* **STOP BEFORE PRODUCTION.** Do not open the exam (§10). Do not raise production weight
  above `0.0`. The next phase requires explicit account-holder authorisation, in writing, as
  a separate decision — the discipline V4 §9.3 modelled.

### 9.4 Sequencing requirement

Fixed order, may not be reordered: **this charter (committed) → power gate built and run
(§6, reading no forward return until the verdict is recorded) → confirmatory
pre-registration committed, fixing the window and CONTINUE rule → first event-return read.**

---

## 10. Exam policy

The 72-cutoff exam is sealed and, per V4 §10.1's reasoning applied here, **not constituted
for an event-time question at any window**: its separation guarantee is built around a fixed
5-session calendar grid, and an event-time sample does not align with it at all. **Default
position: the exam stays SEALED throughout PEAD-1, unconditionally.** If PEAD-1 ever reaches
a stage requiring a final untouched test, a new exam — event-time, with its own frozen
separation rule — would be a separate authorisation, not designed, specified or costed here.

---

## 11. Prohibited in PEAD-1, restated so this document stands alone

* Opening, scoring, inspecting, modifying or rebuilding the 72 exam cutoffs.
* Raising production weight above `0.0` or modifying `alpha/adapter.py`.
* Editing, amending, rescoring or reinterpreting any V3 or V4 artefact.
* Modifying the `sue` feature construction in any particular.
* Selecting the event window, or any threshold, after any forward return has been read.
* Adding a second feature, a fitted learner, or a cross-sectional blend back into the design.
* Restricting any result to a regime, sector, year or sub-universe to make it survive.
* Flipping any sign on any outcome.
* Reporting a power-gate estimate, or any pre-gate quantity, as a result.
* Purchasing data or substituting a lower-quality free source (§27B).
* `git push` (§27A — `origin` is a third party's public repository).

---

## 12. Recording

* This charter is committed before any PEAD-1 measurement exists.
* The power gate (§6) is its own committed artefact, before any confirmatory
  pre-registration.
* The confirmatory pre-registration is its own committed document, fixing the window and
  CONTINUE rule, before the first event-return read.
* The registry entry records: hypothesis, source, window, controls, MDE, achieved
  half-width, result with its half-width, and the diagnosis — did the information fail, the
  clustering/power, the PIT quality, or the coverage?

---

## 13. Preservation statement

Nothing in V3 or V4 was edited by this charter. No predictive measurement of any kind was
performed. No forward return at any horizon or window was read. The exam remains sealed at
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. Production weight
remains `0.0`. Nothing was pushed.

**PEAD-1 is not authorised to run by this document.** It is authorised only to proceed to
the §6 power gate, and building that gate is the next and only next step.
