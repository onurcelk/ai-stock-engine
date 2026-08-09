# V3 Family 3 — 13F institutional holdings: **REJECT**. The programme ends.

**Run 2026-08-09** on explicit authorization. Pre-registration
`alpha/V3_FAMILY3_PREREGISTRATION.md`, committed at `5cb409f` **before any measurement**
and unedited since. Reproduce with `./.venv/Scripts/python.exe -W ignore -m alpha.v3_family3`.

> # DECISION: REJECT. **Budget slot 3 of 3 is SPENT.**
>
> **All three slots are now spent. Spent: 3. Remaining: 0.**
>
> **All four CONTINUE criteria FAIL.** No threshold, criterion, benchmark, budget or
> stopping rule was modified before, during or after the run. The exam was never opened.
> Nothing was pushed.
>
> **Under §21 the V3 family-testing programme is CLOSED.** No Family 3′, no fourth family.
> The comparative diagnosis §21 requires is at §8.

---

## 1. Ingest

| | |
|---|---|
| Archives | **45**, 2015q2 … filings received May 2026 (2.7 GB) |
| Event rows | **20,687,226** |
| Distinct 13F filers | **11,661** |
| Issuers mapped | **573** of 619 (**map rate 0.926**) |
| Issuers with holdings | **572** |
| Filing dates spanned | 2015-04-01 … 2026-05-29 |
| Holdings periods | 2014-12-31 … **2026-03-31** |

## 2. Mapping and integrity validation

13F identifies securities by **CUSIP** and carries no issuer CIK, so a name bridge was
required. It failed validation three times before passing, and each failure was a silent
corruption that would have invalidated the study:

| Defect | Effect | Fix |
|---|---|---|
| CUSIPs with stripped leading zeros | Abbott `002824109` arrived as `2824109`, slicing to `282410` — a different issuer | zero-pad to 9 before slicing |
| Result keyed by CUSIP | issuers silently overwrote each other: **Meta landed on JPMorgan's CUSIP**; Apple and Microsoft vanished | strict **one-to-one** assignment |
| Left-justified CUSIPs | Berkshire `084670702` arrived as `846707020`, slicing to a plausible-looking `846707` that **fails the CUSIP check digit** | validate the **modulus-10 check digit** |
| Modal-name mismatch | the real Berkshire CUSIP reads "BERKSHIRE HATHAWAY **DEL**" (29,592 filings); a junk one read exactly "BERKSHIRE HATHAWAY" (7 filings) and won the exact match | containment tier + rank by **filings held**, name match as the gate |

**Final validation: 14 hand-checked mega-cap CUSIPs, 14 correct, 0 wrong, 0 absent.**
The build **refuses to produce a feature** if this check fails. (A 15th, Exxon, is skipped
because CIK 34088 is not in this universe — that was an error in the validation list, not
in the map.)

**Period integrity.** 80 distinct periods appear, but the **46 with ≥100 filers are all
calendar quarter-ends**, contiguous from 2014-12-31 to 2026-03-31. The other 34 are late
back-filings of pre-2015 quarters (1–93 filers each), all older than the study era, so
they can never occupy the Q1/Q0 slots. Verified, not assumed.

**Point-in-time.** The door is **stricter** than Families 1 and 2': a filing is admissible
only if `FILING_DATE < cutoff`. The bulk sets carry no acceptance time and the filer
population is 11,661 institutions, so rather than approximate a timestamp (§2.1 forbids
it) the rule can only ever *delay* information. **It cannot leak.** Measured staleness of
Q1 at the cutoff: **median 92 days, p90 128** — the 45–135 the audit predicted.

**Exam contamination: 0**, asserted in code. Digest `b55e065f4c9f9173`.

## 3. Feature coverage and shape

| | |
|---|---|
| Defined (non-NaN) | **0.8556** — 20,750 NaN, never filled (§5) |
| Per cutoff | mean 0.8534, median 0.8699, p10 0.8056, **min 0.8014** |
| Names per cutoff | median **394**, p10 339, **min 323** |
| Distribution | p1 −0.2455, p25 −0.0186, median −0.0023, p75 +0.0134, p99 +0.7521 |

**Continuous, with no tie block** — unlike Family 2, whose 86% mass at zero left it unable
to form a short book. Measured coverage **0.8556 sits inside the 0.80–1.00 range the §2.6
gate was evaluated over**, so the gate's PASS holds at the realised coverage without
re-derivation.

## 4. §2.10 clause 3 — **PASS**, by the widest margin of the three families

Ceilings fixed in the pre-registration §8, **before the correlation was read**.

| | ceiling | measured | |
|---|---|---|---|
| vs `z__ret_12_1` | ≤ 0.30 | mean \|ρ\| **0.0726** (mean +0.0117, p95 0.1822, n=316) | **PASS** |
| vs each of the 34 inputs | ≤ 0.50 | highest **0.0780** (`z__overnight_share_60d`) | **PASS** |

Next: `z__sma200_dist` 0.0649, `z__rvol_20d` 0.0596. **Nothing reaches a sixth of its
ceiling.** This information is genuinely orthogonal to everything the panel already holds —
and it still carries no forward signal, which is §8's central lesson.

## 5. Admissibility — every gate

| Gate | Verdict |
|---|---|
| §2.6 power gate | **PASS**, calibrated half-width 0.00352 (coverage 0.80) to 0.00158 (1.00) vs MDE +0.007 |
| §2.10 cl. 1 not in `alpha/cache` | **PASS** — institutional holdings are no price/volume transform |
| §2.10 cl. 2 own timestamp | **PASS** — `FILING_DATE`, door stricter than acceptance |
| §2.10 cl. 3 correlation ceiling | **PASS** (§4) |
| §2.10 cl. 4 effect exceeds resolution | **PASS** on resolution |
| Turnover input to the MDE | **PASS** — extra turnover **+0.3 pp** vs a 30 pp allowance; **+0.007 MDE stands** |
| §21 independence from Families 1, 2 | **PASS** — different filer, different content |
| Mapping integrity | **PASS** — 14/14 |

**Family 3 was ADMISSIBLE. Slot 3 was then spent.**

## 6. Results

| | mean IC | half-width | 95% CI | hit |
|---|---|---|---|---|
| b1 12-1 momentum | +0.01000 | 0.02386 | [−0.01342, +0.03430] | 0.532 |
| b2 5d reversal | +0.00675 | 0.01836 | [−0.01062, +0.02610] | 0.509 |
| b3 regime rule (incumbent) | +0.02241 | 0.02328 | [−0.00086, +0.04570] | 0.560 |
| **Arm 0 — raw holdings rank** | **−0.00659** | 0.00758 | **[−0.01465, +0.00051]** | 0.475 |
| Arm 1 — B3 + 0.25 tilt | +0.01903 | 0.02368 | [−0.00477, +0.04259] | 0.541 |

**Primary contrast, Arm 1 − B3: −0.00339, half-width 0.00279, CI [−0.00631, −0.00073],
breadth 0.4494, n = 316.**

### 6.1 The four CONTINUE criteria

| Criterion | | |
|---|---|---|
| 1 — effect ≥ +0.010 | **FAIL** | −0.00339 |
| 2 — CI excludes zero **on the favourable side** (A1, `bool(lo > 0.0)`) | **FAIL** | lo = −0.00631 |
| 3 — breadth > 0.50 **and** both halves positive | **FAIL** | breadth 0.4494; halves −0.00253 / −0.00424 |
| 4 — survives with BEAR removed | **FAIL** | ex-bear −0.00377 |

> **Amendment A1 did exactly the job it was written for.** Under the old direction-blind
> wording, criterion 2 would have recorded **PASS** here — the interval excludes zero, but
> entirely below it. A1 turns that into the FAIL it always was. This is the first study
> run under A1, and it changed a criterion's recorded value on the very first use.

### 6.2 Everything else, as registered

* **Regimes:** BULL −0.00417, BEAR −0.00031, SIDEWAYS −0.00059, **EX-BEAR −0.00377**.
  Negative everywhere — no regime rescues it, and none was sought.
* **Noise control: PASS.** 30 paired within-cutoff permutations, median −0.00142, sd
  0.00118, **0.0%** of draws above threshold.
* **Holm–Bonferroni: both arms "significant"** — Arm 0 p_raw 0.0136 → p_holm 0.0272; Arm 1
  p_raw 0.0169 → p_holm 0.0272. **Both are significantly NEGATIVE.** Significance here is
  evidence against the family, not for it.
* **Turnover / net of cost:** Arm 1 extra turnover **+0.3 pp**, gross spread advantage
  −0.00015, **net −0.000148**. Arm 0: −0.002617. **The seventh consecutive time this
  programme has measured a tilt that does not pay for its own trading.**
* **Arm 0 standalone:** IC −0.00659, CI **[−0.01465, +0.00051]** — spans zero, so **"no
  signal", not "an inverted signal"**, despite a point estimate opposite the pre-registered
  +1 prior. Halves −0.00174 / −0.01144. Long-short spread −0.00064, CI [−0.00141, +0.00014].
  **The sign may not be flipped and re-run** — that is a Family 3′ and is barred.

## 7. §2.12 — the collinearity warning, third time

Spearman(Arm 1, B3) = **0.9725** per cutoff (min 0.9695) — the tilt is a *stronger*
instrument than Family 2's 0.9896, and the half-width is correspondingly wider (0.00279 vs
0.00092). **The pattern holds across all three families: a bounded tilt on a strong base
buys resolution by surrendering authority.** Resolution and authority are the same dial.

---

## 8. §21 comparative diagnosis — what failed, across three families

§21 requires the programme to distinguish which element failed. Taking each candidate in
turn, against three families' evidence:

| Candidate | Verdict | Evidence |
|---|---|---|
| **Power** | **NOT the failure** | Every family resolved far better than its MDE: half-widths 0.00229, 0.00092, 0.00279 against +0.007. The gate over-delivered every time |
| **Point-in-time quality** | **NOT the failure** | Three independent doors, all tested. 51.8% of 10-K/10-Q and 77.3% of Form 4 filings would have leaked under `filed <= cutoff`; none was used. Family 3's door is stricter still and cannot leak |
| **Coverage** | **NOT the failure** | 93% (F1), 13.6% (F2), 85.6% (F3). The best-covered and the worst-covered families failed alike, and F3's 85.6% is ample |
| **Target** | **NOT the failure** | The target is a within-cutoff Spearman IC on forward alpha — the same instrument that resolves B3 at +0.02241. It measures signal when signal is there |
| **Economic significance** | **A real failure, but downstream** | Seven consecutive tilts failed to pay their own trading. But they failed to pay because they were ~0, not because costs ate a real effect |
| **Horizon** | **A live, UNRESOLVED possibility** | All three ran at 5D. All three sources are slow — quarterly earnings, 45–135-day-stale holdings. §2.9/§21 bar re-testing any of them at 10D/20D, so **this programme cannot distinguish "no information" from "wrong horizon"** |
| **Information** | **The primary failure, and specific** | See below |

### 8.1 The information failed, and the three failed differently

* **Family 1 — real but not incremental.** SUE's own IC cleared zero (+0.01305, CI
  [+0.00263, +0.02339]) — the only factor this programme ever produced that did. It still
  added nothing to B3 (+0.00090) and its spread did not clear zero.
* **Family 2 — absent, and structurally untradeable.** IC −0.00547, CI spanning zero. 86%
  of names tied at zero, so **no name reached the bottom quintile at any of 316 cutoffs**
  and its long-short spread was undefined everywhere.
* **Family 3 — absent, and orthogonal.** IC −0.00659, CI spanning zero, at |ρ| 0.0726
  against momentum. **The cleanest test of the three** — good coverage, continuous
  distribution, the strictest door, the lowest correlation with anything already known —
  and the answer was still nothing.

### 8.2 What the evidence says is wrong with the V3 formulation

**The formulation asked the wrong question of the data, in a specific and identifiable way.**

1. **Every family was tested as a bounded tilt on a strong incumbent, and that design
   cannot express a large effect.** At λ = 0.25 the arm is 0.97–0.99 correlated with B3 by
   construction. The design was chosen because a standalone formulation fails §2.6 — but
   the escape bought resolution by giving up the authority needed to *move* anything. **The
   binding constraint is the ~500-cutoff history, not the choice of information.**
2. **Free, filing-timestamped data is structurally slow, and 5D is fast.** EDGAR
   fundamentals, Form 4 and 13F are quarterly-to-event sources, 45–135 days stale in
   Family 3's case, tested against a 5-session horizon. §27B's free-data constraint and
   `TARGET_DESIGN` §4.2's 5D/10D cap were set independently and **jointly select for a
   mismatch between the speed of the information and the speed of the target.**
3. **B3 is a high bar, and beating it was never the same problem as finding signal.** B3
   scores +0.02241; the best new factor found was +0.01305 standalone. The programme kept
   asking "does this add to B3" when no candidate ever reached B3 alone.
4. **What is NOT supported by the evidence:** that these three sources contain no
   information. Family 1 disproves that outright. The correct reading is that **this
   history cannot resolve their incremental contribution at this horizon through this
   arm** — three times over, each time for a measurable reason.

**§21 is satisfied and the programme stops here.** Continuing would mean either a fourth
family (barred), a re-test at another horizon (barred), or a different arm on rejected
information (barred). Each of those is the "one more carrier" move that produced
V2 → V2.3, and the budget exists precisely to make it unavailable.

## 9. Status

| | |
|---|---|
| **Budget slots** | **3 SPENT, 0 REMAINING.** Programme **CLOSED** under §21 |
| Family 3′ / fourth family | **barred**, including a sign flip |
| Exam | **sealed**, `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, never opened, 72 cutoffs |
| Production | weight **0.0**, `passed_all_criteria False`, `alpha/adapter.py` untouched |
| Thresholds / criteria / benchmarks / budget / stopping rules modified | **None** |
| Pushed | **No** |

Artefacts: `alpha/out/v3_family3_development.json`, `.pkl` (per-cutoff IC series, primary
series, 30 noise draws), `alpha/out/f13_gate.json`, `alpha/edgar/f13_meta.json`,
`alpha/edgar/f13_cusip_map.json`.
