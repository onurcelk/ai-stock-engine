# V3 Pre-registration — Family 3: 13F institutional holdings

**Written 2026-08-09, before any Family 3 correlation, IC, spread or arm was computed.**
Fixed on commit. Not edited after a result exists; corrections are appended, dated, and
leave the original wording visible.

Family 3 of the three frozen in `reports/INFORMATION_AUDIT.md` §5 — the **reserve** slot.
**This spends budget slot 3 of 3 (§21). It is the last slot. There is no fourth family.**

> ## Who fixed this design, stated plainly because it differs from Family 2
>
> For Family 2 the account holder fixed the six open design elements and
> `FAMILY2_ELIGIBILITY.md` refused to invent them. **No Family 3 design was ever
> specified**, and the account holder's instruction was to proceed and run the test. The
> construction in §1–§5 was therefore **fixed by the executing session** under the §2.3
> mandate to use *the simplest possible version of the new information source*, and
> **committed before any measurement was taken**.
>
> **No alternative construction was built, measured, compared or ranked.** Exactly one
> feature exists. If that is not the intended delegation, the correct remedy is to stop
> now — not to run a second version afterwards, which would be a Family 3′ and is barred.

> ## The audit's standing warning, reproduced rather than quietly bypassed
>
> `INFORMATION_AUDIT.md` §5 recorded, before any family ran: *"It is recorded as the
> reserve slot precisely so that a disappointing Family 1 or 2 does not become an argument
> for inventing a fourth family. If Families 1 and 2 both fail, the correct reading is
> likely that the formulation is wrong, and §21 requires the programme to say so rather
> than spend slot 3 as consolation."*
>
> Families 1 and 2 have both failed. The account holder was shown this warning and
> instructed that Family 3 run anyway. **It is reproduced here so the result is read
> against a prior that was set in advance and not revised after two nulls.**

---

## 1. The hypothesis, stated so it can fail

> **The quarter-over-quarter change in aggregate institutional share holdings, timestamped
> at the filing date that made it knowable, contains incremental cross-sectional
> predictive information over 12-1 momentum and over the B3 regime rule — of a size this
> history can resolve.**

**What would falsify it:** the decisive contrast in §8 fails to clear its threshold. Then
Family 3 is REJECTED, spends slot 3, and **the family-testing programme ends** under §21 —
it is not re-tested with a larger model, another learner, another target, another horizon,
another holdings statistic, or "one more carrier" (§2.9, §21).

## 2. Feature construction — FROZEN

**`inst_holdings_change`**, one number per (cutoff, issuer).

Let `S(i, Q)` be the **total shares of issuer *i* reported held at calendar quarter-end
*Q***, summed across every 13F filer, counting only filings admissible at the cutoff (§4).

> **`inst_holdings_change(i, T) = S(i, Q1) / S(i, Q0) − 1`**
>
> where **Q1** is the most recent quarter-end whose 13F deadline has passed as of *T*, and
> **Q0** is the quarter-end immediately before Q1.

| Element | Decision |
|---|---|
| Instrument | **common stock only.** `SSHPRNAMTTYPE == 'SH'`; every `PUTCALL` row is an option and is excluded |
| Aggregation | **plain sum of shares across all filers.** No filer weighting, no size weighting, no concentration statistic |
| Normalisation | **none needed — the ratio is already scale-free.** See §2.1 |
| Transform | **none.** No winsorisation, no log, no nonlinearity |
| Forms | `13F-HR` and `13F-HR/A` |

### 2.1 Why a ratio, and not a share of shares outstanding

The economically natural denominator is shares outstanding, giving *institutional
ownership as a fraction of the company*. **It is deliberately not used.** Family 2 measured
that `dei:EntityCommonStockSharesOutstanding` carries placeholder values for a handful of
filers — FOX's only such fact is literally `1.0` shares — which put 105 rows above an
impossible 100% (`FAMILY2_ADMISSIBILITY.md` §6).

`S(Q1)/S(Q0) − 1` needs **no external denominator at all**: it is the percentage change in
institutions' aggregate position, scale-free by construction, and immune to that defect.
It is also the simpler of the two, which is what §2.3 asks for.

**Recorded in advance, so it is not discovered later and treated as a finding:** a name
with a very small `S(Q0)` produces a very large ratio. Both arms consume the feature as a
**within-cutoff rank**, so such a name can only be placed at the top of the ranking, not by
an unbounded amount.

## 3. The 45-day deadline gate — FROZEN

A quarter *Q* is usable at cutoff *T* only if **T > Q_end + 45 calendar days**, the
statutory 13F deadline.

**Why this is a correctness requirement and not a tuning knob:** the set of filers who have
reported for a quarter grows as filings arrive. Comparing a freshly-opened quarter against
a settled one would measure *how much of the quarter has been filed*, not how holdings
changed. The gate makes both Q1 and Q0 deadline-passed. **The residual asymmetry — Q0 is
always more completely reported than Q1 — is a known property of the design, largely common
across the cross-section at a given cutoff, and therefore largely cancelled by the
within-cutoff rank transform.** It is not engineered around.

**The cost, stated rather than hidden:** the information is **45–135 days stale at every
cutoff**. `INFORMATION_AUDIT.md` §2.3 identified this as structural and as the reason
Family 3 is the reserve slot. Nothing in this design removes it.

## 4. Availability — FROZEN, and deliberately stricter than Families 1 and 2

> **A 13F filing is admissible at cutoff *T* only if its `FILING_DATE` is strictly before
> *T*.**

The bulk data sets carry `FILING_DATE` but **no acceptance timestamp**, and the 13F filer
population is tens of thousands of institutions whose `submissions.zip` this project does
not hold. Rather than approximate an acceptance time — which §2.1 forbids — the door is
made **stricter than the acceptance-time door** used for Families 1 and 2: a filing dated
*T* is not usable at *T*.

**This can only ever delay information, never advance it, so it cannot leak.** It costs at
most one session against a 45–135 day staleness.

**Amendments** are resolved exactly as `alpha/filings.py` resolves restatements: per
(filer, period), **the latest filing admissible at *T* wins**; earlier ones are superseded;
later ones do not exist yet.

## 5. Missing data — FROZEN

> If `S(i, Q1)` or `S(i, Q0)` is unavailable, or `S(i, Q0)` is zero, the feature is
> **NaN**. Nothing is imputed, filled, or replaced.

Unlike Family 2's absent insider — where "nobody bought" was a true and informative zero —
a large-cap with no reported institutional holdings is **missing data, not news**. NaN
names are excluded from that cutoff's ranking and are never filled to the median, which
would be a silent bet.

## 6. Primary prediction horizon — FROZEN

> **`alpha_5d`, 5 sessions.**

Carried unchanged from Families 1 and 2 under `TARGET_DESIGN.md` §4.2 as written. **No
second horizon is run, and none may be added later** (§2.4). The panel already carries this
target, so no rebuild occurs and §0.4's warning about overwriting frozen evidence is not
engaged.

**The honest tension, pre-recorded:** the information is 45–135 days stale, and 5D is the
shortest permitted horizon. If Family 3 returns a null, *"the horizon was too short for
information this stale"* is a live diagnosis — and §2.9/§21 mean it may **not** then be
re-tested at 10D or 20D. That is the price of the three-slot budget and it is accepted
knowingly.

## 7. Simplicity — FROZEN

§2–§5 **is** the primary Family 3 arm and is the "simplest possible version of the new
information source" that §2.3 requires as a mandatory baseline.

**Prohibited in this study:** machine learning of any kind, filer weighting or filer
selection (no "smart money" subset), holdings concentration or breadth statistics, multiple
lookbacks, option positions, sales/decrease-only variants, post-hoc transformations, and
any second horizon.

---

## 8. Baselines, arms, metrics and the decision rule — inherited, and fixed here

| | |
|---|---|
| Baselines (§2.3) | **B3** (the incumbent), B1 12-1 momentum, B2 5d reversal, and the raw feature alone |
| Arms | **two**: **Arm 0** = within-cutoff rank of the feature, sign **+1 by economic prior** (institutions accumulating is good news); **Arm 1** = `rank(b3) + λ·(rank(feature) − 0.5)` |
| λ | **0.25**, carried unchanged from Families 1 and 2. **Fixed, and not scanned as an arm** |
| Primary metric | paired per-cutoff IC difference, **Arm 1 − B3** |
| Interval | moving-block bootstrap, `alpha/stats.py`, `BLOCK_LENGTH = 4`, 10,000 draws |
| Multiplicity | **Holm–Bonferroni** across the two arms' primary contrasts (§6.4) |
| §2.10 clause-3 ceilings | **≤ 0.30** mean \|ρ\| vs `z__ret_12_1`; **≤ 0.50** vs each of the 34 stock-level inputs — carried unchanged from Families 1 and 2, **fixed here before the correlation is read** |
| Noise control (§2.11) | **30 paired** within-cutoff permutations; fails if median > +0.002 or >10% of draws clear +0.010 |
| Cost model | 5 bps, net-of-cost spread advantage reported from the first measurement |

### 8.1 The CONTINUE rule — `V3_PREREGISTRATION.md` §6.3 **as amended by A1**

All four required:

1. **Arm 1 − B3 ≥ +0.010** in mean paired IC, **and**
2. its **95% block-bootstrap CI excludes zero on the favourable side** — **Amendment A1,
   commit `830aafc`**. Implemented as **`bool(lo > 0.0)`**. An interval lying entirely
   *below* zero is a **FAIL** of this criterion, **and**
3. **breadth > 0.50** and **both chronological halves positive**, **and**
4. the effect is **not concentrated in one regime bucket** — it must survive with
   `BEAR_TREND` removed. Concentration disqualifies; it does not caveat.

**Anything less is REJECT.** The direction-blind predicate `bool(lo > 0.0 or hi < 0.0)`
used by `v3_family1.py` and `v3_family2.py` **must not be copied**; those modules are left
unmodified so their recorded results stay reproducible.

## 9. The §2.6 power gate — computed before implementation

`alpha/out/f13_gate.json`, run 2026-08-09 **before** any holdings were parsed into a
feature. Evaluated across a **range** of coverages so the verdict cannot depend on a
number that was not yet measured:

| coverage | calibrated half-width | vs MDE +0.007 |
|---|---|---|
| 0.80 | 0.00352 | 2.0× inside |
| 0.90 | 0.00259 | 2.7× inside |
| 1.00 | 0.00158 | 4.4× inside |

**Verdict: PASS at every level in the range.** MDE **+0.007**, carried unchanged and
**not re-derived** — re-deriving an MDE for a family about to be tested is how an MDE gets
softened.

## 10. Prohibitions

Carried from §0.1 and the roadmap. The exam is never opened, scored or inspected —
`b55e065f4c9f9173`. Production weight is not raised and `alpha/adapter.py` is not modified.
No threshold is lowered, no benchmark swapped, no B3 modified. No λ point, rung or control
is promoted to an arm. No result is restricted to a regime, sector or year to make it
survive. No cutoff is dropped because it is inconvenient. The feature sign is **not**
flipped after seeing a result. Development numbers are never reported as alpha. Nothing is
pushed.

> **If Family 3 is rejected, no Family 3′ is opened and no fourth family is opened.**
> §21 requires the programme to conclude that the *formulation* is wrong and to stop,
> with a diagnosis of which element failed: information, target, horizon, point-in-time
> quality, coverage, economic significance, or power.
