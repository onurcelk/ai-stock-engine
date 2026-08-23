"""What a desk launcher does before it opens a window.

Extracted from `run_app.py` at Phase 7 (the cutover), unchanged in behaviour.
It lived in the Streamlit launcher because that was the only launcher; now
there are two -- `run_desk.py` starts the API and the Next.js frontend, and
`run_app.py` starts the Streamlit fallback -- and a sequence this order-
sensitive must not exist twice.  Two copies of it would agree today and
disagree the first time either was touched, which is exactly the drift
`api/bars.py` was created to end on the request path.

**Why a launcher and not the application.**  The freeze below writes to the
append-only prospective ledger.  That is a deliberate act, so it belongs to the
process a person started, not to an HTTP server's boot: `uvicorn --reload`
restarts on every file save, and a server that froze 86 forecasts each time it
came up would fill the one record this programme cannot regenerate with rows
nobody chose.  Phase 6a moved the same hazard off `GET /api/signal`; this keeps
it off the API's startup too.

The backup lifecycle is the opposite case and lives in both places: it never
writes to the ledger, never raises, and the thing it protects is lost if the
process that could have changed the ledger exits without it.
"""

from __future__ import annotations

import sys
from typing import Any


def collect_then_replay(*, stream: Any = None) -> None:
    """Freeze the current session, then recover missed ones. Never the reverse.

    Neither step may stop the app starting. A data outage should cost you a
    day's accumulation, not the ability to open the application, so both are
    reported and neither propagates.
    """
    errors = stream or sys.stderr
    from . import collector, replay

    try:
        symbols = collector.read_universe()
    except Exception as error:                                   # noqa: BLE001
        print(f"[startup] no collection universe: {error}", file=errors)
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
                  f"{failure.detail}", file=errors)
    except Exception as error:                                   # noqa: BLE001
        print(f"[startup] prospective freeze failed: {error}", file=errors)
        # Deliberately still attempt replays: they write to a different store
        # and cannot corrupt the prospective record whatever happened above.

    try:
        replayed = replay.replay_missed(symbols, since_by_symbol=covered_through)
        print(f"[startup] replay: {replayed.summary()}")
        for failure in replayed.failures:
            print(f"[startup] replay FAILED {failure.symbol}: "
                  f"{failure.detail}", file=errors)
    except Exception as error:                                   # noqa: BLE001
        print(f"[startup] missed-session replay failed: {error}", file=errors)
