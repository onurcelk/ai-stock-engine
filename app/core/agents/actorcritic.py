"""The actor-critic family, ported from agent/14 through agent/17.

Four networks rather than one. The *actor* maps a state to the three action
scores and is the policy actually used for trading; the *critic* scores how
good the actor's output was, and each has a frozen target copy supplying the
bootstrap value. The actor never sees a loss of its own — it is trained by
pushing its output along the critic's gradient, which is the DDPG arrangement.

Same two orthogonal flags as the Q-learning family:

    duel       the hidden layer splits into value and advantage streams
    recurrent  an LSTM over the last four states replaces the dense input

    notebook 14  plain      notebook 16  recurrent
    notebook 15  duel       notebook 17  duel + recurrent

Two indexing bugs in the notebooks are fixed here rather than reproduced, since
neither is a design choice:

* the bootstrap was gated on `replay[0]`'s done-flag for every entry in the
  batch instead of `replay[i]`'s, so one sample decided it for all 32;
* the actor's weights were collected with scope `'actor'`, which prefix-matches
  `actor-target` as well as `actor-original`. TensorFlow returned None
  gradients for the target's variables and the optimiser skipped them, so the
  effect was only wasted work — but the intent is clearly the online actor.
"""

from __future__ import annotations

import random
import time
from collections import deque

import numpy as np

from .base import BaseAgent, EpisodeState, ProgressFn, TrainingReport

ACTIONS = 3


class _Actor:
    def __init__(self, X, logits, hidden=None, last_state=None):
        self.X = X
        self.logits = logits
        self.hidden = hidden
        self.last_state = last_state


class _Critic:
    def __init__(self, X, Y, reward, logits, cost, optimizer, hidden=None):
        self.X = X
        self.Y = Y
        self.REWARD = reward
        self.logits = logits
        self.cost = cost
        self.optimizer = optimizer
        self.hidden = hidden


class ActorCriticAgent(EpisodeState, BaseAgent):
    """Shared skeleton. The registered agents are the subclasses below."""

    name = "Actor-critic"
    duel = False
    recurrent = False

    def __init__(self, close, window_size: int = 30, skip: int = 1,
                 layer_size: int = 256, batch_size: int = 32,
                 learning_rate: float = 0.001, gamma: float = 0.99,
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

        self.actor = self._build_actor(tf, "actor-original")
        self.actor_target = self._build_actor(tf, "actor-target")
        self.critic = self._build_critic(tf, "critic-original", learning_rate)
        self.critic_target = self._build_critic(tf, "critic-target", learning_rate)

        # The actor has no loss. It is trained by pushing its output in the
        # direction the critic says improves the score, which means feeding the
        # critic's gradient w.r.t. its own input back through the actor.
        self.grad_critic = tf.gradients(self.critic.logits, self.critic.Y)
        self.actor_critic_grad = tf.placeholder(tf.float32, (None, ACTIONS))
        actor_weights = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                                          scope="actor-original")
        grad_actor = tf.gradients(self.actor.logits, actor_weights,
                                  -self.actor_critic_grad)
        self.optimizer = tf.train.AdamOptimizer(learning_rate).apply_gradients(
            zip(grad_actor, actor_weights))

        self.session = tf.InteractiveSession()
        self.session.run(tf.global_variables_initializer())

        self._reset_episode()

    # ----------------------------------------------------------------- graph

    def _trunk(self, tf):
        """Input placeholder plus the shared representation both heads read."""
        if self.recurrent:
            X = tf.placeholder(tf.float32, (None, None, self.window_size))
            hidden_in = tf.placeholder(tf.float32, (None, 2 * self.layer_size))
            cell = tf.nn.rnn_cell.LSTMCell(self.layer_size, state_is_tuple=False)
            rnn, last_state = tf.nn.dynamic_rnn(
                inputs=X, cell=cell, dtype=tf.float32, initial_state=hidden_in)
            return X, hidden_in, last_state, rnn[:, -1]
        X = tf.placeholder(tf.float32, (None, self.window_size))
        return X, None, None, tf.layers.dense(X, self.layer_size, activation=tf.nn.relu)

    def _scores(self, tf, feed):
        """Three action scores, duelling or not. No activation — callers add it."""
        if not self.duel:
            return tf.layers.dense(feed, ACTIONS)
        advantage_stream, value_stream = tf.split(feed, 2, 1)
        advantage = tf.layers.dense(advantage_stream, ACTIONS)
        value = tf.layers.dense(value_stream, 1)
        return value + (advantage - tf.reduce_mean(advantage, axis=1, keepdims=True))

    def _build_actor(self, tf, scope: str) -> _Actor:
        with tf.variable_scope(scope):
            X, hidden_in, last_state, feed = self._trunk(tf)
            return _Actor(X, self._scores(tf, feed), hidden_in, last_state)

    def _build_critic(self, tf, scope: str, learning_rate: float) -> _Critic:
        with tf.variable_scope(scope):
            X, hidden_in, _last, feed = self._trunk(tf)
            Y = tf.placeholder(tf.float32, (None, ACTIONS))
            reward = tf.placeholder(tf.float32, (None, 1))
            # The actor's output enters here as Y: the critic scores the pair.
            body = tf.nn.relu(self._scores(tf, feed)) + Y
            body = tf.layers.dense(body, self.layer_size // 2, activation=tf.nn.relu)
            logits = tf.layers.dense(body, 1)
            cost = tf.reduce_mean(tf.square(reward - logits))
            optimizer = tf.train.AdamOptimizer(learning_rate).minimize(cost)
            return _Critic(X, Y, reward, logits, cost, optimizer, hidden_in)

    def _sync_targets(self) -> None:
        tf = self._tf
        for source, destination in (("actor-original", "actor-target"),
                                    ("critic-original", "critic-target")):
            from_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=source)
            to_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=destination)
            for from_var, to_var in zip(from_vars, to_vars):
                self.session.run(to_var.assign(from_var))

    def close_session(self) -> None:
        """Graphs are process-global in TF1; leaking sessions exhausts memory."""
        if getattr(self, "session", None) is not None:
            self.session.close()
            self.session = None

    # ----------------------------------------------------------------- policy

    def _with_hidden(self, net, states, hidden=None) -> dict:
        feed = {net.X: states}
        if self.recurrent:
            feed[net.hidden] = self._hidden if hidden is None else hidden
        return feed

    def act(self, state: np.ndarray, explore: bool = False) -> int:
        flat = self._push(state)

        if explore and self._random.random() < self.epsilon:
            return self._random.randrange(ACTIONS)

        if self.recurrent:
            logits, last_state = self.session.run(
                [self.actor.logits, self.actor.last_state],
                feed_dict=self._with_hidden(self.actor, [self._frames]),
            )
            self._hidden = last_state
            return int(np.argmax(logits[0]))

        logits = self.session.run(self.actor.logits,
                                  feed_dict={self.actor.X: flat[None, :]})
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

        states = np.array([item[0] for item in batch])
        next_states = np.array([item[3] for item in batch])
        hiddens = np.array([item[5] for item in batch]) if self.recurrent else None

        actor_out = self.session.run(
            self.actor.logits, feed_dict=self._with_hidden(self.actor, states, hiddens))
        target_out = self.session.run(
            self.actor_target.logits,
            feed_dict=self._with_hidden(self.actor_target, states, hiddens))

        # Push the actor toward whatever the critic scores higher.
        critic_feed = self._with_hidden(self.critic, states, hiddens)
        critic_feed[self.critic.Y] = actor_out
        gradients = self.session.run(self.grad_critic, feed_dict=critic_feed)[0]

        actor_feed = self._with_hidden(self.actor, states, hiddens)
        actor_feed[self.actor_critic_grad] = gradients
        self.session.run(self.optimizer, feed_dict=actor_feed)

        rewards = np.array([item[2] for item in batch], dtype=float).reshape(-1, 1)
        target_feed = self._with_hidden(self.critic_target, next_states, hiddens)
        target_feed[self.critic_target.Y] = target_out
        bootstrap = self.session.run(self.critic_target.logits, feed_dict=target_feed)
        for index, item in enumerate(batch):
            if not item[4]:  # notebooks read replay[0] here; see module docstring
                rewards[index] += self.gamma * bootstrap[index]

        train_feed = self._with_hidden(self.critic, states, hiddens)
        train_feed[self.critic.Y] = actor_out
        train_feed[self.critic.REWARD] = rewards
        self.session.run([self.critic.cost, self.critic.optimizer], feed_dict=train_feed)

        self._copies += 1
        if self._copies % self.copy_every == 0:
            self._sync_targets()

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

            # Greedy policy return, so the curve means the same thing here as
            # in the other families. See deepq.py for why the traded episode's
            # return is not usable at these epsilon values.
            history.append(self._simulate(initial_money))
            self.epsilon = self.epsilon_min + (1.0 - self.epsilon_min) * np.exp(
                -self.decay_rate * iteration)
            if on_progress:
                on_progress(iteration, iterations, history[-1])

        return self._report(history, started, iterations)


class ActorCriticDuelAgent(ActorCriticAgent):
    """Notebook 15."""
    name = "Actor-critic duel"
    duel = True


class ActorCriticRecurrentAgent(ActorCriticAgent):
    """Notebook 16."""
    name = "Actor-critic recurrent"
    recurrent = True


class ActorCriticDuelRecurrentAgent(ActorCriticAgent):
    """Notebook 17."""
    name = "Actor-critic duel recurrent"
    duel = True
    recurrent = True
