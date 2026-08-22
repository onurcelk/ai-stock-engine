"""JSON adapters for `core/` dataclasses -- the API boundary only.

Nothing here modifies a `core/` dataclass or recomputes anything the
research/forecasting path already produced. Every function is a pure,
read-only walk of an object the caller already built by calling the real
`core` functions (`ledger_activation.evaluate_and_freeze`, etc.) -- the same
discipline this project's research code applies to its own instruments:
new code wraps and reuses, it never reimplements.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from typing import Any

import numpy as np
import pandas as pd


def to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses / numpy / pandas scalars to JSON-safe values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, np.floating):
        as_float = float(value)
        return None if math.isnan(as_float) else as_float
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Fallback for anything unexpected (e.g. an enum): stringify rather than
    # raise, since a Phase 0 endpoint failing on one odd field is worse than
    # a slightly-lossy string.
    return str(value)


def horizon_verdict_to_dict(horizon_verdict) -> dict:
    """A `core.ultimate.HorizonVerdict`, plus the computed properties the
    Signal page needs (`action`, `expected_move_pct`, `target_price`,
    `available`) that `dataclasses.fields()` does not see."""
    data = to_jsonable(horizon_verdict)
    data["action"] = horizon_verdict.action
    data["expected_move_pct"] = to_jsonable(horizon_verdict.expected_move_pct)
    data["target_price"] = to_jsonable(horizon_verdict.target_price)
    data["available"] = horizon_verdict.available
    return data


def verdict_to_dict(verdict) -> dict:
    """A `core.ultimate.UltimateVerdict`, with per-horizon data expanded
    through `horizon_verdict_to_dict` and the top-level `action`/`last_price`
    properties included."""
    data = to_jsonable(verdict)
    data["action"] = verdict.action
    data["last_price"] = to_jsonable(verdict.last_price)
    data["horizons"] = [horizon_verdict_to_dict(h) for h in verdict.horizons]
    return data
