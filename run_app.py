"""Launch the Streamlit app with the ledger backup lifecycle attached.

    python run_app.py

Use this rather than `streamlit run app/streamlit_app.py` directly.  Both start
the same application; only this one backs the forecast ledger up when the
process ends, and recovers a missed backup when it starts.

**Why a launcher rather than a hook inside `streamlit_app.py`.**  Streamlit
re-executes that script top to bottom on every interaction, and its process
outlives the browser tab — closing the tab is a websocket disconnect, not a
shutdown.  There is no reliable "the app is closing" callback inside the script.
The process that owns the lifecycle is this one, so this is where `try/finally`,
`atexit` and the signal handlers belong.

It also keeps the test suite structurally safe: `app/tests/test_ui.py` boots
`streamlit_app.py` directly and therefore cannot reach any of this, so no test
can write to the backup drive by booting the app.
"""

from __future__ import annotations

import pathlib
import sys

APP_DIR = pathlib.Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(APP_DIR))

from core import ledger_lifecycle          # noqa: E402


def _collect_then_replay() -> None:
    """Freeze the current session, then recover missed ones. Never the reverse.

    Neither step may stop the app starting. A data outage should cost you a
    day's accumulation, not the ability to open the application, so both are
    reported and neither propagates.
    """
    from core import collector, replay

    try:
        symbols = collector.read_universe()
    except Exception as error:                                   # noqa: BLE001
        print(f"[startup] no collection universe: {error}", file=sys.stderr)
        return

    # Before anything is frozen: what did the record already cover? The
    # prospective freeze below advances every symbol's newest cutoff to today,
    # so asking afterwards would answer "nothing was missed" however long the
    # gap really was.
    covered_through = replay.snapshot_cutoffs(symbols)

    try:
        run = collector.collect(symbols=symbols)
        print(f"[startup] prospective: {run.summary()}")
        for failure in run.failures:
            print(f"[startup] prospective FAILED {failure.symbol}: "
                  f"{failure.detail}", file=sys.stderr)
    except Exception as error:                                   # noqa: BLE001
        print(f"[startup] prospective freeze failed: {error}", file=sys.stderr)
        # Deliberately still attempt replays: they write to a different store
        # and cannot corrupt the prospective record whatever happened above.

    try:
        replayed = replay.replay_missed(symbols, since_by_symbol=covered_through)
        print(f"[startup] replay: {replayed.summary()}")
        for failure in replayed.failures:
            print(f"[startup] replay FAILED {failure.symbol}: "
                  f"{failure.detail}", file=sys.stderr)
    except Exception as error:                                   # noqa: BLE001
        print(f"[startup] missed-session replay failed: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    from streamlit.web import cli as streamlit_cli

    arguments = list(argv if argv is not None else sys.argv[1:])
    script = str(APP_DIR / "streamlit_app.py")

    # Recovery first: if the last run died before its shutdown backup, take one
    # now, before any forecast can be frozen on top of the unbacked state.
    ledger_lifecycle.start()
    # Then arrange for the normal path however this process ends.
    ledger_lifecycle.install()

    # START -> CURRENT PROSPECTIVE FREEZE -> MISSED-DAY REPLAYS -> UI.
    #
    # The order is the whole point. Today's bar must be claimed by the genuine
    # prospective freeze before any reconstruction runs, so a replay can never
    # be the row that owns the current session. Replays then fill in sessions
    # that were missed — into a different database, as diagnostics.
    _collect_then_replay()

    try:
        sys.argv = ["streamlit", "run", script, *arguments]
        return int(streamlit_cli.main() or 0)
    except SystemExit as exit_request:          # Streamlit exits through this
        return int(exit_request.code or 0)
    finally:
        # Belt and braces alongside `atexit`: the fingerprint guard means a
        # second call after a successful one writes nothing.
        ledger_lifecycle.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
