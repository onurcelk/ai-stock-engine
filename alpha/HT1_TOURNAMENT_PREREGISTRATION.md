# HT-1 — Full historical point-in-time tournament: pre-registration

**Date:** 2026-08-16
**Status:** FROZEN. Committed **before** the measurement code exists and
**before** any forward return is read.
**Instrument:** HR-1's historical replay machinery (`reports/V5_HISTORICAL_REPLAY.md`).
**Class:** DIAGNOSTIC. Every row this study produces is `RETROSPECTIVE_REPLAY`
and counts **zero** toward every promotion, demotion and resolution gate in the
programme.
**Budget slots spent:** **0.** HT-1 opens no information source. It reads the
free daily price history the repository already holds.

---

## 0. Conflict analysis — does this reopen anything closed?

Required by `CLAUDE.md` §1.3 before a line of measurement code is written.

| Closed programme | Its question | Does HT-1 touch it? |
|---|---|---|
| **V2 → V2.3** ABANDONED | Does a wider cross-sectional feature set rank the cross-section? | **No.** HT-1 is single-name time-series, no cross-sectional ranking, no learner fitted to a panel. |
| **V3** CLOSED, 3/3 slots | Do filings / Form 4 / 13F carry incremental information? | **No.** No new information family. No slot spent. |
| **V4** slot 1 SPENT, slot 2 BARRED | Does a 20-session horizon rescue filing-derived SUE? | **No.** No filings, no SUE. |
| **SN-1**, **F10-PILOT** | Calibrated selective single-name prediction on the alpha panel | **No.** Different instrument, different panel, no probability calibration claimed. |
| **PIT-1** CLOSED | Single-name point-in-time backtest of the app engine | Superseded in resolution by HR-1, which is the instrument HT-1 extends. Not reopened — HT-1 adds candidates, it does not re-litigate PIT-1's verdict. |
| **AMS-1** CLOSED, **REJECT** | Does *agreement among trading-agent families* identify more reliable 5-session single-name predictions? | **Adjacent. Constrained below.** |

### 0.1 The AMS-1 constraint, stated explicitly

AMS-1 rejected the hypothesis that **cross-family trading-agent agreement**
carries incremental information, and `EXPERIMENT_REGISTRY.md` §11.3 bars four
specific follow-ups: no sign flip, no claim the excluded agents would have
rescued it, no AMS-2, and **no re-run at another horizon**.

HT-1 measures the **directional accuracy of individual candidates**, which is
not AMS-1's arm — AMS-1's arms were consensus *states* feeding a calibrated
probability, and its Stage 1 audit already published per-agent signals and their
redundancy as a *diagnostic*. HT-1 extends that diagnostic to a different
instrument and a wider roster.

Three constraints are nevertheless binding on HT-1, and are frozen here:

1. **No agent-consensus arm.** HT-1 will not construct, score, or report a
   candidate defined as agreement across trading-agent families, at any horizon.
   If the challenger rule in §8 would produce one, the challenger is **not
   built** and that fact is the recorded outcome.
2. **No sign flip.** If a candidate's interval sits below the baseline, the
   inverted candidate is not thereby created. Inversions are reported as
   measured and never traded, promoted, or converted into an arm.
3. **HT-1 may not be cited as evidence that AMS-1 was wrong.** A different
   instrument reaching a different number about a different object is not a
   refutation of a closed verdict.

### 0.2 What HT-1 may never do

The HR-1 traps carry over unchanged and are restated because HT-1 runs a much
larger sweep over the same instrument:

- **No candidate here may enter `indicators.SOURCES`.** `ultimate.evaluate`
  consumes that dict wholesale, so adding a source changes the live incumbent's
  evidence set while the ensemble's version — the sha256 of `ultimate.py` —
  stays put, splitting the prospective record across two engines under one
  version string.
- **`app/core/ultimate.py` is not modified.** Not a constant, not a comment.
  The three horizons are passed to `evaluate_frame`, never added to
  `ultimate.HORIZONS`.
- **No threshold in the incumbent is tuned against any number HT-1 produces.**
  `MIN_T`, `MIN_CONFIDENCE` and `FAMILY_CAP` are frozen by
  `EXPERIMENT_REGISTRY.md` §3.5, and fitting them to a retrospective sample is
  the specific act it forbids.
- **The prospective ledger is neither read for evidence nor written.**
- **No result here promotes, demotes, or retires anything.**

---

## 1. The question

> Across a common grid of historical point-in-time cutoffs, how do the
> repository's price-only predictive components rank on directional accuracy at
> 1 day, 1 week and 5 weeks — and does any of them beat the trivial
> always-bullish baseline that HR-1 found the incumbent could not?

HT-1 is a **measurement of existing components**, not a search for a new one.
It answers "what does this repository actually contain, measured on one grid,
scored one way" — a question the repository has never answered because each
component was measured, when it was measured at all, on its own instrument.

---

## 2. The grid — frozen

Computed from the cached daily bars before this document was written. No
outcome was read to produce it.

| Property | Value |
|---|---|
| Cutoff generator | `replay_study.shared_calendar` on the universe **majority calendar** |
| Stride | **25 bars** — the 5-week horizon length |
| Cutoffs | **88**, from **2017-11-09** to **2026-07-10** |
| Independence | Consecutive windows touch but do not overlap, so all 88 are independent draws at 5w under `promotion.independent_cutoffs`, and strictly more than independent at 1d and 1w |
| Universe | `app/collection_universe.txt`, 30 symbols as declared 2026-08-15 |

**One grid for all three horizons, all candidates.** HR-1 used a per-horizon
grid; HT-1 does not, and the reason is that every comparison in a tournament
must be **paired on identical rows**. A candidate measured on cutoffs another
candidate never saw is not being compared with it.

### 2.1 Cell admission — one rule for every candidate

A `(symbol, cutoff)` **cell** is admissible iff, in that symbol's own series:

1. a bar exists **exactly at** the cutoff date (grid dates a symbol did not
   trade are skipped, never snapped to a neighbour), **and**
2. there are **at least 500 bars at or before** the cutoff, **and**
3. there are **at least 25 bars after** it.

500 is the RL and neural training window (§4.4, §4.5). Applying the *most
demanding* candidate's requirement to *every* candidate is deliberate: it costs
cells, and it buys the property that every candidate is scored on exactly the
same rows, so every paired comparison is exact rather than approximately paired.

**Measured before any outcome was read: 1,995 admissible cells over 26 symbols.**
`CBRS` (2 cutoffs), `SPCX` (1), `SNDK` (15) and `NBIS` (18) fall below the
history floor and contribute nothing. This is a property of listing dates, not
a selection.

### 2.2 Horizons

Read from the **same** cutoff, so a candidate's three horizons are three
readings of one moment rather than three studies.

| Key | Bars ahead | Source |
|---|---|---|
| `1d` | 1 | `ultimate.HORIZON_BY_KEY["1d"]`, unmodified |
| `1w` | 5 | `ultimate.HORIZON_BY_KEY["1w"]`, unmodified |
| `5w` | 25 | `replay_study.FIVE_WEEKS`, defined outside the engine |

`4h` is excluded for HR-1's reason: the feed serves ~2 years of hourly bars, and
PIT-1 measured the 4-hour after-close case **inverted** at p = 0.009 — a finding
to respect, not to re-open with a bigger sample.

---

## 3. Point-in-time discipline

Three mechanisms, none relying on the others. This is HR-1 §4 applied to a
wider roster, and the roster is exactly why it is restated.

1. **Truncation at the door.** Every candidate receives a frame produced by
   `replay._truncating_fetcher` — the same truncation RR-2 and HR-1 use, not a
   second implementation.
2. **The future-rewrite proof.** Every bar after the cutoff is multiplied by
   3.5 and the whole roster is re-run. **Every candidate's call at every cutoff
   must be identical.** This does not inspect the truncation; it demonstrates
   the answer cannot depend on the future. A candidate that fails is
   PIT-INADMISSIBLE and is removed from the roster with the failure recorded —
   it is not repaired mid-study.
3. **Causality cross-check.** For every closed-form candidate, the value
   computed on the truncated frame must equal the value computed on the full
   frame and read at the cutoff bar. Equality *is* causality; a mismatch is
   look-ahead. This is a property test, not a shortcut — the study always
   computes on the truncated frame.

**Two-process separation.** `predict` writes signals and never reads an outcome.
`score` reads outcomes and never writes a signal. Rows are immutable by database
trigger, so "frozen before the outcome was read" is a property of the storage,
not a claim about call order.

**Storage.** A **fourth** database file, `app/tournament.sqlite3`, under its own
CHECK constraint. The prospective ledger, the RR-2 replay ledger and the HR-1
study ledger are untouched and cannot receive a tournament row.

---

## 4. The roster — frozen before measurement

**27 candidates in 5 families, plus 2 reference arms.** Every candidate is an
existing repository component. Nothing here is newly invented, tuned, or
selected on performance.

### 4.1 Family P — Pine studies ported from TradingView (7)

`app/core/pine.py`, ported 2026-08-16. Read as
`indicators.stance(pine.signals(key, frame)).iloc[-1]` — the standing position
implied by the study's own published trading rule, quoted verbatim in
`pine.SIGNAL_RULES`.

`supertrend`, `mavilim`, `hl_ott`, `leledc`, `wavetrend`, `squeeze`, `vix_fix`.

**Research-only.** These are not in `indicators.SOURCES`, do not reach
`ultimate.py`, and are registered EXPERIMENTAL so
`model_registry.assert_record_admissible` refuses any production record that
names one. HT-1 does not change that and cannot.

### 4.2 Family T — Ultimate technical sources (10)

`indicators.SOURCES`, unmodified, read at the cutoff bar.

`trend_ma`, `trend_slope`, `macd`, `adx`, `rsi`, `roc`, `bollinger`,
`donchian`, `obv`, `structure`.

**Call rule: the sign, with no threshold.** Score > 0 → BUY, < 0 → SELL,
exactly 0 or NaN → HOLD. A magnitude threshold would be a free parameter with
no pre-registered value, and choosing one after seeing coverage is the retrofit
§3.2 exists to prevent.

### 4.3 Family R — rule agents (3)

`alpha/agents_audit.rule_signals`, whose windows were frozen at the 252-bar
reference **before AMS-1 read any outcome** and are reused unchanged:
`TURTLE_CHANNEL=26`, `MA_SHORT=6`, `MA_LONG=13`, `ROLLING_DELAY=4`,
`TURTLE_FOLLOW_BREAKOUT=False`.

`Turtle`, `Moving average crossover`, `Signal rolling`.

### 4.4 Family A — PIT-reconstructed RL agents (4)

`alpha/ams1_signals.pit_agent_stance`, reused unchanged: the policy speaking at
bar *t* was fitted on the **500 bars before the most recent annual refit
boundary at or before *t***, seed 42, at the repository's own default
iterations. Bars before the first admissible boundary are **unavailable, not
HOLD**.

`Policy gradient` (50 iters), `Evolution strategy` (100), `Neuro-evolution`
(30), `Neuro-evolution (novelty search)` (30).

**The other 15 RL agents are excluded on measured cost**, exactly as AMS-1
excluded them, and the figures are AMS-1's own measurements rather than new
claims: `B_VALUE_RL` (8 agents) **175 s per fit**, `C_ACTOR_CRITIC` (4)
**167 s per fit and degenerate at the repository's own default iterations** —
`Actor-critic` emits BUY on 98.5% of bars, `Actor-critic duel recurrent` emits
nothing — and `F_CURIOSITY_RL` (3) **43 s per fit**. At 1,995 cells these
require 8,700 to 35,400 CPU-hours between them.

**Per §11.3 of the registry, their exclusion may not later be offered as a
reason the result would have been different.**

### 4.5 Family N — recurrent neural projections (3)

`forecast.project` on the truncated close series. `LSTM`, `GRU`,
`Vanilla RNN` — `forecast.MODELS`, complete.

Frozen study parameterisation, chosen on **measured cost** before any outcome
was read, and declared as a study variant exactly as the rule agents' 252-bar
windows are:

| Parameter | Value | Why |
|---|---|---|
| Training bars | **500 trailing** | Matches the RL window, so a 2018 model and a 2026 model are fitted on the same amount of evidence and a change in their behaviour is not just a change in how much data each saw |
| Epochs | **60** | Measured: 9.7 s per fit at 500 bars against 23.5 s at the 150-epoch default. 150 epochs costs 16 h of CPU that buys no additional independent cutoffs |
| `size_layer` / `timestamp` / `dropout` / `learning_rate` | library defaults, untouched | Not tuned, not chosen by looking at a return |
| Rollout | **one 25-bar path per cell**, read at bars **1, 5, 25** | A 25-step autoregressive rollout's first step is identical to a 1-step rollout's first step — same weights, same deterministic loop — so three horizons cost one fit instead of three |

**Call rule:** sign of the projected move from the cutoff close to the bar at
the horizon. This family is the only one that emits a magnitude, so it is the
only one carrying return-based metrics.

### 4.6 Reference arms (not candidates, not ranked, not gated)

- **B0 — always BUY.** The trivial baseline HR-1 found the incumbent could not
  beat at any horizon. This is the thing to beat.
- **INC — `ensemble.ultimate`**, the frozen production incumbent, at
  `sha256:e629405d…6fb8f97a`, via `ultimate.evaluate_frame(frame, horizon)` on
  the identical cells. Measured at **18 ms per call**, so it is affordable and
  is included for exact comparability with the candidates. HR-1 already measured
  it on this grid; HT-1 re-measures it on the *admitted subset* so the
  comparison is paired rather than approximately aligned.

---

## 5. Metrics

The common currency is **direction**, because 24 of 27 candidates emit only a
direction. Return-based metrics are reported where a candidate emits a
magnitude, and are never compared across candidates that do not.

| Metric | Definition |
|---|---|
| **Coverage** | share of admissible cells on which the candidate emits a non-HOLD call |
| **Directional accuracy** | share of non-HOLD calls whose sign matches the sign of the realised forward return |
| **Wilson 95% CI** | on directional accuracy, for display |
| **Paired advantage** | candidate accuracy − B0 accuracy, computed **per cutoff on identical rows**, then averaged |
| **95% interval on the advantage** | paired moving-block bootstrap over cutoffs, `alpha/stats.block_bootstrap_ci`, **block = 4 cutoffs, 10,000 draws, seed frozen in `alpha/stats`** |
| **p-value** | `alpha/stats.block_bootstrap_p` against a null of zero advantage |
| **BUY−SELL return spread** | mean forward return on BUY calls minus mean on SELL calls, in basis points — a returns-based read that does not depend on the accuracy convention |

A HOLD is an abstention and carries **no** accuracy. Scoring it as a directional
miss would count an abstention as a wrong answer, which is the reading
`ultimate`'s design note rejects and HR-1 refused.

---

## 6. Resolution floor and the gate — declared before measurement

### 6.1 Resolution floor

A `(candidate, horizon)` cell is reported as **UNRESOLVED** — not as a result,
and not entered into the gate family — unless it has:

- **≥ 200 scored non-HOLD calls**, and
- **≥ 20 independent cutoffs** under `promotion.independent_cutoffs`.

A candidate that abstains its way under the floor has produced no finding. That
is a reportable outcome, not a failure to be worked around by lowering the
floor.

### 6.2 Gate G-HT1

A candidate **BEATS THE BASELINE** at a horizon iff **both** hold:

1. the paired moving-block bootstrap **95% interval on the advantage over B0
   lies entirely above zero**, and
2. its p-value survives **Holm–Bonferroni at α = 0.05** across the **entire
   family** of resolved `(candidate, horizon)` tests — up to 27 × 3 = 81 —
   using `alpha/stats.holm_bonferroni`.

Multiplicity control is declared **now**, before the family size is known,
because 81 tests at α = 0.05 produce roughly four spurious winners by
construction and picking the correction afterwards is choosing the answer.

**A candidate that clears (1) but not (2) is REPORTED AS NOT BEATING THE
BASELINE.** Its uncorrected interval is still printed — suppressing it would be
its own distortion — but the verdict column reads REJECT.

### 6.3 What a failed gate costs

Nothing is promoted, nothing changes weight, and no candidate is re-run with
different parameters to see whether it clears on a second attempt. There is no
budget slot to spend and no second attempt to spend it on: **the roster, the
grid, the parameterisation and the gate are frozen by this document.**

---

## 7. Redundancy and correlation — diagnostic, not a test

No hypothesis, no gate, no p-value. Reported because a leaderboard of 27
candidates that are secretly three candidates would be a misleading object.

- Pairwise **Pearson** and **Spearman** correlation of the call series across
  all admissible cells, all 351 pairs.
- **Agreement rate**: share of cells on which two candidates emit the same call.
- **Near-clone** flag at **|ρ| ≥ 0.9**, AMS-1's threshold, reused rather than
  re-chosen.
- Hierarchical clustering on `1 − |ρ|` to report **effective independent
  opinions** against nominal count.

AMS-1 measured zero near-clones among 231 agent pairs. HT-1's pairs include the
Pine and technical families, which have never been measured against each other.

---

## 8. Challenger construction — rule declared before ranking

### 8.1 The chronological split

The 88 cutoffs are split **by date, not at random**:

| Segment | Cutoffs | Use |
|---|---|---|
| **SELECTION** | first **53** (60%), 2017-11-09 → ~2023 | ranking, survivor identification, challenger construction |
| **VALIDATION** | last **35** (40%), ~2023 → 2026-07-10 | the challenger's only reported evaluation |

A challenger measured on the rows that selected it is measuring its own
selection. The split is the minimum honest defence, and it is declared before
either segment is scored.

### 8.2 The rule

The challenger is the **equal-weight majority vote** of every candidate that
**passes gate G-HT1 on SELECTION alone**, evaluated on VALIDATION. Ties → HOLD.

Bindings, all declared here:

- **Fewer than 2 survivors → no challenger is built.** That is the outcome, and
  it is reported as such rather than replaced by a weaker rule.
- **If the survivor set is composed only of trading agents**, the construction
  would be cross-family trading-agent agreement, which **§0.1 bars**. The
  challenger is then **not built**, and the bar is cited as the reason.
- **No weight is fitted.** Equal-weight, because any fitted weighting is a
  model trained on SELECTION whose evaluation would need its own held-out
  segment.
- **The challenger earns nothing.** Clearing on VALIDATION earns it a
  prospective test and no production weight, under HR-1's division of labour:
  *historical replay buys resolution for model development and cannot spend it
  on production.*

---

## 9. What is registered, and what is not

`model_registry` census discipline requires every predictive component to carry
a declared identity. The 7 Pine studies are registered under a **new
`pine.*` namespace** with a **new family constant**, so that:

- the existing census tests, which assert equality against
  `indicators.SOURCES` and `agents.REGISTRY`, are unaffected;
- no existing model's `version` changes, because `version` is the sha256 of each
  spec's own `version_module` and no existing spec's module is edited;
- they are `EXPERIMENTAL`, so `assert_record_admissible` **refuses** any
  production record naming one — the registration is a lock, not a promotion.

The technical sources, rule agents, RL agents and neural projections are already
registered and are not re-registered or modified.

---

## 10. Declared in advance: what would make HT-1 uninformative

Recorded now so it cannot be reframed later as a discovery:

1. **Everything abstains under the floor.** Plausible: HR-1 measured the
   incumbent's HOLD share at 0.86–0.93. Pine studies fire rarely by design.
2. **Nothing beats always-BUY.** The expected outcome. Three independent designs
   (SN-1, Family-10, AMS-1) and HR-1 have already measured this wall on free
   daily price data, and 0 of 9 components beat always-predicting-up in PIT-1.
   HT-1 is powered to *resolve* that, not to overturn it.
3. **A winner appears at one horizon only, and does not survive Holm–Bonferroni.**
   This is what 81 tests look like when the null is true.

**If (2) happens, HT-1 has succeeded.** A tournament whose value depends on
producing a winner is not a tournament.

---

## 11. Reproduction

```
python -m core.tournament --predict          # writes signals, reads no outcome
python -m core.tournament --predict --family N --shard 0 --of 12
python -m core.tournament --score            # reads outcomes, writes no signal
python -m core.tournament --report
```

---

**Frozen 2026-08-16. No number in this document was chosen by looking at a
forward return, and no section may be edited after the first signal is written —
corrections are appended, dated, and leave the original wording visible.**

---

## Amendment 1 — 2026-08-16, before any signal was written

**Nothing above is altered. This appends a parameterisation §4.5 omitted, and
records why it is required.**

**What was found.** `forecast.project` is **stochastic**. `app/core/forecast.py`
sets no seed anywhere, and its `DropoutWrapper(output_keep_prob=0.8)` is built
into the graph unconditionally — so dropout is active **at prediction time as
well as during training**, not only while fitting. Two identical calls on
identical inputs returned projected moves of **−9.08%** and **−14.25%**.

**Why this blocks the protocol as written.** §3.2 requires that rewriting the
future leave every candidate's call *identical*. Against a stochastic candidate
that test cannot distinguish look-ahead from the model's own noise, so family N
would enter the tournament with no point-in-time proof at all.

**What is frozen, in addition to §4.5.** Both are set inside `tournament.py`.
**`app/core/forecast.py` is not modified**, so no `neural.*` model version moves:

1. **Graph seed 42**, applied at graph construction, via a wrapper contained in
   the study module. 42 is `BaseAgent`'s own default and AMS-1's `AGENT_SEED`,
   reused rather than chosen.
2. **Single-threaded op scheduling** — `OMP_NUM_THREADS`,
   `TF_NUM_INTRAOP_THREADS`, `TF_NUM_INTEROP_THREADS` all `1`. The residual
   non-determinism after seeding is multi-threaded float accumulation order, and
   it is not cosmetic: unpinned, a seeded pair still diverged to −10.79% against
   +10.69%. Pinned and seeded, the 25-bar path is **bit-identical**, verified
   before this amendment was written.

The study's 12 parallel workers each need one thread regardless, so this costs
nothing.

**Recorded as a finding, not a defect fixed here.** Dropout at prediction time
means every projection the *application* shows a user is one draw from a
distribution it never displays, and the UI reports no interval around it. That
is a property of a `CHALLENGER`-status component, it is outside HT-1's scope to
change, and HT-1 must not be read as licensing a change to it.
