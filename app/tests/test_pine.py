"""The Pine ports: right arithmetic, right shape, and off the evidence path.

Two different things are guarded here. The first is that each indicator says
what the Pine script says — the primitives are checked against closed-form
answers, and the indicators against the behaviour that makes them worth drawing
(Supertrend ratchets, Squeeze detects a squeeze, the Vix Fix spikes at a low).

The second matters more to the repository than to the charts: these indicators
must stay *out* of `indicators.SOURCES` and out of the model registry. Adding
one there would change the live incumbent's evidence set without changing the
ensemble's version, and re-version every `technical.*` model against forecasts
already frozen in the ledger. That is a research-record failure rather than a
drawing bug, so it is asserted rather than left to review.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import indicators, pine


def ohlc(rows: int = 400, direction: float = 0.0, seed: int = 7) -> pd.DataFrame:
    """A deterministic OHLC frame with a controllable drift."""
    rng = np.random.default_rng(seed)
    steps = direction * 0.25 + rng.standard_normal(rows) * 0.6
    close = 100 + np.cumsum(steps)
    spread = np.abs(rng.standard_normal(rows)) * 0.5 + 0.1
    return pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=rows),
        "open": close - rng.standard_normal(rows) * 0.2,
        "high": close + spread,
        "low": close - spread,
        "close": close,
        "volume": np.full(rows, 10_000.0) + rng.integers(0, 500, rows),
    })


@pytest.fixture
def frame() -> pd.DataFrame:
    return ohlc()


@pytest.fixture
def rising() -> pd.DataFrame:
    return ohlc(direction=1.0)


# ---------------------------------------------------------------- primitives


def test_linreg_endpoint_matches_a_least_squares_fit(frame):
    """`ta.linreg(src, n, 0)` is the fitted line read at the current bar."""
    length = 20
    ported = pine.linreg(frame["close"], length, 0).to_numpy()
    values = frame["close"].to_numpy()

    for i in range(length - 1, len(values)):
        window = values[i - length + 1:i + 1]
        slope, intercept = np.polyfit(np.arange(length), window, 1)
        assert ported[i] == pytest.approx(intercept + slope * (length - 1))


def test_linreg_offset_reads_the_line_one_bar_back(frame):
    length = 20
    ported = pine.linreg(frame["close"], length, 1).to_numpy()
    values = frame["close"].to_numpy()

    window = values[-length:]
    slope, intercept = np.polyfit(np.arange(length), window, 1)
    assert ported[-1] == pytest.approx(intercept + slope * (length - 2))


def test_wma_weights_the_newest_bar_hardest(frame):
    weighted = pine.wma(frame["close"], 5).iloc[-1]
    expected = np.dot(frame["close"].to_numpy()[-5:], [1, 2, 3, 4, 5]) / 15
    assert weighted == pytest.approx(expected)


def test_stdev_is_the_population_deviation(frame):
    """Pine's `ta.stdev` divides by n; pandas defaults to n-1."""
    ported = pine.stdev(frame["close"], 10).iloc[-1]
    window = frame["close"].to_numpy()[-10:]
    assert ported == pytest.approx(np.std(window, ddof=0))
    assert ported != pytest.approx(np.std(window, ddof=1))


def test_pine_smoothers_seed_with_a_simple_average(frame):
    """`ta.ema` is NaN until bar n-1, then starts from the SMA of that window."""
    smoothed = pine.ema(frame["close"], 10)
    assert smoothed.iloc[:9].isna().all()
    assert smoothed.iloc[9] == pytest.approx(frame["close"].iloc[:10].mean())

    alpha = 2 / 11
    expected = alpha * frame["close"].iloc[10] + (1 - alpha) * smoothed.iloc[9]
    assert smoothed.iloc[10] == pytest.approx(expected)


def test_rma_uses_wilders_alpha(frame):
    smoothed = pine.rma(frame["close"], 14)
    expected = frame["close"].iloc[14] / 14 + smoothed.iloc[13] * 13 / 14
    assert smoothed.iloc[14] == pytest.approx(expected)


def test_seeded_smoother_carries_through_a_gap():
    """A NaN mid-series holds the previous value, as `nz(x[1])` does in Pine."""
    series = pd.Series([1.0, 2.0, 3.0, np.nan, 5.0])
    smoothed = pine.ema(series, 2)
    assert not np.isnan(smoothed.iloc[3])
    assert smoothed.iloc[3] == pytest.approx(smoothed.iloc[2])


# ---------------------------------------------------------------- indicators


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_every_indicator_returns_the_frames_index(key, frame):
    output = pine.INDICATORS[key].read(frame)
    assert len(output) == len(frame)
    assert output.index.equals(frame.index)


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_declared_lines_exist_and_are_drawable(key, frame):
    """A line the catalogue promises must be numeric and not entirely absent."""
    indicator = pine.INDICATORS[key]
    output = indicator.read(frame)

    for column in indicator.lines:
        assert column in output, f"{key} promised a {column} line it did not return"
        series = output[column]
        assert pd.api.types.is_numeric_dtype(series)
        assert series.notna().any(), f"{key}.{column} is empty on a 400-bar frame"
        finite = series.dropna().to_numpy()
        assert np.isfinite(finite).all(), f"{key}.{column} produced inf"


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_overlays_stay_on_the_price_scale(key, frame):
    """An overlay shares the price axis, so a stray zero would flatten the chart.

    This is the regression that the HL OTT warm-up caused: Pine seeds its
    recursive averages at zero, which drew a line from 0 up to 100.
    """
    indicator = pine.INDICATORS[key]
    if indicator.pane != pine.OVERLAY:
        pytest.skip("oscillators have their own pane and their own scale")

    low, high = frame["low"].min(), frame["high"].max()
    span = high - low
    for column in indicator.lines:
        drawn = indicator.read(frame)[column].dropna()
        assert drawn.between(low - span, high + span).all(), \
            f"{key}.{column} left the price scale"


def test_indicators_refuse_a_frame_they_cannot_read(frame):
    """Close-only series must raise, not invent highs from the close."""
    close_only = frame[["date", "close"]]
    with pytest.raises(pine.MissingColumns, match="high"):
        pine.INDICATORS["supertrend"].read(close_only)


def test_available_filters_to_what_the_frame_supports(frame):
    close_only = frame[["date", "close"]]
    assert set(pine.available(frame)) == set(pine.INDICATORS)
    # MavilimW is the only one that needs nothing but a close.
    assert set(pine.available(close_only)) == {"mavilim"}
    assert pine.read_all(close_only).keys() == {"mavilim"}


def test_supertrend_ratchets_and_only_flips_on_a_break(rising):
    """The live stop may tighten while the trend holds, never loosen."""
    output = pine.supertrend(rising)
    trend, up = output["trend"], output["up"]

    held = up.notna() & up.shift(1).notna() & (trend == 1) & (trend.shift(1) == 1)
    assert (up[held] >= up.shift(1)[held] - 1e-9).all(), "the long stop loosened"

    # A flip is exactly a change of state, and the flags agree with it.
    flips = trend != trend.shift(1)
    assert (output["buy"] == (flips & (trend == 1))).all()
    assert (output["sell"] == (flips & (trend == -1))).all()
    assert set(trend.unique()) <= {1.0, -1.0}


def test_supertrend_follows_a_sustained_uptrend(rising):
    """A series that only goes up should end long, with the stop below price."""
    output = pine.supertrend(rising)
    assert output["trend"].iloc[-1] == 1
    assert output["supertrend"].iloc[-1] < rising["close"].iloc[-1]


def test_squeeze_detects_a_volatility_squeeze():
    """A flat stretch inside a volatile series is what "squeeze on" means."""
    rows = 300
    rng = np.random.default_rng(3)
    steps = rng.standard_normal(rows) * 0.8
    steps[150:230] *= 0.02  # a long quiet patch
    close = 100 + np.cumsum(steps)
    spread = np.abs(steps) * 0.5 + 0.01
    frame = pd.DataFrame({
        "date": pd.bdate_range("2021-01-01", periods=rows),
        "open": close, "high": close + spread, "low": close - spread, "close": close,
    })

    output = pine.squeeze_momentum(frame)
    assert output["squeeze_on"].iloc[170:230].any(), "missed an obvious squeeze"
    assert not output["squeeze_on"].iloc[40:140].all(), \
        "called the volatile stretch a squeeze"
    # The three states partition every warmed-up bar.
    warm = output.dropna(subset=["momentum"])
    assert (warm["squeeze_on"].astype(int) + warm["squeeze_off"].astype(int)
            + warm["no_squeeze"].astype(int) == 1).all()


def test_wavetrend_is_bounded_in_practice_and_crosses_zero(frame):
    output = pine.wavetrend(frame)
    wt1 = output["wt1"].dropna()
    # The 0.015 constant is chosen to keep the bulk inside +/-100; the fixed
    # +/-60 levels are meaningless otherwise.
    assert wt1.abs().quantile(0.95) < 150
    assert (wt1 > 0).any() and (wt1 < 0).any()
    assert output["difference"].equals(output["wt1"] - output["wt2"])


def test_wavetrend_survives_a_flat_series():
    """Zero deviation is a division by zero in Pine; here it must not be inf."""
    flat = pd.DataFrame({
        "date": pd.bdate_range("2022-01-01", periods=120),
        "high": 50.0, "low": 50.0, "close": 50.0,
    })
    wt1 = pine.wavetrend(flat)["wt1"]
    assert np.isfinite(wt1.dropna().to_numpy()).all()


def test_mavilim_uses_fibonacci_lengths_and_lags_a_turn(rising):
    output = pine.mavilim(rising)
    assert output["rising"].iloc[-1]

    # Six averages stacked over 3, 5, 8, 13, 21, 34 bars. Each one consumes
    # length-1 bars of the series beneath it, so the first honest reading lands
    # at the sum of those, not at 34.
    warmup = sum([3, 5, 8, 13, 21, 34]) - 6
    assert output["mavw"].iloc[:warmup].isna().all()
    assert output["mavw"].iloc[warmup:].notna().all()
    assert output["mavw"].iloc[-1] < rising["close"].iloc[-1], "no lag in a rising market"


def test_mavilim_turn_flags_are_actual_turns(frame):
    output = pine.mavilim(frame)
    line = output["mavw"]
    turned = output["turned_up"] & line.notna() & line.shift(2).notna()
    assert (line[turned] > line.shift(1)[turned]).all()
    assert (line.shift(1)[turned] <= line.shift(2)[turned]).all()


def test_vix_fix_spikes_into_a_crash():
    """The study exists to mark capitulation, so a crash must flag a bottom."""
    rows = 200
    rng = np.random.default_rng(11)
    # The uptrend needs real noise: on a perfectly smooth ramp the reading is
    # constant, its rolling deviation collapses to zero, and every bar ties with
    # its own Bollinger band. That degeneracy is a property of the fixture
    # rather than of the study.
    close = np.concatenate([
        np.full(150, 100.0) + np.linspace(0, 5, 150) + rng.standard_normal(150) * 0.8,
        np.linspace(105, 70, 50),  # the washout
    ])
    frame = pd.DataFrame({
        "date": pd.bdate_range("2021-01-01", periods=rows),
        "open": close, "high": close + 0.5, "low": close - 0.5, "close": close,
    })

    output = pine.williams_vix_fix(frame)
    assert output["wvf"].iloc[-1] > output["wvf"].iloc[:150].max()
    assert output["bottom"].iloc[160:].any(), "the crash did not flag a bottom"

    # It flags the odd pullback in the uptrend too — a relative-bottom finder
    # is supposed to — so the claim worth testing is density, not silence.
    calm = output["bottom"].iloc[:150].mean()
    washout = output["bottom"].iloc[150:].mean()
    assert washout > 3 * calm, f"crash flagged at {washout:.2f} vs {calm:.2f} in the calm"


def test_leledc_levels_only_move_on_an_exhaustion(frame):
    output = pine.leledc(frame)
    assert set(output["exhaustion"].unique()) <= {-1.0, 0.0, 1.0}
    assert (output["exhaustion"] != 0).any(), "no exhaustion in 400 bars"

    # A level is held flat until the next exhaustion bar of that direction.
    moved = output["resistance"].notna() & (output["resistance"].diff() != 0) \
        & output["resistance"].shift(1).notna()
    assert (output["exhaustion"][moved] == -1).all()

    tops = output["exhaustion"] == -1
    assert (output.loc[tops, "resistance"] == frame.loc[tops, "high"]).all()


def test_hl_ott_bands_bracket_the_price_and_lag_two_bars(frame):
    output = pine.hl_ott(frame)
    assert (output["hott"].dropna() >= output["lott"].dropna()).all(), \
        "the upper band fell through the lower one"

    # The published bands are the raw ones shifted two, as the study plots them.
    assert output["hott"].equals(output["hott_raw"].shift(2))
    assert output["lott"].equals(output["lott_raw"].shift(2))
    assert set(np.unique(output["state"])) <= {-1.0, 0.0, 1.0}


@pytest.mark.parametrize("ma_type", pine.OTT_MA_TYPES)
def test_hl_ott_supports_every_offered_moving_average(ma_type, frame):
    output = pine.hl_ott(frame, ma_type=ma_type)
    band = output["hott"].dropna()
    assert len(band) > 300, f"{ma_type} produced almost nothing"
    low, high = frame["low"].min(), frame["high"].max()
    assert band.between(low * 0.8, high * 1.2).all(), f"{ma_type} left the price scale"


def test_hl_ott_rejects_an_unknown_moving_average(frame):
    with pytest.raises(ValueError, match="unknown moving average"):
        pine.hl_ott(frame, ma_type="TRIPLE_HULL")


# ------------------------------------------------------- staying off the path


def test_pine_indicators_are_not_evidence_sources():
    """The separation this module exists to keep. See its docstring.

    `ultimate.evaluate` reads `dict(indicators.SOURCES)` wholesale, so anything
    landing there is folded into the live incumbent — silently, because the
    ensemble versions off `ultimate.py` alone.
    """
    assert not set(pine.INDICATORS) & set(indicators.SOURCES)
    for key in pine.INDICATORS:
        assert key not in indicators.SOURCES


def test_pine_module_does_not_mutate_the_evidence_catalogue(frame):
    """Importing and running the ports must leave `SOURCES` exactly as it was."""
    before = dict(indicators.SOURCES)
    pine.read_all(frame)
    assert indicators.SOURCES == before
    assert len(indicators.SOURCES) == len(before)


def test_pine_indicators_cannot_reach_a_forecast_through_the_registry():
    """Registered as a **lock**, not as a promotion — HT-1, 2026-08-16.

    This test previously asserted the studies were *absent* from the registry,
    on the premise that a registry entry is for something that can reach a
    forecast. HT-1 registers them so the census cannot drift, and the property
    that matters is asserted directly instead — which is strictly stronger than
    absence, because absence was only ever enforced by this test, while the
    entry is enforced by `ModelSpec.__post_init__`: a status outside
    `PRODUCTION_ADMISSIBLE` may not name a ledger key, so there is no route from
    a Pine study into a frozen forecast to begin with.
    """
    from core import model_registry

    registered = {spec.model_id: spec for spec in model_registry.specs()}
    for key in pine.INDICATORS:
        # Still never a technical source: `ultimate.evaluate` reads those.
        assert f"technical.{key}" not in registered

        spec = registered[f"pine.{key}"]
        assert spec.family == model_registry.PINE_STUDY
        assert spec.production_status == model_registry.EXPERIMENTAL
        assert spec.production_status not in model_registry.PRODUCTION_ADMISSIBLE
        assert spec.record_key is None, "a Pine study must have no ledger path"


# ------------------------------------------------------- the studies as agents


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_every_study_has_a_stated_rule_and_a_source(key):
    """A tradeable study must say what its rule is and where it came from."""
    indicator = pine.INDICATORS[key]
    assert key in pine.SIGNAL_RULES, f"{key} is tradeable but states no rule"
    assert pine.SIGNAL_RULES[key].strip()
    assert indicator.source.endswith(".txt"), f"{key} does not name its Pine script"


def test_every_named_source_script_exists(repo_root):
    """The provenance the UI prints has to be a file someone can open."""
    for indicator in pine.INDICATORS.values():
        assert (repo_root / "agent" / indicator.source).is_file(), \
            f"{indicator.name} names a missing script: {indicator.source}"


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_signals_are_backtester_events(key, frame):
    """`backtest.run` takes +1/-1/0 over the frame's index, and nothing else."""
    events = pine.signals(key, frame)

    assert len(events) == len(frame)
    assert events.index.equals(frame.index)
    assert set(np.unique(events)) <= {pine.BUY, pine.SELL, pine.HOLD}
    assert events.notna().all()


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_every_study_actually_trades_on_400_bars(key, frame):
    """A rule that never fires is not a strategy, it is a bug."""
    events = pine.signals(key, frame)
    assert (events != pine.HOLD).sum() >= 2, f"{key} produced almost no signals"


@pytest.mark.parametrize("key", list(pine.INDICATORS))
def test_signals_run_through_the_real_backtester(key, frame):
    """The point of the agents tab: the same engine scores these as the turtle."""
    from core import backtest, data

    events = pine.signals(key, frame)
    result = backtest.run(
        frame["close"], events, frame["date"], initial_money=10_000,
        periods_per_year=data.periods_per_year(frame["date"]),
    )
    assert np.isfinite(result.roi_pct)
    assert np.isfinite(result.buy_hold_roi_pct)
    assert len(result.equity) == len(frame)


def test_supertrend_signals_are_the_studys_own_flips(frame):
    """No reinterpretation: the buy/sell columns are the rule."""
    output = pine.supertrend(frame)
    events = pine.signals("supertrend", frame)
    assert (events == pine.BUY).equals(output["buy"].fillna(False))
    assert (events == pine.SELL).equals(output["sell"].fillna(False))


def test_wavetrend_only_trades_its_crossings_at_the_extremes(frame):
    """The conventional reading: a cross alone is not a signal."""
    output = pine.wavetrend(frame)
    events = pine.signals("wavetrend", frame)

    buys = events == pine.BUY
    assert (output["wt2"][buys] < -53).all(), "bought without being oversold"
    sells = events == pine.SELL
    assert (output["wt2"][sells] > 53).all(), "sold without being overbought"


def test_vix_fix_only_buys(frame):
    """It is a bottom finder: every entry is long, the exit is the added one."""
    output = pine.williams_vix_fix(frame)
    events = pine.signals("vix_fix", frame)
    assert output["bottom"][events == pine.BUY].all(), "bought an unflagged bar"


def test_bands_are_returned_for_overlays_and_withheld_for_oscillators(frame):
    for key, indicator in pine.INDICATORS.items():
        drawn = pine.bands(key, frame)
        if indicator.pane == pine.OVERLAY:
            assert drawn is not None and list(drawn.columns) == list(indicator.lines)
        else:
            assert drawn is None, f"{key} is an oscillator and has no price overlay"


def test_signals_rejects_an_unknown_study(frame):
    with pytest.raises(KeyError, match="no ported study"):
        pine.signals("ichimoku", frame)


def test_trading_the_studies_does_not_touch_strategies_or_the_registry(frame):
    """The rules live here precisely so `strategies.py` keeps its version.

    `rule_agent.*` versions off `app.core.strategies`; adding a fourth rule
    there would re-version the turtle, the crossover and the rolling agent
    against every forecast already in the ledger.
    """
    from core import strategies

    before = {name for name in dir(strategies) if not name.startswith("_")}
    for key in pine.INDICATORS:
        pine.signals(key, frame)
    assert {name for name in dir(strategies) if not name.startswith("_")} == before
