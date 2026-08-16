# HT-1 — Full historical point-in-time tournament: result

**Date:** 2026-08-17
**Protocol:** `alpha/HT1_TOURNAMENT_PREREGISTRATION.md`, frozen at `4108818`,
amended at `d43f756` and `60afa2a`, all **before** the measurement code existed
and before any forward return was read. Implementation `9bee1e8`.
**Status:** RUN AND SCORED. **172,881 scored signals.**
**Class:** DIAGNOSTIC. Every row counts **zero** toward every promotion,
demotion and resolution gate. **0 budget slots spent** — no information family
was opened.
**Nothing was promoted, demoted, retired, reopened or tuned.**

---

## 0. The one-line answer

> ```text
> HT-1 VERDICT: 0 of 27 candidates beat the always-bullish baseline
>               at any of the three horizons. 81 tests, 81 REJECT.
> ```

Seven Pine studies, the ten sources the incumbent aggregates, three rule agents,
four point-in-time-reconstructed RL agents and three recurrent architectures were
measured on **one grid of 88 independent historical cutoffs**, against **one
baseline**, with **one scoring rule**, on **identical rows**. None of them beat
buying and holding. **No challenger was built**, because the pre-registered rule
requires at least two survivors and there were none.

This was the declared expected outcome (§10.2 of the pre-registration), and
§10 said in advance that if it happened **HT-1 has succeeded**. A tournament
whose value depends on producing a winner is not a tournament.

---

## 1. What was measured

| | |
|---|---|
| Grid | **88 cutoffs**, stride 25 bars on the universe majority calendar, **2017-11-09 → 2026-07-10** |
| Cells | **1,995** `(symbol, cutoff)` pairs over **26 symbols** |
| Admission | one rule for every candidate: a bar at the cutoff, ≥500 bars behind it, ≥25 ahead |
| Horizons | `1d` (1 bar), `1w` (5), `5w` (25), all read from the same cutoff |
| Candidates | **27 ranked**, in 5 families, plus 2 reference arms |
| Scored signals | **172,881** |
| Independent cutoffs | **88 at every horizon, for every candidate** |
| Gate family | **81** resolved tests — every candidate × horizon cleared the resolution floor |
| Instrument | paired per-cutoff moving-block bootstrap, block 4 cutoffs, 10,000 draws, then Holm–Bonferroni at α = 0.05 |

Compute: 335 s closed-form, 194 s reference, 1,833 s RL reconstruction,
6,908 s neural. **2 h 35 m wall clock**, 0 failures in any phase.

Every candidate was scored on **exactly the same 1,995 cells**, so every
comparison in this document is exactly paired rather than approximately aligned.

---

## 2. The leaderboard

Advantage is *candidate accuracy − always-BUY accuracy on the rows the candidate
actually called*. The interval is the paired block bootstrap; `p Holm` is the
step-down correction across all 81 tests.

### 2.1 One day — best five and worst three

| Candidate | Family | Calls | Cov. | Accuracy | Baseline | Advantage | 95% interval | p Holm | Verdict |
|---|---|---:|---:|---:|---:|---:|---|---:|---|
| `technical.trend_ma` | technical | 1,995 | 1.00 | 0.5173 | 0.5113 | **−0.0028** | [−0.0667, +0.0577] | 1.000 | REJECT |
| `technical.trend_slope` | technical | 1,995 | 1.00 | 0.5153 | 0.5113 | −0.0032 | [−0.0675, +0.0498] | 1.000 | REJECT |
| `neural.lstm` | neural | 1,995 | 1.00 | 0.5073 | 0.5113 | −0.0054 | [−0.0654, +0.0464] | 1.000 | REJECT |
| `pine.mavilim` | pine | 1,995 | 1.00 | 0.5118 | 0.5113 | −0.0061 | [−0.0693, +0.0458] | 1.000 | REJECT |
| `neural.gru` | neural | 1,995 | 1.00 | 0.5128 | 0.5113 | −0.0068 | [−0.0704, +0.0547] | 1.000 | REJECT |
| … | | | | | | | | | |
| `neural.vanilla_rnn` | neural | 1,995 | 1.00 | 0.4647 | 0.5113 | −0.0536 | [−0.1299, +0.0127] | 1.000 | REJECT |
| `pine.leledc` | pine | 1,995 | 1.00 | 0.4632 | 0.5113 | −0.0557 | [−0.1390, +0.0192] | 1.000 | REJECT |
| `pine.wavetrend` | pine | 1,995 | 1.00 | 0.4637 | 0.5113 | −0.0585 | [−0.1478, +0.0204] | 1.000 | REJECT |

**Not one candidate has a positive advantage at `1d`.** The best of 27 is 0.28
percentage points *below* always-BUY.

### 2.2 One week — the only horizon where anything is positive

| Candidate | Family | Calls | Accuracy | Baseline | Advantage | 95% interval | p | p Holm | Verdict |
|---|---|---:|---:|---:|---:|---|---:|---:|---|
| `rule.moving_average_crossover` | rule | 1,995 | 0.5293 | 0.5118 | **+0.0139** | [−0.0573, +0.0789] | 0.693 | 1.000 | REJECT |
| `pine.supertrend` | pine | 1,995 | 0.5238 | 0.5118 | +0.0127 | [−0.0636, +0.0814] | 0.741 | 1.000 | REJECT |
| `technical.obv` | technical | 1,995 | 0.5263 | 0.5118 | +0.0123 | [−0.0578, +0.0799] | 0.730 | 1.000 | REJECT |
| `technical.trend_slope` | technical | 1,995 | 0.5178 | 0.5118 | +0.0036 | [−0.0681, +0.0727] | 0.919 | 1.000 | REJECT |
| `technical.donchian` | technical | 1,994 | 0.5155 | 0.5115 | +0.0006 | [−0.0779, +0.0681] | 0.986 | 1.000 | REJECT |

Five candidates out of 27 are above zero. **Every interval straddles zero and
the smallest uncorrected p-value among them is 0.693** — these are not weak
positives, they are noise. All three of the leaders are trend-following, which
is the one coherent pattern in the table and is not a significant one.

### 2.3 Five weeks — the horizon where the baseline is hardest

At `5w` the always-BUY baseline is right **57.04%** of the time, because
five-week equity returns are usually positive. Nothing came close.

| Candidate | Family | Accuracy | Baseline | Advantage | 95% interval | p | p Holm | Verdict |
|---|---|---:|---:|---:|---|---:|---:|---|
| `rule.moving_average_crossover` | rule | 0.5378 | 0.5704 | **−0.0340** | [−0.0815, +0.0087] | 0.150 | 1.000 | REJECT |
| `technical.donchian` | technical | 0.5341 | 0.5702 | −0.0357 | [−0.0832, +0.0048] | 0.118 | 1.000 | REJECT |
| `pine.supertrend` | pine | 0.5353 | 0.5704 | −0.0361 | [−0.0797, +0.0153] | 0.139 | 1.000 | REJECT |
| … | | | | | | | | |
| `rule.signal_rolling` | rule | 0.4667 | 0.5704 | −0.1034 | [−0.1604, −0.0416] | 0.0007 | 0.057 | REJECT |
| `pine.vix_fix` | pine | 0.4491 | 0.5704 | −0.1166 | [−0.1970, −0.0371] | 0.005 | 0.357 | REJECT |

**At `5w`, 18 of 27 candidates have intervals lying entirely *below* zero** —
that is, measurably *worse* than doing nothing but buying. **After Holm–Bonferroni
none of those survive either**, and the protocol's §0.1 bar applies: an inverted
candidate is not thereby created, and none of this may be traded as a contrarian
signal.

Full tables: `reports/ht1_leaderboard.csv` (all 87 rows).

---

## 3. The incumbent, measured on identical cells

`ensemble.ultimate` at `sha256:e629405d…6fb8f97a`, unmodified.

| Horizon | Calls | Coverage | Accuracy | Baseline on its own rows | Advantage | 95% interval |
|---|---:|---:|---:|---:|---:|---|
| `1d` | 373 | 0.187 | **0.5845** | 0.5871 | −0.0040 | [−0.0643, +0.0579] |
| `1w` | 371 | 0.186 | 0.5337 | 0.4906 | +0.0327 | [−0.0656, +0.1344] |
| `5w` | 354 | 0.177 | 0.5593 | 0.6356 | −0.0824 | [−0.1422, −0.0318] |

**The incumbent has the highest raw accuracy on the board at `1d` — 0.5845 —
and it still does not beat its baseline.** That number is the clearest single
illustration of what this whole tournament measures: the engine abstains on 81%
of cells, and the cells it chooses to speak on are ones that drifted *up*
(baseline 0.5871 against 0.5113 across all cells). Its selection is picking
favourable days, and then it is not adding anything on top of them.

At `5w` its interval lies entirely below zero. This reproduces HR-1's finding on
the admitted subset and is not a new measurement of the engine.

---

## 4. Redundancy — 27 nominal candidates are 27 real ones

Diagnostic. No hypothesis, no gate.

| | |
|---|---|
| Pairs examined | **351** |
| Near-clones at \|ρ\| ≥ 0.9 | **0** |
| Effective independent opinions | **27 of 27** |
| Largest \|ρ\| of any pair | **0.832** — `technical.bollinger` vs `technical.donchian`, and **negative** |

Mean within-family \|ρ\|:

| Family | n | mean \|ρ\| | max \|ρ\| |
|---|---:|---:|---:|
| technical | 10 | **0.487** | 0.832 |
| pine | 7 | 0.330 | 0.676 |
| rule | 3 | 0.217 | 0.344 |
| neural | 3 | 0.079 | 0.165 |
| rl | 4 | **0.047** | 0.084 |

Two things worth stating. First, **AMS-1's Stage 1 finding generalises**: it
measured zero near-clones among 231 agent pairs, and adding the Pine and
technical families — which had never been measured against each other — leaves
that unchanged at 351 pairs. The repository's components really are
algorithmically distinct.

Second, **distinctness bought nothing.** Twenty-seven genuinely independent
opinions, none of which beats buy-and-hold, is a sharper negative than
twenty-seven correlated ones would have been: this is not a case of one idea
counted many times.

The strongest pair is *negatively* correlated by design — `_bollinger_reversion`
argues against the trend sources deliberately, and the measurement confirms it
does what its docstring says.

---

## 5. The challenger was not built

> ```text
> §8.2: 0 candidate(s) passed G-HT1 on SELECTION; fewer than two, so no
> challenger is built. That is the outcome, not a reason to weaken the rule.
> ```

SELECTION was the first 53 cutoffs, **2017-11-09 → 2023-01-11**; VALIDATION the
last 35, **2023-02-16 → 2026-07-10**. The split was chronological and declared
before either segment was scored. **Zero candidates cleared G-HT1 on SELECTION**,
so the rule's first refusal fired and no vote was constructed.

The AMS-1 bar (§0.1) was therefore never reached. It remains in force: had the
survivors been trading agents only, the challenger would have been refused as
cross-family trading-agent agreement regardless of what it measured.

---

## 6. `neural.lstm` is NOT REPRODUCIBLE — measured

Amendment 2 committed the study to publishing this rather than asserting it.
Sample of 60 cells × 3 horizons = 180 calls, each run twice through the full
pipeline, in fresh interpreters, seeded and thread-pinned:

| Candidate | Compared | Sign flips | **Flip rate** | Median drift | p90 drift | Mean drift | Max drift | Reproducible |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `neural.lstm` | 180 | 13 | **7.2%** | 0.44 pp | 4.43 pp | 16.66 pp | **1,898.7 pp** | **No** |
| `neural.gru` | 180 | 0 | **0.0%** | 0.00 | 0.00 | 0.00 | 0.00 | **Yes** |
| `neural.vanilla_rnn` | 180 | 0 | **0.0%** | 0.00 | 0.00 | 0.00 | 0.00 | **Yes** |

A second independent probe of the same size returned **17** flips rather than
13 — **the instability estimate is itself unstable**, which is the cleanest
statement of the problem available.

**How to read `neural.lstm`'s leaderboard rows: as one draw.** About one call in
fourteen would change sign on a re-run, so its measured accuracies — 0.5073,
0.5018, 0.5048 — carry an additional error bar that the tournament's confidence
intervals do **not** contain, because those intervals describe sampling
variation in the market, not variation in the model given the market. Its
verdict is REJECT at all three horizons and the margin is far larger than this
noise, so the conclusion is unaffected; a *positive* result from this candidate
could not have been read the same way.

**The drift is heavy-tailed and that is the more serious half.** The median
re-run moves the projected return by 0.44 percentage points, which is
tolerable. The maximum moved it by **1,899 percentage points** — the
autoregressive rollout occasionally diverges outright. GRU and Vanilla RNN,
running through the identical code path on the identical cells, are bit-identical
every time, so this is a property of the LSTM configuration and not of the
harness.

**This is a finding about the application, recorded and not fixed here.**
`neural.lstm` holds `CHALLENGER` status, and the app presents its projection to
a user as a single number with no interval. Repairing it — a seed, a dropout
flag that distinguishes training from inference, a divergence guard — is outside
HT-1's scope, and HT-1 does not license the change.

---

## 7. What this does and does not say

### 7.1 What it says

- **On free daily price data, over 2017–2026, none of this repository's 27
  price-only components carries directional information that beats buying.**
  At the resolution of 88 independent cutoffs and ~1,995 calls per candidate,
  that statement is now *resolved* rather than merely unrefuted.
- **The abstention remains the incumbent's best feature, and its selection is
  not skill.** It speaks on 18% of cells and those cells drift up more than
  average; on them, it adds nothing.
- **Trend-following is the only coherent pattern**, and it is not significant.
  The three highest `1w` advantages are a moving-average crossover, Supertrend
  and on-balance volume; the three worst `5w` are a bottom-finder, an oscillator
  and an exhaustion detector.
- **The seven newly ported Pine studies are not exceptions.** They are drawn
  from the same distribution as everything else, and four of the seven are among
  the worst rows at `5w`.

### 7.2 What it does **not** say

- **It is not a finding about the market.** It is a finding about these 27
  components on a back-adjusted, survivorship-selected reconstruction of a
  30-symbol universe someone watches today.
- **It is not a demotion.** No production weight moved. D1 requires 50
  independent cutoffs of *prospective* evidence and this study supplies none —
  independent prospective cutoffs remain **0 of 50**.
- **It licenses no change to any engine.** Tuning `MIN_T`, `MIN_CONFIDENCE` or
  `FAMILY_CAP` against these numbers is the specific act
  `EXPERIMENT_REGISTRY.md` §3.5 forbids.
- **It does not refute AMS-1**, and may not be cited as doing so. AMS-1 tested
  agent *consensus* as a calibrated meta-signal; HT-1 measured individual
  candidates on a different instrument. Both found nothing, separately.
- **It does not license inverting anything.** §0.1 and AMS-1 §11.3 both bar it,
  and the 18 negative `5w` intervals do not survive multiplicity correction in
  any case.

### 7.3 Where it sits in the programme

Five independent designs have now measured the same wall on free daily price
data for single names:

| study | design | resolution | result |
|---|---|---|---|
| PIT-1 | 12 cutoffs, app engine | very low | 0 of 9 components beat always-up |
| SN-1 | weekly grid, B3-based | 39 bp / 3.0 pp | no probability below 0.5 |
| Family-10 | event time, 8-K adverse items | floor 49 bp | unreachable hurdle |
| AMS-1 | agent consensus | 31 bp / 3.0 pp | nothing above it |
| HR-1 | incumbent, 88–200 cutoffs | ±0.6–5.0 pp | does not beat its baseline |
| **HT-1** | **27 components, 88 cutoffs, paired** | **±5–7 pp on advantage** | **0 of 27, 81 tests** |

HT-1 is the **broadest** of the six rather than the sharpest: it buys coverage
of the whole component inventory at a resolution similar to HR-1's. Its
contribution is that the inventory has now been measured *as an inventory*,
on one grid, with one rule — which no previous study did.

---

## 8. Reproduction

```
python -m core.tournament --predict --family closed_form
python -m core.tournament --predict --family reference
python -m core.tournament --predict --family rl
python -m core.tournament --predict --family neural --workers 12
python -m core.tournament --score
python -m core.tournament --report
python -m core.tournament --stability --workers 12
```

Storage is `app/tournament.sqlite3`, a **fourth** database under a CHECK
constraint admitting only `HT-1` rows. The prospective ledger, the RR-2 replay
ledger and the HR-1 study ledger were neither read for evidence nor written.
Signals are immutable by trigger.

**Verified after the run:** `app/core/ultimate.py`, `app/core/forecast.py` and
`app/core/indicators.py` are byte-identical to their state before HT-1 began;
`indicators.SOURCES` is unchanged at 10 entries; `5w` is absent from
`ultimate.HORIZONS`; and no `neural.*`, `technical.*`, `rule_agent.*` or
`ensemble.*` model version moved.
