"""SUE, as two columns on a price frame.

`indicators.py`'s sources are pure functions of a frame — no network, no
state, no symbol identity. Post-earnings drift needs all three: it is a claim
about *this firm* in the weeks after *its* filing was accepted, and none of
that is recoverable from a column of closes.

So this module does not add a source. It adds the **columns a source can
read**, and the source (`indicators._pead_drift`) stays a pure function of a
frame exactly like the other twelve. A frame carrying `sue` and
`days_since_filing` gets a drift reading; a frame without them gets zeros,
which is the same "no opinion" a close-only frame already gets from the
volume sources. No contract is bent to fit this in.

Point-in-time, by the same mechanism `alpha/filings_features.py` established
and `app/tests/test_alpha_filings_features.py` pins: each firm's acceptance
events are replayed into a step function of *believed* SUE, and bar `t` reads
the step in force strictly before `t`'s 16:00 ET close. A restatement accepted
next March cannot reach back into this January's bar, because the step it
creates begins at its own acceptance.

**The cache is not tracked, and that is visible rather than silent.**
`alpha/edgar/facts.parquet` is gitignored — a local rebuild from EDGAR, not
repository content. A machine without it produces frames with no `sue` column
and a permanently silent drift source, while carrying the *identical*
`technical_sources` version string as a machine that has it. That is exactly
the "two engines wearing one version string" failure `tournament.py`'s
docstring warns about, and the thing that closes it is the ledger:
`forecast_ledger.fingerprint_frame` digests the frame's **columns and rows**,
so a forecast made without the cache carries a different input fingerprint
from one made with it. The distinction lands in the record, which is where it
has to land.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib

import numpy as np
import pandas as pd

#: The concept PEAD-1 measured (`alpha/pead1_power_gate.py::CONCEPT`), reused
#: verbatim. Choosing a different one here would be retuning a rejected arm's
#: free parameter, which §3.2 of CLAUDE.md forbids.
CONCEPT = "NetIncomeLoss"

EDGAR_DIR = pathlib.Path(__file__).resolve().parents[2] / "alpha" / "edgar"

SUE_COLUMN = "sue"
AGE_COLUMN = "days_since_filing"


def available() -> bool:
    """Whether the filings cache is on this machine at all."""
    return (EDGAR_DIR / "facts.parquet").exists() and \
           (EDGAR_DIR / "filings_meta.json").exists()


@functools.lru_cache(maxsize=1)
def _symbol_to_cik() -> dict[str, int]:
    meta = json.loads((EDGAR_DIR / "filings_meta.json").read_text())
    return {str(k).upper(): int(v) for k, v in meta["symbol_to_cik"].items()}


@functools.lru_cache(maxsize=1)
def _concept_facts() -> pd.DataFrame:
    """Every vintage of `CONCEPT`, for every filer in the cache.

    Read once. The replay below does its own truncation, so this is the whole
    table on purpose — filtering it by date here would be the leak.
    """
    facts = pd.read_parquet(EDGAR_DIR / "facts.parquet")
    return facts[facts["concept"] == CONCEPT]


@functools.lru_cache(maxsize=256)
def _events(symbol: str):
    """One firm's SUE step function, or None if it has no history here."""
    from alpha import filings_features

    cik = _symbol_to_cik().get(symbol.strip().upper())
    if cik is None:
        return None
    rows = _concept_facts()
    rows = rows[rows["cik"] == cik]
    if rows.empty:
        return None
    events = filings_features.replay(rows)
    return events if len(events.valid_from) else None


def attach(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """`frame` plus `sue` and `days_since_filing`, or `frame` unchanged.

    Unchanged is the honest outcome whenever the answer is unknown — no cache,
    no CIK, no filing history, an index with no usable dates. A column of NaN
    would say "we looked and there is nothing", which is a different and
    stronger claim than "we could not look".
    """
    if not symbol or "date" not in frame.columns or not available():
        return frame

    try:
        events = _events(symbol)
    except Exception:                                           # noqa: BLE001
        # A malformed or half-written cache must not take the engine down; it
        # takes one source's opinion away, which the calibrator already knows
        # how to read.
        return frame
    if events is None:
        return frame

    stamps = pd.to_datetime(frame["date"], errors="coerce")
    if stamps.isna().all():
        return frame

    # Each bar reads the step in force strictly before its own 16:00 ET close.
    # searchsorted over the whole column rather than a call per bar: same
    # answer as `FirmEvents.as_of`, which the tests check directly.
    closes = (stamps.dt.normalize()
              + pd.Timedelta(hours=16)).to_numpy(dtype="datetime64[ns]")
    position = np.searchsorted(events.valid_from, closes, side="left") - 1

    sue = np.where(position >= 0, events.sue[position.clip(min=0)], np.nan)
    accepted = np.where(position >= 0,
                        events.accepted[position.clip(min=0)],
                        np.datetime64("NaT"))
    age = (closes - accepted.astype("datetime64[ns]")) / np.timedelta64(1, "D")

    out = frame.copy()
    out[SUE_COLUMN] = sue
    out[AGE_COLUMN] = np.where(np.isfinite(age), age, np.nan)
    return out
