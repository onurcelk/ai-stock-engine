"""Outcome scoring and performance memory for frozen forecasts.

This module is the second half of the two-process separation that Phase 1
established.  `forecast_ledger` writes forecasts and never reads outcomes;
this module reads forecasts and never writes them.  The dependency arrow
points one way only, and `test_outcome_ledger.py` asserts it at the source
level.

Scoring never regenerates a forecast.  Everything here is a function of a
frozen `ForecastRecord` plus realised prices, so a historical prediction can
be scored years later without loading a model.

Units follow Phase 1: returns are percentage points (`1.25` means `+1.25%`)
and `probability_positive` is in `[0, 1]`.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import math
import pathlib
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from . import model_registry
from .forecast_ledger import (
    CHALLENGER,
    PRODUCTION_INCUMBENT,
    ForecastLedger,
    ForecastRecord,
    _canonical_json,
    _digest,
    _freeze_json,
    _normalise_json,
    _thaw_json,
    _utc_iso,
    fingerprint_frame,
)


#: v1 → v2 (AB-1, 2026-08-15) records the adjustment basis a return was
#: computed on.  See `reports/V5_ADJUSTMENT_BASIS_FINDING.md`.
OUTCOME_SCHEMA_VERSION = 2

#: How far the per-probe rescaling ratios may spread and still count as one
#: uniform back-adjustment.
#:
#: A genuine corporate action rescales every pre-action bar by an identical
#: constant, so in exact arithmetic the spread is zero; what is left is the
#: provider's float rounding.  The value is a deliberate middle: tight enough
#: that the tampering this guard exists to catch (whole percentage points)
#: cannot pass, loose enough that rounding noise does not re-open the very
#: hole AB-1 was written to close.  **If live data ever refuses here, this
#: constant is the one place to revisit — and doing so needs an amendment,
#: because loosening it trades tamper sensitivity for coverage.**
BASIS_UNIFORMITY_REL_TOL = 1e-4

#: Declared before any measurement.  Breakdowns thinner than this are not
#: reported as results — they are suppressed with their sample count visible.
MIN_SAMPLES = 30

#: Two trivial baselines, both computable from forecast-time information only.
#: `zero_return` is the random walk and is the control for error metrics.
#: `always_bullish` is the drift control for directional accuracy, which a
#: neutral baseline cannot supply.
BASELINE_ZERO_RETURN = "zero_return"
BASELINE_ALWAYS_BULLISH = "always_bullish"
BASELINE_FROM_RECORD = "forecast_record"
BASELINE_PHASE2_TRIVIAL = "phase2_trivial"

BULLISH, NEUTRAL, BEARISH = "bullish", "neutral", "bearish"

_Z = 1.959963984540054  # two-sided 95%


class OutcomeLedgerError(RuntimeError):
    """Base error for an outcome that cannot be resolved or trusted."""


class OutcomeExistsError(OutcomeLedgerError):
    """This forecast has already been scored; outcomes are written once."""


class OutcomeIntegrityError(OutcomeLedgerError):
    """Realised prices do not match the frozen forecast they would score."""


class NotMaturedError(OutcomeLedgerError):
    """The horizon has not elapsed yet, so no outcome exists to read."""


# --------------------------------------------------------------- maturity


@dataclasses.dataclass(frozen=True)
class MaturitySpec:
    """How far past the anchor bar this forecast's outcome lives."""

    interval: str
    bars_ahead: int

    def __post_init__(self) -> None:
        if not self.interval:
            raise ValueError("maturity interval is required")
        if self.bars_ahead < 1:
            raise ValueError("bars_ahead must be at least one bar")


def maturity_spec(record: ForecastRecord) -> MaturitySpec:
    """Read the horizon's bar distance from the frozen record, never guess it.

    A horizon in this repository is a number of bars at a stated interval, not
    a calendar duration — `1w` is five daily bars, `4h` is four hourly bars.
    Both numbers were frozen at forecast time, so scoring reads them back
    rather than re-deriving them from a horizon label.
    """
    if record.production_or_challenger == PRODUCTION_INCUMBENT:
        interval = record.metadata.get("interval")
        bars_ahead = record.metadata.get("bars_used")
        if not isinstance(interval, str) or not isinstance(bars_ahead, int):
            raise OutcomeIntegrityError(
                f"incumbent record {record.forecast_id} lacks a frozen bar mapping"
            )
        return MaturitySpec(interval=interval, bars_ahead=bars_ahead)

    if record.production_or_challenger == CHALLENGER:
        steps, _, interval = record.horizon.partition("x")
        declared = record.metadata.get("interval")
        if not interval or not steps.isdigit():
            raise OutcomeIntegrityError(
                f"challenger horizon {record.horizon!r} is not <steps>x<interval>"
            )
        if declared != interval:
            raise OutcomeIntegrityError(
                f"challenger record {record.forecast_id} disagrees about its interval"
            )
        return MaturitySpec(interval=interval, bars_ahead=int(steps))

    raise OutcomeIntegrityError(
        f"unknown production status: {record.production_or_challenger}"
    )


# --------------------------------------------------------------- outcomes


def _direction(return_pct: float) -> str:
    if return_pct > 0:
        return BULLISH
    if return_pct < 0:
        return BEARISH
    return NEUTRAL


def _correct(predicted: str, realised: str) -> bool | None:
    """None means the call is not scoreable, not that it was wrong.

    A neutral forecast declines to name a direction, and a bar that closed
    exactly flat offers no direction to have named.  Both are excluded from
    directional accuracy rather than counted as failures.
    """
    if predicted == NEUTRAL or realised == NEUTRAL:
        return None
    return predicted == realised


@dataclasses.dataclass(frozen=True)
class OutcomeRecord:
    outcome_id: str
    forecast_id: str
    scored_at: str
    anchor_at: str
    matured_at: str
    symbol: str
    horizon: str
    interval: str
    bars_ahead: int
    price_at_cutoff: float
    price_at_maturity: float
    #: The anchor the return was actually divided by, on the same adjustment
    #: basis as `price_at_maturity`.  Equal to `price_at_cutoff` unless a
    #: corporate action intervened.  Stored so the arithmetic is auditable
    #: from the record alone, without re-deriving the factor.
    scoring_anchor_price: float
    basis_factor: float
    corporate_action: bool
    basis_probe_count: int
    basis_max_deviation: float
    predicted_return: float
    predicted_direction: str
    realised_return: float
    realised_direction: str
    error: float
    absolute_error: float
    squared_error: float
    directional_correct: bool | None
    probability_positive: float | None
    brier_contribution: float | None
    baseline_source: str
    baseline_predictions: Mapping[str, Any]
    baseline_absolute_error: float
    baseline_squared_error: float
    baseline_directional_correct: bool | None
    baseline_relative_absolute_error: float
    market_symbol: str | None
    market_return: float | None
    market_relative_return: float | None
    sector_symbol: str | None
    sector_return: float | None
    sector_relative_return: float | None
    constituent_directional: Mapping[str, Any]
    realised_fingerprint: str
    outcome_schema_version: int
    notes: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("baseline_predictions", "constituent_directional", "notes"):
            object.__setattr__(
                self, field_name, _freeze_json(_normalise_json(getattr(self, field_name)))
            )
        if self.outcome_schema_version != OUTCOME_SCHEMA_VERSION:
            raise ValueError(f"unsupported outcome schema {self.outcome_schema_version}")
        if self.bars_ahead < 1:
            raise ValueError("bars_ahead must be at least one bar")
        if not math.isfinite(self.price_at_maturity) or self.price_at_maturity <= 0:
            raise ValueError("price_at_maturity must be finite and positive")
        if self.probability_positive is not None and not 0 <= self.probability_positive <= 1:
            raise ValueError("probability_positive must be null or in [0, 1]")
        anchor = pd.Timestamp(self.anchor_at)
        matured = pd.Timestamp(self.matured_at)
        scored = pd.Timestamp(self.scored_at)
        if any(stamp.tzinfo is None for stamp in (anchor, matured, scored)):
            raise ValueError("outcome timestamps must be timezone-aware")
        if not anchor < matured <= scored:
            raise ValueError("outcome timestamps violate maturity ordering")
        expected = "otcm_" + _digest(self.identity_payload())
        if self.outcome_id != expected:
            raise ValueError("outcome_id does not match the outcome payload")

    def payload(self) -> dict[str, Any]:
        return {
            field.name: _thaw_json(getattr(self, field.name))
            for field in dataclasses.fields(self)
        }

    def identity_payload(self) -> dict[str, Any]:
        return {
            key: value for key, value in self.payload().items()
            if key != "outcome_id"
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "OutcomeRecord":
        return cls(**dict(payload))


def _utc(value: dt.datetime | pd.Timestamp | str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _locate(frame: pd.DataFrame, anchor_at: str) -> int:
    if frame.empty or "date" not in frame or "close" not in frame:
        raise OutcomeIntegrityError("realised frame must contain date and close")
    dates = pd.to_datetime(frame["date"], errors="raise", utc=True)
    if not dates.is_monotonic_increasing:
        raise OutcomeIntegrityError("realised frame must be chronological")
    matches = np.flatnonzero((dates == _utc(anchor_at)).to_numpy())
    if matches.size != 1:
        raise OutcomeIntegrityError(
            f"realised frame does not contain exactly one bar at {anchor_at}"
        )
    return int(matches[0])


@dataclasses.dataclass(frozen=True)
class BasisReconciliation:
    """The result of asking why a frozen anchor no longer matches the feed.

    `factor` is the constant every pre-action bar was multiplied by.  It is
    1.0 exactly when nothing happened, which is the overwhelmingly common
    case and costs one comparison.
    """

    factor: float
    corporate_action: bool
    probe_count: int
    max_deviation: float
    scoring_anchor: float


def reconcile_basis(
    record: ForecastRecord, frame: pd.DataFrame, anchor_close: float,
) -> BasisReconciliation:
    """Decide whether a changed anchor is a rescaling or a corruption.

    The live feed is fetched with `auto_adjust=True`, so a split or dividend
    after a forecast was frozen back-adjusts the *entire* pre-action history
    by one constant.  A tampered or substituted bar does not: it moves alone.
    That difference is the whole test, and it is why Phase 1 stores several
    probes rather than one price.

    Raises rather than returning a fallback.  A mismatch this cannot explain
    is exactly the corruption Phase 2's guard was written to stop, and it
    must never be downgraded to a skipped row.
    """
    frozen = float(record.price_at_cutoff)
    if math.isclose(anchor_close, frozen, rel_tol=1e-9, abs_tol=1e-9):
        return BasisReconciliation(
            factor=1.0, corporate_action=False, probe_count=0,
            max_deviation=0.0, scoring_anchor=frozen,
        )

    probes = record.basis_probes
    if not probes:
        # Pre-AB-1 records carry no probes, so nothing can distinguish a
        # rescaling from corruption.  Refusing is the honest answer and it is
        # the behaviour that existed before AB-1.
        raise OutcomeIntegrityError(
            f"realised anchor price {anchor_close} does not match the frozen "
            f"{frozen} for {record.forecast_id}, and the record carries no "
            f"basis probes to reconcile it"
        )

    dates = pd.to_datetime(frame["date"], errors="raise", utc=True).to_numpy()
    ratios: list[float] = []
    for probe_date, probe_close in probes:
        matches = np.flatnonzero(dates == _utc(str(probe_date)))
        if matches.size != 1:
            raise OutcomeIntegrityError(
                f"realised frame does not contain exactly one bar at "
                f"{probe_date} to reconcile {record.forecast_id}"
            )
        observed = float(frame["close"].iloc[int(matches[0])])
        stored = float(probe_close)
        if not math.isfinite(observed) or observed <= 0 or stored <= 0:
            raise OutcomeIntegrityError(
                f"unusable probe close reconciling {record.forecast_id}"
            )
        ratios.append(observed / stored)

    factor = float(np.median(ratios))
    if not math.isfinite(factor) or factor <= 0:
        raise OutcomeIntegrityError(
            f"implied adjustment factor is unusable for {record.forecast_id}"
        )
    max_deviation = max(abs(ratio / factor - 1.0) for ratio in ratios)
    anchor_deviation = abs((anchor_close / frozen) / factor - 1.0)
    max_deviation = max(max_deviation, anchor_deviation)
    if max_deviation > BASIS_UNIFORMITY_REL_TOL:
        # Not a uniform rescaling.  Some bars moved and others did not, which
        # no corporate action can produce.
        raise OutcomeIntegrityError(
            f"realised anchor price {anchor_close} does not match the frozen "
            f"{frozen} for {record.forecast_id}, and the change is not a "
            f"uniform rescaling (deviation {max_deviation:.3e} across "
            f"{len(ratios)} probes)"
        )
    return BasisReconciliation(
        factor=factor, corporate_action=True, probe_count=len(ratios),
        max_deviation=max_deviation, scoring_anchor=anchor_close,
    )


def _window_return(
    frame: pd.DataFrame, anchor_at: str, matured_at: str, *, label: str,
) -> float:
    """Percentage move of a reference series over the identical bar window."""
    dates = pd.to_datetime(frame["date"], errors="raise", utc=True)
    start = np.flatnonzero((dates == _utc(anchor_at)).to_numpy())
    end = np.flatnonzero((dates == _utc(matured_at)).to_numpy())
    if start.size != 1 or end.size != 1:
        raise OutcomeIntegrityError(
            f"{label} frame does not span the forecast window exactly"
        )
    first = float(frame["close"].iloc[int(start[0])])
    last = float(frame["close"].iloc[int(end[0])])
    if not math.isfinite(first) or first <= 0 or not math.isfinite(last) or last <= 0:
        raise OutcomeIntegrityError(f"{label} frame has an unusable close")
    return (last / first - 1.0) * 100.0


def _baseline(record: ForecastRecord) -> tuple[str, dict[str, Any]]:
    """Return the baseline to beat and where it came from.

    A baseline frozen at forecast time wins if one exists.  Otherwise the two
    trivial controls are constructed here from `price_at_cutoff` alone, which
    is forecast-time information — no realised price is consulted.
    """
    stored = record.baseline_prediction
    if stored:
        return BASELINE_FROM_RECORD, _thaw_json(stored)
    return BASELINE_PHASE2_TRIVIAL, {
        BASELINE_ZERO_RETURN: {"predicted_return": 0.0, "predicted_direction": NEUTRAL},
        BASELINE_ALWAYS_BULLISH: {"predicted_direction": BULLISH},
    }


def _baseline_terms(
    source: str, baselines: Mapping[str, Any], realised_return: float,
    realised_direction: str,
) -> tuple[float, float, bool | None]:
    if source == BASELINE_FROM_RECORD:
        predicted = float(baselines.get("predicted_return", 0.0))
        direction = str(baselines.get("predicted_direction", _direction(predicted)))
    else:
        predicted = float(baselines[BASELINE_ZERO_RETURN]["predicted_return"])
        direction = str(baselines[BASELINE_ALWAYS_BULLISH]["predicted_direction"])
    error = predicted - realised_return
    return abs(error), error * error, _correct(direction, realised_direction)


def _constituent_directional(
    record: ForecastRecord, realised_direction: str,
) -> dict[str, Any]:
    """Directional hit/miss for each constituent that named a direction.

    This is a diagnostic, not a return forecast: a constituent emits a signal
    score, so only the sign of its call is scoreable here.  Phase 3 and 4 own
    the question of what a constituent is worth.
    """
    result: dict[str, Any] = {}
    for key, prediction in record.model_predictions.items():
        if key == "ensemble" or not isinstance(prediction, Mapping):
            continue
        direction = prediction.get("direction")
        if direction not in {BULLISH, NEUTRAL, BEARISH}:
            continue
        result[key] = {
            "direction": direction,
            "correct": _correct(str(direction), realised_direction),
        }
    return result


def resolve_outcome(
    record: ForecastRecord,
    frame: pd.DataFrame,
    *,
    market_frame: pd.DataFrame | None = None,
    market_symbol: str | None = None,
    sector_frame: pd.DataFrame | None = None,
    sector_symbol: str | None = None,
    scored_at: dt.datetime | pd.Timestamp | None = None,
) -> OutcomeRecord | None:
    """Score one frozen forecast against realised prices, or return None.

    None means the horizon has not elapsed.  It is not an error and it is not
    a zero — an unmatured forecast simply has no outcome yet.

    Only the bars from the anchor through the maturity bar are read.  The
    window is sliced before anything is computed, so prices after maturity
    cannot reach any number in the returned record.
    """
    spec = maturity_spec(record)
    anchor_at = record.input_last_bar_at
    anchor = _locate(frame, anchor_at)

    anchor_close = float(frame["close"].iloc[anchor])
    # The guard is unchanged in strength: an anchor that moved for any reason
    # this cannot explain as a uniform rescaling still raises.  What AB-1 adds
    # is the ability to explain one specific, legitimate reason.
    basis = reconcile_basis(record, frame, anchor_close)

    target = anchor + spec.bars_ahead
    if target >= len(frame):
        return None

    window = frame.iloc[anchor:target + 1].reset_index(drop=True)
    matured_at = _utc_iso(pd.to_datetime(window["date"].iloc[-1]))
    # Fingerprinting with the maturity cutoff proves the scored window ends
    # where the horizon ends.
    realised_fingerprint = fingerprint_frame(window, cutoff_at=matured_at)

    price_at_maturity = float(window["close"].iloc[-1])
    if not math.isfinite(price_at_maturity) or price_at_maturity <= 0:
        raise OutcomeIntegrityError(
            f"realised maturity price is unusable for {record.forecast_id}"
        )

    # Both prices on one basis.  Without a corporate action `scoring_anchor`
    # *is* the frozen price and this is bit-for-bit the pre-AB-1 arithmetic;
    # with one, using the frozen price here would book a 2-for-1 split as a
    # −50% return on a flat position.
    realised_return = (price_at_maturity / basis.scoring_anchor - 1.0) * 100.0
    realised_direction = _direction(realised_return)
    error = record.predicted_return - realised_return

    probability = record.probability_positive
    brier = None
    if probability is not None:
        # The event is a strictly positive move, matching `_direction`.
        outcome_bit = 1.0 if realised_return > 0 else 0.0
        brier = (probability - outcome_bit) ** 2

    baseline_source, baselines = _baseline(record)
    baseline_ae, baseline_se, baseline_correct = _baseline_terms(
        baseline_source, baselines, realised_return, realised_direction
    )

    market_return = None
    if market_frame is not None:
        market_return = _window_return(
            market_frame, anchor_at, matured_at, label="market"
        )
    sector_return = None
    if sector_frame is not None:
        sector_return = _window_return(
            sector_frame, anchor_at, matured_at, label="sector"
        )

    notes = {
        # Countable by design: AB-1's whole complaint about the pre-existing
        # behaviour was that dropped observations left no trace to count.
        "basis_status": (
            "CORPORATE_ACTION_RECONCILED" if basis.corporate_action
            else "UNCHANGED_BASIS"
        ),
        "baseline_source": baseline_source,
        "sector_status": (
            "CALLER_SUPPLIED_PROXY" if sector_frame is not None
            else "UNAVAILABLE_NO_PIT_SECTOR_MAP"
        ),
        "probability_status": (
            "SCORED" if probability is not None else "NO_PROBABILISTIC_FORECAST"
        ),
    }

    fields = dict(
        forecast_id=record.forecast_id,
        scored_at=_utc_iso(scored_at or dt.datetime.now(dt.timezone.utc)),
        anchor_at=anchor_at,
        matured_at=matured_at,
        symbol=record.symbol,
        horizon=record.horizon,
        interval=spec.interval,
        bars_ahead=spec.bars_ahead,
        price_at_cutoff=float(record.price_at_cutoff),
        price_at_maturity=price_at_maturity,
        scoring_anchor_price=float(basis.scoring_anchor),
        basis_factor=float(basis.factor),
        corporate_action=bool(basis.corporate_action),
        basis_probe_count=int(basis.probe_count),
        basis_max_deviation=float(basis.max_deviation),
        predicted_return=float(record.predicted_return),
        predicted_direction=record.predicted_direction,
        realised_return=realised_return,
        realised_direction=realised_direction,
        error=error,
        absolute_error=abs(error),
        squared_error=error * error,
        directional_correct=_correct(record.predicted_direction, realised_direction),
        probability_positive=probability,
        brier_contribution=brier,
        baseline_source=baseline_source,
        baseline_predictions=baselines,
        baseline_absolute_error=baseline_ae,
        baseline_squared_error=baseline_se,
        baseline_directional_correct=baseline_correct,
        baseline_relative_absolute_error=baseline_ae - abs(error),
        market_symbol=market_symbol,
        market_return=market_return,
        market_relative_return=(
            None if market_return is None else realised_return - market_return
        ),
        sector_symbol=sector_symbol,
        sector_return=sector_return,
        sector_relative_return=(
            None if sector_return is None else realised_return - sector_return
        ),
        constituent_directional=_constituent_directional(record, realised_direction),
        realised_fingerprint=realised_fingerprint,
        outcome_schema_version=OUTCOME_SCHEMA_VERSION,
        notes=notes,
    )
    identity = {key: _normalise_json(value) for key, value in fields.items()}
    return OutcomeRecord(outcome_id="otcm_" + _digest(identity), **fields)


# ------------------------------------------------------------------ store


class OutcomeStore:
    """Append-only outcomes, keyed by `forecast_id`, in their own table.

    The Phase 1 `forecasts` table is never written, altered, or joined into a
    mutable view.  A foreign key makes an outcome impossible without the
    frozen forecast it scores, and a unique constraint makes a forecast
    scoreable exactly once.
    """

    def __init__(self, path: str | pathlib.Path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    forecast_id TEXT NOT NULL UNIQUE
                        REFERENCES forecasts(forecast_id),
                    scored_at TEXT NOT NULL,
                    anchor_at TEXT NOT NULL,
                    matured_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS outcomes_matured
                    ON outcomes(matured_at, symbol, horizon);
                CREATE TRIGGER IF NOT EXISTS outcomes_no_update
                BEFORE UPDATE ON outcomes BEGIN
                    SELECT RAISE(ABORT, 'outcome records are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS outcomes_no_delete
                BEFORE DELETE ON outcomes BEGIN
                    SELECT RAISE(ABORT, 'outcome records are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS outcomes_no_replace
                BEFORE INSERT ON outcomes
                WHEN EXISTS (
                    SELECT 1 FROM outcomes WHERE forecast_id = NEW.forecast_id
                ) BEGIN
                    SELECT RAISE(ABORT, 'outcome records are immutable');
                END;
            """)

    def insert(self, record: OutcomeRecord) -> None:
        self.insert_many([record])

    def insert_many(self, records: Iterable[OutcomeRecord]) -> None:
        pending = list(records)
        if not pending:
            return
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                for record in pending:
                    payload = _canonical_json(record.payload())
                    connection.execute(
                        """INSERT INTO outcomes (
                               outcome_id, forecast_id, scored_at, anchor_at,
                               matured_at, symbol, horizon, payload, payload_sha256
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (record.outcome_id, record.forecast_id, record.scored_at,
                         record.anchor_at, record.matured_at, record.symbol,
                         record.horizon, payload,
                         hashlib.sha256(payload.encode("utf-8")).hexdigest()),
                    )
        except sqlite3.IntegrityError as error:
            if "FOREIGN KEY" in str(error):
                raise OutcomeIntegrityError(
                    "cannot score a forecast that is not frozen in this ledger"
                ) from error
            raise OutcomeExistsError(
                f"outcome cannot be written: {error}"
            ) from error

    def _load_payload(self, row: sqlite3.Row) -> OutcomeRecord:
        actual = hashlib.sha256(row["payload"].encode("utf-8")).hexdigest()
        if actual != row["payload_sha256"]:
            raise OutcomeIntegrityError(
                f"stored outcome failed integrity check: {row['outcome_id']}"
            )
        return OutcomeRecord.from_payload(json.loads(row["payload"]))

    def load(self, forecast_id: str) -> OutcomeRecord:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT outcome_id, payload, payload_sha256 FROM outcomes
                   WHERE forecast_id = ?""",
                (forecast_id,),
            ).fetchone()
        if row is None:
            raise KeyError(forecast_id)
        return self._load_payload(row)

    def list(self, *, symbol: str | None = None) -> list[OutcomeRecord]:
        query = "SELECT outcome_id, payload, payload_sha256 FROM outcomes"
        parameters: tuple[str, ...] = ()
        if symbol is not None:
            query += " WHERE symbol = ?"
            parameters = (symbol.upper(),)
        query += " ORDER BY matured_at, outcome_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._load_payload(row) for row in rows]

    def scored_ids(self) -> set[str]:
        with self._connect() as connection:
            return {
                row["forecast_id"]
                for row in connection.execute("SELECT forecast_id FROM outcomes")
            }


def score_matured(
    ledger: ForecastLedger,
    store: OutcomeStore,
    frames: Callable[[str, str], pd.DataFrame | None],
    *,
    symbol: str | None = None,
    market_frames: Callable[[str, str], tuple[str, pd.DataFrame] | None] | None = None,
    scored_at: dt.datetime | pd.Timestamp | None = None,
) -> list[OutcomeRecord]:
    """Score every matured, unscored forecast.  Writes outcomes only.

    `frames(symbol, interval)` supplies realised prices.  No model is called
    and no forecast is regenerated, which is the Phase 2 gate.
    """
    already = store.scored_ids()
    resolved: list[OutcomeRecord] = []
    for record in ledger.list(symbol=symbol):
        if record.forecast_id in already:
            continue
        spec = maturity_spec(record)
        frame = frames(record.symbol, spec.interval)
        if frame is None or frame.empty:
            continue
        market_symbol, market_frame = None, None
        if market_frames is not None:
            supplied = market_frames(record.symbol, spec.interval)
            if supplied is not None:
                market_symbol, market_frame = supplied
        outcome = resolve_outcome(
            record, frame,
            market_frame=market_frame, market_symbol=market_symbol,
            scored_at=scored_at,
        )
        if outcome is not None:
            resolved.append(outcome)
    store.insert_many(resolved)
    return resolved


# ----------------------------------------------------- performance memory


def model_key(record: ForecastRecord) -> str:
    """The unit a score is attributed to: the Phase 3 registry identity.

    Identity is stable across retraining, so two versions of one model pool
    into one row here.  When that pooling matters, group on `model_version`
    as well — `performance_frame` carries both columns for exactly that
    reason, and Phase 4 must decide which it wants rather than inherit one.
    """
    return model_registry.record_spec(record).model_id


def wilson_interval(successes: int, n: int, z: float = _Z) -> tuple[float, float]:
    """Score interval for a rate — usable at the small n this ledger starts at."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def _mean_half_width(values: Sequence[float], z: float = _Z) -> float:
    """Normal-approximation half-width.  Read it alongside n, never alone."""
    array = np.asarray([v for v in values if v is not None and math.isfinite(v)],
                       dtype=float)
    if array.size < 2:
        return float("nan")
    return float(z * array.std(ddof=1) / math.sqrt(array.size))


def performance_frame(
    pairs: Iterable[tuple[ForecastRecord, OutcomeRecord]],
) -> pd.DataFrame:
    """One tidy row per scored forecast — the substrate for every summary."""
    rows = []
    for record, outcome in pairs:
        if record.forecast_id != outcome.forecast_id:
            raise OutcomeIntegrityError("forecast and outcome identities disagree")
        rows.append({
            "forecast_id": record.forecast_id,
            "model_key": model_key(record),
            "model_version": model_registry.record_version(record),
            "status": record.production_or_challenger,
            "symbol": outcome.symbol,
            "horizon": outcome.horizon,
            "interval": outcome.interval,
            "bars_ahead": outcome.bars_ahead,
            "cutoff_at": pd.Timestamp(record.cutoff_at),
            "matured_at": pd.Timestamp(outcome.matured_at),
            "predicted_return": outcome.predicted_return,
            "realised_return": outcome.realised_return,
            "predicted_direction": outcome.predicted_direction,
            "realised_direction": outcome.realised_direction,
            "error": outcome.error,
            "absolute_error": outcome.absolute_error,
            "squared_error": outcome.squared_error,
            "directional_correct": outcome.directional_correct,
            "confidence": record.confidence,
            "probability_positive": outcome.probability_positive,
            "brier_contribution": outcome.brier_contribution,
            "baseline_source": outcome.baseline_source,
            "baseline_absolute_error": outcome.baseline_absolute_error,
            "baseline_squared_error": outcome.baseline_squared_error,
            "baseline_directional_correct": outcome.baseline_directional_correct,
            "baseline_relative_absolute_error": outcome.baseline_relative_absolute_error,
            "market_relative_return": outcome.market_relative_return,
            "sector_relative_return": outcome.sector_relative_return,
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["matured_at", "forecast_id"]).reset_index(drop=True)


def known_as_of(frame: pd.DataFrame, when: dt.datetime | pd.Timestamp) -> pd.DataFrame:
    """Outcomes observable at `when` — the only slice a weight may be built on.

    Performance memory becomes known at *maturity*, not at the cutoff the
    forecast was made on.  Any Phase 5 weighting that filters on `cutoff_at`
    would be using outcomes that had not happened yet.
    """
    if frame.empty:
        return frame
    return frame.loc[frame["matured_at"] <= _utc(when)].reset_index(drop=True)


def _summarise_group(group: pd.DataFrame) -> dict[str, Any]:
    called = group.loc[group["directional_correct"].notna()]
    hits = int(called["directional_correct"].sum())
    n_called = int(len(called))
    low, high = wilson_interval(hits, n_called)

    baseline_called = group.loc[group["baseline_directional_correct"].notna()]
    baseline_hits = int(baseline_called["baseline_directional_correct"].sum())
    n_baseline = int(len(baseline_called))

    mae = float(group["absolute_error"].mean())
    baseline_mae = float(group["baseline_absolute_error"].mean())
    probabilistic = group.loc[group["brier_contribution"].notna()]

    return {
        "n": int(len(group)),
        "n_directional": n_called,
        "directional_accuracy": (hits / n_called) if n_called else float("nan"),
        "directional_ci_low": low,
        "directional_ci_high": high,
        "baseline_directional_accuracy": (
            (baseline_hits / n_baseline) if n_baseline else float("nan")
        ),
        "mean_error": float(group["error"].mean()),
        "mean_error_half_width": _mean_half_width(group["error"].tolist()),
        "mae": mae,
        "mae_half_width": _mean_half_width(group["absolute_error"].tolist()),
        "rmse": float(math.sqrt(group["squared_error"].mean())),
        "baseline_mae": baseline_mae,
        "baseline_rmse": float(math.sqrt(group["baseline_squared_error"].mean())),
        # Positive skill means the forecast beat the baseline it declared.
        "mae_skill": (1.0 - mae / baseline_mae) if baseline_mae > 0 else float("nan"),
        "mae_advantage": float(group["baseline_relative_absolute_error"].mean()),
        "mae_advantage_half_width": _mean_half_width(
            group["baseline_relative_absolute_error"].tolist()
        ),
        "n_probabilistic": int(len(probabilistic)),
        "brier": (float(probabilistic["brier_contribution"].mean())
                  if len(probabilistic) else float("nan")),
        "mean_realised_return": float(group["realised_return"].mean()),
    }


def summarise(
    frame: pd.DataFrame,
    *,
    by: Sequence[str] = ("model_key", "horizon"),
    min_samples: int = 0,
) -> pd.DataFrame:
    """Expanding (all-history) performance, grouped by `by`.

    Every row carries `n` and an interval.  Groups below `min_samples` are
    reported with their counts and a `sufficient` flag of False rather than
    quietly dropped — a thin cell is evidence about coverage.
    """
    if frame.empty:
        return pd.DataFrame()
    rows = []
    for key, group in frame.groupby(list(by), dropna=False, sort=True):
        keys = key if isinstance(key, tuple) else (key,)
        summary = dict(zip(by, keys))
        summary.update(_summarise_group(group))
        summary["sufficient"] = summary["n"] >= min_samples
        rows.append(summary)
    return pd.DataFrame(rows)


def breakdown(
    frame: pd.DataFrame,
    *,
    by: Sequence[str] = ("model_key", "horizon", "symbol"),
    min_samples: int = MIN_SAMPLES,
) -> pd.DataFrame:
    """Symbol/sector-level cuts, suppressed until the sample supports them.

    The metric columns of an insufficient row are blanked; `n` stays visible
    so the reader can see what was withheld and why.
    """
    summary = summarise(frame, by=by, min_samples=min_samples)
    if summary.empty:
        return summary
    protected = set(by) | {"n", "n_directional", "n_probabilistic", "sufficient"}
    thin = ~summary["sufficient"]
    for column in summary.columns:
        if column not in protected:
            summary.loc[thin, column] = np.nan
    return summary


def expanding_summary(
    frame: pd.DataFrame, *, by: Sequence[str] = ("model_key", "horizon"),
) -> pd.DataFrame:
    """All-history performance after each maturity, in maturity order."""
    return _sequential_summary(frame, by=by, window=None)


def rolling_summary(
    frame: pd.DataFrame, *, by: Sequence[str] = ("model_key", "horizon"),
    window: int = 20,
) -> pd.DataFrame:
    """Trailing-`window` performance after each maturity, in maturity order."""
    if window < 1:
        raise ValueError("rolling window must be at least one outcome")
    return _sequential_summary(frame, by=by, window=window)


def _sequential_summary(
    frame: pd.DataFrame, *, by: Sequence[str], window: int | None,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = []
    for key, group in frame.groupby(list(by), dropna=False, sort=True):
        keys = key if isinstance(key, tuple) else (key,)
        ordered = group.sort_values(["matured_at", "forecast_id"])
        for position in range(len(ordered)):
            start = 0 if window is None else max(0, position + 1 - window)
            slice_ = ordered.iloc[start:position + 1]
            row = dict(zip(by, keys))
            row["matured_at"] = ordered["matured_at"].iloc[position]
            row["forecast_id"] = ordered["forecast_id"].iloc[position]
            row["window"] = "expanding" if window is None else window
            row.update(_summarise_group(slice_))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["matured_at", "forecast_id"]
    ).reset_index(drop=True)


def calibration(
    frame: pd.DataFrame, *, bins: Sequence[float] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
) -> pd.DataFrame:
    """Reliability table for probabilistic forecasts.

    Returns an empty frame when nothing carried a probability.  Confidence is
    never substituted for a probability — Phase 1 kept those fields distinct
    and this module does not quietly rejoin them.
    """
    if frame.empty or "probability_positive" not in frame:
        return pd.DataFrame()
    scored = frame.loc[frame["probability_positive"].notna()].copy()
    if scored.empty:
        return pd.DataFrame()
    scored["observed"] = (scored["realised_return"] > 0).astype(int)
    edges = list(bins)
    scored["bin"] = pd.cut(
        scored["probability_positive"], bins=edges, include_lowest=True
    )
    rows = []
    for interval, group in scored.groupby("bin", observed=True, sort=True):
        hits = int(group["observed"].sum())
        n = int(len(group))
        low, high = wilson_interval(hits, n)
        rows.append({
            "bin": str(interval),
            "n": n,
            "mean_predicted": float(group["probability_positive"].mean()),
            "observed_rate": hits / n,
            "observed_ci_low": low,
            "observed_ci_high": high,
            "brier": float(group["brier_contribution"].mean()),
        })
    return pd.DataFrame(rows)


def constituent_directional(
    pairs: Iterable[tuple[ForecastRecord, OutcomeRecord]],
    *,
    min_samples: int = MIN_SAMPLES,
) -> pd.DataFrame:
    """Per-constituent directional hit rate — a diagnostic, not a ranking.

    A constituent's score is a signal, not a predicted return, so only the
    sign is scoreable.  Rows thinner than `min_samples` keep their counts and
    are flagged insufficient.
    """
    tally: dict[tuple[str, str], list[int]] = {}
    for record, outcome in pairs:
        horizon = outcome.horizon
        for key, call in outcome.constituent_directional.items():
            correct = call.get("correct")
            if correct is None:
                continue
            bucket = tally.setdefault((key, horizon), [0, 0])
            bucket[0] += int(bool(correct))
            bucket[1] += 1
    rows = []
    for (key, horizon), (hits, n) in sorted(tally.items()):
        low, high = wilson_interval(hits, n)
        rows.append({
            "constituent": key,
            "horizon": horizon,
            "n_directional": n,
            "hit_rate": hits / n,
            "ci_low": low,
            "ci_high": high,
            "sufficient": n >= min_samples,
        })
    return pd.DataFrame(rows)
