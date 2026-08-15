"""Local, usage-driven backup for the prospective forecast ledger.

`app/forecast_ledger.sqlite3` holds forecasts frozen before their outcomes
existed.  That is the whole source of their value and also why they cannot be
recreated: re-running the engine today produces a forecast made today, not the
one made last Tuesday.  A lost ledger is lost evidence at any price, and the
file is gitignored by Phase 1's design, so nothing else here protects it.

**Usage-driven, not scheduled.**  A backup happens when the application has
actually changed the ledger — at shutdown, or at the next start if the process
died before it could.  There is no timer, no daemon, no background sync and no
cloud service.  Opening the app and changing nothing produces no file.

Five properties this module is built around:

**The live ledger is never written.**  Snapshots use `sqlite3.Connection.backup`
from a read-only connection, which is consistent against a live writer and
leaves the source byte-identical.  Never a raw filesystem copy of an open
database: that can catch a torn write and produce a file that verifies as
SQLite but is missing the last transaction.

**Change is decided on immutable content, never on mtime.**  The fingerprint
digests forecast identities and their stored payload hashes.  A file touched
but unchanged does not qualify; a file whose rows changed always does.

**Nothing counts as a backup until it is verified.**  Snapshots are written to a
temporary name, `PRAGMA integrity_check`ed, hashed, and only then atomically
renamed into place.  A reader can never observe a half-written backup under a
real backup name.

**Restore is manual, always.**  Nothing here restores automatically.  The one
restore path refuses to discard forecasts the backup lacks unless explicitly
forced, because the realistic accident is not losing the file — it is putting
last month's copy over this month's.

**Retention never costs you the newest copy.**  Pruning is best-effort, bounded,
and structurally unable to remove the newest or the only valid backup.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
from typing import Any


#: The separate physical drive.  Deliberately not inside the repository and
#: deliberately not a cloud-synced folder: the failure this guards against is
#: losing the working copy, so a second copy on the same volume is worth less.
DEFAULT_BACKUP_ROOT = pathlib.Path(r"D:\prediction market backup")

#: What this machine believes it has already backed up.  Kept beside the ledger
#: rather than on the backup drive, so a disconnected drive is detected as
#: "backup missing" instead of silently losing the record of what was done.
DEFAULT_STATE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "ledger_backup_state.json")

MANIFEST_NAME = "backup_manifest.json"
FILENAME_FORMAT = "forecast_ledger_%Y-%m-%d_%H-%M-%S.sqlite3"
#: Temporary snapshots carry a prefix the backup glob cannot match, so an
#: interrupted run can never be counted as a backup or pruned as one.
TEMP_PREFIX = "_incomplete_"
BACKUP_GLOB = "forecast_ledger_*.sqlite3"

#: Snapshots kept.  Beyond this the oldest verified backup is removed.
RETENTION = 90

UNCHANGED = "UNCHANGED"
BACKED_UP = "BACKED_UP"
FAILED = "FAILED"

#: Set by the test suite. A hard stop on ever touching the real backup drive
#: from an automated run, independent of anyone remembering to pass a path.
DISABLE_ENV = "V5_LEDGER_BACKUP_DISABLED"


class LedgerBackupError(RuntimeError):
    """A backup could not be taken, or could not be trusted once taken."""


@dataclasses.dataclass(frozen=True)
class LedgerFingerprint:
    """Immutable state of a ledger, in the terms "has it changed" needs.

    Built from row identities and stored payload hashes — never from file size
    or modification time, both of which move without the contents changing and
    stay still when a row is rewritten in place.
    """

    forecast_rows: int
    outcome_rows: int
    symbols: int
    latest_forecast_id: str | None
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class BackupOutcome:
    status: str
    reason: str
    path: pathlib.Path | None = None
    sha256: str | None = None
    fingerprint: LedgerFingerprint | None = None
    integrity: str | None = None
    pruned: tuple[str, ...] = ()
    error: str | None = None

    @property
    def created(self) -> bool:
        return self.status == BACKED_UP

    def summary(self) -> str:
        if self.status == UNCHANGED:
            return "Ledger unchanged since the last verified backup; nothing written."
        if self.status == FAILED:
            return f"BACKUP FAILED ({self.reason}): {self.error}"
        rows = self.fingerprint.forecast_rows if self.fingerprint else "?"
        pruned = f", pruned {len(self.pruned)}" if self.pruned else ""
        return f"Backed up {rows} forecasts to {self.path.name}{pruned}."


# ----------------------------------------------------------------- reading


def _connect_readonly(path: pathlib.Path) -> sqlite3.Connection:
    """Open without creating.  `sqlite3.connect` on a missing path creates it."""
    if not path.exists():
        raise LedgerBackupError(f"no ledger at {path}")
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def ledger_fingerprint(path: str | pathlib.Path) -> LedgerFingerprint:
    """Digest a ledger's immutable contents without modifying it."""
    connection = _connect_readonly(pathlib.Path(path))
    try:
        tables = _tables(connection)
        if "forecasts" not in tables:
            raise LedgerBackupError(f"{path} has no forecasts table")
        forecasts = list(connection.execute(
            "SELECT forecast_id, payload_sha256 FROM forecasts ORDER BY forecast_id"))
        outcomes = list(connection.execute(
            "SELECT outcome_id, payload_sha256 FROM outcomes ORDER BY outcome_id"
        )) if "outcomes" in tables else []
        symbols = connection.execute(
            "SELECT COUNT(DISTINCT symbol) FROM forecasts").fetchone()[0]
        latest = connection.execute(
            "SELECT forecast_id FROM forecasts "
            "ORDER BY generated_at DESC, forecast_id DESC LIMIT 1").fetchone()
    finally:
        connection.close()

    digest = hashlib.sha256(json.dumps(
        {"forecasts": forecasts, "outcomes": outcomes}, sort_keys=True
    ).encode("utf-8")).hexdigest()
    return LedgerFingerprint(
        forecast_rows=len(forecasts), outcome_rows=len(outcomes),
        symbols=int(symbols),
        latest_forecast_id=(latest[0] if latest else None),
        digest=digest,
    )


def file_sha256(path: str | pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def integrity_check(path: str | pathlib.Path) -> str:
    connection = _connect_readonly(pathlib.Path(path))
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


# ------------------------------------------------------------------ state


def read_state(state_path: str | pathlib.Path | None = None) -> dict[str, Any] | None:
    path = pathlib.Path(state_path or DEFAULT_STATE_PATH)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A truncated state file means "we do not know", which must resolve to
        # taking a backup rather than skipping one.
        return None


def _write_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f"{TEMP_PREFIX}{path.name}.part"
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


# --------------------------------------------------------------- manifest


def manifest_path(backup_root: str | pathlib.Path | None = None) -> pathlib.Path:
    return pathlib.Path(backup_root or DEFAULT_BACKUP_ROOT) / MANIFEST_NAME


def read_manifest(backup_root: str | pathlib.Path | None = None) -> list[dict[str, Any]]:
    path = manifest_path(backup_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    entries = payload.get("backups", []) if isinstance(payload, dict) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def _write_manifest(backup_root: pathlib.Path, entries: list[dict[str, Any]]) -> None:
    _write_atomic(manifest_path(backup_root), {
        "manifest_version": 1,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "retention": RETENTION,
        "backups": entries,
    })


def list_backups(backup_root: str | pathlib.Path | None = None) -> list[pathlib.Path]:
    """Completed backups, oldest first.  Incomplete snapshots cannot match."""
    root = pathlib.Path(backup_root or DEFAULT_BACKUP_ROOT)
    if not root.exists():
        return []
    return sorted(p for p in root.glob(BACKUP_GLOB)
                  if not p.name.startswith(TEMP_PREFIX))


# -------------------------------------------------------------- retention


def apply_retention(
    backup_root: str | pathlib.Path | None = None, *, keep: int = RETENTION,
) -> list[str]:
    """Drop the oldest verified backups beyond `keep`.

    Bounded by three refusals that hold regardless of the manifest's state: the
    newest backup is never removed, the last remaining valid backup is never
    removed, and nothing outside the completed-backup glob is ever touched.
    Retention is a convenience; losing a backup to it would defeat the module.
    """
    root = pathlib.Path(backup_root or DEFAULT_BACKUP_ROOT)
    entries = read_manifest(root)
    by_name = {entry.get("filename"): entry for entry in entries}

    present = list_backups(root)
    valid = [p for p in present
             if by_name.get(p.name, {}).get("integrity") == "ok"]
    if len(valid) <= keep or len(valid) <= 1:
        return []

    removed: list[str] = []
    # Oldest first, and never the last element: `valid` is sorted by filename,
    # which sorts by timestamp, so `valid[-1]` is the newest.
    for candidate in valid[:-1]:
        if len(valid) - len(removed) <= keep:
            break
        try:
            candidate.unlink()
        except OSError:
            # A file we cannot delete is not a reason to fail the backup that
            # just succeeded. Leave it and its manifest entry alone.
            continue
        removed.append(candidate.name)

    if removed:
        _write_manifest(root, [entry for entry in entries
                               if entry.get("filename") not in removed])
    return removed


# ----------------------------------------------------------------- backup


def backup_if_changed(
    source: str | pathlib.Path | None = None,
    *,
    backup_root: str | pathlib.Path | None = None,
    state_path: str | pathlib.Path | None = None,
    reason: str = "shutdown",
    keep: int = RETENTION,
    now: dt.datetime | None = None,
) -> BackupOutcome:
    """Snapshot the ledger if, and only if, its contents have moved.

    Never raises.  This runs on the shutdown path of an application the user
    is closing and on the start path of one they are opening; an exception in
    either place would be a worse outcome than a missed backup, so failures
    come back as `FAILED` with the reason attached for the caller to display.
    """
    from .forecast_ledger import DEFAULT_PATH

    if os.environ.get(DISABLE_ENV):
        return BackupOutcome(status=UNCHANGED, reason="disabled",
                             error=f"{DISABLE_ENV} is set")

    source_path = pathlib.Path(source or DEFAULT_PATH)
    root = pathlib.Path(backup_root or DEFAULT_BACKUP_ROOT)
    state_file = pathlib.Path(state_path or DEFAULT_STATE_PATH)
    stamp = (now or dt.datetime.now(dt.timezone.utc))

    try:
        if not source_path.exists():
            return BackupOutcome(status=UNCHANGED, reason=reason,
                                 error="no ledger to back up")
        fingerprint = ledger_fingerprint(source_path)

        state = read_state(state_file)
        if state and state.get("fingerprint", {}).get("digest") == fingerprint.digest:
            # Known-good only if the file it names is still on the drive: a
            # disconnected or wiped backup volume must read as "not backed up".
            recorded = root / str(state.get("filename", ""))
            if recorded.exists():
                return BackupOutcome(status=UNCHANGED, reason=reason,
                                     fingerprint=fingerprint)

        if not root.exists():
            return BackupOutcome(
                status=FAILED, reason=reason, fingerprint=fingerprint,
                error=f"backup drive is not available: {root}")

        temporary = root / f"{TEMP_PREFIX}{stamp.strftime(FILENAME_FORMAT)}.part"
        final = root / stamp.strftime(FILENAME_FORMAT)
        suffix = 1
        while final.exists():
            suffix += 1
            final = root / (stamp.strftime(FILENAME_FORMAT).replace(
                ".sqlite3", f"_{suffix}.sqlite3"))

        origin = _connect_readonly(source_path)
        try:
            destination = sqlite3.connect(temporary)
            try:
                with destination:
                    origin.backup(destination)
            finally:
                destination.close()
        finally:
            origin.close()

        verdict = integrity_check(temporary)
        if verdict != "ok":
            temporary.unlink(missing_ok=True)
            return BackupOutcome(status=FAILED, reason=reason,
                                 fingerprint=fingerprint, integrity=verdict,
                                 error=f"integrity_check returned {verdict!r}")

        copied = ledger_fingerprint(temporary)
        if copied.digest != fingerprint.digest:
            temporary.unlink(missing_ok=True)
            return BackupOutcome(status=FAILED, reason=reason,
                                 fingerprint=fingerprint,
                                 error="snapshot contents do not match the source")

        digest = file_sha256(temporary)
        # Atomic: a reader never observes a partial file under a real name.
        os.replace(temporary, final)
    except (LedgerBackupError, sqlite3.Error, OSError) as error:
        return BackupOutcome(status=FAILED, reason=reason,
                             error=f"{type(error).__name__}: {error}")

    entry = {
        "filename": final.name,
        "timestamp": stamp.isoformat(),
        "reason": reason,
        "forecast_rows": fingerprint.forecast_rows,
        "outcome_rows": fingerprint.outcome_rows,
        "symbols": fingerprint.symbols,
        "fingerprint": fingerprint.digest,
        "latest_forecast_id": fingerprint.latest_forecast_id,
        "sha256": digest,
        "integrity": "ok",
    }
    _write_manifest(root, read_manifest(root) + [entry])
    _write_atomic(state_file, {
        "state_version": 1,
        "filename": final.name,
        "backed_up_at": stamp.isoformat(),
        "sha256": digest,
        "fingerprint": fingerprint.as_dict(),
    })

    pruned: list[str] = []
    try:
        pruned = apply_retention(root, keep=keep)
    except OSError as error:                                     # noqa: BLE001
        # Retention is best-effort by design. A valid new backup already exists
        # and must survive any failure to tidy older ones.
        return BackupOutcome(status=BACKED_UP, reason=reason, path=final,
                             sha256=digest, fingerprint=fingerprint,
                             integrity="ok", error=f"retention skipped: {error}")

    return BackupOutcome(status=BACKED_UP, reason=reason, path=final,
                         sha256=digest, fingerprint=fingerprint,
                         integrity="ok", pruned=tuple(pruned))


def verify_backup(
    backup: str | pathlib.Path,
    backup_root: str | pathlib.Path | None = None,
) -> bool:
    """Re-check a stored backup against its manifest entry.

    Answers the only question that matters about an old backup: would it still
    restore what it claims to?  A manifest alone proves nothing.
    """
    path = pathlib.Path(backup)
    root = pathlib.Path(backup_root or path.parent)
    entry = next((e for e in read_manifest(root)
                  if e.get("filename") == path.name), None)
    if entry is None:
        raise LedgerBackupError(f"no manifest entry for {path.name}")
    if not path.exists():
        raise LedgerBackupError(f"backup file is missing: {path}")
    if file_sha256(path) != entry.get("sha256"):
        return False
    if integrity_check(path) != "ok":
        return False
    return ledger_fingerprint(path).digest == entry.get("fingerprint")


def restore(
    backup: str | pathlib.Path,
    target: str | pathlib.Path | None = None,
    *,
    force: bool = False,
    now: dt.datetime | None = None,
) -> pathlib.Path:
    """Put a verified backup back.  **Manual only — never called automatically.**

    Refuses to overwrite a ledger holding forecasts the backup lacks, because
    those are prospective records that cannot be regenerated at any price.
    `force` exists for a ledger known to be corrupt, and even then the file
    being replaced is copied aside first.
    """
    from .forecast_ledger import DEFAULT_PATH

    source = pathlib.Path(backup)
    if not verify_backup(source):
        raise LedgerBackupError(f"refusing to restore an unverified backup: {source}")

    destination = pathlib.Path(target or DEFAULT_PATH)
    if destination.exists():
        current = ledger_fingerprint(destination)
        incoming = ledger_fingerprint(source)
        if current.forecast_rows > incoming.forecast_rows and not force:
            raise LedgerBackupError(
                f"refusing to restore: {destination} holds "
                f"{current.forecast_rows} forecast rows and the backup holds "
                f"{incoming.forecast_rows}. Restoring would discard "
                f"{current.forecast_rows - incoming.forecast_rows} prospective "
                f"forecast(s) that cannot be regenerated. Pass force=True only "
                f"if the current ledger is known to be corrupt."
            )
        stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime(
            "%Y-%m-%d_%H-%M-%S")
        shutil.copy2(destination,
                     destination.parent / f"{destination.name}.superseded_{stamp}")

    shutil.copy2(source, destination)
    return destination
