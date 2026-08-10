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

**PENDING.** Computed and appended in the second commit of this document, after the
block-length freeze above was committed.
