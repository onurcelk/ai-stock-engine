# Family 10 — Stage 3: block structure and the §2.6 power gate

**Written 2026-08-11. NON-PREDICTIVE.** No forward return of this family is read
anywhere in this stage. The only distributional inputs are the **marginal
properties of the target** already measured and committed in
`alpha/source_probe.py` at `4a966a2` — no feature, no conditioning, no outcome
of Family 10.

**This document is committed in two parts, deliberately.** §1–§3 — the block
freeze and the independent-unit census — are committed **before any half-width
exists**. §4 — the half-widths and the verdict — is appended in a second commit.
The git history is the evidence that the ordering held, exactly as
`reports/V4_SUE_POWER_GATE.md` did it.

Stage 1 was committed at `cc2613b`, Stage 2 at `e02d857`.

Reproduce:

```
./venv/Scripts/python.exe -W ignore -m alpha.family10_power --freeze
./venv/Scripts/python.exe -W ignore -m alpha.family10_power --gate     # part 2 only
```

---

## 1. The block length, frozen before any half-width

Family 10 samples in **event time**, not on the 5-session cutoff grid, so the
dependence structure is not the one V3 and V4 faced and the block cannot be
inherited unchanged.

### 1.1 Mechanical overlap

Two events on sessions `s₁ < s₂` share forward sessions whenever
`s₂ − s₁ < HORIZON`:

| Sessions apart | Shared sessions of the 5 | Shared fraction |
|---:|---:|---:|
| 1 | 4 | 0.80 |
| 2 | 3 | 0.60 |
| 3 | 2 | 0.40 |
| **4** | **1** | **0.20** |
| ≥ 5 | 0 | 0.00 |

**Highest lag carrying mechanical overlap: q = 4 sessions.** V3's grid study had
**q = 0**, because its cutoffs were spaced exactly one horizon apart —
`alpha/dataset.py` and `alpha/stats.py` both say so. Event time removes that
protection: events land on adjacent days.

### 1.2 The record's own persistence allowance

`alpha/stats.py` sets `BLOCK_LENGTH = 4` and names the span in its own words:
*"moving-block bootstrap, block length 4 cutoffs (~one month)"*, applied where
*"the mechanical overlap §5 warns about is absent by construction; what remains
is the market's own persistence, which is what these intervals are for."*

At `H = 5` with `q = 0`, the whole **20 sessions** was a persistence allowance.
The market is the same market and the horizon is the same horizon, so the same
allowance applies here — now on top of an overlap that did not exist there:

```
L  =  q  +  the record's persistence allowance  =  4  +  20  =  24 sessions
```

### 1.3 The independent rule, which lands in the same place

The moving-block rule of thumb is `L ≈ n^(1/3)` in the units of the resampling
*observation*. V4-SUE's observations were cutoffs: `313^(1/3) = 6.79 → 7`
cutoffs. Family 10's are **event sessions**, of which the panel has **1,221**:

```
1221^(1/3)  =  10.69 event sessions
2664 / 1221 =  2.182 calendar sessions per event session
10.69 × 2.182 = 23.32  →  24 calendar sessions
```

### 1.4 The freeze

> **SELECTED BLOCK LENGTH: L = 24 sessions. D = 2,664 // 24 = 111 blocks.**
> **Frozen here, before any half-width has been computed.**

Two derivations — the overlap structure plus the record's own standard, and the
`n^(1/3)` rule — give **24** and **23.3**. They agree, so `alpha/V4_CHARTER.md`
§6.1's tie-break (take the longer where the evidence does not clearly favour the
shorter) is not even needed.

**Against the survey's own pre-declaration.**
`reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §1.1 declared 532 five-session blocks
and 266 ten-session ones, with *"the conservative column governs the verdict"*.
**111 is more conservative than both**, and it was reached from the dependence
structure rather than from either figure. Both survey columns are reported in §4
so the cost of the choice is visible, but **only L = 24 decides.**

L = 24 is used for the gate. No other value may be substituted, and a half-width
computed at any other length is a diagnostic, not a result.

---

## 2. The three nested samples

| sample | events | issuers | sessions | what it is |
|---|---:|---:|---:|---|
| **all events** | **1,682** | 477 | 1,221 | the Stage 1 panel |
| **panel-priceable** | **1,478** | 407 | 1,118 | …on a name `alpha/universe.py` admits — bars, 252 sessions of history, $3M median dollar volume, $3 price |
| **primary — development-safe** | **687** | 316 | 520 | …and ≥ `examset.MIN_SEPARATION` = 10 sessions from every one of the 72 sealed exam cutoffs |

The third is the **primary** sample and it governs the verdict. Its two
reductions are different in kind and both are disclosed rather than absorbed:

* **1,682 → 1,478 (−12.1%)** is the pricing survivorship channel Stage 2
  measured. It cannot be repaired from free data: a company whose bars no longer
  exist has no computable forward return, however well its CIK is identified.
* **1,478 → 687 (−53.5%)** is the **sealed exam**. Seventy-two exam cutoffs each
  carry a ±9-session guard band, which is 51% of the 2,664-session calendar.
  This is the price of the exam being sealed, and it is paid here rather than
  argued away. A family preregistered with its own hold-out design would keep
  the 1,478; that is a question for a preregistration, not a licence to quote
  the larger number now.

The exam itself was **not opened**: digest
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, and only the
cutoff *dates* were read, which is calendar arithmetic.

---

## 3. Independent information units

> 2,000 events on a small number of dates are not 2,000 draws.

| | all events | panel-priceable | **primary** |
|---|---:|---:|---:|
| Events | 1,682 | 1,478 | **687** |
| Unique event sessions | 1,221 | 1,118 | **520** |
| Unique issuers | 477 | 407 | **316** |
| Blocks occupied (of 111) | 111 | 111 | **110** |
| Events per occupied block, mean | 15.15 | 13.32 | **6.25** |
| …median / max | — / 28 | — / 25 | — / **20** |
| Issuers per occupied block, mean | 14.44 | 12.68 | **6.09** |
| **Largest single block's share** | 1.66% | 1.69% | **2.91%** |
| Events per date, mean / max | 1.38 / 5 | 1.32 / 5 | **1.32 / 4** |
| Share of dates with exactly one event | 71.3% | 72.3% | **75.4%** |
| Events per issuer, mean / max | 3.53 / 20 | 3.63 / 20 | **2.17 / 10** |
| **Largest single issuer's share** | 1.19% | 1.35% | **1.46%** |
| Top-10 issuers' share | 8.68% | 9.88% | **10.77%** |
| Same-issuer consecutive pairs | 1,205 | 1,071 | **371** |
| …closer than the horizon | 31 | 26 | **9** |
| …inside one 24-session block | 143 (11.9%) | 126 (11.8%) | **27 (7.3%)** |

Three properties matter and all three hold on the primary sample:

1. **The panel is date-spread, not date-clustered.** 520 distinct sessions carry
   687 events; three quarters of those sessions carry exactly one. Nothing here
   resembles a handful of dates dressed up as hundreds of observations.
2. **No issuer carries the family.** The largest contributes 1.46% and the top
   ten 10.8% — comparable to the full panel, so the exam guard bands did not
   concentrate it.
3. **Within-block repetition is small.** 27 of 371 consecutive same-issuer pairs
   (7.3%) fall inside a single block, which is *less* than on the full panel —
   the block absorbs them by construction, which is what it is for.

**Effective independent-date count: 110 occupied blocks of 111 available.** That
is the number the gate is computed on, and it is fixed before any half-width
exists.

---

## 4. The power gate

**Appended in a second commit.** §1–§3 above were committed at `b75a70e` with no
half-width in the artefact — a test asserts that
`alpha/out/family10_block_freeze.json` contains no key matching `half_width`,
`mde`, `verdict`, `passed` or `detectable`, and `--gate` refuses to run if
`BLOCK_LENGTH` has moved since the freeze.

### 4.1 The hurdle, quoted from before the pilot

`reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §1.2, committed at `4a966a2`:

| Claim | Requirement |
|---|---|
| **(a)** the conditional up-rate differs from the 0.537 base rate | shift > half-width |
| **(b)** the conditional up-rate is credibly below 0.50 — *the prize Phase 1 could not produce* | shift > 3.7 pp + half-width |
| **(c)** economically useful absolute return | **> ~39 bp per 5 sessions** (Phase 1's covered-book resolution) |

And §3.3 of the same survey applied (c) as a pass/fail test in exactly this
form: *"The clean-negative pool resolves to **27.7–35.6 bp**, inside Phase 1's
39 bp. **Clears.**"*

**39 bp is therefore a pre-declared number, not one chosen here.** A gate has
teeth only if failing it has consequences (`CLAUDE.md` §3.1), and it may not be
weakened after seeing a result that would fail it (§3.2).

### 4.2 The measurement

Variance inputs, all marginal properties of the target already committed in
`alpha/source_probe.py` — no feature, no conditioning, no outcome of this
family: `sd = 0.04526`, `ρ = 0.2916`, `up-var = 0.24783`, `up-ρ = 0.1778`,
block-bootstrap inflation `1.077` calibrated against Phase 1's *measured*
half-width.

At the frozen **L = 24, D = 111**:

| sample | n | **return MDE** | up-rate MDE | sub-50% needs |
|---|---:|---:|---:|---:|
| all events | 1,682 | **52.7 bp** | 4.80 pp | 8.50 pp |
| panel-priceable | 1,478 | **53.2 bp** | 4.88 pp | 8.58 pp |
| **primary — development-safe** | **687** | **57.8 bp** | **5.56 pp** | **9.26 pp** |

Against the survey's own predictions for this family — **27.7 bp** at 532 blocks
and **35.6 bp** at 266 — the repaired panel resolves **57.8 bp**. The survey
over-estimated the family's resolution by a factor of **1.6–2.1**, and every
component of the gap is something Stages 1–3 measured rather than assumed:
2,419 → 687 usable events, and 532/266 → 111 independent blocks.

### 4.3 Robustness — the verdict does not turn on the block choice

Computed after the freeze, unable to change it:

| L | blocks | primary MDE | all-events MDE | |
|---:|---:|---:|---:|---|
| **5** | 532 | **38.0 bp** | 29.7 bp | the only length that clears |
| 7 | 380 | 40.5 bp | 32.9 bp | fails |
| **10** | 266 | **44.1 bp** | 37.2 bp | fails — *and this is the survey's own conservative column* |
| 14 | 190 | 48.4 bp | 42.3 bp | fails |
| 21 | 126 | 55.3 bp | 50.0 bp | fails |
| **24** | **111** | **57.8 bp** | 52.7 bp | **frozen — fails** |
| 30 | 88 | 63.0 bp | 58.4 bp | fails |

**The family clears 39 bp at exactly one block length: L = 5** — the choice with
*zero* allowance for market persistence, which contradicts `alpha/stats.py`'s own
standard and which the survey itself declined to let govern (*"the conservative
column governs the verdict"*). At the survey's conservative L = 10 the primary
sample already reads 44.1 bp. **The failure is not an artefact of freezing L at
24.**

### 4.4 The structural reason, which no amount of data repairs

Because the bracket in the resolution formula tends to `ρ` rather than to zero,
the half-width does **not** go to zero as events accumulate — the common market
move never diversifies away. The floor, as the event count grows without bound:

| L | blocks | **half-width floor** |
|---:|---:|---:|
| 5 | 532 | 22.4 bp |
| 10 | 266 | 31.6 bp |
| **24** | **111** | **49.0 bp** |

> **At the frozen block length, 39 bp is unreachable at any event count.** Not
> difficult — unreachable. Collecting every 8-K ever filed by every issuer would
> not get there, because the binding constraint is the number of independent
> time blocks the 2016–2026 window contains, and that is 111.

This is the source survey's own §1.1 structural result — *"resolution is bought
with independent dates, not with more names per date"* — turned around and
applied to the family the survey recommended. The survey believed event-time
sampling bought 532 or 266 blocks. Once the block length is set by the
dependence structure the sampling actually has, it buys **111**.

### 4.5 The other two claims

* **Claim (b), the sub-50% group.** Needs a **9.26 pp** shift. The survey put
  this at 6.4–7.0 pp and already called it **BORDERLINE**. It is now half again
  as far away. This is the claim the family was selected for — the thing Phase 1
  could not produce and the only reason 8-K adverse items outranked larger and
  cleaner candidates (survey §5, *"sign is the binding scarcity"*).
* **Claim (a), a conditional up-rate different from 0.537.** Needs **5.56 pp**,
  against the survey's 2.73–3.34 pp. A 5.6 pp swing in the five-session
  direction of a stock is not what the literature documents for 8-K drift; and
  **61.1% of these filings are accepted after the close (measured, Stage 1)**, so
  the instantaneous reaction is structurally unavailable and only residual drift
  is capturable — the survey's own §7.1 says so.

**"The effect might be huge" is not available as an argument.** The pilot
directive forbids it, and the after-close measurement is the specific reason it
would be wrong here.

### 4.6 Stage 3 gate

```text
FAMILY10 STAGE 3: FAIL — POWER
```

| claim | needs | has | |
|---|---:|---:|---|
| (c) economic return, hurdle 39 bp | ≤ 39.0 bp | **57.8 bp** | **FAIL** |
| (b) credible sub-50% group | 9.26 pp shift | survey called 6.4–7.0 pp borderline | not reachable |
| (a) up-rate differs from 0.537 | 5.56 pp shift | survey predicted 2.73–3.34 pp | not plausible |

**Stage 4 (the PIT invariance proof) is not reached.** The pilot directive is
explicit: *"If underpowered: FAMILY10 PILOT: FAIL — POWER. Commit and stop."*

**Family slot spent: NO.** No predictive experiment was implemented, no forward
return was read, no sign was fitted, the sealed exam was never opened, and
production weight remains 0.0.

---

## 5. Artefacts

| file | content |
|---|---|
| `alpha/family10_power.py` | the two-mode module: `--freeze` (no half-width) then `--gate` |
| `alpha/out/family10_block_freeze.json` | the frozen block length and the independent-unit census, with no MDE in it |
| `alpha/out/family10_power_gate.json` | the half-widths, the sensitivity table and the floors |
| `app/tests/test_family10_power.py` | 20 tests, including the assertion that the freeze artefact carries no half-width |
