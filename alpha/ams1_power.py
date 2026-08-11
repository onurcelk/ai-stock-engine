"""AMS-1 §7 power gate. Computed from SIGNAL GEOMETRY ONLY — no outcome is read.

The gate asks one question: given how often the consensus ladder actually
reaches its extreme states, and how those observations are spread over dates and
symbols, can the study resolve the effects its hypotheses are about?

Every distributional input is a **marginal property of the target** already
measured and committed in `alpha/source_probe.py` at `4a966a2` — the standard
deviation of the 5-session return, its within-date correlation, and the
block-bootstrap inflation calibrated against Phase 1's own measured half-width.
No AMS-1 outcome, no conditioning, no feature enters it. That is what a §2.6
power gate is computed from in this programme.

Run:  python -m alpha.ams1_power
"""

from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from . import ams1_config as cfg
from . import ams1_meta as meta


def half_width(variance: float, rho: float, per_date: float, dates: float) -> float:
    """95% half-width of a mean over `dates` dates carrying `per_date` names each.

    Identical form to `source_probe.half_width`, which was calibrated to
    reproduce Phase 1's *measured* covered-book half-width exactly. Because the
    bracket tends to `rho` as `per_date` grows, breadth within a date buys very
    little — resolution comes from independent dates.
    """
    per_date = max(float(per_date), 1e-9)
    return float(cfg.BLOCK_INFLATION * 1.96
                 * (variance * (rho + (1.0 - rho) / per_date)
                    / max(dates, 1e-9)) ** 0.5)


def geometry(states: pd.Series) -> dict:
    """Rows, dates, symbols and per-date density for each ladder state."""
    out = {}
    total = int(states.notna().sum())
    for state in cfg.LADDER:
        block = states[states == state]
        if block.empty:
            out[state] = {"rows": 0}
            continue
        cutoffs = block.index.get_level_values(0)
        out[state] = {
            "rows": int(len(block)),
            "coverage": round(len(block) / max(total, 1), 4),
            "cutoffs": int(cutoffs.nunique()),
            "symbols": int(block.index.get_level_values(1).nunique()),
            "rows_per_cutoff_mean": round(float(len(block) / cutoffs.nunique()), 3),
            "rows_per_cutoff_max": int(block.groupby(level=0).size().max()),
        }
    return out


def resolution(rows: int, cutoffs: int) -> dict:
    """Directional and economic MDE for a bucket of `rows` over `cutoffs` dates."""
    per_date = rows / max(cutoffs, 1)
    up = half_width(cfg.UP_VAR, cfg.UP_RHO, per_date, cutoffs)
    ret = half_width(cfg.RETURN_SD ** 2, cfg.RETURN_RHO, per_date, cutoffs)
    return {"rows": rows, "cutoffs": cutoffs,
            "rows_per_cutoff": round(per_date, 3),
            "directional_mde_pp": round(100 * up, 3),
            "economic_mde_bp": round(1e4 * ret, 1),
            "sub50_shift_required_pp": round(
                100 * (cfg.BASE_UP_RATE - cfg.SUB_50) + 100 * up, 3)}


def gate(states: pd.Series) -> dict:
    """The §7 geometry check and the §8 Gate 1 verdict."""
    shape = geometry(states)
    extremes = ("strong bearish", "strong bullish")
    per_state = {}
    for state, got in shape.items():
        if not got.get("rows"):
            per_state[state] = {"rows": 0, "meets_minimum": False}
            continue
        got = dict(got, **resolution(got["rows"], got["cutoffs"]))
        got["meets_minimum"] = bool(
            got["rows"] >= cfg.MIN_BUCKET_ROWS
            and got["cutoffs"] >= cfg.MIN_BUCKET_CUTOFFS
            and got["symbols"] >= cfg.MIN_BUCKET_SYMBOLS)
        per_state[state] = got

    passed = all(per_state[s].get("meets_minimum") for s in extremes)
    return {
        "minimum_geometry": {"rows": cfg.MIN_BUCKET_ROWS,
                             "cutoffs": cfg.MIN_BUCKET_CUTOFFS,
                             "symbols": cfg.MIN_BUCKET_SYMBOLS},
        "states": per_state,
        "extremes_measurable": passed,
        "gate_1_power": "PASS" if passed else "FAIL",
    }


def main() -> int:
    stances = pd.read_pickle(cfg.SIGNALS_PATH)
    votes = meta.family_votes(stances)
    signals = meta.meta_signals(stances, votes)
    states = pd.Series(meta.ladder_state(signals["M3_family_net_vote"]),
                       index=stances.index)
    raw_states = pd.Series(meta.raw_ladder_state(signals["M1_raw_net_vote"]),
                           index=stances.index)

    payload = {
        "measured_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "Signal geometry only. No forward return, target or label was "
                "read. Variance inputs are the marginal target properties "
                "committed in alpha/source_probe.py.",
        "rows": int(len(stances)),
        "cutoffs": int(stances.index.get_level_values(0).nunique()),
        "symbols": int(stances.index.get_level_values(1).nunique()),
        "agents": sorted(stances.columns),
        "availability": {c: round(float(stances[c].notna().mean()), 4)
                         for c in stances.columns},
        "family_vote_balance": {
            f: {"buy": round(float((votes[f] > 0).mean()), 4),
                "flat": round(float((votes[f] == 0).mean()), 4),
                "sell": round(float((votes[f] < 0).mean()), 4),
                "absent": round(float(votes[f].isna().mean()), 4)}
            for f in votes.columns},
        "variance_inputs": {"return_sd": cfg.RETURN_SD, "return_rho": cfg.RETURN_RHO,
                            "up_variance": cfg.UP_VAR, "up_rho": cfg.UP_RHO,
                            "block_inflation": cfg.BLOCK_INFLATION,
                            "base_up_rate": cfg.BASE_UP_RATE},
        "family_ladder": gate(states),
        "raw_ladder": gate(raw_states),
    }
    cfg.POWER_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"rows {payload['rows']:,}  cutoffs {payload['cutoffs']}  "
          f"symbols {payload['symbols']}")
    print("\nfamily vote balance:")
    for family, got in payload["family_vote_balance"].items():
        print(f"  {family:20s} buy {got['buy']:.3f}  flat {got['flat']:.3f}  "
              f"sell {got['sell']:.3f}  absent {got['absent']:.3f}")
    print(f"\n{'state':18s} {'rows':>7s} {'cover':>7s} {'dates':>6s} {'syms':>5s} "
          f"{'k/date':>7s} {'dir pp':>7s} {'ret bp':>7s} {'min':>5s}")
    for state, got in payload["family_ladder"]["states"].items():
        if not got.get("rows"):
            print(f"  {state:16s} {'0':>7s}")
            continue
        print(f"{state:18s} {got['rows']:7,} {got['coverage']:7.3f} "
              f"{got['cutoffs']:6d} {got['symbols']:5d} {got['rows_per_cutoff']:7.2f} "
              f"{got['directional_mde_pp']:7.2f} {got['economic_mde_bp']:7.1f} "
              f"{'yes' if got['meets_minimum'] else 'NO':>5s}")
    print(f"\nGate 1 (power): {payload['family_ladder']['gate_1_power']}")
    print(f"wrote {cfg.POWER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
