"""The consensus engine, and the gates that keep it honest.

Most of this file is about what the indicator *refuses* to say. That is the
hard part: producing a confident BUY from sixteen sources is trivial, and
every one of the guards below exists because an earlier version of this
module produced one it had no business producing.

Nothing here touches the network — `evaluate()` takes its fetcher by
injection, and every other entry point works on a frame.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import indicators, live, ultimate


def series(direction: float, rows: int = 900, noise: float = 0.4,
           seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    steps = direction + rng.standard_normal(rows) * noise
    close = 100 + np.cumsum(steps)
    close = np.maximum(close, 1.0)
    return pd.DataFrame({
        "date": pd.bdate_range("2019-01-01", periods=rows),
        "open": close, "high": close + 0.5, "low": close - 0.5, "close": close,
        "volume": np.full(rows, 5_000.0),
    })


@pytest.fixture
def uptrend() -> pd.DataFrame:
    return series(0.35)


@pytest.fixture
def random_walk() -> pd.DataFrame:
    return series(0.0, noise=1.0, seed=11)


DAILY = ultimate.HORIZON_BY_KEY["1d"]
WEEKLY = ultimate.HORIZON_BY_KEY["1w"]


# ----------------------------------------------------------------- calibration


def test_a_perfect_source_is_measured_as_perfect():
    """A source built from the answer should read 100% and carry weight."""
    frame = series(0.2, rows=600)
    close = frame["close"]
    oracle = np.sign(ultimate.forward_return(close, 1)).fillna(0.0)

    skill = ultimate.calibrate(oracle, close, 1)
    assert skill.hit_rate == pytest.approx(100.0)
    assert skill.edge == pytest.approx(50.0)
    assert skill.weight > 0
    assert skill.significant


def test_a_coin_flip_earns_no_weight(random_walk):
    rng = np.random.default_rng(5)
    noise = pd.Series(rng.choice([-1.0, 1.0], len(random_walk)),
                      index=random_walk.index)
    skill = ultimate.calibrate(noise, random_walk["close"], 1)
    assert skill.weight == 0.0
    assert abs(skill.edge) < 8


def test_an_anti_predictive_source_is_dropped_and_never_inverted():
    """Flipping a losing source is how you find an edge in pure noise."""
    frame = series(0.2, rows=600)
    close = frame["close"]
    wrong = -np.sign(ultimate.forward_return(close, 1)).fillna(0.0)

    skill = ultimate.calibrate(wrong, close, 1)
    assert skill.hit_rate == pytest.approx(0.0)
    assert skill.weight == 0.0
    assert "wrong more often" in skill.note


def test_neutral_bars_are_not_scored():
    """A source at 0.02 is not making a call and must not be graded on one."""
    frame = series(0.2, rows=600)
    close = frame["close"]
    oracle = np.sign(ultimate.forward_return(close, 1)).fillna(0.0)

    quiet = oracle * 0.05                    # same signs, below the threshold
    assert ultimate.calibrate(quiet, close, 1).samples == 0
    assert ultimate.calibrate(oracle, close, 1).samples > 0


def test_overlapping_windows_are_discounted():
    """Five daily views of one week are one observation, not five.

    Without this correction a 5-bar horizon manufactures significance out of
    correlated draws, and the week-ahead reading becomes the loudest thing in
    the app for no reason other than arithmetic.
    """
    frame = series(0.2, rows=900)
    close = frame["close"]
    oracle = np.sign(ultimate.forward_return(close, 5)).fillna(0.0)

    skill = ultimate.calibrate(oracle, close, 5)
    assert skill.effective == pytest.approx(skill.samples / 5, rel=1e-6)
    assert skill.t_stat < skill.edge / (50 / np.sqrt(skill.samples))


def test_thin_holdout_samples_earn_nothing():
    frame = series(0.2, rows=200)
    close = frame["close"]
    oracle = np.sign(ultimate.forward_return(close, 1)).fillna(0.0)
    skill = ultimate.calibrate(oracle, close, 1, min_samples=10_000)
    assert skill.weight == 0.0
    assert "holdout" in skill.note


def test_only_the_holdout_is_scored():
    """A source that is perfect early and random late must not read perfect."""
    frame = series(0.2, rows=800)
    close = frame["close"]
    truth = np.sign(ultimate.forward_return(close, 1)).fillna(0.0)

    split = int(len(close) * (1 - ultimate.HOLDOUT))
    rng = np.random.default_rng(2)
    mixed = truth.copy()
    mixed.iloc[split:] = rng.choice([-1.0, 1.0], len(close) - split)

    assert ultimate.calibrate(mixed, close, 1).hit_rate < 60
    assert ultimate.calibrate(truth, close, 1).hit_rate == pytest.approx(100.0)


def test_significance_floor_is_enforced():
    weak = ultimate.Skill(hit_rate=52.0, samples=100, effective=100.0,
                          edge=2.0, t_stat=0.4, weight=0.0)
    assert not weak.active
    assert ultimate.MIN_T > 1.0, "the floor is what keeps noise out"


# ------------------------------------------------------------ the family cap


def test_one_family_cannot_carry_a_verdict_alone():
    weights = {"a": 9.0, "b": 9.0, "c": 9.0, "d": 1.0}
    families = {"a": "trend", "b": "trend", "c": "trend", "d": "momentum"}
    capped = ultimate.cap_families(weights, families, cap=0.55)

    total = sum(capped.values())
    trend = sum(capped[k] for k in "abc")
    assert trend / total <= 0.55 + 1e-6
    # The evidence removed was double-counted, so the total shrinks with it.
    assert total < sum(weights.values())


def test_the_cap_converges_rather_than_creeping_towards_the_limit():
    """The rescale-and-renormalise version left a family at 70% of a 55% cap."""
    weights = {"a": 100.0, "b": 1.0}
    capped = ultimate.cap_families(weights, {"a": "agent", "b": "momentum"},
                                   cap=0.55)
    share = capped["a"] / sum(capped.values())
    assert share == pytest.approx(0.55, abs=0.01)


def test_a_lone_family_is_not_capped_to_nothing():
    """Capping the only evidence there is would zero the horizon, not balance it."""
    weights = {"a": 4.0, "b": 2.0}
    capped = ultimate.cap_families(weights, {"a": "trend", "b": "trend"})
    assert capped == weights


# ------------------------------------------------------------- classification


@pytest.mark.parametrize("score,expected", [
    (80, ultimate.STRONG_BUY), (25, ultimate.BUY), (5, ultimate.HOLD),
    (-25, ultimate.SELL), (-80, ultimate.STRONG_SELL),
])
def test_bands_map_score_to_action(score, expected):
    assert ultimate.classify(score, confidence=90.0) == expected


def test_confidence_vetoes_any_direction():
    """A +90 built on nothing measured is a confident statement about nothing."""
    assert ultimate.classify(90.0, confidence=1.0) == ultimate.HOLD
    assert ultimate.classify(-90.0, confidence=1.0) == ultimate.HOLD


def test_strong_needs_more_than_the_floor():
    barely = ultimate.MIN_CONFIDENCE + 1
    assert ultimate.classify(90.0, barely) == ultimate.BUY
    assert ultimate.classify(90.0, ultimate.STRONG_CONFIDENCE + 1) == ultimate.STRONG_BUY


# ------------------------------------------------------------- whole horizons


def test_a_random_walk_produces_no_call(random_walk):
    verdict = ultimate.evaluate_frame(random_walk, DAILY, interval="1d")
    assert verdict.available
    assert verdict.action == ultimate.HOLD
    assert verdict.confidence < ultimate.MIN_CONFIDENCE


def test_a_persistent_trend_is_found(uptrend):
    verdict = ultimate.evaluate_frame(uptrend, DAILY, interval="1d")
    assert verdict.score > 0
    assert verdict.live, "a strong trend should leave something significant"
    assert verdict.action in (ultimate.BUY, ultimate.STRONG_BUY)


def test_weights_never_exceed_one(uptrend):
    verdict = ultimate.evaluate_frame(uptrend, DAILY, interval="1d")
    assert sum(r.weight for r in verdict.readings) <= 1.0 + 1e-9
    assert abs(verdict.score) <= 100.0


def test_score_and_contributions_agree(uptrend):
    """The table shown to the user has to add up to the number beside it."""
    verdict = ultimate.evaluate_frame(uptrend, DAILY, interval="1d")
    assert sum(r.contribution for r in verdict.readings) == pytest.approx(
        verdict.score, abs=1e-6)


def test_a_short_frame_is_declined_rather_than_guessed():
    verdict = ultimate.evaluate_frame(series(0.2, rows=120), DAILY, interval="1d")
    assert not verdict.available
    assert "too few" in verdict.unavailable


def test_a_horizon_shorter_than_one_bar_is_declined():
    """4 hours cannot be read off weekly bars, and saying so beats interpolating."""
    frame = series(0.2, rows=400)
    verdict = ultimate.evaluate_frame(
        frame, ultimate.HORIZON_BY_KEY["4h"], interval="1wk")
    assert not verdict.available


def test_agents_enter_as_evidence_not_as_authority(uptrend):
    with_agents = ultimate.evaluate_frame(uptrend, DAILY, interval="1d",
                                          include_agents=True)
    names = {r.key for r in with_agents.readings}
    assert {"agent_turtle", "agent_crossover", "agent_rolling"} <= names

    without = ultimate.evaluate_frame(uptrend, DAILY, interval="1d",
                                      include_agents=False)
    assert not any(r.family == ultimate.AGENT for r in without.readings)


def test_expected_move_is_sized_by_the_horizon(uptrend):
    day = ultimate.evaluate_frame(uptrend, DAILY, interval="1d")
    week = ultimate.evaluate_frame(uptrend, WEEKLY, interval="1d")
    assert week.typical_move_pct > day.typical_move_pct
    assert abs(day.expected_move_pct) <= day.typical_move_pct + 1e-9


# ------------------------------------------------------------- model evidence


def test_a_chance_level_forecast_earns_no_weight():
    evidence = ultimate.ModelEvidence(
        name="LSTM", interval="1d", horizon_bars=5, predicted_move_pct=8.0,
        directional_pct=50.0, samples=150)
    reading = evidence.reading(bars=5, yardstick=1.0)
    assert reading.skill.weight == 0.0
    assert reading.score > 0, "it still has an opinion; it just has no weight"


def test_a_small_sample_forecast_is_shrunk_away():
    """30 predicted bars at 60% directional is 6 independent windows."""
    evidence = ultimate.ModelEvidence(
        name="LSTM", interval="1d", horizon_bars=5, predicted_move_pct=8.0,
        directional_pct=60.0, samples=30)
    assert evidence.reading(bars=5, yardstick=1.0).skill.weight == 0.0


def test_a_well_measured_forecast_is_used():
    evidence = ultimate.ModelEvidence(
        name="LSTM", interval="1d", horizon_bars=5, predicted_move_pct=4.0,
        directional_pct=60.0, samples=2_000)
    reading = evidence.reading(bars=5, yardstick=1.0)
    assert reading.skill.weight > 0
    assert reading.score > 0


def test_the_forecast_move_is_pro_rated_to_the_horizon():
    evidence = ultimate.ModelEvidence(
        name="LSTM", interval="1d", horizon_bars=10, predicted_move_pct=10.0,
        directional_pct=60.0, samples=2_000)
    assert "+1.00%" in evidence.reading(bars=1, yardstick=1.0).detail


def test_a_forecast_on_another_interval_is_ignored(uptrend):
    evidence = ultimate.ModelEvidence(
        name="LSTM", interval="1h", horizon_bars=4, predicted_move_pct=9.0,
        directional_pct=70.0, samples=5_000)
    verdict = ultimate.evaluate_frame(uptrend, DAILY, interval="1d",
                                      model=evidence)
    assert not any(r.kind == ultimate.MODEL for r in verdict.readings)


# ------------------------------------------------------------ the whole thing


def fake_fetch(frames: dict[str, pd.DataFrame]):
    def fetch(symbol, period="5y", interval="1d", force=False):
        if interval not in frames:
            raise live.FetchError(f"no {interval} bars in this test")
        return frames[interval], None
    return fetch


def test_evaluate_reads_each_horizon_at_its_own_resolution(uptrend):
    hourly = series(0.05, rows=2_000)
    hourly["date"] = pd.date_range("2025-01-01 09:30", periods=2_000, freq="h")

    verdict = ultimate.evaluate(
        "TEST", fetcher=fake_fetch({"1d": uptrend, "1h": hourly}))

    assert len(verdict.horizons) == 3
    assert verdict.by_key("4h").interval == "1h"
    assert verdict.by_key("4h").bars_used == 4
    assert verdict.by_key("1d").bars_used == 1
    assert verdict.by_key("1w").bars_used == 5


def test_a_missing_interval_degrades_rather_than_failing(uptrend):
    verdict = ultimate.evaluate("TEST", fetcher=fake_fetch({"1d": uptrend}))
    assert not verdict.by_key("4h").available
    assert verdict.by_key("1d").available
    assert verdict.errors


def test_no_readable_horizon_is_a_hold_not_a_crash():
    verdict = ultimate.evaluate("TEST", fetcher=fake_fetch({}))
    assert verdict.action == ultimate.HOLD
    assert verdict.confidence == 0.0
    assert not verdict.available
    assert "No horizon could be read" in verdict.conclusion


def test_horizons_are_weighted_by_their_own_confidence(uptrend):
    """A horizon that measured nothing must not get a vote."""
    verdict = ultimate.evaluate("TEST", fetcher=fake_fetch({"1d": uptrend}))
    quiet = [h for h in verdict.available if h.confidence == 0]
    if quiet:
        assert all(h.action == ultimate.HOLD for h in quiet)
    assert verdict.confidence <= max(
        (h.confidence for h in verdict.available), default=0.0) + 1e-9


def test_disagreeing_timeframes_discount_the_score():
    bull = ultimate.HorizonVerdict(
        horizon=DAILY, readings=[], score=60.0, confidence=50.0, agreement=1.0,
        weighted_edge=6.0, typical_move_pct=1.0, bars_used=1, interval="1d",
        rows=900, last_price=100.0, as_of=None, coverage=1.0)
    bear = ultimate.HorizonVerdict(
        horizon=WEEKLY, readings=[], score=-60.0, confidence=50.0,
        agreement=1.0, weighted_edge=6.0, typical_move_pct=2.0, bars_used=5,
        interval="1d", rows=900, last_price=100.0, as_of=None, coverage=1.0)

    split = ultimate.combine("TEST", [bull, bear])
    assert split.alignment == "split"
    assert abs(split.score) < 30

    aligned = ultimate.combine("TEST", [bull, bull])
    assert aligned.alignment == "aligned"
    assert aligned.score > 60


def test_alignment_never_inflates_confidence():
    """Timeframes agreeing is evidence about direction, not about measurement."""
    horizon = ultimate.HorizonVerdict(
        horizon=DAILY, readings=[], score=60.0, confidence=50.0, agreement=1.0,
        weighted_edge=6.0, typical_move_pct=1.0, bars_used=1, interval="1d",
        rows=900, last_price=100.0, as_of=None, coverage=1.0)
    combined = ultimate.combine("TEST", [horizon, horizon])
    assert combined.confidence <= 50.0 + 1e-9


# ----------------------------------------------------------------- reporting


def test_the_conclusion_quotes_the_numbers_it_computed(uptrend):
    verdict = ultimate.evaluate("TEST", fetcher=fake_fetch({"1d": uptrend}))
    text = verdict.conclusion
    assert verdict.action in text
    assert f"{verdict.score:+.0f}" in text
    assert f"{verdict.confidence:.0f}% confidence" in text


def test_a_quiet_verdict_says_why_rather_than_going_silent(random_walk):
    verdict = ultimate.evaluate("TEST", fetcher=fake_fetch({"1d": random_walk}))
    assert verdict.action == ultimate.HOLD
    assert "below the floor" in verdict.conclusion


def test_tables_render_for_every_state(uptrend, random_walk):
    for frame in (uptrend, random_walk):
        verdict = ultimate.evaluate("TEST", fetcher=fake_fetch({"1d": frame}))
        assert not verdict.table().empty
        for horizon in verdict.available:
            assert len(horizon.table()) == len(horizon.readings)


# --------------------------------------------------------------- bar mapping


@pytest.mark.parametrize("key,interval,bars", [
    ("4h", "1h", 4), ("4h", "4h", 1), ("4h", "1d", None),
    ("1d", "1h", 7), ("1d", "1d", 1),
    ("1w", "1d", 5), ("1w", "1wk", 1), ("1w", "1h", 33),
])
def test_horizon_bar_counts_are_a_written_table(key, interval, bars):
    """A US session is 6.5 hours, so these are not horizon_hours / bar_hours."""
    assert ultimate.HORIZON_BY_KEY[key].bars_on(interval) == bars


@pytest.mark.parametrize("freq,expected", [
    ("h", "1h"), ("B", "1d"), ("7D", "1wk"),
])
def test_interval_is_inferred_from_the_timestamps(freq, expected):
    dates = pd.Series(pd.date_range("2024-01-01", periods=500, freq=freq))
    assert ultimate.infer_interval(dates) == expected


def test_offline_reads_what_a_loaded_frame_can_express(uptrend):
    """A daily CSV answers 1 day and 1 week and declines 4 hours."""
    verdict = ultimate.evaluate_offline(uptrend, "GOOG-year")
    assert verdict.symbol == "GOOG-YEAR"
    assert not verdict.by_key("4h").available
    assert verdict.by_key("1d").available
    assert verdict.by_key("1w").available


def test_warmup_bars_are_never_calibrated_on(uptrend):
    """Every source reads 0 through its warm-up; grading those is grading zeros.

    `trend_slope` is the slowest of them — EMA(50) sampled 20 bars back, so
    its first honest value lands at bar 69 and `WARMUP` sits just past it.
    """
    close = uptrend["close"]
    scores = indicators.SOURCES["trend_slope"].read(uptrend)
    assert (scores.iloc[:69].abs() == 0).all()
    assert indicators.WARMUP > 69

    # On a long series the warm-up falls entirely inside the calibration
    # body, so it changes nothing — the holdout starts far later. Push it into
    # the holdout and the exclusion becomes observable.
    always_bullish = pd.Series(1.0, index=close.index)
    everything = ultimate.calibrate(always_bullish, close, 1, warmup=0)
    trimmed = ultimate.calibrate(always_bullish, close, 1,
                                 warmup=len(close) - 100)
    assert trimmed.samples < everything.samples


# ------------------------------------------------------------ scanning a book


def test_a_scan_runs_the_same_engine_as_a_single_symbol(uptrend):
    """A portfolio row disagreeing with the signal tab would be worse than none."""
    fetch = fake_fetch({"1d": uptrend})
    alone = ultimate.evaluate("AAA", fetcher=fetch)
    scanned = ultimate.scan(["AAA"], fetcher=fetch)["AAA"]

    assert scanned.action == alone.action
    assert scanned.score == pytest.approx(alone.score)
    assert scanned.confidence == pytest.approx(alone.confidence)


def test_a_scan_keeps_every_symbol_including_the_broken_ones(uptrend):
    """Dropping an unreadable holding shortens a list the user is counting."""
    def fetch(symbol, period="5y", interval="1d", force=False):
        if symbol == "BOOM":
            raise RuntimeError("something unexpected")
        if interval != "1d":
            raise live.FetchError("no intraday")
        return uptrend, None

    scanned = ultimate.scan(["AAA", "BOOM", "AAA"], fetcher=fetch)
    assert list(scanned) == ["AAA", "BOOM"], "duplicates should collapse"
    assert scanned["BOOM"].action == ultimate.HOLD
    assert scanned["BOOM"].errors


def test_scan_reports_progress_per_symbol(uptrend):
    seen = []
    ultimate.scan(["AAA", "BBB"], fetcher=fake_fetch({"1d": uptrend}),
                  on_progress=lambda i, n, s: seen.append((i, n, s)))
    assert seen == [(0, 2, "AAA"), (1, 2, "BBB")]


def test_scan_table_has_a_column_per_horizon(uptrend):
    table = ultimate.scan_table(
        ultimate.scan(["AAA"], fetcher=fake_fetch({"1d": uptrend})))
    assert list(table["Symbol"]) == ["AAA"]
    for column in ("Call", "Signal", "Confidence %", "4 hours", "1 day",
                   "1 week", "Horizons"):
        assert column in table.columns
    # 4 hours cannot be read off daily bars, and says so rather than guessing.
    assert table.loc[0, "4 hours"] == "—"
    assert table.loc[0, "Horizons"] == "2/3"


def verdict_reading(symbol: str, action: str, score: float,
                    confidence: float) -> ultimate.UltimateVerdict:
    """A verdict with a chosen action, for testing the aggregate alone."""
    horizon = ultimate.HorizonVerdict(
        horizon=DAILY, readings=[], score=score, confidence=confidence,
        agreement=1.0, weighted_edge=6.0, typical_move_pct=1.0, bars_used=1,
        interval="1d", rows=900, last_price=100.0, as_of=None, coverage=1.0)
    built = ultimate.combine(symbol, [horizon])
    assert built.action == action, f"fixture wanted {action}, got {built.action}"
    return built


def test_a_book_is_weighted_by_market_value_not_by_position_count():
    """A 40% holding reading SELL is not one vote among eighteen."""
    verdicts = {
        "BIG": verdict_reading("BIG", ultimate.SELL, -30.0, 50.0),
        "A": verdict_reading("A", ultimate.BUY, 20.0, 50.0),
        "B": verdict_reading("B", ultimate.BUY, 20.0, 50.0),
    }
    even = ultimate.book_signal(verdicts)
    tilted = ultimate.book_signal(verdicts, {"BIG": 90.0, "A": 5.0, "B": 5.0})

    assert even.score > 0, "unweighted, the two small buys outvote the sell"
    assert tilted.score < 0, "weighted, the position that is the book decides"


def test_a_book_signal_names_what_disagrees_with_holding_it():
    verdicts = {
        "GOOD": verdict_reading("GOOD", ultimate.STRONG_BUY, 60.0, 50.0),
        "BAD": verdict_reading("BAD", ultimate.SELL, -25.0, 50.0),
        "MEH": verdict_reading("MEH", ultimate.HOLD, 2.0, 50.0),
    }
    signal = ultimate.book_signal(verdicts)
    assert signal.selling == ["BAD"]
    assert signal.buying == ["GOOD"]
    assert signal.total == 3
    assert "sell" in signal.describe()


def test_an_unreadable_holding_is_counted_as_such(uptrend):
    scanned = ultimate.scan(["AAA"], fetcher=fake_fetch({}))
    signal = ultimate.book_signal(scanned)
    assert signal.unreadable == ["AAA"]
    assert signal.confidence == 0.0
