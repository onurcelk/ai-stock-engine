"""Tests for the Single-Name Phase 1 harness.

Five categories, in the order the directive's SOFTWARE REQUIREMENTS list them:

* **Frozen constants** — `singlename_config.py` against
  `alpha/SINGLE_NAME_PREREGISTRATION.md`. If a constant drifts, the study is
  void, and this is the cheapest possible way to notice.
* **Point-in-time and leakage** — the label door, the purge/embargo boundary,
  and the counterpart of `test_validation.py::test_future_cannot_change_the_verdict`:
  rewrite every outcome the harness was not entitled to see and demand a
  bit-identical prediction.
* **Prediction logic** — probability bounds, missing features, abstention,
  determinism, and the relative/absolute separation the directive's Phase 8
  requires.
* **Scoring logic** — calibration on a synthetic set whose answer is known by
  construction, covered-call accounting, and the gate evaluation.
* **Process separation** — the scorer cannot write predictions.

Everything is hermetic: the panel is synthesised here, no cache is read, no
network is touched, and no frozen artefact is required.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from alpha import market_state, protocol, singlename  # noqa: E402
from alpha import singlename_config as cfg  # noqa: E402
from alpha import singlename_score as scoring  # noqa: E402


# ----------------------------------------------------------------- fixtures


SYMBOLS = [f"S{i:03d}" for i in range(60)]
N_CUTOFFS = 140


def synthetic_panel(seed: int = 7, n_cutoffs: int = N_CUTOFFS,
                    symbols: list[str] | None = None
                    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
    """A panel with the shape `alpha/dataset.py::build` produces, and none of its cost.

    Cutoffs sit on a 5-session grid of a synthetic 250-day-a-year calendar, so
    the horizon/embargo arithmetic the harness performs is the real arithmetic
    rather than a simplified stand-in. `asset_return` is deliberately given a
    weak dependence on `ret_12_1` so that the arms have something to fit; the
    tests below never assert on the size of that dependence.
    """
    symbols = SYMBOLS if symbols is None else symbols
    rng = np.random.default_rng(seed)
    calendar = pd.DatetimeIndex(pd.bdate_range("2016-01-04", periods=n_cutoffs * 5 + 60))
    cutoffs = [calendar[i * 5] for i in range(n_cutoffs)]

    rows, regimes = [], {}
    for index, cutoff in enumerate(cutoffs):
        ret_12_1 = rng.normal(0.05, 0.25, len(symbols))
        ret_5d = rng.normal(0.0, 0.04, len(symbols))
        ret_20d = rng.normal(0.0, 0.08, len(symbols))
        forward = 0.002 + 0.02 * ret_12_1 + rng.normal(0.0, 0.045, len(symbols))

        trend = ("BULL_TREND" if index % 5 else "BEAR_TREND")
        vol = "HIGH_VOL" if index % 3 == 0 else "LOW_VOL"
        regimes[cutoff] = {"trend": trend, "vol": vol}

        rows.append(pd.DataFrame({
            "ret_12_1": ret_12_1, "ret_5d": ret_5d, "ret_20d": ret_20d,
            "ret_60d": rng.normal(0.0, 0.15, len(symbols)),
            "asset_return": forward,
            "horizon_end": calendar[index * 5 + cfg.HORIZON],
            "vix_level": 15.0 + index % 11,
            "vix_percentile": (index % 20) / 20.0,
            "index_breadth_above_sma50": 0.4 + (index % 10) / 25.0,
            "index_advance_share": 0.5,
            "mkt_spy_ret_20d": 0.01 * (1 if index % 4 else -1),
            "mkt_spy_ret_60d": 0.02 * (1 if index % 5 else -1),
            "cutoff": cutoff, "symbol": symbols,
        }))

    frame = pd.concat(rows, ignore_index=True).set_index(["cutoff", "symbol"]).sort_index()
    regime_frame = pd.DataFrame(regimes).T
    regime_frame.index = pd.DatetimeIndex(regime_frame.index)
    return frame, regime_frame, calendar


@pytest.fixture(scope="module")
def panel():
    return synthetic_panel()


@pytest.fixture(scope="module")
def data(panel):
    frame, regimes, calendar = panel
    return singlename.build(frame, regimes, calendar)


@pytest.fixture(scope="module")
def predictions(data):
    return singlename.run(data, verbose=False)


@pytest.fixture(scope="module")
def scored(predictions, data):
    return predictions.join(data.labels[["asset_return", "direction"]], how="inner")


# -------------------------------------------------------- frozen constants


class TestFrozenConstants:
    """§1 of the pre-registration, expressed as assertions."""

    def test_horizon_is_five_sessions(self):
        from alpha import targets
        assert cfg.HORIZON == 5 == targets.HORIZON

    def test_embargo_is_five_sessions(self):
        from alpha import dataset
        assert cfg.EMBARGO == 5 == dataset.EMBARGO

    def test_target_is_the_absolute_return_not_alpha(self):
        assert cfg.TARGET_RETURN == "asset_return"
        assert cfg.TARGET_RETURN != "alpha_5d"

    def test_no_second_horizon_exists_anywhere_in_the_study(self):
        source = "".join(
            (REPO / "alpha" / name).read_text(encoding="utf-8")
            for name in ("singlename.py", "singlename_score.py", "singlename_config.py"))
        for banned in ("alpha_20d", "horizon=20", "HORIZON = 20"):
            assert banned not in source, f"V4 §9.2 bars a third horizon: found {banned!r}"

    def test_arms_are_the_five_preregistered_baselines(self):
        assert cfg.ARMS == ("S0", "S1", "S2", "S3", "S4")

    def test_decision_thresholds(self):
        assert (cfg.BUY_PROB, cfg.SELL_PROB, cfg.MIN_EDGE) == (0.55, 0.45, 0.0025)

    def test_thresholds_are_symmetric_around_a_coin_flip(self):
        assert cfg.BUY_PROB - 0.5 == pytest.approx(0.5 - cfg.SELL_PROB)

    def test_walk_forward_geometry(self):
        assert cfg.MIN_TRAIN_CUTOFFS == 100
        assert cfg.CONFORMAL_CUTOFFS == 20

    def test_gate_thresholds(self):
        assert cfg.G2_MAX_ECE == 0.02
        assert cfg.G2_MIN_MONOTONE_SPEARMAN == 0.5
        assert cfg.G3_MIN_COVERAGE == 0.05
        assert cfg.G3_MIN_SYMBOLS == 100

    def test_bucket_fallback_threshold(self):
        assert cfg.MIN_BUCKET_CUTOFFS == 20

    def test_interval_is_nominal_ninety_percent(self):
        assert cfg.INTERVAL_LEVEL == 0.90
        assert (cfg.INTERVAL_HIGH_Q - cfg.INTERVAL_LOW_Q) == pytest.approx(0.90)

    def test_preregistration_exists_and_precedes_the_fit(self):
        text = (REPO / "alpha" / "SINGLE_NAME_PREREGISTRATION.md").read_text(
            encoding="utf-8")
        assert "PRE-REGISTRATION ONLY" in text
        assert "PHASE 1 VERDICT: ADVANCE" in text


# ------------------------------------------------------------ B3 and Layer 1


class TestIncumbent:
    def test_b3_rank_is_the_protocol_benchmark_ranked(self, panel):
        frame, regimes, _ = panel
        expected = protocol.benchmark_scores(frame, regimes)["b3_regime_switched"]
        expected = expected.groupby(level=0).rank(pct=True, na_option="keep")
        pd.testing.assert_series_equal(singlename.b3_rank(frame, regimes), expected,
                                       check_names=False)

    def test_b3_switches_on_the_bear_tag(self, panel):
        """§1.3: in BEAR_TREND the incumbent is -rank(mom_5d), not rank(mom_12_1)."""
        frame, regimes, _ = panel
        bear = regimes.index[regimes["trend"] == "BEAR_TREND"][0]
        scores = protocol.benchmark_scores(frame, regimes)["b3_regime_switched"]
        block = frame.xs(bear, level=0)
        reversal = -block["ret_5d"].rank(pct=True)
        assert scores.xs(bear, level=0).corr(reversal) == pytest.approx(1.0, abs=1e-9)

    def test_market_state_only_exposes_trend_and_vol_as_a_bucket(self, data):
        state = data.states[data.cutoffs[0]]
        assert state.bucket == (state.trend, state.vol)
        assert set(state.to_dict()) == {"regime", "trend", "vol", "risk_score",
                                        "vix_percentile", "breadth_sma50",
                                        "dispersion_20d"}

    def test_risk_score_is_bounded_and_unfitted(self):
        assert market_state.risk_score("BULL_TREND", 0.05, 0.9, 0.1) == pytest.approx(0.95)
        assert market_state.risk_score("BEAR_TREND", -0.05, 0.1, 0.9) == pytest.approx(0.05)
        for trend in ("BULL_TREND", "BEAR_TREND", "SIDEWAYS"):
            score = market_state.risk_score(trend, 0.01, 0.5, 0.5)
            assert 0.0 <= score <= 1.0

    def test_market_state_ignores_bars_after_the_cutoff(self, panel):
        """Layer 1 reads trailing columns only, so rewriting later cutoffs is a no-op."""
        frame, regimes, _ = panel
        cutoff = frame.index.get_level_values(0).unique()[3]
        before = market_state.at(cutoff, frame.xs(cutoff, level=0), regimes)

        tampered = frame.copy()
        later = tampered.index.get_level_values(0) > cutoff
        for column in market_state.CONTEXT_COLUMNS + (market_state.DISPERSION_INPUT,):
            tampered.loc[later, column] = 999.0
        after = market_state.at(cutoff, tampered.xs(cutoff, level=0), regimes)
        assert before == after


# ------------------------------------------------- point-in-time and leakage


class TestLabelDoor:
    def test_admissible_cutoffs_respect_horizon_plus_embargo(self, data):
        door = singlename.PastOutcomes(data)
        calendar = data.calendar
        for cutoff in data.cutoffs[::17]:
            position = calendar.searchsorted(cutoff)
            for train in door.admissible_cutoffs(cutoff):
                gap = position - calendar.searchsorted(train)
                assert gap >= cfg.HORIZON + cfg.EMBARGO

    def test_the_boundary_is_exact_not_conservative(self, data):
        """A cutoff exactly HORIZON+EMBARGO sessions back must be admissible."""
        door = singlename.PastOutcomes(data)
        cutoff = data.cutoffs[60]
        position = data.calendar.searchsorted(cutoff)
        boundary = data.calendar[position - cfg.HORIZON - cfg.EMBARGO]
        admissible = set(door.admissible_cutoffs(cutoff))
        assert boundary in admissible or boundary not in set(data.cutoffs)
        assert all(c <= boundary for c in admissible)

    def test_no_returned_outcome_window_is_still_open(self, data):
        door = singlename.PastOutcomes(data)
        for cutoff in data.cutoffs[::23]:
            rows = door.before(cutoff)
            if rows.empty:
                continue
            limit = data.calendar[data.calendar.searchsorted(cutoff) - cfg.EMBARGO]
            assert rows["horizon_end"].max() <= limit

    def test_a_tampered_horizon_end_raises_rather_than_being_trimmed(self, data):
        tampered = singlename.SingleNameData(
            data.features, data.labels.copy(), data.states, data.calendar)
        cutoff = data.cutoffs[60]
        earlier = data.cutoffs[10]
        tampered.labels.loc[(earlier, slice(None)), "horizon_end"] = data.cutoffs[-1]

        door = singlename.PastOutcomes(tampered)
        with pytest.raises(singlename.LookAheadError):
            door.before(cutoff)

    def test_future_outcomes_cannot_change_a_prediction(self, data):
        """The counterpart of `test_future_cannot_change_the_verdict`.

        Every label the harness was not entitled to see at the evaluation
        cutoffs is overwritten with nonsense. If the predictions move by a
        single bit, the walk-forward is reading the future.
        """
        cutoffs = singlename.evaluation_cutoffs(data)
        pivot = cutoffs[0]
        boundary_position = data.calendar.searchsorted(pivot) - cfg.HORIZON - cfg.EMBARGO

        rewritten = data.labels.copy()
        positions = data.calendar.searchsorted(
            pd.DatetimeIndex(rewritten.index.get_level_values(0)))
        forbidden = positions > boundary_position
        rewritten.loc[forbidden, "asset_return"] = -0.5
        rewritten.loc[forbidden, "direction"] = 0.0

        tampered = singlename.SingleNameData(data.features, rewritten,
                                             data.states, data.calendar)
        original = singlename.run(data, verbose=False).loc[[pivot]]
        after = singlename.run(tampered, verbose=False).loc[[pivot]]
        pd.testing.assert_frame_equal(original, after)

    def test_the_evaluation_window_starts_only_after_the_warm_up(self, data):
        door = singlename.PastOutcomes(data)
        for cutoff in singlename.evaluation_cutoffs(data):
            assert len(door.admissible_cutoffs(cutoff)) >= cfg.MIN_TRAIN_CUTOFFS

    def test_conformal_block_is_disjoint_from_the_fit_block(self, data):
        door = singlename.PastOutcomes(data)
        cutoff = singlename.evaluation_cutoffs(data)[0]
        admissible = door.admissible_cutoffs(cutoff)
        fit, calib = admissible[:-cfg.CONFORMAL_CUTOFFS], admissible[-cfg.CONFORMAL_CUTOFFS:]
        assert len(calib) == cfg.CONFORMAL_CUTOFFS
        assert not set(fit) & set(calib)
        assert max(fit) < min(calib)


# ----------------------------------------------------------- prediction logic


class TestPredictions:
    def test_probabilities_stay_inside_the_clip(self, predictions):
        for arm in cfg.ARMS:
            column = predictions[f"p_up_{arm}"]
            assert column.between(cfg.PROB_CLIP, 1.0 - cfg.PROB_CLIP).all()
            assert column.notna().all()

    def test_every_arm_emits_a_call_from_the_declared_vocabulary(self, predictions):
        allowed = {"BUY", "SELL", "HOLD", "NO_EDGE"}
        for arm in cfg.ARMS:
            assert set(predictions[f"call_{arm}"].unique()) <= allowed

    def test_intervals_are_ordered_and_contain_the_point_estimate(self, predictions):
        for arm in cfg.ARMS:
            low, high, point = (predictions[f"lo_{arm}"], predictions[f"hi_{arm}"],
                                predictions[f"er_{arm}"])
            usable = low.notna() & high.notna()
            assert (low[usable] <= high[usable]).all()
            assert (low[usable] <= point[usable] + 1e-12).all()
            assert (high[usable] >= point[usable] - 1e-12).all()

    def test_results_are_deterministic(self, data):
        first = singlename.run(data, verbose=False)
        second = singlename.run(data, verbose=False)
        pd.testing.assert_frame_equal(first, second)

    def test_a_missing_feature_is_never_imputed_and_never_acted_on(self, panel):
        frame, regimes, calendar = panel
        holed = frame.copy()
        cutoffs = sorted(holed.index.get_level_values(0).unique())
        victim = (cutoffs[-1], SYMBOLS[0])
        holed.loc[victim, "ret_12_1"] = np.nan
        holed.loc[victim, "ret_5d"] = np.nan

        data = singlename.build(holed, regimes, calendar)
        result = singlename.run(data, verbose=False)
        row = result.loc[victim]
        for arm in ("S2", "S3", "S4"):
            assert not row[f"usable_{arm}"]
            assert row[f"call_{arm}"] == "NO_EDGE"
            # Falls back to the unconditional prior rather than a cross-sectional
            # mean, which would be computed from the very cutoff it is filling.
            assert row[f"p_up_{arm}"] == pytest.approx(row["p_up_S1"])

    def test_the_prediction_file_carries_no_outcome(self, predictions):
        banned = {"asset_return", "direction", "alpha_5d", "horizon_end",
                  "target_train", "target_rank", "quintile"}
        assert not banned & set(predictions.columns)

    def test_the_output_schema_keeps_relative_and_absolute_apart(self, predictions):
        cutoff, symbol = predictions.index[0]
        payload = singlename.view(predictions.loc[(cutoff, symbol)], symbol, cutoff)
        assert set(payload) == {"symbol", "cutoff", "horizon", "market_state",
                                "relative", "absolute", "decision", "model"}
        assert set(payload["relative"]) == {"score", "percentile"}
        assert set(payload["absolute"]) == {"prob_up", "expected_return",
                                            "prediction_interval"}
        assert payload["horizon"] == "5D"

    def test_a_top_percentile_name_with_a_negative_forecast_is_not_a_buy(self):
        """Directive Phase 8: relative strength may never be promoted to an absolute BUY."""
        call, reason = singlename.decide(prob_up=0.80, expected=-0.01, usable=True)
        assert call == "HOLD"
        assert "expected return" in reason


class TestAbstention:
    def test_the_rule_is_hold_by_default(self):
        assert singlename.decide(0.50, 0.0, True)[0] == "HOLD"
        assert singlename.decide(0.54, 0.10, True)[0] == "HOLD"
        assert singlename.decide(0.99, 0.0001, True)[0] == "HOLD"

    def test_both_conditions_are_required_for_a_call(self):
        assert singlename.decide(0.55, 0.0025, True)[0] == "BUY"
        assert singlename.decide(0.45, -0.0025, True)[0] == "SELL"
        assert singlename.decide(0.55, 0.0024, True)[0] == "HOLD"
        assert singlename.decide(0.45, -0.0024, True)[0] == "HOLD"

    def test_an_unusable_row_is_no_edge_not_hold(self):
        assert singlename.decide(0.90, 0.05, False)[0] == "NO_EDGE"
        assert singlename.decide(np.nan, np.nan, True)[0] == "NO_EDGE"

    def test_confidence_tiers_are_the_frozen_ones(self):
        assert singlename.confidence_tier(0.505) == "low"
        assert singlename.confidence_tier(0.53) == "medium"
        assert singlename.confidence_tier(0.62) == "high"
        assert singlename.confidence_tier(0.38) == "high"


# ------------------------------------------------------------ scoring logic


class TestScoring:
    def test_call_correct_scores_sells_inverted_and_abstentions_as_nan(self):
        calls = pd.Series(["BUY", "SELL", "HOLD", "NO_EDGE"])
        actual = pd.Series([1.0, 0.0, 1.0, 1.0])
        correct = scoring.call_correct(calls, actual)
        assert correct.iloc[0] == 1.0
        assert correct.iloc[1] == 1.0
        assert correct.iloc[2:].isna().all()

    def test_log_loss_and_brier_reward_the_right_answer(self):
        actual = pd.Series([1.0, 1.0])
        confident = pd.Series([0.9, 0.9])
        wrong = pd.Series([0.1, 0.1])
        assert scoring.log_loss(confident, actual).mean() < \
               scoring.log_loss(wrong, actual).mean()
        assert scoring.brier(confident, actual).mean() < \
               scoring.brier(wrong, actual).mean()

    def test_a_perfectly_calibrated_set_has_almost_no_calibration_error(self):
        rng = np.random.default_rng(11)
        n = 200_000
        prob = rng.uniform(0.05, 0.95, n)
        frame = pd.DataFrame({
            "p_up_S3": prob,
            "direction": (rng.uniform(size=n) < prob).astype(float),
        }, index=pd.MultiIndex.from_arrays(
            [pd.to_datetime(["2020-01-01"] * n), np.arange(n)],
            names=["cutoff", "symbol"]))
        table = scoring.reliability(frame, "S3")
        assert scoring.expected_calibration_error(table) < 0.01
        assert scoring.monotonicity(table, min_cutoffs=0)["spearman"] == pytest.approx(1.0)

    def test_a_miscalibrated_set_is_caught(self):
        rng = np.random.default_rng(12)
        n = 50_000
        prob = rng.uniform(0.05, 0.95, n)
        frame = pd.DataFrame({
            "p_up_S3": prob,
            "direction": (rng.uniform(size=n) < 0.5).astype(float),   # truth is a coin
        }, index=pd.MultiIndex.from_arrays(
            [pd.to_datetime(["2020-01-01"] * n), np.arange(n)],
            names=["cutoff", "symbol"]))
        assert scoring.expected_calibration_error(scoring.reliability(frame, "S3")) > 0.1

    def test_per_cutoff_metrics_have_one_row_per_cutoff(self, scored):
        series = scoring.per_cutoff(scored, "S3")
        assert len(series) == scored.index.get_level_values(0).nunique()
        assert series["accuracy"].between(0.0, 1.0).all()
        assert series["coverage"].between(0.0, 1.0).all()

    def test_every_headline_number_carries_its_resolution(self, scored):
        row = scoring.describe(scoring.per_cutoff(scored, "S3")["accuracy"], "accuracy")
        assert row["half_width"] is not None and row["half_width"] > 0
        assert row["n_cutoffs"] > 0

    def test_gates_report_pass_or_fail_for_all_four(self, scored):
        series = {arm: scoring.per_cutoff(scored, arm) for arm in cfg.ARMS}
        result = scoring.gates(scored, series, "S3")
        assert set(result) == {"G1", "G2", "G3", "G4", "verdict"}
        assert result["verdict"] in ("ADVANCE", "DO NOT ADVANCE")
        for name in ("G1", "G2", "G3", "G4"):
            assert isinstance(result[name]["passed"], bool)

    def test_the_verdict_is_conjunctive(self, scored):
        series = {arm: scoring.per_cutoff(scored, arm) for arm in cfg.ARMS}
        result = scoring.gates(scored, series, "S3")
        passed = [result[name]["passed"] for name in ("G1", "G2", "G3", "G4")]
        assert (result["verdict"] == "ADVANCE") == all(passed)

    def test_threshold_sweep_coverage_falls_as_the_bar_rises(self, scored):
        sweep = scoring.threshold_sweep(scored, "S3")
        assert sweep["coverage"].is_monotonic_decreasing

    def test_interval_coverage_is_reported_not_asserted(self, scored):
        series = scoring.per_cutoff(scored, "S3")
        assert series["interval_coverage"].between(0.0, 1.0).all()


# ------------------------------------------------------- process separation


class TestProcessSeparation:
    def test_the_scorer_never_writes_the_prediction_file(self):
        source = (REPO / "alpha" / "singlename_score.py").read_text(encoding="utf-8")
        assert "PREDICTIONS_PATH" in source                      # it reads it
        for write in ("to_pickle(", "write_text("):
            for line in source.splitlines():
                if write in line:
                    assert "PREDICTIONS_PATH" not in line, \
                        "singlename_score.py must never write the frozen predictions"

    def test_the_predictor_never_reads_the_score_file(self):
        source = (REPO / "alpha" / "singlename.py").read_text(encoding="utf-8")
        assert "SCORES_PATH" not in source

    def test_the_predictor_refuses_to_overwrite(self, tmp_path, monkeypatch):
        target = tmp_path / "single_name_predictions.pkl"
        target.write_bytes(b"frozen")
        monkeypatch.setattr(cfg, "OUT_DIR", tmp_path)
        monkeypatch.setattr(cfg, "PREDICTIONS_PATH", target)
        with pytest.raises(SystemExit, match="frozen"):
            singlename.main([])
        assert target.read_bytes() == b"frozen"

    def test_the_sealed_exam_is_never_reachable_from_this_study(self):
        """`development_only` is the only permitted contact, and it only removes dates."""
        for name in ("singlename.py", "singlename_score.py", "singlename_config.py",
                     "market_state.py"):
            source = (REPO / "alpha" / name).read_text(encoding="utf-8")
            for line in source.splitlines():
                if "examset" in line and not line.lstrip().startswith(("#", "*")):
                    assert ("development_only" in line or line.lstrip().startswith("from ")
                            or line.lstrip().startswith("import ")), \
                        f"{name}: only examset.development_only may be called ({line!r})"
            for banned in ("exam_predictions", "v2_1_exam", "exam_scores",
                           "exam_set.json"):
                assert banned not in source
