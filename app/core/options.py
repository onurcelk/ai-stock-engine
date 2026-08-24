"""The live options chain, as information and never as a backtest.

**Read `reports/OPTIONS1_ADMISSIBILITY.md` §3 before extending this module.**
It records, from a direct check rather than an assumption, that no free source
this programme may use serves options data *point-in-time*. yfinance returns
the chain as it stands right now; once a contract expires it is retrievable
from nowhere free. An expired option's mid-price and implied vol do not merely
lack a timestamp — they cease to exist.

So the honest scope, and the only scope this module has, is: **describe what is
quoted at this moment.** Everything downstream of that — option P&L, margin,
assignment probability from a fitted model, tail risk, a premium-selling
backtest — needs a *history* of strikes and implied vols, which is exactly what
does not exist. Building any of it on today's snapshot silently converts it
into a look-ahead study, which `CLAUDE.md` §2.1 forbids at the data door, not
merely at the feature level.

Three consequences, enforced here rather than left to a reader's discipline:

- **Nothing in this module writes.** No ledger, no book, no saved run. A
  premium screen is not a forecast and must never be recordable as one; the
  forecast ledger's value is that every row was a deliberate prospective call
  on a series that can be replayed, and none of that is true of this.
- **Every payload carries `WARNING`.** Not decoration around the numbers — part
  of them, on the same principle as `research_view`'s `study_warning`. A yield
  column with no caveat attached is read as a backtested return, which it is
  not and can never be made into.
- **`static_yield` is arithmetic, not a return.** It is the quoted premium over
  the collateral. It assumes the option expires worthless — the single
  assumption that makes premium selling look free — and the `static_` prefix
  keeps that visible in every column name it touches.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import pandas as pd

from .live import FetchError, UnknownSymbol

#: Attached to every payload this module produces. Stated once, carried
#: verbatim, never paraphrased at a call site.
WARNING = (
    "Live quoted snapshot. No historical options data exists at any free "
    "source, so nothing here is or can be backtested: these are today's "
    "quotes, not a measured strategy. Static yields assume the option expires "
    "worthless and ignore assignment, early exercise, margin and tail risk."
)

CASH_SECURED_PUT = "cash_secured_put"
COVERED_CALL = "covered_call"

#: A quote with no bid is not a price you can sell at.
MIN_BID = 0.01


@dataclasses.dataclass(frozen=True)
class Chain:
    """One expiry's calls and puts, as quoted when it was asked for."""

    symbol: str
    expiry: dt.date
    spot: float
    fetched_at: dt.datetime
    calls: pd.DataFrame
    puts: pd.DataFrame


def _ticker(symbol: str):
    try:
        import yfinance as yf
    except ImportError as exc:                                  # pragma: no cover
        raise FetchError(
            "yfinance is not installed — run: pip install yfinance") from exc
    return yf.Ticker(symbol.strip().upper())


def expiries(symbol: str, *, ticker=None) -> list[dt.date]:
    """Expiries currently listed. Empty is a fact, not an error.

    `ticker` is injectable so tests drive the whole module offline; it is the
    only seam through which this file reaches the network.
    """
    handle = ticker if ticker is not None else _ticker(symbol)
    try:
        listed = handle.options or ()
    except Exception as exc:                                    # noqa: BLE001
        raise FetchError(f"Could not read expiries for {symbol}: {exc}") from exc
    return [pd.Timestamp(value).date() for value in listed]


def _spot(handle, symbol: str) -> float:
    """Last traded price, from whichever of yfinance's surfaces answers.

    A screen with no spot is not a screen — every moneyness and every yield
    below divides by it — so failing to find one raises rather than defaulting.
    """
    readers = (
        lambda: handle.fast_info["last_price"],
        lambda: handle.info["regularMarketPrice"],
        lambda: handle.history(period="1d")["Close"].iloc[-1],
    )
    for reader in readers:
        try:
            price = float(reader())
        except Exception:                                       # noqa: BLE001
            continue
        if np.isfinite(price) and price > 0:
            return price
    raise FetchError(f"No spot price available for {symbol}")


def chain(symbol: str, expiry: dt.date | str | None = None, *,
          ticker=None) -> Chain:
    """One expiry's chain, as quoted now. Defaults to the nearest listed."""
    symbol = symbol.strip().upper()
    handle = ticker if ticker is not None else _ticker(symbol)

    listed = expiries(symbol, ticker=handle)
    if not listed:
        raise UnknownSymbol(f"{symbol} has no listed options")

    wanted = listed[0] if expiry is None else pd.Timestamp(expiry).date()
    if wanted not in listed:
        raise FetchError(
            f"{symbol} has no {wanted} expiry. Listed: "
            + ", ".join(str(value) for value in listed[:8]))

    try:
        quoted = handle.option_chain(str(wanted))
    except Exception as exc:                                    # noqa: BLE001
        raise FetchError(f"Could not read the {wanted} chain: {exc}") from exc

    return Chain(
        symbol=symbol, expiry=wanted, spot=_spot(handle, symbol),
        fetched_at=dt.datetime.now(dt.timezone.utc),
        calls=pd.DataFrame(quoted.calls).copy(),
        puts=pd.DataFrame(quoted.puts).copy(),
    )


def _mid(rows: pd.DataFrame) -> pd.Series:
    """Mid of the quoted spread, falling back to the last trade.

    `lastPrice` can be hours or days stale on an illiquid strike, so it is the
    fallback rather than the default, and `is_stale` below says when a row has
    no live bid behind it.
    """
    bid = pd.to_numeric(rows.get("bid"), errors="coerce")
    ask = pd.to_numeric(rows.get("ask"), errors="coerce")
    last = pd.to_numeric(rows.get("lastPrice"), errors="coerce")
    quoted = (bid + ask) / 2.0
    return quoted.where(bid.notna() & ask.notna() & (bid > 0) & (ask > 0), last)


def premium_screen(chain_: Chain, *, kind: str = CASH_SECURED_PUT,
                   min_open_interest: int = 0,
                   out_of_the_money_only: bool = True,
                   today: dt.date | None = None) -> pd.DataFrame:
    """Every strike of one side, with what selling it would collect today.

    Sorted by static yield, which is a ranking of *quotes* and not a ranking of
    strategies. The columns that would make it the latter — a realised return,
    a hit rate, a drawdown — are absent because they cannot be computed from a
    snapshot, and leaving them out is the point rather than an omission.

    `out_of_the_money_only` defaults to True, and the reason is worth stating
    because it is a default that changes what the top of the table says.
    Ranking purely by yield puts deep in-the-money strikes first — an in-the-
    money put quotes an enormous premium because it is nearly certain to be
    assigned, and on expiry day that annualises into the thousands of percent.
    That is arithmetic doing what it was told, but selling an in-the-money put
    is a synthetic long position, not premium harvesting, and putting it at the
    head of a premium screen would be answering a question nobody asked.

    It is a visible switch rather than a silent filter: pass False and every
    strike comes back, `cushion` says which side of the money each one is on,
    and nothing has been hidden.
    """
    if kind not in (CASH_SECURED_PUT, COVERED_CALL):
        raise ValueError(f"unknown screen {kind!r}")

    rows = (chain_.puts if kind == CASH_SECURED_PUT else chain_.calls).copy()
    if rows.empty:
        return rows

    strike = pd.to_numeric(rows["strike"], errors="coerce")
    bid = pd.to_numeric(rows.get("bid"), errors="coerce")
    premium = _mid(rows)

    days = days_to_expiry(chain_, today=today)
    # A zero-day option annualises to infinity. Expiry day is priced as one
    # day, which understates the yield rather than inventing one.
    years = max(days, 1) / 365.0

    # Collateral is what the position actually ties up: the strike for a
    # cash-secured put, the shares for a covered call.
    collateral = (strike if kind == CASH_SECURED_PUT
                  else pd.Series(chain_.spot, index=rows.index))

    out = pd.DataFrame({
        "contract": rows.get("contractSymbol"),
        "strike": strike,
        "bid": bid,
        "ask": pd.to_numeric(rows.get("ask"), errors="coerce"),
        "premium": premium,
        "implied_volatility": pd.to_numeric(
            rows.get("impliedVolatility"), errors="coerce"),
        "open_interest": pd.to_numeric(
            rows.get("openInterest"), errors="coerce").fillna(0.0),
        "volume": pd.to_numeric(rows.get("volume"), errors="coerce"),
    })

    out["days_to_expiry"] = days
    out["moneyness"] = strike / chain_.spot - 1.0
    out["static_yield"] = premium / collateral.replace(0.0, np.nan)
    out["static_yield_annualised"] = out["static_yield"] / years
    # How far the underlying would have to move for this to be assigned. Not a
    # probability — turning it into one needs a model this module will not
    # pretend to have.
    out["cushion"] = (out["moneyness"] if kind == COVERED_CALL
                      else -out["moneyness"])
    out["is_stale"] = ~(bid.notna() & (bid >= MIN_BID))

    out = out[out["premium"].notna() & (out["premium"] > 0)]
    if out_of_the_money_only:
        out = out[out["cushion"] > 0]
    if min_open_interest:
        out = out[out["open_interest"] >= min_open_interest]

    return out.sort_values("static_yield_annualised",
                           ascending=False).reset_index(drop=True)


def days_to_expiry(chain_: Chain, *, today: dt.date | None = None) -> int:
    """Calendar days from today to the expiry, floored at zero."""
    today = today or dt.date.today()
    return max((chain_.expiry - today).days, 0)


def screen_payload(chain_: Chain, table: pd.DataFrame, kind: str, *,
                   out_of_the_money_only: bool = True,
                   today: dt.date | None = None) -> dict:
    """The screen as JSON, warning included. Never without it."""
    return {
        "symbol": chain_.symbol,
        "kind": kind,
        "expiry": chain_.expiry.isoformat(),
        "spot": chain_.spot,
        "fetched_at": chain_.fetched_at.isoformat(),
        "days_to_expiry": days_to_expiry(chain_, today=today),
        "out_of_the_money_only": out_of_the_money_only,
        "rows": table.to_dict(orient="records"),
        "backtestable": False,
        "WARNING": WARNING,
    }
