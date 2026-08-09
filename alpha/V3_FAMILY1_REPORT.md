# V3 Family 1 — reported fundamentals. Result.

**Run 2026-08-09 under `V3_PREREGISTRATION.md`, which was committed before the first
fit.** Phase 5 information-only test (roadmap §7). 316 development cutoffs, 143,675
rows, SUE coverage 0.930, **exam contamination 0**, digest `b55e065f…`.

---

## The verdict

**REJECT. All four pre-registered CONTINUE criteria failed.** Family 1 spends budget
slot 1 of 3 (§21).

**Primary contrast — Arm 1 (B3 + 0.25·SUE tilt) minus B3:**

| | |
|---|---|
| mean paired IC difference | **+0.00090** |
| 95% block-bootstrap CI | [−0.00140, +0.00317] |
| **half-width** | **0.00229** |
| breadth | 0.5032 |
| n cutoffs | 316 |

| Criterion | Required | Measured | |
|---|---|---|---|
| 1 | effect ≥ +0.010 | +0.00090 | **FAIL** |
| 2 | CI excludes zero | [−0.00140, +0.00317] | **FAIL** |
| 3 | breadth > 0.50 **and** both halves positive | 0.5032; halves −0.00005 / +0.00185 | **FAIL** |
| 4 | survives with BEAR removed | +0.00088 | **FAIL** |

**This is a well-resolved null, not an underpowered one.** The interval's *upper*
bound, +0.00317, is below the +0.007 economic floor derived in §4 of the
pre-registration. The study can say what it set out to say: at the pre-registered
authority, this information does not improve the incumbent by an amount worth acting on.

---

## 1. What the arms did

| | mean IC | half-width | 95% CI | hit rate | turnover |
|---|---|---|---|---|---|
| b1 12-1 momentum | +0.01000 | 0.02386 | [−0.01342, +0.03430] | 0.532 | — |
| b2 5-day reversal | +0.00675 | 0.01836 | [−0.01062, +0.02610] | 0.509 | — |
| **b3 regime rule — the incumbent** | **+0.02241** | 0.02328 | [−0.00086, +0.04570] | 0.560 | 0.231 |
| **Arm 0 — raw SUE rank** | **+0.01305** | 0.01038 | **[+0.00263, +0.02339]** | **0.576** | **0.091** |
| Arm 1 — B3 + 0.25·SUE | +0.02331 | 0.02320 | [+0.00008, +0.04648] | 0.563 | 0.227 |

Neither arm's contrast against B3 is significant after Holm–Bonferroni across the two
declared arms (p_holm = 0.678 for both).

## 2. The finding that survives the rejection: SUE is a real factor

**Arm 0's own interval excludes zero.** Mean IC **+0.01305, CI [+0.00263, +0.02339]**,
hit rate 57.6%, **both chronological halves positive** (+0.01100 / +0.01509), turnover
**0.091** — a quarter of B3's.

For scale, this is the **first factor this programme has produced whose own confidence
interval excludes zero apart from B3 itself.** It is measured on 316 cutoffs, it is
built from information that did not exist in the V2 feature space, and it is cheaper to
trade than either benchmark. Against 12-1 momentum, the factor V2 → V2.3 spent four
studies failing to improve on, it has a higher mean IC (+0.01305 vs +0.01000), a higher
hit rate (0.576 vs 0.532), and — unlike momentum — an interval that clears zero.

**And it is not enough.** Three measurements say so:

* **Against the incumbent it is worse: −0.00937 vs B3.** Beating momentum is not the
  bar; §2.3 names B3 as *the* incumbent and eleven fitted arms have now failed to beat it.
* **Its long-short spread does not clear zero: +0.00051, CI [−0.00081, +0.00158].** An
  IC that excludes zero and a spread that does not is the signature of a signal that
  ranks the middle of the cross-section and not its tails — which is where a portfolio
  would have to trade.
* **Its own vs-B1 difference does not clear zero either:** +0.00305, CI [−0.01598,
  +0.02193]. The standalone IC is significant; the *improvement* over momentum is not.

## 3. The λ ceiling — no setting of the dial rescues it

Reported as a **diagnostic** under §6.1 of the pre-registration. **No point on this
curve may be promoted to an arm** (§0.1), and none is.

| λ | Arm IC | vs B3 | half-width |
|---|---|---|---|
| 0.00 | +0.02207 | −0.00034 | 0.00156 |
| 0.10 | +0.02280 | +0.00038 | 0.00169 |
| **0.25** (pre-registered) | **+0.02331** | **+0.00090** | 0.00229 |
| 0.50 | +0.02368 | **+0.00127** ← curve maximum | 0.00378 |
| 0.75 | +0.02324 | +0.00083 | 0.00564 |
| 1.00 | +0.02263 | +0.00022 | 0.00744 |
| 1.50 | +0.02110 | −0.00132 | 0.01010 |
| 2.00 | +0.01984 | −0.00258 | 0.01190 |
| pure SUE, no base | +0.01305 | **−0.00937** | 0.01949 |

**The best advantage available anywhere on the curve is +0.00127, against a half-width
of 0.00378 at that point** — inside its own resolution, and 5.5× below the +0.007
economic floor. Past λ = 1 it turns negative, heading toward pure SUE's −0.00937.

This is the V2.3 shape reproduced on new information: *"the maximum advantage over base
available anywhere on either λ curve is +0.00045, against a measured resolution of
0.00827"* (`V2_3_LADDER_REPORT.md`). Different data, same ceiling.

### 3.1 A subtlety the curve exposed, recorded rather than smoothed over

**At λ = 0 the contrast is −0.00034, not 0.00000.** It should be zero — at λ = 0 the arm
*is* B3. The gap is not a bug in the arm; it is **universe composition**. The arm is NaN
wherever SUE is undefined (7.0% of rows, never imputed — §3 of the pre-registration), so
it is scored on a slightly smaller cross-section than full-universe B3, and that
restriction alone costs −0.00034 of IC.

**The honest consequence: the coverage-matched tilt effect is +0.00090 − (−0.00034) =
+0.00124, not +0.00090.** That is the number the information actually contributed. It
does not change the decision — it is still an order of magnitude below the +0.010
threshold, below the +0.007 floor, and inside the ±0.00229 resolution — but reporting
+0.00090 without this decomposition would understate the information's contribution,
and the pre-registration does not permit choosing whichever framing looks better in
either direction.

## 4. Costs: the tilt does not pay for its own trading

**Net-of-cost is the primary economic metric from the first measurement** (§10), not a
later sanity check.

| Arm | gross spread advantage vs B3 | extra turnover | **net** |
|---|---|---|---|
| Arm 0 | −0.00146 | −0.140 | **−0.001461** |
| Arm 1 | −0.00006 | −0.004 | **−0.000065** |

Both negative. **This is the fifth consecutive study in which no tilt pays for its own
trading.** Note Arm 0's turnover is *lower* than B3's — quarterly-updating fundamentals
are naturally slow — so this is not a cost problem. There is simply nothing to pay for.

## 5. The BEAR concentration, for the fifth time

Arm 1 beats **momentum** by +0.01332 with an interval excluding zero, [+0.00167,
+0.02714]. Decomposed:

| Arm 1 vs B1 | BULL_TREND | BEAR_TREND | SIDEWAYS | ex-BEAR |
|---|---|---|---|---|
| mean IC difference | +0.00075 | **+0.11317** | +0.00189 | **+0.00088** |

**The entire advantage over momentum is the regime rule Arm 1 is built on, not the new
information.** `V2_3_LADDER_REPORT.md` §2 wrote the identical sentence about V2.3-B.
Under §2.5 this concentration **disqualifies**; it does not caveat. Criterion 4 exists
precisely to stop this being reported as a win, and it fired.

## 6. The noise control behaved as a control

30 paired draws, each a within-cutoff permutation of the SUE values — the cross-sectional
distribution preserved, the identity-to-value mapping destroyed.

| | |
|---|---|
| median | **−0.00045** (limit +0.002) |
| mean / sd | −0.00043 / 0.00096 |
| share of draws ≥ +0.010 | **0.000** (limit 0.10) |
| verdict | **PASS** |

The sd of 0.00096 is small against the +0.010 threshold the control guards, which is
what §2.11 requires after V2.3's single seeded draw landed ~2σ high and aborted a run.
**A control that can fire on noise is not a control**; this one cannot.

## 7. Verification

| Invariant | |
|---|---|
| exam contamination | **0** — asserted in code before any scoring |
| exam digest | `b55e065f4c9f9173…`, unchanged |
| exam files | still absent; the §5.2 gate still refuses |
| production weight | **0**, untouched |
| pre-registration | committed at `5a8b92e`, **before** this run; unedited |
| clause-3 ceilings | fixed at `5a8b92e` before any correlation was read |
| per-cutoff series | `alpha/out/v3_family1_development.pkl` — every number above is re-derivable from per-cutoff data |

**No protocol departure.** Everything run is what §6 of the pre-registration declared:
two arms, one target, one horizon, one primary contrast, λ fixed at 0.25.

## 8. Diagnosis — which thing failed (§21 requires this)

Not the power: the primary contrast resolved to ±0.00229, three times *better* than the
0.0074 the gate predicted. Not the point-in-time quality: the door is tested and the
coverage is 93%. Not the implementation: the arms behaved, the control passed, the
universe held.

**The information failed — but in a specific and unusual way.** SUE *is* real: its own
IC clears zero, which nothing in V2 → V2.3 ever did. What it is not, is **incremental to
a regime-switched momentum rule**, and it is not tradeable at the tails.

The better resolution than predicted is itself the §2.12 warning working as intended: a
bounded arm at λ = 0.25 is nearly collinear with its base, and *resolution and authority
are the same dial*. Turning the dial up is measured in §3 — the curve peaks at +0.00127
and then falls. There is no setting at which this information both differs from the
incumbent and beats it.

## 9. What is now closed

1. *Do free, point-in-time reported fundamentals contain cross-sectional information
   beyond price and volume?* **Yes — measurably.** SUE's IC excludes zero.
2. *Is it incremental to the B3 incumbent?* **No.** +0.00090 (+0.00124 coverage-matched),
   inside its own resolution, and the λ curve tops out at +0.00127.
3. *Does it pay for its own trading?* **No.** Net −0.000065.
4. *Is the apparent win over momentum the information?* **No.** It is the regime rule:
   +0.11317 in BEAR against +0.00075 in BULL.

## 10. What is not closed, and is not reopened here

Family 1 tested **one construction** — time-series SUE on `NetIncomeLoss` at a 5-session
horizon. Reported fundamentals also carry margins, accruals, cash-flow quality, balance
sheet growth and drift measured over longer windows, and this study did not test them.

**That is not a licence to run Family 1′.** §21 and §2.9 are explicit: a family that
fails its Phase 5 test is rejected and is not re-tested with another feature, another
learner, or another horizon. The correct record is: *this construction of this
information, at this horizon, on this history, does not clear the bar* — and the slot is
spent. Anything else is the "one more carrier" move that produced V2 → V2.3.

**The reusable asset survives the rejection:** the filings door, the acceptance-time
rule, the ingest and the restatement guarantee are built and tested, and Family 2 does
not have to rebuild them.

---

## Production

**Unchanged. Weight 0, action HOLD.** No adapter was modified. Nothing here reaches the
application, and Phase 7b was never entered because Phase 5 did not return CONTINUE.
