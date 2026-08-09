# V4 formulation review — did V3 test the right information under the wrong formulation?

**Written 2026-08-09. DESIGN ONLY.** No new feature was measured, no backtest was run, no
ingest was performed, no model was selected on development data, and no forward return was
read. Every number below is either (a) quoted from a completed V3 artefact, (b) a
rank-versus-rank structural property of an arm computed from a completed V3 feature panel
with no target, or (c) arithmetic on (a) and (b), labelled as such.

**V3 is closed and stays closed.** No V3 pre-registration, Family 1/2/3 module, completed
result, exam file or production adapter is edited by this document. Exam sealed at
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. Production weight
`0.0`.

---

## 0. The V3 evidence, taken as fixed

| | Family 1 — SUE | Family 2 — Form 4 | Family 3 — 13F |
|---|---|---|---|
| Standalone IC (Arm 0) | **+0.01305** | −0.00547 | −0.00659 |
| Its 95% CI | **[+0.00263, +0.02339]** | [−0.01278, +0.00151] | [−0.01465, +0.00051] |
| Arm 1 − B3 | +0.00090 | −0.00096 | −0.00339 |
| Half-width of that contrast | 0.00229 | 0.00092 | 0.00279 |
| Coverage | 0.930 | 0.136 non-zero | 0.856 |
| \|ρ\| vs `z__ret_12_1` | 0.1305 | 0.1313 | **0.0726** |
| Decision | REJECT | REJECT | REJECT |

Incumbent **B3 = +0.02241** IC (CI [−0.00086, +0.04570]); B1 12-1 momentum +0.01000.

**One fact governs everything below: the single best factor V3 found scored +0.01305
standalone against an incumbent scoring +0.02241.** Every candidate was weaker than the
thing it was asked to improve.

---

## 1. Horizon mismatch

### 1.1 The candidates

| | 5D | 20D | 40D | 60D (~1 quarter) |
|---|---|---|---|---|
| Non-overlapping draws in the 2,655-session development span | 531 | 133 | 66 | 44 |
| Neighbours each observation overlaps (5-session spacing) | 0 | 3 | 7 | 11 |
| Half-width, Family-2 calibration (0.0016 @ H=5) | 0.0016 | 0.0032 | 0.0045 | 0.0055 |
| Half-width, roadmap calibration (0.0057 @ H=5) | 0.0057 | 0.0114 | 0.0161 | 0.0197 |

The 5D/20D/90D columns are quoted from `V3_FAMILY2_PREREGISTRATION.md` §6, which computed
them before Family 2 ran. 40D and 60D are the same √(H/5) scaling applied to the same
anchors; that scaling reproduces the quoted 20D and 90D entries exactly, so it is
arithmetic on existing numbers rather than a new estimate.

### 1.2 Economic rationale and decay, per horizon

* **5D** — matches nothing about the information. SUE becomes knowable at an acceptance
  event; 13F holdings are **45–135 days stale on arrival** (measured: median 92, p90 128).
  A 5-session window asks a quarterly-cadence signal to express itself inside one week.
* **20D** — one trading month. The shortest horizon over which a repricing driven by
  quarterly information can plausibly accumulate. Retains **133** independent draws.
* **40D** — two months. Fits post-earnings drift literature well; costs half the
  independent draws of 20D for a modest further gain.
* **60D** — one trading quarter, matching the natural update cadence of all three sources.
  Economically the best fit, and statistically the weakest: **44** independent draws, and
  each observation overlaps 11 neighbours, which `alpha/stats.py`'s `BLOCK_LENGTH = 4`
  (four cutoffs = 20 sessions) **cannot span**. Using it unchanged would report an interval
  far narrower than the truth — the §2.12 failure mode.

### 1.3 The arithmetic that matters, and it is discouraging

Under the standard model where a signal predicts a **drift that accumulates linearly** in
time while noise **diffuses as √t**:

* effect grows as `IC(H) ≈ IC(5)·√(H/5)`;
* half-width also grows as `√(H/5)`, because a fixed calendar span contains proportionally
  fewer independent draws.

**These are the same factor, so the t-statistic is invariant to the horizon.** Lengthening
the horizon does **not** buy statistical resolution. The same conclusion follows from the
fundamental law: `IR ≈ IC·√breadth`, and breadth falls exactly as fast as IC rises.

**A longer horizon helps through exactly two channels, and neither is statistical:**

1. **Cost.** Rebalancing 13×/year instead of 52 cuts the cost drag ~4×. In V3's own MDE
   derivation the cost term was 0.0003 of a 0.0007/week gross hurdle — **43% of the bar.**
   Removing three quarters of it lowers the MDE from +0.007 to **≈ +0.005 in
   5D-equivalent IC units** (≈ +0.0095 in native 20D units). Real, and worth having.
2. **Any decay that is *superlinear* in H** — i.e. if slow information is *more* attenuated
   at 5D than √H predicts, because the repricing needs weeks and the 5-day window is
   dominated by microstructure noise. **This is a hypothesis, not a measured fact, and V3
   cannot speak to it because it only ever measured at 5D.**

The second channel is the only way a horizon change rescues anything, and it is precisely
what a V4 test would establish. It should be stated as the hypothesis, not assumed.

### 1.4 Fit to the three sources

All three are quarterly-cadence. 13F is the most horizon-sensitive (structurally stale);
SUE is event-driven and therefore the least dependent on a long horizon; Form 4 is
event-driven but its defect (§4) is horizon-invariant.

### 1.5 **Recommendation — ONE primary V4 horizon: 20 sessions.**

Chosen on economic and structural grounds, with no forward return consulted. It is the
**longest horizon that leaves the existing bootstrap machinery honest** — at 20 sessions
each observation overlaps 3 neighbours and `BLOCK_LENGTH = 4` spans exactly that, whereas
40D and 60D would require re-deriving the block length, which is a change to a tested
statistical instrument. It captures the cost reduction (MDE +0.007 → ≈ +0.005
5D-equivalent) and retains 133 independent draws. 60D fits the information best and is
rejected because its interval could not be trusted.

---

## 2. Arm authority

### 2.1 How tied to B3 Arm 1 actually was

Rank-versus-rank structural properties of the arm, computed on the completed Family 1
feature panel. **No forward return is read; this measures what the arm *can* reorder, not
how well it predicts.**

| λ | Spearman(Arm 1, B3) | Top-quintile book changed |
|---|---|---|
| **0.25 (V3's value)** | **0.9758** | **14.4%** |
| 0.50 | 0.9191 | 26.7% |
| 1.00 | 0.7761 | 40.0% |

Measured directly in the V3 runs: Family 2 **0.9896** / 5.4% of book (its 86% tie block
suppressed authority further); Family 3 **0.9725**.

### 2.2 The core question, answered against the evidence — and the answer is *no*

The question posed is whether V3 bought resolution by making the treatment so weak that
independent information could not move the portfolio. **The completed evidence says this
was NOT the binding constraint**, and the decisive artefact is the oracle ceiling already
computed in `FAMILY2_POWER_GATE.md` §4: an **oracle tilt (perfect foresight) through the
identical λ = 0.25 arm achieved roughly 30× the half-width.** An arm with 30× headroom is
not a straitjacket. Had any V3 feature carried even 5% of oracle information, it would have
produced ≈ +0.003 — comfortably above the 0.0023 resolution, and it would have been seen.

The measured contrasts (+0.00090, −0.00096, −0.00339) are therefore **genuinely near zero,
not artificially compressed.** Authority is a real but *secondary* fault: at λ = 0.25 the
arm dilutes roughly 4× versus equal weight, so it could mask a marginal effect, but it
cannot manufacture three nulls out of three real signals.

### 2.3 The threshold V3 never computed, and should have

For two rank signals with ICs `r_B3`, `r_new` and near-zero mutual correlation (V3's
features were |ρ| 0.07–0.13), an equal-weight rank blend scores about
`(r_B3 + r_new)/√2`. Requiring that to exceed `r_B3 + MDE`:

| Required incremental | Required **standalone** IC of the new source |
|---|---|
| +0.007 (V3's MDE, 5D) | **≈ 0.0192** |
| +0.005 (20D-adjusted MDE) | **≈ 0.0164** |

**V3's best candidate scored 0.01305 — 68% of what the 5D bar required and 80% of the
20D bar.** The other two scored ≈ 0. **This bar was never stated in V3**, and it is the
single most useful number this review produces: it converts "find incremental alpha" into a
concrete admission test a candidate source can be screened against *before* a slot is spent.

### 2.4 The five architectures, conceptually

| | Authority | Assessment |
|---|---|---|
| **A. standalone rank** | maximal | Already run as Arm 0 in all three families and required by §2.3 anyway. Cannot beat an incumbent it scores below. Not a primary arm |
| **B. equal-weight B3 + feature** | high (Spearman 0.776, 40% book) | Simple, deterministic, no fitting; makes §2.3's threshold arithmetic exact. In the old parameterisation this is λ = 1.0 |
| **C. residualised feature** | high | Elegant — orthogonalises by construction — but requires estimating a B3 loading on development data, which is a fitted step and a §2.9 escalation risk |
| **D. stronger fixed bounded tilt** | tunable | A λ change and nothing more. Cannot by itself constitute a new scientific question (§4) |
| **E. two-stage: B3 gates eligibility, feature ranks within** | maximal within the gate | Genuinely different question and full authority. But it halves the cross-section, changes the comparison universe, and breaks the clean paired contrast against B3 on identical names |

### 2.5 The binding constraint is §2.6, and it eliminates most of the above

Extrapolating half-width from the two measured anchors — λ = 0.25 → 0.00229, standalone →
≈ 0.0227, both at n = 316, H = 5 — and scaling to 20D by √4:

| Architecture | est. half-width @ 5D | est. @ 20D | vs 20D MDE ≈ 0.0095 |
|---|---|---|---|
| λ = 0.25 | 0.0023 | 0.0046 | 2.1× inside |
| **λ = 0.50** | **≈ 0.0046** | **≈ 0.0092** | **≈ 1.03× — marginal** |
| λ = 1.00 (equal weight, B) | ≈ 0.0080 | ≈ 0.0160 | **FAILS** |
| standalone / two-stage (A, E) | ≈ 0.0227 | ≈ 0.045 | **FAILS badly** |

**This is the central tension of the whole programme.** High authority and adequate
resolution are not simultaneously available on ~316 cutoffs. V3 chose resolution and got a
null it could trust; the opposite choice yields an effect it could not measure. Equal
weight — the architecture the threshold arithmetic in §2.3 assumes — **does not pass
§2.6 at 20D on this history.**

### 2.6 **Recommendation — ONE primary V4 arm: `rank_pct(B3) + 0.50·(rank_pct(feature) − 0.5)`.**

Double V3's authority (Spearman 0.919, **26.7%** of the traded book reordered versus
14.4%), simple, deterministic, no fitted parameter, falsifiable, and the **most authority
that the §2.6 gate can still admit at a 20-session horizon**. Equal weight is preferred on
every ground except the one that is non-negotiable.

> **The estimated gate margin is ≈ 1.03×, which is marginal.** The §2.6 gate must be run
> for this exact design **before V4 executes**, and **if it fails, V4 does not run.** That
> is the §2.6 discipline and this review does not soften it.

---

## 3. Power and history

Using only completed V3 bootstrap evidence. `half-width ∝ 1/√n`, anchored on the
recommended design's estimated **0.0092 at n = 316** (native 20D units), so
`n = 316·(0.0092/m)²`. Development cutoffs accrue at ≈ 30/year.

| Target effect (20D units) | 5D-equivalent | Required cutoffs | ≈ years |
|---|---|---|---|
| **+0.010** | +0.005 | **267** | **9 — already held (316)** |
| +0.007 | +0.0035 | 546 | 18 |
| +0.005 | +0.0025 | 1,070 | 36 |
| +0.003 | +0.0015 | 2,972 | 99 |

**Classification:**

* **Resolvable with current history:** effects ≥ **+0.010** in 20D units (≈ +0.005
  5D-equivalent). This bracket contains the 20D-adjusted MDE, which is why the design is
  viable at all — but only just.
* **Requires more history than exists:** +0.007 and +0.005 (18 and 36 years of
  *development* cutoffs). The panel begins **2016**; free filing-timestamped data begins
  ~2009–2013. Even extending back to the earliest free PIT data yields ≈ 17 years total,
  most of which would be needed before an exam could be re-cut.
* **Not practically resolvable with free PIT data, ever:** **+0.003 and below.** 99 years
  does not exist. Any future claim of an effect this size on this universe is unfalsifiable
  and should be refused at the gate, not tested.

**On overlap.** These counts are *cutoff* counts at 5-session spacing, and a 20-session
horizon makes each observation overlap 3 neighbours. The 0.0092 anchor already carries that
penalty via the √(H/5) scaling, and `BLOCK_LENGTH = 4` spans the induced dependence.
**Effective independent sample size is ≈ n/4, not n** — at n = 316 that is ≈ 79 independent
blocks. The table must not be read as "316 observations"; it is read as "316 cutoffs whose
dependence the block bootstrap already prices in." Multiplying observations by the nominal
horizon would overstate power roughly fourfold and is exactly the §2.12 artefact.

---

## 4. Reusing V3 information

### 4.1 The rule, applied strictly

Reuse is scientifically acceptable **only if V4 asks a materially different question at the
formulation level.** A different λ alone is not enough; a cosmetic carrier or model change
is not enough; a post-hoc sign flip is never enough.

**The recommended V4 changes the target variable itself** — from 5-session forward alpha to
20-session forward alpha. That is a different dependent variable, not a different estimator
of the same one, and it makes a genuinely new prediction: *that slow filing-timestamped
information gains on a fast incumbent as the horizon lengthens.* V3 cannot have answered
it, because V3 measured only at 5D. The λ change from 0.25 to 0.50 is **secondary and does
not carry the justification** — the horizon does.

### 4.2 **But V3's own rules forbid this, and that must not be glossed**

> §2.9/§21 bar re-testing a rejected family **with another feature, learner or horizon.**
> That wording is explicit, it was written precisely to stop the "one more carrier" move,
> and it was reaffirmed at each of the three rejections.

**Therefore reuse of any V3 source cannot be authorised under V3's rules, and this document
does not authorise it.** V4 would have to be constituted as a **new programme with its own
charter**, in which the account holder deliberately and on the record supersedes §21's
no-re-test clause for a named source, with the reason stated. That is a legitimate thing
for a principal to do; it is not something an executing session may infer.

**If instead §21 is left standing as written, V4 must use information no V3 family
touched**, and the ranking below applies only to a charter that explicitly reopens reuse.

### 4.3 Ranking by suitability, on V3 evidence alone

1. **SUE (Family 1) — clearly first.** The only V3 source whose standalone interval
   excluded zero (+0.01305, [+0.00263, +0.02339]), stable across halves, cheap to trade
   (turnover 0.091), and at 80% of the 20D threshold in §2.3 — the only candidate for which
   a horizon effect of plausible size would close the gap. Its V3 failure was *"real but
   not incremental,"* which is the one failure mode a formulation change could genuinely
   reverse.
2. **13F (Family 3) — a distant second.** Best coverage (0.856), lowest correlation with
   momentum (|ρ| 0.0726), strictest PIT door, and the **most horizon-sensitive** source, so
   it has the most to gain from 20D in principle. Against it: standalone IC −0.00659 with a
   CI spanning zero, i.e. no evidence of any signal to amplify. Amplifying zero yields zero.
3. **Form 4 (Family 2) — NOT eligible, at any horizon or architecture.** Its defect is
   structural and formulation-invariant: with 86% of names tied at exactly zero, **no name
   reached the bottom quintile at any of 316 cutoffs** and the long-short spread was
   undefined everywhere. A longer horizon and a stronger tilt do not create a short book.
   Reusing it would be a Family 2′ with no material change and should be refused.

---

## 5. The ONE recommended V4 formulation

| # | Element | Specification |
|---|---|---|
| 1 | **Hypothesis** | Slow, filing-timestamped information gains predictive strength *relative to a fast momentum-regime incumbent* as the prediction horizon lengthens, such that at 20 sessions a bounded tilt on B3 delivers an incremental IC ≥ the 20D economic bar. |
| 2 | **Target** | Within-cutoff Spearman IC on forward alpha, unchanged instrument |
| 3 | **Primary horizon** | **20 sessions.** One only; no second horizon may be added later |
| 4 | **Primary arm** | `rank_pct(B3) + 0.50·(rank_pct(feature) − 0.5)`. λ = 0.50 **fixed**, never scanned, no point on any λ curve promotable to an arm |
| 5 | **Baselines** | B3 (incumbent), B1 12-1 momentum, B2 5d reversal, **and the raw feature alone** (§2.3, mandatory) |
| 6 | **Minimum economically relevant effect** | **+0.0095 IC in native 20D units** (≈ +0.005 5D-equivalent), re-derived from the frozen 5 bps cost model at 13 rebalances/year. Fixed before any measurement; never lowered |
| 7 | **Expected resolution** | Estimated half-width **≈ 0.0092** at 316 cutoffs. Margin ≈ 1.03× — **marginal, and the gate must be run for real** |
| 8 | **Required history** | 267 cutoffs for +0.010; **316 held**. Anything below +0.007 (546 cutoffs) is out of reach |
| 9 | **PIT rule** | Acceptance-time door where an acceptance timestamp exists (`alpha/filings.py`, tested); `FILING_DATE < cutoff` where it does not. A source with neither is inadmissible, never approximated |
| 10 | **Coverage** | ≥ 0.80 of the point-in-time cross-section, and a **continuous** feature: any candidate whose ties prevent forming *both* book tails is inadmissible — the Family 2 lesson, made a gate |
| 11 | **Turnover / economic significance** | Net-of-cost spread advantage at 5 bps is primary from the first measurement. Extra turnover ≤ 30 pp or the MDE rises |
| 12 | **Multiplicity** | Two arms, one primary contrast, one target, one horizon, declared before the first fit. Holm–Bonferroni across the arms |
| 13 | **Noise control** | 30 paired within-cutoff permutations; fails if median > +0.002 or > 10% of draws clear the threshold |
| 14 | **Stopping rule** | The four V3 criteria **with Amendment A1's wording**: effect ≥ MDE; CI excludes zero **on the favourable side**, `bool(lo > 0.0)`; breadth > 0.50 and both halves positive; survives with BEAR removed. Anything less is REJECT |
| 15 | **Budget** | **ONE slot.** V4 tests one source at one horizon through one arm. If it fails, V4 ends — there is no V4 second family. A one-slot budget is the honest size given §2.3's threshold screen can be applied *before* spending it |
| 16 | **V3 reuse** | **SUE only, and only under a new charter that explicitly supersedes §21** (§4.2). Under §21 as written, no V3 source is eligible |
| 17 | **Falsification** | Any of the four criteria failing. Specifically: if SUE's standalone IC at 20D does not exceed its 5D value of +0.01305 by enough to approach the ≈0.0164 threshold of §2.3, the horizon hypothesis is **false** and the correct conclusion is that free PIT data on this universe cannot beat B3 — not that another horizon should be tried |

---

## 6. Ranking the three interventions

**Highest priority — greater arm authority. *A formulation error, but a modest one.***
It is the only intervention that is free, immediate, and certain to change the measurement:
it doubles the reordered book from 14.4% to 26.7%. **It is ranked first because it is
cheap, not because it is the main fault** — the oracle ceiling (§2.2) proves the λ = 0.25
arm had ~30× headroom, so authority did not cause the three nulls. Its real value is
eliminating the one remaining alternative explanation, at essentially no cost.

**Second — longer horizon. *A plausible formulation error, and the only one that could
change a result.*** It is the sole intervention that can raise a *standalone* IC toward the
§2.3 threshold, and the sole one addressing a genuine mismatch (quarterly-cadence data,
45–135 days stale, tested over five sessions). It is ranked second only because the
arithmetic in §1.3 shows it **cannot** help through statistical power — the t-statistic is
horizon-invariant — so its benefit rests entirely on the cost reduction (real, ~30% off the
MDE) plus an *unproven* superlinear decay. Highest upside, lowest certainty.

**Lowest — more history. *A power limitation, not a formulation error, and largely
unobtainable.*** More history resolves smaller effects; it does not make effects larger.
V3's problem was never resolution — every family resolved 2–25× better than its MDE and
returned a null anyway. Adding history to a design whose measured effect is −0.003 buys a
more precise estimate of approximately nothing. It becomes binding **only after** the first
two are fixed, and even then §3 shows the required 18–99 years does not exist.

**The separation the evidence supports:**

* **Likely formulation errors:** the horizon mismatch (§1) and, secondarily, the arm's
  dilution (§2) — but note §2.3's finding that the deeper error was *never computing the
  standalone-IC threshold a candidate had to clear*, which is a screening failure rather
  than a horizon or arm failure.
* **Merely a power limitation:** history. And it is the one that cannot be fixed with free
  data.

**More history does not fix a misspecified horizon or a diluted arm**, and this review does
not propose it as a remedy for either. The honest reading of V3 is that the binding
constraint is neither the horizon nor the arm but **the strength of the information
available for free** — no candidate came within 68% of the standalone IC required, and the
correct next step is to screen candidates against that threshold *before* spending a slot,
not to re-run the same sources through a new arm.

---

## 7. Preservation

Nothing in V3 was edited: no pre-registration, no Family 1/2/3 module, no completed result,
no exam file, no production adapter. This document is the only file added. No predictive
measurement was performed. Exam sealed at
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`; production weight
`0.0`; nothing pushed.

**V4 is not authorised by this document.** It requires a new charter from the account
holder, and — if any V3 source is to be reused — an explicit, recorded supersession of §21.
