"""The forecaster's shape, without training one.

`forecast.run()` and `walk_forward()` are exercised end to end by the slow UI
tests, because they need TensorFlow and a minute. What can be checked in
milliseconds is the arithmetic around them: how many folds a series supports,
what a projection reports, and the cost estimate the UI puts in front of a
user before making them wait.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import forecast


# ------------------------------------------------------------------ the metric


def test_directional_accuracy_scores_the_first_step_too():
    """The anchor is the last observed price, so no predicted bar is dropped."""
    actual = np.array([101.0, 102.0, 101.0])
    perfect = np.array([101.0, 102.0, 101.0])
    assert forecast.directional_accuracy(actual, perfect, anchor=100.0) == 100.0


def test_directional_accuracy_of_a_mirror_is_zero():
    actual = np.array([101.0, 102.0, 103.0])
    inverted = np.array([99.0, 98.0, 97.0])
    assert forecast.directional_accuracy(actual, inverted, anchor=100.0) == 0.0


def test_the_repo_metric_flatters_a_flat_prediction():
    """The reason directional accuracy exists: this reads 90%+ on nothing."""
    actual = np.linspace(300, 310, 30)
    never_moves = np.full(30, 300.0)
    assert forecast.accuracy(actual, never_moves) > 90


# -------------------------------------------------------------------- folds


@pytest.mark.parametrize("rows,horizon,expected", [
    (1_250, 5, 226), (400, 30, 9), (120, 5, 0), (500, 0, 0),
])
def test_max_folds_counts_non_overlapping_windows(rows, horizon, expected):
    assert forecast.max_folds(rows, horizon) == expected


def test_walk_forward_refuses_a_series_too_short_to_split():
    close = pd.Series(np.linspace(100, 110, 100))
    dates = pd.Series(pd.bdate_range("2024-01-01", periods=100))
    with pytest.raises(ValueError, match="Need at least"):
        forecast.walk_forward(close, dates, folds=3, horizon=30)


# ----------------------------------------------------------------- projection


def test_a_projection_reports_its_move_against_the_last_close():
    projection = forecast.Projection(
        model="LSTM", path=np.array([101.0, 103.0, 105.0]), horizon=3,
        last_price=100.0, last_date=pd.Timestamp("2026-08-07"))
    assert projection.final == 105.0
    assert projection.move_pct == pytest.approx(5.0)
    assert projection.direction == 1


def test_a_projection_with_no_last_price_does_not_divide_by_zero():
    projection = forecast.Projection(
        model="GRU", path=np.array([1.0]), horizon=1, last_price=0.0,
        last_date=pd.Timestamp("2026-08-07"))
    assert projection.move_pct == 0.0


# ------------------------------------------------------------ the cost estimate


@pytest.mark.parametrize("folds,epochs,bars,measured", [
    (3, 30, 1_250, 35.3),      # timed on this stack
    (3, 30, 2_514, 73.7),      # timed on this stack
])
def test_the_training_estimate_matches_what_training_actually_costs(
        folds, epochs, bars, measured):
    """Out by a third is fine. Out by a factor of a thousand is not.

    The first version of this constant lived in the UI and told the user a
    fifty-second job would take "roughly 0s".
    """
    estimate = forecast.estimate_train_seconds(folds, epochs, bars)
    assert estimate == pytest.approx(measured, rel=0.25)


def test_the_estimate_scales_with_every_input():
    base = forecast.estimate_train_seconds(3, 30, 1_000)
    assert forecast.estimate_train_seconds(7, 30, 1_000) == pytest.approx(base * 2)
    assert forecast.estimate_train_seconds(3, 60, 1_000) == pytest.approx(base * 2)
    assert forecast.estimate_train_seconds(3, 30, 2_000) == pytest.approx(base * 2)


# ------------------------------------------------- Phase B: the rollout guard
#
# HT-1 §6 measured `neural.lstm` flipping the sign of its projection on 7.2% of
# identical re-runs, with a maximum drift of 1,899 percentage points -- the
# autoregressive rollout occasionally diverging outright and being shown to the
# user as an ordinary number. These pin the guard that catches it. No
# TensorFlow: `_predict`'s loop is driven with a stub session, so the check runs
# in milliseconds and stays in the default suite rather than behind --runslow.


class _StubSession:
    """A session whose predictions do whatever the test needs them to do."""

    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def run(self, _fetches, feed_dict=None):
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        # (logits, state) -- one row per timestep, one column, as the graph
        # returns for a single-feature series.
        return np.array([[value]], dtype=float), np.zeros((1, 4))


def _rollout(values, *, rows=6, timestamp=2, test_size=3):
    from sklearn.preprocessing import MinMaxScaler

    prices = np.linspace(100.0, 110.0, rows).reshape(-1, 1)
    minmax = MinMaxScaler().fit(prices)
    train = pd.DataFrame(minmax.transform(prices))
    # Keys only, not tensors: the stub session ignores the feed dict, so these
    # just have to exist for `_predict` to build one.
    graph = {
        "logits": "logits", "last_state": "last_state", "state_width": 4,
        "X": "X", "hidden_layer": "hidden_layer",
    }
    return forecast._predict(
        _StubSession(values), graph, train, minmax, timestamp, test_size)


def test_a_diverging_rollout_is_caught_rather_than_returned():
    """A value far outside the scaled training range is not a forecast."""
    with pytest.raises(forecast.DivergedRollout) as raised:
        _rollout([0.5, 0.5, 0.5, forecast.DIVERGENCE_LIMIT * 100])
    assert "not usable" in str(raised.value)


def test_a_non_finite_rollout_is_caught():
    with pytest.raises(forecast.DivergedRollout) as raised:
        _rollout([0.5, 0.5, 0.5, np.inf])
    assert "non-finite" in str(raised.value)


def test_an_ordinary_rollout_passes_the_guard():
    """The guard must not fire on a projection that stays in range."""
    path = _rollout([0.5, 0.4, 0.6, 0.55])
    assert len(path) == 3
    assert np.all(np.isfinite(path))


def test_the_guard_names_the_step_that_diverged():
    """Which step blew up is the useful half of the message."""
    with pytest.raises(forecast.DivergedRollout) as raised:
        _rollout([0.5] * 6 + [1e6], test_size=4)
    assert "step" in str(raised.value)


# --------------------------------------------- Phase B: dropout and the seed


def test_the_default_is_reproducible_not_unseeded():
    """A caller who says nothing gets a seed, and `None` is the explicit opt-out."""
    assert forecast.DEFAULT_SEED is not None
    import inspect

    for entry in (forecast.run, forecast.walk_forward, forecast.project):
        assert inspect.signature(entry).parameters["seed"].default == \
            forecast.DEFAULT_SEED, entry.__name__


def test_dropout_is_not_baked_into_the_graph():
    """The wrapper must read a placeholder, so inference can turn it off.

    Previously `output_keep_prob` was the constant `dropout`, which stayed
    active through `_predict` and randomly dropped a fifth of the outputs of
    every inference call. `_build_graph` no longer takes that argument at all,
    which is what makes the old mistake unexpressible.
    """
    import inspect

    assert "forget_bias" not in inspect.signature(forecast._build_graph).parameters
    source = inspect.getsource(forecast._build_graph)
    assert "placeholder_with_default" in source
    assert 'output_keep_prob=graph["keep_prob"]' in source
