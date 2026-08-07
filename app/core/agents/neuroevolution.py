"""Neuro-evolution agents, ported from agent/21 and agent/22.

A genetic algorithm over small feed-forward networks, with no gradients
anywhere: each generation scores the whole population by trading the series,
keeps the fittest 40% untouched, then refills the rest with mutated crossovers
of fitness-weighted parents. Pure numpy, so it trains without TensorFlow.

The novelty-search variant (notebook 22) *ranks* by how unlike anything already
seen an individual is, rather than by how much it earned, on the theory that
optimising return directly collapses the population onto one mediocre
strategy. Fitness still decides who gets to reproduce — novelty only decides
who survives.
"""

from __future__ import annotations

import time
from collections import deque

import numpy as np

from .base import BaseAgent, ProgressFn, TrainingReport, all_states

# Novelty-search constants, named as in the notebook.
NOVELTY_THRESHOLD = 6      # out of 10, the chance of archiving a generation
NOVELTY_LOG_MAXLEN = 1000
BACKLOG_MAXSIZE = 500
NEIGHBOURS = 4


class Individual:
    """One candidate policy: two weight matrices and its last score."""

    __slots__ = ("W1", "W2", "fitness", "features")

    def __init__(self, window_size: int, hidden_size: int, rng: np.random.Generator):
        # Notebook initialisation, including the fan-in scaling.
        self.W1 = rng.standard_normal((window_size, hidden_size)) / np.sqrt(window_size)
        self.W2 = rng.standard_normal((hidden_size, 3)) / np.sqrt(hidden_size)
        self.fitness = 0.0
        self.features: np.ndarray | None = None

    def copy_weights_from(self, other: "Individual") -> None:
        self.W1 = other.W1.copy()
        self.W2 = other.W2.copy()


class NeuroEvolutionAgent(BaseAgent):
    """Genetic algorithm over feed-forward policies (notebook 21)."""

    name = "Neuro-evolution"
    novelty_search = False

    def __init__(self, close, window_size: int = 30, skip: int = 1,
                 layer_size: int = 128, population_size: int = 50,
                 mutation_rate: float = 0.1, seed: int | None = 42):
        super().__init__(close, window_size=window_size, skip=skip, seed=seed)
        self.layer_size = layer_size
        self.mutation_rate = mutation_rate

        # Crossover consumes parents two at a time, so an odd parent count
        # would walk off the end of the list. Keep the split even instead.
        self.population_size = max(4, population_size)
        self.n_winners = max(2, int(self.population_size * 0.4))
        if (self.population_size - self.n_winners) % 2:
            self.n_winners += 1
        self.n_parents = self.population_size - self.n_winners

        self.states = all_states(self.trend, window_size)
        self.best = self._spawn()

        # Behaviour archives for novelty search. deque(maxlen=...) drops the
        # oldest entry; the notebook's _memorize pops the item it just pushed,
        # so its archives went inert the moment they filled up.
        self.novel_pop: deque = deque(maxlen=BACKLOG_MAXSIZE)
        self.novel_backlog: deque = deque(maxlen=NOVELTY_LOG_MAXLEN)

    def _spawn(self) -> Individual:
        return Individual(self.window_size, self.layer_size, self.rng)

    # ---------------------------------------------------------------- policy

    def act(self, state: np.ndarray, explore: bool = False) -> int:
        hidden = np.maximum(state @ self.best.W1, 0)
        # The notebook softmaxes before argmax; softmax is monotonic per row,
        # so the chosen action is identical and the exponential is wasted work.
        return int(np.argmax(hidden @ self.best.W2, axis=1)[0])

    def _actions(self, individual: Individual) -> np.ndarray:
        """Every action for the whole series in one forward pass."""
        hidden = np.maximum(self.states @ individual.W1, 0)
        return np.argmax(hidden @ individual.W2, axis=1)

    def _score(self, individual: Individual) -> float:
        """Percentage return of this policy — one unit per trade, no costs."""
        actions = self._actions(individual)
        cash = 10_000.0
        held = 0
        for t in range(0, len(self.trend) - 1, self.skip):
            price = self.trend[t]
            action = actions[t]
            if action == 1 and cash >= price:
                held += 1
                cash -= price
            elif action == 2 and held > 0:
                held -= 1
                cash += price
        return (cash - 10_000.0) / 10_000.0 * 100

    # -------------------------------------------------------------- genetics

    def _mutate(self, individual: Individual, scale: float = 1.0) -> Individual:
        for name in ("W1", "W2"):
            weights = getattr(individual, name)
            mask = self.rng.binomial(1, self.mutation_rate, size=weights.shape)
            weights += self.rng.normal(0.0, scale, size=weights.shape) * mask
        return individual

    def _crossover(self, first: Individual, second: Individual) -> tuple[Individual, Individual]:
        """Single-point crossover on the hidden axis of both weight matrices."""
        child_a, child_b = self._spawn(), self._spawn()
        child_a.copy_weights_from(first)
        child_b.copy_weights_from(second)
        for name in ("W1", "W2"):
            columns = getattr(child_a, name).shape[1]
            cut = int(self.rng.integers(0, columns))
            getattr(child_a, name)[:, cut:] = getattr(second, name)[:, cut:].copy()
            getattr(child_b, name)[:, cut:] = getattr(first, name)[:, cut:].copy()
        return child_a, child_b

    def _choose_parents(self, population: list[Individual]) -> list[Individual]:
        """Fitness-proportionate selection, without replacement.

        Returns are routinely zero or negative — a policy that never sells
        scores exactly 0 — so the notebook's `p = |fitness| / total` blows up
        (division by zero) or is rejected by numpy for having fewer non-zero
        entries than the sample size. Fall back to uniform in those cases.
        """
        weights = np.abs([individual.fitness for individual in population], dtype=float)
        total = weights.sum()
        if total <= 0 or np.count_nonzero(weights) < self.n_parents:
            probabilities = None
        else:
            probabilities = weights / total
        picked = self.rng.choice(len(population), size=self.n_parents,
                                 replace=False, p=probabilities)
        return [population[index] for index in picked]

    # ---------------------------------------------------------------- novelty

    @staticmethod
    def _novelty(descriptor: np.ndarray, archive: deque) -> float:
        """Mean distance to the k nearest entries already archived."""
        if not archive:
            return 0.0
        matrix = np.asarray(archive)
        distances = np.linalg.norm(matrix - descriptor, axis=1)
        k = min(NEIGHBOURS, len(distances))
        return float(np.mean(np.sort(distances)[:k]))

    def _rank(self, population: list[Individual]) -> list[Individual]:
        if not self.novelty_search:
            return sorted(population, key=lambda p: p.fitness, reverse=True)
        scores = [
            self._novelty(p.features, self.novel_backlog)
            + self._novelty(p.features, self.novel_pop)
            for p in population
        ]
        order = np.argsort(scores)[::-1]
        return [population[index] for index in order]

    def _archive(self, survivors: list[Individual]) -> None:
        for individual in survivors:
            if individual.features is None:
                continue
            self.novel_pop.append(individual.features)
            if self.rng.integers(0, 10) < NOVELTY_THRESHOLD:
                self.novel_backlog.append(individual.features)

    # --------------------------------------------------------------- training

    def train(self, iterations: int = 30,
              on_progress: ProgressFn | None = None) -> TrainingReport:
        started = time.time()
        history: list[float] = []
        population = [self._spawn() for _ in range(self.population_size)]

        for generation in range(iterations):
            for individual in population:
                individual.fitness = self._score(individual)
                # The notebook's behaviour descriptor is the output weights
                # themselves, so "novel" here means structurally unlike its
                # ancestors rather than behaving differently on the tape.
                individual.features = individual.W2.ravel().copy()

            ranked = self._rank(population)
            fittest = max(population, key=lambda p: p.fitness)
            if fittest.fitness >= self.best.fitness or generation == 0:
                self.best = fittest

            survivors = ranked[: self.n_winners]
            if self.novelty_search:
                self._archive(survivors)

            parents = self._choose_parents(ranked)
            children: list[Individual] = []
            for index in range(0, len(parents) - 1, 2):
                first, second = self._crossover(parents[index], parents[index + 1])
                children += [self._mutate(first), self._mutate(second)]
            population = survivors + children

            history.append(fittest.fitness)
            if on_progress:
                on_progress(generation, iterations, fittest.fitness)

        return self._report(history, started, iterations)


class NoveltySearchAgent(NeuroEvolutionAgent):
    """Neuro-evolution ranked by novelty rather than return (notebook 22)."""

    name = "Neuro-evolution (novelty search)"
    novelty_search = True
