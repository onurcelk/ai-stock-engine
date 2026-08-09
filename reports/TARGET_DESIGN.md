# Target Design — V3 Phase 3

**Written 2026-08-09 under master roadmap v2 §5. Deliverable per §5.**

**Objective:** stop optimizing for microscopic IC improvements; decide what the system
should predict, with each candidate carrying its measured class balance and its **power
implication (§2.6)** rather than an aesthetic preference.

**What was measured, and what was not.** Class balances and outcome distributions below
are **measured on the 316 development cutoffs only** — `examset.load().development`, so
the 72 sealed exam cutoffs are excluded by construction and remain untouched. Only raw
outcome distributions were computed: no feature was read, no model fitted, no prediction
scored. Reproducible via `alpha/target_design_measure.py` (SHA-256
`66618c43c1fa21bcda8cc5df1af6e0e0fa0e6a0607875fdb015ba8604c722fbd`).

**One measurement caveat, stated up front:** the measurement universe is the full local
cache (median cross-section 605) rather than point-in-time index membership (panel
median 465). Class balances on the PIT universe will differ modestly. This does not
change any conclusion below, and Phase 4 recomputes everything on the PIT panel anyway.

---

## 1. The power table — the constraint every target lives under

The record's calibration (roadmap §2.6): half-width **0.00827 IC at 255 paired
cutoffs**, scaling as √(255/n). Weekly (5-session) cutoff spacing.

| Horizon | Cutoffs with outcome | **Non-overlapping** | Achievable half-width (paired IC) |
|---|---:|---:|---:|
| **5D** | 316 | **316** | **~0.0074** |
| **10D** | 315 | **158** | **~0.0105** |
| **20D** | 313 | **79** | **~0.0149** |

Two readings, both required:

* **Every doubling of the horizon costs √2 of resolution.** At 20D the design can only
  see effects ≥ ~0.015 IC — twice the 5D floor and ~10–30× anything V2 measured.
* **§2.6's counter-reading:** a target with a larger per-observation effect and fewer
  cutoffs may still be strictly better. A 20D effect of 0.020 is visible at 79 cutoffs;
  a 5D effect of 0.005 is invisible at 316. **The question is the ratio, not the count.**

At horizons past the 5-session spacing, windows overlap; §2.2 applies — purge and
embargo at the horizon, and the moving-block bootstrap in `alpha/stats.py` remains the
headline interval, with the **non-overlapping count** reported as the honest effective
n.

---

## 2. The four candidates, measured

### Target A — forward return (cross-sectional alpha rank). *The incumbent instrument.*

The record's target: `alpha_5d = R_asset − R_SPY`, winsorised for training, scored by
within-cutoff Spearman IC. Already built, already tested, already calibrated
(`alpha/targets.py`).

| Property | 5D | 10D | 20D |
|---|---|---|---|
| alpha > 0 rate (vs SPY) | **0.491** | 0.491 | 0.495 |
| Sample size | 316 cutoffs | 158 eff. | 79 eff. |
| Achievable half-width | **0.0074** | 0.0105 | 0.0149 |

**Balanced by construction at every horizon** — benchmarking against SPY removes the
market draw, which is precisely why the cross-section is the research instrument
(§1.1). No degenerate baseline exists for it: "always-up" is meaningless on alpha.

### Target B — directional return (single-name). *The product's language.*

| Property | 5D | 10D | 20D |
|---|---|---|---|
| Up-rate, pooled | 0.547 | 0.553 | 0.567 |
| **Up-rate per cutoff, p10 → p90** | **0.24 → 0.75** | 0.27 → 0.74 | 0.26 → 0.73 |

The pooled rate looks tame; the per-cutoff spread is the real finding. **The base rate
of "up" swings from 24% to 75% depending on the week.** Pooled directional accuracy is
therefore mostly a bet on which weeks are in the sample — the exact pathology
`validation/REPORT.md` measured, where always-up beat every component because the
period's up-rate was 64.6%. Directional accuracy is only meaningful **per cutoff,
against that cutoff's own up-rate**, clustered by date — which is how Phase 7b already
scores (roadmap §9b).

### Target C — economically meaningful move (±5% classes). *The roadmap's hinted favourite.*

| Class share | 5D | 10D | 20D |
|---|---|---|---|
| BUY (≥ +5%) | 0.105 | 0.181 | **0.285** |
| SELL (≤ −5%) | 0.091 | 0.144 | **0.197** |
| HOLD (between) | **0.804** | 0.675 | 0.518 |
| BUY share per cutoff, p10 → p90 | 0.02 → 0.20 | 0.04 → 0.36 | 0.08 → 0.47 |

The §5 hint was that C's coarser classes are plausibly a larger effect. The measurement
adds the constraint the hint was missing: **at 5D a ±5% move is a 10% tail event** —
the classifier would be hunting rare events with 80% of rows in HOLD — while at 20D the
classes are usable (28/20/52) **but only 79 independent draws exist**. The class-share
instability (BUY share swinging 8%–47% across cutoffs at 20D) also means class-balanced
metrics must be computed per cutoff, never pooled.

A fixed ±5% band is also **not vol-adaptive**: in a quiet regime almost nothing clears
it, in 2022 half the cross-section does. The band would need per-regime renormalisation
to mean the same thing across the sample — which is Target D by another name.

### Target D — risk-adjusted direction (move vs own volatility).

Move scaled by the name's trailing 60-session vol, √h-scaled; thresholds at ±1σ:

| Class share | 5D | 10D | 20D |
|---|---|---|---|
| z ≥ +1 | 0.150 | 0.161 | 0.180 |
| z ≤ −1 | 0.122 | 0.119 | 0.115 |
| \|z\| < 1 | 0.728 | 0.720 | 0.705 |

**Class balance is nearly horizon-invariant and far more stable across regimes** than
C's — the vol denominator absorbs the regime. The cost: the target now depends on a
fitted quantity (the vol estimate), so a leakage test must pin that the vol window ends
at the cutoff, and the economic meaning is one step removed from "a 5% move".

---

## 3. §5 mandatory comparison, condensed

| Criterion | A (alpha rank) | B (direction) | C (±5% classes) | D (vol-adjusted) |
|---|---|---|---|---|
| Adequate sample | **best** — 316 at 5D | same counts | needs 20D → **79** | same as C but usable at 10D |
| Stable class balance | **yes, by construction** | **no** — 0.24–0.75 per cutoff | no — regime-driven | **yes** — vol-absorbed |
| Economic meaning | via spread/net-of-cost | direct | **most direct** | one step removed |
| Leakage surface | known, tested | known | fixed thresholds — none new | **vol window must be pinned** |
| Portfolio compatibility | **native** (rank → top-N) | needs sizing rule | native (act on BUY/SELL) | native |
| Power at its natural design | **0.0074** | n/a (accuracy metric) | **0.0149** at 20D | ~0.0105 at 10D |
| Degenerate baseline | none | **always-up wins by default** | HOLD-always at 5D (80%) | HOLD-always (72%) |

---

## 4. Decisions

### 4.1 Primary research target — **Target A: cross-sectional alpha rank, 5-session horizon, unchanged from the record.**

For Phase 5 information-only tests and the first Phase 6 model. Reasons, in order of
weight:

1. **Power.** 316 independent cutoffs and a 0.0074 floor — the best resolution any
   design on this history can buy (§1). Every alternative halves it or worse.
2. **Comparability.** B3 (+0.02836) and 12-1 momentum are measured on exactly this
   target. Changing the target changes the incumbent's number too, and the programme
   would be comparing against a benchmark nobody has measured.
3. **Baseline sanity.** Alpha is balanced by construction (0.491); nothing degenerate
   to accidentally lose to.
4. **Tooling.** `alpha/targets.py`, `protocol.py`, `walkforward.py`, `stats.py` are
   built, tested and frozen-calibrated for it.

### 4.2 The horizon question is a **family-level pre-registration decision, made on priors, before any fit.**

Family 1's information (post-filing drift) classically accrues over weeks to months; a
5-session window may catch only a slice of it. The temptation after Phase 5 will be to
"check whether 10D looks better". **That is horizon shopping, and it is barred (§2.4).**
The rule fixed now:

> Each family's preregistration names **one primary horizon** (5D or 10D), chosen on
> priors and its §2.6 arithmetic, **before the first fit**. Any second horizon is a
> declared secondary hypothesis, counted in the multiplicity correction, and can never
> be promoted to primary after results are seen. 20D is available only under the §2.6
> trade: the pre-registration must argue the expected effect ≥ ~0.015, twice the 5D bar.

### 4.3 Product-side target for Phase 7b — **Target B scored per cutoff against that cutoff's own up-rate, with C's bands as the action layer.**

The product speaks BUY/HOLD/SELL (§1). Phase 7b therefore scores **direction on the
calls made**, against always-up and no-change **on the period's actual up-rate**
(roadmap §9b — this is already the `validation/` scoring design, reused per the
manifest §6). The BUY/SELL action thresholds are C's economic bands **at the model's
horizon**, fixed in the Phase 7b preregistration; a HOLD-heavy output is acceptable and
expected — the abstention machinery is the one vindicated part of V1.

### 4.4 Target D is the **declared fallback**, not a parallel arm.

If a family's preregistration argues its effect is regime-conditional (vol-dependent),
it may adopt D at 10D **instead of** A — not alongside it. D never runs as a second
target on the same information; that spends power twice on one idea (§0.3 finding 9).

### 4.5 What is ruled out

* **Pooled directional accuracy as a primary metric, at any phase.** The 0.24–0.75
  per-cutoff base-rate swing makes it a market-draw thermometer.
* **Target C at 5D.** A 10% tail event with 80% HOLD is a rare-event problem this
  history cannot power.
* **Any target change after Phase 5 results are visible.** The target is part of the
  §21 family budget: a family that fails on Target A has failed; re-running it on
  Target C or D is the "one more carrier" move that §21 names and forbids.

---

## 5. Power implication, stated per §2.6 for the registry

For the first study (Family 1 on Target A at 5D):

| | |
|---|---|
| Achievable half-width, 316 dev cutoffs, paired vs B3/momentum | **~0.0074 IC** (record-calibrated) |
| Smallest effect worth acting on (economic floor, §2.3/§10) | to be fixed in the preregistration from the cost model; **not lower than ~0.0074**, else unrunnable |
| V2's entire feature set, for scale | +0.0005 to +0.0014 |
| Therefore the family's hypothesis must claim | **an effect ≥ ~5–10× V2's**, i.e. ≥ 0.007–0.015 IC, stated before the first fit |

The §2.6 gate itself — smallest-effect statement, exact half-width computation with
`alpha/stats.py` on the actual paired design, runnable/not-runnable verdict — is
computed **in the Family 1 preregistration**, not here. This document fixes the target
and horizon rules it will be computed under.
