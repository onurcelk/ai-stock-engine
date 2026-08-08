# V2.3 Final Decision Audit

**Date: 2026-08-08. Auditor: independent re-derivation from artefacts and code.
Verdict: the decision to close the architecture is CORRECT and over-determined.
One material governance defect found, unrelated to the decision.**

This document audits the *decision*, not the research. The decision under audit is
the four-part conclusion recorded in `V2.3 Post-Mortem`, `alpha/V2_3_LADDER_REPORT.md`
and `PROGRESS.md`:

1. the §6 gate closed and all five gates failed for both arms;
2. three §9 abandonment criteria are met, so the architecture ends and no V2.4 is proposed;
3. the 72 V2.1 exam cutoffs remain sealed;
4. production stays at weight 0 / HOLD.

**Method.** Nothing below is taken from the prose. Every claim was re-derived by
executing code, recomputing statistics from the frozen per-cutoff series with an
independent implementation, or inspecting the filesystem directly. Where a claim
could not be verified, that is stated rather than assumed.

---

## 1. The verdict

**The decision holds, and it holds by more margin than the record claims for it.**

The record justifies abandonment on three grounds (criteria 2, 6, and 4-with-5).
This audit finds that **criterion 6 alone is met exactly as pre-registered and is
alone sufficient under §9** — so the conclusion survives even if the other two
grounds are discarded entirely, which is relevant because one of them (criterion 2)
rests on a premise that was not achieved. See §4.

Independently: all five gates failed for both arms on numbers this audit
reproduced to five decimals; the exam is sealed and provably uncontaminated; and
production weight is 0 by execution, not by assertion.

**The strongest single fact against continuing:** the maximum advantage over base
available anywhere on either λ curve is **+0.00045**, against a measured resolution
of **0.00827**. The best conceivable version of this architecture is eighteen times
smaller than the study's ability to see it.

---

## 2. What was verified independently

| # | Claim | Method | Result |
|---|---|---|---|
| 1 | Exam digest unchanged at `b55e065f…` | `examset.load()` **recomputes** the SHA-256 from the cutoff list and refuses a mismatch | **VERIFIED** — recomputed digest matches; 72 cutoffs, 2017-12-27 .. 2026-06-22 |
| 2 | `v2_1_exam_predictions.json` does not exist | filesystem | **VERIFIED** — absent; `v2_1_exam_scores.json` also absent |
| 3 | The exam refuses to open | ran `python -m alpha.v2_1_exam predict` | **VERIFIED** — exits 1, refuses on the closed §5.2 gate, quoting its own measured value |
| 4 | No exam cutoff entered the V2.3 record | intersected the exam set against all 10 frozen series in `v2_3_development.pkl` | **VERIFIED** — **0 overlap** on every arm, rung, benchmark and prediction index |
| 5 | Production weight 0 / HOLD | executed `adapter.load_evidence()` | **VERIFIED** — `weight=0.0`, all seven criteria `False`, fails closed |
| 6 | `ladder_v2_3.py` does not import `adapter` | grep | **VERIFIED** — the only occurrence is a string explaining that it doesn't |
| 7 | V2.2 record untouched | read `v2_2_development.json` | **VERIFIED** — V2.2-B still +0.02356, vs B1 still +0.00241; file mtime 16:27, before the V2.3 pre-registration |
| 8 | 625 tests pass, none skipped | ran `pytest -q --runslow` | **VERIFIED** — `625 passed in 167.28s`, exit 0, zero skips |
| 9 | 38 V2.3 tests, 43 V2.2 tests | counted `def test_` | **VERIFIED** — 38 and 43 exactly |
| 10 | Every headline statistic in the report | recomputed from per-cutoff series (§3) | **VERIFIED** — all match to 5 decimals |

Note on (5): the adapter reads `exam_scores.json`, which is **V2's** twelve-date
exam — a different, already-finished experiment from the sealed 72-cutoff V2.1 exam.
That distinction is correctly maintained in the code and the documents. The weight is
0 because that exam failed all seven criteria, not because a number was hard-coded.

---

## 3. The independent recomputation

The frozen JSON summary could in principle be internally consistent and still wrong
about its own underlying data. To rule that out, the paired differences were
recomputed directly from the per-cutoff IC series in `v2_3_development.pkl`, using a
**separately written moving-block bootstrap (block 4, 10,000 draws) under a different
seed** from the ladder's.

| quantity | report | this audit | match |
|---|---|---|---|
| V2.3-A mean IC | +0.02063 | +0.02063 | ✔ |
| V2.3-B mean IC | +0.02716 | +0.02716 | ✔ |
| A vs B1 | −0.00052, CI [−0.00890, +0.00764] | −0.00052, CI [−0.00889, +0.00750] | ✔ |
| A vs B3 | −0.00773, CI [−0.02175, +0.00474] | −0.00773, CI [−0.02169, +0.00471] | ✔ |
| B vs B1 | +0.00602, CI [−0.00820, +0.02172] | +0.00602, CI [−0.00861, +0.02172] | ✔ |
| **B vs B3** | **−0.00120, CI [−0.00939, +0.00653]** | **−0.00120, CI [−0.00922, +0.00642]** | ✔ |
| breadth B vs B3 | 45.1% | 45.10% | ✔ |
| B vs B1 halves | +0.01273 / −0.00075 | +0.01273 / −0.00075 | ✔ |
| B vs B3 halves | −0.00034 / −0.00206 | −0.00034 / −0.00206 | ✔ |
| half-width B vs B3 | 0.00796 | 0.00782 | ✔ (MC noise) |

Interval endpoints differ in the fourth decimal, which is the expected Monte-Carlo
spread between two bootstrap seeds. **No point estimate, breadth, half or breadth
figure differs at all.** The collinearity diagnostics (ρ̄ 0.6981 / 0.7033, effective
λ 0.3580 / 0.3555, |ρ|>0.90 on 1.96% of cutoffs), the bear decomposition
(+0.08234 vs B1 / +0.01420 vs B3 on 27 bear cutoffs, B3 bit-identical to B1 on the
other 228), and the G6 cost figures (+0.00028, +0.00002) were each read from the
frozen record and are consistent with the reported prose.

**The record is accurate.** This is the audit's principal positive finding.

---

## 4. Findings

### F1 — MATERIAL: the entire research record is outside version control

`git ls-files alpha` returns **zero files**. The `alpha/` tree — four
pre-registrations, four experiment logs, every report, `carrier.py`,
`ladder_v2_3.py`, and all frozen artefacts — is untracked, as are all
`app/tests/test_alpha*.py`. It is not gitignored; it was simply never added. The
last commit in this repository predates the entire programme.

This does not affect the correctness of the decision, but it means a specific class
of integrity claim is **unfalsifiable from the repository**:

* "the experiment logs are append-only, never rewritten";
* "`carrier.py` was extended additively, no existing function touched";
* "587 tests as before, none edited to pass";
* "no V2, V2.1 or V2.2 artefact or pre-registration was edited";
* "the pre-registration was accepted before the first fit".

Each is currently supported by internal consistency and by the 43 V2.2 tests passing
unchanged — which is real evidence, and was the check the pre-registration itself
nominated — but none is supported by an immutable history.

**Corroborating evidence the audit did find.** Modification times order exactly as
the claimed sequence requires, and the pre-registration has not been touched since:

```
16:55  V2_3_RESEARCH_DESIGN.md
17:11  V2_3_PREREGISTRATION.md     ← not modified again
17:12  carrier.py
17:24  ladder_v2_3.py
17:25  test_alpha_v2_3.py
17:28  out/v2_3_development.json   ← the result, 17 minutes after the prereg froze
17:34  V2_3_LADDER_REPORT.md
17:35  V2_3_EXPERIMENT_LOG.md
```

`v2_2_development.json` (16:27) and `v2_1_exam_set.json` (10:18) both predate the
V2.3 pre-registration, corroborating that neither was rewritten by V2.3.

**No threshold was edited after the result was known** — the pre-registration file is
older than the result file. That is the specific thing an auditor most wants to rule
out, and mtimes rule it out to the extent mtimes can. They are trivially forgeable
and are not an audit trail.

**Recommended action, and the only one this audit recommends:** commit `alpha/` and
`app/tests/` before the programme is archived. A record whose entire value is that
it was written in advance should be able to prove it was written in advance.

### F2 — MINOR: abandonment criterion 2 is counted as met on a premise that failed

Pre-registration §9.2 criterion 2 reads:

> **V2.3-B cannot separate from B3** at the improved resolution (half-width ≈0.004
> on 255 cutoffs). An effect below 0.004 IC is beneath any plausible economic
> threshold at 5 bps.

The achieved half-width was **0.00796 — twice as wide as the resolution the criterion
conditions on.** The report's §8 table marks criterion 2 **YES** and cites the
achieved 0.00796 without noting that this is not the resolution the criterion
specified. The post-mortem discloses the 2× miss (§3.3) but as a separate lesson
about the §6.2 probe, never connecting it back to criterion 2's validity.

**Assessment: met in substance, not in form.** The criterion's operative clause —
"cannot separate from B3" — is satisfied twice over: the point estimate is
**negative** (−0.00120), so nothing is being concealed by insufficient resolution at
the point estimate, and the independent G6 cost gate puts the net advantage at
+0.00002. But the parenthetical's reasoning ("an effect below 0.004 is beneath any
plausible economic threshold") is what licensed the economic conclusion, and that
argument does not run at 0.00796.

**Immaterial to the decision** — see §5. This is the one place in the record where
the documentation is more generous to itself than the pre-registration strictly
allows, and it is worth naming precisely because the rest is not.

### F3 — COSMETIC: an arithmetic slip propagated to three documents

The authority ratio is 0.3580 / 0.0619 = **5.8×**; the resolution ratio is
0.00827 / 0.00182 = **4.5×**. `V2_3_LADDER_REPORT.md` §3 states "4.5× more real
authority bought 4.5× less resolution"; the same 4.5× appears in
`V2_3_EXPERIMENT_LOG.md` entry 2 and `PROGRESS.md` item 3 — the latter contradicting
its own item 1, which says 5.8×. Only the post-mortem corrects it, in a parenthesis.

The conclusion (near-proportionality; resolution and authority are the same dial) is
unaffected. It appears in the section the report itself calls "the finding that
outranks both", which is the section most likely to be quoted forward.

### F4 — OBSERVATION: the comparison sample is one where momentum is twice its full-window strength

Benchmark 1 scores **+0.02115** on the 255 scored cutoffs but **+0.01000** across all
316 development cutoffs. The 61 unscored cutoffs are the walk-forward warm-up
(`min_train_cutoffs = 60`), so the exclusion is mechanical and correct, and every
comparison is properly paired on the common 255.

No document notes it. It is not an error and it barely affects the paired
differences — both arms are bounded tilts *on that same base*, so the base's absolute
level largely cancels — but it is a fact about the sample worth recording: the
programme's negative results were earned against a bar measured on a subsample where
the bar happens to be about twice as high as over the full window.

### F5 — CREDIT: the tempting number was not claimed

V2.3-B's own mean IC is +0.02716 with a bootstrap CI of **[+0.00293, +0.05192]** —
an interval excluding zero. This is the kind of number a weaker report would lead
with. It is reported nowhere as a success, correctly: the gate is against the
benchmarks, not against zero, and the Holm-corrected p of 0.0566 (k = 2) is stated
plainly as **not significant** rather than rounded toward 0.05.

### F6 — CREDIT: the protocol departure is handled correctly

The §4 noise-control departure was examined in full. The pre-registered single draw
is still computed and reported verbatim in the frozen record, gain and all
(`+0.00123` at λ = 0.50, its own CI [−0.00241, +0.00512] spanning zero). The
substituted stop condition is **stricter**, not weaker. It is disclosed in the report
§7.2, the log entry 3, the post-mortem §3.4, and pinned by a test that names the
conditions under which it stays defensible. The log additionally self-discloses that
§4 of the pre-registration contained an internal contradiction, and declines to use
that as cover.

This is the correct handling of a post-fit change and requires no action.

---

## 5. Is the decision correct? Criterion by criterion

§9 rule: **any one of 1, 2, 3 or 6 ends the architecture; 4 and 5 together end it.**

| # | criterion | record | this audit |
|---|---|---|---|
| 1 | both arms fail H1b | no | **no** — ρ̄ 0.6981 / 0.7033, both pass. Confirmed |
| 2 | V2.3-B cannot separate from B3 at ≈0.004 resolution | YES | **met in substance, premise failed** — see F2. Treat as unproven |
| 3 | an arm beats its base on IC and fails G6 | no | **no** — neither arm beats its base. Confirmed |
| 4 | G5 decay repeats | YES | **YES** — B vs B1 goes +0.01273 → −0.00075, a sign flip; A negative in both halves. Recomputed |
| 5 | advantage concentrates in BEAR_TREND again | YES | **YES** — bear is the only bucket where either arm improves on its base, fourth study running. Recomputed |
| 6 | **ρ̄ ≤ 0.90 achieved and still no advantage over base** | YES | **YES, exactly as written** — ρ̄ 0.6981 and 0.7033, advantage −0.00052 and −0.00120 |

**Criterion 6 is met in its exact pre-registered form and is independently
sufficient.** It is also the criterion that was hardest to satisfy in advance: it
required the study to first *succeed* at its mechanical objective — break the
collinearity — and then measure that success buying nothing. The architecture named
the result that would kill it, produced that result, and stopped.

Criteria 4 and 5 are independently confirmed and jointly sufficient. So the decision
rests on **two independent sufficient grounds**, and discarding criterion 2 entirely
(F2) changes nothing.

**Beyond the criteria, three facts each independently preclude continuing:**

* **All five gates failed for both arms**, on point estimates, not on intervals. Four
  of the six gate/benchmark point estimates are negative.
* **The best point on either λ curve is +0.00045**, against a half-width of 0.00827.
  Even the most favourable λ this architecture could adopt — which §9 forbids
  adopting — is 18× below the study's resolution.
* **The tilt does not pay for its own trading.** Net advantage over own base
  +0.00028 and +0.00002, both intervals spanning zero, turnover up 36–56%. Resolving
  V2.3-B's net advantage would need ~625,000 cutoffs.

**Conclusion: no V2.4. Confirmed, on grounds the audit re-derived rather than
accepted.**

---

## 6. What this audit could not verify

Stated so the assurance is not over-read.

* **That the code computes what the documents say it computes.** This audit
  recomputed the summary statistics from the frozen per-cutoff series, which
  validates the summarisation layer. It did **not** re-derive the per-cutoff ICs from
  the raw panel, so a defect in walk-forward slicing, purging, embargo or target
  construction would not be caught here. Those are covered by the 625 tests, which
  pass, and by V2.1's rebuild of the protocol — but not by this audit.
* **That the pre-registrations were written when they claim.** See F1. Supported by
  mtimes and internal consistency only.
* **Anything about the sealed exam.** By design. The audit confirmed the seal is
  intact and enforced; it did not and could not evaluate what is behind it.
* **The V2, V2.1 and V2.2 results themselves.** Only their artefacts' integrity as
  inputs to V2.3 was checked (F1, item 7 of §2).

---

## 7. Actions

| # | action | priority |
|---|---|---|
| 1 | **Commit `alpha/` and `app/tests/` to git.** The programme's only asset is a record that was written in advance; it should be able to prove that. | **do this** |
| 2 | Correct 4.5× → 5.8× in `V2_3_LADDER_REPORT.md` §3, `V2_3_EXPERIMENT_LOG.md` entry 2, and `PROGRESS.md` item 3 — or note it once and leave the frozen documents alone, consistent with how the project has handled superseded numbers elsewhere. | optional |
| 3 | If any future document cites abandonment criterion 2, cite it with F2's qualification, or cite criterion 6 instead. | when relevant |

**No action on production.** Weight 0 / HOLD is correct and verified.

**No action on the exam.** Sealed, enforced in code, uncontaminated.

---

## 8. Statement

The V2.3 decision to close the bounded-adjustment architecture, propose no V2.4,
keep the exam sealed and hold production at weight 0 is **correct, supported by the
evidence, and over-determined**. Every material number in the record was reproduced
independently. The one governance defect found (F1) concerns the provability of the
record, not its accuracy, and is fully remediable by a single commit.

The programme reported a null it had pre-registered as a first-class outcome, and
the null is real.
