"""The Streamlit app, driven headlessly.

These boot the real app via streamlit.testing, so they are all slow. They catch
the class of breakage unit tests cannot: a widget signature drift, a tab that
raises only when a particular mode is selected, an agent the dropdown can reach
but the training path cannot construct.

Widgets are located by scanning `.options` rather than by index. Positional
lookup (`at.radio[0]`) picks the wrong widget here, because sidebar creation
order is not render order.
"""

from __future__ import annotations

import pathlib

import pytest

APP_FILE = pathlib.Path(__file__).resolve().parents[1] / "streamlit_app.py"

pytestmark = pytest.mark.slow


# The sidebar defaults to this symbol; the Portfolio tab seeds this basket.
SEEDED_SYMBOLS = ["AAPL", "MSFT", "NVDA"]


@pytest.fixture(autouse=True)
def scratch_runs(tmp_path, monkeypatch):
    """Send saved runs to a scratch folder, not the user's real app/runs/.

    Training through the UI now persists a run, so without this the tests
    would litter whatever checkout they ran from — the same mistake the cache
    fixture below exists to prevent.
    """
    from core import runs

    directory = tmp_path / "runs"
    directory.mkdir()
    monkeypatch.setattr(runs, "RUNS_DIR", directory)
    return directory


@pytest.fixture(autouse=True)
def scratch_holdings(tmp_path, monkeypatch):
    """Send the book and the trade ledger to a scratch folder.

    The portfolio tab can now *write* — it has a Buy button — so without this
    a headless run posts a real position into whoever's holdings.json. It did
    exactly that once, which is also why `holdings.py` resolves these paths at
    call time rather than binding them in a default argument.
    """
    from core import holdings

    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")
    return tmp_path


@pytest.fixture(autouse=True)
def offline_cache(tmp_path, monkeypatch):
    """Give every test in this module a synthetic, offline market cache.

    Two problems this solves at once. First, the app's default data source is
    "Live ticker", so merely *booting* it downloaded several symbols — the
    suite was quietly dependent on Yahoo being up and wrote a real app/cache/
    into whatever checkout it ran from. Second, a fresh clone has no cache at
    all, so the Portfolio tab could not render and the chart counts differed
    between machines.

    Seeding a deterministic cache and blocking downloads fixes both: the tests
    are hermetic, and they exercise every tab rather than only the ones that
    survive without market data.
    """
    import numpy as np
    import pandas as pd

    from core import live

    monkeypatch.setattr(live, "CACHE_DIR", tmp_path)

    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2022-01-03", periods=420)
    for offset, symbol in enumerate(SEEDED_SYMBOLS):
        close = 100 + offset * 25 + np.cumsum(rng.standard_normal(len(dates)))
        live._write_cache(symbol, "1d", pd.DataFrame({
            "date": dates,
            "open": close, "high": close + 1, "low": close - 1, "close": close,
            "volume": rng.integers(1_000, 90_000, len(dates)).astype(float),
        }))

    # One weekly series too, so switching the toolbar's interval pill has
    # somewhere offline to land.
    weekly = pd.date_range("2022-01-03", periods=180, freq="7D")
    close = 100 + np.cumsum(rng.standard_normal(len(weekly)))
    live._write_cache(SEEDED_SYMBOLS[0], "1wk", pd.DataFrame({
        "date": weekly, "open": close, "high": close + 1, "low": close - 1,
        "close": close, "volume": rng.integers(1_000, 90_000, len(weekly)).astype(float),
    }))

    def refuse(symbol, period, interval):
        raise live.FetchError("network disabled in tests")

    monkeypatch.setattr(live, "_download", refuse)


def fresh_app(timeout=900, mode=None):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(APP_FILE), default_timeout=timeout)
    app.run()
    if mode:
        radio_offering(app, mode).set_value(mode).run()
    return app


def radio_offering(app, value):
    return next(widget for widget in app.radio if value in list(widget.options))


def select_offering(app, value):
    return next(widget for widget in app.selectbox if value in list(widget.options))


def train_button(app, agent_name):
    """The agent tab's Train button, specifically.

    The Forecast tab also renders a button starting with "Train" ("Train and
    forecast"), so matching on the prefix alone finds the wrong one.
    """
    wanted = f"train {agent_name.lower()}"
    return [button for button in app.button if button.label.lower() == wanted]


def assert_clean(app, context):
    assert not app.exception, f"{context}: {app.exception[0].message}"


@pytest.fixture
def bundled_app():
    """The Pro workbench on a tracked dataset — no network, no cache needed.

    Pro, because the agent, forecast and history tabs only exist there now.
    Lite is three tabs and deliberately cannot reach any of them.
    """
    app = fresh_app()
    assert_clean(app, "initial load")
    radio_offering(app, "Bundled dataset").set_value("Bundled dataset").run()
    radio_offering(app, "Pro").set_value("Pro").run()
    assert_clean(app, "select bundled source in Pro")
    return app


@pytest.fixture
def lite_app():
    """Lite on the seeded live cache — the decision-first view."""
    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, "lite on a live ticker")
    return app


# ------------------------------------------------------------------ rendering


@pytest.mark.parametrize("mode,least_charts", [("Lite", 3), ("Pro", 5)])
def test_app_renders_in_both_modes(mode, least_charts):
    app = fresh_app()
    assert_clean(app, "initial load")

    radio_offering(app, "Bundled dataset").set_value("Bundled dataset").run()
    radio_offering(app, mode).set_value(mode).run()
    assert_clean(app, f"{mode} mode")

    assert len(app.get("plotly_chart")) >= least_charts


def test_the_modes_are_different_applications():
    """Not the same app with fewer knobs — a different set of tabs.

    This is the assertion that would fail if Lite drifted back into being a
    trimmed Pro, which is what it was before the split.
    """
    lite = fresh_app(mode="Lite")
    pro = fresh_app(mode="Pro")
    assert_clean(lite, "lite")
    assert_clean(pro, "pro")

    def tab_labels(app):
        return {tab.label for tab in app.tabs} if hasattr(app, "tabs") else set()

    lite_tabs, pro_tabs = tab_labels(lite), tab_labels(pro)
    if lite_tabs:                       # AppTest exposes tabs from 1.36 on
        assert lite_tabs == {"Signal", "Chart", "Portfolio"}
        assert {"Trading agents", "Forecast", "Monte Carlo", "History"} <= pro_tabs

    # Whatever the harness exposes, Pro must reach controls Lite cannot.
    assert not [s for s in lite.selectbox if s.label == "Model"]
    assert [s for s in pro.selectbox if s.label == "Model"]
    assert not [s for s in lite.number_input if s.label == "Commission %"]
    assert [s for s in pro.number_input if s.label == "Commission %"]


def test_every_bundled_dataset_renders(bundled_app):
    """All four CSV layouts have to survive the whole app, not just the loader."""
    from core import data

    for name in data.list_datasets():
        # Re-locate every iteration: each run rebuilds the widget tree, which
        # invalidates any handle captured before it.
        select_offering(bundled_app, name).set_value(name).run()
        assert_clean(bundled_app, f"dataset {name}")


def test_live_ticker_serves_cache_when_offline():
    """Losing Yahoo must not take the app down.

    Downloads are blocked, so everything here comes off the seeded cache. This
    is the regression that would matter most to anyone working offline.
    """
    app = fresh_app()
    assert_clean(app, "initial load with no network")

    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, "live ticker with no network")
    # Lite is three tabs: the signal chart, and the price and distribution
    # panes behind it.
    assert len(app.get("plotly_chart")) >= 3


def test_unknown_symbol_is_reported_not_raised(monkeypatch):
    """A cache miss with no network shows an error and stops cleanly."""
    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    symbol = next(w for w in app.text_input if w.label == "Symbol")
    symbol.set_value("NOTAREALTICKER").run()

    assert_clean(app, "unknown symbol")
    assert app.sidebar.error, "expected a readable error in the sidebar"


# -------------------------------------------------------- the TradingView bar


def test_interval_pills_drive_the_fetch():
    """The toolbar owns the interval now; the sidebar only offers the history."""
    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    radio_offering(app, "W").set_value("W").run()
    assert_clean(app, "switch to weekly bars")
    # Only AAPL is seeded weekly, so the Portfolio tab legitimately loses its
    # holdings here. The price chart and the agent tab must still draw.
    assert len(app.get("plotly_chart")) >= 4
    assert any("Weekly" in str(block.value) for block in app.markdown)


def test_the_range_bar_offers_only_ranges_the_series_can_show():
    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    ranges = radio_offering(app, "All")
    offered = list(ranges.options)
    # 420 daily bars: no intraday "1D", and nowhere near five years.
    assert "1D" not in offered and "5Y" not in offered
    assert offered[-1] == "All"

    ranges.set_value("3M").run()
    assert_clean(app, "zoom to three months")


def test_the_watchlist_links_back_into_the_app():
    """Each row is an <a href="?sym=…">; that link is the whole interaction."""
    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, "live ticker rail")

    rail = " ".join(str(block.value) for block in app.markdown)
    for symbol in SEEDED_SYMBOLS:
        assert f'href="?sym={symbol}"' in rail, f"{symbol} missing from the watchlist"
    assert 'class="tv-wl-row on"' in rail, "the current symbol is not marked active"


def test_a_watchlist_row_still_works_after_a_symbol_is_typed():
    """Click MSFT, type NVDA, click MSFT again — the row must still answer.

    The href never changes, so a guard that remembered the last value it had
    applied saw nothing new on the second click and did nothing. `?sym=` is
    consumed on read instead: it is a one-shot instruction from a row, not a
    statement of what is on screen.
    """
    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    def charted():
        return next(w for w in app.text_input if w.key == "symbol").value

    app.query_params["sym"] = "MSFT"
    app.run()
    assert charted() == "MSFT"

    next(w for w in app.text_input if w.key == "symbol").set_value("NVDA").run()
    assert charted() == "NVDA"

    app.query_params["sym"] = "MSFT"
    app.run()
    assert charted() == "MSFT", "the row went dead once a symbol was typed"
    assert_clean(app, "re-clicking a watchlist row")


def test_a_consumed_symbol_does_not_override_the_next_thing_typed():
    """The stale parameter must not re-assert itself on the following rerun."""
    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    app.query_params["sym"] = "MSFT"
    app.run()
    next(w for w in app.text_input if w.key == "symbol").set_value("NVDA").run()
    app.run()          # any later rerun — a button, a slider, anything

    assert next(w for w in app.text_input if w.key == "symbol").value == "NVDA"


def test_the_watchlist_is_hidden_for_a_bundled_csv(bundled_app):
    """A CSV has no ticker, so a row linking to ?sym= would go nowhere."""
    rail = " ".join(str(block.value) for block in bundled_app.markdown)
    assert "?sym=" not in rail
    assert "Key stats" in rail, "the rail lost its stats panel too"


# ------------------------------------------------------- the ultimate signal


def markdown_text(app) -> str:
    return " ".join(str(block.value) for block in app.markdown)


def test_lite_leads_with_a_buy_hold_sell_call(lite_app):
    """The one thing Lite exists for has to be on screen without a click."""
    from core import ultimate

    page = markdown_text(lite_app)
    assert 'class="tv-verdict"' in page, "no verdict card rendered"
    assert any(action in page for action in ultimate.ACTIONS)
    assert 'class="tv-meter"' in page, "the call has no scale beside it"
    # One card per horizon, plus the hero.
    assert page.count('class="tv-hcard') >= 3


def test_the_verdict_names_all_three_horizons(lite_app):
    page = markdown_text(lite_app)
    for horizon in ("4 hours", "1 day", "1 week"):
        assert horizon in page, f"{horizon} missing from the signal tab"


def test_the_conclusion_is_written_out(lite_app):
    page = markdown_text(lite_app)
    assert "Net score" in page
    assert "confidence" in page


def test_an_unreadable_horizon_says_so_rather_than_guessing(lite_app):
    """Only AAPL is seeded hourly, so MSFT cannot answer the 4-hour horizon."""
    symbol = next(w for w in lite_app.text_input if w.label == "Symbol")
    symbol.set_value("MSFT").run()
    assert_clean(lite_app, "a symbol with no intraday bars")

    page = markdown_text(lite_app)
    assert "NO READ" in page or "too few" in page


def test_pro_shows_the_evidence_behind_the_call():
    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, "pro ultimate tab")

    headers = set()
    for table in app.dataframe:
        frame = getattr(table, "value", None)
        if frame is not None and hasattr(frame, "columns"):
            headers |= set(frame.columns)
    assert {"Hit rate %", "Independent", "t", "Weight %"} <= headers, (
        "the per-source calibration table is missing from Pro")


def test_pro_can_switch_off_the_agents():
    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    toggle = [t for t in app.toggle if "trading agents" in t.label]
    assert toggle, "no control for including the agents"
    toggle[0].set_value(False).run()
    assert_clean(app, "verdict without agents")


def test_the_forecast_toggle_measures_and_predicts_on_its_own():
    """Flipping it on does the work; it does not send you to another tab.

    Slow even at the smallest settings, because it really does train the
    network — which is the point, since the alternative was a warning telling
    the user to go and assemble the two halves by hand.
    """
    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    next(t for t in app.toggle if "forecast" in t.label).set_value(True).run()
    assert_clean(app, "forecast toggle on")

    # Cheapest run the sliders allow, so the test stays under a minute.
    next(s for s in app.slider if s.key == "ultimate_folds").set_value(2).run()
    next(s for s in app.slider if s.key == "ultimate_epochs").set_value(10).run()
    assert_clean(app, "forecast trained")

    labels = [m.label for m in app.metric]
    assert "Directional" in labels, "no measured accuracy reported"
    assert "Weight earned" in labels, "no verdict on whether it counts"

    # Measured, projected, and kept — so a rerun does not retrain it.
    trained = app.session_state["ultimate_model"]
    assert trained["walk"].folds
    assert trained["projection"].horizon > 0

    # And it says plainly when the model earned nothing, which is the usual case.
    said = " ".join([str(i.value) for i in app.info]
                    + [str(s.value) for s in app.success])
    assert "forecast" in said.lower()


def test_a_measured_forecast_is_not_retrained_on_every_rerun():
    """Without a fingerprint the toggle would retrain on each interaction."""
    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    next(t for t in app.toggle if "forecast" in t.label).set_value(True).run()
    next(s for s in app.slider if s.key == "ultimate_folds").set_value(2).run()
    next(s for s in app.slider if s.key == "ultimate_epochs").set_value(10).run()

    first = app.session_state["ultimate_model"]
    app.run()
    assert app.session_state["ultimate_model"] is first, "it retrained"


# ---------------------------------------------------------------- the portfolio


def buy_ticket(app, symbol, units, price):
    """Fill the trade ticket and press Buy. Returns the app after the rerun."""
    next(w for w in app.text_input if w.key == "trade_symbol").set_value(symbol)
    next(w for w in app.number_input if w.key == "trade_units").set_value(units)
    next(w for w in app.number_input if w.key == "trade_price").set_value(price)
    next(b for b in app.button if b.key == "trade_buy").click().run()
    return app


@pytest.mark.parametrize("mode", ["Lite", "Pro"])
def test_the_portfolio_is_tradeable_in_both_modes(mode):
    """Buying is not an advanced feature."""
    app = fresh_app(mode=mode)
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    assert [b for b in app.button if b.key == "trade_buy"], f"{mode} cannot buy"
    assert [b for b in app.button if b.key == "trade_sell"], f"{mode} cannot sell"


def test_a_buy_reaches_disk_and_shows_up_as_a_position():
    from core import holdings

    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    buy_ticket(app, "MSFT", 4.0, 125.0)
    assert_clean(app, "buy through the ticket")

    book = holdings.load()
    assert [h.symbol for h in book] == ["MSFT"]
    assert book[0].quantity == pytest.approx(4.0)
    assert [t.side for t in holdings.load_ledger()] == ["buy"]


def test_selling_more_than_held_is_reported_not_raised():
    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    buy_ticket(app, "MSFT", 2.0, 125.0)

    next(w for w in app.text_input if w.key == "trade_symbol").set_value("MSFT")
    next(w for w in app.number_input if w.key == "trade_units").set_value(99.0)
    next(b for b in app.button if b.key == "trade_sell").click().run()

    assert_clean(app, "oversized sell")
    assert any("does not go short" in str(e.value) for e in app.error)


def test_the_sell_button_is_disabled_without_a_position():
    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    next(w for w in app.text_input if w.key == "trade_symbol").set_value("ZZZZ")
    app.run()

    sell = next(b for b in app.button if b.key == "trade_sell")
    assert sell.disabled


@pytest.mark.parametrize("mode", ["Lite", "Pro"])
def test_edit_all_is_available_in_both_modes(mode):
    """Fixing a wrong cost basis is bookkeeping, not an advanced feature."""
    from core import holdings

    holdings.save([holdings.Holding("MSFT", 1.0, 100.0)])

    app = fresh_app(mode=mode)
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, f"{mode} portfolio with a position")

    assert [b for b in app.button if b.key == "save_all"], f"{mode} cannot edit"


@pytest.mark.parametrize("mode", ["Lite", "Pro"])
def test_the_portfolio_list_carries_the_ultimate_signal(mode):
    """The call belongs where it is actionable, not only on the signal tab."""
    from core import holdings

    holdings.save([holdings.Holding(symbol, 1.0, 100.0)
                   for symbol in SEEDED_SYMBOLS])

    app = fresh_app(mode=mode)
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, f"{mode} portfolio scan")

    positions = None
    for table in app.dataframe:
        frame = getattr(table, "value", None)
        columns = set(getattr(frame, "columns", []))
        if {"Symbol", "P&L", "Daily P&L", "Call", "Signal"} <= columns:
            positions = frame
            break

    assert positions is not None, "no positions table carrying a call"
    assert set(positions["Symbol"]) == set(SEEDED_SYMBOLS)
    assert positions["Call"].notna().all(), "a holding with no call"

    labels = [m.label for m in app.metric]
    assert "Book signal" in labels
    assert "Reading sell" in labels
    assert "Daily P&L" in labels, "Daily P&L metric missing from portfolio overview"


def test_the_research_tab_renders_on_an_empty_record(bundled_app):
    """Phase 8's normal case is the empty one, and it must not raise."""
    assert_clean(bundled_app, "Pro research tab")

    labels = [m.label for m in bundled_app.metric]
    assert "Forecasts frozen" in labels
    assert "Independent cutoffs" in labels
    assert "Promotion floor" in labels


def test_the_research_tab_says_why_it_is_thin(bundled_app):
    """A thin panel must not read as a measured null.

    Renamed from `..._says_why_it_is_empty` on 2026-08-15, when the owner
    authorised switching the ledger on. The assertion used to look for the
    first of Phase 8's three empty states ("no forecast has ever been
    frozen"), which was correct while the ledger did not exist and is simply
    false now that it does. The invariant being tested never changed: the tab
    must state, in words, why its numbers cannot carry a decision. So the test
    now asks `research_view` which of its states applies and requires *that*
    sentence — which keeps working as the record accumulates.
    """
    from core import research_view

    expected = research_view.sample_size_warning(research_view.load())
    assert expected is not None, (
        "the record is no longer thin — this test has outlived its premise "
        "and the promotion gate, not a warning banner, is now the guard")

    warnings = " ".join(str(getattr(w, "value", "")) for w in bundled_app.warning)
    assert expected[:40] in warnings, (
        f"no state explanation among: {warnings[:400]}")


def test_opening_the_research_tab_does_not_write_to_the_record(bundled_app):
    """Rendering reads frozen evidence and must never add to it.

    Was `..._does_not_start_a_record`, asserting the ledger file did not
    exist. That was the right guard while its absence was load-bearing for
    Phase 7 §6 and Phase 9 §6; the owner spent that guarantee deliberately on
    2026-08-15. The surviving invariant is stronger and outlasts activation:
    **opening a tab must not change the record.** A UI that appended on render
    would manufacture rows nobody forecast.
    """
    import sqlite3

    from core import forecast_ledger, research_view

    ledger_path = pathlib.Path(forecast_ledger.DEFAULT_PATH)

    def count() -> int:
        if not ledger_path.exists():
            return 0
        with sqlite3.connect(ledger_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0]

    before = count()
    assert_clean(bundled_app, "Pro research tab")
    assert count() == before

    # And the no-manufacture property itself, which activation did not repeal:
    # reading a ledger that is not there must not bring one into existence.
    missing = ledger_path.parent / "definitely_not_a_ledger.sqlite3"
    assert not missing.exists()
    assert research_view.load(missing).exists is False
    assert not missing.exists()


def test_lite_cannot_reach_the_research_tab():
    """Lite answers what to do; the research record is Pro's business."""
    app = fresh_app(mode="Lite")
    assert_clean(app, "Lite load")

    labels = [m.label for m in app.metric]
    assert "Independent cutoffs" not in labels


@pytest.mark.parametrize("mode", ["Lite", "Pro"])
def test_the_bar_pnl_is_named_after_the_bar_it_measures(mode):
    """On weekly bars the prior close is a week back, so it is not "Daily".

    The portfolio prices off whatever interval the toolbar is on. Measuring
    the move since the previous bar and calling it a day would overstate a
    weekly move as a daily one — the label has to follow the data.
    """
    from core import holdings

    holdings.save([holdings.Holding(SEEDED_SYMBOLS[0], 1.0, 100.0)])

    app = fresh_app(mode=mode)
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    next(w for w in app.radio if w.key == "interval_pill").set_value("W").run()
    assert_clean(app, f"{mode} portfolio on weekly bars")

    labels = [m.label for m in app.metric]
    assert "Weekly P&L" in labels, f"bar P&L not named for the bar: {labels}"
    assert "Daily P&L" not in labels, "weekly bars still labelled Daily"


def test_the_scan_agrees_with_the_signal_tab():
    """Two numbers for one ticker on one screen would be worse than none."""
    from core import holdings, ultimate

    holdings.save([holdings.Holding("AAPL", 1.0, 100.0)])

    app = fresh_app(mode="Pro")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, "scan against the signal tab")

    row = None
    for table in app.dataframe:
        frame = getattr(table, "value", None)
        if {"Symbol", "Call", "Signal"} <= set(getattr(frame, "columns", [])):
            row = frame[frame["Symbol"] == "AAPL"].iloc[0]
            break
    assert row is not None

    page = markdown_text(app)
    assert row["Call"] in page, (
        "the portfolio row and the verdict card disagree on AAPL")
    assert any(f"{row['Signal']:+.0f}" in str(m.value) for m in app.markdown)


def test_an_empty_book_still_offers_the_first_buy():
    app = fresh_app(mode="Lite")
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, "empty portfolio")

    assert [b for b in app.button if b.key == "trade_buy"]
    assert any("No positions yet" in str(item.value) for item in app.info)


# ------------------------------------------------------------------- training


# One per implementation family, so every training code path is exercised.
FAMILIES = [
    "Neuro-evolution",              # numpy GA
    "Policy gradient",              # TF, per-episode update
    "Duel Q-learning",              # TF, deepq family
    "Curiosity Q-learning",         # TF, intrinsic reward
    "Actor-critic",                 # TF, four networks
]


@pytest.mark.parametrize("agent_name", FAMILIES)
def test_agent_trains_through_the_ui(bundled_app, agent_name):
    select_offering(bundled_app, agent_name).set_value(agent_name).run()
    assert_clean(bundled_app, f"select {agent_name}")

    iterations = [s for s in bundled_app.slider if s.label == "Training iterations"]
    assert iterations, "no iteration slider rendered for an RL agent"
    iterations[0].set_value(5).run()

    train = train_button(bundled_app, agent_name)
    assert train, f"no Train button for {agent_name}"
    train[0].click().run()
    assert_clean(bundled_app, f"train {agent_name}")

    # The learning curve is the extra chart that only appears once trained.
    assert len(bundled_app.get("plotly_chart")) >= 6


def test_rule_based_agents_need_no_training(bundled_app):
    turtle = "Turtle (channel breakout)"
    select_offering(bundled_app, turtle).set_value(turtle).run()
    assert_clean(bundled_app, "turtle")

    assert not train_button(bundled_app, turtle)
    assert not [s for s in bundled_app.slider if s.label == "Training iterations"]


def test_every_registered_agent_is_reachable_from_the_dropdown(bundled_app):
    """A registered agent the UI cannot offer is dead code."""
    from core import agents

    picker = select_offering(bundled_app, "Neuro-evolution")
    offered = set(picker.options)
    assert set(agents.REGISTRY) <= offered


# ------------------------------------------------------------------- history


def test_history_tab_is_empty_before_anything_is_trained(bundled_app):
    assert_clean(bundled_app, "history with nothing saved")
    # The empty-state message, so a new user is not staring at a blank tab.
    messages = " ".join(str(item.value) for item in bundled_app.info)
    assert "Nothing saved yet" in messages


def test_training_survives_a_refresh(bundled_app, scratch_runs):
    """The whole point: train, throw the session away, still have the result."""
    from core import runs

    agent = "Neuro-evolution"
    select_offering(bundled_app, agent).set_value(agent).run()
    iterations = [s for s in bundled_app.slider if s.label == "Training iterations"]
    iterations[0].set_value(5).run()
    train_button(bundled_app, agent)[0].click().run()
    assert_clean(bundled_app, "train for history")

    # It reached disk, not just session state.
    saved = runs.load_all()
    assert len(saved) == 1
    assert saved[0].kind == runs.AGENT
    assert saved[0].settings["agent"] == agent
    assert "return_pct" in saved[0].metrics

    # A brand-new session — exactly what a browser refresh produces.
    reloaded = fresh_app(mode="Pro")
    radio_offering(reloaded, "Bundled dataset").set_value("Bundled dataset").run()
    assert_clean(reloaded, "after refresh")

    assert runs.load_all(), "the run vanished on refresh"
    assert not any("Nothing saved yet" in str(item.value) for item in reloaded.info)


def test_history_lists_and_deletes(bundled_app, scratch_runs):
    from core import runs

    for index in range(3):
        runs.save(runs.FORECAST, f"SERIES-{index}",
                  settings={"model": "lstm", "epochs": 10},
                  metrics={"directional_pct": 50.0 + index},
                  payload={"actual": [1.0, 2.0], "mean_forecast": [1.1, 2.1],
                           "naive": [1.0, 1.0]})

    app = fresh_app(mode="Pro")
    radio_offering(app, "Bundled dataset").set_value("Bundled dataset").run()
    assert_clean(app, "history listing")

    # The comparison table renders every saved run.
    assert len(runs.load_all()) == 3

    delete = [b for b in app.button if b.label == "Delete this run"]
    assert delete, "no delete control rendered"
    delete[0].click().run()
    assert_clean(app, "after delete")
    assert len(runs.load_all()) == 2

