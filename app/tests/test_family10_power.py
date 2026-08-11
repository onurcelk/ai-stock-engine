"""Family 10 Stage 3: the independent-information machinery, before any half-width.

The block length is a frozen constant and the gate is a measurement; what can be
tested is the machinery that decides which events are usable and how many
independent units they represent — plus the ordering guarantee itself, that the
freeze step cannot emit a half-width.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import examset, family10_power as power  # noqa: E402


CALENDAR = pd.DatetimeIndex(pd.bdate_range("2021-01-04", periods=200))


def events_of(*specs) -> pd.DataFrame:
    return pd.DataFrame([{"cik": cik, "ticker": ticker, "tickers": ticker,
                          "session": pd.Timestamp(session), "items": items}
                         for cik, ticker, session, items in specs])


class TestFrozenBlockLength:
    def test_the_block_is_twenty_four_sessions(self):
        assert power.BLOCK_LENGTH == 24

    def test_it_covers_the_mechanical_overlap(self):
        """Two events closer than the horizon share forward sessions."""
        assert power.BLOCK_LENGTH >= power.HORIZON

    def test_it_carries_the_record_s_own_persistence_allowance(self):
        """alpha/stats.py: block length 4 cutoffs (~one month) at H=5 with q=0."""
        from alpha import stats
        allowance = stats.BLOCK_LENGTH * 5          # 4 cutoffs x 5 sessions
        assert power.BLOCK_LENGTH == (power.HORIZON - 1) + allowance

    def test_it_is_more_conservative_than_both_survey_columns(self):
        assert power.BLOCK_LENGTH > 10 > 5
        blocks = 2664 // power.BLOCK_LENGTH
        assert blocks < power.SURVEY_BLOCKS_10D < power.SURVEY_BLOCKS_5D


class TestDevelopmentSafe:
    def test_an_event_on_an_exam_cutoff_is_excluded(self):
        exam = [CALENDAR[100]]
        events = events_of((1, "AAA", CALENDAR[100], "1.02"))
        assert not power.development_safe(events, CALENDAR, exam).iloc[0]

    def test_the_separation_is_the_examset_s_own(self):
        exam = [CALENDAR[100]]
        just_inside = events_of((1, "AAA", CALENDAR[100 - examset.MIN_SEPARATION + 1],
                                 "1.02"))
        just_outside = events_of((1, "AAA", CALENDAR[100 - examset.MIN_SEPARATION],
                                  "1.02"))
        assert not power.development_safe(just_inside, CALENDAR, exam).iloc[0]
        assert power.development_safe(just_outside, CALENDAR, exam).iloc[0]

    def test_it_is_symmetric_around_the_exam_cutoff(self):
        exam = [CALENDAR[100]]
        before = events_of((1, "AAA", CALENDAR[100 - examset.MIN_SEPARATION], "1.02"))
        after = events_of((1, "AAA", CALENDAR[100 + examset.MIN_SEPARATION], "1.02"))
        assert power.development_safe(before, CALENDAR, exam).iloc[0]
        assert power.development_safe(after, CALENDAR, exam).iloc[0]

    def test_every_exam_cutoff_is_checked_not_just_the_nearest_one(self):
        exam = [CALENDAR[20], CALENDAR[100], CALENDAR[180]]
        events = events_of((1, "AAA", CALENDAR[20], "1.02"),
                           (2, "BBB", CALENDAR[60], "1.02"),
                           (3, "CCC", CALENDAR[180], "1.02"))
        safe = power.development_safe(events, CALENDAR, exam)
        assert list(safe) == [False, True, False]


class TestOnPanel:
    def test_a_name_the_panel_carries_is_kept(self):
        grid = list(CALENDAR[4::5])
        index = pd.MultiIndex.from_product([pd.DatetimeIndex(grid), ["AAA"]],
                                           names=["cutoff", "symbol"])
        events = events_of((1, "AAA", CALENDAR[7], "1.02"))
        assert power.on_panel(events, grid, CALENDAR, index).iloc[0]

    def test_a_name_the_panel_cannot_carry_is_dropped(self):
        grid = list(CALENDAR[4::5])
        index = pd.MultiIndex.from_product([pd.DatetimeIndex(grid), ["AAA"]],
                                           names=["cutoff", "symbol"])
        events = events_of((1, "DEAD", CALENDAR[7], "3.01"))
        assert not power.on_panel(events, grid, CALENDAR, index).iloc[0]

    def test_a_dual_class_issuer_only_needs_one_of_its_securities(self):
        grid = list(CALENDAR[4::5])
        index = pd.MultiIndex.from_product([pd.DatetimeIndex(grid), ["FOXA"]],
                                           names=["cutoff", "symbol"])
        events = pd.DataFrame([{"cik": 1, "ticker": "FOX", "tickers": "FOX|FOXA",
                                "session": CALENDAR[7], "items": "2.06"}])
        assert power.on_panel(events, grid, CALENDAR, index).iloc[0]


class TestBlockStructure:
    def test_events_in_one_block_are_not_counted_as_independent(self):
        events = events_of(*[(i, f"S{i}", CALENDAR[i], "1.02") for i in range(10)])
        got = power.block_structure(events, CALENDAR, block=24)
        assert got["events"] == 10
        assert got["occupied_blocks"] == 1

    def test_events_spread_across_blocks_occupy_them(self):
        events = events_of(*[(i, f"S{i}", CALENDAR[i * 30], "1.02") for i in range(6)])
        got = power.block_structure(events, CALENDAR, block=24)
        assert got["occupied_blocks"] == 6

    def test_the_total_block_count_follows_the_calendar_not_the_events(self):
        events = events_of((1, "AAA", CALENDAR[0], "1.02"))
        got = power.block_structure(events, CALENDAR, block=24)
        assert got["total_blocks"] == len(CALENDAR) // 24

    def test_issuer_repetition_inside_a_block_is_counted(self):
        events = events_of((1, "AAA", CALENDAR[0], "1.02"),
                           (1, "AAA", CALENDAR[3], "2.06"),
                           (1, "AAA", CALENDAR[100], "2.05"))
        got = power.block_structure(events, CALENDAR, block=24)
        assert got["same_issuer_pairs"] == 2
        assert got["same_issuer_pairs_under_block"] == 1
        assert got["same_issuer_pairs_under_horizon"] == 1


class TestTheOrdering:
    def test_the_freeze_artefact_carries_no_half_width(self):
        """The whole point of running --freeze first, asserted rather than trusted."""
        import json
        payload = json.loads(power.FREEZE_PATH.read_text(encoding="utf-8"))

        def keys(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    yield key
                    yield from keys(value)

        forbidden = ("half_width", "mde", "verdict", "passed", "detectable")
        for key in keys(payload):
            assert not any(word in key.lower() for word in forbidden), key

    def test_the_gate_refuses_a_block_length_that_moved(self, monkeypatch):
        monkeypatch.setattr(power, "BLOCK_LENGTH", 999)
        with pytest.raises(SystemExit):
            power.run_gate(verbose=False)


class TestResolutionSurface:
    def test_more_blocks_narrow_the_half_width(self):
        wide = power.gate(1000, 100)
        narrow = power.gate(1000, 400)
        assert narrow["economic_mde_bp"] < wide["economic_mde_bp"]

    def test_the_sub_fifty_claim_needs_the_baseline_gap_on_top(self):
        got = power.gate(1000, 111)
        assert got["sub50_shift_required_pp"] == pytest.approx(
            got["sub50_baseline_gap_pp"] + got["directional_mde_pp"], abs=0.01)
        assert got["sub50_baseline_gap_pp"] == pytest.approx(3.7, abs=0.01)

    def test_k_times_d_equals_the_sample(self):
        """The accounting the survey caught itself getting wrong."""
        got = power.gate(1110, 111)
        assert got["per_date"] * got["independent_dates"] == pytest.approx(1110, rel=1e-6)
