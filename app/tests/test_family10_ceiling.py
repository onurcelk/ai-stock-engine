"""Family 10 Stage 2: the clause-3 machinery, and the guard that keeps it feature-side.

The gate itself is a measurement and lives in `alpha/out/family10_ceiling.json`.
What is testable is the machinery underneath it: that an outcome column cannot
reach the statistic, that the event dummy lands on the cutoff whose window
actually contains the event, and that the sparsity disclosure measures what it
claims to.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import family10_ceiling as ceiling  # noqa: E402


CALENDAR = pd.DatetimeIndex(pd.bdate_range("2021-01-04", periods=40))
#: A 5-session grid over that calendar, the same spacing `alpha/dataset.py` uses.
#: It stops at CALENDAR[34] so the tail sessions have no cutoff ahead of them —
#: that is the off-grid case, and `dataset.schedule` leaves the same tail for the
#: same reason (a cutoff needs a full horizon after it).
GRID = list(CALENDAR[4:35:5])


def panel_index(cutoffs, symbols) -> pd.MultiIndex:
    return pd.MultiIndex.from_product([pd.DatetimeIndex(cutoffs), symbols],
                                      names=["cutoff", "symbol"])


def events_of(*specs) -> pd.DataFrame:
    return pd.DataFrame([{"cik": cik, "ticker": ticker, "tickers": ticker,
                          "session": pd.Timestamp(session), "items": items}
                         for cik, ticker, session, items in specs])


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

class TestOutcomeGuard:
    def test_every_outcome_column_is_dropped(self):
        frame = pd.DataFrame({"ret_5d": [1.0], "asset_return": [0.02],
                              "alpha_5d": [0.01], "quintile": [3]})
        kept = ceiling._feature_frame(frame)
        assert list(kept.columns) == ["ret_5d"]

    def test_the_outcome_list_covers_the_panel_s_own_targets(self):
        """If `alpha/targets.py` grows a column, this list must grow with it."""
        for column in ("asset_return", "alpha_5d", "target_train", "quintile"):
            assert column in ceiling.OUTCOME_COLUMNS

    def test_a_frame_with_no_outcome_column_passes_through(self):
        frame = pd.DataFrame({"ret_5d": [1.0], "rvol_20d": [0.3]})
        assert ceiling._feature_frame(frame).equals(frame)


# ---------------------------------------------------------------------------
# The representation
# ---------------------------------------------------------------------------

class TestEventDummy:
    def test_an_event_lands_on_the_cutoff_whose_window_contains_it(self):
        index = panel_index(GRID, ["AAA", "BBB"])
        # GRID[1] is CALENDAR[9]; its window is CALENDAR[5..9].
        events = events_of((1, "AAA", CALENDAR[7], "1.02"))
        dummy = ceiling.event_dummy(events, GRID, CALENDAR, index)
        assert dummy.loc[(GRID[1], "AAA")] == 1.0
        assert dummy.sum() == 1.0

    def test_an_event_on_the_cutoff_itself_belongs_to_that_cutoff(self):
        index = panel_index(GRID, ["AAA"])
        events = events_of((1, "AAA", GRID[2], "2.06"))
        dummy = ceiling.event_dummy(events, GRID, CALENDAR, index)
        assert dummy.loc[(GRID[2], "AAA")] == 1.0

    def test_the_windows_partition_the_calendar(self):
        """Every session belongs to exactly one cutoff — no gap, no double count."""
        index = panel_index(GRID, ["AAA"])
        for session in CALENDAR[:len(GRID) * 5]:
            events = events_of((1, "AAA", session, "1.02"))
            dummy = ceiling.event_dummy(events, GRID, CALENDAR, index)
            assert dummy.sum() == 1.0, session

    def test_an_event_with_no_cutoff_ahead_of_it_is_dropped_and_counted(self):
        index = panel_index(GRID, ["AAA"])
        events = events_of((1, "AAA", CALENDAR[-1], "1.02"))
        dummy = ceiling.event_dummy(events, GRID, CALENDAR, index)
        assert dummy.sum() == 0.0
        assert dummy.attrs["events_off_grid"] == 1

    def test_a_symbol_absent_from_the_panel_is_counted_not_dropped_silently(self):
        index = panel_index(GRID, ["AAA"])
        events = events_of((1, "AAA", CALENDAR[7], "1.02"),
                           (2, "DEAD", CALENDAR[7], "3.01"))
        dummy = ceiling.event_dummy(events, GRID, CALENDAR, index)
        assert dummy.attrs["pairs_built"] == 2
        assert dummy.attrs["pairs_on_panel"] == 1

    def test_a_dual_class_issuer_marks_every_security_it_carries(self):
        index = panel_index(GRID, ["FOX", "FOXA"])
        events = pd.DataFrame([{"cik": 1, "ticker": "FOX", "tickers": "FOX|FOXA",
                                "session": CALENDAR[7], "items": "2.06"}])
        dummy = ceiling.event_dummy(events, GRID, CALENDAR, index)
        assert dummy.loc[(GRID[1], "FOX")] == 1.0
        assert dummy.loc[(GRID[1], "FOXA")] == 1.0


class TestPanelReach:
    def test_it_separates_off_grid_from_off_panel(self):
        index = panel_index(GRID, ["AAA"])
        events = events_of((1, "AAA", CALENDAR[7], "1.02"),      # on grid, on panel
                           (2, "DEAD", CALENDAR[7], "3.01"),     # on grid, off panel
                           (3, "AAA", CALENDAR[-1], "1.02"))     # off grid
        reach = ceiling.panel_reach(events, GRID, CALENDAR, index)
        assert reach["assigned_to_a_development_cutoff"] == 2
        assert reach["off_grid"] == 1
        assert reach["on_panel"] == 1
        assert reach["by_item"]["3.01"]["lost_share"] == 1.0
        assert reach["by_item"]["1.02"]["lost_share"] == 0.0


# ---------------------------------------------------------------------------
# The statistics
# ---------------------------------------------------------------------------

class TestPerCutoffSpearman:
    def test_a_thin_cross_section_is_skipped_not_included_noisily(self):
        index = panel_index([GRID[0]], [f"S{i}" for i in range(10)])
        x = pd.Series(np.arange(10.0), index=index)
        assert ceiling.per_cutoff_spearman(x, x).empty

    def test_a_constant_column_yields_no_cutoff(self):
        index = panel_index([GRID[0]], [f"S{i}" for i in range(60)])
        x = pd.Series(np.arange(60.0), index=index)
        assert ceiling.per_cutoff_spearman(x, pd.Series(1.0, index=index)).empty

    def test_a_perfect_monotone_relation_is_one(self):
        index = panel_index([GRID[0]], [f"S{i}" for i in range(60)])
        x = pd.Series(np.arange(60.0), index=index)
        rho = ceiling.per_cutoff_spearman(x, x ** 3)
        assert rho.iloc[0] == pytest.approx(1.0)


class TestRankBiserial:
    def test_no_shift_reads_near_zero(self):
        index = panel_index([GRID[0]], [f"S{i}" for i in range(100)])
        feature = pd.Series(np.arange(100.0), index=index)
        dummy = pd.Series(0.0, index=index)
        dummy.iloc[::10] = 1.0                       # evenly spread through the ranking
        assert abs(ceiling.rank_biserial(dummy, feature)["rank_biserial"]) < 0.10

    def test_events_at_the_bottom_read_strongly_negative(self):
        index = panel_index([GRID[0]], [f"S{i}" for i in range(100)])
        feature = pd.Series(np.arange(100.0), index=index)
        dummy = pd.Series(0.0, index=index)
        dummy.iloc[:10] = 1.0
        assert ceiling.rank_biserial(dummy, feature)["rank_biserial"] < -0.8

    def test_it_does_not_shrink_as_events_get_rarer(self):
        """The property that makes it the honest companion to a sparse Spearman."""
        index = panel_index([GRID[0]], [f"S{i}" for i in range(200)])
        feature = pd.Series(np.arange(200.0), index=index)
        scores = []
        for n in (2, 10, 40):
            dummy = pd.Series(0.0, index=index)
            dummy.iloc[:n] = 1.0
            scores.append(ceiling.rank_biserial(dummy, feature)["rank_biserial"])
        assert all(s < -0.75 for s in scores)

    def test_a_sparse_spearman_does_shrink_where_the_biserial_does_not(self):
        """Why the disclosure exists, demonstrated rather than asserted in prose."""
        index = panel_index([GRID[0]], [f"S{i}" for i in range(200)])
        feature = pd.Series(np.arange(200.0), index=index)
        dummy = pd.Series(0.0, index=index)
        dummy.iloc[:2] = 1.0
        spearman = abs(ceiling.per_cutoff_spearman(dummy, feature).iloc[0])
        biserial = abs(ceiling.rank_biserial(dummy, feature)["rank_biserial"])
        assert spearman < 0.2 and biserial > 0.9

    def test_an_empty_treated_group_is_nan_not_an_error(self):
        index = panel_index([GRID[0]], [f"S{i}" for i in range(10)])
        out = ceiling.rank_biserial(pd.Series(0.0, index=index),
                                    pd.Series(1.0, index=index))
        assert np.isnan(out["rank_biserial"])


class TestFrozenThresholds:
    def test_the_ceilings_are_the_ones_family_1_was_judged_against(self):
        assert ceiling.CEILING_MOMENTUM == 0.30
        assert ceiling.CEILING_INPUT == 0.50
