"""The TradingView axis gestures.

The gesture itself only exists in a browser, so what is testable here is the
contract it rests on: the three plotly class names it dispatches into, the
guard that stops a Streamlit rerun installing the listeners twice, and the
sensitivity actually reaching the script. Each of those fails silently — the
scales simply stop responding — which is exactly the kind of breakage worth a
cheap assertion.
"""

from __future__ import annotations

from core import axis_drag


def test_the_script_dispatches_into_plotly_own_bands():
    """`ewdrag` and `nsdrag` are where the wheel events go; `nsewdrag` is the
    pane body the pointer is hit-tested against. Renaming any of them in the
    script leaves a chart that looks right and scales nothing."""
    script = axis_drag.script()
    for handle in (".nsewdrag", ".ewdrag", ".nsdrag", ".js-plotly-plot"):
        assert handle in script


def test_the_listeners_install_once_per_session():
    """Streamlit re-runs the whole script on every widget change, so without
    the flag each rerun would add another set of document listeners and each
    drag would scale the axis n times over."""
    script = axis_drag.script()
    assert "if (win.__tvAxisDrag) return;" in script
    assert "win.__tvAxisDrag = true;" in script


def test_the_sensitivity_reaches_the_script():
    """A stray %(name)s would ship the placeholder as JavaScript."""
    script = axis_drag.script()
    assert "%(" not in script
    assert f"var NOTCHES_PER_PIXEL = {axis_drag.NOTCHES_PER_PIXEL};" in script


def test_it_gives_up_rather_than_throwing_when_the_page_is_out_of_reach():
    """The component is sandboxed; if a future Streamlit drops
    `allow-same-origin`, reading `window.parent.document` raises. The script
    has to return there, not leave a half-installed handler behind."""
    script = axis_drag.script()
    head = script[:script.index("win.__tvAxisDrag = true;")]
    assert "try {" in head and "catch (err) {" in head and "return;" in head
