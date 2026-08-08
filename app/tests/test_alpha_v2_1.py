"""Validation and leakage tests for the V2.1 protocol.

V2's exam was twelve dates and could not pass its own sample-size criterion.
V2.1 replaces it with a deterministic 72-date paper, and the whole value of that
replacement rests on properties that are easy to state and easy to break later:
the dates are independent, they never reach the training side, the rule that
produced them is reproducible, and the file cannot be edited after a result.
Each one gets a test.

Two kinds of test live here.

* **Hermetic** — most of them. They build a synthetic market in `tmp_path` or a
  synthetic panel in memory, exactly as `test_alpha.py` does, because
  `alpha/cache/` is a downloaded artefact that will not exist on a fresh clone.
* **Against the real frozen artefact** — the handful that can only be asked of
  the actual exam set ("are there at least 60 cutoffs", "is every one of them in
  the built panel"). Those skip when the artefact is absent rather than fail,
  and they are the reason the suite is worth running on this machine.
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

from alpha import (adapter, build_panel, dataset, examset, membership,  # noqa: E402
                   models, pitdata, protocol, walkforward)

SPLIT = 900
SYMBOLS = [f"SYM{i:02d}" for i in range(40)]

EXAM_PATH = examset.PATH
PANEL_PATH = build_panel.PANEL_PATH

needs_exam_set = pytest.mark.skipif(
    not EXAM_PATH.exists(), reason="v2_1_exam_set.json is not frozen on this machine")
needs_panel = pytest.mark.skipif(
    not PANEL_PATH.exists(), reason="alpha/out/panel.pkl has not been built")


# ------------------------------------------------------------------ fixtures


def _frames(seed: int = 11) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=SPLIT + 400)
    frames = {}
    for symbol in ["SPY", "QQQ", "^VIX"] + SYMBOLS:
        steps = rng.standard_normal(len(dates)) * 0.011
        close = 100.0 * np.exp(np.cumsum(steps))
        frames[symbol] = pd.DataFrame({
            "date": dates, "open": close, "high": close * 1.005,
            "low": close * 0.995, "close": close,
            "volume": rng.integers(2_000_000, 9_000_000, len(dates)).astype(float)})
    return frames


@pytest.fixture
def book(tmp_path, monkeypatch):
    """A synthetic `PriceBook` — enough calendar for the selection rule to bite."""
    root = tmp_path / "cache"
    root.mkdir(parents=True, exist_ok=True)
    for symbol, frame in _frames().items():
        frame.to_csv(root / f"{symbol.replace('^', '_')}.csv", index=False)

    meta = root / "_meta"
    meta.mkdir(parents=True, exist_ok=True)
    sectors = ["Information Technology", "Financials", "Health Care", "Energy"]
    pd.DataFrame([{"ticker": s, "name": s, "sector": sectors[i % 4],
                   "date_added": "2010-01-01"} for i, s in enumerate(SYMBOLS)]
                 ).to_csv(meta / "sp500_current.csv", index=False)
    pd.DataFrame(columns=["effective_date", "added", "removed"]).to_csv(
        meta / "sp500_changes.csv", index=False)
    (meta / "sector_overrides.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(membership, "META_DIR", meta)
    membership._tables.cache_clear()
    membership.sector_map.cache_clear()
    pitdata.load_book.cache_clear()
    yield pitdata.load_book(str(root))
    membership._tables.cache_clear()
    membership.sector_map.cache_clear()
    pitdata.load_book.cache_clear()


def _split(book) -> tuple[list, list, pd.DatetimeIndex]:
    points = examset.grid(book)
    exam = examset.select(points)
    dev = examset.development(points, exam, book.calendar)
    return exam, dev, book.calendar


# ------------------------------------------------------- the selection rule


def test_exam_construction_is_deterministic(book):
    """Same calendar in, same dates out — twice, with the digest to prove it."""
    first_exam, first_dev, _ = _split(book)
    second_exam, second_dev, _ = _split(book)

    assert first_exam == second_exam
    assert first_dev == second_dev
    assert examset.digest_of(first_exam) == examset.digest_of(second_exam)
    # Order must not change the digest; content must.
    assert examset.digest_of(first_exam) == examset.digest_of(list(reversed(first_exam)))
    assert examset.digest_of(first_exam) != examset.digest_of(first_exam[:-1])


def test_the_exam_set_has_no_duplicates(book):
    exam, _dev, _calendar = _split(book)
    assert len(exam) == len(set(exam))


def test_exam_cutoffs_are_independent_under_the_horizon(book):
    """§2.4: outcome windows are 5 sessions and the dates are 30 apart.

    "Independent" here is a structural claim, not a statistical hope: the gap
    between consecutive exam cutoffs exceeds the horizon, so no two exam outcome
    windows can share a session at any lag.
    """
    exam, _dev, calendar = _split(book)
    report = examset.independence(exam, calendar)

    assert report["all_windows_disjoint"]
    assert report["min_gap_sessions"] == examset.EXAM_STEP * examset.SPACING
    assert report["min_gap_sessions"] > dataset.HORIZON
    assert report["min_clear_sessions_between_windows"] >= dataset.HORIZON

    for first, second in zip(exam, exam[1:]):
        assert book.horizon_end(first, dataset.HORIZON) < second


def test_no_development_window_overlaps_an_exam_window(book):
    """The purge, stated as the invariant a future refactor must not break.

    Overlap alone is not enough. Two windows that merely touch share the price
    at the boundary, so the rule is `HORIZON + EMBARGO` sessions of separation
    between every development cutoff and every exam cutoff, in both directions.
    """
    exam, dev, calendar = _split(book)
    exam_positions = np.array([calendar.searchsorted(e) for e in exam])

    assert not set(dev) & set(exam)
    for cutoff in dev:
        gap = int(np.abs(exam_positions - calendar.searchsorted(cutoff)).min())
        assert gap >= dataset.HORIZON + dataset.EMBARGO, f"{cutoff.date()} is {gap} sessions away"

        window = (cutoff, book.horizon_end(cutoff, dataset.HORIZON))
        for exam_cutoff in exam:
            other = (exam_cutoff, book.horizon_end(exam_cutoff, dataset.HORIZON))
            assert window[1] < other[0] or other[1] < window[0]


def test_the_warmup_leaves_enough_training_cutoffs_for_the_first_exam_date(book):
    """§2.1 rule 2 exists for exactly one reason; this is that reason, measured.

    The warm-up is specified in sessions, not in cutoffs, because the
    development set is defined in terms of the exam set — defining the exam set
    in terms of the development set would close the loop. What it has to deliver
    is that the earliest exam date already has the minimum training sample
    behind it.
    """
    exam, dev, _calendar = _split(book)
    usable = dataset.training_cutoffs(dev, exam[0], book)
    assert len(usable) >= walkforward.MIN_TRAIN_CUTOFFS


# ------------------------------------------------------------- exam vs training


def test_training_never_sees_an_exam_cutoff(book):
    """§7: exam cutoffs are excluded from training, at every exam date."""
    exam, dev, calendar = _split(book)
    for cutoff in exam:
        usable = dataset.training_cutoffs(dev, cutoff, book)
        assert not set(usable) & set(exam)
        limit = calendar.searchsorted(cutoff) - dataset.HORIZON - dataset.EMBARGO
        for train_cutoff in usable:
            assert calendar.searchsorted(train_cutoff) <= limit
            assert book.horizon_end(train_cutoff, dataset.HORIZON) < cutoff


def test_no_training_target_window_overlaps_the_exam_target_window(book):
    """The same guarantee expressed in outcome windows rather than in cutoffs."""
    exam, dev, _calendar = _split(book)
    for cutoff in exam[:10]:
        exam_window = (cutoff, book.horizon_end(cutoff, dataset.HORIZON))
        for train_cutoff in dataset.training_cutoffs(dev, cutoff, book):
            end = book.horizon_end(train_cutoff, dataset.HORIZON)
            assert end < exam_window[0]


def test_development_only_refuses_a_panel_carrying_exam_cutoffs(book):
    """§7's "the frozen exam cannot accidentally be used by develop".

    `slice_cutoffs` takes a keep-list, so a caller that passes the wrong list
    gets a wrong panel and no error. `development_only` is the call a
    development stage is meant to make, and it checks rather than trusts.
    """
    exam, dev, _calendar = _split(book)
    cutoffs = sorted(set(exam) | set(dev))
    index = pd.MultiIndex.from_product([cutoffs, SYMBOLS[:5]], names=["cutoff", "symbol"])
    panel = dataset.Panel(pd.DataFrame({"alpha_5d": 0.0}, index=index), [],
                          pd.DataFrame(), pd.DataFrame())

    honest = examset.ExamSet(exam, dev, {}, [], examset.digest_of(exam), "test")
    sliced = examset.development_only(panel, honest)
    assert not set(sliced.cutoffs) & set(exam)
    assert set(sliced.cutoffs) == set(dev)

    corrupted = examset.ExamSet(exam, dev + exam[:3], {}, [],
                                examset.digest_of(exam), "test")
    with pytest.raises(RuntimeError, match="contains exam cutoffs"):
        examset.development_only(panel, corrupted)


def test_the_exam_set_carries_no_outcome_of_any_kind(book, tmp_path):
    """§7: what `examset` hands back is dates and pre-cutoff descriptions.

    Asserted structurally as well as by inspection, because "we were careful" is
    not a property a later edit preserves. `forward_return` is the one method in
    `pitdata` that reads past a cutoff and it is named to be greppable.
    """
    source = (REPO / "alpha" / "examset.py").read_text(encoding="utf-8")
    assert "forward_return" not in source
    for column in ("alpha_5d", "target_train", "target_rank", "target_vol_scaled",
                   "asset_return", "spy_return", "quintile"):
        assert column not in source, f"examset.py mentions the outcome column {column}"

    exam, dev, calendar = _split(book)
    described = examset.describe(book, exam[len(exam) // 2], calendar)
    banned = {"alpha_5d", "asset_return", "spy_return", "forward_return",
              "target_train", "quintile", "ic", "spread"}
    assert not banned & set(described)
    assert described["cutoff"] == str(exam[len(exam) // 2].date())


# ---------------------------------------------------------------- immutability


def test_freeze_refuses_to_overwrite_a_frozen_exam(tmp_path, monkeypatch):
    """§2.5: re-freezing is deleting the file, which is a deliberate act."""
    path = tmp_path / "v2_1_exam_set.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(examset, "PATH", path)
    with pytest.raises(SystemExit, match="already exists"):
        examset.freeze(verbose=False)


def test_load_detects_an_edited_exam_set(tmp_path):
    """A silently edited exam paper is the failure this protocol exists to prevent."""
    cutoffs = [pd.Timestamp("2020-01-06") + pd.Timedelta(days=30 * i) for i in range(8)]
    payload = {
        "protocol": "V2.1", "frozen_at": "2026-08-08T00:00:00", "rule": {},
        "digest": examset.digest_of(cutoffs),
        "exam_cutoffs": [str(c.date()) for c in cutoffs],
        "development_cutoffs": [], "metadata": [],
    }
    path = tmp_path / "frozen.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert len(examset.load(path).cutoffs) == 8

    payload["exam_cutoffs"].append("2021-06-01")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="edited since it was frozen"):
        examset.load(path)


# ------------------------------------------------------ the frozen artefact


@needs_exam_set
def test_the_frozen_exam_has_at_least_sixty_independent_cutoffs():
    """§2.3. The single number V2's exam could not reach.

    Criterion 8 asks for 50 scored cutoffs; the set is built to 72 so that dates
    lost at scoring time do not put the study back under the bar.
    """
    exam_set = examset.load()
    assert len(exam_set.cutoffs) >= examset.MIN_EXAM_CUTOFFS
    assert len(exam_set.cutoffs) >= protocol.THRESHOLD_MIN_CUTOFFS
    assert len(exam_set.cutoffs) == len(set(exam_set.cutoffs))
    assert not set(exam_set.cutoffs) & set(exam_set.development)
    assert len(exam_set.development) > len(exam_set.cutoffs)


@needs_exam_set
def test_the_frozen_exam_matches_the_rule_that_claims_to_have_produced_it():
    """Re-derive the dates from the recorded rule and demand the same digest."""
    exam_set = examset.load()
    rule = exam_set.rule
    assert rule["exam_step_grid_cutoffs"] == examset.EXAM_STEP
    assert rule["warmup_sessions"] == examset.WARMUP_SESSIONS
    assert rule["min_separation_sessions"] == dataset.HORIZON + dataset.EMBARGO
    assert rule["exam_cutoffs"] == len(exam_set.cutoffs)
    assert rule["development_cutoffs"] == len(exam_set.development)
    assert examset.digest_of(exam_set.cutoffs) == exam_set.digest


@needs_exam_set
def test_the_frozen_exam_spans_more_than_one_market_condition():
    """§2 asks for bull, bear and sideways, and for both volatility states.

    Not a quota — the sample is systematic in calendar time, so this asserts
    that the window actually contained the conditions, which is a fact about
    2016-2026 rather than about the selection.
    """
    frame = examset.load().frame()
    assert set(frame["trend_regime"]) >= {"BULL_TREND", "BEAR_TREND", "SIDEWAYS"}
    assert set(frame["vol_regime"]) == {"HIGH_VOL", "LOW_VOL"}
    counts = frame["trend_regime"].value_counts()
    assert counts.min() >= protocol.MIN_REGIME_CUTOFFS, (
        "a trend bucket is too small to gate criterion 7: " + counts.to_string())
    assert frame["eligible_names"].min() >= 100


@needs_exam_set
@needs_panel
def test_every_frozen_exam_cutoff_exists_in_the_built_panel():
    """The bug that crashed V2's first exam run, asserted against the new set.

    Eight of V2's twelve dates were absent from the panel because they came from
    V1 and knew nothing about the 5-session grid. Every V2.1 exam date is a grid
    point by construction, which is what makes this assertion cheap — and worth
    keeping, because the construction is exactly what a future edit would change.
    """
    exam_set = examset.load()
    panel, _development, _v2_exam = build_panel.load()
    available = set(panel.cutoffs)

    missing = sorted(str(c.date()) for c in exam_set.cutoffs if c not in available)
    assert not missing, f"exam cutoffs with no rows in the panel: {missing}"
    missing_dev = [c for c in exam_set.development if c not in available]
    assert not missing_dev, f"{len(missing_dev)} development cutoffs have no rows"

    widths = panel.frame.loc[exam_set.index].groupby(level=0).size()
    assert widths.min() >= 100


# ----------------------------------------------------- §3 benchmark hierarchy


def test_the_benchmark_hierarchy_is_fixed_not_selected():
    """§3: 12-1 momentum is primary, at sign +1, by prior rather than by fit.

    V2 chose its baseline as the factor with the largest |mean development IC|,
    which selected 5-day reversal — the strongest in sample and −0.0008 out of
    it — while 12-1 momentum beat the model on the exam. A rule that reliably
    picks the weakest available opponent is not a benchmark rule, and the
    replacement has to contain no selection at all.
    """
    keys = [b.key for b in protocol.BENCHMARKS]
    assert keys[0] == "b1_momentum_12_1"

    by_key = {b.key: b for b in protocol.BENCHMARKS}
    assert by_key["b1_momentum_12_1"].sign == +1
    assert by_key["b1_momentum_12_1"].factor == "mom_12_1"
    assert by_key["b2_reversal_5d"].sign == -1
    assert by_key["b2_reversal_5d"].factor == "mom_5d"
    assert by_key["b1_momentum_12_1"].gate and by_key["b2_reversal_5d"].gate
    assert not by_key["b3_regime_switched"].gate

    source = (REPO / "alpha" / "protocol.py").read_text(encoding="utf-8")
    assert "choose_best_simple_factor" not in source


def test_the_primary_benchmark_is_alive():
    """`mom_12_1` was identically NaN for a whole V2 run. It is now the bar.

    A dead primary benchmark would make criterion 5 unfalsifiable — an empty
    paired difference reads as "no comparison available", not as a failure.
    """
    assert "mom_12_1" in models.SIMPLE_FACTORS
    assert models.SIMPLE_FACTORS["mom_12_1"] == "ret_12_1"

    frame = _panel(n_cutoffs=6, seed=2).frame
    scores = protocol.benchmark_scores(frame, _regimes(6))
    assert "b1_momentum_12_1" in scores.columns
    assert scores["b1_momentum_12_1"].notna().any()


def test_the_regime_switched_benchmark_switches_on_the_pre_cutoff_tag():
    """Benchmark 3: momentum outside bear markets, reversal inside them."""
    panel = _panel(n_cutoffs=4, seed=5)
    regimes = _regimes(4, bear_at=[1])
    ranks = models.simple_factor_scores(panel.frame)
    scores = protocol.benchmark_scores(panel.frame, regimes)

    cutoffs = sorted(panel.frame.index.get_level_values(0).unique())
    calm, bear = cutoffs[0], cutoffs[1]
    pd.testing.assert_series_equal(scores.loc[calm, "b3_regime_switched"],
                                   ranks.loc[calm, "mom_12_1"], check_names=False)
    pd.testing.assert_series_equal(scores.loc[bear, "b3_regime_switched"],
                                   -ranks.loc[bear, "mom_5d"], check_names=False)


# ------------------------------------------------------------ §4 the gates


def test_no_v2_threshold_was_lowered():
    """§4.1's closing claim, asserted rather than promised."""
    assert protocol.THRESHOLD_MEAN_IC == walkforward.THRESHOLD_MEAN_IC
    assert protocol.THRESHOLD_HIT_RATE == walkforward.THRESHOLD_HIT_RATE
    assert protocol.THRESHOLD_SIGN_STABILITY == walkforward.THRESHOLD_SIGN_STABILITY
    assert protocol.THRESHOLD_MIN_CUTOFFS == walkforward.THRESHOLD_MIN_CUTOFFS


def test_sign_stability_catches_an_edge_that_lives_in_one_half():
    """§4.1: V2's criteria 2 and 4 were the same number, so 4 could not fail.

    The failure it should have caught is a model that works and then stops. Here
    the first half is strongly positive and the second is strongly negative, so
    the hit rate is a respectable 0.5-ish and the halves disagree outright.
    """
    assessment = _assessment(signs=[+1] * 12 + [-1] * 12)
    criteria = assessment.criteria()
    halves = criteria["4_sign_stability"]["value"]

    assert halves["first_half_mean_ic"] > 0
    assert halves["second_half_mean_ic"] < 0
    assert not criteria["4_sign_stability"]["passed"]

    steady = _assessment(signs=[+1] * 24).criteria()["4_sign_stability"]
    assert steady["value"]["first_half_mean_ic"] > 0
    assert steady["value"]["second_half_mean_ic"] > 0
    assert steady["passed"]


def test_a_regime_bucket_too_small_to_mean_anything_does_not_gate():
    """§4.1: V2 gated on buckets holding one or two cutoffs. Those are coin flips.

    A tiny bucket can fail on noise, and — the worse direction — it can pass on
    noise. Below the minimum it is reported in full and decides nothing.
    """
    assessment = _assessment(signs=[+1] * 24, bear_at=[3])
    criterion = assessment.criteria()["7_no_regime_collapse"]

    gating = criterion["value"]["gating"]
    reported = criterion["value"]["below_minimum_reported_only"]
    assert "BEAR_TREND" in reported and reported["BEAR_TREND"]["n_cutoffs"] == 1
    assert "BEAR_TREND" not in gating
    assert all(entry["n_cutoffs"] >= protocol.MIN_REGIME_CUTOFFS for entry in gating.values())


def test_the_gate_list_is_the_nine_the_preregistration_names():
    """Which criteria gate is itself a pre-registered decision."""
    criteria = _assessment(signs=[+1] * 24).criteria()
    gating = {k for k, v in criteria.items() if v.get("gate")}
    assert gating == {
        "1_mean_ic", "2_ic_hit_rate", "3_top_minus_bottom", "4_sign_stability",
        "5_beats_12_1_momentum", "6_beats_5d_reversal", "7_no_regime_collapse",
        "8_effective_sample", "9_cost_adjusted_spread"}
    assert {"10_turnover", "11_cost_sensitivity", "12_independent_cutoffs"} <= set(criteria)
    assert all(not criteria[k]["gate"] for k in
               ("10_turnover", "11_cost_sensitivity", "12_independent_cutoffs"))


# ------------------------------------------------------------ §4.1 costs


def test_turnover_is_measured_not_assumed():
    """Identical legs cost nothing to hold; disjoint legs are fully replaced."""
    names = [f"S{i}" for i in range(20)]
    cutoffs = pd.date_range("2020-01-06", periods=3, freq="30B")
    rows = []
    for index, cutoff in enumerate(cutoffs):
        # cutoff 1 repeats cutoff 0's ordering; cutoff 2 reverses it outright.
        order = names if index < 2 else list(reversed(names))
        for rank, name in enumerate(order):
            rows.append({"cutoff": cutoff, "symbol": name, "prediction": float(rank)})
    frame = pd.DataFrame(rows).set_index(["cutoff", "symbol"])

    measured = protocol.turnover(frame, "prediction")
    assert measured["turnover_long"].iloc[0] == 1.0          # the book has to be built
    assert measured["turnover_long"].iloc[1] == 0.0          # unchanged leg
    assert measured["turnover_long"].iloc[2] == 1.0          # reversed leg
    assert measured["turnover_short"].iloc[2] == 1.0


def test_costs_can_turn_a_positive_gross_spread_negative():
    """§4.1: V2-F's exam spread was 26bp. Two-sided trading can eat that whole."""
    index = pd.date_range("2020-01-06", periods=6, freq="30B")
    spread = pd.Series(0.0015, index=index)
    total = pd.Series(2.0, index=index)

    assert protocol.net_spread(spread, total, bps=5.0).mean() == pytest.approx(0.0005)
    assert protocol.net_spread(spread, total, bps=10.0).mean() == pytest.approx(-0.0005)
    # A book that does not trade is not charged for trading.
    assert protocol.net_spread(spread, pd.Series(0.0, index=index),
                               bps=20.0).mean() == pytest.approx(0.0015)


def test_cost_sensitivity_reports_every_pre_registered_level():
    sensitivity = _assessment(signs=[+1] * 24).cost_sensitivity()
    assert set(sensitivity) == {f"{b:g}bps" for b in protocol.COST_SENSITIVITY_BPS}
    means = [sensitivity[f"{b:g}bps"]["mean"] for b in sorted(protocol.COST_SENSITIVITY_BPS)]
    assert means == sorted(means, reverse=True), "a higher cost must not help"


def test_interval_sensitivity_shows_the_block_length_choice():
    """§5: block 4 is pre-registered; the alternatives are reported, not hidden."""
    sensitivity = _assessment(signs=[+1] * 24).interval_sensitivity()
    assert {f"block_{b}" for b in protocol.BLOCK_SENSITIVITY} <= set(sensitivity)
    assert sensitivity["newey_west_se"] is not None


# ------------------------------------------------------------- §9 production


def test_production_stays_hold_under_the_v2_1_protocol(tmp_path):
    """§9: nothing in this stage may move production off HOLD."""
    evidence = adapter.load_evidence(tmp_path / "nothing.json")
    assert evidence.weight == 0.0 and not evidence.passed_all_criteria
    action, reason = adapter.decide(0.9, 0.99, evidence, regime="BULL_TREND",
                                    historical_spread=1.0)
    assert action == adapter.Action.HOLD
    assert "insufficient model evidence" in reason

    record = _assessment(signs=[+1] * 24).record()
    assert record["production_weight"] == 0.0


def test_v2_1_did_not_edit_the_v2_record():
    """§1 of the directive: V2 is a completed experiment, not a draft."""
    preregistration = (REPO / "alpha" / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "V2.1" not in preregistration
    assert "# V2 pre-registration" in preregistration

    for name in ("V2_1_PREREGISTRATION.md", "examset.py", "protocol.py"):
        assert (REPO / "alpha" / name).exists()

    # The V2 exam paper is still what it was; V2.1 does not extend it.
    assert len(dataset.EXAM_CUTOFFS) == 12
    assert dataset.EXAM_CUTOFFS[0] == "2022-03-08"


# ---------------------------------------------------------------- synthetic panel


def _regimes(n_cutoffs: int, bear_at: list[int] | None = None) -> pd.DataFrame:
    cutoffs = pd.date_range("2020-01-06", periods=n_cutoffs, freq="30B")
    bear = set(bear_at or [])
    return pd.DataFrame(
        {"trend": ["BEAR_TREND" if i in bear else "BULL_TREND" for i in range(n_cutoffs)],
         "vol": ["HIGH_VOL" if i % 2 else "LOW_VOL" for i in range(n_cutoffs)]},
        index=cutoffs)


def _panel(n_cutoffs: int, seed: int = 0, signs: list[int] | None = None,
           bear_at: list[int] | None = None) -> dataset.Panel:
    """A panel with a controllable per-cutoff relationship between signal and outcome.

    Cheaper and far more legible than building one through `dataset.build`: the
    gates being tested are functions of per-cutoff IC and quintile spread, and
    this makes both directly dialable.
    """
    rng = np.random.default_rng(seed)
    names = [f"S{i:02d}" for i in range(60)]
    cutoffs = pd.date_range("2020-01-06", periods=n_cutoffs, freq="30B")
    signs = signs or [1] * n_cutoffs

    rows = []
    for index, cutoff in enumerate(cutoffs):
        signal = rng.standard_normal(len(names))
        noise = rng.standard_normal(len(names)) * 0.02
        alpha = signs[index] * signal * 0.01 + noise
        for position, name in enumerate(names):
            rows.append({"cutoff": cutoff, "symbol": name,
                         "prediction": float(signal[position]),
                         "alpha_5d": float(alpha[position]),
                         "ret_12_1": float(rng.standard_normal()),
                         "ret_5d": float(rng.standard_normal())})

    frame = pd.DataFrame(rows).set_index(["cutoff", "symbol"]).sort_index()
    return dataset.Panel(frame, ["ret_12_1", "ret_5d"],
                         _regimes(n_cutoffs, bear_at), pd.DataFrame())


def _assessment(signs: list[int], bear_at: list[int] | None = None) -> protocol.Assessment:
    panel = _panel(len(signs), seed=17, signs=signs, bear_at=bear_at)
    return protocol.assess(panel, panel.frame["prediction"], "synthetic")
