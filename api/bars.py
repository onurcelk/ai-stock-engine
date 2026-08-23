"""Phase 6e: the API's one data door.

Every endpoint that reads a price series goes through `resolve` here. Before
this there were two private `_bars` helpers -- one in `routers/jobs.py`, one in
`routers/strategies.py` -- that had drifted into being the same function, and
adding a third capability to each of them separately is how they would have
stopped agreeing about what "the window" means.

Three things a caller can ask for, and the reason each exists:

**A live symbol.** The default, and what every page used until now. `interval`
is passed through to `live.fetch` rather than fixed at daily: all five of
`live.INTERVALS` work, and the new frontend selector is the thing that finally
makes them reachable.

**A bundled dataset.** `dataset/*.csv`, loaded through `data.load`. The live
path's own failure message has always ended "switch to a bundled dataset to
keep working offline", and until now that advice pointed at a Streamlit
sidebar the API had no equivalent of -- so the recommendation was not
actionable outside the app it was written for. It is now.

**A date window.** `start`/`end` trim the frame after it is loaded, so a
backtest can be scored on 2021 alone. Deliberately a trim of a fetched series
rather than a fetch parameter: `period` decides what is downloaded and cached,
`start`/`end` decide what is *looked at*, and conflating them would re-download
on every slider move and cache a hundred overlapping ranges.

Nothing here writes. Reading bars never has, and this module is where that
stays true for every caller at once.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from fastapi import HTTPException

from core import data, live

DEFAULT_PERIOD = "5y"
DEFAULT_INTERVAL = "1d"

#: The fewest bars any caller here can do something honest with. Below this a
#: backtest has no trades to speak of and a study has not finished warming up,
#: so an empty-looking result would be reported as if it meant something.
MIN_BARS = 5


def _parse_day(value: str | None, field: str) -> dt.date | None:
    if value is None or not str(value).strip():
        return None
    try:
        return dt.date.fromisoformat(str(value).strip())
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"{field} must be an ISO date like 2021-03-01, not {value!r}.",
        ) from error


def trim(frame: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    """Restrict a frame to a closed date window. Either end may be omitted.

    Compared on calendar dates rather than timestamps so an intraday series
    behaves the way someone typing two dates expects: `end=2021-03-01` includes
    everything that traded that day, not just its midnight bar.
    """
    first, last = _parse_day(start, "start"), _parse_day(end, "end")
    if first and last and first > last:
        raise HTTPException(
            status_code=400,
            detail=f"start ({first}) is after end ({last}).",
        )
    if not first and not last:
        return frame

    days = frame["date"].dt.date
    mask = pd.Series(True, index=frame.index)
    if first:
        mask &= days >= first
    if last:
        mask &= days <= last
    return frame.loc[mask].reset_index(drop=True)


def resolve(
    symbol: str = "",
    *,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    dataset: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """The bars a request is about, and the label a saved run files them under.

    Raises `HTTPException(400)` for everything a caller can get wrong -- an
    unknown symbol, an unknown dataset, an impossible window -- because all of
    them are bad requests rather than failures of the thing being asked for.
    """
    if dataset:
        available = data.list_datasets()
        if dataset not in available:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown dataset {dataset!r}. Known: {', '.join(available)}.",
            )
        try:
            frame = data.load(dataset)
        except Exception as error:                                # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"Could not read {dataset}: {error}",
            ) from error
        # A bundled CSV is one fixed series; `period`/`interval` describe a
        # download and mean nothing here, so the label does not pretend they do.
        label = f"{dataset} · CSV"
    else:
        if not str(symbol).strip():
            raise HTTPException(status_code=400, detail="No symbol given.")
        try:
            frame, _ = live.fetch(symbol.strip().upper(), period=period,
                                  interval=interval)
        except Exception as error:                                # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(error)) from error
        label = f"{symbol.strip().upper()} · {interval}"

    if not len(frame):
        raise HTTPException(status_code=400, detail=f"No bars for {label}.")

    windowed = trim(frame, start, end)
    if len(windowed) < MIN_BARS:
        raise HTTPException(
            status_code=400,
            detail=(f"{label} has {len(windowed)} bars in that window; "
                    f"at least {MIN_BARS} are needed. Widen the dates."),
        )
    return windowed, label


def catalogue() -> dict:
    """What a caller may ask for: intervals, their valid periods, datasets.

    Served from `live.INTERVALS`, `live.periods_for` and `data.list_datasets`
    themselves. The per-interval period lists matter and are not decoration --
    Yahoo will not serve 5 years of hourly bars, so a selector offering it
    would produce a failure the user could not diagnose.
    """
    return {
        "intervals": [
            {"code": code, "name": name, "periods": live.periods_for(code),
             "intraday": code in live.INTRADAY}
            for name, code in live.INTERVALS.items()
        ],
        "default_interval": DEFAULT_INTERVAL,
        "default_period": DEFAULT_PERIOD,
        "datasets": data.list_datasets(),
        "quick_picks": list(live.QUICK_PICKS),
    }
