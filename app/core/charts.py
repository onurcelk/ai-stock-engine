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

# TradingView's dark theme, sampled from its default chart.
BACKGROUND = "#131722"
GRID = "#1e222d"
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


def has_ohlc(frame: pd.DataFrame) -> bool:
    return {"open", "high", "low"}.issubset(frame.columns)


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
    show_range_buttons: bool = True,
) -> go.Figure:
    """A TradingView-style candlestick chart with an optional volume pane."""
    dates = frame["date"]
    close = frame["close"]
    volume_available = show_volume and "volume" in frame.columns \
        and frame["volume"].fillna(0).abs().sum() > 0

    rows = 2 if volume_available else 1
    figure = make_subplots(
        rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.02,
        row_heights=[0.76, 0.24] if volume_available else [1.0],
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
            text=symbol, xref="paper", yref="paper", x=0.5, y=0.55,
            showarrow=False, font=dict(size=72, color=WATERMARK, family="Arial Black"),
        )

    # TradingView's top-left legend: symbol, interval, then the last OHLC.
    header = f"<b>{symbol}</b>" if symbol else ""
    if interval_label:
        header += f"  <span style='color:{AXIS_TEXT}'>· {interval_label}</span>"
    if has_ohlc(frame):
        row = frame.iloc[-1]
        header += (
            f"   <span style='color:{AXIS_TEXT}'>O</span> {row['open']:,.2f}"
            f"  <span style='color:{AXIS_TEXT}'>H</span> {row['high']:,.2f}"
            f"  <span style='color:{AXIS_TEXT}'>L</span> {row['low']:,.2f}"
            f"  <span style='color:{AXIS_TEXT}'>C</span> "
            f"<span style='color:{badge}'>{row['close']:,.2f}</span>"
        )
    if header:
        figure.add_annotation(
            text=header, xref="paper", yref="paper", x=0, y=1.06,
            showarrow=False, xanchor="left", align="left",
            font=dict(size=13, color=TEXT),
        )

    breaks = _rangebreaks(dates, interval_label)

    figure.update_layout(
        height=height,
        margin=dict(l=8, r=64, t=48, b=8),
        paper_bgcolor=BACKGROUND,
        plot_bgcolor=BACKGROUND,
        font=dict(color=TEXT, size=11),
        hovermode="x unified",
        dragmode="pan",
        xaxis_rangeslider_visible=False,
        bargap=0.15,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0.35,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT)),
        hoverlabel=dict(bgcolor="#1e222d", bordercolor=GRID,
                        font=dict(color=TEXT, size=11)),
    )

    axis_common = dict(
        gridcolor=GRID, zeroline=False, showspikes=True, spikemode="across",
        spikesnap="cursor", spikedash="dot", spikecolor=CROSSHAIR, spikethickness=1,
        linecolor=GRID, tickfont=dict(color=AXIS_TEXT),
    )
    figure.update_xaxes(**axis_common, rangebreaks=breaks, showgrid=True)
    figure.update_yaxes(**axis_common, side="right", showgrid=True)

    if show_range_buttons:
        figure.update_xaxes(
            rangeselector=dict(
                buttons=RANGE_BUTTONS, bgcolor="#1e222d", activecolor="#2962ff",
                font=dict(color=TEXT, size=10), bordercolor=GRID, borderwidth=1,
                x=0, y=1.18, xanchor="left",
            ),
            row=1, col=1,
        )

    if volume_available:
        figure.update_yaxes(title_text="", showticklabels=True, row=2, col=1)

    return figure


def apply_dark(figure: go.Figure) -> go.Figure:
    """Match a plain plotly figure to the price chart's palette."""
    figure.update_layout(
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font=dict(color=TEXT, size=11),
        hoverlabel=dict(bgcolor="#1e222d", bordercolor=GRID, font=dict(color=TEXT)),
    )
    figure.update_xaxes(gridcolor=GRID, linecolor=GRID,
                        tickfont=dict(color=AXIS_TEXT), zeroline=False)
    figure.update_yaxes(gridcolor=GRID, linecolor=GRID,
                        tickfont=dict(color=AXIS_TEXT), zeroline=False)
    return figure


CONFIG = {
    # TradingView scrolls to zoom and drags to pan; match that.
    "scrollZoom": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
}
