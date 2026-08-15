# V5 Phase 6 — Regime-Aware Evaluation: admissibility audit

**Verdict: `PHASE 6 VERDICT: INADMISSIBLE AS WRITTEN`.**

Phase 6 is not entered. No regime was constructed, no performance was split, no
accuracy was computed, and `validation/out/calls.csv` was not opened. This
document is committed **before** any Phase 6 measurement and before any regime
construction code exists, per CLAUDE.md §5.2.

| | |
|---|---|
| Requested | "start phase 6" — programme owner, 2026-08-14 |
| Roadmap ACTIVE PHASE at time of request | **Phase 9 — Data Gap Analysis**, taken deliberately out of order ahead of Phases 6–8 (`V5_ADAPTIVE_PREDICTION_ROADMAP.md` §3) |
| Outcomes read | **None.** Frozen *reports* were quoted; no outcome file was opened |
| Prediction-side data read | `validation/out/predictions.json` — cutoff dates only (§3.3) |
| Budget | No information-family slot spent. Nothing trained, no symbol or cutoff added |
| Exam | Sealed. Not accessed |

---

## 1. What Phase 6 asks

From `V5_ADAPTIVE_PREDICTION_ROADMAP.md`:

> **Goal.** Determine whether model skill genuinely depends on market environment.
>
> **Tasks.** Define a small number of regime hypotheses · Freeze regime
> construction before testing model-performance interaction · Measure model
> performance by regime · Require adequate sample size · Reject regime
> conditioning if it adds no robust information.
>
> **STOP / GO Gate.** Only validated regime effects may influence ensemble
> weights or model selection.

Three independent findings below each block entry. They are separable: fixing
any one leaves the other two standing.

## 2. Ground 1 — the question was already asked, on the only record that can answer it

### 2.1 There is exactly one performance record

Phase 6 must split *model performance* by regime, so it needs a body of scored
forecasts. This repository has one, and only one.

`app/forecast_ledger.sqlite3` **does not exist.** The Phase 1 forecast ledger and
the Phase 2 outcome scoring were built and tested, but no live forecast has ever
been frozen into them, so they hold nothing to split. Verified by absence of the
file, not by inference.

That leaves the frozen PIT-1 record — `validation/out/calls.csv`, 12 cutoffs,
30 symbols — as the sole dataset Phase 6 could measure.

### 2.2 PIT-1 already ran this analysis on that record

`validation/REPORT.md`, under the heading **"Checked, no effect found"**, quoted
verbatim and not recomputed:

> **Volatility regime.** Accuracy by pre-cutoff 60-day volatility tercile is
> flat for the consensus: calm 54.5%, middling 53.3%, turbulent 52.3%. It does
> not degrade in turbulence — it does not do much of anything in any regime.
> (The turtle agent *does* degrade: −0.27% / −1.74% / −2.79% per week by tercile.)

> **Market direction.** Consensus accuracy by what SPY did over the same week:
> market fell >1% → 50.0% (n = 26); flat → 65.7% (n = 35); rose >1% → 49.3%
> (n = 73). Best in quiet markets, no better than chance in either trend. It
> did **not** fail specifically during the drawdowns.

That is Phase 6's third task — *measure model performance by regime* — already
executed on Phase 6's only available dataset, with a pre-cutoff PIT-safe regime
construction (60-day volatility tercile), and filed as a null.

PIT-1 is **CLOSED**.

### 2.3 Why a different regime variable does not make it a new question

The obvious move is to keep the record and change the regime construction —
trend state instead of volatility, drawdown state, dispersion, breadth. That is
the move the programme's standing exclusions forbid. `ROADMAP.md`, *"The rule
that mattered most, and still binds"*:

> `alpha/PREREGISTRATION.md` fixed seven numeric criteria in advance — [...]
> **no regime collapse**, and ≥ 50 independent cutoffs. It also listed, in
> advance, the moves ruled out if the result were disappointing: no rescue
> features, no re-running the exam dates, no relaxed thresholds, no switching
> the headline metric.
>
> Those exclusions did not lapse when the programmes closed — they are the
> reason a closed entry cannot be reopened with a larger model, a different
> learner, another horizon or **one more carrier**.

Re-splitting a closed null on a fresh regime variable is one more carrier. It is
also the specific error `alpha/V5_ABSTENTION_PREREGISTRATION.md` §8 named for
this exact record — *"a claim that may not be made after a null: that a
different gate, a different band count, or `confidence` instead of `coverage`
would have shown it. Re-banding after a null is mining."*

## 3. Ground 2 — regime conditioning is a rejected family and a disqualifier, not a promotion route

### 3.1 It was tested as a feature family and rejected

`reports/EXPERIMENT_REGISTRY.md` §2, quoted:

| ID | Study | Arm | Primary result | Resolution | Decision |
|---|---|---|---|---|---|
| `V2-E` | V2 | **+ regime/VIX/breadth (exploratory tier)** | IC +0.02381, CI [+0.00558, +0.04455] | 0.02194 vs A′ | **REJECT** |

The V2 architecture is ABANDONED (CLAUDE.md §1.3, production weight 0, action
HOLD). This does not by itself bar Phase 6 — V2-E tested regime as a
*cross-sectional feature*, whereas Phase 6 proposes regime as a *conditioning
variable on an existing model's skill*, and CLAUDE.md's own reasoning treats a
different target as a different research object. It is recorded because a Phase 6
that reported a regime effect would have to explain its relationship to V2-E,
and because the direction of the existing evidence is not neutral.

### 3.2 The programme already rules that regime concentration disqualifies

This is the harder problem, and it is internal to the roadmap.

`reports/EXPERIMENT_REGISTRY.md` applies roadmap §2.5 as a **disqualifier**, in
four separate places:

- §347 — *"Stability | halves, yearly, regime — concentration disqualifies (§2.5)"*
- §429 — *"vs-B1 advantage **+0.11317 in BEAR** against +0.00075 BULL — disqualifying concentration (§2.5)"*
- §643 — *"regimes BULL −0.00251, BEAR +0.00497, SIDEWAYS +0.00364, EX-BEAR −0.00182. **The only positive regime is the one §2.5 disqualifies**"*
- §827 — *"Regime-concentrated results are a disqualifier under roadmap §2.5 and **may not be restricted to in order to survive**."*

Set that against Phase 6's STOP/GO gate:

> Only validated regime effects may influence ensemble weights or model selection.

**These two rules point in opposite directions on the same evidence.** A finding
that skill is concentrated in one regime is, under §2.5, grounds to disqualify
the model; under the Phase 6 gate, grounds to condition ensemble weights on the
regime. A Phase 6 that ran without resolving this would be free to read whichever
rule its result happened to satisfy — which is exactly the latitude a
preregistration exists to remove.

**This is not Claude's to resolve.** It is a contradiction between two committed
programme rules and requires a programme-owner decision, recorded before any
regime measurement. Recorded here; not decided here.

## 4. Ground 3 — power, and the fact that there are not twelve independent regime draws

A regime is a property of a *date*, not of a symbol-row. So a regime contrast is
a **between-cluster** comparison and its effective sample size is the number of
independent cutoffs — never the row count. Clustering by cutoff is mandatory
throughout this programme (`alpha/V5_ABSTENTION_PREREGISTRATION.md` §4:
*"by cutoff date, always. 30 symbols read on one day are one draw"*).

### 4.1 The best-case contrast on this record is already 3.9× too coarse

ABS-1 measured the resolution of this record directly, and its primary contrast
had **12 cutoff dates on each side** — the most favourable geometry the record
can offer:

| | |
|---|---|
| `D − B` clustered half-width | 20.39 pp |
| `D − B` MDE at 80% power | **29.15 pp** |
| Pre-registered threshold | 7.5 pp |

A regime split cannot improve on that. It partitions the same 12 dates into two
or three arms, so each arm holds a fraction of the dates the ABS-1 contrast had
on each side. The direction of the change is certain even though its magnitude is
not computed here.

**No regime MDE is asserted in this document.** Under CLAUDE.md §7.3 and §3.2 a
number of that kind may only appear from a gate computation committed before it
is run. If the owner wants the figure, §6(a) below is how to get it honestly.

### 4.2 Twelve dates are fewer than twelve regime draws

Computed from `validation/out/predictions.json` cutoff dates only — no outcome,
no bar, no return. This is the prediction side of the two-process separation.

```text
2022-03-08    gap    —
2022-10-10    gap  216 d
2024-08-13    gap  673 d
2024-09-05    gap   23 d   ←
2024-12-10    gap   96 d
2025-03-27    gap  107 d
2025-06-23    gap   88 d
2025-11-28    gap  158 d
2026-02-06    gap   70 d
2026-05-07    gap   90 d
2026-07-07    gap   61 d
2026-07-24    gap   17 d   ←
```

Six of the eleven adjacent gaps are ≤ 90 days. Two are ≤ 23 days. A regime built
on a 60-day trailing window — the construction PIT-1 used, and the natural one
for realised volatility, trend or drawdown state — reads **overlapping data** at
those spacings: the pairs 17 and 23 days apart share roughly two-thirds and
three-fifths of their estimation window respectively, and will almost always be
assigned the same regime for that reason rather than as independent evidence.

The last five cutoffs span 169 days in total. Four of the twelve are the
recency-anchored *named* cutoffs (`2 weeks / 1 month / 3 months / 6 months ago`,
per `cutoff_kind`), which is why they clump.

So the regime partition is not 12 draws split into arms. It is materially fewer,
and the shortfall is worst precisely where the record is densest.

Against this, `ROADMAP.md`'s own preregistered criterion asked for **"no regime
collapse, and ≥ 50 independent cutoffs."** Phase 6 on this record has at most 12
and in effect fewer.

## 5. What this document does not conclude

- **It does not conclude that skill is regime-independent.** PIT-1 reported a
  null on two regime constructions; a null at this resolution is a statement
  about the instrument as much as about the engine. §4.1 is the reason.
- **It does not conclude that Phase 6 is wrong to exist.** The question is
  well-posed and would matter on a record that could resolve it.
- **It does not correct PIT-1 or any frozen record.** Nothing was appended to an
  append-only file by this audit. §3.2 records a contradiction between two live
  roadmap rules, which is a different thing from correcting a result.
- **It resolves nothing about the §2.5 conflict.** That is deferred to the owner
  by design.

## 6. Admissible options for the programme owner

**(a) Phase 6 reduced to a frozen regime construction + power gate, and stopped
there.** Define one regime hypothesis, commit the construction code before it is
run, assign the 12 cutoffs, and compute the between-cluster MDE from geometry
alone with `p = 0.5` — the ABS-1 method, reading no outcome. Publish the gate
result and stop. This produces the frozen regime artifact Phase 7 and Phase 10
would need regardless, costs one short session, opens no outcome file, and
cannot mine anything because the verdict rule is fixed before the split is seen.
It does **not** answer Phase 6's question; it establishes whether the question is
answerable here. §3.2 must still be resolved before any result could be acted on.

**(b) Defer Phase 6 and proceed to Phase 9 — Data Gap Analysis.** The roadmap's
recorded ACTIVE PHASE, and the standing Phase 4 §10.2(b) / Phase 5(a) §8
recommendation. Phase 6 strengthens the case for it rather than competing with
it: regime conditioning *multiplies* the resolution requirement — it asks the
same 12 draws to support two or three separate accuracy estimates instead of one.
If 12 cutoffs cannot resolve a 7.5 pp main effect, they cannot resolve an
interaction. Phase 9's gate — *"any new dataset must have a precise hypothesis
and measurable expected role"* — should then carry an explicit **independent-draw
count** requirement, anchored on `ROADMAP.md`'s own ≥ 50 cutoffs.

**(c) Resolve the §2.5 / Phase-6-gate contradiction as a documentation act.**
No measurement, no data touched. Free, and a prerequisite for (a) and for any
future Phase 6 on any record.

**Recommendation: (b), with (c) as a free prerequisite.** (a) is defensible and
cheap, but §4.1 says what it will most likely find, and the artifact it produces
is only useful once a record exists that could use it — which is (b)'s question.

## 7. Phase 6 task status

Marked against the roadmap's five tasks, reflecting what was and was not done.

- [ ] Define a small number of regime hypotheses — **not done.** Blocked at entry.
- [ ] Freeze regime construction before testing interaction — **not done.**
- [ ] Measure model performance by regime — **not done, and not attempted.**
- [x] Require adequate sample size — **done, and it is the finding.** §4.
- [ ] Reject regime conditioning if it adds no robust information — **not
      reached.** Nothing was measured, so nothing was rejected on evidence. The
      block above is an admissibility finding, not a null result.
