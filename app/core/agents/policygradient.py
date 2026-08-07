"""Policy gradient agent, ported from agent/4.policy-gradient-agent.ipynb.

Instead of learning what each action is worth and then acting greedily, this
learns the policy directly: one softmax head over the three actions, updated
once per episode from the whole trajectory, weighted by discounted reward.

Two inherited oddities, kept because changing them would make the numbers
incomparable with the notebook:

* the action is the argmax of the softmax rather than a sample from it, so the
  policy is deterministic and never explores — unusual for a policy gradient,
  and it means the only randomness is the weight initialisation;
* the per-step reward banked in the trajectory is the running *cash balance*,
  not the change in it, so the discounted signal is dominated by the account
  size rather than by what any single action earned.
"""

from __future__ import annotations

import time

import numpy as np

from .base import BaseAgent, ProgressFn, TrainingReport

ACTIONS = 3


class PolicyGradientAgent(BaseAgent):
    name = "Policy gradient"

    def __init__(self, close, window_size: int = 30, skip: int = 1,
                 layer_size: int = 256, learning_rate: float = 1e-4,
                 gamma: float = 0.9, seed: int | None = 42):
        super().__init__(close, window_size=window_size, skip=skip, seed=seed)
        self.layer_size = layer_size
        self.gamma = gamma
        self.half_window = window_size // 2

        from ..forecast import _load_tf  # lazy: TensorFlow costs seconds

        tf = self._tf = _load_tf()
        tf.reset_default_graph()
        if seed is not None:
            tf.set_random_seed(seed)

        self.X = tf.placeholder(tf.float32, (None, window_size))
        self.REWARDS = tf.placeholder(tf.float32, (None,))
        self.ACTIONS = tf.placeholder(tf.int32, (None,))

        feed = tf.layers.dense(self.X, layer_size, activation=tf.nn.relu)
        self.logits = tf.layers.dense(feed, ACTIONS, activation=tf.nn.softmax)

        taken = tf.one_hot(self.ACTIONS, ACTIONS)
        # The notebook's own log-likelihood surrogate, kept verbatim: it is a
        # smooth stand-in for log pi(a|s) that stays finite at probability 0.
        loglike = tf.log(
            (taken * (taken - self.logits) + (1 - taken) * (taken + self.logits)) + 1)
        rewards = tf.tile(tf.reshape(self.REWARDS, (-1, 1)), [1, ACTIONS])
        self.cost = -tf.reduce_mean(loglike * (rewards + 1))
        self.optimizer = tf.train.AdamOptimizer(learning_rate).minimize(self.cost)

        self.session = tf.InteractiveSession()
        self.session.run(tf.global_variables_initializer())

    def close_session(self) -> None:
        """Graphs are process-global in TF1; leaking sessions exhausts memory."""
        if getattr(self, "session", None) is not None:
            self.session.close()
            self.session = None

    def act(self, state: np.ndarray, explore: bool = False) -> int:
        probabilities = self.session.run(
            self.logits, feed_dict={self.X: np.asarray(state, dtype=float).reshape(1, -1)})
        return int(np.argmax(probabilities[0]))

    def _discount(self, rewards: np.ndarray) -> np.ndarray:
        discounted = np.zeros_like(rewards, dtype=float)
        running = 0.0
        for index in reversed(range(rewards.size)):
            running = running * self.gamma + rewards[index]
            discounted[index] = running
        return discounted

    def train(self, iterations: int = 50, initial_money: float = 10_000.0,
              on_progress: ProgressFn | None = None) -> TrainingReport:
        started = time.time()
        history: list[float] = []
        last_bar = len(self.trend) - self.half_window

        for iteration in range(iterations):
            states: list[np.ndarray] = []
            actions: list[int] = []
            banked: list[float] = []
            cash = initial_money
            inventory: list[float] = []

            for t in range(0, len(self.trend) - 1, self.skip):
                state = self.state(t)
                action = self.act(state)
                price = self.trend[t]

                # Stop opening positions near the end, so the agent isn't
                # rewarded for buying with no time left to sell.
                if action == 1 and cash >= price and t < last_bar:
                    inventory.append(price)
                    cash -= price
                elif action == 2 and inventory:
                    inventory.pop(0)
                    cash += price

                states.append(state.ravel())
                actions.append(action)
                banked.append(cash)

            discounted = self._discount(np.asarray(banked, dtype=float))
            self.session.run(
                [self.cost, self.optimizer],
                feed_dict={
                    self.X: np.vstack(states),
                    self.REWARDS: discounted,
                    self.ACTIONS: np.asarray(actions, dtype=np.int32),
                },
            )

            # The policy is deterministic, so the episode just traded *is* the
            # greedy policy — no separate evaluation pass needed.
            history.append((cash - initial_money) / initial_money * 100)
            if on_progress:
                on_progress(iteration, iterations, history[-1])

        return self._report(history, started, iterations)
