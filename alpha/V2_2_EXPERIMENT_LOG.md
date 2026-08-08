# V2.2 experiment log

Every V2.2 run, in order, including the ones that were abandoned. Appended to,
never rewritten. `V2_1_EXPERIMENT_LOG.md` and `EXPERIMENT_LOG.md` record earlier
studies and are not touched.

---

## 1 — 2026-08-08, acceptance and two amendments. No fit.

`V2_2_PREREGISTRATION.md` was accepted with the two amendments recorded in its
§12. At the moment of acceptance:

* `alpha/carrier.py` and `alpha/ladder_v2_2.py` existed and imported cleanly;
* `app/tests/test_alpha_v2_2.py` existed — 36 tests, all passing, 7 skipping for
  want of a frozen V2.2 development record;
* **no V2.2 model had been fitted, no V2.2 carrier had been applied to outcome
  data, and no V2.2 IC had been computed on any cutoff.**

Verified at the same time: `alpha/out/v2_1_exam_predictions.json` does not exist,
and the V2.1 exam digest is still
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`.

**A1 — acceptance.** The DRAFT marker was replaced. No content changed.

**A2 — §11's fifth bullet was unprovable as worded.** It asked for a test that
"arm C produces zero inversions against `ret_12_1`". `monotonic_cst` is a
statement about the model's *function*: non-decreasing in `z__ret_12_1` at fixed
values of the other 34 columns. Twenty-six of those are cutoff-constant, so they
*are* fixed inside a cutoff — but the eight stock-level ranks are not, and two
names differing in volatility can therefore be ordered against their momentum.
The claim holds unconditionally only for the one-feature rung `S1-C`.

The arm was not changed: same constraint, same column, same learner, same 35
inputs. What changed is what the study claims to have proved. §3.3 now states the
guarantee and its limit, and §11 asserts the unconditional claim for `S1-C` while
arm C's inversion count is measured and reported. `test_alpha_v2_2.py` implements
both, and `test_the_monotone_constraint_binds_only_where_it_can` asserts the
provable form directly by sweeping the constrained column with the other 34 held
fixed.

Found before the first fit, which is the only window in which it could be fixed
without moving a target. Had it surfaced while writing the report, the natural
repair would have been to weaken the test rather than the claim.

## 2 — 2026-08-08, the development ladder. First fit.

`python -m alpha.ladder_v2_2 --quiet` — three arms, three one-feature rungs, three
grid cells (the fourth is `S1-A` by construction and is reused), development
cutoffs only via `examset.development_only`. 143,675 rows, 316 cutoffs,
2016-01-04 to 2026-07-28, 34 refits per run, ~4 minutes.

Before any fit, two assertions the run makes and would have stopped on:

* §2.1's asymmetry — all 26 market-context columns are cutoff-constant, all 9
  stock-level columns vary. Checked on every development cutoff, not a sample.
* §2.2's identity — ranking by `z__ret_12_1` reproduces Benchmark 1's per-cutoff
  IC with `max |difference| = 0.0` exactly, over all 316 cutoffs.

Result: **the §6.3 gate closed.** V2.2-A and V2.2-C were carrier-defective under
§6.1 (G1 = −0.02495 and −0.00696 against a −0.005 floor) despite holding the two
highest mean ICs. V2.2-B was the only eligible arm, passed G2 and G4, failed G3
and G5. Production stays weight 0 / HOLD. Numbers, mechanism and what the study
closed are in `V2_2_LADDER_REPORT.md`.

Three things belong in the log rather than the report.

**The grid refuted its own premise.** §4.2 was built to decompose the collapse
into an input effect and a target effect. Neither exists at the scale required:
all four cells land within 0.0023 of zero against a factor worth +0.02115.
Reported as the study's headline rather than smoothed over, because a diagnostic
that comes back "your hypothesis about the mechanism was wrong" is the most
informative outcome a diagnostic has.

**G1's threshold was justified against the wrong mechanism, and was not moved.**
§6.1 justified −0.005 as room for the ties "≤255 bins" produce. `S1-C`'s actual
discretisation loss is −0.00696, and it comes from `max_leaf_nodes = 31` under the
monotone constraint yielding a *five*-step staircase, not from `max_bins`. So the
threshold rejects an honest discretisation loss it was written to admit. §9 names
lowering a threshold as forbidden, so arm C is carrier-defective on the record and
the discrepancy is explained in §3 of the report instead. This is the one place
where a pre-registered number is, in hindsight, mis-calibrated; noting it is not a
licence to re-run.

**λ = 0.50 turned out to be the maximum of its own sensitivity curve** (+0.02115 /
+0.02200 / +0.02356 / +0.02105 at λ = 0 / 0.25 / 0.50 / 1.00). It was fixed before
the first fit and would have stayed the arm had it been the worst point. That it is
the best is luck and is not treated as vindication of the choice.

## 3 — 2026-08-08, one re-run for a reporting field. No change to any number.

The first run printed `S0`'s mean IC over all 316 development cutoffs (+0.01000)
beside rung means over 255 (`S1-B` +0.02097), inviting a reader to conclude the
learner *improved* on momentum. The G1 arithmetic was already paired and therefore
already correct — `stats.paired_difference` drops unmatched cutoffs — but the table
was misleading.

`carrier_integrity` now also reports both sides of the pair on the paired sample
(`rung_mean_ic_on_paired_cutoffs`, `s0_mean_ic_on_paired_cutoffs`), the grid quotes
`S0` on the grid's own 255 cutoffs, and `record["s0"]` carries a `sample_note`. The
ladder was re-run to regenerate the artefact.

Every number is bit-identical to run 2: the learner is seeded (`random_state = 0`),
the bootstrap is seeded (`stats.SEED`), and the panel and cutoff list are frozen
files. No arm, threshold, target, column list, eligibility rule, selection rule or
gate changed — the diff is three reported fields and three print statements. Logged
because a second invocation of a study after its result is visible is exactly the
kind of thing that should never be silent, even when it is inert.

## 4 — 2026-08-08, post-result analysis of the frozen V2.2 artefacts. No fit.

V2.2's development result was accepted and the exam left sealed. A design pass then
re-scored the frozen predictions in `out/v2_2_development.pkl` to answer six
questions about the bounded-adjustment architecture. **No model was fitted, no arm
was added, no threshold was changed, and the only exam data read was the frozen
pre-cutoff regime metadata.** Written up as `alpha/V2_3_RESEARCH_DESIGN.md`. Every
number produced is post-hoc and diagnostic and selects nothing.

Four measurements change what V2.2's report concluded, and are recorded here
because they qualify a document that must not be edited:

1. **V2.2-B's learned adjustment is 99.2% collinear with its own base** —
   within-cutoff Spearman(u, z) = −0.9923, negative on 255 of 255 cutoffs. The
   residual target's dominant predictable component is `−z`, and `rank_series`
   re-encodes it at full amplitude. λ = 0.50 therefore delivered ≈0.062 rank units
   of new authority rather than 0.50, and the +0.00241 decomposes as +0.00604 from
   the orthogonal component and −0.00363 of dilution.
2. **The λ bound is not what blocked G3.** An oracle adjustment at λ = 0.50 reaches
   +0.370 IC on bear cutoffs against B3's +0.035. The intuitive conclusion — that
   §3.2's bound structurally forbids matching B3's sign switch — is wrong, and was
   checked before being written down.
3. **B3's advantage over B1 is not statistically established.** B3 is bit-identical
   to B1 on all 228 non-bear cutoffs; its whole margin is +0.06814 on 27 bear
   cutoffs, 17 of them in 2022, winning 15 and losing 12. B3 − B1 = +0.00721, CI
   [−0.00329, +0.02006]. B3's *IC* is significantly positive, as the reports say;
   B3 *beating B1* is a different claim and is unproven. G3 is unchanged and
   remains a gate.
4. **V2.2-B's IC gain does not convert into a cost-adjusted gain.** Net quintile
   spread over B1 is +0.00021 at 5 bps, CI [−0.00012, +0.00058], and B trades 21%
   more per leg than plain momentum (0.1796 vs 0.1485) — it trades far less than
   arms A and C, but not less than the benchmark.

The exam-resolution figure of `V2_2_PREREGISTRATION.md` §8 was also recomputed:
≈0.066 for unconstrained arms (confirmed) against **≈0.0034** for a B1-bounded arm
on 72 dates. This is not a reason to open the exam and the exam was not opened; it
is a number a future exam-decision document has to use instead of the stale one.
The frozen exam holds 10 BEAR_TREND cutoffs of 72, so G3 on the exam would rest on
10 dates.

A leakage and artefact audit of the bounded blend passed nine checks, including the
decisive one: blending the base with pure Gaussian noise **monotonically destroys**
IC (+0.02046 / +0.01908 / +0.01554 at λ = 0.25 / 0.50 / 1.00 against B1's +0.02115),
so the construction cannot manufacture IC through rank mechanics. The λ = 0.5 rank
lattice does create ties on 17% of names; its effect on IC is 3 × 10⁻⁵ and runs
against the arm.

No V2.3 code was written. The design proposes two arms, k = 2, and six abandonment
criteria.

## Test status

`pytest -q --runslow`: **587 passed, none skipped.** 544 as before V2.2 (all still
passing, none edited) plus 43 in `test_alpha_v2_2.py`.

`alpha/out/v2_1_exam_predictions.json` does not exist. The V2.1 exam digest is
`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`, unchanged.
