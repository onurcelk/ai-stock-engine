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


def test_live_ticker_path(tmp_path):
    """Only meaningful when a cache exists; app/cache/ is gitignored."""
    from core import live

    if not live.cache_entries():
        pytest.skip("no cached symbols — run the app once, or go online")

    app = fresh_app()
    radio_offering(app, "Live ticker").set_value("Live ticker").run()
    assert_clean(app, "live ticker")


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
