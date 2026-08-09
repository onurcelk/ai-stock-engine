# V3 Pre-registration — Family 2: Form 4 insider purchases

**Design decisions taken by the account holder 2026-08-09 and frozen here before any
Family 2 performance measurement.** This document is fixed. It is not edited after a
result exists; corrections are appended, dated, and leave the original wording visible.

Family 2 of the three frozen in `reports/INFORMATION_AUDIT.md` §5.
**This would spend budget slot 2 of 3 (§21) — and it has not been spent.**

> # STATUS: NOT IN FORCE. NOT AUTHORIZED TO RUN.
>
> **§6 (primary prediction horizon) conflicts with a pre-registered rule already in
> force** — `reports/TARGET_DESIGN.md` §4.2, committed at `9532d87` before any Family 2
> work existed. The conflict is reported at §6 below and **has not been silently
> overridden**. Every other decision is frozen as written.
>
> A preregistration with an unresolved element is not a valid preregistration. Family 2
> may not run until §6 is resolved by the account holder.

---

## 1. Feature construction — FROZEN

**`insider_purchase_intensity`**, one number per (cutoff, issuer).

| Element | Decision |
|---|---|
| Transactions included | **open-market purchases of the issuer's common equity only** |
| Excluded | awards, grants, option exercises, tax withholding, gifts, transfers, and all other non-open-market transactions |
| Sales | **excluded from the primary feature** |
| Role weighting | **none** — officers, directors and 10% holders are treated identically |
| Transforms | **none** beyond the normalisation below. No nonlinear transformation |

### 1.1 The normalisation, resolved under the account holder's instruction

The instruction was: *"Use the transaction value/size and normalize it by issuer scale
using the simplest economically defensible pre-specified normalization available in the
existing data."* That delegates one bounded choice. It is resolved as:

> **purchase dollar value ÷ issuer market capitalisation at the cutoff**, where
> dollar value = shares transacted × transaction price per share (both reported on the
> Form 4), and market capitalisation = common shares outstanding × close at the cutoff.

**Economic justification, stated because §2.4 forbids choosing on performance:** a
$1m purchase means something different in a $200m company than in a $2tn one. Dividing
by market capitalisation makes the number *the fraction of the company the insiders
bought*, which is scale-free and directly interpretable. Unnormalised dollar value would
rank a signal that is mostly a firm-size proxy.

**Inputs, all already available and point-in-time:**

* shares and price per share — reported on the Form 4 itself;
* shares outstanding — `dei:EntityCommonStockSharesOutstanding`, already ingested in
  `alpha/edgar/facts.parquet`, read through the **same acceptance-time door** as every
  other filing fact (`alpha/filings.py`);
* close — `alpha/cache` at the cutoff, through `pitdata.PriceView`.

**§2.10 clause 1 note:** price and shares outstanding enter only as a *denominator*.
Insider purchase activity is not derivable from `alpha/cache`, and normalising by scale
does not make it so.

**§21 independence note:** `EntityCommonStockSharesOutstanding` is a share count, not
Family 1's information. Family 1's rejected feature was time-series SUE on
`NetIncomeLoss`; no financial-statement value enters Family 2.

## 2. Aggregation — FROZEN

> **Sum** the normalised dollar value of **every eligible open-market purchase** whose
> Form 4 is admissible at the cutoff and whose transaction falls in the lookback window,
> across all insiders of that issuer, into **one issuer-level number**.

Simple signed size-based sum. No count weighting, no decay, no winsorisation beyond what
§3 of this document fixes, no per-insider normalisation.

## 3. Availability — FROZEN, and already PASSed

Preserved exactly from `reports/FAMILY2_ELIGIBILITY.md` §2:

> **A Form 4 is admissible at cutoff *T* only if its SEC acceptance timestamp (ET) is
> strictly before 16:00 ET on *T*. The transaction date is NOT the admissibility key.**

Enforced by `alpha/filings.py` (`close_of`, `FilingsBook.view`), already tested
(`test_alpha_filings.py`, including the 15:59:59-in / 16:00:00-out boundary). Measured
basis: 77.3% of study-era Form 4 filings are accepted after the close, rising to 82.9%
by 2025, so this rule governs the large majority of the stream.

**Both timestamps are used, for different purposes, and the distinction is the rule:**
acceptance decides *whether* a filing may be seen; the transaction date decides *whether
it falls in the lookback window* once it may be seen.

## 4. Lookback window — FROZEN

> **90 calendar days**, measured backwards from the cutoff date on the transaction date.

**Chosen on economic grounds, not statistical ones.** 90 days is one reporting quarter —
the natural period over which an issuer's insiders act on a shared information set
between earnings events. **No comparison of candidate windows by coverage, half-width,
power, MDE or performance was made or may be made** (§2.4). The coverage and half-width
figures published in `FAMILY2_POWER_GATE.md` §3 and `FAMILY2_ELIGIBILITY.md` §3 are
eligibility facts and **must not be used to revisit this choice**.

## 5. Absent-insider policy — FROZEN

> If no eligible open-market purchase exists in the 90-day window, the issuer's Family 2
> signal is **exactly zero**. Nothing is imputed, filled, or replaced by another
> statistic.

This encodes "no insider bought" as the informative value it is, rather than as missing
data. **Consequence recorded in advance, so it is not discovered later and treated as a
finding:** the feature will have a large point mass at zero, so the within-cutoff rank
transform will produce a large tied block. Ties are ranked by the average method, which
places every non-purchasing issuer at the same rank. This is a property of the
pre-registered design, not a defect to be engineered around.

## 6. Primary prediction horizon — **UNRESOLVED. CONFLICT REPORTED, NOT OVERRIDDEN.**

**Instructed:** fix the primary forward horizon at **90 trading days**.

**Conflict.** `reports/TARGET_DESIGN.md` §4.2, committed at `9532d87` on 2026-08-09
*before any Family 2 work*, is already in force and states:

> Each family's preregistration names **one primary horizon** (5D or 10D), chosen on
> priors and its §2.6 arithmetic, **before the first fit**. […] 20D is available only
> under the §2.6 trade: the pre-registration must argue the expected effect ≥ ~0.015,
> twice the 5D bar.

**90 trading days is outside the permitted set**, and is 4.5× the longest horizon the
programme has ever measured. Three further consequences, computed rather than asserted:

| | H=5 | H=10 | H=20 | **H=90** |
|---|---|---|---|---|
| Non-overlapping draws in the 2,655-session development span | 531 | 266 | 133 | **29.5** |
| Each observation overlaps … others | 0 | 1 | 3 | **17** |
| Half-width, roadmap calibration (0.00827 @ 255) | 0.0057 | 0.0081 | 0.0115 | **0.0243** |
| Half-width, Family-2 calibration (0.00205 @ 316) | 0.0016 | 0.0022 | 0.0032 | **0.0067** |

1. **§2.6 may fail, and the two available calibrations disagree across the MDE.** The
   roadmap calibration gives 0.0243 — **3.5× the +0.007 MDE, a clear FAIL**. The
   Family-2-specific calibration gives 0.0067, marginally inside. **The gate cannot be
   settled between them without measuring at H=90, and that measurement does not exist.**
2. **The panel has no 90-session target.** `alpha/targets.py` sets `HORIZON = 5` and
   `alpha_5d` is the only forward alpha built; `panel_meta.json` records
   `horizon_sessions 5`, `spacing_sessions 5`, `embargo_sessions 5`. Producing an H=90
   target requires rebuilding the panel, and §0.4 warns that re-running overwrites
   frozen evidence.
3. **§2.2 purge and embargo.** At 5-session spacing with a 90-session horizon each
   observation overlaps 17 neighbours. The embargo would have to widen from 5 sessions
   to ≥90, and `alpha/stats.py`'s `BLOCK_LENGTH = 4` cutoffs would no longer span the
   induced dependence — the bootstrap would report an interval far narrower than the
   truth. **That is exactly the §2.12 failure mode: a power gain that is an artifact.**

**Not overridden. Not silently substituted. Awaiting the account holder's resolution.**
Three routes exist and each is the account holder's to choose:

* select 5D or 10D under `TARGET_DESIGN.md` §4.2 as written;
* invoke §4.2's own 20D provision, pre-registering an expected effect ≥ ~0.015;
* amend `TARGET_DESIGN.md` §4.2 deliberately and on the record — which is a change to a
  pre-registered rule and therefore explicitly outside what this session may do.

## 7. Simplicity — FROZEN

The construction in §1–§5 **is** the primary Family 2 arm, and it is the "simplest
possible version of the new information source" §2.3 requires as a mandatory baseline.

**Prohibited in this study:** machine learning of any kind, role weighting, multiple
windows, alternative transaction filters, sales-based or net-of-sales variants,
post-hoc transformations, and any second horizon.

---

## 8. Baselines, arms and metrics — inherited, and fixed here

| | |
|---|---|
| Baselines (§2.3) | **B3** (the incumbent), B1 12-1 momentum, B2 reversal, and the raw feature alone |
| Arms | **two**: Arm 0 = within-cutoff rank of the feature, sign **+1 by economic prior** (insiders buy on good news); Arm 1 = `rank(b3) + λ·(rank(feature) − 0.5)` |
| λ | **0.25**, carried unchanged from Family 1 and from the §2.6 gate's stated assumption. Not scanned as an arm |
| Primary metric | paired per-cutoff IC difference, **Arm 1 − B3** |
| Interval | moving-block bootstrap, `alpha/stats.py`, `BLOCK_LENGTH = 4`, 10,000 draws |
| §2.10 clause-3 ceilings | **≤ 0.30** mean \|ρ\| vs `z__ret_12_1`; **≤ 0.50** vs each stock-level input — carried unchanged from Family 1's preregistration, **fixed before measurement** |
| Noise control (§2.11) | 30 paired within-cutoff permutations; fails if median > +0.002 or >10% of draws clear the threshold |
| CONTINUE rule | the four-part rule of `V3_PREREGISTRATION.md` §6.3, unchanged, **with its threshold to be restated once §6 is resolved** |

## 9. Prohibitions

Carried from §0.1 and the roadmap. The exam is never opened, scored or inspected.
Production weight is not raised and `alpha/adapter.py` is not modified. No threshold is
lowered, no benchmark swapped, no B3 modified. No λ point, rung or control is promoted to
an arm. No result is restricted to a regime bucket to make it survive. Development
numbers are never reported as alpha. **If Family 2 is rejected, no Family 2′ is opened** —
the next study is Family 3 or the programme stops (§21).
