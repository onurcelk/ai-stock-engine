"""Deep Q-learning agent, ported from agent/5.q-learning-agent.ipynb.

A one-hidden-layer network estimates the value of each action; experience is
replayed from a bounded memory and epsilon decays from exploration toward
exploitation. TensorFlow is imported lazily so the app starts instantly.
"""

from __future__ import annotations

import random
import time
from collections import deque

import numpy as np

from .base import BaseAgent, ProgressFn, TrainingReport


class QLearningAgent(BaseAgent):
    name = "Q-learning"

    def __init__(self, close, window_size: int = 30, skip: int = 1,
                 layer_size: int = 256, batch_size: int = 32,
                 learning_rate: float = 1e-5, gamma: float = 0.95,
                 epsilon: float = 0.5, epsilon_min: float = 0.01,
                 epsilon_decay: float = 0.999, seed: int | None = 42):
        super().__init__(close, window_size=window_size, skip=skip, seed=seed)
        self.action_size = 3
        self.batch_size = batch_size
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.memory: deque = deque(maxlen=1000)
        self._random = random.Random(seed)

        from ..forecast import _load_tf  # lazy: TensorFlow costs seconds

        tf = self._tf = _load_tf()
        tf.reset_default_graph()
        if seed is not None:
            tf.set_random_seed(seed)

        self.session = tf.InteractiveSession()
        self.X = tf.placeholder(tf.float32, [None, window_size])
        self.Y = tf.placeholder(tf.float32, [None, self.action_size])
        feed = tf.layers.dense(self.X, layer_size, activation=tf.nn.relu)
        self.logits = tf.layers.dense(feed, self.action_size)
        self.cost = tf.reduce_mean(tf.square(self.Y - self.logits))
        self.optimizer = tf.train.GradientDescentOptimizer(
            learning_rate).minimize(self.cost)
        self.session.run(tf.global_variables_initializer())

    def close_session(self) -> None:
        """Graphs are process-global in TF1; leaking sessions exhausts memory."""
        if getattr(self, "session", None) is not None:
            self.session.close()
            self.session = None

    def act(self, state: np.ndarray, explore: bool = False) -> int:
        if explore and self._random.random() <= self.epsilon:
            return self._random.randrange(self.action_size)
        return int(np.argmax(
            self.session.run(self.logits, feed_dict={self.X: state})[0]
        ))

    def _replay(self, batch_size: int) -> float:
        # The notebook replays the most recent transitions rather than a random
        # sample; kept as-is so behaviour matches.
        batch = list(self.memory)[-batch_size:]
        states = np.array([item[0][0] for item in batch])
        next_states = np.array([item[3][0] for item in batch])

        q_current = self.session.run(self.logits, feed_dict={self.X: states})
        q_next = self.session.run(self.logits, feed_dict={self.X: next_states})

        inputs = np.empty((len(batch), self.window_size))
        targets = np.empty((len(batch), self.action_size))
        for i, (state, action, reward, _next, done) in enumerate(batch):
            target = q_current[i]
            target[action] = reward
            if not done:
                target[action] += self.gamma * np.amax(q_next[i])
            inputs[i] = state
            targets[i] = target

        cost, _ = self.session.run(
            [self.cost, self.optimizer], feed_dict={self.X: inputs, self.Y: targets}
        )
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        return float(cost)

    def train(self, iterations: int = 50, initial_money: float = 10_000.0,
              on_progress: ProgressFn | None = None) -> TrainingReport:
        started = time.time()
        rewards_history: list[float] = []
        half_window = self.window_size // 2

        for iteration in range(iterations):
            cash = initial_money
            inventory: list[float] = []
            state = self.state(0)

            for t in range(0, len(self.trend) - 1, self.skip):
                action = self.act(state, explore=True)
                next_state = self.state(t + 1)
                price = self.trend[t]

                # Stop opening positions near the end so the agent isn't
                # rewarded for buying with no time left to sell.
                if action == 1 and cash >= price and t < len(self.trend) - half_window:
                    inventory.append(price)
                    cash -= price
                elif action == 2 and inventory:
                    inventory.pop(0)
                    cash += price

                gain = (cash - initial_money) / initial_money
                self.memory.append((state, action, gain, next_state, cash < initial_money))
                state = next_state
                self._replay(min(self.batch_size, len(self.memory)))

            reward = (cash - initial_money) / initial_money * 100
            rewards_history.append(reward)
            if on_progress:
                on_progress(iteration, iterations, reward)

        return self._report(rewards_history, started, iterations)
