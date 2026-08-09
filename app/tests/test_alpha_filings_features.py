"""The SUE feature's knowability guarantee, pinned the same way as the door's.

The decisive test is the last one: rewrite the future — add restatements and
new filings after a cutoff — and demand the feature at that cutoff does not
move. Everything else (Q4 derivation, YoY matching, the std window) exists so
that when that test passes, it is passing on the construction the study will
actually run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import filings_features as ff  # noqa: E402


def quarter(end, value, accepted, start=None, accn=None):
    end = pd.Timestamp(end)
    start = pd.Timestamp(start) if start else end - pd.Timedelta(days=90)
    return dict(cik=1, concept="NetIncomeLoss", unit="USD",
                start=start, end=end, value=float(value),
                accn=accn or f"a-{end.date()}", form="10-Q", fy=end.year,
                fp="Q", filed=pd.Timestamp(accepted).normalize(),
                accepted=pd.Timestamp(accepted))


def annual(end, value, accepted, start=None, accn=None):
    row = quarter(end, value, accepted, start=start or
                  (pd.Timestamp(end) - pd.Timedelta(days=364)), accn=accn)
    row["form"] = "10-K"
    return row


def firm(*rows):
    return pd.DataFrame(list(rows))


def steady_history(quarters=13, start_value=100.0, step=5.0):
    """Quarterly NI growing by `step` each quarter, filed ~35 days after end."""
    rows = []
    end = pd.Timestamp("2016-03-31")
    value = start_value
    for _ in range(quarters):
        rows.append(quarter(end, value, end + pd.Timedelta(days=35)))
        end = end + pd.Timedelta(days=91)
        value += step
    return rows


class TestQuarterlySeries:
    def test_q4_is_derived_from_the_annual_and_knowable_at_the_10k(self):
        rows = firm(
            quarter("2019-03-31", 10, "2019-05-05"),
            quarter("2019-06-30", 11, "2019-08-05"),
            quarter("2019-09-30", 12, "2019-11-05"),
            annual("2019-12-31", 50, "2020-02-20", start="2019-01-01"),
        )
        series = ff.quarterly_as_known(rows)
        q4 = series[series["end"] == pd.Timestamp("2019-12-31")]
        assert list(q4["value"]) == [50 - 33]
        assert list(q4["accepted"]) == [pd.Timestamp("2020-02-20")]

    def test_no_q4_without_all_three_quarters(self):
        rows = firm(
            quarter("2019-03-31", 10, "2019-05-05"),
            annual("2019-12-31", 50, "2020-02-20", start="2019-01-01"),
        )
        series = ff.quarterly_as_known(rows)
        assert pd.Timestamp("2019-12-31") not in set(series["end"])

    def test_a_restated_quarter_supersedes_only_itself(self):
        rows = firm(
            quarter("2019-03-31", 10, "2019-05-05"),
            quarter("2019-06-30", 11, "2019-08-05"),
            quarter("2019-03-31", 99, "2020-05-05", accn="restated"),
        )
        series = ff.quarterly_as_known(rows)
        assert list(series["value"]) == [99.0, 11.0]


class TestSue:
    def test_constant_growth_has_zero_surprise_variance_and_no_sue(self):
        # Perfectly steady growth: every seasonal surprise is identical, the
        # std is 0, and SUE is undefined rather than infinite.
        series = ff.quarterly_as_known(firm(*steady_history()))
        assert np.isnan(ff.sue_from_series(series))

    def test_a_jump_after_noisy_history_produces_a_positive_sue(self):
        rows = steady_history(12)
        # Perturb with period 3 so the seasonal (4-quarter) difference does
        # not cancel it — an alternating +/- pattern would, exactly.
        for i, row in enumerate(rows):
            row["value"] += (1.5 if i % 3 else -1.5)
        rows.append(quarter("2019-03-31", 500.0, "2019-05-05"))
        series = ff.quarterly_as_known(firm(*rows))
        assert ff.sue_from_series(series) > 3

    def test_sue_needs_a_year_ago_peer(self):
        rows = steady_history(3)   # not enough for any YoY difference
        series = ff.quarterly_as_known(firm(*rows))
        assert np.isnan(ff.sue_from_series(series))


class TestReplay:
    def test_events_are_frozen_history(self):
        events = ff.replay(firm(*steady_history()))
        assert len(events.valid_from) == 13
        assert (np.diff(events.valid_from) > np.timedelta64(0, "s")).all()

    def test_as_of_reads_strictly_before_the_edge(self):
        rows = firm(
            quarter("2019-03-31", 10, "2019-05-05 16:30:00"),
        )
        events = ff.replay(rows)
        import datetime as dt
        # at the close of the acceptance day the filing is 16:30 — not knowable
        sue, accepted = events.as_of(dt.datetime(2019, 5, 5, 16, 0))
        assert accepted is None
        sue, accepted = events.as_of(dt.datetime(2019, 5, 6, 16, 0))
        assert accepted == pd.Timestamp("2019-05-05 16:30:00")


class TestTheGuarantee:
    def test_the_future_cannot_change_the_feature(self):
        """Rewrite the future, demand an identical past — at the feature level."""
        history = steady_history(12)
        for i, row in enumerate(history):
            row["value"] += (2.0 if i % 3 else -2.0)

        clean = ff.replay(firm(*history))

        tampered_rows = history + [
            quarter("2019-03-31", 10_000.0, "2019-05-05"),
            quarter("2016-03-31", -10_000.0, "2019-06-01", accn="evil-restate"),
            annual("2019-12-31", 77.0, "2020-02-20", start="2019-01-01"),
        ]
        tampered = ff.replay(firm(*tampered_rows))

        import datetime as dt
        for edge in (dt.datetime(2017, 6, 1, 16, 0),
                     dt.datetime(2018, 6, 1, 16, 0),
                     dt.datetime(2019, 3, 1, 16, 0)):
            clean_sue, clean_accepted = clean.as_of(edge)
            tampered_sue, tampered_accepted = tampered.as_of(edge)
            assert clean_accepted == tampered_accepted
            assert (np.isnan(clean_sue) and np.isnan(tampered_sue)) \
                or clean_sue == tampered_sue

    def test_a_restatement_changes_belief_only_from_its_acceptance(self):
        history = steady_history(12)
        for i, row in enumerate(history):
            row["value"] += (2.0 if i % 3 else -2.0)
        restated = history + [
            quarter(history[-2]["end"], 9_999.0, "2019-06-01", accn="restate")]
        events = ff.replay(firm(*restated))
        import datetime as dt
        before_sue, _ = events.as_of(dt.datetime(2019, 5, 1, 16, 0))
        after_sue, _ = events.as_of(dt.datetime(2019, 7, 1, 16, 0))
        clean_sue, _ = ff.replay(firm(*history)).as_of(dt.datetime(2019, 5, 1, 16, 0))
        assert before_sue == clean_sue
        assert after_sue != before_sue


class TestBuildFeature:
    def test_panel_shape_and_nan_policy(self):
        facts = firm(*steady_history())
        cutoffs = pd.DatetimeIndex(["2018-06-04", "2018-06-11"])
        members = pd.DataFrame(
            [(c, s) for c in cutoffs for s in ("GOOD", "NOCIK")],
            columns=["cutoff", "symbol"])
        panel = ff.build_feature(facts, "NetIncomeLoss", cutoffs, members,
                                 {"GOOD": 1})
        assert len(panel) == 4
        assert panel.loc[(cutoffs[0], "NOCIK")].isna().all()
        good = panel.loc[(cutoffs[0], "GOOD")]
        assert np.isfinite(good["staleness_days"])
