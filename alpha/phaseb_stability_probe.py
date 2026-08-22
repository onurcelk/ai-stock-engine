"""Phase B.3 — does the reproducibility fix actually reproduce?

HT-1 §6 measured `neural.lstm` flipping the sign of its projection on 7.2% of
identical re-runs (13 of 180, and 17 of 180 on a second probe of the same size
— the instability estimate was itself unstable), with a maximum drift of 1,899
percentage points, while `neural.gru` and `neural.vanilla_rnn` were
bit-identical through the same code path. HT-1 scoped the repair out and did
not license it; roadmap Phase B is the repair, and this is its verification.

**This is not a tournament and spends no budget slot.** It re-runs HT-1's
stability methodology at small scale against one question only: after seeding
the rollout and disabling dropout at inference, does an identical call return
an identical projection? It measures the *instrument*, not the market, and it
can promote nothing.

Two arms, so the fix cannot be credited with a stability the harness had all
along:

    fixed     seed=DEFAULT_SEED, dropout off at inference (the new default)
    unseeded  seed=None, which restores the pre-fix seeding behaviour

Run:

    ./venv/Scripts/python.exe -m alpha.phaseb_stability_probe
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from core import forecast  # noqa: E402

MODELS = ("LSTM", "GRU", "Vanilla RNN")

#: Small on purpose. HT-1 ran 180 calls to *estimate a rate*; this asks whether
#: the rate is now zero, and a single reproduced pair is already informative
#: about a defect that fired one time in fourteen.
TRIALS = 3
HORIZON = 5
EPOCHS = 12
BARS = 260


def series(seed: int = 11) -> tuple[pd.Series, pd.Series]:
    """A deterministic price series, so the probe measures the model and not
    the data it happened to be handed."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.013, BARS)))
    dates = pd.date_range("2023-01-02", periods=BARS, freq="B")
    return pd.Series(close), pd.Series(dates)


def project_once(close, dates, model: str, seed: int | None):
    return forecast.project(
        close, dates, model=model, horizon=HORIZON, epochs=EPOCHS,
        size_layer=32, seed=seed,
    )


def probe(model: str, seed: int | None) -> dict:
    """Run the same projection twice per trial and compare the pairs."""
    close, dates = series()
    flips = 0
    drifts: list[float] = []
    identical = 0
    diverged = 0

    for _ in range(TRIALS):
        try:
            first = project_once(close, dates, model, seed)
            second = project_once(close, dates, model, seed)
        except forecast.DivergedRollout:
            # Caught rather than silently returned is the other half of the
            # fix, so a guard firing is recorded, not treated as an error.
            diverged += 1
            continue

        drift = abs(first.move_pct - second.move_pct)
        drifts.append(drift)
        if np.sign(first.move_pct) != np.sign(second.move_pct):
            flips += 1
        if np.array_equal(first.path, second.path):
            identical += 1

    compared = len(drifts)
    return {
        "model": model,
        "arm": "fixed" if seed is not None else "unseeded",
        "compared": compared,
        "bit_identical": identical,
        "sign_flips": flips,
        "flip_rate_pct": (100 * flips / compared) if compared else float("nan"),
        "max_drift_pp": max(drifts) if drifts else float("nan"),
        "median_drift_pp": float(np.median(drifts)) if drifts else float("nan"),
        "diverged_caught": diverged,
    }


def main() -> int:
    rows = []
    for model in MODELS:
        for seed in (forecast.DEFAULT_SEED, None):
            row = probe(model, seed)
            rows.append(row)
            print(f"  {row['arm']:9s} {model:12s} "
                  f"identical {row['bit_identical']}/{row['compared']}  "
                  f"flips {row['sign_flips']}  "
                  f"max drift {row['max_drift_pp']:.4f} pp  "
                  f"diverged {row['diverged_caught']}", flush=True)

    frame = pd.DataFrame(rows)
    print()
    print(frame.to_string(index=False))

    fixed = frame[frame["arm"] == "fixed"]
    reproduced = int((fixed["bit_identical"] == fixed["compared"]).sum())
    print(f"\nfixed arm: {reproduced}/{len(fixed)} model(s) bit-identical on "
          f"every compared pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
