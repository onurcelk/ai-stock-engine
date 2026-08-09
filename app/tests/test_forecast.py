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
