"""Family 1's candidate feature: time-series SUE from the filings door.

The simplest possible version of the information (roadmap §2.3, last row): one
number per (cutoff, symbol) — **standardized unexpected earnings**, measured
purely from the firm's own reported history as known at the cutoff:

    surprise_q = NI_q - NI_{q-4}                (seasonal difference)
    SUE_q      = surprise_q / std(last 8 surprises, min 4, ddof=1)

No consensus, no analyst data — the consensus-relative version is struck as
unobtainable free (`reports/INFORMATION_AUDIT.md` §3.1); this is the
own-history version that is fully computable from EDGAR.

Knowability is handled by *event replay*, not by row filtering: for each firm,
every acceptance event re-derives the quarterly series exactly as it was
believed at that moment (later vintages do not exist yet, restatements apply
only from their own acceptance), and the SUE computed from it is valid from
that acceptance until the next. A cutoff then reads the last event strictly
before its close. This is the same guarantee the door's `as_known` gives,
precomputed once per firm instead of once per cutoff.

Q4 is derived, not read: most filers report Q4 income only inside the 10-K's
annual figure, so Q4 = FY - (Q1+Q2+Q3), and it becomes knowable at the moment
the *last* of its four components is accepted — which is the 10-K's
acceptance. The derived row carries that timestamp.

`app/tests/test_alpha_filings_features.py` pins all of it, including the
restatement-cannot-change-history property at the feature level.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import pandas as pd

QUARTER_DAYS = (70, 100)     # a duration in this closed range is one quarter
ANNUAL_DAYS = (330, 380)     # ... and in this one, a fiscal year
YOY_DAYS = (340, 385)        # gap between a quarter end and its year-ago peer
SUE_WINDOW = 8               # surprises in the std window
SUE_MIN = 4                  # minimum surprises before SUE is defined


def _duration_days(rows: pd.DataFrame) -> pd.Series:
    return (rows["end"] - rows["start"]).dt.days


def _latest_vintage(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per (start, end): the latest-accepted vintage. Ties break on accn."""
    rows = rows.sort_values(["accepted", "accn"], kind="mergesort")
    return rows.groupby(["start", "end"], dropna=False).tail(1)


def quarterly_as_known(rows: pd.DataFrame) -> pd.DataFrame:
    """The quarterly series a holder of `rows` believes in, Q4 derived.

    `rows` is every vintage of one firm's one concept known at some moment
    (the caller guarantees the truncation). Returns columns
    (end, value, accepted) sorted by end — `accepted` is when that quarter's
    value became knowable, which for a derived Q4 is the acceptance of its
    last component.
    """
    if rows.empty:
        return pd.DataFrame(columns=["end", "value", "accepted"])
    latest = _latest_vintage(rows)
    duration = _duration_days(latest)
    quarters = latest[duration.between(*QUARTER_DAYS)]
    annuals = latest[duration.between(*ANNUAL_DAYS)]

    out = quarters[["end", "value", "accepted"]]
    derived: list[dict] = []
    for annual in annuals.itertuples():
        # Containment by quarter END inside the fiscal year, with a week of
        # tolerance on the start: 52/53-week calendars and day-count quirks
        # put a quarter's start a few days off the year's, and demanding
        # exact nesting silently loses the Q4 of every such filer.
        inside = quarters[
            (quarters["start"] >= annual.start - pd.Timedelta(days=7))
            & (quarters["end"] <= annual.end)
            & (quarters["end"] > annual.start)]
        if len(inside) != 3:
            continue
        if inside["end"].max() >= annual.end:      # already have the last quarter
            continue
        derived.append(dict(
            end=annual.end,
            value=annual.value - inside["value"].sum(),
            accepted=max(annual.accepted, inside["accepted"].max()),
        ))
    if derived:
        out = pd.concat([out, pd.DataFrame(derived)], ignore_index=True)
    # A restated quarter can appear under a slightly shifted (start, end);
    # keep one value per end, preferring the latest-accepted belief.
    out = out.sort_values(["accepted"], kind="mergesort")
    out = out.groupby("end", dropna=False).tail(1)
    return out.sort_values("end").reset_index(drop=True)


def sue_from_series(series: pd.DataFrame) -> float:
    """SUE of the newest quarter in a `quarterly_as_known` result. NaN if undefined."""
    if len(series) < SUE_MIN + 1:
        return float("nan")
    ends = series["end"].to_numpy()
    values = series["value"].to_numpy(dtype=float)
    surprises = np.full(len(series), np.nan)
    for i in range(len(series)):
        gap_days = (ends[i] - ends) / np.timedelta64(1, "D")
        peers = np.nonzero((gap_days >= YOY_DAYS[0]) & (gap_days <= YOY_DAYS[1]))[0]
        if len(peers):
            surprises[i] = values[i] - values[peers[-1]]
    latest = surprises[-1]
    if not np.isfinite(latest):
        return float("nan")
    history = surprises[:-1]
    history = history[np.isfinite(history)][-SUE_WINDOW:]
    if len(history) < SUE_MIN:
        return float("nan")
    spread = history.std(ddof=1)
    if not np.isfinite(spread) or spread == 0.0:
        return float("nan")
    return float(latest / spread)


@dataclasses.dataclass(frozen=True)
class FirmEvents:
    """One firm's SUE history as a step function of acceptance time."""

    valid_from: np.ndarray      # naive ET datetimes, ascending
    sue: np.ndarray
    period_end: np.ndarray
    accepted: np.ndarray        # acceptance of the newest quarter at each step

    def as_of(self, edge: dt.datetime) -> tuple[float, pd.Timestamp | None]:
        """The (sue, newest-quarter acceptance) believed strictly before `edge`."""
        position = np.searchsorted(self.valid_from, np.datetime64(edge)) - 1
        if position < 0:
            return float("nan"), None
        return float(self.sue[position]), pd.Timestamp(self.accepted[position])


def replay(rows: pd.DataFrame) -> FirmEvents:
    """Replay one firm's acceptance events into a SUE step function.

    At each distinct acceptance time, the quarterly series is re-derived from
    exactly the vintages accepted so far — so a restatement re-shapes the
    series only from its own acceptance onward, and the past steps are frozen.
    """
    rows = rows.sort_values(["accepted", "accn"], kind="mergesort").reset_index(drop=True)
    events = rows["accepted"].unique()
    valid_from, sues, period_end, accepted = [], [], [], []
    for event in events:
        known = rows[rows["accepted"] <= event]
        series = quarterly_as_known(known)
        if series.empty:
            continue
        newest = series.iloc[-1]
        valid_from.append(event)
        sues.append(sue_from_series(series))
        period_end.append(newest["end"])
        accepted.append(newest["accepted"])
    return FirmEvents(
        np.array(valid_from, dtype="datetime64[ns]"),
        np.array(sues, dtype=float),
        np.array(period_end, dtype="datetime64[ns]"),
        np.array(accepted, dtype="datetime64[ns]"),
    )


def build_feature(facts: pd.DataFrame, concept: str,
                  cutoffs: pd.DatetimeIndex,
                  members: pd.DataFrame,
                  symbol_to_cik: dict[str, int]) -> pd.DataFrame:
    """The (cutoff, symbol) SUE panel for one concept.

    `facts` is the full FilingsBook table (every vintage — the replay does its
    own truncation); `members` has columns (cutoff, symbol) — the point-in-time
    universe. Output columns: sue, staleness_days (calendar days since the
    newest quarter's acceptance). Symbols with no CIK, no history, or an
    undefined SUE carry NaN — never a filled-in value.
    """
    from . import filings as filings_module

    concept_rows = facts[facts["concept"] == concept]
    events_by_cik: dict[int, FirmEvents] = {
        cik: replay(rows) for cik, rows in concept_rows.groupby("cik")}

    records: list[dict] = []
    for cutoff in cutoffs:
        edge = filings_module.close_of(cutoff)
        for symbol in members.loc[members["cutoff"] == cutoff, "symbol"]:
            cik = symbol_to_cik.get(symbol)
            events = events_by_cik.get(cik) if cik is not None else None
            if events is None:
                records.append(dict(cutoff=cutoff, symbol=symbol,
                                    sue=np.nan, staleness_days=np.nan))
                continue
            sue, accepted = events.as_of(edge)
            staleness = (np.nan if accepted is None
                         else (pd.Timestamp(cutoff) - accepted.normalize()).days)
            records.append(dict(cutoff=cutoff, symbol=symbol,
                                sue=sue, staleness_days=staleness))
    return (pd.DataFrame(records)
            .set_index(["cutoff", "symbol"])
            .sort_index())
