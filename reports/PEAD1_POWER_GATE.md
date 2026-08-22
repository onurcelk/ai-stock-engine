# PEAD-1 power gate — result

**Date:** 2026-08-22
**Protocol:** `alpha/PEAD1_CHARTER.md` §6. Run **before** any confirmatory pre-registration
and **before** any point estimate for this candidate was read, printed, or written to any
file. `alpha/pead1_power_gate.py` computes only bootstrap half-widths from a per-event
advantage series that is centred on its own sample mean immediately after computation —
the mean itself is a local variable, discarded (`del values` in the source), never returned,
never logged. This is the same discipline `reports/V5_HISTORICAL_REPLAY.md` used for HR-1's
gate ("the paired series was centred immediately, and a percentile bootstrap's width is
invariant to centring").

---

## 0. The result — contrary to the charter's own stated expectation

> ```text
> PEAD-1 GATE: 5-session and 20-session windows PASS. 60-session window FAILS.
> ```

The charter's §6 stated, in advance, that this gate was "more likely to fail than to pass"
on the theory that earnings events cluster too tightly in calendar time (quarterly
"earnings season") to supply enough independent draws. **That prior was wrong, measured
directly rather than assumed.** Aggregating to one observation per calendar week (rather
than per event) absorbs the within-week clustering by construction, and the resulting
weekly series showed low enough autocorrelation (lag-1 < 0.2 at every window) that the
minimum block length of 4 weeks — the same block length HT-1 and Family-10 used for their
own paired series — was sufficient throughout.

---

## 1. What was measured

| | |
|---|---|
| Source | `alpha/edgar/facts.parquet`, concept `NetIncomeLoss`, replayed via `alpha/filings_features.replay` — the same acceptance-time step function V3/V4's SUE feature already uses |
| Universe | Symbols with both a CIK mapping (`filings_meta.json`) and cached daily price history (`alpha/cache/*.csv`) |
| Event | Each distinct SUE-bearing acceptance event per firm; the anchor bar is the first trading session strictly after (acceptance date + 1 calendar day) — a deliberately conservative PIT rule for a gate-only computation |
| Advantage proxy | `sign(SUE) × forward return` over the window, aggregated to one value per calendar week before bootstrapping |
| MDE | 39 bp — Single-Name Phase 1's covered-book 5-session resolution, reused as this program's standing single-name absolute-return reference (also used by `orb_1h`'s gate, below) |

| Window (sessions) | Events | Independent weeks | Block (weeks) | Achieved half-width | MDE | Verdict |
|---:|---:|---:|---:|---:|---:|---|
| 5 | 29,755 | 647 | 4 | **12.5 bp** | 39.0 bp | **PASS** |
| 20 | 29,597 | 644 | 4 | **27.8 bp** | 39.0 bp | **PASS** |
| 60 | 29,508 | 636 | 4 | **67.1 bp** | 39.0 bp | FAIL |

**No point estimate — sign, magnitude, or direction of the effect — was inspected to produce
this table.** Only the four columns above (counts and widths) were ever computed into a
variable that left the gate function.

---

## 2. Window selection, on variance-only grounds

Per the charter's own rule (§6.2 item 4: "a window that clears the hurdle may be selected...
on this variance-only basis, not on any peeked return"): **the 5-session window is selected**,
on the sole ground that its margin against the MDE (39.0 / 12.5 ≈ 3.1×) is far more
comfortable than the 20-session window's (39.0 / 27.8 ≈ 1.4×). The 60-session window is
dropped — not because of any predictive result, but because its own half-width already
exceeds the hurdle before any forward return's sign was ever read.

---

## 3. What happens next

Per `alpha/PEAD1_CHARTER.md` §9.4's fixed sequencing: a confirmatory pre-registration must
be committed — fixing the 5-session window, the CONTINUE rule, the controls, and the
noise-control procedure — **before** the first actual event-return is read for the
confirmatory study. That document does not exist yet and this gate does not authorise
writing it under time pressure; §6.2's discipline (variance only, no peeking) continues to
bind until it is committed.

---

## 4. Verification

- Fast suite: 1261 passed, 87 skipped — green, before and after this gate's code existed.
- `alpha/V3_*`, `alpha/V4_*`, and every frozen V3/V4 artefact: untouched, not read for
  re-evaluation.
- `alpha/edgar/facts.parquet`, `filings_meta.json`, `alpha/cache/*.csv`: read-only.
- No production engine file touched. Sealed exam not accessed. Production weight `0.0`.
- 4 new tests (`app/tests/test_pead1_power_gate.py`): zero-SUE exclusion, PIT-safety of the
  event cutoff, the too-few-weeks refusal, and the pass/fail boundary arithmetic.
