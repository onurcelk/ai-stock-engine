"""Multi-symbol portfolios: combine several series into one basket.

Everything else in the app looks at one symbol at a time, which cannot answer
the question that actually matters for allocation — how these holdings behave
*together*. Two series that each look strong but move in lockstep are one bet,
not two, and only the correlation shows it.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import data, live

MAX_HOLDINGS = 8

# Rebalancing is expressed in bars, not calendar months, so the same setting
# means something sensible whether the series is hourly or monthly.
REBALANCE = {
    "Never (let it drift)": 0,
    "Monthly": 21,
    "Quarterly": 63,
    "Yearly": 252,
}


@dataclasses.dataclass
class Holding:
    symbol: str
    weight: float
    frame: pd.DataFrame

    @property
    def close(self) -> pd.Series:
        return self.frame["close"]


@dataclasses.dataclass
class PortfolioResult:
    dates: pd.Series
    equity: pd.Series
    contributions: pd.DataFrame  # value of each holding over time
    weights: dict[str, float]
    initial_money: float
    bars_per_year: int
    rebalanced: int

    @property
    def final_value(self) -> float:
        return float(self.equity.iloc[-1])

    @property
    def profit(self) -> float:
        return self.final_value - self.initial_money

    @property
    def roi_pct(self) -> float:
        return self.profit / self.initial_money * 100

    @property
    def volatility_pct(self) -> float:
        returns = self.equity.pct_change().dropna()
        return float(returns.std() * np.sqrt(self.bars_per_year) * 100)

    @property
    def sharpe(self) -> float:
        returns = self.equity.pct_change().dropna()
        if returns.empty or returns.std() == 0:
            return 0.0
        return float(returns.mean() / returns.std() * np.sqrt(self.bars_per_year))

    @property
    def max_drawdown_pct(self) -> float:
        peak = self.equity.cummax()
        return float(-((self.equity - peak) / peak).min() * 100)

    @property
    def final_weights(self) -> dict[str, float]:
        """Where the money actually ended up after drift."""
        last = self.contributions.iloc[-1]
        total = last.sum()
        if total == 0:
            return {k: 0.0 for k in self.contributions.columns}
        return {k: float(v / total * 100) for k, v in last.items()}


def fetch_many(
    symbols: list[str],
    period: str = "5y",
    interval: str = "1d",
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Load several symbols, reporting failures instead of raising.

    Returns (frames, errors) so the UI can render what worked and explain
    what didn't — one bad ticker shouldn't lose the whole portfolio.
    """
    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    for symbol in symbols:
        symbol = symbol.strip().upper()
        if not symbol or symbol in frames:
            continue
        try:
            frame, _ = live.fetch(symbol, period=period, interval=interval)
            frames[symbol] = frame
        except live.FetchError as error:
            errors[symbol] = str(error)
    return frames, errors


def align(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Join holdings on their common timestamps.

    Different listings have different histories and holidays, so the basket is
    only defined where every member traded. An inner join keeps that honest
    rather than forward-filling prices that never existed.
    """
    if not frames:
        return pd.DataFrame()
    joined = None
    for symbol, frame in frames.items():
        series = frame.set_index("date")["close"].rename(symbol)
        joined = series.to_frame() if joined is None else joined.join(series, how="inner")
    return joined.dropna().sort_index()


def normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, w) for w in weights.values())
    if total <= 0:
        equal = 100.0 / len(weights) if weights else 0.0
        return {k: equal for k in weights}
    return {k: max(0.0, w) / total * 100 for k, w in weights.items()}


def build(
    prices: pd.DataFrame,
    weights: dict[str, float],
    initial_money: float = 10_000.0,
    rebalance_every: int = 0,
) -> PortfolioResult:
    """Buy the basket on day one and hold, optionally rebalancing.

    Without rebalancing the winners grow into a larger share of the book —
    `final_weights` shows how far it drifted from the target.
    """
    weights = normalise_weights(weights)
    symbols = list(prices.columns)
    bars = len(prices)

    values = np.zeros((bars, len(symbols)), dtype=float)
    # Fractional units: this models an allocation, not a share-count backtest.
    units = np.array([
        initial_money * (weights[s] / 100) / float(prices[s].iloc[0]) for s in symbols
    ])
    values[0] = units * prices.iloc[0].to_numpy(dtype=float)
    rebalances = 0

    for i in range(1, bars):
        row = prices.iloc[i].to_numpy(dtype=float)
        values[i] = units * row
        if rebalance_every and i % rebalance_every == 0:
            total = values[i].sum()
            units = np.array([
                total * (weights[s] / 100) / row[j] for j, s in enumerate(symbols)
            ])
            values[i] = units * row
            rebalances += 1

    contributions = pd.DataFrame(values, index=prices.index, columns=symbols)
    equity = contributions.sum(axis=1)
    dates = pd.Series(prices.index, name="date")

    return PortfolioResult(
        dates=dates,
        equity=equity,
        contributions=contributions,
        weights=weights,
        initial_money=float(initial_money),
        bars_per_year=data.periods_per_year(dates),
        rebalanced=rebalances,
    )


def correlations(prices: pd.DataFrame) -> pd.DataFrame:
    """Correlation of returns, not prices — price correlation mostly measures trend."""
    return prices.pct_change().dropna().corr()


def per_symbol_stats(prices: pd.DataFrame, bars_per_year: int) -> pd.DataFrame:
    """Standalone behaviour of each holding, for ranking and comparison."""
    rows = []
    for symbol in prices.columns:
        series = prices[symbol]
        returns = series.pct_change().dropna()
        first, last = float(series.iloc[0]), float(series.iloc[-1])
        peak = series.cummax()
        drawdown = float(-((series - peak) / peak).min() * 100)
        sharpe = (float(returns.mean() / returns.std() * np.sqrt(bars_per_year))
                  if returns.std() else 0.0)
        rows.append({
            "Symbol": symbol,
            "Return %": round((last - first) / first * 100, 2),
            "Volatility %": round(float(returns.std() * np.sqrt(bars_per_year) * 100), 1),
            "Sharpe": round(sharpe, 2),
            "Max DD %": round(drawdown, 1),
            "Last": round(last, 2),
        })
    return pd.DataFrame(rows).sort_values("Return %", ascending=False).reset_index(drop=True)


def diversification_note(corr: pd.DataFrame) -> tuple[float, str]:
    """The average off-diagonal correlation, and what it implies."""
    if len(corr) < 2:
        return 0.0, "A single holding has nothing to diversify against."
    mask = ~np.eye(len(corr), dtype=bool)
    average = float(corr.to_numpy()[mask].mean())
    if average > 0.8:
        verdict = ("These move almost identically — this is close to one position "
                   "held in several names, not a diversified book.")
    elif average > 0.5:
        verdict = "Substantially correlated; expect them to fall together in a selloff."
    elif average > 0.2:
        verdict = "Moderately correlated — some genuine diversification."
    else:
        verdict = "Largely independent, which is what diversification is supposed to buy."
    return average, verdict
