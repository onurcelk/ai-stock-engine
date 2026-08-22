"""VIX1 power gate -- alpha/VIX1_PREREGISTRATION.md SS5. Half-width only.

Reuses HT-1's exact grid (`core.tournament.build_grid`/`admissible_cells`) and
`core.pine.williams_vix_fix`'s flag, unmodified. Follows the same
centre-before-inspecting discipline as `alpha/pead1_power_gate.py` and
`alpha/orb1h_power_gate.py`: the per-cutoff advantage series is computed
(unavoidable), immediately centred on its own mean, and only the centred
series's bootstrap half-width is ever printed or returned.
"""

from __future__ import annotations

import dataclasses
import pathlib
import sys

import numpy as np
import pandas as pd

from . import stats

_APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

WINDOWS = (5, 20)


@dataclasses.dataclass(frozen=True)
class GateResult:
    window: int
    n_flags: int
    n_cutoffs: int
    block: int
    half_width_points: float
    mde_points: float = 3.0

    @property
    def passes(self) -> bool:
        return bool(np.isfinite(self.half_width_points)
                     and self.half_width_points <= self.mde_points)


def _realised_vol(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return float("nan")
    return float(np.std(returns, ddof=1) * np.sqrt(252) * 100.0)


def _flag_rows(window: int) -> pd.DataFrame:
    """One row per flagged (symbol, cutoff): trailing/forward realised vol.

    Raw and uncentred -- `gate()` and `measure()` (in the confirmatory module)
    consume this; it is never printed or written as-is.
    """
    from core import pine, tournament                    # noqa: E402 (sys.path set above)

    frames = tournament.load_frames()
    grid = tournament.build_grid(frames)
    cells = tournament.admissible_cells(frames, grid)

    rows: list[dict] = []
    for cell in cells:
        frame = frames[cell.symbol]
        position = cell.position
        if position - window < 0 or position + window >= len(frame):
            continue
        truncated = frame.iloc[: position + 1]
        try:
            flagged = bool(pine.williams_vix_fix(truncated)["bottom"].iloc[-1])
        except Exception:                                       # noqa: BLE001
            continue
        if not flagged:
            continue

        closes = frame["close"].to_numpy()
        trailing_returns = closes[position - window + 1: position + 1] / \
            closes[position - window: position] - 1.0
        forward_returns = closes[position + 1: position + window + 1] / \
            closes[position: position + window] - 1.0
        trailing_vol = _realised_vol(trailing_returns)
        forward_vol = _realised_vol(forward_returns)
        if not (np.isfinite(trailing_vol) and np.isfinite(forward_vol)):
            continue

        rows.append({
            "symbol": cell.symbol, "cutoff": cell.cutoff,
            "advantage": trailing_vol - forward_vol,
        })
    return pd.DataFrame(rows)


def gate(*, min_cutoffs: int = 20) -> list[GateResult]:
    results: list[GateResult] = []
    for window in WINDOWS:
        raw = _flag_rows(window)
        if raw.empty:
            results.append(GateResult(window, 0, 0, 0, float("nan")))
            continue
        per_cutoff = raw.groupby("cutoff")["advantage"].mean().sort_index()
        n_cutoffs = len(per_cutoff)
        if n_cutoffs < min_cutoffs:
            results.append(GateResult(window, len(raw), n_cutoffs, 0, float("nan")))
            continue

        values = per_cutoff.to_numpy(dtype=float)
        centred = values - values.mean()          # the mean is discarded here
        del values

        block = 4
        ci_low, ci_high = stats.block_bootstrap_ci(centred, block=block,
                                                    draws=stats.BOOTSTRAP_DRAWS)
        half_width = float((ci_high - ci_low) / 2.0)

        results.append(GateResult(
            window=window, n_flags=len(raw), n_cutoffs=n_cutoffs, block=block,
            half_width_points=half_width))
    return results


def main() -> int:
    results = gate()
    print(f"{'Window':>8} {'Flags':>8} {'Cutoffs':>8} {'Block':>7} "
          f"{'Half-width(pts)':>16} {'MDE(pts)':>10}  Verdict")
    any_pass = False
    for r in results:
        verdict = "PASS" if r.passes else "FAIL"
        if r.passes:
            any_pass = True
        hw = f"{r.half_width_points:.2f}" if np.isfinite(r.half_width_points) else "n/a"
        print(f"{r.window:>8} {r.n_flags:>8} {r.n_cutoffs:>8} {r.block:>7} "
              f"{hw:>16} {r.mde_points:>10.1f}  {verdict}")
    print()
    print("VIX1 GATE: at least one window PASSES" if any_pass
          else "VIX1 GATE: ALL WINDOWS FAIL -- VIX1 MUST NOT RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
