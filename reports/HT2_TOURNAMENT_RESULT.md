# HT-2 — swing VWAP mean reversion: result

**Date:** 2026-08-22
**Protocol:** `alpha/HT2_TOURNAMENT_PREREGISTRATION.md` §3.2, window and threshold frozen in
Amendment 1 **before any forward return for this candidate was read.**
**Status:** RUN AND SCORED. **5,988 scored signals.**
**Class:** new candidate (not a reopening). 0 budget slots spent — this is a price-only
technical census addition, the same class as HT-1's original 27, not an information family.
**Instrument:** `core/tournament.leaderboard`, HT-1's own scoring/statistics pipeline,
reused unmodified against a dataframe this study built independently. `core/tournament.py`'s
`CANDIDATES` roster and `app/tournament.sqlite3` (HT-1's frozen, trigger-immutable record)
were not touched.

---

## 0. The one-line answer

> ```text
> HT-2 VERDICT: vwap_reversion REJECTED at all three horizons. 3 tests, 3 REJECT,
>               combined with HT-1's 81 under one Holm-Bonferroni family of 84.
> ```

---

## 1. What was measured

| | |
|---|---|
| Grid | HT-1's own — 88 independent cutoffs, stride 25 bars, majority calendar, 2017-11-09 → 2026-07-10 |
| Cells | 1,996 `(symbol, cutoff)` pairs over 26 symbols (HT-1 reported 1,995 on 2026-08-17; the one-cell difference is consistent with five more days of cached daily bars accumulating since then, not a design change) |
| Candidate | `ht2.vwap_reversion` — short when close ≥ 10-session VWAP + 2.0σ(close, 10), long when close ≤ VWAP − 2.0σ, flat otherwise |
| Window / threshold | 10 sessions / 2.0σ, both frozen on variance-only and precedent grounds (Amendment 1) before this run |
| Horizons | 1d, 1w, 5w, read from the same cutoff, HT-1's own admission rule |
| Instrument | Paired per-cutoff moving-block bootstrap (block 4, 10,000 draws), Holm–Bonferroni across the **combined** family of HT-1's 81 resolved tests plus this study's 3 |

---

## 2. The result

| Horizon | Calls | Coverage | Accuracy | Baseline | Advantage | 95% interval | p | p Holm (of 84) | Verdict |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|
| `1d` | 212 | 0.106 | 0.4292 | 0.5283 | **−0.0391** | [−0.1628, +0.0809] | 0.529 | 1.000 | REJECT |
| `1w` | 212 | 0.106 | 0.5330 | 0.5896 | −0.0240 | [−0.0987, +0.0992] | 0.657 | 1.000 | REJECT |
| `5w` | 212 | 0.106 | 0.3774 | 0.5943 | **−0.1194** | [−0.2504, **−0.0056**] | 0.054 | 1.000 | REJECT |

**Coverage is 10.6%** — a 2.0σ band trigger is a rare-event signal by construction, unlike
most of HT-1's always-on candidates. 212 calls clears the resolution floor (`MIN_CALLS=200`)
with no margin to spare; 64 independent cutoffs clears `MIN_INDEPENDENT_CUTOFFS=20`
comfortably.

**At `5w`, the interval lies entirely below zero** — the same pattern HT-1 found in 18 of
its original 27 candidates. Combined with HT-1's 81 tests under one Holm–Bonferroni family
of 84, `p Holm = 1.0`: not significant after correction, exactly as HT-1's own negative
`5w` intervals were not. **This is not a licence to invert the sign** — the same rule
`HT1_TOURNAMENT_PREREGISTRATION.md` §6 states, and `AMS-1` §11.3 before it, applies
unchanged: a negative uncorrected interval is not a discovery of a contrarian signal.

---

## 3. Reading

`vwap_reversion` joins HT-1's inventory as one more technical/rule candidate that does not
beat buying and holding on this history, at any of the three horizons tested. It does not
change HT-1's own finding — "trend-following is the only coherent pattern, and it is not
significant" — because `vwap_reversion` is explicitly a *reversion*, not a trend, candidate,
and it fails in the same direction reversion candidates already did (`pine.vix_fix`,
`technical.bollinger`'s reversion construction, both among HT-1's `5w` negatives).

**What this does not say:** it is not a finding about VWAP as a concept, only about this
specific 10-session/2.0σ swing formulation on this 26-symbol universe. It is not a
demotion of anything — nothing is in production. It does not touch HT-1's own 27-candidate
result, which is unchanged and unscored again here.

---

## 4. What remains open under `HT2_TOURNAMENT_PREREGISTRATION.md`

`orb_1h` (the hourly opening-range-breakout proxy) still needs its own power gate before any
measurement — §4 of that document — because its usable free history (≤730 days of `1h`
bars) is categorically shorter than this grid's nine years, and HT-1's resolution numbers do
not transfer to it. Not built here.

---

## 5. Verification

- Fast suite: **1250 passed, 87 skipped** — green, before this run.
- `core/tournament.py`, `CANDIDATES`, and `app/tournament.sqlite3` byte-for-byte /
  row-for-row unchanged — this study writes to no store, only in-memory frames and two new
  CSVs (`reports/ht2_vwap_raw.csv`, `reports/ht2_vwap_leaderboard.csv`).
- `reports/ht1_leaderboard.csv` read-only, unmodified.
- No production engine file (`ultimate.py`/`forecast.py`/`indicators.py`) touched. Sealed
  exam not accessed. Production weight `0.0`.
