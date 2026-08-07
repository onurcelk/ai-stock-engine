"""The curiosity-driven family, ported from agent/18, agent/19 and agent/20.

Ordinary Q-learning only ever chases the extrinsic reward, so on a price series
it tends to settle early on whatever crude rule happened to pay first. These
agents add a second network — a *forward model* that tries to predict the next
state from the current one and the action taken — and hand its prediction error
back as an intrinsic reward:

    total reward  =  extrinsic (money) + curiosity (surprise)

Where the forward model is still wrong, the agent has not understood that part
of the series yet, so it is worth more visits. As the model learns a region the
bonus decays on its own, which is what makes it a self-annealing explorer
rather than a fixed exploration constant.

    notebook 18  plain      notebook 20  duel
    notebook 19  recurrent

Unlike the other families here the Q-network is trained with RMSProp and a hard
target-network copy, matching these three notebooks.
"""

from __future__ import annotations

import random
import time
from collections import deque

import numpy as np

from .base import BaseAgent, EpisodeState, ProgressFn, TrainingReport

ACTIONS = 3
CURIOSITY_HIDDEN = 32


class CuriosityAgent(EpisodeState, BaseAgent):
    """Shared skeleton. The registered agents are the subclasses below."""

    name = "Curiosity Q-learning"
    duel = False
    recurrent = False

    def __init__(self, close, window_size: int = 30, skip: int = 1,
                 layer_size: int = 128, batch_size: int = 32,
                 learning_rate: float = 0.003, gamma: float = 0.99,
                 epsilon: float = 0.5, epsilon_min: float = 0.1,
                 decay_rate: float = 0.005, memory_size: int = 300,
                 copy_every: int = 1000, seed: int | None = 42):
        super().__init__(close, window_size=window_size, skip=skip, seed=seed)
        # Duel splits the hidden layer in two, so it has to be even.
        self.layer_size = layer_size + (layer_size % 2)
        self.batch_size = batch_size
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.decay_rate = decay_rate
        self.copy_every = copy_every
        self.memory: deque = deque(maxlen=memory_size)
        self._random = random.Random(seed)
        self._copies = 0

        from ..forecast import _load_tf  # lazy: TensorFlow costs seconds

        tf = self._tf = _load_tf()
        tf.reset_default_graph()
        if seed is not None:
            tf.set_random_seed(seed)

        shape = (None, None, window_size) if self.recurrent else (None, window_size)
        self.X = tf.placeholder(tf.float32, shape)
        self.Y = tf.placeholder(tf.float32, shape)
        self.ACTION = tf.placeholder(tf.float32, (None,))
        self.REWARD = tf.placeholder(tf.float32, (None,))
        self.hidden = tf.placeholder(tf.float32, (None, 2 * self.layer_size))
        batch = tf.shape(self.ACTION)[0]

        curiosity_cost = self._build_curiosity(tf, batch)
        # The whole point: surprise is added to money before bootstrapping.
        total_reward = tf.add(curiosity_cost, self.REWARD)

        with tf.variable_scope("q_model"):
            with tf.variable_scope("eval_net"):
                self.logits = self._q_head(tf, self.X, evaluating=True)
            with tf.variable_scope("target_net"):
                next_q = self._q_head(tf, self.Y, evaluating=False)

            q_target = total_reward + self.gamma * tf.reduce_max(next_q, axis=1)
            taken = tf.cast(self.ACTION, tf.int32)
            indices = tf.stack([tf.range(batch, dtype=tf.int32), taken], axis=1)
            q_taken = tf.gather_nd(params=self.logits, indices=indices)
            self.cost = tf.losses.mean_squared_error(labels=q_target, predictions=q_taken)
            # Only the evaluation net learns; the target net is copied onto.
            self.optimizer = tf.train.RMSPropOptimizer(learning_rate).minimize(
                self.cost,
                var_list=tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                                           "q_model/eval_net"))

        target_vars = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,
                                        scope="q_model/target_net")
        eval_vars = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,
                                      scope="q_model/eval_net")
        self.replace_target = [tf.assign(t, e) for t, e in zip(target_vars, eval_vars)]

        self.session = tf.InteractiveSession()
        self.session.run(tf.global_variables_initializer())

        self._reset_episode()

    # ----------------------------------------------------------------- graph

    def _build_curiosity(self, tf, batch):
        """Forward model: predict the next state, and return its per-sample error."""
        with tf.variable_scope("curiosity_model"):
            if self.recurrent:
                steps = tf.shape(self.X)[1]
                action = tf.tile(tf.reshape(self.ACTION, (-1, 1, 1)), [1, steps, 1])
                state_action = tf.concat([self.X, action], axis=-1)
                cell = tf.nn.rnn_cell.LSTMCell(self.layer_size, state_is_tuple=False)
                rnn, _last = tf.nn.dynamic_rnn(
                    inputs=state_action, cell=cell, dtype=tf.float32,
                    initial_state=self.hidden)
                predicted = tf.layers.dense(rnn[:, -1], self.window_size)
                actual = self.Y[:, -1]
            else:
                action = tf.reshape(self.ACTION, (-1, 1))
                state_action = tf.concat([self.X, action], axis=1)
                feed = tf.layers.dense(state_action, CURIOSITY_HIDDEN,
                                       activation=tf.nn.relu)
                predicted = tf.layers.dense(feed, self.window_size)
                actual = tf.identity(self.Y)

            self.curiosity_cost = tf.reduce_sum(tf.square(actual - predicted), axis=1)
            self.curiosity_optimizer = tf.train.RMSPropOptimizer(0.003).minimize(
                tf.reduce_mean(self.curiosity_cost))
        return self.curiosity_cost

    def _q_head(self, tf, source, evaluating: bool):
        if self.recurrent:
            cell = tf.nn.rnn_cell.LSTMCell(self.layer_size, state_is_tuple=False)
            rnn, last_state = tf.nn.dynamic_rnn(
                inputs=source, cell=cell, dtype=tf.float32, initial_state=self.hidden)
            if evaluating:
                self.last_state = last_state
            feed = rnn[:, -1]
        else:
            feed = tf.layers.dense(source, self.layer_size, tf.nn.relu)

        if not self.duel:
            return tf.layers.dense(feed, ACTIONS)
        advantage_stream, value_stream = tf.split(feed, 2, 1)
        advantage = tf.layers.dense(advantage_stream, ACTIONS)
        value = tf.layers.dense(value_stream, 1)
        return value + (advantage - tf.reduce_mean(advantage, axis=1, keepdims=True))

    def close_session(self) -> None:
        """Graphs are process-global in TF1; leaking sessions exhausts memory."""
        if getattr(self, "session", None) is not None:
            self.session.close()
            self.session = None

    # ----------------------------------------------------------------- policy

    def act(self, state: np.ndarray, explore: bool = False) -> int:
        flat = self._push(state)

        if explore and self._random.random() < self.epsilon:
            return self._random.randrange(ACTIONS)

        if self.recurrent:
            logits, last_state = self.session.run(
                [self.logits, self.last_state],
                feed_dict={self.X: [self._frames], self.hidden: self._hidden},
            )
            self._hidden = last_state
            return int(np.argmax(logits[0]))

        logits = self.session.run(self.logits, feed_dict={self.X: flat[None, :]})
        return int(np.argmax(logits[0]))

    def signals(self):
        self._reset_episode()
        return super().signals()

    def _simulate(self, initial_money: float = 10_000.0) -> float:
        self._reset_episode()
        return super()._simulate(initial_money)

    # ----------------------------------------------------------------- replay

    def _learn(self) -> None:
        size = min(len(self.memory), self.batch_size)
        if size == 0:
            return
        batch = self._random.sample(list(self.memory), size)

        feed = {
            self.X: np.array([item[0] for item in batch]),
            self.Y: np.array([item[3] for item in batch]),
            self.ACTION: np.array([item[1] for item in batch], dtype=float),
            self.REWARD: np.array([item[2] for item in batch], dtype=float),
        }
        if self.recurrent:
            feed[self.hidden] = np.array([item[5] for item in batch])

        # The forward model and the Q-network are trained on the same batch;
        # the Q-target reads the forward model's current error as its bonus.
        self.session.run(self.curiosity_optimizer, feed_dict=feed)
        self.session.run([self.cost, self.optimizer], feed_dict=feed)

        self._copies += 1
        if self._copies % self.copy_every == 0:
            self.session.run(self.replace_target)

    # --------------------------------------------------------------- training

    def train(self, iterations: int = 10, initial_money: float = 10_000.0,
              on_progress: ProgressFn | None = None) -> TrainingReport:
        started = time.time()
        history: list[float] = []

        for iteration in range(iterations):
            self._reset_episode()
            cash = initial_money
            inventory: list[float] = []

            for t in range(0, len(self.trend) - 1, self.skip):
                action = self.act(self.state(t), explore=True)
                state_now = self._observation()
                hidden_now = self._hidden[0].copy() if self.recurrent else None

                price = self.trend[t]
                if action == 1 and cash >= price:
                    inventory.append(price)
                    cash -= price
                elif action == 2 and inventory:
                    inventory.pop(0)
                    cash += price

                next_state = self._next_observation(self.state(t + 1).ravel())
                reward = (cash - initial_money) / initial_money
                self.memory.append((state_now, action, reward, next_state,
                                    cash < initial_money, hidden_now))
                self._learn()

            # Greedy policy return; see deepq.py for why the traded episode's
            # own return is not a usable curve at these epsilon values.
            history.append(self._simulate(initial_money))
            self.epsilon = self.epsilon_min + (1.0 - self.epsilon_min) * np.exp(
                -self.decay_rate * iteration)
            if on_progress:
                on_progress(iteration, iterations, history[-1])

        return self._report(history, started, iterations)


class RecurrentCuriosityAgent(CuriosityAgent):
    """Notebook 19."""
    name = "Recurrent curiosity Q-learning"
    recurrent = True


class DuelCuriosityAgent(CuriosityAgent):
    """Notebook 20."""
    name = "Duel curiosity Q-learning"
    duel = True
