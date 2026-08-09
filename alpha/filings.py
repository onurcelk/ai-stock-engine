"""The V3 filings door. One way in, and it filters on *acceptance time*, not filing date.

Same contract as `alpha/pitdata.py`, restated for SEC filings: **nothing on the
prediction side may see a fact that was not accepted by EDGAR strictly before
the close of the cutoff session.** `app/tests/test_alpha_filings.py` proves the
guarantee the same way the price door's is proved — by rewriting the future and
demanding an identical view.

Why acceptance time and not `filed`: the Phase 2 audit measured that **51.8% of
10-K/10-Q filings are accepted after the 16:00 ET close of the very date they
are stamped with** (`reports/INFORMATION_AUDIT.md` §1, n=2,056). A door keyed
on `filed <= cutoff` therefore leaks in about half of all observations. The
rule enforced here, pinned by test:

    admissible at cutoff T  <=>  accepted (ET)  <  T 16:00 ET

A fact with no acceptance timestamp is **inadmissible, not approximated** —
roadmap §2.1: if you cannot say when a value became knowable, it does not
enter the panel. The ingest counts what it drops; the door never sees it.

Restatements: EDGAR keeps every vintage of a fact — the same (cik, concept,
period) appears once per accession that reported it (measured: 46 of 66
period-keys carry more than one vintage). The door keeps them all and
`FilingsView.as_known` resolves "what was believed at T": the latest vintage
*accepted before T's close*, never the latest vintage in existence.

There is no scorer side in this module at all. Outcomes are prices; the only
forward-reading method in the research codebase stays `PriceBook.forward_return`.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import functools
import pathlib

import pandas as pd

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
FACTS_PATH = EDGAR_DIR / "facts.parquet"

CLOSE_ET = dt.time(16, 0)   # the NYSE close the admissibility rule is anchored on

#: Columns every facts table must carry. `accepted` is a naive ET datetime.
COLUMNS = ("cik", "concept", "unit", "start", "end", "value",
           "accn", "form", "fy", "fp", "filed", "accepted")


def et_from_utc(stamp: str | dt.datetime) -> dt.datetime:
    """EDGAR `acceptanceDateTime` (UTC, Z-suffixed) -> naive US/Eastern datetime.

    The US DST rule, applied directly rather than via a tz database, so the
    conversion has no environment dependency: EDT (UTC-4) from the second
    Sunday of March to the first Sunday of November, EST (UTC-5) otherwise.
    Pinned for both regimes by `test_et_conversion_handles_both_dst_regimes`.
    """
    if isinstance(stamp, str):
        stamp = dt.datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")
    year = stamp.year
    march = dt.datetime(year, 3, 8)
    dst_start = march + dt.timedelta(days=(6 - march.weekday()) % 7)
    november = dt.datetime(year, 11, 1)
    dst_end = november + dt.timedelta(days=(6 - november.weekday()) % 7)
    offset = 4 if dst_start <= stamp < dst_end else 5
    return stamp - dt.timedelta(hours=offset)


def close_of(cutoff: pd.Timestamp) -> dt.datetime:
    """The 16:00 ET close of the cutoff session, as a naive ET datetime."""
    day = pd.Timestamp(cutoff).normalize()
    return dt.datetime.combine(day.date(), CLOSE_ET)


@dataclasses.dataclass(frozen=True)
class FilingsView:
    """Every fact knowable at the cutoff's close, and nothing else.

    `facts` is already truncated on `accepted < close_of(cutoff)`. A holder of
    a view cannot obtain a later-accepted fact from it by any route — the view
    keeps no reference to the book it came from.
    """

    cutoff: pd.Timestamp
    facts: pd.DataFrame

    def as_known(self, concept: str) -> pd.DataFrame:
        """What was believed about `concept` at the cutoff, one row per (cik, period).

        The latest vintage accepted before the cutoff's close wins; earlier
        vintages of the same period are superseded, later ones do not exist
        here by construction. Ties on `accepted` break on accession number so
        the result is deterministic.
        """
        rows = self.facts[self.facts["concept"] == concept]
        if rows.empty:
            return rows
        rows = rows.sort_values(["accepted", "accn"], kind="mergesort")
        return rows.groupby(["cik", "start", "end"], dropna=False).tail(1)

    def latest_period(self, concept: str) -> pd.DataFrame:
        """Per CIK: the most recently *ended* period known at the cutoff.

        This is the feature layer's staple — "the last reported quarter and
        when we learned about it". Carries `accepted` so staleness (sessions
        since acceptance) is computable without touching the book.
        """
        known = self.as_known(concept)
        if known.empty:
            return known
        known = known.sort_values(["end", "accepted"], kind="mergesort")
        return known.groupby("cik", dropna=False).tail(1)


class FilingsBook:
    """Every vintage of every ingested fact. Hand out views; never hand out this."""

    def __init__(self, facts: pd.DataFrame):
        missing = [c for c in COLUMNS if c not in facts.columns]
        if missing:
            raise ValueError(f"facts table is missing columns: {missing}")
        if facts["accepted"].isna().any():
            # The ingest is required to have dropped these already (§2.1:
            # inadmissible, not approximated). A NaT reaching the book is a
            # build bug, and failing closed here keeps it from becoming a leak.
            raise ValueError("facts with no acceptance timestamp reached the book")
        self._facts = facts.sort_values(
            ["accepted", "accn"], kind="mergesort").reset_index(drop=True)

    @property
    def concepts(self) -> list[str]:
        return sorted(self._facts["concept"].unique())

    @property
    def ciks(self) -> list[int]:
        return sorted(self._facts["cik"].unique())

    def view(self, cutoff: pd.Timestamp) -> FilingsView:
        """The prediction-side accessor. The acceptance filter lives here and only here."""
        edge = close_of(cutoff)
        knowable = self._facts[self._facts["accepted"] < edge]
        return FilingsView(pd.Timestamp(cutoff).normalize(),
                           knowable.reset_index(drop=True))


@functools.lru_cache(maxsize=1)
def load_book(path: str | None = None) -> FilingsBook:
    """Load the ingested facts table. Cached; the table is one object, like the panel."""
    source = pathlib.Path(path) if path else FACTS_PATH
    if not source.exists():
        raise RuntimeError(
            f"no facts table at {source} — run: python -m alpha.build_filings")
    return FilingsBook(pd.read_parquet(source))
