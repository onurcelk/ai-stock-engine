# Absolute-Alpha Source Survey — pre-ingest feasibility

**Written 2026-08-11. SURVEY ONLY. No dataset ingested, no feature built, no model fitted,
no forward outcome read, no exam cutoff opened, no family budget slot spent.**

Commissioned after `reports/SINGLE_NAME_PHASE1.md` returned **DO NOT ADVANCE** — all four
gates failed, no arm ever emitted `p_up < 0.5`, and zero SELL calls were produced in
101,137 symbol-dates. The burden of proof now sits on the **information source**, not on
the model.

> **The question.** Is there a genuinely free, historically point-in-time information
> source with a plausible mechanism and sufficient coverage and timing to change the
> **absolute** conditional distribution of a single stock's 5-session return by an
> economically and statistically detectable amount?

**Change of research object.** Every prior study in this repository asked whether a feature
improved *cross-sectional ranking* over B3. That is no longer the primary question. A
feature can rank well and be useless here. Each candidate below is classified on three
separate axes — **cross-sectional content**, **absolute directional content**, **absolute
magnitude content** — and only the second one decides the verdict.

Everything marked **MEASURED** was computed on 2026-08-11 from the SEC's free bulk
submissions archive already on disk, or from marginal properties of the target. Everything
marked **VERIFIED** was checked against the live primary source on 2026-08-11. Everything
marked **PRIOR** is an expectation from literature and is not treated as evidence.

---

## 1. The resolution model — and why it is the survey's main finding

Before ranking sources, the survey establishes what size of effect this study design can
*see*. Roadmap §2.6: power before permission.

For a mean taken over `k` names on one date and `D` independent dates, with average
within-date pairwise correlation `ρ`:

```
half-width(95%)  =  1.077 · 1.96 · sqrt(  V · [ ρ + (1−ρ)/k ]  /  D  )
```

Inputs, all **MEASURED** marginal properties of the target on the 316-cutoff development
panel — no feature, no conditioning, no candidate involved:

| | |
|---|---|
| sd of the 5-session absolute return | **0.04526** (143,675 rows) |
| average within-date pairwise correlation of returns | **ρ = 0.2916** |
| up-indicator variance / within-date correlation | **0.24783 / ρ = 0.1778** |
| block-bootstrap inflation over the i.i.d.-across-dates form | **1.077** |

**Calibration.** At Phase 1's own geometry — `k = 230` covered names, `D = 177` cutoffs —
the formula returns **39.0 bp**. Phase 1 *measured* **39.0 bp**. The model reproduces the
observed resolution exactly, so the surface below is a calibrated instrument rather than an
assumption.

### 1.1 The structural result

> **Resolution is bought with independent dates, not with more names per date.**

Because the bracket tends to `ρ` as `k → ∞`, the common market move never diversifies away.
At `ρ = 0.29`, going from 17 names per date to *infinitely many* narrows the half-width by
only **7%**. Going from 177 dates to 532 narrows it by **42%**.

This is why Phase 1 could not be rescued by breadth, and it is the single most important
constraint on any future family: **an absolute-return study on a weekly grid over this
history has a hard floor near 35 bp / 3.0 pp, no matter how many names it looks at.**

An **event-driven** design is the only lever that moves it, because events land on every
trading session rather than on 215 Tuesdays. The study window holds **2,664 trading
sessions (MEASURED)** = 532 non-overlapping 5-session blocks, or 266 if a 10-session block
is used to absorb the overlap between neighbouring events' windows. Both are reported
throughout; the conservative column governs the verdict.

### 1.2 What an effect must clear

| Claim | Requirement |
|---|---|
| **(a) The conditional up-rate differs from the 0.537 base rate** | shift > half-width |
| **(b) The conditional up-rate is credibly below 0.50** — the prize Phase 1 could not produce | shift > 3.7 pp + half-width |
| **(c) Economically useful absolute return** | > ~39 bp per 5 sessions (Phase 1's covered-book resolution) |

---

## 2. Candidate comparison — all ten families

Cost: **FREE** = no subscription for the historical research data · **LIMITED** = freemium
quota too small for historical research, therefore effectively unavailable · **PAID**.

| # | Family | Cost | PIT timestamp | Coverage | Cross-sect. content | **Absolute directional content** | Magnitude content | Detectability | **Verdict** |
|---|---|---|---|---|---|---|---|---|---|
| 10 | **SEC 8-K adverse-event items** | **FREE** (bulk on disk) | **acceptance datetime, to the second** | **612/622 filers (98.4%)** | low | **the only candidate with a statutory a-priori sign** | high | **PLAUSIBLY DETECTABLE** | **OPEN FAMILY CANDIDATE** |
| 9 | Corporate action / capital structure (424B5, S-3) | FREE | acceptance datetime | 424 filers | low | plausible (dilution) but equity/debt **not separable from metadata** | medium | BORDERLINE | WATCHLIST |
| 3 | Short interest (FINRA, bi-monthly) | FREE | dissemination date, **7 business days** after settlement | ~all | medium | weak, and stale at 5D | low | **UNDERPOWERED** (24 obs/yr) | REJECT BEFORE INGEST |
| 3b | Short **volume** (FINRA Reg SHO daily) | FREE | **posted 18:00 ET on the trade date** | ~all | medium | weak, relative not absolute | medium | detectable, but see independence | **REJECT BEFORE INGEST** (clause 7) |
| 1 | Analyst estimate revisions | **PAID** | n/a | n/a | high (PRIOR) | medium (PRIOR) | medium | n/a | REJECT BEFORE INGEST |
| 2 | Options-derived (IV, skew, term structure) | **PAID** | n/a | n/a | medium | **low — it prices magnitude, not sign** | high | n/a | REJECT BEFORE INGEST |
| 4 | Fund / ETF flows | LIMITED→PAID | N-PORT public **60 days after quarter end** | fund-level only | low | very low at 5D | low | UNDERPOWERED | REJECT BEFORE INGEST |
| 5 | Institutional positioning (13F, N-PORT) | FREE | acceptance datetime | high | low | **none at 5D** — 45–135 days stale | none | UNDERPOWERED | REJECT (already spent V3 slot 3) |
| 6 | Macro surprise (ALFRED, BLS, BEA) | FREE (key needed) | vintage date | n/a | **zero — one value per date** | market-wide only, no per-stock heterogeneity | medium | n/a | REJECT AS A FAMILY (conditioning only) |
| 7 | Industry-relative fundamentals | FREE but fragmented | mixed | poor | low | low | low | UNDERPOWERED | REJECT BEFORE INGEST |
| 8 | News / event archives (GDELT) | FREE | publication time of an *article*, not of the *event* | high nominal | medium | unknown | medium | unmeasurable without linkage | WATCHLIST |

### 2.1 The three vetoes, applied first

* **No reconstructable PIT timestamp → out.** GDELT timestamps an article, not a corporate
  event, and offers no reliable ticker linkage — the first-publication moment for a given
  company event cannot be established, so admissibility cannot be decided. Families 1 and 2
  have no free historical *as-of* vintage at all: **VERIFIED 2026-08-11** that the free
  tiers (FMP, Finnhub, TIKR) serve *current* consensus and current chains; the point-in-time
  products are LSEG I/B/E/S, Zacks, OptionMetrics, IVolatility, FirstRateData and
  HistoricalData.net, all paid.
* **Derivable from the existing price cache, or the same information as a rejected family
  → out.** FINRA daily short volume is free, daily, and beautifully timestamped — but it is
  a decomposition of the same executed trades whose OHLCV is already in `alpha/cache`, and
  the programme's price/volume market-structure line already failed its gate. It fails
  source constraint 7 in substance even though it passes it in letter. Recorded honestly:
  **this is the strongest source the survey rejects, and it is rejected on independence,
  not on power.**
* **Effect plausibly below the study's resolution → out.** Short interest gives 24
  observations a year with a 7-business-day dissemination lag against a 5-session horizon.
  N-PORT is published 60 days after quarter end (**VERIFIED 2026-08-11**, SEC's February
  2026 proposal retains quarterly public disclosure). Both are structurally stale.
* **Cutoff-constant → cannot be a single-name family.** A macro surprise takes one value per
  date and is identical for every stock. `reports/INFORMATION_AUDIT.md` §3.2 struck it on
  this ground for the cross-sectional programme; the ground survives the change of research
  object, because the objective is explicitly *per-stock* heterogeneity. It is legitimate
  conditioning context for Layer 1 and nothing more.

---

## 3. The surviving candidate, measured

Everything in this section is **MEASURED** from `alpha/edgar/submissions.zip` — the SEC's
free bulk submissions archive, already downloaded 2026-08-09 for V3. No network call, no new
ingest, no price, no return. Reproduce with `python -m alpha.source_probe`.

### 3.1 Volume, coverage and timestamp

| | |
|---|---|
| Panel symbols mapping to a CIK | **622** |
| Filers with at least one 8-K since 2016-01-04 | **612 (98.4%)** |
| 8-K filings in the window | **82,076** |
| Non-earnings 8-K (item 2.02 excluded) | **55,118** |
| 8-Ks per filer per year | **12.19** |
| Distinct sessions carrying a non-earnings 8-K | **3,221** — essentially every session |
| Coverage by year (filers with ≥1 8-K) | 2016: **539** → 2026: **612**, monotone |
| Filings whose only item is the structural 9.01 | **2.3% in 2016 falling to 0.3% in 2026** |
| **Accepted at or after the 16:00 ET close** | **57.9%** |

That last row is the family's defining hazard and it is *worse* than the 51.8% the V3 audit
measured for 10-K/10-Q. A door keyed on `filed <= cutoff` would leak on the majority of
observations. **The repair already exists and is already tested:** `alpha/filings.py`
admits a fact only when `accepted (ET) < 16:00 ET on the cutoff session`, and
`app/tests/test_alpha_filings.py` proves it by rewriting the future.

### 3.2 Item mix — where the sign lives

| Item | Meaning | Filings | Filers | A-priori sign |
|---|---|---:|---:|---|
| 2.02 | results of operations (**EARNINGS**) | 25,984 | 612 | **excluded — this is the rejected SUE family's information** |
| 8.01 | other events | 19,776 | 608 | **none** |
| 7.01 | Regulation FD disclosure | 19,224 | 602 | **none** |
| 5.02 | departure **or** election of officers/directors | 15,393 | 608 | **ambiguous — one code carries both** |
| 1.01 | entry into a material agreement | 8,871 | 586 | weakly positive at best |
| 2.03 | creation of a financial obligation | 5,448 | 543 | ambiguous |
| **1.02** | **termination of a material agreement** | **998** | 366 | **negative** |
| **3.02** | **unregistered sales of equity (dilution)** | **700** | 212 | **negative** |
| **2.05** | **exit or disposal costs** | **410** | 173 | **negative** (weakest member) |
| **2.06** | **material impairments** | **175** | 93 | **negative** |
| **3.01** | **delisting / listing-rule failure** | **132** | 80 | **negative** |
| **2.04** | **acceleration of a financial obligation** | **82** | 41 | **negative** |
| **1.03 / 4.02** | **bankruptcy / non-reliance (restatement)** | in the pool | — | **strongly negative** |

**Clean-negative-sign pool (1.02, 1.03, 2.04, 2.05, 2.06, 3.01, 3.02, 4.02): 2,419 filings
on 1,632 distinct sessions (MEASURED).**

The tension the survey exists to expose: **the frequent items have no sign, and the signed
items are the rare ones.** That is a fact about the taxonomy, not about our ambition.

### 3.3 Detectability, computed on the calibrated surface

| Configuration | Events | 5D blocks (532) | | 10D blocks (266, conservative) | |
|---|---:|---:|---:|---:|---:|
| | | **return bp** | **up-rate pp** | **return bp** | **up-rate pp** |
| Pooled non-earnings 8-K | 55,118 | 22.6 | 1.96 | 31.8 | 2.75 |
| Item 5.02 alone | 15,393 | 23.3 | 2.07 | 32.3 | 2.82 |
| 424B5 supplements | 5,159 | 25.0 | 2.33 | 33.6 | 3.02 |
| **Clean-negative-sign pool** | **2,419** | **27.7** | **2.73** | **35.6** | **3.34** |
| Item 3.02 alone | 700 | 37.7 | 4.08 | 43.9 | 4.51 |
| Item 2.06 alone | 175 | 64.8 | 7.45 | 68.5 | 7.70 |

Against the §1.2 hurdles:

* **Claim (c), economic return.** The clean-negative pool resolves to **27.7–35.6 bp**, inside
  Phase 1's 39 bp. **Clears.**
* **Claim (a), a conditional up-rate different from 0.537.** Needs a shift above
  **2.73–3.34 pp**. **Clears** for any effect of the size adverse corporate events plausibly
  carry.
* **Claim (b), a credible sub-50% group.** Needs a shift of **6.4–7.0 pp**. **Borderline.**
  This is the prize and it is not guaranteed; it is, however, the first configuration in this
  programme's history where the arithmetic does not rule it out in advance.

**A correction, recorded rather than quietly fixed.** The survey's first pass paired
events-per-*calendar-date* with a block count already reduced for overlap. That charges the
same concentration twice and overstated every half-width — it put the clean-negative pool at
4.98 pp and would have produced a REJECT verdict. The consistent accounting requires
`k · D = sample`, which `source_probe.resolution_for_events` now enforces by construction so
the error cannot recur. The corrected numbers are above.

---

## 4. Feasibility record — Family 10, SEC 8-K adverse-event items

| | |
|---|---|
| **A. Source** | SEC EDGAR, `submissions` bulk archive + per-filer JSON. `alpha/edgar/submissions.zip`, 1.56 GB, already on disk |
| **B. Cost** | **Genuinely free.** No key, no quota, no subscription. Fair-access policy: descriptive User-Agent, 10 req/s |
| **C. Historical availability** | 8-K item codes are the post-August-2004 taxonomy; **MEASURED** complete over the whole panel window, with only 2.3% (2016) → 0.3% (2026) of filings carrying no substantive item |
| **D. PIT timestamp** | **`acceptanceDateTime`, ISO-8601 to the second.** Immutable once issued. Admissible at cutoff *T* only if `accepted (ET) < 16:00 ET on T`; otherwise from the next session |
| **E. Coverage** | **612 of 622 mapped panel filers (98.4%)**, rising monotonically 539 → 612 across the decade |
| **F. Frequency** | 12.19 8-Ks per filer per year overall; the adverse-item pool runs **≈ 228 events per year across the universe** |
| **G. Mechanism** | These are discrete, dated, firm-specific *shocks to the level of expected cash flow or to the claim structure over it* — an impairment writes down assets, a 3.02 dilutes the per-share claim, a 4.02 withdraws the accounting record the price was built on, a 3.01 threatens the listing itself. Each moves the **absolute** distribution of the issuer's own return, not merely its rank among peers |
| **H. Expected sign** | **Negative, fixed by statute rather than estimated.** The item code *is* the sign map — the only candidate in this survey where direction comes from the taxonomy instead of from a fitted parameter or a classifier |
| **I. Persistence** | **PRIOR**, and the family's central uncertainty. Lerman & Livnat (*Review of Accounting Studies*, 2010) document abnormal volume and return volatility around **all** 8-K items and significant post-filing drift for **some**. 57.9% of filings are accepted after the close, so the first tradeable price is the *next* session's — the immediate reaction is not capturable and only the residual drift is. Whether that residual survives five sessions is exactly what the study would measure |
| **J. Leakage risk** | **Identified and already solved.** (1) The 57.9% after-close trap — `alpha/filings.py` handles it, pinned by test. (2) `company_tickers.json` lists current registrants only, so dead names silently vanish — and dead names are *precisely the adverse-event population*, making this survivorship trap sign-correlated and the single most dangerous defect. Identity must be carried as CIK, keyed to `alpha/membership.py`'s point-in-time index. (3) Item 2.02 contamination — excluded structurally, not filtered later |
| **K. External evidence** | 8-K item-level drift is documented but on other samples, other periods, and mostly at 30–90 days. **Treated as a hypothesis, not as proof** |
| **L. Independence** | vs price/momentum/B3: an event dummy is a filing fact, not a price transform — but the §2.10 clause-3 correlation ceiling must be **measured before the study runs**. vs SUE: structural, item 2.02 is excluded. vs Form 4: different form, different filer, different information. vs 13F: different form and a 45-day lag this family does not have. vs market state: events are firm-specific by construction |
| **M. Sample size** | **2,419 adverse events** over 2,664 sessions; 532 five-session blocks, 266 conservative |
| **N. Detectability** | **PLAUSIBLY DETECTABLE** for claims (a) and (c); **BORDERLINE** for claim (b), the sub-50% group |
| **O. Verdict** | **OPEN FAMILY CANDIDATE** |

---

## 5. Event-driven, not universal — and the base-rate criterion

The directive asks whether the predictor should stop expecting a forecast for every stock
every week. **It should**, and the arithmetic in §1 is the reason rather than a preference:
a weekly grid over 215 cutoffs has a 3.0 pp floor on the up-rate, and no source can beat
that floor on that grid. Sampling in event time is what buys the extra dates.

The correct architecture is therefore:

```
no qualifying event in the window   ->  NO EDGE          (the overwhelming majority)
qualifying adverse 8-K, accepted before the close  ->  a real conditional forecast
```

This is not a lowering of ambition. Phase 1 produced 101,137 forecasts and 49,517 BUY calls
and none of them contained information. A family that produces **≈ 228 forecasts a year** and
can defend them is strictly more useful.

**On the base rate.** The prize is a group with `P(up | event)` credibly below 0.50, because
none of S0–S4 could produce one — every arm's probability lived above 0.5 at every one of
101,137 opportunities. Only the adverse-item pool has both a negative a-priori sign and
enough events to test it. That is why it wins the ranking, and it is the only reason it wins
it: on volume alone, item 5.02 and the pooled set are larger, and on independence alone,
FINRA short volume is cleaner. **Sign is the binding scarcity.**

---

## 6. Ranking, on the directive's own criteria

| Rank | Family | Absolute mechanism | PIT | Free | ± groups | 5D persistence | Sample | Breadth | Independence | Complexity |
|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **8-K adverse items** | **strong** | **verified** | **yes** | **negative group available** | PRIOR, untested | 2,419 | 98.4% | high | **low — metadata only** |
| 2 | 424B5 equity issuance | strong | verified | yes | negative only | PRIOR | 5,159 mixed | 68% | high | medium (needs text) |
| 3 | 8-K item 5.02 | medium | verified | yes | **sign ambiguous** | PRIOR | 15,393 | 98% | high | medium (needs text) |
| 4 | FINRA daily short volume | weak, relative | **excellent** | yes | possible | PRIOR | very large | ~100% | **fails clause 7** | low |
| 5 | GDELT news | unknown | **fails** | yes | unknown | unknown | large | high | medium | very high |
| — | everything else | — | — | **no** or stale | — | — | — | — | — | — |

Note that the winner is **last on sample size among the viable candidates and first on
sign**. That ordering is the survey's recommendation in one line.

---

## 7. Verdict

The pre-ingest evidence does not prove that an edge exists. It establishes something
narrower and sufficient for a decision: **one free source has a verified point-in-time
timestamp, 98.4% coverage, a direction fixed by statute rather than fitted, and enough
events that the primary contrast sits inside the instrument's resolution.** Every other free
candidate fails an availability, timestamp, staleness, independence or cutoff-constancy veto
that no amount of modelling can repair.

```text
SOURCE SURVEY VERDICT: OPEN ONE FAMILY
```

### 7.1 The family, specified

| | |
|---|---|
| **Exact source** | SEC EDGAR bulk `submissions` archive (`alpha/edgar/submissions.zip`), per-filer JSON, `filings.recent` plus every continuation file |
| **Exact event** | An 8-K whose `items` field contains at least one of **1.02, 1.03, 2.04, 2.05, 2.06, 3.01, 3.02, 4.02** — the adverse-event set — and which does **not** contain item 2.02 |
| **Availability timestamp** | `acceptanceDateTime`, converted to ET. Admissible at cutoff *T* iff `accepted < 16:00 ET on T`; otherwise first admissible at the next session's close |
| **Sign mapping** | **Negative, fixed in advance for every item in the set.** No sign is estimated, scanned or flipped. `E[r]` is predicted below the unconditional mean and `P(up)` below the unconditional rate |
| **Expected coverage** | 612 of 622 mapped filers file 8-Ks; the adverse pool touches a smaller subset — measuring **how many distinct symbols** it reaches is the pilot's first job |
| **Sample size** | **2,419 events**, ≈ 228/year, over 2,664 sessions / 532 five-session blocks |
| **Why a 5D effect could persist** | 57.9% of filings arrive after the close, so the first tradeable price is the next session's open — the instantaneous reaction is structurally unavailable to us and therefore cannot be what we are measuring. What remains is diffusion into a name that most participants do not follow filing-by-filing. That is a hypothesis and the study exists to falsify it |
| **Biggest leakage risk** | **Survivorship, not timing.** The timing trap (57.9% after close) is already solved by `alpha/filings.py`. The unsolved one is that `company_tickers.json` carries current registrants only, and delisted/bankrupt names are exactly the adverse-event population — so the trap is *correlated with the sign of the effect* and would bias the result toward zero or, worse, toward a spurious positive. Identity must be CIK, joined to point-in-time index membership |
| **Biggest statistical risk** | The sub-50% claim needs a **6.4–7.0 pp** shift, against published post-event drifts that are mostly documented at 30–90 days, not 5. The family may clear claim (a) and still fail the claim that makes it useful |
| **Minimum pilot before full ingest** | Four measurements, in order, none of which reads a forward return: (1) symbol breadth and per-year event counts for the adverse pool, keyed on CIK with dead names retained; (2) the §2.10 clause-3 correlation ceiling of the event dummy against `z__ret_12_1`, B3 and the existing 34-column set; (3) the §2.6 power gate recomputed on the *actual* post-survivorship-repair event count, with the block length frozen **before** any half-width is read; (4) a PIT door test proving the event panel is unchanged when future filings are rewritten. **If (1) or (3) fails, the family is not implemented and the slot is not opened.** |

### 7.2 Draft preregistration structure — NOT EXECUTED

Recorded here so its shape is on the record before any measurement, per CLAUDE.md §5.2. It
is a skeleton, not an authorisation.

```
§0  Standing: a new family under a new account-holder directive. Slot accounting stated
    explicitly. V3 and V4 remain CLOSED; this is not a continuation of either.
§1  Frozen constants: horizon 5 (inherited), target asset_return (absolute), adverse item
    set enumerated, sign fixed negative, acceptance-time rule, dev/exam split unchanged.
§2  Event construction: item membership, the 2.02 exclusion, CIK identity, PIT membership
    join, and the rule for multiple events on one name in one window.
§3  Admissibility gates, all BLOCKING and all computed BEFORE any outcome is read:
      3.1 coverage      - distinct symbols and per-year counts after survivorship repair
      3.2 clause 3      - correlation ceiling vs momentum, B3 and the existing features
      3.3 turnover      - implied trading, and cost at 5 bp
      3.4 §2.6 power    - block length frozen first, then the half-width, then the verdict
§4  Arms: exactly two, declared in advance.
      A1  adverse-event dummy, full pool
      A2  the same pool excluding item 2.05, whose sign is the weakest member
    No third arm. No item-by-item scan. No λ. No sign flip at any outcome.
§5  Primary contrast: P(up | event) and E[r | event] against the SAME NAMES ON NON-EVENT
    DATES, paired by block, not against the panel-wide base rate.
§6  Criteria, frozen numerically before measurement, including the sub-50% claim stated
    separately from the "differs from base rate" claim so a partial pass cannot be
    reported as a full one.
§7  What a failure means, fixed in advance: if the adverse pool - the best-signed, best-
    timestamped free event set available - moves neither the up-rate nor the mean, the
    correct conclusion is that free point-in-time data cannot support absolute single-name
    forecasting on this universe at this horizon, and the programme says so.
§8  Budget: this spends the slot whether it passes or fails.
```

---

## 8. Artefacts

| File | Content |
|---|---|
| `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` | This survey |
| `alpha/source_probe.py` | The non-predictive probe and the calibrated resolution surface. Reads no price, no return, no target |
| `alpha/out/source_probe_8k.json` | Every measured 8-K number quoted above |

Reproduce with `./venv/Scripts/python.exe -W ignore -m alpha.source_probe`.

**Nothing was ingested. No model was fitted. No forward outcome was read. The 72-cutoff exam
remains SEALED at `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0` and was
not opened. Production weight remains 0.0. No family budget slot has been spent by this
survey — opening the family above is a separate, deliberate act.**

*Independent-review note: the CLAUDE.md second-opinion route was unavailable on 2026-08-11 —
Gemini CLI returned a daily-quota error and the local `qwen3:30b` failed over both the MCP
transport and the shell fallback. The arithmetic was therefore self-checked instead, which is
how the §3.3 accounting error was found and corrected. A second opinion on §1 and §3.3 remains
an open action.*
