"""Family 10 Stage 1: the survivorship-safe SEC 8-K adverse-event panel.

**NON-PREDICTIVE.** No price is read, no forward return is computed, no target
is touched, no model is fitted. This module builds the *left-hand side* of an
experiment that has not been authorised and must not be run.

Three rules define the panel, all frozen here before any outcome exists.

**1. The event.** An 8-K carrying at least one of the adverse items fixed by
`reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §7.1 and **not** carrying item 2.02.
The sign is the taxonomy's, not a fitted parameter, and the item set is closed:
nothing may be added or removed on the strength of a result.

**2. The clock.** `acceptanceDateTime`, converted to Eastern by
`alpha.filings.et_from_utc`, admitted at session *T* only when
`accepted < 16:00 ET on T` — the door `alpha/filings.py` already implements and
`app/tests/test_alpha_filings.py` already proves. The *information session* is
the earliest calendar session that door opens on. **57.9% of 8-Ks are accepted
at or after the close (MEASURED)**, so a `filed <= cutoff` join would leak on
the majority of this panel; there is no second door here, only the first one
evaluated forward.

**3. The identity.** CIK, joined to point-in-time index membership through
`alpha.family10_identity`. Never the present-day ticker map: 16.6% of the
tickers that were ever members since 2016 are absent from
`company_tickers.json`, and those are the delisted, merged and bankrupt names —
the adverse-event population itself. Rebuilding the panel on current symbols
would delete the observations the hypothesis is about, and the deletion would be
*correlated with the sign of the effect*.

Deduplication, frozen before any analysis (directive "MULTIPLE EVENTS"):

| case | rule |
|---|---|
| several adverse items in one filing | one event; the item codes are unioned |
| several adverse filings, one issuer, one information session | one **issuer-event**; codes unioned |
| amendments (`8-K/A`) | excluded from the panel, counted separately |
| repeated issuer events inside the 5-session horizon | the **first** is kept; a `HORIZON`-session refractory period per issuer defines the non-overlapping subset |

None of these rules can consult a return, and none of them was chosen after
seeing one.

Build:  python -m alpha.family10_panel
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import zipfile

import pandas as pd

from . import family10_identity as identity
from . import filings, pitdata, singlename_config as cfg

EDGAR_DIR = pathlib.Path(__file__).resolve().parent / "edgar"
SUBMISSIONS = EDGAR_DIR / "submissions.zip"
PANEL_PATH = cfg.OUT_DIR / "family10_events.parquet"
REPORT_PATH = cfg.OUT_DIR / "family10_stage1.json"

STUDY_START = "2016-01-04"
HORIZON = cfg.HORIZON               # 5 sessions, inherited — never re-chosen here

#: The frozen adverse set. `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §7.1.
ADVERSE_ITEMS = ("1.02", "1.03", "2.04", "2.05", "2.06", "3.01", "3.02", "4.02")

#: Structurally excluded, not filtered later: item 2.02 is the earnings release,
#: which is the V4-SUE family's own information and was REJECTED with slot 2
#: barred. An 8-K carrying 2.02 is out of this family whatever else it carries.
EXCLUDED_ITEMS = ("2.02",)

PRIMARY_FORM = "8-K"
AMENDMENT_FORM = "8-K/A"

ITEM_LABELS = {
    "1.02": "termination of a material definitive agreement",
    "1.03": "bankruptcy or receivership",
    "2.04": "triggering events that accelerate a financial obligation",
    "2.05": "costs associated with exit or disposal activities",
    "2.06": "material impairments",
    "3.01": "notice of delisting or failure to satisfy a listing rule",
    "3.02": "unregistered sales of equity securities (dilution)",
    "4.02": "non-reliance on previously issued financial statements",
}


def information_session(accepted: dt.datetime,
                        calendar: pd.DatetimeIndex) -> pd.Timestamp | None:
    """The earliest session on which `alpha.filings`' door admits this filing.

    Not a second timestamp rule — the same one, solved forwards. `FilingsBook.view`
    admits a fact at cutoff *T* iff `accepted < close_of(T)`; the first such *T*
    on the study calendar is where the fact becomes knowable. A filing accepted
    at 15:59:59 ET on a session is knowable that session; one accepted at
    16:00:00 is not, and waits for the next.
    """
    position = int(calendar.searchsorted(pd.Timestamp(accepted.date()), side="left"))
    while position < len(calendar):
        if accepted < filings.close_of(calendar[position]):
            return calendar[position]
        position += 1
    return None


def adverse_codes(items: str) -> tuple[list[str], bool]:
    """(the adverse codes in this filing, whether it is disqualified by 2.02)."""
    codes = [c.strip() for c in str(items).split(",") if c.strip()]
    return ([c for c in codes if c in ADVERSE_ITEMS],
            any(c in EXCLUDED_ITEMS for c in codes))


def _filings_for(archive: zipfile.ZipFile, cik: int) -> list[dict]:
    """Every 8-K and 8-K/A a CIK has on record, across `recent` and continuations."""
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
        size = len(forms)
        items = block.get("items", [""] * size)
        accession = block.get("accessionNumber", [""] * size)
        filed = block.get("filingDate", [""] * size)
        accepted = block.get("acceptanceDateTime", [""] * size)
        for index, form in enumerate(forms):
            if form not in (PRIMARY_FORM, AMENDMENT_FORM):
                continue
            out.append({"form": form,
                        "accn": accession[index] if index < len(accession) else "",
                        "filed": filed[index] if index < len(filed) else "",
                        "accepted_utc": accepted[index] if index < len(accepted) else "",
                        "items": (items[index] or "") if index < len(items) else ""})
    return out


def build(archive: zipfile.ZipFile, identity_map: dict,
          calendar: pd.DatetimeIndex, verbose: bool = True) -> dict:
    """The whole Stage 1 measurement. Returns the filing-level frame and its census.

    Every filing that reaches the adverse set is kept as a row, with the reason
    it was or was not admitted recorded alongside it, so the funnel from *raw
    8-K* to *eligible issuer-event* is auditable end to end rather than being a
    single surviving number.
    """
    boundaries, member_sets = identity.member_sets_by_boundary(STUDY_START)
    boundary_index = pd.DatetimeIndex(boundaries)

    by_cik: dict[int, list[str]] = collections.defaultdict(list)
    for ticker, record in identity_map["resolved"].items():
        if record["cik"] is not None:
            by_cik[int(record["cik"])].append(ticker)

    start = pd.Timestamp(STUDY_START)
    last_usable = calendar[len(calendar) - 1 - HORIZON]

    rows: list[dict] = []
    census = collections.Counter()
    amendments = collections.Counter()

    for count, (cik, tickers) in enumerate(sorted(by_cik.items()), 1):
        for record in _filings_for(archive, cik):
            if not record["accepted_utc"]:
                census["dropped_no_acceptance_timestamp"] += 1
                continue
            accepted = filings.et_from_utc(record["accepted_utc"])
            if pd.Timestamp(accepted) < start:
                continue
            codes, excluded = adverse_codes(record["items"])

            if record["form"] == AMENDMENT_FORM:
                amendments["all"] += 1
                if codes and not excluded:
                    amendments["adverse"] += 1
                continue

            census["raw_8k_in_window"] += 1
            if not codes:
                continue
            census["carries_an_adverse_item"] += 1
            if excluded:
                census["dropped_item_2_02_present"] += 1
                continue
            census["candidate_adverse_filings"] += 1

            session = information_session(accepted, calendar)
            if session is None or session > last_usable:
                census["dropped_no_usable_session"] += 1
                continue
            census["pit_eligible_filings"] += 1

            position = int(boundary_index.searchsorted(session, side="right")) - 1
            members = member_sets[position] if position >= 0 else set()
            live = sorted(t for t in tickers if t in members)
            if not live:
                census["dropped_not_an_index_member_that_session"] += 1
                continue
            census["membership_eligible_filings"] += 1

            rows.append({
                "cik": int(cik),
                "ticker": live[0],
                "tickers": "|".join(live),
                "accn": record["accn"],
                "filed": record["filed"],
                "accepted_et": pd.Timestamp(accepted),
                "after_close": accepted.time() >= filings.CLOSE_ET,
                "acceptance_date": pd.Timestamp(accepted.date()),
                "session": session,
                "deferred": pd.Timestamp(accepted.date()) != session,
                "items": ",".join(sorted(codes)),
                "n_items": len(codes),
            })
        if verbose and count % 100 == 0:
            print(f"  {count}/{len(by_cik)} CIKs, {len(rows):,} eligible filings",
                  flush=True)

    frame = pd.DataFrame(rows)
    return {"filings": frame, "census": dict(census),
            "amendments": dict(amendments),
            "ciks_scanned": len(by_cik),
            "last_usable_session": str(last_usable.date())}


def collapse(frame: pd.DataFrame) -> pd.DataFrame:
    """Filing-level rows -> one **issuer-event** per (CIK, information session).

    The frozen rule for two adverse filings by one issuer on one session: they
    are one observation, and their item codes are unioned. A study that counted
    them twice would be claiming two independent draws from a single day's news
    about a single company.
    """
    if frame.empty:
        return frame.assign(items=[], n_filings=[])
    grouped = frame.sort_values(["cik", "session", "accepted_et", "accn"])
    out = grouped.groupby(["cik", "session"], as_index=False).agg(
        ticker=("ticker", "first"),
        tickers=("tickers", "first"),
        accns=("accn", lambda s: "|".join(s)),
        n_filings=("accn", "size"),
        first_accepted=("accepted_et", "first"),
        after_close=("after_close", "all"),
        deferred=("deferred", "first"),
        items=("items", lambda s: ",".join(sorted({c for v in s
                                                   for c in str(v).split(",")}))),
    )
    out["n_items"] = out["items"].map(lambda v: len(str(v).split(",")))
    return out


def non_overlapping(events: pd.DataFrame, calendar: pd.DatetimeIndex,
                    horizon: int = HORIZON) -> pd.DataFrame:
    """The subset in which no issuer contributes two overlapping forecast windows.

    First event kept, then a `horizon`-session refractory period for that issuer.
    Greedy-earliest is the only rule here that does not require knowing anything
    about the events it is choosing between — any "keep the more severe one"
    rule would need a severity scale, and a severity scale fitted to outcomes is
    exactly what this pilot may not build.
    """
    if events.empty:
        return events.assign(kept=[])
    position = pd.Series(calendar.searchsorted(pd.DatetimeIndex(events["session"]),
                                               side="left"), index=events.index)
    order = events.assign(pos=position).sort_values(["cik", "pos"])
    keep, last_kept = [], {}
    for row in order.itertuples():
        previous = last_kept.get(row.cik)
        if previous is None or row.pos - previous >= horizon:
            keep.append(row.Index)
            last_kept[row.cik] = row.pos
    return events.loc[sorted(keep)]


def concentration(events: pd.DataFrame, calendar: pd.DatetimeIndex,
                  horizon: int = HORIZON) -> dict:
    """Independent information units, not row counts.

    The survey's structural result is that resolution is bought with independent
    *dates*. A panel of 2,000 events on 200 dates is not 2,000 draws, and this
    is where that is measured rather than assumed.
    """
    if events.empty:
        return {}
    sessions = pd.DatetimeIndex(events["session"])
    position = pd.Series(calendar.searchsorted(sessions, side="left"))
    block = position // horizon
    per_date = events.groupby("session").size()
    per_issuer = events.groupby("cik").size()
    per_block = events.assign(_block=block.to_numpy()).groupby("_block")
    return {
        "events": int(len(events)),
        "unique_ciks": int(events["cik"].nunique()),
        "unique_sessions": int(sessions.nunique()),
        "calendar_sessions": int(len(calendar)),
        "session_coverage": round(sessions.nunique() / len(calendar), 4),
        "events_per_date_mean": round(float(per_date.mean()), 3),
        "events_per_date_max": int(per_date.max()),
        "dates_with_one_event": int((per_date == 1).sum()),
        "top_date_share": round(float(per_date.max() / len(events)), 4),
        "events_per_issuer_mean": round(float(per_issuer.mean()), 3),
        "events_per_issuer_max": int(per_issuer.max()),
        "issuers_with_one_event": int((per_issuer == 1).sum()),
        "top_issuer_share": round(float(per_issuer.max() / len(events)), 4),
        "top10_issuer_share": round(float(per_issuer.nlargest(10).sum() / len(events)), 4),
        "occupied_blocks": int(block.nunique()),
        "total_blocks": int(len(calendar) // horizon),
        "events_per_occupied_block_mean": round(float(per_block.size().mean()), 3),
        "events_per_occupied_block_max": int(per_block.size().max()),
        "issuers_per_occupied_block_mean": round(
            float(per_block["cik"].nunique().mean()), 3),
    }


def survivorship(events: pd.DataFrame, identity_map: dict) -> dict:
    """What a present-day reconstruction of this panel would have deleted.

    The survey named this the family's fatal risk and the reason is arithmetic
    rather than rhetorical: adverse corporate events cluster in issuers that
    later disappear, so a panel keyed on *today's* symbols loses observations
    **in proportion to how adverse they were**. Two counterfactuals are measured
    against the survivorship-safe panel:

    * **current registrant** — keep only issuers still listed in
      `company_tickers.json`, which is how `alpha/source_probe.py` had to reach
      its 622 symbols and is the natural way to build this panel by accident;
    * **current index member** — keep only issuers whose ticker is in today's
      S&P 500 constituent table, the strongest form of the same error.

    Item-level loss is reported because a *uniform* loss would merely cost
    power. A loss concentrated on 1.03, 3.01 and 2.04 costs the hypothesis its
    evidence, and that is the difference between an underpowered study and a
    biased one.
    """
    if events.empty:
        return {}
    from . import membership

    table = EDGAR_DIR / "company_tickers.json"
    live_ciks = {int(row["cik_str"])
                 for row in json.loads(table.read_text(encoding="utf-8")).values()}
    current_members = set(membership._tables()[0]["ticker"])

    resolved = identity_map["resolved"]
    member_ciks = {int(r["cik"]) for t, r in resolved.items()
                   if r["cik"] is not None and t in current_members}

    def census(frame: pd.DataFrame) -> dict:
        return {"events": int(len(frame)),
                "issuers": int(frame["cik"].nunique()),
                "sessions": int(frame["session"].nunique())}

    def per_item(frame: pd.DataFrame) -> dict:
        return {code: int(frame["items"].str.split(",").map(
            lambda v: code in v).sum()) for code in ADVERSE_ITEMS}

    kept_registrant = events[events["cik"].isin(live_ciks)]
    kept_member = events[events["cik"].isin(member_ciks)]
    full = per_item(events)

    dead_registrant = events[~events["cik"].isin(live_ciks)]
    tickers = {t for v in events["tickers"] for t in str(v).split("|") if t}

    return {
        "survivorship_safe": dict(census(events), by_item=full),
        "current_registrant_only": dict(
            census(kept_registrant), by_item=per_item(kept_registrant),
            events_lost=int(len(events) - len(kept_registrant)),
            share_lost=round(1 - len(kept_registrant) / len(events), 4)),
        "current_index_member_only": dict(
            census(kept_member), by_item=per_item(kept_member),
            events_lost=int(len(events) - len(kept_member)),
            share_lost=round(1 - len(kept_member) / len(events), 4)),
        "item_loss_share_registrant": {
            code: round(1 - per_item(kept_registrant)[code] / full[code], 4)
            for code in ADVERSE_ITEMS if full[code]},
        "item_loss_share_index_member": {
            code: round(1 - per_item(kept_member)[code] / full[code], 4)
            for code in ADVERSE_ITEMS if full[code]},
        "historical_securities": len(tickers),
        "securities_not_current_members": len(tickers - current_members),
        "issuers_no_longer_registrants": int(dead_registrant["cik"].nunique()),
        "events_from_issuers_no_longer_registrants": int(len(dead_registrant)),
    }


def by_year(events: pd.DataFrame) -> dict:
    if events.empty:
        return {}
    year = pd.DatetimeIndex(events["session"]).year
    grouped = events.assign(_y=year).groupby("_y")
    return {str(int(y)): {"events": int(len(g)),
                          "issuers": int(g["cik"].nunique()),
                          "sessions": int(g["session"].nunique())}
            for y, g in grouped}


def by_item(events: pd.DataFrame) -> dict:
    if events.empty:
        return {}
    out = {}
    for code in ADVERSE_ITEMS:
        hit = events[events["items"].str.split(",").map(lambda v: code in v)]
        out[code] = {"label": ITEM_LABELS[code], "events": int(len(hit)),
                     "issuers": int(hit["cik"].nunique()) if len(hit) else 0}
    return out


def main() -> None:
    cfg.OUT_DIR.mkdir(parents=True, exist_ok=True)
    calendar = pitdata.load_calendar().calendar
    calendar = calendar[calendar >= pd.Timestamp(STUDY_START)]
    identity_map = identity.load_identity()
    archive = zipfile.ZipFile(SUBMISSIONS)

    built = build(archive, identity_map, calendar)
    frame = built["filings"]
    events = collapse(frame)
    independent = non_overlapping(events, calendar)

    events.to_parquet(PANEL_PATH, index=False)

    resolved = identity_map["resolved"]
    unresolved = identity_map["unresolved"]
    report = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "study_start": STUDY_START,
        "last_usable_session": built["last_usable_session"],
        "calendar_sessions": int(len(calendar)),
        "adverse_items": list(ADVERSE_ITEMS),
        "excluded_items": list(EXCLUDED_ITEMS),
        "horizon": HORIZON,
        "identity": {
            "ever_member_tickers": len(resolved),
            "resolved_tickers": sum(1 for r in resolved.values() if r["cik"]),
            "unresolved_tickers": len(unresolved),
            "unresolved": unresolved,
            "methods": identity_map.get("methods", {}),
            "unique_ciks": built["ciks_scanned"],
            "multi_security_ciks": len(identity_map.get("multi_security_ciks", {})),
        },
        "census": built["census"],
        "amendments": built["amendments"],
        "filing_level": {
            "eligible_filings": int(len(frame)),
            "accepted_after_close": int(frame["after_close"].sum()) if len(frame) else 0,
            "share_after_close": round(float(frame["after_close"].mean()), 4) if len(frame) else 0.0,
            "deferred_to_next_session": int(frame["deferred"].sum()) if len(frame) else 0,
            "share_deferred": round(float(frame["deferred"].mean()), 4) if len(frame) else 0.0,
        },
        "survivorship": survivorship(events, identity_map),
        "issuer_events": concentration(events, calendar),
        "issuer_events_by_year": by_year(events),
        "issuer_events_by_item": by_item(events),
        "non_overlapping": concentration(independent, calendar),
        "non_overlapping_by_year": by_year(independent),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=1), encoding="utf-8")

    census = built["census"]
    print("\nfunnel")
    for key, value in census.items():
        print(f"  {key:44s} {value:8,}")
    print(f"  {'issuer-events after same-session collapse':44s} {len(events):8,}")
    print(f"  {'non-overlapping (5-session refractory)':44s} {len(independent):8,}")
    print(f"\nissuers {events['cik'].nunique()}  sessions "
          f"{events['session'].nunique()}  blocks "
          f"{report['issuer_events']['occupied_blocks']}")
    print(f"wrote {PANEL_PATH}\nwrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
