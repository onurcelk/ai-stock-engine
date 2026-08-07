"""Execution engine shared by every rule-based agent.

The notebooks each carried their own copy of a `buy_stock` loop that
printed to stdout and returned only the final gain. This is the same
simulation, minus the copy-paste, plus the things you need to judge a
result: an equity curve, a trade log, and a buy-and-hold benchmark.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import strategies


@dataclasses.dataclass
class Trade:
    buy_index: int
    buy_date: pd.Timestamp
    buy_price: float
    sell_index: int
    sell_date: pd.Timestamp
    sell_price: float
    units: int

    @property
    def profit(self) -> float:
        return (self.sell_price - self.buy_price) * self.units

    @property
    def return_pct(self) -> float:
        return (self.sell_price - self.buy_price) / self.buy_price * 100


@dataclasses.dataclass
class Result:
    buys: list[int]
    sells: list[int]
    trades: list[Trade]
    equity: pd.Series
    cash: float
    inventory: int
    initial_money: float
    close: pd.Series
    fees_paid: float = 0.0
    cost_pct: float = 0.0
    periods_per_year: int = 252

    @property
    def final_value(self) -> float:
        return self.cash + self.inventory * float(self.close.iloc[-1])

    @property
    def profit(self) -> float:
        return self.final_value - self.initial_money

    @property
    def roi_pct(self) -> float:
        return self.profit / self.initial_money * 100

    @property
    def buy_hold_roi_pct(self) -> float:
        """Holding from day one, charged the same round trip of costs.

        Costed on both sides so the comparison against the agent is
        like-for-like — an agent shouldn't look good purely because the
        benchmark was allowed to trade for free.
        """
        first, last = float(self.close.iloc[0]), float(self.close.iloc[-1])
        entry = first * (1 + self.cost_pct)
        exit_ = last * (1 - self.cost_pct)
        return (exit_ - entry) / entry * 100

    @property
    def exposure_pct(self) -> float:
        """Share of the run actually holding something.

        Worth reading next to the return: an agent in the market 10% of the
        time is not comparable to one that is always invested.
        """
        held = sum(1 for value in self.equity if value != self.initial_money)
        return held / len(self.equity) * 100 if len(self.equity) else 0.0

    @property
    def win_rate_pct(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.profit > 0)
        return wins / len(self.trades) * 100

    @property
    def max_drawdown_pct(self) -> float:
        """Worst peak-to-trough fall of the portfolio, as a positive %."""
        running_peak = self.equity.cummax()
        drawdown = (self.equity - running_peak) / running_peak
        return float(-drawdown.min() * 100)

    @property
    def sharpe(self) -> float:
        """Annualised Sharpe of the equity curve, risk-free rate assumed 0.

        Annualises by the bar size, not a hardcoded 252 — weekly and monthly
        bars are reachable now that data comes from a live feed.
        """
        returns = self.equity.pct_change().dropna()
        if returns.empty or returns.std() == 0:
            return 0.0
        return float(returns.mean() / returns.std() * np.sqrt(self.periods_per_year))


FIXED_UNITS = "fixed_units"
PCT_EQUITY = "pct_equity"
ALL_IN = "all_in"

SIZING_MODES = {
    FIXED_UNITS: "Fixed units",
    PCT_EQUITY: "% of equity",
    ALL_IN: "All in",
}


def run(
    close: pd.Series,
    signal: pd.Series,
    dates: pd.Series,
    initial_money: float = 10_000.0,
    max_buy: int = 1,
    max_sell: int = 1,
    fee_pct: float = 0.0,
    slippage_pct: float = 0.0,
    sizing: str = FIXED_UNITS,
    size_pct: float = 100.0,
    periods_per_year: int = 252,
) -> Result:
    """Walk the price series once, acting on each signal in turn.

    A buy is skipped when there isn't enough cash for a single unit; a
    sell is skipped when the inventory is empty. Both mirror the original
    notebooks, which simply printed a message and moved on.

    Costs: buys fill `slippage_pct` above the close and sells the same
    distance below it, and `fee_pct` of notional is charged on every fill.
    Defaults are zero so the notebooks' original numbers stay reproducible.

    Sizing decides how much to commit per signal:
      fixed_units  one `max_buy` block, as the notebooks did
      pct_equity   `size_pct` of current portfolio value
      all_in       everything available — the like-for-like comparison
                   against a fully invested buy & hold
    """
    prices = close.to_numpy(dtype=float)
    signals = signal.to_numpy(dtype=float)

    fee = fee_pct / 100.0
    slip = slippage_pct / 100.0

    cash = float(initial_money)
    inventory = 0
    fees_paid = 0.0
    buys: list[int] = []
    sells: list[int] = []
    trades: list[Trade] = []
    # FIFO queue of (index, price) so each sell can be paired with a buy.
    open_lots: list[tuple[int, float]] = []
    equity = np.empty(len(prices), dtype=float)

    for i, price in enumerate(prices):
        action = signals[i]

        if action == strategies.BUY:
            fill = price * (1 + slip)
            # Each unit costs its fill plus the fee charged on it, so budget
            # against that rather than the raw price or the last unit is
            # unaffordable at settlement.
            unit_cost = fill * (1 + fee)
            affordable = int(cash // unit_cost) if unit_cost > 0 else 0

            if sizing == FIXED_UNITS:
                units = min(affordable, max_buy)
            elif sizing == PCT_EQUITY:
                budget = (cash + inventory * price) * (size_pct / 100.0)
                units = min(affordable, int(budget // unit_cost) if unit_cost > 0 else 0)
            else:  # ALL_IN
                units = affordable

            if units >= 1:
                notional = units * fill
                charge = notional * fee
                cash -= notional + charge
                fees_paid += charge
                inventory += units
                buys.append(i)
                open_lots.append((i, fill))

        elif action == strategies.SELL and inventory > 0:
            fill = price * (1 - slip)
            # Fixed sizing sheds one block; the other modes go flat, which is
            # what "% of equity" and "all in" mean on the way out.
            units = min(inventory, max_sell) if sizing == FIXED_UNITS else inventory

            notional = units * fill
            charge = notional * fee
            inventory -= units
            cash += notional - charge
            fees_paid += charge
            sells.append(i)

            # A single sell can close several lots when sizing is not fixed.
            remaining = units
            while remaining > 0 and open_lots:
                lot_index, lot_price = open_lots[0]
                matched = remaining  # lots are whole positions in this model
                open_lots.pop(0)
                trades.append(
                    Trade(
                        buy_index=lot_index,
                        buy_date=dates.iloc[lot_index],
                        buy_price=lot_price,
                        sell_index=i,
                        sell_date=dates.iloc[i],
                        sell_price=fill,
                        units=matched,
                    )
                )
                remaining -= matched

        equity[i] = cash + inventory * price

    return Result(
        buys=buys,
        sells=sells,
        trades=trades,
        equity=pd.Series(equity, index=close.index),
        cash=cash,
        inventory=inventory,
        initial_money=float(initial_money),
        close=close,
        fees_paid=fees_paid,
        cost_pct=fee + slip,
        periods_per_year=periods_per_year,
    )


def trade_table(result: Result) -> pd.DataFrame:
    """Closed trades as a display-ready frame."""
    if not result.trades:
        return pd.DataFrame(
            columns=["Bought", "Buy price", "Sold", "Sell price", "Units", "Profit", "Return %"]
        )
    return pd.DataFrame(
        [
            {
                "Bought": t.buy_date.date(),
                "Buy price": round(t.buy_price, 2),
                "Sold": t.sell_date.date(),
                "Sell price": round(t.sell_price, 2),
                "Units": t.units,
                "Profit": round(t.profit, 2),
                "Return %": round(t.return_pct, 2),
            }
            for t in result.trades
        ]
    )
