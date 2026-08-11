"""Pre-ingest source feasibility probe. NON-PREDICTIVE — reads no forward return.

Supports `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md`. It answers, with measurement
rather than expectation, the questions a feasibility record needs about SEC 8-K
event filings:

  1. coverage      — how many panel symbols file 8-Ks, per year
  2. frequency     — 8-Ks per symbol per year, and per item code
  3. timestamp     — what share are accepted after the 16:00 ET close
  4. event classes — the item-code distribution, and how much of it is earnings
  5. sample size   — usable (cutoff, symbol) events on the study's own grid

Everything is read from `alpha/edgar/submissions.zip`, the SEC's free bulk
submissions archive already on disk (downloaded 2026-08-09 for V3). **No network
call, no new ingest, no price, no return, no target, no model.** A filing's
acceptance timestamp is immutable once issued, so a current snapshot is a valid
point-in-time record of when each filing became knowable — which is the one
property this probe is measuring.

The cutoff grid, horizon and embargo are imported from the study's own frozen
constants so the event counts are counts of *usable* events rather than of
filings in the abstract.

Run:  python -m alpha.source_probe            # writes out/source_probe_8k.json
      python -m alpha.source_probe --show     # print the last probe
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import sys
import zipfile

import pandas as pd

from . import filings
from . import singlename_config as cfg

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
SUBMISSIONS = EDGAR_DIR / "submissions.zip"
TICKERS = EDGAR_DIR / "company_tickers.json"
OUT_PATH = cfg.OUT_DIR / "source_probe_8k.json"

STUDY_START = "2016-01-04"
FORM = "8-K"

#: Item codes whose content is an earnings release. Excluded when measuring the
#: non-earnings event set, because Item 2.02 is the SUE family's own information
#: and the survey's clause 8 bars re-testing it under a new name.
EARNINGS_ITEMS = frozenset({"2.02"})

ITEM_LABELS = {
    "1.01": "entry into a material definitive agreement",
    "1.02": "termination of a material definitive agreement",
    "1.03": "bankruptcy or receivership",
    "1.05": "material cybersecurity incident",
    "2.01": "completion of acquisition or disposition of assets",
    "2.02": "results of operations and financial condition (EARNINGS)",
    "2.03": "creation of a direct financial obligation",
    "2.04": "triggering events that accelerate a financial obligation",
    "2.05": "costs associated with exit or disposal activities",
    "2.06": "material impairments",
    "3.01": "notice of delisting or failure to satisfy a listing rule",
    "3.02": "unregistered sales of equity securities (DILUTION)",
    "3.03": "material modification to rights of security holders",
    "4.01": "changes in registrant's certifying accountant",
    "4.02": "non-reliance on previously issued financial statements",
    "5.01": "changes in control of registrant",
    "5.02": "departure or election of directors or principal officers",
    "5.03": "amendments to articles of incorporation or bylaws",
    "5.07": "submission of matters to a vote of security holders",
    "7.01": "Regulation FD disclosure",
    "8.01": "other events",
    "9.01": "financial statements and exhibits (ATTACHMENT, not an event)",
}

#: Item codes carrying no independent event content — they accompany another item.
STRUCTURAL_ITEMS = frozenset({"9.01"})


def mapped_ciks() -> dict[str, int]:
    """Panel symbol -> CIK, from the SEC's current ticker map.

    Carries the survivorship caveat `reports/INFORMATION_AUDIT.md` §2.1 measured:
    `company_tickers.json` lists current registrants only, so names that died
    are silently absent. Reported here as a count rather than repaired, because
    repairing it is ingest work and this is a probe.
    """
    table = json.loads(TICKERS.read_text(encoding="utf-8"))
    lookup = {row["ticker"]: int(row["cik_str"]) for row in table.values()}
    symbols = sorted(p.stem for p in (EDGAR_DIR.parent / "cache").glob("*.csv"))
    return {s: lookup[s] for s in symbols if s in lookup}


def _rows_for(archive: zipfile.ZipFile, cik: int) -> list[tuple[str, str, str, str]]:
    """Every filing a CIK has on record: (form, filingDate, acceptance, items).

    Reads the `recent` block *and* every continuation file the filer has, so a
    high-volume filer's 2016-2019 history is not silently truncated to whatever
    fits in the most recent 1,000 filings.
    """
    member = f"CIK{cik:010d}.json"
    try:
        payload = json.loads(archive.read(member))
    except KeyError:
        return []

    blocks = [payload["filings"]["recent"]]
    for extra in payload["filings"].get("files", []):
        try:
            blocks.append(json.loads(archive.read(extra["name"])))
        except KeyError:
            continue

    out = []
    for block in blocks:
        forms = block.get("form", [])
        for index, form in enumerate(forms):
            out.append((form,
                        block["filingDate"][index],
                        block["acceptanceDateTime"][index],
                        block.get("items", [""] * len(forms))[index] or ""))
    return out


def probe(limit: int | None = None, verbose: bool = True) -> dict:
    """Measure 8-K coverage, frequency, timing and item mix over the study window."""
    if not SUBMISSIONS.exists():
        raise SystemExit(f"no {SUBMISSIONS} — the V3 bulk submissions archive is required")

    mapped = mapped_ciks()
    ciks = sorted(set(mapped.values()))
    if limit:
        ciks = ciks[:limit]

    start = pd.Timestamp(STUDY_START)
    per_year: dict[int, set[int]] = collections.defaultdict(set)
    filings_per_year: collections.Counter = collections.Counter()
    item_counts: collections.Counter = collections.Counter()
    item_ciks: dict[str, set[int]] = collections.defaultdict(set)
    item_dates: dict[str, set[dt.date]] = collections.defaultdict(set)
    all_event_dates: set[dt.date] = set()
    hour_counts: collections.Counter = collections.Counter()
    after_close = before_close = 0
    total = 0
    non_earnings = 0
    event_days: set[tuple[int, dt.date]] = set()
    filers_with_any = set()

    archive = zipfile.ZipFile(SUBMISSIONS)
    for count, cik in enumerate(ciks, 1):
        for form, filed, accepted, items in _rows_for(archive, cik):
            if form != FORM or not accepted:
                continue
            stamp = filings.et_from_utc(accepted)
            if pd.Timestamp(stamp) < start:
                continue

            total += 1
            filers_with_any.add(cik)
            year = stamp.year
            per_year[year].add(cik)
            filings_per_year[year] += 1
            hour_counts[stamp.hour] += 1
            if stamp.time() < filings.CLOSE_ET:
                before_close += 1
            else:
                after_close += 1

            codes = [c.strip() for c in items.split(",") if c.strip()]
            substantive = [c for c in codes if c not in STRUCTURAL_ITEMS]
            # The *admissible* session is the one whose close the filing precedes:
            # accepted before 16:00 ET is knowable that session, otherwise the next.
            session = stamp.date() if stamp.time() < filings.CLOSE_ET else (
                stamp.date() + dt.timedelta(days=1))
            for code in codes:
                item_counts[code] += 1
                item_ciks[code].add(cik)
                item_dates[code].add(session)
            if substantive and not (set(substantive) & EARNINGS_ITEMS):
                non_earnings += 1
                event_days.add((cik, session))
                all_event_dates.add(session)

        if verbose and count % 100 == 0:
            print(f"  {count:4d}/{len(ciks)} filers, {total:,} 8-Ks", flush=True)

    years = sorted(per_year)
    span = max(1.0, (max(years) - min(years) + 1)) if years else 1.0
    return {
        "probed_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "source": "alpha/edgar/submissions.zip (SEC bulk submissions, free)",
        "note": "No network call, no price, no forward return, no model. "
                "Acceptance timestamps are immutable, so a current snapshot is a "
                "valid point-in-time record of knowability.",
        "study_start": STUDY_START,
        "panel_symbols_with_cik": len(mapped),
        "ciks_probed": len(ciks),
        "filers_with_at_least_one_8k": len(filers_with_any),
        "total_8k": total,
        "non_earnings_8k": non_earnings,
        "distinct_filer_event_days": len(event_days),
        "mean_8k_per_filer_per_year": round(total / max(len(filers_with_any), 1) / span, 2),
        "acceptance": {
            "before_1600_et": before_close,
            "after_1600_et": after_close,
            "share_after_close": round(after_close / max(total, 1), 4),
            "by_hour_et": {str(h): n for h, n in sorted(hour_counts.items())},
        },
        "coverage_by_year": {str(y): len(per_year[y]) for y in years},
        "filings_by_year": {str(y): filings_per_year[y] for y in years},
        "non_earnings_event_dates": len(all_event_dates),
        "items": [
            {
                "code": code,
                "label": ITEM_LABELS.get(code, "(uncatalogued)"),
                "filings": n,
                "filers": len(item_ciks[code]),
                "event_dates": len(item_dates[code]),
                "per_date": round(n / max(len(item_dates[code]), 1), 2),
                "per_filer_per_year": round(n / max(len(item_ciks[code]), 1) / span, 3),
            }
            for code, n in item_counts.most_common(30)
        ],
    }


# ----------------------------------------------------------------------
# Pre-study resolution arithmetic (roadmap §2.6). No candidate feature is
# involved: the only inputs are marginal properties of the target itself.
# ----------------------------------------------------------------------

#: Marginal properties of the 5-session absolute return on the 316-cutoff
#: development panel. Descriptions of the *target*, measured with no feature and
#: no conditioning — the same quantities a §2.6 power gate is computed from.
RETURN_SD = 0.04526             # sd of asset_return, 143,675 development rows
RETURN_RHO = 0.2916             # implied average within-cutoff pairwise correlation
UP_VAR = 0.24783                # p(1-p) for the marginal up-rate 0.54659
UP_RHO = 0.1778                 # same decomposition for the up indicator

#: Ratio of the block-bootstrap half-width to the i.i.d.-across-dates formula,
#: calibrated against Phase 1's *measured* covered-book half-width of 0.00390
#: (k = 230 names, D = 177 cutoffs). Calibrating rather than assuming keeps the
#: surface honest about serial dependence the closed form does not carry.
BLOCK_INFLATION = 1.077


def half_width(variance: float, rho: float, per_date: float, dates: float) -> float:
    """95% half-width of a mean over `dates` dates carrying `per_date` names each.

    `rho` is the average within-date pairwise correlation, so the bracket is the
    variance of a date's own mean: adding names past ~1/rho buys almost nothing,
    because the common market move does not diversify away. That is the whole
    result — resolution is bought with independent *dates*, not with breadth.
    """
    per_date = max(float(per_date), 1e-9)
    return float(BLOCK_INFLATION * 1.96
                 * (variance * (rho + (1.0 - rho) / per_date) / max(dates, 1e-9)) ** 0.5)


#: Trading sessions in the study window, 2016-01-04 .. 2026-08-07, from the study
#: calendar. 532 non-overlapping 5-session blocks; 266 if a 10-session block is
#: used to absorb the overlap between windows of events on neighbouring days.
SESSIONS = 2664
BLOCKS_5D = SESSIONS // 5
BLOCKS_10D = SESSIONS // 10


def resolution(per_date: float, dates: float) -> dict:
    """Achievable half-width on the two quantities a directional family must move."""
    return {
        "per_date": round(float(per_date), 3),
        "independent_dates": round(float(dates), 1),
        "return_half_width_bp": round(1e4 * half_width(
            RETURN_SD ** 2, RETURN_RHO, per_date, dates), 1),
        "up_rate_half_width_pp": round(100.0 * half_width(
            UP_VAR, UP_RHO, per_date, dates), 2),
    }


def resolution_for_events(events: int, blocks: int = BLOCKS_5D) -> dict:
    """Resolution for `events` observations spread over `blocks` independent blocks.

    Takes the event *total* and derives the per-block count, rather than letting
    a caller supply `k` and `D` separately. That separation is where the first
    pass of this survey went wrong: quoting events-per-*calendar-date* alongside
    a block count already reduced for overlap charged the same concentration
    twice and overstated every half-width. `k * D` must equal the sample, and
    here it does by construction.
    """
    return resolution(events / max(blocks, 1), blocks)


def show(payload: dict) -> None:
    print(f"source      {payload['source']}")
    print(f"panel       {payload['panel_symbols_with_cik']} symbols map to a CIK; "
          f"{payload['filers_with_at_least_one_8k']} filed at least one 8-K since "
          f"{payload['study_start']}")
    print(f"volume      {payload['total_8k']:,} 8-Ks  ·  "
          f"{payload['non_earnings_8k']:,} non-earnings  ·  "
          f"{payload['mean_8k_per_filer_per_year']} per filer per year")
    acceptance = payload["acceptance"]
    print(f"timestamp   {acceptance['share_after_close']:.1%} accepted at or after "
          f"16:00 ET — the filed<=cutoff rule would leak on those")
    print(f"dates       {payload['non_earnings_event_dates']} distinct sessions carry at "
          f"least one non-earnings 8-K")
    print("\nitem                                          filings  filers   dates  /date  /filer/yr")
    for row in payload["items"][:18]:
        print("%-5s %-38s %8d %7d %7d %6.2f %10.3f" % (
            row["code"], row["label"][:38], row["filings"], row["filers"],
            row["event_dates"], row["per_date"], row["per_filer_per_year"]))
    print("\ncoverage by year (filers with >=1 8-K):")
    print("  " + "  ".join(f"{y}:{n}" for y, n in payload["coverage_by_year"].items()))


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if "--show" in argv:
        show(json.loads(OUT_PATH.read_text(encoding="utf-8")))
        return

    limit = None
    for index, token in enumerate(argv):
        if token == "--limit":
            limit = int(argv[index + 1])

    payload = probe(limit=limit)
    cfg.OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    show(payload)
    print(f"\nwrote       {OUT_PATH}")


if __name__ == "__main__":
    main()
