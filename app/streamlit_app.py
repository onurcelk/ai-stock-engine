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
    portfolio, strategies,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

RULE_BASED = ["Turtle (channel breakout)", "Moving average crossover", "Signal rolling"]

# Gains and losses borrow the candle colours so green means the same thing in
# every pane. The other three are picked to stay legible on the dark canvas,
# where TradingView's own blue (#2962ff) is too heavy for a line or a fill.
PRICE = "#5B8DEF"
BUY = charts.UP
SELL = charts.DOWN
MUTED = "#8B93A7"
ACCENT = "#B084F5"

st.set_page_config(page_title="Stock Prediction Models", page_icon="📈", layout="wide")


# ---------------------------------------------------------------- helpers


@st.cache_data(show_spinner=False)
def load_bundled(name: str) -> pd.DataFrame:
    return data.load(name)


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


# ---------------------------------------------------------------- sidebar

st.sidebar.title("📈 Stock Prediction Models")

# Lite hides every knob that has a sensible default, which is most of them.
# Pro exposes the full parameter surface.
mode_choice = st.sidebar.radio(
    "Interface", ["Lite", "Pro"], horizontal=True, label_visibility="collapsed",
    help="Lite keeps the essentials on screen. Pro adds model internals, "
         "trading costs, position sizing and walk-forward validation.",
)
pro = mode_choice == "Pro"
st.sidebar.caption(
    "Essentials only — switch to **Pro** for model internals, costs and sizing."
    if not pro else "Full control. Switch to **Lite** for a simpler view."
)

source = st.sidebar.radio("Data source", ["Live ticker", "Bundled dataset", "Upload CSV"])

frame: pd.DataFrame | None = None
label = ""
# Defaults for the non-live sources: the Portfolio tab always pulls live data
# (a basket needs several symbols, and the bundled CSVs are one series each),
# so it needs these defined whichever source is selected.
interval = "1d"
period = "5y"

if source == "Live ticker":
    # Quick picks are rendered before the text input so a click can set its
    # value: session_state may only be written before the widget is created.
    if "symbol" not in st.session_state:
        st.session_state.symbol = "AAPL"

    picks = st.sidebar.columns(4)
    for index, ticker in enumerate(live.QUICK_PICKS):
        if picks[index % 4].button(ticker, key=f"pick_{ticker}", use_container_width=True):
            st.session_state.symbol = ticker

    symbol = st.sidebar.text_input("Symbol", key="symbol")

    if pro:
        columns = st.sidebar.columns(2)
        # Interval first: it decides which history lengths Yahoo will serve.
        interval_label = columns[0].selectbox("Bars", list(live.INTERVALS),
                                              index=list(live.INTERVALS).index("Daily"))
        interval = live.INTERVALS[interval_label]

        choices = live.periods_for(interval)
        period = columns[1].selectbox(
            "History", choices, index=choices.index(live.default_period(interval)),
            help="Yahoo serves intraday bars only for the last 730 days."
            if interval in live.INTRADAY else None,
        )
    else:
        interval_label, interval, period = "Daily", "1d", "5y"

    refresh = st.sidebar.button("↻ Refresh from Yahoo", use_container_width=True,
                                help="Ignore the local cache and re-download.")

    try:
        frame, entry = live.fetch(symbol, period=period, interval=interval, force=refresh)
        label = f"{entry.symbol} · {interval_label}"
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
    choice = st.sidebar.selectbox("Series", data.list_datasets())
    try:
        frame = load_bundled(choice)
        label = choice
    except Exception as error:  # noqa: BLE001 - surface any parse failure in the UI
        st.sidebar.error(f"Could not read {choice}: {error}")

else:
    upload = st.sidebar.file_uploader("CSV with a date and a price column", type="csv")
    if upload is not None:
        try:
            frame = data.load_upload(upload)
            label = upload.name
        except Exception as error:  # noqa: BLE001
            st.sidebar.error(f"Could not read that file: {error}")

if frame is None:
    st.title("Stock Prediction Models")
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

if pro:
    initial_money = st.sidebar.number_input(
        "Starting capital", min_value=100, max_value=1_000_000, value=10_000, step=1_000
    )
    with st.sidebar.expander("Trading costs"):
        fee_pct = st.number_input("Commission %", 0.0, 5.0, 0.10, step=0.01, format="%.3f",
                                  help="Charged on the notional of every fill, both sides.")
        slippage_pct = st.number_input("Slippage %", 0.0, 5.0, 0.05, step=0.01,
                                       format="%.3f",
                                       help="Buys fill above the close, sells below it.")
        st.caption("Set both to 0 to reproduce the original notebook figures.")
else:
    # Realistic retail defaults; Pro exposes them.
    initial_money, fee_pct, slippage_pct = 10_000, 0.10, 0.05

st.sidebar.divider()
st.sidebar.caption(
    f"**{len(frame)}** rows · {frame['date'].min():%Y-%m-%d} → {frame['date'].max():%Y-%m-%d}"
)

close = frame["close"]
dates = frame["date"]

# "30 days" is wrong once bars are hourly — every horizon control counts bars.
bar_word = "bars" if interval in live.INTRADAY else "days"

if len(frame) < 40:
    st.warning("That window is very short — most models need a few hundred rows to behave.")


# ------------------------------------------------------------------- tabs

if pro:
    overview_tab, agent_tab, forecast_tab, portfolio_tab, carlo_tab = st.tabs(
        ["Overview", "Trading agents", "Forecast", "Portfolio", "Monte Carlo"]
    )
else:
    overview_tab, agent_tab, forecast_tab, portfolio_tab = st.tabs(
        ["Overview", "Trading agents", "Forecast", "Portfolio"]
    )
    carlo_tab = None


with overview_tab:
    st.subheader(f"{label}")
    stats = data.describe(frame)

    columns = st.columns(5)
    columns[0].metric("Last close", f"{stats['last']:,.2f}", f"{stats['change_pct']:+.1f}% overall")
    columns[1].metric("High", f"{stats['high']:,.2f}")
    columns[2].metric("Low", f"{stats['low']:,.2f}")
    columns[3].metric("Ann. volatility", f"{stats['volatility_pct']:.1f}%",
                      help=f"Annualised from {stats['bars_per_year']:,} bars per year, "
                           "measured from this series rather than assumed.")
    columns[4].metric("Bars", f"{stats['rows']:,}")

    st.plotly_chart(
        charts.price_chart(frame, symbol=label.split(" · ")[0],
                           interval_label=interval),
        use_container_width=True, config=charts.CONFIG,
    )

    left, right = st.columns([2, 1])
    with left:
        st.markdown("**Daily returns**")
        returns = close.pct_change().dropna() * 100
        histogram = base_chart(height=260)
        histogram.add_trace(go.Histogram(x=returns, nbinsx=60, marker_color=PRICE, name="Daily %"))
        st.plotly_chart(histogram, use_container_width=True)
    with right:
        st.markdown("**Raw data**")
        st.dataframe(frame.tail(200), use_container_width=True, height=260, hide_index=True)


with agent_tab:
    st.subheader("Rule-based trading agents")
    st.caption(
        "Each agent emits buy/sell signals; the same engine executes them. "
        "The benchmark is buy & hold over the identical window."
    )

    if pro:
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
    else:
        agent_name = st.selectbox(
            "Agent",
            RULE_BASED + list(agents.REGISTRY),
        )
        # Fully invested, so the buy & hold benchmark is a fair fight.
        sizing, size_pct, max_buy, max_sell = backtest.ALL_IN, 100.0, 1, 1

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
        if pro:
            layer_size = columns[2].select_slider("Hidden units", [32, 64, 128, 256],
                                                  value=64)
            seed = columns[3].number_input("Seed", 0, 9_999, 42,
                                           help="Same seed, same agent.")
        else:
            layer_size, seed = 64, 42

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
                st.session_state["rl"] = {
                    "fingerprint": fingerprint,
                    "signal": learner.signals(),
                    "rewards": report.rewards,
                    "seconds": report.seconds,
                }
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

        if pro:
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
        else:
            columns = st.columns(4)
            columns[0].metric("Final value", f"{result.final_value:,.0f}",
                              f"{result.profit:+,.0f}")
            columns[1].metric("Return", f"{result.roi_pct:.2f}%",
                              delta_vs_benchmark(result.roi_pct, result.buy_hold_roi_pct))
            columns[2].metric("Buy & hold", f"{result.buy_hold_roi_pct:.2f}%")
            columns[3].metric("Trades", len(result.trades))

        st.plotly_chart(
            charts.price_chart(
                frame, symbol=label.split(" · ")[0], interval_label=interval,
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

        if pro:
            left, right = st.columns([3, 2])
            with left:
                st.markdown("**Portfolio value vs buy & hold**")
                st.plotly_chart(equity_chart, use_container_width=True)
            with right:
                st.markdown("**Closed trades**")
                st.dataframe(backtest.trade_table(result), use_container_width=True,
                             height=300, hide_index=True)
        else:
            st.markdown("**Your money vs simply holding**")
            st.plotly_chart(equity_chart, use_container_width=True)

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


with forecast_tab:
    st.subheader("Neural forecast")
    st.caption(
        "Trains on everything except the last N days, then predicts them. "
        "Runs on CPU — a few hundred epochs takes roughly 20 seconds per simulation."
    )

    if pro:
        mode = st.radio(
            "Evaluation", ["Single split", "Walk-forward"], horizontal=True,
            help="A single split trains once and predicts the final window. "
                 "Walk-forward repeats that down the series so you can see whether a "
                 "good result holds up.",
        )
    else:
        mode = "Single split"

    columns = st.columns(4 if pro else 3)
    model_name = columns[0].selectbox("Model", list(forecast.MODELS))
    test_size = columns[1].slider(f"{bar_word.capitalize()} to predict", 5, 60, 30)
    epochs = columns[2].slider("Epochs", 10, 500, 150, step=10)

    if not pro:
        simulations, fold_count = 3, 0
    elif mode == "Single split":
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

    if pro:
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
    else:
        num_layers, size_layer, timestamp, learning_rate, dropout = 1, 128, 5, 0.01, 0.8

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

            st.session_state["walk"] = forecast.walk_forward(
                close, dates, folds=fold_count, horizon=test_size, model=model_name,
                num_layers=num_layers, size_layer=size_layer, timestamp=timestamp,
                epochs=epochs, dropout=dropout, learning_rate=learning_rate,
                progress=on_fold_progress,
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

    outcome = st.session_state.get("forecast") if mode == "Single split" else None
    if outcome is not None:
        if pro:
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
        else:
            columns = st.columns(3)
            columns[0].metric("Got the direction right",
                              f"{outcome.directional_accuracy:.0f}%",
                              f"{outcome.directional_accuracy - 50:+.0f} pts vs a coin flip",
                              help="The number that matters: how often it called the "
                                   "next move correctly.")
            columns[1].metric("Typical error", f"{outcome.mae:,.2f}",
                              f"{outcome.mae - outcome.naive_mae:+,.2f} vs guessing "
                              "no change", delta_color="inverse")
            columns[2].metric("Best run", f"{max(outcome.accuracies):.2f}%")

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
        "Hold several symbols together and see how the basket behaves — which is not "
        "the average of how they behave alone."
    )
    if source != "Live ticker":
        st.caption(
            f"Holdings are always fetched live ({period} of {interval} bars); the "
            "sidebar source only affects the other tabs."
        )

    saved = holdings.load()
    view = st.radio(
        "View", ["My portfolio", "Custom basket"] if saved else ["Custom basket"],
        horizontal=True, label_visibility="collapsed",
    )

    if view == "My portfolio":
        with st.spinner(f"Pricing {len(saved)} positions…"):
            frames, errors = portfolio.fetch_many(
                [h.symbol for h in saved], period=period, interval=interval)
        prices = {s: float(f["close"].iloc[-1]) for s, f in frames.items()}
        book = holdings.value(saved, prices)

        for symbol, message in errors.items():
            st.warning(f"**{symbol}** could not be priced — {message}")

        columns = st.columns(5 if pro else 4)
        columns[0].metric("Market value", f"${book.market_value:,.2f}",
                          f"{book.pnl:+,.2f}")
        columns[1].metric("Cost basis", f"${book.cost_basis:,.2f}")
        columns[2].metric("Return", f"{book.pnl_pct:+.2f}%")
        columns[3].metric("Positions", f"{len(book.priced)}")
        if pro:
            columns[4].metric("Largest position", f"{book.concentration_pct:.1f}%",
                              help="Share of the book in its single biggest holding.")

        table = book.table()
        st.dataframe(table, use_container_width=True, hide_index=True,
                     height=min(640, 40 + 35 * len(table)))

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

        if pro:
            with st.expander("Edit holdings"):
                edited = st.data_editor(
                    holdings.editable(saved), num_rows="dynamic",
                    use_container_width=True, key="holdings_editor",
                )
                if st.button("Save holdings"):
                    holdings.save(holdings.from_frame(edited))
                    st.success("Saved.")
                    st.rerun()
                st.caption(
                    f"Stored locally at `{holdings.STORE.relative_to(REPO_ROOT)}` "
                    "and gitignored — this is personal financial data."
                )

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
                        st.dataframe(stats, use_container_width=True, hide_index=True)
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
