"""Build the V3 filings facts table from the EDGAR bulk archives.

Inputs (all free, all already on disk in `alpha/edgar/`):

* `companyfacts.zip`  — every XBRL fact per filer, with `filed` and accession
* `submissions.zip`   — every filing's `acceptanceDateTime` per filer
* `company_tickers.json` — the SEC's current ticker -> CIK map (fetched once,
  kept beside the zips so the build is reproducible offline)

Output: `alpha/edgar/facts.parquet` — one row per *vintage* of a fact, with the
acceptance timestamp joined and converted to naive US/Eastern, plus
`filings_meta.json` recording what was kept, what was dropped and why.

The two audit findings this build exists to respect
(`reports/INFORMATION_AUDIT.md` §1, §2.1):

1. **`filed` is a date, not a knowability timestamp.** 51.8% of 10-K/10-Q
   filings are accepted after the close of their own filing date. So every
   fact is joined to its accession's `acceptanceDateTime`; a fact whose
   accession cannot be resolved is DROPPED and counted — inadmissible, not
   approximated (roadmap §2.1).
2. **Identity is CIK, never ticker.** Tickers are reused and the current
   ticker map covers only current registrants. The 32 cache symbols that do
   not map (dead names — mergers mostly, plus the sector ETFs and ^VIX which
   correctly have no filings) are recorded by name in the meta, because a
   silent 5% survivorship hole is how a fundamentals panel quietly flatters
   itself.

Knowability semantics, stated rather than hidden: acceptance of the 10-K/10-Q
is *later* than the 8-K earnings press release that usually precedes it by
days to weeks. Features built on this table are therefore conservative —
information enters the panel later than the market first saw it, never
earlier. That direction of error costs signal, not validity.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.request
import zipfile

import pandas as pd

from . import filings

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
CACHE_DIR = pathlib.Path(__file__).resolve().parent / "cache"
USER_AGENT = {"User-Agent": "research contact onur.celk@gmail.com"}

#: Concepts ingested, by taxonomy. A deliberate superset of what the feature
#: layer will use; per-firm fallback chains (Revenues vs the post-606 tag) are
#: resolved at feature time, not here — the ingest keeps every candidate tag so
#: that choice stays visible and testable.
CONCEPTS = {
    "us-gaap": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "Assets",
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ),
    "dei": (
        "EntityCommonStockSharesOutstanding",
    ),
}

#: Units accepted per concept kind. Anything else (a stray EUR filer, a
#: shares-based revenue tag) is dropped and counted.
UNITS = {"USD", "USD/shares", "shares"}

#: Statement forms. 8-K press releases are not in companyfacts' XBRL history at
#: usable depth; foreign-filer forms are out of scope for this US universe.
FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}

#: Upstream gaps in the SEC's own ticker map, each verified against the
#: submissions API before being added (the API's `tickers` field for the CIK
#: must list the symbol). AEP: absent from company_tickers.json on 2026-08-09
#: while data.sec.gov/submissions/CIK0000004904.json lists tickers=['AEP'].
TICKER_OVERRIDES = {"AEP": 4904}


def cache_symbols() -> list[str]:
    return sorted(p.stem for p in CACHE_DIR.glob("*.csv") if not p.stem.startswith("_"))


def ticker_map() -> dict[str, int]:
    """Current ticker -> CIK, fetched once and kept beside the zips."""
    path = EDGAR_DIR / "company_tickers.json"
    if not path.exists():
        request = urllib.request.Request(
            "https://www.sec.gov/files/company_tickers.json", headers=USER_AGENT)
        path.write_bytes(urllib.request.urlopen(request, timeout=60).read())
    table = json.loads(path.read_text())
    out = {row["ticker"]: int(row["cik_str"]) for row in table.values()}
    out.update(TICKER_OVERRIDES)
    return out


def acceptance_map(archive: zipfile.ZipFile, cik: int) -> dict[str, dt.datetime]:
    """accession -> acceptance (naive ET) for one filer, across every shard."""
    out: dict[str, dt.datetime] = {}
    member = f"CIK{cik:010d}.json"
    try:
        head = json.loads(archive.read(member))
    except KeyError:
        return out
    shards = [head["filings"]["recent"]]
    for extra in head["filings"].get("files", ()):
        try:
            shards.append(json.loads(archive.read(extra["name"])))
        except KeyError:
            continue
    for shard in shards:
        accessions = shard["accessionNumber"]
        accepted = shard["acceptanceDateTime"]
        for accession, stamp in zip(accessions, accepted):
            if stamp:
                out[accession] = filings.et_from_utc(stamp)
    return out


def facts_for(archive: zipfile.ZipFile, cik: int) -> list[dict]:
    """Every vintage of every ingested concept for one filer. No acceptance yet."""
    try:
        payload = json.loads(archive.read(f"CIK{cik:010d}.json"))
    except KeyError:
        return []
    rows: list[dict] = []
    for taxonomy, concepts in CONCEPTS.items():
        branch = payload.get("facts", {}).get(taxonomy, {})
        for concept in concepts:
            for unit, entries in branch.get(concept, {}).get("units", {}).items():
                if unit not in UNITS:
                    continue
                for entry in entries:
                    if entry.get("form") not in FORMS:
                        continue
                    rows.append(dict(
                        cik=cik, concept=concept, unit=unit,
                        start=entry.get("start"), end=entry.get("end"),
                        value=entry.get("val"), accn=entry.get("accn"),
                        form=entry.get("form"), fy=entry.get("fy"),
                        fp=entry.get("fp"), filed=entry.get("filed"),
                    ))
    return rows


def build() -> dict:
    started = time.time()
    symbols = cache_symbols()
    tickers = ticker_map()
    mapped = {s: tickers[s] for s in symbols if s in tickers}
    unmapped = sorted(set(symbols) - set(mapped))

    facts_zip = zipfile.ZipFile(EDGAR_DIR / "companyfacts.zip")
    subs_zip = zipfile.ZipFile(EDGAR_DIR / "submissions.zip")

    all_rows: list[dict] = []
    dropped_no_acceptance = 0
    filers_with_facts = 0
    ciks = sorted(set(mapped.values()))
    for count, cik in enumerate(ciks, 1):
        rows = facts_for(facts_zip, cik)
        if rows:
            filers_with_facts += 1
        acceptance = acceptance_map(subs_zip, cik) if rows else {}
        for row in rows:
            when = acceptance.get(row["accn"])
            if when is None:
                dropped_no_acceptance += 1     # inadmissible, not approximated
                continue
            row["accepted"] = when
            all_rows.append(row)
        if count % 100 == 0:
            print("  ... %d/%d filers, %d facts" % (count, len(ciks), len(all_rows)))

    frame = pd.DataFrame(all_rows)
    for column in ("start", "end", "filed"):
        frame[column] = pd.to_datetime(frame[column])
    frame["accepted"] = pd.to_datetime(frame["accepted"])
    frame = frame.sort_values(["cik", "concept", "accepted", "accn"],
                              kind="mergesort").reset_index(drop=True)

    frame.to_parquet(EDGAR_DIR / "facts.parquet", index=False)

    cik_to_symbols = collections.defaultdict(list)
    for symbol, cik in mapped.items():
        cik_to_symbols[cik].append(symbol)
    meta = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "seconds": round(time.time() - started, 1),
        "cache_symbols": len(symbols),
        "mapped_symbols": len(mapped),
        "unmapped_symbols": unmapped,
        "ciks": len(ciks),
        "filers_with_facts": filers_with_facts,
        "facts_kept": int(len(frame)),
        "facts_dropped_no_acceptance": int(dropped_no_acceptance),
        "accepted_after_close_share": round(float(
            (frame["accepted"].dt.time >= filings.CLOSE_ET).mean()), 4),
        "first_accepted": str(frame["accepted"].min()),
        "last_accepted": str(frame["accepted"].max()),
        "concepts": {c: int(n) for c, n in
                     frame["concept"].value_counts().items()},
        "forms": {c: int(n) for c, n in frame["form"].value_counts().items()},
        "symbol_to_cik": {s: mapped[s] for s in sorted(mapped)},
    }
    (EDGAR_DIR / "filings_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    meta = build()
    for key in ("cache_symbols", "mapped_symbols", "ciks", "filers_with_facts",
                "facts_kept", "facts_dropped_no_acceptance",
                "accepted_after_close_share", "first_accepted", "last_accepted",
                "seconds"):
        print("%-32s %s" % (key, meta[key]))
    print("unmapped: %s" % " ".join(meta["unmapped_symbols"]))


if __name__ == "__main__":
    sys.exit(main())
