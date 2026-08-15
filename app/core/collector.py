"""Headless prospective collection: accumulate without anyone opening the app.

Until now the ledger gained a row only when somebody read a live ticker in
Streamlit.  That makes the sampling schedule a function of when the owner
happened to be curious, which is not a schedule at all — and a week nobody
opens the app is a week with no new dates, on a programme whose only binding
constraint is dates.

This module is **not a second forecasting path**.  It calls
`ledger_activation.evaluate_and_freeze`, the same function `streamlit_app`
calls, and therefore inherits every guarantee already in place: incumbent only,
AB-1 basis probes, `assert_prospective`, input-fingerprint idempotency, and no
route to `evaluate_offline`.  If this file ever grows its own notion of what a
forecast is, that is a defect.

What it adds is *when* and *over what*, plus a run log and an exit code.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
import sys
from typing import Any


#: The collection universe, declared in a file rather than discovered from
#: whatever happens to be cached.  A universe that drifts with the cache is
#: not auditable: a symbol could enter or leave the record without anyone
#: choosing it, and later panels could not say what was watched when.  Changes
#: to this file are visible in git, which is the point.
UNIVERSE_FILE = pathlib.Path(__file__).resolve().parents[1] / "collection_universe.txt"

#: Run logs, one JSON file per run, beside the ledger and gitignored with it.
DEFAULT_LOG_DIR = pathlib.Path(__file__).resolve().parents[1] / "collection_logs"


class CollectionError(RuntimeError):
    """The run could not be completed as declared."""


@dataclasses.dataclass(frozen=True)
class SymbolResult:
    symbol: str
    status: str            # frozen | nothing_new | refused | excluded | error
    horizons: tuple[str, ...] = ()
    detail: str | None = None

    @property
    def is_failure(self) -> bool:
        return self.status in {"refused", "error"}


@dataclasses.dataclass(frozen=True)
class CollectionRun:
    started_at: str
    finished_at: str
    results: tuple[SymbolResult, ...]
    frozen_records: int
    backup: str | None = None
    backup_anomaly: str | None = None

    @property
    def failures(self) -> tuple[SymbolResult, ...]:
        return tuple(r for r in self.results if r.is_failure)

    @property
    def ok(self) -> bool:
        return not self.failures and self.backup_anomaly is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "frozen_records": self.frozen_records,
            "backup": self.backup,
            "backup_anomaly": self.backup_anomaly,
            "ok": self.ok,
            "results": [dataclasses.asdict(r) for r in self.results],
        }

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        parts = ", ".join(f"{status}={n}" for status, n in sorted(counts.items()))
        return f"{self.frozen_records} record(s) frozen; {parts}"


def read_universe(path: str | pathlib.Path | None = None) -> list[str]:
    """Symbols to collect, one per line; `#` comments and blanks ignored."""
    source = pathlib.Path(path or UNIVERSE_FILE)
    if not source.exists():
        raise CollectionError(f"no collection universe at {source}")
    symbols = []
    for line in source.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            symbols.append(entry.upper())
    if not symbols:
        raise CollectionError(f"collection universe at {source} is empty")
    return sorted(dict.fromkeys(symbols))


def collect(
    symbols: list[str] | None = None,
    *,
    path: str | pathlib.Path | None = None,
    universe_file: str | pathlib.Path | None = None,
    backup: bool = True,
    backup_dir: str | pathlib.Path | None = None,
    state_path: str | pathlib.Path | None = None,
    log_dir: str | pathlib.Path | None = None,
    **freeze_kwargs: Any,
) -> CollectionRun:
    """Freeze the incumbent forecast for every symbol in the universe.

    One symbol failing never stops the run: a delisted ticker or a network
    blip must not cost the other twenty-nine their date.  Every failure is
    recorded, surfaced in the summary, and reflected in the exit code.
    """
    from . import ledger_activation

    started = dt.datetime.now(dt.timezone.utc)
    names = symbols if symbols is not None else read_universe(universe_file)
    results: list[SymbolResult] = []
    frozen_records = 0

    for symbol in names:
        try:
            _, report = ledger_activation.evaluate_and_freeze(
                symbol, path=path, **freeze_kwargs
            )
        except Exception as error:                              # noqa: BLE001
            # The engine itself failed for this symbol. Recorded, never
            # swallowed: `is_failure` puts it in the exit code.
            results.append(SymbolResult(
                symbol=symbol, status="error",
                detail=f"{type(error).__name__}: {error}"))
            continue

        if report.failed:
            results.append(SymbolResult(
                symbol=symbol, status="refused", detail=report.error))
        elif report.excluded:
            results.append(SymbolResult(
                symbol=symbol, status="excluded", detail=report.excluded))
        elif report.wrote_anything:
            frozen_records += len(report.frozen_ids)
            results.append(SymbolResult(
                symbol=symbol, status="frozen",
                horizons=tuple(report.frozen_horizons)))
        else:
            results.append(SymbolResult(
                symbol=symbol, status="nothing_new",
                horizons=tuple(report.skipped_horizons)))

    backup_name = backup_anomaly = None
    if backup and frozen_records:
        # Only after something was written. `backup_if_changed` decides on the
        # ledger's immutable fingerprint, so a run that froze nothing but was
        # asked to back up still writes no file.
        from . import ledger_backup
        result = ledger_backup.backup_if_changed(
            source=path, backup_root=backup_dir, state_path=state_path,
            reason="collection")
        backup_name = result.path.name if result.path else None
        if result.status == ledger_backup.FAILED:
            backup_anomaly = result.summary()

    run = CollectionRun(
        started_at=started.isoformat(),
        finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        results=tuple(results), frozen_records=frozen_records,
        backup=backup_name, backup_anomaly=backup_anomaly,
    )
    _write_log(run, log_dir)
    return run


def _write_log(run: CollectionRun, log_dir: str | pathlib.Path | None) -> pathlib.Path:
    directory = pathlib.Path(log_dir or DEFAULT_LOG_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = run.started_at.replace(":", "").replace("-", "")[:15]
    destination = directory / f"collection_{stamp}Z.json"
    destination.write_text(json.dumps(run.as_dict(), indent=2), encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.collector",
        description="Freeze one prospective incumbent forecast per symbol.",
    )
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="override the declared universe (testing only)")
    parser.add_argument("--ledger", default=None, help="ledger path")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the post-collection backup")
    arguments = parser.parse_args(argv)

    run = collect(symbols=arguments.symbols, path=arguments.ledger,
                  backup=not arguments.no_backup)

    for result in run.results:
        if result.status == "frozen":
            print(f"{result.symbol:10s} FROZE       {', '.join(result.horizons)}")
        elif result.status == "nothing_new":
            print(f"{result.symbol:10s} nothing new")
        else:
            print(f"{result.symbol:10s} {result.status.upper():11s} "
                  f"{(result.detail or '')[:100]}")

    print("-" * 70)
    print(run.summary())
    if run.backup:
        print(f"backup: {run.backup}")
    if run.backup_anomaly:
        print(f"BACKUP ANOMALY: {run.backup_anomaly}", file=sys.stderr)
    for failure in run.failures:
        print(f"FAILED {failure.symbol}: {failure.detail}", file=sys.stderr)

    return 0 if run.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
