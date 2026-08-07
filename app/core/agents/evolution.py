"""Deep evolution strategy agent, ported from agent/6.evolution-strategy-agent.ipynb.

This is the repo's headline result — the chart in its README. There is no
gradient here: a population of jittered weight sets is scored, and the weights
step toward whichever jitters earned more. Pure numpy, so it is by far the
fastest agent to train.
"""

from __future__ import annotations

import time

import numpy as np

from .base import BaseAgent, ProgressFn, TrainingReport


class Network:
    """One hidden layer, no activation — exactly as the notebook had it."""

    def __init__(self, input_size: int, layer_size: int, output_size: int,
                 rng: np.random.Generator):
        self.weights = [
            rng.standard_normal((input_size, layer_size)),
            rng.standard_normal((layer_size, output_size)),
            rng.standard_normal((1, layer_size)),
        ]

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        feed = np.dot(inputs, self.weights[0]) + self.weights[-1]
        return np.dot(feed, self.weights[1])


class EvolutionStrategyAgent(BaseAgent):
    name = "Evolution strategy"

    def __init__(self, close, window_size: int = 30, skip: int = 1,
                 layer_size: int = 128, population_size: int = 15,
                 sigma: float = 0.1, learning_rate: float = 0.03,
                 seed: int | None = 42):
        super().__init__(close, window_size=window_size, skip=skip, seed=seed)
        self.population_size = population_size
        self.sigma = sigma
        self.learning_rate = learning_rate
        self.network = Network(window_size, layer_size, 3, self.rng)

    def act(self, state: np.ndarray, explore: bool = False) -> int:
        return int(np.argmax(self.network.predict(state)[0]))

    def _reward(self, weights: list[np.ndarray]) -> float:
        original = self.network.weights
        self.network.weights = weights
        try:
            return self._simulate()
        finally:
            self.network.weights = original

    def train(self, iterations: int = 100,
              on_progress: ProgressFn | None = None) -> TrainingReport:
        started = time.time()
        rewards_history: list[float] = []
        weights = self.network.weights

        for iteration in range(iterations):
            # Score a cloud of jittered weight sets around the current point.
            population = [
                [self.rng.standard_normal(w.shape) for w in weights]
                for _ in range(self.population_size)
            ]
            rewards = np.array([
                self._reward([w + self.sigma * jitter
                              for w, jitter in zip(weights, member)])
                for member in population
            ])

            # Standardise so the update depends on ranking, not on the scale
            # of returns, which varies wildly between symbols.
            rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)

            for index in range(len(weights)):
                stacked = np.array([member[index] for member in population])
                weights[index] = weights[index] + (
                    self.learning_rate / (self.population_size * self.sigma)
                    * np.dot(stacked.T, rewards).T
                )

            self.network.weights = weights
            current = self._simulate()
            rewards_history.append(current)
            if on_progress:
                on_progress(iteration, iterations, current)

        return self._report(rewards_history, started, iterations)
