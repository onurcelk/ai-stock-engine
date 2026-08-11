# AMS-1 — Agent Meta-Signal Study: pre-registration

**Frozen 2026-08-11, committed BEFORE any AMS-1 forward return was read, before
any consensus bucket was counted against an outcome, and before any gate
statistic existed.** Stage 1 (`reports/AGENT_META_AUDIT.md`) was committed
first; this document may not be edited afterwards, only appended to with dated
corrections (CLAUDE.md §1.1).

> **The question.** Even if individual trading agents are weak, does agreement
> among *algorithmically distinct* trading-agent families identify situations
> where a single-stock 5-session prediction becomes materially more reliable?

This is the repository's original multi-agent thesis, and AMS-1 is the first
study to put the burden of proof on it directly.

**What AMS-1 is not.** It is not "which agent is best". Individual agent
accuracy is a secondary diagnostic and no agent is admitted or dropped on the
strength of it — a weak agent that supplies diversity is exactly what the thesis
needs, and a strong agent that duplicates another family adds nothing.

---

## §0 Standing

| | |
|---|---|
| Prior results | **Unchanged.** Production weight 0.0; Single-Name Phase 1 failed all four gates; B3 did not solve absolute 5D prediction; S0/S1 remain the absolute incumbents; no prior arm produced a meaningful SELL population; Family-10 failed admissibility on power with no slot spent |
| Budget | AMS-1 spends **no information-family slot**. It opens no external data source and re-uses only agents already in this repository |
| Exam | **SEALED**, `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`. Not loaded, not scored, not inspected. AMS-1 runs on the 316 development cutoffs only |
| Horizon | **5 sessions**, inherited from `alpha/targets.py`. **No second horizon is computed anywhere in AMS-1** |
| Target | `asset_return` — the absolute forward return, not `alpha_5d` |

## §1 Admissible roster — frozen by the Stage 1 audit

The audit measured, rather than assumed, that all 19 reinforcement-learning
agents are point-in-time **inadmissible as the repository implements and uses
them**: `BaseAgent.__init__` takes the whole close series, `train()` maximises
`_simulate()` over that whole series, and `signals()` replays the fitted policy
from bar 0. Rewriting the future moved **47%–71% of past signals**.

They are therefore **reconstructed** rather than admitted. Reconstruction costs
were measured before any outcome existed, and they decide which families AMS-1
can carry:

| family | agents | one fit, 500 bars | status |
|---|---:|---:|---|
| `A_RULE` | 3 | 0 s — closed form | **admitted** |
| `E_EVOLUTIONARY` | 3 | 6.7 s | **admitted** |
| `D_POLICY_GRADIENT` | 1 | 8.5 s | **admitted** |
| `F_CURIOSITY_RL` | 3 | 43.1 s | excluded |
| `C_ACTOR_CRITIC` | 4 | 166.9 s | excluded |
| `B_VALUE_RL` | 8 | 175.4 s | excluded |

**Three families, seven agents.** The exclusions are on measured cost, recorded
in the audit before any outcome was read, and they are **not** revisable on the
strength of a result. `reports/AGENT_META_AUDIT.md` §6 states what the exclusion
costs the study and why it cannot be repaired within this programme's budget.

## §2 Point-in-time construction

```
policy at cutoff t   trained on the 500 bars before the most recent refit
                     boundary, which is itself <= t
inputs at t          the trailing 30-bar price window ending at t
refit boundaries     the first development cutoff of each calendar year
calibration at t     labels whose forward windows closed EMBARGO sessions
                     before t, via singlename.PastOutcomes (raises, never trims)
```

Bars before an agent's first admissible policy are **absent**, not HOLD.
`alpha/ams1_signals.py` is the only producer of agent stances and it reads no
return.

**Signal normalisation.** Every agent's event series is forward-filled into a
standing position in `{+1, 0, -1}` by `app/core/indicators.stance`, the
repository's own tested function. For the RL agents the *raw policy action* is
read rather than `BaseAgent.signals()`, because that method suppresses SELL
whenever inventory is empty — a suppressed SELL is not a HOLD, it is a SELL the
bookkeeping refused to print. No threshold anywhere was set by future accuracy.

**Symbols.** Eligibility is a data-availability filter (a name must appear at
≥100 of the 316 development cutoffs); the sample is then 100 names drawn with
frozen seed `20260811`. Neither step consults a return.

## §3 Meta-signals — frozen

| | definition |
|---|---|
| **M0** raw BUY fraction | BUY agents / available agents, over all 7 |
| **M1** raw net vote | mean agent stance, over all 7 |
| **M2** family BUY fraction | families voting BUY / families present |
| **M3** family net vote | mean family vote — **the ladder's coordinate** |
| **M4** agreement strength | `abs(M3)`; 1 is unanimity |
| **M5** diversity-weighted | M3 with per-family weights `1 − mean between-family exact agreement`, taken from the Stage 1 redundancy measurement. **Signal-derived, never outcome-fitted** |
| **M6** disagreement | normalised Shannon entropy of the family votes; the NO EDGE candidate |

**Family vote rule, frozen:** `family vote = sign(mean(stances of that family's
admissible agents))`. A mean of exactly zero votes 0 and is a genuine
abstention. **One family, one vote** — `E_EVOLUTIONARY`'s three implementations
cannot outvote `D_POLICY_GRADIENT`'s one. A row receives a consensus state only
when all three families are present.

## §4 Consensus ladder — boundaries are arithmetic, not fitted

Three ternary votes make M3 take only the values
`{-1, -2/3, -1/3, 0, 1/3, 2/3, 1}`. The five ordered states are:

```
strong bearish    M3 == -1     (unanimous SELL)
moderate bearish  -1 < M3 < 0
mixed             M3 == 0
moderate bullish   0 < M3 < 1
strong bullish    M3 == +1     (unanimous BUY)
```

No boundary was placed by looking at a hit rate and none may be moved after one
is seen. The same five states are computed from the **raw** agent vote for the
H2 comparison.

**A structural fact about the ladder, measured from signals before any outcome
was read.** A family votes 0 only when its agents' stances average exactly zero,
and on this roster that almost never happens — the family-vote balance is
`A_RULE` 46.2/0.0/52.9, `D_POLICY_GRADIENT` 47.6/0.1/49.8, `E_EVOLUTIONARY`
39.7/0.1/57.7 (buy/flat/sell). The `mixed` state therefore holds **20 rows on 2
dates**, against 3,275–12,021 rows on 314–316 dates for the other four.

**Rule, fixed here and not later:** a ladder state enters the Gate 3
monotonicity statistic only if it meets §7's minimum geometry. That is §7's own
criterion — *"minimum geometry for a ladder state to count as a **result**
rather than a diagnostic"* — applied to the statistic it was written for.
`mixed` is reported in every table as a diagnostic and is excluded from the rank
correlation, because a 20-row point would otherwise inject pure noise into a
five-point Spearman. The four surviving states remain strictly ordered, so the
hypothesis H1 is unweakened: **strong bearish < moderate bearish < moderate
bullish < strong bullish** is still the claim.

## §5 Baselines — frozen

| | |
|---|---|
| **B0** | walk-forward base rate (Single-Name `S1`) |
| **B1** | 12-1 momentum rank, walk-forward logistic (`S2`) |
| **B2** | B3 rank, walk-forward logistic (`S3`) |
| **B3** | B3 × market state (`S4`) — **the primary incumbent**, SN-1's best probabilistic arm |
| **B4** | naive **raw** agent vote, walk-forward logistic on M1 |
| **B5** | equal-weight **family** consensus, five shrunk bucket rates (shrinkage 50, frozen) |

AMS-1's own arms, and the complete list of them:

| | |
|---|---|
| **AMS-C** | calibrated family consensus — walk-forward logistic on M3 |
| **AMS-I** | incumbent logit **+** M3, two coefficients, walk-forward |
| **AMS-A** | AMS-C restricted to unanimous rows; everything else NO EDGE |

**Eight arms in total, declared here.** No subset search, no genetic ensemble,
no learned agent weights, no post-hoc bucket thresholds, no "best 3 agents".

## §6 Hypotheses

* **H1 consensus monotonicity** — `P(up)` rises monotonically across the five
  ordered states. *The central hypothesis.*
* **H2 family > raw** — family-aware agreement carries more usable information
  than raw vote count.
* **H3 strong consensus** — unanimity scores materially better than mixed.
* **H4 disagreement → NO EDGE** — abstaining where families disagree improves
  conditional quality at usable coverage.
* **H5 bearish consensus** — unanimous SELL produces a materially lower
  conditional up-rate; the prize is a credible `P(up) < 0.50`.
* **H6 incremental value** — consensus adds information beyond base rate,
  momentum, B3 and market state.

## §7 Power — frozen before any half-width was computed

Uncertainty instrument: **paired per-cutoff moving-block bootstrap**, block
length **4 cutoffs (~one month)**, 10,000 draws — `alpha/stats.py`'s own
constants, inherited because AMS-1 runs on exactly the grid they were written
for. Cutoffs are spaced one horizon apart, so outcome windows are adjacent and
non-overlapping by construction; the block absorbs the market's own persistence.

Resolution is computed from the marginal properties of the target already
committed in `alpha/source_probe.py` (`sd 0.04526`, `ρ 0.2916`, `up-var 0.24783`,
`up-ρ 0.1778`, inflation `1.077`) — no feature, no conditioning, no AMS-1
outcome.

Minimum geometry for a ladder state to count as a **result** rather than a
diagnostic: **2,000 rows, 100 cutoffs, 50 symbols**.

### §7.1 The gate, computed from signal geometry alone

**31,600 cells — 100 symbols × 316 development cutoffs.** Measured before any
outcome was read (`alpha/out/ams1_power_gate.json`):

| state | rows | coverage | dates | symbols | rows/date | **directional MDE** | **economic MDE** | meets §7 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| strong bearish | **5,449** | 17.7% | 314 | 100 | 17.35 | **2.81 pp** | **31.1 bp** | yes |
| moderate bearish | 12,021 | 39.0% | 316 | 100 | 38.04 | 2.64 pp | 29.9 bp | yes |
| mixed | 20 | 0.1% | 2 | 20 | 10.00 | 37.89 pp | 406.7 bp | **no** |
| moderate bullish | 10,036 | 32.6% | 316 | 100 | 31.76 | 2.67 pp | 30.1 bp | yes |
| strong bullish | **3,275** | 10.6% | 314 | 100 | 10.43 | **3.00 pp** | **32.3 bp** | yes |

```text
GATE 1 (POWER): PASS
```

Both extreme states clear the minimum geometry on all three counts and resolve
to about **3 pp** on the up-rate and **31 bp** on the mean return — sharper than
Phase 1's 39 bp, because 316 dates buy more resolution than 177 did.

What that resolution implies for the two claims that matter, stated **before**
the outcomes:

* **H1 / Gate 3.** The `strong bullish − strong bearish` gap must exceed its own
  half-width; at these geometries that is a gap of roughly **4 pp**.
* **H5 / Gate 9.** `P(up | strong bearish) < 0.50` with the interval's upper end
  below 0.50 requires the observed rate to sit near **0.472 or lower** — a
  **6.5 pp** shift from the 0.537 base rate. This is the prize and it is not
  guaranteed; it is, however, inside the instrument, which is more than Phase 1
  could say.

## §8 Acceptance gates — numeric, frozen, not adjustable after a result

| # | gate | threshold |
|---|---|---|
| **1** | **Power** | both extreme states clear §7's minimum geometry, and the directional half-width on each is smaller than the shift the state actually needs |
| **2** | **Probabilistic value** | AMS-C beats the primary incumbent B3 on paired per-cutoff **log loss** by **≥ 0.001** with a 95% block-bootstrap interval excluding 0 |
| **3** | **Monotonicity** | Spearman of `P(up)` against the ordered states meeting §7's minimum geometry **≥ 0.90**, and `strong bullish − strong bearish` exceeds its own half-width |
| **4** | **Family > raw** | AMS-C beats B4 (raw vote) on paired log loss with the interval excluding 0 |
| **5** | **Incremental** | AMS-I beats B3 on paired log loss by **≥ 0.001** with the interval excluding 0 |
| **6** | **Abstention** | AMS-A improves log loss versus AMS-C on all rows while retaining **≥ 10%** coverage |
| **7** | **Breadth** | **≥ 100 symbols and ≥ 100 cutoffs** in each extreme state |
| **8** | **Stability** | no sign inversion of the extreme-state effect between the first and second halves of the development period |
| **9** | **Bearish utility** | `P(up \| strong bearish) < 0.50` with the 95% interval's upper end below 0.50 — **or** AMS-1 is explicitly classified one-sided. A BUY-only model may not be described as a symmetric predictor |

The 0.001 threshold is not invented here: SN-1's measured paired log-loss
half-width against S1 was **0.00096** (`reports/EXPERIMENT_REGISTRY.md` §9.4),
so a smaller improvement is inside this panel's resolution and is not a result.

**Multiplicity.** Holm-Bonferroni across the nine primary gate statistics. The
pre-declared diagnostic set is small and fixed: three leave-one-family-out runs,
six meta-signals, five ladder states. Nothing else is searched.

**Verdict rule.** `AMS-1 VERDICT: ADVANCE` requires Gates 1–5, 7 and 8. Gate 6
and Gate 9 are reported and, if Gate 9 fails, the system is classified
**one-sided** rather than the gate being waived. Anything else is
`AMS-1 VERDICT: REJECT`.

## §9 Leave-one-family-out

Run once per family. **Diagnostic only** — it may not be used to construct a
better ensemble, and no family is dropped from the primary construction on the
strength of what it shows. Its purpose is one question: is the consensus
distributed, or is one family carrying all of it?

## §10 What a failure means, fixed in advance

If cross-family agreement among the admissible families moves neither the
conditional up-rate nor the mean return at this panel's resolution, then **the
original multi-agent thesis is not supported at measurable resolution on free
data at this horizon**, and the programme says so. The correct next steps are
then horizon redesign, external information, or ending the free-data single-name
programme — not another ensemble.

A specific claim that may **not** be made after a null: that the excluded
families B, C and F would have rescued it. The audit records that four of those
fifteen agents are degenerate at the repository's own default iteration counts
— Actor-critic votes BUY on 98.5% of bars, Actor-critic duel recurrent votes on
0% — and a constant is not an opinion.

## §11 If AMS-1 advances

Stop at `AMS-1 ELIGIBLE FOR SEALED EXAM`. Do not run the exam. The next study is
**AMS-2, a calibrated agent meta-predictor** using a small regularised
family-level model — not an unconstrained neural meta-model and not learned
agent weights.
