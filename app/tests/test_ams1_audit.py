"""AMS-1 Stage 1: the agent audit's machinery.

The audit's verdicts are measurements and live in `alpha/out/ams1_agent_audit.json`.
What is testable here is the machinery that produces them: that the taxonomy is
deterministic and total, that signal normalisation means what it claims, that the
redundancy statistics behave, and — the load-bearing one — that the
rewrite-the-future probe actually catches a generator which reads the future.

Hermetic: no network, no cache, no agent training, no forward return.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alpha import agents_audit as audit  # noqa: E402


def series(*values: float) -> pd.Series:
    return pd.Series(list(values), dtype=float,
                     index=pd.bdate_range("2021-01-04", periods=len(values)))


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

class TestTaxonomy:
    def test_every_implemented_agent_has_exactly_one_family(self):
        specs = audit.inventory()
        assert len(specs) == 22
        for spec in specs:
            assert spec.family in audit.FAMILIES
            assert audit.FAMILY_OF[spec.name] == spec.family

    def test_the_map_covers_the_live_registry_exactly(self):
        """A new agent added to REGISTRY must fail this until it is classified."""
        from app.core import agents as registry
        rl = {name for name, family in audit.FAMILY_OF.items() if family != "A_RULE"}
        assert rl == set(registry.REGISTRY)

    def test_every_deepq_flag_combination_lands_in_the_value_family(self):
        """Double/duel/recurrent are flags on one implementation, not designs."""
        for name in ("Q-learning", "Double Q-learning", "Duel Q-learning",
                     "Double duel Q-learning", "Recurrent Q-learning",
                     "Double recurrent Q-learning", "Duel recurrent Q-learning",
                     "Double duel recurrent Q-learning"):
            assert audit.FAMILY_OF[name] == "B_VALUE_RL"

    def test_no_family_is_empty(self):
        used = set(audit.FAMILY_OF.values())
        assert used == set(audit.FAMILIES)

    def test_the_mapping_is_deterministic(self):
        assert audit.inventory()[0].name == audit.inventory()[0].name
        assert [s.family for s in audit.inventory()] == \
               [s.family for s in audit.inventory()]

    def test_unimplemented_notebooks_are_recorded_not_classified(self):
        """A census, not a selection — but they cannot receive a family vote."""
        assert audit.UNIMPLEMENTED
        for name in audit.UNIMPLEMENTED:
            assert name not in audit.FAMILY_OF


# ---------------------------------------------------------------------------
# Signal normalisation
# ---------------------------------------------------------------------------

class TestStance:
    def test_an_event_series_becomes_a_standing_position(self):
        got = audit.stance(series(0, 1, 0, 0, -1, 0, 0))
        assert list(got) == [0, 1, 1, 1, -1, -1, -1]

    def test_it_is_causal(self):
        """A later event cannot change an earlier stance."""
        base = series(0, 1, 0, 0, 0, 0)
        changed = series(0, 1, 0, 0, -1, 0)
        assert list(audit.stance(base)[:4]) == list(audit.stance(changed)[:4])

    def test_before_the_first_signal_the_agent_is_flat_not_missing(self):
        got = audit.stance(series(0, 0, 1, 0))
        assert list(got) == [0, 0, 1, 1]
        assert got.notna().all()

    def test_values_stay_in_the_ternary_alphabet(self):
        got = audit.stance(series(0, 1, -1, 1, 0))
        assert set(np.unique(got)) <= {-1.0, 0.0, 1.0}


# ---------------------------------------------------------------------------
# The PIT probe — the test that the leak detector detects leaks
# ---------------------------------------------------------------------------

class TestRewriteTheFuture:
    def test_a_causal_generator_is_unchanged(self):
        close = series(*np.linspace(100, 120, 40))
        got = audit.past_signals_moved(
            lambda c: np.sign(c.diff()).fillna(0.0), close)
        assert got["moved"] == 0 and got["causal"]

    def test_a_generator_that_reads_the_whole_series_is_caught(self):
        """Centring on the full-series mean is the simplest full-history fit."""
        close = series(*np.linspace(100, 120, 40))
        got = audit.past_signals_moved(lambda c: np.sign(c - c.mean()), close)
        assert got["moved"] > 0 and not got["causal"]

    def test_only_the_second_half_of_the_series_is_rewritten(self):
        close = series(*np.linspace(100, 120, 40))
        bent = audit.rewrite_the_future(close)
        half = len(close) // 2
        assert (bent.iloc[:half].to_numpy() == close.iloc[:half].to_numpy()).all()
        assert (bent.iloc[half:].to_numpy() != close.iloc[half:].to_numpy()).any()

    def test_the_rule_agents_are_causal_on_a_real_shaped_series(self):
        rng = np.random.default_rng(0)
        close = series(*(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))))
        for name in ("Turtle", "Moving average crossover", "Signal rolling"):
            got = audit.past_signals_moved(
                lambda c, n=name: audit.rule_signals(c)[n], close)
            assert got["causal"], f"{name} moved {got['moved']} past signals"


# ---------------------------------------------------------------------------
# Redundancy statistics
# ---------------------------------------------------------------------------

class TestAgreement:
    def test_identical_signals_agree_everywhere(self):
        left = series(1, 1, -1, 0, 1)
        got = audit.agreement(left, left.copy())
        assert got["exact"] == 1.0
        assert got["pearson"] == pytest.approx(1.0)

    def test_opposite_signals_disagree_everywhere(self):
        left = series(1, 1, -1, -1)
        got = audit.agreement(left, -left)
        assert got["exact"] == 0.0
        assert got["pearson"] == pytest.approx(-1.0)

    def test_directional_agreement_ignores_the_bars_where_one_is_flat(self):
        left = series(1, 1, 0, -1)
        right = series(1, 0, 0, -1)
        got = audit.agreement(left, right)
        assert got["both_active_n"] == 2
        assert got["directional_when_both_active"] == 1.0
        assert got["exact"] < 1.0

    def test_an_empty_overlap_is_reported_not_crashed(self):
        left = pd.Series(dtype=float)
        assert audit.agreement(left, left)["n"] == 0

    def test_a_constant_signal_has_no_correlation_to_report(self):
        got = audit.agreement(series(1, 1, 1, 1), series(1, -1, 1, -1))
        assert got["pearson"] is None


class TestMutualInformation:
    def test_independent_signals_carry_almost_no_information(self):
        rng = np.random.default_rng(7)
        n = 4000
        left = pd.Series(rng.choice([-1.0, 0.0, 1.0], n))
        right = pd.Series(rng.choice([-1.0, 0.0, 1.0], n))
        assert audit.mutual_information(left, right) < 0.01

    def test_a_deterministic_relabelling_carries_full_information(self):
        rng = np.random.default_rng(7)
        left = pd.Series(rng.choice([-1.0, 0.0, 1.0], 3000))
        assert audit.mutual_information(left, -left) == pytest.approx(
            audit.mutual_information(left, left), rel=1e-6)

    def test_it_catches_dependence_that_sign_correlation_misses(self):
        """Two agents can be uncorrelated in sign and still dependent in *when*
        they are flat. That is why MI is reported next to Pearson."""
        rng = np.random.default_rng(3)
        flat = rng.random(4000) < 0.5
        left = pd.Series(np.where(flat, 0.0, rng.choice([-1.0, 1.0], 4000)))
        right = pd.Series(np.where(flat, 0.0, rng.choice([-1.0, 1.0], 4000)))
        assert abs(left.corr(right)) < 0.15
        assert audit.mutual_information(left, right) > 0.4


class TestNearClones:
    def test_a_clone_pair_is_flagged(self):
        signals = {"a": series(1, 1, -1, 1, -1), "b": series(1, 1, -1, 1, -1),
                   "c": series(-1, 1, 1, -1, 1)}
        matrix = audit.redundancy_matrix(signals)
        clones = audit.near_clones(matrix, threshold=0.90)
        assert set(zip(clones["left"], clones["right"])) == {("a", "b")}

    def test_effective_opinions_merges_clones_but_keeps_distinct_agents(self):
        signals = {"a": series(1, 1, -1, 1, -1), "b": series(1, 1, -1, 1, -1),
                   "c": series(-1, 1, 1, -1, 1)}
        matrix = audit.redundancy_matrix(signals)
        got = audit.effective_opinions(matrix, list(signals), threshold=0.90)
        assert got["nominal_agents"] == 3
        assert got["effective_opinions"] == 2

    def test_clustering_is_transitive(self):
        """a~b and b~c must not leave three clusters."""
        signals = {"a": series(1, 1, -1, 1), "b": series(1, 1, -1, 1),
                   "c": series(1, 1, -1, 1)}
        matrix = audit.redundancy_matrix(signals)
        got = audit.effective_opinions(matrix, list(signals), threshold=0.90)
        assert got["effective_opinions"] == 1

    def test_the_taxonomy_does_not_move_with_the_diagnostic(self):
        """Redundancy is a diagnostic; architecture decides the family."""
        before = dict(audit.FAMILY_OF)
        signals = {"Turtle": series(1, 1, 1), "Signal rolling": series(1, 1, 1)}
        audit.effective_opinions(audit.redundancy_matrix(signals),
                                 list(signals), threshold=0.5)
        assert audit.FAMILY_OF == before


class TestOutcomeGuard:
    def test_an_outcome_column_cannot_reach_the_audit(self):
        frame = pd.DataFrame({"Turtle": [1.0], "asset_return": [0.02]})
        with pytest.raises(RuntimeError):
            audit.assert_no_outcome_columns(frame)

    def test_a_signal_only_frame_passes(self):
        audit.assert_no_outcome_columns(pd.DataFrame({"Turtle": [1.0]}))


class TestFrozenRuleParameters:
    def test_the_windows_are_absolute_not_scaled_to_the_series(self):
        """The app scales them to whatever is on screen; a study cannot."""
        short = audit.rule_signals(series(*np.linspace(100, 110, 80)))
        long = audit.rule_signals(series(*np.linspace(100, 110, 400)))
        assert set(short) == set(long)
        assert audit.TURTLE_CHANNEL == 26 and audit.MA_SHORT == 6
        assert audit.MA_LONG == 13 and audit.ROLLING_DELAY == 4

    def test_the_turtle_keeps_the_notebooks_direction(self):
        assert audit.TURTLE_FOLLOW_BREAKOUT is False
