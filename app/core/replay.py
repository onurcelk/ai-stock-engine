"""Reconstructing sessions the collector missed — as diagnostics, never evidence.

Accumulation depends on someone opening the app or running the collector, so
days get missed.  This module recovers what the engine *would* have said on
those days, and stores it where it can never be mistaken for what the engine
*did* say at the time.

**Why a replay is not evidence, at the level that matters.**  It is tempting to
think a faithful point-in-time reconstruction is as good as the real thing.  It
is not, and the reason is not sloppiness in the reconstruction.  AB-1 §2
established that a prospective forecast escapes three retrospection artefacts
precisely because the cutoff *is* the present: no corporate action has happened
yet to back-adjust its price history, the watchlist is the live one, and the
intraday depth is production depth.  A replay walks back into all three.  Its
prices are adjusted for splits and dividends that post-date the session, its
universe is the one someone watches today, and its bar depth is whatever
survives now.

There is a fourth, and it is the worst: **the person running the replay already
knows what the market did.**  Nothing in the code prevents a missed day being
replayed, inspected, and replayed again with a different universe.  That is
harmless for diagnostics and fatal for a promotion gate, which is why the
separation here is a different database file rather than a column.

What is guaranteed is narrower and still worth having: the engine sees no bar
after the session it is reconstructing.  That makes a replay a valid *diagnostic*
— it can tell you the engine ran, what it said, and how that compares — without
being a draw.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import pathlib
from typing import Any

import pandas as pd

from . import forecast_ledger


#: How far back missed sessions are recovered.  Not a research parameter: a
#: bound on work at startup, and a statement that a replay's usefulness as a
#: diagnostic decays as the reconstruction drifts further from what the day
#: actually looked like.
DEFAULT_LOOKBACK_SESSIONS = 10


@dataclasses.dataclass(frozen=True)
class ReplayResult:
    symbol: str
    status: str            # replayed | nothing_missed | skipped | error
    sessions: tuple[str, ...] = ()
    records: int = 0
    detail: str | None = None

    @property
    def is_failure(self) -> bool:
        return self.status == "error"


@dataclasses.dataclass(frozen=True)
class ReplayRun:
    started_at: str
    finished_at: str
    results: tuple[ReplayResult, ...]
    replayed_records: int

    @property
    def failures(self) -> tuple[ReplayResult, ...]:
        return tuple(r for r in self.results if r.is_failure)

    def summary(self) -> str:
        sessions = {s for r in self.results for s in r.sessions}
        return (f"{self.replayed_records} replay record(s) across "
                f"{len(sessions)} missed session(s)")


def missed_sessions(
    frame: pd.DataFrame,
    *,
    since: pd.Timestamp | None,
    now: pd.Timestamp,
    lookback: int = DEFAULT_LOOKBACK_SESSIONS,
) -> list[pd.Timestamp]:
    """Completed sessions between the last frozen cutoff and the current one.

    Trading days are read from the bars themselves rather than from a market
    calendar: a bar exists exactly when the market traded, which is the same
    question a calendar answers and is never wrong about holidays.

    The most recent bar is excluded.  It belongs to the *current* prospective
    freeze, which runs first and must own it — replaying it would produce a
    duplicate of today's genuine forecast with a worse provenance.
    """
    if frame.empty or "date" not in frame:
        return []
    dates = pd.to_datetime(frame["date"], errors="raise", utc=True)
    completed = sorted(set(dates))[:-1]        # never the newest bar
    if since is not None:
        completed = [d for d in completed if d > pd.Timestamp(since)]
    completed = [d for d in completed if d < pd.Timestamp(now)]
    return completed[-lookback:] if lookback else completed


def _truncating_fetcher(source, cutoff: pd.Timestamp):
    """Hand the engine history that stops at the session being reconstructed.

    This is the no-look-ahead guarantee for a replay, and it is enforced twice:
    here by construction, and again by `fingerprint_frame(cutoff_at=...)`, which
    raises if a single bar past the cutoff survives.
    """
    def fetch(symbol: str, *, period: str, interval: str, force: bool = False):
        frame, entry = source(symbol, period=period, interval=interval, force=force)
        dates = pd.to_datetime(frame["date"], errors="raise", utc=True)
        truncated = frame.loc[(dates <= cutoff).to_numpy()].reset_index(drop=True)
        return truncated, entry
    return fetch


def replay_symbol(
    symbol: str,
    sessions: list[pd.Timestamp],
    *,
    ledger: forecast_ledger.ReplayLedger,
    fetcher=None,
    now: dt.datetime | pd.Timestamp | None = None,
    **engine: Any,
) -> ReplayResult:
    """Reconstruct one symbol across the sessions it missed."""
    from . import live

    source = fetcher or live.fetch
    reconstructed_at = forecast_ledger._utc_iso(
        now or dt.datetime.now(dt.timezone.utc))
    written, done = 0, []

    for session in sessions:
        stamp = forecast_ledger._utc_iso(session)
        try:
            _, records = forecast_ledger.generate_incumbent_records(
                symbol,
                fetcher=_truncating_fetcher(source, pd.Timestamp(session)),
                cutoff_at=session,
                # The truth, always: this was computed now, not on the session
                # it describes. `assert_replay` refuses anything else.
                generated_at=reconstructed_at,
                record_class=forecast_ledger.RETROSPECTIVE_REPLAY,
                replay={"reconstructed_at": reconstructed_at, "session": stamp,
                        "reason": "missed session recovered at app start"},
                **engine,
            )
        except Exception as error:                              # noqa: BLE001
            return ReplayResult(symbol=symbol, status="error",
                                sessions=tuple(done), records=written,
                                detail=f"{type(error).__name__}: {error}")

        fresh = [r for r in records if not ledger.has_frozen_input(
            symbol=r.symbol, horizon=r.horizon,
            input_fingerprint=r.input_fingerprint)]
        forecast_ledger.assert_replay(fresh)
        ledger.insert_many(fresh)
        if fresh:
            written += len(fresh)
            done.append(stamp)

    if not written:
        return ReplayResult(symbol=symbol, status="nothing_missed")
    return ReplayResult(symbol=symbol, status="replayed",
                        sessions=tuple(done), records=written)


def last_prospective_cutoff(
    path: str | pathlib.Path | None = None, *, symbol: str | None = None,
) -> pd.Timestamp | None:
    """The newest cutoff already frozen prospectively, or None."""
    target = pathlib.Path(path or forecast_ledger.DEFAULT_PATH)
    if not target.exists():
        return None
    records = forecast_ledger.ForecastLedger(target).list(symbol=symbol)
    if not records:
        return None
    return max(pd.Timestamp(record.cutoff_at) for record in records)


def snapshot_cutoffs(
    symbols: list[str], *, path: str | pathlib.Path | None = None,
) -> dict[str, pd.Timestamp | None]:
    """Each symbol's newest prospective cutoff, read **before** collection.

    This must be taken before the current prospective freeze, and the reason is
    a bug this module had until it was caught: the freeze advances every
    symbol's newest cutoff to today, so a `missed_sessions` call made
    afterwards compares against today and finds that nothing was missed. A
    fortnight of gaps would silently produce no replays at all, and the failure
    would look exactly like success.
    """
    return {symbol: last_prospective_cutoff(path, symbol=symbol)
            for symbol in symbols}


def replay_missed(
    symbols: list[str],
    *,
    path: str | pathlib.Path | None = None,
    replay_path: str | pathlib.Path | None = None,
    fetcher=None,
    now: dt.datetime | pd.Timestamp | None = None,
    lookback: int = DEFAULT_LOOKBACK_SESSIONS,
    since_by_symbol: dict[str, pd.Timestamp | None] | None = None,
    **engine: Any,
) -> ReplayRun:
    """Recover every symbol's missed sessions into the replay ledger.

    Runs *after* the current prospective freeze, never before: today's bar
    belongs to the genuine record, and a replay must never be the thing that
    claims it.  `since_by_symbol` should therefore be a `snapshot_cutoffs`
    taken *before* that freeze — see the note there.
    """
    from . import live

    started = dt.datetime.now(dt.timezone.utc)
    moment = pd.Timestamp(now or dt.datetime.now(dt.timezone.utc))
    if moment.tzinfo is None:
        moment = moment.tz_localize("UTC")
    source = fetcher or live.fetch
    ledger = forecast_ledger.ReplayLedger(
        pathlib.Path(replay_path or forecast_ledger.DEFAULT_REPLAY_PATH))
    results: list[ReplayResult] = []
    total = 0

    for symbol in symbols:
        try:
            frame, _ = source(symbol, period="1y", interval="1d")
            since = (since_by_symbol.get(symbol) if since_by_symbol is not None
                     else last_prospective_cutoff(path, symbol=symbol))
            sessions = missed_sessions(
                frame, since=since, now=moment, lookback=lookback)
        except Exception as error:                              # noqa: BLE001
            results.append(ReplayResult(symbol=symbol, status="error",
                                        detail=f"{type(error).__name__}: {error}"))
            continue

        if not sessions:
            results.append(ReplayResult(symbol=symbol, status="nothing_missed"))
            continue

        result = replay_symbol(symbol, sessions, ledger=ledger, fetcher=source,
                               now=moment, **engine)
        results.append(result)
        total += result.records

    return ReplayRun(
        started_at=started.isoformat(),
        finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        results=tuple(results), replayed_records=total,
    )
