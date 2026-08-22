"""Headless prospective scoring: read matured outcomes for the live ledger.

`core/collector.py` writes forecasts. Nothing wrote outcomes for them: until
this module existed, `outcome_ledger.score_matured` was only ever called
against `app/replay_study.sqlite3` (by `replay_study.py`) and by tests, never
against the production ledger. `promotion.evidence_for` counts *matured* rows
only, so without this, independent prospective cutoffs would stay at 0
forever regardless of how long collection ran.

This module is **not a second scoring path**. It calls
`outcome_ledger.score_matured` unmodified, pointed at the production ledger,
with realised prices from `live.fetch` — the same fetch the engine itself
uses. It reads prices and writes outcomes; it never calls a model, never
regenerates a forecast, and never touches the `forecasts` table.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
import sys
from typing import Any, Callable

import pandas as pd


#: Run logs, one JSON file per run, beside the ledger and gitignored with it.
DEFAULT_LOG_DIR = pathlib.Path(__file__).resolve().parents[1] / "score_logs"

#: Wide enough to cover every horizon and every forecast age this ledger can
#: hold, mirroring `replay_study.MemoisedFetcher`'s convention. Intraday bars
#: are a separate case: Yahoo refuses `1h` history older than 730 days
#: regardless of what is asked for, so requesting "10y" for an intraday
#: interval fails outright rather than silently truncating.
FETCH_PERIOD_DAILY_PLUS = "10y"
FETCH_PERIOD_INTRADAY = "729d"
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}


def _fetch_period(interval: str) -> str:
    return FETCH_PERIOD_INTRADAY if interval in INTRADAY_INTERVALS else FETCH_PERIOD_DAILY_PLUS


class ScoringError(RuntimeError):
    """The run could not be completed as declared."""


class _MemoisedFrames:
    """One download per `(symbol, interval)`, reused across every forecast.

    A ledger with N unscored rows for one symbol at one horizon would
    otherwise be N identical downloads. Fetching once makes every forecast
    for that symbol and interval read the same realised history.
    """

    def __init__(self, fetcher: Callable[..., tuple[pd.DataFrame, Any]] | None = None):
        self._fetcher = fetcher
        self._cache: dict[tuple[str, str], pd.DataFrame] = {}

    def _resolve(self):
        if self._fetcher is None:
            from . import live
            self._fetcher = live.fetch
        return self._fetcher

    def __call__(self, symbol: str, interval: str) -> pd.DataFrame | None:
        key = (symbol.upper(), interval)
        if key not in self._cache:
            try:
                frame, _entry = self._resolve()(
                    symbol, period=_fetch_period(interval), interval=interval)
            except Exception:                                    # noqa: BLE001
                return None
            self._cache[key] = frame.reset_index(drop=True)
        return self._cache[key].copy(deep=True)


@dataclasses.dataclass(frozen=True)
class ScoringRun:
    started_at: str
    finished_at: str
    scored: tuple[str, ...]          # forecast_ids newly scored
    symbols_attempted: tuple[str, ...]
    symbols_failed: tuple[str, ...]
    failure_detail: dict[str, str] = dataclasses.field(default_factory=dict)
    backup: str | None = None
    backup_anomaly: str | None = None

    @property
    def ok(self) -> bool:
        return not self.symbols_failed and self.backup_anomaly is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "scored_count": len(self.scored),
            "scored": list(self.scored),
            "symbols_attempted": list(self.symbols_attempted),
            "symbols_failed": list(self.symbols_failed),
            "failure_detail": dict(self.failure_detail),
            "backup": self.backup,
            "backup_anomaly": self.backup_anomaly,
            "ok": self.ok,
        }

    def summary(self) -> str:
        return (f"{len(self.scored)} outcome(s) scored across "
                f"{len(self.symbols_attempted)} symbol(s)")


def score(
    *,
    path: str | pathlib.Path | None = None,
    symbols: list[str] | None = None,
    fetcher: Callable[..., tuple[pd.DataFrame, Any]] | None = None,
    scored_at: dt.datetime | pd.Timestamp | None = None,
    backup: bool = True,
    backup_dir: str | pathlib.Path | None = None,
    state_path: str | pathlib.Path | None = None,
    log_dir: str | pathlib.Path | None = None,
) -> ScoringRun:
    """Score every matured, unscored forecast in the production ledger.

    One symbol failing never stops the run for the others — a stale-feed
    error, a delisting, or an AB-1 basis-integrity refusal on one symbol's
    history must not cost every other symbol its date. This mirrors
    `collector.collect`'s per-symbol isolation on the freeze side. A refused
    symbol's forecasts remain unscored and eligible on the next run; nothing
    about the refusal is worked around here.
    """
    from . import forecast_ledger, outcome_ledger

    started = dt.datetime.now(dt.timezone.utc)
    ledger_path = pathlib.Path(path) if path is not None else forecast_ledger.DEFAULT_PATH
    ledger = forecast_ledger.ForecastLedger(ledger_path)
    store = outcome_ledger.OutcomeStore(ledger_path)

    attempted = symbols if symbols is not None else sorted(
        {record.symbol for record in ledger.list()}
    )
    frames = _MemoisedFrames(fetcher)
    failed: list[str] = []
    detail: dict[str, str] = {}

    def bound_frames(symbol: str, interval: str) -> pd.DataFrame | None:
        frame = frames(symbol, interval)
        if frame is None and symbol not in failed:
            failed.append(symbol)
            detail.setdefault(symbol, "no realised price history available")
        return frame

    scored: list[outcome_ledger.OutcomeRecord] = []
    for symbol in attempted:
        try:
            scored.extend(outcome_ledger.score_matured(
                ledger, store, bound_frames, symbol=symbol, scored_at=scored_at))
        except Exception as error:                                # noqa: BLE001
            if symbol not in failed:
                failed.append(symbol)
            detail[symbol] = f"{type(error).__name__}: {error}"

    backup_name = backup_anomaly = None
    if backup and scored:
        from . import ledger_backup
        result = ledger_backup.backup_if_changed(
            source=ledger_path, backup_root=backup_dir, state_path=state_path,
            reason="scoring")
        backup_name = result.path.name if result.path else None
        if result.status == ledger_backup.FAILED:
            backup_anomaly = result.summary()

    run = ScoringRun(
        started_at=started.isoformat(),
        finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        scored=tuple(outcome.forecast_id for outcome in scored),
        symbols_attempted=tuple(attempted),
        symbols_failed=tuple(failed),
        failure_detail=dict(detail),
        backup=backup_name, backup_anomaly=backup_anomaly,
    )
    _write_log(run, log_dir)
    return run


def _write_log(run: ScoringRun, log_dir: str | pathlib.Path | None) -> pathlib.Path:
    directory = pathlib.Path(log_dir or DEFAULT_LOG_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = run.started_at.replace(":", "").replace("-", "")[:15]
    destination = directory / f"score_{stamp}Z.json"
    destination.write_text(json.dumps(run.as_dict(), indent=2), encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.score_outcomes",
        description="Score every matured, unscored forecast in the "
                     "production prospective ledger.",
    )
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="restrict to these symbols (testing only)")
    parser.add_argument("--ledger", default=None, help="ledger path")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the post-scoring backup")
    arguments = parser.parse_args(argv)

    run = score(path=arguments.ledger, symbols=arguments.symbols,
                backup=not arguments.no_backup)

    for forecast_id in run.scored:
        print(f"SCORED {forecast_id}")
    print("-" * 70)
    print(run.summary())
    if run.backup:
        print(f"backup: {run.backup}")
    if run.backup_anomaly:
        print(f"BACKUP ANOMALY: {run.backup_anomaly}", file=sys.stderr)
    for symbol in run.symbols_failed:
        reason = run.failure_detail.get(symbol, "unknown reason")
        print(f"FAILED {symbol}: {reason}", file=sys.stderr)

    return 0 if run.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
