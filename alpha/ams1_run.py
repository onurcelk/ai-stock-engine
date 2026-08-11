"""AMS-1 prediction side: walk-forward, writes predictions, never reads an outcome.

Two-process separation, exactly as `validation/predict.py` and
`alpha/singlename.py` have it: this module writes `ams1_predictions.pkl` and
reads outcomes only through `singlename.PastOutcomes`, which hands back labels
whose forward windows closed `EMBARGO` sessions before the cutoff asked for and
raises `LookAheadError` rather than trimming when they have not.

At each evaluation cutoff *t*:

```
agent policies      trained at a refit boundary <= t          (ams1_signals.py)
agent inputs        the trailing price window at t            (ams1_signals.py)
meta-signals        a function of those stances only          (ams1_meta.py)
calibration         fitted on labels whose windows closed before t - EMBARGO
prediction          written, then never revisited
```

The arm roster is small, bounded and declared in the pre-registration before any
of it was run. There is no subset search, no learned agent weighting, and no
threshold chosen after a hit rate was seen.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pickle

import numpy as np
import pandas as pd

from . import ams1_config as cfg
from . import ams1_meta as meta
from . import singlename
from . import stats

BASELINE_ARMS = {"B0": "S1", "B1": "S2", "B2": "S3", "B3": "S4"}


def shrunk_rate(direction: pd.Series, prior: float, strength: float = 50.0) -> float:
    """Binomial shrinkage of a bucket's up-rate toward the walk-forward prior.

    Five buckets and one shrinkage constant is the whole capacity of the B5 arm.
    `strength` is a prior sample size, frozen at 50 — chosen as the order of a
    single cutoff's cross-section, not tuned against any result.
    """
    n = int(direction.notna().sum())
    if n == 0:
        return prior
    hits = float(direction.sum())
    return (hits + strength * prior) / (n + strength)


def run(verbose: bool = True) -> pd.DataFrame:
    """Walk forward over the development cutoffs, writing one row per prediction."""
    data = singlename.load(verbose=verbose)
    stances = pd.read_pickle(cfg.SIGNALS_PATH)

    # Restrict the panel to the cells the agent roster actually covers. This is
    # an availability intersection, not a filter on anything outcome-related.
    index = data.features.index.intersection(stances.index)
    stances = stances.loc[index]
    features = data.features.loc[index]
    # Every arm — baselines included — is fitted and scored on exactly the cells
    # the agent roster covers. Training the incumbents on the wider panel while
    # scoring them here would hand them evidence AMS-1's own arms never saw, and
    # the comparison is supposed to be like for like.
    data = dataclasses.replace(data, features=features,
                               labels=data.labels.loc[index])

    votes = meta.family_votes(stances)
    signals = meta.meta_signals(stances, votes)
    signals["state"] = meta.ladder_state(signals["M3_family_net_vote"])
    signals["raw_state"] = meta.raw_ladder_state(signals["M1_raw_net_vote"])

    past = singlename.PastOutcomes(data)
    cutoffs = sorted(index.get_level_values(0).unique())
    evaluation = [c for c in cutoffs
                  if len(past.admissible_cutoffs(c)) >= cfg.MIN_TRAIN_CUTOFFS]
    if verbose:
        print(f"cells {len(index):,}  cutoffs {len(cutoffs)}  "
              f"evaluation cutoffs {len(evaluation)}  "
              f"symbols {index.get_level_values(1).nunique()}")

    rows = []
    for count, cutoff in enumerate(evaluation, 1):
        train_labels = past.before(cutoff)
        train = train_labels.join(features, how="inner")
        train_meta = signals.reindex(train_labels.index)
        arms = singlename.fit_arms(train, data.states)
        prior = float(train["direction"].mean())

        block_index = index[index.get_level_values(0) == cutoff]
        block = features.loc[block_index]
        block_meta = signals.loc[block_index]
        state = data.states[cutoff]
        fallback = arms["S1"]          # ConstantArm — apply_arm's own §3.6 fallback

        row = pd.DataFrame(index=block_index)
        for name, arm_key in BASELINE_ARMS.items():
            prediction = singlename.apply_arm(arm_key, arms.get(arm_key), block,
                                              state, fallback)
            row[f"{name}_prob"] = prediction.prob_up.to_numpy()

        # B4 — naive raw agent vote, walk-forward logistic on the raw net vote.
        raw_arm = singlename.fit_linear(
            meta.to_unit(train_meta["M1_raw_net_vote"]),
            train["direction"], singlename._winsorised_returns(train))
        row["B4_prob"] = _apply(raw_arm, meta.to_unit(block_meta["M1_raw_net_vote"]),
                                prior, block_index)

        # B5 — equal-weight family consensus as five shrunk bucket rates.
        joined = train_meta.join(train["direction"])
        rates = {s: shrunk_rate(g["direction"], prior)
                 for s, g in joined.groupby("state", observed=True)}
        row["B5_prob"] = block_meta["state"].map(rates).astype(float).fillna(prior)

        # AMS-C — calibrated family consensus, walk-forward logistic on M3.
        family_arm = singlename.fit_linear(
            meta.to_unit(train_meta["M3_family_net_vote"]),
            train["direction"], singlename._winsorised_returns(train))
        row["AMS_prob"] = _apply(family_arm,
                                 meta.to_unit(block_meta["M3_family_net_vote"]),
                                 prior, block_index)

        # AMS-I — the incremental test: the incumbent's own probability plus the
        # family consensus, two features, one low-capacity logistic.
        row["AMSI_prob"] = _incremental(train, train_meta, block, block_meta,
                                        arms, data.states, state, fallback, prior)

        row["state"] = block_meta["state"].to_numpy()
        row["raw_state"] = block_meta["raw_state"].to_numpy()
        for column in ("M0_raw_buy_fraction", "M1_raw_net_vote",
                       "M2_family_buy_fraction", "M3_family_net_vote",
                       "M4_agreement", "M6_disagreement", "families_present",
                       "agents_available"):
            row[column] = block_meta[column].to_numpy()
        for family in cfg.FAMILIES:
            row[f"vote_{family}"] = votes.loc[block_index, family].to_numpy()

        rows.append(row)
        if verbose and count % 25 == 0:
            print(f"  {count}/{len(evaluation)} cutoffs", flush=True)

    predictions = pd.concat(rows)
    predictions.to_pickle(cfg.PREDICTIONS_PATH)
    if verbose:
        print(f"wrote {cfg.PREDICTIONS_PATH}  {predictions.shape}")
    return predictions


def _apply(arm, x: pd.Series, prior: float, index) -> np.ndarray:
    if arm is None:
        return np.full(len(index), prior, dtype=float)
    return arm.apply(x).prob_up.reindex(index).fillna(prior).to_numpy()


def _incremental(train, train_meta, block, block_meta, arms, states, state,
                 fallback, prior) -> np.ndarray:
    """Gate 5: does consensus add anything on top of the incumbent's own output?

    The incumbent enters as its **own fitted probability**, so the comparison is
    "incumbent alone" against "incumbent plus consensus" rather than against a
    re-parameterised incumbent. Two coefficients, fitted walk-forward.
    """
    from sklearn.linear_model import LogisticRegression

    incumbent = arms.get(cfg.PRIMARY_INCUMBENT)
    if incumbent is None:
        return np.full(len(block), prior, dtype=float)

    base = []
    for cutoff, group in train.groupby(level=0):
        got = singlename.apply_arm(cfg.PRIMARY_INCUMBENT, incumbent, group,
                                   states[cutoff], fallback)
        base.append(got.prob_up)
    base = pd.concat(base).reindex(train.index)

    frame = pd.DataFrame({
        "p": np.clip(base.to_numpy(dtype=float), cfg.PROB_CLIP, 1 - cfg.PROB_CLIP),
        "m": meta.to_unit(train_meta["M3_family_net_vote"]).to_numpy(),
        "d": train["direction"].to_numpy(),
    }).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 500 or frame["d"].nunique() < 2 or frame["m"].nunique() < 3:
        return np.full(len(block), prior, dtype=float)

    design = np.column_stack([np.log(frame["p"] / (1 - frame["p"])),
                              frame["m"] - 0.5])
    model = LogisticRegression(**cfg.LOGISTIC_PARAMS)
    model.fit(design, frame["d"].astype(int))

    live = singlename.apply_arm(cfg.PRIMARY_INCUMBENT, incumbent, block, state,
                                fallback).prob_up
    live = np.clip(live.to_numpy(dtype=float), cfg.PROB_CLIP, 1 - cfg.PROB_CLIP)
    consensus = meta.to_unit(block_meta["M3_family_net_vote"]).to_numpy()
    usable = np.isfinite(consensus)
    out = np.where(usable, np.nan, live)
    if usable.any():
        matrix = np.column_stack([np.log(live[usable] / (1 - live[usable])),
                                  consensus[usable] - 0.5])
        out[usable] = model.predict_proba(matrix)[:, 1]
    return out


def main() -> None:
    run()


if __name__ == "__main__":
    main()
