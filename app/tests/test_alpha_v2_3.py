"""Tests for V2.3 — the adjustment must not re-encode its own base.

`test_alpha_v2_2.py` tests the carrier: whether a factor survives being routed
through a learner. This file tests the one thing V2.2 could not have known to
measure — **how much of a bounded adjustment is just a copy of the base it
adjusts** — and the two arms built around that measurement.

The load-bearing tests are:

* `test_the_collinearity_diagnostic_recovers_a_known_rho` — the measurement itself,
  against synthetic data whose answer is known by construction;
* `test_h1b_rejects_a_v2_2_b_shaped_carrier_and_admits_a_decoupled_one` — the new
  eligibility ceiling, checked at V2.2-B's measured 0.9923 and below it;
* `test_v2_3_a_trains_on_exactly_v2_2_bs_target` — what makes the whole study a
  controlled experiment. If A's target drifted from V2.2-B's by anything, the
  A-minus-V2.2-B delta would no longer be "one deleted column";
* `test_the_noise_control_destroys_ic_rather_than_creating_it` — the direct evidence
  that a bounded blend cannot manufacture IC through rank mechanics.

Two kinds of test, as in the sibling files: hermetic ones that build what they
need, and ones against the real artefacts that skip when those are absent.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from alpha import (build_panel, carrier, examset, ladder, ladder_v2_2,  # noqa: E402
                  ladder_v2_3, models, protocol, stats, targets)

PANEL_PATH = build_panel.PANEL_PATH
DEV_PATH = ladder_v2_3.JSON_PATH
DEV_PICKLE = ladder_v2_3.PICKLE_PATH

V2_1_EXAM_DIGEST = "b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0"
V2_2_B_MEAN_IC = 0.02356            # the frozen V2.2 record; must not move
V2_2_B_RHO = 0.9923                 # the measurement V2.3 exists to act on

needs_panel = pytest.mark.skipif(
    not PANEL_PATH.exists(), reason="alpha/out/panel.pkl has not been built")
needs_development = pytest.mark.skipif(
    not DEV_PATH.exists(), reason="alpha/out/v2_3_development.json has not been written")
needs_exam_set = pytest.mark.skipif(
    not examset.PATH.exists(), reason="v2_1_exam_set.json is not frozen on this machine")
needs_v2_2 = pytest.mark.skipif(
    not ladder_v2_2.JSON_PATH.exists(), reason="the V2.2 record is not on this machine")


# ----------------------------------------------------------------------
# A synthetic panel with a controllable collinearity
# ----------------------------------------------------------------------

def _panel(n_cutoffs: int = 40, n_symbols: int = 80, seed: int = 0) -> pd.DataFrame:
    """A small panel with a base, a second stock-level rank, and an outcome."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_cutoffs):
        u = rng.permutation(np.linspace(0.0, 1.0, n_symbols))
        v = rng.permutation(np.linspace(0.0, 1.0, n_symbols))
        rows.append(pd.DataFrame({
            "cutoff": pd.Timestamp("2016-01-04") + pd.Timedelta(days=7 * i),
            "symbol": [f"S{j:03d}" for j in range(n_symbols)],
            "ret_12_1": u,
            "ret_20d": v,
            "ret_5d": rng.normal(size=n_symbols),
            "alpha_5d": 0.01 * u + 0.004 * rng.normal(size=n_symbols),
        }))
    frame = pd.concat(rows, ignore_index=True).set_index(["cutoff", "symbol"]).sort_index()
    frame["target_train"] = frame.groupby(level=0)["alpha_5d"].transform(targets.winsorise)
    frame["target_rank"] = frame.groupby(level=0)["alpha_5d"].transform(
        targets.cross_sectional_rank)
    frame, _ = carrier.add_rank_columns(frame, ("ret_12_1", "ret_20d"))
    return frame


def _mean_ic(frame: pd.DataFrame, score: pd.Series) -> float:
    block = frame[["alpha_5d"]].copy()
    block["prediction"] = score
    return float(stats.ic_by_cutoff(block, "prediction", "alpha_5d").dropna().mean())


# ---------------------------------------------- the collinearity measurement


def test_the_collinearity_diagnostic_recovers_a_known_rho():
    """Three cases whose answers are known by construction.

    An adjustment that *is* the base ranks with it (rho = +1). Its negation ranks
    against it (rho = -1) — which is V2.2-B's case, at -0.9923. An independent draw
    ranks with neither.
    """
    frame = _panel()
    base = frame["z__ret_12_1"]

    same = carrier.collinearity(base, base, "same", 0.5)
    assert same.mean_abs == pytest.approx(1.0)
    assert same.summary()["mean_signed_rho"] == pytest.approx(1.0)
    # At rho = 1 the adjustment carries no new information, so the effective
    # lambda is zero however large the nominal one is.
    assert same.effective_lambda == pytest.approx(0.0)

    opposite = carrier.collinearity(-base, base, "opposite", 0.5)
    assert opposite.mean_abs == pytest.approx(1.0)
    assert opposite.summary()["mean_signed_rho"] == pytest.approx(-1.0)
    assert opposite.summary()["share_negative"] == pytest.approx(1.0)

    rng = np.random.default_rng(3)
    independent = carrier.collinearity(
        pd.Series(rng.normal(size=len(frame)), index=frame.index), base, "iid", 0.5)
    assert abs(independent.mean_abs) < 0.15
    # And an uncorrelated adjustment gets essentially all of its nominal authority.
    assert independent.effective_lambda > 0.49


def test_the_ceiling_is_on_the_mean_of_the_absolute_value_not_the_absolute_mean():
    """An arm at +0.95 half the time and -0.95 the other half is maximally collinear.

    `|mean rho|` would score it 0 and wave it through. `mean |rho|` scores it 0.95
    and rejects it. The pre-registration specifies the second for exactly this
    reason, and the signed mean is reported beside it rather than instead of it.
    """
    index = pd.date_range("2016-01-08", periods=100, freq="W")
    alternating = pd.Series(np.where(np.arange(100) % 2 == 0, 0.95, -0.95), index=index)
    coll = carrier.Collinearity("alternating", alternating, 0.5)

    assert abs(alternating.mean()) < 1e-12          # the absolute mean is ~0
    assert coll.mean_abs == pytest.approx(0.95)     # the mean absolute is 0.95
    assert not ladder_v2_3.h1b(coll)["passed"]
    assert ladder_v2_3.h1b(coll)["signed_mean"] == pytest.approx(0.0, abs=1e-4)


def test_the_effective_lambda_is_the_share_of_authority_that_is_new():
    """`lambda * sqrt(1 - rho^2)` — the quantity V2.2's report did not have.

    V2.2-B advertised lambda = 0.50 and, at rho = 0.9923, delivered about 0.062
    rank units of new authority. That arithmetic is the whole justification for
    H1b's threshold, so it gets a test rather than a comment.
    """
    index = pd.date_range("2016-01-08", periods=50, freq="W")
    for rho, expected in ((0.9923, 0.062), (0.90, 0.218), (0.0, 0.500)):
        coll = carrier.Collinearity("x", pd.Series(-rho, index=index), 0.50)
        assert coll.effective_lambda == pytest.approx(expected, abs=0.001)

    # The ceiling is where the arm still delivers >= 44% of what it advertises.
    at_ceiling = carrier.Collinearity("c", pd.Series(0.90, index=index), 0.50)
    assert at_ceiling.summary()["effective_share_of_nominal"] == pytest.approx(0.436, abs=0.005)


def test_h1b_rejects_a_v2_2_b_shaped_carrier_and_admits_a_decoupled_one():
    """§5's new eligibility condition, checked at the number that motivated it."""
    assert ladder_v2_3.H1B_CEILING == 0.90
    index = pd.date_range("2016-01-08", periods=255, freq="W")

    v2_2_b_shaped = carrier.Collinearity("V2.2-B", pd.Series(-V2_2_B_RHO, index=index), 0.5)
    verdict = ladder_v2_3.h1b(v2_2_b_shaped)
    assert not verdict["passed"]
    assert verdict["value"] == pytest.approx(V2_2_B_RHO, abs=1e-4)
    assert verdict["reference_v2_2_b"] == V2_2_B_RHO

    decoupled = carrier.Collinearity("ok", pd.Series(-0.40, index=index), 0.5)
    assert ladder_v2_3.h1b(decoupled)["passed"]

    # Exactly at the ceiling is a pass; a hair over is not. The threshold is fixed
    # in the pre-registration and this pins which side of it is inclusive.
    assert ladder_v2_3.h1b(carrier.Collinearity("e", pd.Series(0.90, index=index), 0.5))["passed"]
    assert not ladder_v2_3.h1b(
        carrier.Collinearity("e", pd.Series(0.9001, index=index), 0.5))["passed"]


# -------------------------------------------------- the arms are pre-registered


def test_the_ladder_is_the_two_arms_the_preregistration_names():
    assert [a.name for a in ladder_v2_3.ARMS] == ["V2.3-A", "V2.3-B"]
    assert ladder_v2_3.FAMILY_SIZE == len(ladder_v2_3.ARMS) == 2
    assert all(a.is_arm for a in ladder_v2_3.ARMS)
    assert all(not r.is_arm for r in ladder_v2_3.RUNGS)

    by_name = {a.name: a for a in ladder_v2_3.ARMS}
    assert by_name["V2.3-A"].base == ladder_v2_3.BASE_B1 == "z__ret_12_1"
    assert by_name["V2.3-A"].benchmark == "b1_momentum_12_1"
    assert by_name["V2.3-B"].base == ladder_v2_3.BASE_B3 == "z__b3"
    assert by_name["V2.3-B"].benchmark == "b3_regime_switched"

    # The two arms differ by their base and by nothing else.
    assert by_name["V2.3-A"].columns == by_name["V2.3-B"].columns
    assert by_name["V2.3-A"].lam == by_name["V2.3-B"].lam == ladder_v2_3.LAMBDA == 0.50


def test_no_arm_carries_its_own_base_as_an_input():
    """The single change that defines V2.3. It gets a structural check, not a note."""
    for spec in ladder_v2_3.ARMS + ladder_v2_3.RUNGS:
        assert spec.base not in spec.columns, spec.name
    assert ladder_v2_3.BASE_B1 not in ladder_v2_3.INPUT_COLUMNS
    assert ladder_v2_3.BASE_B3 not in ladder_v2_3.INPUT_COLUMNS


def test_the_inputs_are_v2_1_cs_thirty_five_columns_minus_the_base():
    """§3: no new features. Enforced by the import graph, not by a promise."""
    v2_1_c = set(ladder.ARMS_BY_NAME["V2.1-C"].columns)
    assert len(v2_1_c) == 35

    ranked_back = {c[len(carrier.RANK_PREFIX):] for c in ladder_v2_3.RANKED_STOCK_LEVEL}
    assert ranked_back | set(ladder_v2_3.MARKET_CONTEXT) == v2_1_c - {"ret_12_1"}
    assert len(ladder_v2_3.INPUT_COLUMNS) == 34
    assert len(ladder_v2_3.RANKED_STOCK_LEVEL) == 8
    assert len(ladder_v2_3.MARKET_CONTEXT) == 26

    # V2.2's arms had 35 inputs including the base; V2.3 has 34 excluding it.
    assert len(ladder_v2_2.ARM_COLUMNS) == 35
    assert set(ladder_v2_3.INPUT_COLUMNS) == set(ladder_v2_2.ARM_COLUMNS) - {"z__ret_12_1"}

    assert ladder_v2_3.MARKET_CONTEXT is ladder.MARKET_CONTEXT
    assert ladder_v2_3.STOCK_LEVEL is ladder.STOCK_LEVEL


def test_v2_3_a_trains_on_exactly_v2_2_bs_target():
    """What makes A-minus-V2.2-B "one deleted column" rather than two changes.

    V2.2-B's target was `target_rank - rank_pct(ret_12_1)`. V2.3 computes
    `target_rank - rank_pct(base)` where the base is already a centred rank, and
    `rank_pct` of a rank is that rank again — so the two are bit-identical. If they
    ever were not, the study's central contrast would be confounded and this fails.
    """
    frame = _panel()
    columns = ["z__ret_20d"]

    v2_3 = ladder_v2_3._training_frame(frame, columns, ladder_v2_3.BASE_B1)
    v2_2, target = ladder_v2_2._training_frame(frame, columns, ladder_v2_2.RESID_TARGET)
    assert target == ladder_v2_2.RESID_TARGET == ladder_v2_3.RESID_TARGET == "y_resid"

    a = v2_3["y_resid"].dropna()
    b = v2_2["y_resid"].reindex(a.index)
    assert float((a - b).abs().max()) == 0.0
    assert a.between(-1.0, 1.0).all()
    assert "y_resid" not in frame.columns, "the panel must not carry the residual"


def test_the_residual_target_is_derived_on_the_training_slice():
    """Both terms are within-cutoff, so a half-sample reproduces them exactly."""
    frame = _panel()
    columns = ["z__ret_20d"]
    full = ladder_v2_3._training_frame(frame, columns, ladder_v2_3.BASE_B1)["y_resid"]

    half = sorted(frame.index.get_level_values(0).unique())[:20]
    part = ladder_v2_3._training_frame(
        frame[frame.index.get_level_values(0).isin(pd.DatetimeIndex(half))],
        columns, ladder_v2_3.BASE_B1)["y_resid"]
    assert float((part - full.reindex(part.index)).abs().max()) == 0.0


def test_the_learner_and_lambda_were_not_retuned():
    """§1.6 and §1.7: V2.3 changes the base and the input list. Nothing else."""
    assert models.MODEL_A_PARAMS["max_iter"] == 300
    assert models.MODEL_A_PARAMS["learning_rate"] == 0.05
    assert models.MODEL_A_PARAMS["max_leaf_nodes"] == 31
    assert models.MODEL_A_PARAMS["min_samples_leaf"] == 100
    assert "monotonic_cst" not in models.MODEL_A_PARAMS

    assert ladder_v2_3.LAMBDA == ladder_v2_2.LAMBDA == 0.50
    assert set(ladder_v2_3.LAMBDA_CURVE) == {0.00, 0.25, 0.50, 1.00}
    # Exactly one point on the curve is the arm, and it is the carried-over value.
    assert sum(l == ladder_v2_3.LAMBDA for l in ladder_v2_3.LAMBDA_CURVE) == 1
    assert {a.lam for a in ladder_v2_3.ARMS} == {0.50}


# ------------------------------------------------------------ the identities


def test_the_two_bases_are_rank_identical_to_their_benchmarks():
    """§2.1: ranking `z__ret_12_1` must reproduce B1 and `z__b3` must reproduce B3.

    Both are monotone transforms of the benchmark scores, so these are identities
    rather than approximations, and `ladder_v2_3.main` stops the study if either
    fails on the real panel.
    """
    frame = _panel()
    b1 = models.simple_factor_scores(frame)["mom_12_1"]
    assert float((frame["z__ret_12_1"] - (b1 - carrier.RANK_CENTRE)).abs().max()) == 0.0
    assert _mean_ic(frame, frame["z__ret_12_1"]) == _mean_ic(frame, b1)

    # B3 on a bear-free synthetic panel is B1; the transform must still be exact.
    scores = protocol.benchmark_scores(frame, pd.DataFrame())
    z3 = carrier.rank_series(scores["b3_regime_switched"])
    assert _mean_ic(frame, z3) == _mean_ic(frame, scores["b3_regime_switched"])


def test_each_arm_at_lambda_zero_is_its_own_base():
    """§2: the identity that makes the lambda curve interpretable at its left end."""
    frame = _panel()
    rng = np.random.default_rng(5)
    prediction = pd.Series(rng.normal(size=len(frame)), index=frame.index)
    prediction.iloc[::9] = np.nan

    for base_column in (ladder_v2_3.BASE_B1, "z__ret_20d"):
        base = frame[base_column]
        assert carrier.blend(base, prediction, 0.0).equals(base)
    assert 0.0 in ladder_v2_3.LAMBDA_CURVE


def test_the_order_bound_still_holds_and_still_bites():
    """§2: inherited from V2.2 §3.2, and it must remain a real constraint."""
    frame = _panel()
    base = frame["z__ret_12_1"]
    rng = np.random.default_rng(6)
    noise = pd.Series(rng.normal(size=len(frame)), index=frame.index)

    assert carrier.order_bound_violations(
        base, carrier.blend(base, noise, ladder_v2_3.LAMBDA), ladder_v2_3.LAMBDA) == 0
    # A score built at lambda = 1 violates the lambda = 0.5 bound, so the checker
    # is not vacuously returning zero.
    inverted = carrier.blend(base, -base, 1.0)
    assert carrier.order_bound_violations(base, inverted, 0.5) > 0


# --------------------------------------------------------- the noise control


def test_the_noise_control_destroys_ic_across_independent_draws():
    """§4: a bounded blend must lose to its base when the adjustment is noise.

    The direct evidence that the construction cannot manufacture IC through
    tie-breaking or rank mechanics — and the reason it is measured over many draws
    rather than one. A single draw's mean IC has a sampling spread wider than the
    effect, so a single draw can show a gain on pure noise; §4 as pre-registered
    asked for one draw and did exactly that on the real panel. The expectation is
    what has to be negative, and it is.
    """
    frame = _panel()
    base = frame["z__ret_12_1"]
    base_ic = _mean_ic(frame, base)

    for lam in (0.25, 0.50, 1.00):
        diffs = []
        for draw in range(ladder_v2_3.NOISE_DRAWS):
            rng = np.random.default_rng(ladder_v2_3.NOISE_SEED + 1 + draw)
            noise = pd.Series(rng.normal(size=len(frame)), index=frame.index)
            diffs.append(_mean_ic(frame, carrier.blend(base, noise, lam)) - base_ic)
        array = np.array(diffs)
        assert array.mean() < 0, f"noise helped in expectation at lambda={lam}"
        assert (array > 0).mean() <= 0.5, f"noise helped on most draws at lambda={lam}"
    assert ladder_v2_3.NOISE_DRAWS >= 30, "one draw cannot resolve this"


# Why the powered version exists is a property of the *real* panel, not of a
# synthetic one: it needs a base whose IC (+0.021) is small enough that a single
# noise draw's sampling spread is comparable to the effect. A synthetic panel with a
# strong base settles the question in one draw and cannot demonstrate the problem.
# So the claim is asserted against the frozen record instead —
# `test_the_preregistered_single_draw_misfired_and_was_reported_anyway`.


# ----------------------------------------------- eligibility, selection, gates


def test_h1a_is_carried_over_from_v2_2_verbatim():
    """§1.8 and §5: the threshold that disqualified V2.2's arm C is not re-derived."""
    assert ladder_v2_3.H1A_FLOOR == ladder_v2_2.G1_FLOOR == -0.005
    assert ladder_v2_3.MIN_SCORED_CUTOFFS == ladder_v2_2.MIN_SCORED_CUTOFFS == 200
    assert ladder_v2_3.BREADTH_FLOOR == ladder_v2_2.BREADTH_FLOOR == 0.55
    assert ladder_v2_3.GATE_BENCHMARKS == ladder_v2_2.GATE_BENCHMARKS
    assert ladder_v2_3.COST_BPS == protocol.COST_BPS == 5.0

    index = pd.date_range("2016-01-08", periods=200, freq="W")
    s0 = pd.Series(0.021, index=index)
    assert ladder_v2_3.h1a(pd.Series(0.018, index=index), s0, "S1-A")["passed"]
    assert not ladder_v2_3.h1a(pd.Series(0.0159, index=index), s0, "S1-A")["passed"]


def test_a_carrier_defective_arm_cannot_be_selected_however_good_its_ic():
    """§5: not eligible whatever its IC — including when it leads."""
    records = {"V2.3-A": {"is_arm": True, "ic": {"mean": 0.99}},
               "V2.3-B": {"is_arm": True, "ic": {"mean": 0.01}}}
    eligible = {"V2.3-A": {"eligible": False}, "V2.3-B": {"eligible": True}}
    assert ladder_v2_3.select_arm(records, eligible) == "V2.3-B"
    assert ladder_v2_3.select_arm(records, {k: {"eligible": False} for k in records}) is None


def test_eligibility_needs_all_three_conditions():
    ok_a = {"passed": True, "value": -0.001, "rung": "S1-A", "ci": [-0.01, 0.01],
            "n_cutoffs": 255, "criterion": "…", "threshold": ">= -0.005"}
    ok_b = {"passed": True, "value": 0.4, "threshold": "<= 0.9"}
    assert ladder_v2_3.eligibility("V2.3-A", ok_a, ok_b, 255)["eligible"]
    assert not ladder_v2_3.eligibility("V2.3-A", {**ok_a, "passed": False}, ok_b, 255)["eligible"]
    assert not ladder_v2_3.eligibility("V2.3-A", ok_a, {**ok_b, "passed": False}, 255)["eligible"]
    thin = ladder_v2_3.eligibility("V2.3-A", ok_a, ok_b, 150)
    assert not thin["eligible"] and "carrier-defective" in thin["consequence"]


def test_selection_breaks_ties_toward_the_harder_null():
    """§5.1: B before A, because a tie means B matched A over the stronger base."""
    assert ladder_v2_3.SAFETY_ORDER == ("V2.3-B", "V2.3-A")
    records = {n: {"is_arm": True, "ic": {"mean": 0.03}} for n in ("V2.3-A", "V2.3-B")}
    eligible = {n: {"eligible": True} for n in records}
    assert ladder_v2_3.select_arm(records, eligible) == "V2.3-B"


def test_the_rungs_and_the_lambda_curve_can_never_be_chosen():
    """§4 and §6.1: promoting a diagnostic would make the Holm family bigger."""
    records = {"S1-A": {"is_arm": False, "ic": {"mean": 0.99}},
               "V2.3-A": {"is_arm": True, "ic": {"mean": 0.01}}}
    eligible = {n: {"eligible": True} for n in records}
    assert ladder_v2_3.select_arm(records, eligible) == "V2.3-A"
    assert ladder_v2_3.RUNG_FOR_ARM == {"V2.3-A": "S1-A", "V2.3-B": "S1-B"}
    for rung in ladder_v2_3.RUNGS:
        assert rung.columns == (ladder_v2_3.RUNG_COLUMN,)
        assert ladder_v2_3.RUNG_COLUMN == "z__ret_20d"


def _fake(name, **series):
    class F:
        pass
    f = F()
    f.name = name
    f.versus = {}
    return f


def _diff(mean: float, n: int = 255, share_positive: float = 1.0,
          second_half: float | None = None, scale: float = 0.0) -> pd.Series:
    index = pd.date_range("2016-01-08", periods=n, freq="W")
    if share_positive >= 1.0:
        values = np.full(n, float(mean))
        values[::2] += abs(mean) * 0.1
        values[1::2] -= abs(mean) * 0.1
    else:
        loss = 0.01
        positive = (np.arange(n) % 10) < round(share_positive * 10)
        gain = (mean + (1.0 - share_positive) * loss) / share_positive
        values = np.where(positive, gain, -loss)
    if scale:
        values = values + np.random.default_rng(1).normal(scale=scale, size=n)
    if second_half is not None:
        tail = values[n // 2:]
        values[n // 2:] = tail + (second_half - tail.mean())
    return pd.Series(values, index=index)


def test_paired_requires_the_interval_not_just_the_sign():
    """§9 names lowering a threshold as forbidden, so the shape gets a test.

    V2.1-D's number against momentum was +0.013 with a CI of [-0.019, +0.050] —
    positive and useless. `paired`'s `beats` is what every gate reads.
    """
    tight = ladder_v2_3.paired(_diff(0.08), pd.Series(0.0, index=_diff(0.08).index), "t")
    assert tight["beats"] and tight["ci"][0] > 0

    # V2.1-D's shape: a genuinely positive mean sitting inside a wide interval. The
    # noise is mean-centred so the point estimate is exactly +0.013 by construction.
    index = pd.date_range("2016-01-08", periods=255, freq="W")
    noise = np.random.default_rng(4).normal(scale=0.25, size=255)
    wide = pd.Series(0.013 + noise - noise.mean(), index=index)
    loose = ladder_v2_3.paired(wide, pd.Series(0.0, index=index), "w")
    assert loose["mean"] == pytest.approx(0.013, abs=1e-5)
    assert loose["ci"][0] < 0 and not loose["beats"]

    negative = ladder_v2_3.paired(_diff(-0.05), pd.Series(0.0, index=_diff(-0.05).index), "n")
    assert not negative["beats"]


def test_g6_fails_on_a_v2_2_b_shaped_cost_difference():
    """§6: the gate V2.2 lacked, checked against the number that motivated it.

    V2.2-B's net-spread advantage over momentum was +0.00021 with CI
    [-0.00012, +0.00058] at 5 bps — an IC gain that did not become a tradeable one.
    That shape must fail.
    """
    index = pd.date_range("2016-01-08", periods=255, freq="W")
    rng = np.random.default_rng(11)
    v2_2_b_shaped = pd.Series(0.00021 + rng.normal(scale=0.0027, size=255), index=index)
    verdict = ladder_v2_3.paired(v2_2_b_shaped, pd.Series(0.0, index=index), "cost")
    assert verdict["mean"] > 0
    assert verdict["ci"][0] < 0
    assert not verdict["beats"], "a cost gain inside the noise is not a pass"

    real = pd.Series(0.0020 + rng.normal(scale=0.0005, size=255), index=index)
    assert ladder_v2_3.paired(real, pd.Series(0.0, index=index), "cost")["beats"]


def test_breadth_and_stability_are_computed_the_way_v2_2_computed_them():
    narrow = ladder_v2_3.paired(_diff(0.08, share_positive=0.3),
                                pd.Series(0.0, index=_diff(0.08).index), "n")
    assert narrow["beats"] and narrow["share_positive"] < ladder_v2_3.BREADTH_FLOOR

    drifts = _diff(0.20, second_half=-0.02)
    entry = ladder_v2_3.paired(drifts, pd.Series(0.0, index=drifts.index), "d")
    assert entry["halves"]["first"]["mean"] > 0 > entry["halves"]["second"]["mean"]
    assert not ladder_v2_3._both_halves_positive(entry)
    assert ladder_v2_3._both_halves_positive(
        ladder_v2_3.paired(_diff(0.08), pd.Series(0.0, index=_diff(0.08).index), "p"))


def test_power_is_reported_and_scales_to_the_frozen_exam_size():
    """§6.2: a reader must be able to tell a power failure from an effect failure."""
    assert ladder_v2_3.EXAM_CUTOFFS_FOR_POWER == 72
    entry = {"half_width": 0.00182, "n_cutoffs": 255, "mean": 0.00241}
    got = ladder_v2_3.power(entry)
    assert got["half_width_scaled_to_72_cutoffs"] == pytest.approx(0.00343, abs=1e-5)
    assert got["cutoffs_needed_to_resolve_the_observed_effect"] == pytest.approx(145, abs=2)
    assert ladder_v2_3.power({"half_width": None, "n_cutoffs": 0})["half_width_development"] is None


# ------------------------------------------------------------------ the seal


def test_the_ladder_reads_its_cutoffs_through_development_only():
    source = (REPO / "alpha" / "ladder_v2_3.py").read_text(encoding="utf-8")
    assert "examset.development_only(panel, exam_set)" in source
    assert "exam_set.cutoffs" not in source
    assert ".slice_cutoffs(" not in source


def test_the_ladder_does_not_import_the_production_layer():
    """§1.4, structurally: if it imported adapter, the module would carry it."""
    assert not hasattr(ladder_v2_3, "adapter")


def test_the_ladder_refuses_to_run_if_an_exam_prediction_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(ladder_v2_3, "OUT_DIR", tmp_path)
    (tmp_path / "v2_1_exam_predictions.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="must not come into existence"):
        ladder_v2_3.main([])


def test_the_v2_1_exam_is_untouched():
    assert not (ladder_v2_3.OUT_DIR / "v2_1_exam_predictions.json").exists()
    assert not (ladder_v2_3.OUT_DIR / "v2_3_exam_predictions.json").exists()
    if examset.PATH.exists():
        assert examset.load().digest == V2_1_EXAM_DIGEST


@needs_v2_2
def test_the_v2_2_record_is_untouched():
    """§1.3: V2.3 extends `carrier.py` additively. The V2.2 numbers must not move.

    The 43 tests in `test_alpha_v2_2.py` are the other half of this check — they
    assert V2.2's behaviour, and they run against the same extended `carrier.py`.
    """
    record = json.loads(ladder_v2_2.JSON_PATH.read_text(encoding="utf-8"))
    assert record["arms"]["V2.2-B"]["ic"]["mean"] == V2_2_B_MEAN_IC
    assert record["family_size"] == 3
    assert record["production_weight"] == 0.0
    assert record["exam_may_be_opened"] is False
    assert set(record["arms"]) == {"V2.2-A", "V2.2-B", "V2.2-C"}

    # The V2.2 module still describes its own three arms at its own lambda.
    assert [a.name for a in ladder_v2_2.ARMS] == ["V2.2-A", "V2.2-B", "V2.2-C"]
    assert ladder_v2_2.FAMILY_SIZE == 3
    assert ladder_v2_3.JSON_PATH != ladder_v2_2.JSON_PATH


def test_v2_3_did_not_edit_the_earlier_documents():
    """The pre-registrations record finished experiments and must not learn of V2.3.

    `V2_2_LADDER_REPORT.md` is deliberately excluded: it was written during V2.2 and
    its §8 already speculates about "what a V2.3 would have to be". That sentence is
    part of the V2.2 record, not an edit made now — so what is checked there instead
    is that its numbers still say what V2.2 measured.
    """
    for name in ("PREREGISTRATION.md", "V2_1_PREREGISTRATION.md",
                 "V2_1_LADDER_PREREGISTRATION.md", "V2_1_LADDER_REPORT.md",
                 "V2_2_PREREGISTRATION.md"):
        assert "V2.3" not in (REPO / "alpha" / name).read_text(encoding="utf-8"), name

    v2_2_report = (REPO / "alpha" / "V2_2_LADDER_REPORT.md").read_text(encoding="utf-8")
    assert "+0.02356" in v2_2_report and "The §6.3 gate closed" in v2_2_report
    assert "Production stays at weight 0" in v2_2_report or "weight 0" in v2_2_report


def test_the_preregistration_fixes_what_it_says_it_fixes():
    doc = (REPO / "alpha" / "V2_3_PREREGISTRATION.md").read_text(encoding="utf-8")
    assert V2_1_EXAM_DIGEST in doc
    assert "k = 2" in doc
    assert "ACCEPTED on review, before the first fit" in doc
    plain = (doc.replace("≤", "<=").replace("≥", ">=")
             .replace("λ", "lambda").replace("−", "-"))
    assert "<= 0.90" in plain
    assert ">= -0.005" in plain
    assert ">= 200" in plain
    assert "lambda = 0.50" in plain
    for forbidden in ("lowering a threshold", "re-choosing", "adding a third arm",
                      "modifying B3", "post-hoc orthogonalisation"):
        assert forbidden in doc, forbidden
    # The abandonment criteria are part of the commitment, not an afterthought.
    assert "Both arms fail H1b" in doc
    assert "does not propose a v2.4" in doc.replace("\n", " ").lower()


# --------------------------------------------------- against the frozen record


@needs_development
def test_the_frozen_record_reports_everything_the_review_asked_for():
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    assert set(record["arms"]) <= {"V2.3-A", "V2.3-B"}
    for name, arm in record["arms"].items():
        for key in ("ic", "collinearity", "carrier_diagnostics", "gate", "power",
                    "lambda_curve", "noise_control", "bear_decomposition",
                    "order_bound_violations", "base_column", "input_columns"):
            assert key in arm, f"{name} is missing {key}"
        assert arm["base_is_an_input"] is False
        assert arm["scored_against"] == "alpha_5d"
        assert arm["n_inputs"] == 34
        assert arm["lambda"] == 0.50
        assert arm["order_bound_violations"] == 0, name
        # The verdict comes from the powered control; the pre-registered single
        # draw is reported beside it, gain and all.
        assert arm["noise_control"]["destroys_ic"], name
        assert arm["noise_control"]["powered"]["draws"] >= 30, name
        assert arm["noise_control"]["powered"]["share_of_draws_above_base"] <= 0.5, name
        assert "preregistered_single_draw" in arm["noise_control"], name
        for key in ("G2_beats_12_1_momentum", "G3_beats_regime_switched_momentum",
                    "G4_breadth", "G5_stability", "G6_cost"):
            assert key in arm["gate"]["gates"], f"{name} is missing {key}"
    for name, verdict in record["eligibility"].items():
        for key in ("h1a_carrier_integrity", "h1b_collinearity_ceiling",
                    "h1c_scored_cutoffs", "eligible"):
            assert key in verdict, f"{name} is missing {key}"


@needs_development
def test_the_preregistered_single_draw_misfired_and_was_reported_anyway():
    """§4's control, as worded, produced a gain on noise. The record must show it.

    This is the one place the study departed from the accepted pre-registration's
    literal text, and it is departed from in the direction of a *stricter* test. The
    departure is only defensible if the evidence is on the record, so:

    * the single pre-registered draw is present, with its gain and its interval;
    * that gain is **not significant** — the paired CI spans zero;
    * the powered control, over >= 30 draws, shows destruction.

    If any of those stopped being true the departure would stop being defensible.
    """
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    seen_a_gain = False
    for name, arm in record["arms"].items():
        control = arm["noise_control"]
        single = control["preregistered_single_draw"]
        assert single["seed"] == ladder_v2_3.NOISE_SEED
        at_lambda = single["at_lambda"]["0.50"]
        # Whatever the single draw did, it may not have done it *significantly*.
        assert not at_lambda["gain_is_significant"], (
            f"{name}: the single-draw gain on pure noise is significant. That is a "
            "real defect in the construction, not an under-powered control, and the "
            "study must stop rather than report a powered version.")
        seen_a_gain = seen_a_gain or at_lambda["gained_on_base"]
        assert control["powered"]["mean_paired_difference"] < 0, name
        assert control["powered"]["draws"] >= 30, name
    assert seen_a_gain, (
        "no arm's pre-registered single draw gained on noise, so §4 as written did "
        "not misfire and the powered version needs no separate justification")


@needs_development
def test_the_frozen_bases_reproduced_their_benchmarks_exactly():
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    identities = record["base_identities"]
    assert set(identities) == {"z__ret_12_1", "z__b3"}
    for base, entry in identities.items():
        assert entry["rank_identical"]
        assert (entry["max_abs_ic_difference"] or 0.0) < 1e-12, base
    assert identities["z__ret_12_1"]["equals"] == "b1_momentum_12_1"
    assert identities["z__b3"]["equals"] == "b3_regime_switched"


@needs_development
def test_the_lambda_bound_holds_on_the_frozen_predictions():
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    for name, arm in record["arms"].items():
        for lam, entry in arm["lambda_curve"].items():
            if float(lam) <= ladder_v2_3.LAMBDA:
                assert entry["order_bound_violations"] == 0, f"{name} @ {lam}"

    if not (DEV_PICKLE.exists() and PANEL_PATH.exists()):
        pytest.skip("the frozen predictions or the panel are not on this machine")
    blob = pd.read_pickle(DEV_PICKLE)
    panel, _d, _e = build_panel.load()
    frame = examset.development_only(panel).frame
    base = carrier.centred_rank(frame, "ret_12_1")
    if "V2.3-A" in blob["final_scores"]:
        final = blob["final_scores"]["V2.3-A"]
        assert carrier.order_bound_violations(
            base.reindex(final.index), final, ladder_v2_3.LAMBDA) == 0


@needs_development
@needs_exam_set
def test_the_frozen_v2_3_record_never_touched_an_exam_cutoff():
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    exam_set = examset.load()
    assert record["exam_set_digest"] == exam_set.digest == V2_1_EXAM_DIGEST
    assert record["development_cutoffs"] == len(exam_set.development)
    assert record["family_size"] == 2
    assert record["exam_may_be_opened"] is False
    assert record["exam_predictions_exist"] is False

    if not DEV_PICKLE.exists():
        pytest.skip("the frozen pickle is not on this machine")
    blob = pd.read_pickle(DEV_PICKLE)
    exam_dates = set(exam_set.cutoffs)
    for name, series in blob["ic_series"].items():
        scored = set(pd.DatetimeIndex(series.index))
        assert not scored & exam_dates, f"{name} scored an exam cutoff"
        assert scored <= set(exam_set.development), name


@needs_development
def test_the_frozen_record_left_production_at_zero():
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    assert record["production_weight"] == 0.0
    for entry in {**record["arms"], **record["rungs"]}.values():
        assert entry["production_weight"] == 0.0
        assert "gates_passed" not in entry
        assert "diagnostic_gates_passed" in entry


@needs_development
def test_the_multiplicity_family_is_the_two_arms():
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    holm = record["holm_bonferroni_on_development"]
    assert set(holm) <= {"V2.3-A", "V2.3-B"}
    assert set(holm) == set(record["arms"])
    for name in record["rungs"]:
        assert name not in holm, f"{name} entered the multiplicity family"


@needs_development
def test_b3_is_identical_to_b1_outside_bear_on_the_frozen_record():
    """The structural fact the bear decomposition rests on, checked as measured."""
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    for name, entry in record["bear_decomposition"].items():
        assert entry["b3_identical_to_b1_off_bear"], name
        b1 = entry["b1_momentum_12_1"]["by_trend"]
        b3 = entry["b3_regime_switched"]["by_trend"]
        for bucket in b1:
            if bucket == protocol.BEAR:
                continue
            assert b1[bucket]["mean"] == pytest.approx(b3[bucket]["mean"], abs=1e-9), (
                f"{name}: {bucket} differs between the B1 and B3 comparisons, but B3 "
                "is B1 there")
