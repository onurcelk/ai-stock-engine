"""Stage 1 — freeze the information set and generate predictions.

Nothing in this module may read a bar dated after the cutoff it is working on.
The only data access is `pit.fetcher(cutoff)`, and `pit.future` is not imported.

What gets recorded per (cutoff, symbol):

* the information set itself (Step 1) — bar counts, first/last bar, last close;
* the consensus verdict from `ultimate.evaluate` (Step 2) — action, score,
  confidence, expected move, target price, and the sources behind it, per
  horizon as well as aggregated;
* each rule-based agent's standing position (Step 3), with the windows it was
  given, since those are sized from the pre-cutoff series length.

Run:  python -m validation.predict
"""

from __future__ import annotations

import datetime as dt
import json
import time

import numpy as np
import pandas as pd

from . import pit, schedule
from app.core import indicators, ultimate


def _reading_row(reading: ultimate.Reading) -> dict:
    return {
        "source": reading.name,
        "family": reading.family,
        "kind": reading.kind,
        "score": round(float(reading.score), 4),
        "says": reading.direction,
        "weight_pct": round(float(reading.weight) * 100, 2),
        "contribution": round(float(reading.contribution), 2),
        "hit_rate": round(float(reading.skill.hit_rate), 2) if reading.skill.samples else None,
        "calls": int(reading.skill.samples) or None,
        "independent": round(float(reading.skill.effective), 2) if reading.skill.samples else None,
        "edge_pts": round(float(reading.skill.edge), 3) if reading.skill.samples else None,
        "t_stat": round(float(reading.skill.t_stat), 3) if reading.skill.samples else None,
        "why_not": reading.skill.note,
    }


def _horizon_row(horizon: ultimate.HorizonVerdict) -> dict:
    if not horizon.available:
        return {
            "horizon": horizon.horizon.key,
            "label": horizon.horizon.label,
            "available": False,
            "unavailable": horizon.unavailable,
        }
    return {
        "horizon": horizon.horizon.key,
        "label": horizon.horizon.label,
        "available": True,
        "action": horizon.action,
        "score": round(float(horizon.score), 3),
        "confidence": round(float(horizon.confidence), 3),
        "agreement": round(float(horizon.agreement), 4),
        "coverage": round(float(horizon.coverage), 4),
        "weighted_edge": round(float(horizon.weighted_edge), 4),
        "expected_move_pct": round(float(horizon.expected_move_pct), 4),
        "typical_move_pct": round(float(horizon.typical_move_pct), 4),
        "target_price": round(float(horizon.target_price), 6),
        "last_price": round(float(horizon.last_price), 6),
        "bars_used": int(horizon.bars_used),
        "interval": horizon.interval,
        "rows": int(horizon.rows),
        "sources_counted": len(horizon.live),
        # Everything the horizon weighed, not only what survived — the report
        # has to be able to say why a call was small as well as why it was made.
        "readings": [_reading_row(r) for r in horizon.readings],
    }


def consensus_prediction(symbol: str, cutoff: pd.Timestamp) -> dict:
    """Step 2 — the production verdict, on frozen information."""
    verdict = ultimate.evaluate(symbol, fetcher=pit.fetcher(cutoff))
    horizons = [_horizon_row(h) for h in verdict.horizons]

    # The aggregate verdict has no expected move of its own; the strongest
    # readable horizon carries the price target, which is what the UI shows.
    strongest = max((h for h in verdict.available), key=lambda h: h.confidence,
                    default=None)
    return {
        "action": verdict.action,
        "score": round(float(verdict.score), 3),
        "confidence": round(float(verdict.confidence), 3),
        "alignment": verdict.alignment,
        "direction": int(np.sign(verdict.score)),
        "last_price": round(float(verdict.last_price), 6),
        "horizons_readable": len(verdict.available),
        "horizons_total": len(verdict.horizons),
        "errors": verdict.errors,
        "lead_horizon": strongest.horizon.key if strongest else None,
        "expected_move_pct": (round(float(strongest.expected_move_pct), 4)
                              if strongest else None),
        "target_price": (round(float(strongest.target_price), 6)
                         if strongest else None),
        "conclusion": verdict.conclusion,
        "by_horizon": horizons,
    }


def agent_predictions(symbol: str, cutoff: pd.Timestamp) -> dict:
    """Step 3 — each rule-based agent's standing position at the cutoff.

    `ultimate.agent_sources` is used rather than a re-implementation, so these
    are the same agents the consensus folds in and the same ones the Trading
    agents tab runs by default. Their windows are a function of the series
    length, so they are recorded: a 2022 cutoff gives an agent a different
    channel from a 2026 one, and that is part of the prediction.
    """
    frame = pit.frame_at(symbol, cutoff, interval="1d", period="10y")
    if frame is None or len(frame) < 60:
        return {"available": False,
                "reason": f"only {0 if frame is None else len(frame)} daily bars before cutoff"}

    sources = ultimate.agent_sources(frame["close"])
    out: dict[str, object] = {"available": True, "bars": int(len(frame)),
                              "last_price": float(frame["close"].iloc[-1])}
    agents = {}
    for key, source in sources.items():
        series = source.read(frame)
        stance = float(series.iloc[-1])
        # When the position last changed — an agent long since 2019 and one
        # that flipped yesterday are not the same claim.
        changes = series.ne(series.shift(1))
        held_since = frame["date"][changes].iloc[-1] if changes.any() else frame["date"].iloc[0]
        agents[key] = {
            "name": source.name,
            "stance": stance,
            "direction": int(np.sign(stance)),
            "signal": ("long" if stance > 0 else "short/flat" if stance < 0 else "no position"),
            "describe": source.describe,
            "held_since": str(pd.Timestamp(held_since).date()),
            # The agents emit a position, not a price. Recording None rather
            # than deriving one keeps rule 10: unavailable, not estimated.
            "target_price": None,
            "expected_return_pct": None,
        }
    out["agents"] = agents

    # The combined agent call: the majority position, which is what the
    # consensus's agent family reduces to once the family cap has its say.
    votes = [a["direction"] for a in agents.values()]
    combined = int(np.sign(sum(votes)))
    out["combined"] = {
        "direction": combined,
        "signal": "long" if combined > 0 else "short/flat" if combined < 0 else "split",
        "votes": votes,
        "unanimous": len(set(votes)) == 1,
    }
    return out


def run() -> dict:
    calendar = pit.trading_days()
    cutoff_list = schedule.cutoffs(calendar)
    symbols = schedule.symbols()

    started = time.time()
    records: list[dict] = []
    for entry in cutoff_list:
        cutoff = entry["date"]
        for symbol in symbols:
            record = {
                "cutoff": str(cutoff.date()),
                "cutoff_label": entry["label"],
                "cutoff_kind": entry["kind"],
                "symbol": symbol,
                "information_set": pit.describe_information_set(symbol, cutoff),
            }
            try:
                record["consensus"] = consensus_prediction(symbol, cutoff)
            except Exception as error:  # noqa: BLE001 — one dead symbol, not a dead study
                record["consensus"] = {"failed": str(error)}
            try:
                record["agents"] = agent_predictions(symbol, cutoff)
            except Exception as error:  # noqa: BLE001
                record["agents"] = {"available": False, "reason": str(error)}
            records.append(record)
        print(f"  {entry['label']:>14s}  {cutoff.date()}  ·  {len(symbols)} symbols "
              f"({time.time() - started:.0f}s elapsed)", flush=True)

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "stage": "predict",
        "as_of_last_bar": str(pd.Timestamp(calendar.iloc[-1]).date()),
        "seed": schedule.SEED,
        "symbols": symbols,
        "cutoffs": [{"date": str(c["date"].date()), "label": c["label"],
                     "kind": c["kind"]} for c in cutoff_list],
        "predictions": records,
    }


def main() -> None:
    pit.OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = pit.OUT_DIR / "predictions.json"
    if target.exists():
        # Rule 2: a frozen prediction is never regenerated. Overwriting one
        # after its outcome is known is the single failure this study exists
        # to avoid, so make it require a deliberate deletion.
        raise SystemExit(f"{target} already exists — delete it to re-run stage 1.")

    print("Stage 1 — generating point-in-time predictions (no future data)…")
    payload = run()
    target.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nFroze {len(payload['predictions'])} predictions to {target}")


if __name__ == "__main__":
    main()
