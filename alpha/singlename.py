"""Layer 3 — the single-name walk-forward harness. PREDICTION SIDE.

`alpha/SINGLE_NAME_PREREGISTRATION.md` is the protocol; this module implements
it and imports every constant from `singlename_config.py` rather than restating
one. It writes `alpha/out/single_name_predictions.pkl` and **never reads a
forward return that had not already happened at the cutoff it is predicting**.

Three structural guarantees, each backed by a test rather than by a comment:

* **`PastOutcomes` is the only route to a label.** It hands back rows for
  cutoffs `T'` satisfying `pos(T') + HORIZON + EMBARGO <= pos(T)` and re-checks
  the result against each row's own `horizon_end` before returning it. A caller
  that asks for more gets a `LookAheadError`, not a warning.
* **The written file carries no outcome.** Features, market state, probabilities,
  expected returns, intervals and decisions — and nothing that could only be
  known after the cutoff. `singlename_score.py` performs the join.
* **It refuses to overwrite.** A prediction file that can be rebuilt after a
  result is not a frozen prediction (CLAUDE.md §6.5).

The dependent variable is `asset_return` — the raw 5-session forward return of
one name — not `alpha_5d`. That distinction is the whole point of the phase: the
cross-sectional programme measured relative rank, and a user asking "will NVDA
be up next week" is asking something the cross-sectional programme never
answered.

Run:  python -m alpha.singlename            # writes predictions, refuses to overwrite
      python -m alpha.singlename --describe # sizes only, writes nothing
"""

from __future__ import annotations

import dataclasses
import sys
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge

from . import build_panel, dataset, examset, market_state, protocol, targets
from . import singlename_config as cfg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FEATURE_COLUMNS = ("b3_rank", "mom_rank")
LABEL_COLUMNS = ("asset_return", "direction", "horizon_end")


class LookAheadError(RuntimeError):
    """Raised when something asks for a label that had not happened yet."""


# ----------------------------------------------------------------------
# The dataset: features and labels kept in separate frames on purpose
# ----------------------------------------------------------------------

@dataclasses.dataclass
class SingleNameData:
    """Development-only (cutoff x symbol) features, labels and market state.

    `features` and `labels` are separate frames rather than two column groups of
    one frame so that a function which is handed the features cannot reach the
    outcomes by typo. `labels` is scorer-side and is only ever accessed through
    `PastOutcomes` on the prediction path.
    """

    features: pd.DataFrame              # MultiIndex (cutoff, symbol)
    labels: pd.DataFrame                # MultiIndex (cutoff, symbol) — SCORER SIDE
    states: dict[pd.Timestamp, market_state.MarketState]
    calendar: pd.DatetimeIndex

    @property
    def cutoffs(self) -> list[pd.Timestamp]:
        return sorted(self.features.index.get_level_values(0).unique())

    def block(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        return self.features.xs(pd.Timestamp(cutoff), level=0)


def b3_rank(frame: pd.DataFrame, regimes: pd.DataFrame) -> pd.Series:
    """B3, rank-transformed within the cutoff — §1.3, unchanged from V3/V4.

    `protocol.benchmark_scores` is imported, not reimplemented, so "B3" here is
    the same object the cross-sectional programme benchmarked against. The
    second rank matches `alpha/v3_family1.py:149`.
    """
    scores = protocol.benchmark_scores(frame, regimes)
    if "b3_regime_switched" not in scores.columns:
        raise RuntimeError("the panel cannot produce b3_regime_switched — B3 needs "
                           "ret_12_1 and ret_5d and a trend tag")
    return scores["b3_regime_switched"].groupby(level=0).rank(pct=True, na_option="keep")


def build(frame: pd.DataFrame, regimes: pd.DataFrame,
          calendar: pd.DatetimeIndex) -> SingleNameData:
    """Split a development panel into the three objects the harness needs."""
    features = pd.DataFrame(index=frame.index)
    features["b3_rank"] = b3_rank(frame, regimes)
    features["mom_rank"] = frame.groupby(level=0)[cfg.FEATURE_S2].rank(
        pct=True, na_option="keep")

    returns = pd.to_numeric(frame[cfg.TARGET_RETURN], errors="coerce")
    labels = pd.DataFrame(index=frame.index)
    labels["asset_return"] = returns
    # §1.2: a return of exactly zero is *not* up. Fixed before any label was read.
    labels["direction"] = (returns > 0).astype(float).where(returns.notna())
    labels["horizon_end"] = pd.to_datetime(frame["horizon_end"])

    labels = labels[labels["asset_return"].notna()]
    features = features.loc[labels.index]

    states = market_state.series(frame.loc[labels.index], regimes)
    return SingleNameData(features, labels, states, pd.DatetimeIndex(calendar))


def load(verbose: bool = True) -> SingleNameData:
    """The development panel, with the 72 sealed exam cutoffs removed.

    `examset.development_only` is the single call that performs the removal, and
    it raises if any exam cutoff survives the slice. Nothing else in this module
    knows an exam date exists.
    """
    from . import pitdata

    panel, _, _ = build_panel.load()
    development = examset.development_only(panel)
    book = pitdata.load_book()
    if verbose:
        print(f"development {len(development.cutoffs)} cutoffs, "
              f"{len(development.frame):,} rows "
              f"(72 sealed exam cutoffs removed by examset.development_only)")
    return build(development.frame, development.regimes, book.calendar)


# ----------------------------------------------------------------------
# The label door
# ----------------------------------------------------------------------

class PastOutcomes:
    """Labels whose outcome window closed EMBARGO sessions before the cutoff asked for.

    The admissibility rule is `alpha/dataset.py::training_cutoffs`, imported
    rather than restated. The second check — that every returned row's own
    `horizon_end` sits at least `EMBARGO` sessions before the cutoff — is
    redundant on purpose: it is computed from the rows rather than from the
    schedule, so a schedule bug and a row bug would have to agree to get past
    both.
    """

    def __init__(self, data: SingleNameData, horizon: int = cfg.HORIZON,
                 embargo: int = cfg.EMBARGO):
        self._labels = data.labels
        self._cutoffs = data.cutoffs
        self._calendar = data.calendar
        self.horizon = horizon
        self.embargo = embargo

    def admissible_cutoffs(self, cutoff: pd.Timestamp) -> list[pd.Timestamp]:
        """Cutoffs whose outcomes were genuinely known `embargo` sessions before `cutoff`."""
        class _Calendar:                      # dataset.training_cutoffs wants a book
            calendar = self._calendar
        return dataset.training_cutoffs(self._cutoffs, pd.Timestamp(cutoff), _Calendar(),
                                        horizon=self.horizon, embargo=self.embargo)

    def before(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        """Every admissible label at `cutoff`. Raises rather than trims on a violation."""
        cutoff = pd.Timestamp(cutoff)
        keep = self.admissible_cutoffs(cutoff)
        if not keep:
            return self._labels.iloc[:0]

        rows = self._labels[self._labels.index.get_level_values(0).isin(set(keep))]
        self._assert_closed(rows, cutoff)
        return rows

    def _assert_closed(self, rows: pd.DataFrame, cutoff: pd.Timestamp) -> None:
        if rows.empty:
            return
        limit = self._calendar.searchsorted(cutoff) - self.embargo
        if limit < 0:
            raise LookAheadError(f"no admissible history at {cutoff.date()}")
        boundary = self._calendar[limit]
        latest = pd.Timestamp(rows["horizon_end"].max())
        if latest > boundary:
            raise LookAheadError(
                f"outcome window ending {latest.date()} is not {self.embargo} sessions "
                f"clear of {cutoff.date()} (boundary {boundary.date()}) — a training row "
                "would have been labelled with something that had not happened yet")


# ----------------------------------------------------------------------
# The five incumbents (§3)
# ----------------------------------------------------------------------

@dataclasses.dataclass
class Prediction:
    """One arm's output for one cutoff's cross-section."""

    prob_up: pd.Series
    expected_return: pd.Series
    usable: pd.Series                   # False where the feature was absent (§3.6)


def _clip(p) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), cfg.PROB_CLIP, 1.0 - cfg.PROB_CLIP)


def _winsorised_returns(rows: pd.DataFrame) -> pd.Series:
    """Per-cutoff 1% winsorisation of the magnitude target (§3.6)."""
    return rows.groupby(level=0)["asset_return"].transform(
        lambda block: targets.winsorise(block, tail=cfg.WINSOR_TAIL))


@dataclasses.dataclass
class LinearArm:
    """A logistic for direction and a ridge for magnitude, on one centred feature."""

    intercept_p: float
    slope_p: float
    intercept_r: float
    slope_r: float

    def apply(self, x: pd.Series) -> Prediction:
        usable = x.notna()
        centred = (x - 0.5).astype(float)
        logit = self.intercept_p + self.slope_p * centred
        prob = pd.Series(1.0 / (1.0 + np.exp(-logit)), index=x.index)
        expected = pd.Series(self.intercept_r + self.slope_r * centred, index=x.index)
        return Prediction(prob.where(usable), expected.where(usable), usable)


def fit_linear(x: pd.Series, direction: pd.Series, ret: pd.Series) -> LinearArm | None:
    """Fit the pair. Returns None when the slice cannot support a fit."""
    frame = pd.DataFrame({"x": x, "d": direction, "r": ret}).replace(
        [np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 500 or frame["d"].nunique() < 2 or frame["x"].nunique() < 3:
        return None

    design = (frame[["x"]].to_numpy(dtype=float) - 0.5)
    logistic = LogisticRegression(**cfg.LOGISTIC_PARAMS)
    logistic.fit(design, frame["d"].to_numpy(dtype=int))
    ridge = Ridge(**cfg.RIDGE_PARAMS)
    ridge.fit(design, frame["r"].to_numpy(dtype=float))

    return LinearArm(float(logistic.intercept_[0]), float(logistic.coef_[0][0]),
                     float(ridge.intercept_), float(ridge.coef_[0]))


@dataclasses.dataclass
class ConstantArm:
    """S0 and S1: one probability and one expected return for every name."""

    prob: float
    expected: float

    def apply(self, index: pd.Index) -> Prediction:
        return Prediction(pd.Series(self.prob, index=index),
                          pd.Series(self.expected, index=index),
                          pd.Series(True, index=index))


@dataclasses.dataclass
class BucketedArm:
    """S4: one `LinearArm` per (trend, vol) bucket, with a pooled fallback (§3.5)."""

    pooled: LinearArm | None
    buckets: dict[tuple[str, str], LinearArm]

    def apply(self, x: pd.Series, bucket: tuple[str, str]) -> Prediction:
        arm = self.buckets.get(bucket) or self.pooled
        if arm is None:
            empty = pd.Series(np.nan, index=x.index)
            return Prediction(empty, empty, pd.Series(False, index=x.index))
        return arm.apply(x)

    def used_bucket(self, bucket: tuple[str, str]) -> bool:
        return bucket in self.buckets


def fit_arms(train: pd.DataFrame, states: dict[pd.Timestamp, market_state.MarketState]
             ) -> dict[str, object]:
    """Fit S0-S4 on one admissible training slice. Reads only past labels."""
    ret = _winsorised_returns(train)
    raw_prior = float(train["direction"].mean())

    arms: dict[str, object] = {
        "S0": ConstantArm(1.0, 0.0),
        "S1": ConstantArm(raw_prior, float(ret.mean())),
        "S2": fit_linear(train["mom_rank"], train["direction"], ret),
        "S3": fit_linear(train["b3_rank"], train["direction"], ret),
    }

    pooled = arms["S3"] if isinstance(arms["S3"], LinearArm) else None
    buckets: dict[tuple[str, str], LinearArm] = {}
    cutoffs = train.index.get_level_values(0)
    bucket_of = pd.Series([states[pd.Timestamp(c)].bucket if pd.Timestamp(c) in states
                           else None for c in cutoffs], index=train.index)
    for bucket, rows in train.groupby(bucket_of, dropna=True):
        if rows.index.get_level_values(0).nunique() < cfg.MIN_BUCKET_CUTOFFS:
            continue
        fitted = fit_linear(rows["b3_rank"], rows["direction"], _winsorised_returns(rows))
        if fitted is not None:
            buckets[tuple(bucket)] = fitted
    arms["S4"] = BucketedArm(pooled, buckets)
    return arms


def apply_arm(key: str, arm, block: pd.DataFrame, state: market_state.MarketState,
              fallback: ConstantArm) -> Prediction:
    """One arm's prediction for one cutoff, with the §3.6 missing-feature rule."""
    if arm is None:
        return fallback.apply(block.index)

    if key in ("S0", "S1"):
        predicted = arm.apply(block.index)
    elif key == "S2":
        predicted = arm.apply(block["mom_rank"])
    elif key == "S3":
        predicted = arm.apply(block["b3_rank"])
    elif key == "S4":
        predicted = arm.apply(block["b3_rank"], state.bucket)
    else:                                                   # pragma: no cover
        raise KeyError(key)

    # A row with no feature is not imputed; it falls back to the unconditional
    # prior and is emitted as NO_EDGE by `decide`.
    base = fallback.apply(block.index)
    return Prediction(predicted.prob_up.fillna(base.prob_up),
                      predicted.expected_return.fillna(base.expected_return),
                      predicted.usable.fillna(False).astype(bool))


# ----------------------------------------------------------------------
# §3.7 conformal interval and §4 decision
# ----------------------------------------------------------------------

def conformal_offsets(residuals: pd.Series) -> tuple[float, float]:
    """The §3.7 asymmetric residual quantiles. NaN when the block is too thin."""
    clean = pd.to_numeric(residuals, errors="coerce").dropna()
    if len(clean) < 100:
        return (float("nan"), float("nan"))
    return (float(clean.quantile(cfg.INTERVAL_LOW_Q)),
            float(clean.quantile(cfg.INTERVAL_HIGH_Q)))


def decide(prob_up: float, expected: float, usable: bool) -> tuple[str, str]:
    """§4, HOLD by default. Returns `(call, reason)`.

    Fails closed at every branch, exactly as `alpha/adapter.py::decide` does: a
    quantity that cannot be evaluated is a reason not to act, never a shrug.
    """
    if not usable or not np.isfinite(prob_up) or not np.isfinite(expected):
        return "NO_EDGE", "no usable feature for this symbol at this cutoff"
    if prob_up >= cfg.BUY_PROB and expected >= cfg.MIN_EDGE:
        return "BUY", (f"p_up {prob_up:.3f} >= {cfg.BUY_PROB} and expected "
                       f"{expected:+.4f} >= {cfg.MIN_EDGE:+.4f}")
    if prob_up <= cfg.SELL_PROB and expected <= -cfg.MIN_EDGE:
        return "SELL", (f"p_up {prob_up:.3f} <= {cfg.SELL_PROB} and expected "
                        f"{expected:+.4f} <= {-cfg.MIN_EDGE:+.4f}")
    if prob_up < cfg.BUY_PROB and prob_up > cfg.SELL_PROB:
        return "HOLD", f"p_up {prob_up:.3f} is inside the [{cfg.SELL_PROB}, {cfg.BUY_PROB}] band"
    return "HOLD", (f"direction threshold met (p_up {prob_up:.3f}) but expected return "
                    f"{expected:+.4f} does not clear {cfg.MIN_EDGE:+.4f}")


def confidence_tier(prob_up: float) -> str:
    """§5.1's frozen tiers, on distance from a coin flip."""
    if not np.isfinite(prob_up):
        return "none"
    edge = abs(prob_up - 0.5)
    for name, low, high in cfg.CONFIDENCE_TIERS:
        if low <= edge < high:
            return name
    return cfg.CONFIDENCE_TIERS[-1][0]


# ----------------------------------------------------------------------
# The walk-forward run
# ----------------------------------------------------------------------

def evaluation_cutoffs(data: SingleNameData,
                       min_train: int = cfg.MIN_TRAIN_CUTOFFS) -> list[pd.Timestamp]:
    """Development cutoffs with at least `min_train` admissible predecessors (§1.5)."""
    door = PastOutcomes(data)
    return [c for c in data.cutoffs if len(door.admissible_cutoffs(c)) >= min_train]


def run(data: SingleNameData, verbose: bool = True) -> pd.DataFrame:
    """Walk forward once, returning the frozen prediction frame. Reads no future label."""
    door = PastOutcomes(data)
    cutoffs = evaluation_cutoffs(data)
    if not cutoffs:
        raise RuntimeError("no cutoff has enough admissible history — check MIN_TRAIN_CUTOFFS")

    started = time.time()
    rows: list[pd.DataFrame] = []
    for index, cutoff in enumerate(cutoffs):
        admissible = door.admissible_cutoffs(cutoff)
        fit_cutoffs = admissible[:-cfg.CONFORMAL_CUTOFFS]
        calib_cutoffs = admissible[-cfg.CONFORMAL_CUTOFFS:]

        labels = door.before(cutoff)
        train = data.features.loc[labels.index].join(labels)
        fit_rows = train[train.index.get_level_values(0).isin(set(fit_cutoffs))]
        calib_rows = train[train.index.get_level_values(0).isin(set(calib_cutoffs))]
        if fit_rows.empty:
            continue

        arms = fit_arms(fit_rows, data.states)
        fallback = arms["S1"]
        block = data.block(cutoff)
        state = data.states[pd.Timestamp(cutoff)]

        frame = pd.DataFrame(index=block.index)
        frame["b3_rank"] = block["b3_rank"]
        frame["mom_rank"] = block["mom_rank"]

        for key in cfg.ARMS:
            predicted = apply_arm(key, arms[key], block, state, fallback)
            calibration = apply_arm(key, arms[key], calib_rows, state, fallback)
            low, high = conformal_offsets(
                calib_rows["asset_return"] - calibration.expected_return)

            frame[f"p_up_{key}"] = _clip(predicted.prob_up)
            frame[f"er_{key}"] = predicted.expected_return.to_numpy(dtype=float)
            frame[f"lo_{key}"] = predicted.expected_return + low
            frame[f"hi_{key}"] = predicted.expected_return + high
            frame[f"usable_{key}"] = predicted.usable.to_numpy(dtype=bool)

            calls = [decide(p, e, u) for p, e, u in
                     zip(frame[f"p_up_{key}"], frame[f"er_{key}"], frame[f"usable_{key}"])]
            frame[f"call_{key}"] = [c for c, _ in calls]
            frame[f"tier_{key}"] = [confidence_tier(p) for p in frame[f"p_up_{key}"]]

        frame["cutoff"] = pd.Timestamp(cutoff)
        frame["symbol"] = frame.index
        frame["trend"] = state.trend
        frame["vol"] = state.vol
        frame["risk_score"] = state.risk_score
        frame["n_train_cutoffs"] = len(fit_cutoffs)
        frame["n_train_rows"] = len(fit_rows)
        frame["s4_bucket_fitted"] = arms["S4"].used_bucket(state.bucket)
        rows.append(frame.reset_index(drop=True))

        if verbose and (index + 1) % 25 == 0:
            print(f"  {index + 1:4d}/{len(cutoffs)} cutoffs  "
                  f"({time.time() - started:.0f}s)", flush=True)

    out = pd.concat(rows, ignore_index=True).set_index(["cutoff", "symbol"]).sort_index()
    # The cross-sectional percentile is a *relative* quantity and lives in its own
    # branch of the schema (§6); it never enters the absolute decision.
    for key in cfg.ARMS:
        out[f"pctile_{key}"] = out.groupby(level=0)[f"er_{key}"].rank(pct=True,
                                                                     na_option="keep")
    return out


def view(row: pd.Series, symbol: str, cutoff: pd.Timestamp, arm: str = "S4") -> dict:
    """One prediction in the §6 output schema. Relative and absolute stay separate."""
    return {
        "symbol": symbol,
        "cutoff": str(pd.Timestamp(cutoff).date()),
        "horizon": cfg.HORIZON_LABEL,
        "market_state": {
            "regime": f"{row['trend']}/{row['vol']}",
            "trend": row["trend"], "vol": row["vol"],
            "risk_score": _finite(row.get("risk_score")),
        },
        "relative": {
            "score": _finite(row.get("b3_rank")),
            "percentile": _finite(row.get(f"pctile_{arm}")),
        },
        "absolute": {
            "prob_up": _finite(row.get(f"p_up_{arm}")),
            "expected_return": _finite(row.get(f"er_{arm}")),
            "prediction_interval": [_finite(row.get(f"lo_{arm}")),
                                    _finite(row.get(f"hi_{arm}"))],
        },
        "decision": {
            "call": row.get(f"call_{arm}"),
            "confidence": row.get(f"tier_{arm}"),
            "reason": decide(row.get(f"p_up_{arm}", np.nan), row.get(f"er_{arm}", np.nan),
                             bool(row.get(f"usable_{arm}", False)))[1],
        },
        "model": {
            "version": cfg.MODEL_VERSION,
            "calibration_version": f"walkforward-{cfg.MIN_TRAIN_CUTOFFS}-"
                                   f"{cfg.CONFORMAL_CUTOFFS}",
            "arm": arm,
        },
    }


def _finite(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(value) else round(value, 6)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    data = load()

    if "--describe" in argv:
        cutoffs = evaluation_cutoffs(data)
        print(f"cutoffs     {len(data.cutoffs)} development, "
              f"{len(cutoffs)} with >= {cfg.MIN_TRAIN_CUTOFFS} admissible predecessors")
        print(f"evaluation  {cutoffs[0].date()} .. {cutoffs[-1].date()}")
        print(f"rows        {len(data.features):,}  ·  "
              f"{data.features.index.get_level_values(1).nunique()} symbols")
        return

    cfg.OUT_DIR.mkdir(parents=True, exist_ok=True)
    if cfg.PREDICTIONS_PATH.exists():
        raise SystemExit(
            f"{cfg.PREDICTIONS_PATH} already exists — single-name predictions are frozen.\n"
            "Overwriting them means the file is no longer evidence that the predictions "
            "were made before the outcomes were read. Deleting it is a deliberate act "
            "that belongs in the report, not in a re-run.")

    frame = run(data)
    pd.to_pickle({
        "predictions": frame,
        "states": market_state.table(data.states),
        "protocol": cfg.PREREGISTRATION,
        "model_version": cfg.MODEL_VERSION,
        "horizon": cfg.HORIZON,
        "frozen_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }, cfg.PREDICTIONS_PATH)
    print(f"froze       {len(frame):,} predictions x {len(cfg.ARMS)} arms -> "
          f"{cfg.PREDICTIONS_PATH}")
    print("no outcome was read on this path beyond the embargoed training window")


if __name__ == "__main__":
    main()
