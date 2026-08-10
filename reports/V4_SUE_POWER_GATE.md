# V4-SUE — §6 power gate

**Computed 2026-08-10. GATE ONLY.** V4-SUE is **not run**, **not pre-registered as a
study**, and **V4 Slot 1 is NOT spent**. No V3 artefact, no V4 charter clause, no
threshold, no arm, no budget and no production setting is modified by this work. The exam
is not opened. Nothing is pushed.

Run under `alpha/V4_CHARTER.md` §6, which is a blocking pre-study gate: *"No V4 slot may
be spent before a fresh, exact §2.6 power gate for this exact design passes."*

**This document is committed in two parts, deliberately.** Sections 1–3 (the block-length
freeze and the mechanical cutoff count) are committed **before** any half-width is
computed, so that the block length cannot have been chosen to make the gate pass. Section
4 (the half-width and the verdict) is appended in a second commit. The git history is the
evidence that the ordering held.

---

## 1. The criterion, quoted

From `alpha/V4_CHARTER.md` §5 and §6.2:

| | |
|---|---|
| Frozen MDE | **+0.0095 IC, native 20-session units**, versus B3 |
| Primary contrast | Arm 1 − B3, paired per cutoff |
| Arm 1 | `rank_pct(B3) + 0.50·(rank_pct(sue) − 0.5)`, λ = 0.50 fixed |
| Horizon | 20 sessions |
| **PASS** | achieved 95% paired block-bootstrap half-width **≤ +0.0095** |
| **FAIL** | anything else. No discretionary override |

The charter's §6.2 also states, in advance of this computation: *"This gate is more likely
to fail than to pass."*

---

## 2. Step 1 — the bootstrap block length, frozen before any half-width exists

### 2.1 The measured overlap structure (mechanical, no target read)

The 316 frozen development cutoffs sit on a 5-session grid. A 20-session outcome window
therefore shares calendar sessions with its neighbours:

| Cutoff separation k | Sessions apart | Shared sessions of the 20 | Shared fraction |
|---|---|---|---|
| 1 | 5 | 15 | 0.75 |
| 2 | 10 | 10 | 0.50 |
| 3 | 15 | 5 | 0.25 |
| **4** | **20** | **0** | **0.00** |
| ≥ 5 | ≥ 25 | 0 | 0.00 |

**Highest lag carrying mechanical overlap: q = 3.**

**The V3 comparison that sets the standard.** At H = 5 on the same 5-session grid, q = 0 —
outcome windows are exactly adjacent and non-overlapping, as `alpha/dataset.py` and
`alpha/stats.py` both document. The record nonetheless chose `BLOCK_LENGTH = 4`, and its
stated reason was **not** mechanical overlap (there was none) but *"the market's own
week-to-week persistence"* — a four-cutoff, roughly one-month allowance on top of zero
overlap.

### 2.2 The three pre-declared candidates, assessed on dependence structure only

A moving block of length L preserves, within blocks, autocorrelations at lags 1 … L−1.

| L | Calendar span of a block | Lags preserved | Covers mechanical q = 3? | Persistence allowance on top of overlap | Assessment |
|---|---|---|---|---|---|
| **4** | 4 cutoffs ≈ 20 sessions (~1 month) | 1–3 | Yes, exactly | **0 cutoffs** | Covers the mechanical overlap and *nothing else*. **Strictly less conservative at H = 20 than L = 4 was at H = 5**, where the same value bought a 4-cutoff persistence allowance against zero overlap. Defensible only if one asserts the market has no persistence beyond the overlap itself — an assertion the record already rejected at H = 5 |
| **5** | 5 cutoffs ≈ 25 sessions | 1–4 | Yes, +1 slack | **1 cutoff** | Better than 4. Still concedes three quarters of the persistence allowance the record deemed necessary at the shorter horizon. No independent rule selects it |
| **7** | 7 cutoffs ≈ 35 sessions (~7 weeks) | 1–6 | Yes, +3 slack | **4 cutoffs — matches the record's own H = 5 standard** | Reproduces the record's construction exactly: mechanical overlap (q = 3) **plus** the same 4-cutoff persistence allowance `BLOCK_LENGTH = 4` encoded when q was 0 |

### 2.3 An independent rule that lands on the same value

The standard moving-block rule of thumb for bootstrapping a mean is L ≈ n^(1/3). At the
usable count established in §3, **313^(1/3) = 6.79 → 7**.

Two derivations reached independently — the record's own overlap-plus-persistence
construction, and the n^(1/3) rule — both give **7**.

### 2.4 The freeze

> **SELECTED BLOCK LENGTH: L = 7. Frozen here, before any half-width has been computed.**

Reasons, in order: (i) it is the only candidate that reproduces the persistence allowance
the record itself applied at H = 5, now added on top of a mechanical overlap that did not
exist there; (ii) the n^(1/3) rule independently gives 6.79; (iii) `V4_CHARTER.md` §6.1
requires that where more than one length is defensible and the evidence does not clearly
favour the shorter, **the more conservative longer length is chosen** — and nothing in the
overlap structure favours 4 or 5.

**L = 7 is used for the gate decision. No other value may be substituted, and a half-width
computed at any other L is not a gate result.**

### 2.5 A structural caveat, recorded

The usable cutoffs are **not** evenly spaced (§3): 240 consecutive pairs are 5 sessions
apart and 72 are 20 sessions apart, the latter being the holes left where exam cutoffs and
their guards were purged. The moving-block bootstrap treats the series as evenly spaced in
index terms, so a block of 7 spans a variable calendar length. This makes some blocks
group observations that are *less* dependent than assumed, which widens rather than
narrows the interval relative to an exactly-spaced series. It is therefore conservative in
the direction that matters and is not a reason to shorten L.

---

## 3. Step 2 — the usable cutoff count, determined mechanically

Computed with `book.horizon_end(cutoff, 20)`, the tested instrument. No return value, no
feature and no IC is read.

| | |
|---|---|
| Frozen development cutoffs | **316** |
| Exam cutoffs present in that list | **0** (asserted) |
| Carrying a complete 20-session forward window | **313** |
| Dropped — window runs past the end of price history | **3**: 2026-07-14, 2026-07-21, 2026-07-28 |
| Usable span | 2016-01-04 … 2026-07-07 |
| Price calendar ends | 2026-08-07 |

**Nominal usable n = 313.**

### 3.1 An observation that bears on the charter's §10, recorded but not acted on

The gap census shows 72 consecutive-pair gaps of exactly 20 sessions — one per exam
cutoff. A 20-session gap between retained development cutoffs means the purge removed
three grid positions, i.e. development cutoffs sit as close as **10 sessions** either side
of an exam cutoff (`MIN_SEPARATION = 10` is inclusive).

`V4_CHARTER.md` §10.1 estimated the 20D development/exam window overlap at 5 sessions,
reasoning from a retained neighbour 15 sessions away. The true nearest retained neighbour
is **10 sessions** away, so the overlap at a 20-session horizon is **10 sessions — half
the outcome window**, not five.

**This strengthens the charter's conclusion and changes none of its decisions.** The
charter is not edited (its §10 position — exam stays sealed, not valid as constituted for
20D — is unchanged and now rests on a larger defect). Recorded here so the sharper number
is on the record.

---

## 4. Step 3 — the achieved half-width and the verdict

**Appended 2026-08-10 in the second commit, after §2's block-length freeze was committed.**

### 4.1 How the effect was kept out of this section

Charter §6.1(2) permits the gate to inspect variance and dependence and forbids it to
compute, report or inspect any predictive point estimate. The enforcement is structural
rather than a promise:

The paired per-cutoff series `d_t = IC(Arm 1)_t − IC(B3)_t` is formed and **immediately
centred**, and only the centred series reaches any downstream computation or artefact. A
percentile block-bootstrap interval shifts one-for-one with a constant added to its input,
so its **width is exactly invariant to centring** — the half-width below is identical to
the half-width of the uncentred series, while the effect is discarded before anything can
read it. `alpha/out/v4_sue_power_gate.pkl` stores the centred series only; the JSON record
carries no mean. **The Arm 1 − B3 point estimate has not been computed into any inspected
variable, printed, persisted, or used in the verdict.**

### 4.2 Inputs

| | |
|---|---|
| Target | 20-session forward alpha, built by `targets.realise(..., horizon=20)` — the existing tested instrument, reused not rewritten |
| Rows | 142,178 across **313** cutoffs |
| `corr(alpha_5d, alpha_20d)` | **0.4962** — confirming these are distinct dependent variables sharing only their first five sessions, as charter §2.3 asserts |
| SUE coverage on the 20D rows | **0.9299** — clears the charter §5 item 13 gate of ≥ 0.80 |
| Arm 1 | `rank_pct(B3) + 0.50·(rank_pct(sue) − 0.5)`, λ = 0.50, sign +1 |
| Exam contamination | **0**, asserted before scoring |

### 4.3 Dependence structure of the paired difference (measured)

| Lag | Autocorrelation | |
|---|---|---|
| 1 | **+0.5244** | mechanical overlap (0.75 of the window shared) |
| 2 | **+0.2812** | mechanical overlap (0.50 shared) |
| 3 | **+0.0733** | mechanical overlap (0.25 shared) |
| 4 | −0.0311 | no overlap |
| 5 | −0.0344 | no overlap |
| 6 | −0.0573 | no overlap |
| 7 | −0.0144 | no overlap |
| 8 | −0.0285 | no overlap |

**The measured structure matches the predicted structure exactly.** Autocorrelation decays
monotonically across lags 1–3, in the same order as the shared-window fractions
(0.75 / 0.50 / 0.25), and vanishes into small negative noise from lag 4 — precisely where
§2.1 predicted mechanical overlap ends. The block length was frozen on this structure
before it was measured, and the measurement vindicates the freeze.

### 4.4 Effective independent sample size

| Reading | Derivation | n_eff |
|---|---|---|
| Variance inflation, mechanical lags | `1 + 2·Σρ₁..₃ = 2.7578`; `n/2.7578` | **113.5** |
| Variance inflation, through lag 6 | `1 + 2·Σρ₁..₆ = 2.5124`; `n/2.5124` | 124.6 |
| Block-count reading | `n / L = 313 / 7` | 44.7 |

The variance-inflation reading is the one that governs the width of a mean's interval; the
block-count reading is the coarser "how many blocks does the bootstrap have to shuffle"
figure and is quoted for completeness. Both are far below the nominal 313, which is the
§2.12 point made concrete: **nominal n is not evidence.**

### 4.5 The gate

| | |
|---|---|
| Nominal usable n | **313** |
| Selected block length | **7** (frozen in §2.4, before this computation) |
| Effective independent n | **113.5** (variance inflation, mechanical lags) |
| sd of the paired difference | 0.031503 |
| **Achieved 95% half-width** | **0.005372** |
| **Frozen MDE** | **+0.0095** |
| **MDE / half-width** | **1.7683** |
| Newey–West SE, 6 lags (cross-check) | 0.002708 → 1.96·SE = **0.005308** |

> ## VERDICT: **PASS**
>
> Achieved half-width **0.005372 ≤ +0.0095**. The design can resolve the smallest effect
> worth acting on, with a margin of **1.77×**.

**Two independent corroborations.** The Newey–West HAC interval (0.005308) agrees with the
block bootstrap (0.005372) to within 1.2%, and the closed-form check
`1.96·sd/√n·√2.7578 = 0.005796` lands in the same place. Three different corrections for
the same dependence agree, which is the condition under which a resolution figure is
worth quoting.

### 4.6 Non-decisional sensitivity

Reported for transparency. **L is frozen at 7 and the verdict above is the only gate
result.** No other value may be substituted.

| L | Half-width | MDE / half-width | |
|---|---|---|---|
| 4 | 0.005047 | 1.88 | pass |
| 5 | 0.005196 | 1.83 | pass |
| **7 — frozen** | **0.005372** | **1.77** | **PASS** |
| 10 | 0.005319 | 1.79 | pass |

**The verdict is invariant across every candidate block length, including values longer
than the one chosen.** The block-length decision was therefore not load-bearing, and
choosing the most conservative candidate cost the gate nothing. Had the ordering been
reversed — half-widths first, then a choice — this table is what would have made the
choice suspect; it is published here only because the freeze was committed first.

### 4.7 Why the charter expected a FAIL, and why it was wrong

`V4_CHARTER.md` §6.2 predicted *"This gate is more likely to fail than to pass."* **That
prediction was wrong, and the reason is identifiable rather than lucky.**

`V4_FORMULATION_REVIEW.md` §2.5 estimated the 20D λ = 0.50 half-width at ≈ 0.0092 by
taking V3's measured 0.00229 at λ = 0.25 / H = 5 and applying two multiplicative
penalties: ×2 for doubling λ, and ×2 for √(H/5). Measured, the true figure is 0.005372 —
the extrapolation **overstated the interval by 1.71×**. Both penalties were too harsh:

* **The √(H/5) penalty assumed the cutoff count falls with the horizon.** The review's §1.1
  table counted "non-overlapping draws in the span" dropping 531 → 133 and charged √4. But
  the design does not discard cutoffs at a longer horizon: **313 of 316 survive**, and the
  cost of the longer window is dependence, not lost draws. The measured variance inflation
  is **2.7578, not 4** — so the correct penalty is √2.7578 = 1.66×, not 2×.
* **Doubling λ did not double the paired standard deviation.** The review's linear
  authority-to-width extrapolation between two anchors overstated the widening.

**The correction is recorded here, and the charter is not edited.** The charter's §6.2
prediction stands in the record as written and wrong; the MDE, the arm, the horizon and
the CI rule it froze are all unchanged, and the gate was judged against them exactly as
frozen. Nothing was loosened to produce this PASS — the estimate that moved was an
estimate of the *instrument*, measured for the first time, in the direction the charter
did not expect.

---

## 5. The §7 standalone-strength screen, recorded unchanged

Carried verbatim from `alpha/V4_CHARTER.md` §7.2–§7.3. **Nothing is recomputed here and no
realized 20D value is substituted into it** — charter §7.3 forbids substituting the
measured B3 or SUE 20D figures, and none has been read.

| Quantity | Value |
|---|---|
| **R** — required standalone 20D IC at λ = 0.50 | **≈ +0.0318 native** |
| **P** — SUE's √(H/5) extrapolation from its V3 5D standalone (+0.01305) | **+0.0261 native** |
| **R / P** | **≈ 1.22** |
| Pre-registered rule | admit only if **R / P ≤ 1.5** |
| **Screen verdict** | **PASS** |

---

## 6. Status after this gate

| | |
|---|---|
| Power gate | **PASS** (half-width 0.005372 ≤ MDE 0.0095, margin 1.77×) |
| §7 screen | **PASS** (R/P ≈ 1.22 ≤ 1.5) |
| **V4-SUE** | **POWER-ADMISSIBLE — awaiting separate pre-registration authorization** |
| V4 Slot 1 | **NOT SPENT** |
| V4-SUE study | **NOT RUN** |
| V4-SUE pre-registration | **NOT CREATED** — charter §9.4 requires it as its own document, and its authorization is separate from this gate |
| V3 | CLOSED, unchanged. Families 1/2/3 REJECTED, 3 slots spent |
| Exam | **SEALED**, `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. Not opened |
| Production weight | **0.0** |
| Pushed | **No** |

Charter §9.4 fixes what may happen next and in what order: **pre-screen recorded (done) →
V4-SUE pre-registration committed as its own document → first fit.** The second of those
steps requires explicit authorization that this gate does not confer.

Artefacts: `alpha/out/v4_sue_power_gate.json` (record), `alpha/out/v4_sue_power_gate.pkl`
(centred paired series only — reproduces the half-width, carries no effect).
