"""TradingView-styled price charts.

The app's other charts adapt to Streamlit's theme, but a price chart reads
better in TradingView's own dark palette, so this one commits to it: teal/red
candles on a near-black canvas, a volume pane underneath, the last price
badged against the right axis, and a faint symbol watermark behind it all.

Falls back to TradingView's line-with-gradient style when a series has no
OHLC columns (some bundled CSVs are close-only).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# TradingView's dark theme, sampled from its default chart. theme.py imports
# these rather than restating them, so the page and the candles cannot drift.
BACKGROUND = "#131722"
PANEL = "#1e222d"      # tooltips here; toolbars and cards in theme.py
BORDER = "#2a2e39"     # axis lines, and every hairline on the page
GRID = PANEL           # gridlines sit one shade below the borders
AXIS_TEXT = "#787b86"
TEXT = "#d1d4dc"
UP = "#26a69a"
DOWN = "#ef5350"
UP_FILL = "rgba(38,166,154,0.5)"
DOWN_FILL = "rgba(239,83,80,0.5)"
LINE = "#2962ff"
CROSSHAIR = "#758696"
WATERMARK = "rgba(120,130,150,0.09)"

RANGE_BUTTONS = [
    dict(count=5, label="5D", step="day", stepmode="backward"),
    dict(count=1, label="1M", step="month", stepmode="backward"),
    dict(count=3, label="3M", step="month", stepmode="backward"),
    dict(count=6, label="6M", step="month", stepmode="backward"),
    dict(count=1, label="YTD", step="year", stepmode="todate"),
    dict(count=1, label="1Y", step="year", stepmode="backward"),
    dict(count=5, label="5Y", step="year", stepmode="backward"),
    dict(step="all", label="All"),
]

# The same set again, as calendar spans, for the bottom range bar. Slicing the
# frame beats plotly's own rangeselector here: it rescales the price axis, the
# volume pane and the last-price badge to the visible window the way
# TradingView does, where plotly would only move the x range and leave the
# candles squashed against a y axis sized for five years.
RANGE_DAYS = {"1D": 1, "5D": 5, "1M": 31, "3M": 92, "6M": 183, "1Y": 366, "5Y": 1827}
RANGE_KEYS = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "5Y", "All"]


def has_ohlc(frame: pd.DataFrame) -> bool:
    return {"open", "high", "low"}.issubset(frame.columns)


def _tail(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    """The raw slice for a range key, however few bars that turns out to be."""
    if key == "All" or frame.empty:
        return frame
    end = frame["date"].iloc[-1]
    if key == "YTD":
        start = pd.Timestamp(year=end.year, month=1, day=1)
    else:
        days = RANGE_DAYS.get(key)
        if days is None:
            return frame
        start = end - pd.Timedelta(days=days)
    return frame[frame["date"] >= start].reset_index(drop=True)


def window(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    """The tail of `frame` covered by a range-bar key such as "3M"."""
    sliced = _tail(frame, key)
    # Two bars is the least that can be drawn; below that, ignore the request
    # rather than hand the chart something it would render as a single dot.
    return sliced if len(sliced) >= 2 else frame


def usable_ranges(frame: pd.DataFrame, minimum_bars: int = 3) -> list[str]:
    """Range keys that would actually change what this series looks like.

    Dropped from both ends: a daily series has no "1D" worth drawing, and on
    eighteen months of history "5Y" is just "All" wearing a different label.
    Offering either is how a toolbar teaches people its buttons don't work.
    """
    return [key for key in RANGE_KEYS
            if key == "All" or minimum_bars <= len(_tail(frame, key)) < len(frame)]


def _trades_on_weekends(dates: pd.Series) -> bool:
    """Crypto and FX trade through the weekend; equities don't.

    Collapsing weekends is what makes an equity chart look continuous, but
    doing it to a 24/7 series would hide real bars — so decide from the data.
    """
    return bool((dates.dt.dayofweek >= 5).any())


def _rangebreaks(dates: pd.Series, interval: str) -> list[dict]:
    breaks: list[dict] = []
    if not _trades_on_weekends(dates):
        breaks.append(dict(bounds=["sat", "mon"]))
        if interval in {"1h", "4h"}:
            # Hide the overnight session so intraday bars sit shoulder to
            # shoulder, the way TradingView draws them.
            breaks.append(dict(bounds=[16, 9.5], pattern="hour"))
    return breaks


def price_chart(
    frame: pd.DataFrame,
    symbol: str = "",
    interval_label: str = "",
    height: int = 560,
    overlays: pd.DataFrame | None = None,
    buys: list[int] | None = None,
    sells: list[int] | None = None,
    show_volume: bool = True,
    show_range_buttons: bool = False,
    market: str = "",
    watermark_sub: str = "",
) -> go.Figure:
    """A TradingView-style candlestick chart with an optional volume pane.

    `show_range_buttons` draws plotly's own rangeselector above the chart. It
    defaults off because the app renders that bar underneath instead, where
    TradingView keeps it, and slices the frame so the price axis rescales too.
    """
    dates = frame["date"]
    close = frame["close"]
    volume_available = show_volume and "volume" in frame.columns \
        and frame["volume"].fillna(0).abs().sum() > 0

    rows = 2 if volume_available else 1
    figure = make_subplots(
        rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.015,
        # Volume is context, not a second chart: TradingView gives it a strip
        # under the candles, and a quarter of the canvas reads as a claim that
        # it matters as much as the price.
        row_heights=[0.82, 0.18] if volume_available else [1.0],
    )

    if has_ohlc(frame):
        figure.add_trace(
            go.Candlestick(
                x=dates, open=frame["open"], high=frame["high"],
                low=frame["low"], close=close, name=symbol or "Price",
                increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
                decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
                showlegend=False,
            ),
            row=1, col=1,
        )
    else:
        # TradingView's line style: thin stroke over a soft gradient.
        figure.add_trace(
            go.Scatter(
                x=dates, y=close, name=symbol or "Price", mode="lines",
                line=dict(color=LINE, width=2), fill="tozeroy",
                fillcolor="rgba(41,98,255,0.12)", showlegend=False,
            ),
            row=1, col=1,
        )
        figure.update_yaxes(range=[close.min() * 0.97, close.max() * 1.03],
                            row=1, col=1)

    if overlays is not None:
        for index, column in enumerate(overlays.columns):
            figure.add_trace(
                go.Scatter(
                    x=dates, y=overlays[column], name=column.replace("_", " "),
                    line=dict(color=["#f0b90b", "#9c27b0", "#00bcd4"][index % 3],
                              width=1.2),
                ),
                row=1, col=1,
            )

    if buys:
        figure.add_trace(
            go.Scatter(
                x=dates.iloc[buys], y=frame["low"].iloc[buys] * 0.985
                if has_ohlc(frame) else close.iloc[buys] * 0.99,
                mode="markers", name="Buy",
                marker=dict(symbol="triangle-up", size=12, color=UP,
                            line=dict(width=1, color="#0b3b36")),
            ),
            row=1, col=1,
        )
    if sells:
        figure.add_trace(
            go.Scatter(
                x=dates.iloc[sells], y=frame["high"].iloc[sells] * 1.015
                if has_ohlc(frame) else close.iloc[sells] * 1.01,
                mode="markers", name="Sell",
                marker=dict(symbol="triangle-down", size=12, color=DOWN,
                            line=dict(width=1, color="#4a1513")),
            ),
            row=1, col=1,
        )

    if volume_available:
        if has_ohlc(frame):
            rising = frame["close"] >= frame["open"]
        else:
            rising = close.diff().fillna(0) >= 0
        figure.add_trace(
            go.Bar(
                x=dates, y=frame["volume"], name="Volume",
                marker_color=np.where(rising, UP_FILL, DOWN_FILL),
                marker_line_width=0, showlegend=False, hovertemplate="%{y:,.0f}<extra></extra>",
            ),
            row=2, col=1,
        )

    last = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) > 1 else last
    badge = UP if last >= previous else DOWN

    figure.add_hline(
        y=last, line=dict(color=badge, width=1, dash="dot"),
        annotation_text=f" {last:,.2f} ", annotation_position="right",
        annotation_bgcolor=badge, annotation_bordercolor=badge,
        annotation_font=dict(color="#ffffff", size=11),
        row=1, col=1,
    )

    if symbol:
        figure.add_annotation(
            text=symbol, xref="paper", yref="paper", x=0.5, y=0.56,
            showarrow=False, font=dict(size=76, color=WATERMARK, family="Arial Black"),
        )
        if watermark_sub:
            figure.add_annotation(
                text=watermark_sub, xref="paper", yref="paper", x=0.5, y=0.44,
                showarrow=False, font=dict(size=16, color=WATERMARK),
            )

    # TradingView's legend sits *inside* the chart, hard against the top-left
    # corner: symbol, interval, market, then the last bar's OHLC and its move.
    header = f"<b>{symbol}</b>" if symbol else ""
    tags = [t for t in (interval_label, market) if t]
    if tags:
        header += f"  <span style='color:{AXIS_TEXT}'>· {' · '.join(tags)}</span>"
    if has_ohlc(frame):
        row = frame.iloc[-1]
        header += (
            f"   <span style='color:{AXIS_TEXT}'>O</span>"
            f"<span style='color:{badge}'>{row['open']:,.2f}</span>"
            f"  <span style='color:{AXIS_TEXT}'>H</span>"
            f"<span style='color:{badge}'>{row['high']:,.2f}</span>"
            f"  <span style='color:{AXIS_TEXT}'>L</span>"
            f"<span style='color:{badge}'>{row['low']:,.2f}</span>"
            f"  <span style='color:{AXIS_TEXT}'>C</span>"
            f"<span style='color:{badge}'>{row['close']:,.2f}</span>"
        )
    change = last - previous
    header += (
        f"   <span style='color:{badge}'>{change:+,.2f} "
        f"({change / previous * 100 if previous else 0:+.2f}%)</span>"
    )
    figure.add_annotation(
        text=header, xref="paper", yref="paper", x=0.004, y=0.995,
        showarrow=False, xanchor="left", yanchor="top", align="left",
        font=dict(size=12.5, color=TEXT),
    )

    breaks = _rangebreaks(dates, interval_label)

    figure.update_layout(
        height=height,
        # The legend is drawn inside the canvas now, so the only top margin
        # left is whatever plotly's rangeselector needs when it is asked for.
        margin=dict(l=6, r=62, t=46 if show_range_buttons else 10, b=6),
        paper_bgcolor=BACKGROUND,
        plot_bgcolor=BACKGROUND,
        font=dict(color=TEXT, size=11),
        hovermode="x unified",
        dragmode="pan",
        xaxis_rangeslider_visible=False,
        bargap=0.25,
        legend=dict(orientation="h", yanchor="top", y=0.94, x=0.006,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=AXIS_TEXT, size=11)),
        hoverlabel=dict(bgcolor=PANEL, bordercolor=BORDER,
                        font=dict(color=TEXT, size=11)),
    )

    axis_common = dict(
        gridcolor=GRID, zeroline=False, showspikes=True, spikemode="across",
        spikesnap="cursor", spikedash="dot", spikecolor=CROSSHAIR, spikethickness=1,
        linecolor=BORDER, tickfont=dict(color=AXIS_TEXT, size=10.5),
    )
    figure.update_xaxes(**axis_common, rangebreaks=breaks, showgrid=True)
    figure.update_yaxes(**axis_common, side="right", showgrid=True,
                        ticklabelposition="outside", ticks="")

    if show_range_buttons:
        figure.update_xaxes(
            rangeselector=dict(
                buttons=RANGE_BUTTONS, bgcolor=PANEL, activecolor=LINE,
                font=dict(color=TEXT, size=10), bordercolor=GRID, borderwidth=1,
                x=0, y=1.18, xanchor="left",
            ),
            row=1, col=1,
        )

    if volume_available:
        # TradingView's volume pane is deliberately quiet: no grid, three ticks,
        # SI-suffixed so 26,720,000 reads as 26.7M without widening the axis.
        figure.update_yaxes(title_text="", showgrid=False, nticks=3,
                            tickformat="~s", row=2, col=1)

    return figure


# Line colours for indicator panes, in the order the catalogue lists them.
# Deliberately not the candle colours: an indicator line reading as "up" or
# "down" would claim agreement with the price it is drawn against.
INDICATOR_LINES = ["#f0b90b", "#9c27b0", "#00bcd4", "#e91e63"]


def indicator_pane(
    dates: pd.Series,
    lines: pd.DataFrame,
    title: str = "",
    levels: tuple[float, ...] = (),
    histogram: pd.Series | None = None,
    histogram_colors: pd.Series | None = None,
    interval_label: str = "",
    height: int = 190,
) -> go.Figure:
    """A short oscillator strip, styled to sit underneath the price chart.

    Oscillators have no price scale, so they cannot share the candle axis —
    TradingView gives each one its own pane and so does this. `levels` draws the
    fixed reference lines an oscillator is read against (WaveTrend's +/-60, a
    zero line), which is the whole reason those readings mean anything.
    """
    figure = go.Figure()

    if histogram is not None:
        figure.add_trace(go.Bar(
            x=dates, y=histogram, name=title or "Histogram",
            marker_color=histogram_colors if histogram_colors is not None else LINE,
            marker_line_width=0, showlegend=False,
            hovertemplate="%{y:.2f}<extra></extra>",
        ))

    for index, column in enumerate(lines.columns):
        figure.add_trace(go.Scatter(
            x=dates, y=lines[column], name=column.replace("_", " "), mode="lines",
            line=dict(color=INDICATOR_LINES[index % len(INDICATOR_LINES)], width=1.3),
            hovertemplate="%{y:.2f}<extra></extra>",
        ))

    for level in levels:
        # Zero is the axis; the others are thresholds and read as guides.
        figure.add_hline(
            y=level,
            line=dict(color=BORDER if level else AXIS_TEXT,
                      width=1, dash="solid" if not level else "dot"),
        )

    figure.update_layout(
        height=height,
        margin=dict(l=6, r=62, t=22, b=6),
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font=dict(color=TEXT, size=11),
        hovermode="x unified", dragmode="pan", bargap=0.25,
        showlegend=False,
        hoverlabel=dict(bgcolor=PANEL, bordercolor=BORDER,
                        font=dict(color=TEXT, size=11)),
    )
    if title:
        figure.add_annotation(
            text=f"<b>{title}</b>", xref="paper", yref="paper", x=0.004, y=1.0,
            showarrow=False, xanchor="left", yanchor="top",
            font=dict(size=11.5, color=AXIS_TEXT),
        )

    axis_common = dict(
        gridcolor=GRID, zeroline=False, showspikes=True, spikemode="across",
        spikesnap="cursor", spikedash="dot", spikecolor=CROSSHAIR, spikethickness=1,
        linecolor=BORDER, tickfont=dict(color=AXIS_TEXT, size=10.5),
    )
    figure.update_xaxes(**axis_common, showgrid=True,
                        rangebreaks=_rangebreaks(dates, interval_label))
    figure.update_yaxes(**axis_common, side="right", showgrid=True, nticks=4,
                        ticklabelposition="outside", ticks="")
    return figure


def apply_dark(figure: go.Figure) -> go.Figure:
    """Match a plain plotly figure to the price chart's palette."""
    figure.update_layout(
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font=dict(color=TEXT, size=11),
        hoverlabel=dict(bgcolor=PANEL, bordercolor=BORDER, font=dict(color=TEXT)),
    )
    figure.update_xaxes(gridcolor=GRID, linecolor=BORDER,
                        tickfont=dict(color=AXIS_TEXT, size=10.5), zeroline=False)
    figure.update_yaxes(gridcolor=GRID, linecolor=BORDER,
                        tickfont=dict(color=AXIS_TEXT, size=10.5), zeroline=False)
    return figure


CONFIG = {
    # TradingView scrolls to zoom and drags to pan; match that.
    "scrollZoom": True,
    "displaylogo": False,
    "displayModeBar": "hover",
    "doubleClick": "reset",
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
}
