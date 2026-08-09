# Family 2 (Form 4 insiders) — §2.6 power gate

**Computed 2026-08-09. Gate-only decision.** Family 2 is **not implemented**, **not
run**, and **slot 2 of the three-family budget is NOT spent**. No pre-registered
criterion, threshold, abandonment rule or budget was modified by this work. Nothing was
pushed.

This document exists because §2.6 is a **blocking pre-study gate** and §26 requires it to
be "passed and recorded" before an experiment begins.

---

## 1. The exact criterion

Quoted verbatim from `ai stock prediction master roadmap.md` §2.6:

> **This is the rule whose absence cost four studies.** No study may be run before this
> gate is passed, and passing it is arithmetic, not judgement.
>
> 1. **State the smallest effect worth acting on**, derived from the economic threshold
>    and the cost model — not from what the model might plausibly produce.
> 2. **Compute the half-width the planned design will achieve** — cutoff count, spacing,
>    universe, and pairing against the base — using the same moving-block bootstrap the
>    record uses (`alpha/stats.py`, `BLOCK_LENGTH = 4` cutoffs; `block_bootstrap_ci`,
>    `block_bootstrap_p`, `newey_west` and `paired_difference` already exist and should
>    be reused, not rewritten).
> 3. **If the achievable half-width exceeds the effect sought, the study may not run as
>    designed.** Change the horizon, the cutoff count, the history depth, the universe,
>    or the size of effect being chased — or do not run it. Running it anyway produces an
>    unfalsifiable null and burns a family from the §21 budget for nothing.

**The gate blocks on exactly one condition: achievable half-width > effect sought.**

---

## 2. Step 1 — the smallest effect worth acting on

**Carried unchanged from `EXPERIMENT_REGISTRY.md` §6.1. No new threshold is introduced
here.** The derivation is programme-level, not Family-1-specific: it comes from the
frozen cost model and the economic threshold.

| Input | Value | Source |
|---|---|---|
| per-cutoff top-bottom spread per unit IC | ≈ **0.10 × IC** | measured 0.091–0.105 across V2.1-C/D, V2.3-A/B |
| economically meaningful net advantage | ≥ **+0.0004/week** (~2%/yr) | §10 economic threshold |
| assumed cost drag at 5 bps | ≈ **0.0003/week** | frozen cost model |
| ⇒ required gross spread advantage | ≥ 0.0007/week | |
| ⇒ **MDE** | **+0.007 IC vs B3** | 0.0007 / 0.10 |

**MDE = +0.007 IC.**

### 2.1 The one input this step depends on that Family 2 has not determined

The 0.0003/week drag corresponds to an **extra-turnover allowance of ≤ 30 percentage
points** (0.0003 = Δturnover × 2 × 5bps ⇒ Δturnover = 0.30). Family 1's measured extra
turnover was −0.004 — turnover *fell*, because quarterly fundamentals are slow. **Form 4
is event-driven and its turnover is unknown without implementing Family 2.**

**This does not threaten the gate, and the direction matters.** Higher turnover raises
the MDE, i.e. enlarges the effect being sought, which makes the half-width comparison
*easier* to pass, not harder. It is recorded because it makes the eventual **study**
harder — a Family 2 that turns over fast must hypothesise a correspondingly larger
effect — and that belongs in a preregistration, not in this gate.

---

## 3. Step 2 — the half-width the planned design will achieve

### 3.1 Inputs computed from existing infrastructure

| Input | Value | How obtained |
|---|---|---|
| Cutoff count | **316** development cutoffs | `examset.load().development` — the 72 exam cutoffs untouched |
| Spacing / horizon | 5 sessions, non-overlapping | unchanged from the record |
| Base for pairing | **B3 regime rule**, rank-transformed | `protocol.benchmark_scores` |
| Bootstrap | moving-block, `BLOCK_LENGTH = 4`, 10,000 draws | `alpha/stats.py`, reused not rewritten |
| **Universe — Form 4 availability** | **measured, see below** | `alpha/edgar/submissions.zip`, already on disk |

**Form 4 availability**, measured from the filing index only — form type and
`acceptanceDateTime`. **No Form 4 XML was fetched or parsed; no transaction direction,
size, price or owner was read.** The audit's acceptance rule is applied: a filing counts
at cutoff *T* only if accepted (ET) < 16:00 ET on *T*.

| | |
|---|---|
| Issuers scanned / with any Form 4 | 619 / **614** |
| Form 4 filings indexed | **912,564**, 1996-03 → 2026-08 |
| **Accepted after the 16:00 ET close** | **65.5%** — higher than the 51.8% measured for 10-K/10-Q |

Share of the point-in-time cross-section with ≥1 Form 4 in the trailing window:

| Lookback | median | p10 | min | mean names |
|---|---|---|---|---|
| 30 days | 0.754 | 0.671 | 0.554 | 345 |
| **90 days** | **0.959** | 0.931 | 0.919 | 437 |
| 180 days | 0.987 | 0.953 | 0.943 | 445 |
| 365 days | 0.989 | 0.955 | 0.953 | 446 |

**Coverage is not the binding constraint.** Windows are reported, not chosen — selecting
one is a design decision belonging to a preregistration.

### 3.2 Method, and its validation

§2.6 step 2 asks for the resolution of the **design**, not of a particular feature. For
the bounded arm `rank(b3) + λ·(rank(x) − 0.5)`, the variance of the per-cutoff paired IC
difference is driven by how far the tilt moves ranks — set by λ and by coverage — not by
whether *x* predicts anything. The half-width is therefore measured with **coverage-matched
uninformative features** (uniform random draws on exactly the names a real feature would
cover), 24 independent draws per level. **No Form 4 content enters this computation.**

**Validation against the one real measurement available:** at Family 1's coverage
(0.930) the procedure returns **0.00194**, against Family 1's actually-measured
**0.00229** — a ratio of **0.85×**. The estimator runs ~15% narrow. **A ×1.18 correction
is applied throughout below**, derived from that comparison. This is a calibration of the
estimator against a known measurement, not a new assumption; the raw figures are shown
alongside so the correction is visible rather than baked in.

### 3.3 Result

| Design universe | raw half-width | **calibrated (×1.18)** | vs MDE +0.007 |
|---|---|---|---|
| Form 4, 30d lookback | 0.00329 | **0.00388** | 1.8× inside |
| **Form 4, 90d lookback** | 0.00173 | **0.00205** | **3.4× inside** |
| Form 4, 180d lookback | 0.00157 | **0.00185** | 3.8× inside |
| Form 4, 365d lookback | 0.00158 | **0.00186** | 3.8× inside |
| full-coverage ceiling | 0.00134 | 0.00158 | 4.4× inside |

---

## 4. The §2.12 check — is this a free power gain, i.e. is the arm doing nothing?

§2.12 is explicit that a resolution this good should be treated as a **warning**:
*"resolution and authority are the same dial… a power advantage that appears for free
should be read as evidence the arm is doing nothing."* V2.2's 19× power advantage was
collinearity, and taking it as a gift cost a study.

So the other end of the dial was measured directly: an **oracle tilt** — *x* = the
realised forward alpha, perfect foresight — pushed through the identical arm at Form 4's
90d availability. No real feature can beat perfect foresight, so this is the ceiling of
what the design can express. Again, no Form 4 content is involved.

| λ | oracle arm IC | **oracle advantage over B3** | half-width |
|---|---|---|---|
| 0.10 | +0.11035 | **+0.08793** | 0.00134 |
| **0.25** | +0.23471 | **+0.21230** | 0.00263 |
| 0.50 | +0.41762 | +0.39521 | 0.00566 |
| 1.00 | +0.69945 | +0.67703 | 0.01467 |

**The design has roughly 30× headroom over the MDE at λ = 0.25** (+0.21230 attainable
vs +0.007 required). A real feature would need to be only **3.3% as good as perfect
foresight** to clear the economic floor.

**So the narrow half-width is genuine power, not collinearity.** The arm *can* move a
long way; random noise simply does not move it. §2.12's warning does not apply here, and
this is the check Family 1's gate never performed.

**A note that retroactively strengthens the Family 1 record:** the same headroom existed
there, so Family 1's +0.00090 was a genuine **information** null, not an artifact of an
arm that could not express an effect. The rejection stands on firmer ground than it did
yesterday.

---

## 5. Step 3 — verdict

> §2.6 step 3 blocks a study **if the achievable half-width exceeds the effect sought.**

| | |
|---|---|
| Effect sought (MDE) | **+0.00700 IC vs B3** |
| Achievable half-width (90d universe, calibrated) | **+0.00205 IC** |
| Half-width > effect sought? | **NO** |

# GATE: PASS

**Conditional on the design being the bounded-combination arm.** This is not a caveat
added for comfort; it is a second gate outcome, measured:

| Candidate design | half-width vs B3 | vs MDE | §2.6 verdict |
|---|---|---|---|
| **Bounded combination**, `rank(b3) + λ·(rank(x) − 0.5)` | **0.00205** | inside | **PASS** |
| **Standalone factor** paired against B3 | **0.01949** | **exceeds 0.007 by 2.8×** | **FAIL** |

The standalone figure is not an estimate — it is **Family 1's measured half-width for
Arm 0** (`v3_family1_development.json`), the same design on the same cutoffs. The Phase 2
audit anticipated this: *"a standalone new factor paired against B3 (low correlation)
resolves only ~0.03; the family's decisive claim must therefore be formulated as the
increment of adding the information to the incumbent."*

**Consequence for any future Family 2 preregistration:** its decisive contrast must be
the bounded combination against B3. A standalone-factor formulation does not pass §2.6
and may not be run. Recording this now is the point of a blocking gate.

---

## 6. What could not be computed without implementing Family 2

Reported rather than approximated, as required.

1. **The feature's turnover**, and therefore the exact MDE. The +0.007 floor holds while
   extra turnover ≤ 30pp. Direction is favourable to the gate (§2.1); it makes the
   *study* harder, not the gate.
2. **The feature's correlation with `z__ret_12_1` and the 34-column set** — §2.10 clause 3
   admissibility. **This is a separate gate from §2.6 and it is NOT evaluated here.**
   Family 2 must pass it before any study, exactly as Family 1 did, and its thresholds
   must be fixed before the measurement is read.
3. **The specific feature construction** — net insider buying, cluster buys, officer vs
   director weighting, transaction-code filtering, the lookback window. There is no
   pre-registered Family 2 design; §2.6 was therefore computed for the design the record
   calibrates, stated as an assumption rather than assumed silently.
4. **The effect size itself.** A power gate establishes that an effect *could be seen*,
   never that one exists.

---

## 7. Status after this gate

| | |
|---|---|
| Family 2 implemented | **No** |
| Family 2 study run | **No** |
| **Slot 2 of 3** | **UNSPENT** — budget remains 3 slots, 1 spent (Family 1), **2 remaining** |
| Pre-registered criteria modified | **None** |
| Abandonment / stopping rules altered | **None** |
| §2.10 clause-3 admissibility for Family 2 | **Not evaluated** — still required |
| Exam | still sealed, `b55e065f…`, untouched |
| Production | weight 0, HOLD, adapter untouched |
| Pushed | **No.** `origin` is still a third party's public repository |

**A PASS here authorizes nothing.** It records that *if* Family 2 is commissioned as a
bounded-combination study, its design can resolve the effect it would need to find.
Implementation waits on explicit authorization, a §2.10 admissibility check, and a
preregistration fixing the feature, the window, the arms and the thresholds before the
first fit.

---

## 8. Reproduction

```bash
# universe: Form 4 availability from the filing index (no XML, no transactions)
./venv/Scripts/python.exe -W ignore -m alpha.form4_gate coverage

# half-width from coverage-matched uninformative features, plus the validation
./venv/Scripts/python.exe -W ignore -m alpha.form4_gate halfwidth

# the attainable-effect ceiling (oracle tilt)
./venv/Scripts/python.exe -W ignore -m alpha.form4_gate ceiling
```

Artefacts: `alpha/out/form4_coverage.pkl`, `alpha/out/form4_gate_halfwidths.pkl`,
`alpha/out/form4_gate_ceiling.pkl`. Seed 20260809 throughout.
