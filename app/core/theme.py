"""TradingView's chrome, applied to the rest of the page.

charts.py already draws the price pane in TradingView's palette. Everything
around it — the toolbar, the tabs, the metric tiles — still looked like
default Streamlit, which is exactly what made the chart read as a screenshot
pasted into somebody else's app. This module puts the page in the same design
language: a 44px top bar carrying the symbol and the interval, flat #1e222d
panels hairlined in #2a2e39, tabular figures everywhere a number appears, and
green/red that mean the same thing they mean on the candles.

Two decisions worth knowing about:

- **The palette is imported from charts.py, not restated.** There is one
  #131722 in this app and it lives next to the candles that need it.
- **Interactive things stay real Streamlit widgets, restyled.** The only raw
  HTML here is read-only — the watchlist, the quote block, the stat rows —
  and its single interaction (clicking a watchlist row) goes through a query
  parameter, because `st.markdown` strips `<script>` and there is no honest
  way to fake a callback.
"""

from __future__ import annotations

import html
import string

import streamlit as st

from . import charts

# Chrome colours. The four that have to agree with the candles are imported.
BACKGROUND = charts.BACKGROUND
TEXT = charts.TEXT
MUTED = charts.AXIS_TEXT
UP = charts.UP
DOWN = charts.DOWN
BLUE = charts.LINE

PANEL = charts.PANEL                 # toolbars, cards, input fills
BORDER = charts.BORDER               # every hairline on the page
HOVER = charts.BORDER                # a hover is a border-weight lift
RAISED = "#363a45"                   # scrollbars, pressed states
BRIGHT = "#f0f3fa"                   # headings and the numbers you're meant to read
FAINT = "rgba(42,46,57,0.55)"        # row separators inside a panel

# TradingView's own stack. No webfont: the app has to work offline, and a
# missing download would fall back to Times mid-session.
FONT = ("-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, "
        "'Segoe UI', Helvetica, Arial, sans-serif")


_CSS = string.Template("""
<style>
/* ------------------------------------------------------------ page shell */
html, body, .stApp, [class*="css"] { font-family: $FONT; }
.stApp { background: $BG; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
[data-testid="stToolbar"] { right: 6px; top: 4px; }
[data-testid="stDecoration"] { display: none; }
/* The Deploy button lands on top of the toolbar's own controls. */
[data-testid="stAppDeployButton"] { display: none; }
.block-container { padding: 0.55rem 1.1rem 3rem; max-width: 100%; }
footer { display: none; }

h1, h2, h3, h4 { color: $BRIGHT; font-weight: 600; letter-spacing: -0.01em; }
h1 { font-size: 22px; } h2 { font-size: 19px; } h3 { font-size: 16px; }
p, li, label, .stMarkdown { font-size: 13px; }
[data-testid="stCaptionContainer"] p { color: $MUTED; font-size: 11.5px; line-height: 1.5; }
hr { border-color: $BORDER; }
a { color: $BLUE; }


/* --------------------------------------------------------------- sidebar */
section[data-testid="stSidebar"] { background: $BG; border-right: 1px solid $BORDER; }
section[data-testid="stSidebar"] > div { padding-top: 0.6rem; }
section[data-testid="stSidebar"] h1 { font-size: 15px; }

/* ------------------------------------------------------------------ tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 2px; background: transparent; border-bottom: 1px solid $BORDER; padding: 0;
}
.stTabs [data-baseweb="tab"] {
  height: 34px; padding: 0 13px; background: transparent; border-radius: 4px 4px 0 0;
  color: $MUTED; font-size: 13px; font-weight: 500;
}
.stTabs [data-baseweb="tab"]:hover { background: $PANEL; color: $TEXT; }
.stTabs [aria-selected="true"] { background: $PANEL; color: $BRIGHT !important; }
.stTabs [data-baseweb="tab-highlight"] { background: $BLUE; height: 2px; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ----------------------------------------------------- metrics as TV tiles */
[data-testid="stMetric"] {
  background: $PANEL; border: 1px solid $BORDER; border-radius: 6px; padding: 9px 12px;
}
[data-testid="stMetricLabel"] p {
  font-size: 10.5px !important; color: $MUTED !important; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] {
  font-size: 21px; font-weight: 600; color: $BRIGHT; font-variant-numeric: tabular-nums;
}
[data-testid="stMetricDelta"] { font-size: 11.5px; font-variant-numeric: tabular-nums; }
[data-testid="stMetricDelta"] svg { width: 12px; height: 12px; }
/* Streamlit's own green is a different green from the candles'. */
[data-testid="stMetricDelta"]:has([data-testid="stMetricDeltaIcon-Up"]) { color: $UP !important; }
[data-testid="stMetricDelta"]:has([data-testid="stMetricDeltaIcon-Down"]) { color: $DOWN !important; }

/* --------------------------------------------------------------- buttons */
.stButton > button, .stDownloadButton > button {
  background: $PANEL; color: $TEXT; border: 1px solid $BORDER; border-radius: 4px;
  font-size: 12px; font-weight: 500; padding: 3px 12px; min-height: 32px;
  transition: background 90ms ease, border-color 90ms ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  background: $HOVER; border-color: $RAISED; color: $BRIGHT;
}
.stButton > button:focus:not(:active) { color: $BRIGHT; border-color: $BLUE; box-shadow: none; }
.stButton > button[kind="primary"] { background: $BLUE; border-color: $BLUE; color: #fff; }
.stButton > button[kind="primary"]:hover { background: #1e53e5; border-color: #1e53e5; }

/* ------------------------------------------- radios, restyled as TV pills */
div[role="radiogroup"] { gap: 2px; }
div[role="radiogroup"] > label {
  background: transparent; border-radius: 4px; padding: 4px 10px; margin: 0;
  cursor: pointer; transition: background 90ms ease;
}
div[role="radiogroup"] > label > div:first-child { display: none; }   /* the dot */
div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] p {
  font-size: 12px; font-weight: 600; color: $MUTED; margin: 0;
}
div[role="radiogroup"] > label:hover { background: $PANEL; }
div[role="radiogroup"] > label:hover div[data-testid="stMarkdownContainer"] p { color: $TEXT; }
div[role="radiogroup"] > label:has(input:checked) { background: $HOVER; }
div[role="radiogroup"] > label:has(input:checked) div[data-testid="stMarkdownContainer"] p {
  color: $BRIGHT;
}

/* ------------------------------------------------------ inputs and selects */
.stTextInput input, .stNumberInput input, .stDateInput input,
[data-baseweb="select"] > div, [data-baseweb="input"] {
  background: $PANEL !important; border-color: $BORDER !important;
  border-radius: 4px !important; color: $TEXT !important; font-size: 13px !important;
}
.stTextInput input:focus, [data-baseweb="select"] > div:focus-within {
  border-color: $BLUE !important; box-shadow: none !important;
}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"] {
  background: $PANEL; border: 1px solid $BORDER;
}
[data-baseweb="menu"] li:hover { background: $HOVER; }
[data-testid="stWidgetLabel"] p {
  font-size: 11px; color: $MUTED; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.04em;
}

/* -------------------------------------------------- expanders, dataframes */
[data-testid="stExpander"] {
  border: 1px solid $BORDER; border-radius: 6px; background: $PANEL;
}
[data-testid="stExpander"] summary { font-size: 12.5px; color: $TEXT; }
[data-testid="stDataFrame"] { border: 1px solid $BORDER; border-radius: 6px; }
[data-testid="stPlotlyChart"] { border-radius: 6px; overflow: hidden; }
[data-testid="stAlert"] { border-radius: 4px; padding: 9px 14px; font-size: 12.5px; }
[data-testid="stAlert"] p { font-size: 12.5px; }

/* ----------------------------------------------------------- scrollbars */
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: $BG; }
::-webkit-scrollbar-thumb { background: $RAISED; border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: #4b5162; }

/* ============================ read-only TradingView panels ============== */
.tv-rule { height: 1px; background: $BORDER; margin: 3px 0 12px; }

.tv-session {
  display: flex; justify-content: flex-end; align-items: baseline; gap: 12px;
  padding: 6px 4px; font-size: 11px; color: $MUTED; white-space: nowrap;
}
.tv-session .clock {
  color: $TEXT; font-variant-numeric: tabular-nums; border: 1px solid $BORDER;
  border-radius: 3px; padding: 2px 7px;
}

.tv-brand {
  display: flex; align-items: center; gap: 8px; padding: 2px 0 12px;
  font-size: 14px; font-weight: 700; color: $BRIGHT; letter-spacing: -0.01em;
}
.tv-brand .mark {
  width: 20px; height: 20px; border-radius: 4px; flex: none;
  background: linear-gradient(135deg, $BLUE 0%, #26a69a 100%);
}

.tv-panel {
  background: $PANEL; border: 1px solid $BORDER; border-radius: 6px;
  overflow: hidden; margin-bottom: 10px;
  /* The rail is a fraction of the viewport, so the watchlist has to lay
     itself out against its own width rather than the window's. */
  container-type: inline-size;
}
.tv-panel-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
  padding: 8px 11px; border-bottom: 1px solid $BORDER;
  font-size: 12px; font-weight: 600; color: $TEXT;
}
.tv-panel-head .sub { font-size: 10.5px; font-weight: 400; color: $MUTED; }

/* ------------------------------------------- the toolbar's price readout */
.tv-tick {
  display: flex; align-items: baseline; gap: 9px; padding: 2px 0;
  white-space: nowrap; overflow: hidden;
}
.tv-tick .t { font-size: 13px; font-weight: 700; color: $BRIGHT; }
.tv-tick .p {
  font-size: 17px; font-weight: 600; color: $BRIGHT; font-variant-numeric: tabular-nums;
}
.tv-tick .c { font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }
.tv-tick .m {
  font-size: 10px; font-weight: 600; color: $MUTED; border: 1px solid $BORDER;
  border-radius: 3px; padding: 1px 5px; letter-spacing: 0.04em;
}
.tv-tick .n {
  font-size: 10.5px; color: $MUTED; overflow: hidden; text-overflow: ellipsis;
}

/* ----------------------------------------------------------- the quote block */
.tv-quote { padding: 11px 12px 12px; }
.tv-quote .ident { display: flex; align-items: center; gap: 7px; }
.tv-quote .badge {
  width: 20px; height: 20px; border-radius: 50%; flex: none; color: #fff;
  font-size: 10px; font-weight: 700; display: flex; align-items: center;
  justify-content: center;
}
.tv-quote .tick { font-size: 14px; font-weight: 700; color: $BRIGHT; }
.tv-quote .tag {
  font-size: 9.5px; font-weight: 700; color: $MUTED; border: 1px solid $BORDER;
  border-radius: 3px; padding: 1px 5px; letter-spacing: 0.04em;
}
.tv-quote .name {
  margin-top: 5px; font-size: 11.5px; color: $MUTED;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tv-quote .price {
  margin-top: 7px; font-size: 27px; font-weight: 600; color: $BRIGHT;
  line-height: 1.1; font-variant-numeric: tabular-nums;
}
.tv-quote .price .cur {
  font-size: 11px; font-weight: 500; color: $MUTED; margin-left: 5px;
  vertical-align: 3px;
}
.tv-quote .chg {
  margin-top: 3px; font-size: 13px; font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.tv-quote .stamp { margin-top: 7px; font-size: 10.5px; color: $MUTED; }

/* ------------------------------------------------------------- watchlist */
.tv-wl-head, .tv-wl-row {
  display: grid; grid-template-columns: minmax(3.4em,1fr) 4.4em 3.9em 4.2em;
  gap: 3px; align-items: center; padding: 5px 10px;
}
/* On a narrow rail the absolute change is the first column to go — it is the
   one the percentage already tells you. TradingView drops it in the same
   order. Without this the symbol is squeezed to a single letter. */
@container (max-width: 250px) {
  .tv-wl-head, .tv-wl-row { grid-template-columns: minmax(0,1fr) 4.4em 4.2em; }
  .tv-wl-head > *:nth-child(3), .tv-wl-row > *:nth-child(3) { display: none; }
}
.tv-wl-head {
  font-size: 9.5px; font-weight: 600; color: $MUTED; text-transform: uppercase;
  letter-spacing: 0.06em; border-bottom: 1px solid $BORDER;
}
.tv-wl-row {
  font-size: 12px; color: $TEXT; text-decoration: none !important;
  border-bottom: 1px solid $FAINT; cursor: pointer;
}
.tv-wl-row:last-child { border-bottom: none; }
.tv-wl-row:hover { background: $HOVER; }
.tv-wl-row.on { background: rgba(41,98,255,0.13); box-shadow: inset 2px 0 0 $BLUE; }
.tv-wl-row .sym {
  display: flex; align-items: center; gap: 6px; font-weight: 600; color: $BRIGHT;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tv-wl-row .dot { width: 6px; height: 6px; border-radius: 50%; flex: none; }

/* ------------------------------------------------------------- stat rows */
.tv-stat {
  display: flex; justify-content: space-between; align-items: baseline; gap: 10px;
  padding: 6px 11px; font-size: 12px; border-bottom: 1px solid $FAINT;
}
.tv-stat:last-child { border-bottom: none; }
.tv-stat .k { color: $MUTED; }
.tv-stat .v { color: $TEXT; font-weight: 500; font-variant-numeric: tabular-nums; }

.tv-num { text-align: right; font-variant-numeric: tabular-nums; }
.tv-up { color: $UP; } .tv-dn { color: $DOWN; } .tv-flat { color: $MUTED; }

/* ====================================== the ultimate indicator's verdict === */
/* The one thing Lite mode is for, so it is allowed to be the biggest object
   on the page. The meter underneath is the part that stops the word from
   being read as a certainty: a call sitting at +18 on a -100..100 scale looks
   like the lean it is, where "BUY" on its own does not. */

.tv-verdict {
  background: $PANEL; border: 1px solid $BORDER; border-radius: 8px;
  padding: 16px 18px 15px; margin-bottom: 10px;
}
.tv-verdict .top {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
}
.tv-verdict .who { display: flex; align-items: baseline; gap: 9px; }
.tv-verdict .who .sym { font-size: 17px; font-weight: 700; color: $BRIGHT; }
.tv-verdict .who .sub { font-size: 11px; color: $MUTED; }
.tv-verdict .stamp { font-size: 10.5px; color: $MUTED; }
.tv-verdict .call {
  margin: 9px 0 2px; font-size: 40px; font-weight: 700; line-height: 1.05;
  letter-spacing: -0.02em;
}
.tv-verdict .why { font-size: 12.5px; color: $TEXT; margin-bottom: 11px; }

.tv-meter { margin: 12px 0 4px; }
.tv-meter .track {
  position: relative; height: 8px; border-radius: 4px;
  background: linear-gradient(90deg,
      rgba(239,83,80,0.55) 0%, rgba(239,83,80,0.14) 34%,
      $BORDER 50%,
      rgba(38,166,154,0.14) 66%, rgba(38,166,154,0.55) 100%);
}
/* The zero line has to be drawn: without it "slightly bullish" and "flat"
   are the same picture. */
.tv-meter .zero {
  position: absolute; left: 50%; top: -3px; width: 1px; height: 14px;
  background: $RAISED;
}
.tv-meter .pin {
  position: absolute; top: -4px; width: 3px; height: 16px; border-radius: 2px;
  transform: translateX(-50%);
}
.tv-meter .scale {
  display: flex; justify-content: space-between; margin-top: 5px;
  font-size: 9.5px; color: $MUTED; letter-spacing: 0.04em;
}

.tv-facts {
  display: flex; flex-wrap: wrap; gap: 18px; margin-top: 12px;
  padding-top: 11px; border-top: 1px solid $FAINT;
}
.tv-facts .f { min-width: 78px; }
.tv-facts .f .k {
  display: block; font-size: 9.5px; font-weight: 600; color: $MUTED;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.tv-facts .f .v {
  display: block; margin-top: 3px; font-size: 16px; font-weight: 600;
  color: $BRIGHT; font-variant-numeric: tabular-nums;
}

/* --------------------------------------------------- one horizon of three */
/* Three-across, and the three have to end level: the notes underneath differ
   in length, so without stretch the shortest card floats and the tallest
   overhangs whatever follows the row. */
.tv-hrow { display: flex; gap: 10px; flex-wrap: wrap; align-items: stretch; }
.tv-hrow > * { flex: 1 1 170px; display: flex; }
.tv-hcard {
  background: $PANEL; border: 1px solid $BORDER; border-radius: 6px;
  padding: 11px 12px 15px; width: 100%; box-sizing: border-box;
}
.tv-hcard .h {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 10.5px; font-weight: 600; color: $MUTED;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.tv-hcard .call {
  margin: 6px 0 1px; font-size: 20px; font-weight: 700; letter-spacing: -0.01em;
}
.tv-hcard .lead { font-size: 11.5px; color: $TEXT; font-variant-numeric: tabular-nums; }
.tv-hcard .note { margin-top: 7px; font-size: 10.5px; color: $MUTED; line-height: 1.45; }
.tv-hcard.off .call { color: $MUTED; font-size: 15px; }

/* ------------------------------------------------- what argued which way */
.tv-voices { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 9px; }
.tv-voices .v {
  font-size: 10.5px; padding: 2px 7px; border-radius: 3px;
  border: 1px solid $BORDER; background: $BG; color: $MUTED;
  font-variant-numeric: tabular-nums;
}
.tv-voices .v b { font-weight: 600; }
</style>
""")


def inject() -> None:
    """Put the whole page in TradingView's palette. Call once, after set_page_config."""
    st.markdown(
        _CSS.substitute(
            FONT=FONT, BG=BACKGROUND, PANEL=PANEL, BORDER=BORDER, HOVER=HOVER,
            RAISED=RAISED, TEXT=TEXT, MUTED=MUTED, BRIGHT=BRIGHT, BLUE=BLUE,
            UP=UP, DOWN=DOWN, FAINT=FAINT,
        ),
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------ formatting


def _esc(value) -> str:
    """Escape a caller-supplied string on its way into markup.

    Everything below is rendered with `unsafe_allow_html=True`, so any text
    that did not originate here is markup until proved otherwise. Most of it
    is a ticker, but not all: an uploaded CSV's filename becomes the label on
    the toolbar and the quote block, and a filename is whatever the user
    called the file. An unescaped `&` in one is a rendering bug today; the
    same hole is an injection the moment this app is served to more than one
    person.

    Only the *values* are escaped. The tags around them are written here and
    stay markup — which is why this is a function called at each hole rather
    than a filter over the finished string.
    """
    return html.escape(str(value), quote=True)


def direction(change: float) -> str:
    """The class name for a number that should be green, red or neither."""
    if change > 0:
        return "tv-up"
    if change < 0:
        return "tv-dn"
    return "tv-flat"


def colour(change: float) -> str:
    return UP if change > 0 else DOWN if change < 0 else MUTED


def compact(value: float | None) -> str:
    """26,720,000 -> 26.72M, the way a quote board writes volume."""
    if value is None:
        return "—"
    magnitude = abs(value)
    for cutoff, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if magnitude >= cutoff:
            return f"{value / cutoff:,.2f}{suffix}"
    return f"{value:,.2f}"


def _places(reference: float) -> int:
    """How many decimals this instrument is quoted to.

    Chosen from the price rather than the number being printed, so a 3-dollar
    move on a 200-dollar stock prints as +3.00 and not as a bare "+3" next to
    a column of two-decimal prices.
    """
    magnitude = abs(reference)
    if magnitude >= 100:
        return 2
    if magnitude >= 1:
        return 3
    return 5


def price(value: float) -> str:
    """Sub-dollar instruments (FX, penny crypto) need the extra places."""
    return f"{value:,.{_places(value)}f}"


def delta(change: float, reference: float) -> str:
    """A signed move, quoted to the same precision as the price it moved."""
    return f"{change:+,.{_places(reference)}f}"


# ------------------------------------------------------------------- panels
#
# These return HTML strings rather than calling st.markdown themselves, so a
# caller can compose several into one markdown block — Streamlit inserts a
# wrapper div per call, and a stack of them is what puts stray gaps between
# panels that are meant to touch.


def _cell(value):
    """Render a float the way st.dataframe would have on its own.

    Styling a frame opts out of Streamlit's column formatting and back into
    pandas', which prints every float to six places — so "2.53 units" becomes
    "2.530000". Trimming the trailing zeros here puts the table back the way
    it read before it had any colour in it.
    """
    if not isinstance(value, float):
        return value
    if value != value:            # NaN: an unpriced holding, not a zero
        return "—"
    places = 4 if abs(value) >= 0.01 or value == 0 else 8
    return f"{value:,.{places}f}".rstrip("0").rstrip(".")


def signed(frame, columns: tuple[str, ...], calls: tuple[str, ...] = ()):
    """Colour a table's gain/loss columns the way the candles are coloured.

    Returns a Styler that `st.dataframe` renders directly. Named columns that
    aren't in the frame are ignored, so one call covers tables whose shape
    differs between Lite and Pro.

    `calls` names columns holding a verdict word rather than a number — BUY,
    HOLD, SELL. They are coloured by the same rule the meter uses, so a
    portfolio row reading SELL is red for the same reason a losing position
    is, and green never means two different things on one screen.
    """
    present = [name for name in columns if name in frame.columns]
    present_calls = [name for name in calls if name in frame.columns]
    if not present and not present_calls:
        return frame

    def tone(value) -> str:
        if not isinstance(value, (int, float)) or value != value:
            return ""
        return f"color: {colour(value)}"

    def call_tone(value) -> str:
        if not isinstance(value, str):
            return ""
        shade = action_colour(value)
        weight = "600" if shade != MUTED else "400"
        return f"color: {shade}; font-weight: {weight}"

    styler = frame.style
    if present:
        styler = styler.map(tone, subset=present)
    if present_calls:
        styler = styler.map(call_tone, subset=present_calls)
    return styler.format(_cell)


def rule() -> str:
    return '<div class="tv-rule"></div>'


def session_line(stamp: str, detail: str) -> str:
    """The right end of the range bar — TradingView's clock and session tag."""
    return (f'<div class="tv-session"><span>{_esc(detail)}</span>'
            f'<span class="clock">{_esc(stamp)}</span></div>')


def brand(title: str) -> str:
    return f'<div class="tv-brand"><span class="mark"></span>{_esc(title)}</div>'


def toolbar_quote(
    symbol: str,
    last: float,
    change: float,
    change_pct: float,
    market: str = "",
    note: str = "",
) -> str:
    """One line of price for the top bar, beside the interval pills."""
    tone = direction(change)
    parts = [f'<div class="tv-tick"><span class="t">{_esc(symbol)}</span>']
    if market:
        parts.append(f'<span class="m">{_esc(market)}</span>')
    parts.append(f'<span class="p">{price(last)}</span>')
    parts.append(
        f'<span class="c {tone}">{delta(change, last)} ({change_pct:+.2f}%)</span>'
    )
    if note:
        parts.append(f'<span class="n">{_esc(note)}</span>')
    parts.append("</div>")
    return "".join(parts)


def quote_block(
    symbol: str,
    last: float,
    change: float,
    change_pct: float,
    asset: str = "",
    name: str = "",
    stamp: str = "",
    currency: str = "USD",
) -> str:
    """The big price readout — TradingView's right-hand symbol header."""
    tone = direction(change)
    parts = [
        '<div class="tv-panel"><div class="tv-quote">',
        '<div class="ident">',
        f'<span class="badge" style="background:{colour(change)}">'
        f'{_esc(str(symbol)[:1])}</span>',
        f'<span class="tick">{_esc(symbol)}</span>',
    ]
    if asset:
        parts.append(f'<span class="tag">{_esc(asset)}</span>')
    parts.append("</div>")
    if name:
        parts.append(f'<div class="name">{_esc(name)}</div>')
    parts.append(
        f'<div class="price">{price(last)}'
        f'<span class="cur">{_esc(currency)}</span></div>'
    )
    parts.append(
        f'<div class="chg {tone}">{delta(change, last)}&nbsp;&nbsp;'
        f'{change_pct:+.2f}%</div>'
    )
    if stamp:
        parts.append(f'<div class="stamp">{_esc(stamp)}</div>')
    parts.append("</div></div>")
    return "".join(parts)


def watchlist(rows: list[dict], active: str = "", note: str = "") -> str:
    """A clickable quote board.

    Each row is an anchor carrying `?sym=`, which is the only way a read-only
    markdown block can act: Streamlit strips scripts, so a link that re-enters
    the app through a query parameter is the honest mechanism. It costs a page
    load rather than a rerun, which also throws away any trained model in
    session state — acceptable only because every one of them is fingerprinted
    to the series being replaced.
    """
    parts = [
        '<div class="tv-panel">',
        '<div class="tv-panel-head"><span>Watchlist</span>',
        f'<span class="sub">{_esc(note)}</span></div>',
        '<div class="tv-wl-head"><span>Symbol</span><span class="tv-num">Last</span>',
        '<span class="tv-num">Chg</span><span class="tv-num">Chg%</span></div>',
    ]
    for row in rows:
        symbol = row["symbol"]
        on = " on" if symbol == active else ""
        # Escaped once, used in both an attribute and a text node — which is
        # why `quote=True` matters here and not only for tidiness.
        shown = _esc(symbol)
        if row.get("last") is None:
            parts.append(
                f'<a class="tv-wl-row{on}" href="?sym={shown}" target="_self">'
                f'<span class="sym"><i class="dot" style="background:{MUTED}"></i>'
                f'{shown}</span><span class="tv-num tv-flat">—</span>'
                f'<span class="tv-num tv-flat">—</span>'
                f'<span class="tv-num tv-flat">—</span></a>'
            )
            continue
        change, last = row["change"], row["last"]
        tone = direction(change)
        parts.append(
            f'<a class="tv-wl-row{on}" href="?sym={shown}" target="_self">'
            f'<span class="sym"><i class="dot" style="background:{colour(change)}"></i>'
            f'{shown}</span>'
            f'<span class="tv-num">{price(last)}</span>'
            f'<span class="tv-num {tone}">{delta(change, last)}</span>'
            f'<span class="tv-num {tone}">{row["change_pct"]:+.2f}%</span></a>'
        )
    parts.append("</div>")
    return "".join(parts)


# ------------------------------------------------------- the verdict panels
#
# These take already-formatted strings rather than an UltimateVerdict, so
# theme.py keeps knowing nothing about ultimate.py. The dependency only ever
# points one way — charts.py holds the palette, theme.py dresses the page, and
# neither imports anything that computes.


def action_tone(action: str) -> str:
    """Green for a buy, red for a sell, grey for a hold. Matches the candles."""
    upper = action.upper()
    if "BUY" in upper:
        return "tv-up"
    if "SELL" in upper:
        return "tv-dn"
    return "tv-flat"


def action_colour(action: str) -> str:
    return {"tv-up": UP, "tv-dn": DOWN}.get(action_tone(action), MUTED)


def meter(score: float, action: str) -> str:
    """A -100..+100 scale with the score pinned on it.

    The number alone invites being read as a probability. Drawn against its
    own range, +18 looks like the small lean it is.
    """
    position = max(0.0, min(100.0, 50.0 + score / 2.0))
    return (
        '<div class="tv-meter"><div class="track">'
        '<div class="zero"></div>'
        f'<div class="pin" style="left:{position:.2f}%;'
        f'background:{action_colour(action)}"></div>'
        '</div><div class="scale"><span>STRONG SELL</span><span>NEUTRAL</span>'
        '<span>STRONG BUY</span></div></div>'
    )


def facts(items: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<div class="f"><span class="k">{_esc(key)}</span>'
        f'<span class="v">{_esc(value)}</span></div>'
        for key, value in items
    )
    return f'<div class="tv-facts">{cells}</div>'


def verdict_card(
    symbol: str,
    action: str,
    score: float,
    headline: str,
    rows: list[tuple[str, str]],
    subtitle: str = "",
    stamp: str = "",
) -> str:
    """The hero panel: what to do, how strongly, and on what."""
    parts = [
        '<div class="tv-verdict"><div class="top"><div class="who">',
        f'<span class="sym">{_esc(symbol)}</span>',
    ]
    if subtitle:
        parts.append(f'<span class="sub">{_esc(subtitle)}</span>')
    parts.append("</div>")
    if stamp:
        parts.append(f'<span class="stamp">{_esc(stamp)}</span>')
    parts.append("</div>")
    parts.append(f'<div class="call {action_tone(action)}">{_esc(action)}</div>')
    if headline:
        parts.append(f'<div class="why">{_esc(headline)}</div>')
    parts.append(meter(score, action))
    parts.append(facts(rows))
    parts.append("</div>")
    return "".join(parts)


def horizon_card(
    label: str,
    action: str,
    lead: str,
    note: str = "",
    tag: str = "",
    readable: bool = True,
) -> str:
    """One of the three timeframes, sized to sit three-across."""
    classes = "tv-hcard" if readable else "tv-hcard off"
    return (
        f'<div class="{classes}"><div class="h"><span>{_esc(label)}</span>'
        f'<span>{_esc(tag)}</span></div>'
        f'<div class="call {action_tone(action) if readable else "tv-flat"}">'
        f'{_esc(action)}</div>'
        f'<div class="lead">{_esc(lead)}</div>'
        + (f'<div class="note">{_esc(note)}</div>' if note else "")
        + "</div>"
    )


def horizon_row(cards: list[str]) -> str:
    """Lay the horizon cards out side by side, ending level."""
    return ('<div class="tv-hrow">'
            + "".join(f"<div>{card}</div>" for card in cards)
            + "</div>")


def voices(items: list[tuple[str, str, float]]) -> str:
    """Chips naming what argued which way, with its measured hit rate."""
    if not items:
        return ""
    chips = "".join(
        f'<span class="v"><b class="{direction(1 if side == "up" else -1)}">'
        f'{_esc(name)}</b> {rate:.0f}%</span>'
        for name, side, rate in items
    )
    return f'<div class="tv-voices">{chips}</div>'


def stats(title: str, rows: list[tuple[str, str]], note: str = "") -> str:
    """A label/value panel — TradingView's "Key stats"."""
    parts = [
        '<div class="tv-panel"><div class="tv-panel-head">',
        f'<span>{_esc(title)}</span><span class="sub">{_esc(note)}</span></div>',
    ]
    for label, value in rows:
        parts.append(
            f'<div class="tv-stat"><span class="k">{_esc(label)}</span>'
            f'<span class="v">{_esc(value)}</span></div>'
        )
    parts.append("</div>")
    return "".join(parts)
