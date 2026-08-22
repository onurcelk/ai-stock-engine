# HT-2 — pre-registration: two new price-only candidates

**Written 2026-08-22, before any HT-2 measurement code exists and before any forward return
is read.** Not an amendment to HT-1: HT-1's roster, grid, gate and result are a closed,
append-only record (`CLAUDE.md` §1.1, `reports/HT1_TOURNAMENT_RESULT.md`) and are not
edited, re-run, or re-scored here. HT-2 is a **new census**, of two candidates HT-1 never
had, reusing HT-1's validated instrument (`core/tournament.py`'s paired block-bootstrap and
Holm–Bonferroni machinery) where the data supports it and building a separate,
freshly-gated instrument where it does not (§2).

**Class: new candidates, not a reopening.** Opening-range breakout and VWAP mean reversion
were never tested by HT-1 or any prior study, so none of `CLAUDE.md` §1.3's reopening
conditions apply — this needs ordinary pre-registration discipline, not a six-condition
reuse charter. Both are, however, in the same broad technical/rule class HT-1 measured at
0-of-27, and that prior is stated in §5 so a result here is read against it, not in a vacuum.

---

## 1. What HT-1 already established, and does not need re-establishing

**(HT-1)** 27 price-only components, one grid, one baseline: 0 beat buy-and-hold. Trend
-following was "the only coherent pattern, and it is not significant." 351 pairs measured,
0 near-clones — genuine distinctness bought nothing. **These findings are not retested.**
HT-2 adds exactly two new rows to the inventory HT-1 census'd, using HT-1's own instrument
wherever the underlying data supports it.

---

## 2. A data-admissibility check, done before any design commitment

Checked directly, 2026-08-22, via `yfinance` (this programme's default source):

| Interval | Free history actually available |
|---|---|
| 1-minute | ~1 week |
| 5-minute / 15-minute | ~2 months |
| 1-hour | ~730 days (~2 years) |
| Daily | full history (the HT-1 grid: 2017-11-09 → 2026-07-10, ~9 years) |

**Classical opening-range breakout is defined on the first 5–30 minutes of a session.** At
~2 months of free 5-minute history, a backtest has at most a handful of independent trading
days per symbol — nowhere near HT-1's 88 independent cutoffs, and not enough to build a
credible power gate at all. **A true intraday-open-range design is therefore inadmissible
on power grounds before any candidate-specific gate is even attempted**, for the same
reason `OPTIONS1_ADMISSIBILITY.md` found the options execution layer inadmissible: the free
data does not go back far enough to ask the question, not merely far enough to answer it
favourably.

**The admissible substitute, stated as a substitute and not disguised as the original
claim:** an **hourly-bar opening-range proxy** — the range of a session's first `1h` bar,
tested for breakout continuation against the same session's later `1h` bars — using the
730-day free `1h` history already fetched by this programme's live/collector path
(`core/live.py`). This is a different, coarser instrument than 5-minute ORB and is reported
as one. It needs its **own** power gate (§4) because its sample depth (≤730 days) is
categorically shorter than HT-1's 9-year daily grid, and HT-1's resolution numbers do not
transfer.

**VWAP mean reversion has no such problem.** A session-level (intraday) VWAP fade would
have the same 5-minute-data ceiling as ORB, but the classical **swing-VWAP** variant —
price deviation from a rolling multi-day volume-weighted average, faded over the 1w/5w
horizons HT-1 already used — is fully computable from the daily OHLCV history HT-1's own
grid already reads (`technical.obv` in HT-1's roster already consumes daily volume). This
candidate reuses HT-1's exact grid, universe, admission rule and gate **without
modification**.

---

## 3. The two candidates, defined precisely

### 3.1 `technical.orb_1h` (hourly opening-range breakout proxy)

* **Range:** each session's first `1h` bar's high/low, per symbol.
* **Signal:** long if a later `1h` bar in the same session closes above the range high;
  short if it closes below the range low; flat otherwise. Direction is read at the bar the
  breakout occurs, scored against the pre-registered forward horizons from that bar.
* **Grid:** every `1h` bar with a preceding same-session opening range, over the full free
  window (§2) — expected on the order of 400-500 trading sessions across the 30-symbol
  collection universe, materially fewer independent cutoffs than HT-1's 88 once same-session
  and cross-symbol correlation is accounted for (§4).
* **Data door:** `core/live.py` `fetch(..., interval="1h")`, the same call the ledger and
  collector already use. No new data source.

### 3.2 `technical.vwap_reversion` (swing VWAP mean reversion)

* **VWAP:** rolling volume-weighted average close over a pre-registered daily window (a
  single fixed choice, from {10, 20} sessions — fixed at gate time from variance grounds
  only, not scanned after seeing a result, per the same rule HT-1 §0.1 applied to every
  other candidate's parameters).
* **Signal:** short (expect reversion down) when price trades a pre-registered number of
  standard deviations above rolling VWAP; long when equivalently below; flat otherwise.
* **Grid:** HT-1's own — 88 independent cutoffs, 2017-11-09 → 2026-07-10, stride 25 bars on
  the majority calendar, 26-symbol universe, three horizons (1d/1w/5w). **Reused exactly**,
  because the underlying data (daily OHLCV) and the resolution question are identical to
  every technical candidate HT-1 already measured.

---

## 4. Power, gated separately for each candidate

**`vwap_reversion`** inherits HT-1's own power gate result outright: HT-1 measured that
"all 81 candidate × horizon cells cleared the pre-registered resolution floor" on this exact
grid, and `vwap_reversion` is one more member of the same technical family on the same data.
No new gate computation is required; the existing one already covers it.

**`orb_1h` requires its own gate, built before any breakout signal is read**, because its
sample is structurally different (≤730 days, `1h` bars, session-level clustering rather than
25-bar-stride independence). The gate must:

1. Establish the independent-cutoff count for `1h` bars over the free window, accounting for
   same-session autocorrelation (a breakout signal and its own outcome bar sit inside one
   trading day, which the 25-bar daily stride HT-1 used does not address).
2. State the smallest advantage worth acting on (the MDE) and refuse to proceed if the
   achieved half-width exceeds it — the same refuse-before-permission rule as every gate
   this programme runs.
3. Not borrow HT-1's daily-grid half-widths, which describe a different instrument.

**Expected outcome, stated in advance:** at well under 2 years of `1h` bars across 30
symbols, `orb_1h`'s gate is a real candidate to fail on power alone, before any directional
question is even asked — the same honest expectation `V4_CHARTER.md` §6.2 set for its own
gate. That would not be a defect in the design; it would be the free-data ceiling asserting
itself, exactly as it did for classical (5-minute) ORB and for the options execution layer.

---

## 5. What a result means, read against HT-1's prior

| Outcome | Reading |
|---|---|
| Both candidates REJECT (advantage does not clear zero, or the gate fails) | Consistent with HT-1: the technical/rule family remains empty on this history. Adds two more measured rows to the inventory, nothing more |
| One or both candidates pass their confirmatory criteria | A genuine addition to HT-1's null — reported with the same rigor (paired interval, Holm–Bonferroni across the full combined candidate set, not just these two) before any claim is made |

**Multiplicity is combined with HT-1's own 81 tests, not treated as a fresh family of two.**
Running Holm–Bonferroni over only 2 new tests while ignoring the 81 already run against the
same baseline would understate the true multiple-comparisons burden this programme has
spent on price-only technical candidates to date.

---

## 6. Prohibited, restated

* No re-run of any of HT-1's original 27 candidates under any new parameterisation.
* No promotion of `orb_1h` to a "true" opening-range claim — it is reported as an hourly
  proxy, permanently, regardless of outcome.
* No sign flip on either candidate after seeing a negative result.
* No threshold, window, or standard-deviation multiplier chosen after any forward return is
  read.
* No challenger built from either candidate alone — HT-1 §8.2's two-survivor rule and the
  AMS-1 cross-family-agreement bar both apply unchanged.

---

## 7. Recording

This document is committed before any HT-2 measurement code exists. The `orb_1h` power gate
is its own committed artefact, before any breakout signal is read. Results, if run, land in
`reports/HT2_TOURNAMENT_RESULT.md` with the same per-cutoff series discipline as HT-1.

**Neither candidate is authorised to run by this document.** `vwap_reversion` may proceed
directly to measurement (its gate is already satisfied by HT-1's own). `orb_1h` may proceed
only after its own power gate is built and passes.

---

## Amendment 1, 2026-08-22 — `vwap_reversion`'s window and threshold, fixed before measurement

Appended before any forward return for this candidate was read; §3.2's wording above is left
unaltered.

**Window: fixed at 10 sessions**, chosen from the {10, 20} candidate set named in §3.2, on
variance-only grounds computed from the 30-symbol collection universe's cached daily history
(`app/cache/*__1d.csv`, no forward return, no cutoff-relative quantity):

| Window | Symbols with usable history | Mean coefficient of variation of the 63-day rolling std of the VWAP deviation | Median |
|---:|---:|---:|---:|
| 10 sessions | 28 | **0.3754** | 0.3759 |
| 20 sessions | 28 | 0.4162 | 0.4280 |

A threshold expressed as "a number of standard deviations above/below VWAP" is only
well-specified if that standard deviation is itself reasonably stable through time; the
10-session window's deviation is measurably more homoskedastic (lower CV) than the
20-session window's, on every one of the 28 symbols with sufficient history. **This is the
sole criterion. No forward return, accuracy figure, or IC of any kind entered this
decision.**

**Threshold: fixed at 2.0 standard deviations**, taken directly from this repository's own
standing convention for a reversion band — `indicators.bollinger`'s `deviations: float =
2.0` default, already the parameter `technical.bollinger` was measured under in HT-1. Reusing
an existing, already-precedented constant rather than choosing a new one removes the
possibility that this threshold was picked to flatter `vwap_reversion` specifically.

Both parameters are now frozen for `vwap_reversion` and may not be revisited after any
result exists.
