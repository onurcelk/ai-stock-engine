# V5 Phase 9 — Data Gap Analysis

**Verdict: `PHASE 9 VERDICT: NO NEW DATASET AUTHORISED. THE GAP IS DATES, NOT DATA`.**

No dataset was ingested, no network call was made, no source was opened, and no
outcome file was read. Every number below is either quoted from a frozen report
or computed by applying a frozen, published, already-calibrated formula to a date
count. `validation/out/calls.csv` was not opened. The exam is sealed.

| | |
|---|---|
| Roadmap ACTIVE PHASE | **Phase 9 — Data Gap Analysis** (recorded, entered in order) |
| Deliverable | this file, per roadmap Phase 9 §Required Deliverable |
| Outcomes read | **None** |
| Data ingested | **None.** No family opened, no slot spent |
| Budget | V3 3/3 spent and CLOSED · V4 slot 1 spent, slot 2 BARRED · Family-10 unspent and FAILED its power gate. **All unchanged** |
| Exam | Sealed. Not accessed |

---

## 1. What Phase 9 asks, and the short answer

> **Goal.** Only now decide whether more data is needed.
>
> **STOP / GO Gate.** Any new dataset must have a precise hypothesis and
> measurable expected role.

The gate is the answer. A "measurable expected role" is a claim about an effect
*relative to what the instrument can resolve*. This programme has a **calibrated**
resolution model — it predicts its own measured half-widths to the decimal — and
that model says the quantity this engine is short of is **independent dates**.
Data families supply columns and names. Neither buys resolution.

Three findings, each sufficient alone:

1. **All eight of Phase 9's candidate families already have a disposition** in two
   frozen surveys. Not one is both un-surveyed and admissible. §3.
2. **The binding constraint is arithmetic, and no family moves it.** On the V5
   record's geometry, adding *infinitely many symbols* narrows the interval by
   **3.8%**; going from 12 dates to 50 narrows it by **51%**. §4.
3. **The gate therefore cannot be cleared by any candidate.** The expected role is
   not measurable, because the instrument cannot measure any plausible role. §5.

What *is* authorised is in §6, and it is not a purchase.

---

## 2. Prior art — Phase 9 has two predecessors, and they are not superseded

Phase 9 is not the first data-gap analysis in this repository. Two frozen reports
already did this work, and this phase reads them rather than redoing them:

| Report | Date | Scope | Verdict |
|---|---|---|---|
| `reports/INFORMATION_AUDIT.md` | 2026-08 | V3 Phase 2, cross-sectional programme | 3 families named and frozen; 4 struck |
| `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` | 2026-08-11 | **all ten families**, absolute single-name | `OPEN ONE FAMILY` |

Re-ranking the same families on the same criteria to reach a different answer
would be the "one more carrier" move the standing exclusions forbid. This phase
therefore treats both as **inputs**, quotes their dispositions, and adds only what
they could not see: the resolution of the V5 harness specifically, which is an
order of magnitude coarser than the harness they were written for.

---

## 3. Finding 1 — every candidate family already has a disposition

The roadmap names eight candidate families. Mapped onto the frozen record:

| # | Phase 9 family | Prior disposition | Where | Status |
|---|---|---|---|---|
| 1 | **earnings surprises** | Family 1 (time-series SUE) **TESTED, REJECT** (`V3-1`, +0.00090 vs B3); re-tested at 20 sessions **REJECT** (`V4-1`). Consensus-*relative* surprise struck: no free historical as-of vintage | `INFORMATION_AUDIT.md` §3.1, §5 · registry §6–8 | **CLOSED — 2 slots spent** |
| 2 | **analyst revisions** | Struck twice for availability. **VERIFIED 2026-08-11** that free tiers serve current consensus only; PIT products (I/B/E/S, Zacks) all **PAID** | `INFORMATION_AUDIT.md` §3.1 · survey §2, rank —, `REJECT BEFORE INGEST` | **BLOCKED ON DATA** |
| 3 | **options-implied expectations** | **PAID**, no free PIT chain history. And on content: *"it prices magnitude, not sign"* — the wrong quantity for a directional target | survey §2 family 2 | **BLOCKED ON DATA + WRONG QUANTITY** |
| 4 | **volatility term structure** | Same paid source as #3. The free portion is computable from ETF/index history **already in `alpha/cache`** → fails the derivability veto. Tested as a feature in `V2-E` (+ regime/VIX/breadth): **REJECT** | `INFORMATION_AUDIT.md` §3.3 · registry §2 | **VETOED (derivable) + REJECTED** |
| 5 | **liquidity / order-flow proxies** | FINRA daily short volume: free, daily, **timestamped 18:00 ET on the trade date**. Rejected on **independence** — it is a decomposition of the same executed trades whose OHLCV is already cached. The survey's own words: *"the strongest source the survey rejects, and it is rejected on independence, not on power"* | survey §2.1, rank 4 | **VETOED (clause 7)** |
| 6 | **corporate actions / events** | The survey's **winner**. Family 10 (8-K adverse items) opened, piloted, and **FAILED its §2.6 power gate**: 57.8 bp against a 39 bp hurdle, half-width **floors at 49.0 bp as n → ∞**. Form 4 **REJECT** (`V3-2`), 13F **REJECT** (`V3-3`). 424B5 remains WATCHLIST | registry §10 · survey §7 | **BEST CANDIDATE, ALREADY FAILED** |
| 7 | **sector / industry relative** | `V2-B` (+47 relative/percentile) **REJECT**. Industry-relative fundamentals rated `UNDERPOWERED`, coverage poor, sources fragmented | registry §2 · survey §2 family 7 | **REJECTED + UNDERPOWERED** |
| 8 | **macro data** | Struck as **cutoff-constant**: one value per date cannot rank a cross-section. Not conjecture — `V2.1-B` ran 26 cutoff-constant context columns and scored **−0.00269**. Legitimate as *conditioning context* only, and it spends no slot | `INFORMATION_AUDIT.md` §3.2 · registry §2 | **STRUCK AS A FAMILY** |

**Score: 0 of 8 are both un-surveyed and admissible.** Three are closed after
being tested and rejected, two are blocked on paid data, two are vetoed as
derivable-or-dependent, and one — the strongest of them, chosen by a survey that
ranked ten candidates precisely to find it — was opened and failed on power.

Note the shape of that list. The failures are **not** clustered on information
content. They cluster on availability and on **power**. That is the signature of
an instrument problem, not a data problem, and it is what §4 makes exact.

---

## 4. Finding 2 — the constraint is arithmetic, and breadth does not relieve it

### 4.1 The model, and the fact that it is calibrated

`ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §1 publishes a resolution model for a mean over
`k` names on each of `D` independent dates with average within-date pairwise
correlation `ρ`:

```
half-width(95%) = 1.077 · 1.96 · sqrt( V · [ ρ + (1−ρ)/k ] / D )
```

Inputs, all **measured marginal properties of the target** on the 316-cutoff
development panel — no feature, no candidate, no conditioning — and all **quoted,
not recomputed**:

| | |
|---|---|
| sd of the 5-session absolute return | 0.04526 (143,675 rows) |
| within-date pairwise correlation of returns | ρ = 0.2916 |
| up-indicator variance / correlation | 0.24783 / ρ = 0.1778 |
| block-bootstrap inflation | 1.077 |

Re-evaluated here, it reproduces both published anchors:

| Geometry | This computation | Published | Source |
|---|---|---|---|
| k = 230, D = 177 | **39.0 bp** | **39.0 bp** ("the model reproduces the observed resolution exactly") | survey §1 |
| k = 230, D = 215 | **35.4 bp / 3.05 pp** | **35 bp / 3.0 pp** | registry §11.4 |

The instrument is calibrated at the geometry it was built for. That is the licence
to read it at other geometries.

### 4.2 Read at the V5 engine's own geometry

The V5 record is `validation/out/` — **12 cutoffs × 30 symbols**:

| D | k | return half-width | up-rate half-width | |
|---:|---:|---:|---:|---|
| **12** | **30** | **154.8 bp** | **13.74 pp** | **the V5 record** |
| 50 | 30 | 75.9 bp | 6.73 pp | `ROADMAP.md`'s own ≥ 50-cutoff criterion, at V5 breadth |
| 177 | 230 | 39.0 bp | 3.36 pp | SN-1 Phase 1 |
| 215 | 230 | 35.4 bp | 3.05 pp | SN-1 development |
| 316 | 230 | 29.2 bp | 2.52 pp | AMS-1 — the sharpest this programme has reached |
| 532 | 230 | 22.5 bp | 1.94 pp | every session, 5-session blocks |

**Independent corroboration at the geometry that matters.** ABS-1 derived, by a
completely different route and from the record's own signal geometry, an MDE of
**29.15 pp** for its two-band difference contrast. Scaling the single-arm 13.74 pp
above to a difference of two arms (×√2) and from a 95% half-width to an 80%-power
MDE (×1.43) gives **27.8 pp**. Two independent derivations agree within ~5% that
the V5 record resolves somewhere near 28–29 pp on a difference of proportions.
This is a cross-check, not a new gate, and it gates nothing.

### 4.3 The structural result, restated where it bites

The survey's own headline:

> **Resolution is bought with independent dates, not with more names per date.**

Because the bracket `[ρ + (1−ρ)/k]` tends to `ρ` as `k → ∞`, the common market
move never diversifies away. At the V5 record's 12 dates:

| Change | New half-width | Improvement |
|---|---:|---:|
| 30 symbols → **infinitely many** | 148.9 bp | **3.8%** |
| 12 dates → 50 dates (30 symbols) | 75.9 bp | **51.0%** |

**Adding every listed equity on earth to the V5 record buys 3.8%.** Adding 38
Tuesdays buys 51%.

This is the whole of Phase 9 in two rows. A data family is a column, and often
also more names. Neither is the axis the interval lives on. There is no dataset —
free, paid, exotic, or perfectly point-in-time — whose purchase adds a single
independent date to a record of 12.

### 4.4 What dates would cost, in dates

Inverting the same formula at V5's `k = 30`, for the return half-width:

| Target | Independent dates required | At weekly non-overlapping spacing |
|---|---:|---:|
| 100 bp | 29 | **0.6 years** |
| 50 bp | 115 | **2.2 years** |
| 39 bp — SN-1's measured economic MDE | 189 | **3.6 years** |

These are calendar arithmetic on a design, not measurements of any outcome.

And note what sits at the end of that column: reaching the resolution at which
SN-1, Family-10 and AMS-1 **each independently found nothing** takes 3.6 years.
That is the honest framing of the prize.

---

## 5. Finding 3 — the STOP/GO gate cannot be cleared

> Any new dataset must have a precise hypothesis and measurable expected role.

Take the strongest candidate that survives §3 in any form — 424B5 equity issuance,
the survey's rank 2, free, PIT-verified, with a statutory dilution sign. Its
precise hypothesis is writable. Its **measurable expected role** is not, and the
reason is not that the effect is unknown:

- Family 10, ranked **above** it on every criterion including sign, reached a
  half-width that **floors at 49.0 bp as n → ∞** at its own honest block length —
  so even unlimited events do not reach the 39 bp hurdle. 424B5 has fewer usable
  events, not more.
- Any V5-side test inherits §4.2: **154.8 bp / 13.74 pp**.

A dataset whose expected role can only be stated as "smaller than the interval"
has no measurable expected role. The gate is not being failed on a technicality —
it is doing exactly the job it was written for, and it applies to every candidate
uniformly, which is why the verdict is a general one rather than a ranking.

**Ranked on the roadmap's own seven criteria**, for the record — criterion 1 is
the one that decides, and it decides the same way for all eight:

| Criterion | Result across all candidates |
|---|---|
| 1. expected incremental information **relative to resolution** | **Below resolution for every candidate.** Decisive |
| 2. PIT availability | Pass: 5, 6, 8. Fail: 2, 3, 4 (paid). Pass-but-vetoed: 5 |
| 3. historical depth | Adequate for 1, 5, 6, 8; poor for 7 |
| 4. cost | Free: 1, 5, 6, 7, 8. Paid: 2, 3, 4 |
| 5. implementation effort | Low for 8; medium for 6; high for 1, 5 |
| 6. leakage risk | Handled — the timestamp discipline is the mature part of this repository |
| 7. relevance to the exact target | 3 prices magnitude not sign; 8 is cutoff-constant; 6 is the only statutory-sign candidate, and it failed |

Criteria 2–7 separate the candidates cleanly. Criterion 1 collapses them all, and
criterion 1 is the one the gate is written on.

---

## 6. What is authorised — and it is not a purchase

**The gap is independent dates. The repository already owns the only free source
of them, and it has never been switched on.**

`app/forecast_ledger.sqlite3` **does not exist.** Verified by absence of the file,
not inferred. Phase 1 built the forecast ledger and Phase 2 built the outcome
scorer — both COMPLETE, both tested — and **no live forecast has ever been frozen
into them.** Every date the programme has is a date it back-constructed from
cached history; it has never banked a single forward one.

A frozen forward forecast is the one date-source that is:

- **free** — no vendor, no subscription, no ingest;
- **point-in-time by construction, not by repair** — the forecast is written before
  the outcome exists, which is the structural guarantee `validation/predict.py` and
  `validation/score.py` are already built around, rather than a timestamp audit
  performed after the fact;
- **immune to every veto in §3** — it is not derivable from the cache, not
  cutoff-constant, not stale, not paid;
- **the only asset that compounds.** A dataset purchased today is as resolving in
  three years as it is today. A ledger switched on today holds ~155 independent
  dates in three years.

It is also slow, and §4.4 is honest about how slow: **~29 dates to 100 bp, ~115 to
50 bp.** That is the actual price of resolution in this programme, and no
expenditure shortens it.

**This section authorises no run.** Switching the ledger on is a production-side
decision that belongs to **Phase 7**, whose gate — *"no automatic production
promotion without explicit evidence gate"* — exists precisely to govern what gets
frozen and under what versioning. Phase 7 requires no resolution to write, costs
nothing, and is the precondition for accumulation. It is the correct next phase.

---

## 7. What this document does not conclude

- **It does not conclude that no useful data exists.** It concludes that no
  candidate's expected role is measurable *by this instrument*, which is a
  statement about the instrument.
- **It does not reopen anything.** No rejected family is re-ranked into
  admissibility, no failed gate is re-run at a friendlier parameter, no closed
  slot is revisited. The verdict is the maximally conservative one available.
- **It does not authorise a Family-10 re-run.** Registry §10.3 bars a shorter
  block, an enlarged item set, and another horizon. Nothing here disturbs that.
- **It does not put 424B5 or GDELT on a path.** Both stay WATCHLIST, unchanged.
- **It asserts no gate.** §4 applies a published calibrated formula to date counts.
  Any actual study still needs its own §2.6 gate, computed and committed before it
  is run.
- **It does not resolve the §2.5 / Phase-6-gate contradiction** recorded at the
  Phase 6 STOP/GO gate. Still open, still the programme owner's.

---

## 8. Phase 9 task status

Against the roadmap's rules and gate.

- [x] **Rank candidate data families on all seven criteria** — done, §5. Criteria
      2–7 separate them; criterion 1 collapses them.
- [x] **Do not recommend indicator proliferation** — none recommended. Zero new
      indicators, zero transformations proposed.
- [x] **Prefer genuinely distinct information families** — applied as a veto, and
      it is what eliminates #4, #5 and #8: derivable, dependent, or cutoff-constant.
- [x] **Prefer free sources unless paid data solves a demonstrated gap** — no paid
      source is recommended, and §4.3 is the reason no paid source *could* be: the
      demonstrated gap is dates, and dates are not sold.
- [x] **STOP/GO gate applied** — no dataset clears it. §5.

**`PHASE 9 VERDICT: NO NEW DATASET AUTHORISED. THE GAP IS DATES, NOT DATA`**
