# Programme Status — V2 / V2.1 / V2.2 / V2.3 Alpha Research

**Effective 2026-08-08. This document is the authoritative status of the alpha
research programme.**

| | |
|---|---|
| **Research status** | **CLOSED** |
| **Production** | weight **0**, action **HOLD** |
| **Exam** | **SEALED** — 72 cutoffs, digest `b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, never opened |
| **Architecture** | **ABANDONED** |
| **V2.4** | **NOT STARTED, AND NOT AUTHORIZED BY THIS DOCUMENT** |
| Independent audit | 2026-08-08, closure **confirmed** by re-derivation |
| Evidence | preserved under version control at this commit |

---

## 1. What was done

Four pre-registered studies, eleven fitted arms, and a full rebuild of the
validation protocol.

| Study | Question | Result |
|---|---|---|
| **V2** | Does a wider cross-sectional feature set rank the cross-section? | Null. 47 relative/percentile features moved mean IC from +0.0084 to +0.0085 |
| **V2.1** | Rebuilt on 72 frozen cutoffs against 12-1 momentum. Does any arm beat it? | Null. Best arm +0.01312, CI [−0.01862, +0.05006]. **Gate closed; exam sealed** |
| **V2.2** | Does routing the factor around the learner preserve it? | Null. All four grid cells within 0.0023 of zero. One arm (B) showed +0.00241 |
| **V2.3** | With the collinearity removed, does a bounded tilt add anything? | **Null, and backwards.** +0.00241 → −0.00052. All five gates failed for both arms |

## 2. Why it closed

`V2_3_PREREGISTRATION.md` §9 fixed six abandonment criteria before the first fit.

**Criterion 6 is met in its exact pre-registered form** — "ρ̄ ≤ 0.90 achieved and
still no advantage over base." Mean |ρ(u, base)| fell to **0.6981** and **0.7033**,
both under the ceiling, and the advantage over base was **−0.00052** and
**−0.00120**. Under §9 this criterion alone ends the architecture.

**Criteria 4 and 5 are met jointly and independently** — a G5 sign flip
(+0.01273 → −0.00075) and a fourth consecutive `BEAR_TREND` concentration on 27
cutoffs, 63% of them in 2022.

**Criterion 2 is not relied upon.** Its operative clause is satisfied and its point
estimate is negative, but its precision premise (≈0.004 half-width) was not reached —
0.00796 was achieved. Clarified 2026-08-08; see `V2_3_LADDER_REPORT.md` §8. **Cite
criterion 6.**

The decision rests on **two independent sufficient grounds** with or without
criterion 2.

Beyond the criteria: the maximum advantage over base available anywhere on either λ
curve is **+0.00045**, against a measured resolution of **0.00827**. No tilt pays for
its own trading (net advantage +0.00028 and +0.00002, intervals spanning zero,
turnover up 36–56%).

## 3. Current conclusion

**The tested architecture family did not demonstrate reliable incremental predictive
information over momentum.**

The strongest thing the programme produced is a **three-line hand-specified regime
switch with nothing fitted** (B3, +0.02836) — the only benchmark whose confidence
interval excludes zero. Eleven fitted arms did not beat it.

## 4. Important boundary

**This does NOT establish that stock prediction is impossible.**

It establishes a much narrower conclusion:

> Within the tested universe, history, cross-sectional formulation, target/horizon
> and current price/volume-derived feature space, the investigated learning
> architectures did not demonstrate reliable incremental predictive value over the
> momentum baseline or the B3 regime rule.

What was **not** tested is untouched, not vindicated: other data (fundamentals,
flows, holdings, news), other horizons, other universes, longer history, and
non-cross-sectional formulations. Nothing in four studies suggests they would fare
better, and the power arithmetic applies to any of them — resolving an effect the
size of V2.3-B's would need ~11,000 non-overlapping weekly cutoffs. **Ten years of
history cannot settle questions of this size; the effects measured here are absent,
not under-measured.**

## 5. Future research

**No architecture research is authorized by this document.**

Future research, if undertaken, must first **introduce and justify a genuinely new
information dimension or problem formulation** rather than another learner over
substantially the same information. The four studies already ran that experiment
four ways — factor in the input, in the target, around the learner, and as a bounded
tilt on a decoupled adjustment — and the binding constraint was never the
architecture. It was that `E[target_rank | z__ret_12_1]` spans 0.023 while the
learner's leaf-mean noise floor is 0.029: **the signal is narrower than the
instrument.**

## 6. Standing prohibitions

Carried forward from `V2_1_LADDER_PREREGISTRATION.md` §5.2 and
`V2_3_PREREGISTRATION.md` §9, and unchanged by closure:

* the 72 exam cutoffs are not opened, scored, inspected, modified, deleted or rebuilt;
* production weight is not raised and `adapter.py` is not modified to force a signal;
* no threshold is lowered, no λ re-chosen, no benchmark swapped, no B3 modified;
* no rung, λ point or noise control is promoted to an arm;
* no result is restricted to a regime bucket to make it survive;
* development numbers are not reported as alpha.

## 7. Verification state at closure

Every line below was executed, not asserted. Commands and expected output:
[`V2_3_REPRODUCTION_CHECKLIST.md`](V2_3_REPRODUCTION_CHECKLIST.md).

| Check | Result |
|---|---|
| Exam digest, **recomputed** from the cutoff list | `b55e065f…` — matches, 72 cutoffs |
| `v2_1_exam_predictions.json` / `_scores.json` | **do not exist** |
| `alpha.v2_1_exam predict` | refuses on the closed §5.2 gate, exit 1 |
| Exam contamination across ten frozen series | **0** |
| Production weight, by executing the cascade | **0.0**, all seven criteria False |
| **V2.3-B vs B3**, re-derived from per-cutoff series | **−0.00120**, breadth 0.451, halves −0.00034 / −0.00206 |
| Test suite | **625 passed**, none skipped (155 of them the research record) |

## 8. Where the record lives

| Path | What |
|---|---|
| `alpha/` | 25 modules, 15 protocol documents, frozen artefacts with per-cutoff series |
| `app/tests/test_alpha*.py` | 155 tests |
| `reports/V2_3_EVIDENCE_MANIFEST.md` | what is preserved, what is excluded and why, with SHA-256 |
| `reports/V2_3_REPRODUCTION_CHECKLIST.md` | eight checks, tiered by what they depend on |
| `reports/V2_3_FINAL_DECISION_AUDIT.md` | the independent audit |
| `reports/V2_3_POST_MORTEM.md` | the retrospective — belief chain, reasoning errors, what is settled |
| `reports/directives/` | the directives each study was commissioned under |

## 9. Two open items, neither affecting this status

1. **The `origin` remote is a third party's public repository**
   (`huseinzol05/Stock-Prediction-Models`). This commit was **not pushed**. Repoint
   the remote to a repository the author owns before any push, or keep this branch
   local permanently. See `V2_3_EVIDENCE_MANIFEST.md` §5.1.
2. **`validation/` — the point-in-time backtest study — remains untracked.** It is a
   distinct study, out of scope for this closure, and it has not been preserved. It
   needs its own decision.

---

**The programme's output is not a model. It is a sealed exam, a pre-registration
discipline that held under four consecutive disappointments, 625 tests, and a short
list of things now known to be false. Failure was pre-registered as a first-class
outcome, and this is that outcome, recorded as one.**
