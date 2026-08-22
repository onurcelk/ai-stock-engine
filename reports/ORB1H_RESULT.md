# orb_1h — confirmatory result

**Date:** 2026-08-22
**Protocol:** `alpha/HT2_TOURNAMENT_PREREGISTRATION.md` Amendment 2, committed after the
power gate passed (`reports/ORB1H_POWER_GATE.md`) and before this measurement was run.
**Status:** RUN AND SCORED. 0 budget slots spent — this is a price-only technical census
addition, the same class as `vwap_reversion` and HT-1's original 27.

---

## 0. The one-line answer

> ```text
> orb_1h VERDICT: REJECT. Advantage +0.9 bp against a 39 bp hurdle; the 95% interval
>                 [-6.5, +8.1] straddles zero; the first sample half is negative.
> ```

The power gate's PASS said only that this history could *see* an effect of 39 bp if one
existed. It does not — at least not one of that size, in this construction.

---

## 1. Result against the pre-registered CONTINUE rule

| Criterion | Requirement | Measured | Met? |
|---|---|---|---|
| 1. Advantage | ≥ +39.0 bp | **+0.9 bp** | **No** |
| 2. CI excludes zero (favourable side) | `lo > 0` | [−6.5, +8.1] bp | **No** |
| 3. Breadth + both halves positive | breadth > 0.50 and both halves > 0 | breadth 0.514, first half **negative**, second half positive | **No** |
| Noise control | median ≤ 5 bp, exceedance ≤ 10% | median +1.1 bp, exceedance 0.0% | Yes (uninformative given criteria 1–3 already fail) |

**All three CONTINUE criteria fail.** Per Amendment 2: **REJECT.**

| | |
|---|---|
| Sessions with a breakout call | 7,241 |
| Independent trading dates | 915 |
| Net of a nominal 5 bp round-trip cost | **−4.1 bp** |

---

## 2. Reading

The gate's own diagnosis (`reports/ORB1H_POWER_GATE.md` §0) explained why resolution was
never really in doubt here: a same-session close-to-close outcome has low enough variance
that 915 independent dates comfortably resolves effects far smaller than 39 bp. **The
confirmatory measurement shows that resolution correctly finding nothing, rather than a
resolution problem hiding something.** The point estimate (+0.9 bp) is not merely
insignificant — it is an order of magnitude below the hurdle, with a first-half/second-half
sign flip that is itself evidence against a stable effect rather than a noisy-but-real one.

**This is fully consistent with HT-1 and HT-2's `vwap_reversion`:** a fourth and fifth
price-only technical construction (opening-range breakout joins moving-average crossover,
Bollinger-style reversion, VWAP-style reversion, and 24 others) finds nothing on this
26-to-31-symbol universe.

---

## 3. What is barred as a consequence

Per `HT2_TOURNAMENT_PREREGISTRATION.md` Amendment 2: no second outcome window (e.g. adding
a next-session horizon now that same-session failed), no threshold change, no sign flip
(the negative first half is not a licence to trade the opposite direction), no promotion of
any of the 30 noise-control draws to the candidate's own result.

---

## 4. Verification

- Fast suite: 1276 passed, 87 skipped — green.
- `core/tournament.py`'s `CANDIDATES` roster and `app/tournament.sqlite3` untouched — this
  study reads only `app/cache/*__1h.csv` and writes no store.
- No production engine file touched. Sealed exam not accessed. Production weight `0.0`.
- 8 new tests (`app/tests/test_orb1h_confirmatory.py`): the four-criterion verdict
  arithmetic and a direct check that the noise control's permutation shuffles the call
  direction while holding realised returns fixed (not the reverse, which would be circular).
