# Single-Name Phase 1 — Result

**Run 2026-08-11. Development data only. The 72-cutoff exam was not opened.**

Protocol: `alpha/SINGLE_NAME_PREREGISTRATION.md`, committed at `616e41a` **before** any
forward return was read, any model fitted, any probability produced or any gate evaluated.
Every constant, threshold, arm, metric and gate below was fixed in that commit. Nothing was
added, dropped, re-scoped or re-chosen afterwards.

| | |
|---|---|
| Question | Can the programme's incumbent cross-sectional signal be turned into a calibrated **single-stock** forecast of `P(r₅ > 0)` and `E[r₅]`? |
| Target | `asset_return` — the **absolute** 5-session forward return of one name. Not `alpha_5d` |
| Horizon | **5 sessions**, inherited from `targets.HORIZON`. No second horizon computed |
| Sample | **215 development cutoffs**, 2018-01-26 … 2026-07-28 · **101,137 symbol-dates** · **580 symbols** |
| Realised up-rate | **0.5370** · mean 5-day return **+0.188%** |
| Budget slots spent | **0.** No new information family. V3 and V4 remain CLOSED |
| Exam cutoffs touched | **0** |
| Production weight | **0.0**, unchanged. `alpha/adapter.py` untouched |
| Tests | **705 passed, 63 skipped** (was 655/63 at baseline; 50 new) |

---

## 1. S0 – S4, the pre-registered incumbents

Every figure is the mean of a per-cutoff statistic over 215 cutoffs, with the 95%
moving-block bootstrap half-width (block 4 cutoffs, 10,000 draws) beside it. 454 names on
one Tuesday are one observation of that week, not 454.

| Arm | What | Accuracy | Log loss | Brier | ROC-AUC | Coverage |
|---|---|---:|---:|---:|---:|---:|
| **S0** | always up | 0.53707 | 3.19833 | 0.46200 | 0.5000 | 0.0000 |
| **S1** | unconditional prior | 0.53707 | **0.69108** | **0.24896** | 0.5000 | 0.4679 |
| **S2** | 12-1 momentum | 0.53707 | 0.69115 | 0.24900 | 0.5016 | 0.4177 |
| **S3** | B3 | 0.53707 | 0.69112 | 0.24899 | 0.5090 | 0.4956 |
| **S4** | B3 × market state | 0.53707 | 0.69084 | 0.24884 | 0.5095 | 0.4896 |

**The accuracy column is not a rounding coincidence.** Across all 101,137 symbol-dates,
**no arm ever emitted `p_up < 0.5`.** S4's probabilities span `[0.5025, 0.6316]`, S3's
`[0.5362, 0.5860]`, S1's `[0.5464, 0.5694]`. Every arm therefore makes the *same
directional call as S0 on every row*, and directional accuracy is identical by
construction rather than by measurement. **Zero SELL calls were produced in the entire
study.**

### Paired probabilistic contrasts

| Contrast | Mean | 95% interval | Half-width | p (block bootstrap) |
|---|---:|---|---:|---:|
| S3 − S1, log loss | +0.000049 | [−0.000305, +0.000398] | 0.000351 | 0.789 |
| S2 − S1, log loss | +0.000076 | [−0.000153, +0.000304] | 0.000229 | 0.512 |
| S4 − S3, log loss | −0.000288 | [−0.001235, +0.000668] | 0.000952 | 0.542 |
| **S4 − S1, log loss (G1)** | **−0.000239** | **[−0.001214, +0.000702]** | 0.000958 | 0.616 |
| S4 − S1, Brier | −0.000120 | [−0.000597, +0.000341] | 0.000469 | 0.608 |

Negative is better. Every interval spans zero. The best point estimate anywhere in the
table is **−0.00024 log loss against a half-width of 0.00096** — a quarter of the
resolution the instrument has.

---

## 2. The four pre-registered gates

| Gate | Requirement (frozen §5.2) | Measured | Verdict |
|---|---|---|---|
| **G1** | best of S3/S4 beats S1 on log loss, interval entirely below zero | S4 − S1 = −0.00024, interval [−0.00121, **+0.00070**] | **FAIL** |
| **G2** | ECE ≤ 0.02 **and** monotonicity Spearman ≥ +0.5 over bins with ≥ 30 cutoffs | ECE = **0.01799** (passes); only **2** of 10 bins are occupied, so monotonicity is **unassessable** | **FAIL** |
| **G3** | covered accuracy > all-row accuracy, interval above zero, coverage ≥ 5%, breadth ≥ 100 | coverage 0.4896 ✓, breadth 578 ✓, difference +0.00649, interval [**−0.00133**, +0.01473] | **FAIL** |
| **G4** | covered accuracy > always-up on the same rows, interval above zero | difference **identically 0.00000**, sd 0.00000 | **FAIL** |

G4 is not a near miss. Because every covered call is a BUY, "accuracy on covered calls"
and "the always-up rate on those same rows" are *the same number computed twice*. The
contrast has no variance because there is nothing there to vary.

---

## 3. The seven questions

### A. Can B3 be converted into a useful calibrated single-stock probability forecast?

**No — and the failure is resolution, not calibration.**

Calibration in the aggregate is respectable: S4's expected calibration error is **0.01799**,
inside the pre-registered 0.02 bar. But calibration is only half of a probability forecast.
The other half is resolution — the ability to say different things about different names —
and there is essentially none:

| Arm | min p_up | median | max | share < 0.5 |
|---|---:|---:|---:|---:|
| S1 | 0.5464 | 0.5549 | 0.5694 | 0.00000 |
| S3 | 0.5362 | 0.5538 | 0.5860 | 0.00000 |
| S4 | 0.5025 | 0.5521 | 0.6316 | 0.00000 |

98.1% of S4's mass falls in the single bin `(0.5, 0.6]`. B3's cross-sectional rank moves
the *absolute* directional probability by about ±2 percentage points around a 53.7%
unconditional drift — never far enough to reach the other side of a coin flip. A forecast
that cannot say "down" is not a direction forecast; it is the base rate wearing a
per-symbol decoration.

The reliability table shows the residual bias, and it points the wrong way:

| Bin | n | cutoffs | mean predicted | realised hit rate | gap |
|---|---:|---:|---:|---:|---:|
| (0.5, 0.6] | 99,197 | 215 | 0.5540 | 0.5365 | **−0.0174** |
| (0.6, 0.7] | 1,940 | 41 | 0.6079 | 0.5603 | **−0.0476** |

Out of sample the model is **overconfident**, by 1.7 points where it lives and 4.8 points
in the thin tail where it is most assertive. The expanding-window prior systematically
overestimates the forward up-rate, and the more the model commits, the worse the gap gets.
That is the opposite of the property the directive asks for ("a model outputting 70% must
empirically win approximately 70% of the time").

### B. Does conditioning B3 on market state improve it?

**Not measurably, and what improvement exists is disqualified by where it comes from.**

S4 − S3 on log loss is **−0.00029 [−0.00124, +0.00067]**, p = 0.54. The point estimate
favours conditioning; the interval is three times wider than the estimate.

More important is the mechanism. S4 fits its own logistic and ridge inside each
`(trend, vol)` bucket that has ≥ 20 prior cutoffs. Inspecting which buckets were actually
fitted, and the sign of the resulting map:

| Bucket | Evaluation cutoffs | Own fit used | Sign of `E[r]` vs `b3_rank` |
|---|---:|---:|---|
| BULL_TREND / LOW_VOL | 87 | 100% | **negative — B3 inverted** |
| BULL_TREND / HIGH_VOL | 77 | 75% | positive |
| BEAR_TREND / HIGH_VOL | 23 | 13% | positive |
| SIDEWAYS / HIGH_VOL | 18 | 0% (pooled) | positive |
| SIDEWAYS / LOW_VOL | 6 | 0% (pooled) | positive |
| BEAR_TREND / LOW_VOL | 4 | 0% (pooled) | positive |

Every point of S4's separation from S3 comes from **one bucket, in which the fit reverses
B3's ranking.** Roadmap §2.5 is explicit that a regime-concentrated result is a
disqualifier, not a discovery, and §0.1 forbids restricting a result to a regime bucket in
order to make it survive. The honest reading is that a walk-forward least-squares fit found
a sign flip in the calmest 40% of the sample, and that this is a lead for a future
pre-registered study at best. It is not evidence, it was not a pre-registered arm, and it
fails the gates in any case.

### C. Is probability confidence actually monotonic with realised accuracy?

**Unassessable on the pre-registered bins, and negative on every diagnostic that can be
computed.**

Monotonicity was to be measured over probability bins holding ≥ 30 cutoffs. Only **two**
bins are occupied at all (S3: one). Three are needed for a rank correlation, so the
statistic does not exist — not because the answer is ambiguous, but because the model
never produces enough distinct probabilities to ask the question.

What can be read points the wrong way. Across the two occupied bins the calibration gap
**worsens** as the probability rises (−0.017 → −0.048). And on the pre-registered
confidence tiers:

| S4 tier | n | accuracy | log loss | Brier | mean 5D return |
|---|---:|---:|---:|---:|---:|
| abstained | 51,620 | 0.5361 | 0.6905 | 0.2487 | +0.00208 |
| high (`\|p−0.5\| ≥ 0.05`) | 49,517 | 0.5379 | 0.6912 | 0.2490 | +0.00167 |

High-confidence rows are **0.18 percentage points** more accurate than abstained rows —
against a level half-width of **2.63 percentage points** — and their realised return is
*lower*. There is no monotone relationship between confidence and outcome here. (No `low`
or `medium` tier survives into a call, because the decision rule's ±0.05 band and the
tier boundary coincide.)

### D. Can abstention meaningfully increase accuracy / expected return while retaining useful coverage?

**No. Coverage is ample; the abstention is selecting on the wrong axis.**

| S4, primary rule | Value |
|---|---|
| Coverage | 0.4896 (49,517 of 101,137) |
| BUY / SELL | **49,517 / 0** |
| Breadth | 578 symbols |
| Covered accuracy (per-cutoff mean) | 0.54003 [0.51008, 0.57426] |
| vs all-row accuracy | +0.00649 [−0.00133, +0.01473] — **spans zero** |
| vs always-up on the same rows | **0.00000**, exactly |
| Covered mean 5D return | +0.00230 [−0.00166, +0.00614] — **spans zero** |
| Uncertainty-gated variant (§4 secondary) | coverage 0.4879, accuracy 0.5381, 578 symbols — indistinguishable |

The rule declines on 51% of rows, but it never declines *because a name looks bad* — it
declines because the market-wide prior that week was not high enough. With zero SELL calls
in 101,137 opportunities, "abstention" here is a market-timing filter on the base rate
wearing the clothes of stock selection.

The pre-declared threshold sweep (a diagnostic; §4 forbids promoting any point on it to a
rule) shows the shape of what is available:

| Threshold | Coverage | n | Accuracy | Mean return on buys | Symbols |
|---:|---:|---:|---:|---:|---:|
| 0.50 | 0.5308 | 53,685 | 0.5377 | +0.00181 | 580 |
| 0.55 (the rule) | 0.4896 | 49,517 | 0.5379 | +0.00167 | 578 |
| 0.56 | 0.2905 | 29,378 | 0.5510 | +0.00312 | 570 |
| 0.58 | 0.0880 | 8,900 | 0.5751 | +0.00721 | 546 |
| 0.60 | 0.0192 | 1,940 | 0.5603 | +0.00794 | 362 |

Accuracy does rise as the bar rises, to 57.5% at 8.8% coverage. It is recorded here and
**not acted on**: the 0.58 point is one of eight on a curve computed after the fact, its
apparent gain (+3.8pp over the up-rate) sits inside the 2.6pp level half-width once its own
much smaller sample is accounted for, and the row at 0.60 is already non-monotone. Moving
the threshold to 0.58 because this table says so is precisely the post-hoc rescue §0.1 and
CLAUDE.md §3.2 prohibit.

### E. What is the strongest incumbent the future prediction engine must beat?

Two incumbents, because two different questions are being asked:

* **Directional: S0, always-up.** Nothing beat it, and nothing even *differed* from it —
  the paired accuracy contrast is identically zero across all 215 cutoffs. Any future
  single-name model must first produce a probability that crosses 0.5 at all.
* **Probabilistic: S1, the unconditional prior** (log loss **0.69108**, Brier **0.24896**).
  S4 owns the better point estimate on both (0.69084 / 0.24884), but under the
  pre-registered rule — the paired interval must exclude zero — S1 is not beaten by
  anything, and it uses no feature whatsoever. A future model must beat a number computed
  from the calendar, by more than 0.001 of log loss.

B3 remains the strongest *cross-sectional* object in the programme, and this study does
nothing to change that. It is not the strongest single-name incumbent — it is not even
distinguishable from having no feature at all.

### F. What minimum improvement is realistically detectable at this sample size?

Measured, not assumed: the 95% block-bootstrap half-width of the paired per-cutoff contrast.

| Metric | Resolution (half-width) | What it means |
|---|---:|---|
| Log loss vs S1 | **0.00096** | 0.14% of the 0.691 incumbent. Nothing smaller is visible |
| Brier vs S1 | **0.00047** | 0.19% of the 0.249 incumbent |
| Mean 5D return on the covered book | **0.00390** | **39 bp per 5 sessions** on the traded set |
| Directional accuracy, paired | **0.00000** (degenerate) | No arm differs from always-up, so there is no difference to resolve |
| Directional accuracy, level | **0.02628** | An unpaired accuracy claim needs > **2.6 pp** to clear its own noise |

So: a future single-name candidate is detectable only if it improves log loss by more than
**0.001**, or moves the traded book's 5-day return by more than **39 bp**. For scale, the
entire measured effect of B3 on absolute 5-day return, top decile minus bottom decile, is
+66 bp (§4) — meaning the effect and the instrument's resolution are the same order of
magnitude. This is the same wall the cross-sectional programme hit: **power is the binding
constraint, not cleverness** (roadmap §0.3, finding 9).

### G. Is the project justified in moving to M2 / new information families?

**No, on three independent grounds.**

1. **The ladder has not earned its first rung.** M0 (calibrated B3) does not beat a
   constant. M1 (B3 + market state) does not beat M0 at resolution. The directive's own
   rule is that every model must earn the right to advance; M2 is defined as "B3 + market
   state + *previously validated independent alpha features*", and the programme has
   **zero** validated independent alpha features — V3 rejected three families, V4 rejected
   the fourth attempt at one.
2. **The budget does not exist.** V3 spent 3 of 3 slots. V4 spent slot 1 and barred slot 2
   on its own pre-registered terms. The MISSION directive itself says not to spend another
   family slot yet, and nothing measured here creates a case for asking.
3. **The resolution arithmetic does not close.** A new family would have to deliver more
   than 39 bp per 5 sessions on the traded book, from free, point-in-time, quarterly-cadence
   data, against a 53.7% drift. V3's three families delivered +0.0009, −0.0010 and −0.0034
   IC against a 0.007 bar. Nothing about a single-name framing makes that arithmetic easier;
   §4 below shows it makes it harder, because the absolute target adds market variance the
   cross-sectional target did not have.

---

## 4. What did show up — recorded as relative, not as a stock prediction

One thing in this study is resolvable, and the directive's Phase 8 and roadmap §9b both
insist it be described for what it is.

Sorting each cutoff's cross-section by S4's predicted return and taking top decile minus
bottom decile:

| Contrast (S4, per cutoff, n = 215) | Mean | 95% interval | p (bootstrap) |
|---|---:|---|---:|
| Top-decile minus bottom-decile 5D return | **+0.00656** | [+0.00220, +0.01005] | 0.0019 |
| Top-decile minus bottom-decile up-rate | **+0.0501** | [+0.0166, +0.0801] | 0.0030 |
| Within-cutoff rank IC vs absolute return | **+0.0453** | [+0.0179, +0.0720] | 0.0016 |

Read this carefully before it is quoted anywhere:

* It is a **relative** result. Every number above is a *within-cutoff* contrast — one
  observation of the market's week, differenced against itself. It says the ordering
  carries information. It says nothing about whether any individual name is going up.
* Roadmap §9b names this case in advance: *"A signal that beats the cross-section but not
  always-up is a portfolio-construction result, not a stock prediction, and must be
  described as one."* That is what this is.
* **It is regime-concentrated and sign-flipped.** As §3B shows, S4's edge over S3 comes
  entirely from one bucket in which the fit inverts B3. S3 — plain B3, no conditioning —
  produces a decile spread of +0.00225 [−0.00160, +0.00663], p = 0.30: not resolvable.
  Under §2.5 the S4 version is a disqualifier as it stands, not a finding.
* It was **not** a pre-registered gate and does not enter the verdict.

Prediction intervals behaved acceptably: nominal 90%, realised **88.5%** across every arm —
slightly narrow, consistent with the same out-of-sample overconfidence the reliability
table shows, and reported rather than corrected.

### Regime table (pre-defined diagnostic, not a selection)

| S4 slice | Cutoffs | Up-rate | Accuracy | Log loss | Coverage |
|---|---:|---:|---:|---:|---:|
| First half | 107 | 0.5422 | 0.5420 | 0.69045 | 0.5076 |
| Second half | 108 | 0.5322 | 0.5322 | 0.69122 | 0.4731 |
| BULL_TREND | 164 | 0.5311 | 0.5311 | 0.69230 | 0.4394 |
| BEAR_TREND | 27 | 0.5855 | 0.5867 | 0.67758 | 0.6770 |
| SIDEWAYS | 24 | 0.5231 | 0.5222 | 0.69574 | 0.6232 |

Accuracy tracks the up-rate to within 0.1 pp in every slice — including BEAR_TREND, where
the 5-day forward up-rate was *higher* than in bull markets. The arm is reading the drift,
not the stock, in every regime.

---

## 5. Verdict

All four pre-registered gates failed. G1 and G3 failed inside their intervals; G2 failed
for want of any resolution to test; G4 failed because the quantity it measures is
identically zero.

**The fundamental limitation is not the architecture, the learner, the calibration method,
the thresholds or the sample.** It is this:

> The programme's incumbent signal, B3, is a **cross-sectional ranking** device. Converted
> honestly into an absolute per-name probability at a 5-session horizon, its entire
> influence is smaller than the market's unconditional drift — so the calibrated
> probability never crosses 0.5, the model never disagrees with "always up", and no
> abstention rule built on it can select a stock rather than a week.

Layer 3 does not lack a model. It lacks an input with absolute directional content. Adding
capacity on top of the same input is the V2.4 that roadmap §0.1 forbids, and roadmap §2.9
("no architecture escalation before information evidence") governs directly.

The harness itself is sound and is the deliverable that survives: point-in-time, two-process,
purged and embargoed, 50 tests including a leak detector that rewrites every outcome the
predictor was not entitled to see and demands a bit-identical prediction file. It is ready
to score any future candidate the moment one exists, and it will say NO EDGE until then.

`alpha/adapter.py` production weight remains **0.0**. The 72-cutoff exam remains **SEALED**
(`b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0`), was not loaded,
scored, inspected or used for any decision in this study, and **no candidate is eligible
for it.**

```text
PHASE 1 VERDICT: DO NOT ADVANCE
```

---

## 6. Artefacts

| File | Content |
|---|---|
| `alpha/SINGLE_NAME_PREREGISTRATION.md` | The protocol. Committed `616e41a`, before any measurement |
| `alpha/singlename_config.py` | Every frozen constant, imported by both stages |
| `alpha/market_state.py` | Layer 1 — interpretable point-in-time market state, nothing fitted |
| `alpha/singlename.py` | Layer 3 predictor. `PastOutcomes` label door; refuses to overwrite its output |
| `alpha/singlename_score.py` | Scorer. Reads outcomes, writes no prediction |
| `alpha/out/single_name_predictions.pkl` | 101,137 frozen predictions × 5 arms. Carries no outcome column |
| `alpha/out/single_name_scores.json` | Every number in this report, re-derivable |
| `alpha/out/single_name_series.pkl` | Per-cutoff series behind every interval |

SHA-256, so an edited artefact stays identifiable:

```text
single_name_predictions.pkl  29726271cc6c398630f284f5a4d36d9ebef068bb0c43e760fc0e8b31662eb0a0
single_name_scores.json      6b2aaa7df1a3d72db25c784a524f5a40a8b168e3d0ddc2911f3417703e78b102
single_name_series.pkl       e9ad9f2f44a71e413e6ad604f4cba21950d93a19f57d8a456e2ae922e5894e1e
```

| `app/tests/test_single_name.py` | 50 tests: frozen constants, PIT, leakage, purge/embargo, calibration, abstention, bounds, determinism, process separation |

Reproduce with `./venv/Scripts/python.exe -W ignore -m alpha.singlename` (refuses to
overwrite a frozen file) then `-m alpha.singlename_score`.
