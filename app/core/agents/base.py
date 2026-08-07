"""Shared scaffolding for the reinforcement-learning agents.

The notebooks each carried their own copy of the state function *and* their
own money accounting inside a `buy()` method. Here the agents only decide
*what to do* — they emit a signal series, and backtest.run() executes it. That
way an RL agent is charged the same commissions and sized the same way as the
rule-based ones, so the numbers are actually comparable.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Callable

import numpy as np
import pandas as pd

from .. import strategies

# action ids, as the notebooks defined them
HOLD, BUY, SELL = 0, 1, 2

ProgressFn = Callable[[int, int, float], None]


def window_state(trend: np.ndarray, t: int, window_size: int) -> np.ndarray:
    """The agent's view at time `t`: the last `window_size` price changes.

    Before there is enough history the window is left-padded with the first
    price, which makes the early differences zero — the same behaviour as the
    notebooks' list-concatenation version, without requiring a Python list.
    """
    size = window_size + 1
    start = t - size + 1
    if start >= 0:
        block = trend[start : t + 1]
    else:
        block = np.concatenate([np.full(-start, trend[0]), trend[: t + 1]])
    return np.diff(block).reshape(1, -1)


def all_states(trend: np.ndarray, window_size: int) -> np.ndarray:
    """Every window_state stacked into one (len(trend), window_size) matrix.

    Row t is exactly `window_state(trend, t, window_size)`. A feed-forward
    agent chooses its action from the price window alone — cash and inventory
    only decide whether that action is *executable* — so a whole episode's
    forward pass can be a single matmul instead of one per bar. For a
    population-based method that is the difference between a usable slider and
    a two-minute wait. Not valid for the recurrent agents, which carry state.
    """
    padded = np.concatenate([np.full(window_size, trend[0]), trend])
    windows = np.lib.stride_tricks.sliding_window_view(padded, window_size + 1)
    return np.diff(windows, axis=1)


@dataclasses.dataclass
class TrainingReport:
    iterations: int
    rewards: list[float]
    seconds: float

    @property
    def final_reward(self) -> float:
        return self.rewards[-1] if self.rewards else 0.0

    @property
    def best_reward(self) -> float:
        return max(self.rewards) if self.rewards else 0.0

    @property
    def improved(self) -> bool:
        """Did training actually go anywhere?"""
        if len(self.rewards) < 2:
            return False
        return self.rewards[-1] > self.rewards[0]


FRAMES = 4  # state vectors the recurrent variants stack


class EpisodeState:
    """Per-episode bookkeeping shared by the TensorFlow agent families.

    A recurrent agent sees a stack of the last FRAMES state vectors and threads
    the LSTM cell state from one bar to the next; a feed-forward one only needs
    the current vector. Both have to be reset at the start of every episode and
    recorded into replay memory the same way, so the bookkeeping lives here
    instead of being repeated in each family.

    Expects the host class to define `recurrent`, `layer_size` and `state()`.
    """

    recurrent = False

    def _reset_episode(self) -> None:
        first = self.state(0).ravel()
        # The notebooks pre-fill every frame with the opening state, so the
        # first prediction already sees a full-length sequence.
        self._frames = np.repeat(first[None, :], FRAMES, axis=0)
        self._flat = first.copy()
        self._hidden = np.zeros((1, 2 * self.layer_size))

    def _push(self, state: np.ndarray) -> np.ndarray:
        """Record the state for bar t and return it flat."""
        flat = np.asarray(state, dtype=float).ravel()
        if self.recurrent:
            # Newest frame first, which is how the notebooks stack them — note
            # the graphs then read rnn[:, -1], i.e. the *oldest* frame. Odd,
            # but reproducing it is what keeps these numbers comparable.
            self._frames = np.concatenate([flat[None, :], self._frames[:-1]], axis=0)
        else:
            self._flat = flat
        return flat

    def _observation(self) -> np.ndarray:
        """What replay memory should store for the bar just pushed."""
        return self._frames.copy() if self.recurrent else self._flat.copy()

    def _next_observation(self, following: np.ndarray) -> np.ndarray:
        if self.recurrent:
            return np.concatenate([following[None, :], self._frames[:FRAMES - 1]], axis=0)
        return following


class BaseAgent:
    """Common interface: train, then emit signals for the shared backtester."""

    name = "agent"

    def __init__(self, close: pd.Series, window_size: int = 30, skip: int = 1,
                 seed: int | None = 42):
        self.close = close
        self.trend = close.to_numpy(dtype=float)
        self.window_size = window_size
        self.skip = max(1, skip)
        self.rng = np.random.default_rng(seed)
        self.seed = seed

    def state(self, t: int) -> np.ndarray:
        return window_state(self.trend, t, self.window_size)

    def act(self, state: np.ndarray, explore: bool = False) -> int:
        raise NotImplementedError

    def train(self, iterations: int, on_progress: ProgressFn | None = None) -> TrainingReport:
        raise NotImplementedError

    def signals(self) -> pd.Series:
        """Replay the trained policy and record what it would do.

        Inventory is tracked only so a sell is never emitted with nothing to
        sell; cash, fees and position size are the backtester's business.
        """
        signal = np.full(len(self.trend), strategies.HOLD, dtype=float)
        held = 0
        state = self.state(0)

        for t in range(0, len(self.trend) - 1, self.skip):
            action = self.act(state, explore=False)
            if action == BUY:
                signal[t] = strategies.BUY
                held += 1
            elif action == SELL and held > 0:
                signal[t] = strategies.SELL
                held -= 1
            state = self.state(t + 1)

        return pd.Series(signal, index=self.close.index)

    def _report(self, rewards: list[float], started: float, iterations: int) -> TrainingReport:
        return TrainingReport(iterations=iterations, rewards=rewards,
                              seconds=time.time() - started)

    def _simulate(self, initial_money: float = 10_000.0) -> float:
        """Percentage return of the current policy — the RL reward signal.

        Deliberately simple (one unit per trade, no costs) because it is the
        agent's objective function, not a performance claim. The reported
        result comes from the real backtester.
        """
        cash = initial_money
        inventory: list[float] = []
        state = self.state(0)

        for t in range(0, len(self.trend) - 1, self.skip):
            action = self.act(state, explore=False)
            price = self.trend[t]
            if action == BUY and cash >= price:
                inventory.append(price)
                cash -= price
            elif action == SELL and inventory:
                inventory.pop(0)
                cash += price
            state = self.state(t + 1)

        return (cash - initial_money) / initial_money * 100
