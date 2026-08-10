"""The TradingView chrome.

Styling is not worth asserting on, but three things here are: the number
formatting, which is what stops a watchlist column from printing "-3" beside
"312.41"; the watchlist links, which are the only interaction read-only HTML
has; and the palette agreeing with the candles, which is the whole reason
theme.py imports from charts.py rather than restating the hex values.
"""

from __future__ import annotations

import pytest

from core import charts, theme


# ------------------------------------------------------------------ palette


def test_the_page_and_the_candles_share_one_palette():
    assert theme.BACKGROUND == charts.BACKGROUND
    assert theme.PANEL == charts.PANEL
    assert theme.BORDER == charts.BORDER
    assert (theme.UP, theme.DOWN) == (charts.UP, charts.DOWN)


def _rendered_css() -> str:
    """The stylesheet as `inject()` would emit it, without a Streamlit runtime."""
    return theme._CSS.substitute(
        FONT=theme.FONT, BG=theme.BACKGROUND, PANEL=theme.PANEL,
        BORDER=theme.BORDER, HOVER=theme.HOVER, RAISED=theme.RAISED,
        TEXT=theme.TEXT, MUTED=theme.MUTED, BRIGHT=theme.BRIGHT,
        BLUE=theme.BLUE, UP=theme.UP, DOWN=theme.DOWN, FAINT=theme.FAINT,
    )


def test_css_substitutes_every_placeholder():
    """A stray $NAME would ship a literal "$NAME" into the stylesheet."""
    css = _rendered_css()
    assert "$" not in css
    assert css.count("<style>") == 1


@pytest.mark.parametrize("change,expected", [
    (1.5, "tv-up"), (-1.5, "tv-dn"), (0.0, "tv-flat"),
])
def test_direction_classes(change, expected):
    assert theme.direction(change) == expected


# --------------------------------------------------------------- formatting


@pytest.mark.parametrize("value,expected", [
    (312.41, "312.41"),          # equities: two places
    (1_928.5, "1,928.50"),
    (23.71, "23.710"),           # cheap names get a third
    (1.0853, "1.085"),
    (0.00004231, "0.00004"),     # sub-dollar crypto and FX get five
])
def test_price_precision_follows_the_instrument(value, expected):
    assert theme.price(value) == expected


@pytest.mark.parametrize("change,reference,expected", [
    (-3.0, 211.30, "-3.00"),     # the bug this exists for: not a bare "-3"
    (1.41, 312.41, "+1.41"),
    (0.65, 23.71, "+0.650"),
    (-0.0004, 1.0853, "-0.000"),
])
def test_delta_is_quoted_to_the_price_it_moved(change, reference, expected):
    assert theme.delta(change, reference) == expected


@pytest.mark.parametrize("value,expected", [
    (26_720_000, "26.72M"), (47_780_000_000, "47.78B"),
    (4_310, "4.31K"), (912.5, "912.50"), (None, "—"),
])
def test_compact_is_how_a_quote_board_writes_volume(value, expected):
    assert theme.compact(value) == expected


# ----------------------------------------------------------------- watchlist


def rows():
    return [
        {"symbol": "AAPL", "last": 312.41, "change": 1.41, "change_pct": 0.45},
        {"symbol": "NBIS", "last": 189.88, "change": -29.11, "change_pct": -13.29},
        {"symbol": "NOTCACHED", "last": None, "change": None, "change_pct": None},
    ]


def test_every_watchlist_row_links_back_into_the_app():
    """The link *is* the interaction — st.markdown strips scripts."""
    html = theme.watchlist(rows(), active="AAPL")
    for symbol in ("AAPL", "NBIS", "NOTCACHED"):
        assert f'href="?sym={symbol}"' in html
    assert html.count('target="_self"') == 3


def test_the_active_row_is_marked():
    html = theme.watchlist(rows(), active="NBIS")
    active = [line for line in html.split("<a ") if "NBIS" in line]
    assert 'class="tv-wl-row on"' in "<a " + active[0]
    assert html.count('class="tv-wl-row on"') == 1


def test_gains_and_losses_take_the_candle_colours():
    html = theme.watchlist(rows())
    assert charts.UP in html and charts.DOWN in html
    assert '<span class="tv-num tv-up">+1.41</span>' in html
    assert '<span class="tv-num tv-dn">-29.11</span>' in html


def test_an_uncached_row_renders_as_dashes_not_zeroes():
    """A missing quote must not read as "0.00", which is a price."""
    html = theme.watchlist([rows()[2]])
    assert html.count("—") == 3
    assert "0.00" not in html


def test_panels_are_single_strings_so_they_can_be_concatenated():
    """One st.markdown call per panel would put a wrapper div between them."""
    built = "".join([
        theme.quote_block("AAPL", 312.41, 1.41, 0.45, asset="EQUITY"),
        theme.watchlist(rows(), active="AAPL"),
        theme.stats("Key stats", [("Volume", "45.39M")]),
    ])
    assert isinstance(built, str)
    assert built.count('class="tv-panel"') == 3
    assert "\n" not in built  # markdown would read an indented line as code


# ------------------------------------------------------------ signed tables


def signed_frame():
    import pandas as pd
    return pd.DataFrame({
        "Symbol": ["SPCX", "NVDA", "GONE"],
        "Units": [2.53, 1.12, 0.096],
        "Unit cost": [110.0, 253.0, 5.82],
        "P&L": [12.45, -38.09, float("nan")],
        "P&L %": [4.47, -13.44, float("nan")],
    })


def test_signed_colours_only_the_named_columns():
    rendered = theme.signed(signed_frame(), ("P&L", "P&L %")).to_html()
    rules = rendered.split("</style>")[0]
    assert charts.UP in rules and charts.DOWN in rules
    # P&L and P&L % are columns 3 and 4. Units and Unit cost hold positive
    # numbers too, and colouring those would make green mean nothing.
    assert "col3" in rules and "col4" in rules
    assert "col1" not in rules and "col2" not in rules


def test_signed_keeps_streamlits_number_formatting():
    """Styling opts out of Streamlit's formatter and into pandas' six places."""
    rendered = theme.signed(signed_frame(), ("P&L",)).to_html()
    for shown in (">2.53<", ">110<", ">0.096<", ">12.45<", ">-38.09<"):
        assert shown in rendered, f"{shown} was reformatted"
    assert "2.530000" not in rendered


def test_signed_marks_an_unpriced_row_rather_than_zeroing_it():
    assert ">—<" in theme.signed(signed_frame(), ("P&L",)).to_html()


def test_signed_passes_a_frame_through_when_no_column_matches():
    frame = signed_frame()
    assert theme.signed(frame, ("Nonexistent",)) is frame


# ------------------------------------------------------------------ escaping
#
# Every panel here is rendered with unsafe_allow_html=True. Most of what they
# are handed is a ticker, but not all of it: an uploaded CSV's filename becomes
# the label on the toolbar and the quote block, and a filename is whatever the
# user called the file. An unescaped `&` is a rendering bug today and an
# injection the moment this app is served to more than one person.

NASTY = '<script>alert("pwned")</script> & \'x\' > y'


def every_panel(value: str) -> dict[str, str]:
    """Each builder, handed `value` at every hole that takes caller text."""
    return {
        "brand": theme.brand(value),
        "session_line": theme.session_line(value, value),
        "toolbar_symbol": theme.toolbar_quote(value, 312.41, 1.41, 0.45),
        "toolbar_fields": theme.toolbar_quote("AAPL", 312.41, 1.41, 0.45,
                                              market=value, note=value),
        "quote_symbol": theme.quote_block(value, 312.41, 1.41, 0.45),
        "quote_fields": theme.quote_block("AAPL", 312.41, 1.41, 0.45, asset=value,
                                          name=value, stamp=value, currency=value),
        "watchlist_symbol": theme.watchlist(
            [{"symbol": value, "last": 1.0, "change": 0.1, "change_pct": 1.0}]),
        "watchlist_unpriced": theme.watchlist(
            [{"symbol": value, "last": None, "change": None, "change_pct": None}]),
        "watchlist_note": theme.watchlist(rows(), note=value),
        "stats": theme.stats(value, [(value, value)], note=value),
        "facts": theme.facts([(value, value)]),
        "verdict_card": theme.verdict_card(value, "BUY", 10.0, value,
                                           [(value, value)], subtitle=value,
                                           stamp=value),
        "horizon_card": theme.horizon_card(value, "BUY", value, note=value,
                                           tag=value),
        "voices": theme.voices([(value, "up", 55.0)]),
    }


@pytest.mark.parametrize("panel", sorted(every_panel("x")))
def test_no_panel_lets_markup_through(panel):
    rendered = every_panel(NASTY)[panel]
    assert "<script" not in rendered, f"{panel} passed a tag through"
    assert "&lt;script&gt;" in rendered, f"{panel} lost the text instead"
    assert "&amp;" in rendered, f"{panel} left a bare ampersand"
    assert "&gt; y" in rendered, f"{panel} left a bare angle bracket"
    # Raw quotes would close whichever attribute they landed in.
    assert '"pwned"' not in rendered, f"{panel} left a bare quote"


def test_a_watchlist_href_cannot_be_broken_out_of():
    """The symbol goes into an attribute as well as a text node."""
    html = theme.watchlist([{"symbol": '" onmouseover="evil()', "last": None,
                             "change": None, "change_pct": None}])
    assert 'onmouseover="' not in html
    assert "&quot;" in html


def test_escaping_leaves_the_panels_own_markup_alone():
    """Only the values are escaped; the tags around them are still tags."""
    html = theme.quote_block("AAPL", 312.41, 1.41, 0.45, asset="EQUITY")
    assert '<div class="tv-panel">' in html
    assert "&lt;div" not in html
    assert "AAPL" in html and "EQUITY" in html


def test_the_horizon_row_does_not_escape_the_cards_it_is_given():
    """It composes already-built panels — escaping would print their markup."""
    card = theme.horizon_card("1 day", "BUY", "+22 · 40% confidence")
    assert card in theme.horizon_row([card])


def test_an_uploaded_filename_reaches_the_toolbar_intact():
    """The concrete path: `label = ticker = upload.name` in the app."""
    html = theme.toolbar_quote("<b>my&file</b>.csv", 100.0, 1.0, 1.0)
    assert "<b>" not in html
    assert "&lt;b&gt;my&amp;file&lt;/b&gt;.csv" in html


def test_toolbar_quote_carries_symbol_price_and_move():
    html = theme.toolbar_quote("AAPL", 312.41, 1.41, 0.45, market="EQUITY",
                               note="1,254 bars")
    for fragment in ("AAPL", "312.41", "+1.41", "+0.45%", "EQUITY", "1,254 bars"):
        assert fragment in html


# ------------------------------------------------------- the verdict chrome
#
# These panels are the whole of Lite mode, so a silently broken one is a
# blank page rather than a visible error. theme.py is deliberately told the
# action as a string and knows nothing about ultimate.py — the dependency
# only ever points one way — which is exactly why the colour mapping needs
# asserting here rather than being assumed to follow from an enum.


@pytest.mark.parametrize("action,tone", [
    ("STRONG BUY", "tv-up"), ("BUY", "tv-up"),
    ("HOLD", "tv-flat"), ("NO READ", "tv-flat"),
    ("SELL", "tv-dn"), ("STRONG SELL", "tv-dn"),
])
def test_a_call_is_coloured_like_the_candles(action, tone):
    assert theme.action_tone(action) == tone


def test_action_colour_uses_the_chart_palette():
    """Green here and green on the candles must be the same green."""
    assert theme.action_colour("BUY") == charts.UP
    assert theme.action_colour("STRONG SELL") == charts.DOWN


@pytest.mark.parametrize("score,left", [
    (-100, 0.0), (-50, 25.0), (0, 50.0), (50, 75.0), (100, 100.0),
])
def test_the_meter_pins_the_score_on_its_own_scale(score, left):
    html = theme.meter(score, "BUY")
    assert f"left:{left:.2f}%" in html


def test_the_meter_cannot_be_pushed_off_its_track():
    for score in (-500, 500):
        html = theme.meter(score, "HOLD")
        assert "left:0.00%" in html or "left:100.00%" in html


def test_the_meter_draws_its_zero_line():
    """Without it, 'slightly bullish' and 'flat' are the same picture."""
    assert 'class="zero"' in theme.meter(4.0, "HOLD")


def test_verdict_card_carries_the_call_and_its_numbers():
    html = theme.verdict_card(
        "AAPL", "STRONG BUY", 48.0, "3 of 3 horizons readable",
        [("Score", "+48"), ("Confidence", "62%")],
        subtitle="4 hours · 1 day · 1 week", stamp="as of 2026-08-07 12:00",
    )
    for fragment in ("AAPL", "STRONG BUY", "+48", "62%", "tv-up", "tv-meter",
                     "4 hours · 1 day · 1 week", "as of 2026-08-07 12:00"):
        assert fragment in html


def test_horizon_card_marks_an_unreadable_horizon_as_such():
    readable = theme.horizon_card("1 day", "BUY", "+22 · 40% confidence")
    dead = theme.horizon_card("4 hours", "NO READ", "—",
                              note="161 1h bars is too few", readable=False)

    assert "tv-up" in readable and "tv-hcard off" not in readable
    assert "tv-hcard off" in dead
    assert "tv-up" not in dead and "tv-dn" not in dead
    assert "too few" in dead


def test_voices_colour_each_chip_by_its_side():
    html = theme.voices([("RSI 14", "up", 57.7), ("Bollinger", "down", 54.1)])
    assert "tv-up" in html and "tv-dn" in html
    assert "58%" in html and "54%" in html


def test_voices_render_nothing_when_nothing_is_speaking():
    assert theme.voices([]) == ""


def test_the_horizon_row_keeps_its_cards_level():
    """Their notes differ in length; without stretch the tallest overhangs."""
    html = theme.horizon_row(["<i>a</i>", "<i>b</i>", "<i>c</i>"])
    assert html.count("<div>") == 3
    assert 'class="tv-hrow"' in html
    rules = _rendered_css()
    assert "align-items: stretch" in rules


def test_the_verdict_classes_are_all_styled():
    """A panel emitting a class the stylesheet never defines is invisible."""
    rules = _rendered_css()
    for name in ("tv-verdict", "tv-meter", "tv-hcard", "tv-hrow", "tv-voices",
                 "tv-facts"):
        assert f".{name}" in rules, f"{name} has no styling"


def test_call_columns_are_coloured_by_their_verdict():
    """A row reading SELL is red for the same reason a losing position is."""
    import pandas as pd
    frame = pd.DataFrame({
        "Symbol": ["SPY", "SLV", "PL"],
        "Call": ["STRONG BUY", "SELL", "HOLD"],
        "Signal": [49.9, -33.1, 0.0],
    })
    rendered = theme.signed(frame, ("Signal",), calls=("Call",)).to_html()
    rules = rendered.split("</style>")[0]
    assert charts.UP in rules and charts.DOWN in rules
    assert "font-weight: 600" in rules       # a real call is emphasised
    assert "font-weight: 400" in rules       # HOLD is not


def test_signed_still_works_with_only_call_columns():
    import pandas as pd
    frame = pd.DataFrame({"Symbol": ["SPY"], "Call": ["BUY"]})
    assert hasattr(theme.signed(frame, (), calls=("Call",)), "to_html")


def test_signed_passes_through_when_neither_kind_of_column_is_present():
    import pandas as pd
    frame = pd.DataFrame({"Symbol": ["SPY"]})
    assert theme.signed(frame, ("P&L",), calls=("Call",)) is frame
