# Information Audit — V3 Phase 2

**Written 2026-08-09 under master roadmap v2 §4. Deliverable per §4.5.**

**Objective:** find information dimensions V2.3 did not test, that are *obtainable free*,
*properly timestamped*, and *plausibly large enough to see* (§2.6).

**Binding constraint (§4.0, a HUMAN DECISION already taken):** free sources only. No
data-provider spend is authorized. This is not re-opened here.

**Status of every claim below.** The roadmap's §4.2 shortlist was explicitly *"a
candidate whose timestamp semantics the audit must verify and pin with a test — not an
established fact."* This document separates the two:

* **MEASURED** — probed against the live source on 2026-08-09, with the numbers shown.
* **PRIOR** — an expectation from published literature, **not measured here**, carried
  forward as a hypothesis to be gated by §2.6 before any study runs.

No feature has been built and no model has been fitted. Nothing in this document is a
result.

---

## 1. Headline: the finding that changes how any filings feature must be built

> **MEASURED. 51.8% of 10-K/10-Q filings are accepted by EDGAR *after* the 16:00 ET
> close on the date they are stamped with.** The modal acceptance hour is **16:00 ET**
> — 769 of 2,056 filings, 37% of the sample, land in the first hour after the close.

Sample: 60 filers drawn (seed 0) from the 622 panel symbols that map to a CIK; all
10-K and 10-Q filings in their EDGAR `recent` window; 2,056 filings. Reproducible via
`alpha/edgar_probe.py 60`; raw per-filing sample preserved at
`alpha/out/edgar_acceptance_sample.json` (SHA-256
`aabf6ac86f558733e1dc46b3925f5603abc99858d07be2c44427c42efcc30701`).

| Acceptance hour (ET) | Filings | |
|---|---:|---|
| 06:00–15:00 | 991 | knowable at that day's close |
| **16:00** | **769** | **after the close** |
| 17:00 | 173 | after the close |
| 18:00–21:00 | 123 | after the close |

**Consequence, and it is not a caveat.** A feature built on `filed <= cutoff` — the
obvious rule, and the one the roadmap's §4.2 row describes — **leaks in about half of
all observations**, because `companyfacts` carries only `filed`, a *date*. A fact
stamped with the cutoff date was, more likely than not, published after the close whose
forward return the study is trying to predict.

**The rule that must be pinned by a test before any filings feature is used:**

> A fact is admissible at cutoff *T* only if its **acceptance datetime is strictly
> before the 16:00 ET close on *T***. Where acceptance time is unavailable, the fact is
> admissible only from the **next session's** close — never from `filed == T`.

This is directly analogous to `validation/REPORT.md`'s 4-hour horizon result, where a
window that straddled an overnight gap inverted the sign of the finding. The same class
of error, caught before the study this time rather than after.

**It is cheaply fixable.** Acceptance datetimes exist in two places — the per-filer
`submissions` API (`acceptanceDateTime`, ISO-8601 to the second) and, in bulk, the DERA
Financial Statement Data Sets, whose `sub.txt` carries an `accepted` timestamp beside
every value. The fix is a join, not a compromise. **It is not optional.**

---

## 2. Verified timestamp semantics, source by source

### 2.1 SEC EDGAR XBRL `companyfacts` — **PIT basis verified, with one required repair**

| Property | Verdict | Evidence (MEASURED 2026-08-09) |
|---|---|---|
| Facts carry a filing date | **yes** | every fact carries `filed`, `accn`, `form`, `fy`, `fp`, plus `start`/`end` for the period |
| **Restatements are visible, not silently overwriting** | **yes — verified** | AAPL `RevenueFromContractWithCustomerExcludingAssessedTax`: **46 of 66 period-keys carry more than one `filed` date**, each with its own accession. FY2018 revenue appears filed 2019-10-31 *and* 2020-10-30 as a comparative. **The original vintage is not destroyed by the restatement.** |
| Period end ≠ knowability | **confirmed, and large** | reporting lag, period end → filing date: median **36 days**; 10-K median **53**, p90 **59**, max **106**; 10-Q median **34**, p90 **40** |
| Filing date ≠ knowability | **FAILS — see §1** | 51.8% accepted after the close they are dated |
| Universe coverage | **95.1%** | 622 of 654 panel symbols map to a CIK in `company_tickers.json` |
| History | covers the panel | XBRL mandate phased in 2009–2011; the panel begins 2016-01-04 |
| Bulk availability | **yes** | `companyfacts.zip` **1.40 GB**, `submissions.zip` **1.56 GB**, DERA quarterly sets **~128 MB/quarter** — all HTTP 200 |

**This is the strongest point-in-time source available at zero cost**, and the
restatement-vintage property is better than the roadmap assumed: restatements are not
merely *visible*, they are *separately addressable*, which makes "what was believed on
date T" reconstructible rather than approximable.

**Two survivorship traps, MEASURED, that must be handled in Phase 4:**

1. **`company_tickers.json` contains current registrants only.** The 32 unmapped symbols
   are almost entirely dead names — AET, EMC, TWX, ESRX, HOT, COL, SPLS, SCG, CSRA,
   SBNY and similar — plus the sector ETFs and `_VIX`, which correctly have no CIK.
   **Mapping by today's ticker map silently drops exactly the firms that failed**, which
   would bias a fundamentals panel upward. The panel already reconstructs index
   membership point-in-time (`alpha/membership.py`); the CIK mapping must be made to
   match that discipline, keyed on CIK.
2. **Tickers are reused.** A ticker can be reassigned to a different company. Identity
   must be carried as CIK, never as ticker.

### 2.2 SEC Form 4 (insider transactions) — **PIT basis verified**

| Property | Verdict | Evidence (MEASURED) |
|---|---|---|
| Two timestamps present | **yes** | transaction date *and* filing date, both required by §16 |
| Acceptance time available | **yes** | e.g. NVDA Form 4s accepted 20:47–21:07 UTC = **16:47–17:07 ET — after the close.** §1's rule applies here too, and if anything more sharply |
| Statutory lag | 2 business days after the transaction | bounded and short — the shortest lag of any source here |
| Bulk enumerable | **yes** | `full-index/2025/QTR1/form.idx` lists **118,126** Form 4 filings in that quarter alone |
| Coverage | all §16 filers | officers, directors, >10% holders |

**Volume is the implementation cost:** roughly 470k filings a year, ~5M over a decade,
each needing XML parsing. Feasible, but it is the largest ingest of the three.

### 2.3 SEC 13F (institutional holdings) — **PIT basis verified, information is stale by construction**

| Property | Verdict | Evidence (MEASURED) |
|---|---|---|
| Filing date present | **yes** | with acceptance time, as above |
| **Statutory lag** | **~45 days after quarter end** | must be respected, not assumed away |
| Bulk enumerable | **yes** | 8,794 `13F-HR` filings in 2025 QTR1 |
| Effective frequency | **quarterly** | ~4 observations per name per year |

**The lag is the problem, and it is structural.** A holding is reported up to 45 days
after a quarter it may no longer be held in. Against a 5-session horizon on weekly
cutoffs, the information is between 45 and 135 days stale at every cutoff.

### 2.4 FRED / ALFRED — **struck as a standalone family (§3.2), and blocked on access**

| Property | Verdict | Evidence (MEASURED) |
|---|---|---|
| Vintages available | yes, by design | ALFRED serves the value as it stood on a past date — genuinely PIT |
| **Access** | **blocked** | `api.stlouisfed.org` returns **HTTP 400** without an API key; no key is present in the environment |

The key is **free** — this is *not* a §27B data-spend item — but it requires the account
holder to register. **Recorded as a §7 open action for the user, not a purchase
request.** It does not block the programme, because ALFRED is struck on a more
fundamental ground below.

---

## 3. The struck list

### 3.1 Struck for availability — confirmed from §4.1, unchanged

| Struck | Why |
|---|---|
| Consensus estimates, and therefore **earnings surprise vs consensus** | no free historical consensus with as-of dates |
| **Analyst estimate revisions** | same |
| **News / sentiment archives** | no free historical archive with reliable publication timestamps at scale |
| yfinance fundamentals | restated, no filing dates — **inadmissible under §2.1**, not merely weak |

Struck for *availability*, not for lack of signal. Recorded as blocked-on-data so the
reason survives.

**One important recovery, worth stating positively.** Only the *consensus-relative*
surprise is blocked. A **time-series** earnings surprise — standardized unexpected
earnings measured against the firm's own seasonal history — is fully computable from
EDGAR at zero cost and is PIT-clean once §1's rule is applied. Realized earnings growth,
acceleration, margin change and post-filing drift are all reachable. The blocked door is
narrower than v1 assumed.

### 3.2 **Newly struck by this audit: FRED / ALFRED as a standalone family**

The roadmap listed ALFRED in the §4.2 shortlist. **The audit strikes it as one of the
three families, and the reason is arithmetic rather than editorial.**

> **A macro series is cutoff-constant. One value per date cannot rank a cross-section.**

Every name in the cross-section receives the identical value of `DGS10` on a given
cutoff, so its within-cutoff Spearman IC against the target is **undefined — zero
variance in the predictor**. This is not a conjecture: **V2.1-B is the experiment that
already ran it.** Twenty-six cutoff-constant market-context columns scored **−0.00269
against 12-1 momentum** (`EXPERIMENT_REGISTRY.md` §3.2). The information cannot enter a
cross-sectional ranking except through an interaction, and the only way to build a
stock-level exposure to a macro series — a rolling beta to rates, to credit, to the
dollar — is **from the price history already in `alpha/cache`**, which fails §2.10
clause 1 outright.

ALFRED is therefore **conditioning context**, exactly as §4.3 classifies families C and
D. It is legitimate in that role — B3, the incumbent, *is* a regime switch — and it is
the highest-quality PIT source available for it. **It is not the new information that
justifies a V3, and it does not spend a family slot.**

### 3.3 Confirmed struck: families C and D as standalone candidates

Market structure and cross-asset context computed from ETFs are derivable from
`alpha/cache` and fail §2.10 clause 1. Unchanged from §4.3. Legitimate as conditioning
variables only.

---

## 4. Scoring — three criteria are vetoes, not scores

Vetoes applied first (§4.4): **no publication timestamp → out**; **derivable from the
existing cache → out**; **plausible effect below the study's resolution → out**.

| Candidate | PIT timestamp | Not in cache | Effect vs resolution | Availability | Impl. cost | Verdict |
|---|---|---|---|---|---|---|
| **EDGAR fundamentals + time-series SUE / post-filing drift** | **pass** (with §1 repair) | **pass** | **PRIOR: at or above** | free, bulk | medium | **FAMILY 1** |
| **Form 4 insider transactions** | **pass** | **pass** | **PRIOR: at the edge** | free, bulk | **high** (~5M filings) | **FAMILY 2** |
| **13F institutional holdings** | **pass** | **pass** | **PRIOR: below to at the edge** | free, bulk | high | **FAMILY 3 — reserve** |
| FRED / ALFRED macro | pass | pass | **VETO** — cutoff-constant, cannot rank a cross-section; V2.1-B measured −0.00269 | key needed | low | **struck (§3.2)** — conditioning only |
| Consensus surprise, analyst revisions, news | — | — | — | **VETO — unobtainable free** | — | struck (§3.1) |
| yfinance fundamentals | **VETO — no filing dates** | — | — | free | low | struck (§3.1) |
| Market structure / cross-asset (C, D) | pass | **VETO — in `alpha/cache`** | — | free | low | struck (§3.3) |

### 4.1 The effect-size column is a PRIOR, and it is the weakest part of this audit

Roadmap §2.6 requires ranking by **expected effect relative to the study's resolution**,
and demands V3 hunt an effect **5–10× larger than anything V2 found**. Stated concretely:

| | IC |
|---|---|
| What the entire 34-column V2 feature set was worth | **+0.0005 to +0.0014** |
| Floor this history can resolve against a correlated base | **~0.006** |
| **Therefore the minimum target for a V3 family** | **≥ ~0.007, and comfortably above 0.006 to be worth running** |

Published cross-sectional fundamental anomalies have historically produced rank ICs in
roughly the 0.01–0.03 range **in the periods and samples where they were discovered**,
and have decayed materially since publication. Post-earnings drift measured from the
announcement or filing timestamp is among the more persistent. **That is a prior, from
literature, on other samples and other periods. It is not a measurement on this panel,
and this audit does not treat it as one.**

**The honest position: Family 1's prior sits plausibly above the resolution floor, but
not by the comfortable margin §2.6 asks for.** Families 2 and 3 sit at or below it.
That is the single most important sentence in this document, and it is why the §2.6
power gate — not this audit — is what authorizes the first study.

---

## 5. Output: three families, named and frozen (§4.5, §21)

**Family budget: 3 slots. Spent: 0. These three are now frozen. There is no fourth.**

### Family 1 — **Reported fundamentals and the drift from their filing** *(priority 1)*

* **Source:** SEC EDGAR XBRL `companyfacts`, joined to acceptance timestamps.
* **Information:** revenue, EPS, margins, cash flow, debt, book value, per filing; and
  from them realized growth, acceleration, margin change, **time-series standardized
  unexpected earnings**, and drift measured from the moment of filing.
* **Why first:** the only candidate whose PIT basis is *verified rather than assumed*,
  whose restatement handling is provably correct, and whose prior plausibly clears the
  resolution floor. Its ingest is the cheapest of the three.
* **Its own biggest risk:** §1. Get the acceptance-time join wrong and the family
  produces a leaked result that will look excellent.

### Family 2 — **Insider transactions** *(priority 2)*

* **Source:** SEC Form 4 via `full-index`.
* **Information:** direction, size and clustering of officer/director/10%-holder trades,
  measured from the filing acceptance timestamp with the transaction date available
  separately.
* **Why second:** genuinely orthogonal to price and to fundamentals, and the shortest
  statutory lag of the three. Costs the most to ingest, and its prior is nearer the
  resolution floor.

### Family 3 — **Institutional holdings** *(reserve, priority 3)*

* **Source:** SEC 13F-HR.
* **Why last, and honestly:** the 45-day statutory lag makes the information 45–135 days
  stale at every weekly cutoff, and its prior is the weakest of the three. **It is
  recorded as the reserve slot precisely so that a disappointing Family 1 or 2 does not
  become an argument for inventing a fourth family** (§21). If Families 1 and 2 both
  fail, the correct reading is likely that the *formulation* is wrong, and §21 requires
  the programme to say so rather than spend slot 3 as consolation.

---

## 6. What must happen before any of this is implemented

In order. **None of it is optional, and the first study cannot begin until step 4.**

1. **Phase 3 — target design** (`reports/TARGET_DESIGN.md`). Each candidate target
   carries its power implication. Note §5's hint: Target C's coarser
   economically-meaningful classes are plausibly a *larger* effect than a rank IC, which
   is exactly what §2.6 says to hunt.
2. **§2.10 clause 3 — the correlation ceiling.** Measure Family 1's features against
   `z__ret_12_1` and against the existing 34-column set **on the panel, before any model
   is fitted**. A family that is largely a slow proxy for momentum is inside the refuted
   space no matter where it was downloaded from. **Not yet measured.**
3. **Coverage per cutoff.** Confirm the filings cross-section is deep enough at every
   historical cutoff, keyed on CIK with dead names retained. A family that covers 95% of
   *today's* names may cover far less of 2016's.
4. **§2.6 power gate — blocking.** State the smallest effect worth acting on from the
   economic threshold and the cost model; compute the achievable half-width with
   `alpha/stats.py`'s existing `block_bootstrap_ci` / `paired_difference` at the planned
   cutoff count and spacing; **and if the half-width exceeds the effect, do not run the
   study as designed.** Record the verdict in the preregistration and in
   `EXPERIMENT_REGISTRY.md`.

Then Phase 4 (pipeline, mirroring the `alpha/pitdata.py` one-door design with a
**filing-date door** and a restatement test) and Phase 5 (information-only tests).

---

## 7. Open action for the account holder — not a spend request

**A free FRED/ALFRED API key** (`fredaccount.stlouisfed.org`) would unblock the macro
vintages. **This is not a §27B item** — there is no purchase, no trial and no provider
spend, and the programme is not blocked on it: ALFRED is struck as a family on
independent grounds (§3.2) and is wanted only as *conditioning context*, where B3
already serves.

Requested rather than assumed, because it needs an account the programme does not own.

---

## 8. What this audit did not do

* It fitted nothing, built no feature, and measured no IC. Every effect size in §4.1 is
  a **PRIOR**, labelled as one.
* It did not measure the correlation ceiling (§6 step 2) or per-cutoff coverage
  (§6 step 3). Both are required before Family 1 may be implemented.
* It did not run the §2.6 power gate. **Until that gate is computed and passed, no V3
  study is authorized**, and this document does not authorize one.
