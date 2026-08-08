"""Tests for the V2.1 research ladder — the arms, the gate, and the seal.

`test_alpha_v2_1.py` tests the *protocol*: is the exam set independent, frozen
and unreachable from development. This file tests the *ladder* that runs against
it: are the arms the ones that were pre-registered, does the ladder's one
load-bearing structural claim actually hold, and does a closed gate really keep
the exam shut.

The claim in the third of those is worth stating, because it is what the whole
A-vs-B contrast rests on. 26 of V2's 35 "context" columns take a single value for
the entire cross-section at a cutoff. So an arm given `ret_12_1` plus only those
columns can, within one cutoff, produce nothing but a **univariate function of
`ret_12_1`** — and Spearman IC is invariant to monotone transforms, so such an
arm can differ from 12-1 momentum in exactly one way: by bending that function
out of monotonicity. That is checked here against the real panel, not asserted.

Two kinds of test, as in the sibling file: hermetic ones that build what they
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

from alpha import (build_panel, develop, examset, ladder, models,  # noqa: E402
                   protocol, v2_1_exam)

PANEL_PATH = build_panel.PANEL_PATH
DEV_PATH = ladder.JSON_PATH
DEV_PICKLE = ladder.PICKLE_PATH

needs_panel = pytest.mark.skipif(
    not PANEL_PATH.exists(), reason="alpha/out/panel.pkl has not been built")
needs_development = pytest.mark.skipif(
    not DEV_PATH.exists(), reason="alpha/out/v2_1_development.json has not been written")
needs_exam_set = pytest.mark.skipif(
    not examset.PATH.exists(), reason="v2_1_exam_set.json is not frozen on this machine")


# ------------------------------------------------- §3 the arms are pre-registered


def test_the_ladder_is_the_four_arms_the_preregistration_names():
    """Which arms exist, and their order, is itself a pre-registered decision."""
    assert [arm.name for arm in ladder.ARMS] == ["V2.1-A", "V2.1-B", "V2.1-C", "V2.1-D"]
    assert ladder.FAMILY_SIZE == len(ladder.ARMS) == 4

    by_name = ladder.ARMS_BY_NAME
    assert by_name["V2.1-A"].columns == ("ret_12_1",)
    assert by_name["V2.1-B"].columns == ladder.MOMENTUM + ladder.MARKET_CONTEXT
    assert by_name["V2.1-C"].columns == by_name["V2.1-D"].columns

    # A -> B -> C is strictly nested: a ladder whose rungs are not nested cannot
    # attribute a delta to the columns that were added.
    for lower, upper in (("V2.1-A", "V2.1-B"), ("V2.1-B", "V2.1-C")):
        assert set(by_name[lower].columns) < set(by_name[upper].columns)

    # D differs from C in the training target and in nothing else.
    assert by_name["V2.1-D"].train_target == "target_rank"
    assert by_name["V2.1-C"].train_target == "target_train"
    for arm in ladder.ARMS:
        assert len(set(arm.columns)) == len(arm.columns), f"{arm.name} repeats a column"


@needs_development
def test_every_arm_is_scored_on_alpha_5d_whatever_it_trained_on():
    """Changing the model is allowed; changing the yardstick is not.

    V2 applied this to V2-F and it applies to V2.1-D for the same reason: a
    metric that moves with the arm cannot rank arms. Asserted against what was
    written, because that is the thing a later reader will quote.
    """
    arms = json.loads(DEV_PATH.read_text(encoding="utf-8"))["arms"]
    assert {a["train_target"] for a in arms.values()} == {"target_train", "target_rank"}
    for name, arm in arms.items():
        assert arm["scored_against"] == "alpha_5d", name


def test_the_excluded_relative_tier_stays_excluded():
    """§3.3's exclusions are as pre-registered as its inclusions.

    V2 measured the 47-column relative tier over 423 development cutoffs and mean
    IC moved +0.00837 -> +0.00846. Re-adding it to see what happens is the
    feature-generation move the directive rules out, so the ladder must not carry
    a single column from it.
    """
    for arm in ladder.ARMS:
        for column in arm.columns:
            assert develop.tier_of(column) != "relative", (
                f"{arm.name} carries {column}, which is in the V2 relative tier")
            assert not column.endswith(develop.RELATIVE_SUFFIXES)
            assert column not in develop.RELATIVE_EXTRA


def test_arm_b_carries_no_stock_level_column():
    """The A-vs-B contrast exists to isolate *market* context. It has to be isolated.

    V2's `CONTEXT_PREFIXES` bundles `overnight_`/`intraday_` with market context.
    Those are per-symbol quantities. If they were in B, the "market context only"
    arm would quietly carry stock-level information.
    """
    assert not [c for c in ladder.MARKET_CONTEXT
                if c.startswith(("overnight_", "intraday_"))]
    stock_level_in_c = set(ladder.STOCK_LEVEL) - set(ladder.MARKET_CONTEXT)
    assert {"overnight_mean_20d", "intraday_mean_20d", "overnight_share_60d"} <= stock_level_in_c


# ----------------------------------------- §2 the mechanism, against the real panel


@needs_panel
@needs_exam_set
def test_market_context_is_constant_within_a_cutoff():
    """§2's premise, measured. Every B column but `ret_12_1` is one number a day.

    This is what makes arm B a test of "does context say when to flip momentum"
    rather than a test of "does context rank stocks". If a future feature lands
    in `MARKET_CONTEXT` that varies across the cross-section, arm B silently
    becomes a different experiment and this fails.
    """
    panel, _development, _exam = build_panel.load()
    sample = sorted(panel.cutoffs)[-40:]
    block = panel.frame[panel.frame.index.get_level_values(0).isin(pd.DatetimeIndex(sample))]

    widths = block.groupby(level=0).size()
    assert widths.min() > 100, "too thin a cross-section to say anything about constancy"

    distinct = block[list(ladder.MARKET_CONTEXT)].groupby(level=0).nunique().max()
    varying = sorted(distinct[distinct > 1].index)
    assert not varying, f"these MARKET_CONTEXT columns vary within a cutoff: {varying}"

    # The contrast: the stock-level block C adds must vary, or C is not a rung.
    stock = block[list(ladder.STOCK_LEVEL)].groupby(level=0).nunique().max()
    assert (stock > 1).all(), f"constant stock-level columns: {sorted(stock[stock <= 1].index)}"


@needs_development
@needs_panel
@needs_exam_set
def test_arms_a_and_b_are_univariate_functions_of_momentum_and_c_is_not():
    """§2's consequence, measured on the frozen development predictions.

    Sort a cutoff's rows by `ret_12_1`. If the prediction is a function of
    `ret_12_1` alone it is piecewise constant along that ordering, so the number
    of *runs* equals the number of distinct predicted values — no interleaving is
    possible. Arms A and B must satisfy that identity; arms C and D must not,
    because a multivariate function of 35 columns separates names that share a
    momentum bin.
    """
    blob = pd.read_pickle(DEV_PICKLE)
    predictions = blob["predictions"]
    if not {"V2.1-A", "V2.1-B", "V2.1-C"} <= set(predictions):
        pytest.skip("the development record does not hold all of A, B and C")

    panel, _development, _exam = build_panel.load()
    momentum = examset.development_only(panel).frame["ret_12_1"]

    def profile(arm: str) -> tuple[pd.Series, pd.Series, pd.Series]:
        frame = pd.DataFrame({"p": predictions[arm]})
        frame["m"] = momentum.reindex(frame.index)
        frame = frame.dropna()
        grouped = frame.groupby(level=0)
        runs = grouped.apply(
            lambda b: 1 + int((np.diff(b.sort_values("m")["p"].to_numpy()) != 0).sum()))
        return grouped.size(), grouped["p"].nunique(), runs

    for arm in ("V2.1-A", "V2.1-B"):
        width, distinct, runs = profile(arm)
        assert (runs == distinct).all(), f"{arm} is not a step function of ret_12_1"
        assert (distinct < width).all(), f"{arm} separates names that share a momentum bin"

    width, distinct, runs = profile("V2.1-C")
    assert (distinct > 0.8 * width).mean() > 0.95, "arm C did not become multivariate"


# -------------------------------------------------------- §5 selection and the gate


def _record(**ic_means) -> dict:
    """A minimal development record — enough for selection and the gate to bite."""
    out = {}
    for name, (mean, low) in ic_means.items():
        out[name] = {
            "ic": {"mean": mean},
            "criteria": {"5_beats_12_1_momentum": {"value": mean - 0.02,
                                                   "ci": [low, low + 0.06]}},
            "n_cutoffs": 255,
        }
    return out


def test_arm_a_is_never_the_exam_arm():
    """§5.1: A is Benchmark 1 up to non-monotonicity, so it cannot pass criterion 5.

    Excluded by pre-registration rather than by its number — the exclusion has to
    hold in the branch where A has the best development IC, which is exactly the
    branch where the temptation exists.
    """
    records = _record(**{"V2.1-A": (0.99, 0.5), "V2.1-B": (0.02, 0.0),
                         "V2.1-C": (0.01, 0.0), "V2.1-D": (0.005, 0.0)})
    assert ladder.select_exam_arm(records) == "V2.1-B"
    assert not ladder.ARMS_BY_NAME["V2.1-A"].candidate
    assert all(ladder.ARMS_BY_NAME[n].candidate for n in ("V2.1-B", "V2.1-C", "V2.1-D"))


def test_selection_takes_the_best_candidate_and_breaks_ties_toward_simplicity():
    records = _record(**{"V2.1-B": (0.01, 0.0), "V2.1-C": (0.03, 0.0), "V2.1-D": (0.02, 0.0)})
    assert ladder.select_exam_arm(records) == "V2.1-C"

    tied = _record(**{"V2.1-B": (0.03, 0.0), "V2.1-C": (0.03, 0.0), "V2.1-D": (0.03, 0.0)})
    assert ladder.select_exam_arm(tied) == "V2.1-B"

    assert ladder.select_exam_arm(_record(**{"V2.1-A": (0.5, 0.4)})) is None


def test_the_gate_needs_the_interval_not_just_the_sign():
    """§5.2: "> 0" is not the threshold. "> 0 and the CI excludes 0" is.

    Relaxing it to a positive mean is named in the pre-registration as a
    forbidden response to a closed gate, so it gets a test rather than a promise.
    """
    positive_but_wide = {"criteria": {"5_beats_12_1_momentum":
                                      {"value": 0.013, "ci": [-0.019, 0.050]}},
                         "n_cutoffs": 255}
    assert not ladder.gate(positive_but_wide)["passed"]

    clears = {"criteria": {"5_beats_12_1_momentum":
                           {"value": 0.013, "ci": [0.002, 0.026]}},
              "n_cutoffs": 255}
    assert ladder.gate(clears)["passed"]

    negative = {"criteria": {"5_beats_12_1_momentum":
                             {"value": -0.02, "ci": [-0.05, -0.001]}},
                "n_cutoffs": 255}
    assert not ladder.gate(negative)["passed"]

    assert not ladder.gate({"criteria": {}})["passed"]


def test_the_gate_is_measured_against_benchmark_one():
    """Swapping in an easier benchmark is the other forbidden response."""
    assert ladder.GATE_BENCHMARK == "b1_momentum_12_1"
    assert protocol.BENCHMARKS[0].key == ladder.GATE_BENCHMARK
    assert "12-1 momentum" in ladder.gate({"criteria": {}})["criterion"]


# ------------------------------------------------------------------ §7 the seal


def test_the_exam_refuses_to_open_while_the_gate_is_closed(tmp_path, monkeypatch):
    """A closed gate is the result, not a suggestion.

    The failure mode this guards is not malice; it is a later run of
    `v2_1_exam predict` by someone who has forgotten why the exam was sealed.
    """
    path = tmp_path / "v2_1_development.json"
    path.write_text(json.dumps({"exam_configuration": {
        "arm": "V2.1-D", "exam_may_be_opened": False,
        "gate": {"criterion": "vs Benchmark 1", "threshold": "> 0, CI excludes 0",
                 "value": 0.013, "ci": [-0.019, 0.050], "n_cutoffs": 255}}}),
        encoding="utf-8")
    monkeypatch.setattr(ladder, "JSON_PATH", path)

    with pytest.raises(SystemExit, match="gate is CLOSED"):
        v2_1_exam._frozen_configuration()

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["exam_configuration"]["exam_may_be_opened"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert v2_1_exam._frozen_configuration()["arm"] == "V2.1-D"


def test_predict_refuses_to_overwrite_a_frozen_prediction(tmp_path, monkeypatch):
    """Regenerating a prediction once its outcome is known is the cardinal failure."""
    path = tmp_path / "v2_1_exam_predictions.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(v2_1_exam, "PREDICTIONS_PATH", path)
    monkeypatch.setattr(v2_1_exam, "OUT_DIR", tmp_path)
    with pytest.raises(SystemExit, match="already exists"):
        v2_1_exam.predict()


def test_the_exam_predictions_payload_can_carry_no_outcome():
    """Named columns, asserted at write time — see `v2_1_exam.OUTCOME_COLUMNS`."""
    for column in ("alpha_5d", "target_train", "target_rank", "quintile",
                   "asset_return", "horizon_end"):
        assert column in v2_1_exam.OUTCOME_COLUMNS

    source = (REPO / "alpha" / "v2_1_exam.py").read_text(encoding="utf-8")
    assert "forward_return" not in source
    assert "raise RuntimeError" in source


def test_the_ladder_reads_its_cutoffs_through_development_only():
    """§7: the one call that slices *and* checks. `slice_cutoffs` alone would not."""
    source = (REPO / "alpha" / "ladder.py").read_text(encoding="utf-8")
    assert "examset.development_only(panel, exam_set)" in source
    assert "exam_set.cutoffs" not in source, (
        "ladder.py names the exam cutoffs; it has no business knowing them")


@needs_development
@needs_exam_set
def test_the_frozen_development_record_never_touched_an_exam_cutoff():
    """The invariant, checked against what was actually written, not the code."""
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    exam_set = examset.load()

    assert record["exam_set_digest"] == exam_set.digest
    assert record["development_cutoffs"] == len(exam_set.development)
    assert record["family_size"] == ladder.FAMILY_SIZE

    blob = pd.read_pickle(DEV_PICKLE)
    exam_dates = set(exam_set.cutoffs)
    for arm, series in blob["ic_series"].items():
        scored = set(pd.DatetimeIndex(series.index))
        assert not scored & exam_dates, f"{arm} scored an exam cutoff"
        assert scored <= set(exam_set.development)


# ------------------------------------------------------------------ §8 production


@needs_development
def test_the_ladder_left_production_at_zero():
    """§8: no result of this stage moves production, whatever it says."""
    record = json.loads(DEV_PATH.read_text(encoding="utf-8"))
    assert record["production_weight"] == 0.0
    for arm in record["arms"].values():
        assert arm["production_weight"] == 0.0
        # A development slice has no gates. The key name says so.
        assert "gates_passed" not in arm
        assert "diagnostic_gates_passed" in arm


def test_v2_1_ladder_did_not_edit_the_earlier_records():
    """V2 and the V2.1 protocol are finished documents; the ladder is a new one."""
    v2 = (REPO / "alpha" / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "V2.1" not in v2

    # §8 of the protocol document is what *required* a separate ladder
    # pre-registration. It sketches the arms and explicitly declines to fix
    # them, and it must still say so — an edit that quietly pre-registered the
    # ladder there, after the fact, is the failure this catches.
    protocol_doc = (REPO / "alpha" / "V2_1_PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "is **not** pre-registered here" in protocol_doc
    assert "V2.1-A" in protocol_doc and "family size" in protocol_doc
    for column in ladder.MARKET_CONTEXT[:5] + ladder.STOCK_LEVEL[:3]:
        assert column not in protocol_doc, (
            f"V2_1_PREREGISTRATION.md now names the arm column {column}")

    assert (REPO / "alpha" / "V2_1_LADDER_PREREGISTRATION.md").exists()
    # V2's own ladder still runs its own arms.
    assert [e.name for e in develop.UNGATED] == ["V2-A", "V2-B", "V2-E", "V2-F"]
    assert models.MODEL_A_PARAMS["max_iter"] == 300, "the learner was re-tuned"
    assert models.MODEL_A_PARAMS["learning_rate"] == 0.05
