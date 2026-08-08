"""Point-in-time S&P 500 membership, reconstructed from the index change log.

Directive §1 and §2 both turn on the same question: *what did the universe look
like on the cutoff date, not today?* The V1 study answered it honestly but
badly — its universe was "whatever a live user happened to be watching in
2026", which is survivorship-selected by construction and only 22 equities
wide. This module replaces that with membership that actually varies over time.

The reconstruction is a backwards walk. Wikipedia publishes two tables: the
current constituents, and a dated log of additions and removals. Membership at
date *T* is the current set with every change effective *after* T undone —
each addition removed again, each removal put back. Walking backwards rather
than forwards matters because the current set is the only one we know exactly;
a forward walk from some historical guess accumulates error instead of
shedding it.

**Disclosed limits** (validation rule 9 — state gaps, don't fill them):

1. The change log is a community-maintained page. It is dense from ~2000
   onward, which covers this study's window, but it is not S&P's own file. A
   missed change makes one name wrong for the span between the change and the
   next correction; it does not systematically favour winners.
2. Ticker *renames* sometimes appear as an add/remove pair and sometimes not at
   all. A silent rename leaves the old ticker in the historical set, where it
   simply fails to load and drops out — a coverage loss, not a look-ahead.
3. GICS sector is only known for *current* members. Names that have since left
   the index carry `UNKNOWN` unless Yahoo still serves a sector for them, and
   sector membership for surviving names is today's assignment applied to
   history. This is the residual leakage channel §1 says must be "explicitly
   checked for and disclosed if unavoidable" — see `sector_drift_note()`.
4. Delisted names whose bars Yahoo no longer serves cannot be priced. They stay
   in the membership set (so the *count* is right) but drop from the tradeable
   universe, and `alpha.universe` reports how many were lost per cutoff so the
   surviving-share is visible rather than assumed.
"""

from __future__ import annotations

import datetime as dt
import functools
import io
import json
import pathlib
import re
import urllib.request

import pandas as pd

CACHE_DIR = pathlib.Path(__file__).resolve().parent / "cache"
META_DIR = CACHE_DIR / "_meta"

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_UA = {"User-Agent": "Mozilla/5.0 (research; point-in-time index reconstruction)"}

# Wikipedia writes class shares with a dot, Yahoo with a hyphen.
_TICKER_FIXES = {"BRK.B": "BRK-B", "BF.B": "BF-B", "BF.A": "BF-A", "LEN.B": "LEN-B"}


def to_yahoo(ticker: str) -> str:
    ticker = str(ticker).strip().upper()
    return _TICKER_FIXES.get(ticker, ticker.replace(".", "-"))


def _fetch_tables() -> list[pd.DataFrame]:
    request = urllib.request.Request(WIKI_URL, headers=_UA)
    html = urllib.request.urlopen(request, timeout=90).read().decode("utf-8")
    return pd.read_html(io.StringIO(html))


def refresh(force: bool = False) -> dict:
    """Download the constituent and change tables and freeze them to disk.

    Frozen because the reconstruction has to be reproducible: Wikipedia edits
    the change log continuously, and a report whose universe silently shifts
    between runs cannot be checked by anyone.
    """
    META_DIR.mkdir(parents=True, exist_ok=True)
    current_path = META_DIR / "sp500_current.csv"
    changes_path = META_DIR / "sp500_changes.csv"
    stamp_path = META_DIR / "sp500_fetched.json"

    if current_path.exists() and changes_path.exists() and not force:
        return json.loads(stamp_path.read_text(encoding="utf-8"))

    tables = _fetch_tables()
    current = tables[0].copy()
    current.columns = [str(c).strip() for c in current.columns]
    current = current.rename(columns={"GICS Sector": "sector", "Symbol": "ticker",
                                      "Security": "name", "Date added": "date_added"})
    current["ticker"] = current["ticker"].map(to_yahoo)
    current = current[["ticker", "name", "sector", "date_added"]]

    changes = tables[1].copy()
    # Two-level header: ('Effective Date',...), ('Added','Ticker'), ...
    changes.columns = ["_".join(str(p) for p in col).strip() if isinstance(col, tuple) else str(col)
                       for col in changes.columns]
    rename = {}
    for col in changes.columns:
        low = col.lower()
        if "effective" in low:
            rename[col] = "effective_date"
        elif low.startswith("added_ticker"):
            rename[col] = "added"
        elif low.startswith("removed_ticker"):
            rename[col] = "removed"
    changes = changes.rename(columns=rename)
    changes = changes[["effective_date", "added", "removed"]]
    changes["effective_date"] = pd.to_datetime(changes["effective_date"], errors="coerce",
                                               format="mixed")
    changes = changes.dropna(subset=["effective_date"])
    for col in ("added", "removed"):
        changes[col] = changes[col].map(
            lambda v: to_yahoo(v) if isinstance(v, str) and re.fullmatch(r"[A-Za-z.\-]{1,8}", v.strip())
            else None)
    changes = changes.sort_values("effective_date").reset_index(drop=True)

    current.to_csv(current_path, index=False)
    changes.to_csv(changes_path, index=False)
    stamp = {"fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
             "source": WIKI_URL,
             "current_members": int(len(current)),
             "logged_changes": int(len(changes)),
             "earliest_change": str(changes["effective_date"].iloc[0].date()),
             "latest_change": str(changes["effective_date"].iloc[-1].date())}
    stamp_path.write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    return stamp


@functools.lru_cache(maxsize=1)
def _tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached: `members_at` is called once per cutoff, ~500 times per panel build."""
    current = pd.read_csv(META_DIR / "sp500_current.csv")
    changes = pd.read_csv(META_DIR / "sp500_changes.csv",
                          parse_dates=["effective_date"])
    return current, changes


def members_at(cutoff: pd.Timestamp) -> set[str]:
    """Index membership as of end-of-day `cutoff`.

    Undoes every change effective strictly after the cutoff. A change effective
    *on* the cutoff is already reflected in the close of that day, so it stays
    applied — the same edge convention `pit.as_of` uses for bars.
    """
    current, changes = _tables()
    members = set(current["ticker"])
    stamp = pd.Timestamp(cutoff).normalize()

    future = changes[changes["effective_date"] > stamp].sort_values(
        "effective_date", ascending=False)
    for _, row in future.iterrows():
        added, removed = row["added"], row["removed"]
        if isinstance(added, str) and added:
            members.discard(added)          # it wasn't in yet at `cutoff`
        if isinstance(removed, str) and removed:
            members.add(removed)            # it hadn't left yet at `cutoff`
    return members


def membership_panel(cutoffs: list[pd.Timestamp]) -> dict[str, set[str]]:
    """One membership set per cutoff, computed once and reused."""
    return {str(pd.Timestamp(c).date()): members_at(c) for c in cutoffs}


def ever_member(since: pd.Timestamp) -> set[str]:
    """Every ticker that was in the index at any point at or after `since`.

    This is the download list: a name that left the index in 2019 still needs
    bars, because it was tradeable and in the universe for every cutoff before
    it left. Restricting the download to *current* members is exactly the
    survivorship bias this module exists to remove.
    """
    current, changes = _tables()
    names = set(current["ticker"])
    for _, row in changes[changes["effective_date"] >= pd.Timestamp(since)].iterrows():
        for value in (row["added"], row["removed"]):
            if isinstance(value, str) and value:
                names.add(value)
    return names


@functools.lru_cache(maxsize=1)
def sector_map() -> dict[str, str]:
    """GICS sector by ticker — today's assignment, extended by a saved override file.

    Read `sector_drift_note()` before using this for anything load-bearing.
    """
    current, _ = _tables()
    mapping = {row["ticker"]: str(row["sector"]) for _, row in current.iterrows()}
    extra = META_DIR / "sector_overrides.json"
    if extra.exists():
        mapping.update(json.loads(extra.read_text(encoding="utf-8")))
    return {k: v for k, v in mapping.items() if v and v.lower() != "nan"}


def sector_drift_note() -> str:
    """The §1 disclosure, in one place so every report can quote it verbatim."""
    return (
        "Sector assignment is **not** point-in-time. GICS sector is read from the "
        "current constituent table (plus a saved override file for names that have "
        "since left the index) and applied backwards over the whole study window. "
        "Index *membership* is reconstructed as-of-cutoff; sector *labels* are not. "
        "GICS reclassifications are infrequent but real — the 2018 Telecommunication "
        "Services -> Communication Services rebuild moved roughly two dozen large "
        "names at once, and any cutoff before 2018-09 therefore carries a handful of "
        "names filed under a sector they were not yet in. Sector-relative features and "
        "the sector-relative target inherit that error. It is a look-ahead channel of "
        "the same class as adjusted prices in the V1 study: small, one-directional in "
        "no obvious way, and not removable without a paid GICS history."
    )


def main() -> None:
    stamp = refresh(force=True)
    print(json.dumps(stamp, indent=2))
    for probe in ("2016-01-04", "2020-03-16", "2023-06-01", "2026-08-07"):
        members = members_at(pd.Timestamp(probe))
        print(f"  {probe}: {len(members)} members")


if __name__ == "__main__":
    main()
