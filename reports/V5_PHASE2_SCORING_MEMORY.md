# V5 Phase 2 Outcome Scoring & Performance Memory

**Completion date:** 2026-08-14

**Phase:** PHASE 2 — Outcome Scoring & Performance Memory

**Decision:** GO

**Scope:** An append-only outcome boundary keyed by `forecast_id`, horizon-aware
scoring against realised bars, and performance summaries over the resulting
memory. No adaptive weighting, no model registry, no retraining, no promotion,
and no UI work is included. No model weight is changed by anything measured here.

## 1. Result

Phase 2 adds `app/core/outcome_ledger.py`, which reads frozen Phase 1 forecasts
and realised prices and writes outcomes into a separate, append-only `outcomes`
table. The Phase 1 `forecasts` table is not extended, rewritten, or joined into
a mutable view, and `forecast_ledger.py` was not modified.

The STOP / GO gate — *historical predictions can be objectively scored without
regeneration* — passes:

1. `resolve_outcome` is a pure function of a frozen `ForecastRecord` plus a
   realised price frame. It calls no model.
2. `test_scoring_never_regenerates_a_forecast` monkeypatches `ultimate.evaluate`
   and `forecast.project` to raise, then scores 2 forecasts successfully.
3. Scoring 120 forecasts frozen at 60 historical cutoffs required no
   regeneration and left every frozen payload byte-identical.

## 2. Two-Process Separation

Phase 1 established `forecast_ledger` as the writer that never reads outcomes.
Phase 2 is the reader that never writes forecasts. The arrow points one way:
`outcome_ledger` imports `forecast_ledger`, never the reverse.

This is asserted structurally, not by convention, in
`test_forecast_ledger_holds_no_outcome_access`:

- `forecast_ledger` source contains no `outcome_ledger`, no `outcomes`, and no
  `realised`.
- `outcome_ledger` source contains no `INSERT INTO forecasts`, no
  `UPDATE forecasts`, and no `DELETE FROM forecasts`.

It mirrors the existing `validation/predict.py` ↔ `validation/score.py` split.

## 3. Maturity Is Measured in Bars, Not Calendar Time

A horizon in this repository is a bar count at a stated interval: `1d` is one
daily bar, `1w` is five daily bars, `4h` is four hourly bars. Scoring reads that
mapping back out of the frozen record — `metadata.interval` and
`metadata.bars_used` for an incumbent, `<steps>x<interval>` cross-checked
against `metadata.interval` for a challenger — rather than re-deriving it from a
horizon label or converting to wall-clock time. A record without a frozen bar
mapping is refused, not guessed at.

The anchor is `input_last_bar_at`, the last bar actually observed, because that
is the bar `price_at_cutoff` came from.

## 4. Outcome Schema

`outcome_schema_version` is `1`. Returns are percentage points, matching
Phase 1: `realised_return = 1.25` means `+1.25%`.

| Field | Contract |
|---|---|
| `outcome_id` | `otcm_` plus SHA-256 of every other field. |
| `forecast_id` | The frozen forecast scored. Foreign key; unique. |
| `scored_at` | When the outcome was resolved. |
| `anchor_at` | The forecast's last observed bar. |
| `matured_at` | The bar `bars_ahead` later — where the horizon ends. |
| `interval`, `bars_ahead` | The frozen bar mapping actually used. |
| `price_at_cutoff`, `price_at_maturity` | Anchor and maturity closes. |
| `realised_return` | `(price_at_maturity / price_at_cutoff − 1) × 100`. |
| `realised_direction` | `bullish` / `neutral` / `bearish` by sign. |
| `error`, `absolute_error`, `squared_error` | `predicted_return − realised_return` and its magnitudes. |
| `directional_correct` | True/False, or **null when the call abstained**. |
| `probability_positive`, `brier_contribution` | Null unless the forecast carried a probability. |
| `baseline_source`, `baseline_predictions` | Which baseline, and its full statement. |
| `baseline_absolute_error`, `baseline_squared_error`, `baseline_directional_correct` | The baseline scored on the identical outcome. |
| `baseline_relative_absolute_error` | `baseline_ae − ae`; positive means the forecast beat its baseline. |
| `market_symbol`, `market_return`, `market_relative_return` | Null unless a market frame is supplied. |
| `sector_symbol`, `sector_return`, `sector_relative_return` | Null unless a sector proxy is supplied. See §8. |
| `constituent_directional` | Per-constituent hit/miss diagnostic. |
| `realised_fingerprint` | SHA-256 of the exact scored window. |
| `notes` | `baseline_source`, `sector_status`, `probability_status`. |

### Abstention is not a miss

`directional_correct` is null, not False, when the forecast said `neutral` or
when the bar closed exactly flat. A forecast that declines to name a direction
has not been wrong, and a flat close offers no direction to have named. Both are
excluded from directional accuracy and both remain scoreable on return error.
`n_directional` is reported beside `n` everywhere so the size of the abstention
is always visible.

## 5. Baselines

Every outcome is scored against a baseline, and the baseline's provenance is
recorded rather than assumed.

- If the frozen forecast carries a `baseline_prediction` from forecast time,
  that wins. `baseline_source` is `forecast_record`.
- Otherwise two trivial controls are constructed **from `price_at_cutoff`
  alone** — forecast-time information, no realised price consulted.
  `baseline_source` is `phase2_trivial`.

| Control | Statement | Controls for |
|---|---|---|
| `zero_return` | `predicted_return = 0`, direction `neutral` | error metrics (MAE, RMSE, skill) |
| `always_bullish` | direction `bullish` | directional accuracy |

Two controls are needed because a neutral baseline never names a direction and
so cannot supply a directional accuracy to beat. Drift is the honest directional
control; the random walk is the honest error control.

`mae_skill = 1 − mae / baseline_mae`. Positive means the forecast beat the
baseline it declared. Negative is reported as prominently as positive.

## 6. Performance Memory

`performance_frame` flattens (forecast, outcome) pairs into one tidy row each.
Summaries are computed over that frame:

| Function | Grouping | Purpose |
|---|---|---|
| `summarise` | `(model_key, horizon)` by default | all-history performance |
| `breakdown` | adds `symbol` | suppressed below `MIN_SAMPLES` |
| `expanding_summary` | `(model_key, horizon)` | all-history after each maturity |
| `rolling_summary` | `(model_key, horizon)` | trailing-window after each maturity |
| `calibration` | probability bins | reliability, when probabilities exist |
| `constituent_directional` | `(constituent, horizon)` | per-source diagnostic |

### Every point estimate carries its resolution

No row reports a rate without `n` and a Wilson score interval, and no row
reports a mean without `n` and a normal-approximation half-width. `MIN_SAMPLES`
is **30**, declared in the source before any measurement was taken. `breakdown`
blanks the metric columns of a thin cell but keeps `n` and `sufficient` visible,
so a suppressed row still reports what was withheld.

### Performance memory becomes known at maturity, not at cutoff

`known_as_of(frame, when)` filters on `matured_at`, and this is the single most
important detail in the module for Phase 5. A weight built at time *t* may use
an outcome only once that outcome has happened. Filtering on `cutoff_at` would
admit forecasts whose results were still in the future. The demonstration in §9
shows the gap this closes; `test_performance_memory_is_known_only_after_maturity`
pins it.

### Constituent scoring is a diagnostic, not a ranking

A constituent emits a signal score, not a predicted return, so only the sign of
its call is scoreable. `constituent_directional` reports hit rate with a Wilson
interval and a sufficiency flag and nothing else. What a constituent is *worth*
is a Phase 3 and Phase 4 question; nothing here promotes, demotes, or reweights
anything.

## 7. Immutability

Outcomes are evidence and are written once:

1. `OutcomeRecord` is frozen and recursively freezes nested maps.
2. `outcome_id` is recomputed and validated from the complete payload on load.
3. A `UNIQUE` constraint on `forecast_id` makes a forecast scoreable exactly
   once — re-scoring the same forecast at a later `scored_at` is refused, not
   silently replaced.
4. A `FOREIGN KEY` to `forecasts(forecast_id)` makes an outcome impossible
   without the frozen forecast it scores.
5. SQLite triggers reject all `UPDATE` and `DELETE` against `outcomes`.
6. The stored payload SHA-256 is verified on every read.

## 8. What Is Null, and Why

Nothing is imputed. A field that has no admissible source stays null and says so
in `notes`.

- **`probability_positive` / `brier_contribution`** — null for every current
  production path, because no current path emits a probability. Confidence is
  **not** relabelled as a probability; Phase 1 kept those fields distinct and
  Phase 2 does not quietly rejoin them. `calibration` returns an empty frame
  rather than a fabricated reliability curve. The machinery is implemented and
  tested against forecasts that do carry a probability, so it will work the
  moment a probabilistic model exists.
- **Sector-relative outcome** — this repository has no point-in-time sector
  membership map. `sector_status` is therefore `UNAVAILABLE_NO_PIT_SECTOR_MAP`
  unless a caller explicitly supplies a sector proxy frame and asserts the
  mapping, in which case it reads `CALLER_SUPPLIED_PROXY`. A survivorship-safe
  PIT sector map is a Phase 9 data-gap candidate, not a Phase 2 improvisation.
- **Market-relative outcome** — null unless a market frame is supplied. When it
  is, the reference return is measured over the *identical* anchor-to-maturity
  bar window, and a market frame that does not span that window exactly is
  refused rather than approximated.

## 9. Mechanism Demonstration

Run on a **synthetic random walk**, not market data. It exercises the loop at a
sample size the unit tests do not reach. **It carries no information about model
skill** — the series has no signal in it to find, and no conclusion about the
incumbent may be drawn from it.

60 historical cutoffs, 2 horizons each, 120 forecasts frozen, 120 matured and
scored:

```text
        model_key horizon  n  n_directional  directional_accuracy  ci_low   ci_high  baseline_dir_acc      mae  mae_half_width     rmse  baseline_mae  mae_skill  n_prob  brier
ultimate_ensemble      1d 60             12              0.416667 0.19326  0.680489          0.533333 0.881859        0.179719 1.128604      0.872685  -0.010512       0    NaN
ultimate_ensemble      1w 60              0                   NaN     NaN       NaN          0.500000 2.060534        0.425055 2.649658      2.060534   0.000000       0    NaN
```

Three things this demonstrates about the mechanism, none about skill:

1. **Abstention is visible.** 48 of 60 `1d` forecasts and all 60 `1w` forecasts
   were neutral. The `1w` row reports `NaN` directional accuracy over
   `n_directional = 0` instead of inventing a 50%.
2. **The baseline comparison is live.** The `1w` incumbent emitted exactly
   `0.0` expected move every time, so it *was* the zero-return baseline —
   `mae == baseline_mae` and skill is exactly `0.000000`. The scorer reports
   that identity rather than concealing it.
3. **Suppression works.** With `MIN_SAMPLES = 30`, the `n = 60` symbol cut is
   released; the same code blanks a thin cut and keeps its count.

The PIT check on the same run:

```text
as of 2021-08-09: 61 outcomes known by maturity, 62 forecasts merely issued
                  -> 1 would have been borrowed from the future
```

The gap is small here only because these horizons are 1 and 5 bars against an
8-bar cutoff spacing. At longer horizons or denser cutoffs it grows, which is
precisely why Phase 5 must filter on `matured_at`.

## 10. Tests

`app/tests/test_outcome_ledger.py`, 28 tests:

- matching a matured forecast to its realised bar, with hand-computed returns;
- horizon-awareness (1-bar and 5-bar horizons resolve different bars);
- an unmatured horizon yields `None`, not a zero;
- `score_matured` skips unmatured, never re-scores, and is idempotent;
- **prices after the maturity bar cannot change the score or the outcome id**;
- **the frozen forecast rows are byte-identical before and after scoring**;
- an anchor price that disagrees with the frozen price is refused;
- a missing anchor bar is refused;
- structural proof of the two-process separation;
- **scoring with `ultimate.evaluate` and `forecast.project` patched to raise**;
- duplicate outcome refusal, including at a later `scored_at`;
- raw SQL `UPDATE` / `DELETE` refusal, and payload-tamper detection;
- an outcome for a forecast not in the ledger is refused by foreign key;
- trivial baseline construction, and forecast-time baseline override;
- market-relative outcome over the identical window;
- challenger horizon parsing and Brier scoring at a supplied probability;
- confidence is never scored as a probability;
- a neutral forecast abstains rather than scoring wrong;
- sample size and interval present on every summary row;
- negative skill reported when the forecast loses to its baseline;
- breakdown suppression below the declared floor;
- rolling vs expanding divergence in maturity order;
- performance memory known only after maturity;
- calibration bins with counts and intervals;
- constituent diagnostic with counts;
- incumbent and challenger separated by `model_key`.

Verification at completion:

```text
python -m pytest app/tests/test_outcome_ledger.py app/tests/test_forecast_ledger.py app/tests/test_validation.py
51 passed
```

Full fast suite: 876 passed, 63 skipped — the 848-pass Phase 1 baseline plus the
28 tests added here, with no skip-count change and nothing weakened.

## 11. Deliberate Limits

- **The reported intervals are nominal and assume independent observations.**
  Overlapping horizons on one series violate that: a 5-bar horizon issued every
  bar reuses the same returns, so the effective sample size is below `n` and the
  true interval is wider than the Wilson/normal figures printed here. These
  summaries are performance *memory*, adequate for describing what happened and
  for feeding Phase 5 weight construction. **They are not a significance test
  and must not be used as one.** A Phase 4 or Phase 10 significance gate needs a
  dependence-aware procedure — the block bootstrap this programme has used
  before is the natural candidate, and choosing it is that phase's work, not
  this one's.
- No model weight, ensemble weight, or production status is changed by anything
  measured here.
- No challenger is promoted and no model is retired.
- No UI was added. `app/streamlit_app.py` and `app/tests/test_ui.py` retain
  their pre-existing uncommitted modifications and were not touched.
- Sector-relative outcomes remain unavailable pending a PIT sector map.
- Calibration remains untested against real probabilities because no production
  path emits one yet.
- The runtime database is local state and gitignored.

## 12. Decision

**GO to Phase 3.**

A forecast frozen at a historical cutoff can be matched to its realised outcome
and objectively scored without regenerating it, against a declared baseline,
with sample size and resolution attached to every number. Phase 3 may now define
a common model interface and give every predictive component an identity that
`model_key` currently approximates. Phase 3 must not reweight anything on the
strength of these summaries — that is Phase 5, and it is gated on Phase 4 first.
