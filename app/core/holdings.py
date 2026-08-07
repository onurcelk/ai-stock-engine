"""Real positions: quantity and cost basis, valued at the latest price.

The rest of portfolio.py deals in hypothetical weights ("what if I put 25% in
each of these"). This module deals in what is actually owned, so it needs the
two things weights can't express: how many units, and what was paid.

Holdings live in a local JSON file that is gitignored — it is personal
financial data and does not belong in version control.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import pandas as pd

STORE = pathlib.Path(__file__).resolve().parents[1] / "holdings.json"


@dataclasses.dataclass
class Holding:
    symbol: str
    quantity: float
    unit_cost: float

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.unit_cost


@dataclasses.dataclass
class Position:
    """A holding priced at the market."""

    holding: Holding
    last_price: float | None

    @property
    def symbol(self) -> str:
        return self.holding.symbol

    @property
    def priced(self) -> bool:
        return self.last_price is not None

    @property
    def market_value(self) -> float:
        return self.holding.quantity * (self.last_price or 0.0)

    @property
    def pnl(self) -> float:
        return self.market_value - self.holding.cost_basis

    @property
    def pnl_pct(self) -> float:
        basis = self.holding.cost_basis
        return self.pnl / basis * 100 if basis else 0.0


@dataclasses.dataclass
class Valuation:
    positions: list[Position]
    unpriced: list[str]

    @property
    def priced(self) -> list[Position]:
        return [p for p in self.positions if p.priced]

    @property
    def cost_basis(self) -> float:
        """Only counts positions we could price, so totals stay comparable."""
        return sum(p.holding.cost_basis for p in self.priced)

    @property
    def market_value(self) -> float:
        return sum(p.market_value for p in self.priced)

    @property
    def pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def pnl_pct(self) -> float:
        return self.pnl / self.cost_basis * 100 if self.cost_basis else 0.0

    @property
    def winners(self) -> list[Position]:
        return sorted([p for p in self.priced if p.pnl > 0],
                      key=lambda p: p.pnl, reverse=True)

    @property
    def losers(self) -> list[Position]:
        return sorted([p for p in self.priced if p.pnl < 0], key=lambda p: p.pnl)

    @property
    def concentration_pct(self) -> float:
        """Share of the book sitting in its single largest position."""
        if not self.priced or self.market_value <= 0:
            return 0.0
        return max(p.market_value for p in self.priced) / self.market_value * 100

    def table(self) -> pd.DataFrame:
        rows = []
        total = self.market_value
        for position in self.positions:
            rows.append({
                "Symbol": position.symbol,
                "Units": round(position.holding.quantity, 4),
                "Unit cost": round(position.holding.unit_cost, 2),
                "Cost basis": round(position.holding.cost_basis, 2),
                "Last": round(position.last_price, 2) if position.priced else None,
                "Value": round(position.market_value, 2) if position.priced else None,
                "P&L": round(position.pnl, 2) if position.priced else None,
                "P&L %": round(position.pnl_pct, 2) if position.priced else None,
                "Weight %": (round(position.market_value / total * 100, 2)
                             if position.priced and total else None),
            })
        frame = pd.DataFrame(rows)
        return frame.sort_values("Value", ascending=False,
                                 na_position="last").reset_index(drop=True)


def load(path: pathlib.Path = STORE) -> list[Holding]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    holdings = []
    for item in raw.get("holdings", []):
        try:
            holdings.append(Holding(
                symbol=str(item["symbol"]).strip().upper(),
                quantity=float(item["quantity"]),
                unit_cost=float(item["unit_cost"]),
            ))
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed rows rather than losing the whole file
    return holdings


def save(holdings: list[Holding], path: pathlib.Path = STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"holdings": [dataclasses.asdict(h) for h in holdings]},
            indent=2,
        ),
        encoding="utf-8",
    )


def from_frame(frame: pd.DataFrame) -> list[Holding]:
    """Read back the editable table shown in the UI."""
    holdings = []
    for _, row in frame.iterrows():
        symbol = str(row.get("Symbol", "")).strip().upper()
        if not symbol:
            continue
        try:
            quantity = float(row["Units"])
            unit_cost = float(row["Unit cost"])
        except (KeyError, TypeError, ValueError):
            continue
        if quantity <= 0:
            continue
        holdings.append(Holding(symbol, quantity, unit_cost))
    return holdings


def editable(holdings: list[Holding]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Symbol": h.symbol, "Units": h.quantity, "Unit cost": h.unit_cost}
         for h in holdings]
        or [{"Symbol": "", "Units": 0.0, "Unit cost": 0.0}]
    )


def value(holdings: list[Holding], prices: dict[str, float]) -> Valuation:
    positions = [Position(h, prices.get(h.symbol)) for h in holdings]
    unpriced = [p.symbol for p in positions if not p.priced]
    return Valuation(positions=positions, unpriced=unpriced)


def history(holdings: list[Holding], frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Market value of the whole book over the window every holding shares.

    Returns an empty frame when the holdings have no overlapping history — a
    recent listing can shrink the common window to almost nothing, and that is
    worth showing plainly rather than silently plotting a stub.
    """
    usable = {h.symbol: frames[h.symbol] for h in holdings if h.symbol in frames}
    if not usable:
        return pd.DataFrame()

    joined = None
    for symbol, frame in usable.items():
        series = frame.set_index("date")["close"].rename(symbol)
        joined = series.to_frame() if joined is None else joined.join(series, how="inner")

    joined = joined.dropna().sort_index()
    if joined.empty:
        return pd.DataFrame()

    quantities = {h.symbol: h.quantity for h in holdings}
    values = pd.DataFrame(index=joined.index)
    for symbol in joined.columns:
        values[symbol] = joined[symbol] * quantities[symbol]
    return values


def shortest_history(frames: dict[str, pd.DataFrame]) -> tuple[str, int] | None:
    """Which holding limits the common window, and to how many bars."""
    if not frames:
        return None
    symbol = min(frames, key=lambda s: len(frames[s]))
    return symbol, len(frames[symbol])
