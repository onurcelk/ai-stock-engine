# Family 10 — Stage 2: §2.10 clause 3, the correlation ceiling

**Written 2026-08-11. FEATURE-vs-FEATURE ONLY. No forward return, no target and
no outcome column was read; no sign was fitted; the sealed exam was not opened;
no family budget slot was spent.** Stage 1 (`reports/FAMILY10_STAGE1_PANEL.md`)
was committed at `cc2613b` before this stage began.

Reproduce: `./venv/Scripts/python.exe -W ignore -m alpha.family10_ceiling`

> ## Stage 2 verdict: **PASS**
>
> Against ceilings frozen in `alpha/V3_PREREGISTRATION.md` §2.1 **before Family 1
> ran**: the adverse-event dummy's mean |ρ| is **0.0437 vs 12-1 momentum**
> (ceiling 0.30), **0.0432 vs B3** (ceiling 0.30, the strict reading) and at most
> **0.0458 against any of the 34 research inputs** (ceiling 0.50). No column
> reaches a *sixth* of its ceiling. The sparsity-robust disclosure agrees: the
> strongest dependence anywhere is a rank-biserial of **+0.152 against 20-day
> realised volatility**, which is reported rather than waved away.

---

## 1. The threshold, and where it came from

| | ceiling | source |
|---|---|---|
| vs `z__ret_12_1` | **≤ 0.30** | `alpha/V3_PREREGISTRATION.md` §2.1 |
| vs **B3** (`b3_regime_switched`) | **≤ 0.30** | held to the *momentum* ceiling, not the input one |
| vs each of the 34 research inputs | **≤ 0.50** | `alpha/V3_FAMILY2_PREREGISTRATION.md` §8, carried unchanged |

B3 is not a member of the 34-column set, so the pilot had to choose which
ceiling binds it. It is **regime-switched 12-1 momentum**, so it is held to the
tighter of the two. That choice was made and written down before the number was
computed, and it is the strictest available reading.

Metric: **per-cutoff Spearman**, identical to
`alpha/v3_build_insider.py::per_cutoff_spearman` — same minimum cross-section of
50, same requirement that both columns vary. Family 1 and Family 2 were judged
on this function; Family 10 is judged on the same one.

## 2. The representation, fixed before measuring

```
adverse_8k_event(T, symbol) = 1  iff the issuer had an eligible adverse event
                                    whose information session falls in the 5
                                    sessions ending at cutoff T
```

The grid is spaced 5 sessions apart and the horizon is 5, so the windows
**partition** the calendar: every session belongs to exactly one cutoff, with no
gap and no double count. A test walks every session of a synthetic calendar and
asserts the dummy fires exactly once.

Nothing in the mapping can see past *T*. The information session is already the
first session on which `alpha/filings.py`'s door opens, so a dummy set at *T* is
set from filings accepted strictly before *T*'s close.

Item-level one-hots were available as redundancy diagnostics and were **not**
promoted to anything: no weight was fitted, no encoding consulted a target.

## 3. Contamination check — and a correction recorded rather than quietly fixed

**A first pass of this stage used `panel["development"]`, which is the older V1
twelve-date split and does *not* exclude the 72 sealed V2.1 exam cutoffs.** It
measured on 484 cutoffs, 72 of which were the exam's. The run was
feature-vs-feature so no outcome was read and nothing about the exam's answers
was learned — but it inspected cutoffs that `CLAUDE.md` §6.1 reserves, and
`alpha/v3_build_insider.py` asserts against exactly this for exactly this
reason.

Corrected before any result was recorded: the split is now
`examset.load().development` — **316 cutoffs** — and `examset.load().cutoffs` —
the 72 sealed ones — are asserted absent. The published numbers below are the
corrected run. The superseded 484-cutoff numbers were materially the same
(mean |ρ| 0.0440 vs 12-1, 0.0435 vs B3), which is stated so that nobody has to
wonder whether the correction moved the verdict. It did not.

| | |
|---|---|
| Development cutoffs | **316** |
| Sealed exam cutoffs present | **0** |
| Exam digest | `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, never opened |
| Panel rows | 143,675 |

Outcome columns are dropped **by name** from the panel before anything is
computed, and their absence is asserted in code rather than promised in a
docstring (`_feature_frame`).

## 4. Prevalence and sparsity, stated before the numbers

| | |
|---|---|
| Events assigned to a development cutoff | **984** of 1,682 |
| (cutoff, symbol) event cells on the panel | **853** |
| Prevalence per cutoff | mean **0.59%**, median 0.49%, max 1.90% |
| Event names per cutoff | mean **2.70**, median 2, max 8 |
| Cutoffs with no event at all | 23 of 316 |

**A Spearman correlation between a 0.6%-prevalence indicator and a continuous
feature is bounded well below 1 by construction.** A small value is therefore
partly mechanical and cannot on its own be read as independence. The charter's
metric still decides the gate — it is what was frozen, and inventing a
replacement after seeing that sparsity flatters the family would be exactly the
retrofit the protocol exists to prevent.

What is added instead is a statistic that can only make the family look **more**
dependent: the **rank-biserial correlation** (2·AUC−1) of each feature's
within-cutoff percentile rank between event and non-event names. It is a
location shift, not a co-movement, so its scale does not shrink as events get
rarer. A test demonstrates the contrast directly: on a 2-of-200 dummy, Spearman
reads < 0.2 where the rank-biserial reads > 0.9.

## 5. Results

### 5.1 The two ceilings that matter

| | mean ρ | **mean \|ρ\|** | p95 \|ρ\| | max \|ρ\| | n | ceiling | |
|---|---:|---:|---:|---:|---:|---:|---|
| `z__ret_12_1` | −0.0081 | **0.0437** | 0.0944 | 0.166 | 293 | 0.30 | **PASS** |
| `b3_rank` | −0.0037 | **0.0432** | 0.0937 | 0.163 | 293 | 0.30 | **PASS** |

Both sit at **one seventh** of their ceiling.

Rank-biserial disclosure:

| | event names sit at percentile | non-event names | rank-biserial |
|---|---:|---:|---:|
| 12-1 momentum | **0.4766** | 0.5012 | **−0.047** |
| B3 | **0.4905** | 0.5012 | **−0.019** |

**The sign is economically coherent and was not chosen.** Adverse 8-K events
land slightly more often in names that have already underperformed — 2.5
percentiles below the median on 12-1 momentum. That is a mild negative tilt on
the incumbent, which is the strongest available argument that the family carries
something B3 does not already hold: it is not a repackaging of momentum, and
what overlap exists points the same way the hypothesis does rather than
against it.

### 5.2 Against the 34-column research set

Of the 34 inputs, **8 are stock-level** (`z__…`) and **26 are cutoff-constant**
context — market state, VIX, breadth, regime dummies. A cutoff-constant column
has no within-cutoff variance, so no cross-sectional correlation with it exists
to measure. That is reported rather than hidden, exactly as
`alpha/v3_ceiling.py` reported it for Family 1.

| column | mean \|ρ\| | mean ρ | rank-biserial |
|---|---:|---:|---:|
| `z__sma200_dist` | **0.0458** | −0.0059 | −0.041 |
| `z__ret_5d` | 0.0444 | −0.0031 | −0.010 |
| `z__rvol_60d` | 0.0444 | +0.0189 | **+0.140** |
| `z__rvol_20d` | 0.0436 | +0.0200 | **+0.152** |
| `z__overnight_mean_20d` | 0.0421 | +0.0024 | +0.026 |
| `z__intraday_mean_20d` | 0.0408 | +0.0002 | +0.007 |
| `z__ret_20d` | 0.0404 | −0.0011 | +0.000 |
| `z__overnight_share_60d` | 0.0401 | −0.0052 | −0.026 |

**Highest of all measurable columns: 0.0458, against a ceiling of 0.50. Zero
breaches.**

### 5.3 The one dependence worth naming

The rank-biserial disclosure finds something the Spearman column does not
resolve: **adverse-event names sit at the 57th percentile of 20-day realised
volatility** against the 50th for everyone else (+0.152), and similarly on the
60-day measure (+0.140). Companies that terminate agreements, write down assets
and receive delisting notices are more volatile than average *before* they do it.

This is a real property of the population and it is recorded here, before any
outcome is seen, so that it is read later as a known feature of the design
rather than discovered as a result:

* it does **not** breach clause 3 — the charter's metric puts it at 0.044
  against a 0.50 ceiling, and even the disclosure metric is 0.15;
* volatility is not the incumbent. B3 is momentum, and the family's overlap with
  B3 is −0.019;
* but any later stage that finds an effect must consider whether it is an
  *event* effect or a *high-volatility-name* effect. A pre-registration is
  the place to fix that comparison in advance, and §6 below flags it as a
  required clause rather than leaving it to a post-hoc control.

## 6. A second survivorship channel, measured here because Stage 2 exposed it

Index membership is necessary but not sufficient for a name to be in the
research panel: `alpha/universe.py` also requires bars on disk, 252 sessions of
history, $3M median dollar volume and a $3 price. A historically eligible issuer
whose bars Yahoo no longer serves is in the membership set and **not** in the
panel — `alpha/membership.py`'s own disclosed limit 4.

| | |
|---|---|
| Events assigned to a development cutoff | **984** |
| …on a name the research panel carries | **850 (86.4%)** |
| …lost to priceability / liquidity | **134 (13.6%)** |

And the loss is concentrated the same way Stage 1's was:

| item | lost | | item | lost |
|---|---:|---|---|---:|
| **3.01 delisting** | **47.8%** | | 2.06 impairments | 15.7% |
| **1.03 bankruptcy** | **33.3%** | | 1.02 termination | 12.4% |
| **4.02 non-reliance** | **25.0%** | | **3.02 dilution** | **11.7%** |
| 2.04 acceleration | 20.5% | | 2.05 exit costs | 16.3% |

**This is the same bias as Stage 1's, arriving through a different door.** Stage
1 repaired the *identity* channel: dead issuers are now retained. This channel
is the *pricing* one, and it cannot be repaired from free data — a company whose
bars no longer exist cannot have a forward return computed for it, so no study
on this cache can use those observations however well they are identified.

It is **not** fatal, and the reason is specific: it costs 13.6% of events
overall and it is disclosed, whereas the identity channel would have cost 42% of
the delisting item silently. But it is a real ceiling on this family's evidence
about its most severe items, it must be carried into the power gate, and it must
appear in the pre-registration as a known limit rather than as an explanation
offered after a null.

## 7. Stage 2 gate

```text
FAMILY10 STAGE 2: PASS — INDEPENDENCE
```

| | ceiling | measured | |
|---|---|---|---|
| vs `z__ret_12_1` | ≤ 0.30 | **0.0437** | PASS |
| vs B3 | ≤ 0.30 | **0.0432** | PASS |
| vs each of the 34 inputs | ≤ 0.50 | **0.0458** worst | PASS, 0 breaches |

**Family slot spent: NO.** Stage 3 (block structure and the power gate) may
proceed.

## 8. Artefacts

| file | content |
|---|---|
| `alpha/family10_ceiling.py` | the clause-3 measurement, the outcome-column guard, the sparsity disclosure |
| `alpha/out/family10_ceiling.json` | every number quoted above |
| `app/tests/test_family10_ceiling.py` | 19 tests: the guard, the window partition, the two statistics |
