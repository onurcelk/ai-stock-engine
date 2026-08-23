"""Launch the **Streamlit fallback** with the ledger backup lifecycle attached.

    python run_app.py

**Since Phase 7 (the cutover, 2026-08-23) this is not the desk.**  The product
is the FastAPI service plus the Next.js frontend, started by `run_desk.py`.
`app/streamlit_app.py` is retained as an internal fallback and as the parity
reference the rebuild was checked against, so this launcher is retained with
it -- it is the only way to boot that app with the ledger lifecycle attached,
and booting it without one is how a session's forecasts go unbacked.

Nothing here is deprecated in the sense of "about to be deleted": the four
capabilities that were retired at the cutover are listed in
`reports/NEXT_STEPS_ROADMAP.md` and stay retired, but the tab-for-tab app
itself still runs and `app/tests/test_ui.py` still drives it headlessly.

Use this rather than `streamlit run app/streamlit_app.py` directly.  Both start
the same application; only this one backs the forecast ledger up when the
process ends, and recovers a missed backup when it starts.

**Why a launcher rather than a hook inside `streamlit_app.py`.**  Streamlit
re-executes that script top to bottom on every interaction, and its process
outlives the browser tab — closing the tab is a websocket disconnect, not a
shutdown.  There is no reliable "the app is closing" callback inside the script.
The process that owns the lifecycle is this one, so this is where `try/finally`,
`atexit` and the signal handlers belong.  (The API does not have that problem:
`run_desk.py` and `api/main.py`'s own lifespan both hold the same hooks.)

It also keeps the test suite structurally safe: `app/tests/test_ui.py` boots
`streamlit_app.py` directly and therefore cannot reach any of this, so no test
can write to the backup drive by booting the app.
"""

from __future__ import annotations

import pathlib
import sys

APP_DIR = pathlib.Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(APP_DIR))

from core import ledger_lifecycle, startup          # noqa: E402


def main(argv: list[str] | None = None) -> int:
    from streamlit.web import cli as streamlit_cli

    arguments = list(argv if argv is not None else sys.argv[1:])
    script = str(APP_DIR / "streamlit_app.py")

    print("[startup] Streamlit fallback. The desk is `python run_desk.py`.",
          file=sys.stderr)

    # Recovery first: if the last run died before its shutdown backup, take one
    # now, before any forecast can be frozen on top of the unbacked state.
    ledger_lifecycle.start()
    # Then arrange for the normal path however this process ends.
    ledger_lifecycle.install()

    # START -> CURRENT PROSPECTIVE FREEZE -> MISSED-DAY REPLAYS -> UI.
    #
    # The order is the whole point, and it is asserted against
    # `core/startup.py` by `test_replay.py::test_the_launcher_snapshots_before
    # _it_collects`. Today's bar must be claimed by the genuine prospective
    # freeze before any reconstruction runs, so a replay can never be the row
    # that owns the current session.
    startup.collect_then_replay()

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
