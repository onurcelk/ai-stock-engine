"""Build the Family 2 open-market-purchase table from SEC insider bulk data.

Implements ONLY what `alpha/V3_FAMILY2_PREREGISTRATION.md` §1-§3 froze:

* **non-derivative transactions only** (`NONDERIV_TRANS.tsv`), which excludes
  options and every other derivative instrument by construction;
* **`TRANS_CODE == 'P'`** — open-market purchase. This one filter excludes
  awards (A), option exercises (M), tax withholding (F), gifts (G), transfers
  and every other code;
* **acquisitions only** (`TRANS_ACQUIRED_DISP_CD == 'A'`), so a disposition
  never enters with a positive sign;
* **sales excluded** — code S is simply not admitted.

No role weighting is applied: `REPORTINGOWNER.tsv` is not read at all, so
officer/director/10%-holder status cannot influence the result even by accident.

Timestamps. The bulk sets carry `FILING_DATE` but **not** acceptance time, and
§3 of the pre-registration makes acceptance the admissibility key. So every
accession is joined to its `acceptanceDateTime` from `submissions.zip`, and an
accession with no acceptance timestamp is **dropped, not approximated** (§2.1) —
the same rule `build_filings.py` applies.

Both dates are kept and they do different jobs: `accepted` decides *whether* a
filing may be seen at a cutoff; `trans_date` decides *whether it falls in the
90-day lookback window* once it may be seen.

Output: `alpha/edgar/insider_purchases.parquet` and `insider_meta.json`.
ASCII stdout only.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import pathlib
import sys
import time
import zipfile

import pandas as pd

from . import filings

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
INSIDER_DIR = EDGAR_DIR / "insider"
OUT_PARQUET = EDGAR_DIR / "insider_purchases.parquet"
OUT_META = EDGAR_DIR / "insider_meta.json"

PURCHASE_CODE = "P"
ACQUIRED = "A"


def acceptance_index(ciks: set[int]) -> dict[str, dt.datetime]:
    """accession -> acceptance (naive ET) for Form 4s of the tracked issuers."""
    archive = zipfile.ZipFile(EDGAR_DIR / "submissions.zip")
    out: dict[str, dt.datetime] = {}
    for count, cik in enumerate(sorted(ciks), 1):
        try:
            head = json.loads(archive.read("CIK%010d.json" % cik))
        except KeyError:
            continue
        shards = [head["filings"]["recent"]]
        for extra in head["filings"].get("files", ()):
            try:
                shards.append(json.loads(archive.read(extra["name"])))
            except KeyError:
                continue
        for shard in shards:
            forms = shard["form"]
            accessions = shard["accessionNumber"]
            accepted = shard["acceptanceDateTime"]
            for j in range(len(forms)):
                if forms[j] == "4" and accepted[j]:
                    out[accessions[j]] = filings.et_from_utc(accepted[j])
        if count % 200 == 0:
            print("  ... acceptance index %d/%d issuers, %d accessions"
                  % (count, len(ciks), len(out)))
    return out


def build() -> dict:
    started = time.time()
    meta = json.load(open(EDGAR_DIR / "filings_meta.json"))
    symbol_to_cik = {s: int(c) for s, c in meta["symbol_to_cik"].items()}
    ciks = set(symbol_to_cik.values())

    print("building acceptance index for %d issuers ..." % len(ciks))
    accepted_by_accession = acceptance_index(ciks)
    print("  %d Form 4 accessions with an acceptance timestamp" % len(accepted_by_accession))

    archives = sorted(glob.glob(str(INSIDER_DIR / "*_form345.zip")))
    print("\nparsing %d quarterly archives ..." % len(archives))

    frames, quarters = [], []
    raw_rows = purchase_rows = 0
    for path in archives:
        quarter = os.path.basename(path).split("_")[0]
        with zipfile.ZipFile(path) as archive:
            submission = pd.read_csv(
                archive.open("SUBMISSION.tsv"), sep="\t", encoding="latin-1",
                usecols=["ACCESSION_NUMBER", "DOCUMENT_TYPE", "ISSUERCIK"],
                dtype={"ACCESSION_NUMBER": str, "DOCUMENT_TYPE": str},
                low_memory=False)
            submission = submission[(submission["DOCUMENT_TYPE"] == "4")
                                    & submission["ISSUERCIK"].isin(ciks)]
            if submission.empty:
                continue
            transactions = pd.read_csv(
                archive.open("NONDERIV_TRANS.tsv"), sep="\t", encoding="latin-1",
                usecols=["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE",
                         "TRANS_SHARES", "TRANS_PRICEPERSHARE",
                         "TRANS_ACQUIRED_DISP_CD"],
                dtype={"ACCESSION_NUMBER": str, "TRANS_CODE": str,
                       "TRANS_ACQUIRED_DISP_CD": str},
                low_memory=False)
        raw_rows += len(transactions)
        transactions = transactions[
            (transactions["TRANS_CODE"] == PURCHASE_CODE)
            & (transactions["TRANS_ACQUIRED_DISP_CD"] == ACQUIRED)]
        if transactions.empty:
            continue
        merged = transactions.merge(submission[["ACCESSION_NUMBER", "ISSUERCIK"]],
                                    on="ACCESSION_NUMBER", how="inner")
        purchase_rows += len(merged)
        merged["quarter"] = quarter
        frames.append(merged)
        quarters.append(quarter)
        print("  %-8s raw %7d -> purchases %6d" % (quarter, len(transactions), len(merged)))

    table = pd.concat(frames, ignore_index=True)
    table = table.rename(columns={"ACCESSION_NUMBER": "accn", "ISSUERCIK": "cik",
                                  "TRANS_DATE": "trans_date",
                                  "TRANS_SHARES": "shares",
                                  "TRANS_PRICEPERSHARE": "price"})
    table["cik"] = table["cik"].astype(int)
    table["trans_date"] = pd.to_datetime(table["trans_date"], errors="coerce")
    table["shares"] = pd.to_numeric(table["shares"], errors="coerce")
    table["price"] = pd.to_numeric(table["price"], errors="coerce")

    before = len(table)
    table["accepted"] = table["accn"].map(accepted_by_accession)
    dropped_no_acceptance = int(table["accepted"].isna().sum())
    table = table[table["accepted"].notna()]

    dropped_bad_values = int((table["shares"].isna() | table["price"].isna()
                              | (table["shares"] <= 0) | (table["price"] <= 0)).sum())
    table = table[(table["shares"] > 0) & (table["price"] > 0)]
    table["value"] = table["shares"] * table["price"]
    table["accepted"] = pd.to_datetime(table["accepted"])

    table = table[["cik", "accn", "trans_date", "accepted", "shares", "price", "value"]]
    table = table.sort_values(["cik", "accepted", "accn"],
                              kind="mergesort").reset_index(drop=True)
    table.to_parquet(OUT_PARQUET, index=False)

    after_close = float((table["accepted"].dt.time >= filings.CLOSE_ET).mean())
    lag = (table["accepted"].dt.normalize() - table["trans_date"]).dt.days
    payload = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "seconds": round(time.time() - started, 1),
        "quarters": quarters,
        "first_quarter": quarters[0], "last_quarter": quarters[-1],
        "raw_nonderiv_rows": int(raw_rows),
        "purchase_rows_before_join": int(before),
        "dropped_no_acceptance": dropped_no_acceptance,
        "dropped_bad_shares_or_price": dropped_bad_values,
        "purchases_kept": int(len(table)),
        "issuers_with_purchases": int(table["cik"].nunique()),
        "first_trans_date": str(table["trans_date"].min().date()),
        "last_trans_date": str(table["trans_date"].max().date()),
        "last_accepted": str(table["accepted"].max()),
        "accepted_after_close_share": round(after_close, 4),
        "trans_to_acceptance_lag_median_days": float(lag.median()),
    }
    OUT_META.write_text(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    payload = build()
    print()
    for key in ("quarters", "raw_nonderiv_rows", "purchase_rows_before_join",
                "dropped_no_acceptance", "dropped_bad_shares_or_price",
                "purchases_kept", "issuers_with_purchases", "first_trans_date",
                "last_trans_date", "last_accepted", "accepted_after_close_share",
                "trans_to_acceptance_lag_median_days", "seconds"):
        value = payload[key]
        if key == "quarters":
            value = "%d (%s .. %s)" % (len(value), value[0], value[-1])
        print("%-36s %s" % (key, value))
    return 0


if __name__ == "__main__":
    sys.exit(main())
