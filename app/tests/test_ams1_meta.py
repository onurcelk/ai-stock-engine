"""AMS-1 Stage 2: the meta-signal machinery, before any outcome is scored.

Everything here is feature-side. The properties under test are the ones the
pre-registration makes claims about and that a reader would otherwise have to
take on trust: one family one vote, missing is not HOLD, the ladder's boundaries
are arithmetic, and the point-in-time reconstruction really is point-in-time.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import ams1_config as cfg  # noqa: E402
from alpha import ams1_meta as meta  # noqa: E402
from alpha import ams1_signals as signals  # noqa: E402


RULE = cfg.AGENTS["A_RULE"]
EVO = cfg.AGENTS["E_EVOLUTIONARY"]
PG = cfg.AGENTS["D_POLICY_GRADIENT"]
ALL = list(RULE) + list(PG) + list(EVO)


def stances(**values) -> pd.DataFrame:
    """One row per keyword set; absent agents are NaN, which means *absent*."""
    rows = values.pop("rows", 1)
    index = pd.MultiIndex.from_product(
        [pd.bdate_range("2021-01-04", periods=rows), ["AAA"]],
        names=["cutoff", "symbol"])
    frame = pd.DataFrame(np.nan, index=index, columns=ALL)
    for name, value in values.items():
        frame[name.replace("__", " ")] = value
    return frame


def uniform(rule, pg, evo, rows=1) -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [pd.bdate_range("2021-01-04", periods=rows), ["AAA"]],
        names=["cutoff", "symbol"])
    frame = pd.DataFrame(np.nan, index=index, columns=ALL)
    for name in RULE:
        frame[name] = rule
    for name in PG:
        frame[name] = pg
    for name in EVO:
        frame[name] = evo
    return frame


# ---------------------------------------------------------------------------
# One family, one vote
# ---------------------------------------------------------------------------

class TestFamilyVotes:
    def test_a_families_agents_collapse_to_one_vote(self):
        votes = meta.family_votes(uniform(1, -1, 1))
        assert list(votes.columns) == list(cfg.AGENTS)
        assert votes.iloc[0]["A_RULE"] == 1.0
        assert votes.iloc[0]["D_POLICY_GRADIENT"] == -1.0
        assert votes.iloc[0]["E_EVOLUTIONARY"] == 1.0

    def test_a_three_agent_family_cannot_outvote_a_one_agent_family(self):
        """The whole point of M2/M3: E has three implementations, D has one."""
        frame = uniform(0, -1, 1)
        votes = meta.family_votes(frame)
        signals_frame = meta.meta_signals(frame, votes)
        # raw: 3 evolutionary BUY vs 1 policy-gradient SELL -> net positive
        assert signals_frame.iloc[0]["M1_raw_net_vote"] > 0
        # family: one BUY, one SELL, one flat -> net exactly zero
        assert signals_frame.iloc[0]["M3_family_net_vote"] == 0.0

    def test_an_internally_split_family_abstains(self):
        frame = uniform(0, 0, 0)
        frame[EVO[0]] = 1.0
        frame[EVO[1]] = -1.0
        frame[EVO[2]] = 0.0
        votes = meta.family_votes(frame)
        assert votes.iloc[0]["E_EVOLUTIONARY"] == 0.0

    def test_the_vote_is_the_sign_of_the_mean_not_a_majority_of_signs(self):
        frame = uniform(0, 0, 0)
        frame[EVO[0]] = 1.0
        frame[EVO[1]] = 0.0
        frame[EVO[2]] = 0.0
        assert meta.family_votes(frame).iloc[0]["E_EVOLUTIONARY"] == 1.0

    def test_a_family_with_no_available_agent_is_absent_not_flat(self):
        frame = uniform(1, 1, 1)
        for name in EVO:
            frame[name] = np.nan
        votes = meta.family_votes(frame)
        assert pd.isna(votes.iloc[0]["E_EVOLUTIONARY"])

    def test_missing_is_never_turned_into_hold(self):
        frame = uniform(1, 1, 1)
        frame[EVO[0]] = np.nan
        votes = meta.family_votes(frame)
        # the family still speaks from its two remaining agents
        assert votes.iloc[0]["E_EVOLUTIONARY"] == 1.0
        # and a row with a whole family absent gets no consensus state at all
        gone = uniform(1, 1, 1)
        for name in EVO:
            gone[name] = np.nan
        out = meta.meta_signals(gone, meta.family_votes(gone))
        assert pd.isna(out.iloc[0]["M3_family_net_vote"])


# ---------------------------------------------------------------------------
# The meta-signals
# ---------------------------------------------------------------------------

class TestMetaSignals:
    def test_unanimity_saturates_the_agreement_measures(self):
        out = meta.meta_signals(uniform(1, 1, 1), meta.family_votes(uniform(1, 1, 1)))
        row = out.iloc[0]
        assert row["M2_family_buy_fraction"] == 1.0
        assert row["M3_family_net_vote"] == 1.0
        assert row["M4_agreement"] == 1.0
        assert row["M6_disagreement"] == 0.0

    def test_maximum_disagreement_is_one_family_per_state(self):
        frame = uniform(1, -1, 0)
        out = meta.meta_signals(frame, meta.family_votes(frame))
        assert out.iloc[0]["M6_disagreement"] == pytest.approx(1.0)
        assert out.iloc[0]["M3_family_net_vote"] == 0.0

    def test_raw_and_family_signals_can_disagree_in_sign(self):
        """The study exists for exactly this case."""
        frame = uniform(0, -1, 1)
        out = meta.meta_signals(frame, meta.family_votes(frame))
        assert out.iloc[0]["M1_raw_net_vote"] > 0
        assert out.iloc[0]["M3_family_net_vote"] == 0.0

    def test_m5_collapses_to_m3_when_weights_are_equal(self):
        frame = uniform(1, 1, -1)
        votes = meta.family_votes(frame)
        out = meta.meta_signals(frame, votes,
                                weights={f: 1.0 for f in cfg.FAMILIES})
        assert out.iloc[0]["M5_diversity_weighted"] == pytest.approx(
            out.iloc[0]["M3_family_net_vote"])

    def test_entropy_is_bounded(self):
        for combination in ((1, 1, 1), (1, -1, 0), (1, 1, -1), (0, 0, 0)):
            frame = uniform(*combination)
            value = meta.meta_signals(frame, meta.family_votes(frame)
                                      ).iloc[0]["M6_disagreement"]
            assert 0.0 <= value <= 1.0 + 1e-9

    def test_probabilities_of_the_mapped_signal_stay_in_the_unit_interval(self):
        for value in (-1.0, -0.5, 0.0, 0.5, 1.0):
            got = meta.to_unit(pd.Series([value])).iloc[0]
            assert 0.0 <= got <= 1.0


# ---------------------------------------------------------------------------
# The ladder
# ---------------------------------------------------------------------------

class TestLadder:
    def test_the_five_states_are_ordered(self):
        got = meta.ladder_state(pd.Series([-1.0, -1 / 3, 0.0, 1 / 3, 1.0]))
        assert list(got) == list(cfg.LADDER)
        assert got.ordered

    def test_unanimity_is_the_only_route_to_an_extreme_state(self):
        got = meta.ladder_state(pd.Series([-1.0, -2 / 3, 2 / 3, 1.0]))
        assert list(got) == ["strong bearish", "moderate bearish",
                             "moderate bullish", "strong bullish"]

    def test_exactly_zero_is_mixed(self):
        assert meta.ladder_state(pd.Series([0.0]))[0] == "mixed"

    def test_an_absent_net_vote_gets_no_state(self):
        assert pd.isna(meta.ladder_state(pd.Series([np.nan]))[0])

    def test_the_boundaries_are_the_frozen_constants(self):
        assert cfg.STRONG_THRESHOLD == 1.0 and cfg.MIXED_THRESHOLD == 0.0
        assert cfg.LADDER == ("strong bearish", "moderate bearish", "mixed",
                              "moderate bullish", "strong bullish")

    def test_the_raw_ladder_uses_the_same_states(self):
        got = meta.raw_ladder_state(pd.Series([-1.0, -0.2, 0.0, 0.2, 1.0]))
        assert list(got) == list(cfg.LADDER)


# ---------------------------------------------------------------------------
# The point-in-time reconstruction
# ---------------------------------------------------------------------------

class DummyAgent:
    """A policy whose action is decided by the training data it was given.

    If the reconstruction ever hands it data after the refit boundary, the
    action it emits changes — which is what the tests below detect.
    """

    def __init__(self, close, seed=None, window_size=30, skip=1):
        self.close = close
        self.trend = close.to_numpy(dtype=float)
        self.window_size = window_size
        self.skip = skip
        self.trained_max = None

    def train(self, iterations):
        self.trained_max = float(self.trend.max())

    def act(self, state, explore=False):
        from app.core.agents import base
        return base.BUY if self.trained_max < 1_000 else base.SELL


class TestPitReconstruction:
    def test_training_never_sees_a_bar_at_or_after_its_boundary(self, monkeypatch):
        index = pd.bdate_range("2016-01-04", periods=1200)
        close = pd.Series(np.linspace(100, 200, 1200), index=index)
        boundaries = [index[600], index[900]]
        seen = []

        class Recorder(DummyAgent):
            def train(self, iterations):
                seen.append(self.close.index.max())
                super().train(iterations)

        signals.pit_agent_stance(close, Recorder, 1, boundaries, train_bars=200)
        assert seen[0] < boundaries[0]
        assert seen[1] < boundaries[1]

    def test_the_training_window_is_the_frozen_length(self):
        index = pd.bdate_range("2016-01-04", periods=1200)
        close = pd.Series(np.linspace(100, 200, 1200), index=index)
        lengths = []

        class Recorder(DummyAgent):
            def train(self, iterations):
                lengths.append(len(self.close))
                super().train(iterations)

        signals.pit_agent_stance(close, Recorder, 1, [index[600]], train_bars=200)
        assert lengths == [200]

    def test_bars_before_the_first_policy_are_absent_not_hold(self):
        index = pd.bdate_range("2016-01-04", periods=1200)
        close = pd.Series(np.linspace(100, 200, 1200), index=index)
        got = signals.pit_agent_stance(close, DummyAgent, 1, [index[600]],
                                       train_bars=200)
        assert got.iloc[:600].isna().all()
        assert got.iloc[600:].notna().all()

    def test_a_boundary_without_enough_history_is_skipped(self):
        index = pd.bdate_range("2016-01-04", periods=300)
        close = pd.Series(np.linspace(100, 200, 300), index=index)
        got = signals.pit_agent_stance(close, DummyAgent, 1, [index[50]],
                                       train_bars=200)
        assert got.isna().all()

    def test_rewriting_the_future_cannot_move_a_past_stance(self):
        """The guarantee the whole reconstruction exists to provide."""
        index = pd.bdate_range("2016-01-04", periods=1200)
        close = pd.Series(np.linspace(100, 200, 1200), index=index)
        bent = close.copy()
        bent.iloc[900:] = bent.iloc[900:] * 9.0        # push the max over 1,000

        boundaries = [index[600], index[900]]
        before = signals.pit_agent_stance(close, DummyAgent, 1, boundaries,
                                          train_bars=200)
        after = signals.pit_agent_stance(bent, DummyAgent, 1, boundaries,
                                         train_bars=200)
        assert before.iloc[:900].equals(after.iloc[:900])

    def test_the_frozen_roster_is_the_audited_one(self):
        assert signals.PIT_FAMILIES == ("A_RULE", "D_POLICY_GRADIENT",
                                        "E_EVOLUTIONARY")
        assert set(signals.PIT_FAMILIES) == set(cfg.FAMILIES)
        assert signals.TRAIN_BARS == 500

    def test_the_symbol_sample_is_deterministic(self):
        index = pd.MultiIndex.from_product(
            [pd.bdate_range("2016-01-04", periods=200),
             [f"S{i:03d}" for i in range(300)]], names=["cutoff", "symbol"])
        first = signals.sample_symbols(index)
        second = signals.sample_symbols(index)
        assert first == second
        assert len(first) == signals.SAMPLE_SIZE

    def test_refit_boundaries_are_one_per_calendar_year(self):
        cutoffs = list(pd.bdate_range("2016-01-04", "2019-12-31", freq="5B"))
        got = signals.refit_boundaries(cutoffs)
        assert [b.year for b in got] == [2016, 2017, 2018, 2019]


class TestFrozenConfig:
    def test_the_horizon_is_inherited_not_redefined(self):
        from alpha import dataset
        assert cfg.HORIZON == dataset.HORIZON == 5
        assert cfg.EMBARGO == dataset.EMBARGO

    def test_the_target_is_the_absolute_return(self):
        assert cfg.TARGET_RETURN == "asset_return"

    def test_the_gates_are_numeric_and_frozen(self):
        assert cfg.MIN_LOGLOSS_GAIN == 0.001
        assert cfg.MIN_LADDER_SPEARMAN == 0.90
        assert cfg.MIN_SYMBOLS == 100 and cfg.MIN_CUTOFFS == 100
        assert cfg.SUB_50 == 0.50

    def test_the_block_length_is_the_programmes_own(self):
        from alpha import stats
        assert cfg.BLOCK_LENGTH_CUTOFFS == stats.BLOCK_LENGTH
