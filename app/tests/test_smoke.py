"""End-to-end smoke test for the whole `core` package.

The unit tests next to this one each pin down one module's contract in
detail. What nothing covered was the seams: a rename in one module that
breaks an importer, a new source that reads out of range on real-shaped
data, a cache change that stops surviving a restart. Those are exactly the
failures that reach a user while every module's own suite stays green.

So this file boots the whole engine the way the app does -- import every
module, load every bundled dataset, push one synthetic frame through data ->
indicators -> strategies -> backtest / portfolio / montecarlo, run the
composed verdict in `ultimate` over every horizon, and take the live-cache
path through a write, a restart-equivalent read, and an offline fetch. It is
deliberately shallow: each check asserts "runs and returns something sane",
not exact values, which is the unit tests' job.

Hermetic by construction: no network (the `offline` fixture refuses any
download), no TensorFlow training, and the root conftest's backup guard
keeps the ledger lifecycle away from the real drive. The filings checks are
written to hold whether or not `alpha/edgar/facts.parquet` is on the machine
-- only the small JSON metas are tracked, so the populated branch would
otherwise be exercised on the box that built the cache and nowhere else.
Runtime budget is a few seconds so it earns its place in the default fast run.
"""

from __future__ import annotations

import importlib
import json
import pathlib

import numpy as np
import pandas as pd
import pytest

from core import (backtest, data, filings_evidence, indicators, montecarlo,
                  portfolio, strategies, ultimate)


# --------------------------------------------------------------- import sweep

def test_every_core_module_imports():
    """A broken import anywhere in `core` must fail loudly here.

    Walks the package tree rather than listing names, so a module added
    tomorrow is covered without touching this file. Subpackages (agents/)
    resolve naturally through dotted names.
    """
    import core

    package_dir = pathlib.Path(core.__file__).resolve().parent
    modules = sorted(
        p.relative_to(package_dir).with_suffix("").as_posix().replace("/", ".")
        for p in package_dir.rglob("*.py")
        if p.name != "__init__.py"
    )
    assert modules, "core package disappeared?"
    for name in modules:
        module = importlib.import_module(f"core.{name}")
        assert module is not None


# ------------------------------------------------------------------ data layer

def test_data_normalise_cleans_a_messy_frame():
    """Currency marks, stray spaces, thousands separators, rows out of order."""
    messy = pd.DataFrame({
        "Date": ["01/04/2024", "01/02/2024", "01/03/2024"],
        "Close": ["1,003", "$1,001.50", " 1002.5 "],
        "Volume": [30, 10, 20],
    })
    out = data.normalise(messy)
    assert list(out.columns) == ["date", "close", "volume"]
    assert len(out) == 3
    assert pd.api.types.is_datetime64_any_dtype(out["date"])
    # Ascending regardless of input order -- the frame above is shuffled, so
    # this fails if the sort ever comes out of normalise.
    assert out["date"].is_monotonic_increasing
    assert out["close"].tolist() == [1001.5, 1002.5, 1003.0]
    assert out["volume"].tolist() == [10.0, 20.0, 30.0]
    # And the index is positional again, which every downstream `.iloc` assumes.
    assert out.index.tolist() == [0, 1, 2]


def test_data_normalise_rejects_degenerate_frames():
    with pytest.raises(ValueError):
        data.normalise(pd.DataFrame({"close": [1.0, 2.0]}))
    # Unparseable dates leave no rows, which normalise refuses to paper over.
    with pytest.raises(ValueError):
        data.normalise(pd.DataFrame({"date": ["not a date"] * 3,
                                     "close": [1.0, 2.0, 3.0]}))


def test_load_bundled_dataset(bundled_close):
    """The canary dataset still loads and parses into the shared shape."""
    assert len(bundled_close) > 200
    assert bundled_close.notna().all()


def test_every_bundled_dataset_loads():
    """All of `dataset/` through `normalise`, not just the canary.

    Driven off `list_datasets()` so a CSV added tomorrow is covered without
    touching this file. It earns its place because the awkward layouts live
    here: the FX files (`eur-myr`, `usd-myr`) have no real header at all and
    reach `normalise` through its positional fallback, and `GOOG` and `oil`
    are short enough that anything assuming a year of bars breaks on them.
    """
    names = data.list_datasets()
    assert names, "bundled dataset directory came back empty"
    for name in names:
        frame = data.load(name)
        assert {"date", "close"} <= set(frame.columns), name
        assert len(frame) > 20, name
        assert frame["close"].notna().all(), name
        assert (frame["close"] > 0).all(), name
        assert frame["date"].is_monotonic_increasing, name


# -------------------------------------------------------------- indicator wall

def test_every_indicator_source_stays_on_scale(synthetic_ohlcv):
    """The whole point of `Source.read` is finite readings inside [-1, 1].

    Every registered source is exercised, so a new one added to SOURCES is
    automatically included in this guarantee.
    """
    assert indicators.SOURCES, "indicator registry came back empty"
    frame = synthetic_ohlcv.set_index("date")
    for key, source in indicators.SOURCES.items():
        read = source.read(frame)
        assert isinstance(read, pd.Series), f"{key} did not return a Series"
        assert len(read) == len(frame)
        assert np.isfinite(read.to_numpy()).all(), f"{key} produced non-finite values"
        assert read.abs().max() <= 1.0 + 1e-9, f"{key} escaped [-1, 1]"


#: What a close-only daily frame cannot support an opinion about: the volume
#: sources have no volume, `adx` and `opening_range` have no high/low or
#: intraday session, and `pead` has no filing columns. Silence is the contract
#: for all five -- a flat zero reads as "no opinion" to the calibrator, which
#: is a different claim from a small reading and must not decay into one.
SILENT_WITHOUT_THEIR_COLUMNS = {
    "adx", "obv", "vwap_reversion", "opening_range", "pead",
}


def test_volume_sources_degrade_to_zero_not_crash(bundled_close):
    """A close-only frame (no volume column) must yield zeros, not raise.

    Asserted as set equality rather than one-way, so this trips both when a
    source stops degrading quietly and when one that used to have an opinion
    here goes silent.
    """
    frame = pd.DataFrame({"close": bundled_close})
    silent = set()
    for key, source in indicators.SOURCES.items():
        read = source.read(frame)  # the contract: never raises, stays bounded
        assert np.isfinite(read.to_numpy()).all(), key
        assert read.abs().max() <= 1.0 + 1e-9, key
        if (read == 0).all():
            silent.add(key)
    assert silent == SILENT_WITHOUT_THEIR_COLUMNS


# --------------------------------------------------------------- filings seam

def test_filings_evidence_attaches_all_or_nothing(synthetic_ohlcv):
    """`attach` supplies both columns or neither -- never half a frame.

    Half would be worse than none: `_pead_drift` reads `sue` and
    `days_since_filing` together, and a frame carrying one of them would take
    the populated branch with the other missing. Holds on a machine without
    the parquet cache, where the honest answer is the frame unchanged.
    """
    before = set(synthetic_ohlcv.columns)
    out = filings_evidence.attach(synthetic_ohlcv.copy(), "AAPL")
    added = set(out.columns) - before
    assert added in (set(), {filings_evidence.SUE_COLUMN,
                             filings_evidence.AGE_COLUMN}), added
    assert len(out) == len(synthetic_ohlcv)

    # An unknown ticker is a lookup miss, not an error, and adds nothing.
    unknown = filings_evidence.attach(synthetic_ohlcv.copy(), "NOSUCHTICKER")
    assert set(unknown.columns) == before


def test_pead_reads_the_filing_columns_and_stays_on_scale(synthetic_ohlcv):
    """The populated branch, on columns built here rather than from the cache.

    `pead` is the one source reading something other than price, and the cache
    it normally reads is untracked -- so without a synthetic frame this path
    would only ever run on the machine that downloaded EDGAR.
    """
    frame = synthetic_ohlcv.copy()
    age = (np.arange(len(frame)) % 90).astype(float)   # straddles the decay edge
    frame[filings_evidence.SUE_COLUMN] = np.linspace(-3.0, 3.0, len(frame))
    frame[filings_evidence.AGE_COLUMN] = age

    read = indicators.SOURCES["pead"].read(frame.set_index("date"))
    assert np.isfinite(read.to_numpy()).all()
    assert read.abs().max() <= 1.0 + 1e-9
    assert read.abs().max() > 0, "pead stayed silent with its columns present"
    # Past the drift window there is nothing left to say.
    assert (read.to_numpy()[age > indicators.DRIFT_DAYS] == 0).all()


# ------------------------------------------- strategy -> execution, end to end

def test_strategies_emit_valid_signals_and_backtest_executes_them(synthetic_ohlcv):
    close = synthetic_ohlcv["close"]
    dates = synthetic_ohlcv["date"]

    turtle = strategies.turtle(close, window=20, follow_breakout=True)
    cross = strategies.moving_average(close, short_window=5, long_window=20)
    roll = strategies.signal_rolling(close, delay=3)

    for name, signal in (("turtle", turtle), ("ma", cross), ("rolling", roll)):
        assert len(signal) == len(close)
        assert set(signal.unique()).issubset({-1.0, 0.0, 1.0}), name

    result = backtest.run(close, cross, dates, initial_money=10_000.0,
                          sizing=backtest.ALL_IN)
    assert result.final_value > 0
    assert np.isfinite(result.equity.to_numpy()).all()
    assert result.roi_pct == pytest.approx(
        (result.final_value - 10_000.0) / 10_000.0 * 100)
    # The benchmark is costed like-for-like and always computable.
    assert np.isfinite(result.buy_hold_roi_pct)


def test_backtest_respects_cash_and_fees(synthetic_ohlcv):
    close = synthetic_ohlcv["close"]
    dates = synthetic_ohlcv["date"]
    signal = pd.Series(1.0, index=close.index)  # buy on bar one, hold forever

    result = backtest.run(close, signal, dates, initial_money=10_000.0,
                          fee_pct=0.1, slippage_pct=0.1, sizing=backtest.ALL_IN)
    assert result.fees_paid >= 0
    assert result.inventory >= 1 or result.cash < 10_000.0
    table = backtest.trade_table(result)
    assert list(table.columns) == [
        "Bought", "Buy price", "Sold", "Sell price", "Units", "Profit", "Return %"
    ]


# ------------------------------------------------------- portfolio & simulation

@pytest.fixture
def two_frames(synthetic_ohlcv):
    other = synthetic_ohlcv.copy()
    other["close"] = 50 + np.linspace(0, 25, len(other))  # steady climber
    return {"AAA": synthetic_ohlcv, "BBB": other}


def test_portfolio_align_build_and_stats(two_frames):
    prices = portfolio.align(two_frames)
    assert prices.shape[1] == 2
    assert prices.notna().all().all()

    weights = portfolio.normalise_weights({"AAA": 60.0, "BBB": 60.0})  # over-allocated
    assert sum(weights.values()) == pytest.approx(100.0)

    result = portfolio.build(prices, weights, initial_money=10_000.0,
                             rebalance_every=21)
    assert result.final_value > 0
    assert result.rebalanced >= 1
    assert sum(result.final_weights.values()) == pytest.approx(100.0)
    assert np.isfinite(result.volatility_pct)
    corr = portfolio.correlations(prices)
    assert ((corr >= -1.0) & (corr <= 1.0)).all().all()


def test_montecarlo_produces_a_sane_fan(bundled_close):
    result = montecarlo.run(bundled_close, days=30, simulations=100, seed=11)
    assert result.paths.shape == (31, 100)
    assert (result.paths.to_numpy() > 0).all()
    summary = result.summary()
    assert summary["p5"] <= summary["median"] <= summary["p95"]
    assert 0.0 <= summary["prob_up"] <= 100.0


# ----------------------------------------------------------- composed verdict

def test_every_registered_source_reaches_the_engine(synthetic_ohlcv):
    """A source in the registry must actually be read by `ultimate`.

    This is the seam a new source slips through: `indicators` grows an entry,
    every indicator test still passes because they drive `SOURCES` directly,
    and the engine never picks it up. The agents arrive on the same list, as
    evidence rather than as authority, so they are checked here too.
    """
    verdict = ultimate.evaluate_frame(
        synthetic_ohlcv, ultimate.HORIZON_BY_KEY["1d"])
    assert verdict.available, verdict.unavailable

    read = {r.key for r in verdict.readings}
    assert set(indicators.SOURCES) <= read, set(indicators.SOURCES) - read
    assert {r.key for r in verdict.readings if r.kind == ultimate.AGENT}

    # Every reading carries the family it was registered under, which is what
    # the family cap divides the weight by.
    assert all(r.family for r in verdict.readings)
    assert sum(r.weight for r in verdict.readings) <= 1.0 + 1e-9


def test_every_horizon_answers_or_declines(synthetic_ohlcv):
    """No horizon may crash on a frame that cannot support it.

    260 daily bars is too coarse for the 4-hour horizon and too short for the
    1-week one, so this run exercises both branches: one readable verdict and
    two refusals that say why.
    """
    verdicts = [ultimate.evaluate_frame(synthetic_ohlcv, h)
                for h in ultimate.HORIZONS]
    assert any(v.available for v in verdicts)

    for verdict in verdicts:
        if not verdict.available:
            assert verdict.unavailable.strip(), verdict.horizon.key
            assert verdict.score == 0.0 and verdict.confidence == 0.0
            continue
        assert verdict.action in ultimate.ACTIONS
        assert -100.0 <= verdict.score <= 100.0
        assert 0.0 <= verdict.confidence <= 100.0
        assert 0.0 <= verdict.agreement <= 1.0
        assert 0.0 <= verdict.coverage <= 1.0
        assert np.isfinite(verdict.expected_move_pct)
        assert len(verdict.table()) == len(verdict.readings)


# ------------------------------------------------------------ live cache & quotes

def test_offline_fetch_without_cache_raises(temp_cache, offline):
    from core import live

    with pytest.raises(live.FetchError):
        live.fetch("NOSUCH", period="1y", interval="1d")


def test_cache_round_trip_serves_an_offline_fetch(temp_cache, offline):
    """Write a cache, then answer a fetch with the network refused."""
    from core import live

    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2024-01-02", periods=300)
    closes = 100 + np.cumsum(rng.standard_normal(300))
    frame = pd.DataFrame({"date": dates, "close": closes})

    live._write_cache("SMOKE", "1d", frame, period="5y")
    fetched, entry = live.fetch("SMOKE", period="5y", interval="1d")

    assert entry.symbol == "SMOKE"
    assert entry.period == "5y"
    assert entry.is_fresh
    assert len(fetched) == len(frame)
    # A narrower request trims the stored frame rather than refetching.
    trimmed, _ = live.fetch("SMOKE", period="1mo", interval="1d")
    assert len(trimmed) < len(fetched)

    entries = live.cache_entries()
    assert any(e.symbol == "SMOKE" for e in entries)
    assert live.clear_cache("SMOKE", "1d") == 2  # csv + sidecar metadata


def test_quotes_read_straight_from_cache(temp_cache):
    """The watchlist rail answers from disk alone, network never involved."""
    from core import quotes

    directory = temp_cache
    pd.DataFrame({
        "date": pd.bdate_range("2024-06-03", periods=5),
        "close": [101.0, 102.0, 100.5, 103.25, 104.0],
    }).to_csv(directory / "SMOKE__1d.csv", index=False)
    (directory / "SMOKE__1d.meta.json").write_text(json.dumps({
        "symbol": "SMOKE", "interval": "1d",
        "fetched_at": "2026-08-24T12:00:00",
        "rows": 5, "period": "5y",
    }), encoding="utf-8")

    quote = quotes.read_quote("SMOKE", interval="1d")
    assert quote is not None
    assert quote.last == pytest.approx(104.0)
    assert quote.change == pytest.approx(0.75)
    assert quote.change_pct == pytest.approx(0.75 / 103.25 * 100)
    assert quote.asset == "EQUITY"

    rows = quotes.board(["smoke", "UNCACHED"])
    assert [r["symbol"] for r in rows] == ["SMOKE", "UNCACHED"]
    assert rows[1]["last"] is None  # listed but quote-less, exactly as documented

    assert quotes.currency("EURUSD=X") == "USD"
    assert quotes.currency("BTC-USD") == "USD"
    assert quotes.asset_class("BTC-USDT") == "CRYPTO"
