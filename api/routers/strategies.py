"""Phase 6d: the instant agents -- rule-based strategies and the ported studies.

The Trading-agents tab offers three kinds of thing in one dropdown: three fixed
rules, seven ported TradingView studies traded on their published signal, and
19 reinforcement-learning policies. Only the last kind needs training, and only
the last kind therefore needed `api/routers/jobs.py`. These two run in
milliseconds on the main thread, so a job would add a queue, an id and a poll
to something that is finished before the response would have been written.

Everything here delegates:

  rule-based   `strategies.turtle` / `.moving_average` / `.signal_rolling`
  studies      `pine.signals`, and `pine.bands` for the overlay lines
  scoring      `backtest.run` -- the same backtester the RL jobs use, against
               the same buy-and-hold benchmark

No signal maths is restated. `RULES` below is a dispatch table naming those
functions and their parameter ranges; it holds no strategy logic, and it is
deliberately *not* a new registry in `core`. `strategies.py`'s source hash is
the version key for the three registered `rule_agent.*` models
(`forecast_ledger._module_version(strategies)`), so adding a registry to it
would re-version live models against a ledger holding real prospective
forecasts. The same reasoning `pine.py` gives for restating the buy/sell
constants rather than importing them.

**Nothing here writes.** These are `GET`s because they are safe in the HTTP
sense and safe in fact: no ledger, no book, no saved run. That is not an
oversight to be corrected later -- Streamlit does not file a History run for a
rule or a study either (`runs.save` is reached only from the RL branch), and a
`GET` that wrote is the exact defect Phase 6a existed to remove. A test asserts
this module names neither `holdings` nor `ledger_activation`.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Query

from core import backtest, data, live, pine, strategies

from ..schemas import to_jsonable

router = APIRouter()

DEFAULT_PERIOD = "5y"
DEFAULT_INTERVAL = "1d"

RULE = "rule"
STUDY = "study"

#: How each fixed rule is driven, and the words it is honestly described in.
#:
#: `default` is a callable of the frame length because the tab's own defaults
#: scale with the series -- a 10% channel on 250 bars is not a 10% channel on
#: 2500. Keeping that here rather than in the page means the frontend does not
#: reimplement the arithmetic, which is the same reason the signals themselves
#: are not computed there.
RULES = {
    "turtle": {
        "name": "Turtle (channel breakout)",
        "describe": "Buy and sell as price leaves a rolling high/low channel.",
        "rule": ("Mean-reverting by default -- sells strength and buys weakness, "
                 "which is the notebook's version. Turn on 'follow breakouts' for "
                 "the classic turtle, which does the opposite."),
        "params": [
            {"name": "window", "kind": "int", "min": 2, "max": 400,
             "default": lambda n: max(2, int(math.ceil(n * 0.1))),
             "describe": "Channel window, in bars."},
            {"name": "follow_breakout", "kind": "bool", "default": lambda n: False,
             "describe": "Follow breakouts instead of fading them."},
        ],
    },
    "crossover": {
        "name": "Moving average crossover",
        "describe": "Buy when a short average crosses above a long one.",
        "rule": "Buy the golden cross, sell the death cross. Nothing else.",
        "params": [
            {"name": "short_window", "kind": "int", "min": 2, "max": 60,
             "default": lambda n: max(2, int(0.025 * n)),
             "describe": "Short moving average, in bars."},
            {"name": "long_window", "kind": "int", "min": 3, "max": 200,
             "default": lambda n: max(3, int(0.05 * n)),
             "describe": "Long moving average, in bars."},
        ],
    },
    "rolling": {
        "name": "Signal rolling",
        "describe": "Flip position after enough consecutive moves against it.",
        "rule": ("Counts moves against the current position and flips once the "
                 "count reaches the delay. A momentum rule with a patience dial."),
        "params": [
            {"name": "delay", "kind": "int", "min": 1, "max": 30,
             "default": lambda n: 4,
             "describe": "Moves against the position tolerated before acting."},
        ],
    },
}


def _param_spec(spec: dict, bars: int) -> dict:
    """One parameter, with its default resolved against this series."""
    out = {k: v for k, v in spec.items() if k != "default"}
    out["default"] = spec["default"](bars)
    return out


def _bars(symbol: str, period: str, interval: str):
    try:
        frame, _ = live.fetch(symbol.strip().upper(), period=period, interval=interval)
    except Exception as error:                                    # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not len(frame):
        raise HTTPException(status_code=400, detail=f"No bars for {symbol!r}.")
    return frame, f"{symbol.strip().upper()} · {interval}"


@router.get("/api/strategies")
def get_strategies(bars: int = Query(1000, ge=1, description="Series length the "
                                     "defaults should be scaled to.")) -> dict:
    """The catalogue of everything that runs without training.

    Static apart from the parameter defaults, which scale with `bars` for the
    same reason the tab's sliders do. The studies half is `pine.INDICATORS`
    itself with `pine.SIGNAL_RULES` alongside, so a study added to the engine
    appears here without this file being touched -- and its published rule
    travels with it, because a study traded on a rule nobody stated is not a
    ported study.
    """
    return {
        "rules": [
            {
                "key": key,
                "kind": RULE,
                "name": entry["name"],
                "describe": entry["describe"],
                "rule": entry["rule"],
                "params": [_param_spec(p, bars) for p in entry["params"]],
            }
            for key, entry in RULES.items()
        ],
        "studies": [
            {
                "key": indicator.key,
                "kind": STUDY,
                "name": indicator.name,
                "describe": indicator.describe,
                "rule": pine.SIGNAL_RULES[indicator.key],
                "requires": list(indicator.requires),
                "pane": indicator.pane,
                "source": indicator.source,
                "params": [],
            }
            for indicator in pine.INDICATORS.values()
        ],
        "sizing_modes": sorted(backtest.SIZING_MODES),
        "panes": {"overlay": pine.OVERLAY, "oscillator": pine.OSCILLATOR},
    }


@router.get("/api/strategies/{symbol}")
def run_strategy(
    symbol: str,
    key: str = Query(..., description="A rule key or a study key."),
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    # Rule parameters. All optional: an omitted one takes the same
    # series-scaled default the tab's slider would have started on.
    window: int | None = Query(None, ge=2),
    follow_breakout: bool = False,
    short_window: int | None = Query(None, ge=2),
    long_window: int | None = Query(None, ge=3),
    delay: int | None = Query(None, ge=1),
    # Backtest settings, matching `POST /api/jobs/agent` exactly so the two
    # kinds of agent are scored on identical terms.
    initial_money: float = Query(10_000.0, gt=0),
    max_buy: int = Query(1, ge=1, le=100),
    max_sell: int = Query(1, ge=1, le=100),
    fee_pct: float = Query(0.0, ge=0, le=100),
    slippage_pct: float = Query(0.0, ge=0, le=100),
    sizing: str = backtest.FIXED_UNITS,
    size_pct: float = Query(100.0, gt=0, le=100),
) -> dict:
    """Score one rule or study, now. No training, no queue, no write."""
    if sizing not in backtest.SIZING_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sizing {sizing!r}. Expected one of: "
                   f"{', '.join(sorted(backtest.SIZING_MODES))}.",
        )
    if key not in RULES and key not in pine.INDICATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy {key!r}. Expected a rule "
                   f"({', '.join(RULES)}) or a study "
                   f"({', '.join(pine.INDICATORS)}).",
        )

    frame, label = _bars(symbol, period, interval)
    close, dates = frame["close"], frame["date"]
    n = len(frame)

    bands = None
    if key in RULES:
        kind, name = RULE, RULES[key]["name"]
        rule_text = RULES[key]["rule"]
        source = None
        if key == "turtle":
            chosen = window if window is not None else max(2, int(math.ceil(n * 0.1)))
            settings = {"window": chosen, "follow_breakout": follow_breakout}
            signal = strategies.turtle(close, chosen, follow_breakout=follow_breakout)
            bands = strategies.turtle_bands(close, chosen)
        elif key == "crossover":
            short = short_window if short_window is not None else max(2, int(0.025 * n))
            long = long_window if long_window is not None else max(3, int(0.05 * n))
            if short >= long:
                raise HTTPException(
                    status_code=400,
                    detail=(f"Short MA ({short}) must be shorter than the long MA "
                            f"({long}), or there is nothing to cross."),
                )
            settings = {"short_window": short, "long_window": long}
            signal = strategies.moving_average(close, short, long)
            bands = strategies.moving_average_bands(close, short, long)
        else:
            chosen = delay if delay is not None else 4
            settings = {"delay": chosen}
            signal = strategies.signal_rolling(close, chosen)
    else:
        indicator = pine.INDICATORS[key]
        kind, name = STUDY, indicator.name
        rule_text = pine.SIGNAL_RULES[key]
        source = indicator.source
        # A study the series lacks the columns for is absent, not failed --
        # the same distinction `/api/studies/{symbol}` draws.
        if key not in pine.available(frame):
            missing = [c for c in indicator.requires if c not in frame.columns]
            raise HTTPException(
                status_code=400,
                detail=(f"{indicator.name} needs {', '.join(missing)}, which "
                        f"{label} does not have."),
            )
        # No parameters on purpose: the published defaults are the whole point
        # of trading a study, and tuning them on the series you are about to
        # score it on is how a backtest flatters itself.
        settings = {}
        signal = pine.signals(key, frame)
        bands = pine.bands(key, frame)

    result = backtest.run(
        close, signal, dates, initial_money=initial_money,
        max_buy=max_buy, max_sell=max_sell, fee_pct=fee_pct,
        slippage_pct=slippage_pct, sizing=sizing, size_pct=size_pct,
        # Measured from the series, not assumed from the interval -- the same
        # call the RL job body makes.
        periods_per_year=data.periods_per_year(dates),
    )

    return to_jsonable({
        "symbol": symbol.strip().upper(),
        "label": label,
        "kind": kind,
        "key": key,
        "name": name,
        "rule": rule_text,
        "source": source,
        "settings": {**settings, "sizing": sizing, "bars": n},
        "metrics": {
            "return_pct": result.roi_pct,
            "buy_hold_pct": result.buy_hold_roi_pct,
            "trades": len(result.trades),
            "win_rate_pct": result.win_rate_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "fees_paid": result.fees_paid,
            "profit": result.profit,
        },
        "dates": [str(d) for d in dates],
        "equity": list(result.equity),
        "buys": result.buys,
        "sells": result.sells,
        "final_value": result.final_value,
        "initial_money": initial_money,
        "trades": backtest.trade_table(result).to_dict(orient="records"),
        "bands": (
            {column: list(bands[column]) for column in bands.columns}
            if bands is not None else None
        ),
    })
