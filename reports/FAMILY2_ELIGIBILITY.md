# Family 2 (Form 4 insiders) — eligibility and pre-registration record

**Written 2026-08-09.** Follows the §2.6 power gate (`FAMILY2_POWER_GATE.md`, **PASS**).

> # VERDICT: Family 2 is **NOT** authorized to run.
>
> **Slot 2 of 3 remains UNSPENT. Family 2 is not implemented.** No threshold, criterion,
> family budget or stopping rule was modified. Nothing was pushed.
>
> Four eligibility checks **PASS**. Three are **BLOCKED**, and they are blocked on the
> same root cause: **the roadmap does not pre-register a Form 4 feature construction**,
> and §2.10 clause 3, the turnover input to the MDE, and the §2.6 design assumption all
> require one. Per instruction 10 these are **reported as ambiguities, not invented.**

---

## 1. Summary

| # | Check | Status |
|---|---|---|
| 1 | Exact feature construction | **BLOCKED — not pre-registered** (§5.1) |
| 2 | Form 4 point-in-time rule | **PASS** (§2) |
| 3 | §2.10 clause-3 correlation | **BLOCKED — requires the feature** (§5.2) |
| 4a | Universe / coverage | **PASS** (§3) |
| 4b | Turnover input to the MDE | **BLOCKED — requires the feature** (§5.3) |
| 5 | Independence from Family 1 | **PASS** (§4) |
| 6 | §0.1 prohibitions and §2.1–§2.13 | **PASS on all rules evaluable now**; four are feature-conditional (§6) |

---

## 2. The Form 4 point-in-time rule — **RESOLVED, PASS**

Measured on the study era (2016+), 426,432 filings, from the filing **index only** —
form type, `reportDate` (the period of report, i.e. the transaction date), `filingDate`,
`acceptanceDateTime`. **No Form 4 XML was fetched or parsed; no transaction code,
direction, size, price or owner identity was read.** Reproduce with
`python -m alpha.form4_gate pit`.

### 2.1 Two timestamps, and which one governs

| | |
|---|---|
| **Transaction date** (`reportDate`) | present on **100.0%** of filings |
| **Acceptance timestamp** | present, to the second |
| Transaction → acceptance lag | **median 2 days**, p75 4, p90 4, p99 16 |
| Within 2 / 4 calendar days | 61.4% / **93.3%** |
| Later than 10 days | 1.2% |

Consistent with the §16 two-business-day statutory deadline, with a thin late tail.

> **The rule: a Form 4 is admissible at cutoff *T* only if its acceptance timestamp
> (ET) is strictly before 16:00 ET on *T*. The transaction date is never the
> admissibility key — it is knowable only once the filing is accepted.**

Using the transaction date would back-date information by a median of 2 days and up to
16 at the 99th percentile. That is a direct §2.1 violation and it is prohibited here.

### 2.2 Filings received after the close — the dominant case, not an edge case

| | |
|---|---|
| **Accepted after 16:00 ET in the study era** | **77.3%** |
| By year | 68.4% (2016) → 75.2% (2019) → 78.9% (2022) → **82.9% (2025)** |
| Modal acceptance hour | **16:00 ET (34%)**, then 17:00 (19%), 18:00 (11%) |

**Nearly four in five Form 4 filings would leak under a `filed <= cutoff` rule**, against
51.8% for 10-K/10-Q. The trend is rising, so the error would be worst in the most recent
and most heavily weighted years.

**Treatment:** a filing accepted at or after 16:00 ET on date *D* first becomes
admissible at the **next cutoff whose close follows its acceptance**. No same-session
use, no rounding, no "close enough". This is exactly the rule already implemented and
tested in `alpha/filings.py` (`close_of`, `FilingsBook.view`) — Family 2 reuses that
door rather than introducing a second one (§6.1).

**PASS.** Timestamp semantics are documented and pinned by existing tests
(`test_alpha_filings.py`, 15 tests, including the 15:59:59-in / 16:00:00-out boundary).

---

## 3. Universe and coverage — **RESOLVED, PASS**

From `FAMILY2_POWER_GATE.md` §3.1, unchanged: 912,564 Form 4 filings across **614 of
619** issuers. Share of the point-in-time cross-section with ≥1 Form 4 in the trailing
window:

| 30d | 90d | 180d | 365d |
|---|---|---|---|
| 0.754 | **0.959** | 0.987 | 0.989 |

**PASS** — availability is not the binding constraint at any window ≥90 days.

**But coverage is window-dependent, and the window is not pre-registered** (§5.1). The
30-day figure (0.754, min 0.554) is materially thinner than the rest and carries a
noticeably worse half-width (0.00388 vs 0.00205). **Coverage is therefore established as
a function, not as a number** — it resolves to a single value only once the window is
fixed.

---

## 4. Independence from Family 1 — **RESOLVED, PASS**

§21 budgets *genuinely independent* information families. Family 1 used EDGAR XBRL
`companyfacts` (reported financial statement values). Family 2 would use Form 4
(insider transactions). The concern worth testing rather than asserting: **if insider
filings simply cluster on the earnings filing, a Form 4 signal could be an echo of the
event Family 1 already tested.**

Measured — distance from each Form 4 acceptance to the same issuer's nearest 10-K/10-Q
acceptance, against what a uniform spread across a ~91-day quarter would give:

| Within | Observed | Uniform | Ratio |
|---|---|---|---|
| 2 days | 0.081 | 0.044 | 1.84× |
| 5 days | 0.158 | 0.110 | 1.44× |
| 10 days | 0.315 | 0.220 | 1.43× |
| 21 days | 0.552 | 0.462 | 1.20× |
| Median distance | **18.9 days** | 22.75 | — |

**Mild clustering, not an echo.** Insider filings run ~1.4–1.8× the uniform rate near a
periodic filing — expected, since blackout windows close before earnings and reopen
after — but **68.5% of filings land more than 10 days from any 10-K/10-Q**, and the
median sits mid-quarter.

Three further grounds, structural rather than statistical:

1. **Different filer.** Form 4 is filed by the insider under §16; `companyfacts` is the
   issuer's own XBRL. Family 1 never read Form 4 and Family 2 would never read
   `companyfacts`.
2. **Different content.** Who traded, in which direction, and how much is not derivable
   from any financial-statement value. Family 1's rejected feature was `NetIncomeLoss`
   SUE; nothing in Form 4 is a transform of it.
3. **§2.10 clause 1 holds independently** — insider transactions are not computable from
   `alpha/cache`.

**PASS.** Family 2 is a genuinely distinct information family and spending slot 2 on it
would not re-spend slot 1.

---

## 5. What is BLOCKED, and exactly why

### 5.1 The feature construction is not pre-registered anywhere

**This is the root blocker.** The roadmap says exactly one thing about Form 4
(§4.2 table, line 445):

> | **SEC Form 4** | insider transactions | transaction date *and* filing date both present | all §16 filers |

and `INFORMATION_AUDIT.md` §5 adds one sentence:

> direction, size and clustering of officer/director/10%-holder trades, measured from the
> filing acceptance timestamp with the transaction date available separately.

Neither determines a feature. **Six design elements are undetermined**, each of which
materially changes what is being tested:

| # | Undetermined | Why it is not a detail |
|---|---|---|
| 1 | **Transaction-code filter** | Form 4 codes cover open-market purchases (P), sales (S), grants/awards (A), option exercises (M), tax withholding (F), gifts (G). Awards and withholding are *compensation mechanics*, not decisions. Including them measures a payroll calendar; excluding them measures intent. This is the single largest choice and the roadmap is silent |
| 2 | **Aggregation** | net shares, net dollar value, buyer count minus seller count, or a signed indicator — different statistics with different tail behaviour |
| 3 | **Normalisation** | raw, or scaled by shares outstanding, market cap, or dollar volume. Unscaled size is mostly a firm-size proxy |
| 4 | **Role weighting** | the audit names officers, directors **and** 10% holders without a weighting. Treating a CEO purchase and a passive 10% holder's rebalance alike is a choice, not a default |
| 5 | **Lookback window** | 30 / 90 / 180 / 365 all measured; coverage and half-width differ materially (0.754→0.989; 0.00388→0.00185). **Picking the window on its coverage or half-width would be selecting a design on power**, which §2.4 forbids |
| 6 | **Absent-insider policy** | Family 1 pre-registered "NaN, never filled" because absent earnings are *missing*. For Form 4, "no insider traded" is plausibly *informative* (a true zero) rather than missing. NaN and 0 give different cross-sections and different rankings, and neither is pre-registered |

**Instruction 10 applies. I am not choosing any of these.** Each is a research decision
that changes the hypothesis, and inventing one here — then pre-registering it as though
it had been fixed in advance — would be precisely the retrofit the whole protocol exists
to prevent.

**Additionally undetermined, and inherited rather than pre-registered:**

* **λ for the bounded arm.** The §2.6 gate was computed at **λ = 0.25**, which is Family
  1's pre-registered value, **stated as an assumption in that record, not derived from
  the roadmap.**
* **The §2.10 clause-3 numeric ceilings** (≤0.30 vs `z__ret_12_1`, ≤0.50 vs each
  stock-level input) were fixed in **Family 1's** preregistration. Carrying them forward
  unchanged is the non-shopping option, but it is a carry-forward, not a roadmap rule.
* **The primary horizon.** `TARGET_DESIGN.md` §4.2 requires each family's
  preregistration to name **one** primary horizon on priors before the first fit. Family
  2's has not been named.

### 5.2 §2.10 clause 3 — **cannot be computed**

Clause 3 requires the correlation of *the feature* against `z__ret_12_1` and the 34-column
set, measured on the panel before any model is fitted. **There is no feature.** The six
choices above produce materially different columns with materially different momentum
correlations — a 90-day net-purchase indicator and a 365-day dollar-value z-score are not
approximations of each other.

**Reporting a correlation for a feature I invented would be worse than reporting none**,
because it would create the appearance that clause 3 had been satisfied. Not computed.

### 5.3 Turnover, and therefore the exact MDE — **cannot be computed**

`FAMILY2_POWER_GATE.md` §2.1 already flagged this. The +0.007 MDE holds while extra
turnover ≤ 30 percentage points. Turnover is a property of the feature: a 30-day
event-driven signal and a 365-day accumulation differ by an order of magnitude.

**Direction, restated so it is not mistaken for a threat to the gate:** higher turnover
*raises* the MDE, enlarging the effect sought, which makes the §2.6 comparison easier to
pass and the **study** harder to pass. The gate's PASS is unaffected. The number cannot
be filled in without the feature, and **no assumption is substituted for it** here.

---

## 6. §0.1 prohibitions and §2.1–§2.13 — conformance

| Rule | Status |
|---|---|
| §0.1 exam untouched | **PASS** — nothing in this pass reads the exam; digest `b55e065f…` re-verified |
| §0.1 production weight / adapter | **PASS** — weight 0, adapter untouched |
| §0.1 no threshold lowered, benchmark swapped, B3 modified | **PASS** — none touched |
| §0.1 no rung/λ/control promoted to an arm | **PASS** — no arm exists |
| §0.1 no V2.4 | **PASS** — new information, unchanged learner (and no learner in Phase 5) |
| §2.1 point-in-time discipline | **PASS** — §2; acceptance-keyed, transaction date rejected as the key |
| §2.2 walk-forward only | **PASS** — inherits the frozen 5-session protocol |
| §2.3 mandatory baselines | **PASS, and binding** — B3, B1, B2 **and** "the simplest possible version of the new source" must be an arm |
| §2.4 no metric shopping | **PASS, and at risk** — see §5.1 #5: the window must **not** be selected on coverage or half-width |
| §2.5 regime concentration disqualifies | **conditional** — must be a pre-registered criterion, as Family 1's criterion 4 was |
| §2.6 power before permission | **PASS** — `FAMILY2_POWER_GATE.md`, with the λ = 0.25 and bounded-combination assumptions stated |
| §2.7 arms declared before first fit | **conditional** — no arms declared yet |
| §2.8 frozen evidence | **PASS** — artefacts hashed and committed as produced |
| §2.9 no architecture escalation | **PASS** — Phase 5 fits no learner; Family 1's rejection was not answered with a bigger model |
| §2.10 cl. 1 not in `alpha/cache` | **PASS** — insider trades are not a price/volume transform |
| §2.10 cl. 2 own timestamp | **PASS** — §2 |
| §2.10 cl. 3 correlation ceiling | **BLOCKED** — §5.2 |
| §2.10 cl. 4 effect exceeds resolution | **PASS on resolution** (§2.6 gate); the effect claim belongs in the preregistration |
| §2.11 controls powered as gates | **conditional** — the 30-draw paired control must be carried over |
| §2.12 free power gain is a warning | **PASS** — oracle-ceiling check performed; ~30× headroom, so the narrow half-width is genuine power |
| §2.13 never reason from a post-processed number | **PASS** — nothing post-processed |
| §21 three families, no fourth | **PASS** — slot 2 unspent; independence verified (§4) |
| §27A no push | **PASS** — nothing pushed |
| §27B no data spend | **PASS** — SEC bulk data, free |

**No rule is violated. Four are conditional on a design that does not yet exist.**

---

## 7. What would unblock Family 2

A **human decision fixing the six elements in §5.1** (plus λ, the ceilings, and the
horizon), recorded in `alpha/V3_FAMILY2_PREREGISTRATION.md` **before any measurement**.
Once fixed, the remaining checks are mechanical and I can complete them without further
input: compute §2.10 clause 3 against the frozen ceilings, measure turnover and finalise
the MDE, then report PASS/FAIL.

**Two constraints on how that decision is made, from rules already in force:**

* **§2.4 and instruction 8 — the window and the code filter must be chosen on
  *economic reasoning*, not on coverage, half-width, or expected performance.** The
  coverage and half-width figures in §3 are published here as *eligibility* facts; using
  them to pick the window would convert them into a selection criterion.
* **§2.3 — whatever is chosen, the simplest possible version of it must be an arm.** One
  rank, one ratio, one z-score. Family 1's Arm 0 played this role and it is what produced
  the study's only genuinely informative result.

**I have deliberately not ranked the options in §5.1**, because ranking them would be a
choice made under the appearance of a report.

---

## 8. Status

| | |
|---|---|
| Family 2 implemented | **No** |
| Family 2 study run | **No** |
| **Slot 2 of 3** | **UNSPENT** — 1 spent (Family 1), **2 remaining** |
| Thresholds / criteria / budget / stopping rules modified | **None** |
| Family 2 **authorized to run** | **NO** — blocked on §5.1, §5.2, §5.3 |
| Exam | sealed, `b55e065f…` |
| Production | weight 0, HOLD |
| Pushed | **No** |

Reproduce §2 and §4 with `python -m alpha.form4_gate pit`; §3 with
`python -m alpha.form4_gate coverage`. Artefact:
`alpha/out/form4_pit_semantics.pkl`.
