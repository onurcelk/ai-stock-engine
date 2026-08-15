"""Immutable point-in-time forecast records.

This module is deliberately separate from outcome scoring.  It receives only
the information available when a forecast is generated, freezes that payload,
and exposes no update or delete operation.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import inspect
import json
import math
import pathlib
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd

from . import forecast, indicators, strategies, ultimate


#: Phase 1 schema, amended once.
#:
#: v1 → v2 (AB-1, 2026-08-15) adds `basis_probes`.  The live fetch path uses
#: `auto_adjust=True`, so a split or dividend after a forecast is frozen
#: back-adjusts the whole pre-action history and the anchor bar no longer
#: reads what it read at freeze time.  The probes are what let the scorer
#: tell a *legitimate uniform rescaling* apart from *tampering with one bar*,
#: which is the distinction Phase 2's anchor guard alone cannot make.  See
#: `reports/V5_ADJUSTMENT_BASIS_FINDING.md`.
#:
#: v1 records stay readable and keep their original identity digest: the
#: field is excluded from `identity_payload` for them, so no frozen id moves.
SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = (1, 2)

#: Fields that exist only from v2 on, and are therefore excluded from the
#: identity digest of a v1 record.
_V2_FIELDS = ("basis_probes",)

#: How many trailing bars of the consumed frame are stored as basis probes.
#: One would establish a ratio; several are what make *uniformity* testable,
#: and uniformity is the whole signal.  Eight is small enough to be free and
#: long enough that a single tampered bar cannot masquerade as a rescaling.
BASIS_PROBE_COUNT = 8

DEFAULT_PATH = pathlib.Path(__file__).resolve().parents[1] / "forecast_ledger.sqlite3"
PRODUCTION_INCUMBENT = "PRODUCTION_INCUMBENT"
CHALLENGER = "CHALLENGER"


class ForecastLedgerError(RuntimeError):
    """Base error for a forecast that cannot be frozen or trusted."""


class ForecastExistsError(ForecastLedgerError):
    """The immutable identity already exists in the ledger."""


class ForecastIntegrityError(ForecastLedgerError):
    """A stored payload or its point-in-time inputs failed validation."""


def _utc_iso(value: dt.datetime | pd.Timestamp) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat()


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (dt.datetime, dt.date, pd.Timestamp, np.datetime64)):
        return _utc_iso(pd.Timestamp(value))
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number):
            return "NaN"
        if math.isinf(number):
            return "+Infinity" if number > 0 else "-Infinity"
        return number.hex()
    if isinstance(value, str):
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False, default=_json_value)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _module_version(module: Any) -> str:
    """Version un-packaged prediction code by the exact source in use."""
    return "sha256:" + hashlib.sha256(
        inspect.getsource(module).encode("utf-8")
    ).hexdigest()


def _normalise_json(value: Any) -> Any:
    """Return a lossless JSON-native value or reject unsupported metadata."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (dt.datetime, dt.date, pd.Timestamp, np.datetime64)):
        return _utc_iso(pd.Timestamp(value))
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("forecast metadata cannot contain NaN or infinity")
        return number
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("forecast metadata mapping keys must be strings")
        return {key: _normalise_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_normalise_json(item) for item in value]
    raise TypeError(f"unsupported forecast metadata type: {type(value).__name__}")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def fingerprint_frame(
    frame: pd.DataFrame,
    *,
    cutoff_at: dt.datetime | pd.Timestamp | None = None,
) -> str:
    """Hash an exact input frame, rejecting rows beyond a declared cutoff."""
    if frame.empty:
        raise ForecastIntegrityError("cannot fingerprint an empty input frame")
    if "date" not in frame or "close" not in frame:
        raise ForecastIntegrityError("input frame must contain date and close")

    dates = pd.to_datetime(frame["date"], errors="raise", utc=True)
    if not dates.is_monotonic_increasing:
        raise ForecastIntegrityError("input frame must be chronological")
    if cutoff_at is not None:
        cutoff = pd.Timestamp(cutoff_at)
        cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
        if bool((dates > cutoff).any()):
            raise ForecastIntegrityError("input frame contains data after cutoff_at")

    columns = sorted(str(column) for column in frame.columns)
    rows = [
        [_json_value(value) for value in row]
        for row in frame.loc[:, columns].itertuples(index=False, name=None)
    ]
    return "sha256:" + _digest({"columns": columns, "rows": rows})


def basis_probes(
    frame: pd.DataFrame, *, count: int = BASIS_PROBE_COUNT,
) -> list[list[Any]]:
    """Trailing `(iso_date, close)` pairs on the frame's own adjustment basis.

    These exist to answer one question later: when the anchor bar no longer
    reads what it read at freeze time, was the *whole* pre-action history
    rescaled by one constant — a split or dividend — or did a single bar move,
    which is corruption?  A back-adjustment is uniform by construction, so
    uniformity across several bars is the signature, and a single ratio could
    never distinguish the two.

    Read from the same frame that `fingerprint_frame` hashes, so they describe
    exactly the data the forecast consumed.
    """
    if frame.empty:
        raise ForecastIntegrityError("cannot take basis probes from an empty frame")
    if "date" not in frame or "close" not in frame:
        raise ForecastIntegrityError("input frame must contain date and close")
    tail = frame.iloc[-max(1, int(count)):]
    dates = pd.to_datetime(tail["date"], errors="raise", utc=True)
    probes: list[list[Any]] = []
    for stamp, close in zip(dates, tail["close"]):
        value = float(close)
        if not math.isfinite(value) or value <= 0:
            raise ForecastIntegrityError("input frame has an unusable close")
        probes.append([_utc_iso(stamp), value])
    return probes


@dataclasses.dataclass(frozen=True)
class ForecastRecord:
    forecast_id: str
    generated_at: str
    cutoff_at: str
    symbol: str
    horizon: str
    price_at_cutoff: float
    predicted_direction: str
    predicted_return: float
    probability_positive: float | None
    confidence: float | None
    model_predictions: Mapping[str, Any]
    model_weights: Mapping[str, Any]
    model_versions: Mapping[str, str]
    feature_data_version: Mapping[str, str]
    regime_state: Mapping[str, Any] | None
    baseline_prediction: Mapping[str, Any] | None
    application_version: str
    input_last_bar_at: str
    input_row_count: int
    input_fingerprint: str
    forecast_schema_version: int
    source_path: str
    production_or_challenger: str
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    #: Trailing `(iso_date, close)` pairs from the exact consumed frame, on the
    #: adjustment basis prevailing at freeze time.  Absent on v1 records, and
    #: absent means the scorer cannot reconcile a corporate action and must
    #: refuse — which is the pre-AB-1 behaviour, kept as the fail-closed path.
    basis_probes: Sequence[Sequence[Any]] | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "model_predictions", "model_weights", "model_versions",
            "feature_data_version", "regime_state", "baseline_prediction", "metadata",
            "basis_probes",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _freeze_json(_normalise_json(value)))
        if self.forecast_schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported forecast schema {self.forecast_schema_version}")
        if self.forecast_schema_version < 2 and self.basis_probes is not None:
            raise ValueError("basis_probes did not exist before schema v2")
        if self.basis_probes is not None:
            if not self.basis_probes:
                raise ValueError("basis_probes must be absent or non-empty")
            for probe in self.basis_probes:
                if len(probe) != 2:
                    raise ValueError("each basis probe must be (iso_date, close)")
                close = float(probe[1])
                if not math.isfinite(close) or close <= 0:
                    raise ValueError("basis probe close must be finite and positive")
        if self.predicted_direction not in {"bullish", "neutral", "bearish"}:
            raise ValueError("predicted_direction must be bullish, neutral, or bearish")
        if not self.symbol or not self.horizon or self.input_row_count < 1:
            raise ValueError("symbol, horizon, and a non-empty input are required")
        if self.probability_positive is not None and not 0 <= self.probability_positive <= 1:
            raise ValueError("probability_positive must be null or in [0, 1]")
        if self.confidence is not None and not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be null or in [0, 100]")
        if self.production_or_challenger not in {PRODUCTION_INCUMBENT, CHALLENGER}:
            raise ValueError("invalid production_or_challenger status")
        if not math.isfinite(self.price_at_cutoff) or self.price_at_cutoff <= 0:
            raise ValueError("price_at_cutoff must be finite and positive")
        if not math.isfinite(self.predicted_return):
            raise ValueError("predicted_return must be finite")
        generated = pd.Timestamp(self.generated_at)
        cutoff = pd.Timestamp(self.cutoff_at)
        last_bar = pd.Timestamp(self.input_last_bar_at)
        if any(timestamp.tzinfo is None for timestamp in (generated, cutoff, last_bar)):
            raise ValueError("forecast timestamps must be timezone-aware")
        if last_bar > cutoff or cutoff > generated:
            raise ValueError("forecast timestamps violate point-in-time ordering")
        if not self.model_versions or not all(self.model_versions.values()):
            raise ValueError("non-empty model version identifiers are required")
        expected_id = "fcst_" + _digest(self.identity_payload())
        if self.forecast_id != expected_id:
            raise ValueError("forecast_id does not match the immutable forecast payload")

    def payload(self) -> dict[str, Any]:
        return {
            field.name: _thaw_json(getattr(self, field.name))
            for field in dataclasses.fields(self)
        }

    def identity_payload(self) -> dict[str, Any]:
        """The payload the `forecast_id` digests.

        Fields introduced after a record's own schema version are excluded, so
        amending the schema never moves the identity of an already-frozen
        record.  A v1 record reloaded today digests exactly what it digested
        when it was written.
        """
        excluded = {"forecast_id"}
        if self.forecast_schema_version < 2:
            excluded.update(_V2_FIELDS)
        return {
            key: value for key, value in self.payload().items()
            if key not in excluded
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ForecastRecord":
        return cls(**dict(payload))


def _record(
    *,
    generated_at: str,
    cutoff_at: str,
    symbol: str,
    horizon: str,
    price_at_cutoff: float,
    predicted_return: float,
    probability_positive: float | None,
    confidence: float | None,
    model_predictions: Mapping[str, Any],
    model_weights: Mapping[str, Any],
    model_versions: Mapping[str, str],
    feature_data_version: Mapping[str, str],
    regime_state: Mapping[str, Any] | None,
    baseline_prediction: Mapping[str, Any] | None,
    application_version: str,
    input_last_bar_at: str,
    input_row_count: int,
    input_fingerprint: str,
    source_path: str,
    production_or_challenger: str,
    metadata: Mapping[str, Any],
    basis_probes: Sequence[Sequence[Any]] | None = None,
) -> ForecastRecord:
    if predicted_return > 0:
        direction = "bullish"
    elif predicted_return < 0:
        direction = "bearish"
    else:
        direction = "neutral"

    fields = dict(
        generated_at=generated_at,
        cutoff_at=cutoff_at,
        symbol=symbol.upper(),
        horizon=horizon,
        price_at_cutoff=float(price_at_cutoff),
        predicted_direction=direction,
        predicted_return=float(predicted_return),
        probability_positive=probability_positive,
        confidence=confidence,
        model_predictions=dict(model_predictions),
        model_weights=dict(model_weights),
        model_versions=dict(model_versions),
        feature_data_version=dict(feature_data_version),
        regime_state=None if regime_state is None else dict(regime_state),
        baseline_prediction=(None if baseline_prediction is None
                             else dict(baseline_prediction)),
        application_version=application_version,
        input_last_bar_at=input_last_bar_at,
        input_row_count=int(input_row_count),
        input_fingerprint=input_fingerprint,
        forecast_schema_version=SCHEMA_VERSION,
        source_path=source_path,
        production_or_challenger=production_or_challenger,
        metadata=dict(metadata),
        basis_probes=(None if basis_probes is None
                      else [[str(date), float(close)] for date, close in basis_probes]),
    )
    identity = {
        key: _normalise_json(value)
        for key, value in fields.items()
    }
    return ForecastRecord(
        forecast_id="fcst_" + _digest(identity),
        **fields,
    )


def _reading_prediction(reading: ultimate.Reading) -> dict[str, Any]:
    skill = reading.skill
    return {
        "name": reading.name,
        "family": reading.family,
        "kind": reading.kind,
        "score": reading.score,
        "direction": reading.direction,
        "firing": reading.firing,
        "counts": reading.counts,
        "contribution": reading.contribution,
        "detail": reading.detail,
        "skill": {
            "hit_rate": skill.hit_rate,
            "samples": skill.samples,
            "effective": skill.effective,
            "edge": skill.edge,
            "t_stat": skill.t_stat,
            "note": skill.note,
        },
    }


def _incumbent_records(
    verdict: ultimate.UltimateVerdict,
    input_frames: Mapping[tuple[str, str], pd.DataFrame],
    *,
    generated_at: dt.datetime | pd.Timestamp | None = None,
    cutoff_at: dt.datetime | pd.Timestamp | None = None,
    model_versions: Mapping[str, str] | None = None,
    regime_state: Mapping[str, Any] | None = None,
    baseline_prediction: Mapping[str, Any] | None = None,
) -> list[ForecastRecord]:
    """Serialize each available incumbent horizon from its exact input frame."""
    generated = _utc_iso(generated_at or dt.datetime.now(dt.timezone.utc))
    supplied_versions = dict(model_versions or {})
    reserved = {"ultimate_ensemble", "technical_sources", "rule_agents"}
    if reserved & supplied_versions.keys():
        raise ValueError("caller cannot override incumbent implementation versions")
    versions = {
        "ultimate_ensemble": _module_version(ultimate),
        "technical_sources": _module_version(indicators),
        "rule_agents": _module_version(strategies),
        **supplied_versions,
    }
    app_version = versions["ultimate_ensemble"]
    records: list[ForecastRecord] = []

    for horizon in verdict.available:
        key = (horizon.horizon.interval, horizon.horizon.period)
        if key not in input_frames:
            raise ForecastIntegrityError(f"missing exact input frame for {key}")
        frame = input_frames[key]
        fingerprint = fingerprint_frame(frame, cutoff_at=cutoff_at)
        frame_last = _utc_iso(pd.to_datetime(frame["date"].iloc[-1]))
        horizon_cutoff = _utc_iso(horizon.as_of) if horizon.as_of is not None else frame_last
        if horizon_cutoff != frame_last or horizon.rows != len(frame):
            raise ForecastIntegrityError(
                f"captured input does not match the {horizon.horizon.key} verdict"
            )
        if not math.isclose(float(frame["close"].iloc[-1]), horizon.last_price,
                            rel_tol=0.0, abs_tol=1e-12):
            raise ForecastIntegrityError(
                f"captured input price does not match the {horizon.horizon.key} verdict"
            )
        if any(reading.kind == ultimate.MODEL for reading in horizon.readings):
            if "neural_challenger" not in versions:
                raise ForecastIntegrityError(
                    "model-assisted incumbent forecast requires neural_challenger version"
                )

        predictions = {
            reading.key: _reading_prediction(reading)
            for reading in horizon.readings
        }
        predictions["ensemble"] = {
            "action": horizon.action,
            "score": horizon.score,
            "expected_return_pct": horizon.expected_move_pct,
            "typical_move_pct": horizon.typical_move_pct,
            "agreement": horizon.agreement,
            "weighted_edge": horizon.weighted_edge,
            "coverage": horizon.coverage,
        }
        weights = {
            reading.key: {
                "raw": reading.skill.weight,
                "normalised": reading.weight,
            }
            for reading in horizon.readings
        }
        records.append(_record(
            generated_at=generated,
            cutoff_at=horizon_cutoff,
            symbol=verdict.symbol,
            horizon=horizon.horizon.key,
            price_at_cutoff=horizon.last_price,
            predicted_return=horizon.expected_move_pct,
            probability_positive=None,
            confidence=horizon.confidence,
            model_predictions=predictions,
            model_weights=weights,
            model_versions=versions,
            feature_data_version={
                "feature_schema": "ultimate-input-v1",
                "data": fingerprint,
            },
            regime_state=regime_state,
            baseline_prediction=baseline_prediction,
            application_version=app_version,
            input_last_bar_at=frame_last,
            input_row_count=len(frame),
            input_fingerprint=fingerprint,
            source_path="app.core.ultimate.evaluate",
            production_or_challenger=PRODUCTION_INCUMBENT,
            basis_probes=basis_probes(frame),
            metadata={
                "aggregate_action": verdict.action,
                "aggregate_score": verdict.score,
                "aggregate_confidence": verdict.confidence,
                "alignment": verdict.alignment,
                "bars_used": horizon.bars_used,
                "interval": horizon.interval,
                "errors": verdict.errors,
            },
        ))
    return records


def challenger_record(
    projection: forecast.Projection,
    *,
    symbol: str,
    input_frame: pd.DataFrame,
    interval: str,
    model_version: str,
    training_metadata: Mapping[str, Any],
    generated_at: dt.datetime | pd.Timestamp | None = None,
    cutoff_at: dt.datetime | pd.Timestamp | None = None,
    confidence: float | None = None,
    probability_positive: float | None = None,
    regime_state: Mapping[str, Any] | None = None,
    baseline_prediction: Mapping[str, Any] | None = None,
) -> ForecastRecord:
    """Serialize a genuine forward neural projection, never ``forecast.run``."""
    if not model_version.strip():
        raise ValueError("a stable challenger model_version is required")
    required = {"num_layers", "size_layer", "timestamp", "epochs", "dropout",
                "learning_rate", "training_first_bar", "training_last_bar",
                "training_rows"}
    missing = required - set(training_metadata)
    if missing:
        raise ValueError(f"training_metadata missing: {', '.join(sorted(missing))}")

    actual_cutoff = _utc_iso(projection.last_date)
    if _utc_iso(training_metadata["training_first_bar"]) != _utc_iso(
        pd.to_datetime(input_frame["date"].iloc[0])
    ):
        raise ForecastIntegrityError("training start does not match input frame")
    if _utc_iso(training_metadata["training_last_bar"]) != actual_cutoff:
        raise ForecastIntegrityError("training cutoff does not match projection cutoff")
    if int(training_metadata["training_rows"]) != len(input_frame):
        raise ForecastIntegrityError("training row count does not match input frame")
    if float(input_frame["close"].iloc[-1]) != float(projection.last_price):
        raise ForecastIntegrityError("input price does not match projection anchor")

    fingerprint = fingerprint_frame(input_frame, cutoff_at=cutoff_at)
    frame_last = _utc_iso(pd.to_datetime(input_frame["date"].iloc[-1]))
    if frame_last != actual_cutoff:
        raise ForecastIntegrityError("input last bar does not match projection cutoff")

    code_version = _module_version(forecast)
    versions = {
        "neural_challenger": model_version,
        "forecast_implementation": code_version,
    }
    return _record(
        generated_at=_utc_iso(generated_at or dt.datetime.now(dt.timezone.utc)),
        cutoff_at=actual_cutoff,
        symbol=symbol,
        horizon=f"{projection.horizon}x{interval}",
        price_at_cutoff=projection.last_price,
        predicted_return=projection.move_pct,
        probability_positive=probability_positive,
        confidence=confidence,
        model_predictions={
            "model": {
                "name": projection.model,
                "path": [float(value) for value in projection.path],
                "final_price": projection.final,
                "move_pct": projection.move_pct,
                "direction": projection.direction,
            }
        },
        model_weights={"model": {"raw": 1.0, "normalised": 1.0}},
        model_versions=versions,
        feature_data_version={
            "feature_schema": "close-only-neural-v1",
            "data": fingerprint,
        },
        regime_state=regime_state,
        baseline_prediction=baseline_prediction,
        application_version=code_version,
        input_last_bar_at=frame_last,
        input_row_count=len(input_frame),
        input_fingerprint=fingerprint,
        source_path="app.core.forecast.project",
        production_or_challenger=CHALLENGER,
        basis_probes=basis_probes(input_frame),
        metadata={"interval": interval, "training": dict(training_metadata)},
    )


class ForecastLedger:
    """SQLite-backed append-only store for immutable forecast payloads."""

    def __init__(self, path: str | pathlib.Path = DEFAULT_PATH):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    generated_at TEXT NOT NULL,
                    cutoff_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    production_or_challenger TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    CHECK (production_or_challenger IN
                           ('PRODUCTION_INCUMBENT', 'CHALLENGER'))
                );
                CREATE INDEX IF NOT EXISTS forecasts_symbol_cutoff
                    ON forecasts(symbol, cutoff_at, horizon);
                CREATE TRIGGER IF NOT EXISTS forecasts_no_update
                BEFORE UPDATE ON forecasts BEGIN
                    SELECT RAISE(ABORT, 'forecast records are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS forecasts_no_delete
                BEFORE DELETE ON forecasts BEGIN
                    SELECT RAISE(ABORT, 'forecast records are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS forecasts_no_replace
                BEFORE INSERT ON forecasts
                WHEN EXISTS (
                    SELECT 1 FROM forecasts WHERE forecast_id = NEW.forecast_id
                ) BEGIN
                    SELECT RAISE(ABORT, 'forecast records are immutable');
                END;
            """)

    def insert(self, record: ForecastRecord) -> None:
        self.insert_many([record])

    def insert_many(self, records: Iterable[ForecastRecord]) -> None:
        pending = list(records)
        if not pending:
            return
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                for record in pending:
                    payload = _canonical_json(record.payload())
                    connection.execute(
                        """INSERT INTO forecasts (
                               forecast_id, generated_at, cutoff_at, symbol, horizon,
                               source_path, production_or_challenger, input_fingerprint,
                               payload, payload_sha256
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (record.forecast_id, record.generated_at, record.cutoff_at,
                         record.symbol, record.horizon, record.source_path,
                         record.production_or_challenger, record.input_fingerprint,
                         payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()),
                    )
        except sqlite3.IntegrityError as error:
            raise ForecastExistsError("forecast identity is already frozen") from error

    def load(self, forecast_id: str) -> ForecastRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, payload_sha256 FROM forecasts WHERE forecast_id = ?",
                (forecast_id,),
            ).fetchone()
        if row is None:
            raise KeyError(forecast_id)
        actual = hashlib.sha256(row["payload"].encode("utf-8")).hexdigest()
        if actual != row["payload_sha256"]:
            raise ForecastIntegrityError(f"stored payload failed integrity check: {forecast_id}")
        return ForecastRecord.from_payload(json.loads(row["payload"]))

    def list(self, *, symbol: str | None = None) -> list[ForecastRecord]:
        query = "SELECT forecast_id FROM forecasts"
        parameters: tuple[str, ...] = ()
        if symbol is not None:
            query += " WHERE symbol = ?"
            parameters = (symbol.upper(),)
        query += " ORDER BY generated_at, forecast_id"
        with self._connect() as connection:
            ids = [row["forecast_id"] for row in connection.execute(query, parameters)]
        return [self.load(forecast_id) for forecast_id in ids]

    def has_frozen_input(
        self, *, symbol: str, horizon: str, input_fingerprint: str,
    ) -> bool:
        """Has this exact input already produced a forecast at this horizon?

        The idempotency key for live freezing.  `forecast_id` cannot serve:
        it digests `generated_at`, so re-running the engine on unchanged bars
        would mint a new identity every time and fill the ledger with rows
        that carry no new information and no new date.  The input fingerprint
        is the honest unit — one frozen forecast per symbol, horizon, and
        distinct set of consumed bars.
        """
        with self._connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM forecasts
                   WHERE symbol = ? AND horizon = ? AND input_fingerprint = ?
                   LIMIT 1""",
                (symbol.upper(), horizon, input_fingerprint),
            ).fetchone()
        return row is not None


def generate_and_freeze_incumbent(
    ledger: ForecastLedger,
    symbol: str,
    *,
    include_agents: bool = True,
    model: ultimate.ModelEvidence | None = None,
    model_versions: Mapping[str, str] | None = None,
    horizons: list[ultimate.Horizon] | None = None,
    force: bool = False,
    fetcher: Callable[..., tuple[pd.DataFrame, Any]] | None = None,
    generated_at: dt.datetime | pd.Timestamp | None = None,
    cutoff_at: dt.datetime | pd.Timestamp | None = None,
    regime_state: Mapping[str, Any] | None = None,
    baseline_prediction: Mapping[str, Any] | None = None,
) -> tuple[ultimate.UltimateVerdict, list[ForecastRecord]]:
    """Generate through the existing engine and freeze before returning it."""
    from . import live

    source_fetcher = fetcher or live.fetch
    captured: dict[tuple[str, str], pd.DataFrame] = {}

    def capture(name: str, *, period: str, interval: str, force: bool = False):
        frame, entry = source_fetcher(name, period=period, interval=interval, force=force)
        fingerprint_frame(frame, cutoff_at=cutoff_at)
        captured[(interval, period)] = frame.copy(deep=True)
        return frame, entry

    verdict = ultimate.evaluate(
        symbol, include_agents=include_agents, model=model, horizons=horizons,
        force=force, fetcher=capture,
    )
    records = _incumbent_records(
        verdict, captured, generated_at=generated_at, cutoff_at=cutoff_at,
        model_versions=model_versions,
        regime_state=regime_state, baseline_prediction=baseline_prediction,
    )
    ledger.insert_many(records)
    return verdict, records


@dataclasses.dataclass(frozen=True)
class FreezeOutcome:
    """What one live freeze attempt did, in terms a caller can display."""

    symbol: str
    frozen: tuple[ForecastRecord, ...]
    skipped: tuple[str, ...]

    @property
    def wrote_anything(self) -> bool:
        return bool(self.frozen)


def freeze_incumbent_if_new(
    ledger: ForecastLedger,
    symbol: str,
    **kwargs: Any,
) -> tuple[Any, FreezeOutcome]:
    """Freeze the incumbent forecast for any horizon whose bars are new.

    Idempotent by input fingerprint, which is what makes it safe to call on
    every live render: a horizon whose bars have not moved since it was last
    frozen is skipped, not re-frozen under a fresh `generated_at`.

    Nothing here is backfilled.  The engine is run *now*, against bars that
    end now, and the record is written before any outcome for it can exist —
    which is the entire reason a prospective ledger is worth more than a
    retrospective one.
    """
    from . import live

    source_fetcher = kwargs.pop("fetcher", None) or live.fetch
    cutoff_at = kwargs.get("cutoff_at")
    captured: dict[tuple[str, str], pd.DataFrame] = {}

    def capture(name: str, *, period: str, interval: str, force: bool = False):
        frame, entry = source_fetcher(name, period=period, interval=interval, force=force)
        fingerprint_frame(frame, cutoff_at=cutoff_at)
        captured[(interval, period)] = frame.copy(deep=True)
        return frame, entry

    verdict = ultimate.evaluate(
        symbol,
        include_agents=kwargs.pop("include_agents", True),
        model=kwargs.pop("model", None),
        horizons=kwargs.pop("horizons", None),
        force=kwargs.pop("force", False),
        fetcher=capture,
    )
    records = _incumbent_records(verdict, captured, **kwargs)

    fresh, skipped = [], []
    for record in records:
        if ledger.has_frozen_input(
            symbol=record.symbol, horizon=record.horizon,
            input_fingerprint=record.input_fingerprint,
        ):
            skipped.append(record.horizon)
        else:
            fresh.append(record)
    # One transaction: either every new horizon lands or none does, so a
    # crash mid-write cannot leave a symbol half-frozen at one timestamp.
    ledger.insert_many(fresh)
    return verdict, FreezeOutcome(
        symbol=verdict.symbol, frozen=tuple(fresh), skipped=tuple(skipped),
    )
