# Family 2 — admissibility measurements (the three items `FAMILY2_ELIGIBILITY.md` left blocked)

**Written 2026-08-09**, after the account holder froze §1–§5 of
`alpha/V3_FAMILY2_PREREGISTRATION.md`. Reproduce with:

```
./.venv/Scripts/python.exe -m alpha.build_insider      # the purchase table
./.venv/Scripts/python.exe -m alpha.v3_build_insider   # feature, clause 3, turnover
```

> # VERDICT: the three blocked checks now **PASS**. Family 2 is still **NOT authorized to run**.
>
> **Slot 2 of 3 remains UNSPENT.** No study was run, no target was read, no IC against
> forward returns was computed, no threshold or criterion was modified, nothing was pushed.
>
> The **only** remaining blocker is **§6 of the pre-registration — the primary prediction
> horizon**, which is the account holder's to resolve. Everything in this document is
> horizon-independent, which is why it could be measured while §6 is open.

---

## 1. What changed since `FAMILY2_ELIGIBILITY.md`

| # | Check | Was | Now |
|---|---|---|---|
| 1 | Exact feature construction | BLOCKED | **RESOLVED** — frozen by the account holder in `V3_FAMILY2_PREREGISTRATION.md` §1–§5 |
| 3 | §2.10 clause-3 correlation | BLOCKED | **PASS** (§4) |
| 4b | Turnover input to the MDE | BLOCKED | **PASS** — MDE +0.007 stands (§5) |

Two facts discovered while measuring are new, and both are reported rather than repaired
(§6, §7). Neither is a rule violation; both are the account holder's to rule on.

---

## 2. The purchase table

`alpha/build_insider.py`, from the SEC insider-transaction bulk data sets. Implements only
the frozen filter: non-derivative, `TRANS_CODE == 'P'`, acquisitions. `REPORTINGOWNER.tsv`
is never read, so role cannot influence the result even by accident.

| | |
|---|---|
| Quarterly archives | **42**, 2015q4 … 2026q1 |
| Non-derivative rows scanned | 3,190,181 |
| Open-market purchase rows | 19,390 |
| Dropped — no acceptance timestamp | **0** |
| Dropped — unusable shares or price | 43 |
| **Purchases kept** | **19,347** |
| Issuers with ≥1 purchase | **561** of 619 |
| Accepted after the 16:00 ET close | 56.4% |
| Transaction → acceptance lag | median **1 day** |

`2015q4` was added in this pass. Without it the first ten development cutoffs ramped from
0 names up to normal, purely because the archive set began at 2016q1 — an artefact of what
had been downloaded, not of the information. The front boundary is now closed.

## 3. The feature

`insider_purchase_intensity`, 143,675 rows on the **316 development cutoffs**. Exam
contamination **0**, asserted in code.

| | |
|---|---|
| Defined (non-NaN) | **0.9952** — 693 NaN, all of them positive purchases whose market cap was unavailable |
| **Non-zero share per cutoff** | mean **0.1363**, median 0.1396, p10 0.0921 |
| **Non-zero names per cutoff** | median **62**, p10 44, max 130 |
| Purchase value where non-zero | median $300k, p90 $4.9m |

> **The single most important number here: 13.6%, not 95.9%.**
>
> `FAMILY2_ELIGIBILITY.md` §3 and `FAMILY2_POWER_GATE.md` §3.1 measured coverage as
> **0.959 at a 90-day window** — but that was the share of the cross-section with **any
> Form 4**. The frozen feature admits **open-market purchases only** (§1 of the
> pre-registration), and insiders sell, receive awards and exercise options far more often
> than they buy. On the actual pre-registered filter, **a median of 62 names out of ~455
> carry a non-zero value and the other ~86% are tied at exactly zero** by §5.
>
> This is not a defect and it does not violate any rule — §5 pre-registered the point mass
> at zero and pre-recorded the large tied block as a property of the design. But **the
> coverage figure the power gate was computed on is not the coverage this feature has**,
> and §8 below states what that does and does not change.

## 4. §2.10 clause 3 — the correlation ceiling: **PASS**

Ceilings fixed in `V3_FAMILY2_PREREGISTRATION.md` §8 (carried unchanged from Family 1)
**before this measurement was taken**. Per-cutoff Spearman, feature-vs-feature only; the
`z__` columns are built with `alpha/carrier.py`'s own tested `add_rank_columns`, not
approximated.

| | ceiling | measured | |
|---|---|---|---|
| vs `z__ret_12_1` | ≤ 0.30 | mean \|ρ\| **0.1313** (mean ρ **−0.1310**, p95 0.2260, n=312) | **PASS** |
| vs each of the 34 inputs | ≤ 0.50 | highest **0.1432** (`z__sma200_dist`) | **PASS** |

Next highest: `z__rvol_60d` 0.1001, `z__rvol_20d` 0.0825, `z__ret_20d` 0.0562. **No column
comes within a factor of three of its ceiling.**

**The sign is economically coherent and was not chosen:** the mean correlation with 12-1
momentum is **negative**. Insiders buy their own stock after weakness and below the
200-day average. The pre-registered Arm 0 sign is **+1 on the prior that insider buying is
good news**, so the arm is a contrarian tilt on a momentum-based incumbent — which is the
strongest available argument that it carries information B3 does not already have.

## 5. Turnover and the MDE — **PASS**

The number `FAMILY2_ELIGIBILITY.md` §5.3 could not fill. Same definition as
`v3_family1.py::_turnover` (top-quintile long book, average ties), so it is comparable.

| Book | turnover |
|---|---|
| Arm 0 — feature alone | **0.1126** (Family 1's SUE: 0.091) |
| B3 — the incumbent | 0.2308 |
| Arm 1 — B3 + 0.25 tilt | 0.2333 |
| **Extra turnover, Arm 1 − B3** | **+0.0025 = 0.3 pp** |

The §2.6 gate's MDE of **+0.007 holds while extra turnover ≤ 30 pp**. Measured at
**0.3 pp**, a hundredth of the allowance. **The +0.007 MDE stands as computed**, and it is
now a measurement rather than the assumption the gate had to carry.

## 6. Reported, not repaired: the denominator has a few bad values

The pre-registered denominator is `dei:EntityCommonStockSharesOutstanding` × close. It is
a cover-page value and a handful of filers report a placeholder — FOX's only such fact is
literally `1.0` shares, accepted 2019-03-18, which makes its market cap ≈ $33.

| | |
|---|---|
| Rows implying insiders bought **>100% of the company** | **105** of 19,347 non-zero (0.54%) |
| Affected symbols | **FOX, FOXA, PSA, VTRS** (3 issuers — FOX and FOXA share a CIK) |
| Rows > 0.50 | 117 |
| Rows > 0.10 | 143 |

**Not repaired, deliberately.** §2 of the pre-registration says "no winsorisation beyond
what §3 fixes", and §3 fixes none. Inventing a cleaning rule after seeing the data is the
retrofit the protocol exists to prevent.

**What limits the damage:** both arms consume the feature as a **within-cutoff rank**, and
a rank is invariant to how wrong a large value is — a broken denominator can only place a
name at the top of the ranking, not by an unbounded amount. At ~3 issuers out of 561 the
exposure is 4 names that would rank near the top whenever they appear. **This is the
account holder's to rule on**, and the two clean options are to accept it as measured or
to pre-register an explicit admissibility rule on the denominator *before* the study.

**Dual-class is not a defect:** FOX and FOXA share a CIK and therefore receive the same
issuer-level value. §1 specifies "one number per (cutoff, **issuer**)", so this is
conformant, not an error.

## 7. Reported, not repaired: the tail of the development set is truncated

| | |
|---|---|
| Last transaction date in the bulk archives | **2026-03-30** |
| Development cutoffs whose 90-day window runs past it | **10 of 316** (2026-04-09 … 2026-07-28) |
| Of those, cutoffs with **no** purchase data at all | **4** (2026-07-07 … 2026-07-28) |

`2026q2` and `2026q3` **are not yet published by the SEC** — both return HTTP 404 as of
2026-08-09. The front boundary was closable by fetching `2015q4`; this one is not
closable from bulk data at all.

This is the **opposite of a leak** — those cutoffs see *less* than was actually knowable
at the time — but it does thin the feature across the last ten cutoffs (62 → 51 → 38 → 24
→ 0 names). The four empty cutoffs drop out of any IC automatically for want of
cross-sectional variation, which is why clause 3 reports **n = 312, not 316**.

Three routes, all the account holder's: accept 312 effective cutoffs and record the ten as
truncated; wait for the SEC to publish `2026q2`; or parse the daily index for the tail,
which would introduce a second ingest path with different parsing and is the least
attractive of the three.

## 8. What this does — and does not — do to the §2.6 gate

**The gate's PASS is not threatened, and the reason matters.** `FAMILY2_POWER_GATE.md`
§3.2 measured the half-width using "coverage-matched uninformative features — uniform
random draws on exactly the names a real feature would cover" at **coverage 0.959**. The
frozen feature instead gives ~86% of the cross-section an **identical** rank. A tilt that
moves most names by the same constant reorders nothing, so the realised paired difference
will be **less** variable than the gate modelled — a **narrower** half-width, and §2.6
blocks only when the half-width **exceeds** the effect sought.

**But §2.12 says a free power gain is a warning, so it is measured rather than enjoyed:**

| | |
|---|---|
| Cross-section tied at zero | **86.3%** |
| Names the tilt can reorder at all | **13.7%** |
| **Spearman(Arm 1, B3) per cutoff** | **0.9896** (min 0.9810) |
| Top-quintile names changed by the tilt | **5.4%** mean, 14.3% max |

**Arm 1 is 99% the same ranking as B3 and replaces about one name in twenty of the traded
book.** That is not inert — the tilt does move something — but it is a weaker instrument
than the gate's model assumed, and it is the same shape as the finding that closed V2.3:
*resolution and authority are the same dial.* Family 1 reached λ = 0.25 with 93% coverage
and measured +0.00090 against a ±0.00229 interval.

**Recorded here, before the study, so that a tight interval around a small number is read
as the design's known property and not discovered afterwards as a result.** Nothing in
this section changes a threshold, a criterion or the MDE — all of which stay exactly as
pre-registered.

## 9. Status

| | |
|---|---|
| Feature built | **Yes** — `alpha/out/insider_panel.pkl` |
| §2.10 clause 3 | **PASS** |
| Turnover / MDE | **PASS** — +0.007 stands |
| Family 2 study run | **No** |
| **Slot 2 of 3** | **UNSPENT** — 1 spent (Family 1), **2 remaining** |
| Thresholds / criteria / budget / stopping rules modified | **None** |
| Family 2 **authorized to run** | **NO** — blocked on §6 (horizon) alone |
| Exam | sealed, `b55e065f…`, never opened |
| Production | weight 0, HOLD, `alpha/adapter.py` untouched |
| Pushed | **No** |
