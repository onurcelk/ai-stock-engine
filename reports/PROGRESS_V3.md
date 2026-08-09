# V3 Programme — execution progress

Tracks execution of `ai stock prediction master roadmap.md` (v2, 2026-08-09), which
lives outside the repository at `Desktop/AI Stock/`. Versioned from the first day, on
the V2.3 audit's lesson that an untracked record makes every claim about it
unfalsifiable.

**Session started 2026-08-09.** Everything below has been run and committed locally.
**Nothing has been pushed** — `origin` is a third party's public repository (§27A).

---

## The one thing that matters if you read nothing else

**ALL THREE budget slots are spent. All three families were REJECTED. Under §21 the
V3 family-testing programme is CLOSED** - no fourth family, no Family 1'/2'/3', no
re-test at another horizon. The comparative diagnosis §21 requires is in
`alpha/V3_FAMILY3_REPORT.md` §8 and summarised below.

| Family | Information | Own IC | Arm 1 - B3 | Decision |
|---|---|---|---|---|
| 1 | EDGAR fundamentals, time-series SUE | **+0.01305, CI excludes zero** | +0.00090 | REJECT |
| 2 | Form 4 insider open-market purchases | -0.00547, CI spans zero | -0.00096 | REJECT |
| 3 | 13F institutional holdings change | -0.00659, CI spans zero | **-0.00339** | REJECT |

**What failed, and what did not.** Not power - every family resolved 2-25x better than
its +0.007 MDE. Not point-in-time quality - three tested doors, and Family 3's cannot
leak by construction. Not coverage - 93%, 13.6% and 85.6% failed alike. Not the target -
the same IC resolves B3 at +0.02241.

**The information failed, in three distinguishable ways:** Family 1 was **real but not
incremental**; Family 2 was **absent and structurally untradeable** (86% tied at zero, so
no name reached the bottom quintile at any of 316 cutoffs); Family 3 was **absent and
orthogonal** (|rho| 0.0726 against momentum - the cleanest test of the three, and still
nothing).

**Two formulation-level faults the evidence points to.** First, every family was tested as
a bounded tilt at lambda 0.25, which is 0.97-0.99 correlated with B3 *by construction* -
the design bought resolution by surrendering the authority needed to move anything, and
the binding constraint is the ~500-cutoff history rather than the choice of information.
Second, §27B's free-data constraint and TARGET_DESIGN §4.2's 5D/10D cap were set
independently and **jointly select for a mismatch**: free filing-timestamped data is
quarterly-to-event and 45-135 days stale, and it was tested against a 5-session horizon.
**Whether the horizon was wrong is now unresolvable** - §2.9/§21 bar re-testing any
rejected family at 10D or 20D.

---

### The earlier reading, superseded

**Two of the three budget slots are now spent, both on rejections. One remains.**
Family 1 (reported fundamentals / SUE) and Family 2 (Form 4 insider open-market
purchases) were each tested and REJECTED on their pre-registered rules. **If Family 3
also fails, §21 requires concluding the *formulation* is wrong and stopping — not
opening a fourth.**

The two failed differently, and the difference is the most useful thing V3 has produced.
**Family 1's factor was real but not incremental** — SUE's own IC cleared zero and it
still could not add to B3. **Family 2's factor was not there at all** — insider purchase
intensity scores IC −0.00547 with a CI spanning zero, the opposite sign to its
pre-registered prior, and it cannot even form a short book (§ below). A family can fail
because its information is redundant, or because its information is absent; V3 has now
seen one of each.

### Family 1, in detail

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
| **[x]** | §7 | Phase 5 information-only test, Family 2 | `V3_FAMILY2_REPORT.md` → **REJECT** |
| **[x]** | §2.6 | Power gate, Family 3 | `alpha/out/f13_gate.json` → **PASS** |
| **[x]** | §7 | Phase 5 information-only test, Family 3 | `V3_FAMILY3_REPORT.md` → **REJECT** |
| **[–]** | §8 | Phase 6, first model | **permanently blocked**: requires a Phase 5 CONTINUE. All three families returned REJECT and the budget is exhausted |
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
| **[=]** | §21 | 3 families, no fourth | **3 spent, 0 remain. PROGRAMME CLOSED**; no Family 1′/2′/3′, no fourth |
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
| Family 2 admissibility + rulings | §2.10 | **DONE** — commits `bd0c7aa`, `65c0039` |
| 5 — information-only test, Family 2 | §7 | **DONE — REJECT**, slot 2 spent |
| Family 3 prereg + §2.6 gate | §2.6 | **DONE — PASS** — commit `5cb409f` |
| 5 — information-only test, Family 3 | §7 | **DONE — REJECT**, slot 3 spent. **PROGRAMME CLOSED** |
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

## Family 2 - Form 4 insider open-market purchases: REJECT (2026-08-09)

Ran on explicit authorization. **Budget slot 2 of 3 is SPENT. Spent: 2. Remaining: 1.**
Full record in `alpha/V3_FAMILY2_REPORT.md`; artefacts in
`alpha/out/v3_family2_development.{json,pkl}`.

316 development cutoffs, 143,675 rows, feature non-zero 0.135 (median 62 names),
**exam contamination 0**.

| | mean IC | half-width | 95% CI | hit |
|---|---|---|---|---|
| b3 regime rule (incumbent) | +0.02241 | 0.02328 | [-0.00086, +0.04570] | 0.560 |
| **Arm 0 - raw insider rank** | **-0.00547** | 0.00714 | **[-0.01278, +0.00151]** | 0.478 |
| Arm 1 - B3 + 0.25 tilt | +0.02146 | 0.02306 | [-0.00154, +0.04457] | 0.551 |

**Primary contrast, Arm 1 - B3: -0.00096, half-width 0.00092, CI [-0.00187, -0.00004],
breadth 0.4177, n = 316.**

| Pre-registered CONTINUE criterion | |
|---|---|
| 1 - effect >= +0.010 | **FAIL** (-0.00096) |
| 2 - CI excludes zero | **"PASS" - entirely BELOW zero.** The rule is direction-blind; the honest count is four failures, one disguised |
| 3 - breadth > 0.50 and both halves positive | **FAIL** (0.4177; halves -0.00094 / -0.00097) |
| 4 - survives with BEAR removed | **FAIL** (-0.00115) |

**Noise control PASSED** - 30 paired permutations, median -0.00046, 0.0% above threshold.
**Holm-Bonferroni:** neither arm significant (p_holm 0.0752 both). **Net of costs:** Arm 1
gross -0.00006, net -0.000058 - the sixth time a tilt has failed to pay for its trading.

**Three findings that outlast the rejection:**

1. **This failed at the root, unlike Family 1.** SUE cleared zero standalone and lost only
   when asked to add to B3. This feature does not clear zero at all, and its point estimate
   is the **opposite sign to the pre-registered +1 prior** - with a CI spanning zero, so the
   reading is "no signal", not "an inverted signal". **The sign may not be flipped and
   re-run**; that is a Family 2' and is barred.
2. **The feature cannot form a short book.** The lowest percentile rank any name receives
   is a median of **0.4308** - the 86% tied at zero land mid-cross-section. **No name
   reaches the bottom quintile at any of the 316 cutoffs**, so Arm 0's long-short spread is
   undefined everywhere (n = 0 of 316). A consequence of the pre-registered design, which
   recorded the tie block in advance - not a defect in it.
3. **The +-0.00092 half-width, the tightest ever produced here, was predicted before the
   run and warned about.** `FAMILY2_ADMISSIBILITY.md` §8 measured Spearman(Arm 1, B3) =
   0.9896 and a 5.4% book change beforehand. §2.12's "a free power gain is a warning" was
   correct twice over.

**One correction to a pre-commitment:** §10.3 pre-committed effective n = 312. That holds
for Arm 0's own IC but **not** for the primary contrast, which ran at **n = 316** - at an
all-zero cutoff Arm 1 collapses to exactly B3 and contributes an exact zero rather than
dropping. Rescaling to 312 moves the primary from -0.00096 to -0.00097; no criterion
changes.

**Recommended for Family 3, to be fixed BEFORE its data is touched:** criterion 2 should
read "the CI excludes zero **on the favourable side**". Never as an amendment to a
pre-registration that has already been run.

---

## Family 3 - 13F institutional holdings: REJECT (2026-08-09)

Ran on explicit authorization. **Budget slot 3 of 3 SPENT. All three slots spent, none
remain.** Full record in `alpha/V3_FAMILY3_REPORT.md`; artefacts in
`alpha/out/v3_family3_development.{json,pkl}`. Pre-registration committed at `5cb409f`
**before any measurement**; §2.6 power gate at the same commit.

Ingest: 45 archives (2.7 GB), **20,687,226 holdings events, 11,661 filers, 572 issuers**,
map rate 0.926. The CUSIP bridge failed validation three times before passing - stripped
leading zeros, issuer-overwriting collisions that put **Meta on JPMorgan's CUSIP**, and a
left-shifted CUSIP that only the **check digit** caught. Final validation **14/14
hand-checked mega-caps correct**, and the build refuses to emit a feature if it fails.

Feature defined **0.8556**, median **394 names** per cutoff, continuous with no tie block.
Staleness of the newest usable quarter: **median 92 days, p90 128**.

**§2.10 clause 3 PASS by the widest margin of the three families:** mean |rho| **0.0726**
vs `z__ret_12_1` (ceiling 0.30), highest **0.0780** of the 34-column set (ceiling 0.50).
Genuinely orthogonal information - and still no signal.

| | mean IC | half-width | 95% CI | hit |
|---|---|---|---|---|
| b3 regime rule (incumbent) | +0.02241 | 0.02328 | [-0.00086, +0.04570] | 0.560 |
| **Arm 0 - raw holdings rank** | **-0.00659** | 0.00758 | **[-0.01465, +0.00051]** | 0.475 |
| Arm 1 - B3 + 0.25 tilt | +0.01903 | 0.02368 | [-0.00477, +0.04259] | 0.541 |

**Primary contrast, Arm 1 - B3: -0.00339, half-width 0.00279, CI [-0.00631, -0.00073],
breadth 0.4494, n = 316.**

| Pre-registered CONTINUE criterion | |
|---|---|
| 1 - effect >= +0.010 | **FAIL** (-0.00339) |
| 2 - CI excludes zero **on the favourable side** (A1, `bool(lo > 0.0)`) | **FAIL** (lo = -0.00631) |
| 3 - breadth > 0.50 and both halves positive | **FAIL** (0.4494; halves -0.00253 / -0.00424) |
| 4 - survives with BEAR removed | **FAIL** (-0.00377) |

**Amendment A1 did exactly what it was written for, on its first use.** Under the old
direction-blind wording criterion 2 would have recorded **PASS** here - the interval
excludes zero, entirely below it. A1 turns that into the FAIL it always was.

**Noise control PASSED** - 30 paired permutations, median -0.00142, 0.0% above threshold.
**Holm-Bonferroni: both arms significant** (p_holm 0.0272) - and both significantly
**negative**, so significance is evidence against. **Net of costs:** Arm 1 gross -0.00015,
net **-0.000148** on +0.3 pp extra turnover - the seventh consecutive tilt that fails to
pay for its own trading. Regimes negative everywhere: BULL -0.00417, BEAR -0.00031,
SIDEWAYS -0.00059.

**§2.12 confirmed a third time:** Spearman(Arm 1, B3) = **0.9725**. A bounded tilt on a
strong base buys resolution by surrendering authority.

---

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
3. ~~a **preregistration**~~ — **done. `alpha/V3_FAMILY2_PREREGISTRATION.md` is IN FORCE
   as of 2026-08-09**, using the bounded-combination design as required. **§6 was resolved
   by the account holder: the primary horizon is 5D**, under `TARGET_DESIGN.md` §4.2 *as
   written* — §4.2 is not amended and the 90-trading-day instruction is withdrawn, not
   overridden. The two open data rulings were taken with it: the denominator is **accepted
   as measured** (no cleaning rule added) and the truncated tail is **accepted at
   n = 312** (the ten cutoffs recorded, not excluded). See §10 of the preregistration.

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

**Two consequences pre-committed with those rulings, so they cannot be re-decided after a
result:** 5D is the *shortest* permitted horizon against a slow-signal prior, and §2.9/§21
mean a null may **not** be answered by re-testing Family 2 at 10D or 20D; and the
truncation may **not** be offered as the explanation for a null, nor the ten cutoffs
dropped to strengthen a positive.

**This remains the place for human review, and exactly one gate is left — and it is not a
design question: explicit authorization to spend budget slot 2 of 3.** Every check is
measured and passing; the preregistration is valid; slot 2 is **UNSPENT**. Spending it is
irreversible under §21 — the family may never be re-tested with another feature, learner or
horizon — which is why it is a separate decision from the design ones above.
