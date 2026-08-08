"""Deliverable 6 — V1, V2, momentum and the trivial rule, on identical dates.

The comparison the directive asks for is only worth anything if everything is
scored on **one yardstick**, and the yardstick has to be V2's, because V1's
cannot be extended: V1 predicted the direction of an absolute return, and
"direction was right" has no cross-sectional analogue. So everything here is
scored on `alpha_5d` — the realised 5-session return in excess of SPY — which
is a number every contender can be made to produce a position against.

Contenders, all on the twelve frozen exam cutoffs:

* **V2-F long-short** — top quintile minus bottom quintile by predicted alpha,
  equal names per side. The market-neutral spread of §16-17.
* **V2-F long-only** — the top quintile alone, to show how much of the spread
  is the long leg.
* **A′ mom_5d(−1)** — the frozen best simple factor. Same construction.
* **mom_12_1** — classic 12-1 momentum, the factor that was dead in run 1.
* **Always long** — hold the whole eligible cross-section, equal weight. The
  trivial rule, and the one V1 found nothing could beat.
* **V1 consensus (1w)** — the frozen V1 calls on the same dates, restricted to
  the thirteen symbols that are in both universes, signed by its own action and
  scored on the same `alpha_5d`.

The V1 row is the one to read carefully. Its universe is 13 names against V2's
~490, it abstained on most of them, and V1's own report already concluded its
consensus had no edge. It is here because the directive asks for it on
identical dates, not because 13 names on 12 days can settle anything.

Run:  python -m alpha.compare
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

from . import build_panel, develop, exam as exam_module, models, stats

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
COMPARISON_PATH = OUT_DIR / "comparison.json"
V1_PREDICTIONS = pathlib.Path(__file__).resolve().parents[1] / "validation" / "out" / "predictions.json"

QUINTILE = 0.2
BUY_ACTIONS = {"BUY", "STRONG BUY"}
SELL_ACTIONS = {"SELL", "STRONG SELL"}


def _legs(frame: pd.DataFrame, score: str, target: str = "alpha_5d") -> pd.DataFrame:
    """Per-cutoff top/bottom/spread for one scoring column."""
    return stats.quintile_spread(frame, score, target, fraction=QUINTILE)


def _series(values: pd.Series, name: str) -> dict:
    return stats.Series(name, values, null=0.0).row()


def v1_rows(exam_cutoffs: list[pd.Timestamp]) -> tuple[pd.DataFrame, dict]:
    """V1's frozen 1-week consensus, as (cutoff, symbol) -> signed position."""
    if not V1_PREDICTIONS.exists():
        return pd.DataFrame(columns=["cutoff", "symbol", "position"]), {}

    blob = json.loads(V1_PREDICTIONS.read_text(encoding="utf-8"))
    wanted = {str(pd.Timestamp(c).date()) for c in exam_cutoffs}
    rows, counts = [], {"readable": 0, "unreadable": 0, "hold": 0, "acted": 0}

    for record in blob["predictions"]:
        cutoff = record["cutoff"]
        if cutoff not in wanted:
            continue
        horizon = next((h for h in record["consensus"]["by_horizon"]
                        if h["horizon"] == "1w"), None)
        if horizon is None or not horizon.get("available"):
            counts["unreadable"] += 1
            continue
        counts["readable"] += 1
        action = horizon.get("action")
        position = 1 if action in BUY_ACTIONS else (-1 if action in SELL_ACTIONS else 0)
        if position == 0:
            counts["hold"] += 1
        else:
            counts["acted"] += 1
        rows.append({"cutoff": pd.Timestamp(cutoff), "symbol": record["symbol"],
                     "position": position, "action": action})

    return pd.DataFrame(rows), counts


def main() -> None:
    panel, _development, exam_cutoffs = build_panel.load()
    panel = panel.slice_cutoffs(exam_cutoffs)
    frame = panel.frame

    if not exam_module.PREDICTIONS_PATH.exists():
        raise SystemExit("no exam predictions — run: python -m alpha.exam predict")
    payload = json.loads(exam_module.PREDICTIONS_PATH.read_text(encoding="utf-8"))
    predictions = pd.DataFrame(payload["predictions"])
    predictions["cutoff"] = pd.to_datetime(predictions["cutoff"])
    predictions = predictions.set_index(["cutoff", "symbol"]).sort_index()

    scored = frame[["alpha_5d"]].copy()
    scored["v2f"] = predictions["predicted"]
    factors = models.simple_factor_scores(frame)
    scored["mom_5d_reversal"] = -factors["mom_5d"]
    scored["mom_12_1"] = factors["mom_12_1"]

    contenders: dict[str, dict] = {}

    for label, column in (("V2-F", "v2f"),
                          ("A′ mom_5d(−1)", "mom_5d_reversal"),
                          ("mom_12_1", "mom_12_1")):
        legs = _legs(scored, column)
        contenders[f"{label} long-short"] = _series(legs["spread"], f"{label} long-short")
        contenders[f"{label} long-only"] = _series(legs["top"], f"{label} long-only")

    # The trivial rule: hold everything, equal weight, and collect the
    # cross-section's own excess return over SPY.
    always_long = scored.groupby(level=0)["alpha_5d"].mean()
    contenders["Always long (equal weight)"] = _series(always_long, "always long")

    # V1, on the symbols the two universes share.
    v1, counts = v1_rows(exam_cutoffs)
    v1_row, v1_detail = None, {}
    if len(v1):
        joined = v1.set_index(["cutoff", "symbol"]).join(frame[["alpha_5d"]], how="inner")
        acted = joined[joined["position"] != 0]
        v1_detail = {
            "symbols_in_both_universes": sorted(set(joined.index.get_level_values(1))),
            "v1_symbols_total": 30,
            "pairs_scored": int(len(joined)),
            "pairs_acted": int(len(acted)),
            "abstention_rate": round(1 - len(acted) / len(joined), 4) if len(joined) else None,
            "readable_1w_slots": counts.get("readable"),
            "unreadable_1w_slots": counts.get("unreadable"),
        }
        if len(acted):
            per_cutoff = (acted["position"] * acted["alpha_5d"]).groupby(level=0).mean()
            v1_row = _series(per_cutoff, "V1 consensus 1w (acted calls)")
            contenders["V1 consensus 1w (acted calls, 13 shared names)"] = v1_row

    # Print
    print(f"comparison on {len(panel.cutoffs)} identical cutoffs, "
          f"{exam_cutoffs[0].date()} .. {exam_cutoffs[-1].date()}")
    print(f"{'contender':<48} {'mean':>10} {'95% CI':>22} {'hit':>7} {'n':>4}")
    for name, row in contenders.items():
        ci = f"[{row['boot_lo']:+.5f},{row['boot_hi']:+.5f}]"
        print(f"{name:<48} {row['mean']:>+10.5f} {ci:>22} "
              f"{row['hit_rate']:>7.1%} {row['n_cutoffs']:>4d}")

    if v1_detail:
        print(f"\nV1 overlap: {v1_detail['pairs_scored']} (cutoff, symbol) pairs on "
              f"{len(v1_detail['symbols_in_both_universes'])} shared names; "
              f"abstained on {v1_detail['abstention_rate']:.1%}")
        print(f"            {v1_detail['symbols_in_both_universes']}")
        print("            the other 17 V1 symbols are crypto, FX, ETFs or non-members — "
              "the §2 asset-class problem V2 removed")

    record = {
        "written_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "cutoffs": [str(pd.Timestamp(c).date()) for c in panel.cutoffs],
        "target": "alpha_5d (5-session return in excess of SPY)",
        "quintile_fraction": QUINTILE,
        "contenders": contenders,
        "v1_overlap": v1_detail,
        "note": ("All contenders scored on one yardstick. V1's own metric "
                 "(directional accuracy on absolute return) has no "
                 "cross-sectional analogue, so V1 is re-scored here on alpha_5d "
                 "using the sign of its frozen 1-week action."),
    }
    COMPARISON_PATH.write_text(json.dumps(develop._jsonable(record), indent=2),
                               encoding="utf-8")
    print(f"\nwrote      {COMPARISON_PATH}")


if __name__ == "__main__":
    main()
