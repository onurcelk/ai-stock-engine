# PEAD-1 — confirmatory result

**Date:** 2026-08-22
**Protocol:** `alpha/PEAD1_PREREGISTRATION.md`, committed after the power gate passed
(`reports/PEAD1_POWER_GATE.md`, 5-session window, 12.5 bp half-width vs a 39 bp MDE) and
before this measurement was run.
**Status:** RUN AND SCORED. 29,755 events, 647 independent calendar weeks.
**Class:** confirmatory test of a reopened, reformulated closed source (SUE). Spends
PEAD-1's one confirmatory slot. **This is the first read of any PEAD-1 point estimate.**

---

## 0. The one-line answer

> ```text
> PEAD-1 VERDICT: REJECT. A real, statistically detectable effect (+14.7 bp, 95% CI
>                 [+2.1, +27.0], excludes zero) that is too small to clear the
>                 pre-registered 39 bp economic bar, and substantially explained by
>                 market exposure rather than SUE-specific information.
> ```

This is not the same shape of null as V3, V4, HT-1, `vwap_reversion`, or `orb_1h`. Those
found intervals that straddled zero or point estimates near zero. **PEAD-1 found a real,
non-zero, statistically significant effect that failed on economic magnitude and on a
market-exposure control — two different, more informative failure modes than "nothing is
there."**

---

## 1. Result against the pre-registered four-criterion CONTINUE rule

| Criterion | Requirement | Measured | Met? |
|---|---|---|---|
| 1. Advantage | ≥ +39.0 bp | **+14.7 bp** | **No** |
| 2. CI excludes zero (favourable side) | `lo > 0` | **[+2.1, +27.0] bp** | **Yes** |
| 3. Breadth + both halves positive | breadth > 0.50, both halves > 0 | breadth 0.550, both halves positive | **Yes** |
| 4. Market-relative control | `lo > 0` on `(firm − SPY) × sign(SUE)` | +6.8 bp, **CI low −4.3 bp** | **No** |
| Noise control | median ≤ 10 bp, exceedance ≤ 10% | median +7.1 bp, exceedance 0.0% | Yes |

**Two of four required criteria fail. Per the pre-registration's own rule ("all four
required... anything less is REJECT"): REJECT.**

| | |
|---|---|
| Events | 29,755 |
| Independent weeks | 647 |
| Net of a nominal 5 bp round-trip cost | **+9.7 bp** |

---

## 2. Reading — why this result is more informative than a flat null

**The statistical significance (criterion 2) is genuine and not an artefact of multiplicity
or noise.** The noise control's 30 sign-permutation draws produced a median of only +7.1 bp
with 0% of draws reaching the 39 bp bar — the real +14.7 bp sits meaningfully above the
permutation distribution's centre, and the interval's exclusion of zero is not a
data-mining accident from trying many things, because exactly one design was ever measured.

**But the effect is roughly a third the size the pre-registered economic bar required**
(14.7 vs 39 bp), and that bar was not arbitrary: it is Single-Name Phase 1's own resolution
floor, chosen so a passing result would be big enough to matter, not merely big enough to
detect. A 14.7 bp five-session effect, even if real, sits below what this programme has
established as an economically meaningful single-name signal (roadmap §9b's own standard,
and the reason V2's own feature set — worth +0.0005 to +0.0014 IC — never converted to a
tradeable edge either).

**Criterion 4 is the sharper diagnostic.** Once SPY's return over the identical window is
subtracted out, the advantage falls from +14.7 bp to +6.8 bp and the interval's lower bound
turns negative (−4.3 bp). **A large share of the raw effect is SUE-sorted firms
participating in a rising market over the measurement period, not SUE-specific
information.** This is exactly the failure mode `PEAD1_CHARTER.md` §2.6 built the control to
catch, and it caught something real.

**This reconciles PEAD-1 with V3 and V4, rather than contradicting them.** V3's Family 1
found SUE's cross-sectional IC excluded zero (+0.01305) but its long-short *spread* did not
(+0.00051, CI spanning zero) — the same "real in aggregate, not enough at the tails/margin
to trade" signature. PEAD-1's event-time reformulation reproduces that signature in a
different design: a small, real, market-confounded effect, not an absent one.

---

## 3. What is barred as a consequence

Per `PEAD1_CHARTER.md` §9.2: **REJECTED, slot SPENT.** No SUE‴ at any window, control, or
architecture. **This closes SUE permanently, at every formulation the account holder has
authorised testing** — the original V3/V4 cross-sectional design and this event-time,
absolute-return design. No further reopening of SUE may be proposed by an executing
session; a future attempt would require the account holder to name a formulation neither
this document nor `PEAD1_CHARTER.md` anticipated, in writing, as a new decision.

The 20-session window (also passed the power gate, §3 of `PEAD1_CHARTER.md`) is **not**
run as a consolation measurement — running it now, having seen the 5-session result, would
be exactly the "second window after seeing results" violation the pre-registration
forbids.

---

## 4. Verification

- Fast suite: 1277 passed, 87 skipped — green.
- `alpha/V3_*`, `alpha/V4_*`: untouched, not read for re-evaluation.
- `alpha/edgar/facts.parquet`, `alpha/cache/*.csv`: read-only.
- No production engine file touched. Sealed exam not accessed. Production weight `0.0`.
- 9 tests (`app/tests/test_pead1_confirmatory.py`), including a regression test for a
  tz-handling bug caught before this result was ever read: an early draft crashed
  comparing a tz-aware anchor date against a `to_numpy()`-derived SPY date array that
  silently became an object array of tz-aware Timestamps rather than the plain
  `datetime64[ns]` array `.values` provides. Fixed and tested before the fix was trusted
  with this measurement.
