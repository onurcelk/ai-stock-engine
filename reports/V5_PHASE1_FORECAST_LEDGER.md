# V5 Phase 1 Forecast Ledger

**Completion date:** 2026-08-14

**Phase:** PHASE 1 - Forecast Ledger

**Decision:** GO
**Scope:** Immutable point-in-time persistence for the existing Ultimate incumbent and genuine forward neural challengers. No outcome access, scoring, adaptive weighting, retraining, promotion, or UI work is included.

## 1. Result

Phase 1 adds `app/core/forecast_ledger.py`, a standard-library SQLite ledger that can generate an incumbent forecast through the existing engine, capture the exact frames supplied to it, freeze one record per available horizon, and reload the records unchanged. It also serializes an already-generated `forecast.project` neural projection as an explicitly versioned challenger.

The STOP / GO gate passes:

1. `generate_and_freeze_incumbent` generates through `ultimate.evaluate` and records before returning the verdict.
2. The recording fetcher fingerprints deep copies of the exact frames consumed by the engine.
3. A declared historical cutoff rejects any frame containing a later row.
4. SQLite primary-key and insert triggers reject duplicate or replacement identities.
5. Database triggers reject updates and deletes.
6. Reload verifies the canonical payload SHA-256 before constructing an immutable record.
7. Tests prove that changing all data after a cutoff cannot change the frozen forecast.

The mutable `app/runs` history was not reused. It remains separate UI experiment history.

## 2. Record Granularity

The ledger stores one record for each available symbol/horizon forecast. An aggregate Ultimate verdict is preserved in each horizon record's metadata, but it is not stored as a synthetic extra horizon. Unavailable horizons are not forecasts and are not inserted.

The production status values introduced in this phase are:

| Value | Meaning |
|---|---|
| `PRODUCTION_INCUMBENT` | Existing Ultimate technical/rule-based forecast, optionally carrying explicitly versioned model evidence. |
| `CHALLENGER` | Genuine forward projection from `forecast.project`. |

No RL/evolutionary agent and no leaky `forecast.run` output is admitted.

## 3. Forecast Schema

`forecast_schema_version` is `1`. Percent values use percentage points: for example, `predicted_return = 1.25` means `+1.25%`, while `probability_positive`, if eventually available, uses `[0, 1]`.

| Field | Type | Contract |
|---|---|---|
| `forecast_id` | string | `fcst_` plus SHA-256 of every other canonical immutable field. |
| `generated_at` | UTC ISO-8601 string | Time the persistence boundary created the forecast record. |
| `cutoff_at` | UTC ISO-8601 string | Last eligible bar used by this horizon. |
| `symbol` | string | Upper-case forecast symbol or label. |
| `horizon` | string | Ultimate key such as `1d`/`1w`, or challenger form such as `5x1d`. |
| `price_at_cutoff` | positive float | Input close at the forecast cutoff. |
| `predicted_direction` | enum | `bullish`, `neutral`, or `bearish`, derived from predicted return. |
| `predicted_return` | finite float | Expected move in percentage points. |
| `probability_positive` | float/null | Null for current paths; confidence is never relabelled as probability. |
| `confidence` | float/null | Existing Ultimate evidence-strength percentage, or null for an unmeasured challenger. |
| `model_predictions` | immutable JSON object | Full constituent scores, directions, contributions and skill evidence; neural records preserve the complete projected path. |
| `model_weights` | immutable JSON object | Raw and final normalized constituent weights, including zero weights. |
| `model_versions` | immutable string map | SHA-256 source versions plus required challenger version identity where applicable. |
| `feature_data_version` | immutable string map | Feature schema identifier and exact input fingerprint. |
| `regime_state` | immutable JSON object/null | Null unless a PIT-known state is explicitly supplied; no regime is invented. |
| `baseline_prediction` | immutable JSON object/null | Null unless a forecast-time baseline is explicitly supplied; no outcome is read. |
| `application_version` | string | Prediction implementation SHA-256. |
| `input_last_bar_at` | UTC ISO-8601 string | Last timestamp in the captured input frame. |
| `input_row_count` | positive integer | Rows in the captured input frame. |
| `input_fingerprint` | string | SHA-256 over normalized column order, row order, timestamps, values and missing-value markers. |
| `forecast_schema_version` | integer | Schema contract version, currently `1`. |
| `source_path` | string | Authorized generator: `app.core.ultimate.evaluate` or `app.core.forecast.project`. |
| `production_or_challenger` | enum | `PRODUCTION_INCUMBENT` or `CHALLENGER`. |
| `metadata` | immutable JSON object | Horizon mechanics, aggregate context, or explicit neural training configuration. |

SQLite stores indexed identity columns beside one canonical JSON payload and its SHA-256. The canonical payload is the source of truth on reload.

## 4. Versioning

The incumbent record versions:

- the complete `ultimate` implementation,
- technical source formulas in `indicators`,
- rule-agent formulas in `strategies`,
- optional neural evidence through a required caller-supplied `neural_challenger` version.

Reserved incumbent implementation versions cannot be overridden by callers.

The challenger record requires a non-empty model version and complete training configuration: layer count, layer size, timestamp window, epochs, dropout, learning rate, first/last training bars, and training row count. It also stores the forecast implementation hash and complete projected path. Because the full output and metadata participate in `forecast_id`, distinct stochastic projections cannot collide merely by reusing a model label.

## 5. Immutability

Immutability is enforced at four layers:

1. `ForecastRecord` is frozen and recursively freezes nested maps/lists.
2. `forecast_id` is recomputed and validated from the complete canonical payload.
3. SQLite rejects duplicate inserts, including `INSERT OR REPLACE`, and atomically rolls back a batch if any identity already exists.
4. SQLite rejects all `UPDATE` and `DELETE` statements against `forecasts`.

Phase 2 must store outcomes separately, keyed by `forecast_id`. It must not add outcome columns to or rewrite this table.

## 6. Point-In-Time Boundary

Historical prediction remains subject to the repository rule that `validation.pit.fetcher(cutoff)` is the data door. The Phase 1 wrapper adds a second fail-closed check: every captured frame must contain no timestamp after the declared cutoff. It does not truncate an unsafe frame silently.

For each available horizon, serialization verifies:

- captured row count equals the evaluated row count,
- captured final timestamp equals the verdict's `as_of`,
- captured final close equals `price_at_cutoff`,
- timestamp ordering is `input_last_bar_at <= cutoff_at <= generated_at`.

The data fingerprint records the actual supplied snapshot; it does not claim to solve the adjusted-price and historical-universe limitations documented in Phase 0.

## 7. Tests

`app/tests/test_forecast_ledger.py` covers:

- incumbent schema and complete constituent round-trip,
- explicit null `probability_positive`,
- duplicate refusal and unchanged reload,
- raw SQL update/delete refusal,
- `INSERT OR REPLACE` refusal,
- recursive in-memory immutability and identity validation,
- atomic batch rollback,
- rejection of any post-cutoff input row,
- invariance when all unseen future prices are rewritten,
- challenger path, training metadata, version and round-trip,
- rejection of incomplete challenger metadata.

Verification at completion:

```text
.venv/Scripts/python.exe -m pytest app/tests/test_forecast_ledger.py app/tests/test_ultimate.py app/tests/test_forecast.py app/tests/test_validation.py
96 passed
```

The complete fast suite passed with 848 tests passed and 63 skipped; that result is also recorded in the roadmap completion record.

## 8. Deliberate Limits

- The existing modified `app/streamlit_app.py` was not touched. Production UI adoption of the side-effect-free recording wrapper must not be implemented by adding hidden writes inside model functions.
- No Phase 1 UI was required or added.
- No outcome table, maturity query, scorer, performance summary, calibration result, or baseline-relative metric exists yet.
- No model weight is changed from an observed outcome.
- No challenger is promoted.
- No model is retrained or registered automatically.
- The runtime database and SQLite sidecars are local state and gitignored.

## 9. Decision

**GO to Phase 2.**

A forecast can be generated, frozen, reloaded, and proven unchanged. Phase 2 may add a separate append-only outcome/scoring boundary keyed by `forecast_id`; it must preserve the Phase 1 payload byte-for-byte and must not introduce outcome access into `forecast_ledger.py`.
