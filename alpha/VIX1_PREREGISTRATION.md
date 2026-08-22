# VIX1 — pre-registration: does a Williams VIX Fix capitulation flag predict a realised-vol contraction?

**Written 2026-08-22, before the power gate is run and before any forward return is read.**
Commissioned under `reports/OPTIONS1_ADMISSIBILITY.md` §1's six-condition reuse test
(reopening `pine.vix_fix`, rejected by HT-1 as a single-name *directional* signal) and §5's
named budget: **ONE confirmatory study**, own slot, drawing nothing from V3, V4, PEAD-1,
HT-1 or HT-2.

**Not the options execution layer.** This is the free-data-only path §4 of the
admissibility pilot left open after the options chain/greek/margin build-out was found
inadmissible (no free point-in-time source exists). VIX1 tests only whether the underlying
*timing idea* — elevated fear predicts calmer markets ahead — has any measurable content,
using nothing but daily OHLCV this programme already has cached.

---

## 1. What is reused, verbatim, and why that satisfies the six-condition test

**Construction:** `core.pine.williams_vix_fix` (period=22, bb_length=20, multiplier=2.0,
lookback=50, high_percentile=0.85, low_percentile=1.01) — HT-1's exact `pine.vix_fix`
parameters, unmodified. The **flag** used here is that function's own `bottom` column:
`(wvf >= upper_band) | (wvf >= range_high)` — the identical "fear cleared its own band"
condition HT-1 measured, read directly rather than through the position-stance wrapper
`tournament.closed_form_calls` uses for the tournament roster (§2 explains why).

| # | Condition (from `reports/OPTIONS1_ADMISSIBILITY.md` §1) | Status |
|---|---|---|
| 1 | Materially different target | **MET** — realised-vol contraction, not directional price return |
| 2 | Materially different arm/use | **MET** — a one-sided timing flag, not a standalone directional call |
| 3 | No HT-1 result rescored | **MET** — HT-1's `pine.vix_fix` row is unchanged, not reread as evidence |
| 4 | No sign flip on an HT-1 outcome | **MET** — this is not `pine.vix_fix` inverted; it is the same flag against a different outcome |
| 5 | No HT-1 parameter retuned from HT-1's results | **MET** — every constant above is copied from `pine.py`, not touched |
| 6 | Fresh budget/stopping rule | **MET** — §6 |

---

## 2. Why the raw flag, not the tournament's position-stance wrapper

`tournament.closed_form_calls` reads `indicators.stance(pine.signals("vix_fix", frame))` —
a **running position** (long after a flag, flat once the reading falls back under its own
20-bar mean), built for a directional backtest. VIX1's hypothesis is about the **flagged
bar itself** — is fear elevated right now — not about holding a position until an exit rule
fires. Reading `bottom.iloc[-1]` directly at each cutoff is the more faithful test of the
actual hypothesis, and it is a **read of the identical underlying construction**, so
condition 5 above still holds: nothing about `williams_vix_fix` was changed, only which of
its already-computed outputs is consulted.

---

## 3. The design

| # | Element | Specification |
|---|---|---|
| 1 | **Sample** | HT-1's own grid and cells: 88 independent cutoffs, stride 25 bars, majority calendar, 2017-11-09 → 2026-07-10, `tournament.build_grid`/`admissible_cells`, unmodified |
| 2 | **Signal** | `bottom.iloc[-1]` on the truncated frame at each cell — a flag, not a directional call. Cells where it is `False` make no call (coverage < 100% is expected, as with `vwap_reversion`) |
| 3 | **Outcome window** | Realised volatility (std of daily simple returns) over the **W sessions immediately following** the cutoff, compared to realised volatility over the **W sessions immediately preceding** it. `W` is fixed at gate time (§5), from window-stability grounds only, before any forward return is read |
| 4 | **Advantage** | `trailing_vol − forward_vol`, in **annualised percentage points** (`× √252 × 100`), read only where the flag is `True` |
| 5 | **MDE** | **3.0 annualised percentage points of vol contraction** — a fresh judgement, since no standing reference exists in this programme for a volatility-contraction claim (the 39 bp references throughout `PEAD1_*` and `ORB1H_*` are *return* thresholds and do not apply to a volatility target). Fixed here, before any measurement, on the same footing as `V4_CHARTER.md` §7.3's 1.5× factor: "a judgement, and it is fixed here... not adjusted afterwards." Three points of annualised vol is roughly the gap between a calm and a moderately anxious equity regime — large enough to matter for a premium-selling timing decision, not merely large enough to detect |

---

## 4. CONTINUE rule, all three required

1. Advantage (mean, per-independent-cutoff-aggregated) ≥ **+3.0 annualised vol points**.
2. 95% moving-block bootstrap interval excludes zero on the favourable side.
3. Breadth > 0.50 **and** both chronological halves of the sample show positive mean
   advantage.

**Noise control:** 30 permutations of which cells are treated as flagged (holding the total
flagged count and all realised vol outcomes fixed, reshuffling which cells carry the flag).
Fails if the median permuted advantage exceeds +0.5 points or more than 10% of draws clear
the CONTINUE threshold alone.

**Anything less is REJECT.**

---

## 5. The power gate — must be run first, half-width only

Following `PEAD1_CHARTER.md` §6's discipline exactly: the per-cutoff advantage series is
computed (unavoidable — variance is a property of the data), immediately centred on its own
mean, and only the centred series's bootstrap half-width is ever printed or returned. The
window `W` (candidates: 5, 20 sessions — matching HT-1's `1w`/`5w` horizons so the result is
comparable to the rest of this census) is selected on **the stability of realised-vol
estimates at that window**, not on any peeked outcome: a 5-session realised-vol estimate
from 5 daily returns is noisy on its own terms, independent of any predictive claim, and
that noise is measurable without reading a single forward-looking predictive relationship.

---

## 6. Budget and stopping rules

> **VIX1 budget: ONE confirmatory study.** If the gate fails at every candidate window,
> VIX1 is recorded as "not resolvable on this history" and closed. If the gate passes and
> the confirmatory study then fails, VIX1 is REJECTED and closed. There is no second
> window, no second flag construction, no sign flip, no learner.

Draws no slots from V3, V4, PEAD-1, HT-1, or HT-2.

---

## 7. Prohibited, restated

* No modification to `williams_vix_fix`'s parameters.
* No second outcome window beyond the one selected at gate time.
* No sign flip — a negative result is not evidence for an inverted (vol-expansion) claim.
* No promotion of a noise-control draw or a diagnostic to the study's own result.
* No citation of HT-1's `pine.vix_fix` result as evidence either way — different target,
  different question, per §1 condition 3.

---

## 8. Recording

Gate result: `reports/VIX1_POWER_GATE.md`. If it passes, the window is fixed by amendment
here before the first inspected measurement, matching `PEAD1_CHARTER.md`/`HT2_*`'s
convention. Confirmatory result, whichever it is: `reports/VIX1_RESULT.md` and
`reports/EXPERIMENT_REGISTRY.md` (append-only).
