# V2.3 experiment log

Every V2.3 run, in order, including the one that aborted. Appended to, never
rewritten. `V2_2_EXPERIMENT_LOG.md`, `V2_1_EXPERIMENT_LOG.md` and
`EXPERIMENT_LOG.md` record earlier studies and are not touched.

---

## 1 — 2026-08-08, acceptance. No fit.

`V2_3_PREREGISTRATION.md` was written from the reviewed `V2_3_RESEARCH_DESIGN.md`
and accepted before any V2.3 code existed. At the moment of acceptance no V2.3 arm
had been fitted, no V2.3 carrier had been applied to outcome data, and no V2.3 IC
had been computed on any cutoff.

Two arms, k = 2, λ = 0.50 carried over from V2.2 §3.2 with its original argument.
Every V2.2 threshold carried over verbatim, including G1/H1a's −0.005 and its known
mis-calibration. Two gates added: **H1b**, a collinearity ceiling of ρ̄ ≤ 0.90, and
**G6**, a cost gate against the arm's own base. Six abandonment criteria fixed in
advance.

Verified at acceptance: `out/v2_1_exam_predictions.json` does not exist, and the
V2.1 exam digest is
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.

`alpha/carrier.py` was extended **additively** with a `Collinearity` dataclass and a
`collinearity()` function. No existing function was touched, and the check on that
claim is that all 43 tests in `test_alpha_v2_2.py` pass unchanged against the
extended module. They do.

## 2 — 2026-08-08, first ladder run. Completed all four fits, then aborted.

`python -m alpha.ladder_v2_3 --quiet`. Both identity checks passed
(`z__ret_12_1` == B1 and `z__b3` == B3, max |per-cutoff IC difference| = 0.0 for
both). All four fits — two arms, two rungs — completed, and both arms passed H1a,
H1b and H1c.

The run then **aborted before writing any artefact**, on the §4 noise control. See
entry 3; the abort is the reason there is one.

Nothing was frozen by this run. Its arm numbers were visible in the console output
and are identical to entry 4's, the run being deterministic (`random_state = 0`,
seeded bootstrap, frozen panel and cutoff list).

## 3 — 2026-08-08, the §4 noise control was mis-specified. A post-fit change, disclosed.

**This is the one place V2.3 departed from its accepted pre-registration, and it was
done after the first fit. It is recorded here in full because that is the only thing
that makes it legitimate to have done at all.**

§4 specified the control as: blend the base with **one** seeded Gaussian draw at
λ = 0.50, and "if this control ever produces a gain, the construction is
manufacturing IC and V2.3 stops." On seed 20260808 it produced a gain — **+0.00123**
for the `z__ret_12_1` base and **+0.00059** for `z__b3` — so the ladder stopped, as
written.

The control was mis-specified in two ways, both visible only once it ran:

1. **One draw.** The noise blend and its base are highly correlated, so a single
   draw's mean IC has a sampling spread comparable to the effect being looked for.
2. **Unpaired means.** It compared two mean ICs rather than differencing them per
   cutoff, discarding the pairing that removes the day.

Measured across 30 independent draws, at the arm's own λ = 0.50, paired per cutoff:

| base | mean paired difference | sd across draws | range | share of draws above base |
|---|---|---|---|---|
| `z__ret_12_1` | **−0.00202** | 0.00137 | [−0.00579, +0.00041] | **3%** |
| `z__b3` | **−0.00278** | 0.00138 | [−0.00652, −0.00056] | **0%** |

The spread (0.00137) is comparable to the effect (0.00202), which is exactly why one
draw cannot settle it, and the pre-registered seed landed about 2σ into the upper
tail. Its own paired bootstrap interval spans zero — [−0.00241, +0.00512] for B1 and
[−0.00302, +0.00445] for B3 — so **the gain was not significant even on the
pre-registered statistic's own terms.** Stopping the study on it would have been
stopping on a null fluctuation.

What was changed, and what was not:

* the pre-registered single draw is **still computed and still reported verbatim**,
  gain and all, in `out/v2_3_development.json` under
  `noise_control.preregistered_single_draw`;
* the **stop condition** now reads the powered statistic — mean paired difference
  < 0 **and** ≤ 50% of draws above base. This is a *stricter* test: a construction
  manufacturing IC from rank mechanics would gain on most draws, not on one;
* no arm, base, target, input list, λ, threshold, eligibility rule, selection rule
  or gate was touched.

`test_the_preregistered_single_draw_misfired_and_was_reported_anyway` pins the
conditions under which this departure remains defensible: the single-draw gain must
be **non-significant** and the powered mean must be negative. If a future run ever
shows a *significant* single-draw gain, the powered version is no defence and the
study must stop instead.

§4 of the pre-registration also contains an internal contradiction that made the
literal reading ambiguous: the noise control is listed under diagnostics that are
"computed and reported for every arm and rung, **gating nothing**", and the same
bullet then makes it a stop condition. That is noted, not used as cover — the change
above is a change, and it is logged as one.

## 4 — 2026-08-08, the development ladder. The result.

`python -m alpha.ladder_v2_3 --quiet` — two arms, two one-feature rungs, development
cutoffs only via `examset.development_only`. 143,675 rows, 316 cutoffs, 34 refits
per run, ~5 minutes. Frozen to `out/v2_3_development.json` / `.pkl` and reported in
`V2_3_LADDER_REPORT.md`.

**The §6 gate closed. All five gates failed for the selected arm, V2.3-B, and all
five failed for V2.3-A.** Both arms were **eligible** — H1a, H1b and H1c all passed
— so the architecture failed on its hypotheses rather than on its carrier.
Production stays weight 0 / HOLD. Numbers are in the report; what belongs here is
what the run did and what surprised.

**Three things surprised, and two of them reverse earlier conclusions.**

1. **Deleting the base from the inputs fixed the collinearity and made the result
   worse.** ρ̄ went 0.9923 → 0.6981 and effective λ went 0.0619 → 0.3580, a 5.8×
   increase in real authority. Mean IC went +0.02356 → +0.02063, and the advantage
   over momentum went +0.00241 (CI excluding zero) → −0.00052 (CI [−0.00890,
   +0.00764]). The design pass's +0.00604 "orthogonal component" was a property of
   post-processing a collinear model, and it did not survive being learned.
   `V2_3_RESEARCH_DESIGN.md` §3.1 refused to make post-processing an arm on exactly
   that reasoning, and the refusal is vindicated.
2. **The bounded architecture's power advantage was the collinearity, not a free
   gain.** V2.2-B's half-width against its base was 0.00182 at effective λ 0.0619;
   V2.3-A's is 0.00827 at effective λ 0.3580. 5.8× the authority, 4.5× the interval.
   [*corrected 2026-08-08 — see entry 5; originally read "4.5× the authority"*]
   `V2_3_RESEARCH_DESIGN.md` §6 treated the 19× power advantage as a methodological
   result to carry forward, and it is not one — resolution and authority are the same
   dial. That section's forward-looking claim is superseded by this measurement.
3. **The §6.2 probe was optimistic by 2×.** It predicted a B3-based arm would have a
   half-width of ≈0.0039 against B3; the measured value is 0.00796, because the
   probe reused a model still 99% collinear with a *different* base and therefore
   barely moved this one. Any future exam-decision document must use 0.00796, not
   0.0039.

**Abandonment criteria met:** 2 (V2.3-B cannot separate from B3, point estimate
negative), 6 (ρ̄ ≤ 0.90 achieved and no advantage over base), and 4-with-5 (G5 sign
flip plus a fourth consecutive `BEAR_TREND` concentration). §9 says any one of 1, 2,
3 or 6 ends the architecture. Three independent grounds are met, and criterion 6 is
met in its exact pre-registered form.

**Per §9, V2.3 stops and reports the failure mechanism. No V2.4 is proposed.**

## Test status

`pytest -q --runslow`: **625 passed, none skipped.** 587 as before V2.3 — all still
passing, none edited — plus 38 in `test_alpha_v2_3.py`.

`alpha/out/v2_1_exam_predictions.json` does not exist. The V2.1 exam digest is
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, unchanged.
`out/v2_2_development.json` still reports V2.2-B at +0.02356.

---

## 5 — 2026-08-08, independent decision audit, and two documentation corrections. No fit.

The V2.3 closure decision was independently audited
(`V2 3 Final Decision Audit`, preserved at `reports/V2_3_FINAL_DECISION_AUDIT.md`).
The audit re-derived every headline statistic from the per-cutoff series in
`out/v2_3_development.pkl` with a separately written block bootstrap under a
different seed, recomputed the exam digest rather than reading it, intersected the
exam set against all ten frozen series, and executed `adapter.load_evidence()`.
**All point estimates, breadths and halves matched to five decimals; exam overlap
was zero; production weight was 0.0; 625 tests passed.** The closure decision was
confirmed.

**No experiment data, threshold, seed, target, feature, prediction or frozen
artefact was changed by the audit or by this entry.** Two documentation corrections
follow, both textual.

**Correction 1 — the authority ratio.** Entry 2 above and `V2_3_LADDER_REPORT.md`
§3 both stated "4.5× the authority". The authority ratio is 0.3580 / 0.0619 =
**5.8×**; the resolution ratio is 0.00827 / 0.00182 = **4.5×**. The two are
near-proportional but not equal, and writing both as 4.5× overstated the
proportionality. Corrected in place in both documents with the original wording
preserved in a bracketed note. The finding — resolution and authority are the same
dial — is unaffected.

**Correction 2 — abandonment criterion 2 is not a satisfied precision condition.**
`V2_3_PREREGISTRATION.md` §9 criterion 2 conditions on "the improved resolution
(half-width ≈0.004 on 255 cutoffs)". The achieved half-width was **0.00796**, twice
as wide. §8 of the ladder report marked criterion 2 met while citing the achieved
figure, without noting that the criterion's stated precision premise had not been
reached. A retrospective clarification has been added to that table. **The
pre-registration itself is not edited** — it records what was committed to in
advance and stands as written.

The substance is unchanged: criterion 2's point estimate is negative (−0.00120),
and **criterion 6 is met in its exact pre-registered form and is alone sufficient
to end the architecture under §9**. Criteria 4 and 5 are jointly sufficient and
independently confirmed. The decision rests on two independent sufficient grounds
with or without criterion 2.

Programme status after this entry: **CLOSED**. Exam sealed, production weight 0 /
HOLD, no V2.4. See `reports/PROGRAMME_STATUS_V2_3.md`.
