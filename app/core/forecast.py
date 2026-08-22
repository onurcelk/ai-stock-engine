"""Recurrent price forecaster, ported from the deep-learning notebooks.

This is the model from deep-learning/1.lstm.ipynb (and its GRU / vanilla
siblings) with the cell type lifted into a parameter, wrapped so it can be
driven from a UI: no globals, no printing, and a progress callback.

TensorFlow is imported lazily because it costs several seconds — the rest
of the app should start instantly.
"""

from __future__ import annotations

import dataclasses
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

# LSTM carries both a cell and a hidden state, so its flattened state
# vector is twice as wide as GRU's or a vanilla RNN's.
MODELS: dict[str, int] = {"LSTM": 2, "GRU": 1, "Vanilla RNN": 1}

ProgressFn = Callable[[int, int, int, float, float], None]

#: Default random seed. HT-1 §6 measured `neural.lstm` flipping the sign of its
#: projection on 7.2% of identical re-runs, with a maximum drift of 1,899
#: percentage points, while GRU and Vanilla RNN were bit-identical through the
#: same code path. A default seed makes a re-run reproducible by default;
#: passing `seed=None` restores the old unseeded behaviour deliberately rather
#: than by omission.
DEFAULT_SEED = 1337

#: How far outside its own training range a rollout may wander before it is
#: called divergence rather than forecast. The series is min-max scaled to
#: [0, 1] before training, so a scaled prediction beyond ±this is not a
#: prediction about price — it is the autoregressive loop feeding on itself.
DIVERGENCE_LIMIT = 10.0


class DivergedRollout(RuntimeError):
    """The autoregressive rollout left the range its training data occupied.

    Raised rather than returned so a diverged path can never be rendered as a
    number. HT-1 §6 recorded a single re-run moving a projection by 1,899
    percentage points; that is this failure, and it was previously shown to the
    user as an ordinary forecast.
    """


@dataclasses.dataclass
class ForecastResult:
    dates: pd.Series
    actual: np.ndarray
    runs: list[np.ndarray]
    accuracies: list[float]
    naive_accuracy: float
    naive: np.ndarray
    anchor: float = 0.0

    @property
    def mean_accuracy(self) -> float:
        return float(np.mean(self.accuracies))

    @property
    def mean_forecast(self) -> np.ndarray:
        return np.mean(self.runs, axis=0)

    @property
    def beats_naive(self) -> bool:
        return self.mean_accuracy > self.naive_accuracy

    @property
    def directional_accuracy(self) -> float:
        """How often the forecast got the direction of the next move right.

        This is the metric that can actually fail. `accuracy()` is dominated
        by price level, so it reads 90%+ for anything that stays near the
        last known price; getting the *sign* right is the thing a trader
        would need, and coin-flipping scores 50%.
        """
        return directional_accuracy(self.actual, self.mean_forecast, self.anchor)

    @property
    def mae(self) -> float:
        return float(np.mean(np.abs(self.actual - self.mean_forecast)))

    @property
    def rmse(self) -> float:
        return float(np.sqrt(np.mean((self.actual - self.mean_forecast) ** 2)))

    @property
    def naive_mae(self) -> float:
        return float(np.mean(np.abs(self.actual - self.naive)))


def accuracy(real: np.ndarray, predicted: np.ndarray) -> float:
    """The repo's own metric: 100% minus RMS relative error.

    Kept identical to the notebooks so numbers stay comparable — but see
    `naive_accuracy`, which is why it should be read sceptically.
    """
    real = np.asarray(real, dtype=float) + 1
    predicted = np.asarray(predicted, dtype=float) + 1
    return float((1 - np.sqrt(np.mean(np.square((real - predicted) / real)))) * 100)


def directional_accuracy(real: np.ndarray, predicted: np.ndarray, anchor: float) -> float:
    """Percentage of steps where the predicted move had the right sign.

    `anchor` is the last observed price before the forecast window, so the
    very first predicted step is scored too rather than silently dropped.
    """
    real = np.concatenate([[anchor], np.asarray(real, dtype=float)])
    predicted = np.concatenate([[anchor], np.asarray(predicted, dtype=float)])
    real_moves = np.sign(np.diff(real))
    predicted_moves = np.sign(np.diff(predicted))
    if real_moves.size == 0:
        return 0.0
    return float(np.mean(real_moves == predicted_moves) * 100)


def _anchor(signal: np.ndarray, weight: float) -> np.ndarray:
    """Exponential smoothing, as applied to the raw forecast in the notebooks."""
    smoothed = []
    last = signal[0]
    for value in signal:
        last = last * weight + (1 - weight) * value
        smoothed.append(last)
    return np.asarray(smoothed)


def _build_graph(tf, model: str, learning_rate, num_layers, size, size_layer, output_size):
    """The notebook's Model class, with the cell type parameterised."""
    cell_factory = {
        "LSTM": lambda n: tf.nn.rnn_cell.LSTMCell(n, state_is_tuple=False),
        "GRU": lambda n: tf.nn.rnn_cell.GRUCell(n),
        "Vanilla RNN": lambda n: tf.nn.rnn_cell.BasicRNNCell(n),
    }[model]

    rnn_cells = tf.nn.rnn_cell.MultiRNNCell(
        [cell_factory(size_layer) for _ in range(num_layers)], state_is_tuple=False
    )
    state_width = num_layers * MODELS[model] * size_layer

    graph = {}
    graph["X"] = tf.placeholder(tf.float32, (None, None, size))
    graph["Y"] = tf.placeholder(tf.float32, (None, output_size))
    graph["hidden_layer"] = tf.placeholder(tf.float32, (None, state_width))

    # Dropout is a *training* device. It was previously baked into the graph as
    # a constant, so it stayed on during `_predict` and randomly dropped a fifth
    # of the outputs of every inference call -- which is how a projection came
    # to change on a re-run of the identical model (HT-1 §6).
    #
    # `placeholder_with_default(1.0)` makes the distinction explicit and fails
    # safe: a caller that forgets to feed it gets inference behaviour (no
    # dropout), never silent dropout. Training feeds the keep probability.
    graph["keep_prob"] = tf.placeholder_with_default(
        tf.constant(1.0, tf.float32), shape=())

    drop = tf.nn.rnn_cell.DropoutWrapper(
        rnn_cells, output_keep_prob=graph["keep_prob"])
    outputs, last_state = tf.nn.dynamic_rnn(
        drop, graph["X"], initial_state=graph["hidden_layer"], dtype=tf.float32
    )
    logits = tf.layers.dense(outputs[-1], output_size)
    cost = tf.reduce_mean(tf.square(graph["Y"] - logits))

    graph["logits"] = logits
    graph["last_state"] = last_state
    graph["cost"] = cost
    graph["optimizer"] = tf.train.AdamOptimizer(learning_rate).minimize(cost)
    graph["state_width"] = state_width
    return graph


@dataclasses.dataclass
class Fold:
    """One rolling-origin split: train up to `train_end`, predict what follows."""

    index: int
    train_end: int
    dates: pd.Series
    actual: np.ndarray
    predicted: np.ndarray
    naive: np.ndarray

    @property
    def accuracy(self) -> float:
        return accuracy(self.actual, self.predicted)

    @property
    def naive_accuracy(self) -> float:
        return accuracy(self.actual, self.naive)

    @property
    def directional(self) -> float:
        return directional_accuracy(self.actual, self.predicted, float(self.naive[0]))

    @property
    def mae(self) -> float:
        return float(np.mean(np.abs(self.actual - self.predicted)))

    @property
    def beats_naive(self) -> bool:
        return self.accuracy > self.naive_accuracy


@dataclasses.dataclass
class WalkForwardResult:
    """Aggregate of several rolling-origin folds.

    The distribution matters more than the mean: a model that is excellent on
    three folds and catastrophic on seven is not the same as a consistent one,
    and a single split cannot tell them apart.
    """

    folds: list[Fold]
    horizon: int
    model: str

    @property
    def accuracies(self) -> np.ndarray:
        return np.array([f.accuracy for f in self.folds])

    @property
    def directionals(self) -> np.ndarray:
        return np.array([f.directional for f in self.folds])

    @property
    def naive_accuracies(self) -> np.ndarray:
        return np.array([f.naive_accuracy for f in self.folds])

    @property
    def maes(self) -> np.ndarray:
        return np.array([f.mae for f in self.folds])

    @property
    def folds_beating_naive(self) -> int:
        return sum(1 for f in self.folds if f.beats_naive)

    @property
    def win_rate_pct(self) -> float:
        return self.folds_beating_naive / len(self.folds) * 100 if self.folds else 0.0

    def summary(self) -> dict[str, float]:
        return {
            "mean_accuracy": float(self.accuracies.mean()),
            "std_accuracy": float(self.accuracies.std()),
            "worst_accuracy": float(self.accuracies.min()),
            "best_accuracy": float(self.accuracies.max()),
            "mean_naive": float(self.naive_accuracies.mean()),
            "mean_directional": float(self.directionals.mean()),
            "std_directional": float(self.directionals.std()),
            "mean_mae": float(self.maes.mean()),
            "win_rate_pct": self.win_rate_pct,
        }

    def table(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Fold": f.index + 1,
                    "Train bars": f.train_end,
                    "From": f.dates.iloc[0].date(),
                    "To": f.dates.iloc[-1].date(),
                    "Accuracy %": round(f.accuracy, 2),
                    "Naive %": round(f.naive_accuracy, 2),
                    "Beat naive": "yes" if f.beats_naive else "no",
                    "Directional %": round(f.directional, 1),
                    "MAE": round(f.mae, 2),
                }
                for f in self.folds
            ]
        )


def max_folds(n_rows: int, horizon: int, min_train: int = 120) -> int:
    """How many folds this series can support at that horizon."""
    if horizon <= 0:
        return 0
    return max(0, (n_rows - min_train) // horizon)


# Seconds per unit of (folds + 1) x epochs x bars, measured on this repo's CPU
# stack: 1,250 daily bars over 3 folds at 30 epochs plus a projection took 35s,
# and 2,514 bars the same way took 74s. Training cost is linear in all three
# because every epoch walks the whole training slice once.
SECONDS_PER_UNIT = 1 / 4_250


def estimate_train_seconds(folds: int, epochs: int, bars: int) -> float:
    """Roughly how long a walk-forward plus a projection will take.

    Only ever used to set expectations before a wait, so being out by a third
    is fine. Being out by a factor of a thousand is not — the first version of
    this lived in the UI with the wrong constant and told the user a
    fifty-second job would take "roughly 0s".
    """
    return max(0.0, (folds + 1) * epochs * bars * SECONDS_PER_UNIT)


def walk_forward(
    close: pd.Series,
    dates: pd.Series,
    *,
    folds: int = 5,
    horizon: int = 30,
    model: str = "LSTM",
    num_layers: int = 1,
    size_layer: int = 128,
    timestamp: int = 5,
    epochs: int = 100,
    dropout: float = 0.8,
    learning_rate: float = 0.01,
    min_train: int = 120,
    seed: int | None = DEFAULT_SEED,
    progress: ProgressFn | None = None,
) -> WalkForwardResult:
    """Rolling-origin evaluation: repeat the train/predict split down the series.

    Fold *i* trains on everything up to some cut point and predicts the next
    `horizon` bars; each successive fold moves the cut forward by `horizon`,
    so no fold ever sees its own test window. Unlike `run()`, the scaler is
    fitted on the training slice alone — no look-ahead.

    One split on one arbitrary window is not evidence. This is.
    """
    total = len(close)
    available = max_folds(total, horizon, min_train)
    if available < 1:
        raise ValueError(
            f"Need at least {min_train + horizon} bars for one fold; got {total}. "
            "Use a longer history or a shorter horizon."
        )
    folds = min(folds, available)

    tf = _load_tf()
    prices = close.to_numpy(dtype=float)
    results: list[Fold] = []

    for i in range(folds):
        # Oldest fold first; the last one ends at the final bar.
        test_end = total - (folds - 1 - i) * horizon
        test_start = test_end - horizon

        train_prices = prices[:test_start].astype("float32").reshape(-1, 1)
        # Fitted on training data only — the whole point of walk-forward.
        minmax = MinMaxScaler().fit(train_prices)
        train_scaled = pd.DataFrame(minmax.transform(train_prices))

        predicted = _train_once(
            tf, train_scaled, minmax, model=model, num_layers=num_layers,
            size_layer=size_layer, timestamp=timestamp, epochs=epochs,
            dropout=dropout, learning_rate=learning_rate, horizon=horizon,
            seed=seed, progress=progress, slot=i,
        )

        anchor_price = float(prices[test_start - 1])
        results.append(Fold(
            index=i,
            train_end=test_start,
            dates=dates.iloc[test_start:test_end].reset_index(drop=True),
            actual=prices[test_start:test_end],
            predicted=predicted,
            naive=np.full(horizon, anchor_price),
        ))

    return WalkForwardResult(folds=results, horizon=horizon, model=model)


def _load_tf():
    """Import TensorFlow in v1 graph mode. Lazy — it costs several seconds."""
    import logging
    import os

    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    logging.getLogger("tensorflow").setLevel(logging.ERROR)

    import tensorflow.compat.v1 as tf

    tf.disable_v2_behavior()
    return tf


def _train_once(
    tf,
    train: pd.DataFrame,
    minmax: MinMaxScaler,
    *,
    model: str,
    num_layers: int,
    size_layer: int,
    timestamp: int,
    epochs: int,
    dropout: float,
    learning_rate: float,
    horizon: int,
    seed: int | None = DEFAULT_SEED,
    progress: ProgressFn | None = None,
    slot: int = 0,
) -> np.ndarray:
    """Build a fresh graph, train it on `train`, roll `horizon` steps forward.

    Shared by the single-split and walk-forward paths so both run exactly the
    same model.
    """
    tf.reset_default_graph()
    if seed is not None:
        # `reset_default_graph` plus a seed is not enough on its own, and
        # `tournament._seeded_tensorflow` says why after measuring it: Keras
        # state surviving between graphs shifts the op ordering that op-level
        # seeds are derived from, so four identical sequential LSTM
        # projections returned two alternating values. That makes a projection
        # depend on how many ran before it in the same process. Clearing the
        # session first is what removes it; the reset is repeated afterwards
        # because clearing installs a fresh graph of its own.
        try:
            tf.keras.backend.clear_session()
        except Exception:                                        # noqa: BLE001
            # Older/newer TF surfaces move this; a missing clear costs
            # determinism, not correctness, so it must not break a forecast.
            pass
        tf.reset_default_graph()
        tf.set_random_seed(seed)
    graph = _build_graph(
        tf, model, learning_rate, num_layers, train.shape[1], size_layer,
        train.shape[1],
    )
    session = tf.InteractiveSession()
    session.run(tf.global_variables_initializer())
    train_len = train.shape[0]

    try:
        for epoch in range(epochs):
            state = np.zeros((1, graph["state_width"]))
            losses, accs = [], []
            for k in range(0, train_len - 1, timestamp):
                index = min(k + timestamp, train_len - 1)
                batch_x = np.expand_dims(train.iloc[k:index, :].values, axis=0)
                batch_y = train.iloc[k + 1 : index + 1, :].values
                logits, state, _, loss = session.run(
                    [graph["logits"], graph["last_state"], graph["optimizer"], graph["cost"]],
                    feed_dict={graph["X"]: batch_x, graph["Y"]: batch_y,
                               graph["hidden_layer"]: state,
                               # The one place dropout belongs.
                               graph["keep_prob"]: dropout},
                )
                losses.append(loss)
                accs.append(accuracy(batch_y[:, 0], logits[:, 0]))
            if progress:
                progress(slot, epoch, epochs, float(np.mean(losses)), float(np.mean(accs)))

        return _predict(session, graph, train, minmax, timestamp, horizon)
    finally:
        session.close()


def run(
    close: pd.Series,
    dates: pd.Series,
    *,
    model: str = "LSTM",
    num_layers: int = 1,
    size_layer: int = 128,
    timestamp: int = 5,
    epochs: int = 300,
    dropout: float = 0.8,
    learning_rate: float = 0.01,
    test_size: int = 30,
    simulations: int = 1,
    seed: int | None = DEFAULT_SEED,
    progress: ProgressFn | None = None,
) -> ForecastResult:
    """Train on everything but the last `test_size` bars, then predict them.

    Note the scaler is fitted on the *whole* series, test window included.
    That is a mild look-ahead leak, kept because it is what the notebooks do
    and this function exists to reproduce them. `walk_forward()` fits on the
    training slice only.
    """
    tf = _load_tf()

    values = close.to_numpy(dtype="float32").reshape(-1, 1)
    minmax = MinMaxScaler().fit(values)
    scaled = pd.DataFrame(minmax.transform(values))

    train = scaled.iloc[:-test_size]

    runs: list[np.ndarray] = []
    accuracies: list[float] = []
    actual = close.to_numpy(dtype=float)[-test_size:]

    for sim in range(simulations):
        runs.append(_train_once(
            tf, train, minmax, model=model, num_layers=num_layers,
            size_layer=size_layer, timestamp=timestamp, epochs=epochs,
            dropout=dropout, learning_rate=learning_rate, horizon=test_size,
            seed=seed, progress=progress, slot=sim,
        ))
        accuracies.append(accuracy(actual, runs[-1]))

    # The honest yardstick: "tomorrow looks like today" repeated forward.
    anchor_price = float(close.to_numpy()[-test_size - 1])
    naive = np.full(test_size, anchor_price)

    return ForecastResult(
        dates=dates.iloc[-test_size:].reset_index(drop=True),
        actual=actual,
        runs=runs,
        accuracies=accuracies,
        naive_accuracy=accuracy(actual, naive),
        naive=naive,
        anchor=anchor_price,
    )


@dataclasses.dataclass
class Projection:
    """A forecast of bars that have not happened yet.

    Both `run()` and `walk_forward()` predict windows that already exist —
    that is what makes them scoreable, and it is also why neither of them is
    a forecast in the sense a trader means. This trains on the entire series
    and rolls forward past the last bar, so it produces a real prediction and
    no accuracy at all. Its credibility has to come from somewhere else:
    `walk_forward()` measures the same model on windows it did not see, and
    `ultimate.ModelEvidence` pairs the two.
    """

    model: str
    path: np.ndarray
    horizon: int
    last_price: float
    last_date: pd.Timestamp

    @property
    def final(self) -> float:
        return float(self.path[-1])

    @property
    def move_pct(self) -> float:
        if not self.last_price:
            return 0.0
        return (self.final - self.last_price) / self.last_price * 100

    @property
    def direction(self) -> int:
        return int(np.sign(self.move_pct))


def project(
    close: pd.Series,
    dates: pd.Series,
    *,
    model: str = "LSTM",
    num_layers: int = 1,
    size_layer: int = 128,
    timestamp: int = 5,
    epochs: int = 150,
    dropout: float = 0.8,
    learning_rate: float = 0.01,
    horizon: int = 5,
    seed: int | None = DEFAULT_SEED,
    progress: ProgressFn | None = None,
) -> Projection:
    """Train on every bar available, then predict `horizon` bars beyond the last.

    There is no held-out window here on purpose, so scaling on the full series
    carries no look-ahead: every bar the scaler sees is a bar the model is
    entitled to train on. That is the one context in this module where fitting
    on everything is the correct thing to do.
    """
    tf = _load_tf()

    values = close.to_numpy(dtype="float32").reshape(-1, 1)
    minmax = MinMaxScaler().fit(values)
    scaled = pd.DataFrame(minmax.transform(values))

    path = _train_once(
        tf, scaled, minmax, model=model, num_layers=num_layers,
        size_layer=size_layer, timestamp=timestamp, epochs=epochs,
        dropout=dropout, learning_rate=learning_rate, horizon=horizon,
        seed=seed, progress=progress, slot=0,
    )

    return Projection(
        model=model, path=np.asarray(path, dtype=float), horizon=horizon,
        last_price=float(close.iloc[-1]), last_date=dates.iloc[-1],
    )


def _predict(session, graph, train, minmax, timestamp, test_size) -> np.ndarray:
    """Replay the training window, then roll forward `test_size` bars."""
    train_len = train.shape[0]
    future_day = test_size

    output = np.zeros((train_len + future_day, train.shape[1]))
    output[0] = train.iloc[0]
    upper_b = (train_len // timestamp) * timestamp
    state = np.zeros((1, graph["state_width"]))

    for k in range(0, upper_b, timestamp):
        logits, state = session.run(
            [graph["logits"], graph["last_state"]],
            feed_dict={
                graph["X"]: np.expand_dims(train.iloc[k : k + timestamp], axis=0),
                graph["hidden_layer"]: state,
            },
        )
        output[k + 1 : k + timestamp + 1] = logits

    if upper_b != train_len:
        logits, state = session.run(
            [graph["logits"], graph["last_state"]],
            feed_dict={
                graph["X"]: np.expand_dims(train.iloc[upper_b:], axis=0),
                graph["hidden_layer"]: state,
            },
        )
        output[upper_b + 1 : train_len + 1] = logits
        future_day -= 1

    for i in range(future_day):
        window = output[-future_day - timestamp + i : -future_day + i]
        logits, state = session.run(
            [graph["logits"], graph["last_state"]],
            feed_dict={graph["X"]: np.expand_dims(window, axis=0),
                       graph["hidden_layer"]: state},
        )
        step = logits[-1]

        # The rollout feeds its own output back in, so a step that leaves the
        # scaled range compounds instead of correcting. Caught here, at the step
        # that did it, rather than after `inverse_transform` has turned it into
        # a plausible-looking price.
        if not np.all(np.isfinite(step)):
            raise DivergedRollout(
                f"Rollout produced a non-finite value at step {i + 1} of "
                f"{future_day}. The projection is not usable."
            )
        if np.max(np.abs(step)) > DIVERGENCE_LIMIT:
            raise DivergedRollout(
                f"Rollout reached {float(np.max(np.abs(step))):.1f} in scaled "
                f"space at step {i + 1} of {future_day}, outside the "
                f"±{DIVERGENCE_LIMIT:g} bound the training range implies. "
                "The projection is not usable."
            )

        output[-future_day + i] = step

    output = minmax.inverse_transform(output)
    return _anchor(output[:, 0], 0.3)[-test_size:]
