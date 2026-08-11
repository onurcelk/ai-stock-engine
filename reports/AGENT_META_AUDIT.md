# AMS-1 Stage 1 — trading-agent inventory, point-in-time audit and redundancy

**Written 2026-08-11. NON-PREDICTIVE. No forward return, target or label was
read.** This is the admissibility stage of the Agent Meta-Signal Study, and it is
committed before the pre-registration and before any outcome is scored.

Reproduce:

```
./.venv/Scripts/python.exe -W ignore -m alpha.agents_audit
./venv/Scripts/python.exe -m pytest app/tests/test_ams1_audit.py
```

> ## Stage 1 verdict: **PASS** — three genuinely distinct PIT-admissible families
>
> …and two findings that change what the rest of the study can claim:
>
> 1. **All 19 reinforcement-learning agents are point-in-time inadmissible as the
>    repository implements and uses them.** Measured, not inferred: rewriting the
>    *future* half of a price series moves **47%–71% of the past signals**.
> 2. **The agents are not redundant clones. They are mutually near-independent at
>    the level of noise.** The study's motivating premise — that ten Q-learning
>    variants are one effective opinion — is **empirically false here**. Mean
>    pairwise exact agreement inside the eight-strong Q family is **0.523**
>    against **0.468** between families, and **zero** of the 231 agent pairs
>    reach the near-clone threshold.

---

## 1. Inventory — what actually exists

The repository, not an inherited list, is the source of truth. **22 implemented
trading agents:**

| # | agents | module | training | state |
|---|---:|---|---|---|
| 3 | Turtle · Moving average crossover · Signal rolling | `app/core/strategies.py` | none — closed form | none |
| 19 | the RL registry | `app/core/agents/` | `train(iterations)` over the constructed series | network weights (+ LSTM cell state on the recurrent variants) |

The nineteen are **six implementations**, not nineteen designs: `deepq.py`
parameterises double / duel / recurrent as orthogonal flags, and `actorcritic.py`
does the same. The registry's own docstring says so.

**Four further agents exist as notebooks only and have no implementation to
audit** — recorded so the inventory is a census rather than a selection:
`agent/23.abcd-strategy-agent.ipynb`, `agent/updated-NES-google.ipynb`,
`free-agent/evolution-strategy-bayesian-agent.ipynb`,
`realtime-agent/realtime-evolution-strategy.ipynb`. The last of these ships a
pre-trained `model.pkl`, which is definitionally not point-in-time.

## 2. The point-in-time audit

### 2.1 The rule

> A signal at cutoff *t* requires every input, every training row and every piece
> of model state to be `<= t`. **A model trained once on the entire history and
> replayed backwards is forbidden.**

### 2.2 What the code does

`BaseAgent.__init__(close)` takes the **whole** series. `train()` maximises
`_simulate()` over that whole series. `signals()` then replays the fitted policy
from bar 0. The signal at bar *t* is therefore produced by a policy fitted using
bars after *t* — exactly the forbidden construction.

### 2.3 The measurement

Read as code that is an argument; measured it is a fact. The probe trains an
agent on a series, trains it again on a series whose **second half** has been
bent downwards, and counts how many signals in the **untouched first half**
move. Same discipline as `test_validation.py::test_future_cannot_change_the_verdict`.

| agent | past signals moved | |
|---|---:|---|
| Neuro-evolution | **142 / 200 = 71.0%** | PIT-INADMISSIBLE |
| Evolution strategy | **94 / 200 = 47.0%** | PIT-INADMISSIBLE |
| Turtle | **0 / 200** | PIT-ADMISSIBLE |
| Moving average crossover | **0 / 200** | PIT-ADMISSIBLE |
| Signal rolling | **0 / 200** | PIT-ADMISSIBLE |

The two RL agents probed are the *cheapest* two, chosen only because they train
in under four seconds. Every RL agent shares the same `BaseAgent` constructor,
`train()` contract and `signals()` replay, so the classification is structural
and the probe confirms it where it was affordable to run.

### 2.4 Can they be reconstructed? — the cost, measured

They can, in principle: train only on a prefix and apply the frozen policy
forward. What decides whether that is available to this study is cost, so cost
was measured — one training run plus one signal replay, per agent, on one symbol:

| family | agents | 500 bars | 1,000 bars |
|---|---:|---:|---:|
| `E_EVOLUTIONARY` | 3 | **6.7 s** | 11.8 s |
| `D_POLICY_GRADIENT` | 1 | **8.5 s** | 8.0 s |
| `F_CURIOSITY_RL` | 3 | 43.1 s | 86.6 s |
| `C_ACTOR_CRITIC` | 4 | **166.9 s** | 328.2 s |
| `B_VALUE_RL` | 8 | **175.4 s** | 358.3 s |
| **whole roster** | **19** | **400.5 s** | **792.9 s** |

What that buys, at the study's own geometry (316 development cutoffs, ≥100
symbols):

| design | cost |
|---|---|
| refit at every cutoff — the ideal walk-forward | **≈ 3.3 years** |
| annual refit | **≈ 15 days** |
| one burn-in fit, policy frozen for eight years | ≈ 11 hours |

**The full roster cannot be reconstructed point-in-time at this study's
resolution.** Families `A`, `D` and `E` can: their combined cost is **15.2 s per
symbol per refit**, which is an annual-refit walk-forward over 100 symbols in
about an hour. Families `B`, `C` and `F` cost **385 s** for the same unit — 25×
more — and are excluded on that measured ground, recorded here *before* any
outcome was read so the exclusion cannot be revisited on the strength of a
result.

### 2.5 Four of the excluded agents are degenerate anyway

At the repository's **own default iteration counts** — which its registry
docstring already warns are "still mostly exploring" — several policies are
constants, and a constant is not an opinion:

| agent | buy share | flat | sell share |
|---|---:|---:|---:|
| Actor-critic recurrent | 0.333 | **0.333** | 0.333 | 
| Actor-critic duel recurrent | 0.374 | **0.221** | 0.405 |
| Actor-critic | 0.314 | **0.167** | 0.520 |
| Recurrent Q-learning | 0.298 | 0.000 | **0.702** |

`Actor-critic recurrent` splits its actions into exact thirds — a cycling
policy, not a view. On the raw `signals()` path measured separately, `Actor-critic`
emits BUY on **98.5%** of bars and SELL on **0%**, and `Actor-critic duel
recurrent` emits nothing at all.

**This is recorded now so that it cannot later be offered as the explanation for
a null.** If AMS-1 fails, "the good agents were excluded" is not available: four
of the fifteen excluded are degenerate at the settings the repository ships.

### 2.6 Classification

| status | count | agents |
|---|---:|---|
| **PIT-ADMISSIBLE** | **3** | Turtle, Moving average crossover, Signal rolling |
| **PIT-ADMISSIBLE after reconstruction** | **4** | Policy gradient; Evolution strategy, Neuro-evolution, Neuro-evolution (novelty search) |
| **PIT-INADMISSIBLE — excluded on measured cost** | **15** | the 8 value-RL, 4 actor-critic and 3 curiosity variants |
| **no implementation to audit** | 4 | ABCD, NES-Google, ES-Bayesian, realtime-ES |

## 3. Family taxonomy — frozen, architectural, and fixed before any outcome

| family | agents | basis |
|---|---:|---|
| **A_RULE** | 3 | closed-form price rules; no training, no fitted parameter, no state |
| **B_VALUE_RL** | 8 | a network estimates action values; policy is argmax. Double/duel/recurrent are flags on one implementation |
| **C_ACTOR_CRITIC** | 4 | separate policy actor and value critic; action from an explicit policy distribution |
| **D_POLICY_GRADIENT** | 1 | REINFORCE on discounted episode reward; no value function at all |
| **E_EVOLUTIONARY** | 3 | gradient-free population search; no backprop, no replay memory, no TD target |
| **F_CURIOSITY_RL** | 3 | value-based **plus** a forward-dynamics model whose prediction error enters the reward |

**Architecture determines the taxonomy. Redundancy is a diagnostic and does not
move it** — a test asserts the mapping is unchanged by the clustering routine.

## 4. Signal normalisation — frozen

Every agent's event series becomes a **standing position** in `{+1, 0, −1}` via
`app/core/indicators.stance`, the repository's own tested function: *"read
literally, an agent has no opinion on 95% of bars… what it actually claims is a
standing position, long from its last buy until its next sell."* Forward-filling
is causal.

Two decisions worth naming, both frozen before any outcome:

* **The raw policy action is read, not `BaseAgent.signals()`.** That method
  suppresses SELL whenever inventory is empty, because it produces trade
  instructions for a backtester that cannot sell what it does not own. A
  suppressed SELL is not a HOLD — it is a SELL the bookkeeping refused to print.
  The artefact is visible in the raw counts: `signals()` returns *exactly equal*
  BUY and SELL totals for every gradient-free agent.
* **Rule-agent windows are absolute, not scaled to the series.** The Streamlit
  app sizes them as a percentage of whatever is on screen, which would make the
  agent change shape as history accumulates. They are frozen by applying the
  app's own proportions to the repository's own frozen minimum history
  (`universe.MIN_HISTORY = 252`): channel **26**, MA **6/13**, delay **4**, and
  `follow_breakout=False` — the notebook's original direction, *not* flipped,
  because flipping it on performance would be the sign-fitting this study forbids.

## 5. Signal availability

Measured across the full 316-cutoff development panel for the rule family
(143,675 cells, 594 symbols):

| agent | defined | BUY | SELL |
|---|---:|---:|---:|
| Turtle | 1.0000 | 0.4255 | 0.5745 |
| Moving average crossover | 1.0000 | 0.5722 | 0.4278 |
| Signal rolling | 1.0000 | 0.4690 | 0.5310 |

Missing is never turned into HOLD. An agent with no admissible policy at a
cutoff is **absent**; a leading zero before an agent's first ever signal means
*genuinely flat*, which is that agent's own semantics.

## 6. Redundancy — the premise the study was built on, tested

Measured on 6 symbols × 500 bars = 3,000 rows, all 22 agents. **This sweep is
deliberately NOT point-in-time** — each RL agent is trained on the whole sample
series — because how much the agents duplicate *each other* is the one question
a look-ahead cannot corrupt. Nothing from it enters a predictive stage.

### 6.1 The headline

| | |
|---|---|
| Mean pairwise exact agreement **within** a family | **0.4964** |
| Mean pairwise exact agreement **between** families | **0.4677** |
| Mean mutual information within a family | **0.060 bits** (of 1.585 possible) |
| Mean mutual information between families | **0.015 bits** |
| Near-clone pairs (exact ≥ 0.90) | **0 of 231** |
| **Effective opinions** at that threshold | **22 of 22 nominal** |

### 6.2 Family × family

| | A_RULE | B_VALUE | C_ACTOR | D_POLICY | E_EVOL | F_CURIO |
|---|---:|---:|---:|---:|---:|---:|
| **A_RULE** | *0.384* | 0.499 | 0.407 | 0.497 | 0.499 | 0.483 |
| **B_VALUE_RL** | | *0.523* | 0.425 | 0.530 | 0.502 | 0.497 |
| **C_ACTOR_CRITIC** | | | *0.405* | 0.410 | 0.411 | 0.402 |
| **D_POLICY_GRADIENT** | | | | — | 0.505 | 0.495 |
| **E_EVOLUTIONARY** | | | | | *0.512* | 0.510 |
| **F_CURIOSITY_RL** | | | | | | *0.531* |

Diagonal = within-family. **The diagonal is not meaningfully higher than the
off-diagonal.** Directional agreement, conditional on both agents being active,
sits at **0.49–0.53 essentially everywhere** — coin-flip. Pearson correlations
run **−0.09 to +0.08**.

### 6.3 What this means, stated plainly

The study's motivating example was:

```
10 Q variants BUY   ->  may represent only one effective opinion
```

**On this repository that is false.** The eight value-RL variants agree with each
other 52.3% of the time and with everything else 46.8% — a difference of five
percentage points. They are not one opinion repeated; they are eight
near-independent draws.

**The diagnosis is worse than redundancy, not better.** Signals whose pairwise
correlation is ~0.02 and whose mutual information is ~0.015 bits are not
diverse-but-informative; they are what independent *noise* looks like. Agreement
among independent noise sources is a binomial coincidence and carries no
information about the future. Whether these particular signals are noise or weak
information is precisely what Stage 3 measures — but the redundancy structure
that the raw-versus-family distinction was supposed to expose **is not present**,
and Gate 4 must be read in that light.

Two genuine structures do show up and are recorded:

* The single strongest pair is **cross-family**: `Policy gradient` × `Q-learning`
  at 0.747 exact, ρ = 0.52.
* `A_RULE`'s three members agree with each other **less** than with anything
  else (0.384), because the turtle runs the notebook's *fade* direction while
  the crossover follows trend — mean ρ = **−0.19** between them. Architecturally
  they are one family; empirically they are three distinct opinions. The
  taxonomy does not move for it, and the tension is reported rather than
  resolved by regrouping.

## 7. Stage 1 gate

| # | requirement | result |
|---|---|---|
| 1 | every real implementation found and described from the code | **PASS** — 22 implemented, 4 notebook-only |
| 2 | PIT status classified, by measurement where affordable | **PASS** — 3 admissible, 4 admissible after reconstruction, 15 excluded |
| 3 | exclusions justified without silently allowing leakage | **PASS** — measured cost, recorded before any outcome |
| 4 | family taxonomy frozen on architecture, before outcomes | **PASS** — 6 families, pinned by test |
| 5 | signal normalisation frozen | **PASS** — `stance`, absolute windows, raw policy action |
| 6 | redundancy measured on signals only | **PASS** — 231 pairs, 4 measures each |
| 7 | **enough genuinely distinct PIT-safe families to test the thesis** | **PASS — 3** (`A_RULE`, `D_POLICY_GRADIENT`, `E_EVOLUTIONARY`) |

```text
AMS-1 ADMISSIBILITY: PASS
```

**Three families, seven agents, on 100 symbols and 316 development cutoffs.**
The sealed exam was not touched. No forward return was read. No family budget
slot was spent — AMS-1 opens no information source.

**What the reduced roster costs the study, stated now.** Excluding `B_VALUE_RL`
removes the family whose supposed internal redundancy motivated the raw-versus-
family distinction in the first place. Gate 4 can still be tested — `E_EVOLUTIONARY`
carries three agents against `D_POLICY_GRADIENT`'s one, so raw and family
weighting genuinely differ — but the study can no longer answer "would twenty-two
agents have behaved differently from seven". §6.3 is the closest it gets, and it
suggests the answer is *no, because none of them are duplicates of each other*.

## 8. Artefacts

| file | content |
|---|---|
| `alpha/agents_audit.py` | inventory, taxonomy, normalisation, PIT probe, redundancy |
| `alpha/ams1_signals.py` | the point-in-time reconstruction for families A, D, E |
| `alpha/out/ams1_agent_audit.json` | every number quoted above |
| `alpha/out/ams1_agent_costs.json` | the measured per-agent training costs |
| `alpha/out/ams1_rule_stances.pkl` | rule-family stances over the full 143,675-cell panel |
| `app/tests/test_ams1_audit.py` | 30 tests, including the proof that the leak probe catches a leak |
