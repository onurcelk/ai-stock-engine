# V5 Phase 4 — Baseline + Challenger Evaluation

**Date:** 2026-08-14
**Phase:** PHASE 4 — Baseline + Challenger Evaluation
**Decision:** STOP for every candidate on route 1. CONTINUE to Phase 5 on route 2
with exactly one object, under a narrowed premise.
**Measurements performed by this phase:** none. See §2.
**Implementation:** none. No module was added or changed.

---

## 1. Result

**No candidate clears the Phase 4 STOP/GO gate on route 1 — "beats the baseline
with credible OOS evidence."** The gate is not close for any of them, and the
evidence that decides it was already frozen before this phase began.

The candidate set Phase 4 was asked to assemble is, after applying the
repository's own admissibility rules:

| Roadmap slot | Candidate | Standing |
|---|---|---|
| strongest simple baseline | `always_bullish` / `zero_return` | **the incumbents to beat** |
| strongest admissible rule-based model | `ensemble.ultimate` (and its 13 constituents) | measured, REJECTED against baseline |
| strongest admissible ML/neural candidate | `neural.lstm` | measured, REJECTED against baseline |
| strongest admissible RL candidate | **none exists** | all 19 agents PIT-INADMISSIBLE |
| justified new challengers | **zero** | see §8 |

Route 2 — *"adds complementary information that may justify ensemble testing"* —
survives for one object only, and not the one Phase 5 was written to weight.
See §9 and §10.

The single most consequential sentence in this phase is not a number. It is
that **Phase 5's premise is already contradicted by the frozen record**: an
adaptive ensemble reweights constituents whose individual and combined
directional value has been measured at or below a trivial baseline, and whose
one optional external component was demonstrated to change zero verdicts.
Phase 5 cannot be entered as written. §10 states what replaces it.

---

## 2. Why this phase measured nothing

Phase 4 was designed, in this session, as an 88-cutoff × 19-symbol
point-in-time evaluation of the production engine and three recurrent
architectures, routed through the Phase 1–3 ledger. Before any forecast was
frozen, that design was checked against CLAUDE.md §1.3 and found to be a
re-run of a closed programme.

**PIT-1** (`validation/`, run 2026-08-07) is registered in the append-only
`reports/EXPERIMENT_REGISTRY.md` §2 with decision **REJECT**, and in the Phase 3
registry as `closed.pit1_single_name`, status **REJECTED**. The overlap is
near-total:

| | PIT-1 | Phase 4 as designed |
|---|---|---|
| Object | `ultimate.evaluate` consensus, 3 rule agents, LSTM projection | identical |
| Harness | `validation.pit` truncation, freeze-then-score, two processes | identical |
| Baselines | always-long, no-change | identical (`always_bullish`, `zero_return`) |
| Statistics | clustered by cutoff date | identical |
| Neural config | LSTM, 30 epochs, 64 units, 1250 bars, 5-bar horizon | identical |
| Sample | 12 cutoffs × 30 symbols; 96 LSTM runs on 8 symbols | 88 cutoffs × 19 symbols |
| Learners | LSTM | LSTM + GRU + Vanilla RNN |

Under §1.3 the differences are the forbidden ones, not exculpatory ones. Adding
GRU and Vanilla RNN is *"a different learner"* applied to a rejected arm.
Raising 12 cutoffs to 88 is *"no repeated mining until something passes."*
Routing the same measurement through the Phase 1–3 ledger changes the
auditability of the record, not the scientific question being asked.

Two considerations were weighed on the other side and are recorded because they
are genuine:

1. **PIT-1 named this follow-up itself**, in its own conclusion, before its
   REJECT was registered: *"A stronger study would need many more cutoff dates
   (the binding constraint — adding symbols buys almost nothing)."* A
   pre-declared follow-up is not a post-hoc rescue, which is what §3.2 forbids.
2. **PIT-1 carried no pre-registered MDE.** The registry's own §5 template
   states that an entry whose `Resolution / MDE` line is empty is a *blocked*
   study that §2.6 forbids running. On that reading PIT-1's REJECT is a
   study-quality failure rather than a verdict on the engine.

Neither was decisive, for a reason that is independent of governance and is the
strongest argument in this section. **PIT-1 disclosed three residual
look-aheads** — adjusted prices, a universe assembled from today's cache, and
short intraday depth — and stated: *"all three would have to be fixed before a
positive result could be believed. They do not undermine the negative results
below."* More cutoffs repair power. They repair none of those three. A
higher-powered re-run of this harness can therefore return only (a) another
negative, or (b) a positive that the harness's own disclosure says cannot be
believed. Its expected information yield is close to zero at a cost of roughly
three hours of compute and a reopened closed programme.

Phase 3's completion note had already ruled on this in advance:
*"`closed.pit1_single_name` is the prior for single-name direction … Phase 4
must treat it as the prior, not as a fresh question."*

The conflict was flagged to the programme owner before any measurement, per
§1.3, and the decision was **synthesis, no re-measurement**. This report is that
synthesis. PIT-1's frozen numbers are quoted, never recomputed.

### 2.1 Exploratory work performed before the conflict was identified

Three probes ran while the design was being sized, and they are recorded rather
than omitted:

- one `ultimate.evaluate` call through `pit.fetcher` (AAPL, 2024-06-14) to time
  the engine;
- three `forecast.project` fits (AAPL, 2024-06-14, LSTM/GRU/Vanilla RNN) to
  time the neural path;
- two coverage probes over 6 symbols × 12 cutoffs reading `available`,
  `score`, `coverage`, `live` and `confidence` off the verdict objects.

**None of them read a realised return, an outcome, or any bar after its
cutoff.** They called the prediction side only. No forecast was frozen to a
ledger, no outcome was resolved, and no number from them is used as evidence
anywhere in this report. The one structural fact they established is recorded in
§7.3, and it involves no forward return at all.

---

## 3. Task 1 — The exact production target

Phase 4's first task is to state, without ambiguity, what the production system
claims to predict. Read off the code rather than the marketing.

**The production target is the close-to-close percentage price change of one
named symbol, from the last bar at or before the cutoff, over a fixed number of
bars at a fixed interval.**

Precisely, for horizon *h* with `bars_used` = *k* bars at `interval` *i*:

```
target(symbol, cutoff, h) = (close[t + k] / close[t] - 1) x 100
```

where `t` is the index of the last *i*-interval bar at or before the cutoff.

Three properties of this target are load-bearing and are stated because each
one has been the source of a misreading somewhere in the repository's history:

1. **It is an absolute return, not a relative or cross-sectional one.** It is
   not `alpha_5d`, not a market-relative return, and not a rank. The entire
   V2→V2.3 / V3 / V4 programme targeted a *cross-sectional* object; that work is
   therefore not evidence about this target, in either direction.
2. **A horizon is a bar count, not a calendar duration.** `1w` is 5 daily bars;
   `4h` is 4 hourly bars. `outcome_ledger.maturity_spec` reads both numbers off
   the frozen record rather than re-deriving them from the label, which is why a
   crypto symbol's "week" and an equity's "week" are different amounts of
   wall-clock time and neither is wrong.
3. **The three production horizons are `4h`, `1d`, `1w`** (`ultimate.HORIZONS`).
   There is no monthly or six-month production forecast. Any table showing one is
   showing what happens when a one-week call is held longer, which is a different
   quantity and must be labelled as one.

`ensemble.ultimate` and the three `neural.*` challengers both emit this target
as `return_pct`. The 10 technical sources and 3 rule agents do **not** — they
emit a unitless stance in [−1, 1], and only the sign of that stance is
comparable to the target. Phase 3 already fixed this distinction as
`score_class`, and §5 keeps it.

---

## 4. Task 2 — Metrics matching displayed app claims

The rule is that a metric earns its place by corresponding to something the
application actually puts on screen. Everything the app displays, and the metric
that scores it:

| Displayed (source) | The claim | Metric that scores it | Available? |
|---|---|---|---|
| Action per horizon: STRONG BUY / BUY / HOLD / SELL / STRONG SELL (`horizon_cards`) | this symbol will go up / down over this horizon | **directional accuracy** on non-HOLD calls, paired against `always_bullish` on identical rows | yes |
| Aggregate action + score `+/-NN` (`verdict_card`) | a stronger score is a better call | **accuracy and realised return by score band** | yes |
| `Confidence NN%` (`verdict_card`, `horizon_cards`) | a higher number means more reliable | **monotonicity of accuracy in the confidence band** | yes |
| `Expected +X.XX% against a typical Y.YY% move` (`horizon_cards`) | the size of the coming move | **MAE / RMSE vs `zero_return`; correlation of predicted with realised** | yes |
| `1-day target <price>` (`verdict_panel`) | where the price will be | **MAPE vs the no-change forecast** | yes |
| `Timeframes <alignment>` | horizons agree | no production claim of accuracy attaches — diagnostic | n/a |
| `N sources counted of M` | how much evidence stands behind the call | **coverage**, and accuracy conditional on coverage | yes |
| Per-source hit-rate chips | this source has been right X% of the time | **per-constituent directional hit rate** (`outcome_ledger.constituent_directional`) | yes |

Two metrics the roadmap's V5 objective lists as required outputs are
**structurally unavailable and must not be manufactured**:

- **Probability positive.** No registered model emits a calibrated
  `probability_positive`. Phase 1 kept the field, Phase 2 built the Brier and
  calibration columns, Phase 3 confirmed nothing fills them. **Confidence is not
  a probability** and no phase may substitute one for the other. Brier score,
  log loss and calibration error are therefore not computable for any current
  candidate — not "poor", *absent*.
- **Sector-relative outcome.** Unavailable pending a point-in-time sector map
  (Phase 9 candidate). Recorded as absent, not imputed.

### 4.1 The resolution rule

Per CLAUDE.md §6.4, no point estimate in this report appears without its
interval or half-width. Where PIT-1 reported an estimate without one, this
report says so rather than supplying a computed substitute.

---

## 5. The candidate set

Phase 4's rule is *"do not add large numbers of new models"* and its slot list
is followed literally. Candidates are drawn from the Phase 3 registry only, and
every one is checked with `assert_record_admissible`-equivalent reasoning before
it appears here.

| # | Candidate | Registry id | Status | `score_class` | Admissible metrics |
|---|---|---|---|---|---|
| B1 | zero return / no change | `zero_return` | baseline | — | MAE, RMSE, MAPE |
| B2 | always bullish | `always_bullish` | baseline | — | directional accuracy |
| C1 | production consensus | `ensemble.ultimate` | PRODUCTION | `RETURN_AND_DIRECTIONAL` | all five |
| C2 | LSTM forward projection | `neural.lstm` | CHALLENGER | `RETURN_AND_DIRECTIONAL` | all five |
| C3 | GRU forward projection | `neural.gru` | CHALLENGER | `RETURN_AND_DIRECTIONAL` | **never measured** |
| C4 | Vanilla RNN projection | `neural.vanilla_rnn` | CHALLENGER | `RETURN_AND_DIRECTIONAL` | **never measured** |
| D1–D10 | 10 technical sources | `technical.*` | PRODUCTION | `DIRECTIONAL_ONLY` | directional accuracy |
| D11–D13 | 3 rule agents | `rule_agent.*` | PRODUCTION | `DIRECTIONAL_ONLY` | directional accuracy |
| — | RL agents (19) | `rl.*` | EXPERIMENTAL | — | **inadmissible, see §5.1** |

C3 and C4 have never been measured on any point-in-time grid. That is recorded
as a gap in §8, and it is deliberately **not** filled by this phase: measuring
them is the "different learner on a rejected arm" that §1.3 forbids.

### 5.1 There is no admissible RL candidate

The roadmap reserves a slot for the *"strongest existing admissible RL
candidate."* Phase 3 established, and this phase confirms without re-testing,
that **the slot is empty**. All 19 trainable agents in `agents.REGISTRY` are
`PIT-INADMISSIBLE` for a structural reason rather than a measured one: `train()`
optimises over the whole series the agent was constructed with, and the trained
policy is then replayed from bar zero. None declares a `record_key`, so none can
appear in a frozen forecast at all.

This is recorded as an empty slot rather than filled with the least-bad
available agent. Reopening it means building a PIT-safe training protocol,
which is Phase 7 work.

### 5.2 What `closed.ams1_agent_meta` already forecloses

AMS-1 tested single-name 5-session direction from **agreement across agent
families** and was REJECTED, with the measured direction the *opposite* of the
hypothesis: P(up) is perfectly monotone downwards across consensus states. Any
Phase 5 weighting scheme keyed on cross-family agent agreement reopens that
result. It is named here so Phase 5 cannot reach for it as though it were
untried.

---

## 6. Tasks 3 and 4 — Identical PIT splits, and every candidate against baseline

**Not re-measured.** The evaluation exists, on identical splits, in PIT-1.

### 6.1 The splits

12 cutoffs × 30 symbols = 360 frozen predictions, plus 96 LSTM experiments on 8
symbols. Cutoffs: four named dates (6 months / 3 months / 1 month / 2 weeks
before the run) plus eight drawn at random with seed 20260807 from the window
where five years of prior history and a full six-month outcome both exist.
Predictions were frozen to disk before any outcome was read; scoring is a
separate process that never writes predictions. Intervals are **clustered by
cutoff date**, because 30 symbols read on one day are not 30 independent
observations.

C1 and D1–D13 share one grid exactly. C2 was run on a declared 8-symbol subset
of it (SPY, QQQ, AAPL, MSFT, NVDA, AMZN, TSLA, BTC-USD) at all 12 cutoffs, and
every comparison involving C2 is paired on those identical rows. So "identical
PIT splits" holds within each comparison, which is the property the task
requires.

### 6.2 Every candidate against the directional baseline

Paired against `always_bullish` on identical rows, one-week window, clustered by
cutoff date. Reproduced verbatim from `validation/REPORT.md` §15.

| Candidate | n | Accuracy | Always-long | Difference | 95% CI | p |
|---|---:|---:|---:|---:|---|---:|
| C1 consensus (aggregate) | 134 | 53.7% | 61.9% | **−8.2 pts** | [−28.1, +11.7] | 0.383 |
| C1 — 4 hours | 36 | 27.8% | 47.2% | **−19.4 pts** | [−63.6, +24.7] | 0.332 |
| C1 — 1 day | 95 | 50.5% | 54.7% | −4.2 pts | [−35.6, +27.2] | 0.774 |
| C1 — 1 week | 62 | 56.5% | 59.7% | −3.2 pts | [−19.0, +12.6] | 0.662 |
| D11 turtle | 325 | 44.6% | 59.1% | **−14.5 pts** | [−38.5, +9.6] | 0.212 |
| D12 MA crossover | 325 | 56.9% | 59.1% | −2.2 pts | [−16.9, +12.6] | 0.753 |
| D13 signal rolling | 325 | 50.2% | 59.1% | −8.9 pts | [−20.6, +2.7] | 0.121 |
| D11–13 combined | 325 | 50.2% | 59.1% | −8.9 pts | [−25.5, +7.6] | 0.260 |
| C2 LSTM | 96 | 59.4% | 64.6% | −5.2 pts | [−21.3, +10.8] | 0.490 |
| C1, megacap subset | 49 | 51.0% | 73.5% | **−22.4 pts** | **[−40.0, −4.9]** | **0.017** |

**Every candidate is below the baseline.** One difference is individually
significant, and it is negative.

### 6.3 An audit of the prior's own strongest claim

PIT-1 reads the unanimity as *"nine coin flips landing the same way is a
1-in-256 event."* **That figure overstates the evidence and this phase records
the correction rather than repeating it.** The nine systems are not
independent: they share the same 12 cutoff dates and largely the same 30
symbols, and C1 is a weighted function of D1–D13, so the consensus and its own
constituents cannot land independently. The correct reading is that the sign is
unanimous across nine *highly correlated* systems, which is much weaker than
1-in-256 and much stronger than nothing.

The direction of the overstatement matters for how it may be used. It weakens
the *positive* claim "we have shown these are worse than always-long." It does
not rescue any candidate, because no candidate's own interval comes near
clearing zero from above. The gate below is decided on the individual intervals,
not on the unanimity argument.

### 6.4 Every candidate against the level baseline

`zero_return` / no-change, one week. From `validation/REPORT.md` §13, §14 and §9.

| Candidate | n | MAPE | No-change MAPE | Beats no-change | corr(pred, realised) | Size ratio |
|---|---:|---:|---:|---:|---:|---:|
| C1 consensus | 321 | 5.592% | 5.590% | **38%** | **−0.011** | 0.12 |
| C1 — 4 hours | 211 | 2.534% | 2.512% | **4%** | −0.252 | 0.18 |
| C1 — 1 day | 318 | 2.821% | 2.818% | **14%** | +0.118 | 0.14 |
| C1 — 1 week | 316 | 5.583% | 5.555% | **9%** | +0.061 | 0.35 |
| C2 LSTM | 96 | **11.48%** | 3.77% | **23%** | **−0.073** | 3.29× |

Two distinct failure modes, and they are opposite:

- **C1 under-states by ~8×.** `expected_move_pct = score/100 × typical_move_pct`
  is arithmetically incapable of naming a large move: a score of 25 on a symbol
  whose typical weekly move is 3% yields a 0.75% forecast. Its median predicted
  move is 12–35% of the median realised move. A target sitting 0.3% from the
  current price inherits the no-change error almost exactly and then adds a
  biased tilt that loses more often than it wins.
- **C2 over-states by ~3.3×**, with a mean signed error of +6.50% and a single
  projection of **+69.2% over five trading days**.

Neither carries information about magnitude: the correlations are −0.011 and
−0.073.

### 6.5 Confidence

The app displays a 0–100 confidence and the implicit claim is that it tracks
reliability. From `validation/REPORT.md` §11, one-week window:

| Band | 0–10 | 10–20 | 20–30 | 30–50 | 50–70 | 70–90 | **90–100** |
|---|---:|---:|---:|---:|---:|---:|---:|
| n | 16 | 22 | 30 | 35 | 15 | 11 | **5** |
| Accuracy | 56.2% | 36.4% | 53.3% | 57.1% | 66.7% | 63.6% | **40.0%** |

There is a rising trend through the middle that **collapses at the top band,
where the system is most certain and least right — 2 of 5 at a stated 95%.**
The 1-day table has no monotone structure at all. Aggregated, calls at ≥50%
stated confidence were right 61.3% (n = 31) against a stated ~70%: overconfident,
and worst where it matters most.

The n values are small and the report states no interval on these bands. This
phase therefore records the confidence finding as **directional evidence of
miscalibration, not a resolved measurement.**

---

## 7. Task 5 — Single-name and cross-sectional metrics, separated

### 7.1 Single-name

Everything in §6 is single-name: an absolute directional and magnitude claim
about one symbol, which is exactly what the application displays. This is the
target defined in §3, and it is where every candidate fails.

### 7.2 Cross-sectional

**Never measured for this engine, and not measured here.** No candidate in §5
has been evaluated on whether its score *ranks* symbols within a cutoff date.

The repository does hold a large cross-sectional record — V2→V2.3, V3, V4, and
the B3 carrier — but that work targets `alpha_5d` on a point-in-time index
membership panel of ~465 names. It is **a different object and a different
target** and is not evidence about `ensemble.ultimate`'s ranking ability in
either direction. All of it is CLOSED.

The relevant precedent is not a result but a rule. Roadmap §9b, quoted in
`reports/SINGLE_NAME_PHASE1.md` §4: *"A signal that beats the cross-section but
not always-up is a portfolio-construction result, not a stock prediction, and
must be described as one."* If a future phase measures the ultimate engine
cross-sectionally, that rule binds the write-up in advance.

This is the one part of Phase 4's brief that is genuinely open. It is recorded
as an open question with a named constraint, and **not** opened here: it is a new
research object and needs its own preregistration, not a paragraph in a
synthesis report.

### 7.3 One structural fact about abstention

Recorded because it is a property of the code, established without reading any
forward return, and because Phase 5 depends on it.

**When the engine returns a neutral call, it is abstaining, not predicting
neutral.** In the coverage probe of §2.1, every neutral horizon verdict had
`coverage == 0` and *zero* live sources — the neutral output arises because no
source cleared significance, never because weighted sources cancelled out.
`expected_move_pct` is then exactly 0.0.

The consequence for scoring is mechanical and matters: a neutral forecast has
`predicted_return == 0`, which is *identical to the `zero_return` baseline*. On
every abstained row the candidate's MAE and the baseline's MAE are the same
number by construction. Pooling abstentions into an MAE comparison therefore
dilutes any real advantage toward zero and makes a candidate look neutral when
it has simply declined to speak.

PIT-1's frozen abstention rate is **74.3% HOLD**, with a direction named on only
40.5% of scoreable symbol-dates. Any future MAE or MAE-skill comparison on this
engine must report the abstained and spoken subsets separately, and must declare
that split before measuring.

---

## 8. Task 6 — Reject complexity with no incremental evidence

Three rejections, each on evidence that already exists.

**1. The neural challenger adds nothing to the consensus — as a count, not an
estimate.** Across 96 point-in-time experiments the LSTM was gated out of
**257 of 257** horizon-slots by `ModelEvidence`. Not one action and not one
score changed. "Consensus with the LSTM vs without" is **exactly 0**, and that
row carries no interval because it needs none.

The mechanism deserves recording as the study's one genuinely positive finding
about the architecture: `ModelEvidence` refuses to weight a forecast whose
walk-forward directional edge sits inside its own noise. The LSTM's walk-forward
accuracy averaged **49.9%**, and only **36 of 288 folds** beat the naive
no-change forecast. The gate fired correctly every time, using only information
available at prediction time — and when the projections were finally scored they
came in 5.2 points *behind* always-long. **The gate was right and the model was
useless, and the system knew it in advance.**

**2. GRU and Vanilla RNN are not measured, and are not to be measured as
Phase 4 work.** They are the same architecture family as C2 under a different
cell. Measuring them after C2 was rejected is "a different learner" on a
rejected arm (§1.3). They stay registered as CHALLENGER with **no evidence**,
which is the honest standing — not "promising", not "rejected".

**3. Complexity is not the binding constraint.** Across the whole record the
half-width exceeds the point estimate in nearly every comparison. PIT-1's
consensus interval spans 40.6% to 66.8%. `SINGLE_NAME_PHASE1.md` §3F measured
the instrument's resolution directly and found that an unpaired accuracy claim
needs to clear **2.6 percentage points** to escape its own noise. The repository
has failed to demonstrate skill many times; it has rarely been in a position to
detect it. Adding a learner does not address that, and §2 explains why adding
cutoffs to *this* harness does not either.

---

## 9. The STOP / GO gate, applied

> **Gate.** Proceed only with candidates that either (1) beat the baseline with
> credible OOS evidence, or (2) add complementary information that may justify
> ensemble testing.

| Candidate | Route 1 | Route 2 | Verdict |
|---|---|---|---|
| C1 `ensemble.ultimate` | **FAIL** — −8.2 pts vs always-long, and below every trivial rule tested including a seeded coin flip | **FAIL as a source of complementary information**, because it *is* the combination Phase 5 would build | **remains production incumbent; no promotion, no new standing** |
| C2 `neural.lstm` | **FAIL** — −5.2 pts vs always-long; price path 3× worse than no-change | **FAIL, measured as a count** — 257/257 gated, 0 verdicts changed | **STOP** |
| C3 `neural.gru` | no evidence | no evidence | **STOP — not eligible; measuring it reopens §1.3** |
| C4 `neural.vanilla_rnn` | no evidence | no evidence | **STOP — not eligible; measuring it reopens §1.3** |
| D1–D10 technical | not individually measured vs baseline | see §10.2 | **diagnostic only; no candidate standing** |
| D11–D13 rule agents | **FAIL** — −14.5 / −2.2 / −8.9 pts | see §10.2 | **STOP as standalone candidates** |
| RL agents | **inadmissible** | inadmissible | **STOP — Phase 7 question** |

**No candidate is promoted. No candidate is demoted below its registered status.
No production weight changes. `assert_not_reopened` remains true of all six
closed programmes.**

The one thing that passes anything in this phase is the abstention machinery,
and it is not a candidate — it is a property of the incumbent. It said HOLD on
74.3% of symbol-dates, and on the 25.7% where it spoke its edge over a trivial
rule was zero. Its refusal to speak is calibrated even though its confidence is
not. That argues for keeping the significance gates exactly where they are, and
it is the finding Phase 11 should carry forward.

---

## 10. Notes for Phase 5

### 10.1 Phase 5 as written cannot be entered

Phase 5 is *"Adaptive Ensemble — allow model influence to depend on demonstrated
OOS usefulness."* It presupposes a set of constituents with differing,
measurable OOS usefulness to reallocate weight between. The frozen record does
not supply one:

- the constituents' combined directional accuracy is **50.2%** (n = 325), and
  −8.9 points against always-long;
- the best single agent, MA crossover at 56.9%, is **−2.2 pts [−16.9, +12.6]**
  against always-long and −0.16 pts/week against simply holding — it is long 55%
  of the time in a market that rose;
- the worst, turtle at 44.6%, is the *fading* variant, short most of the time in
  the same rising market. **Both are measuring the drift, in opposite
  directions**, which is the signature of components that carry no independent
  information to weight;
- the one optional external component changed **zero** verdicts;
- weighting by cross-family agent agreement is foreclosed by
  `closed.ams1_agent_meta`, whose measured direction was the reverse of the
  hypothesis.

Reweighting components that are collectively indistinguishable from the drift
produces a different number, not a better forecast. Proceeding to Phase 5 as
written would be architecture escalation ahead of information evidence.

### 10.2 What Phase 5 could legitimately be

Two candidate reformulations, neither of which reopens a closed programme.
**Both require a preregistration committed before any measurement, and the
choice between them is the programme owner's, not Phase 5's.**

**(a) Weight-to-abstain rather than weight-to-predict.** The single validated
property of this system is that its gating is calibrated. The open question is
not "which constituent deserves more weight" but "does the existing coverage
signal identify, in advance, the symbol-dates where the engine's calls are worth
acting on?" That is a question about `coverage`, `agreement` and the
significance gates — machinery PIT-1 endorsed — and it has never been tested as
a decision rule. It uses the existing frozen record's own structure rather than
resampling its outcomes.

**(b) Skip to Phase 9 — Data Gap Analysis.** The roadmap orders Phase 9 last
among the research phases on the premise that modelling should be exhausted
first. The record suggests the premise is inverted here: the engine reads price
and volume only, its components measure market drift, and the resolution
arithmetic in §8 says the instrument cannot see effects of the size the
available information plausibly carries. Phase 9's own gate — *"any new dataset
must have a precise hypothesis and measurable expected role"* — is the right
next gate to face.

Recommendation: **(b), with (a) as a cheap prerequisite** — (a) costs no new
information family, answers a question about machinery the record already
endorses, and its result changes what (b) should look for.

### 10.3 Constraints that carry forward unchanged

- The Phase 2 interval caveat stands: Wilson and normal intervals in
  `outcome_ledger` are **nominal and assume independent observations**, which
  overlapping horizons on one series violate. They describe performance. They
  are not a significance test.
- Cluster by **cutoff date**, always. Symbols read on one day are one
  observation of that day.
- `known_as_of()` is the only admissible slice for building a weight.
  Performance memory becomes known at `matured_at`, never at `cutoff_at`.
- Declare the **abstained / spoken** split before measuring anything on MAE
  (§7.3).
- No `probability_positive` exists. Brier, log loss and calibration error are
  not computable for any current candidate, and **confidence is never
  substituted for a probability**.
- Rank by `score_class`. Only `RETURN_AND_DIRECTIONAL` models may be compared on
  MAE or RMSE.
- Call `assert_record_admissible` on any record entering an evaluation.
- The three residual look-aheads PIT-1 disclosed are unrepaired. Until they are,
  **this harness cannot support a believable positive result** — only a
  believable negative one. Any phase proposing to demonstrate an improvement must
  address them first.

---

## 11. Deliberate limits of this phase

**Nothing was measured.** Every number in this report is quoted from a frozen,
append-only record and is attributed to it. No number was recomputed, and no
estimate was produced by this phase.

**No frozen record was modified.** `reports/EXPERIMENT_REGISTRY.md`,
`validation/REPORT.md` and `reports/SINGLE_NAME_PHASE1.md` were read only. The
correction in §6.3 is an observation recorded in this new document; it does not
alter PIT-1's wording, which stays visible.

**No closed programme was reopened.** PIT-1 is treated as the prior throughout,
which is what Phase 3's completion note instructed.

**C3 and C4 remain unmeasured.** That is a real gap in the candidate census and
it is left open rather than closed by a measurement §1.3 forbids.

**The cross-sectional question is untouched**, not answered. §7.2.

**No sealed exam artifact was accessed.**

---

## 12. STOP / GO Gate

### Gate question

Which candidates either beat the baseline with credible OOS evidence, or add
complementary information that may justify ensemble testing?

### Decision

**Route 1: no candidate. Route 2: no candidate as Phase 5 defines the term.**

### Basis

- The production target is stated exactly (§3) and the metric set is bound to
  displayed claims (§4).
- Every candidate has been compared against both trivial baselines on identical
  point-in-time splits, with clustered intervals, in a frozen prior study (§6).
- Every candidate is below the directional baseline; the one individually
  significant difference is negative (§6.2).
- Both return-emitting candidates lose to no-change on level and carry no
  magnitude information (§6.4).
- Confidence is not monotone in accuracy and inverts at the top band (§6.5).
- The neural challenger's contribution to the consensus is exactly zero, as a
  count (§8).
- The RL slot is structurally empty (§5.1).
- Phase 5's premise is contradicted by the record, and two admissible
  reformulations are proposed (§10).

---

## 13. Phase 4 Completion Summary

- Status: `COMPLETE`
- Result: `STOP on route 1 for every candidate; Phase 5 reformulation required`
- Next active phase: **PHASE 5 — blocked pending a scope decision (§10.2)**
- Candidates evaluated: 4 named + 13 constituents + 2 baselines
- Candidates promoted: 0
- Measurements performed: **none**
- Closed programmes reopened: **none**
- Frozen records modified: **none**
- Sealed exam artifacts accessed: **no**
