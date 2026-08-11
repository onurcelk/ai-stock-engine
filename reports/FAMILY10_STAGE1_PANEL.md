# Family 10 — Stage 1: the survivorship-safe 8-K adverse-event panel

**Written 2026-08-11. NON-PREDICTIVE. No forward return was read, no price was
loaded, no sign was fitted, no exam cutoff was opened, no family budget slot was
spent.** This is the first of four admissibility stages and it is committed
before Stage 2 is begun, per the pilot directive's commit discipline.

Reproduce:

```
./venv/Scripts/python.exe -W ignore -m alpha.family10_identity   # the CIK map
./venv/Scripts/python.exe -W ignore -m alpha.family10_panel      # the event panel
./venv/Scripts/python.exe -m pytest app/tests/test_family10_panel.py
```

> ## Stage 1 verdict: **PASS**
>
> The panel is rebuilt on CIK identity against point-in-time index membership,
> retains 133 securities that are not current index members and 70 issuers that
> are no longer SEC registrants at all, and depends on unresolved identity for
> **0.40% of issuer-years (≈7 of 1,682 events)**. The survey's 2,419 filings
> become **1,682 issuer-events** — and the reduction is measured, decomposed and
> attributed rather than absorbed.

---

## 1. The finding Stage 1 exists to produce

The survey (§4 row J) named **sign-correlated survivorship** the family's fatal
risk and could not measure it. It is now measured, and it is real.

Rebuilding the same panel on **today's** registrants instead of point-in-time
CIK identity loses **10.2% of events overall** — but the loss is not uniform:

| item | meaning | survivorship-safe | current-registrant only | **lost** |
|---|---|---:|---:|---:|
| 3.01 | **delisting / listing-rule failure** | 118 | 68 | **42.4%** |
| 4.02 | **non-reliance (restatement)** | 12 | 9 | **25.0%** |
| 1.03 | **bankruptcy or receivership** | 5 | 4 | **20.0%** |
| 2.04 | acceleration of a financial obligation | 64 | 54 | 15.6% |
| 2.06 | material impairments | 138 | 121 | 12.3% |
| 1.02 | termination of a material agreement | 853 | 756 | 11.4% |
| 2.05 | exit or disposal costs | 211 | 189 | 10.4% |
| 3.02 | unregistered equity sales (dilution) | 393 | 371 | **5.6%** |

**The loss rises monotonically with how bad the event is.** The item that most
directly announces a company's death loses eight times the share of the item
that merely dilutes it. Restricting harder — to issuers whose ticker is in
*today's* S&P 500 constituent table — costs 19.9% overall and **46.6% of item
3.01**.

That is the bias the directive called potentially fatal, quantified: a
present-day-symbol reconstruction does not merely lose power, it deletes the
negative tail of the very distribution the hypothesis is about. **The panel
below does not do that**, and everything downstream inherits the repair.

---

## 2. Identity: CIK → historical security → membership interval

`alpha/family10_identity.py`. Three links, each sourced and each auditable.

### 2.1 Why the ticker map cannot be the key — measured, not argued

| | |
|---|---|
| Tickers that were S&P 500 members at any point since 2016-01-04 | **720** |
| …with **no entry** in `alpha/edgar/company_tickers.json` | **120 (16.7%)** |
| …of those, with price bars already on disk | **19** |

`company_tickers.json` lists current registrants. A filer that stopped filing
keeps its CIK JSON in the bulk archive but **loses its ticker array** —
`CIK0000098246` (Tiffany) and `CIK0001011006` (Altaba, *ex* Yahoo) both carry
`"tickers":[]`. So the ticker map is structurally blind to exactly the
population this family is built on.

Two SEC snapshots disagree in **both** directions and neither is complete:
`company_tickers.json` covers 7,998 CIKs and omits AEP; the bulk archive
attaches a ticker to 7,957 CIKs and omits 406 that `company_tickers.json` has.
They are unioned, and a disagreement raises a conflict rather than a silent pick.

### 2.2 The chain

```
ticker  --(1)-->  historical security name    S&P change log, the Security columns
                                              membership.refresh() discards
name    --(2)-->  CIK                         SEC bulk submissions: name + formerNames,
                                              dead registrants included
CIK     --(3)-->  membership interval         membership.members_at, unchanged
```

**Link 1 does not disturb the frozen universe.** The name sidecar
(`alpha/cache/_meta/sp500_security_names.csv`) was fetched fresh on 2026-08-11
and checked against the change log frozen on 2026-08-08: over the study window,
**225 additions and 226 removals, zero drift in either direction**. The names
attach to exactly the frozen rows. `sp500_changes.csv` and `sp500_current.csv`
were not rewritten.

**Link 2 is corroborated, never assumed. Names propose; filings dispose.** A
candidate CIK is accepted only if it was actually filing periodic reports as a
listed equity issuer *during the interval the ticker was in the index*:

| membership length | requirement |
|---|---|
| ≥ 150 days | at least one `10-K` / `10-Q` / `20-F` / `40-F` filed inside the interval |
| < 150 days | at least one filing of any form (no periodic report was due — `PCP` was a member for four weeks, `MBC` for four days) |

Ties are broken on proxy filings (`DEF 14A`): only a listed equity issuer holds
a shareholder meeting, which is what separates an operating company from a
financing subsidiary with public debt and the same name.

### 2.3 Result

| method | tickers | what it means |
|---|---:|---|
| `sec_ticker` | **593** | in a current registrant's ticker array, and it corroborated |
| `sec_name` | **109** | name-compatible after legal-form and state-of-incorporation normalisation, unique after corroboration |
| `sec_name_subset` | **2** | every distinguishing word of the short name present in the legal one (`DWDP`→DuPont de Nemours, `CDAY`→Dayforce) |
| **unresolved** | **16** | no candidate survived, or more than one did |
| **total** | **720** | **97.8% resolved** |

**704 tickers → 688 distinct CIKs.** Thirteen CIKs carry more than one security
(`GOOG`/`GOOGL`, `FOX`/`FOXA`, `NWS`/`NWSA`, `UA`/`UAA`, `DISCA`/`DISCK`, and the
rename pairs `AA`/`ARNC`/`HWM`, `CHK`/`EXE`, `CPAY`/`FLT`, `DNB`/`MCO`,
`DPS`/`KDP`, `EG`/`RE`, `JCI`/`TYC`, `WLTW`/`WTW`). Events are counted **per
CIK**, so a dual-class issuer contributes one observation, not two.

### 2.4 Ticker reuse, caught rather than assumed away

The corroboration test's other job. Nine tickers resolve to a CIK **different
from the one that holds the symbol today**, because the present holder filed
nothing while the historical member was in the index:

| ticker | today's holder of the symbol | the historical member |
|---|---|---|
| `SE` | Sea Ltd | Spectra Energy |
| `STI` | Solidion Technology | SunTrust Banks |
| `TE` | T1 Energy | TECO Energy |
| `APC` | ARKO Petroleum | Anadarko Petroleum |
| `POM` | POMDOCTOR Ltd | Pepco Holdings |
| `AA` | Alcoa Corp (2016 spin-off) | Alcoa Inc → Arconic → Howmet, CIK 4281 |

A panel keyed on present-day symbols would have attached Spectra Energy's 2016
filings to a Singaporean e-commerce company. **This is a second survivorship
channel, and it is silent** — it does not lose rows, it mislabels them.

A related price-side hazard is recorded and **not** repaired here because Stage 1
reads no prices: `alpha/cache/SBNY.csv` begins **2024-08-15 at $1.79**. That is
not Signature Bank, which failed in March 2023. Any later stage that joins this
panel to bars must resolve the price series by the same PIT identity, not by
file name.

### 2.5 The 16 unresolved, and why they do not carry the panel

| ticker | days in index | ticker | days in index |
|---|---:|---|---:|
| `FRC` First Republic Bank | 1,583 | `CCE` Coca-Cola Enterprises | 148 |
| `VIAB` Viacom | 1,431 | `ADT` ADT Corp | 120 |
| `TSS` TSYS | 1,358 | `BRCM` Broadcom Corp | 28 |
| `CA` CA Technologies | 1,037 | `ACE` ACE Ltd | 15 |
| `BCR` C. R. Bard | 730 | `FERG` Ferguson | 6 |
| `DNB` Dun & Bradstreet | 457 | `BMS` Bemis | 4 |
| `SBNY` Signature Bank | 450 | `FOSL` Fossil | 1 |
| `HOT` Starwood | 262 | `CVC` Cablevision | 170 |

They fail for three honest reasons: an acronym or short name with no
mechanical route to the legal one (`TSS`→*Total System Services*,
`BCR`→*Bard C R Inc*, `HOT`→*Starwood Hotels & Resorts Worldwide*); two
same-named registrants both of which corroborate (`ACE`/Chubb, `VIAB`/Paramount,
`CCE`, `CVC`, `DNB`, `BRCM`); or a membership window too short to contain a
filing at all (`FOSL` 1 day, `BMS` 4 days, `FERG` 6 days).

**Exposure, bounded:**

| | |
|---|---|
| Resolved issuer-years in the window | **5,333.7** |
| Unresolved issuer-years | **21.4** |
| Share of the panel's exposure that is unresolved | **0.40%** |
| Measured event rate | 0.315 events / issuer-year |
| **Expected events lost to unresolved identity** | **≈ 7 of 1,682 (0.4%)** |

An earlier version of the resolver reached 6 further tickers with a weaker
first-word rule. **Two of its six answers were wrong** — it mapped *Ferguson
Enterprises* to `FERGUSON WELLMAN CAPITAL MANAGEMENT` and *Signature Bank* to
`GB SCIENCES INC`. That tier was deleted rather than tuned, and both errors are
now pinned by test. A hole is countable; a guess is not.

### 2.6 A structural coverage hole, reported not repaired

**`SBNY` and `FRC` cannot contribute events under any identity scheme.**
Signature Bank (CIK 1288784) and First Republic Bank (CIK 1132979) filed
**only** `SC 13G`/`SC 13D` forms with the SEC — no 10-K, no 10-Q, **no 8-K**.
Both were state-chartered banks without a holding company, filing periodic and
current reports with the FDIC under Exchange Act §12(i) instead of with the SEC.

The two largest bank failures of 2023 — as adverse as corporate events get — are
**structurally absent from EDGAR**. This is not a defect of the reconstruction
and resolving their CIKs would add nothing. It is a property of the source, it
is sign-correlated, and it is recorded here so it cannot later be discovered as
a result.

---

## 3. The event panel

`alpha/family10_panel.py`. Item set frozen, 2.02 excluded structurally, sign
fixed by the taxonomy, nothing split by observed returns.

### 3.1 The funnel

| stage | filings |
|---|---:|
| Raw 8-K by a resolved CIK, 2016-01-04 → 2026-07-31 | **87,794** |
| Carrying at least one adverse item | **2,589** |
| − dropped: item 2.02 present (structural exclusion) | −222 |
| **Candidate adverse filings** | **2,367** |
| − dropped: no usable session before the horizon runs out | −7 |
| **PIT-eligible filings** | **2,360** |
| − dropped: issuer was **not an index member** on that session | **−673** |
| **Historical-membership-eligible filings** | **1,687** |
| collapse: same issuer, same information session | → **1,682 issuer-events** |
| non-overlapping subset (5-session refractory per issuer) | → **1,651** |

Filings with no acceptance timestamp: **0**. None had to be approximated, and
none was.

**Against the survey's 2,419.** The survey counted *filings carrying an adverse
item* across 622 current-registrant symbols, with no membership join. The
repaired panel starts from a **wider** issuer set (688 CIKs, dead names
included) and reaches 2,589 such filings — then loses 222 to the 2.02 exclusion
and **673 to point-in-time index membership**, because a filing made before the
issuer joined the index or after it left is not an observation this universe
ever had. Net: **2,419 → 1,682 issuer-events, a 30.5% reduction**, of which the
membership join is by far the largest component and is a correction, not a loss.

### 3.2 The clock

| | |
|---|---|
| Eligible filings accepted **at or after 16:00 ET** | **1,031 of 1,687 = 61.1%** |
| Filings whose information session is **not** their acceptance date | **1,033 = 61.2%** |

Worse than the 57.9% the survey measured over all 8-Ks and worse than the 51.8%
the V3 audit measured for 10-K/10-Q. **A `filed <= cutoff` join would leak on
three filings in five.** The door is `alpha/filings.py`'s, solved forwards:
`information_session` returns the earliest session *T* with
`accepted < 16:00 ET on T`, which is exactly the predicate `FilingsBook.view`
enforces. There is no second timestamp rule, and a test asserts the agreement
hour by hour.

### 3.3 Deduplication, frozen before any analysis

| case | rule | incidence |
|---|---|---:|
| several adverse items in one filing | one event, codes unioned | 107 events |
| several adverse filings, one issuer, one session | one issuer-event, codes unioned | 5 events |
| amendments `8-K/A` | **excluded**, counted separately | 1,883 total, 84 adverse |
| repeat inside the 5-session horizon | first kept, per-issuer refractory period | 31 events |

The refractory rule is greedy-earliest because that is the only rule available
that does not require ranking two events by severity — and a severity scale
fitted to outcomes is precisely what this pilot may not build.

### 3.4 Coverage

| | issuer-events | non-overlapping |
|---|---:|---:|
| Events | **1,682** | 1,651 |
| Unique CIKs | **477** | 477 |
| Unique historical securities | **485** | — |
| …**not** current index members | **133** | — |
| Issuers no longer SEC registrants, retained | **70** (172 events) | — |
| Unique event sessions | **1,221** of 2,664 (45.8%) | 1,201 |
| Occupied 5-session blocks | **498** of 532 (93.6%) | 497 |

Per year (issuer-events / issuers / sessions):

| | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| events | 180 | 139 | 170 | 157 | 192 | 167 | 115 | 135 | 136 | 184 | 107 |
| issuers | 131 | 112 | 126 | 121 | 121 | 125 | 100 | 115 | 108 | 137 | 86 |
| sessions | 119 | 110 | 123 | 115 | 134 | 124 | 85 | 96 | 102 | 135 | 78 |

\* seven months. No year is thin and no year dominates; the range is 115–192.

By item (an event may carry several):

| item | events | issuers |
|---|---:|---:|
| 1.02 termination of a material agreement | 853 | 351 |
| 3.02 unregistered equity sales (dilution) | 393 | 163 |
| 2.05 exit or disposal costs | 211 | 125 |
| 2.06 material impairments | 138 | 85 |
| 3.01 delisting / listing-rule failure | 118 | 94 |
| 2.04 acceleration of a financial obligation | 64 | 36 |
| 4.02 non-reliance (restatement) | 12 | 12 |
| 1.03 bankruptcy or receivership | **5** | 4 |

**Recorded before any power arithmetic:** the two items with the strongest
a-priori sign are the two with almost no events. 1.03 and 4.02 together are 17
of 1,682. Whatever this family can detect, it will not be detected on those two.

### 3.5 Concentration

| | issuer-events |
|---|---|
| Events per session | mean **1.38**, max **5** |
| Sessions carrying exactly one event | **870 of 1,221 (71.3%)** |
| Largest single session's share of the panel | **0.30%** |
| Events per issuer | mean **3.53**, max **20** |
| Issuers with exactly one event | **126 of 477** |
| Largest single issuer's share | **1.19%** |
| Top-10 issuers' share | **8.68%** |
| Events per occupied 5-session block | mean **3.38**, max **12** |
| Issuers per occupied block | mean **3.34** |
| Same-issuer gap between consecutive events | median **236 sessions**; 31 pairs closer than 5 |

The panel is **date-spread, not date-clustered**: 1,221 distinct sessions for
1,682 events, and no session holds more than five. That is the property §1.1 of
the survey said an event family had to have, and it is the input Stage 3 will
turn into a block count.

---

## 4. Stage 1 gate

| # | requirement | result |
|---|---|---|
| 1 | historical membership reconstructed without present-day survivorship filtering | **PASS** — `members_at` at every change-log boundary; 133 non-current securities and 70 non-registrant issuers retained |
| 2 | later-delisted names retained when historically eligible | **PASS** — 172 events from issuers that are no longer registrants at all |
| 3 | CIK is the primary filing identity | **PASS** — the panel is keyed on CIK; tickers are attributes, and 9 reused symbols were caught by it |
| 4 | PIT event timestamp deterministic | **PASS** — `acceptanceDateTime` → ET → earliest session with `accepted < 16:00`; 0 filings without a timestamp |
| 5 | unresolved identity quantified | **PASS** — 16 tickers, 0.40% of issuer-years, ≈7 expected events |
| 6 | effective sample not obviously underpowered | **PASS** — 1,682 events, 477 issuers, 1,221 sessions, 498 of 532 blocks occupied |

```text
FAMILY10 STAGE 1: PASS — SURVIVORSHIP / IDENTITY
```

**Family slot spent: NO.** Stage 2 (independence) may proceed.

---

## 5. Artefacts

| file | content |
|---|---|
| `alpha/family10_identity.py` | the CIK → historical security → membership chain |
| `alpha/family10_panel.py` | the event panel, its frozen dedup rules, the survivorship counterfactual |
| `alpha/edgar/cik_directory.parquet` | 980,321 CIKs: name, tickers, former names, SIC. **Not versioned** (23 MB, regenerable in ~30 s), fingerprinted in `family10_meta.json` like `facts.parquet` before it |
| `alpha/edgar/family10_identity.json` | the resolved map, per-ticker method and evidence |
| `alpha/edgar/family10_meta.json` | the build's fingerprint: SHA-256 of every unversioned input, and the zero-drift check against the frozen change log |
| `alpha/cache/_meta/sp500_security_names.csv` | ticker → security name sidecar. Unversioned like its two siblings under `alpha/cache/` (the repo has excluded that tree since programme closure), so it is pinned by SHA-256 instead: `6fb1e7cd99fa9385145d7a9f6c60d81bdd9fdf5ae24878c4ee2fce2b04cc50e8`. The membership files themselves were **not** rewritten |
| `alpha/out/family10_events.parquet` | 1,682 issuer-events |
| `alpha/out/family10_stage1.json` | every number quoted above |
| `app/tests/test_family10_panel.py` | 33 tests: names, corroboration, the door, the dedup rules, survivorship |
