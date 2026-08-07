"""The 19 reinforcement-learning agents.

Registry integrity and the vectorised state helper are cheap and always run.
Actually training all 19 is not — each builds a TensorFlow graph and trains a
policy — so that sweep is marked slow and needs --runslow.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import agents, backtest
from core.agents.base import all_states, window_state

# What streamlit_app.py passes when it constructs an agent. If an agent stops
# accepting these, the UI breaks — so the sweep below uses exactly this set.
UI_KWARGS = dict(window_size=20, layer_size=32, seed=42)


# ------------------------------------------------------------------- registry


def test_registry_is_complete():
    """Every registered agent needs an iteration default and a citation."""
    assert len(agents.REGISTRY) == 19
    assert set(agents.DEFAULT_ITERATIONS) == set(agents.REGISTRY)
    assert set(agents.SOURCE_NOTEBOOK) == set(agents.REGISTRY)


def test_iteration_defaults_fit_the_ui_slider():
    """The slider is range 5-500 with step 5, so defaults must land on it."""
    for name, value in agents.DEFAULT_ITERATIONS.items():
        assert 5 <= value <= 500, name
        assert value % 5 == 0, name


def test_notebook_citations_are_in_range():
    """Notebooks 4-22 are the RL ones; 1-3 and 23 are rule-based."""
    numbers = sorted(agents.SOURCE_NOTEBOOK.values())
    assert numbers == list(range(4, 23))


def test_every_agent_exposes_the_interface():
    for name, klass in agents.REGISTRY.items():
        assert hasattr(klass, "train"), name
        assert hasattr(klass, "signals"), name
        assert hasattr(klass, "act"), name


def test_families_are_parameterised_not_copied():
    """19 agents from 6 modules is the whole point of the flag decomposition."""
    modules = {klass.__module__.rsplit(".", 1)[-1] for klass in agents.REGISTRY.values()}
    assert len(modules) <= 7
    assert {"deepq", "actorcritic", "curiosity", "neuroevolution"} <= modules


@pytest.mark.parametrize("flag", ["double", "duel", "recurrent"])
def test_deepq_flags_produce_distinct_graphs(flag):
    """Each flag must actually be set on some registered agent."""
    from core.agents import deepq

    variants = [k for k in agents.REGISTRY.values()
                if issubclass(k, deepq.DeepQAgent)]
    assert any(getattr(k, flag) for k in variants), flag
    assert any(not getattr(k, flag) for k in variants), flag


# --------------------------------------------------------------- state helper


@pytest.mark.parametrize("rows, window", [
    (200, 30),
    (50, 5),
    (12, 30),    # series shorter than the window — the padding path
    (1254, 17),
])
def test_all_states_matches_the_per_bar_version(rows, window):
    """The vectorised path is only safe if it is bit-identical to the slow one."""
    trend = np.cumsum(np.random.default_rng(0).standard_normal(rows)) + 100
    fast = all_states(trend, window)
    slow = np.vstack([window_state(trend, t, window)[0] for t in range(rows)])

    assert fast.shape == (rows, window)
    assert np.allclose(fast, slow)


def test_window_state_left_pads_with_the_first_price():
    """Before there is history the differences must be zero, not garbage."""
    trend = np.array([100.0, 101.0, 103.0])
    assert np.allclose(window_state(trend, 0, 3)[0], [0.0, 0.0, 0.0])


# ---------------------------------------------------------------- the sweep


@pytest.mark.slow
@pytest.mark.parametrize("name", list(agents.REGISTRY))
def test_agent_trains_and_produces_tradeable_signals(name, bundled, bundled_close):
    """Construct, train, emit signals, and clear the real backtester.

    Three iterations is enough to prove the loop runs; it is nowhere near
    enough to learn anything, so nothing here asserts on profitability.
    """
    klass = agents.REGISTRY[name]
    learner = klass(bundled_close, **UI_KWARGS)
    try:
        report = learner.train(3, on_progress=None)
        signal = learner.signals()

        assert len(report.rewards) == 3
        assert report.seconds >= 0
        assert len(signal) == len(bundled_close)
        assert signal.index.equals(bundled_close.index)
        assert not signal.isna().any()
        assert set(signal.unique()) <= {-1.0, 0.0, 1.0}

        result = backtest.run(bundled_close, signal, bundled["date"],
                              initial_money=10_000, max_buy=1, max_sell=1)
        # Never short: a sell needs inventory to sell.
        assert len(result.sells) <= len(result.buys)
        assert np.isfinite(result.roi_pct)
    finally:
        if hasattr(learner, "close_session"):
            learner.close_session()


@pytest.mark.slow
def test_seed_makes_training_reproducible(bundled_close):
    """The UI exposes a seed control, so it has to mean something."""
    runs = [
        agents.NeuroEvolutionAgent(bundled_close, **UI_KWARGS).train(5).rewards
        for _ in range(2)
    ]
    assert runs[0] == runs[1]

    other = dict(UI_KWARGS, seed=99)
    different = agents.NeuroEvolutionAgent(bundled_close, **other).train(5).rewards
    assert different != runs[0]


@pytest.mark.slow
def test_novelty_search_diverges_from_plain_neuroevolution(bundled_close):
    """Ranking by novelty rather than fitness must change what survives.

    At very few generations both keep generation zero's fittest individual and
    look identical, so this needs enough generations for selection to bite.
    """
    plain = agents.NeuroEvolutionAgent(bundled_close, **UI_KWARGS)
    novel = agents.NoveltySearchAgent(bundled_close, **UI_KWARGS)
    plain.train(20)
    novel.train(20)
    assert not plain.signals().equals(novel.signals())
