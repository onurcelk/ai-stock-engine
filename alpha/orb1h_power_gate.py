"""orb_1h power gate -- alpha/HT2_TOURNAMENT_PREREGISTRATION.md SS4.

Estimates the achievable half-width for the hourly-bar opening-range-breakout
proxy on the free `1h` history this repository already has cached locally
(`app/cache/*__1h.csv`, accumulated since 2023-09-26 -- no network fetch
needed here), **before any predictive quantity is read**. Follows the same
centre-before-inspecting discipline as `alpha/pead1_power_gate.py` and
`reports/V5_HISTORICAL_REPLAY.md`'s precedent: the per-session advantage is
computed (unavoidable), immediately centred on its own mean, and only the
centred series's bootstrap half-width is ever printed or written.

Reuses `HT2_TOURNAMENT_PREREGISTRATION.md`'s own MDE reference (39 bp, Single-
Name Phase 1's covered-book resolution) rather than deriving a new one, for
the same reason PEAD-1's gate does: one standing reference for this
programme's single-name absolute-return claims, not a fresh number per study.
"""

from __future__ import annotations

import dataclasses
import pathlib

import numpy as np
import pandas as pd

from . import stats

CACHE_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "cache"
MDE_BP = 39.0


@dataclasses.dataclass(frozen=True)
class GateResult:
    n_sessions: int
    n_dates: int
    block_days: int
    half_width_bp: float
    mde_bp: float

    @property
    def passes(self) -> bool:
        return bool(np.isfinite(self.half_width_bp) and self.half_width_bp <= self.mde_bp)


def _symbols() -> list[str]:
    return sorted({p.name.split("__1h.csv")[0] for p in CACHE_DIR.glob("*__1h.csv")})


def _session_rows(symbol: str) -> pd.DataFrame:
    """One row per (symbol, session-date): the opening-range breakout call and
    its same-session close-to-close outcome. Raw, unaggregated, uncentred --
    `gate()` consumes this and it is never printed or written as-is.
    """
    frame = pd.read_csv(CACHE_DIR / f"{symbol}__1h.csv")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise", utc=True)
    frame = frame.sort_values("date").reset_index(drop=True)
    frame["session"] = frame["date"].dt.tz_convert("America/New_York").dt.date

    rows: list[dict] = []
    for session, group in frame.groupby("session"):
        if len(group) < 3:
            continue
        group = group.reset_index(drop=True)
        range_high, range_low = float(group["high"].iloc[0]), float(group["low"].iloc[0])
        if not (np.isfinite(range_high) and np.isfinite(range_low)) or range_high <= range_low:
            continue
        entry_close = float(group["close"].iloc[1])
        session_close = float(group["close"].iloc[-1])
        if entry_close >= range_high:
            call = 1.0
        elif entry_close <= range_low:
            call = -1.0
        else:
            continue                                    # no breakout, no call
        realised = session_close / entry_close - 1.0
        rows.append({"symbol": symbol, "date": session, "advantage": realised * call})
    return pd.DataFrame(rows)


def gate(*, min_dates: int = 60) -> GateResult:
    raw = pd.concat([_session_rows(s) for s in _symbols()], ignore_index=True)
    if raw.empty:
        return GateResult(0, 0, 0, float("nan"), MDE_BP)

    per_date = raw.groupby("date")["advantage"].mean().sort_index()
    n_dates = len(per_date)
    if n_dates < min_dates:
        return GateResult(len(raw), n_dates, 0, float("nan"), MDE_BP)

    values = per_date.to_numpy(dtype=float)
    centred = values - values.mean()               # the mean is discarded here
    del values

    autocorr = pd.Series(centred).autocorr(lag=1)
    block = 4 if not np.isfinite(autocorr) or autocorr < 0.15 else (
        8 if autocorr < 0.30 else 15)
    block = min(block, max(1, n_dates // 5))

    ci_low, ci_high = stats.block_bootstrap_ci(centred, block=block,
                                                draws=stats.BOOTSTRAP_DRAWS)
    half_width_bp = float((ci_high - ci_low) / 2.0 * 1e4)
    return GateResult(len(raw), n_dates, block, half_width_bp, MDE_BP)


def main() -> int:
    result = gate()
    hw = f"{result.half_width_bp:.1f}" if np.isfinite(result.half_width_bp) else "n/a"
    print(f"Sessions with a breakout call: {result.n_sessions}")
    print(f"Independent dates:             {result.n_dates}")
    print(f"Block length (days):           {result.block_days}")
    print(f"Achieved half-width:           {hw} bp")
    print(f"MDE (SN1 reference):           {result.mde_bp:.1f} bp")
    print()
    print(f"orb_1h GATE: {'PASS' if result.passes else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
