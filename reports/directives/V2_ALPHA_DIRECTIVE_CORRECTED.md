# System Upgrade Directive: V2 Alpha-Driven Predictive Architecture (Corrected)

## Changelog vs. original draft

| # | Issue in original draft | Fix applied here |
|---|---|---|
| 1 | LambdaRank on ~22-name cross-sections | Ranker demoted to Phase 3; Phase 1 uses plain regression + Spearman IC only |
| 2 | No handling of overlapping-window autocorrelation | Added embargo/purge rule + Newey-West note for IC significance |
| 3 | 7 experiments × multiple metrics, no pre-registration | Added mandatory pre-registration step before running V2-A |
| 4 | Sector map assumed static | Sector/industry assignment must be as-of-cutoff, not current |
| 5 | Breadth computed from the 22-name watchlist | Labeled explicitly as a proxy; real breadth flagged as optional/external |
| 6 | Success criteria qualitative ("positive IC") | Numeric thresholds specified below |


Everything from the original directive that was already sound (frozen validation infra, market/sector/residual alpha ladder, no target-price presentation, gated ModelEvidence, staged V2-A→G rollout, HOLD-by-default logic) is preserved unchanged below.

---

## 0. Non-negotiable constraints (unchanged)

Frozen, must not be modified to make V2 look better:
`pit.py` / point-in-time data door, prediction/score process separation, frozen-prediction mechanism, leakage tests, clustered cutoff-date scoring, outcome-revelation timing, the `ModelEvidence` safety principle (fail closed → HOLD), existing validation methodology and test suite.

New prediction fields go through an **adapter/output layer**. Validation logic itself is never touched.

---

## 1. Redefine the target: alpha, not direction

- **A. Absolute return** `R_asset(H)` — not the prediction target, reference only.
- **B. Market-relative alpha (primary target):** `alpha = R_asset(H) - R_SPY(H)`
- **C. Sector-relative return (secondary target):** `R_asset(H) - R_sector(H)`
- **D. Residual alpha (later stage):** `R_asset(H) - β_market·R_SPY(H) - β_sector·R_sector(H)`

**Correction:** β must be estimated on a fixed, documented rolling window (e.g. 60–252 trading days), using only data available before cutoff *T*, with shrinkage toward 1.0 for short/illiquid histories. Do not re-estimate β on an expanding window that could implicitly include information not yet knowable at *T*.

**Correction:** sector membership used in B/C/D must be the membership **as of cutoff T**, pulled through the same point-in-time data door as prices. Static "current sector map applied to history" is a leakage channel and must be explicitly checked for and disclosed if unavoidable (same disclosure standard as §4 of the V1 report — adjusted prices, universe survivorship).

---

## 2. Do not mix asset classes in one ranking

Primary ranking universe: liquid, comparable **equities only**. Exclude BTC/ETH, FX, and broad/commodity ETFs from the equity cross-sectional model; they may get separate models later.

**Correction / open risk to flag explicitly:** the current watchlist is ~22 equities. That is thin for *any* cross-sectional ranking approach — regression, correlation-based, or LambdaRank alike. Before investing in a ranker (§14, Model B), either (a) expand the universe to a broader liquid-equity set (e.g., S&P 500 or a sector-balanced 100–300 name subset) where point-in-time price history is available, or (b) treat all ranking results from a 22-name universe as **directional signal about the methodology, not production-ready evidence**, and say so in every report the same way the V1 report flagged its 12-cutoff limitation.

---

## 3. Primary horizon

- Disable the 4-hour after-close horizon in V2. Do not invert it, do not retrain around it — exclude it, per the V1 recommendation (which itself carried the overnight-gap caveat).
- Primary horizon: **5 trading sessions**.
- Secondary horizon (later): 1 trading day. Do not optimize both simultaneously in the first pass.

---

## 4. Primary target definition

```
future_asset_return_5d = Close[T+5] / Close[T] - 1
future_spy_return_5d   = SPY[T+5]   / SPY[T]   - 1
alpha_5d = future_asset_return_5d - future_spy_return_5d
```
The model never sees `future_spy_return_5d` (or any future value) at prediction time; it exists only in the scoring stage, same as V1's two-process separation.

---

## 5. Secondary target: cross-sectional rank

At each cutoff *T*, rank all eligible equities by realized `alpha_5d` and convert to percentiles (top 20% / 60–80% / 40–60% / 20–40% / bottom 20%).

**Correction on grouping/independence:** cutoff dates chosen for training and evaluation must respect the same "effective independent sample" logic the V1 report applied to statistics (§Statistics: 30 symbols on one date ≠ 30 independent draws). For ranking:
- `group = cutoff_date`, never `group = symbol` — kept as originally specified.
- If cutoffs are spaced closer together than the horizon (5 sessions), consecutive groups' outcome windows overlap and their errors are serially correlated. Either (a) space evaluation cutoffs ≥ H sessions apart when computing summary IC statistics, or (b) apply an embargo/purge scheme (Lopez de Prado–style) and report Newey-West or block-bootstrapped standard errors on the mean IC, not naive ones. This directly parallels the "naive binomial intervals are 2–6× narrower" caveat the V1 report already applied — the same discipline must carry over to IC statistics, or the V2 report will make exactly the mistake V1 was careful to avoid.

---

## 6. Do not volatility-scale the target yet

Establish raw 5-day excess return as the clean baseline first (V2-A/B/C). Test `excess_return / pre_cutoff_volatility` as a separate, later experiment (V2-F) so volatility normalization's effect can be attributed independently rather than folded into multiple simultaneous changes.

---

## 7–8. Features: absolute + relative + percentile, not relative-only

For each feature family, generate the absolute value, market-relative spread, sector-relative spread, and cross-sectional percentile, and let the model select — do not pre-remove absolute features on the assumption relative is always better.

Families (unchanged from original, condensed):
- **Momentum:** 1d/3d/5d/10d/20d/60d returns, each also vs. SPY and vs. sector; cross-sectional percentile ranks.
- **Trend:** `close/SMA20 - 1`, `/SMA50`, `/SMA200` (continuous distance, not boolean), each vs. SPY/sector.
- **Oscillators:** RSI absolute, RSI − SPY RSI, RSI − sector RSI, RSI percentile. Let validation determine which representation matters.
- **Volume:** volume/20d-avg, volume surprise, relative-to-sector, relative percentile — computed strictly from data available at *T*.
- **Volatility:** 5d/20d/60d realized vol, ratio to SPY/sector vol, percentile.

**Correction:** any ratio feature (`asset_X / sector_X`, `volume/avg_volume`, etc.) must have an explicit denominator floor or fallback (e.g., minimum average dollar volume) to avoid blow-ups on thin names — the directive said "avoid ratios where the denominator can approach zero" but didn't specify a concrete guard; add one in the feature pipeline code, not just as a principle.

---

## 9. Overnight / intraday decomposition

Keep as specified: separate `overnight_return = Open[T]/Close[T-1] - 1` from `intraday_return = Close[T]/Open[T] - 1`, with rolling stats and SPY-relative versions for both. This directly operationalizes the V1 finding that the 4-hour-after-close signal was overnight-dominated (77% of the move, 82% sign match) — V2 should be able to tell overnight-driven names from intraday-driven ones rather than rediscovering the same confound.

---

## 10–11. Market regime and breadth

SPY/QQQ trend & vol features, VIX level/percentile/changes — all through the same point-in-time data door as everything else (this is a leakage vector if breadth/VIX data is pulled through a separate, unaudited path — flag and test it with the same leakage test structure as `test_future_cannot_change_the_verdict`).

**Correction:** breadth computed from a 22-name watchlist (`% universe above SMA20`, advancers/decliners, etc.) is **not real market breadth** — it's a proxy over an arbitrarily small, non-representative set. Label it explicitly as `watchlist_breadth_proxy` in the schema, distinct from any true broad-market breadth series if one is later sourced. Do not let it silently masquerade as a market regime signal in reporting.

Regime states (BULL_TREND / BEAR_TREND / SIDEWAYS / HIGH_VOL / LOW_VOL) stay deterministic and pre-cutoff-derived, as originally specified; no separate regime model in phase 1.

---

## 12. Sector context

`asset_20d_return - sector_20d_return` as the flagship "is this stock stronger than its peer group" feature — kept as specified, contingent on the as-of-cutoff sector mapping fix in §1.

---

## 13. Remove LSTM from the V2 primary path

Confirmed correct given V1's numbers: 49.9% walk-forward directional accuracy, 59.4% apparent OOS accuracy that is actually −5.2 points vs. always-long, 3.3× oversized predicted magnitude, 0/257 production weight slots ever used. Archive it for comparison only; it does not influence V2 training or gating.

---

## 14. Model stack — corrected sequencing

- **Model A — Alpha regression baseline.** LightGBM/XGBoost/CatBoost regression on 5d excess return vs. SPY. Question: can a tree model find any signal at all. Do not over-tune.
- **Model A′ — Simple factor baselines, run *before* Model B, not after.** 5d/20d/60d momentum rank, relative-strength-vs-SPY rank, relative-strength-vs-sector rank (this was §18 in the original — moved earlier so it acts as a gate: if Model A cannot beat the best single factor, do not proceed to a ranker).
- **Model B — Cross-sectional ranker (LambdaRank),** only after Model A′ shows Model A adds something over the best simple factor, and only once the universe-size caveat from §2 has been addressed or explicitly accepted as a limitation.
- **Model C — Sector-neutral ranker,** after B works: rank within-sector rather than within-universe.

---

## 15. Metrics — accuracy is secondary, not primary

Primary: **Spearman IC** between predicted and realized alpha per cutoff, then mean/median IC, IC standard deviation, IC hit rate (share of cutoffs with IC > 0) — all clustered/aggregated by cutoff date, consistent with V1's statistical discipline.

Secondary: top-quintile realized alpha, bottom-quintile realized alpha, top-minus-bottom spread.

**Correction — numeric thresholds, decided before running any experiment (pre-registration):**
- Mean IC must exceed a pre-specified minimum (e.g., 0.03) with a clustered/block-bootstrapped confidence interval that excludes zero.
- IC hit rate should exceed 55–60% of cutoffs (a coin-flip-consistent hit rate around 50% is not evidence, mirroring how V1 treated 53.7% direction accuracy as "not demonstrated").
- Top-minus-bottom spread must be positive with a confidence interval excluding zero, evaluated with the same cutoff-clustering used throughout V1.
- These thresholds must be written down in the experiment log **before** V2-A is run, not chosen after seeing results — otherwise V2 repeats the exact mistake V1's authors clearly worked hard to avoid (post-hoc rationalization of a marginal number).

---

## 16–17. Portfolio-level test, neutralized

Top-quintile vs. bottom-quintile long-short return, both raw and market-neutral (balanced long/short exposure so beta doesn't drive the result), with sector exposure reported where practical. Credit should go to "best stock vs. its own sector peers," not "was long tech before tech rallied" — kept as specified.

---

## 18. Baselines

Momentum-rank family (§14 Model A′) plus relative-strength-vs-sector rank. The model must beat the best simple factor on the *same* dates and after the *same* costs — not just beat a coin flip. This is the single most important bar in the whole directive; do not relax it if results are disappointing.

---

## 19. Walk-forward discipline

Train → validate → test in strict temporal order, no shuffling, grouping by cutoff date for ranking, hyperparameter selection confined to the historical (development) period. **The 12 original frozen dates remain the exam paper and are never touched during development** — kept exactly as specified; this is correct and should not be watered down under time pressure.

---

## 20. Expand cutoffs — with the autocorrelation fix from §5

Target 50–100+ cutoffs where data allows, still counting *independent dates*, not stock-count, as the real sample size — and applying the embargo/spacing correction from §5 so that expanding the cutoff count doesn't silently reintroduce the "30 symbols on one day aren't 30 independent draws" problem in time-series form.

---

## 21. Pre-registration to prevent feature-selection overfitting

Every experiment gets an ID recording: features, target, horizon, model, hyperparameters, training window, universe, benchmark, and results, in a maintained development/validation split kept separate from the frozen report — as specified, plus the explicit "write success thresholds before running" rule from §15.

---

## 22. ModelEvidence — corrected gating criteria

Production weight requires **all** of: positive out-of-sample rank IC (above the §15 threshold, not just >0), positive top-bottom spread with CI excluding zero, stability across multiple cutoff dates (e.g., consistent sign across ≥60% of cutoffs), outperformance vs. the best simple factor baseline, no regime-specific collapse, and sufficient effective sample size (independent-date count, per §20). Otherwise: weight = 0, production stays HOLD. This mirrors exactly the discipline that made the `ModelEvidence` gate correct in V1 (it gated the LSTM out 257/257 times, correctly) — the bar should not be lower for V2 just because the architecture is newer.

---

## 23. Confidence — rebuilt later, not now

Do not reuse V1's confidence calc (demonstrably miscalibrated: 90–100 band scored 40% accuracy). Do not expose a sophisticated confidence score until the underlying IC signal is established. A correctly weak/absent signal is more valuable than a confidently wrong one.

---

## 24–26. Presentation, decision logic, costs

Expose predicted alpha, rank percentile, model evidence, and evidence strength — never a fabricated `target_price`. Decision logic stays a HOLD-by-default cascade (insufficient evidence → weak alpha → non-extreme rank → non-positive historical spread → out-of-validated-regime → HOLD; else LONG/SHORT). Transaction costs and turnover evaluated once a signal survives everything above — schema should reserve fields for gross/net alpha and turnover now even if not populated yet.

---

## 27. Experiment sequence (unchanged order, gates tightened)

V2-A (regression baseline) → **gate: must beat Model A′ simple factors, per §14/§18** → V2-B (relative features + cross-sectional ranks) → V2-C (LambdaRank, contingent on §2 universe-size caveat) → V2-D (sector-neutral ranking) → V2-E (regime/VIX/breadth/overnight decomposition) → V2-F (volatility-adjusted target) → V2-G (ensemble + ModelEvidence + confidence + production integration).

---

## 28–29. Success and failure criteria

Success requires **multiple independent signs of alpha** (positive OOS rank IC exceeding the pre-registered threshold, positive top-quintile/negative bottom-quintile excess return, positive top-minus-bottom spread, robustness across periods/regimes/symbols, and outperformance vs. simple momentum) — not accuracy > 50%.

Failure is an explicitly allowed, first-class outcome: if IC ≈ 0, spread ≈ 0, or ML ≈ simple momentum, the correct response is to record the result and stop — not add complexity, not loosen the HOLD gate, not tune until the 12 frozen dates turn positive. This is the same intellectual honesty the V1 report modeled throughout, and it is the hardest rule in this document to actually follow under pressure to "make it work."

---

## 30. Deliverables

1. Alpha regression model (5d excess return vs. SPY)
2. Cross-sectional ranking model (5d alpha rank), gated behind §2/§14 caveats
3. Alpha feature pipeline: relative momentum/trend/RSI/volume/volatility, as-of-cutoff sector-relative features, market regime, overnight/intraday decomposition, cross-sectional percentiles — all through the point-in-time data door
4. Walk-forward model evidence report: IC, rank IC, IC hit rate, top/bottom quintile return, spread, vs. SPY, vs. simple momentum baseline — with pre-registered thresholds and clustered/embargoed statistics
5. Confirmation the existing validation harness consumes V2 predictions unmodified
6. Comparison report: V1 vs. V2 regression vs. V2 ranker vs. simple momentum vs. always-long, on identical cutoff dates, with the same honesty standard as the V1 report (wide intervals disclosed, "not demonstrated" used where appropriate, no result overstated)

---

## Final objective (unchanged)

Build a system that identifies relative winners and losers *before* the outcome occurs, proves that ability through point-in-time walk-forward testing, and refuses to trade when that ability cannot be demonstrated.

```
NO LEAKAGE
  → VALID ALPHA TARGET (as-of-cutoff sector/beta)
  → RELATIVE FEATURES (absolute + relative + percentile, not relative-only)
  → SIMPLE FACTOR BASELINE GATE
  → TREE / RANKING MODEL (ranker gated on universe-size caveat)
  → OUT-OF-SAMPLE IC (embargoed, clustered, pre-registered thresholds)
  → TOP/BOTTOM QUINTILE SEPARATION
  → ROBUSTNESS ACROSS DATES
  → BEAT SIMPLE ALPHA BASELINE
  → MODEL EVIDENCE (numeric gate)
  → CONFIDENCE (built last)
  → PRODUCTION ACTION
```

A boring model with a small, repeatable, statistically defensible alpha is success. A beautiful ranking UI without a pre-registered, embargo-corrected, cluster-robust positive IC is not.
