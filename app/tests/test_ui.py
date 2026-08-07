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

    def refuse(symbol, period, interval):
        raise live.FetchError("network disabled in tests")

    monkeypatch.setattr(live, "_download", refuse)


def fresh_app(timeout=900):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(APP_FILE), default_timeout=timeout)
    app.run()
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
    """The app pointed at a tracked dataset — no network, no cache needed."""
    app = fresh_app()
    assert_clean(app, "initial load")
    radio_offering(app, "Bundled dataset").set_value("Bundled dataset").run()
    assert_clean(app, "select bundled source")
    return app


# ------------------------------------------------------------------ rendering


@pytest.mark.parametrize("mode", ["Lite", "Pro"])
def test_app_renders_in_both_modes(mode):
    app = fresh_app()
    assert_clean(app, "initial load")

    radio_offering(app, "Bundled dataset").set_value("Bundled dataset").run()
    radio_offering(app, mode).set_value(mode).run()
    assert_clean(app, f"{mode} mode")

    assert len(app.get("plotly_chart")) >= 5
    assert len(app.metric) >= 5


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
    assert len(app.get("plotly_chart")) >= 5


def test_unknown_symbol_is_reported_not_raised(monkeypatch):
    """A cache miss with no network shows an error and stops cleanly."""
    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()

    symbol = next(w for w in app.text_input if w.label == "Symbol")
    symbol.set_value("NOTAREALTICKER").run()

    assert_clean(app, "unknown symbol")
    assert app.sidebar.error, "expected a readable error in the sidebar"


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
    reloaded = fresh_app()
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

    app = fresh_app()
    radio_offering(app, "Bundled dataset").set_value("Bundled dataset").run()
    assert_clean(app, "history listing")

    # The comparison table renders every saved run.
    assert len(runs.load_all()) == 3

    delete = [b for b in app.button if b.label == "Delete this run"]
    assert delete, "no delete control rendered"
    delete[0].click().run()
    assert_clean(app, "after delete")
    assert len(runs.load_all()) == 2
