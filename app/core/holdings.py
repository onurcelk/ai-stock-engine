"""Real positions: quantity and cost basis, valued at the latest price.

The rest of portfolio.py deals in hypothetical weights ("what if I put 25% in
each of these"). This module deals in what is actually owned, so it needs the
two things weights can't express: how many units, and what was paid.

It also owns the *changing* of those positions. `buy()` and `sell()` are pure
functions returning a new book plus the transaction that produced it, which is
what lets the UI put a trade ticket on screen without the arithmetic living in
a Streamlit callback. Cost basis is average-cost: a buy re-averages the unit
cost (commission included, because commission is part of what you paid), a
sell leaves it alone and books the difference as realised.

Both files here are local JSON and gitignored — this is personal financial
data and does not belong in version control.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import json
import pathlib
import threading
from collections.abc import Iterator

import pandas as pd

STORE = pathlib.Path(__file__).resolve().parents[1] / "holdings.json"
LEDGER = pathlib.Path(__file__).resolve().parents[1] / "transactions.json"

#: `execute()`'s read-modify-write touches both files with no atomicity of
#: its own. Streamlit serialises this for free -- one script thread at a
#: time -- but the FastAPI layer serves requests concurrently, so two
#: overlapping trades could both `load()` the same on-disk state and the
#: second `save()` would silently discard the first. One process-wide lock
#: around the whole read-modify-write sequence is enough for a single-user
#: local app; it costs nothing when trades aren't actually concurrent.
_EXECUTE_LOCK = threading.Lock()


class WritesDisabledError(RuntimeError):
    """A trade or a book write was attempted where writes are switched off."""


#: Per-thread arming for `writes_disabled`. Thread-local rather than a module
#: flag because the API serves ordinary requests on other threads at the same
#: time: a background job disarming the whole process would also disarm the
#: trade ticket a person is using while it runs.
_NO_WRITES = threading.local()


@contextlib.contextmanager
def writes_disabled(reason: str) -> Iterator[None]:
    """Make every write in this module raise, for the current thread only.

    Held open around work that has no business moving the book — a training
    run, a backtest, anything queued and executed away from the request that
    asked for it. `backtest.run` and the reinforcement-learning agents deal in
    a simulated cash balance and never import this module, so nothing *should*
    reach here; the guard is what turns "should not" into "cannot", including
    for whatever gets added to a job body later.
    """
    previous = getattr(_NO_WRITES, "reason", None)
    _NO_WRITES.reason = reason
    try:
        yield
    finally:
        _NO_WRITES.reason = previous


def _assert_writes_allowed(what: str) -> None:
    reason = getattr(_NO_WRITES, "reason", None)
    if reason:
        raise WritesDisabledError(f"refusing to {what}: {reason}")


def _store(path: pathlib.Path | None) -> pathlib.Path:
    """Resolve the book's location at call time, not at import time.

    Every function here used to default its path to `STORE` in the signature,
    which binds the value when the module is imported. Redirecting the store —
    which is exactly what a test does — therefore had no effect, and driving
    the portfolio tab headlessly wrote a position into the real file. Reading
    the module attribute on each call is what makes monkeypatching work, and
    is the only thing standing between a test run and someone's actual
    holdings.
    """
    return STORE if path is None else path


def _ledger(path: pathlib.Path | None) -> pathlib.Path:
    return LEDGER if path is None else path


BUY, SELL = "buy", "sell"

# Enough to survive a fat-fingered decimal point without rejecting a real
# fractional-share purchase.
MIN_QUANTITY = 1e-9


def _quoted(price: float) -> str:
    """A fill price with its trailing zeros trimmed but its meaning intact.

    Four fixed places make `0.0000` of a sub-cent fill, and trimming the zeros
    off that leaves `0` — a trade confirmation quoting a price of zero for a
    trade that had one. Prices under a cent get the places they need instead.

    Trimming is applied here, to the number alone. Doing it to the assembled
    sentence — which is what this used to do, the `rstrip` binding to the whole
    implicitly concatenated string — makes the result depend on what happens to
    follow the price.
    """
    places = 4 if abs(price) >= 0.01 else 8
    return f"{price:,.{places}f}".rstrip("0").rstrip(".")


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
        # Named explicitly so an empty book still has the shape of a holdings
        # table. `pd.DataFrame([])` has no columns at all, and the sort below
        # then raises KeyError("Value") -- which made every read of an empty
        # book a crash rather than an empty answer. Found 2026-08-23 while
        # adding the book's value curve to the API; a new user with no
        # positions could not load the Portfolio endpoint at all.
        columns = ["Symbol", "Units", "Unit cost", "Cost basis", "Last",
                   "Value", "P&L", "P&L %", "Weight %"]
        frame = pd.DataFrame(rows, columns=columns)
        return frame.sort_values("Value", ascending=False,
                                 na_position="last").reset_index(drop=True)


@dataclasses.dataclass
class Transaction:
    """One executed order, and what it did to the book.

    `realised` is only meaningful on a sell — it is the part of the P&L that
    stopped being an opinion. Buys carry 0.0 rather than None so the ledger
    sums without special-casing.
    """

    at: dt.datetime
    side: str
    symbol: str
    quantity: float
    price: float
    fee: float = 0.0
    realised: float = 0.0
    note: str = ""

    @property
    def notional(self) -> float:
        return self.quantity * self.price

    @property
    def cash(self) -> float:
        """Signed cash effect: negative when buying, positive when selling."""
        return (-self.notional - self.fee if self.side == BUY
                else self.notional - self.fee)

    def describe(self) -> str:
        return (f"{self.side.upper()} {self.quantity:g} {self.symbol} "
                f"@ {_quoted(self.price)}")


def _validate(symbol: str, quantity: float, price: float, fee: float) -> str:
    symbol = str(symbol).strip().upper()
    if not symbol:
        raise ValueError("Enter a symbol.")
    if not quantity or quantity < MIN_QUANTITY:
        raise ValueError("Quantity has to be greater than zero.")
    if price <= 0:
        raise ValueError("Price has to be greater than zero.")
    if fee < 0:
        raise ValueError("Commission cannot be negative.")
    return symbol


def buy(holdings: list[Holding], symbol: str, quantity: float, price: float,
        fee: float = 0.0) -> tuple[list[Holding], Transaction]:
    """Add units, re-averaging the cost basis. Returns a new book.

    The commission goes into the basis rather than being written off, which
    is the accounting that makes "P&L" mean what a broker statement means:
    what you would clear if you sold, not what the price did.
    """
    symbol = _validate(symbol, quantity, price, fee)
    book = [dataclasses.replace(h) for h in holdings]

    for index, held in enumerate(book):
        if held.symbol == symbol:
            units = held.quantity + quantity
            spent = held.cost_basis + quantity * price + fee
            book[index] = Holding(symbol, units, spent / units)
            break
    else:
        book.append(Holding(symbol, quantity,
                            (quantity * price + fee) / quantity))

    return book, Transaction(at=dt.datetime.now(), side=BUY, symbol=symbol,
                             quantity=float(quantity), price=float(price),
                             fee=float(fee))


def sell(holdings: list[Holding], symbol: str, quantity: float, price: float,
         fee: float = 0.0) -> tuple[list[Holding], Transaction]:
    """Reduce a position at average cost, booking the realised difference.

    Selling more than is held is refused rather than clamped: a short is a
    different instrument with different risk, and quietly turning a typo into
    one would be the worst possible way to find that out.
    """
    symbol = _validate(symbol, quantity, price, fee)
    book = [dataclasses.replace(h) for h in holdings]

    position = next((h for h in book if h.symbol == symbol), None)
    if position is None:
        raise ValueError(f"You do not hold any {symbol}.")
    if quantity > position.quantity + MIN_QUANTITY:
        raise ValueError(
            f"You hold {position.quantity:g} {symbol}, so {quantity:g} cannot "
            "be sold. This app does not go short."
        )

    realised = quantity * (price - position.unit_cost) - fee
    remaining = position.quantity - quantity
    if remaining <= MIN_QUANTITY:
        book = [h for h in book if h.symbol != symbol]
    else:
        position.quantity = remaining

    return book, Transaction(at=dt.datetime.now(), side=SELL, symbol=symbol,
                             quantity=float(quantity), price=float(price),
                             fee=float(fee), realised=float(realised))


def load_ledger(path: pathlib.Path | None = None) -> list[Transaction]:
    """Every recorded trade, oldest first. A corrupt file reads as empty."""
    path = _ledger(path)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    ledger = []
    for item in raw.get("transactions", []):
        try:
            ledger.append(Transaction(
                at=dt.datetime.fromisoformat(item["at"]),
                side=str(item["side"]).lower(),
                symbol=str(item["symbol"]).strip().upper(),
                quantity=float(item["quantity"]),
                price=float(item["price"]),
                fee=float(item.get("fee", 0.0)),
                realised=float(item.get("realised", 0.0)),
                note=str(item.get("note", "")),
            ))
        except (KeyError, TypeError, ValueError):
            continue  # skip a malformed row rather than losing the ledger
    return sorted(ledger, key=lambda t: t.at)


def save_ledger(ledger: list[Transaction], path: pathlib.Path | None = None) -> None:
    _assert_writes_allowed("write the transaction ledger")
    path = _ledger(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "transactions": [
                    {**dataclasses.asdict(t), "at": t.at.isoformat(timespec="seconds")}
                    for t in ledger
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def record(transaction: Transaction, path: pathlib.Path | None = None) -> None:
    """Append one trade to the ledger on disk."""
    path = _ledger(path)
    save_ledger(load_ledger(path) + [transaction], path)


def execute(side: str, symbol: str, quantity: float, price: float,
            fee: float = 0.0, *, store: pathlib.Path | None = None,
            ledger: pathlib.Path | None = None) -> Transaction:
    """Run a trade against the saved book and persist both files.

    The one place in the app that writes a position. Everything upstream is a
    pure function, so a failed validation raises before anything touches the
    disk and the book on disk is never left half-updated.
    """
    _assert_writes_allowed(f"{side} {quantity} {symbol}")
    if side not in (BUY, SELL):
        raise ValueError(f"Unknown side {side!r}.")
    store, ledger = _store(store), _ledger(ledger)
    with _EXECUTE_LOCK:
        book, transaction = (buy if side == BUY else sell)(
            load(store), symbol, quantity, price, fee)
        save(book, store)
        record(transaction, ledger)
    return transaction


def position(holdings: list[Holding], symbol: str) -> Holding | None:
    symbol = str(symbol).strip().upper()
    return next((h for h in holdings if h.symbol == symbol), None)


def realised_total(ledger: list[Transaction]) -> float:
    return sum(t.realised for t in ledger)


def fees_total(ledger: list[Transaction]) -> float:
    return sum(t.fee for t in ledger)


def ledger_table(ledger: list[Transaction]) -> pd.DataFrame:
    """The trade history, newest first, ready for st.dataframe."""
    if not ledger:
        return pd.DataFrame(
            columns=["When", "Side", "Symbol", "Units", "Price", "Value",
                     "Commission", "Realised"]
        )
    return pd.DataFrame(
        [
            {
                "When": t.at.strftime("%Y-%m-%d %H:%M"),
                "Side": t.side.upper(),
                "Symbol": t.symbol,
                "Units": round(t.quantity, 6),
                "Price": round(t.price, 4),
                "Value": round(t.notional, 2),
                "Commission": round(t.fee, 2),
                "Realised": round(t.realised, 2) if t.side == SELL else None,
            }
            for t in reversed(ledger)
        ]
    )


def load(path: pathlib.Path | None = None) -> list[Holding]:
    path = _store(path)
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


def save(holdings: list[Holding], path: pathlib.Path | None = None) -> None:
    _assert_writes_allowed("write the holdings file")
    path = _store(path)
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
