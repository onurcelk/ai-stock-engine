"""Leakage and discipline tests for the V2 alpha pipeline.

The V1 study's guarantee rested on one test that rewrote the future and
demanded an identical verdict (`test_validation.py::test_future_cannot_change
_the_verdict`). V2 has a wider surface — a cross-section, a reconstructed
universe, an embargoed training window — so it gets the same treatment applied
at each place a future bar could get in:

* features and model predictions, against a rewritten future;
* index membership, against a name that joins later;
* the training window, against the horizon and the embargo;
* the sector peer group, against including the name itself;
* the statistics, against pretending serially correlated cutoffs are
  independent.

Everything is hermetic. `alpha/cache/` is a downloaded artefact that will not
exist on a fresh clone, so every test here builds its own panel in `tmp_path`.
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

from alpha import (adapter, build_panel, dataset, features, membership,  # noqa: E402
                   models, pitdata, stats, targets, universe)

SPLIT = 900          # bars before the divergence point
SYMBOLS = [f"SYM{i:02d}" for i in range(40)]


# ------------------------------------------------------------------ fixtures


def _panel_frames(shock: float, seed: int = 7) -> dict[str, pd.DataFrame]:
    """A synthetic market: identical to `shock=0` up to SPLIT, divergent after.

    The shock is a persistent per-symbol drift applied only to bars after the
    split, so any statistic that reads a single post-split bar changes and any
    statistic that does not cannot.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=SPLIT + 400)
    frames: dict[str, pd.DataFrame] = {}

    for index, symbol in enumerate(["SPY", "QQQ", "^VIX"] + SYMBOLS):
        steps = rng.standard_normal(len(dates)) * 0.011
        if shock and symbol not in ("SPY", "QQQ", "^VIX"):
            steps[SPLIT:] += shock * (1 if index % 2 else -1)
        close = 100.0 * np.exp(np.cumsum(steps))
        frames[symbol] = pd.DataFrame({
            "date": dates,
            "open": close * (1 + rng.standard_normal(len(dates)) * 0.001),
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": rng.integers(2_000_000, 9_000_000, len(dates)).astype(float),
        })
    return frames


def _write_cache(directory: pathlib.Path, frames: dict[str, pd.DataFrame]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for symbol, frame in frames.items():
        frame.to_csv(directory / f"{symbol.replace('^', '_')}.csv", index=False)


def _write_membership(meta: pathlib.Path, added_late: str | None = None,
                      added_on: str = "2021-01-04") -> None:
    """A tiny index whose composition changes on a known date."""
    meta.mkdir(parents=True, exist_ok=True)
    sectors = ["Information Technology", "Financials", "Health Care", "Energy"]
    rows = [{"ticker": s, "name": s, "sector": sectors[i % len(sectors)],
             "date_added": "2010-01-01"} for i, s in enumerate(SYMBOLS)]
    pd.DataFrame(rows).to_csv(meta / "sp500_current.csv", index=False)

    changes = []
    if added_late is not None:
        changes.append({"effective_date": added_on, "added": added_late, "removed": None})
    pd.DataFrame(changes, columns=["effective_date", "added", "removed"]).to_csv(
        meta / "sp500_changes.csv", index=False)
    (meta / "sector_overrides.json").write_text("{}", encoding="utf-8")


@pytest.fixture
def market(tmp_path, monkeypatch):
    """A factory: `market(shock)` returns a loaded book over a synthetic panel."""
    def make(shock: float, name: str = "base", added_late: str | None = None):
        root = tmp_path / name
        _write_cache(root, _panel_frames(shock))
        meta = root / "_meta"
        _write_membership(meta, added_late=added_late)
        monkeypatch.setattr(membership, "META_DIR", meta)
        membership._tables.cache_clear()
        membership.sector_map.cache_clear()
        pitdata.load_book.cache_clear()
        return pitdata.load_book(str(root))
    yield make
    membership._tables.cache_clear()
    membership.sector_map.cache_clear()
    pitdata.load_book.cache_clear()


# ------------------------------------------------------- the central guarantee


def test_future_cannot_change_the_features(market):
    """Rewrite everything after the cutoff; every feature must be bit-identical.

    This is the V2 analogue of the V1 study's load-bearing test. A scaler fitted
    on the whole series, a percentile computed over the full panel, a rolling
    window measured backwards from the end — any of them turns this red.
    """
    calm = market(0.0, "calm")
    storm = market(0.03, "storm")
    cutoff = calm.calendar[SPLIT - 1]

    left_view, right_view = calm.view(cutoff), storm.view(cutoff)
    sectors = pd.Series({s: "Information Technology" for s in SYMBOLS})

    left, _ = features.build(left_view, SYMBOLS, sectors, set(SYMBOLS[:5]),
                             tiers=("absolute", "relative", "context"))
    right, _ = features.build(right_view, SYMBOLS, sectors, set(SYMBOLS[:5]),
                              tiers=("absolute", "relative", "context"))

    assert list(left.columns) == list(right.columns)
    pd.testing.assert_frame_equal(left, right, check_exact=False, atol=1e-12)


def test_future_cannot_change_a_model_prediction(market):
    """The same guarantee, carried through a fitted model rather than a feature."""
    calm = market(0.0, "calm")
    storm = market(0.05, "storm")
    cutoff = calm.calendar[SPLIT - 1]
    schedule = [calm.calendar[i] for i in range(300, SPLIT, dataset.SPACING)]

    left_panel = dataset.build(calm, schedule, verbose=False)
    right_panel = dataset.build(storm, schedule, verbose=False)

    columns = left_panel.feature_columns
    left_fit = models.fit_model_a(left_panel.frame, columns)
    right_fit = models.fit_model_a(right_panel.frame, columns)
    assert left_fit is not None and right_fit is not None

    block_left = calm.view(cutoff)
    block_right = storm.view(cutoff)
    sectors = pd.Series({s: "Information Technology" for s in SYMBOLS})
    fl, _ = features.build(block_left, SYMBOLS, sectors, set(), tiers=("absolute",))
    fr, _ = features.build(block_right, SYMBOLS, sectors, set(), tiers=("absolute",))

    np.testing.assert_allclose(left_fit.predict(fl).to_numpy(),
                               left_fit.predict(fr).to_numpy(), atol=1e-12)


def test_view_cannot_reach_past_its_cutoff(market):
    book = market(0.0)
    cutoff = book.calendar[SPLIT - 1]
    view = book.view(cutoff)
    assert view.calendar.max() <= cutoff
    assert not hasattr(view, "forward_return")


# ------------------------------------------------------------ universe as-of-T


def test_membership_is_as_of_cutoff_not_today(market):
    """A name that joins the index in 2021 must be absent from a 2019 cross-section."""
    book = market(0.0, "late", added_late=SYMBOLS[0])
    early = membership.members_at(pd.Timestamp("2019-06-03"))
    late = membership.members_at(pd.Timestamp("2022-06-03"))

    assert SYMBOLS[0] not in early
    assert SYMBOLS[0] in late

    eligible_early = universe.eligible_at(pd.Timestamp("2019-06-03"), book)
    assert SYMBOLS[0] not in eligible_early.symbols


def test_eligibility_reports_coverage_loss(market):
    book = market(0.0)
    eligible = universe.eligible_at(book.calendar[SPLIT], book)
    diagnostics = eligible.diagnostics
    assert diagnostics["index_members"] >= diagnostics["priceable"] >= diagnostics["eligible"]
    assert 0 <= diagnostics["coverage_pct"] <= 100


# ------------------------------------------------------- embargo and overlap


def test_training_cutoffs_respect_horizon_and_embargo(market):
    """No training label may have resolved later than horizon+embargo before the test."""
    book = market(0.0)
    schedule = dataset.schedule(book, start="2018-06-01")
    test_cutoff = schedule[60]
    usable = dataset.training_cutoffs(schedule, test_cutoff, book)

    calendar = book.calendar
    limit = calendar.searchsorted(test_cutoff) - dataset.HORIZON - dataset.EMBARGO
    for cutoff in usable:
        assert calendar.searchsorted(cutoff) <= limit
        outcome_end = book.horizon_end(cutoff, dataset.HORIZON)
        assert outcome_end < test_cutoff


def test_cutoff_spacing_makes_outcome_windows_non_overlapping(market):
    """§5 option (a): spacing == horizon, so consecutive windows never share a day."""
    book = market(0.0)
    schedule = dataset.schedule(book, start="2018-06-01")
    for first, second in zip(schedule, schedule[1:]):
        end = book.horizon_end(first, dataset.HORIZON)
        assert end <= second


def test_the_built_panel_covers_every_exam_cutoff(market):
    """The exam paper must have rows, or stage 2 predicts nothing on most of it.

    `dataset.schedule` walks a 5-session grid from the study start; the twelve
    exam dates come from V1 and know nothing about that grid. Eight of the
    twelve fell off it, so the first exam run crashed on an empty cross-section
    — the panel simply had no rows for those dates. `panel_cutoffs` builds over
    the union, and the development list must not gain anything from it.
    """
    book = market(0.0)
    built, development, exam = build_panel.panel_cutoffs(book)

    assert set(exam) <= set(built), sorted(set(exam) - set(built))
    assert set(development) <= set(built)
    # Development is defined by the schedule alone; the union must not widen it.
    assert set(development) <= set(dataset.schedule(book))
    assert not set(development) & set(exam)


def test_exam_cutoffs_are_purged_from_development(market):
    book = market(0.0)
    schedule = dataset.schedule(book, start="2018-06-01")
    development, exam = dataset.split(schedule, book)
    calendar = book.calendar
    exam_positions = [calendar.searchsorted(e) for e in exam]
    for cutoff in development:
        position = calendar.searchsorted(cutoff)
        assert all(abs(position - e) > dataset.EXAM_GUARD for e in exam_positions)


# ---------------------------------------------------------- feature mechanics


def test_ratio_features_survive_a_zero_denominator(market):
    """§7-8 correction: an explicit floor, in code, not just as a principle."""
    book = market(0.0)
    cutoff = book.calendar[SPLIT]
    view = book.view(cutoff)

    volume = view.volume.copy()
    volume.iloc[-25:, :] = 0.0
    zeroed = pitdata.PriceView(view.cutoff, view.close, view.open, view.high,
                               view.low, volume)
    frame = features.absolute_block(zeroed.subset(SYMBOLS))

    assert np.isfinite(frame.to_numpy(dtype=float)).sum() > 0
    assert not np.isinf(frame.to_numpy(dtype=float)).any()


def test_sector_relative_leaves_the_name_itself_out(market):
    """A name compared against a peer group containing itself is comparing to noise."""
    values = pd.Series({"A": 1.0, "B": 2.0, "C": 3.0, "D": 10.0})
    sectors = pd.Series({"A": "X", "B": "X", "C": "X", "D": "Y"})
    loo = targets._leave_one_out_mean(values, sectors)

    assert loo["A"] == pytest.approx(2.5)      # mean of B and C, not of A,B,C
    assert np.isnan(loo["D"])                  # singleton group has no peers


def test_absolute_features_are_not_removed_by_the_relative_tier(market):
    """§7-8: 'do not pre-remove absolute features'."""
    book = market(0.0)
    view = book.view(book.calendar[SPLIT])
    sectors = pd.Series({s: "Information Technology" for s in SYMBOLS})
    absolute, _ = features.build(view, SYMBOLS, sectors, set(), tiers=("absolute",))
    both, _ = features.build(view, SYMBOLS, sectors, set(), tiers=("absolute", "relative"))
    assert set(absolute.columns) - {"sector"} <= set(both.columns)


def test_no_feature_is_dead_on_a_full_history(market):
    """A column that is NaN for every name at every cutoff is a bug, not a feature.

    `ret_12_1` was exactly this for a whole development run: its guard read
    `len(close) > 253` while the slice above it capped the frame at 253 rows,
    so the branch never fired. It cost four of the hundred columns and one of
    the six Model A′ baselines, and nothing failed — an all-NaN column is
    silently dropped at fit time, so the study just ran with 96 features and a
    baseline reporting n=0.

    Asserted on a view with 900 bars behind it, which is more history than the
    deepest feature asks for, so any all-NaN column here is an outright defect
    rather than a short-history NaN.
    """
    book = market(0.0)
    view = book.view(book.calendar[SPLIT])
    sectors = pd.Series({s: ["Information Technology", "Financials"][i % 2]
                         for i, s in enumerate(SYMBOLS)})
    frame, _ = features.build(view, SYMBOLS, sectors, set(SYMBOLS[:5]),
                              tiers=("absolute", "relative", "context"))

    dead = [c for c in frame.columns if not np.isfinite(frame[c].to_numpy(dtype=float)).any()]
    assert not dead, f"features are NaN for every symbol: {dead}"
    assert np.isfinite(frame["ret_12_1"]).any(), "12-1 momentum is the one that regressed"


def test_breadth_proxy_is_named_as_a_proxy(market):
    """§11 correction: the 22-name breadth must not masquerade as market breadth."""
    book = market(0.0)
    view = book.view(book.calendar[SPLIT])
    values, _ = features.context_block(view, SYMBOLS, set(SYMBOLS[:5]))
    proxies = [k for k in values if "watchlist_breadth_proxy" in k]
    real = [k for k in values if k.startswith("index_breadth")]
    assert proxies and real
    assert not any(k.startswith("breadth_") for k in values)


# -------------------------------------------------------------------- targets


def test_beta_falls_back_to_the_prior_on_a_short_history(market):
    """§1 correction: a beta that cannot be measured is 1.0, not a noisy number."""
    book = market(0.0)
    view = book.view(book.calendar[targets.BETA_MIN_OBS - 20])
    betas = targets.rolling_beta(view.subset(SYMBOLS), SYMBOLS, view.close["SPY"])
    assert (betas == targets.BETA_PRIOR).all()


def test_beta_shrinkage_scales_with_measurement_error(market):
    """Shrinkage is proportional to se(beta), so a noisy fit is pulled harder.

    The complement matters as much: on 252 clean observations the weight is
    ~0.98, so a well-measured beta is left almost untouched. Shrinkage that
    fired on every name regardless would be a bias, not a correction.
    """
    rng = np.random.default_rng(3)
    n = targets.BETA_WINDOW + 1
    dates = pd.bdate_range("2018-01-01", periods=n)
    market_steps = rng.standard_normal(n) * 0.01
    spy = pd.Series(100 * np.exp(np.cumsum(market_steps)), index=dates)

    def betas_of(idio: float) -> tuple[float, float]:
        """Returns (raw OLS beta, shrunk beta) for a series with this much noise."""
        steps = 1.0 * market_steps + rng.standard_normal(n) * idio
        close = pd.DataFrame({"X": 100 * np.exp(np.cumsum(steps))}, index=dates)
        view = pitdata.PriceView(dates[-1], close, close, close, close, close)
        shrunk = float(targets.rolling_beta(view, ["X"], spy)["X"])

        y = close["X"].pct_change().to_numpy()[1:]
        x = spy.pct_change().to_numpy()[1:]
        raw = float(np.cov(y, x, ddof=1)[0, 1] / x.var(ddof=1))
        return raw, shrunk

    clean_raw, clean_shrunk = betas_of(0.0005)
    noisy_raw, noisy_shrunk = betas_of(0.08)

    # Well measured: essentially untouched. Shrinkage that fired on every name
    # regardless would be a bias, not a correction.
    assert abs(clean_shrunk - clean_raw) < 0.01
    assert abs(clean_shrunk - 1.0) < 0.05

    # Badly measured: pulled a meaningful distance back toward the prior.
    assert abs(noisy_shrunk - 1.0) < abs(noisy_raw - 1.0)
    pull = abs(noisy_raw - noisy_shrunk) / max(abs(noisy_raw - 1.0), 1e-9)
    assert pull > 0.05


def test_beta_window_is_fixed_not_expanding(market):
    """An expanding window would give a later cutoff a different estimator."""
    book = market(0.0)
    early = book.view(book.calendar[SPLIT])
    assert targets.BETA_WINDOW == 252
    used = early.close.iloc[-(targets.BETA_WINDOW + 1):]
    assert len(used) == targets.BETA_WINDOW + 1


def test_alpha_target_subtracts_the_market(market):
    book = market(0.0)
    cutoff = book.calendar[SPLIT]
    sectors = pd.Series({s: "Information Technology" for s in SYMBOLS})
    outcome = targets.realise(book, cutoff, SYMBOLS, sectors)
    assert outcome is not None
    spy = book.forward_return(cutoff, targets.HORIZON, ["SPY"])["SPY"]
    expected = outcome.frame["asset_return"] - spy
    pd.testing.assert_series_equal(outcome.frame["alpha_5d"], expected,
                                   check_names=False)


def test_winsorising_touches_the_training_target_only(market):
    values = pd.Series(np.concatenate([np.linspace(-0.05, 0.05, 98), [-5.0, 5.0]]))
    trimmed = targets.winsorise(values)
    assert trimmed.max() < 5.0 and trimmed.min() > -5.0
    assert trimmed.iloc[:98].equals(values.iloc[:98])


# ----------------------------------------------------------------- statistics


def test_block_bootstrap_is_wider_than_the_naive_interval_under_autocorrelation():
    """The §5 correction, demonstrated rather than asserted."""
    rng = np.random.default_rng(0)
    noise = rng.standard_normal(400)
    correlated = pd.Series(pd.Series(noise).rolling(8).mean().dropna().to_numpy())

    series = stats.Series("ic", correlated)
    low, high = series.bootstrap_ci()
    naive_width = 2 * 1.96 * series.naive_se
    assert (high - low) > naive_width
    assert series.newey_west_se > series.naive_se


def test_spearman_ic_is_rank_based_not_level_based():
    predicted = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0] * 4)
    realised = predicted ** 3
    assert stats.spearman_ic(predicted, realised) == pytest.approx(1.0)


def test_holm_bonferroni_is_stricter_than_raw():
    """Two of these clear 0.05 raw and fail once the family is accounted for."""
    adjusted = stats.holm_bonferroni({"a": 0.005, "b": 0.03, "c": 0.045})
    assert all(adjusted[k]["p_holm"] >= adjusted[k]["p_raw"] for k in "abc")
    assert adjusted["a"]["significant"]
    assert not adjusted["b"]["significant"]     # raw 0.030 -> Holm 0.060
    assert not adjusted["c"]["significant"]     # raw 0.045 -> Holm 0.060


def test_quintile_spread_is_balanced_long_short(market):
    """§17: equal names on each side, so the spread cannot be net market exposure."""
    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2020-01-02")], [f"S{i}" for i in range(50)]],
        names=["cutoff", "symbol"])
    frame = pd.DataFrame({"prediction": np.arange(50, dtype=float),
                          "alpha_5d": np.arange(50, dtype=float)}, index=index)
    out = stats.quintile_spread(frame, "prediction", "alpha_5d")
    assert out["spread"].iloc[0] == pytest.approx(40.0)


# ---------------------------------------------------------------- integration


@pytest.mark.slow
def test_walk_forward_never_trains_on_a_future_cutoff(market):
    book = market(0.0)
    schedule = dataset.schedule(book, start="2018-06-01")
    panel = dataset.build(book, schedule, verbose=False)
    run = walk_forward_probe(panel, book)
    for record in run.fits:
        refit_at = pd.Timestamp(record["refit_at"])
        trained_through = pd.Timestamp(record["trained_through"])
        gap = book.calendar.searchsorted(refit_at) - book.calendar.searchsorted(trained_through)
        assert gap >= dataset.HORIZON + dataset.EMBARGO


def walk_forward_probe(panel, book):
    from alpha import walkforward
    return walkforward.walk_forward(panel, book, panel.feature_columns,
                                    min_train_cutoffs=20, verbose=False)


# ------------------------------------------------------- the §24-26 output layer


def _evidence(passed: bool, weight: float = 1.0, n_cutoffs: int = 400,
              mean_ic: float = 0.04) -> adapter.ModelEvidence:
    return adapter.ModelEvidence(
        weight=weight if passed else 0.0, passed_all_criteria=passed,
        criteria={f"{i}_x": passed for i in range(1, 8)}, n_cutoffs=n_cutoffs,
        mean_ic=mean_ic, spread=0.003, source="synthetic", note="test")


def test_adapter_never_exposes_a_target_price_or_a_confidence(market):
    """§23-24: the two numbers V1 got measurably wrong are not in the schema.

    Not "set to None" — absent. A field that exists is a field a template will
    eventually render, and the V1 study measured both of these losing to a
    trivial rule (price targets 62% of the time; the 90-100 confidence band
    scoring 40%).
    """
    rendered = adapter.view("AAA", "2026-01-05", 0.02, 0.95, _evidence(True),
                            regime="BULL_TREND", historical_spread=0.004)
    fields = set(rendered.to_dict())
    assert not fields & {"target_price", "confidence", "expected_move", "price_path"}
    assert {"gross_alpha", "net_alpha", "turnover", "cost_model"} <= fields
    assert rendered.evidence_strength in ("NONE", "WEAK", "MODERATE", "STRONG")


def test_adapter_holds_when_evidence_is_missing(tmp_path):
    """Fail closed: no scores file on disk must mean HOLD, not 'assume fine'."""
    evidence = adapter.load_evidence(tmp_path / "does_not_exist.json")
    assert evidence.weight == 0.0
    assert not evidence.passed_all_criteria
    assert evidence.strength == "NONE"

    action, reason = adapter.decide(0.9, 0.99, evidence,
                                    regime="BULL_TREND", historical_spread=1.0)
    assert action == adapter.Action.HOLD
    assert "insufficient model evidence" in reason


def test_adapter_cascade_holds_at_every_gate(market):
    """§25's cascade in order, each gate checked on its own.

    The first gate is closed in production today, so the ones below it would
    otherwise never execute. A gate nobody has watched run is a gate whose
    behaviour is unknown.
    """
    passing = _evidence(True)
    strong = dict(regime="BULL_TREND", historical_spread=0.004)

    # 1. insufficient evidence
    assert adapter.decide(0.02, 0.95, _evidence(False), **strong)[0] == adapter.Action.HOLD
    # 2. weak alpha
    assert adapter.decide(0.0, 0.95, passing, **strong)[0] == adapter.Action.HOLD
    # 3. non-extreme rank
    assert adapter.decide(0.02, 0.50, passing, **strong)[0] == adapter.Action.HOLD
    # 4. non-positive historical spread
    assert adapter.decide(0.02, 0.95, passing, regime="BULL_TREND",
                          historical_spread=-0.001)[0] == adapter.Action.HOLD
    # 5. out-of-validated-regime
    assert adapter.decide(0.02, 0.95, passing, regime="NOT_A_REGIME",
                          historical_spread=0.004)[0] == adapter.Action.HOLD
    # and missing inputs are HOLD, never a shrug-and-proceed
    assert adapter.decide(None, 0.95, passing, **strong)[0] == adapter.Action.HOLD
    assert adapter.decide(0.02, None, passing, **strong)[0] == adapter.Action.HOLD
    assert adapter.decide(0.02, 0.95, passing, regime="BULL_TREND",
                          historical_spread=None)[0] == adapter.Action.HOLD


def test_adapter_can_still_act_when_every_gate_opens(market):
    """The cascade must not be HOLD-only by accident — a closed gate is a choice.

    `VALIDATED_REGIMES` is empty today, which is what actually holds production
    at HOLD. Patching it is how this test distinguishes "nothing has been
    validated" from "the LONG branch is unreachable".
    """
    passing = _evidence(True)
    validated = frozenset({"BULL_TREND"})
    original = adapter.VALIDATED_REGIMES
    try:
        adapter.VALIDATED_REGIMES = validated
        long_action, _ = adapter.decide(0.02, 0.95, passing, regime="BULL_TREND",
                                        historical_spread=0.004)
        short_action, _ = adapter.decide(-0.02, 0.03, passing, regime="BULL_TREND",
                                         historical_spread=0.004)
    finally:
        adapter.VALIDATED_REGIMES = original

    assert long_action == adapter.Action.LONG
    assert short_action == adapter.Action.SHORT
    # ...and with the real, empty set, the same call is a HOLD.
    assert adapter.decide(0.02, 0.95, passing, regime="BULL_TREND",
                          historical_spread=0.004)[0] == adapter.Action.HOLD


def test_adapter_does_not_import_validation_or_app():
    """§0: the adapter is a one-way layer. Validation logic is never touched."""
    source = (REPO / "alpha" / "adapter.py").read_text(encoding="utf-8")
    assert "from validation" not in source and "import validation" not in source
    assert "from app" not in source and "import app" not in source
