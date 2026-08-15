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


def main(argv: list[str] | None = None) -> int:
    from streamlit.web import cli as streamlit_cli

    arguments = list(argv if argv is not None else sys.argv[1:])
    script = str(APP_DIR / "streamlit_app.py")

    # Recovery first: if the last run died before its shutdown backup, take one
    # now, before any forecast can be frozen on top of the unbacked state.
    ledger_lifecycle.start()
    # Then arrange for the normal path however this process ends.
    ledger_lifecycle.install()

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
