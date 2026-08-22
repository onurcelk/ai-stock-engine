# VIX1 power gate — result: FAIL, study closed

**Date:** 2026-08-22
**Protocol:** `alpha/VIX1_PREREGISTRATION.md` §5. Run **before** any point estimate for this
study was read, printed, or written to any file — `alpha/vix1_power_gate.py` computes only
bootstrap half-widths from a per-cutoff advantage series centred on its own sample mean
immediately after computation, following the same discipline as
`alpha/pead1_power_gate.py` and `alpha/orb1h_power_gate.py`.

---

## 0. The result

> ```text
> VIX1 GATE: ALL WINDOWS FAIL -- VIX1 MUST NOT RUN
> ```

| Window (sessions) | Flagged cells | Independent cutoffs | Block | Achieved half-width | MDE | Verdict |
|---:|---:|---:|---:|---:|---:|---|
| 5 | 362 | 74 | 4 | **7.57 pts** | 3.0 pts | FAIL |
| 20 | 362 | 74 | 4 | **5.45 pts** | 3.0 pts | FAIL |

Both windows exceed the 3.0-annualised-percentage-point MDE by a wide margin (2.5x and
1.8x). **Unlike PEAD-1's and `orb_1h`'s gates, this one failed as its pre-registration
expected was possible** — a genuine outcome, not the "surprise" the other two produced.

---

## 1. Why this one failed where the other two passed

Realised volatility is a substantially noisier quantity to estimate than a return: a
5-session or 20-session standard-deviation estimate has heavy sampling variance on its own
terms, before any predictive claim is even asked of it — the reason `VIX1_PREREGISTRATION.md`
§5 named window-estimate stability, not a peeked outcome, as the selection criterion in the
first place. Combined with only **74 independent cutoffs carrying a flag** (`williams_vix_fix`'s
"bottom" condition is a genuinely rare capitulation signal, not an always-on indicator), the
achievable resolution never had much chance of clearing a 3-point bar — a materially harder
combination than PEAD-1's 647 weeks or `orb_1h`'s 915 dates of a comparatively low-variance
same-session return.

---

## 2. Disposition — per the pre-registration's own rule

`VIX1_PREREGISTRATION.md` §6: *"If the gate fails at every candidate window, VIX1 is
recorded as 'not resolvable on this history' and closed."* **VIX1 is CLOSED.** No
confirmatory measurement is run. **0 budget slots spent** — a failed power gate is a
recorded finding, not a spent attempt, the same accounting `Family10_pilot`'s admissibility
FAIL used.

**What is barred as a consequence**, restated from §7: no lowering the 3.0-point MDE, no
third window, no change to `williams_vix_fix`'s frozen parameters, no switch to a different
flag construction to make the gate pass. The correct reading is that this specific timing
idea — flag on `pine.vix_fix`'s own construction, measure realised-vol contraction — is not
resolvable on this history, not that volatility contraction around fear spikes does not
exist.

---

## 3. What this closes out

This was the last of the six candidates named in the 2026-08-22 account-holder directive.
All six are now resolved:

| Candidate | Verdict |
|---|---|
| `vwap_reversion` | REJECTED |
| `orb_1h` | REJECTED |
| PEAD-1 (SUE, event-time) | REJECTED — real effect, sub-threshold, market-confounded |
| VIX1 (vol-timing signal) | **Gate FAILED — not resolvable on this history, closed** |
| Options execution layer | Inadmissible — no free point-in-time data exists |
| (PEAD and VIX mean reversion were the two reopened closed findings; both now closed again, on new evidence) | |

---

## 4. Verification

- Fast suite: 1282 passed, 87 skipped — green.
- `core/tournament.py`'s `CANDIDATES` roster, `app/tournament.sqlite3`, and `core/pine.py`:
  untouched — this study reads both read-only and writes to no store.
- No production engine file touched. Sealed exam not accessed. Production weight `0.0`.
- 5 new tests (`app/tests/test_vix1_power_gate.py`): realised-vol arithmetic, the
  too-few-cutoffs refusal, and the pass/fail boundary.
