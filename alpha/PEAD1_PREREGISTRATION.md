# PEAD-1 — confirmatory pre-registration

**Written 2026-08-22, before the first event-return is read for this confirmatory study.**
This document is fixed. Corrections are appended, dated, leaving the original wording
visible — the convention `V2_3_PREREGISTRATION.md` established.

Commissioned under `alpha/PEAD1_CHARTER.md`. Authorised to proceed by the passed power gate
in `reports/PEAD1_POWER_GATE.md` (5-session window, half-width 12.5 bp vs a 39 bp MDE).
**This spends PEAD-1's one confirmatory budget slot when it runs — and it has not run.**

---

## 1. The hypothesis, restated from the charter, now with the gate's window fixed

> **H1.** SUE's surprise sign, read at the point-in-time moment a firm's earnings become
> known (EDGAR acceptance), predicts the sign of that firm's own subsequent 5-session
> return, at a magnitude this history can resolve (≥ 39 bp advantage over the trivial
> controls), with positive breadth and a bootstrap interval excluding zero on the
> favourable side.

**H0.** No relationship, or one too small for this history to see even at event-time
resolution — the same null V3 and V4 established at their own (calendar-grid,
cross-sectional) formulations.

---

## 2. The design, frozen in every element

### 2.1 Sample

Every SUE-bearing acceptance event, for every symbol with both a CIK mapping
(`alpha/edgar/filings_meta.json`) and cached daily price history (`alpha/cache/*.csv`),
with `sue != 0` and finite. Per `reports/PEAD1_POWER_GATE.md`, this is **29,755 events**
before window-maturity filtering, aggregating to **647 independent calendar weeks**.

### 2.2 Event cutoff

The first trading session strictly after `acceptance_date + 1 calendar day` — the same
conservative rule the power gate used. **Not modified.**

### 2.3 Window

**5 sessions. One only**, selected in the power gate on variance-only grounds (§3 of
`reports/PEAD1_POWER_GATE.md`). No second window is run, reported as an arm, or added
later. The 20-session window also passed the gate but is **not** run — running both and
reporting whichever looks better would be exactly the "add an arm after seeing results"
violation `CLAUDE.md` §6 item 3 forbids.

### 2.4 Feature and sign

`sue`, construction frozen verbatim per `V3_PREREGISTRATION.md` §3 (unchanged, §4.1 of
`PEAD1_CHARTER.md`). Sign **+1** by the same economic prior SUE has carried since V3.

### 2.5 Primary quantity

For event *i*: `advantage_i = sign(sue_i) × r_i`, where `r_i` is the firm's own 5-session
forward return from the event cutoff. Aggregated to **one value per calendar week** (mean
across that week's events) before any interval is computed — the same aggregation the power
gate used, chosen there and carried here unchanged because switching to a per-event
(unaggregated) statistic now would be a design change made after seeing the gate pass.

### 2.6 Mandatory controls, both required

Per `PEAD1_CHARTER.md` §5 item 5:

* **Always-flat** — the trivial zero-return control.
* **Always-long-market** — SPY's return over the identical window, read from the same
  cutoff and horizon, unsigned by any firm-specific SUE.

`advantage_i` above is already measured *against* always-flat implicitly (a firm with no
information should average to zero); the **always-long-market** control is reported
separately as `market_advantage = sign(sue_i) × (r_i − r_i^{SPY})`, so a result cannot be
mistaken for "SUE-sorted firms merely track the market's own drift over five sessions."

### 2.7 CONTINUE rule — all four required, Amendment A1's favourable-side convention

1. Weekly-aggregated advantage ≥ **+39 bp** (the pre-registered MDE, not lowered).
2. 95% moving-block bootstrap interval (block = 4 weeks, the gate's own choice) excludes
   zero **on the favourable side**: `lo > 0.0`.
3. **Breadth** > 0.50 (more than half of the 647 weeks have positive mean advantage) **and**
   both chronological halves of the sample (weeks 1–323 / 324–647) show positive mean
   advantage.
4. The market-relative control (§2.6) is **also** positive with an interval excluding zero
   on the favourable side — a result driven entirely by SUE-sorted firms happening to track
   a rising market is not confirmed as SUE information.

**Anything less is REJECT.** There is no fifth path to CONTINUE.

### 2.8 Noise control

30 within-week permutations of the SUE sign (shuffled independently each draw, holding the
event set and realised returns fixed), recomputing the weekly-aggregated advantage each
time. **Fails if** the median permuted advantage exceeds +10 bp, or if more than 10% of the
30 draws clear the §2.7 item-1 threshold on their own. A single favourable draw never aborts
the run.

### 2.9 Economic significance

Net-of-cost advantage at a nominal 5 bp round-trip cost is reported alongside the gross
figure, from the first measurement — not deferred. Turnover is inherent to the design (one
trade per firm per earnings event, roughly quarterly) and is reported, not bounded, since
there is no rebalancing schedule to compare it against.

---

## 3. What each outcome means, stated before the result exists

| Outcome | Reading |
|---|---|
| All four §2.7 criteria pass, noise control passes | PEAD-1 CONTINUEs: event-time absolute-return reformulation succeeded where V3's and V4's calendar-grid cross-sectional formulations did not |
| Any criterion fails | REJECT. Per `PEAD1_CHARTER.md` §9.2: closes SUE permanently, at every formulation the account holder has authorised testing. No SUE‴, no further reopening by an executing session |

---

## 4. Prohibited, restated so this document stands alone

* No second window, no λ-style blend back to cross-sectional B3, no learner.
* No sign flip on any outcome.
* No threshold, control, or breadth rule changed after this result is read.
* No restriction to a sub-universe, sector, or period to make a result survive.
* No citation of the 20-session gate PASS as license to also report that window here.

---

## 5. Recording

Committed before the first event-return for this confirmatory study is read. Result, whichever
it is, is written to `reports/PEAD1_RESULT.md` and `reports/EXPERIMENT_REGISTRY.md` (append-only),
with the per-week series preserved so the headline number is re-derivable.
