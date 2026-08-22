# orb_1h power gate — result

**Date:** 2026-08-22
**Protocol:** `alpha/HT2_TOURNAMENT_PREREGISTRATION.md` §4. Run **before** any confirmatory
measurement and before any point estimate for this candidate was read. `alpha/orb1h_power_gate.py`
follows the identical centre-before-inspecting discipline as `alpha/pead1_power_gate.py` (§0
of that gate's report): the per-session advantage series is centred on its own mean
immediately after computation, and only the centred series's bootstrap half-width is ever
printed or returned.

---

## 0. The result — also contrary to the pre-registration's stated expectation

> ```text
> orb_1h GATE: PASS. Achieved half-width 7.3 bp against a 39 bp MDE — a 5.3x margin.
> ```

`HT2_TOURNAMENT_PREREGISTRATION.md` §4 stated, in advance, that this gate was "a real
candidate to fail on power alone" given only ≤730 days of free hourly history. **That
expectation was wrong for a reason worth recording precisely**: the repository's local
`1h` cache (`app/cache/*__1h.csv`) has accumulated since **2023-09-26** through ordinary
app/ledger use — nearly three years, not the 730-day ceiling a single fresh fetch would be
limited to (Yahoo's 730-day cap applies to how far back *one download* can reach, not to
how much history a cache can accumulate over time). This is incidental, not something to
rely on for future candidates: a from-scratch `1h` fetch today would still be capped at 730
days, and this margin should not be assumed for any hourly-bar study that starts without
this cache's head start.

**A second reason, more fundamental:** this candidate's outcome is a same-session
close-to-close return (bar 1 to the session's last bar), which has far lower variance than
a multi-day or multi-week forward return. Resolution here was never really about how many
years of data existed — it was about how many independent trading *days* existed (915), and
915 independent days of a low-variance intraday outcome resolves far below 39 bp regardless
of the underlying history's length.

---

## 1. What was measured

| | |
|---|---|
| Source | `app/cache/*__1h.csv`, 31 symbols, no network fetch |
| Signal | Session's first `1h` bar sets the opening range; a breakout call is made if the *second* bar's close clears the range high (BUY) or low (SELL); sessions with no breakout make no call |
| Outcome | Same-session return from the second bar's close to the session's last bar's close, signed by the call |
| Aggregation | One value per calendar date (mean across symbols with a call that day), before bootstrapping — the same per-unit aggregation `tournament.leaderboard` uses before bootstrapping over cutoffs |
| MDE | 39 bp — Single-Name Phase 1's covered-book resolution, the same standing reference `PEAD1_POWER_GATE.md` uses |

| | |
|---|---|
| Sessions with a breakout call | 7,241 |
| Independent dates | 915 |
| Block length (days) | 4 |
| **Achieved half-width** | **7.3 bp** |
| MDE | 39.0 bp |
| **Verdict** | **PASS** |

**No point estimate was inspected to produce this table** — only the counts and the width.

---

## 2. What happens next

`orb_1h` may now proceed to a confirmatory pre-registration and measurement, per
`HT2_TOURNAMENT_PREREGISTRATION.md` §4's own rule ("`orb_1h` may proceed only after its own
power gate is built and passes"). That pre-registration — fixing the CONTINUE rule, the
horizon(s) read from the outcome (currently same-session only; whether to also read a
next-session or multi-day outcome is a design choice not yet fixed), and the noise-control
procedure — does not exist yet and must be committed before the first inspected measurement,
per this programme's standing sequencing rule.

---

## 3. Verification

- Fast suite: 1261 passed, 87 skipped — green.
- No production engine file touched. `core/tournament.py`'s `CANDIDATES` roster and
  `app/tournament.sqlite3` untouched. Sealed exam not accessed. Production weight `0.0`.
- 7 new tests (`app/tests/test_orb1h_power_gate.py`): breakout-direction correctness in both
  directions, the no-call case, the too-few-bars refusal, a same-session PIT-safety check
  (a later bar's extreme move cannot change the call already fixed at bar 1), and the
  pass/fail boundary arithmetic.
