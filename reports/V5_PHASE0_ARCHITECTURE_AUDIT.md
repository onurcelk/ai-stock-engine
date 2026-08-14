# V5 Phase 0 Architecture Audit

**Audit date:** 2026-08-14  
**Phase:** PHASE 0 — Architecture Audit  
**Decision:** GO  
**Scope:** Read-only architecture audit of the live Streamlit application, its production-relevant prediction paths, persistence layer, agent implementations, and non-sealed validation infrastructure.

## 1. Executive Decision

**GO to Phase 1 — Forecast Ledger.**

The live execution path is understood well enough to add forecast memory without guessing:

1. The default displayed forecast is the `Ultimate signal`, produced by `app/core/ultimate.py`.
2. It combines ten deterministic technical sources and three deterministic rule-based trading-agent stances.
3. An optional LSTM, GRU, or vanilla RNN projection can be trained on demand and added as model evidence.
4. Nineteen trainable RL/evolutionary agents exist in the Trading agents tab, but they do not enter the default Ultimate verdict.
5. The application persists training-run summaries, not immutable production forecasts.
6. No live forecast is later matched automatically to its realised outcome.
7. A separate validation package already supplies the strongest reusable precedent for Phase 1: point-in-time truncation, separate predict/score processes, frozen prediction records, and overwrite refusal.

The main architectural defect is therefore not an unknown model path. It is the absence of a durable identity-preserving chain:

`generated forecast -> immutable stored record -> matured outcome -> score -> historical model performance`

The current live application recomputes evidence from the latest available frame. It does not preserve what the user was actually shown at a particular cutoff.

## 2. Scope And Safety

### 2.1 Included

This audit inspected:

- `app/streamlit_app.py`
- `app/core/ultimate.py`
- `app/core/indicators.py`
- `app/core/forecast.py`
- `app/core/runs.py`
- `app/core/live.py`
- `app/core/data.py`
- `app/core/strategies.py`
- `app/core/agents/*.py`
- relevant non-sealed tests under `app/tests/`
- non-sealed validation infrastructure under `validation/`
- non-sealed architecture inventory in `alpha/agents_audit.py`
- legacy standalone paths where needed to classify duplication or dead code

### 2.2 Explicitly Excluded

Sealed exam artifacts were not opened, read, or used. The repository rules prohibit inspecting the frozen exam cutoffs outside their protocol and prohibit deleting or overwriting frozen predictions (`Stock-Prediction-Models/CLAUDE.md:150-162`).

No conclusions in this report depend on sealed exam contents.

### 2.3 Classification Vocabulary

| Classification | Meaning |
|---|---|
| `EXISTS` | Implemented and usable for its stated role. |
| `PARTIAL` | Some required behaviour exists, but the V5 contract is incomplete. |
| `MISSING` | No implementation of the required behaviour was found. |
| `UNSAFE` | Implemented in a way that is unsuitable for production forecasting or historical evidence. |
| `UNUSED` | Implemented or retained in the repository but not part of the live production verdict path. |

A component can have more than one classification where its status differs by use. For example, run persistence `EXISTS` as UI history but is `UNSAFE` as an immutable forecast ledger.

## 3. Current System Map

### 3.1 Live Data Path

For live tickers, the application calls `live.fetch`, which downloads split/dividend-adjusted Yahoo data or reuses the local cache (`Stock-Prediction-Models/app/core/live.py:222-263`, `Stock-Prediction-Models/app/core/live.py:266-326`).

The cache is keyed by symbol and interval and stores CSV data plus metadata (`Stock-Prediction-Models/app/core/live.py:165-196`). Wider histories are retained and then trimmed to the requested period (`Stock-Prediction-Models/app/core/live.py:279-326`).

Bundled CSVs and uploads instead pass through `data.normalise`, which produces a chronological `date`, `close`, and optional OHLCV frame (`Stock-Prediction-Models/app/core/data.py:45-101`).

**Classification:** `EXISTS / PARTIAL`

The live cache is operational and reproducible enough for the UI, but it has no immutable data-version identifier suitable for a forecast ledger.

### 3.2 Default Displayed Prediction Path

The default prediction call is:

`streamlit_app.py -> read_ultimate() -> ultimate.evaluate() -> ultimate.evaluate_frame() -> ultimate.combine() -> verdict_panel()`

The cached UI wrapper constructs optional `ModelEvidence` and calls `ultimate.evaluate` (`Stock-Prediction-Models/app/streamlit_app.py:106-119`).

For a live symbol, `ultimate.evaluate` fetches the required frames and evaluates each configured horizon (`Stock-Prediction-Models/app/core/ultimate.py:913-962`). The configured horizons are:

- 4 hours from four hourly bars
- 1 day from one daily bar
- 1 week from five daily bars

(`Stock-Prediction-Models/app/core/ultimate.py:141-150`).

For uploads and bundled files, `evaluate_offline` evaluates only the horizons expressible from the supplied interval (`Stock-Prediction-Models/app/core/ultimate.py:1087-1107`).

The UI displays the combined action, score, confidence, alignment, price, and available horizon details (`Stock-Prediction-Models/app/streamlit_app.py:245-273`, `Stock-Prediction-Models/app/streamlit_app.py:606-622`).

**Classification:** `EXISTS`

### 3.3 Production-Used Technical Sources

`indicators.SOURCES` contains ten deterministic sources:

1. EMA 12/48 spread
2. EMA 50 slope
3. MACD histogram
4. ADX direction
5. RSI 14
6. 20-bar return
7. Bollinger reversion
8. Donchian position
9. On-balance-volume trend
10. Market structure

The complete source registry is defined at `Stock-Prediction-Models/app/core/indicators.py:311-341`.

Every source is transformed to a finite value in `[-1, 1]` (`Stock-Prediction-Models/app/core/indicators.py:48-62`). The source calculations are pandas-based, stateless, and do not themselves access the network (`Stock-Prediction-Models/app/core/indicators.py:23-25`).

**Classification:** `EXISTS`

### 3.4 Production-Used Rule-Based Agents

When `include_agents=True`, the Ultimate path adds three deterministic standing-position sources:

- Turtle
- Moving-average crossover
- Signal rolling

They are constructed in `ultimate.agent_sources` (`Stock-Prediction-Models/app/core/ultimate.py:357-390`) and added during horizon evaluation (`Stock-Prediction-Models/app/core/ultimate.py:626-639`).

The event signals are converted to persistent stances by forward-filling the most recent non-zero event (`Stock-Prediction-Models/app/core/indicators.py:354-365`).

These are the only trading agents included in the default Ultimate verdict.

**Classification:** `EXISTS`

### 3.5 Optional Neural Forecast Path

The available recurrent forecast families are:

- LSTM
- GRU
- Vanilla RNN

(`Stock-Prediction-Models/app/core/forecast.py:20-23`).

On the Ultimate tab, the neural path is off by default (`Stock-Prediction-Models/app/streamlit_app.py:526-532`). When enabled, the application:

1. loads up to 1,250 daily bars,
2. runs rolling-origin walk-forward evaluation,
3. trains a forward projection,
4. converts the projection and historical directional accuracy into `ModelEvidence`,
5. adds that evidence to the Ultimate calculation.

The paired measurement and projection are built at `Stock-Prediction-Models/app/streamlit_app.py:141-186`. The UI retrains when the symbol, model, folds, epochs, units, row count, or last close changes (`Stock-Prediction-Models/app/streamlit_app.py:550-586`).

`forecast.walk_forward` fits its scaler on each training slice only and predicts the next non-overlapping window (`Stock-Prediction-Models/app/core/forecast.py:268-333`). `forecast.project` trains on all currently available bars and projects beyond the last observed bar (`Stock-Prediction-Models/app/core/forecast.py:495-532`).

**Classification:** `EXISTS / PARTIAL`

The model can produce a real forward projection, but its production identity, training cutoff, random state, data version, and complete output are not frozen in an immutable forecast record.

### 3.6 Final Aggregation

For every source and horizon, `calibrate`:

1. constructs realised forward returns,
2. keeps only source firings,
3. uses the tail holdout,
4. discounts overlapping windows through an effective sample size,
5. removes non-positive or sub-threshold edges,
6. shrinks surviving weights.

(`Stock-Prediction-Models/app/core/ultimate.py:202-278`).

Weights are capped by source family (`Stock-Prediction-Models/app/core/ultimate.py:446-490`). The horizon score is the sum of weighted source contributions (`Stock-Prediction-Models/app/core/ultimate.py:645-680`).

Horizon confidence is:

`100 * skill_gate * agreement_gate * coverage_gate`

(`Stock-Prediction-Models/app/core/ultimate.py:682-695`).

Horizons are then combined using confidence-weighted scores, with an alignment multiplier applied to score but not confidence (`Stock-Prediction-Models/app/core/ultimate.py:858-910`).

Action classification applies score bands and a confidence veto (`Stock-Prediction-Models/app/core/ultimate.py:493-513`).

**Classification:** `EXISTS / PARTIAL`

The aggregation is explicit and testable, but the weights are recalculated from the latest frame rather than loaded from immutable historical performance memory.

### 3.7 Displayed Output Contract

The displayed system currently exposes:

- symbol
- BUY / HOLD / SELL, including strong variants
- score
- expected move by horizon
- confidence
- horizon
- source contributions
- measured hit rates

The expected move is not a direct model estimate. It is the horizon score multiplied by the median absolute historical move for that horizon (`Stock-Prediction-Models/app/core/ultimate.py:281-292`, `Stock-Prediction-Models/app/core/ultimate.py:543-550`).

The application does not compute or display a calibrated `probability_positive`.

**Classification:** `PARTIAL`

The output resembles the V5 target interface, but `confidence` is not a probability and `probability_positive` is `MISSING`.

## 4. Current Learning Map

### 4.1 Technical And Rule-Based Source Learning

The technical and rule-agent formulas do not train. Their influence adapts because every live evaluation recalculates source hit rate and weight from historical forward returns in the current frame.

The source score is read from the final row, while the historical source series is compared with realised forward returns (`Stock-Prediction-Models/app/core/ultimate.py:335-354`). The current incomplete tail cannot be scored because shifted forward returns are `NaN` there (`Stock-Prediction-Models/app/core/ultimate.py:202-204`, `Stock-Prediction-Models/app/core/ultimate.py:233-244`).

**Classification:** `EXISTS / PARTIAL`

There is adaptation, but not durable learning memory. The system cannot show what weight existed at an earlier forecast time unless that forecast is regenerated against a historical cutoff.

### 4.2 Neural Learning

The neural forecast uses TensorFlow v1-compatible graph mode (`Stock-Prediction-Models/app/core/forecast.py:336-347`). Each fold and projection builds and trains a fresh recurrent graph (`Stock-Prediction-Models/app/core/forecast.py:350-400`).

The live Ultimate path stores the trained result in `st.session_state`, keyed by a runtime fingerprint (`Stock-Prediction-Models/app/streamlit_app.py:563-586`). It does not persist model weights or a versioned model artifact.

**Classification:** `EXISTS / PARTIAL`

Training exists. Controlled retraining, artifact versioning, promotion, rollback, and durable model state are missing.

### 4.3 RL And Evolutionary Learning

Nineteen trainable agents are registered behind one UI interface (`Stock-Prediction-Models/app/core/agents/__init__.py:37-60`). They cover value-based RL, actor-critic, policy gradient, evolutionary, neuro-evolutionary, and curiosity-based families (`Stock-Prediction-Models/alpha/agents_audit.py:62-104`).

Their common state is a trailing window of price changes (`Stock-Prediction-Models/app/core/agents/base.py:27-55`). The UI constructs an agent over the complete selected frame, trains it, replays the trained policy over that same frame, and backtests the result (`Stock-Prediction-Models/app/streamlit_app.py:925-982`).

For example, Q-learning trains sequentially over the full supplied series and uses cash-relative gains as replay rewards (`Stock-Prediction-Models/app/core/agents/qlearning.py:94-129`). The deep-Q family likewise walks the full supplied series and updates from replay memory (`Stock-Prediction-Models/app/core/agents/deepq.py:187-265`). Policy gradient trains directly on discounted rewards collected over the full supplied trajectory (`Stock-Prediction-Models/app/core/agents/policygradient.py:77-132`).

The repository’s own non-sealed agent audit classifies these live implementations as PIT-inadmissible when trained on the whole series and replayed from bar zero (`Stock-Prediction-Models/alpha/agents_audit.py:470-489`).

**Classification:** `UNSAFE` for production predictive evidence  
**Classification:** `EXISTS` as an interactive same-sample training/backtest demonstration  
**Classification:** `UNUSED` by the default Ultimate verdict

### 4.4 Persistence And Historical Memory

`runs.save` writes one JSON file per completed training run with settings, headline metrics, and chart payload (`Stock-Prediction-Models/app/core/runs.py:115-157`).

This is not an immutable ledger:

- records can be deleted individually,
- all records can be cleared,
- the oldest records are automatically pruned beyond 200,
- filenames are time-based rather than deterministic forecast identities.

(`Stock-Prediction-Models/app/core/runs.py:194-225`).

The tests explicitly verify deletion, clearing, and pruning (`Stock-Prediction-Models/app/tests/test_runs.py:149-178`).

The Ultimate path saves neural walk-forward summaries, but its saved payload contains fold directions rather than the complete displayed verdict or projected path (`Stock-Prediction-Models/app/streamlit_app.py:587-600`). The default technical/rule-based Ultimate verdict is not saved at all.

The UI also states that saved runs are not read automatically into the verdict because a backtest is not a measured forward edge (`Stock-Prediction-Models/app/streamlit_app.py:762-770`).

**Classification:** `PARTIAL` as user run history  
**Classification:** `UNSAFE` as forecast evidence  
**Classification:** `MISSING` as an immutable forecast ledger

### 4.5 Outcome Matching And Scoring

No application service scans saved live forecasts for maturity, retrieves realised outcomes, and scores them.

The separate validation subsystem does contain this pattern:

- `validation.predict` generates PIT predictions and refuses to overwrite an existing frozen prediction file (`Stock-Prediction-Models/validation/predict.py:203-215`).
- `validation.model` records cutoff-specific neural forecasts and appends completed symbol/cutoff pairs (`Stock-Prediction-Models/validation/model.py:123-154`).
- `validation.score` reads frozen predictions, never writes them, and attaches outcomes in a separate stage (`Stock-Prediction-Models/validation/score.py:1-18`, `Stock-Prediction-Models/validation/score.py:162-180`).

**Classification:** `MISSING` in the live application  
**Classification:** `EXISTS` as reusable offline validation precedent

### 4.6 Learning Loop Summary

Current live loop:

`latest bars -> recompute historical source scores -> recompute weights -> current verdict -> display`

Optional neural loop:

`latest bars -> walk-forward training -> projection training -> temporary evidence -> current verdict -> mutable run summary`

RL tab loop:

`selected full frame -> train on full frame -> replay on full frame -> same-sample backtest -> mutable run summary`

Required V5 loop, currently absent:

`PIT data -> versioned model -> forecast -> immutable forecast ledger -> maturity -> realised outcome -> score -> performance memory -> PIT-safe future weighting/retraining`

## 5. Phase 0 Task Findings

| Phase 0 task | Result | Classification | Evidence |
|---|---|---|---|
| Trace the real prediction execution path | Complete | `EXISTS` | `read_ultimate` calls `ultimate.evaluate` (`Stock-Prediction-Models/app/streamlit_app.py:114-119`); horizon evaluation and combination are in `Stock-Prediction-Models/app/core/ultimate.py:913-962`. |
| Identify all production-used models/agents | Complete | `EXISTS` | Ten technical sources (`Stock-Prediction-Models/app/core/indicators.py:311-341`), three rule agents (`Stock-Prediction-Models/app/core/ultimate.py:357-390`), optional LSTM/GRU/RNN (`Stock-Prediction-Models/app/core/forecast.py:20-23`). |
| Identify implemented but unused models | Complete | `UNUSED` | Nineteen trainable agents are registered (`Stock-Prediction-Models/app/core/agents/__init__.py:40-60`) but Ultimate adds only the three rule agents (`Stock-Prediction-Models/app/core/ultimate.py:630-635`). Legacy unported notebook paths are inventoried at `Stock-Prediction-Models/alpha/agents_audit.py:134-142`. |
| Identify TensorFlow/neural training paths | Complete | `EXISTS / PARTIAL` | Recurrent graph and training are in `Stock-Prediction-Models/app/core/forecast.py:109-139` and `Stock-Prediction-Models/app/core/forecast.py:350-400`; several RL families load the same TF compatibility layer, for example `Stock-Prediction-Models/app/core/agents/qlearning.py:37-52`. |
| Identify RL training/reward paths | Complete | `EXISTS / UNSAFE` | Shared same-series simulation reward is described at `Stock-Prediction-Models/app/core/agents/base.py:176-198`; concrete Q-learning reward/training is at `Stock-Prediction-Models/app/core/agents/qlearning.py:94-129`. |
| Identify retraining behaviour | Complete | `PARTIAL` | Neural Ultimate retrains when its runtime fingerprint changes (`Stock-Prediction-Models/app/streamlit_app.py:563-586`); RL retrains only when the user presses Train (`Stock-Prediction-Models/app/streamlit_app.py:925-944`); no versioned scheduled retraining policy exists. |
| Determine whether historical forecasts are persisted | Complete | `PARTIAL / MISSING` | Training-run summaries are persisted (`Stock-Prediction-Models/app/core/runs.py:115-157`), but complete live Ultimate forecasts are not. |
| Determine whether predictions are immutable after generation | Complete | `MISSING / UNSAFE` | Run records can be deleted, cleared, or pruned (`Stock-Prediction-Models/app/core/runs.py:194-225`). Only the offline validation prediction file refuses overwrite (`Stock-Prediction-Models/validation/predict.py:203-215`). |
| Determine whether forecasts are later matched to realised outcomes | Complete | `MISSING` live, `EXISTS` offline | Offline separation and outcome attachment are implemented in `Stock-Prediction-Models/validation/score.py:1-18` and `Stock-Prediction-Models/validation/score.py:162-180`. |
| Trace confidence calculation | Complete | `EXISTS / PARTIAL` | Confidence is the product of skill, agreement, and coverage gates (`Stock-Prediction-Models/app/core/ultimate.py:682-695`), then combined across horizons (`Stock-Prediction-Models/app/core/ultimate.py:881-906`). It is not a probability-positive estimate. |
| Trace ensemble/model weighting | Complete | `EXISTS / PARTIAL` | Source weights derive from held-out hit-rate edge and t-statistic (`Stock-Prediction-Models/app/core/ultimate.py:207-278`), family caps apply at `Stock-Prediction-Models/app/core/ultimate.py:446-490`, and horizon aggregation applies at `Stock-Prediction-Models/app/core/ultimate.py:645-695`. |
| Verify PIT safety of all production-relevant paths | Complete | Mixed | Current technical/rule evaluation is causal on the frame supplied; historical safety requires `pit.fetcher`, which truncates before period slicing (`Stock-Prediction-Models/validation/pit.py:78-108`). Neural walk-forward is PIT-safe per fold (`Stock-Prediction-Models/app/core/forecast.py:284-333`), while single-split `forecast.run` explicitly fits its scaler on the test-inclusive full series (`Stock-Prediction-Models/app/core/forecast.py:403-458`). RL same-series training/replay is PIT-inadmissible (`Stock-Prediction-Models/alpha/agents_audit.py:470-489`). |
| Identify duplicated/dead prediction paths | Complete | `UNUSED` | The standalone realtime Flask agent loads `model.pkl` and hard-coded TWTR data independently of the Streamlit application (`Stock-Prediction-Models/realtime-agent/app.py:342-357`, `Stock-Prediction-Models/realtime-agent/app.py:359-393`). TensorFlow stacking code is another separate implementation (`Stock-Prediction-Models/stacking/model.py:1-19`). |
| Mark all components | Complete | See Section 6 | Every material component is classified below. |

## 6. Component Classification Register

| Component | Current role | Classification | Phase 1 disposition |
|---|---|---|---|
| `app/core/live.py` | Live/cache market data | `EXISTS / PARTIAL` | Keep; add a stable data fingerprint to ledger records. |
| `app/core/data.py` | Frame normalisation | `EXISTS` | Keep. |
| `app/core/indicators.py` | Ten deterministic source families | `EXISTS` | Keep as incumbent source implementations. |
| `app/core/strategies.py` | Three deterministic rule agents | `EXISTS` | Keep as incumbent rule-based models. |
| `app/core/ultimate.py` | Default displayed ensemble | `EXISTS / PARTIAL` | Keep as pre-V5 incumbent; wrap its output rather than rewriting it in Phase 1. |
| `ultimate.calibrate` | In-frame historical source scoring | `EXISTS / PARTIAL` | Record resulting weights in the ledger; do not treat recomputation as historical memory. |
| `ultimate.ModelEvidence` | Optional neural model adapter | `EXISTS / PARTIAL` | Keep temporarily; assign stable model/version metadata. |
| `forecast.walk_forward` | Rolling-origin evaluation | `EXISTS` | Keep as evaluation infrastructure. |
| `forecast.project` | Genuine forward projection | `EXISTS / PARTIAL` | Keep; freeze each projection and training cutoff. |
| `forecast.run` | Notebook-compatible single split | `UNSAFE` | Isolate from production evidence because its scaler sees the test window. |
| `app/core/runs.py` | User-visible training history | `PARTIAL / UNSAFE` | Keep as UI history only; do not reuse it as the immutable ledger. |
| `app/core/agents/REGISTRY` | Nineteen trainable agents | `EXISTS / UNSAFE` | Keep isolated as experimental/challenger infrastructure; zero production authority. |
| Three rule-agent sources in Ultimate | Default ensemble evidence | `EXISTS` | Keep. |
| RL agent weights/checkpoints | Durable trained state | `MISSING` | Do not add in Phase 1; model registry/retraining belongs to later phases. |
| Probability-positive output | Forecast probability | `MISSING` | Store `null` until an admissible calibrated probability exists. |
| Immutable forecast ledger | Forecast evidence | `MISSING` | Build in Phase 1. |
| Mature-outcome matcher | Learning loop | `MISSING` live | Build in Phase 2, not Phase 1. |
| `validation/pit.py` | Historical PIT data door | `EXISTS` | Reuse its truncation contract and tests. |
| `validation/predict.py` | Frozen prediction precedent | `EXISTS` | Reuse overwrite-refusal and predict-only separation. |
| `validation/score.py` | Separate outcome scoring | `EXISTS` | Reuse in Phase 2; do not merge scoring into ledger generation. |
| `realtime-agent/app.py` | Standalone legacy Flask trader | `UNUSED` | Isolate/retire from V5. |
| `deep-learning/*.ipynb` | Original notebook experiments | `UNUSED` | Retain as historical source material, not executable production paths. |
| `stacking/*` | Separate TensorFlow stacking experiments | `UNUSED` | Isolate from V5 until explicitly admitted through the model registry. |
| Unported agent notebooks | Historical implementations only | `UNUSED` | Do not port during V5 without a later evidence-gated proposal. |

## 7. Point-In-Time Safety Assessment

### 7.1 Current Technical And Rule-Based Verdict

The source calculations use only the frame supplied to them. The current reading is the final row of that frame (`Stock-Prediction-Models/app/core/ultimate.py:335-354`). Historical outcomes used for calibration are constructed within that same frame, and incomplete future windows are excluded by `NaN` (`Stock-Prediction-Models/app/core/ultimate.py:202-244`).

For a forecast generated now from a frame ending now, this is causally valid. For historical reconstruction, it is valid only if the frame is truncated first.

The validation fetcher performs that truncation and only then applies period slicing (`Stock-Prediction-Models/validation/pit.py:78-108`). The leak-detector test verifies that rewriting all post-cutoff prices cannot change the verdict (`Stock-Prediction-Models/app/tests/test_validation.py:103-133`).

**Verdict:** `PARTIAL`

The algorithm can be PIT-safe, but the production application has no explicit `cutoff_at` contract or frozen input fingerprint.

### 7.2 Data-Level Residual Risks

The validation layer documents two production-relevant residual risks:

- adjusted historical prices can include later dividend adjustments,
- today’s cached symbol universe is not a PIT historical universe.

(`Stock-Prediction-Models/validation/pit.py:18-29`).

**Verdict:** `PARTIAL`

These do not block Phase 1, but ledger records must preserve the actual input cutoff and data fingerprint rather than claiming stronger historical purity than exists.

### 7.3 Neural Paths

`forecast.walk_forward` is PIT-safe within each fold because the scaler and model use only the training slice (`Stock-Prediction-Models/app/core/forecast.py:284-333`).

`forecast.project` is PIT-safe for a forecast made at the current final bar because every input is available at forecast time (`Stock-Prediction-Models/app/core/forecast.py:509-525`).

`forecast.run` is explicitly leaky for evaluation because it fits the scaler on the whole series, including the held-out window (`Stock-Prediction-Models/app/core/forecast.py:403-429`).

**Verdict:**

- `walk_forward`: `EXISTS`
- `project`: `EXISTS / PARTIAL`
- `run`: `UNSAFE`

### 7.4 RL Paths

The trainable UI agents are constructed with the complete selected series, optimise over it, and replay the trained policy from its beginning. The repository audit states that this is the forbidden historical construction (`Stock-Prediction-Models/alpha/agents_audit.py:470-489`).

**Verdict:** `UNSAFE` for production and historical predictive claims.

## 8. Confidence And Weighting Semantics

### 8.1 Source Weight

A source’s raw weight is derived from:

- directional hit rate,
- edge over 50%,
- effective sample size,
- t-statistic,
- shrinkage.

A source receives zero weight if it has too few calls, a non-positive edge, or a t-statistic below `MIN_T` (`Stock-Prediction-Models/app/core/ultimate.py:244-278`).

### 8.2 Family And Breadth Controls

Correlated sources are limited through a family cap (`Stock-Prediction-Models/app/core/ultimate.py:446-490`). Surviving evidence is then discounted by total weight and number of active families (`Stock-Prediction-Models/app/core/ultimate.py:650-668`).

### 8.3 Confidence

Confidence is a heuristic evidence-strength score:

- skill gate,
- agreement gate,
- coverage gate.

It is not the empirical probability that the future return is positive (`Stock-Prediction-Models/app/core/ultimate.py:682-695`).

The final action also applies a hard confidence veto (`Stock-Prediction-Models/app/core/ultimate.py:493-513`).

**Classification:** `EXISTS / PARTIAL`

The calculation is transparent, but V5 must not store or display it as `probability_positive`. Phase 1 should preserve both fields separately, with `probability_positive = null` until a calibrated probability model exists.

## 9. Retraining Behaviour

### 9.1 Technical And Rule-Based Sources

There is no parameter training. Their historical skill and weights are recomputed each time a verdict is generated.

**Classification:** `PARTIAL`

This adapts to the latest frame but does not produce versioned, reviewable learning state.

### 9.2 Neural Forecaster

The neural model is retrained from scratch when its UI fingerprint changes. Only the current browser session retains the actual `walk` and `projection` objects (`Stock-Prediction-Models/app/streamlit_app.py:563-586`).

No durable checkpoint, training cutoff, model artifact hash, promotion state, or rollback target exists.

**Classification:** `PARTIAL`

### 9.3 Trainable Agents

RL/evolutionary models retrain only on explicit user action (`Stock-Prediction-Models/app/streamlit_app.py:930-944`). Saved runs contain metrics and chart payloads, not reusable policy checkpoints (`Stock-Prediction-Models/app/streamlit_app.py:960-982`).

**Classification:** `PARTIAL / UNSAFE`

### 9.4 Automated Production Retraining

No scheduler or policy automatically retrains, evaluates, promotes, degrades, retires, or rolls back production models.

**Classification:** `MISSING`

This is correctly deferred to Phase 7.

## 10. Historical Forecast Persistence And Immutability

### 10.1 What Exists

The `runs` module provides durable JSON history for forecasts, walk-forward evaluations, and agents (`Stock-Prediction-Models/app/core/runs.py:1-20`).

The validation package freezes historical predictions and separates prediction generation from outcome scoring (`Stock-Prediction-Models/validation/predict.py:1-15`, `Stock-Prediction-Models/validation/score.py:1-18`).

### 10.2 What Is Missing

No persisted live record contains all of:

- forecast identity,
- generation timestamp,
- cutoff timestamp,
- symbol,
- horizon,
- input price,
- action/direction,
- expected return,
- probability positive,
- confidence,
- constituent predictions,
- constituent weights,
- model versions,
- data fingerprint,
- baseline,
- immutable original payload.

### 10.3 Why `app/runs` Cannot Be Reused Directly

`app/runs` permits deletion, clearing, and automatic pruning (`Stock-Prediction-Models/app/core/runs.py:194-225`). It is intentionally gitignored personal UI state (`Stock-Prediction-Models/.gitignore:5-10`).

Its records represent heterogeneous training experiments rather than one record per production/challenger forecast.

**Verdict:** An immutable forecast ledger is `MISSING`.

## 11. Critical Gaps Ranked By Severity

### Severity 1 — No Immutable Forecast Ledger

The system cannot prove what prediction was shown at a given time. The default Ultimate verdict is not persisted, while run history is mutable and incomplete.

**Impact:** Objective future scoring is impossible without regeneration.

**Classification:** `MISSING`

### Severity 2 — No Live Forecast-To-Outcome Join

No live service identifies matured forecasts and attaches realised returns without changing the original forecast.

**Impact:** The production application has no closed learning loop.

**Classification:** `MISSING`

### Severity 3 — Historical Weights Are Recomputed, Not Remembered

Current source weights are reconstructed from the latest available frame. A later run can therefore produce different weights from those used in the original forecast.

**Impact:** Historical explanations are not identity-preserving.

**Classification:** `PARTIAL / UNSAFE` for retrospective evidence

### Severity 4 — RL Results Are Same-Series And PIT-Inadmissible

The nineteen trainable agents optimise over and replay the same selected frame.

**Impact:** Their displayed backtests cannot justify production forecast authority.

**Classification:** `UNSAFE`

### Severity 5 — Confidence Is Not Probability Positive

The displayed confidence is an evidence-strength gate, not a calibrated probability.

**Impact:** The current output cannot satisfy the V5 `probability_positive` contract without semantic mislabelling.

**Classification:** `PARTIAL / MISSING`

### Severity 6 — No Stable Model Or Data Versioning

Technical formulas, neural settings, runtime dependencies, training cutoff, random seed, and data snapshot are not combined into immutable version identifiers.

**Impact:** Forecast reproduction and comparison are weak.

**Classification:** `MISSING`

### Severity 7 — Unsafe Single-Split Neural Evaluation Remains User-Reachable

`forecast.run` intentionally preserves the notebook’s full-series scaler fit.

**Impact:** Its single-split metrics must not enter production evidence.

**Classification:** `UNSAFE`

### Severity 8 — Duplicated Legacy Prediction Paths

Standalone notebooks, stacking code, and the Flask realtime agent implement independent model paths outside the live application architecture.

**Impact:** They create ambiguity and maintenance risk if treated as production candidates.

**Classification:** `UNUSED`

### Severity 9 — Residual PIT Data Limitations

Adjusted prices and present-day cached universe selection remain disclosed historical limitations.

**Impact:** Historical claims require explicit caveats and data fingerprints.

**Classification:** `PARTIAL`

## 12. Components Worth Keeping

### 12.1 Keep As Production Incumbent

- `app/core/ultimate.py`
- `app/core/indicators.py`
- the three deterministic rule-agent sources
- horizon definitions and HOLD/confidence veto behaviour
- family caps and overlap-adjusted effective sample sizes

These provide a concrete pre-V5 baseline that can be frozen and compared rather than silently replaced.

### 12.2 Keep As Neural Challenger Infrastructure

- `forecast.walk_forward`
- `forecast.project`
- `ModelEvidence`

The split between historical measurement and genuine forward projection is conceptually sound (`Stock-Prediction-Models/app/core/forecast.py:461-471`).

### 12.3 Keep As Validation Infrastructure

- `validation.pit.fetcher`
- separate prediction and scoring processes
- overwrite refusal
- future-rewrite leak test
- native-horizon outcome scoring

These are the closest existing implementation to the V5 scientific contract.

### 12.4 Keep As UI History Only

- `app/core/runs.py`
- History tab

They remain useful for personal experiment comparison, but must be visibly separate from forecast evidence.

## 13. Components To Isolate Or Retire

### 13.1 Isolate From Production Evidence

- all nineteen trainable RL/evolutionary agents until evaluated through a PIT-safe challenger protocol,
- `forecast.run`,
- same-sample agent backtests,
- mutable `app/runs` records.

### 13.2 Retire From The V5 Execution Graph

- `realtime-agent/app.py`,
- standalone stacking code,
- direct execution of old deep-learning notebooks,
- unported notebook agents.

Retirement here means “not callable by V5 production or scoring,” not deletion of historical research material.

### 13.3 Preserve But Do Not Reopen

Closed research programmes and frozen records remain historical evidence. Phase 1 must not modify them or use forecast-ledger work as a pretext to rerun sealed studies.

## 14. Minimum V5 Architecture Proposal

Phase 1 should make the smallest possible change: place an immutable persistence boundary around forecasts already generated by the incumbent and explicitly selected challengers.

### 14.1 Proposed Flow

`PIT input frame`
-> `existing model/Ultimate call`
-> `normalised ForecastRecord`
-> `append-only forecast ledger`
-> later Phase 2 outcome attachment
-> later performance memory
-> later adaptive weights

### 14.2 Forecast Record Boundary

A forecast record should be created after all constituent predictions and weights are known but before anything reads the future outcome.

Minimum immutable core:

- `forecast_id`
- `generated_at`
- `cutoff_at`
- `symbol`
- `horizon`
- `price_at_cutoff`
- `predicted_direction`
- `predicted_return`
- `probability_positive`
- `confidence`
- `model_predictions`
- `model_weights`
- `model_versions`
- `feature_data_version`
- `regime_state`
- `baseline_prediction`

Additional audit fields recommended immediately:

- `application_version`
- `input_last_bar_at`
- `input_row_count`
- `input_fingerprint`
- `forecast_schema_version`
- `source_path`
- `production_or_challenger`

### 14.3 Immutability Rule

The original forecast object must never be updated after insertion.

Phase 2 outcomes should be stored as a separate record keyed by `forecast_id`, or in a separate outcome table with a one-to-one relationship. Scoring must never rewrite forecast fields.

### 14.4 Storage Choice

A small SQLite database is the minimum robust implementation for:

- primary-key uniqueness,
- transactions,
- schema constraints,
- indexed maturity queries,
- separation of forecast and outcome tables.

Append-only JSONL can work, following `validation/model.py`, but would require additional locking, uniqueness, and corruption handling. SQLite is preferable unless repository constraints discovered in Phase 1 dictate otherwise.

### 14.5 Integration Points

1. Add one serializer that converts `UltimateVerdict` and its horizon readings into ledger records.
2. Add one serializer for optional neural projections and other challengers.
3. Persist immediately after generation and before display.
4. Preserve `app/runs` independently; do not replace or reinterpret it.
5. Reuse the `validation.pit.fetcher` contract for historical tests.
6. Add overwrite/duplicate tests patterned after `validation.predict`.
7. Add a future-rewrite test patterned after `test_future_cannot_change_the_verdict`.
8. Do not implement outcome scoring, adaptive weighting, retraining, or Phase 1 UI expansion during Phase 1.

### 14.6 Initial Model Statuses

| Component | Initial V5 status |
|---|---|
| Current Ultimate technical/rule ensemble | `PRODUCTION_INCUMBENT` |
| LSTM/GRU/Vanilla projection | `CHALLENGER` |
| Nineteen trainable agents | `EXPERIMENTAL_UNSAFE` |
| Rule-agent sources inside Ultimate | `PRODUCTION_INCUMBENT` |
| `forecast.run` | `RETIRED_FROM_EVIDENCE` |
| Legacy Flask/stacking/notebook paths | `RETIRED_FROM_V5_GRAPH` |

## 15. Phase 1 Constraints

Phase 1 must not:

- implement outcome scoring,
- adapt weights from newly observed outcomes,
- promote a challenger,
- retrain automatically,
- expose RL agents as production forecasts,
- reinterpret confidence as probability,
- modify frozen research records,
- access sealed exam artifacts.

Phase 1 should only establish that a forecast can be generated, frozen, reloaded, and proven unchanged.

## 16. STOP / GO Gate

### Gate Question

Is the actual execution path understood well enough to add forecast memory without guessing?

### Decision

**GO**

### Basis

- The default prediction call graph is identified.
- Every production-used source and optional model is identified.
- Confidence and weighting calculations are traced.
- Persistence and immutability gaps are explicit.
- PIT-safe and unsafe paths are separated.
- The validation package provides directly reusable freeze and leak-test patterns.
- The proposed Phase 1 boundary can wrap existing prediction outputs without changing model behaviour.

## 17. Phase 0 Completion Summary

- Status: `COMPLETE`
- Result: `GO`
- Next active phase: `PHASE 1 — Forecast Ledger`
- Phase 1 entry condition: satisfied
- Phase 1 implementation performed by this audit: none
- Sealed exam artifacts accessed: no
