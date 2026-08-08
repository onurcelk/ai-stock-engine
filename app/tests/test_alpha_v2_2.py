"""Tests for V2.2 — the carrier, and the defect it exists to fix.

`test_alpha_v2_1.py` tests the protocol; `test_alpha_v2_1_ladder.py` tests the
V2.1 arms. This file tests the *carrier*: the four steps between a raw feature
and a position in the ranking, which V2.1's headline finding showed was where
V2's null came from.

The load-bearing test is `test_a_raw_level_carrier_can_invert_a_monotone_factor`.
It reproduces the V2.1-A pathology on a synthetic panel from first principles: a
factor that predicts the outcome *within every cutoff*, whose pooled level
relationship runs the other way, fed to a learner that minimises squared error on
the pooled level and then used to rank. The learner comes out decreasing in its
own input. That test must keep passing after the carrier is fixed — the point is
not that the defect is gone, it is that the defect stays visible, so a future
reader can see what the fix was for.

`V2_2_PREREGISTRATION.md` §11 lists the tests that must exist before the result
is trusted. Each of them is below, and one of them is narrower here than §11
words it — see `test_the_monotone_constraint_binds_only_where_it_can`, which
records why.

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

from alpha import (adapter, build_panel, carrier, examset, ladder,  # noqa: E402
                  ladder_v2_2, models, protocol, stats, targets)

PANEL_PATH = build_panel.PANEL_PATH
DEV_PATH = ladder_v2_2.JSON_PATH
DEV_PICKLE = ladder_v2_2.PICKLE_PATH

# §1.1 — the digest the V2.1 exam was frozen with. Written out rather than read
# from the artefact, so an edited artefact fails instead of redefining the target.
V2_1_EXAM_DIGEST = "b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0"

needs_panel = pytest.mark.skipif(
    not PANEL_PATH.exists(), reason="alpha/out/panel.pkl has not been built")
needs_development = pytest.mark.skipif(
    not DEV_PATH.exists(), reason="alpha/out/v2_2_development.json has not been written")
needs_exam_set = pytest.mark.skipif(
    not examset.PATH.exists(), reason="v2_1_exam_set.json is not frozen on this machine")


# ----------------------------------------------------------------------
# A synthetic panel with the V2.1-A pathology built into it
# ----------------------------------------------------------------------

def _simpson_panel(n_cutoffs: int = 60, n_symbols: int = 100) -> pd.DataFrame:
    """A factor that works within every cutoff and inverts when the levels are pooled.

    Cutoff *i* draws `ret_12_1` from `[0.05i, 0.05i + 1]` and `alpha_5d` from
    `[-0.002i, -0.002i + 0.01]`, both increasing in the same symbol index. So:

    * **within** any cutoff, `alpha_5d` is a strictly increasing function of
      `ret_12_1` — the factor is perfect, per-cutoff Spearman IC is exactly +1;
    * **pooled**, the cutoff offsets dominate: `ret_12_1` rises by 0.05 per cutoff
      while `alpha_5d` falls by 0.002, a pooled slope of about -0.04 per unit
      against a within-cutoff slope of +0.01.

    That is Simpson's paradox, and it is the shape V2.1-A ran into: nothing about
    it is adversarial to trees in particular. Any learner minimising squared error
    on pooled levels sees the -0.04.
    """
    rows = []
    for i in range(n_cutoffs):
        u = np.linspace(0.0, 1.0, n_symbols)
        rows.append(pd.DataFrame({
            "cutoff": pd.Timestamp("2016-01-04") + pd.Timedelta(days=7 * i),
            "symbol": [f"S{j:03d}" for j in range(n_symbols)],
            "ret_12_1": 0.05 * i + u,
            "alpha_5d": -0.002 * i + 0.01 * u,
        }))
    frame = pd.concat(rows, ignore_index=True).set_index(["cutoff", "symbol"]).sort_index()
    frame["target_train"] = frame.groupby(level=0)["alpha_5d"].transform(targets.winsorise)
    frame["target_rank"] = frame.groupby(level=0)["alpha_5d"].transform(
        targets.cross_sectional_rank)
    frame, _added = carrier.add_rank_columns(frame, ("ret_12_1",))
    return frame


def _mean_ic(frame: pd.DataFrame, score: pd.Series) -> float:
    block = frame[["alpha_5d"]].copy()
    block["prediction"] = score
    return float(stats.ic_by_cutoff(block, "prediction", "alpha_5d").dropna().mean())


def _fit_and_predict(frame: pd.DataFrame, columns: list[str], target: str,
                     monotone: str | None = None) -> pd.Series:
    """In-sample fit and predict. Hermetic on purpose — the claim is about the *map*.

    Nothing here is a performance measurement, so there is no walk-forward and no
    embargo: the question is what shape of function the carrier produces, and an
    in-sample fit answers it with less machinery and no ambiguity.
    """
    fit = (carrier.fit_monotone(frame, columns, target, monotone) if monotone
           else models.fit_model_a(frame, columns, target=target))
    assert fit is not None, "the synthetic panel is too small to fit"
    return fit.predict(frame)


# ------------------------------------------------ §11.1 the pathology, on demand


def test_a_raw_level_carrier_can_invert_a_monotone_factor():
    """The V2.1-A defect, reproduced from first principles and kept reproducible.

    V2.1-A scored +0.00053 where ranking its single input directly scored
    +0.02115, with a within-cutoff correlation against its own input of -0.198,
    negative on 224 of 255 cutoffs. This is that, in miniature and with the
    mechanism visible: raw level in, winsorised level target, output ranked.

    The test asserts the *sign flip*, not a magnitude, because the magnitude
    depends on how strongly the pooled trend dominates and that is a property of
    the synthetic panel rather than of the defect.
    """
    frame = _simpson_panel()
    factor = frame["ret_12_1"]

    # The factor itself is perfect within every cutoff — Spearman IC exactly +1.
    assert _mean_ic(frame, carrier.centred_rank(frame, "ret_12_1")) == pytest.approx(1.0)

    prediction = _fit_and_predict(frame, ["ret_12_1"], "target_train")
    diagnostics = carrier.diagnose(prediction, factor, "raw-level carrier")
    summary = diagnostics.summary()

    # The learner fit a predominantly *decreasing* function of its own input.
    assert summary["spearman_vs_factor"]["mean"] < -0.5
    assert summary["spearman_vs_factor"]["share_negative"] > 0.9
    assert summary["inversions"]["cutoffs_with_any"] == summary["n_cutoffs"]

    # And ranking by it therefore destroys a factor that was worth +1.0.
    assert _mean_ic(frame, prediction) < 0.0

    # It is a step function of its input — the sharp §5.3 test. Every change in
    # the score coincides with a change in the factor, and it cannot separate two
    # names that share a histogram bin.
    assert summary["is_univariate_in_factor"]


def test_the_rank_carrier_fixes_the_pathology_on_the_same_panel():
    """§3.1 on the panel that breaks the raw-level carrier. Same data, same learner.

    Ranks in and ranks out removes the only thing the two carriers differ by: the
    cutoff offsets that made the pooled level relationship point the wrong way.
    `z__ret_12_1` is identical in every cutoff by construction, so there is no
    pooled trend left to fit.
    """
    frame = _simpson_panel()
    prediction = _fit_and_predict(frame, ["z__ret_12_1"], "target_rank")
    summary = carrier.diagnose(prediction, frame["ret_12_1"], "rank carrier").summary()

    assert summary["spearman_vs_factor"]["mean"] > 0.9
    assert summary["spearman_vs_factor"]["share_negative"] == 0.0
    assert _mean_ic(frame, prediction) > 0.9


def test_the_blend_carrier_cannot_invert_the_factor_at_all():
    """§3.2 on the same panel, and this one holds whatever the model does.

    The residual target here is degenerate — the factor already ranks perfectly,
    so `y_resid` is ~0 everywhere and the model has nothing to say. That is the
    interesting case: the guarantee has to survive a model whose output is noise,
    because a bound that only holds for good models is not a bound.
    """
    frame = _simpson_panel()
    base = frame["z__ret_12_1"]

    rng = np.random.default_rng(0)
    noise = pd.Series(rng.normal(size=len(frame)), index=frame.index)

    final = carrier.blend(base, noise, ladder_v2_2.LAMBDA)
    assert carrier.order_bound_violations(base, final, ladder_v2_2.LAMBDA) == 0

    # Even adversarially: the exact negation of the base, ranked, cannot flip it.
    adversarial = carrier.blend(base, -base, ladder_v2_2.LAMBDA)
    assert carrier.order_bound_violations(base, adversarial, ladder_v2_2.LAMBDA) == 0
    assert _mean_ic(frame, adversarial) > 0.9


# ---------------------------------------------------- §11.2 / §11.3 the identities


def test_s0_is_rank_identical_to_benchmark_one():
    """§2.2: ranking by `z__ret_12_1` must reproduce Benchmark 1 exactly.

    `centred_rank` is `models.simple_factor_scores`'s own operation less a
    constant, so this is an identity — and §2.2 makes it an assertion rather than
    a hope: if it does not hold to the last digit the pipeline is wrong and V2.2
    stops. `ladder_v2_2.main` re-checks it on the real panel before any fit.
    """
    frame = _simpson_panel()
    s0 = frame["z__ret_12_1"]
    b1 = models.simple_factor_scores(frame)["mom_12_1"] * protocol.BENCHMARKS[0].sign

    assert protocol.BENCHMARKS[0].key == "b1_momentum_12_1"
    assert protocol.BENCHMARKS[0].factor == "mom_12_1"
    assert float((s0 - (b1 - carrier.RANK_CENTRE)).abs().max()) == 0.0
    assert _mean_ic(frame, s0) == _mean_ic(frame, b1)


def test_arm_b_at_lambda_zero_is_rank_identical_to_benchmark_one():
    """§3.2: lambda = 0 is the identity check, and it has to be exact.

    `blend` short-circuits at lambda = 0 rather than computing `base + 0.0 * u`,
    because `0.0 * NaN` is NaN and would silently drop every name the model had
    no opinion about — turning an identity into a near-miss on a different sample.
    """
    frame = _simpson_panel()
    base = frame["z__ret_12_1"]
    rng = np.random.default_rng(1)
    prediction = pd.Series(rng.normal(size=len(frame)), index=frame.index)
    prediction.iloc[::7] = np.nan          # the model declines to score some names

    final = carrier.blend(base, prediction, 0.0)
    assert final.equals(base)
    assert final.notna().sum() == base.notna().sum()

    b1 = models.simple_factor_scores(frame)["mom_12_1"]
    assert _mean_ic(frame, final) == _mean_ic(frame, b1)

    assert 0.0 in ladder_v2_2.LAMBDA_CURVE, "the identity check must stay on the curve"


def test_the_order_bound_actually_bites_when_lambda_is_large():
    """The bound is a real constraint, so it has to be possible to violate it.

    A checker that returns 0 for everything proves nothing. At lambda = 1.0 the
    adjustment spans the whole cross-section and can reorder any pair, so
    `order_bound_violations` at the *wrong* lambda must find the violations that
    the pre-registered lambda forbids.
    """
    frame = _simpson_panel()
    base = frame["z__ret_12_1"]
    inverted = carrier.blend(base, -base, 1.0)

    # Honest at its own lambda: at 1.0 nothing is guaranteed and nothing is claimed.
    assert carrier.order_bound_violations(base, inverted, 1.0) == 0
    # But that same score does violate the lambda = 0.5 bound, which is the point.
    assert carrier.order_bound_violations(base, inverted, 0.5) > 0


# ------------------------------------------------------ §11.5 the monotone arm


def test_the_one_feature_monotone_rung_cannot_invert_momentum():
    """§3.3 where the guarantee is unconditional: one constrained column, nothing else.

    With `z__ret_12_1` as the only input, "non-decreasing in the momentum rank at
    fixed values of everything else" has no "everything else" to be conditional
    on, so the prediction is non-decreasing along the momentum ordering inside
    every cutoff. Zero inversions, by construction.

    §3.3's disclosed risk is also checked: when the pooled relationship runs
    against the constraint the learner may collapse to a constant rather than
    merely flatten, which drops the cutoff out of the IC sample. Either outcome is
    pre-registered as acceptable; an *inversion* is not.
    """
    frame = _simpson_panel()
    prediction = _fit_and_predict(frame, ["z__ret_12_1"], "target_rank",
                                  monotone="z__ret_12_1")
    summary = carrier.diagnose(prediction, frame["ret_12_1"], "S1-C").summary()

    assert summary["inversions"]["total"] == 0
    assert summary["spearman_vs_factor"]["share_negative"] == 0.0
    # Collapse would be reported, not worked around. On this panel it does not
    # happen, because the rank target agrees with the constraint.
    assert summary["collapsed_cutoffs"] == 0


def test_the_monotone_constraint_binds_only_where_it_can():
    """§11's fifth bullet is narrower than it reads, and this records why.

    §11 asks for a test that "arm C produces zero inversions against `ret_12_1`".
    That is provable for the one-feature rung `S1-C` and is asserted above. It is
    **not** provable for the 35-feature arm: `monotonic_cst` constrains the model
    to be non-decreasing in `z__ret_12_1` *holding the other 34 columns fixed*,
    and eight of those are stock-level columns that vary across the cross-section
    inside a cutoff. Two names can therefore be ordered against their momentum by
    a difference in volatility, and no constraint sklearn offers prevents it.

    What the constraint does guarantee for arm C is the thing §3.3 actually claims
    in prose: two names identical in the other 34 columns can never be ordered
    against their momentum. That is asserted here directly. Arm C's inversion
    count against `ret_12_1` is *measured and reported* rather than asserted to be
    zero — see `test_the_frozen_record_reports_every_section_5_diagnostic`.

    This is a defect in §11's wording, found before the first fit and recorded
    rather than fixed by weakening the arm.
    """
    frame = _simpson_panel()
    frame["rvol_20d"] = np.tile(np.linspace(0.1, 0.9, 100), 60)
    frame, _added = carrier.add_rank_columns(frame, ("rvol_20d",))
    columns = ["z__ret_12_1", "z__rvol_20d"]

    fit = carrier.fit_monotone(frame, columns, "target_rank", "z__ret_12_1")
    assert fit is not None and fit.columns == columns
    assert list(fit.model.monotonic_cst) == [1, 0]

    # The guarantee, stated as sklearn states it: sweep the constrained column
    # with everything else held fixed and the prediction may not decrease.
    held = frame.iloc[[0]].copy()
    sweep = pd.concat([held.assign(z__ret_12_1=z) for z in np.linspace(-0.5, 0.5, 40)])
    predicted = fit.predict(sweep).to_numpy()
    assert (np.diff(predicted) >= -1e-12).all()


def test_the_monotone_fitter_refuses_a_constraint_it_cannot_apply():
    """A constraint on an all-NaN column would be silently dropped. That must fail loudly.

    `fit_model_a` drops columns that are entirely NaN over the training slice, and
    `monotonic_cst` is positional — so a constraint built against the requested
    list and applied to the surviving list would land on the wrong column. That is
    the worst kind of bug: it produces a plausible number.
    """
    frame = _simpson_panel()
    frame["dead"] = np.nan
    with pytest.raises(RuntimeError, match="all-NaN"):
        carrier.fit_monotone(frame, ["z__ret_12_1", "dead"], "target_rank", "dead")

    # And when the constrained column survives, the positions must line up.
    fit = carrier.fit_monotone(frame, ["z__ret_12_1", "dead"], "target_rank", "z__ret_12_1")
    assert fit is not None and fit.columns == ["z__ret_12_1"]
    assert list(fit.model.monotonic_cst) == [1]


# --------------------------------------------- §11.6 the rank-transform asymmetry


def test_the_rank_transform_is_asked_for_column_by_column():
    """§2.1: `add_rank_columns` transforms what it is handed and nothing else.

    There is no prefix rule and no "everything numeric" default, because those are
    the things that quietly start ranking a context column when someone adds a
    feature. A column the panel lacks is an error rather than a skip.
    """
    frame = _simpson_panel()
    widened, added = carrier.add_rank_columns(frame, ("ret_12_1",))
    assert added == ["z__ret_12_1"]
    assert not [c for c in widened.columns if c.startswith(carrier.RANK_PREFIX)
                and c != "z__ret_12_1"]

    with pytest.raises(KeyError, match="cannot rank-transform"):
        carrier.add_rank_columns(frame, ("no_such_column",))


def test_the_arms_rank_the_stock_level_columns_and_not_the_context_columns():
    """§2.1's asymmetry, read off the pre-registered column lists.

    A within-cutoff rank of a cutoff-constant column is 0.5 for every name, so
    ranking the 26 context columns would annihilate them. The asymmetry is a
    design decision; this is the assertion the pre-registration promised.
    """
    assert ladder_v2_2.ARM_COLUMNS == ladder_v2_2.RANKED_STOCK_LEVEL + ladder_v2_2.MARKET_CONTEXT
    assert len(ladder_v2_2.ARM_COLUMNS) == 35
    assert len(ladder_v2_2.RANKED_STOCK_LEVEL) == 9
    assert len(ladder_v2_2.MARKET_CONTEXT) == 26

    for column in ladder_v2_2.RANKED_STOCK_LEVEL:
        assert column.startswith(carrier.RANK_PREFIX)
    for column in ladder_v2_2.MARKET_CONTEXT:
        assert not column.startswith(carrier.RANK_PREFIX)
    assert not [c for c in ladder_v2_2.STOCK_LEVEL if c.startswith("mkt_")]

    # The base score is the momentum rank, and it is in every arm's input.
    assert ladder_v2_2.Z_BASE == "z__ret_12_1"
    assert ladder_v2_2.Z_BASE in ladder_v2_2.ARM_COLUMNS


def test_constant_within_cutoff_is_what_decides_that_asymmetry():
    """The check that makes the decision auditable rather than asserted."""
    frame = _simpson_panel()
    frame["context"] = frame.index.get_level_values(0).astype("int64") % 7
    verdict = carrier.constant_within_cutoff(frame, ["ret_12_1", "context"])
    assert verdict == {"ret_12_1": False, "context": True}


@needs_panel
@needs_exam_set
def test_the_asymmetry_holds_on_the_real_development_panel():
    """The same claim against the built panel, over every development cutoff.

    `ladder_v2_2.check_rank_transform_asymmetry` refuses to run the study if this
    ever flips, because a `MARKET_CONTEXT` column that varies within a cutoff
    makes the arms a different experiment.
    """
    panel, _development, _exam = build_panel.load()
    panel = examset.development_only(panel)
    verdict = ladder_v2_2.check_rank_transform_asymmetry(panel)
    assert verdict["all_market_context_cutoff_constant"]
    assert verdict["all_stock_level_varying"]
    assert not verdict["market_context_rank_transformed"]
    assert verdict["stock_level_rank_transformed"]


# ------------------------------------------------ §3 the arms are pre-registered


def test_the_ladder_is_the_three_arms_the_preregistration_names():
    """Which arms exist, and how many, is itself a pre-registered decision."""
    assert [arm.name for arm in ladder_v2_2.ARMS] == ["V2.2-A", "V2.2-B", "V2.2-C"]
    assert ladder_v2_2.FAMILY_SIZE == len(ladder_v2_2.ARMS) == 3
    assert all(arm.arm for arm in ladder_v2_2.ARMS)

    by_name = {arm.name: arm for arm in ladder_v2_2.ARMS}
    # All three carry the identical 35 columns. The carrier is the only difference.
    for arm in ladder_v2_2.ARMS:
        assert arm.columns == ladder_v2_2.ARM_COLUMNS, arm.name

    assert by_name["V2.2-A"].train_target == "target_rank"
    assert by_name["V2.2-A"].combination == "prediction"
    assert by_name["V2.2-A"].monotone is None

    assert by_name["V2.2-B"].train_target == ladder_v2_2.RESID_TARGET
    assert by_name["V2.2-B"].combination == "blend"
    assert by_name["V2.2-B"].lam == ladder_v2_2.LAMBDA == 0.50

    assert by_name["V2.2-C"].train_target == "target_rank"
    assert by_name["V2.2-C"].monotone == ladder_v2_2.Z_BASE


def test_the_features_are_exactly_v2_1_cs_thirty_five_columns():
    """§3: "no feature is added, removed or re-justified", enforced by the import.

    The lists come from `ladder.py`, so a V2.2 arm cannot drift from V2.1-C by a
    column without the V2.1 module changing — which its own tests forbid.
    """
    v2_1_c = set(ladder.ARMS_BY_NAME["V2.1-C"].columns)
    assert v2_1_c == set(ladder.ARMS_BY_NAME["V2.1-D"].columns)

    ranked_back = {c[len(carrier.RANK_PREFIX):] for c in ladder_v2_2.RANKED_STOCK_LEVEL}
    assert ranked_back | set(ladder_v2_2.MARKET_CONTEXT) == v2_1_c
    assert ladder_v2_2.STOCK_LEVEL == ladder.MOMENTUM + ladder.STOCK_LEVEL
    assert ladder_v2_2.MARKET_CONTEXT is ladder.MARKET_CONTEXT


def test_the_learner_was_not_retuned():
    """§3: "the learner's hyperparameters are unchanged". V2.2 changes the carrier."""
    assert models.MODEL_A_PARAMS["max_iter"] == 300
    assert models.MODEL_A_PARAMS["learning_rate"] == 0.05
    assert models.MODEL_A_PARAMS["max_leaf_nodes"] == 31
    assert models.MODEL_A_PARAMS["min_samples_leaf"] == 100
    assert models.MODEL_A_PARAMS["loss"] == "squared_error"
    assert "monotonic_cst" not in models.MODEL_A_PARAMS

    # Arm C's params are MODEL_A_PARAMS *plus* the constraint, and the module-level
    # dict must not be mutated in the process.
    frame = _simpson_panel()
    carrier.fit_monotone(frame, ["z__ret_12_1"], "target_rank", "z__ret_12_1")
    assert "monotonic_cst" not in models.MODEL_A_PARAMS


def test_the_residual_target_is_derived_on_the_training_slice():
    """§3.2: the model is asked how much a name should out-rank its own momentum.

    Both terms are within-cutoff quantities, so the value is the same whether it
    is computed on a slice or on the panel — but it is computed on the slice, and
    the panel never carries a `y_resid` column for a scorer to stumble into.
    """
    frame = _simpson_panel()
    columns = ["z__ret_12_1"]
    slice_frame, target = ladder_v2_2._training_frame(frame, columns,
                                                     ladder_v2_2.RESID_TARGET)
    assert target == ladder_v2_2.RESID_TARGET == "y_resid"
    assert "y_resid" not in frame.columns

    resid = slice_frame["y_resid"].dropna()
    assert resid.between(-1.0, 1.0).all()
    expected = frame["target_rank"] - carrier.rank_pct(frame, "ret_12_1")
    assert float((slice_frame["y_resid"] - expected).abs().max()) == pytest.approx(0.0)

    # Computed on half the cutoffs, it is unchanged on those cutoffs.
    half = sorted(frame.index.get_level_values(0).unique())[:30]
    partial, _ = ladder_v2_2._training_frame(
        frame[frame.index.get_level_values(0).isin(pd.DatetimeIndex(half))],
        columns, ladder_v2_2.RESID_TARGET)
    assert float((partial["y_resid"] - expected.reindex(partial.index)).abs().max()) == 0.0


# ---------------------------------- §4 the rungs and the grid can never be chosen


def test_the_rungs_and_the_grid_are_not_arms():
    """§4: "none of them may be selected, gated on, or promoted to an arm".

    §6.4 puts the price on it: promoting one would make the Holm family 5 instead
    of 3. `select_arm` reads `is_arm`, so the guard is structural.
    """
    for spec in ladder_v2_2.RUNGS + ladder_v2_2.GRID:
        assert not spec.arm, spec.name

    records = {
        "S1-A": {"is_arm": False, "ic": {"mean": 0.99}},
        "raw_level__rank": {"is_arm": False, "ic": {"mean": 0.98}},
        "V2.2-A": {"is_arm": True, "ic": {"mean": 0.01}},
    }
    eligible = {name: {"eligible": True} for name in records}
    assert ladder_v2_2.select_arm(records, eligible) == "V2.2-A"


def test_the_one_feature_rungs_match_their_arms_carrier():
    """§4.1: each rung is its arm's carrier applied to `ret_12_1` alone.

    A rung that differed from its arm in anything but the column count would not
    diagnose that arm's carrier, and G1 would be gating on the wrong thing.
    """
    arms = {arm.name: arm for arm in ladder_v2_2.ARMS}
    rungs = {rung.name: rung for rung in ladder_v2_2.RUNGS}
    assert ladder_v2_2.RUNG_FOR_ARM == {"V2.2-A": "S1-A", "V2.2-B": "S1-B",
                                        "V2.2-C": "S1-C"}
    for arm_name, rung_name in ladder_v2_2.RUNG_FOR_ARM.items():
        arm, rung = arms[arm_name], rungs[rung_name]
        assert rung.columns == (ladder_v2_2.Z_BASE,), rung_name
        assert rung.train_target == arm.train_target, rung_name
        assert rung.combination == arm.combination, rung_name
        assert rung.lam == arm.lam, rung_name
        assert rung.monotone == arm.monotone, rung_name


def test_the_grid_is_the_two_by_two_the_preregistration_draws():
    """§4.2: four cells decomposing the collapse into an input and a target effect."""
    cells = {spec.name: spec for spec in ladder_v2_2.GRID}
    assert set(cells) == {"raw_level__winsorised_level", "raw_level__rank",
                          "z_rank__winsorised_level"}
    assert ladder_v2_2.GRID_FOURTH_CELL == "z_rank__rank"

    assert cells["raw_level__winsorised_level"].columns == (ladder_v2_2.BASE,)
    assert cells["raw_level__winsorised_level"].train_target == "target_train"
    assert cells["raw_level__rank"].columns == (ladder_v2_2.BASE,)
    assert cells["raw_level__rank"].train_target == "target_rank"
    assert cells["z_rank__winsorised_level"].columns == (ladder_v2_2.Z_BASE,)
    assert cells["z_rank__winsorised_level"].train_target == "target_train"

    # The top-left cell IS V2.1-A: same column, same target, same fitter.
    v2_1_a = ladder.ARMS_BY_NAME["V2.1-A"]
    assert cells["raw_level__winsorised_level"].columns == v2_1_a.columns
    assert cells["raw_level__winsorised_level"].train_target == v2_1_a.train_target


def test_the_grid_reuses_s1_a_for_its_fourth_cell():
    """The fourth cell is `S1-A` by construction, so re-fitting it would be theatre."""
    s1_a = {rung.name: rung for rung in ladder_v2_2.RUNGS}["S1-A"]
    assert s1_a.columns == (ladder_v2_2.Z_BASE,)
    assert s1_a.train_target == "target_rank"
    assert s1_a.combination == "prediction" and s1_a.monotone is None
    assert ladder_v2_2.GRID_FOURTH_CELL not in {spec.name for spec in ladder_v2_2.GRID}


# ---------------------------------------- §6 eligibility, selection and the gate


def test_g1_rejects_a_v2_1_a_shaped_carrier_and_admits_discretisation_loss():
    """§6.1: -0.005 tolerates the ties a histogram learner makes, not a sign flip.

    The threshold's justification is arithmetic that was fixed before the fact:
    S0 is about +0.021, so -0.005 concedes a quarter of the factor to
    discretisation. V2.1-A lost -0.0206 — 98% of it.
    """
    assert ladder_v2_2.G1_FLOOR == -0.005
    index = pd.date_range("2016-01-08", periods=200, freq="W")
    s0 = pd.Series(0.021, index=index)

    ok = ladder_v2_2.carrier_integrity(pd.Series(0.018, index=index), s0, "S1-A")
    assert ok["passed"] and ok["value"] == pytest.approx(-0.003)

    v2_1_a_shaped = ladder_v2_2.carrier_integrity(pd.Series(0.0005, index=index),
                                                  s0, "S1-A")
    assert not v2_1_a_shaped["passed"]

    just_under = ladder_v2_2.carrier_integrity(pd.Series(0.0159, index=index), s0, "S1-A")
    assert not just_under["passed"]


def test_a_carrier_defective_arm_cannot_be_selected_however_good_its_ic():
    """§6.1: "not eligible for selection whatever its IC". Including when it leads."""
    records = {"V2.2-A": {"is_arm": True, "ic": {"mean": 0.99}},
               "V2.2-B": {"is_arm": True, "ic": {"mean": 0.01}},
               "V2.2-C": {"is_arm": True, "ic": {"mean": 0.02}}}
    eligible = {"V2.2-A": {"eligible": False}, "V2.2-B": {"eligible": True},
                "V2.2-C": {"eligible": True}}
    assert ladder_v2_2.select_arm(records, eligible) == "V2.2-C"

    none_eligible = {name: {"eligible": False} for name in records}
    assert ladder_v2_2.select_arm(records, none_eligible) is None


def test_too_few_scored_cutoffs_is_carrier_defective_not_a_smaller_sample():
    """§6.1: arm C's anticipated collapse must not become a comparison on 40 dates."""
    assert ladder_v2_2.MIN_SCORED_CUTOFFS == 200
    integrity = {"passed": True, "value": -0.001, "rung": "S1-C",
                 "ci": [-0.01, 0.01], "n_cutoffs": 255,
                 "criterion": "…", "threshold": ">= -0.005"}
    assert ladder_v2_2.eligibility("V2.2-C", integrity, 255)["eligible"]
    thin = ladder_v2_2.eligibility("V2.2-C", integrity, 150)
    assert not thin["eligible"] and "carrier-defective" in thin["consequence"]


def test_selection_breaks_ties_toward_the_structurally_safer_arm():
    """§6.2: B before C before A — B's bound is provable, A's is not guaranteed."""
    assert ladder_v2_2.SAFETY_ORDER == ("V2.2-B", "V2.2-C", "V2.2-A")
    records = {name: {"is_arm": True, "ic": {"mean": 0.03}}
               for name in ("V2.2-A", "V2.2-B", "V2.2-C")}
    eligible = {name: {"eligible": True} for name in records}
    assert ladder_v2_2.select_arm(records, eligible) == "V2.2-B"

    del records["V2.2-B"]
    assert ladder_v2_2.select_arm(records, eligible) == "V2.2-C"


class _FakeAssessment:
    """Enough of `protocol.Assessment` for the gate. The gate reads `versus` only."""

    def __init__(self, name: str, **series: pd.Series):
        self.name = name
        self.versus = {key: stats.Series(key, values, null=0.0)
                       for key, values in series.items()}


def _diff(mean: float, n: int = 255, share_positive: float = 1.0,
          second_half: float | None = None) -> pd.Series:
    """A per-cutoff paired difference with a chosen mean, breadth and second half.

    `share_positive < 1` builds the shape G4 exists to reject: a real positive mean
    earned on a minority of dates, with a small loss on the rest. The mean is held
    at `mean` while the breadth moves, so G2 and G4 can be separated.
    """
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
    if second_half is not None:
        tail = values[n // 2:]
        values[n // 2:] = tail + (second_half - tail.mean())
    return pd.Series(values, index=index)


def test_the_gate_requires_both_benchmarks():
    """§6.3: B3 is a gate in V2.2, where V2.1 only reported it.

    A three-line rule with no fitted parameters scored +0.02836 on V2.1's
    development set with the only benchmark CI excluding zero. A study that will
    not measure itself against the strongest free alternative is not asking the
    question §0 asks, so beating 12-1 momentum alone is not enough.
    """
    assert ladder_v2_2.GATE_BENCHMARKS == ("b1_momentum_12_1", "b3_regime_switched")
    assert {b.key for b in protocol.BENCHMARKS} >= set(ladder_v2_2.GATE_BENCHMARKS)
    # And B3 gates *here* even though the V2.1 protocol object says otherwise.
    assert not [b for b in protocol.BENCHMARKS if b.key == "b3_regime_switched"][0].gate

    beats_b1_only = _FakeAssessment("V2.2-B", b1_momentum_12_1=_diff(0.08),
                                   b3_regime_switched=_diff(-0.02))
    verdict = ladder_v2_2.gate(beats_b1_only)
    assert verdict["gates"]["G2_beats_12_1_momentum"]["passed"]
    assert not verdict["gates"]["G3_beats_regime_switched_momentum"]["passed"]
    assert not verdict["passed"]
    assert "gate is closed" in verdict["consequence"]

    both = _FakeAssessment("V2.2-B", b1_momentum_12_1=_diff(0.08),
                           b3_regime_switched=_diff(0.07))
    assert ladder_v2_2.gate(both)["passed"]


def test_the_gate_needs_the_interval_not_just_the_sign():
    """§9: "lowering a threshold" is a named forbidden response. So it gets a test.

    V2.1-D's number against momentum was +0.013 with a CI of [-0.019, +0.050] —
    positive and useless. That shape must not pass.
    """
    index = pd.date_range("2016-01-08", periods=255, freq="W")
    rng = np.random.default_rng(2)
    wide = pd.Series(0.013 + rng.normal(scale=0.25, size=255), index=index)
    verdict = ladder_v2_2.gate(_FakeAssessment(
        "V2.2-D", b1_momentum_12_1=wide, b3_regime_switched=wide))
    assert verdict["gates"]["G2_beats_12_1_momentum"]["value"] > 0
    assert verdict["gates"]["G2_beats_12_1_momentum"]["ci"][0] < 0
    assert not verdict["gates"]["G2_beats_12_1_momentum"]["passed"]


def test_breadth_and_stability_can_fail_on_their_own():
    """§6.3 G4 and G5 exist to reject an edge earned on a handful of extreme dates."""
    assert ladder_v2_2.BREADTH_FLOOR == 0.55

    narrow = _FakeAssessment("V2.2-B", b1_momentum_12_1=_diff(0.08, share_positive=0.3),
                             b3_regime_switched=_diff(0.08, share_positive=0.3))
    gates = ladder_v2_2.gate(narrow)["gates"]
    assert gates["G2_beats_12_1_momentum"]["passed"]
    assert not gates["G4_breadth"]["passed"]

    drifts = _FakeAssessment("V2.2-B", b1_momentum_12_1=_diff(0.20, second_half=-0.02),
                             b3_regime_switched=_diff(0.20, second_half=-0.02))
    gates = ladder_v2_2.gate(drifts)["gates"]
    assert not gates["G5_stability"]["passed"]
    assert gates["G5_stability"]["value"]["vs_b1"]["second"]["mean"] < 0


def test_the_lambda_curve_is_reported_and_never_promoted():
    """§3.2: if 0.25 or 1.00 scores better, that is reported and 0.50 stays the arm."""
    assert ladder_v2_2.LAMBDA == 0.50
    assert set(ladder_v2_2.LAMBDA_CURVE) == {0.00, 0.25, 0.50, 1.00}
    # Exactly one point on the curve is the arm, and it is the pre-registered one.
    assert sum(lam == ladder_v2_2.LAMBDA for lam in ladder_v2_2.LAMBDA_CURVE) == 1
    # A lambda variant is not in ARMS, so it cannot enter the Holm family.
    assert {arm.lam for arm in ladder_v2_2.ARMS} == {0.0, ladder_v2_2.LAMBDA}
    assert [arm.lam for arm in ladder_v2_2.ARMS if arm.combination == "blend"] == [0.50]


# --------------------------------------------------------------- §1 / §7 the seal


def test_the_ladder_reads_its_cutoffs_through_development_only():
    """§1.2: the one call that slices *and* checks. `slice_cutoffs` alone would not."""
    source = (REPO / "alpha" / "ladder_v2_2.py").read_text(encoding="utf-8")
    assert "examset.development_only(panel, exam_set)" in source
    assert "exam_set.cutoffs" not in source, (
        "ladder_v2_2.py names the exam cutoffs; it has no business knowing them")
    assert ".slice_cutoffs(" not in source, (
        "a bare slice_cutoffs call takes a keep-list and would not complain if the "
        "wrong list were handed to it — that is exactly what development_only fixes")


def test_the_v2_1_exam_is_untouched():
    """§1.1: the digest is unchanged and the prediction file does not exist."""
    assert not (ladder_v2_2.OUT_DIR / "v2_1_exam_predictions.json").exists()
    if examset.PATH.exists():
        assert examset.load().digest == V2_1_EXAM_DIGEST
    assert not (REPO / "alpha" / "out" / "v2_2_exam_predictions.json").exists()


def test_the_ladder_refuses_to_run_if_an_exam_prediction_exists(tmp_path, monkeypatch):
    """A file that must not come into existence gets a check, not a comment."""
    monkeypatch.setattr(ladder_v2_2, "OUT_DIR", tmp_path)
    (tmp_path / "v2_1_exam_predictions.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="must not come into existence"):
        ladder_v2_2.main([])


def test_v2_2_did_not_edit_the_earlier_records():
    """V2, the V2.1 protocol and the V2.1 ladder are finished documents."""
    for name in ("PREREGISTRATION.md", "V2_1_PREREGISTRATION.md",
                 "V2_1_LADDER_PREREGISTRATION.md", "V2_1_LADDER_REPORT.md"):
        assert "V2.2" not in (REPO / "alpha" / name).read_text(encoding="utf-8"), name

    assert [arm.name for arm in ladder.ARMS] == ["V2.1-A", "V2.1-B", "V2.1-C", "V2.1-D"]
    assert ladder.FAMILY_SIZE == 4
    assert ladder.JSON_PATH.name == "v2_1_development.json"
    assert ladder_v2_2.JSON_PATH.name == "v2_2_development.json"
    assert ladder_v2_2.JSON_PATH != ladder.JSON_PATH

    # `protocol.py` still describes the V2.1 hierarchy, B3 included as a report.
    assert "V2.2" not in (REPO / "alpha" / "protocol.py").read_text(encoding="utf-8")


def test_the_preregistration_exists_and_fixes_what_it_says_it_fixes():
    """The document is the experiment. If it stopped saying these things, stop."""
    doc = (REPO / "alpha" / "V2_2_PREREGISTRATION.md").read_text(encoding="utf-8")
    assert V2_1_EXAM_DIGEST in doc
    assert "k = 3" in doc
    assert "lambda = 0.50" in doc.replace("λ", "lambda")
    assert ">= 200 development cutoffs" in doc.replace("≥", ">=")
    assert "carrier-defective" in doc
    for forbidden in ("lowering a threshold", "re-choosing", "adding a fourth arm",
                      "promoting a diagnostic rung to an arm"):
        assert forbidden in doc, forbidden

    # The document was accepted before the first fit, and its two amendments were
    # made in that same window. An amendment made after a result is a moved target,
    # so the timing claim is part of the document rather than a note beside it.
    assert "DRAFT — awaiting review" not in doc
    assert "ACCEPTED 2026-08-08, before the first fit" in doc
    assert "## 12. Amendments, and when they were made" in doc
    assert "measured and reported" in doc, "§3.3's A2 clarification is missing"


# ------------------------------------------------------------------ §8 production


def test_v2_2_cannot_move_production():
    """§1.4: weight 0, action HOLD, `adapter.py` not modified, whatever V2.2 says."""
    evidence = adapter.load_evidence(pathlib.Path("nothing-here.json"))
    assert evidence.weight == 0.0 and not evidence.passed_all_criteria
    action, _reason = adapter.decide(0.9, 0.99, evidence, regime="BULL_TREND",
                                    historical_spread=0.05)
    assert action == adapter.Action.HOLD

    # Structural rather than textual: if the ladder imported the production layer,
    # the module would carry the attribute. It does not import it, so it cannot
    # call it, and no amount of prose in the record can change that.
    assert not hasattr(ladder_v2_2, "adapter"), (
        "ladder_v2_2.py imports the production layer; §1.4 says it must not")
    assert "adapter" not in {name for name in dir(ladder_v2_2)}


def test_the_gate_passing_does_not_open_the_exam():
    """§8: "the exam is still not opened", even when every gate holds."""
    both = _FakeAssessment("V2.2-B", b1_momentum_12_1=_diff(0.08),
                           b3_regime_switched=_diff(0.07))
    verdict = ladder_v2_2.gate(both)
    assert verdict["passed"]
    assert "stays sealed" in verdict["consequence"]
    assert "V2_2_EXAM_DECISION.md" in verdict["consequence"]


# ------------------------------------------------- against the frozen V2.2 record


@needs_development
def test_the_frozen_record_reports_every_section_5_diagnostic():
    """§5: all seven measurements, for every arm and every rung, before any IC.

    Arm C's inversion count is *reported* here rather than asserted to be zero —
    see `test_the_monotone_constraint_binds_only_where_it_can` for why the
    35-feature arm carries no such guarantee. `S1-C`'s is asserted, because there
    the constraint is unconditional.
    """
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    everything = {**record["arms"], **record["rungs"]}
    assert {"V2.2-A", "V2.2-B", "V2.2-C", "S1-A", "S1-B", "S1-C"} <= set(everything)

    for name, entry in everything.items():
        summary = entry["carrier_diagnostics"]
        for key in ("spearman_vs_factor", "inversions", "runs_vs_factor",
                    "distinct_scores", "cross_section", "is_univariate_in_factor",
                    "collapsed_cutoffs", "n_cutoffs"):
            assert key in summary, f"{name} is missing diagnostic {key}"
        assert entry["scored_against"] == "alpha_5d", name

    assert everything["S1-C"]["carrier_diagnostics"]["inversions"]["total"] == 0


@needs_development
def test_the_frozen_record_reproduces_v2_1_a_in_the_grid():
    """§4.2's top-left cell IS V2.1-A, so it has to come out at V2.1-A's number.

    This is the one check that crosses a module boundary: a different panel slice,
    a different cutoff list or a different fitter would show up here and nowhere
    else.
    """
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    grid = record["carrier_grid"]
    if grid["frozen_v2_1_a_mean_ic"] is None:
        pytest.skip("the V2.1 development record is not on this machine")
    assert grid["reproduces_frozen_v2_1_a"], (
        f"grid top-left {grid['cells']['raw_level__winsorised_level']} vs frozen "
        f"V2.1-A {grid['frozen_v2_1_a_mean_ic']}")
    assert set(grid["cells"]) == {"raw_level__winsorised_level", "raw_level__rank",
                                  "z_rank__winsorised_level", "z_rank__rank"}


@needs_development
def test_s0_reproduced_benchmark_one_on_the_real_panel():
    """§2.2, checked against what was written rather than against the code."""
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    assert record["s0"]["rank_identical_to_benchmark_1"]
    assert (record["s0"]["max_abs_ic_difference"] or 0.0) < 1e-12
    assert record["s0"]["n_cutoffs"] >= ladder_v2_2.MIN_SCORED_CUTOFFS


@needs_development
def test_the_lambda_bound_holds_on_the_frozen_predictions():
    """§11.4 and §3.2 criterion 5: the bound, asserted on real output.

    Not on synthetic data and not in the abstract — on the numbers the study
    actually produced, because that is the artefact a reader will quote.
    """
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    curves = record["lambda_sensitivity"]
    assert curves, "no lambda curve was recorded"
    for name, curve in curves.items():
        for lam, entry in curve.items():
            if float(lam) <= ladder_v2_2.LAMBDA:
                assert entry["order_bound_violations"] == 0, f"{name} @ lambda={lam}"

    if not DEV_PICKLE.exists() or not PANEL_PATH.exists():
        pytest.skip("the frozen predictions or the panel are not on this machine")

    blob = pd.read_pickle(DEV_PICKLE)
    if "V2.2-B" not in blob["final_scores"]:
        pytest.skip("arm B did not run")
    panel, _development, _exam = build_panel.load()
    base = carrier.centred_rank(examset.development_only(panel).frame, "ret_12_1")
    final = blob["final_scores"]["V2.2-B"]
    assert carrier.order_bound_violations(base.reindex(final.index), final,
                                          ladder_v2_2.LAMBDA) == 0


@needs_development
@needs_exam_set
def test_the_frozen_v2_2_record_never_touched_an_exam_cutoff():
    """The invariant, checked against what was written, not against the code."""
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    exam_set = examset.load()

    assert record["exam_set_digest"] == exam_set.digest == V2_1_EXAM_DIGEST
    assert record["development_cutoffs"] == len(exam_set.development)
    assert record["family_size"] == ladder_v2_2.FAMILY_SIZE == 3
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
    """§1.4: no result of this stage moves production, whatever it says."""
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    assert record["production_weight"] == 0.0
    for entry in {**record["arms"], **record["rungs"]}.values():
        assert entry["production_weight"] == 0.0
        # A development slice has no gates. The key name has to say so.
        assert "gates_passed" not in entry
        assert "diagnostic_gates_passed" in entry


@needs_development
def test_the_frozen_record_names_its_own_multiplicity_family():
    """§6.4: Holm over the k = 3 arms. Rungs and grid cells carry no p-value."""
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    holm = record["holm_bonferroni_on_development"]
    assert set(holm) <= {arm.name for arm in ladder_v2_2.ARMS}
    assert set(holm) == set(record["arms"])
    for name in record["rungs"]:
        assert name not in holm, f"{name} entered the multiplicity family"
