# AMS-1 — Agent Meta-Signal Study: development result

**Written 2026-08-11.** Development set only. The sealed exam
(`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`) was **not
loaded, not scored, not inspected**. Production weight remains **0.0**. **No
information-family slot was spent** — AMS-1 opened no data source. Nothing was
pushed.

Stage 1 audit committed at `c493a5b`; pre-registration and power gate at
`229990c`, **before any forward return was read**; this result is the third and
final commit.

Reproduce:

```
./venv/Scripts/python.exe -W ignore -m alpha.ams1_run     # writes predictions
./venv/Scripts/python.exe -W ignore -m alpha.ams1_score   # reads outcomes
```

> ```text
> AMS-1 VERDICT: REJECT
> ```
>
> Cross-family trading-agent agreement does **not** contain measurable
> incremental information for single-name 5-session prediction on this panel.
>
> **And the direction is the opposite of the hypothesis.** Across the four
> populated consensus states `P(up)` is **perfectly monotone downwards**
> (Spearman **−1.00**): unanimous SELL is followed by an up-move **56.3%** of the
> time, unanimous BUY **53.0%**. The gap is **−3.28 pp** where H1 required it
> positive — but its paired interval is **[−4.34, +1.82] pp**, so the inversion
> itself is *not* significant either. The honest reading is not "the agents are
> contrarian"; it is **"the agents carry no directional information, and what
> little structure there is points the wrong way."**

---

## The fifteen questions, answered

| | question | answer |
|---|---|---|
| **A** | How many actual agents exist? | **22 implemented** (3 rule-based + 19 RL, which are 6 implementations); 4 more exist only as notebooks |
| **B** | How many are PIT-admissible? | **3 outright**, **4 more after reconstruction** = **7**. The other 15 are excluded |
| **C** | How many genuinely distinct families remain? | **3** — `A_RULE`, `D_POLICY_GRADIENT`, `E_EVOLUTIONARY` |
| **D** | How redundant are the agents internally? | **They are not.** Zero of 231 pairs are near-clones; effective opinions 22 of 22 |
| **E** | Does raw vote count contain predictive information? | **No.** Raw unanimity reaches 0.7% / 0.5% coverage and its extremes miss the minimum geometry entirely |
| **F** | Does family consensus contain more than raw vote? | **No.** Paired log-loss difference **−0.000031**, interval **[−0.00027, +0.00015]** |
| **G** | Is `P(up)` monotonic with cross-family agreement? | **Yes — inverted.** Spearman **−1.00** over the four populated states |
| **H** | `P(up)` under strong BUY consensus? | **0.5298** [0.5059, 0.5809] — **below** the 0.5435 base rate |
| **I** | `P(up)` under strong SELL consensus? | **0.5626** [0.5212, 0.5868] — **above** the base rate |
| **J** | Any credible sub-50% SELL population? | **No.** The strong-SELL up-rate is 6.3 pp *above* 0.50, and its interval's lower end is 0.5212 |
| **K** | Does disagreement create useful NO_EDGE observations? | **Technically yes, substantively no** — see Gate 6 below |
| **L** | Does consensus add value beyond momentum / B3 / market state? | **No.** AMS-I is **worse** than the incumbent by +0.00047 log loss |
| **M** | Are results broad across symbols and dates? | **Yes** — 100 symbols, 214–215 cutoffs in both extreme states |
| **N** | Does one family dominate the result? | **No.** Dropping any one family leaves the same inversion |
| **O** | Is the original multi-agent thesis supported? | **No** |

---

## 1. What was run

| | |
|---|---|
| Panel | **19,173 scored rows**, 100 symbols × **215 evaluation cutoffs** (2018-01 … 2026-07) |
| Roster | 7 agents in 3 families, each policy trained on the 500 bars before its most recent annual refit boundary |
| Base up-rate | **0.5435** · base mean return **+19.4 bp** |
| Arms | 6 baselines + 3 AMS arms, all declared in §5 of the pre-registration |
| Instrument | paired per-cutoff moving-block bootstrap, block 4 cutoffs, 10,000 draws |

## 2. Model comparison

| model | log loss | Brier | accuracy | coverage |
|---|---:|---:|---:|---:|
| **B0** base rate | 0.69036 | 0.24860 | 0.5432 | 1.00 |
| **B1** momentum | 0.69038 | 0.24861 | 0.5432 | 1.00 |
| **B2** B3 | **0.69032** | **0.24858** | 0.5432 | 1.00 |
| **B3** B3 × market state *(primary incumbent)* | 0.69096 | 0.24889 | 0.5429 | 1.00 |
| **B4** raw agent vote | 0.69040 | 0.24862 | 0.5432 | 1.00 |
| **B5** family buckets | 0.69044 | 0.24864 | 0.5432 | 1.00 |
| **AMS-C** calibrated family consensus | 0.69037 | 0.24861 | 0.5432 | 1.00 |
| **AMS-I** incumbent + consensus | 0.69143 | 0.24911 | 0.5430 | 1.00 |
| **AMS-A** consensus + abstention | 0.68809 | 0.24747 | 0.5527 | **0.28** |

**Every arm is within 0.001 of every other**, and every accuracy equals the base
rate to three decimals — because **no arm ever emits a probability below 0.5**.
The whole probability range across 19,173 rows is **0.542 → 0.562**. This is
Single-Name Phase 1's central finding reproduced exactly, now with agents
instead of B3.

## 3. The consensus ladder — the primary table

| family agreement | N | coverage | dates | symbols | **P(up)** | 95% CI | mean 5D return | CI | Brier | log loss |
|---|---:|---:|---:|---:|---:|---|---:|---|---:|---:|
| **strong bearish** | 3,299 | 17.2% | 214 | 100 | **0.5626** | [0.5212, 0.5868] | **+35.3 bp** | [−30.2, +56.1] | 0.24652 | 0.68619 |
| moderate bearish | 7,362 | 38.4% | 215 | 100 | 0.5417 | [0.5127, 0.5682] | +20.8 bp | [−15.1, +50.5] | 0.24891 | 0.69098 |
| *mixed* | *0* | — | — | — | — | — | — | — | — | — |
| moderate bullish | 6,266 | 32.7% | 215 | 100 | 0.5402 | [0.5118, 0.5746] | +15.8 bp | [−18.4, +56.3] | 0.24885 | 0.69085 |
| **strong bullish** | 2,131 | 11.1% | 214 | 100 | **0.5298** | [0.5059, 0.5809] | **−0.3 bp** | [−47.9, +51.2] | 0.24954 | 0.69224 |

**Spearman −1.00 over the four populated states. Perfectly ordered, and
perfectly backwards.** The `mixed` state is empty at scoring time — the power
gate had already recorded, before any outcome, that a family almost never
abstains and that state holds 20 rows on 2 dates.

The return column runs the same way: **+35.3 bp** after unanimous SELL against
**−0.3 bp** after unanimous BUY.

### 3.1 Directional extremes, paired

| contrast | mean | 95% CI | |
|---|---:|---|---|
| `P(up \| strong bullish) − P(up \| strong bearish)` | **−1.10 pp** | [−4.34, +1.82] | not significant |
| mean 5D return, same contrast | **−10.2 bp** | [−52.9, +25.7] | not significant |

The pre-registered half-width was 3.0 pp; the realised paired half-width is
3.08 pp. **The instrument performed as designed — there was simply nothing above
it in the intended direction, and nothing significant below it either.**

## 4. Raw consensus versus family consensus — the mandatory comparison

| | strong bearish | strong bullish |
|---|---|---|
| **family** ladder (3 families) | 3,299 rows · 17.2% · 214 dates | 2,131 rows · 11.1% · 214 dates |
| **raw** ladder (7 agents) | **132 rows · 0.7% · 86 dates** | **89 rows · 0.5% · 58 dates** |

Raw unanimity across all seven agents is **almost unreachable** — which is
itself the answer to the study's motivating example. `18 / 22 agents BUY` is not
a strong signal here; it is a rare accident, and it does not survive the minimum
geometry (2,000 rows / 100 dates / 50 symbols) that §7 fixed in advance.

Where raw unanimity does occur it points the same way as the family ladder:
`P(up | raw strong bullish) = 0.4831` on 89 rows, `P(up | raw strong bearish) =
0.5152` on 132.

**Gate 4, the family-versus-raw test, fails on a paired log-loss difference of
−0.000031 with interval [−0.00027, +0.00015].** Family aggregation neither helps
nor hurts, because **there is nothing to aggregate**: the Stage 1 audit measured
that the agents are not duplicates of each other, so collapsing them into
families removes no double-counting. The premise the raw-versus-family
distinction was built on is absent from this repository.

## 5. Individual agents — secondary, and reported without acting on it

| agent | family | n | share BUY | `P(up \| BUY)` | `P(up \| SELL)` |
|---|---|---:|---:|---:|---:|
| Turtle | A_RULE | 19,173 | 0.435 | 0.5357 | **0.5495** |
| Moving average crossover | A_RULE | 19,173 | 0.573 | 0.5523 | 0.5317 |
| Signal rolling | A_RULE | 19,173 | 0.466 | 0.5406 | **0.5461** |
| Policy gradient | D | 19,058 | 0.487 | 0.5350 | **0.5518** |
| Evolution strategy | E | 19,058 | 0.436 | 0.5328 | **0.5519** |
| Neuro-evolution | E | 19,058 | 0.449 | 0.5405 | **0.5460** |
| Neuro-evolution (novelty) | E | 19,058 | 0.432 | 0.5478 | 0.5402 |

Base rate **0.5435**. Every agent sits within ~1 pp of it on both sides, and
**five of seven are individually inverted** — their SELL is followed by more
up-moves than their BUY. No agent was dropped for this, per the pre-registration:
weak individual agents are exactly what the ensemble hypothesis is allowed to
use. But an ensemble of seven signals that individually point the wrong way does
not become right by agreeing.

## 6. Leave-one-family-out — diagnostic only

| family dropped | unanimous rows | bullish `P(up)` | bearish `P(up)` |
|---|---:|---:|---:|
| `A_RULE` removed | 9,824 | 0.5319 | **0.5589** |
| `D_POLICY_GRADIENT` removed | 10,227 | 0.5343 | **0.5474** |
| `E_EVOLUTIONARY` removed | 9,866 | 0.5382 | **0.5554** |

**No family carries the result.** Every two-family combination reproduces the
same inversion at the same magnitude. This was run once per family as declared
and was **not** used to construct a better ensemble.

## 7. Abstention — Gate 6

| | N | coverage | accuracy | Brier | log loss | `P(up)` | mean return |
|---|---:|---:|---:|---:|---:|---:|---:|
| all rows | 19,173 | 100% | 0.5432 | 0.24861 | 0.69037 | 0.5435 | +19.4 bp |
| **retained** (unanimous) | 5,430 | **28.3%** | 0.5527 | 0.24747 | **0.68809** | 0.5497 | +21.4 bp |
| abstained | 13,743 | 71.7% | 0.5390 | 0.24909 | 0.69134 | 0.5411 | +18.7 bp |

Gate 6 **passes as written** — log loss improves by 0.0023 at 28.3% coverage.
**It should not be read as a success, and the pre-registration's own framing is
why.** The retained set's accuracy of 0.5527 is almost exactly its own base rate
of 0.5497, because the arm calls "up" on every row it keeps. Abstention did not
find rows where the model predicts better; it found rows that **drift up more**.
The paired log-loss change is **−0.0023 [−0.0053, +0.0004]** — its interval
includes zero.

This is the one gate that passes and it passes for a reason that does not
support the thesis.

## 8. Calibration

**ECE 0.01488** — but the whole probability range is 0.542–0.562, so there are
only two occupied bins:

| stated | observed | n |
|---:|---:|---:|
| 0.5421 | **0.5463** | 6,346 |
| 0.5623 | **0.5421** | 12,827 |

**The higher-confidence bin is the less accurate one.** Where AMS-C says 56.2%
the realised rate is 54.2%; where it says 54.2% the realised rate is 54.6%. The
calibration is adequate in aggregate and has **no resolution whatsoever** —
identical in shape to Single-Name Phase 1's, where 98.1% of mass fell in one bin.

## 9. Stability — Gate 8

| | cutoffs | strong bullish `P(up)` | strong bearish `P(up)` |
|---|---:|---:|---:|
| first half | 107 | 0.5235 (n=978) | **0.5583** (n=1,594) |
| second half | 108 | 0.5351 (n=1,153) | **0.5666** (n=1,705) |

**There is no regime inversion — and that is the problem.** The effect is stable
across both halves *in the wrong direction*. Gate 8 as written requires the
hypothesis's direction to hold in both halves; it holds in neither, so the gate
fails. Reported both ways so neither reading can be quoted alone.

## 10. Gate table

| # | gate | requirement | measured | |
|---|---|---|---|---|
| **1** | Power | extremes clear 2,000 rows / 100 dates / 50 symbols | 3,299 & 2,131 rows, 214 dates, 100 symbols | **PASS** *(pre-outcome)* |
| **2** | Probabilistic value | AMS-C beats B3 by ≥0.001 log loss, interval excluding 0 | **−0.00059** [−0.00310, +0.00145] | **FAIL** |
| **3** | Monotonicity | Spearman ≥ +0.90 and a positive extreme gap | **−1.00**, gap **−1.10 pp** [−4.34, +1.82] | **FAIL** |
| **4** | Family > raw | AMS-C beats B4, interval excluding 0 | **−0.000031** [−0.00027, +0.00015] | **FAIL** |
| **5** | Incremental | AMS-I beats B3 by ≥0.001, interval excluding 0 | **+0.00047** (worse) [−0.00047, +0.00100] | **FAIL** |
| **6** | Abstention | log loss improves at ≥10% coverage | 0.68809 vs 0.69037 at 28.3% | **PASS** *(see §7)* |
| **7** | Breadth | ≥100 symbols and ≥100 cutoffs in each extreme | 100 symbols, 214 cutoffs | **PASS** |
| **8** | Stability | no directional inversion between halves | stably inverted in both | **FAIL** |
| **9** | Bearish utility | `P(up \| strong bearish) < 0.50`, CI upper below 0.50 | **0.5626** [0.5212, 0.5868] | **FAIL** |

Holm correction was prepared for the nine primary statistics and is **not
needed**: no gate produced an uncorrected result that would have survived it.

**Per §8's verdict rule** — ADVANCE requires Gates 1–5, 7 and 8 — four of those
seven fail.

```text
AMS-1 VERDICT: REJECT
```

## 11. What this establishes, and what it does not

**Established.** On this universe, at 5 sessions, with free data and the trading
agents this repository actually contains, agreement among algorithmically
distinct agent families does **not** identify situations where a single-name
prediction becomes more reliable. The instrument resolved ~3 pp on the up-rate
and ~31 bp on the mean return — sharper than Phase 1 — and found nothing above
it. The original multi-agent thesis has now been tested directly and it is not
supported.

**Two findings that outlive the verdict.**

1. **The redundancy premise was wrong, and its failure explains the result.**
   The study was designed around "ten Q variants are one opinion". Stage 1
   measured the opposite: zero near-clones in 231 pairs, mutual information
   0.015–0.060 bits of a possible 1.585, pairwise correlations from −0.09 to
   +0.08. The agents are not duplicates — they are **independent of each other
   *and* of the future**. Agreement among independent noise sources is a
   binomial coincidence, and that is what the ladder measured.

2. **Unanimity is reachable at family level and not at agent level.** Three
   families agree unanimously on 28.3% of rows; seven agents agree unanimously
   on 1.2%. Any product surface that shows "18 of 22 agents agree" as a
   confidence signal is displaying an artefact of counting correlated-by-chance
   votes, not evidence. **This applies to the app's Trading-agents tab as it
   stands.**

**Not established.** Whether the fifteen excluded agents would behave
differently. Per §10 of the pre-registration that claim may not be made after a
null — and the audit already recorded that four of the fifteen are degenerate at
the repository's own default iteration counts, with `Actor-critic` emitting BUY
on 98.5% of bars and `Actor-critic duel recurrent` emitting nothing at all.

**Explicitly not claimed: that the signal works inverted.** Flipping the sign
after seeing a negative result is the sign-fitting this programme's protocol
exists to prevent, and the inversion is not significant in any case
(gap −1.10 pp, interval [−4.34, +1.82]).

## 12. Recommended next step

Per §10 of the pre-registration, the multi-agent idea has now been properly
tested and the remaining routes are horizon redesign, external information, or
ending the free-data single-name programme. Given that:

* Family-10 established that an **event-time** design on this window has a
  half-width floor of **49 bp** at a defensible block length;
* Single-Name Phase 1 established that a **weekly-grid** design has a floor near
  39 bp and never produced a probability below 0.5;
* AMS-1 now establishes that **agent agreement adds nothing** to either;

the recommendation is **not** AMS-2. Three independent designs have now hit the
same wall, and the wall is the information content of free daily price data on a
5-session horizon for single names.

> **Recommended next step: close the free-data single-name programme and, if the
> account holder wishes to continue, re-scope to the one question none of these
> studies could address — whether a longer horizon changes the answer — under a
> fresh charter with its own power gate computed first.**

AMS-1 does not authorise that study; it only says which question is left.

## 13. Artefacts

| file | content |
|---|---|
| `alpha/ams1_run.py` | the walk-forward prediction side |
| `alpha/ams1_score.py` | the scorer and every gate |
| `alpha/out/ams1_predictions.pkl` | 19,173 frozen predictions, written before any outcome was joined |
| `alpha/out/ams1_result.json` | every number quoted above |
| `app/tests/test_ams1_meta.py` · `test_ams1_audit.py` | 60 tests |
