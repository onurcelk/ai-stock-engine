"""Family 10 identity: CIK -> historical security -> point-in-time membership.

**NON-PREDICTIVE.** This module reads no price, no return, no target and no
model. It exists to answer one question the source survey flagged as the
family's fatal risk (`reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §4 row J):

> `company_tickers.json` lists **current** registrants only, so names that
> delisted, merged or went bankrupt silently vanish — and those names are
> *precisely* the adverse-event population. The survivorship trap is therefore
> correlated with the sign of the effect the study is looking for.

Measured here: **120 of the 721 tickers that were S&P 500 members at any point
since 2016 have no entry in `company_tickers.json`** (16.6%). Nineteen of them
have bars on disk, so they would have been panel members. Rebuilding the event
panel on the current ticker map would delete them.

The repair is a three-link chain, each link sourced and auditable:

```
ticker  --(1)-->  historical security name   (S&P change log: the same Wikipedia
                                              source alpha/membership.py already
                                              uses; the *Security* columns that
                                              refresh() discards)
name    --(2)-->  CIK                        (SEC bulk submissions: every CIK's
                                              name and formerNames, dead ones
                                              included -- a dead filer keeps its
                                              JSON, it only loses its `tickers`)
CIK     --(3)-->  membership interval        (alpha/membership.members_at, the
                                              existing PIT machinery, unchanged)
```

Link (2) is corroborated, never assumed: a name match is accepted only when it
is unique *and* the CIK actually filed something during the ticker's index
membership interval. Ambiguous cases are recorded as UNRESOLVED rather than
guessed, per the pilot directive.

Three frozen artefacts, all written once and read thereafter:

| file | content |
|---|---|
| `alpha/edgar/cik_directory.parquet` | every CIK in the bulk archive: name, current tickers, former names, SIC |
| `alpha/cache/_meta/sp500_security_names.csv` | ticker -> security name, from the constituent table and the change log |
| `alpha/edgar/family10_identity.json` | the resolved map, with method and evidence per ticker |

`alpha/cache/_meta/sp500_changes.csv` and `sp500_current.csv` are **not**
touched. The membership used by this pilot is the frozen one; the refresh here
writes a sidecar and reports drift rather than overwriting the universe.

Build:  python -m alpha.family10_identity
"""

from __future__ import annotations

import collections
import datetime as dt
import io
import json
import pathlib
import re
import urllib.request
import zipfile

import pandas as pd

from . import membership

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
META_DIR = pathlib.Path(__file__).resolve().parent / "cache" / "_meta"

SUBMISSIONS = EDGAR_DIR / "submissions.zip"
DIRECTORY_PATH = EDGAR_DIR / "cik_directory.parquet"
NAMES_PATH = META_DIR / "sp500_security_names.csv"
IDENTITY_PATH = EDGAR_DIR / "family10_identity.json"

STUDY_START = "2016-01-04"

#: How many bytes of each per-CIK JSON to read. The metadata block (`cik`,
#: `name`, `tickers`, `exchanges`, `formerNames`) precedes the `filings` block,
#: so a prefix is enough and the 1.5 GB archive never has to be fully inflated.
#: Prefixes that do not reach `formerNames` are re-read in full and counted.
_PREFIX = 16384

_CIK_RE = re.compile(rb'"cik":"(\d+)"')
_NAME_RE = re.compile(rb'"name":"((?:[^"\\]|\\.)*)"')
_TICKERS_RE = re.compile(rb'"tickers":\[(.*?)\]', re.S)
_EXCHANGES_RE = re.compile(rb'"exchanges":\[(.*?)\]', re.S)
_FORMER_RE = re.compile(rb'"formerNames":\[(.*?)\](?:,"filings"|\})', re.S)
_SIC_RE = re.compile(rb'"sic":"(\d*)"')

#: Corporate-form noise stripped before comparing a Wikipedia security name to
#: an SEC registrant name. Deliberately conservative: it removes suffixes and
#: punctuation only, never a distinguishing word, so it cannot merge two
#: genuinely different issuers.
_LEGAL_SUFFIXES = (
    "incorporated", "inc", "corporation", "corp", "company", "co",
    "limited", "ltd", "plc", "lp", "llc", "holdings", "holding",
    "group", "the", "sa", "nv", "ag", "class", "trust", "and",
)


def normalise_name(name: str) -> str:
    """Company name -> comparison key. Punctuation, case and legal form removed.

    `TIFFANY & CO` and `Tiffany & Co.` both become `tiffany`; `E I DU PONT DE
    NEMOURS & CO` becomes `e i du pont de nemours`. The suffix list is applied
    repeatedly from the end so `... Holdings Inc.` loses both words.
    """
    text = str(name).lower()
    # EDGAR appends the state of incorporation as `/DE/`, `/CA/`, `/NJ/`. It is
    # part of the registrant's filed name, not part of the company, and leaving
    # it in blocks `LINEAR TECHNOLOGY CORP /CA/` from matching `Linear Technology`.
    text = re.sub(r"/[a-z]{2}(?:/|\b)", " ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [w for w in text.split() if w]
    changed = True
    while changed and words:
        changed = False
        while words and words[-1] in _LEGAL_SUFFIXES:
            words.pop()
            changed = True
        while words and words[0] in ("the",):
            words.pop(0)
            changed = True
    return " ".join(words)


# ----------------------------------------------------------------------
# Link 2 — the SEC side: every CIK, dead ones included
# ----------------------------------------------------------------------

def _unpack_strings(blob: bytes) -> list[str]:
    return [m.decode("utf-8", "replace") for m in re.findall(rb'"([^"]*)"', blob)]


def _former_names(blob: bytes) -> list[str]:
    return [m.decode("utf-8", "replace")
            for m in re.findall(rb'"name":"((?:[^"\\]|\\.)*)"', blob)]


def scan_submissions(path: pathlib.Path | None = None,
                     limit: int | None = None,
                     verbose: bool = True) -> pd.DataFrame:
    """Directory of every CIK in the bulk archive: name, tickers, former names.

    A filer that stopped filing keeps its JSON but loses its `tickers` entry —
    **measured**: `CIK0000098246` (Tiffany) and `CIK0000001011006` (Altaba, ex
    Yahoo) both carry `"tickers":[]`. That is exactly why the ticker map cannot
    be the identity key and the name has to carry the join.
    """
    source = pathlib.Path(path) if path else SUBMISSIONS
    archive = zipfile.ZipFile(source)
    members = [n for n in archive.namelist()
               if n.startswith("CIK") and "-submissions-" not in n]
    if limit:
        members = members[:limit]

    rows, reread = [], 0
    for count, member in enumerate(members, 1):
        with archive.open(member) as handle:
            head = handle.read(_PREFIX)
        former = _FORMER_RE.search(head)
        if former is None and len(head) == _PREFIX:
            head = archive.read(member)          # a long address block; pay the cost
            former = _FORMER_RE.search(head)
            reread += 1
        cik = _CIK_RE.search(head)
        name = _NAME_RE.search(head)
        if cik is None or name is None:
            continue
        tickers = _TICKERS_RE.search(head)
        exchanges = _EXCHANGES_RE.search(head)
        sic = _SIC_RE.search(head)
        rows.append({
            "cik": int(cik.group(1)),
            "name": name.group(1).decode("utf-8", "replace"),
            "tickers": "|".join(_unpack_strings(tickers.group(1))) if tickers else "",
            "exchanges": "|".join(_unpack_strings(exchanges.group(1))) if exchanges else "",
            "former_names": "|".join(_former_names(former.group(1))) if former else "",
            "sic": sic.group(1).decode() if sic else "",
        })
        if verbose and count % 200_000 == 0:
            print(f"  {count:,}/{len(members):,} CIK files", flush=True)

    frame = pd.DataFrame(rows)
    frame.attrs["reread_full"] = reread
    return frame


def sec_ticker_map() -> dict[str, set[int]]:
    """Ticker -> CIK from the SEC's two disagreeing snapshots, unioned.

    Neither is complete and the disagreement runs both ways (**measured**):
    `company_tickers.json` covers 7,998 CIKs and omits AEP, which the bulk
    archive carries; the bulk archive attaches a ticker to 7,957 CIKs and omits
    406 that `company_tickers.json` has. Taking the union and letting a
    disagreement raise a *conflict* — never a silent pick — is the only reading
    that does not quietly prefer one snapshot's blind spot.

    Both are **current-registrant** snapshots either way. Neither can see a dead
    ticker, which is what the name route in `resolve` exists for.
    """
    mapping: dict[str, set[int]] = collections.defaultdict(set)
    directory = load_directory()
    for cik, blob in zip(directory["cik"], directory["tickers"]):
        for ticker in str(blob).split("|"):
            if ticker:
                mapping[membership.to_yahoo(ticker)].add(int(cik))
    table = EDGAR_DIR / "company_tickers.json"
    if table.exists():
        for row in json.loads(table.read_text(encoding="utf-8")).values():
            mapping[membership.to_yahoo(row["ticker"])].add(int(row["cik_str"]))
    return dict(mapping)


def load_directory(path: pathlib.Path | None = None) -> pd.DataFrame:
    source = pathlib.Path(path) if path else DIRECTORY_PATH
    if not source.exists():
        raise RuntimeError(f"no CIK directory at {source} — "
                           "run: python -m alpha.family10_identity")
    return pd.read_parquet(source)


# ----------------------------------------------------------------------
# Link 1 — the index side: ticker -> historical security name
# ----------------------------------------------------------------------

def refresh_security_names(force: bool = False) -> pd.DataFrame:
    """Freeze ticker -> security name from the S&P constituent and change tables.

    `membership.refresh()` keeps only the *ticker* columns of the change log.
    The `Security` columns are what turns a dead ticker back into a name, so
    they are frozen here into a sidecar. The membership files themselves are
    never rewritten by this function — the universe this pilot runs on stays
    the one frozen on 2026-08-08.
    """
    META_DIR.mkdir(parents=True, exist_ok=True)
    if NAMES_PATH.exists() and not force:
        return pd.read_csv(NAMES_PATH)

    request = urllib.request.Request(membership.WIKI_URL, headers=membership._UA)
    html = urllib.request.urlopen(request, timeout=90).read().decode("utf-8")
    tables = pd.read_html(io.StringIO(html))

    rows = []
    current = tables[0].copy()
    current.columns = [str(c).strip() for c in current.columns]
    for _, row in current.iterrows():
        rows.append({"ticker": membership.to_yahoo(row["Symbol"]),
                     "security": str(row["Security"]),
                     "source": "current",
                     "effective_date": "",
                     "wiki_cik": int(row["CIK"]) if pd.notna(row.get("CIK")) else -1})

    changes = tables[1].copy()
    changes.columns = ["_".join(str(p) for p in c) if isinstance(c, tuple) else str(c)
                       for c in changes.columns]
    lookup = {}
    for column in changes.columns:
        low = column.lower()
        for key, prefix in (("effective_date", "effective"),
                            ("added_ticker", "added_ticker"),
                            ("added_security", "added_security"),
                            ("removed_ticker", "removed_ticker"),
                            ("removed_security", "removed_security")):
            if low.startswith(prefix):
                lookup.setdefault(key, column)
    for _, row in changes.iterrows():
        stamp = pd.to_datetime(row[lookup["effective_date"]], errors="coerce",
                               format="mixed")
        for side in ("added", "removed"):
            ticker = row.get(lookup[f"{side}_ticker"])
            security = row.get(lookup[f"{side}_security"])
            if not isinstance(ticker, str) or not re.fullmatch(r"[A-Za-z.\-]{1,8}",
                                                               ticker.strip()):
                continue
            rows.append({"ticker": membership.to_yahoo(ticker),
                         "security": str(security) if isinstance(security, str) else "",
                         "source": side,
                         "effective_date": "" if pd.isna(stamp) else str(stamp.date()),
                         "wiki_cik": -1})

    frame = pd.DataFrame(rows).drop_duplicates()
    frame.to_csv(NAMES_PATH, index=False)
    return frame


def load_security_names() -> pd.DataFrame:
    if not NAMES_PATH.exists():
        raise RuntimeError(f"no security-name sidecar at {NAMES_PATH} — "
                           "run: python -m alpha.family10_identity")
    return pd.read_csv(NAMES_PATH).fillna({"security": "", "effective_date": ""})


# ----------------------------------------------------------------------
# Link 3 — membership intervals, from the existing PIT machinery
# ----------------------------------------------------------------------

def membership_intervals(since: str = STUDY_START) -> dict[str, list[tuple[str, str]]]:
    """Per ticker, the [start, end] spans it was an index member, from the frozen log.

    Derived from `membership.members_at` evaluated at every date the change log
    moves, so it agrees with the existing machinery by construction rather than
    by a second implementation of the same walk. `test_family10_identity.py`
    pins the agreement.
    """
    _, changes = membership._tables()
    start = pd.Timestamp(since)
    boundaries = sorted({start} | {pd.Timestamp(d) for d in changes["effective_date"]
                                   if pd.Timestamp(d) > start})
    spans: dict[str, list[list[str]]] = {}
    previous: set[str] = set()
    for stamp in boundaries:
        members = membership.members_at(stamp)
        for ticker in members - previous:
            spans.setdefault(ticker, []).append([str(stamp.date()), ""])
        for ticker in previous - members:
            if spans.get(ticker):
                spans[ticker][-1][1] = str(stamp.date())
        previous = members
    return {t: [(a, b) for a, b in v] for t, v in spans.items()}


def member_sets_by_boundary(since: str = STUDY_START
                            ) -> tuple[list[pd.Timestamp], list[set[str]]]:
    """Membership as a step function: the dates it changes, and the set after each.

    `members_at` is exact but walks the whole change log per call; an event panel
    needs membership on all 2,664 sessions rather than on the 532 cutoffs. The
    set can only change on a change-log date, so evaluating there and holding it
    constant in between is the same answer at a fraction of the cost.
    """
    _, changes = membership._tables()
    start = pd.Timestamp(since)
    boundaries = sorted({start} | {pd.Timestamp(d) for d in changes["effective_date"]
                                   if pd.Timestamp(d) > start})
    return boundaries, [membership.members_at(b) for b in boundaries]


def members_on(date: pd.Timestamp, boundaries: list[pd.Timestamp],
               sets: list[set[str]]) -> set[str]:
    """Membership on `date` from the step function. Same edge rule as `members_at`."""
    stamp = pd.Timestamp(date).normalize()
    position = int(pd.DatetimeIndex(boundaries).searchsorted(stamp, side="right")) - 1
    return sets[position] if position >= 0 else set()


# ----------------------------------------------------------------------
# Resolution
# ----------------------------------------------------------------------

#: Forms only a listed *equity* issuer files. A financing subsidiary with public
#: debt files 10-Ks too, which is why the periodic-report test alone cannot
#: separate `DISH Network` from `DISH DBS`; only the equity issuer holds a
#: shareholder meeting and files a proxy.
PERIODIC_FORMS = ("10-K", "10-Q", "20-F", "40-F")
EQUITY_FORMS = ("DEF 14A", "DEFA14A", "DEFM14A", "DEFR14A")

#: A quarter plus the filing lag. Membership shorter than this can legitimately
#: contain no periodic report at all — `PCP` was in the index for four weeks
#: before Berkshire closed, `MBC` for four days — so demanding one would reject
#: the correct CIK. Below the threshold, any filing during membership counts.
SHORT_MEMBERSHIP_DAYS = 150


def filing_profile(archive: zipfile.ZipFile, cik: int) -> pd.DataFrame:
    """Every filing a CIK has on record as (form, filed), across all blocks.

    Reads the `recent` block *and* every continuation file, so a filer with more
    than 1,000 filings is not silently truncated to its recent history — the same
    correctness point `source_probe._rows_for` makes.
    """
    member = f"CIK{cik:010d}.json"
    try:
        payload = json.loads(archive.read(member))
    except KeyError:
        return pd.DataFrame(columns=["form", "filed"])
    blocks = [payload["filings"]["recent"]]
    for extra in payload["filings"].get("files", []):
        try:
            blocks.append(json.loads(archive.read(extra["name"])))
        except KeyError:
            continue
    forms: list[str] = []
    filed: list[str] = []
    for block in blocks:
        forms.extend(block.get("form", []))
        filed.extend(block.get("filingDate", []))
    size = min(len(forms), len(filed))
    return pd.DataFrame({"form": forms[:size], "filed": filed[:size]})


def _activity(profile: pd.DataFrame, spans: list[tuple[str, str]]) -> dict:
    """How a CIK behaved *during* the ticker's index membership, and only then."""
    if profile.empty:
        return {"filings": 0, "periodic": 0, "equity": 0, "first": "", "last": ""}
    inside = pd.Series(False, index=profile.index)
    for start, end in spans:
        stop = end or "9999-12-31"
        inside |= (profile["filed"] >= start) & (profile["filed"] < stop)
        # A removal is effective at the close of `end`; a filing on that day was
        # still the filing of an index member, so the window is closed on the
        # left and the last membership session is retained by `<` on the *next*
        # boundary rather than by excluding `end` itself.
    window = profile[inside]
    forms = window["form"].astype(str)
    return {
        "filings": int(len(window)),
        "periodic": int(forms.str.startswith(PERIODIC_FORMS).sum()),
        "equity": int(forms.isin(EQUITY_FORMS).sum()),
        "first": str(profile["filed"].min()),
        "last": str(profile["filed"].max()),
    }


def span_days(spans: list[tuple[str, str]], today: str = "2026-08-11") -> int:
    """Total calendar days a ticker spent in the index, across all its spans."""
    total = 0
    for start, end in spans:
        stop = pd.Timestamp(end) if end else pd.Timestamp(today)
        total += max(0, int((stop - pd.Timestamp(start)).days))
    return total


def corroborated(seen: dict, days: int) -> bool:
    """Did this CIK behave like the issuer of that ticker while it was a member?

    Long membership demands a periodic report — that is what separates the live
    registrant from a same-named shell, and what exposes a **reused ticker**,
    whose present-day owner filed nothing during the old membership. Short
    membership cannot demand one, because none was due.
    """
    return seen["periodic"] > 0 if days >= SHORT_MEMBERSHIP_DAYS else seen["filings"] > 0


def _name_index(directory: pd.DataFrame) -> dict[str, set[int]]:
    """First word of a normalised registrant name -> the CIKs whose name starts there.

    Both the registered name and every former name are indexed, because an issuer
    that renamed keeps filing under the same CIK — `ALTABA INC.` is `YAHOO INC`,
    and the ticker `YHOO` only reaches it through the former name.
    """
    index: dict[str, set[int]] = collections.defaultdict(set)
    for cik, name, former in zip(directory["cik"], directory["name"],
                                 directory["former_names"]):
        labels = [str(name)] + [n for n in str(former).split("|") if n]
        for label in labels:
            key = normalise_name(label)
            if key:
                index[key.split()[0]].add(int(cik))
    return dict(index)


def _normalised_labels(directory: pd.DataFrame) -> dict[int, set[str]]:
    out: dict[int, set[str]] = collections.defaultdict(set)
    for cik, name, former in zip(directory["cik"], directory["name"],
                                 directory["former_names"]):
        for label in [str(name)] + [n for n in str(former).split("|") if n]:
            key = normalise_name(label)
            if key:
                out[int(cik)].add(key)
    return dict(out)


#: Words that may differ between a Wikipedia security name and an SEC registrant
#: name without making them different companies: legal form, the state-of-
#: incorporation tail EDGAR appends (`SEALED AIR CORP/DE`), and the handful of
#: generic business nouns Wikipedia drops (`DISCOVER FINANCIAL SERVICES` ->
#: `Discover Financial`). Nothing distinguishing is in this list, which is what
#: keeps `Apple` from absorbing `Apple Hospitality REIT`.
_GENERIC_TAIL = frozenset({
    "corp", "corporation", "co", "company", "companies", "cos", "inc",
    "incorporated", "holdings", "holding", "group", "groups", "plc", "ltd",
    "limited", "llc", "lp", "sa", "nv", "ag", "se", "the", "of", "and",
    "services", "service", "industries", "international", "enterprises",
    "de", "md", "ny", "tx", "ma", "dl", "new", "usa", "us", "america",
    "american", "class", "cl", "a", "b", "c",
})


def name_compatible(wiki: str, sec: str) -> bool:
    """Is `sec` the registrant name of the security Wikipedia calls `wiki`?

    Wikipedia writes the *short* name (`Sealed Air`, `Discover Financial`) and
    the SEC the *legal* one (`SEALED AIR CORP/DE`, `DISCOVER FINANCIAL
    SERVICES`), so exact equality on the normalised forms misses most dead names
    — **measured**, it left 40 of 720 tickers unresolved, live issuers among
    them. A bare prefix rule overcorrects just as badly: it made `Apple` a
    candidate for `APPLE HOSPITALITY REIT`, and 110 tickers came back ambiguous.

    The rule that works is a prefix in either direction whose surplus words are
    **all generic** — legal form, incorporation state, filler. A distinguishing
    word in the tail means a different company.
    """
    if not wiki or not sec:
        return False
    if wiki == sec:
        return True
    longer, shorter = (sec, wiki) if len(sec) > len(wiki) else (wiki, sec)
    if not longer.startswith(shorter + " "):
        return False
    tail = longer[len(shorter) + 1:].split()
    return bool(tail) and all(word in _GENERIC_TAIL for word in tail)


def name_subset(wiki: str, sec: str) -> bool:
    """Every word of the short name appears in the registrant name.

    The last resort, for the cases where Wikipedia's short name is not a prefix
    of the legal one: `Mead Johnson` inside `MEAD JOHNSON NUTRITION CO`,
    `Ceridian` inside `Ceridian HCM Holding Inc.`. It requires **all** the
    distinguishing words, which is what an earlier first-word-only version of
    this rule did not — that version mapped `Ferguson Enterprises` to `FERGUSON
    WELLMAN CAPITAL MANAGEMENT` and `Signature Bank` to `GB SCIENCES INC`, two
    of its six resolutions wrong. Both are rejected here.
    """
    if not wiki or not sec:
        return False
    words = [w for w in wiki.split() if w not in ("the", "of", "and")]
    return bool(words) and set(words) <= set(sec.split())


def resolve(directory: pd.DataFrame, names: pd.DataFrame,
            intervals: dict[str, list[tuple[str, str]]],
            archive: zipfile.ZipFile,
            ticker_map: dict[str, set[int]] | None = None,
            verbose: bool = True) -> dict:
    """Ticker -> CIK for every ticker that was ever a member, with method and evidence.

    Two stages, and the separation is the point: **names propose, filings
    dispose.** A name match is only a candidate; what accepts a candidate is
    that the CIK was actually filing periodic reports as a listed equity issuer
    *during the interval the ticker was in the index*. That test is what
    separates `MONSANTO CO` (CIK 1110783, filing through 2018) from the older
    registrant of the same name that stopped filing in 2003, and it is
    information the SEC archive carries rather than something assumed.

    | method | how the CIK was reached |
    |---|---|
    | `sec_ticker` | the ticker is in a current registrant's ticker array, and that CIK filed during the interval |
    | `wiki_cik` | the S&P constituent table's own CIK column, corroborated the same way |
    | `sec_name` | a name-compatible registrant, unique after the activity test |
    | `unresolved` | no candidate, or more than one survives |

    Every rejection is recorded in `conflicts` with its reason, so the count of
    holes is auditable and no hole is quietly filled.
    """
    if ticker_map is None:
        ticker_map = sec_ticker_map()

    by_first_word = _name_index(directory)
    labels = _normalised_labels(directory)

    wiki_cik = {row["ticker"]: int(row["wiki_cik"])
                for _, row in names[names["source"] == "current"].iterrows()
                if int(row["wiki_cik"]) > 0}
    security: dict[str, set[str]] = collections.defaultdict(set)
    for _, row in names.iterrows():
        if str(row["security"]).strip():
            security[row["ticker"]].add(str(row["security"]).strip())

    profiles: dict[int, pd.DataFrame] = {}

    def activity(cik: int, spans: list[tuple[str, str]]) -> dict:
        if cik not in profiles:
            profiles[cik] = filing_profile(archive, cik)
        return _activity(profiles[cik], spans)

    resolved: dict[str, dict] = {}
    conflicts: list[dict] = []
    unresolved: list[str] = []

    for count, ticker in enumerate(sorted(intervals), 1):
        spans = intervals[ticker]
        record = {"ticker": ticker, "cik": None, "method": "unresolved",
                  "evidence": "", "spans": spans,
                  "security_names": sorted(security.get(ticker, ()))}

        # --- stage 1: propose ------------------------------------------------
        proposals: dict[int, str] = {}
        for cik in ticker_map.get(ticker, ()):
            proposals[int(cik)] = "sec_ticker"
        if ticker in wiki_cik:
            proposals.setdefault(wiki_cik[ticker], "wiki_cik")
        for label in security.get(ticker, ()):
            key = normalise_name(label)
            if not key:
                continue
            for cik in by_first_word.get(key.split()[0], ()):
                others = labels.get(cik, ())
                if any(name_compatible(key, other) for other in others):
                    proposals.setdefault(int(cik), "sec_name")
                elif any(name_subset(key, other) for other in others):
                    # Tier 3, consulted only if tiers 1-2 come back empty.
                    proposals.setdefault(int(cik), "sec_name_subset")

        # --- stage 2: dispose ------------------------------------------------
        # Direct evidence first. A ticker array entry says *this* CIK trades
        # under that symbol; a name match only says the names look alike. The
        # two are not weighed together — the name route is consulted only when
        # no direct proposal survives, which is also what makes a **reused
        # ticker** fall through to its historical owner instead of silently
        # rebinding an old event to whoever holds the symbol today.
        days = span_days(spans)
        survivors: dict[int, dict] = {}
        for tier in (("sec_ticker", "wiki_cik"), ("sec_name",), ("sec_name_subset",)):
            for cik, method in proposals.items():
                if method not in tier:
                    continue
                seen = activity(cik, spans)
                if corroborated(seen, days):
                    survivors[cik] = dict(seen, method=method)
                elif tier[0] == "sec_ticker":
                    # Direct evidence that does not corroborate is the signature
                    # of ticker reuse, and it is recorded rather than ignored.
                    conflicts.append({
                        "ticker": ticker, "cik": int(cik), "method": method,
                        "reason": "direct ticker match filed no periodic report "
                                  "during membership (ticker reuse or shell)",
                        "filings_in_window": seen["filings"],
                        "history": f"{seen['first']}..{seen['last']}"})
            if survivors:
                break

        if len(survivors) > 1:
            # Only a listed equity issuer files a proxy; a financing subsidiary
            # with public debt files 10-Ks and does not.
            proxied = {c: v for c, v in survivors.items() if v["equity"] > 0}
            if proxied:
                survivors = proxied

        if len(survivors) == 1:
            cik, seen = next(iter(survivors.items()))
            record.update(cik=int(cik), method=seen["method"],
                          evidence=f"{seen['periodic']} periodic and {seen['equity']} "
                                   f"proxy filings during membership; "
                                   f"filed {seen['first']}..{seen['last']}",
                          filings_in_window=seen["filings"],
                          periodic_in_window=seen["periodic"],
                          equity_in_window=seen["equity"])
        else:
            conflicts.append({"ticker": ticker,
                              "reason": "several CIKs survive" if survivors
                                        else "no candidate survives",
                              "ciks": sorted(int(c) for c in survivors)[:12],
                              "survivors": len(survivors),
                              "proposed": len(proposals)})
            unresolved.append(ticker)

        resolved[ticker] = record
        if verbose and count % 100 == 0:
            print(f"  {count}/{len(intervals)} tickers, "
                  f"{len(unresolved)} unresolved", flush=True)

    by_cik: dict[int, list[str]] = collections.defaultdict(list)
    for ticker, record in resolved.items():
        if record["cik"] is not None:
            by_cik[int(record["cik"])].append(ticker)

    return {"resolved": resolved,
            "unresolved": unresolved,
            "conflicts": conflicts,
            "multi_security_ciks": {str(c): sorted(v)
                                    for c, v in by_cik.items() if len(v) > 1}}


def load_identity() -> dict:
    if not IDENTITY_PATH.exists():
        raise RuntimeError(f"no identity map at {IDENTITY_PATH} — "
                           "run: python -m alpha.family10_identity")
    return json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))


def main() -> None:
    if not DIRECTORY_PATH.exists():
        print("scanning the bulk submissions archive for every CIK ...")
        directory = scan_submissions()
        directory.to_parquet(DIRECTORY_PATH, index=False)
        print(f"  {len(directory):,} CIKs "
              f"({directory.attrs.get('reread_full', 0)} needed a full read)")
    directory = load_directory()

    names = refresh_security_names()
    intervals = membership_intervals()
    archive = zipfile.ZipFile(SUBMISSIONS)
    payload = resolve(directory, names, intervals, archive, sec_ticker_map())

    ever = sorted(intervals)
    methods = collections.Counter(r["method"] for r in payload["resolved"].values())
    payload["built_at"] = dt.datetime.now().isoformat(timespec="seconds")
    payload["ever_member_tickers"] = len(ever)
    payload["methods"] = dict(methods)
    IDENTITY_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"\never-member tickers since {STUDY_START}: {len(ever)}")
    for method, count in methods.most_common():
        print(f"  {method:18s} {count:4d}")
    print(f"unresolved: {len(payload['unresolved'])} -> {payload['unresolved']}")
    print(f"conflicts recorded: {len(payload['conflicts'])}")
    print(f"wrote {IDENTITY_PATH}")


if __name__ == "__main__":
    main()
