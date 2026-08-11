# Family 10 — SEC 8-K adverse-event items: admissibility pilot

**Written 2026-08-11.** Commissioned after `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md`
returned `SOURCE SURVEY VERDICT: OPEN ONE FAMILY` at `4a966a2`, to decide whether
the surviving candidate is *scientifically admissible* **before** the family
budget slot is opened.

> ```text
> FAMILY10 ADMISSIBILITY: FAIL
> ```
>
> **Single blocking reason: POWER.** At a block length fixed by the dependence
> structure of event-time sampling (L = 24 sessions, D = 111 blocks), the study's
> resolution on the primary sample is **57.8 bp per 5 sessions** against the
> **39 bp** economic hurdle the source survey fixed at `4a966a2` before this
> pilot began — and at that block length 39 bp is **unreachable at any event
> count**, because the half-width floors at 49.0 bp.
>
> **Family slot spent: NO.**

**Nothing predictive was done.** No forward return was read. No sign was fitted.
No post-event return was calculated. The sealed exam
(`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`) was never
opened — only its cutoff *dates* were read, which is calendar arithmetic.
Production weight remains **0.0**. Nothing was pushed.

| stage | commit | verdict |
|---|---|---|
| 1 — survivorship-safe event panel | **`cc2613b`** | **PASS** |
| 2 — independence / clause-3 ceiling | **`e02d857`** | **PASS** |
| 3a — block length frozen before any half-width | **`b75a70e`** | L = 24 frozen |
| 3b — power gate | **`ac2505e`** | **FAIL** |
| 4 — PIT invariance proof | — | **not reached** |

Full stage records: `FAMILY10_STAGE1_PANEL.md`,
`FAMILY10_STAGE2_INDEPENDENCE.md`, `FAMILY10_STAGE3_POWER.md`.

---

## 1. Candidate

**SEC 8-K adverse-event items.** Discrete, dated, firm-specific disclosures whose
direction is fixed by the statutory taxonomy rather than estimated — the only
candidate in the survey's field of ten with an a-priori sign, and the reason it
outranked larger and cleaner sources (survey §5: *"sign is the binding
scarcity"*).

Source: SEC EDGAR bulk `submissions` archive, already on disk, genuinely free.

## 2. Frozen event items

```
1.02  termination of a material definitive agreement
1.03  bankruptcy or receivership
2.04  triggering events that accelerate a financial obligation
2.05  costs associated with exit or disposal activities
2.06  material impairments
3.01  notice of delisting or failure to satisfy a listing rule
3.02  unregistered sales of equity securities (dilution)
4.02  non-reliance on previously issued financial statements
```

**Item 2.02 (earnings) is excluded structurally**, not filtered later: an 8-K
carrying 2.02 is out of this family whatever else it carries (222 filings
dropped on that rule alone). It is the V4-SUE family's own information, and
V4-SUE was REJECTED with its slot barred.

No item was added or removed during the pilot. No item was split by observed
returns. No sign was estimated.

## 3. Survivorship result

**The pilot's most important finding, and the one it existed to produce.**

Rebuilding the panel on *today's* registrants instead of point-in-time CIK
identity loses **10.2% of events overall — but the loss rises monotonically with
how adverse the event is**:

| item | safe | current-registrant only | **lost** | current-index-member only | **lost** |
|---|---:|---:|---:|---:|---:|
| **3.01 delisting** | 118 | 68 | **42.4%** | 63 | **46.6%** |
| **1.03 bankruptcy** | 5 | 4 | **20.0%** | 4 | 20.0% |
| **4.02 non-reliance** | 12 | 9 | **25.0%** | 8 | **33.3%** |
| 2.04 acceleration | 64 | 54 | 15.6% | 43 | 32.8% |
| 2.06 impairments | 138 | 121 | 12.3% | 113 | 18.1% |
| 1.02 termination | 853 | 756 | 11.4% | 690 | 19.1% |
| 2.05 exit costs | 211 | 189 | 10.4% | 153 | 27.5% |
| **3.02 dilution** | 393 | 371 | **5.6%** | 326 | 17.1% |
| **total** | **1,682** | 1,510 | **10.2%** | 1,347 | **19.9%** |

The item that most directly announces a company's death loses **eight times**
the share of the item that merely dilutes it. A present-day-symbol
reconstruction does not merely lose power — it deletes the negative tail of the
distribution the hypothesis is about. **The panel used here does not carry that
bias.**

Retained:

| | |
|---|---|
| Historical securities in the panel | **485** |
| …that are **not** current index members | **133** |
| Issuers that are **no longer SEC registrants at all** | **70**, contributing **172 events** |
| Ever-member tickers with no entry in `company_tickers.json` | **120 of 720 (16.7%)** |

**Ticker reuse, caught rather than assumed away.** Nine tickers resolve to a CIK
different from today's holder of the symbol, because the present holder filed
nothing while the historical member was in the index — `SE` (Sea Ltd *vs*
Spectra Energy), `STI` (Solidion *vs* SunTrust), `TE` (T1 Energy *vs* TECO),
`APC` (ARKO *vs* Anadarko), `POM` (POMDOCTOR *vs* Pepco), `AA` (Alcoa Corp *vs*
Alcoa Inc/Arconic/Howmet). This is a **silent** survivorship channel: it does not
lose rows, it mislabels them. A related price-side hazard is recorded and not
repaired, because this pilot reads no prices: `alpha/cache/SBNY.csv` begins
2024-08-15 at $1.79 and is **not** Signature Bank.

**A structural hole, reported not repaired.** Signature Bank (CIK 1288784) and
First Republic Bank (CIK 1132979) filed **only** `SC 13G`/`SC 13D` with the SEC
— no 10-K, no 10-Q, **no 8-K**. Both were state-chartered banks reporting to the
FDIC under Exchange Act §12(i). The two largest bank failures of 2023 are
**structurally absent from EDGAR** under any identity scheme, and resolving their
CIKs would add nothing.

## 4. PIT identity design

```
ticker  --(1)-->  historical security name    S&P change log — the Security columns
                                              membership.refresh() discards
name    --(2)-->  CIK                         SEC bulk submissions: name + formerNames,
                                              dead registrants included
CIK     --(3)-->  membership interval         membership.members_at, unchanged
```

**Link 1 does not disturb the frozen universe.** The name sidecar was fetched
fresh on 2026-08-11 and agrees with the change log frozen on 2026-08-08 exactly
— **225 additions, 226 removals, zero drift** over the study window. The
membership files were not rewritten.

**Link 2 is corroborated, never assumed — names propose, filings dispose.** A
candidate CIK is accepted only if it was filing periodic reports as a listed
equity issuer *during the interval the ticker was in the index* (≥150-day
memberships demand a 10-K/10-Q/20-F/40-F; shorter ones demand any filing, because
none was due). Ties break on proxy filings, which only an equity issuer files.

| method | tickers |
|---|---:|
| `sec_ticker` — in a current registrant's ticker array, corroborated | 593 |
| `sec_name` — name-compatible after legal-form and state-tail normalisation | 109 |
| `sec_name_subset` — every distinguishing word present in the legal name | 2 |
| **unresolved** | **16** |
| **total** | **720 (97.8% resolved)** |

**704 tickers → 688 CIKs**; 13 CIKs carry more than one security, and events are
counted per CIK so a dual-class issuer contributes one observation.

An earlier resolver reached 6 further tickers with a weaker first-word rule and
**two of its six answers were wrong** (*Ferguson Enterprises* → `FERGUSON
WELLMAN CAPITAL MANAGEMENT`; *Signature Bank* → `GB SCIENCES INC`). That tier was
deleted rather than tuned, and both errors are pinned by test. A hole is
countable; a guess is not.

**PIT event timestamp.** `acceptanceDateTime` → Eastern via
`alpha.filings.et_from_utc` → the earliest session *T* with
`accepted < 16:00 ET on T`. This is not a second door — it is
`FilingsBook.view`'s own predicate solved forwards, and a test asserts the
agreement hour by hour. **Filings with no acceptance timestamp: 0.** None was
approximated.

## 5. Coverage

| stage | filings |
|---|---:|
| Raw 8-K by a resolved CIK, 2016-01-04 → 2026-07-31 | 87,794 |
| Carrying at least one adverse item | 2,589 |
| − item 2.02 present (structural exclusion) | −222 |
| Candidate adverse filings | 2,367 |
| − no usable session before the horizon runs out | −7 |
| PIT-eligible filings | 2,360 |
| − issuer **not an index member** on that session | **−673** |
| Historical-membership-eligible filings | 1,687 |
| collapse same issuer + same information session | **1,682 issuer-events** |
| non-overlapping (5-session refractory per issuer) | 1,651 |

**Against the survey's 2,419: a 30.5% reduction**, of which the point-in-time
membership join is by far the largest component and is a *correction*, not a
loss — a filing made before an issuer joined the index or after it left is not
an observation this universe ever had.

| | |
|---|---|
| Unique CIKs | **477** |
| Unique event sessions | **1,221** of 2,664 (45.8%) |
| Occupied 5-session blocks | 498 of 532 |
| Accepted at or after 16:00 ET | **61.1%** — a `filed <= cutoff` join would leak on three filings in five |
| Amendments (`8-K/A`) excluded, counted | 1,883 total, 84 adverse |

Per year — no year is thin and none dominates (2026 is seven months):

| | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| events | 180 | 139 | 170 | 157 | 192 | 167 | 115 | 135 | 136 | 184 | 107 |
| issuers | 131 | 112 | 126 | 121 | 121 | 125 | 100 | 115 | 108 | 137 | 86 |
| sessions | 119 | 110 | 123 | 115 | 134 | 124 | 85 | 96 | 102 | 135 | 78 |

**Recorded before any power arithmetic:** the two items with the strongest
a-priori sign are the two with almost no events — 1.03 and 4.02 together are
**17 of 1,682**.

## 6. Independence — §2.10 clause 3: **PASS**

Ceilings carried unchanged from `alpha/V3_PREREGISTRATION.md` §2.1 and
`alpha/V3_FAMILY2_PREREGISTRATION.md` §8, both fixed **before Family 1 ran**.
Metric identical to `v3_build_insider.per_cutoff_spearman`. B3 is not in the
34-column set, so it was held to the tighter *momentum* ceiling — decided and
written down before the number was computed.

| | ceiling | measured | |
|---|---:|---:|---|
| vs `z__ret_12_1` | 0.30 | **0.0437** | PASS |
| vs `b3_rank` | 0.30 | **0.0432** | PASS |
| vs each of the 34 inputs | 0.50 | **0.0458** worst (`z__sma200_dist`) | PASS, 0 breaches |

Nothing reaches a sixth of its ceiling. 316 development cutoffs, **0 exam
cutoffs**; outcome columns are dropped by name and their absence asserted in
code before any statistic is computed.

**Sparsity is disclosed, not banked.** At 0.6% prevalence a Spearman is bounded
well below 1 by construction. The rank-biserial (2·AUC−1) of each feature's
within-cutoff percentile rank is reported alongside — a location shift that does
not shrink with prevalence and can therefore only make the family look *more*
dependent:

| | event names sit at percentile | others | rank-biserial |
|---|---:|---:|---:|
| 12-1 momentum | 0.4766 | 0.5012 | **−0.047** |
| B3 | 0.4905 | 0.5012 | **−0.019** |
| **20-day realised volatility** | **0.5759** | 0.5007 | **+0.152** |

The one dependence worth naming: **adverse-event names are more volatile than
average before the event**. It breaches nothing, volatility is not the incumbent,
and it is recorded here — before any outcome — so it could never be discovered
later as a result.

**A correction recorded rather than quietly fixed.** A first pass used
`panel["development"]`, the older V1 twelve-date split, which does not exclude
the 72 sealed cutoffs; it read no outcome but inspected cutoffs `CLAUDE.md` §6.1
reserves. Corrected to `examset.load().development`. The superseded numbers
(0.0440 / 0.0435) are published so nobody has to wonder whether the correction
moved the verdict. It did not.

## 7. Concentration

| | all events | panel-priceable | **primary** |
|---|---:|---:|---:|
| Events | 1,682 | 1,478 | **687** |
| Unique event sessions | 1,221 | 1,118 | **520** |
| Unique issuers | 477 | 407 | **316** |
| Blocks occupied (of 111) | 111 | 111 | **110** |
| Events per occupied block, mean / max | 15.15 / 28 | 13.32 / 25 | **6.25 / 20** |
| Issuers per occupied block, mean | 14.44 | 12.68 | **6.09** |
| Largest single block's share | 1.66% | 1.69% | **2.91%** |
| Dates carrying exactly one event | 71.3% | 72.3% | **75.4%** |
| Largest single issuer's share | 1.19% | 1.35% | **1.46%** |
| Top-10 issuers' share | 8.68% | 9.88% | **10.77%** |
| Same-issuer pairs inside one block | 143/1,205 (11.9%) | 126/1,071 (11.8%) | **27/371 (7.3%)** |

**Concentration is not this family's problem.** The panel is date-spread rather
than date-clustered, three quarters of event dates carry exactly one event, and
no issuer contributes 1.5%. Had the family failed on concentration the diagnosis
would be different and possibly repairable. It did not.

The primary sample's two reductions:

* **1,682 → 1,478 (−12.1%)** — the *pricing* survivorship channel. `alpha/universe.py`
  demands bars, 252 sessions of history, $3M median dollar volume and a $3 price;
  a company whose bars no longer exist has no computable forward return however
  well its CIK is identified. Concentrated the same way Stage 1's loss was:
  **47.8% of item 3.01** against 11.7% of item 3.02. **This one cannot be
  repaired from free data.**
* **1,478 → 687 (−53.5%)** — the **sealed exam**. Seventy-two cutoffs with
  ±9-session guard bands cover 51% of the calendar. Paid here rather than argued
  away.

## 8. Frozen block choice

> **L = 24 sessions → D = 111 blocks.** Frozen at `b75a70e`, **before any
> half-width existed**; the freeze artefact contains no MDE and a test asserts it.

Two derivations from dependence structure only, both landing in the same place:

1. **Mechanical overlap + the record's own persistence allowance.** In event time
   two events closer than the horizon share forward sessions, so `q = 4` — where
   V3's grid study had `q = 0` because its cutoffs were spaced exactly one
   horizon apart. `alpha/stats.py` sets `BLOCK_LENGTH = 4` cutoffs and names the
   span *"~one month"*, which at `H = 5` with `q = 0` was **20 sessions of pure
   persistence allowance**. Same market, same horizon: `L = 4 + 20 = 24`.
2. **`n^(1/3)` in the units of the resampling observation.** V4-SUE's were
   cutoffs (`313^(1/3) = 6.79 → 7`). Family 10's are event sessions:
   `1221^(1/3) = 10.69` event sessions × `2664/1221 = 2.182` calendar sessions
   each = **23.3 → 24**.

They agree, so `alpha/V4_CHARTER.md` §6.1's longer-when-tied rule was not needed.
The survey pre-declared 532 blocks at L=5 and 266 at L=10 with *"the conservative
column governs"*; **111 is more conservative than both** and was reached from the
structure rather than from either figure.

## 9. Power — the blocking stage

**The hurdle was not chosen here.** `ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §1.2 claim
(c), committed at `4a966a2`: an effect is economically useful above **~39 bp per
5 sessions** (Phase 1's covered-book resolution). §3.3 applied it as a pass/fail
test — *"resolves to 27.7–35.6 bp, inside Phase 1's 39 bp. **Clears.**"*

### Directional and economic MDE, at the frozen L = 24

| sample | n | **return MDE** | **up-rate MDE** | sub-50% needs |
|---|---:|---:|---:|---:|
| all events | 1,682 | 52.7 bp | 4.80 pp | 8.50 pp |
| panel-priceable | 1,478 | 53.2 bp | 4.88 pp | 8.58 pp |
| **primary — development-safe** | **687** | **57.8 bp** | **5.56 pp** | **9.26 pp** |

The survey predicted 27.7–35.6 bp for this family. The repaired panel resolves
**57.8 bp** — an over-estimate by **1.6–2.1×**, every component of it measured:
2,419 → 687 usable events, 532/266 → 111 independent blocks.

### The verdict does not turn on the block choice

| L | blocks | primary MDE | |
|---:|---:|---:|---|
| **5** | 532 | **38.0 bp** | the only length that clears |
| 7 | 380 | 40.5 bp | fails |
| **10** | 266 | **44.1 bp** | fails — *the survey's own conservative column* |
| 14 | 190 | 48.4 bp | fails |
| 21 | 126 | 55.3 bp | fails |
| **24** | **111** | **57.8 bp** | **frozen — fails** |
| 30 | 88 | 63.0 bp | fails |

It clears only at L = 5, the choice with zero allowance for market persistence,
contradicting `alpha/stats.py`'s own standard and the column the survey declined
to let govern.

### The structural reason no additional data repairs

The bracket tends to `ρ`, not to zero — the common market move never diversifies
away. So the half-width has a **floor**:

| L | blocks | floor as n → ∞ |
|---:|---:|---:|
| 5 | 532 | 22.4 bp |
| 10 | 266 | 31.6 bp |
| **24** | **111** | **49.0 bp** |

> **At the frozen block length, 39 bp is unreachable at any event count.** Not
> difficult — unreachable. Every 8-K ever filed would not get there, because the
> binding constraint is the number of independent time blocks 2016–2026 contains.

This is the survey's own §1.1 result — *"resolution is bought with independent
dates, not with more names per date"* — turned around and applied to the family
the survey recommended. It believed event-time sampling bought 532 or 266
blocks. Set by the dependence structure the sampling actually has, it buys 111.

### Sub-50% detectability requirement

**A 9.26 pp shift** in the conditional up-rate — i.e. `P(up | adverse event)`
would have to fall to **0.4444 or below** for the study to distinguish it from
the 0.537 base rate. The survey put this at 6.4–7.0 pp and already labelled it
**BORDERLINE**. It is now half again as far away.

This is the claim the family was *selected* for: the credible sub-50% group that
Phase 1 could not produce in 101,137 symbol-dates, and the only reason 8-K
adverse items outranked larger and cleaner candidates.

**"The effect might be huge" is not available.** The directive forbids it, and
there is a specific reason it would be wrong here: **61.1% of these filings are
accepted after the close (measured)**, so the first tradeable price is the next
session's and the instantaneous reaction is structurally unavailable. Only
residual drift is capturable, and residual drift is not a 58 bp five-session
effect.

## 10. PIT mutation result

**NOT REACHED.** Stage 4 runs only after Stage 3 passes; the pilot directive is
explicit — *"If underpowered: `FAMILY10 PILOT: FAIL — POWER`. Commit and stop."*
No mutation test was constructed and none is claimed.

What *was* proved about point-in-time behaviour, in the stages that were reached:

* The event clock is `alpha/filings.py`'s existing door solved forwards, not a
  second rule, and `test_family10_panel.py` asserts the agreement across all 24
  hours of a session.
* The 16:00 ET boundary is pinned in both directions: **15:59:59 is eligible for
  that session, 16:00:00 exactly is not** and waits for the next — plus the
  weekend and holiday cases.
* Identity resolution is corroborated against filing behaviour *inside* the
  membership interval, which is what makes a reused ticker fall through to its
  historical owner rather than silently rebinding an old event.

These are unit guarantees on the panel's construction. They are **not** the
mutation proof Stage 4 asks for — rewriting the future and demanding an
identical past — and nothing here should be read as if they were.

## 11. Test suite

| | |
|---|---|
| Collected **before** the pilot | **768** |
| Collected **after** | **840** (+72) |
| Passed | **777** |
| Skipped | **63** (unchanged — `@slow`, needing `--runslow`) |
| **Failed** | **0** |

No existing test was weakened, relaxed, skipped or removed.
`test_validation.py::test_future_cannot_change_the_verdict` passes.

New: `test_family10_panel.py` (33), `test_family10_ceiling.py` (19),
`test_family10_power.py` (20).

## 12. Slot status

```text
Family slot spent: NO
```

No predictive experiment was implemented. No forward return was read. No sign
was fitted. No post-event return was calculated. No preregistration was drafted
— the directive authorises a draft only on PASS. The sealed exam remains sealed
at `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.
Production weight remains **0.0**. Nothing was pushed.

---

## 13. What this result does and does not establish

**Established.** The family is admissible on *identity* and on *independence*,
and the evidence for both is strong rather than marginal. What it is not, is
**resolvable**: on a 2016–2026 window, at a five-session horizon, with a block
length set by the dependence structure of event-time sampling, an absolute
single-name return study has a floor of 49 bp and this family's best claim needs
resolution below 39 bp.

**Not established.** Whether an effect exists. The pilot did not look and may not.

**Where the survey went wrong, precisely.** Its §1.1 identified the right
structural constraint and then applied it with a block length it did not
derive — it took 532 and 266 from dividing the calendar by the horizon and by
twice the horizon, rather than from the dependence structure of the sampling
scheme it was proposing. §5's central argument — *"an event-driven design is the
only lever that moves it, because events land on every trading session rather
than on 215 Tuesdays"* — is true about *event dates* and false about
*independent* ones. Events do land on 1,221 sessions; those sessions are not
1,221 independent draws, and once blocked properly they are 111.

**The reusable measurement.** The half-width floors of §9 are a property of the
study window and the target, not of this family:

| block length | independent blocks | floor, as n → ∞ |
|---:|---:|---:|
| 5 sessions | 532 | 22.4 bp |
| 10 sessions | 266 | 31.6 bp |
| 24 sessions | 111 | **49.0 bp** |

Any future absolute-return candidate on this universe and window must clear its
own claim against these, **before** it is proposed — not after a panel has been
built for it. That is the cheapest thing this pilot produced and it should be
the first thing the next one reads.

---

```text
FAMILY10 ADMISSIBILITY: FAIL
```

**Blocking reason: POWER.** The post-repair effective sample does not make the
preregistered primary claim realistically detectable, and at the frozen block
length no achievable event count would.

**The family is not implemented. The slot is not opened. No returns were read.**
