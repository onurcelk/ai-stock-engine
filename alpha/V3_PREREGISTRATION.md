# V3 Pre-registration — Family 1: reported fundamentals

**Written 2026-08-09, before the first fit and before any result was inspected.**
This document is fixed. It is not edited after a result exists; corrections are
appended, dated, and leave the original wording visible — the convention
`V2_3_PREREGISTRATION.md` established and the reason that document is still worth
reading.

Commissioned under master roadmap v2 (`reports/directives/`). Family 1 of the three
frozen in `reports/INFORMATION_AUDIT.md` §5. **This spends budget slot 1 of 3 (§21).**

---

## 1. The hypothesis, stated so it can fail

> **Point-in-time reported earnings, timestamped at EDGAR acceptance, contain
> incremental cross-sectional predictive information over 12-1 momentum and over the
> B3 regime rule — of a size this history can resolve.**

The specific claim: a firm's **time-series standardized unexpected earnings** (SUE),
computed only from its own reported history as known at the cutoff, ranks the
cross-section of 5-session forward alpha, and adding it to the incumbent improves on
the incumbent.

**What would falsify it:** the decisive contrast in §6 fails to clear its threshold.
Then Family 1 is REJECTED, spends slot 1, and is **not** re-tested with a larger model,
a different learner, a different target, another horizon, or "one more carrier" (§2.9,
§21).

## 1.1 Why this is not a V2.4

§0.1 prohibits adding another learner to the same information. Family 1 is admissible
under §2.10 because the information is **not computable from `alpha/cache`**: it comes
from `companyfacts.zip` joined to `submissions.zip`, carries its own acceptance
timestamp, and no transform of price or volume produces a firm's reported net income.
The learner is unchanged and is not the subject of the study.

---

## 2. Admissibility under §2.10 — all four clauses

| Clause | Status |
|---|---|
| 1 — not computable from `alpha/cache` | **PASS.** Source is SEC filings; no price/volume transform yields reported earnings |
| 2 — carries its own timestamp | **PASS, verified.** `acceptanceDateTime` to the second, joined per accession. 87 facts lacking one were **dropped, not approximated** |
| 3 — clears a correlation ceiling | **thresholds fixed below, measurement pending** |
| 4 — plausible effect exceeds resolution | **PASS conditionally** — see §4 |

### 2.1 The clause-3 ceiling — thresholds fixed here, before the measurement is read

The correlation run was launched before this section was written and **its output has
not been inspected.** The thresholds below are therefore committed blind, which is the
only condition under which a ceiling means anything.

| Ceiling | Threshold |
|---|---|
| Mean per-cutoff \|Spearman(SUE, `z__ret_12_1`)\| | **≤ 0.30** |
| Mean per-cutoff \|Spearman(SUE, *c*)\| for every *c* in the 34-column V2 input set | **≤ 0.50** |

**If either ceiling is breached, Family 1 is inadmissible and the study does not run.**
A breach means the information is substantially a slow proxy for something already
inside the refuted space, and running it anyway would re-spend V2's power on V2's
question. A breach is recorded as REJECT-on-admissibility and **still spends slot 1** —
that is the point of the §2.6/§2.10 gates having teeth.

---

## 3. Data, target, horizon — fixed

| | |
|---|---|
| Universe | the panel's point-in-time index membership, unchanged (`alpha/membership.py`); median cross-section 465 |
| Cutoffs | the **316 development cutoffs** of `examset.load().development`. **The 72 exam cutoffs are not read, not scored, not inspected** (§0.1) |
| Target | **Target A — `alpha_5d`, within-cutoff Spearman IC**, unchanged from the record (`reports/TARGET_DESIGN.md` §4.1) |
| Horizon | **5 sessions.** The single primary horizon, fixed here on priors. **No second horizon is run**; 10D/20D are not secondary hypotheses in this study and may not be added later (§2.4, TARGET_DESIGN §4.2) |
| Feature | **`sue`** — time-series SUE on `NetIncomeLoss`, seasonal difference over the year-ago quarter, scaled by the standard deviation of the last 8 such surprises (minimum 4), Q4 derived as FY − (Q1+Q2+Q3) |
| Knowability | `accepted (ET) < 16:00 ET on the cutoff date`, enforced in `alpha/filings.py` and by event replay in `alpha/filings_features.py` |
| Missing data | **NaN, never filled.** A name without a defined SUE is excluded from that cutoff's SUE ranking; it is not imputed to the median, which would be a silent bet |
| Winsorisation | SUE is winsorised per cutoff at the 1st/99th percentile before ranking — declared here, applied identically in every test |

**Secondary feature, declared now so it cannot be introduced later as a rescue:**
`staleness_days` (calendar days since the newest known quarter's acceptance) is recorded
in the panel as a **diagnostic only**. It is not an input to any test in §6 and may not
become one in this study.

---

## 4. The §2.6 power gate — restated verbatim from `EXPERIMENT_REGISTRY.md` §6.1

Computed 2026-08-09 before any implementation.

| | |
|---|---|
| Smallest effect worth acting on (MDE), from the frozen cost model | **+0.007 IC vs B3** |
| Achievable half-width, 255–316 paired cutoffs, combination-vs-incumbent design | **0.0074–0.0083 IC** |
| **Hypothesized effect this study commits to seeking** | **≥ +0.010 IC vs B3** |
| Verdict | **RUNNABLE** at the hypothesized effect; **not runnable** for anything smaller |

Derivation: the frozen record measures the per-cutoff top-bottom spread at ≈0.10 × IC
(0.091–0.105 across V2.1-C/D and V2.3-A/B) and a cost drag of 0.0002–0.0007 per week at
the pre-registered 5 bps. A net advantage of ≥ +0.0004/week (~2%/yr) after ~0.0003/week
of added turnover requires a gross spread advantage ≥ ~0.0007/week, i.e. **≥ ~0.007 IC**.

**The consequence, accepted in advance:** an effect of +0.003 — twice anything V2 ever
found — is **a null in this study**, because it is inside the resolution. This study
cannot and will not claim it. If Family 1's true effect is real but small, the correct
recorded outcome is "not resolvable on this history", and §21 counts the slot as spent.

---

## 5. Baselines — all mandatory (§2.3)

| Baseline | Role |
|---|---|
| **B3 regime-switched momentum** | **the incumbent.** +0.02836, the only benchmark whose CI excludes zero. The number to beat |
| **B1 12-1 momentum** | the factor V2→V2.3 could not improve on |
| B2 5-day reversal | reported, as in the record |
| **The simplest possible version of the new information** | **the raw SUE rank alone**, one number, no model. This is Arm 0 and it is not optional |

Cross-sectional study, so always-up and no-change do not apply here; they are **Phase 7b's**
baselines and bind anything that reaches the product (§1.1, §9b).

---

## 6. The tests, the arms, and the decision rule — all fixed

### 6.1 Arms declared: **two.** No third arm exists in this study.

| Arm | Definition |
|---|---|
| **Arm 0 — raw factor** | within-cutoff percentile rank of `sue`, sign **+1 by economic prior** (higher surprise → higher forward alpha). **The sign is fixed here and is not re-estimated from any data** |
| **Arm 1 — bounded combination** | `z__b3 + λ·(rank_pct(sue) − 0.5)`, **λ = 0.25**, fixed here. The incumbent plus a bounded tilt on the new information |

**λ = 0.25 is fixed and no λ curve is scanned as an arm.** A λ sensitivity curve may be
*reported as a diagnostic* (as V2.3 did), and **no point on it may be promoted to an
arm** (§0.1). Arm 1 uses the same bounded-combination form V2.3 measured, so its
resolution against B3 is the one §4 calibrated.

**No learner is fitted in Phase 5.** This is an information-only test (§2.9). A model is
built only if §6.3 says CONTINUE.

### 6.2 Metrics, fixed before any result is seen

* **Primary metric:** paired per-cutoff difference in within-cutoff Spearman IC,
  **Arm 1 versus B3**, over the common development cutoffs.
* **Interval:** moving-block bootstrap, `alpha/stats.py`, `BLOCK_LENGTH = 4`, 10,000
  draws, as used throughout the record. Newey-West as cross-check.
* **Secondary, reported always:** Arm 0's standalone IC and its difference vs B1 and B3;
  Arm 1 vs B1; breadth (share of cutoffs positive); chronological halves; regime
  decomposition; turnover and **net-of-cost spread advantage at 5 bps** (§10 makes
  net-of-cost primary from the first measurement).
* **Achieved half-width is reported next to every point estimate.** A point estimate
  without its resolution is not a result (§2.6).

### 6.3 Decision rule — CONTINUE requires all four

1. **Arm 1 − B3 ≥ +0.010** in mean paired IC, **and**
2. its **95% block-bootstrap CI excludes zero on the favourable side**, **and**
   *(**Amendment A1**, 2026-08-09 — see §10. Original wording, which remains the wording
   Families 1 and 2 were evaluated under: "its **95% block-bootstrap CI excludes zero**".
   **A1 is prospective from Family 3 onward and changes no completed result.**)*
3. **breadth > 0.50** and **both chronological halves positive** (the G5 sign-flip
   failure that killed V2.3 must not repeat), **and**
4. the effect is **not concentrated in one regime bucket** — specifically, it must
   survive with `BEAR_TREND` cutoffs removed. **Concentration disqualifies; it does not
   caveat** (§2.5).

**Anything less is REJECT.** In particular:

* A positive point estimate with an interval spanning zero is **REJECT**, not
  "promising". That is exactly V2.1-D's +0.01312, and treating it as promising is what
  bought three more studies.
* An improvement over B1 but not over B3 is **REJECT**. B3 is the incumbent (§2.3).
* A result that lives in `BEAR_TREND` is **REJECT**, whatever its size — a fourth
  consecutive bear concentration would be the same finding a fourth time.

### 6.4 Multiplicity

Two arms, one primary contrast, one target, one horizon, declared before the first
computation. Holm–Bonferroni across the two arms' primary contrasts, reported alongside
raw p-values, as in the record.

---

## 7. Sanity control — powered as a gate, not as a gesture (§2.11)

V2.3's noise control fired on a single seeded draw that landed ~2σ high and aborted a
run. This study's control is specified to avoid that failure:

* **30 paired draws**, not one.
* Each draw replaces `sue` with a **random permutation of the SUE values within each
  cutoff**, preserving the cross-sectional distribution and destroying only the
  identity-to-value mapping.
* Compared **paired against the same base**, on the same cutoffs, with the same bootstrap.
* **Firing rule:** the control fails, and the study is void, if the *median* of the 30
  draws' Arm-1-minus-B3 differences exceeds **+0.002**, or if more than **10%** of draws
  clear the §6.3 threshold of +0.010.
* A single draw's result is **never** grounds to abort. The sampling spread of the
  control is reported next to its median.

---

## 8. What is prohibited in this study

Carried from §0.1 and the roadmap, restated so this document stands alone.

* The 72 exam cutoffs are not opened, scored, inspected, modified or rebuilt.
* Production weight is not raised; `alpha/adapter.py` is not modified.
* No threshold in §6.3 is lowered after a result is seen. No benchmark is swapped. B3 is
  not modified.
* No λ point, rung, or noise-control draw is promoted to an arm.
* No result is restricted to a regime bucket, sector, year or sub-universe to make it
  survive.
* The horizon is not changed, and no second horizon is added.
* `staleness_days` does not become an input.
* Development numbers are never reported as alpha.
* **If Family 1 is rejected, no Family 1′ is opened.** The next study is Family 2 (Form 4)
  or the programme stops. There is no fourth family (§21).

---

## 9. Recording

Before the first computation: this document is committed. After: results are written to
`alpha/out/v3_family1_development.json` and `.pkl` (per-cutoff series, so every headline
number is re-derivable from per-cutoff data rather than from a summary), the registry
entry in `reports/EXPERIMENT_REGISTRY.md` §6.2 is completed with its decision and reason,
and `alpha/V3_EXPERIMENT_LOG.md` records every run **including aborted and superseded
ones** (§2.7).

The diagnosis recorded on rejection must distinguish: did the *information* fail, or the
target, the horizon, the point-in-time quality, the coverage, the economic significance,
or the **power**? A family killed by insufficient resolution was never tested — and it
still spends its slot.

---

## 10. Amendment A1 — Criterion 2 wording. **Prospective only.**

**Dated 2026-08-09.** Made **after** Family 2 returned REJECT and **before** any Family 3
data was fetched, preprocessed, inspected or tested. This is the **only** amendment to
this document.

### 10.1 The change, in full

| | |
|---|---|
| **Original wording (§6.3 clause 2)** | "its **95% block-bootstrap CI excludes zero**" |
| **Amended wording (§6.3 clause 2)** | "its **95% block-bootstrap CI excludes zero on the favourable side**" |

The original wording is preserved verbatim in the table above **and** inline at §6.3
itself, so the text Families 1 and 2 were judged under stays readable in place.

### 10.2 Why

The rule as originally written is **direction-blind**. Family 2's primary contrast came in
at **−0.00096 with a CI of [−0.00187, −0.00004]** — an interval that excludes zero
*entirely below it*. A mechanical evaluation therefore recorded criterion 2 as **PASS**
for what was in fact that study's clearest evidence **against** the family. The overall
decision was REJECT regardless, because criteria 1, 3 and 4 all failed, so **nothing about
Family 2's outcome turned on this defect** — but a future reader seeing a "3 FAIL / 1
PASS" tally could mistake a four-way failure for a near miss.

"On the favourable side" means: for a contrast whose CONTINUE direction is positive, the
**entire** interval must lie **above** zero. An interval lying entirely below zero is a
**FAIL** of criterion 2, not a pass.

### 10.3 What this amendment does NOT do

* It does **not** change Family 2's result, tally, decision, commit, artefacts, or
  eligibility. **Family 2 remains REJECTED and its four-criterion tally stands exactly as
  recorded** in `alpha/V3_FAMILY2_REPORT.md` and
  `alpha/out/v3_family2_development.json`. Neither file is touched by this amendment.
* It does **not** change Family 1's result or tally. Family 1 is likewise judged under the
  original wording.
* It does **not** change any threshold (+0.010 stands), the MDE (+0.007 stands), the
  horizon, λ, the noise-control procedure, the Holm–Bonferroni procedure, sample handling,
  any other clause of the CONTINUE rule, any feature definition, any learner, or the
  three-family budget rule. **Criteria 1, 3 and 4 are untouched.**
* It does **not** re-open, re-run or re-interpret any completed study. §21 still bars a
  Family 1′ or Family 2′, and **budget slots stand at 2 spent, 1 remaining.**
* It does **not** touch the exam, which remains sealed at `b55e065f4c9f9173`, or the
  production weight, which remains `0.0`.

### 10.4 Implementation note for Family 3

`alpha/v3_family1.py` and `alpha/v3_family2.py` encode criterion 2 as
`bool(lo > 0.0 or hi < 0.0)`. **Those two modules are deliberately left unmodified**, so
that re-running either family reproduces its recorded result exactly. Family 3's study
module must instead encode the amended rule directly:

```python
"2_ci_excludes_zero_favourably": bool(lo > 0.0)
```

Copying Family 2's inline criteria block without applying this change would silently
reintroduce the direction-blind test.
