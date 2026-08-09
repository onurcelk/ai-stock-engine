"""Stage 1b — the neural forecaster, on frozen information.

Same rule as `predict.py`: no bar after the cutoff is readable. The model is
trained from scratch at every cutoff on the 1,250 daily bars ending there,
which is what `streamlit_app.py` hands it in production (`daily.tail(1250)`,
LSTM, 3 folds, 30 epochs, 64 units, 5-bar horizon). None of those were tuned
for this study.

Each experiment produces two things, and the pairing is the point:

* a **projection** past the cutoff — the actual prediction, with no accuracy
  attached to it, because nothing it predicts has happened yet;
* a **walk-forward** over the pre-cutoff series — three rolling-origin folds
  the model never trained on, which is the only track record available at
  prediction time and the number `ultimate.ModelEvidence` weights it by.

It also records the production verdict *with* the model folded in, so the
scorer can ask whether the forecaster added anything to the consensus rather
than only whether it was right on its own.

Runs ~35 s per experiment and appends to `out/model.jsonl` as it goes, so a
long run stays useful if it is interrupted.

Run:  python -m validation.model
"""

from __future__ import annotations

import datetime as dt
import json
import time

import numpy as np
import pandas as pd

from . import pit, schedule
from app.core import forecast, ultimate

MODEL_NAME = "LSTM"
MODEL_BARS = 1_250


def experiment(symbol: str, cutoff: pd.Timestamp) -> dict:
    """One point-in-time forecast, measured and projected."""
    daily = pit.frame_at(symbol, cutoff, interval="1d", period="10y")
    if daily is None:
        return {"available": False, "reason": "no daily bars before cutoff"}

    usable = daily.tail(MODEL_BARS).reset_index(drop=True)
    possible = forecast.max_folds(len(usable), schedule.MODEL_HORIZON)
    if possible < 2:
        return {"available": False,
                "reason": f"{len(usable)} bars supports {possible} folds; "
                          "an unmeasured forecast carries no weight"}

    folds_used = min(schedule.MODEL_FOLDS, possible)
    walk = forecast.walk_forward(
        usable["close"], usable["date"], folds=folds_used,
        horizon=schedule.MODEL_HORIZON, model=MODEL_NAME,
        size_layer=schedule.MODEL_UNITS, epochs=schedule.MODEL_EPOCHS,
    )
    projection = forecast.project(
        usable["close"], usable["date"], model=MODEL_NAME,
        size_layer=schedule.MODEL_UNITS, epochs=schedule.MODEL_EPOCHS,
        horizon=schedule.MODEL_HORIZON,
    )
    summary = walk.summary()

    evidence = ultimate.ModelEvidence(
        name=f"{MODEL_NAME} forecast",
        interval="1d",
        horizon_bars=projection.horizon,
        predicted_move_pct=projection.move_pct,
        directional_pct=summary["mean_directional"],
        samples=len(walk.folds) * walk.horizon,
    )
    # The same verdict the app shows with "Include the forecast" switched on.
    with_model = ultimate.evaluate(symbol, model=evidence,
                                   fetcher=pit.fetcher(cutoff))

    return {
        "available": True,
        "model": MODEL_NAME,
        "bars_trained_on": int(len(usable)),
        "train_first_bar": str(usable["date"].iloc[0].date()),
        "train_last_bar": str(usable["date"].iloc[-1].date()),
        "horizon_bars": int(projection.horizon),
        "last_price": round(float(projection.last_price), 6),
        # ---- the prediction itself
        "predicted_path": [round(float(v), 6) for v in projection.path],
        "predicted_price": round(float(projection.final), 6),
        "predicted_move_pct": round(float(projection.move_pct), 4),
        "direction": int(projection.direction),
        # ---- its track record, measured before the cutoff
        "walk_forward": {
            "folds": folds_used,
            "horizon": int(walk.horizon),
            "samples": int(len(walk.folds) * walk.horizon),
            "mean_directional_pct": round(float(summary["mean_directional"]), 3),
            "std_directional_pct": round(float(summary["std_directional"]), 3),
            "mean_accuracy_pct": round(float(summary["mean_accuracy"]), 3),
            "mean_naive_accuracy_pct": round(float(summary["mean_naive"]), 3),
            "mean_mae": round(float(summary["mean_mae"]), 5),
            "folds_beating_naive": int(walk.folds_beating_naive),
            "per_fold_directional": [round(float(f.directional), 2) for f in walk.folds],
        },
        # ---- what the consensus does once it is folded in
        "consensus_with_model": {
            "action": with_model.action,
            "score": round(float(with_model.score), 3),
            "confidence": round(float(with_model.confidence), 3),
            "direction": int(np.sign(with_model.score)),
            "alignment": with_model.alignment,
            "model_weight_pct": {
                h.horizon.key: round(
                    next((r.weight * 100 for r in h.readings if r.key == "model"), 0.0), 3)
                for h in with_model.available
            },
        },
    }


def main() -> None:
    pit.OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = pit.OUT_DIR / "model.jsonl"
    done = set()
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done.add((row["cutoff"], row["symbol"]))

    grid = [(c, s) for c in schedule.cutoffs() for s in schedule.MODEL_SYMBOLS]
    todo = [(c, s) for c, s in grid if (str(c["date"].date()), s) not in done]
    print(f"Stage 1b — {len(todo)} forecasts to run "
          f"({len(done)} already frozen), ~35 s each", flush=True)

    started = time.time()
    with target.open("a", encoding="utf-8") as handle:
        for index, (entry, symbol) in enumerate(todo, start=1):
            cutoff = entry["date"]
            row = {
                "cutoff": str(cutoff.date()),
                "cutoff_label": entry["label"],
                "cutoff_kind": entry["kind"],
                "symbol": symbol,
                "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            }
            try:
                row["forecast"] = experiment(symbol, cutoff)
            except Exception as error:  # noqa: BLE001
                row["forecast"] = {"available": False, "reason": str(error)}
            handle.write(json.dumps(row) + "\n")
            handle.flush()

            got = row["forecast"]
            note = (f"{got['predicted_move_pct']:+.2f}% over {got['horizon_bars']} bars, "
                    f"walk-forward directional "
                    f"{got['walk_forward']['mean_directional_pct']:.1f}%"
                    if got.get("available") else got.get("reason", "failed"))
            print(f"  [{index}/{len(todo)}] {row['cutoff']} {symbol:8s} {note} "
                  f"({time.time() - started:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
