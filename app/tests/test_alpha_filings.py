"""The filings door's guarantee, proved the only way that counts.

Same discipline as `test_alpha.py` proves for the price door and
`test_validation.py` proves for the V1 engine: build a world, rewrite its
future, and demand the past does not move. Plus the two rules this door
specifically exists to enforce, both measured in `reports/INFORMATION_AUDIT.md`:

* a fact accepted *after the 16:00 ET close* of its own filing date is not
  knowable at that session's cutoff (51.8% of 10-K/10-Q filings are);
* a restatement is a new vintage, visible only from its own acceptance —
  it can never reach back into a historical observation (roadmap §6.1).
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import filings  # noqa: E402


def fact(cik=1, concept="Revenues", start="2019-10-01", end="2019-12-31",
         value=100.0, accn="0001-20-000001", form="10-Q", fy=2020, fp="Q1",
         filed="2020-01-30", accepted="2020-01-30 10:00:00"):
    return dict(cik=cik, concept=concept, unit="USD",
                start=pd.Timestamp(start), end=pd.Timestamp(end), value=value,
                accn=accn, form=form, fy=fy, fp=fp,
                filed=pd.Timestamp(filed), accepted=pd.Timestamp(accepted))


def book_of(*facts):
    return filings.FilingsBook(pd.DataFrame(list(facts)))


# ---------------------------------------------------------------------------
# The door itself
# ---------------------------------------------------------------------------

class TestTheDoor:
    def test_future_acceptance_never_enters_a_view(self):
        book = book_of(
            fact(accn="a", accepted="2020-01-30 10:00:00"),
            fact(accn="b", accepted="2021-01-30 10:00:00", value=999.0),
        )
        view = book.view(pd.Timestamp("2020-06-01"))
        assert list(view.facts["accn"]) == ["a"]

    def test_accepted_after_the_close_is_not_knowable_that_session(self):
        """The 51.8% rule. 15:59:59 is in; 16:00:00 exactly and later are out."""
        book = book_of(
            fact(accn="before", accepted="2020-01-30 15:59:59"),
            fact(accn="at",     accepted="2020-01-30 16:00:00"),
            fact(accn="after",  accepted="2020-01-30 16:39:00"),
        )
        same_day = book.view(pd.Timestamp("2020-01-30"))
        assert list(same_day.facts["accn"]) == ["before"]
        next_day = book.view(pd.Timestamp("2020-01-31"))
        assert sorted(next_day.facts["accn"]) == ["after", "at", "before"]

    def test_the_view_keeps_no_route_back_to_the_book(self):
        view = book_of(fact()).view(pd.Timestamp("2020-06-01"))
        assert not any(isinstance(v, filings.FilingsBook)
                       for v in vars(view).values())

    def test_missing_acceptance_fails_closed(self):
        rows = pd.DataFrame([fact(), fact(accn="x", accepted=None)])
        rows.loc[rows["accn"] == "x", "accepted"] = pd.NaT
        with pytest.raises(ValueError, match="no acceptance timestamp"):
            filings.FilingsBook(rows)

    def test_missing_columns_fail_closed(self):
        with pytest.raises(ValueError, match="missing columns"):
            filings.FilingsBook(pd.DataFrame([{"cik": 1}]))


# ---------------------------------------------------------------------------
# Restatements: the roadmap §6.1 required test
# ---------------------------------------------------------------------------

class TestRestatements:
    ORIGINAL = dict(accn="orig", value=100.0, accepted="2020-01-30 10:00:00")
    RESTATED = dict(accn="rest", value=120.0, accepted="2021-01-29 17:30:00",
                    form="10-K", fy=2021, fp="FY", filed="2021-01-29")

    def test_a_restatement_cannot_change_history(self):
        """Rewrite the future, demand an identical past — the door's whole point."""
        clean = book_of(fact(**self.ORIGINAL))
        tampered = book_of(
            fact(**self.ORIGINAL),
            fact(**{**self.RESTATED, "value": 999999.0}),
            fact(**{**self.RESTATED, "accn": "rest2", "value": -1.0,
                    "accepted": "2022-01-29 17:30:00"}),
        )
        cutoff = pd.Timestamp("2020-06-01")
        before = clean.view(cutoff).as_known("Revenues")
        after = tampered.view(cutoff).as_known("Revenues")
        pd.testing.assert_frame_equal(
            before.reset_index(drop=True), after.reset_index(drop=True))
        assert list(after["value"]) == [100.0]

    def test_a_restatement_is_visible_from_its_own_acceptance(self):
        book = book_of(fact(**self.ORIGINAL), fact(**self.RESTATED))
        known = book.view(pd.Timestamp("2021-06-01")).as_known("Revenues")
        assert list(known["value"]) == [120.0]
        assert list(known["accn"]) == ["rest"]

    def test_vintages_of_different_periods_do_not_supersede_each_other(self):
        book = book_of(
            fact(accn="q1", start="2019-10-01", end="2019-12-31", value=100.0),
            fact(accn="q2", start="2020-01-01", end="2020-03-31", value=110.0,
                 accepted="2020-04-30 10:00:00", filed="2020-04-30", fp="Q2"),
        )
        known = book.view(pd.Timestamp("2020-06-01")).as_known("Revenues")
        assert sorted(known["value"]) == [100.0, 110.0]

    def test_latest_period_reports_the_newest_known_quarter_only(self):
        book = book_of(
            fact(accn="q1", start="2019-10-01", end="2019-12-31", value=100.0),
            fact(accn="q2", start="2020-01-01", end="2020-03-31", value=110.0,
                 accepted="2020-04-30 10:00:00", filed="2020-04-30", fp="Q2"),
        )
        latest = book.view(pd.Timestamp("2020-06-01")).latest_period("Revenues")
        assert list(latest["accn"]) == ["q2"]
        # ... and at an earlier cutoff, the earlier quarter.
        latest = book.view(pd.Timestamp("2020-02-15")).latest_period("Revenues")
        assert list(latest["accn"]) == ["q1"]


# ---------------------------------------------------------------------------
# The ET conversion the whole rule stands on
# ---------------------------------------------------------------------------

class TestEasternTime:
    def test_et_conversion_handles_both_dst_regimes(self):
        # July: EDT, UTC-4. 20:30Z -> 16:30 ET (after the close).
        july = filings.et_from_utc("2026-07-30T20:30:28.000Z")
        assert july == dt.datetime(2026, 7, 30, 16, 30, 28)
        # January: EST, UTC-5. 21:30Z -> 16:30 ET.
        january = filings.et_from_utc("2026-01-29T21:30:33.000Z")
        assert january == dt.datetime(2026, 1, 29, 16, 30, 33)

    def test_dst_boundaries_for_2026(self):
        # DST starts 2026-03-08, ends 2026-11-01.
        assert filings.et_from_utc("2026-03-08T12:00:00Z").hour == 8   # EDT
        assert filings.et_from_utc("2026-03-07T12:00:00Z").hour == 7   # EST
        assert filings.et_from_utc("2026-11-01T12:00:00Z").hour == 7   # EST
        assert filings.et_from_utc("2026-10-31T12:00:00Z").hour == 8   # EDT

    def test_close_of_is_four_pm_on_the_cutoff_date(self):
        edge = filings.close_of(pd.Timestamp("2020-01-30 09:13:00"))
        assert edge == dt.datetime(2020, 1, 30, 16, 0, 0)


# ---------------------------------------------------------------------------
# as_known determinism
# ---------------------------------------------------------------------------

class TestAsKnown:
    def test_acceptance_ties_break_on_accession(self):
        book = book_of(
            fact(accn="0001-20-000001", value=1.0),
            fact(accn="0001-20-000002", value=2.0),
        )
        known = book.view(pd.Timestamp("2020-06-01")).as_known("Revenues")
        assert list(known["value"]) == [2.0]

    def test_concepts_do_not_bleed_into_each_other(self):
        book = book_of(
            fact(concept="Revenues", value=100.0),
            fact(concept="NetIncomeLoss", accn="ni", value=10.0),
        )
        view = book.view(pd.Timestamp("2020-06-01"))
        assert list(view.as_known("Revenues")["value"]) == [100.0]
        assert list(view.as_known("NetIncomeLoss")["value"]) == [10.0]

    def test_ciks_do_not_bleed_into_each_other(self):
        book = book_of(fact(cik=1, value=100.0), fact(cik=2, accn="c2", value=200.0))
        known = book.view(pd.Timestamp("2020-06-01")).as_known("Revenues")
        assert sorted(known["value"]) == [100.0, 200.0]
        assert len(known) == 2
