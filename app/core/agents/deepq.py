"""The deep Q-learning family, ported from agent/7 through agent/13.

Seven notebooks, but not seven algorithms: they are the combinations of three
independent modifications to one DQN skeleton, so they are expressed here as
three flags rather than seven copies of the same file.

    double     a second, frozen copy of the network supplies the bootstrap
               target, which stops the estimate chasing its own tail
    duel       the hidden layer is split into a state-value stream and an
               advantage stream, recombined as V + (A - mean A)
    recurrent  an LSTM over the last four state vectors replaces the dense
               input layer, and its cell state is threaded across timesteps

    notebook 7  double            notebook 11  double + duel
    notebook 8  recurrent         notebook 12  duel + recurrent
    notebook 9  double+recurrent  notebook 13  double + duel + recurrent
    notebook 10 duel

Notebook 5 is the plain case and is already ported in qlearning.py, which keeps
that notebook's own hyperparameters (plain SGD, most-recent-transition replay).
Everything here follows notebooks 7-13 instead: Adam, and a random sample from
replay memory.

One inherited quirk worth knowing before reading the numbers: epsilon is reset
to nearly 1.0 after the first iteration and then decays as
`min + (1 - min) * exp(-0.005 * i)`, which is calibrated for the couple of
hundred iterations the notebooks ran. Over a short run the agent is still
mostly exploring, so the policy `signals()` replays is trained largely from
random experience. Raise the iteration count for a policy worth trusting.
"""

from __future__ import annotations

import random
import time
from collections import deque

import numpy as np

from .base import FRAMES, BaseAgent, EpisodeState, ProgressFn, TrainingReport

ACTIONS = 3


class _Net:
    """The tensors making up one Q-network."""

    def __init__(self, X, Y, logits, cost, optimizer, hidden=None, last_state=None):
        self.X = X
        self.Y = Y
        self.logits = logits
        self.cost = cost
        self.optimizer = optimizer
        self.hidden = hidden
        self.last_state = last_state


class DeepQAgent(EpisodeState, BaseAgent):
    """Shared skeleton. The registered agents are the subclasses below."""

    name = "Deep Q-learning"
    double = False
    duel = False
    recurrent = False

    def __init__(self, close, window_size: int = 30, skip: int = 1,
                 layer_size: int = 256, batch_size: int = 32,
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

        self.online = self._build(tf, "online", learning_rate)
        # Without `double` the bootstrap target comes from the network being
        # trained, which is exactly what plain DQN does.
        self.target = self._build(tf, "target", learning_rate) if self.double else self.online

        self.session = tf.InteractiveSession()
        self.session.run(tf.global_variables_initializer())

        self._frames = np.zeros((FRAMES, self.window_size))
        self._flat = np.zeros(self.window_size)
        self._hidden = np.zeros((1, 2 * self.layer_size))

    # ----------------------------------------------------------------- graph

    def _build(self, tf, scope: str, learning_rate: float) -> _Net:
        with tf.variable_scope(scope):
            hidden_in = last_state = None
            if self.recurrent:
                X = tf.placeholder(tf.float32, (None, None, self.window_size))
                hidden_in = tf.placeholder(tf.float32, (None, 2 * self.layer_size))
                cell = tf.nn.rnn_cell.LSTMCell(self.layer_size, state_is_tuple=False)
                rnn, last_state = tf.nn.dynamic_rnn(
                    inputs=X, cell=cell, dtype=tf.float32, initial_state=hidden_in)
                feed = rnn[:, -1]
            else:
                X = tf.placeholder(tf.float32, (None, self.window_size))
                feed = tf.layers.dense(X, self.layer_size, activation=tf.nn.relu)

            if self.duel:
                advantage_stream, value_stream = tf.split(feed, 2, 1)
                advantage = tf.layers.dense(advantage_stream, ACTIONS)
                value = tf.layers.dense(value_stream, 1)
                # Subtracting the mean advantage is what makes the split
                # identifiable; without it V and A can drift by any constant.
                logits = value + (advantage - tf.reduce_mean(advantage, axis=1,
                                                             keepdims=True))
            else:
                logits = tf.layers.dense(feed, ACTIONS)

            Y = tf.placeholder(tf.float32, (None, ACTIONS))
            cost = tf.reduce_mean(tf.square(Y - logits))
            optimizer = tf.train.AdamOptimizer(learning_rate).minimize(cost)

        return _Net(X, Y, logits, cost, optimizer, hidden_in, last_state)

    def _sync_target(self) -> None:
        """Copy the trained weights onto the frozen target network."""
        tf = self._tf
        source = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope="online")
        destination = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope="target")
        for from_var, to_var in zip(source, destination):
            self.session.run(to_var.assign(from_var))

    def close_session(self) -> None:
        """Graphs are process-global in TF1; leaking sessions exhausts memory."""
        if getattr(self, "session", None) is not None:
            self.session.close()
            self.session = None

    # ----------------------------------------------------------------- policy

    def _feed(self, net: _Net, states: np.ndarray, hidden: np.ndarray | None = None) -> dict:
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
                [self.online.logits, self.online.last_state],
                feed_dict=self._feed(self.online, [self._frames]),
            )
            self._hidden = last_state
            return int(np.argmax(logits[0]))

        logits = self.session.run(self.online.logits,
                                  feed_dict={self.online.X: flat[None, :]})
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

        q_current = self.session.run(
            self.online.logits, feed_dict=self._feed(self.online, states, hiddens))
        q_next = self.session.run(
            self.target.logits, feed_dict=self._feed(self.target, next_states, hiddens))

        targets = q_current.copy()
        for index, (_state, action, reward, _next, dead, *_rest) in enumerate(batch):
            targets[index, action] = reward
            if not dead:
                targets[index, action] += self.gamma * np.amax(q_next[index])

        feed = self._feed(self.online, states, hiddens)
        feed[self.online.Y] = targets
        self.session.run([self.online.cost, self.online.optimizer], feed_dict=feed)

        if self.double:
            self._copies += 1
            if self._copies % self.copy_every == 0:
                self._sync_target()

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
                # Captured after act() so the stack already holds this bar,
                # matching what the notebooks memorise.
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

            # Score the *greedy* policy, not the episode just traded. At the
            # notebooks' epsilon the episode is almost entirely random, so its
            # return is noise — and identical across variants, since they all
            # draw the same seeded random actions. This is also what the
            # evolution agents report, so the learning curve means one thing
            # everywhere. The training itself is untouched.
            history.append(self._simulate(initial_money))
            # The notebooks' schedule: this jumps epsilon back to ~1.0 after
            # the first pass, then anneals slowly. See the module docstring.
            self.epsilon = self.epsilon_min + (1.0 - self.epsilon_min) * np.exp(
                -self.decay_rate * iteration)
            if on_progress:
                on_progress(iteration, iterations, history[-1])

        return self._report(history, started, iterations)


class DoubleQLearningAgent(DeepQAgent):
    """Notebook 7."""
    name = "Double Q-learning"
    double = True


class RecurrentQLearningAgent(DeepQAgent):
    """Notebook 8."""
    name = "Recurrent Q-learning"
    recurrent = True


class DoubleRecurrentQLearningAgent(DeepQAgent):
    """Notebook 9."""
    name = "Double recurrent Q-learning"
    double = True
    recurrent = True


class DuelQLearningAgent(DeepQAgent):
    """Notebook 10."""
    name = "Duel Q-learning"
    duel = True


class DoubleDuelQLearningAgent(DeepQAgent):
    """Notebook 11."""
    name = "Double duel Q-learning"
    double = True
    duel = True


class DuelRecurrentQLearningAgent(DeepQAgent):
    """Notebook 12."""
    name = "Duel recurrent Q-learning"
    duel = True
    recurrent = True


class DoubleDuelRecurrentQLearningAgent(DeepQAgent):
    """Notebook 13."""
    name = "Double duel recurrent Q-learning"
    double = True
    duel = True
    recurrent = True
