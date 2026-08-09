"""Build the Family 3 institutional-holdings table from SEC Form 13F data sets.

Two stages, both content-light and neither of which computes a feature:

**Stage 1 - the CUSIP6 map.** 13F identifies securities by CUSIP; the panel is
keyed by symbol and the filings door by CIK, and a 13F carries no issuer CIK.
The bridge is the issuer NAME, matched against every name EDGAR has for our
issuers - the current one, every `formerNames` entry, and the ticker file's
title. Former names are essential: EDGAR holds the CURRENT name while a 2016
filing holds the 2016 name (CenturyLink -> Lumen, PerkinElmer -> Revvity).

CUSIPs are zero-padded to 9 before the 6-character issuer key is sliced. Some
filers strip leading zeros, so Abbott's `002824109` arrives as `2824109`, and
slicing that raw yields `282410` - a different, wrong issuer.

The map is pooled over archives spanning the whole era, because a name that
listed in 2021 cannot be matched from a 2016 archive.

**Stage 2 - the holdings events.** Per (filer, period, issuer): shares held,
with the filing date that made them knowable. Common stock only - `PUTCALL`
rows are options and are excluded, and `SSHPRNAMTTYPE` must be `SH`.

Point-in-time rule. The bulk sets carry `FILING_DATE` but **no acceptance
time**, and the 13F filer population is tens of thousands of institutions whose
`submissions.zip` we do not hold. Rather than approximate an acceptance
timestamp, the door here is deliberately **stricter** than Families 1 and 2':

    admissible at cutoff T  <=>  FILING_DATE  <  T

A filing dated T is not usable at T. This can only ever *delay* information,
never advance it, so it cannot leak; it costs at most one session against a
statutory lag of 45-135 days.

Amendments are resolved the way the filings door resolves restatements: per
(filer, period), the latest filing admissible at T wins, and earlier ones are
superseded.

Output: `alpha/edgar/f13_events.parquet` and `f13_meta.json`. ASCII stdout.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import pathlib
import re
import sys
import time
import zipfile
from collections import defaultdict

import pandas as pd

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
F13_DIR = EDGAR_DIR / "f13"
OUT_PARQUET = EDGAR_DIR / "f13_events.parquet"
OUT_MAP = EDGAR_DIR / "f13_cusip_map.json"
OUT_META = EDGAR_DIR / "f13_meta.json"

HOLDING_FORMS = ("13F-HR", "13F-HR/A")

SUFFIX = (r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|COMPANIES|LTD|LIMITED"
          r"|PLC|LLC|LP|HLDG|HLDGS|HOLDING|HOLDINGS|GROUP|GRP|THE|NEW|COM|CL|CLASS"
          r"|SA|NV|AG|TRUST|REIT|INTL|INTERNATIONAL|INDS|INDUSTRIES|USA|US|SVCS"
          r"|SERVICES|SVC)\b")


def norm(name) -> str:
    if not isinstance(name, str):
        return ""
    s = name.upper()
    s = re.sub(r"[/\\]\s*[A-Z]{2,4}\s*[/\\]?", " ", s)     # /DE/  \DE\  /NEW/  / MA
    s = s.replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(SUFFIX, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def token_key(name) -> str:
    """Order-insensitive key, so EDGAR's 'HUNT J B TRANSPORT' matches
    13F's 'J B HUNT TRANSPORT'."""
    n = norm(name)
    return " ".join(sorted(set(n.split()))) if n else ""


def cusip_check_digit(s: str) -> str | None:
    """The standard CUSIP modulus-10 double-add-double check character."""
    total = 0
    for i, ch in enumerate(s[:8]):
        if ch.isdigit():
            value = int(ch)
        elif ch.isalpha():
            value = ord(ch) - 55
        else:
            return None
        if i % 2:
            value *= 2
        total += value // 10 + value % 10
    return str((10 - total % 10) % 10)


def cusip6(raw) -> str | None:
    """The 6-character issuer key, or None if the CUSIP is not well formed.

    Two guards, both load-bearing:

    * **zero-padding.** Filers strip leading zeros, so Abbott's `002824109`
      arrives as `2824109`; slicing that raw yields `282410`, a different
      issuer.
    * **the check digit.** Some filers left-justify into a 9-wide field, so
      Berkshire's `084670702` arrives as `846707020` - which zero-pads to
      itself and slices to a plausible-looking `846707`. Padding cannot catch
      that; the check digit can, and does. Without this guard the map put
      Berkshire on a CUSIP that does not exist.
    """
    if not isinstance(raw, str):
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if len(s) < 8 or len(s) > 9 or set(s) <= {"0"}:
        return None
    s = s.zfill(9)
    if cusip_check_digit(s) != s[8]:
        return None
    return s[:6]


def universe():
    meta = json.load(open(EDGAR_DIR / "filings_meta.json"))
    symbol_to_cik = {s: int(c) for s, c in meta["symbol_to_cik"].items()}
    submissions = zipfile.ZipFile(EDGAR_DIR / "submissions.zip")
    names: dict[int, set[str]] = {}
    for cik in sorted(set(symbol_to_cik.values())):
        try:
            blob = json.loads(submissions.read("CIK%010d.json" % cik))
        except KeyError:
            continue
        found = {blob.get("name", "")}
        for former in blob.get("formerNames", []) or []:
            if former.get("name"):
                found.add(former["name"])
        names[cik] = {n for n in found if n}
    try:
        for row in json.load(open(EDGAR_DIR / "company_tickers.json")).values():
            cik = int(row["cik_str"])
            if cik in names and row.get("title"):
                names[cik].add(row["title"])
    except FileNotFoundError:
        pass
    return symbol_to_cik, names


def archives() -> list[str]:
    return sorted(glob.glob(str(F13_DIR / "*_form13f.zip")))


def member(archive: zipfile.ZipFile, table: str) -> str:
    """Locate a table inside the archive.

    Most archives hold the tables at the root; `01jun2025-31aug2025` nests them
    one directory down. Resolving by suffix rather than by exact name keeps that
    one archive from being silently skipped - which would have punched a
    three-month hole in the middle of the study era.
    """
    for name in archive.namelist():
        if name.rsplit("/", 1)[-1] == table:
            return name
    raise KeyError("%s not found in archive" % table)


#: A hand-checked sample of issuer CUSIP6 values, used to validate the
#: name-matched map rather than trust it. Each is the real, published CUSIP6.
KNOWN_CUSIP6 = {
    320193: "037833",    # Apple
    789019: "594918",    # Microsoft
    1018724: "023135",   # Amazon
    1652044: "02079K",   # Alphabet
    1326801: "30303M",   # Meta
    1318605: "88160R",   # Tesla
    19617: "46625H",     # JPMorgan Chase
    200406: "478160",    # Johnson & Johnson
    34088: "30231G",     # Exxon Mobil
    1067983: "084670",   # Berkshire Hathaway
    104169: "931142",    # Walmart
    1045810: "67066G",   # NVIDIA
    80424: "742718",     # Procter & Gamble
    21344: "191216",     # Coca-Cola
    93410: "166764",     # Chevron
}


def build_map(paths, cik_names) -> dict[str, int]:
    """CUSIP6 -> CIK, pooled over archives spanning the whole era.

    Three rules keep the fuzz out, each fixing a way a name matcher goes wrong:

    1. **Only a CUSIP's MODAL name is indexed.** Filers typo and mislabel, so
       indexing every name ever paired with a CUSIP lets one bad row attach a
       mega-cap's CUSIP to an unrelated issuer.
    2. **Popularity is distinct filings, not rows**, so a widely held name does
       not win a tie merely by being listed many times per filing.
    3. **The assignment is strictly one-to-one**, resolved globally by
       confidence. Keying the result by CUSIP silently lets a later issuer
       overwrite an earlier one, which is how a first attempt mapped Meta onto
       JPMorgan's CUSIP and dropped Apple and Microsoft entirely.
    """
    name_rows = defaultdict(lambda: defaultdict(int))     # cusip6 -> name -> rows
    filings = defaultdict(set)                            # cusip6 -> accessions
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            reader = pd.read_csv(archive.open(member(archive, "INFOTABLE.tsv")),
                                 sep="\t", encoding="latin-1",
                                 usecols=["ACCESSION_NUMBER", "NAMEOFISSUER", "CUSIP"],
                                 dtype=str, chunksize=1_000_000, low_memory=False)
            for chunk in reader:
                for accn, name, raw in zip(chunk["ACCESSION_NUMBER"],
                                           chunk["NAMEOFISSUER"], chunk["CUSIP"]):
                    key = cusip6(raw)
                    if key is None:
                        continue
                    filings[key].add(accn)
                    n = norm(name)
                    if n:
                        name_rows[key][n] += 1
        print("  map pass: %-42s cusip6 so far %d"
              % (os.path.basename(path), len(filings)))

    # rule 1 - the modal name only
    modal: dict[str, set[str]] = defaultdict(set)
    modal_tokens: dict[str, set[str]] = defaultdict(set)
    modal_tight: dict[str, set[str]] = defaultdict(set)
    modal_name: dict[str, str] = {}
    for key, counts in name_rows.items():
        best_name = max(counts.items(), key=lambda kv: kv[1])[0]
        modal_name[key] = best_name
        modal[best_name].add(key)
        modal_tokens[" ".join(sorted(set(best_name.split())))].add(key)
        modal_tight[best_name.replace(" ", "")].add(key)

    # Containment index: EDGAR's tokens as a subset of the modal name's tokens.
    # EDGAR writes "BERKSHIRE HATHAWAY INC" while 13F's modal name is
    # "BERKSHIRE HATHAWAY DEL" - the state qualifier as a bare word, which no
    # amount of suffix stripping catches.
    modal_sets = {key: frozenset(name.split()) for key, name in modal_name.items()}

    scored = []
    for cik, variants in cik_names.items():
        seen = {}
        for variant in variants:
            n = norm(variant)
            if not n:
                continue
            for key in modal.get(n, ()):
                seen[key] = max(seen.get(key, 0), 3)
            for key in modal_tight.get(n.replace(" ", ""), ()):
                seen[key] = max(seen.get(key, 0), 3)
            for key in modal_tokens.get(token_key(variant), ()):
                seen[key] = max(seen.get(key, 0), 1)
            mine = frozenset(n.split())
            if len(mine) >= 2:
                for key, theirs in modal_sets.items():
                    if mine < theirs or theirs < mine:
                        seen[key] = max(seen.get(key, 0), 2)
        for key, tier in seen.items():
            scored.append((len(filings[key]), tier, key, cik))

    # rule 3 - strict one-to-one. Ranked by how widely the CUSIP is actually
    # held, with the name-match tier breaking ties: among names that match at
    # all, a CUSIP in 29,592 filings is the S&P constituent and one in 7 is a
    # typo. Name matching decides candidacy; popularity decides between
    # candidates.
    scored.sort(reverse=True)
    mapping: dict[str, int] = {}
    taken_cik: set[int] = set()
    matched = ambiguous = 0
    for _, tier, key, cik in scored:
        if key in mapping or cik in taken_cik:
            continue
        mapping[key] = cik
        taken_cik.add(cik)
        matched += 1
        if tier == 1:
            ambiguous += 1
    print("  mapped %d issuers (%d had >1 candidate, most-held taken)"
          % (matched, ambiguous))

    # Validate rather than trust: check the map against hand-verified CUSIP6s.
    cik_to_cusip = {v: k for k, v in mapping.items()}
    right = wrong = absent = 0
    for cik, expected in KNOWN_CUSIP6.items():
        if cik not in cik_names:
            # Not in this universe at all - checking it would test the
            # validation list, not the map. Exxon (34088) is such a case.
            continue
        got = cik_to_cusip.get(cik)
        if got is None:
            absent += 1
            print("    VALIDATION: cik %d not mapped (expected %s)" % (cik, expected))
        elif got == expected:
            right += 1
        else:
            wrong += 1
            print("    VALIDATION MISMATCH: cik %d expected %s got %s"
                  % (cik, expected, got))
    print("  validation on %d hand-checked issuers: %d correct, %d WRONG, %d absent"
          % (len(KNOWN_CUSIP6), right, wrong, absent))
    if wrong:
        raise SystemExit("CUSIP map failed validation - refusing to build a feature "
                         "on a mapping known to be wrong")
    return mapping


def build_events(paths, cusip_to_cik) -> pd.DataFrame:
    wanted = set(cusip_to_cik)
    frames = []
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            submission = pd.read_csv(
                archive.open(member(archive, "SUBMISSION.tsv")), sep="\t", encoding="latin-1",
                usecols=["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE",
                         "CIK", "PERIODOFREPORT"],
                dtype={"ACCESSION_NUMBER": str, "SUBMISSIONTYPE": str}, low_memory=False)
            submission = submission[submission["SUBMISSIONTYPE"].isin(HOLDING_FORMS)]
            if submission.empty:
                continue
            keep_accn = set(submission["ACCESSION_NUMBER"])

            parts = []
            reader = pd.read_csv(
                archive.open(member(archive, "INFOTABLE.tsv")), sep="\t", encoding="latin-1",
                usecols=["ACCESSION_NUMBER", "CUSIP", "SSHPRNAMT",
                         "SSHPRNAMTTYPE", "PUTCALL"],
                dtype={"ACCESSION_NUMBER": str, "CUSIP": str,
                       "SSHPRNAMTTYPE": str, "PUTCALL": str},
                chunksize=1_000_000, low_memory=False)
            for chunk in reader:
                chunk = chunk[chunk["PUTCALL"].isna()
                              & (chunk["SSHPRNAMTTYPE"] == "SH")
                              & chunk["ACCESSION_NUMBER"].isin(keep_accn)]
                if chunk.empty:
                    continue
                key = chunk["CUSIP"].map(cusip6)
                chunk = chunk.assign(cusip6=key)
                chunk = chunk[chunk["cusip6"].isin(wanted)]
                if chunk.empty:
                    continue
                chunk["shares"] = pd.to_numeric(chunk["SSHPRNAMT"], errors="coerce")
                parts.append(chunk[["ACCESSION_NUMBER", "cusip6", "shares"]])
            if not parts:
                continue
            holdings = pd.concat(parts, ignore_index=True)
            # one filer may list a name on several lines
            holdings = (holdings.groupby(["ACCESSION_NUMBER", "cusip6"], as_index=False)
                        ["shares"].sum())
            merged = holdings.merge(submission, on="ACCESSION_NUMBER", how="inner")
            frames.append(merged)
            print("  %-42s holdings rows %7d" % (os.path.basename(path), len(merged)))

    events = pd.concat(frames, ignore_index=True)
    events = events.rename(columns={"ACCESSION_NUMBER": "accn", "CIK": "filer",
                                    "FILING_DATE": "filed",
                                    "PERIODOFREPORT": "period"})
    events["filed"] = pd.to_datetime(events["filed"], format="%d-%b-%Y",
                                     errors="coerce")
    events["period"] = pd.to_datetime(events["period"], format="%d-%b-%Y",
                                      errors="coerce")
    events["filer"] = pd.to_numeric(events["filer"], errors="coerce")
    events = events.dropna(subset=["filed", "period", "filer", "shares"])
    events = events[events["shares"] > 0]
    events["filer"] = events["filer"].astype("int64")
    events["cik"] = events["cusip6"].map(cusip_to_cik).astype("int64")
    events = events[["cik", "cusip6", "filer", "period", "filed", "accn", "shares"]]
    # a filer may file the same period more than once in one archive window
    events = events.sort_values(["cik", "period", "filer", "filed", "accn"],
                                kind="mergesort").reset_index(drop=True)
    return events


def main() -> int:
    started = time.time()
    symbol_to_cik, cik_names = universe()
    paths = archives()
    print("universe %d symbols / %d issuers, %d archives"
          % (len(symbol_to_cik), len(cik_names), len(paths)))

    # Pool the map over archives spread across the whole era, so a name that
    # listed in 2021 is matchable. Every 6th archive plus the last.
    sample = sorted(set(paths[::6] + paths[-1:]))
    print("\nstage 1 - CUSIP6 map from %d sampled archives" % len(sample))
    cusip_to_cik = build_map(sample, cik_names)
    json.dump({k: int(v) for k, v in cusip_to_cik.items()}, open(OUT_MAP, "w"),
              indent=0)

    print("\nstage 2 - holdings events from %d archives" % len(paths))
    events = build_events(paths, cusip_to_cik)
    events.to_parquet(OUT_PARQUET, index=False)

    periods = sorted(events["period"].unique())
    payload = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "seconds": round(time.time() - started, 1),
        "archives": len(paths),
        "map_sample_archives": [os.path.basename(p) for p in sample],
        "issuers_mapped": len(cusip_to_cik),
        "issuers_in_universe": len(cik_names),
        "map_rate": round(len(cusip_to_cik) / len(cik_names), 4),
        "event_rows": int(len(events)),
        "distinct_filers": int(events["filer"].nunique()),
        "issuers_with_holdings": int(events["cik"].nunique()),
        "periods": len(periods),
        "first_period": str(pd.Timestamp(periods[0]).date()),
        "last_period": str(pd.Timestamp(periods[-1]).date()),
        "first_filed": str(events["filed"].min().date()),
        "last_filed": str(events["filed"].max().date()),
    }
    OUT_META.write_text(json.dumps(payload, indent=2))
    print()
    for key, value in payload.items():
        if key != "map_sample_archives":
            print("%-26s %s" % (key, value))
    return 0


if __name__ == "__main__":
    sys.exit(main())
