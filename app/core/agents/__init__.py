"""Reinforcement-learning agents, exposed behind one interface.

Each emits a signal series for backtest.run(), so they are charged the same
costs and sized the same way as the rule-based strategies — which is what makes
the numbers on the Trading agents tab comparable to each other and to buy &
hold.

Nineteen agents, but only six implementations: the notebooks' "double duel
recurrent" naming enumerates combinations of a few orthogonal features, so the
families are parameterised rather than copied. See each module's docstring for
which notebook maps to which flags.
"""

from .actorcritic import (
    ActorCriticAgent,
    ActorCriticDuelAgent,
    ActorCriticDuelRecurrentAgent,
    ActorCriticRecurrentAgent,
)
from .base import BaseAgent, EpisodeState, TrainingReport, all_states, window_state
from .curiosity import CuriosityAgent, DuelCuriosityAgent, RecurrentCuriosityAgent
from .deepq import (
    DeepQAgent,
    DoubleDuelQLearningAgent,
    DoubleDuelRecurrentQLearningAgent,
    DoubleQLearningAgent,
    DoubleRecurrentQLearningAgent,
    DuelQLearningAgent,
    DuelRecurrentQLearningAgent,
    RecurrentQLearningAgent,
)
from .evolution import EvolutionStrategyAgent
from .neuroevolution import NeuroEvolutionAgent, NoveltySearchAgent
from .policygradient import PolicyGradientAgent
from .qlearning import QLearningAgent

# Ordered cheapest-to-train first, which is also the order worth trying them
# in: the three gradient-free agents at the top finish in about a second and
# are the ones that actually produced this repo's headline chart.
REGISTRY = {
    "Evolution strategy": EvolutionStrategyAgent,
    "Neuro-evolution": NeuroEvolutionAgent,
    "Neuro-evolution (novelty search)": NoveltySearchAgent,
    "Policy gradient": PolicyGradientAgent,
    "Q-learning": QLearningAgent,
    "Double Q-learning": DoubleQLearningAgent,
    "Duel Q-learning": DuelQLearningAgent,
    "Double duel Q-learning": DoubleDuelQLearningAgent,
    "Recurrent Q-learning": RecurrentQLearningAgent,
    "Double recurrent Q-learning": DoubleRecurrentQLearningAgent,
    "Duel recurrent Q-learning": DuelRecurrentQLearningAgent,
    "Double duel recurrent Q-learning": DoubleDuelRecurrentQLearningAgent,
    "Curiosity Q-learning": CuriosityAgent,
    "Duel curiosity Q-learning": DuelCuriosityAgent,
    "Recurrent curiosity Q-learning": RecurrentCuriosityAgent,
    "Actor-critic": ActorCriticAgent,
    "Actor-critic duel": ActorCriticDuelAgent,
    "Actor-critic recurrent": ActorCriticRecurrentAgent,
    "Actor-critic duel recurrent": ActorCriticDuelRecurrentAgent,
}

# What the iteration slider opens on. Chosen so a run finishes in roughly a
# minute on a few thousand daily bars — the recurrent variants unroll an LSTM
# per bar and cost several times what their feed-forward siblings do, so they
# start lower. These are starting points, not recommendations: the Q-learning
# family in particular is still mostly exploring at these counts (see
# deepq.py), so raise the slider before trusting a policy.
DEFAULT_ITERATIONS = {
    "Evolution strategy": 100,
    "Neuro-evolution": 30,
    "Neuro-evolution (novelty search)": 30,
    "Policy gradient": 50,
    "Q-learning": 20,
    "Double Q-learning": 20,
    "Duel Q-learning": 20,
    "Double duel Q-learning": 20,
    "Recurrent Q-learning": 10,
    "Double recurrent Q-learning": 10,
    "Duel recurrent Q-learning": 10,
    "Double duel recurrent Q-learning": 10,
    "Curiosity Q-learning": 20,
    "Duel curiosity Q-learning": 20,
    "Recurrent curiosity Q-learning": 10,
    "Actor-critic": 15,
    "Actor-critic duel": 15,
    "Actor-critic recurrent": 10,
    "Actor-critic duel recurrent": 10,
}

# The notebook each registered agent came from, for the UI to cite.
SOURCE_NOTEBOOK = {
    "Policy gradient": 4,
    "Q-learning": 5,
    "Evolution strategy": 6,
    "Double Q-learning": 7,
    "Recurrent Q-learning": 8,
    "Double recurrent Q-learning": 9,
    "Duel Q-learning": 10,
    "Double duel Q-learning": 11,
    "Duel recurrent Q-learning": 12,
    "Double duel recurrent Q-learning": 13,
    "Actor-critic": 14,
    "Actor-critic duel": 15,
    "Actor-critic recurrent": 16,
    "Actor-critic duel recurrent": 17,
    "Curiosity Q-learning": 18,
    "Recurrent curiosity Q-learning": 19,
    "Duel curiosity Q-learning": 20,
    "Neuro-evolution": 21,
    "Neuro-evolution (novelty search)": 22,
}

__all__ = [
    "BaseAgent",
    "EpisodeState",
    "TrainingReport",
    "all_states",
    "window_state",
    "EvolutionStrategyAgent",
    "NeuroEvolutionAgent",
    "NoveltySearchAgent",
    "PolicyGradientAgent",
    "QLearningAgent",
    "DeepQAgent",
    "DoubleQLearningAgent",
    "DuelQLearningAgent",
    "DoubleDuelQLearningAgent",
    "RecurrentQLearningAgent",
    "DoubleRecurrentQLearningAgent",
    "DuelRecurrentQLearningAgent",
    "DoubleDuelRecurrentQLearningAgent",
    "CuriosityAgent",
    "DuelCuriosityAgent",
    "RecurrentCuriosityAgent",
    "ActorCriticAgent",
    "ActorCriticDuelAgent",
    "ActorCriticRecurrentAgent",
    "ActorCriticDuelRecurrentAgent",
    "REGISTRY",
    "DEFAULT_ITERATIONS",
    "SOURCE_NOTEBOOK",
]
