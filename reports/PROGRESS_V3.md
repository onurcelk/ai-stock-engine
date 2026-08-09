# V3 Programme — execution progress

Tracks execution of `ai stock prediction master roadmap.md` (v2, 2026-08-09), which
lives outside the repository at `Desktop/AI Stock/`. Versioned from the first day, on
the V2.3 audit's lesson that an untracked record makes every claim about it
unfalsifiable.

**Session started 2026-08-09.** Everything below has been run and committed locally.
**Nothing has been pushed** — `origin` is a third party's public repository (§27A).

---

## The one thing that matters if you read nothing else

**Family 1 (reported fundamentals / time-series SUE) was tested and REJECTED on its
pre-registered rule. Budget slot 1 of 3 is spent.** The primary contrast — B3 plus a
bounded SUE tilt, versus B3 — measured **+0.00090 with a half-width of 0.00229**. All
four CONTINUE criteria failed. This is a *well-resolved* null, not an underpowered one:
even the interval's upper bound (+0.00317) sits below the +0.007 economic floor.

**The one genuinely new positive finding:** raw SUE alone scores **mean IC +0.01305,
CI [+0.00263, +0.02339] — an interval that excludes zero**, with a 57.6% hit rate,
both chronological halves positive, and turnover of only 0.091. That is a real
standalone factor and it is *better behaved than 12-1 momentum* (+0.01000, hit 53.2%,
CI spanning zero). **It still does not beat the incumbent B3 (−0.00937), and its
long-short spread does not clear zero (+0.00051, CI [−0.00081, +0.00158]).**

So: the information is real, and it is not enough. Both halves of that sentence are
load-bearing.

---

## Roadmap conformance checklist — section by section

Legend: **[x]** done · **[ ]** not started · **[–]** not reached yet (blocked upstream) ·
**[=]** standing rule, held continuously.

### Phases

| | § | Requirement | Evidence |
|---|---|---|---|
| **[x]** | §3.1 | Checks 1–6, do not re-audit | all six reproduce; `EXPERIMENT_REGISTRY.md` §1 |
| **[x]** | §3.2 | Decide `validation/` — preserve, reuse, don't merge | `VALIDATION_EVIDENCE_MANIFEST.md`; harness decisions §6 |
| **[x]** | §3.3 | Open + seed the registry | `EXPERIMENT_REGISTRY.md`, 13 arms + PIT-1 |
| **[x]** | §4 | Information audit, free-only, ≤3 families | `INFORMATION_AUDIT.md`; 3 families frozen |
| **[x]** | §4.5 | Scoring table, struck list, verified timestamps | audit §2–§4 |
| **[x]** | §5 | Target design + power implication per target | `TARGET_DESIGN.md` |
| **[x]** | §2.6 | Power gate, Family 1 — **before** implementation | registry §6.1 |
| **[x]** | §6, §6.1 | Pipeline; one-door design mirrored; filing-date door | `alpha/filings.py` |
| **[x]** | §6.2 | Required test categories incl. **restatements** | `test_alpha_filings*.py`, 26 tests |
| **[x]** | §2.10 | Admissibility, all four clauses | prereg §2; ceilings fixed before measurement |
| **[x]** | §7 | Phase 5 information-only tests, 7 test types | `V3_FAMILY1_REPORT.md` → **REJECT** |
| **[x]** | §2.6 | Power gate, Family 2 — gate only | `FAMILY2_POWER_GATE.md` → **PASS** |
| **[–]** | §8 | Phase 6, first model | blocked: requires a Phase 5 **CONTINUE**. Family 1 returned REJECT |
| **[–]** | §9 | Phase 7 walk-forward | blocked upstream |
| **[–]** | §9b | Phase 7b single-name re-validation | blocked upstream; harness decisions already recorded |
| **[–]** | §10 | Working Model gate | blocked upstream |
| **[–]** | §11–§20 | Ensemble → retraining | blocked upstream |
| **[–]** | §15 | Final untouched exam | **not reached.** Exam still sealed |

### Standing rules — held throughout, not one-off steps

| | § | Rule | Held? |
|---|---|---|---|
| **[=]** | §0.1 | Exam never opened/scored/modified | digest `b55e065f…` re-verified after every commit |
| **[=]** | §0.1 | Production weight not raised; adapter untouched | weight `0.0`, all seven criteria False |
| **[=]** | §0.1 | No threshold lowered, no benchmark swapped, no B3 modified | Family 1 rejected **on** its thresholds, not around them |
| **[=]** | §0.1 | No rung/λ/control promoted to an arm | λ curve reported as diagnostic only |
| **[=]** | §0.1 | **No V2.4** | V3 changed the *information*, not the model |
| **[=]** | §2.1 | No source without a publication timestamp | 87 facts dropped, not approximated |
| **[=]** | §2.2 | Walk-forward only | 5-session spacing, non-overlapping |
| **[=]** | §2.3 | All mandatory baselines | B3, B1, B2, and the raw factor alone |
| **[=]** | §2.4 | No metric shopping | metrics fixed in prereg §6.2 before any result |
| **[=]** | §2.5 | Regime concentration **disqualifies** | criterion 4 fired on the BEAR concentration |
| **[=]** | §2.7 | Arms declared before first fit; nothing discarded | 2 arms declared; Holm applied |
| **[=]** | §2.8 | Frozen evidence, hashed | manifests + per-cutoff `.pkl` committed |
| **[=]** | §2.9 | No architecture escalation | Phase 5 fitted **no learner** |
| **[=]** | §2.11 | Controls powered as gates | 30 paired draws, sd 0.00096 |
| **[=]** | §2.12 | Free power gain read as a warning | oracle-ceiling check performed, not assumed |
| **[=]** | §2.13 | Never reason from a post-processed number | no post-processing anywhere in V3 |
| **[=]** | §21 | 3 families, no fourth | **1 spent, 2 remain**; no Family 1′ opened |
| **[=]** | §25 | No `research/` tree | used `alpha/` + `reports/` |
| **[=]** | §27A | No push | 10 local commits, `origin` untouched |
| **[=]** | §27B | No data spend | all sources free; FRED key flagged, not bought |

### The one §29 step not yet done

**[ ] §29.5 — "implement only the highest-priority dimension and run the first V3
information-only experiment"** is **done for Family 1** and returned REJECT. The roadmap's
§29 sequence is therefore complete through its last numbered step. What follows is
governed by §21: Family 2 or Family 3, or the termination condition.

---

## Status by roadmap phase

| Phase | § | State |
|---|---|---|
| 1 — confirm the base, decide `validation/`, open the registry | §3 | **DONE** — commit `20b5e69` |
| 2 — information audit, free-data constraint | §4 | **DONE** — commit `73c5f54` |
| 3 — target design | §5 | **DONE** — commit `9532d87` |
| §2.6 power gate, Family 1 | §29.4 | **DONE** — commit `7eba2c1` |
| 4 — filings pipeline | §6 | **DONE** — commit `9a0bec7` |
| Pre-registration + §2.10 admissibility | §2.10 | **DONE** — commit `5a8b92e` |
| 5 — information-only test, Family 1 | §7 | **DONE — REJECT** — commit `7ab3c8f` |
| §2.6 power gate, Family 2 | §2.6 | **DONE — PASS**, gate only — commit `c274982` |
| 6 onward | §8+ | **not started.** Blocked: Phase 6 requires a Phase 5 CONTINUE |

### Phase 1 — the three deltas (§3)

* **§3.1** Reproduction checklist checks 1–6 re-run at `db97386`. **All six pass with
  the recorded values.** Exam digest `b55e065f…` over 72 cutoffs; the §5.2 gate still
  refuses to open (exit 1); production weight `0.0`, all seven criteria False;
  V2.3-B vs B3 re-derived at **−0.00120**, breadth 0.451, halves −0.00034 / −0.00206;
  zero exam contamination; **625 tests passed**, none skipped. No §27D contradiction.
* **§3.2** `validation/` **preserved** as its own study with its own manifest
  (`reports/VALIDATION_EVIDENCE_MANIFEST.md`), *not* merged into the V2–V2.3 record.
  Scope is the computed import closure: the harness plus its four engine dependencies
  (`ultimate`, `indicators`, `forecast`, `live`) and their tests — 184 tests, so the
  commit is self-verifying. All four engine modules were last modified *before*
  `out/predictions.json` was written, which is the provenance evidence and its stated
  limit. Phase 7b harness-reuse decisions are recorded there too.
* **§3.3** `reports/EXPERIMENT_REGISTRY.md` opened and seeded with all thirteen fitted
  V2→V2.3 arms plus the `validation/` study.

### Phase 2 — the audit (§4)

**Headline: 51.8% of 10-K/10-Q filings are accepted by EDGAR *after* the 16:00 ET
close of the date they are stamped with** (n = 2,056, 60 sampled filers; modal
acceptance hour is 16:00 itself). A `filed <= cutoff` rule — the obvious one — leaks in
about half of all observations. The repair is a join to `acceptanceDateTime`.

Verified positively: EDGAR keeps **every vintage** of a fact (46 of 66 sampled
period-keys carry more than one `filed` date), so restatements are separately
addressable rather than silently overwriting history.

**FRED/ALFRED struck as a standalone family** — a macro series is cutoff-constant and
cannot rank a cross-section by construction; V2.1-B already measured this at −0.00269.
It remains legitimate as conditioning context only. Three families frozen:
(1) EDGAR fundamentals, (2) Form 4 insiders, (3) 13F holdings as reserve.

### Phase 3 — target design (§5)

Class balance measured on the 316 development cutoffs only. **Target A (cross-sectional
alpha rank, 5 sessions) kept** — 316 independent cutoffs, ~0.0074 IC floor, and B3 and
momentum are already measured on it. Pooled directional accuracy **ruled out** as a
primary metric anywhere: the per-cutoff up-rate swings **0.24 → 0.75**, so it is a
market-draw thermometer. Target C at 5D ruled out (a ±5% move is a 10% tail event).

### Phase 4 — the pipeline (§6)

`alpha/filings.py` mirrors `pitdata.py`'s one-door contract, filtering on acceptance
time. `alpha/build_filings.py` ingested **1,070,383 fact vintages, 613 filers,
2009-04 → 2026-08**; 87 facts lacking an acceptance timestamp were **dropped, not
approximated** (§2.1). Identity is CIK, never ticker; the 30 unmapped cache symbols are
recorded by name because a silent 5% survivorship hole is how a fundamentals panel
flatters itself. `alpha/filings_features.py` builds SUE by **event replay**, so a
restatement reshapes belief only from its own acceptance forward.

**26 new tests.** The decisive ones rewrite the future — adding restatements and later
filings — and demand the door's view and the feature's value at an earlier cutoff do
not move.

### §2.10 admissibility — thresholds fixed before any number was read

| Ceiling | Threshold | Measured | |
|---|---|---|---|
| SUE vs `z__ret_12_1`, mean \|ρ\| | ≤ 0.30 | **0.2533** (p95 0.3874) | PASS |
| SUE vs each stock-level input | ≤ 0.50 | **0.1669** worst (`z__sma200_dist`) | PASS |

0.2533 is a pass but not a comfortable one, and is recorded as such — SUE and momentum
are genuinely related, which was expected.

Also recorded: **only 8 of V2's 34 input columns are stock-level.** The other 26 are
cutoff-constant (verified: max 1 distinct value within a cutoff).

---

## Phase 5 result — Family 1, REJECTED

Run under `alpha/V3_PREREGISTRATION.md`, which was committed before the first fit.
316 development cutoffs, 143,675 rows, SUE coverage 0.930, **exam contamination 0**.

| | mean IC | half-width | 95% CI | hit |
|---|---|---|---|---|
| b1 12-1 momentum | +0.01000 | 0.02386 | [−0.01342, +0.03430] | 0.532 |
| b3 regime rule (incumbent) | +0.02241 | 0.02328 | [−0.00086, +0.04570] | 0.560 |
| **Arm 0 — raw SUE rank** | **+0.01305** | 0.01038 | **[+0.00263, +0.02339]** | **0.576** |
| Arm 1 — B3 + 0.25·SUE tilt | +0.02331 | 0.02320 | [+0.00008, +0.04648] | 0.563 |

**Primary contrast, Arm 1 − B3: +0.00090, half-width 0.00229, CI [−0.00140, +0.00317],
breadth 0.5032, n = 316.**

| Pre-registered CONTINUE criterion | |
|---|---|
| 1 — effect ≥ +0.010 | **FAIL** (+0.00090) |
| 2 — CI excludes zero | **FAIL** |
| 3 — breadth > 0.50 **and** both halves positive | **FAIL** (halves −0.00005 / +0.00185) |
| 4 — survives with BEAR removed | **FAIL** (+0.00088) |

**Noise control PASSED** — 30 paired within-cutoff permutations, median −0.00045,
sd 0.00096, 0.0% of draws above threshold. The control behaved as a control, which is
what §2.11 was written to ensure after V2.3's single-draw misfire.

**Net of costs, from the first measurement (§10):** Arm 1's gross spread advantage over
B3 is **−0.00006** and net **−0.000065**. Arm 0's is −0.00146. No tilt pays for its own
trading — the fifth time this programme has measured that.

**The V2.3 finding reproduced exactly.** Arm 1 beats momentum by +0.01332 with an
interval excluding zero — and **+0.11317 of that lives in BEAR_TREND**, against
+0.00075 in BULL and +0.00189 in SIDEWAYS. That apparent win over B1 *is the regime
rule it is built on*, not the new information. `V2_3_LADDER_REPORT.md` §2 said the same
sentence about V2.3-B.

---

## What is now known that was not known this morning

1. **A free, genuinely point-in-time fundamentals panel is buildable**, and the door
   that makes it safe is written and tested. That asset survives this rejection.
2. **`filed` is not a knowability timestamp.** Half of all filings land after the close
   they are dated. Any future filings work must join acceptance time.
3. **Time-series SUE is a real standalone factor on this universe** — IC +0.01305 with
   an interval excluding zero, stable across halves, cheap to trade (turnover 0.091).
   **It is the first factor this programme has found whose own interval excludes zero
   other than B3.**
4. **It still does not beat B3, and adding it to B3 changes nothing measurable.**
5. The **λ ceiling argument**: Arm 0 (full authority) is −0.00937 against B3 and Arm 1
   (λ = 0.25) is +0.00090. The information cannot be rescued by turning λ up — that
   direction leads toward Arm 0's negative number, and turning it down leads to B3
   itself. No λ point may be promoted to an arm in any case (§0.1).

---

## Standing constraints — unchanged

* The 72 exam cutoffs remain **sealed**. Digest `b55e065f…`. Never opened.
* Production weight **0**, action **HOLD**. `alpha/adapter.py` untouched.
* **Family budget: 3 slots. Spent: 1 (Family 1). Remaining: 2.**
* Family 1 is **not** re-tested with a larger model, a different learner, another
  horizon, or one more carrier (§2.9, §21). No Family 1′.
* If Families 2 and 3 also fail, §21 requires concluding that the *formulation* is
  wrong and stopping — not opening a fourth family. That is a §27F reporting stop.

## Next decision point

Family 2 is **Form 4 insider transactions**. Its **§2.6 power gate was computed
2026-08-09 and PASSED** (`reports/FAMILY2_POWER_GATE.md`): MDE +0.007 against an
achievable half-width of 0.00205, with ~30× design headroom confirmed by an oracle
ceiling. **Slot 2 remains UNSPENT and Family 2 is not implemented.**

A passed power gate authorizes nothing. Before Family 2 could run it needs, in order:

1. **explicit human authorization** to spend slot 2 of 3 — **still outstanding**;
2. ~~**§2.10 clause-3 admissibility**~~ — **done 2026-08-09, PASS.** mean |ρ| **0.1313**
   vs `z__ret_12_1` (ceiling 0.30) and **0.1432** highest against the 34-column set
   (ceiling 0.50). Ceilings were fixed in the preregistration before the correlation was
   read. `reports/FAMILY2_ADMISSIBILITY.md` §4;
3. a **preregistration** — **written and frozen on §1–§5** by the account holder
   (`alpha/V3_FAMILY2_PREREGISTRATION.md`), using the bounded-combination design as
   required. **§6, the primary prediction horizon, is unresolved** and a preregistration
   with an open element is not valid.

**Turnover, the last blocked input, is also measured:** extra turnover of Arm 1 over B3 is
**+0.3 pp** against a 30 pp allowance, so the **+0.007 MDE stands** as a measurement
rather than an assumption.

**Two facts found while measuring, both reported and neither repaired:**

* **Coverage is 13.6%, not 95.9%.** The gate's 0.959 was the share of names with *any*
  Form 4; the frozen feature admits **open-market purchases only**, so a median of 62
  names of ~455 carry a non-zero value and ~86% are tied at zero by §5. Measured
  consequence: **Spearman(Arm 1, B3) = 0.9896** and the tilt replaces **5.4%** of the
  traded book. The §2.6 PASS is unaffected — a weaker tilt resolves *more* tightly, and
  the gate blocks only on half-width exceeding the effect — but §2.12 requires that a free
  power gain be read as a warning, so it is on the record **before** the study.
* **The dev-set tail is truncated.** The bulk archives end at transaction date
  **2026-03-30**; `2026q2`/`2026q3` are unpublished (HTTP 404 on 2026-08-09). Ten of 316
  cutoffs are affected and four are empty, so effective **n = 312**. This is the opposite
  of a leak. The front boundary was closed by fetching `2015q4`.

**This remains the place for human review**, and the review needed is now exactly one
decision: **§6, the horizon.** Everything else is measured and passing.
