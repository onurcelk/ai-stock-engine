"""Stock-Prediction-Models — interactive front end.

Wraps the repo's notebooks in something you can actually click through:
pick a series, run a trading agent or a forecaster over it, and see the
result next to a benchmark that tells you whether it was any good.

Run with:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from core import (  # noqa: E402
    agents, backtest, charts, data, forecast, holdings, live, montecarlo,
    portfolio, quotes, runs, strategies, theme, ultimate,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

RULE_BASED = ["Turtle (channel breakout)", "Moving average crossover", "Signal rolling"]

# TradingView writes intervals as one or two characters on the toolbar and
# spells them out nowhere. live.INTERVALS keeps the readable names for the
# yfinance codes; these are the pills.
PILLS = {"1h": "1H", "4h": "4H", "1d": "D", "1wk": "W", "1mo": "M"}
CODE_FOR_PILL = {pill: code for code, pill in PILLS.items()}
NAME_FOR_CODE = {code: name for name, code in live.INTERVALS.items()}

# Gains and losses borrow the candle colours so green means the same thing in
# every pane. The other three are picked to stay legible on the dark canvas,
# where TradingView's own blue (#2962ff) is too heavy for a line or a fill.
PRICE = "#5B8DEF"
BUY = charts.UP
SELL = charts.DOWN
MUTED = "#8B93A7"
ACCENT = "#B084F5"

st.set_page_config(page_title="Stock Prediction Models", page_icon="📈", layout="wide")
theme.inject()


# ---------------------------------------------------------------- helpers


@st.cache_data(show_spinner=False)
def load_bundled(name: str) -> pd.DataFrame:
    return data.load(name)


@st.cache_data(ttl=60, show_spinner=False)
def watchlist_rows(symbols: tuple[str, ...], interval: str) -> list[dict]:
    """Quote board for the rail. Reads the cache only — see core/quotes.py."""
    return quotes.board(list(symbols), interval)


def base_chart(height: int = 420) -> go.Figure:
    """Every chart outside the price pane starts here.

    Routed through charts.apply_dark so the app sits in one palette: the price
    chart commits to TradingView's dark theme, and a chart that didn't follow
    would read as a light patch pasted next to it. Only the vertical gridlines
    are dropped again — these panes are small, and the price chart is the one
    that earns a full grid.
    """
    figure = go.Figure()
    figure.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)"),
    )
    charts.apply_dark(figure)
    figure.update_xaxes(showgrid=False)
    return figure


def delta_vs_benchmark(strategy_pct: float, benchmark_pct: float) -> str:
    gap = strategy_pct - benchmark_pct
    return f"{gap:+.2f} pts vs buy & hold"


def local_path(path: pathlib.Path) -> str:
    """Show a store path relative to the repo when it is inside it.

    Tests redirect these stores into a tmp_path, and `relative_to` raises
    rather than giving up when the target is elsewhere — which turned a
    caption into a crash the first time the portfolio tab was driven
    headlessly.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# --------------------------------------------------------- ultimate indicator
#
# The verdict is cheap to compute (about 0.1s once the bars are on disk) but
# it re-reads three cache files to do it, so it is memoised per symbol. The
# model evidence travels as a tuple rather than a dataclass because that is
# what st.cache_data can hash without complaint.


@st.cache_data(ttl=600, show_spinner=False)
def read_ultimate(symbol: str, include_agents: bool,
                  model: tuple | None) -> ultimate.UltimateVerdict:
    evidence = ultimate.ModelEvidence(*model) if model else None
    return ultimate.evaluate(symbol, include_agents=include_agents,
                             model=evidence)


# The forecast needs both halves and will not invent either: a projection past
# the last bar to say which way, and a walk-forward directional accuracy to say
# whether that has ever been worth anything. A projection alone is an opinion
# with no track record, which `ModelEvidence` would weight at zero regardless —
# so the toggle runs the pair itself rather than sending you to another tab to
# assemble them by hand.

MODEL_HORIZON = 5          # bars ahead: a week of daily bars
MODEL_BARS = 1_250         # ~5y, the depth that keeps this under a minute


def train_seconds(folds: int, epochs: int, bars: int) -> str:
    """The estimate from forecast.py, rounded to something worth reading."""
    estimate = forecast.estimate_train_seconds(folds, epochs, bars)
    if estimate < 90:
        return f"{max(5, round(estimate / 5) * 5)}s"
    return f"{estimate / 60:.0f} min"


def measure_model(close, dates, *, model_name: str, folds: int, epochs: int,
                  units: int, horizon: int = MODEL_HORIZON) -> tuple:
    """Measure the forecaster out of sample, then let it predict forward.

    Returns the `ModelEvidence` fields as a tuple, plus the two objects behind
    it, so the caller can show what was measured rather than only its verdict.
    Trained on the same daily series the 1-day and 1-week horizons are scored
    on, so the accuracy attached to the prediction belongs to the prediction.
    """
    total = folds + 1                       # the folds, then the projection
    bar = st.progress(0.0)
    status = st.empty()

    def on_fold(slot: int, epoch: int, epoch_total: int, loss: float,
                accuracy: float) -> None:
        done = (slot * epoch_total + epoch + 1) / (total * epoch_total)
        bar.progress(min(1.0, done))
        stage = ("projecting forward" if slot >= folds
                 else f"measuring fold {slot + 1}/{folds}")
        status.caption(f"{stage} · epoch {epoch + 1}/{epoch_total} · "
                       f"loss {loss:.5f}")

    try:
        walk = forecast.walk_forward(
            close, dates, folds=folds, horizon=horizon, model=model_name,
            size_layer=units, epochs=epochs, progress=on_fold,
        )
        projection = forecast.project(
            close, dates, model=model_name, size_layer=units, epochs=epochs,
            horizon=horizon,
            progress=lambda _s, e, t, l, a: on_fold(folds, e, t, l, a),
        )
    finally:
        bar.empty()
        status.empty()

    summary = walk.summary()
    evidence = (
        f"{model_name} forecast",             # name
        "1d",                                 # interval it was measured on
        projection.horizon,                   # horizon_bars
        projection.move_pct,                  # predicted_move_pct
        summary["mean_directional"],          # directional_pct
        len(walk.folds) * walk.horizon,       # samples
    )
    return evidence, walk, projection


def model_frame(symbol: str, fallback: pd.DataFrame) -> pd.DataFrame:
    """The daily series the model is measured and scored on.

    Deliberately the horizon's own bars rather than whatever the sidebar has
    selected: an accuracy measured on one series and attached to a prediction
    about another is not a measurement of anything.
    """
    if source == "Live ticker" and symbol:
        try:
            fetched, _ = live.fetch(symbol, period="10y", interval="1d")
            return fetched
        except live.FetchError:
            pass
    return fallback


@st.cache_data(ttl=900, show_spinner=False)
def scan_book(symbols: tuple[str, ...],
              include_agents: bool = True) -> dict[str, ultimate.UltimateVerdict]:
    """Every holding read through the same engine as the signal tab.

    Cached hard, because a cold scan of eighteen positions fetches two
    resolutions each. Once the day's bars are on disk it comes back in about
    a second, which is why this can run on tab load rather than behind a
    button — the number is only useful if it is already there when you look
    at the list.
    """
    return ultimate.scan(list(symbols), include_agents=include_agents)


def horizon_cards(verdict: ultimate.UltimateVerdict) -> str:
    """The three timeframes, side by side, in the order they are traded."""
    cards = []
    for reading in verdict.horizons:
        if not reading.available:
            cards.append(theme.horizon_card(
                reading.horizon.label, "NO READ", "—",
                note=reading.unavailable, tag=reading.interval, readable=False))
            continue
        counted = len(reading.live)
        cards.append(theme.horizon_card(
            reading.horizon.label,
            reading.action,
            f"{reading.score:+.0f} · {reading.confidence:.0f}% confidence",
            note=(f"Expected {reading.expected_move_pct:+.2f}% against a typical "
                  f"{reading.typical_move_pct:.2f}% move. "
                  f"{counted} source{'' if counted == 1 else 's'} counted of "
                  f"{len(reading.readings)}."
                  if counted else
                  "No source cleared significance here, so this horizon "
                  "contributes nothing to the call."),
            tag=f"{reading.bars_used} × {reading.interval}",
        ))
    return theme.horizon_row(cards)


def verdict_panel(verdict: ultimate.UltimateVerdict, subtitle: str) -> None:
    """Hero card, then the three horizons, then who argued which way."""
    price_now = verdict.last_price
    day = verdict.by_key("1d")
    target = day.target_price if day and day.available and day.live else None

    rows = [
        ("Score", f"{verdict.score:+.0f}"),
        ("Confidence", f"{verdict.confidence:.0f}%"),
        ("Timeframes", verdict.alignment),
        ("Last price", theme.price(price_now) if price_now else "—"),
    ]
    if target:
        rows.append(("1-day target", theme.price(target)))

    headline = (
        f"{len(verdict.available)} of {len(verdict.horizons)} horizons readable · "
        f"weighted by out-of-sample hit rate, not by reputation"
    )

    st.markdown(
        theme.verdict_card(
            verdict.symbol, verdict.action, verdict.score, headline, rows,
            subtitle=subtitle,
            stamp=f"as of {verdict.generated_at:%Y-%m-%d %H:%M}",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(horizon_cards(verdict), unsafe_allow_html=True)

    loudest = max((h for h in verdict.available), key=lambda h: h.confidence,
                  default=None)
    if loudest is not None and loudest.live:
        chips = [
            (r.name, "up" if r.score > 0 else "down", r.skill.hit_rate)
            for r in loudest.live[:8]
        ]
        st.caption(f"What is speaking at {loudest.horizon.label} — each chip is a "
                   "source, coloured by which way it argues, labelled with the "
                   "hit rate it was measured at:")
        st.markdown(theme.voices(chips), unsafe_allow_html=True)


# ------------------------------------------------------------- URL handling
#
# A watchlist row is an <a href="?sym=…">, because st.markdown strips scripts
# and a query parameter is the only handle read-only HTML has on the app.
#
# The parameter is *consumed*: read once, then removed from the URL. It is a
# one-shot instruction from a row that was clicked, not a statement of what is
# on screen, and leaving it in place breaks both directions. Remembering the
# last value applied instead — which is what this did — made re-clicking a row
# a no-op once the symbol box had been typed into, because the href had not
# changed and so neither had the remembered value. Comparing against the
# current symbol rather than the last one would have been worse: a stale
# parameter would then re-assert itself over the next thing typed.

wanted = (st.query_params.get("sym") or "").strip().upper()
if wanted:
    del st.query_params["sym"]
    st.session_state.symbol = wanted
    st.session_state.source = "Live ticker"   # a ticker is a live-data request


# ---------------------------------------------------------------- sidebar

st.sidebar.markdown(theme.brand("Stock Prediction Models"), unsafe_allow_html=True)

# These are two different applications, not one with a knob count. Lite is
# three tabs and answers "what do I do"; Pro is seven and answers "why, and
# can I trust it". Hiding parameters was the old distinction and it only made
# Lite a worse Pro.
mode_choice = st.sidebar.radio(
    "Interface", ["Lite", "Pro"], horizontal=True, label_visibility="collapsed",
    help="Lite is the buy/hold/sell call, the chart and your positions. Pro "
         "adds every measurement behind that call, the trading agents, the "
         "neural forecast, walk-forward validation and Monte Carlo.",
)
pro = mode_choice == "Pro"
st.sidebar.caption(
    "The call, the chart, your positions. Switch to **Pro** for the evidence "
    "behind the call and the models that produced it."
    if not pro else
    "Everything, opened up. Switch to **Lite** for the decision on its own."
)

st.session_state.setdefault("source", "Live ticker")
source = st.sidebar.radio("Data source",
                          ["Live ticker", "Bundled dataset", "Upload CSV"], key="source")


# ----------------------------------------------------------------- top bar
#
# TradingView's toolbar: what you're looking at, and at what resolution. It is
# built before the fetch because it *is* the fetch's input, so the price
# readout beside it is a placeholder filled in once the bars land.

frame: pd.DataFrame | None = None
label = ticker = market = ""
symbol = ""
# Defaults for the non-live sources: the Portfolio tab always pulls live data
# (a basket needs several symbols, and the bundled CSVs are one series each),
# so these have to be defined whichever source is selected.
interval, period, refresh = "1d", "5y", False

toolbar = st.container()
with toolbar:
    if source == "Live ticker":
        st.session_state.setdefault("symbol", "AAPL")
        box, pills, readout, action = st.columns([1.35, 2.5, 3.6, 1.0])
        symbol = box.text_input("Symbol", key="symbol", label_visibility="collapsed",
                                placeholder="Symbol")
        with pills:
            chosen_pill = st.radio(
                "Interval", list(PILLS.values()),
                index=list(PILLS.values()).index(PILLS["1d"]), horizontal=True,
                label_visibility="collapsed", key="interval_pill",
            )
        interval = CODE_FOR_PILL[chosen_pill]
        quote_slot = readout.empty()
        refresh = action.button("↻ Refresh", use_container_width=True,
                                help="Ignore the local cache and re-download from Yahoo.")
    elif source == "Bundled dataset":
        box, readout = st.columns([2, 6])
        choice = box.selectbox("Series", data.list_datasets(), label_visibility="collapsed")
        quote_slot = readout.empty()
    else:
        box, readout = st.columns([3, 5])
        upload = box.file_uploader("CSV with a date and a price column", type="csv",
                                   label_visibility="collapsed")
        quote_slot = readout.empty()

st.markdown(theme.rule(), unsafe_allow_html=True)

if source == "Live ticker":
    # Interval decides which history lengths Yahoo will serve, so it is read
    # off the toolbar above before this offers any.
    choices = live.periods_for(interval)
    period = st.sidebar.selectbox(
        "History", choices, index=choices.index(live.default_period(interval)),
        help="Yahoo serves intraday bars only for the last 730 days."
        if interval in live.INTRADAY else None,
    ) if pro else live.default_period(interval)

    try:
        frame, entry = live.fetch(symbol, period=period, interval=interval, force=refresh)
        ticker = entry.symbol
        market = quotes.asset_class(ticker)
        label = f"{ticker} · {NAME_FOR_CODE[interval]}"
        if entry.is_fresh:
            st.sidebar.caption(
                f"✅ {entry.rows:,} bars · {entry.start} → {entry.end} · "
                f"updated {entry.describe_age()}"
            )
            if interval in live.INTRADAY:
                st.sidebar.caption(
                    f"Last bar {frame['date'].iloc[-1]:%Y-%m-%d %H:%M} (exchange local time)."
                )
        else:
            st.sidebar.warning(
                f"Showing cached data from {entry.describe_age()} — Yahoo was unreachable. "
                f"{entry.rows:,} bars through {entry.end}."
            )
    except live.RequestError as error:
        # Bad symbol or impossible period/interval combination.
        st.sidebar.error(str(error))
    except live.FetchError as error:
        st.sidebar.error(
            f"{error}\n\nNo cached copy of {symbol.upper()} either — switch to a bundled "
            "dataset to keep working offline."
        )

elif source == "Bundled dataset":
    st.sidebar.caption("Static CSVs shipped with the repo — most end in 2017-2019.")
    try:
        frame = load_bundled(choice)
        label = ticker = choice
        market = "CSV"
    except Exception as error:  # noqa: BLE001 - surface any parse failure in the UI
        st.sidebar.error(f"Could not read {choice}: {error}")

else:
    if upload is not None:
        try:
            frame = data.load_upload(upload)
            label = ticker = upload.name
            market = "UPLOAD"
        except Exception as error:  # noqa: BLE001
            st.sidebar.error(f"Could not read that file: {error}")

if frame is None:
    st.info("Choose a data source in the sidebar to begin.")
    st.stop()

# Trim to a window so every tab works off the same slice.
min_date = frame["date"].min().date()
max_date = frame["date"].max().date()
if min_date < max_date:
    start, end = st.sidebar.slider(
        "Date range", min_value=min_date, max_value=max_date,
        value=(min_date, max_date), format="YYYY-MM-DD",
    )
    mask = (frame["date"].dt.date >= start) & (frame["date"].dt.date <= end)
    frame = frame.loc[mask].reset_index(drop=True)

# Every backtest, agent and portfolio is quoted against the same notional
# stake, so results stay comparable and percentages carry the meaning.
initial_money = 10_000

if pro:
    with st.sidebar.expander("Trading costs"):
        fee_pct = st.number_input("Commission %", 0.0, 5.0, 0.10, step=0.01, format="%.3f",
                                  help="Charged on the notional of every fill, both sides.")
        slippage_pct = st.number_input("Slippage %", 0.0, 5.0, 0.05, step=0.01,
                                       format="%.3f",
                                       help="Buys fill above the close, sells below it.")
        st.caption("Set both to 0 to reproduce the original notebook figures.")
else:
    # Realistic retail defaults; Pro exposes them.
    fee_pct, slippage_pct = 0.10, 0.05

st.sidebar.divider()
st.sidebar.caption(
    f"**{len(frame)}** rows · {frame['date'].min():%Y-%m-%d} → {frame['date'].max():%Y-%m-%d}"
)

close = frame["close"]
dates = frame["date"]

# "30 days" is wrong once bars are hourly — every horizon control counts bars.
bar_word = "bars" if interval in live.INTRADAY else "days"

# The move on the last bar, which the toolbar, the chart legend and the rail
# all quote. Computed once here so they cannot disagree.
last_price = float(close.iloc[-1])
prior_price = float(close.iloc[-2]) if len(close) > 1 else last_price
last_change = last_price - prior_price
last_change_pct = last_change / prior_price * 100 if prior_price else 0.0

quote_slot.markdown(
    theme.toolbar_quote(
        ticker or label, last_price, last_change, last_change_pct,
        market=market,
        note=f"{len(frame):,} bars · through {dates.iloc[-1]:%Y-%m-%d}",
    ),
    unsafe_allow_html=True,
)

if len(frame) < 40:
    st.warning("That window is very short — most models need a few hundred rows to behave.")


# ------------------------------------------------------------------- tabs

# The two modes are not the same app with different knobs — that was the old
# arrangement and it made Lite a worse Pro. Lite answers one question, in this
# order: what should I do, what does the price look like, what do I own. Pro
# answers why, and its first tab is the same verdict opened up into every
# measurement behind it.
if pro:
    (signal_tab, overview_tab, agent_tab, forecast_tab, portfolio_tab,
     carlo_tab, history_tab) = st.tabs(
        ["Ultimate signal", "Overview", "Trading agents", "Forecast",
         "Portfolio", "Monte Carlo", "History"]
    )
else:
    signal_tab, overview_tab, portfolio_tab = st.tabs(
        ["Signal", "Chart", "Portfolio"]
    )
    agent_tab = forecast_tab = carlo_tab = history_tab = None


with signal_tab:
    if pro:
        st.subheader("Ultimate signal")
        columns = st.columns([1.2, 1.2, 3])
        include_agents = columns[0].toggle(
            "Include trading agents", value=True,
            help="Folds the three rule-based agents in as evidence, measured "
                 "the same way as everything else rather than trusted.",
        )
        use_model = columns[1].toggle(
            "Include the forecast", value=False,
            help="Trains the neural forecaster on this symbol's daily bars: "
                 "walk-forward to measure how often it gets the direction "
                 "right, then a projection past the last bar. Takes about a "
                 "minute the first time, then it is remembered.",
        )

        model_tuple = None
        if use_model:
            model_units = 64
            with columns[2]:
                knobs = st.columns(4)
                model_name_u = knobs[0].selectbox(
                    "Model", list(forecast.MODELS), key="ultimate_model_kind")
                model_folds = knobs[1].slider("Folds", 2, 8, 3,
                                              key="ultimate_folds")
                model_epochs = knobs[2].slider("Epochs", 10, 150, 30, step=10,
                                               key="ultimate_epochs")
                model_depth = knobs[3].select_slider(
                    "Bars", [600, 1_250, 2_500, 5_000], value=MODEL_BARS,
                    key="ultimate_depth",
                    help="More history measures better and trains slower.")

            daily = model_frame(ticker or symbol, frame)
            usable = daily.tail(model_depth).reset_index(drop=True)
            possible = forecast.max_folds(len(usable), MODEL_HORIZON)

            if possible < 2:
                st.error(
                    f"{len(usable)} daily bars supports {possible} folds at a "
                    f"{MODEL_HORIZON}-bar horizon. There is not enough history "
                    "here to measure the forecaster, and an unmeasured "
                    "forecast is worth nothing to the verdict."
                )
            else:
                folds_used = min(model_folds, possible)
                # Anything that changes the model or its data invalidates it,
                # or the verdict would carry an accuracy measured elsewhere.
                fingerprint = (ticker or label, model_name_u, folds_used,
                               model_epochs, model_units, len(usable),
                               float(usable["close"].iloc[-1]))
                stored = st.session_state.get("ultimate_model")

                if stored is None or stored["fingerprint"] != fingerprint:
                    st.caption(
                        f"Training {model_name_u} on {len(usable):,} daily bars "
                        f"— {folds_used} walk-forward folds at {model_epochs} "
                        f"epochs, then a projection. Roughly "
                        f"{train_seconds(folds_used, model_epochs, len(usable))}"
                        "; the result is kept until the settings or the data "
                        "change."
                    )
                    evidence, walk, projection = measure_model(
                        usable["close"], usable["date"], model_name=model_name_u,
                        folds=folds_used, epochs=model_epochs, units=model_units,
                    )
                    st.session_state["ultimate_model"] = stored = {
                        "fingerprint": fingerprint, "evidence": evidence,
                        "walk": walk, "projection": projection,
                    }
                    runs.save(
                        kind=runs.WALKFORWARD, label=label,
                        settings={"model": model_name_u, "folds": folds_used,
                                  "horizon": MODEL_HORIZON,
                                  "epochs": model_epochs, "units": model_units,
                                  "bars": len(usable), "source": "ultimate"},
                        metrics={
                            "mean_directional": walk.summary()["mean_directional"],
                            "folds_beating_naive": walk.folds_beating_naive,
                            "projected_move_pct": projection.move_pct,
                        },
                        payload={"fold_index": [f.index + 1 for f in walk.folds],
                                 "directionals": walk.directionals},
                    )

                model_tuple = stored["evidence"]
    else:
        include_agents, model_tuple = True, None

    with st.spinner(f"Measuring {ticker or label} across three horizons…"):
        if source == "Live ticker":
            verdict = read_ultimate(ticker or symbol, include_agents, model_tuple)
        else:
            # A bundled CSV or an upload cannot be re-fetched at another
            # resolution, so it answers whichever horizons its own bars can
            # express and declines the rest.
            verdict = ultimate.evaluate_offline(
                frame, label, include_agents=include_agents,
                model=ultimate.ModelEvidence(*model_tuple) if model_tuple else None,
            )

    verdict_panel(
        verdict,
        subtitle=("4 hours · 1 day · 1 week" if source == "Live ticker"
                  else f"from the loaded {verdict.by_key('1d').interval} bars"),
    )

    trained = st.session_state.get("ultimate_model") if pro else None
    if model_tuple is not None and trained is not None:
        walk, projection = trained["walk"], trained["projection"]
        summary = walk.summary()
        # The reading the engine actually built from this, so the panel and
        # the evidence table below cannot tell different stories.
        reading = ultimate.ModelEvidence(*model_tuple).reading(
            MODEL_HORIZON, max(0.01, verdict.by_key("1w").typical_move_pct
                               if verdict.by_key("1w") else 1.0))

        with st.container(border=True):
            st.markdown("**The forecast, measured and then asked**")
            columns = st.columns(5)
            columns[0].metric(
                "Directional", f"{summary['mean_directional']:.1f}%",
                f"{summary['mean_directional'] - 50:+.1f} pts vs a coin flip",
                help="Measured across walk-forward folds it never trained on.")
            columns[1].metric("Folds beating naive",
                              f"{walk.folds_beating_naive}/{len(walk.folds)}")
            columns[2].metric(f"Projected {MODEL_HORIZON} bars",
                              f"{projection.move_pct:+.2f}%")
            columns[3].metric("Weight earned",
                              f"{reading.weight * 100:.0f}%"
                              if reading.weight else "none")
            columns[4].metric("Target", theme.price(projection.final))

            if reading.skill.weight <= 0:
                st.info(
                    f"**The forecast contributes nothing to the call.** "
                    f"{reading.skill.note.capitalize()}. It still has an "
                    f"opinion — {projection.move_pct:+.2f}% over "
                    f"{MODEL_HORIZON} bars — but an opinion with no measured "
                    "track record is exactly what this indicator is built not "
                    "to weight. Turning the toggle on and getting a zero is "
                    "the honest outcome, not a failure to run."
                )
            else:
                st.success(
                    f"Measured at {summary['mean_directional']:.1f}% "
                    f"directional over {len(walk.folds)} folds, which clears "
                    f"the gate — the forecast carries "
                    f"{reading.weight * 100:.0f}% of the weight where its "
                    "interval matches."
                )

    st.markdown("**The conclusion**")
    st.markdown(verdict.conclusion)

    if verdict.errors:
        for horizon_label, message in verdict.errors.items():
            st.caption(f"⚠️ {horizon_label}: {message}")

    if not pro:
        # Lite gets the chart with the call written on it and nothing else —
        # the whole point of the mode is that the decision is the page.
        offered = charts.usable_ranges(frame)
        picked = st.radio("Range", offered, index=offered.index("All"),
                          horizontal=True, label_visibility="collapsed",
                          key="signal_range")
        st.plotly_chart(
            charts.price_chart(
                charts.window(frame, picked), symbol=ticker,
                interval_label=PILLS.get(interval, interval), market=market,
                watermark_sub=NAME_FOR_CODE.get(interval, ""), height=430,
            ),
            use_container_width=True, config=charts.CONFIG,
        )
        st.caption(
            "Switch to **Pro** in the sidebar to see every source behind this "
            "call, its measured hit rate, and the model internals."
        )
    else:
        st.divider()
        st.markdown("**Horizon summary**")
        st.dataframe(theme.signed(verdict.table(),
                                  ("Score", "Expected move %", "Edge pts")),
                     use_container_width=True, hide_index=True)

        st.markdown("**The evidence, source by source**")
        st.caption(
            "`Hit rate` is measured on the held-out tail only, on the bars "
            "where that source was actually saying something. `Independent` "
            "discounts overlapping forward windows — five daily bars of a "
            "one-week return are one observation, not five. `t` is the edge "
            f"over its own standard error; below {ultimate.MIN_T:.2f} a source "
            "carries no weight however large its edge looks."
        )
        readable = [h for h in verdict.available]
        if readable:
            names = [h.horizon.label for h in readable]
            chosen_label = st.radio("Horizon", names, horizontal=True,
                                    label_visibility="collapsed",
                                    key="ultimate_horizon")
            chosen = next(h for h in readable if h.horizon.label == chosen_label)

            columns = st.columns(6)
            columns[0].metric("Call", chosen.action)
            columns[1].metric("Score", f"{chosen.score:+.0f}")
            columns[2].metric("Confidence", f"{chosen.confidence:.0f}%")
            columns[3].metric("Agreement", f"{chosen.agreement * 100:.0f}%",
                              help="Share of live weight on the winning side.")
            columns[4].metric("Coverage", f"{chosen.coverage * 100:.0f}%",
                              help="Surviving weight and breadth of families, "
                                   "against what a full reading needs.")
            columns[5].metric("Weighted edge", f"{chosen.weighted_edge:+.2f} pts",
                              help="Measured advantage over a coin flip, "
                                   "weighted by each source's contribution.")

            evidence = chosen.table()
            st.dataframe(
                theme.signed(evidence, ("Reading", "Edge pts", "t", "Contributes")),
                use_container_width=True, hide_index=True,
                height=min(560, 60 + 35 * len(evidence)),
            )

            contributions = [r for r in chosen.readings if r.counts]
            if contributions:
                figure = base_chart(300)
                ordered = sorted(contributions, key=lambda r: r.contribution)
                figure.add_trace(go.Bar(
                    x=[r.contribution for r in ordered],
                    y=[r.name for r in ordered], orientation="h",
                    marker_color=[BUY if r.contribution >= 0 else SELL
                                  for r in ordered],
                    name="Contribution",
                ))
                figure.update_layout(
                    xaxis_title=f"Points of the {chosen.score:+.0f} score")
                st.plotly_chart(figure, use_container_width=True)
            else:
                st.info(
                    f"Nothing cleared the significance gate at "
                    f"{chosen.horizon.label}. Every source's edge on the "
                    "held-out tail was inside its own noise, so the horizon "
                    "reads HOLD at zero confidence — which is the correct "
                    "output, not a failure to compute one."
                )

        st.divider()
        st.markdown("**What the other tabs found on this series**")
        recent = [run for run in runs.load_all() if run.label == label][:6]
        if not recent:
            st.caption(
                "Nothing saved for this series yet. Train an agent or a "
                "forecast and its result is written to disk and summarised "
                "here — the verdict above never reads it automatically, "
                "because a backtest is not a measured forward edge."
            )
        else:
            st.dataframe(runs.table(recent).drop(columns=["id"]),
                         use_container_width=True, hide_index=True)


with overview_tab:
    stats = data.describe(frame)
    chart_column, rail = st.columns([4.4, 1.55], gap="medium")

    with chart_column:
        # The chart is drawn after the range bar is read but rendered above it,
        # which is where TradingView puts that bar.
        chart_box = st.container()

        offered = charts.usable_ranges(frame)
        bar_left, bar_right = st.columns([5, 3])
        picked = bar_left.radio("Range", offered, index=offered.index("All"),
                                horizontal=True, label_visibility="collapsed",
                                key="overview_range")
        bar_right.markdown(
            theme.session_line(
                f"{dates.iloc[-1]:%Y-%m-%d %H:%M}" if interval in live.INTRADAY
                else f"{dates.iloc[-1]:%Y-%m-%d}",
                f"{NAME_FOR_CODE.get(interval, 'Daily')} · "
                f"{stats['bars_per_year']:,} bars/yr",
            ),
            unsafe_allow_html=True,
        )
        # Slicing the frame rather than only the x axis rescales the price
        # axis, the volume pane and the last-price badge along with it.
        view = charts.window(frame, picked)

        with chart_box:
            st.plotly_chart(
                charts.price_chart(
                    view, symbol=ticker, interval_label=PILLS.get(interval, interval),
                    market=market, watermark_sub=NAME_FOR_CODE.get(interval, ""),
                    height=560,
                ),
                use_container_width=True, config=charts.CONFIG,
            )

        left, right = st.columns([2, 1])
        with left:
            st.markdown("**Return distribution**")
            returns = close.pct_change().dropna() * 100
            histogram = base_chart(height=250)
            histogram.add_trace(go.Histogram(x=returns, nbinsx=60, marker_color=PRICE,
                                             name=f"Per-{bar_word[:-1]} %"))
            st.plotly_chart(histogram, use_container_width=True)
        with right:
            st.markdown("**Raw bars**")
            st.dataframe(frame.tail(200), use_container_width=True, height=250,
                         hide_index=True)

    with rail:
        panels = [theme.quote_block(
            ticker or label, last_price, last_change, last_change_pct,
            asset=market,
            name=f"{NAME_FOR_CODE.get(interval, 'Daily')} bars · "
                 f"{'Yahoo Finance' if source == 'Live ticker' else label}",
            stamp=f"Last bar {dates.iloc[-1]:%Y-%m-%d %H:%M}"
                  if interval in live.INTRADAY else f"Last bar {dates.iloc[-1]:%Y-%m-%d}",
            currency=quotes.currency(ticker) if source == "Live ticker" else "",
        )]

        if source == "Live ticker":
            board = quotes.watchlist_symbols(ticker, interval)
            panels.append(theme.watchlist(
                watchlist_rows(tuple(board), interval), active=ticker,
                note=f"{PILLS.get(interval, interval)} · from cache",
            ))

        volume = frame["volume"] if "volume" in frame.columns else None
        rows = [
            ("Range high", theme.price(stats["high"])),
            ("Range low", theme.price(stats["low"])),
            ("Change over range", f"{stats['change_pct']:+.2f}%"),
            ("Ann. volatility", f"{stats['volatility_pct']:.1f}%"),
            ("Bars per year", f"{stats['bars_per_year']:,}"),
            ("Bars in range", f"{stats['rows']:,}"),
        ]
        if volume is not None and volume.fillna(0).abs().sum() > 0:
            rows[2:2] = [
                ("Volume", theme.compact(float(volume.iloc[-1]))),
                ("Avg volume (30)", theme.compact(float(volume.tail(30).mean()))),
            ]
        panels.append(theme.stats("Key stats", rows,
                                  note=f"{stats['start']} → {stats['end']}"))

        st.markdown("".join(panels), unsafe_allow_html=True)


if pro:
    with agent_tab:
        st.subheader("Rule-based trading agents")
        st.caption(
            "Each agent emits buy/sell signals; the same engine executes them. "
            "The benchmark is buy & hold over the identical window."
        )

        columns = st.columns([2, 1.4, 1, 1])
        agent_name = columns[0].selectbox(
            "Agent",
            RULE_BASED + list(agents.REGISTRY),
            help=f"The first three follow a fixed rule. The remaining "
                 f"{len(agents.REGISTRY)} learn a policy from the price history "
                 "and need training first — they are listed cheapest-to-train "
                 "first, and the three at the top finish in about a second.",
        )
        sizing_label = columns[1].selectbox(
            "Position sizing", list(backtest.SIZING_MODES.values()), index=0,
            help="Fixed units buys one share per signal — which deploys a fraction of "
                 "your capital against a fully invested benchmark. 'All in' is the fair "
                 "comparison.",
        )
        sizing = next(k for k, v in backtest.SIZING_MODES.items() if v == sizing_label)

        if sizing == backtest.FIXED_UNITS:
            max_buy = columns[2].number_input("Units per buy", 1, 100, 1)
            max_sell = columns[3].number_input("Units per sell", 1, 100, 1)
            size_pct = 100.0
        else:
            max_buy = max_sell = 1
            size_pct = columns[2].number_input(
                "% of equity", 1.0, 100.0, 100.0, step=5.0,
                disabled=sizing == backtest.ALL_IN,
            ) if sizing == backtest.PCT_EQUITY else 100.0

        bands: pd.DataFrame | None = None
        signal: pd.Series | None = None
        training = None

        if agent_name in agents.REGISTRY:
            notebook = agents.SOURCE_NOTEBOOK.get(agent_name)
            if notebook:
                st.caption(
                    f"Ported from `agent/{notebook}.*.ipynb`. The learning curve below "
                    "scores the greedy policy on a simplified objective — one unit per "
                    "trade, no costs — while the metrics come from the same backtester "
                    "every other agent uses. The two disagreeing is the point."
                )
            columns = st.columns([1, 1, 1, 1.4])
            iterations = columns[0].slider(
                "Training iterations", 5, 500, agents.DEFAULT_ITERATIONS[agent_name], step=5
            )
            window_size = columns[1].slider("Lookback window", 5, 60, 30,
                                            help="How many past price changes the agent sees.")
            layer_size = columns[2].select_slider("Hidden units", [32, 64, 128, 256],
                                                  value=64)
            seed = columns[3].number_input("Seed", 0, 9_999, 42,
                                           help="Same seed, same agent.")

            # Anything that changes the agent must invalidate a trained one, or the
            # UI would show a policy learned on different data.
            fingerprint = (agent_name, label, len(frame), float(close.iloc[-1]),
                           iterations, window_size, layer_size, int(seed))

            if st.button(f"Train {agent_name.lower()}", type="primary"):
                bar = st.progress(0.0)
                status = st.empty()

                def on_agent_progress(step: int, total: int, reward: float) -> None:
                    bar.progress((step + 1) / total)
                    status.caption(f"Iteration {step + 1}/{total} · "
                                   f"policy return {reward:+.2f}%")

                agent_class = agents.REGISTRY[agent_name]
                learner = agent_class(close, window_size=window_size,
                                      layer_size=layer_size, seed=int(seed))
                try:
                    report = learner.train(iterations, on_progress=on_agent_progress)
                    trained_signal = learner.signals()
                    st.session_state["rl"] = {
                        "fingerprint": fingerprint,
                        "signal": trained_signal,
                        "rewards": report.rewards,
                        "seconds": report.seconds,
                    }
                    # Persist before anything can navigate away. Scored here with
                    # the sizing on screen so the saved ROI matches what the user
                    # is about to see.
                    scored = backtest.run(
                        close, trained_signal, dates, initial_money=initial_money,
                        max_buy=max_buy, max_sell=max_sell, fee_pct=fee_pct,
                        slippage_pct=slippage_pct, sizing=sizing, size_pct=size_pct,
                        periods_per_year=data.periods_per_year(dates),
                    )
                    runs.save(
                        kind=runs.AGENT, label=label,
                        settings={
                            "agent": agent_name, "iterations": iterations,
                            "window": window_size, "units": layer_size,
                            "seed": int(seed), "sizing": sizing, "bars": len(frame),
                        },
                        metrics={
                            "return_pct": scored.roi_pct,
                            "buy_hold_pct": scored.buy_hold_roi_pct,
                            "trades": len(scored.trades),
                            "win_rate_pct": scored.win_rate_pct,
                            "max_drawdown_pct": scored.max_drawdown_pct,
                            "train_seconds": report.seconds,
                        },
                        payload={
                            "rewards": report.rewards,
                            "buys": scored.buys,
                            "sells": scored.sells,
                            "equity": scored.equity,
                            "dates": dates,
                        },
                    )
                finally:
                    # TF graphs are process-global; a leaked session accumulates.
                    if hasattr(learner, "close_session"):
                        learner.close_session()
                bar.empty()
                status.empty()

            stored = st.session_state.get("rl")
            if stored and stored["fingerprint"] == fingerprint:
                signal = stored["signal"]
                training = stored
            elif stored:
                st.info("Settings or data changed since training — train again to refresh.")

        elif agent_name.startswith("Turtle"):
            columns = st.columns([1, 1, 2])
            window = columns[0].slider(
                "Channel window (days)", 2, max(3, len(frame) // 3), max(2, int(np.ceil(len(frame) * 0.1)))
            )
            follow = columns[1].checkbox("Follow breakouts", value=False,
                                         help="Off = the notebook's mean-reverting version, which "
                                              "sells strength and buys weakness. On = classic turtle.")
            signal = strategies.turtle(close, window, follow_breakout=follow)
            bands = strategies.turtle_bands(close, window)
        elif agent_name.startswith("Moving"):
            columns = st.columns([1, 1, 2])
            short_window = columns[0].slider("Short MA", 2, 60, max(2, int(0.025 * len(frame))))
            long_window = columns[1].slider("Long MA", 3, 200, max(3, int(0.05 * len(frame))))
            if short_window >= long_window:
                st.warning("Short MA should be shorter than long MA, or there is nothing to cross.")
            signal = strategies.moving_average(close, short_window, long_window)
            bands = strategies.moving_average_bands(close, short_window, long_window)
        else:
            delay = st.slider("Delay before flipping (days)", 1, 30, 4,
                              help="How many moves against the current position we tolerate "
                                   "before acting.")
            signal = strategies.signal_rolling(close, delay)

        if signal is None:
            st.info(
                f"**{agent_name}** learns a policy from the price history rather than "
                "following a fixed rule. Press **Train** above to run it."
            )
        else:
            result = backtest.run(
                close, signal, dates, initial_money=initial_money,
                max_buy=max_buy, max_sell=max_sell, fee_pct=fee_pct,
                slippage_pct=slippage_pct, sizing=sizing, size_pct=size_pct,
                # Measured from the series, not assumed from the interval: hourly
                # crypto has ~5x the bars per year of hourly equities.
                periods_per_year=data.periods_per_year(dates),
            )

            columns = st.columns(7)
            columns[0].metric("Final value", f"{result.final_value:,.0f}",
                              f"{result.profit:+,.0f}")
            columns[1].metric("Return", f"{result.roi_pct:.2f}%",
                              delta_vs_benchmark(result.roi_pct, result.buy_hold_roi_pct))
            columns[2].metric("Buy & hold", f"{result.buy_hold_roi_pct:.2f}%")
            columns[3].metric("Costs paid", f"{result.fees_paid:,.0f}")
            columns[4].metric("Closed trades", len(result.trades))
            columns[5].metric("Win rate", f"{result.win_rate_pct:.0f}%")
            columns[6].metric("Max drawdown", f"{result.max_drawdown_pct:.1f}%")

            st.plotly_chart(
                charts.price_chart(
                    frame, symbol=ticker, interval_label=PILLS.get(interval, interval),
                    market=market, watermark_sub=NAME_FOR_CODE.get(interval, ""),
                    height=520, overlays=bands, buys=result.buys, sells=result.sells,
                ),
                use_container_width=True, config=charts.CONFIG,
            )

            hold_units = initial_money / float(close.iloc[0])
            equity_chart = base_chart(300)
            equity_chart.add_trace(go.Scatter(x=dates, y=result.equity, name="Agent",
                                              line=dict(color=ACCENT, width=2)))
            equity_chart.add_trace(go.Scatter(x=dates, y=close * hold_units,
                                              name="Buy & hold",
                                              line=dict(color=MUTED, width=1.5, dash="dash")))

            left, right = st.columns([3, 2])
            with left:
                st.markdown("**Portfolio value vs buy & hold**")
                st.plotly_chart(equity_chart, use_container_width=True)
            with right:
                st.markdown("**Closed trades**")
                st.dataframe(theme.signed(backtest.trade_table(result),
                                          ("Profit", "Return %")),
                             use_container_width=True, height=300, hide_index=True)

            if training is not None:
                rewards = training["rewards"]
                st.markdown("**Learning curve**")
                curve = base_chart(240)
                curve.add_trace(go.Scatter(y=rewards, name="Policy return %",
                                           line=dict(color=ACCENT, width=2)))
                curve.update_layout(xaxis_title="Training iteration",
                                    yaxis_title="Return % on its own objective")
                st.plotly_chart(curve, use_container_width=True)
                st.caption(
                    f"Trained in {training['seconds']:.1f}s. The agent optimises a "
                    f"simplified objective — one unit per trade, no costs — which reached "
                    f"{rewards[-1]:+.2f}%. The metrics above are the same policy run "
                    f"through the real backtester with costs and sizing applied, at "
                    f"{result.roi_pct:+.2f}%. The gap is what the objective ignores."
                )

            if result.roi_pct < result.buy_hold_roi_pct:
                message = (
                    f"This agent underperformed buy & hold by "
                    f"{result.buy_hold_roi_pct - result.roi_pct:.2f} percentage points."
                )
                if sizing == backtest.FIXED_UNITS:
                    message += (
                        " Some of that gap is sizing, not skill: buying one unit per signal "
                        "deploys a fraction of your capital while the benchmark is fully "
                        "invested. Switch position sizing to **All in** for a fair "
                        "comparison."
                    )
                else:
                    message += (
                        f" Sizing is like-for-like here, so this is a real result. Costs "
                        f"took {result.fees_paid:,.0f} of it."
                    )
                st.info(message)


if pro:
    with forecast_tab:
        st.subheader("Neural forecast")
        st.caption(
            "Trains on everything except the last N days, then predicts them. "
            "Runs on CPU — a few hundred epochs takes roughly 20 seconds per simulation."
        )

        mode = st.radio(
            "Evaluation", ["Single split", "Walk-forward"], horizontal=True,
            help="A single split trains once and predicts the final window. "
                 "Walk-forward repeats that down the series so you can see whether a "
                 "good result holds up.",
        )

        columns = st.columns(4)
        model_name = columns[0].selectbox("Model", list(forecast.MODELS))
        test_size = columns[1].slider(f"{bar_word.capitalize()} to predict", 5, 60, 30)
        epochs = columns[2].slider("Epochs", 10, 500, 150, step=10)

        if mode == "Single split":
            simulations = columns[3].slider("Simulations", 1, 10, 3,
                                            help="The model is stochastic; each run differs.")
            fold_count = 0
        else:
            simulations = 1
            possible = forecast.max_folds(len(frame), test_size)
            if possible < 2:
                # A slider needs min < max, and one fold isn't walk-forward anyway.
                fold_count = 0
                columns[3].caption(
                    f"⚠️ This window ({len(frame)} bars) supports {possible} folds at a "
                    f"{test_size}-bar horizon. Use a longer history or a shorter horizon."
                )
            else:
                fold_count = columns[3].slider(
                    "Folds", 2, min(20, possible), min(5, possible),
                    help=f"This series supports up to {possible} non-overlapping folds "
                         f"at that horizon.",
                )

        with st.expander("Model settings"):
            columns = st.columns(4)
            num_layers = columns[0].slider("Layers", 1, 3, 1)
            size_layer = columns[1].select_slider("Units per layer",
                                                  [16, 32, 64, 128, 256], value=128)
            timestamp = columns[2].slider("Sequence length", 2, 20, 5)
            learning_rate = columns[3].select_slider(
                "Learning rate", [0.0001, 0.001, 0.01, 0.05], value=0.01
            )
            dropout = st.slider("Keep probability", 0.1, 1.0, 0.8, step=0.05)

        if mode == "Walk-forward" and st.button("Run walk-forward", type="primary",
                                                disabled=fold_count < 2):
            if fold_count < 2:
                st.error(
                    f"Need at least {120 + test_size * 2} bars for two folds — this window "
                    f"has {len(frame)}. Use a longer history or a shorter horizon."
                )
            else:
                bar = st.progress(0.0)
                status = st.empty()
                total = epochs * fold_count

                def on_fold_progress(fold: int, epoch: int, epoch_total: int,
                                     loss: float, acc: float) -> None:
                    done = fold * epoch_total + epoch + 1
                    bar.progress(min(1.0, done / total))
                    status.caption(
                        f"Fold {fold + 1}/{fold_count} · epoch {epoch + 1}/{epoch_total} "
                        f"· loss {loss:.5f}"
                    )

                walk_result = forecast.walk_forward(
                    close, dates, folds=fold_count, horizon=test_size, model=model_name,
                    num_layers=num_layers, size_layer=size_layer, timestamp=timestamp,
                    epochs=epochs, dropout=dropout, learning_rate=learning_rate,
                    progress=on_fold_progress,
                )
                st.session_state["walk"] = walk_result

                walk_summary = walk_result.summary()
                runs.save(
                    kind=runs.WALKFORWARD, label=label,
                    settings={
                        "model": model_name, "folds": fold_count, "horizon": test_size,
                        "epochs": epochs, "layers": num_layers, "units": size_layer,
                        "bars": len(frame),
                    },
                    metrics={
                        "folds_beating_naive": walk_result.folds_beating_naive,
                        "win_rate_pct": walk_summary["win_rate_pct"],
                        "mean_accuracy": walk_summary["mean_accuracy"],
                        "mean_naive": walk_summary["mean_naive"],
                        "mean_directional": walk_summary["mean_directional"],
                        "mean_mae": walk_summary["mean_mae"],
                    },
                    payload={
                        "fold_index": [f.index + 1 for f in walk_result.folds],
                        "accuracies": walk_result.accuracies,
                        "naive_accuracies": walk_result.naive_accuracies,
                        "directionals": walk_result.directionals,
                        "maes": walk_result.maes,
                    },
                )
                bar.empty()
                status.empty()

        if mode == "Walk-forward":
            walk = st.session_state.get("walk")
            if walk is not None:
                summary = walk.summary()
                columns = st.columns(5)
                columns[0].metric("Folds beating naive",
                                  f"{walk.folds_beating_naive}/{len(walk.folds)}",
                                  f"{summary['win_rate_pct']:.0f}% of folds")
                columns[1].metric("Mean accuracy", f"{summary['mean_accuracy']:.2f}%",
                                  f"±{summary['std_accuracy']:.2f} across folds")
                columns[2].metric("Mean naive", f"{summary['mean_naive']:.2f}%")
                columns[3].metric("Mean directional", f"{summary['mean_directional']:.1f}%",
                                  f"±{summary['std_directional']:.1f} spread")
                columns[4].metric("Mean MAE", f"{summary['mean_mae']:,.2f}")

                figure = base_chart(360)
                fold_numbers = [f.index + 1 for f in walk.folds]
                figure.add_trace(go.Bar(x=fold_numbers, y=walk.directionals,
                                        name="Directional %", marker_color=PRICE))
                figure.add_hline(y=50, line=dict(color=SELL, dash="dash"),
                                 annotation_text="coin flip")
                figure.update_layout(xaxis_title="Fold", yaxis_title="Directional accuracy %",
                                     yaxis=dict(range=[0, 100]))
                st.plotly_chart(figure, use_container_width=True)

                st.dataframe(walk.table(), use_container_width=True, hide_index=True)

                if walk.folds_beating_naive == 0:
                    st.error(
                        f"**{walk.model} beat the naive baseline in 0 of {len(walk.folds)} folds.** "
                        "The single-split number is not reproducible across time — which is the "
                        "whole reason to run this."
                    )
                elif summary["win_rate_pct"] < 50:
                    st.warning(
                        f"Beat the baseline in only {walk.folds_beating_naive} of "
                        f"{len(walk.folds)} folds. A single split landing on a good window "
                        "would have looked convincing."
                    )
                else:
                    st.success(
                        f"Beat the baseline in {walk.folds_beating_naive} of "
                        f"{len(walk.folds)} folds, mean directional "
                        f"{summary['mean_directional']:.1f}%."
                    )
                st.caption(
                    "Walk-forward fits the scaler on each fold's training slice only, so unlike "
                    "the single-split path there is no look-ahead into the test window."
                )

                # Everything above predicts windows that already happened —
                # which is what makes them scoreable, and also why none of
                # them is a forecast. This trains on every bar and rolls past
                # the last one, borrowing the folds above for its credibility.
                st.divider()
                st.markdown("**Project past the last bar**")
                st.caption(
                    "Trains on the whole series and predicts forward, so there "
                    "is nothing to score it against. The folds above are its "
                    "track record: the Ultimate signal tab pairs the two and "
                    f"weights the result by that {summary['mean_directional']:.1f}% "
                    "directional accuracy, which is the only reason to believe "
                    "any of it."
                )
                columns = st.columns([1, 1, 2])
                ahead = columns[0].slider(f"{bar_word.capitalize()} ahead", 1, 30, 5,
                                          key="project_ahead")
                if columns[1].button("Project forward", key="project_button"):
                    bar = st.progress(0.0)
                    status = st.empty()

                    def on_project(slot, epoch, epoch_total, loss, acc):
                        bar.progress((epoch + 1) / epoch_total)
                        status.caption(f"Epoch {epoch + 1}/{epoch_total} · "
                                       f"loss {loss:.5f}")

                    st.session_state["projection"] = forecast.project(
                        close, dates, model=model_name, num_layers=num_layers,
                        size_layer=size_layer, timestamp=timestamp,
                        epochs=epochs, dropout=dropout,
                        learning_rate=learning_rate, horizon=ahead,
                        progress=on_project,
                    )
                    bar.empty()
                    status.empty()

                projection = st.session_state.get("projection")
                if projection is not None:
                    columns = st.columns(4)
                    columns[0].metric("Last close",
                                      f"{projection.last_price:,.2f}")
                    columns[1].metric(f"In {projection.horizon} {bar_word}",
                                      f"{projection.final:,.2f}",
                                      f"{projection.move_pct:+.2f}%")
                    columns[2].metric("Model", projection.model)
                    columns[3].metric("Measured directional",
                                      f"{summary['mean_directional']:.1f}%",
                                      f"{summary['mean_directional'] - 50:+.1f} pts "
                                      "vs a coin flip")

                    figure = base_chart(320)
                    tail = 60
                    figure.add_trace(go.Scatter(
                        x=dates.iloc[-tail:], y=close.iloc[-tail:], name="History",
                        line=dict(color=PRICE, width=2)))
                    step = dates.iloc[-1] - dates.iloc[-2]
                    ahead_dates = [dates.iloc[-1] + step * (i + 1)
                                   for i in range(projection.horizon)]
                    figure.add_trace(go.Scatter(
                        x=[dates.iloc[-1]] + ahead_dates,
                        y=[projection.last_price] + list(projection.path),
                        name="Projection",
                        line=dict(color=ACCENT, width=2.5, dash="dot")))
                    st.plotly_chart(figure, use_container_width=True)
                    st.caption(
                        "Turn on **Include the forecast** on the Ultimate "
                        "signal tab to fold this into the verdict. It enters "
                        "through the same significance gate as every other "
                        "source, so a directional accuracy near 50% earns it "
                        "no weight at all."
                    )

        if mode == "Single split" and st.button("Train and forecast", type="primary"):
            if len(frame) <= test_size + timestamp + 5:
                st.error("Not enough history for that prediction window. Widen the date range.")
            else:
                bar = st.progress(0.0)
                status = st.empty()
                total = epochs * simulations

                def on_progress(sim: int, epoch: int, epoch_total: int, loss: float, acc: float) -> None:
                    done = sim * epoch_total + epoch + 1
                    bar.progress(done / total)
                    status.caption(
                        f"Simulation {sim + 1}/{simulations} · epoch {epoch + 1}/{epoch_total} "
                        f"· loss {loss:.5f} · training accuracy {acc:.2f}%"
                    )

                outcome = forecast.run(
                    close, dates, model=model_name, num_layers=num_layers,
                    size_layer=size_layer, timestamp=timestamp, epochs=epochs,
                    dropout=dropout, learning_rate=learning_rate, test_size=test_size,
                    simulations=simulations, progress=on_progress,
                )
                bar.empty()
                status.empty()
                st.session_state["forecast"] = outcome
                st.session_state["forecast_label"] = f"{model_name} · {label}"

                runs.save(
                    kind=runs.FORECAST, label=label,
                    settings={
                        "model": model_name, "epochs": epochs,
                        "simulations": simulations, "horizon": test_size,
                        "layers": num_layers, "units": size_layer,
                        "lookback": timestamp, "bars": len(frame),
                    },
                    metrics={
                        "directional_pct": outcome.directional_accuracy,
                        "accuracy_pct": outcome.mean_accuracy,
                        "naive_pct": outcome.naive_accuracy,
                        "beats_naive": outcome.beats_naive,
                        "mae": outcome.mae,
                        "naive_mae": outcome.naive_mae,
                        "rmse": outcome.rmse,
                    },
                    payload={
                        "dates": outcome.dates,
                        "actual": outcome.actual,
                        "mean_forecast": outcome.mean_forecast,
                        "naive": outcome.naive,
                    },
                )

        outcome = st.session_state.get("forecast") if mode == "Single split" else None
        if outcome is not None:
            columns = st.columns(6)
            columns[0].metric("Repo accuracy", f"{outcome.mean_accuracy:.2f}%",
                              help="The notebooks' own metric: 100% minus RMS relative "
                                   "error.")
            columns[1].metric("Naive baseline", f"{outcome.naive_accuracy:.2f}%",
                              help="Predicting that the price never moves from its last "
                                   "known value.")
            columns[2].metric("Model minus baseline",
                              f"{outcome.mean_accuracy - outcome.naive_accuracy:+.2f} pts")
            columns[3].metric("Directional", f"{outcome.directional_accuracy:.0f}%",
                              f"{outcome.directional_accuracy - 50:+.0f} pts vs coin flip",
                              help="How often the predicted move had the right sign. This "
                                   "is the one that can fail — 50% is chance.")
            columns[4].metric("MAE", f"{outcome.mae:,.2f}",
                              f"{outcome.mae - outcome.naive_mae:+,.2f} vs naive",
                              delta_color="inverse",
                              help="Mean absolute error in price units.")
            columns[5].metric("RMSE", f"{outcome.rmse:,.2f}")

            figure = base_chart(460)
            history = 90
            figure.add_trace(go.Scatter(
                x=dates.iloc[-(test_size + history):-test_size],
                y=close.iloc[-(test_size + history):-test_size],
                name="History", line=dict(color=MUTED, width=1.5),
            ))
            for index, run_values in enumerate(outcome.runs):
                figure.add_trace(go.Scatter(
                    x=outcome.dates, y=run_values, name=f"Forecast {index + 1}",
                    line=dict(width=1), opacity=0.55,
                ))
            figure.add_trace(go.Scatter(x=outcome.dates, y=outcome.mean_forecast, name="Mean forecast",
                                        line=dict(color=ACCENT, width=2.5)))
            figure.add_trace(go.Scatter(x=outcome.dates, y=outcome.actual, name="Actual",
                                        line=dict(color=PRICE, width=3)))
            figure.add_trace(go.Scatter(x=outcome.dates, y=outcome.naive, name="Naive baseline",
                                        line=dict(color=SELL, width=1.5, dash="dot")))
            st.plotly_chart(figure, use_container_width=True)

            directional = outcome.directional_accuracy
            if outcome.beats_naive:
                st.success(
                    f"The model beat the do-nothing baseline by "
                    f"{outcome.mean_accuracy - outcome.naive_accuracy:.2f} points on this window."
                )
            else:
                st.warning(
                    f"The model scored {outcome.mean_accuracy:.2f}% but simply repeating the last "
                    f"known price scores {outcome.naive_accuracy:.2f}%. A high number here mostly "
                    "reflects that prices move slowly, not that the model learned anything."
                )

            if directional < 55:
                st.error(
                    f"**Directional accuracy is {directional:.0f}%** — near the {50}% you would get "
                    "by flipping a coin. Whatever the accuracy percentage above says, this model is "
                    "not predicting which way the price goes. Treat it as a curve-fitting demo."
                )
            else:
                st.info(
                    f"Directional accuracy is {directional:.0f}% on this window. Worth checking "
                    "across several date ranges before reading anything into it — a single "
                    "30-day window is a small sample."
                )


with portfolio_tab:
    st.subheader("Portfolio")
    st.caption(
        "What you actually own, priced at the market — buy, sell and correct "
        "it here."
        if not pro else
        "What you own, and what a hypothetical basket would have done. A "
        "basket is not the average of how its members behave alone."
    )
    if source != "Live ticker":
        st.caption(
            f"Holdings are always fetched live ({period} of {interval} bars); the "
            "sidebar source only affects the other tabs."
        )

    saved = holdings.load()
    ledger = holdings.load_ledger()
    # The hypothetical basket is a Pro tool: Lite's portfolio is the book you
    # hold, and nothing that looks like a position but isn't one.
    view = st.radio(
        "View", ["My portfolio", "Custom basket"],
        horizontal=True, label_visibility="collapsed", key="portfolio_view",
    ) if pro else "My portfolio"

    if view == "My portfolio":
        with st.spinner(f"Pricing {len(saved)} positions…"):
            frames, errors = portfolio.fetch_many(
                [h.symbol for h in saved], period=period, interval=interval)
        prices = {s: float(f["close"].iloc[-1]) for s, f in frames.items()}
        book = holdings.value(saved, prices)

        for symbol, message in errors.items():
            st.warning(f"**{symbol}** could not be priced — {message}")

        # ------------------------------------------------------ trade ticket
        #
        # The book used to be editable only through a table in a Pro-only
        # expander, which meant the ordinary act of buying something was the
        # hardest thing in the app to do. This is a ticket: pick a side, name
        # a size, and the cost-basis arithmetic happens in holdings.py where
        # it can be tested.
        with st.container(border=True):
            st.markdown("**Trade**")
            columns = st.columns([1.4, 1, 1.2, 1, 0.9, 0.9])

            owned = sorted(h.symbol for h in saved)
            default_symbol = (ticker if source == "Live ticker" and ticker
                              else (owned[0] if owned else ""))
            trade_symbol = columns[0].text_input(
                "Symbol", value=default_symbol, key="trade_symbol",
                placeholder="e.g. AAPL",
            ).strip().upper()

            held = holdings.position(saved, trade_symbol)
            quoted = prices.get(trade_symbol)
            if quoted is None and trade_symbol == ticker:
                quoted = last_price          # already on screen, no second fetch
            if quoted is None:
                quoted = quotes.last_close(trade_symbol, interval)

            # A keyed widget keeps its own value across reruns, which is right
            # for a price the user typed and wrong the moment they change the
            # symbol — the ticket would otherwise offer to buy NVDA at AAPL's
            # last close. Dropping the key here re-prefills it, and this runs
            # before the widget is created, which is the only point where that
            # is still allowed.
            if st.session_state.get("trade_symbol_seen") != trade_symbol:
                st.session_state["trade_symbol_seen"] = trade_symbol
                st.session_state.pop("trade_price", None)

            trade_units = columns[1].number_input(
                "Units", min_value=0.0, value=1.0, step=1.0, format="%.4f",
                key="trade_units",
            )
            trade_price = columns[2].number_input(
                "Price", min_value=0.0, value=float(quoted or 0.0), step=0.01,
                format="%.4f", key="trade_price",
                help="Prefilled with the latest price we hold for this symbol. "
                     "Overwrite it with what you actually paid.",
            )
            trade_fee = columns[3].number_input(
                "Commission", min_value=0.0, value=0.0, step=0.5, format="%.2f",
                key="trade_fee",
                help="Added to the cost basis on a buy, deducted from realised "
                     "P&L on a sell — the way a broker statement does it.",
            )

            columns[4].markdown("<div style='height:26px'></div>",
                                unsafe_allow_html=True)
            columns[5].markdown("<div style='height:26px'></div>",
                                unsafe_allow_html=True)
            do_buy = columns[4].button("Buy", use_container_width=True,
                                       type="primary", key="trade_buy")
            do_sell = columns[5].button("Sell", use_container_width=True,
                                        key="trade_sell",
                                        disabled=held is None)

            if held is not None:
                st.caption(
                    f"You hold **{held.quantity:g} {held.symbol}** at an "
                    f"average cost of {held.unit_cost:,.4f}"
                    + (f" · selling everything at {trade_price:,.4f} would "
                       f"realise {held.quantity * (trade_price - held.unit_cost):+,.2f}"
                       if trade_price else "")
                )
            elif trade_symbol:
                st.caption(f"No open position in **{trade_symbol}** — a buy "
                           "opens one.")

            if do_buy or do_sell:
                try:
                    done = holdings.execute(
                        holdings.BUY if do_buy else holdings.SELL,
                        trade_symbol, trade_units, trade_price, trade_fee,
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    message = f"{done.describe()} — cash {done.cash:+,.2f}"
                    if done.side == holdings.SELL:
                        message += f", realised {done.realised:+,.2f}"
                    st.success(message)
                    st.rerun()

    # An empty book still gets the ticket above — the first buy has to be
    # possible — but none of the analytics below, which would all be zeros.
    if view == "My portfolio" and not saved:
        st.info(
            "No positions yet. Enter a symbol above and press **Buy** — "
            "everything below fills in from there. The book lives in a local "
            "file that is gitignored; nothing leaves this machine."
        )
        if ledger:
            st.markdown("**Closed trades**")
            st.dataframe(theme.signed(holdings.ledger_table(ledger), ("Realised",)),
                         use_container_width=True, hide_index=True)

    elif view == "My portfolio":
        realised = holdings.realised_total(ledger)

        # ------------------------------------------------- change on the bar
        #
        # The book is priced off whatever interval the toolbar is on, so the
        # move since the previous bar is only a *daily* move when those are
        # daily bars. Name it after the bar rather than claim a day the data
        # does not cover. A position with a single bar has nothing to compare
        # against and reads as absent, not zero — NaN rather than None so the
        # column stays a float and `theme.signed` renders it the same "—" an
        # unpriced holding gets, even when every position is missing one.
        bar_pnl: dict[str, float] = {}
        for position in book.priced:
            frame = frames.get(position.symbol)
            if frame is None or len(frame) < 2:
                bar_pnl[position.symbol] = float("nan")
                continue
            previous_close = float(frame["close"].iloc[-2])
            bar_pnl[position.symbol] = round(
                (position.last_price - previous_close) * position.holding.quantity, 2)
        bar_label = f"{NAME_FOR_CODE.get(interval, 'Session')} P&L"
        total_bar_pnl = round(sum(v for v in bar_pnl.values() if v == v), 2)

        columns = st.columns(7 if pro else 6)
        columns[0].metric("Market value", f"${book.market_value:,.2f}",
                          f"{book.pnl:+,.2f}")
        columns[1].metric("Cost basis", f"${book.cost_basis:,.2f}")
        columns[2].metric("Unrealised", f"{book.pnl_pct:+.2f}%")
        columns[3].metric("Realised", f"${realised:+,.2f}",
                          help="Booked on sells, commission deducted. Comes "
                               "from the trade ledger, not from prices.")
        columns[4].metric(bar_label, f"${total_bar_pnl:+,.2f}",
                          help="Change in market value since the previous bar "
                               "close, across every position that has one.")
        columns[5].metric("Positions", f"{len(book.priced)}")
        if pro:
            columns[6].metric("Largest position", f"{book.concentration_pct:.1f}%",
                              help="Share of the book in its single biggest holding.")

        # -------------------------------------------------- the book's signal
        #
        # The same verdict the signal tab produces, per position, in the list
        # where it is actually actionable. Run through `ultimate.scan` rather
        # than a cheaper approximation so a row here can never disagree with
        # the tab for the same ticker.
        with st.spinner(f"Reading {len(saved)} positions across three horizons…"):
            scanned = scan_book(tuple(sorted(h.symbol for h in saved)))

        signal = ultimate.book_signal(
            scanned, {p.symbol: p.market_value for p in book.priced})

        columns = st.columns([1.2, 1, 1, 1, 1, 0.9])
        columns[0].metric("Book signal", f"{signal.score:+.0f}",
                          f"{signal.confidence:.0f}% confidence",
                          delta_color="off",
                          help="Every position's call, weighted by market "
                               "value rather than by position count — a 40% "
                               "holding is not one vote among eighteen.")
        columns[1].metric("Reading buy", len(signal.buying))
        columns[2].metric("Reading sell", len(signal.selling))
        columns[3].metric("Reading hold",
                          signal.total - len(signal.buying) - len(signal.selling))
        columns[4].metric("Unreadable", len(signal.unreadable),
                          help="Too little history to measure an edge on. "
                               "Usually a recent listing.")
        columns[5].markdown("<div style='height:26px'></div>",
                            unsafe_allow_html=True)
        if columns[5].button("↻ Rescan", use_container_width=True,
                             help="Drop the cached scan and re-read every "
                                  "position."):
            scan_book.clear()
            st.rerun()

        if signal.selling:
            st.warning(
                f"**{len(signal.selling)} position(s) you hold read as a sell:** "
                f"{', '.join(signal.selling)}. That is the disagreement worth "
                "looking at — the rest of this table only says what has already "
                "happened."
            )

        calls = ultimate.scan_table(scanned)
        table = book.table().merge(
            calls[["Symbol", "Call", "Signal", "Confidence %"]],
            on="Symbol", how="left")
        table[bar_label] = table["Symbol"].map(bar_pnl)
        st.dataframe(
            theme.signed(table, ("P&L", "P&L %", bar_label, "Signal"),
                         calls=("Call",)),
            use_container_width=True, hide_index=True,
            height=min(640, 40 + 35 * len(table)))
        st.caption(
            "`Call` and `Signal` are the ultimate indicator on that symbol, "
            "measured the same way the Signal tab measures it. `HOLD` at a "
            "signal of 0 means nothing cleared significance — which is the "
            "ordinary result, not a missing number."
        )
        st.caption(
            f"`{bar_label}` is the change in market value from the previous "
            f"{NAME_FOR_CODE.get(interval, 'session').lower()} bar's close to "
            "the latest price, so it follows the interval the toolbar is on "
            "rather than always meaning a day. A dash means the symbol has "
            "only one bar to stand on."
        )

        if pro:
            with st.expander("Each position, horizon by horizon"):
                st.dataframe(
                    theme.signed(calls, ("Signal",),
                                 calls=("Call", "4 hours", "1 day", "1 week")),
                    use_container_width=True, hide_index=True,
                    height=min(560, 40 + 35 * len(calls)))
                st.caption(
                    "A position whose horizons disagree is not a weak signal, "
                    "it is two different signals — the short view and the long "
                    "view are answering different questions about it."
                )

        left, right = st.columns(2)
        with left:
            st.markdown("**Profit and loss by position**")
            ordered = sorted(book.priced, key=lambda p: p.pnl)
            waterfall = base_chart(380)
            waterfall.add_trace(go.Bar(
                x=[p.pnl for p in ordered], y=[p.symbol for p in ordered],
                orientation="h",
                marker_color=[BUY if p.pnl >= 0 else SELL for p in ordered],
                name="P&L",
            ))
            waterfall.update_layout(xaxis_title="Unrealised P&L")
            st.plotly_chart(waterfall, use_container_width=True)
        with right:
            st.markdown("**Weight by market value**")
            weighted = sorted(book.priced, key=lambda p: p.market_value, reverse=True)
            pie = base_chart(380)
            pie.add_trace(go.Pie(
                labels=[p.symbol for p in weighted],
                values=[p.market_value for p in weighted],
                hole=0.45, textinfo="label+percent", sort=False,
                # Slices are adjacent fills with no axis between them, so on a
                # dark canvas they need the background drawn back in as a border.
                marker=dict(line=dict(color=charts.BACKGROUND, width=2)),
            ))
            st.plotly_chart(pie, use_container_width=True)

        if book.winners and book.losers:
            best, worst = book.winners[0], book.losers[0]
            st.markdown(
                f"**Biggest winner** {best.symbol} {best.pnl:+,.2f} "
                f"({best.pnl_pct:+.1f}%) · **biggest loser** {worst.symbol} "
                f"{worst.pnl:+,.2f} ({worst.pnl_pct:+.1f}%)"
            )

        curve = holdings.history(saved, frames)
        if not curve.empty:
            limiting = holdings.shortest_history(frames)
            total = curve.sum(axis=1)
            value_chart = base_chart(360)
            value_chart.add_trace(go.Scatter(
                x=curve.index, y=total, name="Portfolio value",
                line=dict(color=ACCENT, width=2.5)))
            value_chart.add_hline(
                y=book.cost_basis, line=dict(color=MUTED, dash="dash"),
                annotation_text="cost basis")
            st.markdown("**Value over the window every holding shares**")
            st.plotly_chart(value_chart, use_container_width=True)
            if limiting:
                st.caption(
                    f"Limited to {len(curve)} bars by **{limiting[0]}**, the most "
                    f"recently listed holding. The curve assumes today's share counts "
                    "throughout, so it is a what-if on the current book, not a record "
                    "of what you actually held."
                )

        # Editing the whole book is no longer behind Pro. Correcting a wrong
        # cost basis is bookkeeping, not an advanced feature, and a mode that
        # can buy but not fix a typo is a worse mode.
        with st.expander("Edit all positions"):
            st.caption(
                "Direct edits to the book. Rows can be added and removed; "
                "changes here are **not** written to the trade history, "
                "because a correction is not a trade."
            )
            edited = st.data_editor(
                holdings.editable(saved), num_rows="dynamic",
                use_container_width=True, key="holdings_editor",
            )
            columns = st.columns([1, 1, 4])
            if columns[0].button("Save all", type="primary", key="save_all"):
                holdings.save(holdings.from_frame(edited))
                st.success("Saved.")
                st.rerun()
            if columns[1].button("Discard", key="discard_edits"):
                st.rerun()
            columns[2].caption(
                f"Stored at `{local_path(holdings.STORE)}` and "
                f"`{local_path(holdings.LEDGER)}`, both gitignored — this is "
                "personal financial data."
            )

        st.markdown("**Trade history**")
        if not ledger:
            st.caption("No trades recorded yet. Anything entered through the "
                       "ticket above lands here.")
        else:
            columns = st.columns(3)
            columns[0].metric("Trades", len(ledger))
            columns[1].metric("Realised P&L",
                              f"${holdings.realised_total(ledger):+,.2f}")
            columns[2].metric("Commission paid",
                              f"${holdings.fees_total(ledger):,.2f}")
            st.dataframe(
                theme.signed(holdings.ledger_table(ledger), ("Realised",)),
                use_container_width=True, hide_index=True,
                height=min(420, 60 + 35 * len(ledger)),
            )
            if pro:
                with st.expander("Clear trade history"):
                    st.caption(
                        "Removes the ledger only. Positions and cost basis are "
                        "a separate file and are left alone — which also means "
                        "realised P&L resets to zero while the book does not."
                    )
                    if st.button("Delete every recorded trade", key="clear_ledger"):
                        holdings.save_ledger([])
                        st.rerun()

    else:
        # Kept separate from the saved book so switching views doesn't
        # overwrite either one.
        if "holdings_basket" not in st.session_state:
            st.session_state.holdings_basket = ["AAPL", "MSFT", "NVDA"]
        basket = st.session_state.holdings_basket

        chosen = st.multiselect(
            "Holdings", options=sorted(set(live.QUICK_PICKS) | set(basket)),
            default=basket,
            max_selections=portfolio.MAX_HOLDINGS,
            help="Pick from the list, or type any Yahoo symbol below to add one.",
        )

        columns = st.columns([2, 1, 2])
        extra = columns[0].text_input("Add a symbol", placeholder="e.g. GOOGL, BTC-USD",
                                      key="portfolio_add")
        if columns[1].button("Add", use_container_width=True) and extra.strip():
            candidate = extra.strip().upper()
            if candidate not in chosen and len(chosen) < portfolio.MAX_HOLDINGS:
                st.session_state.holdings_basket = chosen + [candidate]
                st.rerun()

        if not chosen:
            st.info("Choose at least one holding to build a portfolio.")
        else:
            st.session_state.holdings_basket = chosen

            if pro:
                rebalance_label = columns[2].selectbox("Rebalance",
                                                       list(portfolio.REBALANCE))
            else:
                rebalance_label = "Never (let it drift)"
            rebalance_every = portfolio.REBALANCE[rebalance_label]

            with st.spinner(f"Loading {len(chosen)} holdings…"):
                frames, errors = portfolio.fetch_many(chosen, period=period, interval=interval)

            for symbol, message in errors.items():
                st.warning(f"**{symbol}** skipped — {message}")

            if not frames:
                st.error("None of those symbols could be loaded.")
            else:
                weights = {s: 100 / len(frames) for s in frames}
                if pro:
                    with st.expander("Weights", expanded=False):
                        weight_columns = st.columns(len(frames))
                        for index, symbol in enumerate(frames):
                            weights[symbol] = weight_columns[index].number_input(
                                symbol, 0.0, 100.0, round(100 / len(frames), 1), step=5.0,
                                key=f"weight_{symbol}",
                            )
                        st.caption("Rescaled to total 100% automatically.")

                prices = portfolio.align(frames)
                if len(prices) < 5:
                    st.error(
                        "These holdings barely overlap in time — the basket is only defined "
                        "where every member traded. Try a shorter history or drop the "
                        "newest listing."
                    )
                else:
                    book = portfolio.build(prices, weights, initial_money=initial_money,
                                           rebalance_every=rebalance_every)
                    stats = portfolio.per_symbol_stats(prices, book.bars_per_year)

                    columns = st.columns(5 if pro else 4)
                    columns[0].metric("Value", f"{book.final_value:,.0f}",
                                      f"{book.profit:+,.0f}")
                    columns[1].metric("Return", f"{book.roi_pct:.2f}%")
                    columns[2].metric("Best holding", stats.iloc[0]["Symbol"],
                                      f"{stats.iloc[0]['Return %']:+.1f}%")
                    columns[3].metric("Max drawdown", f"{book.max_drawdown_pct:.1f}%")
                    if pro:
                        columns[4].metric("Sharpe", f"{book.sharpe:.2f}",
                                          help=f"Annualised at {book.bars_per_year:,} "
                                               "bars/year.")

                    figure = base_chart(400)
                    for symbol in prices.columns:
                        scaled = prices[symbol] / float(prices[symbol].iloc[0]) * initial_money
                        figure.add_trace(go.Scatter(
                            x=prices.index, y=scaled, name=symbol,
                            line=dict(width=1.2), opacity=0.55,
                        ))
                    figure.add_trace(go.Scatter(
                        x=prices.index, y=book.equity, name="Portfolio",
                        line=dict(color=ACCENT, width=3),
                    ))
                    figure.update_layout(yaxis_title="Value of your starting capital")
                    st.plotly_chart(figure, use_container_width=True)

                    left, right = st.columns([3, 2])
                    with left:
                        st.markdown("**Each holding on its own**")
                        st.dataframe(theme.signed(stats, ("Return %",)),
                                     use_container_width=True, hide_index=True)
                    with right:
                        st.markdown("**Where the money ended up**")
                        final = book.final_weights
                        allocation = base_chart(260)
                        allocation.add_trace(go.Bar(
                            x=list(final.values()), y=list(final), orientation="h",
                            marker_color=PRICE, name="Final %",
                        ))
                        allocation.add_trace(go.Scatter(
                            x=[book.weights[s] for s in final], y=list(final), mode="markers",
                            marker=dict(symbol="line-ns", size=14, line=dict(width=2,
                                                                             color=SELL)),
                            name="Target %",
                        ))
                        allocation.update_layout(xaxis_title="% of portfolio")
                        st.plotly_chart(allocation, use_container_width=True)

                    drift = max(abs(final[s] - book.weights[s]) for s in final)
                    if rebalance_every == 0 and drift > 15:
                        biggest = max(final, key=final.get)
                        st.info(
                            f"Without rebalancing, **{biggest}** has grown to "
                            f"{final[biggest]:.0f}% of the book against a "
                            f"{book.weights[biggest]:.0f}% target. The portfolio is now "
                            "largely a bet on one holding."
                            + ("" if pro else " Pro mode can rebalance.")
                        )

                    if len(prices.columns) > 1:
                        correlation = portfolio.correlations(prices)
                        average, verdict = portfolio.diversification_note(correlation)
                        st.markdown(
                            f"**Diversification** — average correlation "
                            f"{average:.2f}. {verdict}"
                        )
                        if pro:
                            heat = base_chart(320)
                            heat.add_trace(go.Heatmap(
                                z=correlation.to_numpy(), x=list(correlation.columns),
                                y=list(correlation.index), zmin=-1, zmax=1,
                                colorscale="RdBu", reversescale=True,
                                text=correlation.round(2).to_numpy(), texttemplate="%{text}",
                            ))
                            st.plotly_chart(heat, use_container_width=True)


if pro:
    with carlo_tab:
        st.subheader("Monte Carlo simulation")
        st.caption(
            "Projects the series forward as a random walk using its own historic drift "
            "and volatility. It describes a range of outcomes, not a prediction."
        )

        columns = st.columns(4)
        days = columns[0].slider(f"{bar_word.capitalize()} ahead", 5, 252, 30)
        paths = columns[1].slider("Paths", 20, 2_000, 200, step=20)
        seed_on = columns[2].checkbox("Reproducible", value=True)
        seed = columns[3].number_input("Seed", 0, 9_999, 42, disabled=not seed_on)

        simulation = montecarlo.run(close, days=days, simulations=paths,
                                    seed=int(seed) if seed_on else None)
        summary = simulation.summary()

        columns = st.columns(5)
        columns[0].metric("Start price", f"{simulation.last_price:,.2f}")
        columns[1].metric("Median outcome", f"{summary['median']:,.2f}",
                          f"{(summary['median'] / simulation.last_price - 1) * 100:+.1f}%")
        columns[2].metric("5th percentile", f"{summary['p5']:,.2f}")
        columns[3].metric("95th percentile", f"{summary['p95']:,.2f}")
        columns[4].metric("Paths ending higher", f"{summary['prob_up']:.0f}%")

        left, right = st.columns([3, 2])
        with left:
            figure = base_chart(400)
            # Drawing every path kills the browser, so show a sample plus the envelope.
            for column in simulation.paths.columns[:120]:
                figure.add_trace(go.Scatter(
                    y=simulation.paths[column], mode="lines", showlegend=False,
                    line=dict(width=0.7, color="rgba(91,141,239,0.18)"), hoverinfo="skip",
                ))
            figure.add_trace(go.Scatter(y=simulation.paths.median(axis=1), name="Median",
                                        line=dict(color=ACCENT, width=2.5)))
            figure.update_layout(xaxis_title=f"{bar_word.capitalize()} ahead")
            st.plotly_chart(figure, use_container_width=True)
        with right:
            histogram = base_chart(400)
            histogram.add_trace(go.Histogram(x=simulation.endings, nbinsx=50,
                                             marker_color=PRICE, name="Final price"))
            histogram.add_vline(x=simulation.last_price,
                                line=dict(color=SELL, dash="dash"))
            histogram.update_layout(xaxis_title=f"Price after {days} {bar_word}")
            st.plotly_chart(histogram, use_container_width=True)


if pro:
    with history_tab:
        st.subheader("Saved runs")
        st.caption(
            "Every training run is written to disk the moment it finishes, so a "
            "browser refresh no longer throws the result away — and you can compare "
            "what different settings actually produced."
        )

        saved_runs = runs.load_all()

        if not saved_runs:
            st.info(
                "Nothing saved yet. Train a forecast or a trading agent and it will "
                "appear here automatically."
            )
        else:
            kinds = ["All"] + [runs.KIND_LABELS[k] for k in
                               dict.fromkeys(run.kind for run in saved_runs)]
            columns = st.columns([2, 3])
            chosen_kind = columns[0].selectbox("Show", kinds)
            if chosen_kind != "All":
                code = next(k for k, v in runs.KIND_LABELS.items() if v == chosen_kind)
                shown = [run for run in saved_runs if run.kind == code]
            else:
                shown = saved_runs
            columns[1].caption(
                f"{len(saved_runs)} run(s) on disk · newest {saved_runs[0].describe_age()}"
            )

            table = runs.table(shown)
            st.dataframe(table.drop(columns=["id"]), use_container_width=True,
                         hide_index=True, height=min(420, 60 + 35 * len(table)))

            st.markdown("**Look at one again**")
            labels = {
                f"{run.saved_at:%Y-%m-%d %H:%M} · {run.kind_label} · {run.label}": run
                for run in shown
            }
            picked_label = st.selectbox("Run", list(labels), label_visibility="collapsed")
            picked = labels[picked_label]

            left, right = st.columns([3, 1])
            with right:
                st.markdown("**Settings**")
                st.json(picked.settings, expanded=True)
            with left:
                payload = picked.payload

                if picked.kind == runs.FORECAST and payload.get("actual"):
                    figure = base_chart(360)
                    axis = list(range(len(payload["actual"])))
                    figure.add_trace(go.Scatter(x=axis, y=payload["actual"],
                                                name="Actual",
                                                line=dict(color=PRICE, width=3)))
                    figure.add_trace(go.Scatter(x=axis, y=payload.get("mean_forecast", []),
                                                name="Forecast",
                                                line=dict(color=ACCENT, width=2.5)))
                    figure.add_trace(go.Scatter(x=axis, y=payload.get("naive", []),
                                                name="Naive baseline",
                                                line=dict(color=SELL, width=1.5, dash="dot")))
                    figure.update_layout(xaxis_title=f"{bar_word.capitalize()} ahead")
                    st.plotly_chart(figure, use_container_width=True)

                elif picked.kind == runs.WALKFORWARD and payload.get("directionals"):
                    figure = base_chart(360)
                    figure.add_trace(go.Bar(x=payload.get("fold_index", []),
                                            y=payload["directionals"],
                                            name="Directional %", marker_color=PRICE))
                    figure.add_hline(y=50, line=dict(color=SELL, dash="dash"),
                                     annotation_text="coin flip")
                    figure.update_layout(xaxis_title="Fold",
                                         yaxis_title="Directional accuracy %",
                                         yaxis=dict(range=[0, 100]))
                    st.plotly_chart(figure, use_container_width=True)

                elif picked.kind == runs.AGENT and payload.get("equity"):
                    figure = base_chart(360)
                    figure.add_trace(go.Scatter(y=payload["equity"], name="Agent",
                                                line=dict(color=ACCENT, width=2)))
                    figure.update_layout(xaxis_title="Bar",
                                         yaxis_title="Portfolio value")
                    st.plotly_chart(figure, use_container_width=True)
                    if payload.get("rewards"):
                        curve = base_chart(220)
                        curve.add_trace(go.Scatter(y=payload["rewards"],
                                                   name="Policy return %",
                                                   line=dict(color=PRICE, width=2)))
                        curve.update_layout(xaxis_title="Training iteration")
                        st.plotly_chart(curve, use_container_width=True)
                else:
                    st.caption("This run has no chart data saved.")

            st.markdown("**Headline numbers**")
            metric_columns = st.columns(min(6, max(1, len(picked.metrics))))
            for index, (name, value) in enumerate(picked.metrics.items()):
                label_text = name.replace("_", " ").capitalize()
                if isinstance(value, bool):
                    shown_value = "yes" if value else "no"
                elif isinstance(value, (int, float)) and value is not None:
                    shown_value = f"{value:,.2f}"
                else:
                    shown_value = "—" if value is None else str(value)
                metric_columns[index % len(metric_columns)].metric(label_text, shown_value)

            st.divider()
            left, right = st.columns([1, 4])
            if left.button("Delete this run"):
                runs.delete(picked.id)
                st.rerun()
            with right.expander("Delete every saved run"):
                st.caption("This cannot be undone.")
                if st.button("Yes, delete all", type="primary"):
                    removed = runs.clear()
                    st.success(f"Deleted {removed} run(s).")
                    st.rerun()
