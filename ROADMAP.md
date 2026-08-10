# Roadmap: Live Data + Making the Results Mean Something

## Status — updated 2026-08-10

| # | Item | State |
|---|---|---|
| 1 | Live data via yfinance + disk cache | ✅ **Done** |
| 2 | Transaction costs, position sizing, interval-aware Sharpe | ✅ **Done** |
| 3 | Directional accuracy, MAE / RMSE | ✅ **Done** |
| 3.3 | Walk-forward validation | ✅ **Done** |
| — | Intraday intervals (1h / 4h) | ✅ **Done** |
| 5a | Portfolio (multi-symbol baskets) | ✅ **Done** |
| 5c | TradingView-style price chart + app-wide dark theme | ✅ **Done** |
| 4 | Reinforcement-learning agents in the UI | ✅ **Done** — 19 of 19 |
| 5b | Run persistence (History tab) | ✅ **Done** |
| 5e | TradingView chrome: toolbar, watchlist rail, range bar | ✅ **Done** |
| **6** | **Ultimate indicator — skill-weighted consensus at 4h / 1d / 1w** | ✅ **Done** |
| **7** | **Tradeable portfolio — buy, sell, ledger, edit-all** | ✅ **Done** |
| **8** | **Lite and Pro split into two applications** | ✅ **Done** |
| — | Point-in-time historical validation (V1 study) | ✅ **Done** — `validation/REPORT.md` |
| **9** | **V2 alpha architecture — predict relative winners, not direction** | ■ **Closed** — architecture abandoned; V3 and V4 closed under their own protocols. See `reports/` |
| 5d | Deploy split, cache warming | ⬜ Not started |

### The verdict walk-forward delivered

Six folds, 30-bar horizon, LSTM at 60 epochs, on **live AAPL daily bars (2021→2026)**:

| Fold | Test window | Accuracy % | Naive % | Beat naive | Directional % |
|---|---|---|---|---|---|
| 1 | 2025-11-17 → 2025-12-30 | 97.67 | 98.02 | no | 43.3 |
| 2 | 2025-12-31 → 2026-02-12 | 92.03 | 94.58 | no | 46.7 |
| 3 | 2026-02-13 → 2026-03-27 | 94.40 | 96.94 | no | 46.7 |
| 4 | 2026-03-30 → 2026-05-11 | 96.04 | 91.74 | **yes** | 53.3 |
| 5 | 2026-05-12 → 2026-06-24 | 96.69 | 96.36 | **yes** | 56.7 |
| 6 | 2026-06-25 → 2026-08-06 | 94.05 | 91.49 | **yes** | 43.3 |

- Mean accuracy **95.14%** against a naive baseline of **94.86%** — a 0.28 point edge.
- **3 of 6** folds beat the baseline. That is a coin flip.
- Directional accuracy **48.3%**, i.e. *below* chance, ranging 43–57% by fold.
- Mean absolute error **$11.16** on a stock trading near $300.

Note fold 1: the **highest** accuracy of the six (97.67%) and it still lost to the naive
baseline, with 43% directional. A single split landing on that window would have been
reported as the model's headline result. That is precisely the failure mode walk-forward
exists to catch, and it is why this repo's advertised 95%+ accuracies mean nothing.

**What the first three changed, measured on `GOOG-year`:**

- Training samples available: **222 → 11,474** (live AAPL at `max`).
- Turtle agent under fair sizing: **3.62% → 14.75%** on identical signals. The old
  number was mostly a sizing artefact, exactly as suspected.
- LSTM on a 30-day window: **96.62%** by the repo's metric, **53.33%** directional.
  The second number is the real one.
- Canary intact: the turtle agent still returns **3.6198%** at zero cost with fixed
  sizing, matching the original notebook.

---

## Priority 6 — The ultimate indicator  ✅ DONE

Everything before this produces *a* number. None of them is a decision, and
averaging them would only have produced a more confident average of things
that mostly do not work — the walk-forward table above is on record that the
LSTM is below a coin flip on direction.

So `app/core/ultimate.py` does not average opinions. It **measures** them, per
symbol and per horizon, and weights each one by what it has actually been
worth out of sample. `app/core/indicators.py` supplies the evidence: ten
technical sources plus the three rule-based agents' standing positions, all
expressed on one [-1, +1] scale so a single calibrator can score them against
the same forward returns.

### How a source earns weight

1. Score the whole history on the source's own scale.
2. Keep the bars where it actually had an opinion (|score| ≥ 0.15) — grading
   a source on its neutral bars dilutes its hit rate towards 50% however good
   its real calls were.
3. Check the sign of that opinion against the realised forward return, on a
   **held-out final 30%** only.
4. Compute the t-statistic on the **effective** sample size, `samples / bars`.
   Overlapping forward windows are not independent observations: a 5-bar
   return sampled every bar is five views of the same week. Skipping this is
   the single easiest way to manufacture significance out of correlated draws.
5. Below `t = 1.65` (one-sided 5%) the source carries **nothing**. Above it,
   the edge is shrunk by `t²/(t²+1)`.

Nothing here may flip a sign. A source measured as anti-predictive is dropped,
never inverted — inverting on a fit is how you find an edge in pure noise.

### Four things had to be fixed before the numbers meant anything

Each of these was a real output of an earlier pass, and each has a test:

- **The least-insignificant source carried the verdict.** With shrinkage but
  no floor, AAPL's 1-week horizon handed **70% of its weight** to a 54.0% hit
  rate at *t* = 0.7. Hence `MIN_T`.
- **The family cap did not cap.** Scaling a family down and renormalising in a
  loop converges towards the limit far too slowly to enforce it; three rounds
  left that same agent family at 70% of a verdict it was supposed to be held
  to 55% of. `cap_families()` is now a water-filling solve, and weight lost to
  the cap is *not* redistributed — it was double-counted evidence.
- **One source could produce a full-scale call.** Normalising weights to their
  own total makes them sum to 1 no matter how little evidence there is. They
  are divided by a fixed `REFERENCE_WEIGHT` instead, so thin evidence reads as
  a weak call rather than a confident one made on nothing.
- **One *family* could still produce a 99% confident STRONG SELL.** On
  EURUSD=X a single agent at 58.5% over 77 independent weeks did exactly that.
  Weights are now also scaled by breadth: `FULL_BREADTH = 3` different
  families before a horizon speaks at full volume.

### What it reads on

| Horizon | Bars | Period | Why |
|---|---|---|---|
| 4 hours | 4 × `1h` | 2y | 1h has ~3,500 bars of depth; 4h bars have a tenth of that |
| 1 day | 1 × `1d` | 10y | Exact, no inference |
| 1 week | 5 × `1d` | 10y | Five daily bars, not one weekly one — 5× the observations |

Interval/bar pairings are a **written table**, not `horizon_hours / bar_hours`:
a US session is 6.5 hours, so a day is 7 hourly bars and not 24.

### Confidence is a product of gates, any one of which can zero it

`skill` (weighted edge against `FULL_EDGE`) × `agreement` (share of live weight
on the winning side, rescaled so a 50/50 split is zero) × `coverage` (surviving
weight and breadth). Below `MIN_CONFIDENCE` the score may not name a direction
at all, and STRONG needs `STRONG_CONFIDENCE` on top of the band. Timeframe
alignment moves the **score** but deliberately never the confidence —
horizons agreeing is evidence about direction, not about measurement quality.

### What it actually says

Across eighteen symbols on ten years of daily bars: **13 HOLD, 5 with a call.**
SPY and VOO read STRONG BUY on six-to-seven sources across four families at
53–60% hit rates and *t* ≈ 2; most single names read HOLD because nothing on
them clears significance. The 4-hour horizon is usually silent — four-hour
direction is close to unpredictable and the engine says so rather than filling
the space.

**This thing is allowed to say it does not know.** When nothing clears the
gates the weights are zero, the confidence is zero, and the conclusion
explains which gate closed. That is not a degraded mode; it is the correct
output for most symbols on most days, and an indicator that cannot produce it
is not measuring anything.

### The forecast and the agents feed in through the same gate

The user-facing ask was that the ultimate indicator read the forecast and
trading-agent reports and reach a conclusion. Both do, and neither is trusted:

- **The agents** enter as `indicators.stance()` — their signal series is an
  *event* series, so read literally an agent has no opinion on 95% of bars
  including almost always the last one. Forward-filling recovers the standing
  position, which is the thing worth scoring. They are then calibrated exactly
  like a technical source, and the turtle agent is routinely dropped at 38–43%
  on trending indices.
- **The forecast** needed a new function. `run()` and `walk_forward()` both
  predict windows that already happened — which is what makes them scoreable
  and also why neither is a forecast. `forecast.project()` trains on every bar
  and rolls past the last one, and `ultimate.ModelEvidence` pairs that
  direction with the walk-forward's measured directional accuracy. At the ~48%
  this repo measured, it earns a weight of exactly zero.

### A cache bug this exposed

`live.fetch()` trusted a cached file whenever it was *fresh*, so a 1-year
download in the morning answered a 10-year request in the afternoon — silently,
with a tenth of the bars. Every calibration here sizes itself to the history it
is handed, so this was not cosmetic. The metadata now records the widest period
ever requested (`is_wider()`), and the returned frame is trimmed to what was
actually asked for, which also makes the Pro sidebar's History selector do
something for the first time.

---

## Priority 7 — A portfolio you can change  ✅ DONE

The book was previously editable only through a table inside a Pro-only
expander, which made buying something the hardest thing in the app to do.
`app/core/holdings.py` now owns the changing of positions as well as their
valuation:

- `buy()` / `sell()` are pure functions returning a new book plus the
  `Transaction` that produced it, so the arithmetic is testable and does not
  live in a Streamlit callback.
- Average-cost basis. Commission goes **into** the basis on a buy and **out of**
  the realised on a sell, which is what makes P&L mean what a broker statement
  means.
- Selling more than is held is refused, not clamped. A short is a different
  instrument with different risk and quietly turning a typo into one is the
  worst possible way to find that out.
- A trade ledger in `app/transactions.json` (gitignored alongside
  `holdings.json`), giving realised P&L and total commission that come from
  recorded trades rather than from prices.
- The UI is a trade ticket — side, size, price prefilled from cache, commission
  — plus **Edit all**, which is no longer behind Pro. Correcting a wrong cost
  basis is bookkeeping, not an advanced feature.

**One bug worth recording, because it wrote to a real file.** Every path here
defaulted its store to `STORE` in the signature, which binds the value at
import. Monkeypatching the module attribute therefore had no effect, and the
first headless run of the new portfolio tab posted a live position into the
actual `holdings.json`. Paths are now resolved at call time via `_store()` /
`_ledger()`, `test_ui.py` has an autouse fixture redirecting both, and
`test_holdings.py` ends with the test that pins the behaviour.

---

## Priority 8 — Lite and Pro are two applications  ✅ DONE

They used to be one app with a knob count, which only made Lite a worse Pro.
They now differ in what they are *for*:

| | Lite | Pro |
|---|---|---|
| Tabs | Signal · Chart · Portfolio | Ultimate signal · Overview · Trading agents · Forecast · Portfolio · Monte Carlo · History |
| Opens on | The buy/hold/sell call | The same call, opened into every measurement behind it |
| Portfolio | The book you hold | The book, plus hypothetical baskets |

Lite leads with the verdict card, three horizon cards and the written
conclusion, then the chart. It cannot reach the agents, the forecast, the
walk-forward or Monte Carlo at all — `test_ui.py::test_the_modes_are_different_applications`
is the assertion that would fail if it drifted back into being a trimmed Pro.

Pro's first tab is the evidence: a per-source table carrying hit rate, raw and
independent sample counts, edge, *t*, weight and contribution — including the
`Why not` column for every source that earned nothing, which is usually most
of them.

---

## Priority 9 — V2 alpha architecture  ■ CLOSED

Executes `../V2_Alpha_Directive_Corrected.md`. Lives in `alpha/`, a new package
kept separate from `validation/`, which the directive freezes (§0).

**This entry is a build record, not a live workstream.** The architecture below
was built and tested; the research programmes that ran on it have since reached
their decisions and closed. The V2→V2.3 architecture is abandoned, and the V3
and V4 family-testing programmes are closed under their recorded protocols with
their budgets spent. What follows describes what was constructed and what was
learned about *building* it — the results, the decisions and the reasoning that
produced them live in the permanent record and are not restated or interpreted
here:

| Record | Where |
|---|---|
| Every arm, its decision and its budget accounting | `reports/EXPERIMENT_REGISTRY.md` |
| V2.3 programme status, post-mortem and closure audit | `reports/PROGRAMME_STATUS_V2_3.md`, `reports/V2_3_POST_MORTEM.md`, `reports/V2_3_FINAL_DECISION_AUDIT.md` |
| V3 and V4 progress and closure | `reports/PROGRESS_V3.md`, `reports/PROGRESS_V4.md` |
| Rebuilding any excluded artefact | `reports/V2_3_REPRODUCTION_CHECKLIST.md`, `reports/V2_3_EVIDENCE_MANIFEST.md` |

Nothing in this file reopens any of it. The preregistrations and experiment
logs under `alpha/` are append-only, and a closed programme stays closed.

**The premise it was built on.** The V1 point-in-time study (`validation/REPORT.md`) answered
"can this system predict direction" with a clean no: consensus 53.7%, no
component beating always-predicting-up on its own horizon, 0 of 9. V2 does not
try to answer that question better. It changes the question to **relative**
performance — rank a cross-section by next-5-session return in excess of SPY —
because a market-wide move is most of what direction accuracy was measuring in
the first place, and subtracting it is the only way to find out whether
anything is left.

### Phases executed

| Phase | What | State |
|---|---|---|
| **0** | Frozen-infra audit — confirm `validation/`, `pit.py`, the leakage tests and `app/cache` can be left untouched | ✅ Done. `app/cache` is the V1 universe definition; V2 downloads to `alpha/cache` so the frozen comparison cannot shift underneath it. |
| **1** | Point-in-time universe (§2) | ✅ Done. S&P 500 membership reconstructed by walking the index change log backwards from the current constituent list. **410–500 eligible equities per cutoff, against V1's 22.** |
| **2** | Pre-registration (§15, §21) | ✅ Done, and genuinely prior — written before a single model was fitted. |
| **3** | Alpha targets (§1, §4, §5, §6) | ✅ Done. `alpha_5d`, sector-relative, residual with shrunk rolling β. |
| **4** | Feature pipeline (§7-12) | ✅ Done. 100 features in three tiers. |
| **5** | Statistics (§5, §15) | ✅ Done. Spearman IC, moving-block bootstrap, Newey-West, Holm-Bonferroni. |
| **6** | Models (§14) | ✅ Done. Model A (GBM), Model A′ (six simple factors), gated B and C. |
| **7** | Leakage tests | ✅ Done. **22 tests pass; the 431 that existed at that point still passed.** (Counts are as of the build; the current suite is listed under Testing below.) |
| **8** | Panel freeze (stage 0) | ✅ Done. |
| **9-12** | Development sequence, exam, adapter, reports | ■ Closed. Ran and concluded under the preregistered protocol; decisions are recorded in `reports/EXPERIMENT_REGISTRY.md`. |

### Three corrections in the directive that changed the design, not just the wording

- **§2, the 22-name universe.** The directive offered a choice: expand the
  universe, or label every ranking result as methodology-signal-not-evidence.
  Expansion was taken. Yahoo serves bars for 654 of the 781 names that were
  ever in the index since 2014, so the cross-section is a real one and the
  ranker is no longer blocked by its own sample width. The remaining 127 are a
  **disclosed coverage loss** — index coverage runs 85% in 2016 rising to 100%
  today, biased toward names later acquired or delisted, and that is stated
  rather than netted out.
- **§5, overlapping outcome windows.** Two options were offered: space the
  cutoffs at least a horizon apart, or apply an embargo and report
  block-bootstrapped errors. Both are applied. Cutoffs are spaced **exactly 5
  sessions = the horizon**, so consecutive outcome windows are adjacent and
  non-overlapping *by construction*; the bootstrap and Newey-West intervals sit
  on top of that, for the market's own week-to-week persistence rather than for
  mechanical overlap. The naive i.i.d. interval is printed beside them, in the
  same style as the V1 report's naive-vs-clustered columns.
- **§14, A′ before B.** Model A′ is not a post-hoc comparison, it is a gate.
  `fit_model_b` and `fit_model_c` take a `gate_passed` argument and return
  `None` when it is false, so a ranker that has not earned its place is **not
  built**, rather than built and then caveated.

### What the leakage tests actually do

The V1 study rested on one test — rewrite the future, demand an identical
verdict. V2 has a wider surface, so the same move is applied at each place a
future bar could get in:

| Test | Would fail if |
|---|---|
| `test_future_cannot_change_the_features` | any of the 100 features read past the cutoff — a scaler fitted on the whole series, a percentile over the full panel, a window measured backwards from the end |
| `test_future_cannot_change_a_model_prediction` | the same, carried through a fitted GBM |
| `test_membership_is_as_of_cutoff_not_today` | a name that joined the index in 2021 appeared in a 2019 cross-section |
| `test_training_cutoffs_respect_horizon_and_embargo` | a training label had not resolved by prediction time |
| `test_cutoff_spacing_makes_outcome_windows_non_overlapping` | the §5 spacing guarantee lapsed |
| `test_exam_cutoffs_are_purged_from_development` | development touched the 12 frozen dates |
| `test_ratio_features_survive_a_zero_denominator` | the §7-8 floor were a principle rather than code |
| `test_sector_relative_leaves_the_name_itself_out` | a name were compared against a peer group containing itself |
| `test_block_bootstrap_is_wider_than_the_naive_interval` | the §5 correction were cosmetic |

### Findings from building it, before any experiment has been run

- **Beta shrinkage barely fires, and that is correct.** On 252 clean
  observations the posterior weight is ~0.98, so a well-measured β is left
  alone; the pull only becomes material when `se(β)` is large, which is the
  short/illiquid case §1 actually names. The first version of the test asserted
  the opposite and was wrong about the code, not the other way round.
- **Sector membership can be made point-in-time; sector *labels* cannot.** GICS
  classification is today's, applied backwards. The 2018 Communication Services
  rebuild moved ~two dozen large names at once, so any cutoff before 2018-09
  carries names filed under a sector they were not yet in. This is the same
  class of residual look-ahead as V1's adjusted prices — small, not removable
  without a paid GICS history, and disclosed in every report via
  `membership.sector_drift_note()`.
- **An all-NaN feature column is a hard crash in sklearn 1.9's histogram
  binner.** Such columns are dropped at fit time and the survivors recorded on
  the `Fit`. They are deliberately *not* imputed: a cross-sectional mean would
  be computed from the same cutoff it is filling, which is the exact leak the
  pipeline refuses everywhere else.
- **"Refit quarterly" needs stating in sessions, not cutoffs.** The two are
  identical on the weekly development schedule (13 × 5 = 65 sessions), but the
  twelve exam dates are spread over four years, and a literal every-13th-cutoff
  rule would have predicted 2026 with a model trained through 2022. Recorded
  before the exam ran, so it cannot be mistaken for a post-hoc adjustment.

### The rule that mattered most, and still binds

`alpha/PREREGISTRATION.md` fixed seven numeric criteria in advance — mean IC >
0.03 with a bootstrap CI excluding zero, IC hit rate > 55%, a positive
top-minus-bottom spread, sign stability, **beating the best simple factor**, no
regime collapse, and ≥ 50 independent cutoffs. It also listed, in advance, the
moves ruled out if the result were disappointing: no rescue features, no
re-running the exam dates, no relaxed thresholds, no switching the headline
metric.

Those exclusions did not lapse when the programmes closed — they are the reason
a closed entry cannot be reopened with a larger model, a different learner,
another horizon or one more carrier. The decisions themselves are in
`reports/EXPERIMENT_REGISTRY.md`.

Failure is a complete deliverable here. The V1 report is the standard — it
concluded its own neural forecaster was a provable no-op and said so.

---

## Context

The Streamlit app in `app/` now wraps the repo's notebooks in a working UI (overview,
rule-based agents, neural forecast, Monte Carlo). But it runs on the CSVs the original
repo shipped with, and those are **7–10 years stale**:

| Dataset | Range | Rows |
|---|---|---|
| `GOOG-year.csv` (every notebook's default) | 2016-11-02 → 2017-11-01 | 252 |
| `TSLA`, `AMD`, `FB`, `TWTR`, … | 2018 → 2019 | ~252 |
| `BTC-sentiment.csv` | 5 days in Aug 2019 | 339 |
| `oil`, `eur-myr`, `usd-myr` | ~1 month in 2017 | 24–30 |

Two consequences, and the second is the bigger one:

1. **The data is old.** Nothing here has seen COVID, the 2022 drawdown, or anything since.
2. **The data is tiny.** 252 rows means the LSTM trains on ~222 samples. That is far too
   little for a 128-unit recurrent net, and it is the real reason the forecasts collapse
   into noise. Pulling 10 years turns 222 samples into ~2,500 — a 10× increase that costs
   one API call.

So live data isn't only a freshness fix; it's the precondition for the models being worth
evaluating at all. That's Priority 1. Priorities 2–3 then fix the things that currently
make a good result indistinguishable from a bad one: no transaction costs, unfair position
sizing, and a single 30-day holdout scored with a metric that flatters everything.

---

## Priority 1 — Live data via yfinance  ✅ DONE

Shipped as `app/core/live.py`. Both gotchas below were confirmed against the live API:
`multi_level_index` does default to `True`, and an unknown symbol returns an empty frame
rather than raising. The disk cache lives in `app/cache/` (gitignored).

**Decision: `yfinance`, no API key.** The app needs daily bars for one symbol at a time,
a few calls per session. That is the lightest possible data requirement, and yfinance is
the only option with zero signup friction that also covers equities, crypto (`BTC-USD`)
and FX (`EURUSD=X`) through one interface. Its weakness — unofficial endpoint, can
rate-limit — is neutralised by the disk cache below. See the appendix for what we give up.

### 1.1 New module: `app/core/live.py`

```python
PERIODS = ["1y", "2y", "5y", "10y", "max"]      # yfinance-native period strings
INTERVALS = {"Daily": "1d", "Weekly": "1wk"}

def fetch(symbol: str, period: str = "5y", interval: str = "1d",
          force: bool = False) -> pd.DataFrame
def cache_entries() -> list[CacheEntry]     # for a "cached symbols" list in the sidebar
def clear_cache(symbol: str | None = None) -> int
```

Two details that will otherwise cost an hour of debugging:

- **`multi_level_index=False` is mandatory.** As of yfinance 1.5.2 it defaults to `True`,
  so even a *single* ticker comes back with MultiIndex columns and every downstream
  `frame["close"]` breaks. Also pass `progress=False` (it writes a progress bar to stdout)
  and `threads=False` (irrelevant for one symbol, and it muddies error handling).
- **`auto_adjust` now defaults to `True`**, which is what we want — `Close` arrives
  split- and dividend-adjusted, so backtests don't see phantom gaps on split dates. Set it
  explicitly rather than inheriting the default, which has flipped between releases.

### 1.2 Reuse the existing normaliser — don't write a second one

`app/core/data.py` already contains `_normalise()`, which lowercases columns, finds the
date and price columns by name, coerces numerics and sorts. A yfinance frame becomes
compatible with one call:

```python
frame = data.normalise(raw.reset_index())   # DatetimeIndex -> a "Date" column
```

**Action:** rename `_normalise` → `normalise` (drop the underscore) in `app/core/data.py`
since a second module now depends on it. It is referenced in exactly two places today
(`load`, `load_upload`). Everything downstream — `data.describe()`, the backtester, the
forecaster, every chart — then works on live data unchanged, because they all only ever
see the normalised `date`/`close` shape.

### 1.3 Disk cache — the thing that makes rate limits a non-issue

- Location `app/cache/`, added to `.gitignore`.
- One CSV per `(symbol, interval)` holding the **widest range ever fetched**, plus a
  sidecar `_meta.json` recording `fetched_at`. CSV, not Parquet, deliberately: Parquet
  drags in `pyarrow`, and 10 years of daily bars is ~2,500 rows — a 150 KB file.
- On `fetch()`: if the cache covers the requested range and `fetched_at` is from today,
  slice and return without touching the network. Otherwise re-fetch and merge.
- Layer `@st.cache_data(ttl=3600)` on top for in-session memoisation. Disk survives
  restarts; `st.cache_data` avoids re-reading during a single session's slider fiddling.
- `force=True` (wired to a **Refresh** button) bypasses both.

Net effect: a symbol is fetched **once per day**, no matter how much the user clicks.
Yahoo's limits never come into play at this volume.

### 1.4 UI changes in `app/streamlit_app.py`

The sidebar radio becomes three-way:

```python
source = st.sidebar.radio("Data source", ["Live ticker", "Bundled dataset", "Upload CSV"])
```

Make **Live ticker the default** — bundled CSVs demote to an offline fallback. The live
branch needs: a symbol `text_input` (default `AAPL`), a period `selectbox`, an interval
`selectbox`, a **Refresh** button, and a caption showing the fetched range and cache age.

Include a few quick-pick buttons (`AAPL`, `NVDA`, `BTC-USD`, `EURUSD=X`) — they double as
documentation for Yahoo's symbol conventions, which are not guessable.

**Failure handling matters here** because this is the app's first network dependency.
Wrap `fetch()` and distinguish three cases: unknown symbol (yfinance returns an *empty*
frame rather than raising — check `.empty` explicitly), rate-limited/offline (offer the
cached copy if one exists, with its age shown), and everything else. Never let a network
error reach the user as a traceback; the app already has this pattern in the upload branch.

### 1.5 Dependency check

Add `yfinance` to `app/requirements.txt`. It pulls `curl_cffi`, `peewee`, `frozendict`,
`platformdirs`, `multitasking`. **Run `pip check` afterwards** — this venv holds a
deliberately pinned stack (`tensorflow==2.15.1`, `streamlit==1.39.0`, `protobuf==4.25.5`)
that took two attempts to reconcile, and a numpy or protobuf bump from yfinance's tree
would break TensorFlow. If it conflicts, yfinance ships a `requests` fallback that avoids
`curl_cffi` entirely.

---

## Priority 2 — Make the backtest honest  ✅ DONE

Shipped in `app/core/backtest.py`: `fee_pct` / `slippage_pct`, three sizing modes, an
`exposure_pct` metric, and buy & hold now charged the same round trip so the comparison
is like-for-like. Defaults are zero-cost + fixed units, which is why the canary still
reproduces the notebook exactly.

Two flaws in `app/core/backtest.py` currently make every agent result unreadable.

**2.1 There are no transaction costs.** `run()` fills at the close with zero fees and zero
slippage. The moving-average agent turns over 12 trades on 252 days; at a realistic 10 bps
round trip that is a meaningful drag, and for any higher-frequency variant it is decisive.

Add `fee_pct` and `slippage_pct` parameters, applied on both sides of every fill (buy at
`price * (1 + slippage)`, pay `notional * fee`; the reverse on sells). Surface both as
sidebar `number_input`s defaulting to 0.1% and 0.05%. A strategy that only wins at zero
cost has not won.

**2.2 Position sizing makes the benchmark comparison meaningless.** `max_buy=1` means the
agent buys *one share*. On GOOG at ~$1,000 that deploys ~10% of a $10,000 account, while
the buy-and-hold benchmark deploys 100%. The agent is being asked to beat a fully-invested
benchmark using a tenth of the capital — so the current "3.62% vs 33.41%" headline is
partly an artefact of sizing, not skill.

Add a sizing mode to `run()`: `"fixed_units"` (today's behaviour, kept as default so
existing numbers stay reproducible), `"pct_equity"` (deploy N% of current equity per
signal), and `"all_in"` (full position, the true like-for-like against buy & hold). Expose
it in the agent tab. Then the benchmark delta means something.

**2.3 While in here:** `Result.sharpe` annualises with `sqrt(252)` unconditionally. That is
wrong for weekly bars, which Priority 1.4 makes reachable. Pass the periods-per-year in
from the interval.

---

## Priority 3 — Evaluation that can fail  ✅ DONE

All three shipped in `app/core/forecast.py`, with walk-forward as a mode toggle on the
Forecast tab. `walk_forward()` fits the scaler on each fold's training slice only, so it
has no look-ahead; `run()` deliberately keeps the notebooks' full-series scaling because
its job is to reproduce them. See the verdict table above for what it found.

The app already shows the naive baseline next to the forecast, which is why you can see
the LSTM losing to "assume the price never moves." Three additions turn that observation
into a real evaluation.

**3.1 Directional accuracy.** The repo's metric — `1 - RMS relative error` — is dominated
by price *level*, which is why everything scores 90%+. What actually matters is whether
the model got the *sign* of each move right. Add it to `app/core/forecast.py` alongside
the existing `accuracy()`. Expect ~50%; that is the honest headline and it belongs on the
metric row next to the flattering one.

**3.2 MAE and RMSE in price units.** "Off by $12 on average" is interpretable in a way
that "94.7% accurate" is not.

**3.3 Walk-forward validation.** `forecast.run()` does one split: train on everything but
the last 30 days, predict those 30. A single fold on one arbitrary window is not evidence.
Add rolling-origin evaluation: N folds, each training up to time *t* and predicting
*t+1…t+h*, then aggregate. With 10 years of data (Priority 1) there is finally enough
history for ~10 folds. Report the distribution, not just the mean — a model that is
excellent on 3 folds and catastrophic on 7 should look different from a consistent one.

This is the change most likely to show that the models don't work. That is the point.

---

## Priority 4 — Bring the reinforcement-learning agents into the UI  ✅ DONE

`agent/4.policy-gradient` through `agent/22.neuro-evolution-novelty-search` are all ported
to `tf.compat.v1` and runnable, but only the three rule-based agents are in the UI. They
share a common shape — an `Agent`/`Model` class with `get_state`, `act`, and a `train(iterations,
checkpoint)` loop — so they can go behind one interface:

```python
# app/core/agents/base.py
class RLAgent(Protocol):
    def train(self, prices, iterations, on_progress) -> None
    def signals(self, prices) -> pd.Series      # feeds the existing backtest.run()
```

Because they emit signals, they plug straight into the Priority 2 backtester and inherit
fees, sizing, and the buy-and-hold benchmark for free.

**Status: the interface holds.** `app/core/agents/` now contains `base.py` (shared
windowed-state function, signal emission, training report), plus `evolution.py` and
`qlearning.py`. Both are in the agent dropdown with a Train button, a learning curve,
and a fingerprint that invalidates a trained policy when the data or settings change.

Two findings from porting them:

- **The RL objective is not the reported result.** These agents optimise a simplified
  return — one unit per trade, no costs. On `GOOG-year` the evolution strategy's own
  objective reached **+9.10%**, but the same policy through the real backtester with
  commissions and fair sizing gave **+4.40%**: 33 trades cost $651 in fees. The app now
  shows both numbers side by side, because the gap *is* the finding.
- **A latent bug in the original.** `6.evolution-strategy-agent.ipynb`'s `get_reward`
  reads the global `close[t]` where it means `self.trend[t]`; it only works because the
  notebook happens to bind them to the same list. The port uses `self.trend` throughout.

**Status: complete — all 19 reinforcement-learning agents are in the UI.** (`1`-`3` and
`23` are rule-based and already lived in `strategies.py`, so the RL set is `4`-`22`.)

They are **19 agents from 6 implementations**, because the notebooks' naming enumerates
combinations rather than algorithms. `double`, `duel` and `recurrent` are three
independent edits to one DQN skeleton, so `deepq.py` carries all eight of notebooks 5 and
7-13 as flags; the same applies to actor-critic and curiosity:

| Module | Notebooks | Agents | Shape |
|---|---|---|---|
| `evolution.py` | 6 | 1 | numpy, no gradients |
| `neuroevolution.py` | 21, 22 | 2 | numpy GA, `novelty_search` flag |
| `policygradient.py` | 4 | 1 | TF, one update per episode |
| `qlearning.py` | 5 | 1 | TF, notebook 5's own hyperparameters |
| `deepq.py` | 7-13 | 7 | TF, `double` × `duel` × `recurrent` |
| `actorcritic.py` | 14-17 | 4 | TF, `duel` × `recurrent` |
| `curiosity.py` | 18-20 | 3 | TF, intrinsic forward model |

Further findings from this pass:

- **Vectorising the population methods.** A feed-forward agent picks its action from the
  price window alone — cash only gates whether that action is *executable* — so a whole
  episode's forward pass is one matmul, not one per bar. `base.all_states()` does this and
  is asserted identical to the per-bar `window_state()`. Neuro-evolution trains 15
  generations on 1,254 bars in **0.4s**.
- **The exploration schedule is calibrated for runs nobody makes.** Notebooks 7-20 reset
  epsilon to ~1.0 after the first iteration and decay it by `exp(-0.005 i)`. Over the tens
  of iterations the UI encourages, the agent is still essentially random, and the traded
  episode's return is *identical across all seven Q-variants* because they draw the same
  seeded random actions. The learning curve therefore reports the **greedy** policy's
  return instead, which is also what the evolution agents report. Training is untouched.
- **Two more latent bugs.** Notebooks 14-17 gate the bootstrap on `replay[0]`'s done-flag
  for every entry in the batch instead of `replay[i]`'s; notebook 22's `_memorize` pops the
  item it just appended, so its novelty archive goes inert the moment it fills. Both are
  fixed rather than reproduced, and noted in the module docstrings.

Canary intact: the turtle agent still returns **3.6198%** on `GOOG-year`.

---

## Priority 5 — Polish  ◐ PARTIAL

- ~~**Multi-symbol comparison.**~~ ✅ Shipped as the **Portfolio** tab
  (`app/core/portfolio.py`): weighted baskets, optional rebalancing, per-holding stats,
  and a correlation matrix. Holdings are joined on an inner index so the basket is only
  defined where every member actually traded.
- ~~**Price chart.**~~ ✅ Shipped as `app/core/charts.py`: candlesticks with a volume pane,
  last-price badge, symbol watermark, and range buttons, in TradingView's dark palette.
  Weekends are collapsed only for series that don't trade through them (decided from the
  data, so crypto keeps its Saturday bars), and intraday charts also hide the overnight
  session. Close-only bundled CSVs fall back to the line-and-gradient style.
  `apply_dark()` puts every other pane in the same palette via `base_chart()`, and
  `.streamlit/config.toml` matches the page background to the chart canvas — without it
  the chart reads as a dark rectangle pasted onto a light page.
- ~~**The rest of the page.**~~ ✅ Shipped as `app/core/theme.py` and `app/core/quotes.py`.
  The chart was in TradingView's palette but everything around it was still default
  Streamlit, which is what made the chart read as a screenshot pasted into someone
  else's app. Now the page carries the same chrome: a top toolbar holding the symbol,
  the interval pills (`1H 4H D W M`) and a live price readout; a right-hand rail with a
  quote block, a clickable watchlist and a key-stats panel; a `1D…All` range bar under
  the chart; and metric tiles, tabs, inputs and tables restyled to match. Four decisions
  worth knowing:
  - **`theme.py` imports its palette from `charts.py`.** There is one `#131722` in this
    app and it lives next to the candles that need it; `test_theme.py` asserts they
    cannot drift apart.
  - **The range bar slices the frame, not the x axis.** Plotly's own rangeselector moves
    only the x range, leaving the candles squashed against a price axis still sized for
    five years. Slicing rescales the price axis, the volume pane and the last-price badge
    together, the way TradingView does. `usable_ranges()` also hides keys that would draw
    nothing (`1D` on daily bars) or draw exactly what `All` draws.
  - **A watchlist row is an `<a href="?sym=…">`.** `st.markdown` strips scripts, so a
    query parameter is the only handle read-only HTML has on the app. It costs a page
    load rather than a rerun — acceptable only because every model in session state is
    fingerprinted to the series it is replacing.
  - **`quotes.py` never downloads.** The rail wants a dozen quotes on every rerun, and
    `live.fetch()` would parse a decade of bars and hit the network for each. It reads
    the cache files directly with `usecols`; only the symbol on screen is fetched, from
    the sidebar, where a failure has somewhere to be reported. An uncached symbol still
    gets a row — dashes, still clickable, fetched properly once it is the one selected.
- ~~**Persist runs.**~~ ✅ Shipped as `app/core/runs.py` plus a **History** tab. Forecast,
  walk-forward and agent results are written to `app/runs/` the moment training finishes,
  so a browser refresh no longer discards minutes of work, and runs can be compared across
  sessions. One JSON file each — not a pickle, which is tied to the library versions that
  wrote it and unsafe to load. Agent runs keep the buy/sell indices and equity curve rather
  than the full per-bar signal; the folder prunes to the newest 200. Results stay local:
  `app/runs/` is gitignored.
- **Split requirements for deployment.** TensorFlow makes a ~500 MB image. The overview,
  agent and Monte Carlo tabs need only pandas/plotly. A `requirements-lite.txt` that omits
  TF (hiding the forecast tab) deploys to Streamlit Community Cloud comfortably; the full
  stack needs a container. Note Community Cloud must be pinned to Python 3.11 — TF 2.15
  has no 3.12+ wheels.
- **Cache warming.** An optional script that pre-fetches a watchlist so the app is instant
  on first load and works offline afterwards.

---

## Verification

The suite lives in `app/tests/` and is run with pytest from the repo root:

```
venv\Scripts\python.exe -m pytest              # 655 fast checks, ~41s
venv\Scripts\python.exe -m pytest --runslow    # all 718, ~3m10s
```

Note the two virtualenvs: `venv\` has pytest, `.venv\` has the scientific stack
(tensorflow, yfinance, sklearn, plotly, streamlit). Tests run from the first,
`alpha/` and the app run from the second.

The split matters: the slow marker covers the 19-agent training sweep and the headless UI
drivers, which build TensorFlow graphs and boot Streamlit. Everything else is pure numpy
and pandas and stays under a second, so there is no excuse not to run it.

| File | Guards |
|---|---|
| `test_backtest.py` | **The canary** — turtle on `GOOG-year` at zero cost with fixed sizing returns exactly **3.6198%**, matching the original notebook. Also: fees strictly reduce return, `all_in` approaches buy & hold, the engine never goes short |
| `test_data.py` | All four bundled CSV layouts; column aliasing; currency stripping; tz-aware intraday stamps made naive; `periods_per_year` measured against known frequencies |
| `test_live.py` | Cache round-trip, corruption tolerance, `slice_to_period` trimming, and the error taxonomy — a `RequestError` is never answered from cache, while a plain `FetchError` falls back to it |
| `test_agents.py` | Registry integrity (19 agents, defaults and citations aligned); `all_states()` bit-identical to the per-bar `window_state()`; every agent trains, emits legal signals and clears the backtester |
| `test_charts.py` | Session rangebreaks per asset class — equities collapse weekends, crypto keeps them — the range bar's slicing, and the dark palette's agreement with `.streamlit/config.toml` |
| `test_quotes.py` | The watchlist board: symbology (`BTC-USD` → CRYPTO, `EURUSD=X` → FX), the cache read that goes through metadata rather than the sanitised filename, tolerance of corrupt and half-written files, and — the one that matters — that **nothing here touches the network** |
| `test_theme.py` | Number formatting (a `-3` beside a `312.41` is the bug it exists for), the watchlist's `?sym=` links, that `theme.py` and `charts.py` cannot drift to different hex values, the verdict chrome (the call's colour matches the candles, the meter cannot be pushed off its track, an unreadable horizon is greyed rather than coloured, every class the panels emit is actually styled), and that **no panel lets markup through** — every value reaching a builder is escaped, because an uploaded CSV's filename becomes the toolbar's label |
| `test_indicators.py` | The evidence contract — finite, inside [-1,1], indexed like the frame — on rising, falling, flat, close-only and too-short frames; that every source is **scale-free** so a $3 stock and a $90,000 one read alike; and the sign of each one, which calibration deliberately cannot correct |
| `test_ultimate.py` | An oracle source measures 100% and an inverted one measures 0% and is dropped rather than flipped; only the holdout is scored; overlapping windows are discounted; the family cap converges instead of creeping; confidence vetoes any direction; a random walk produces no call and a real trend does; contributions sum to the score shown beside them |
| `test_holdings.py` | Average-cost basis with commission in it, realised P&L with commission out of it, a refusal to go short, a refused ticket writing nothing — and that every path resolves its store at call time, which is the guard against a test run reaching a real portfolio |
| `test_ui.py` | The real app under `AppTest`: that Lite and Pro are **different tab sets**, that Lite leads with a verdict card naming all three horizons, that Pro exposes the calibration table, that the ticket buys and reaches disk and refuses an oversized sell, every bundled dataset, the interval pills and range bar, the rail's links, and one agent per implementation family trained end to end |
| `test_validation.py` | The V1 point-in-time study: two price series identical before a cutoff and violently different after produce the same verdict to the last decimal |
| `test_alpha.py` | The V2 pipeline, 22 checks — the same rewrite-the-future test applied to 100 features and to a fitted GBM, plus index membership as-of-cutoff, the horizon+embargo training boundary, non-overlapping outcome windows, the exam-date purge, denominator floors under zero volume, leave-one-out sector peers, and that the block bootstrap really is wider than the naive interval |
| `test_strategies.py`, `test_montecarlo.py`, `test_portfolio.py` | Signal contracts; seeded reproducibility; inner-join alignment and weight drift |

**Tests are hermetic, and now they also have to be harmless.** `app/cache/` is gitignored,
so nothing may read it — `test_live.py` redirects `live.CACHE_DIR` into `tmp_path` and
builds what it needs. `dataset/` is tracked, so the bundled CSVs are the only fixture data
on disk. No test touches the network. And since the portfolio tab can now *write*,
`test_ui.py` redirects `holdings.STORE` and `holdings.LEDGER` in an autouse fixture:
a headless run pressing Buy is no longer a hypothetical.

Still worth adding:

1. **Live fetch against the real network**, as an opt-in marker — the current suite proves
   the cache and error handling, not that Yahoo still answers.
2. **`force=True` bypasses the cache** — currently only the fallback direction is covered.
3. **The book and the ledger are two files written in sequence.** `holdings.execute()`
   validates before it touches either, so a *rejected* ticket writes nothing — but an
   accepted one saves the position first and appends the trade second, and a crash
   between them would leave a position with no trade behind it. Realised P&L would then
   disagree with the book. Deliberately not fixed here: the honest repair is one file or
   one journalled write, which is a storage-format change and not a patch to the trade
   ticket. Recorded so it is a known limit rather than a surprise.

---

## Appendix — Provider comparison (as of 2026)

| Provider | Key? | Free tier | History | Notes |
|---|---|---|---|---|
| **yfinance** | No | Undocumented, IP-throttled | 10y+ per call | Unofficial endpoint. Stocks + crypto + FX. **Chosen.** |
| Twelve Data | Yes | ~800 calls/day | Good | Best keyed free tier; the natural fallback |
| Finnhub | Yes | ~60 calls/min | Limited on free | Highest throughput, thinnest history |
| Tiingo | Yes | Very restrictive (reports vary, 20–250/day) | Strong EOD | Excellent data, stingy free tier |
| Polygon.io | Yes | EOD only on free | Strong | Generous paid tiers |
| Stooq | No | Unlimited CSV | ~5y via `pandas-datareader` | No real API; useful as a no-key backup |
| IEX Cloud | — | — | — | **Deprecated, do not use** |

Free tiers change often — re-check before depending on any figure here.

If yfinance does start failing, the migration is contained: `live.fetch()` is the only
function that touches the network, and everything downstream consumes the normalised frame
from `data.normalise()`. Swapping providers means rewriting one function.
