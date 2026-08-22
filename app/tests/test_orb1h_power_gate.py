"""orb_1h power gate: the breakout call and its PIT safety, plus the gate's
pass/fail arithmetic. Not a test of any predictive claim -- HT2_TOURNAMENT_
PREREGISTRATION.md SS4 is explicit that this gate touches variance only."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import orb1h_power_gate as gate_module


def _session(date: str, opens_highs_lows_closes: list[tuple[float, float, float, float]]):
    rows = []
    for i, (o, h, l, c) in enumerate(opens_highs_lows_closes):
        rows.append({
            "date": pd.Timestamp(f"{date} {9 + i}:30", tz="America/New_York").tz_convert("UTC"),
            "open": o, "high": h, "low": l, "close": c,
        })
    return rows


def _write_symbol(tmp_path, symbol: str, sessions: list[list[tuple]]):
    rows = []
    for i, session_bars in enumerate(sessions):
        date = f"2024-01-{2 + i:02d}"
        rows.extend(_session(date, session_bars))
    frame = pd.DataFrame(rows)
    frame.to_csv(tmp_path / f"{symbol}__1h.csv", index=False)


def test_a_close_above_the_opening_range_high_is_a_buy_call(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_module, "CACHE_DIR", tmp_path)
    # Bar 0 sets the range (99-101). Bar 1 closes at 105, above the high.
    # Bar 2 closes higher still, so the trade wins.
    _write_symbol(tmp_path, "AAA", [[(100, 101, 99, 100), (102, 106, 102, 105),
                                       (105, 110, 105, 108)]])
    monkeypatch.setattr(gate_module, "_symbols", lambda: ["AAA"])

    rows = gate_module._session_rows("AAA")
    assert len(rows) == 1
    assert rows.iloc[0]["advantage"] > 0     # BUY call, price rose further


def test_a_close_below_the_opening_range_low_is_a_sell_call(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_module, "CACHE_DIR", tmp_path)
    _write_symbol(tmp_path, "AAA", [[(100, 101, 99, 100), (98, 98, 94, 95),
                                       (95, 96, 90, 92)]])
    rows = gate_module._session_rows("AAA")
    assert len(rows) == 1
    # SELL call (-1) times a further negative move -> positive advantage
    assert rows.iloc[0]["advantage"] > 0


def test_a_close_inside_the_range_makes_no_call(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_module, "CACHE_DIR", tmp_path)
    _write_symbol(tmp_path, "AAA", [[(100, 101, 99, 100), (100, 100.5, 99.5, 100.2),
                                       (100.2, 101, 99, 100)]])
    rows = gate_module._session_rows("AAA")
    assert rows.empty


def test_sessions_with_fewer_than_three_bars_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_module, "CACHE_DIR", tmp_path)
    _write_symbol(tmp_path, "AAA", [[(100, 101, 99, 100), (105, 106, 104, 105)]])
    assert gate_module._session_rows("AAA").empty


def test_a_later_bar_does_not_change_an_earlier_bars_call(tmp_path, monkeypatch):
    """The PIT-relevant property for this candidate: the call is fixed by the
    opening range and the entry bar, not by how the session finishes."""
    monkeypatch.setattr(gate_module, "CACHE_DIR", tmp_path)
    _write_symbol(tmp_path, "AAA", [[(100, 101, 99, 100), (102, 106, 102, 105),
                                       (105, 999, 1, 500)]])
    rows = gate_module._session_rows("AAA")
    # Still exactly one row (one call for the session), regardless of how wild
    # the closing bar is -- the call itself was fixed at bar 1.
    assert len(rows) == 1


def test_gate_result_pass_fail_boundary():
    passing = gate_module.GateResult(n_sessions=10, n_dates=100, block_days=4,
                                      half_width_bp=38.9, mde_bp=39.0)
    failing = gate_module.GateResult(n_sessions=10, n_dates=100, block_days=4,
                                      half_width_bp=39.1, mde_bp=39.0)
    unresolved = gate_module.GateResult(n_sessions=0, n_dates=0, block_days=0,
                                         half_width_bp=float("nan"), mde_bp=39.0)
    assert passing.passes is True
    assert failing.passes is False
    assert unresolved.passes is False


def test_too_few_independent_dates_refuses_to_report_a_width(tmp_path, monkeypatch):
    monkeypatch.setattr(gate_module, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(gate_module, "_symbols", lambda: ["AAA"])
    _write_symbol(tmp_path, "AAA", [[(100, 101, 99, 100), (102, 106, 102, 105),
                                       (105, 110, 105, 108)]])
    result = gate_module.gate(min_dates=60)
    assert result.n_dates < 60
    assert np.isnan(result.half_width_bp)
    assert result.passes is False
