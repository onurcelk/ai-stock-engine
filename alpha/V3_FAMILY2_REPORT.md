# V3 Family 2 — Form 4 insider open-market purchases: **REJECT**

**Run 2026-08-09** on explicit authorization to spend the slot. Pre-registration
`alpha/V3_FAMILY2_PREREGISTRATION.md`, IN FORCE and unedited since. Reproduce with
`./.venv/Scripts/python.exe -W ignore -m alpha.v3_family2`.

> # DECISION: REJECT. **Budget slot 2 of 3 is SPENT.**
>
> **Spent: 2 (Family 1, Family 2). Remaining: 1.**
>
> Three of the four CONTINUE criteria fail. The fourth passes mechanically **in the wrong
> direction** (§3.1). No threshold, criterion, benchmark or stopping rule was modified
> before, during or after the run. The exam was never opened. Nothing was pushed.
>
> **No Family 2′ may be opened** (§2.9, §21): not with sales included, not with role
> weighting, not at another window, not at another horizon, and **not with the sign
> flipped** — see §4.3.

---

## 1. What was run

Exactly what §8 of the pre-registration declared, no more and no less. Every scoring
helper is **imported from `alpha/v3_family1.py`** rather than re-implemented, so "the same
protocol as Family 1" is a property of the code rather than a claim in a comment.

| | |
|---|---|
| Development cutoffs | **316**, exam contamination **0**, digest `b55e065f4c9f9173` |
| Rows | 143,675 |
| Target / horizon | `alpha_5d`, **5 sessions** (§10.1) |
| λ | **0.25**, fixed, not scanned |
| Feature sign | **+1**, economic prior, not estimated |
| Winsorisation | **none** — §2 fixes none, unlike Family 1's 1% |
| Feature non-zero | 0.135, median **62 names** per cutoff |

## 2. Results

| | mean IC | half-width | 95% CI | hit |
|---|---|---|---|---|
| b1 12-1 momentum | +0.01000 | 0.02386 | [−0.01342, +0.03430] | 0.532 |
| b2 5d reversal | +0.00675 | 0.01836 | [−0.01062, +0.02610] | 0.509 |
| b3 regime rule (incumbent) | +0.02241 | 0.02328 | [−0.00086, +0.04570] | 0.560 |
| **Arm 0 — raw insider rank** | **−0.00547** | 0.00714 | **[−0.01278, +0.00151]** | 0.478 |
| Arm 1 — B3 + 0.25 tilt | +0.02146 | 0.02306 | [−0.00154, +0.04457] | 0.551 |

**Primary contrast, Arm 1 − B3: −0.00096, half-width 0.00092, CI [−0.00187, −0.00004],
breadth 0.4177, n = 316.**

**Noise control PASSED** — 30 paired within-cutoff permutations, median −0.00046, sd
0.00046, **0.0%** of draws above threshold. The control behaved as a control.

**Holm–Bonferroni across the two arms:** neither is significant (p_holm 0.0752 for both).

**Net of costs:** Arm 1's gross spread advantage over B3 is **−0.00006**, net
**−0.000058**, on +0.3 pp of extra turnover. **The sixth consecutive time this programme
has measured a tilt that does not pay for its own trading.**

## 3. The CONTINUE rule, evaluated mechanically

| Criterion | | |
|---|---|---|
| 1 — effect ≥ +0.010 | **FAIL** | −0.00096 |
| 2 — CI excludes zero | **"PASS"** | [−0.00187, −0.00004] — **see §3.1** |
| 3 — breadth > 0.50 **and** both halves positive | **FAIL** | breadth 0.4177; halves −0.00094 / −0.00097 |
| 4 — survives with BEAR removed | **FAIL** | ex-bear −0.00115 |

### 3.1 Criterion 2 passes in the wrong direction, and that is not a technicality

The pre-registered rule says "the CI excludes zero". It does — **entirely below it.** The
rule as written is **direction-blind**, so a mechanical evaluation records PASS for what is
in fact the study's clearest negative finding: **adding insider purchases to B3 makes it
reliably, if slightly, worse.**

**The rule is reported exactly as written and was not amended** — rewriting a criterion
after seeing which way it pointed is precisely the retrofit this protocol exists to
prevent, and the decision is REJECT either way. It is flagged here so that no future
reader mistakes a "3 FAIL / 1 PASS" tally for a near miss. **The honest count is four
failures, one of them disguised.**

Recommend fixing the wording for Family 3 — "the CI excludes zero **on the favourable
side**" — as a **pre-registration** change made **now, before Family 3's data is touched**,
never as an amendment to this one.

## 4. Diagnosis — which thing failed (§21 requires this)

### 4.1 Not the power — and the tightness was predicted, not lucky

The primary contrast resolved to **±0.00092**, the tightest interval this programme has
ever produced and 2.5× better than Family 1's ±0.00229. **`FAMILY2_ADMISSIBILITY.md` §8
predicted exactly this, before the run, and warned it was not a good sign:** with 86% of
the cross-section tied at zero, Spearman(Arm 1, B3) = 0.9896 and the tilt replaces only
5.4% of the traded book. An arm that barely differs from its base resolves tightly because
there is little to resolve. **§2.12's "a free power gain is a warning" was correct, and it
was on the record beforehand.**

### 4.2 Not the point-in-time quality

The acceptance-time door is tested (`test_alpha_filings.py`, 43 tests passing including
the 15:59:59-in / 16:00:00-out boundary), 0 filings entered without an acceptance
timestamp, and 77.3% of Form 4s would have leaked under a `filed <= cutoff` rule that was
never used.

### 4.3 The information failed — and unlike Family 1, it failed at the root

**Family 1's SUE cleared zero standalone** (IC +0.01305, CI [+0.00263, +0.02339]) and lost
only when asked to add something to B3. **Family 2's feature does not clear zero at all:**
IC **−0.00547**, CI **[−0.01278, +0.00151]**, hit rate **0.478** — below half.

**The point estimate is also the opposite sign to the pre-registered prior.** §8 fixed the
sign at **+1** on the economic prior that insiders buy on good news; the measured
standalone IC is negative, though its interval includes zero, so the honest reading is
**"no signal", not "an inverted signal".**

> **The sign may not be flipped and re-run.** That is a Family 2′ under §2.9/§21, it is
> barred, and the temptation is exactly why the sign was pre-registered. A −0.00547 with a
> CI spanning zero is not evidence for an inverted factor; it is evidence of nothing.

### 4.4 The structural finding: this feature cannot form a short book

Measured across all 316 cutoffs: the **lowest** percentile rank any name receives is a
median of **0.4308** (min 0.3582, max 0.5010). The tied zero block occupies the bottom
~86% of the cross-section, and under the average-tie rule §5 pre-registered, that block
lands near the middle.

> **No name reaches the bottom quintile at any of the 316 cutoffs.** Arm 0's top-minus-
> bottom spread is therefore **undefined everywhere — n = 0 of 316**, which is why it
> prints as `nan` in the run output.

This is a consequence of the pre-registered design, not a defect in it: §5 recorded the
point mass at zero and the large tied block in advance. But it means the feature was never
capable of expressing a short leg. It sharpens Family 1's lesson rather than repeating it —
there, an IC cleared zero while the spread did not; **here the spread cannot be computed at
all.**

### 4.5 A correction to a pre-committed number

§10.3 pre-committed that the four data-truncated cutoffs would leave an **effective
n = 312**. That is correct for **Arm 0's own IC (n = 312)** but **not** for the primary
contrast, which ran at **n = 316**. At an all-zero cutoff the feature's rank is uniformly
0.5, so `λ·(rank − 0.5)` is exactly 0 and Arm 1 collapses to B3 — the paired difference is
an exact zero that is retained rather than a missing value that drops.

**The effect is negligible and dilutes toward zero rather than away from it:** rescaling to
the 312 non-degenerate cutoffs moves the primary from −0.00096 to −0.00097. **No criterion
changes.** Recorded because the pre-commitment was specific and turned out to be
imprecise.

## 5. What survives the rejection

1. **`alpha/build_insider.py` and the purchase table.** 19,347 open-market purchases, 561
   of 619 issuers, 42 quarterly archives, 0 dropped for a missing acceptance timestamp.
   Regenerable; the bulk archives are gitignored.
2. **A measured negative that closes a popular question.** "Insiders are buying" is one of
   the most widely repeated retail signals. On this universe, at this horizon, as a
   scale-normalised 90-day purchase intensity, **it does not rank the cross-section** —
   IC −0.00547 with a CI spanning zero — and it cannot be traded as a long-short.
3. **The §2.12 mechanism, now demonstrated twice.** A bounded tilt on a strong base buys
   resolution by giving up authority. Predicted before this run and confirmed by it.
4. **The correlation structure.** Insider purchases run *contrarian* to momentum
   (mean ρ −0.1310 against `z__ret_12_1`) — genuinely distinct information that still
   carries no forward signal. Being uncorrelated with the incumbent was never sufficient.

## 6. Status

| | |
|---|---|
| **Budget slots** | **2 SPENT** (Family 1, Family 2), **1 REMAINING** |
| Family 2′ | **barred** (§2.9, §21) — including a sign flip |
| Next | **Family 3, or stop.** If Family 3 also fails, §21 requires concluding the *formulation* is wrong and stopping — not opening a fourth |
| Exam | **sealed**, `b55e065f…`, never opened |
| Production | weight **0**, action HOLD, `alpha/adapter.py` untouched |
| Thresholds / criteria / benchmarks / stopping rules modified | **None** |
| Pushed | **No** |

Artefacts: `alpha/out/v3_family2_development.json` (summary),
`alpha/out/v3_family2_development.pkl` (per-cutoff IC series, the primary series, and the
30 noise draws — every headline number above is re-derivable from per-cutoff data).
