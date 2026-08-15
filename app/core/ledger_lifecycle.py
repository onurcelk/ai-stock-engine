"""Start and shutdown hooks that keep the ledger backed up through real use.

The lifecycle is:

    APP START -> recovery backup if the last run did not get one
              -> normal use, the ledger may gain rows
              -> APP SHUTDOWN -> backup if changed

Two things make this harder than it sounds.

**Streamlit's process does not end when the browser tab closes.**  A tab close
is a websocket disconnect; the server keeps running.  So "shutdown" has to mean
the *process* ending, which is why the hooks live in a launcher that owns the
process rather than in `streamlit_app.py`, and why they are installed against
`atexit`, `SIGINT` and `SIGTERM` rather than any Streamlit callback.

**Shutdown callbacks are not guaranteed.**  A kill, a power cut, or a crash
skips every one of them.  `start` exists for exactly that case: it compares the
ledger against the last recorded successful backup and takes a recovery
snapshot before any forecast activity begins.  Repeated starts with no ledger
change produce no files, because the comparison is on immutable content.

Neither hook raises.  A backup problem must never stop the application starting
or prevent it exiting.
"""

from __future__ import annotations

import atexit
import signal
import sys
from typing import Any, Callable

from . import ledger_backup


def _report(outcome: ledger_backup.BackupOutcome, stream: Any) -> None:
    prefix = "ledger backup"
    if outcome.status == ledger_backup.FAILED:
        print(f"[{prefix}] {outcome.summary()}", file=stream)
    elif outcome.created:
        print(f"[{prefix}] {outcome.summary()}", file=stream)


def start(
    *, stream: Any = None, **kwargs: Any,
) -> ledger_backup.BackupOutcome:
    """Recovery point: back up anything the previous run failed to.

    Runs before normal forecast activity.  If the last shutdown was clean the
    fingerprints match and this writes nothing, which is the common case and
    costs one digest over the ledger.
    """
    outcome = ledger_backup.backup_if_changed(reason="startup-recovery", **kwargs)
    _report(outcome, stream or sys.stderr)
    return outcome


def shutdown(
    *, stream: Any = None, **kwargs: Any,
) -> ledger_backup.BackupOutcome:
    """The normal path: one backup per session that actually changed anything."""
    outcome = ledger_backup.backup_if_changed(reason="shutdown", **kwargs)
    _report(outcome, stream or sys.stderr)
    return outcome


def install(
    *, stream: Any = None, register_signals: bool = True, **kwargs: Any,
) -> Callable[[], ledger_backup.BackupOutcome]:
    """Arrange for `shutdown` to run however this process ends.

    `atexit` covers a normal return and `sys.exit`.  `SIGINT` and `SIGTERM`
    cover Ctrl-C and a polite kill, and both re-raise the default behaviour
    afterwards so the process still dies when asked — a handler that swallowed
    the signal would turn a backup convenience into an application that cannot
    be stopped.

    Idempotent: the backup itself is guarded by the fingerprint, so running on
    both a signal and `atexit` produces one file, not two.
    """
    def _run() -> ledger_backup.BackupOutcome:
        return shutdown(stream=stream, **kwargs)

    atexit.register(_run)

    if register_signals:
        for name in ("SIGINT", "SIGTERM"):
            number = getattr(signal, name, None)
            if number is None:
                continue
            previous = signal.getsignal(number)

            def handler(signum, frame, _previous=previous):
                _run()
                if callable(_previous) and _previous not in (
                        signal.SIG_IGN, signal.SIG_DFL):
                    return _previous(signum, frame)
                # Restore the default and re-raise, so the process still exits
                # with the signal it was sent.
                signal.signal(signum, signal.SIG_DFL)
                return signal.raise_signal(signum)

            try:
                signal.signal(number, handler)
            except (ValueError, OSError):
                # Not the main thread, or a platform without this signal.
                # `atexit` still covers the normal exit path.
                continue

    return _run
