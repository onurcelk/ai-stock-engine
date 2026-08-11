"""Family 10 Stage 1: the identity chain and the event panel's frozen rules.

`test_alpha_filings.py` proves the *door*. This file proves the two things
built on top of it that the door cannot see: that the identity a filing is
attached to is a point-in-time one, and that the deduplication rules are the
ones the pilot froze rather than whichever ones happen to be convenient.

Hermetic — every fixture is built in memory or in `tmp_path`. Nothing reads
`alpha/edgar/submissions.zip`, nothing reads a price, nothing reads a return.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import family10_identity as identity  # noqa: E402
from alpha import family10_panel as panel  # noqa: E402
from alpha import filings  # noqa: E402


def calendar_of(*days: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([pd.Timestamp(d) for d in days])


#: A week of sessions with the 2020 New Year holiday and a weekend in it, so the
#: "next eligible session" rule has something to skip over.
WEEK = calendar_of("2020-12-30", "2020-12-31", "2021-01-04", "2021-01-05",
                   "2021-01-06", "2021-01-07", "2021-01-08", "2021-01-11",
                   "2021-01-12", "2021-01-13", "2021-01-14", "2021-01-15")


# ---------------------------------------------------------------------------
# Name normalisation — the link that turns a dead ticker back into a CIK
# ---------------------------------------------------------------------------

class TestNames:
    def test_legal_form_and_punctuation_are_stripped(self):
        assert identity.normalise_name("Apple Inc.") == "apple"
        assert identity.normalise_name("TIFFANY & CO") == "tiffany"
        assert identity.normalise_name("Bath & Body Works, Inc.") == "bath and body works"

    def test_a_legal_word_in_the_middle_is_left_alone(self):
        """Only the *tail* is stripped; `name_compatible` absorbs the rest."""
        assert identity.normalise_name("MONSANTO CO /NEW/") == "monsanto co new"
        assert identity.name_compatible("monsanto", "monsanto co new")

    def test_the_state_of_incorporation_tail_is_not_part_of_the_name(self):
        """`/CA/` is EDGAR's, not the company's — it blocked LLTC for a whole pass."""
        assert identity.normalise_name("LINEAR TECHNOLOGY CORP /CA/") == "linear technology"
        assert identity.normalise_name("AETNA INC /PA/") == "aetna"

    def test_a_generic_tail_is_compatible(self):
        assert identity.name_compatible("sealed air", "sealed air corp de")
        assert identity.name_compatible("discover financial", "discover financial services")
        assert identity.name_compatible("interpublic group", "interpublic")

    def test_a_distinguishing_tail_is_not(self):
        """The guard that keeps `Apple` from absorbing `Apple Hospitality REIT`."""
        assert not identity.name_compatible("apple", "apple hospitality reit")
        assert not identity.name_compatible("first republic bank", "first republic group")

    def test_subset_matching_requires_every_distinguishing_word(self):
        assert identity.name_subset("mead johnson", "mead johnson nutrition")
        assert identity.name_subset("dupont", "dupont de nemours")

    def test_subset_matching_rejects_the_two_it_once_got_wrong(self):
        """An earlier first-word-only rule mapped both of these. Neither may pass."""
        assert not identity.name_subset("ferguson enterprises",
                                        "ferguson wellman capital management")
        assert not identity.name_subset("signature bank", "gb sciences")


class TestCorroboration:
    def test_long_membership_demands_a_periodic_report(self):
        spans = [("2016-01-04", "2020-01-04")]
        assert identity.span_days(spans) > identity.SHORT_MEMBERSHIP_DAYS
        assert identity.corroborated({"periodic": 4, "filings": 40}, identity.span_days(spans))
        assert not identity.corroborated({"periodic": 0, "filings": 40},
                                         identity.span_days(spans))

    def test_short_membership_cannot_demand_one(self):
        """PCP was in the index for four weeks; no 10-K was due in it."""
        spans = [("2016-01-04", "2016-02-01")]
        days = identity.span_days(spans)
        assert days < identity.SHORT_MEMBERSHIP_DAYS
        assert identity.corroborated({"periodic": 0, "filings": 3}, days)
        assert not identity.corroborated({"periodic": 0, "filings": 0}, days)

    def test_a_reused_ticker_fails_corroboration(self):
        """The new owner of a recycled symbol filed nothing while the old one was a member."""
        spans = [("2016-01-04", "2016-07-01")]
        profile = pd.DataFrame({"form": ["10-K", "8-K"],
                                "filed": ["2024-02-01", "2024-03-01"]})
        seen = identity._activity(profile, spans)
        assert seen["filings"] == 0
        assert not identity.corroborated(seen, identity.span_days(spans))


# ---------------------------------------------------------------------------
# The information door, solved forwards
# ---------------------------------------------------------------------------

class TestInformationSession:
    def test_before_the_close_is_knowable_that_session(self):
        stamp = dt.datetime(2021, 1, 5, 15, 59, 59)
        assert panel.information_session(stamp, WEEK) == pd.Timestamp("2021-01-05")

    def test_the_close_itself_is_not(self):
        """16:00:00 exactly is out. The boundary is `<`, not `<=`."""
        stamp = dt.datetime(2021, 1, 5, 16, 0, 0)
        assert panel.information_session(stamp, WEEK) == pd.Timestamp("2021-01-06")

    def test_after_the_close_waits_for_the_next_session(self):
        stamp = dt.datetime(2021, 1, 5, 20, 30, 0)
        assert panel.information_session(stamp, WEEK) == pd.Timestamp("2021-01-06")

    def test_a_weekend_filing_waits_for_the_next_session(self):
        stamp = dt.datetime(2021, 1, 9, 11, 0, 0)      # a Saturday
        assert panel.information_session(stamp, WEEK) == pd.Timestamp("2021-01-11")

    def test_a_holiday_filing_waits_for_the_next_session(self):
        stamp = dt.datetime(2021, 1, 1, 9, 0, 0)       # New Year's Day
        assert panel.information_session(stamp, WEEK) == pd.Timestamp("2021-01-04")

    def test_it_agrees_with_the_door_it_is_derived_from(self):
        """The claim that this is not a second timestamp rule, checked exhaustively."""
        for hour in range(0, 24):
            stamp = dt.datetime(2021, 1, 5, hour, 30, 0)
            session = panel.information_session(stamp, WEEK)
            assert stamp < filings.close_of(session)
            earlier = WEEK[WEEK < session]
            assert all(stamp >= filings.close_of(day) for day in earlier
                       if day >= pd.Timestamp(stamp.date()))

    def test_a_filing_past_the_last_session_has_none(self):
        assert panel.information_session(dt.datetime(2030, 1, 1, 9, 0), WEEK) is None


# ---------------------------------------------------------------------------
# The event definition
# ---------------------------------------------------------------------------

class TestEventDefinition:
    def test_the_adverse_set_is_the_frozen_one(self):
        assert panel.ADVERSE_ITEMS == ("1.02", "1.03", "2.04", "2.05",
                                       "2.06", "3.01", "3.02", "4.02")
        assert panel.EXCLUDED_ITEMS == ("2.02",)

    def test_a_non_adverse_filing_carries_no_codes(self):
        assert panel.adverse_codes("7.01,8.01,9.01") == ([], False)

    def test_several_adverse_items_in_one_filing_are_one_event(self):
        codes, excluded = panel.adverse_codes("2.05,2.06,9.01")
        assert codes == ["2.05", "2.06"] and not excluded

    def test_item_2_02_disqualifies_the_whole_filing(self):
        """Structural exclusion: not a later filter, and not overridable."""
        codes, excluded = panel.adverse_codes("2.02,2.06")
        assert codes == ["2.06"] and excluded is True


# ---------------------------------------------------------------------------
# Deduplication — frozen before any analysis, and unable to consult an outcome
# ---------------------------------------------------------------------------

def event_rows(*specs) -> pd.DataFrame:
    rows = []
    for cik, session, accn, items in specs:
        rows.append({"cik": cik, "ticker": "AAA", "tickers": "AAA", "accn": accn,
                     "filed": session, "accepted_et": pd.Timestamp(session + " 10:00"),
                     "after_close": False, "acceptance_date": pd.Timestamp(session),
                     "session": pd.Timestamp(session), "deferred": False,
                     "items": items, "n_items": len(items.split(","))})
    return pd.DataFrame(rows)


class TestCollapse:
    def test_two_filings_by_one_issuer_on_one_session_are_one_event(self):
        frame = event_rows((1, "2021-01-05", "a", "1.02"),
                           (1, "2021-01-05", "b", "2.06"))
        out = panel.collapse(frame)
        assert len(out) == 1
        assert out.iloc[0]["items"] == "1.02,2.06"
        assert out.iloc[0]["n_filings"] == 2

    def test_two_issuers_on_one_session_stay_two_events(self):
        frame = event_rows((1, "2021-01-05", "a", "1.02"),
                           (2, "2021-01-05", "b", "1.02"))
        assert len(panel.collapse(frame)) == 2

    def test_one_issuer_on_two_sessions_stays_two_events(self):
        frame = event_rows((1, "2021-01-05", "a", "1.02"),
                           (1, "2021-01-12", "b", "1.02"))
        assert len(panel.collapse(frame)) == 2


class TestNonOverlapping:
    def test_a_repeat_inside_the_horizon_is_dropped(self):
        events = panel.collapse(event_rows((1, "2021-01-05", "a", "1.02"),
                                           (1, "2021-01-06", "b", "2.06")))
        kept = panel.non_overlapping(events, WEEK, horizon=5)
        assert len(kept) == 1
        assert kept.iloc[0]["session"] == pd.Timestamp("2021-01-05")

    def test_a_repeat_exactly_a_horizon_later_is_kept(self):
        events = panel.collapse(event_rows((1, "2021-01-05", "a", "1.02"),
                                           (1, "2021-01-12", "b", "2.06")))
        assert len(panel.non_overlapping(events, WEEK, horizon=5)) == 2

    def test_the_refractory_period_is_per_issuer(self):
        events = panel.collapse(event_rows((1, "2021-01-05", "a", "1.02"),
                                           (2, "2021-01-06", "b", "1.02")))
        assert len(panel.non_overlapping(events, WEEK, horizon=5)) == 2

    def test_the_earliest_event_wins_and_the_rule_is_deterministic(self):
        """No severity scale is consulted — one would have to be fitted to outcomes."""
        events = panel.collapse(event_rows((1, "2021-01-05", "a", "1.02"),
                                           (1, "2021-01-06", "b", "1.03")))
        kept = panel.non_overlapping(events, WEEK, horizon=5)
        assert kept.iloc[0]["items"] == "1.02"
        again = panel.non_overlapping(events, WEEK, horizon=5)
        assert kept.reset_index(drop=True).equals(again.reset_index(drop=True))


# ---------------------------------------------------------------------------
# Membership: the step function must equal the machinery it replaces
# ---------------------------------------------------------------------------

class TestMembershipStepFunction:
    def test_members_on_reproduces_members_at(self, monkeypatch):
        boundaries = [pd.Timestamp("2016-01-04"), pd.Timestamp("2018-06-01")]
        sets = [{"AAA", "BBB"}, {"BBB", "CCC"}]
        assert identity.members_on(pd.Timestamp("2016-01-04"), boundaries, sets) == {"AAA", "BBB"}
        assert identity.members_on(pd.Timestamp("2018-05-31"), boundaries, sets) == {"AAA", "BBB"}
        assert identity.members_on(pd.Timestamp("2018-06-01"), boundaries, sets) == {"BBB", "CCC"}

    def test_a_date_before_the_first_boundary_has_no_members(self):
        boundaries = [pd.Timestamp("2016-01-04")]
        assert identity.members_on(pd.Timestamp("2015-01-01"), boundaries, [{"AAA"}]) == set()


# ---------------------------------------------------------------------------
# Survivorship — the measurement the family exists or dies on
# ---------------------------------------------------------------------------

class TestSurvivorship:
    def test_a_dead_issuers_events_are_counted_and_attributed(self, tmp_path,
                                                              monkeypatch):
        table = tmp_path / "company_tickers.json"
        table.write_text(json.dumps({"0": {"cik_str": 1, "ticker": "AAA",
                                           "title": "Alive"}}), encoding="utf-8")
        monkeypatch.setattr(panel, "EDGAR_DIR", tmp_path)
        monkeypatch.setattr(identity.membership, "_tables",
                            lambda: (pd.DataFrame({"ticker": ["AAA"]}), None))

        events = panel.collapse(event_rows((1, "2021-01-05", "a", "1.02"),
                                           (2, "2021-01-06", "b", "3.01")))
        events["tickers"] = ["AAA", "DEAD"]
        out = panel.survivorship(events, {"resolved": {
            "AAA": {"cik": 1}, "DEAD": {"cik": 2}}})

        assert out["survivorship_safe"]["events"] == 2
        assert out["current_registrant_only"]["events"] == 1
        assert out["current_registrant_only"]["events_lost"] == 1
        assert out["issuers_no_longer_registrants"] == 1
        assert out["securities_not_current_members"] == 1
        # and the loss lands on the delisting item, not the benign one
        assert out["item_loss_share_registrant"]["3.01"] == 1.0
        assert out["item_loss_share_registrant"]["1.02"] == 0.0


# ---------------------------------------------------------------------------
# The archive reader
# ---------------------------------------------------------------------------

def make_archive(path: Path, cik: int, rows: list[dict]) -> zipfile.ZipFile:
    payload = {"cik": f"{cik:010d}", "name": "TEST CO", "tickers": ["AAA"],
               "filings": {"recent": {
                   "form": [r["form"] for r in rows],
                   "accessionNumber": [r["accn"] for r in rows],
                   "filingDate": [r["filed"] for r in rows],
                   "acceptanceDateTime": [r["accepted"] for r in rows],
                   "items": [r.get("items", "") for r in rows]}, "files": []}}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"CIK{cik:010d}.json", json.dumps(payload))
    return zipfile.ZipFile(path)


class TestArchiveReader:
    def test_only_8k_and_its_amendment_are_read(self, tmp_path):
        archive = make_archive(tmp_path / "s.zip", 7, [
            {"form": "8-K", "accn": "a", "filed": "2021-01-05",
             "accepted": "2021-01-05T14:00:00.000Z", "items": "1.02"},
            {"form": "10-Q", "accn": "b", "filed": "2021-01-05",
             "accepted": "2021-01-05T14:00:00.000Z"},
            {"form": "8-K/A", "accn": "c", "filed": "2021-01-06",
             "accepted": "2021-01-06T14:00:00.000Z", "items": "1.02"},
        ])
        got = panel._filings_for(archive, 7)
        assert [r["form"] for r in got] == ["8-K", "8-K/A"]

    def test_a_missing_cik_is_empty_not_an_error(self, tmp_path):
        archive = make_archive(tmp_path / "s.zip", 7, [])
        assert panel._filings_for(archive, 999) == []
