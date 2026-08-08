"""Who is eligible to be ranked on a given date, decided with pre-cutoff data only.

Directive §2: equities only, and enough of them that a cross-section means
something. Three filters, in the order they bind:

1. **Index membership as of the cutoff** (`alpha.membership`), which is the
   fix for the V1 universe being a list somebody assembled today.
2. **Priceable**: bars on disk covering the cutoff. The gap between (1) and (2)
   is survivorship the download could not repair — names Yahoo has dropped —
   and it is reported per cutoff rather than absorbed silently.
3. **Tradeable at the cutoff**: enough history for the deepest feature, a
   minimum median dollar volume, and a minimum price. All three are computed
   from the truncated view, so a name that became liquid *after* the cutoff is
   not admitted on the strength of that.

The liquidity floor doubles as the denominator guard §7-8 asks for: a name that
cannot clear $3M of median daily turnover never enters the panel, so no ratio
feature is ever divided by a near-zero volume in the first place.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import membership, pitdata

# Deepest lookback in the feature set is 252 sessions (beta window); require it
# in full so no name is admitted on a back-filled feature.
MIN_HISTORY = 252
MIN_DOLLAR_VOLUME = 3_000_000.0     # median over the trailing 60 sessions
MIN_PRICE = 3.0
STALE_LIMIT = 5                      # sessions since the symbol's last print
LIQUIDITY_WINDOW = 60

NON_EQUITY = {"SPY", "QQQ", "^VIX", "XLK", "XLF", "XLV", "XLE", "XLI",
              "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"}


@dataclasses.dataclass
class Eligible:
    cutoff: pd.Timestamp
    symbols: list[str]
    sectors: pd.Series          # symbol -> GICS sector, UNKNOWN where unmapped
    diagnostics: dict

    def by_sector(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for symbol in self.symbols:
            out.setdefault(self.sectors.get(symbol, "UNKNOWN"), []).append(symbol)
        return out


def _liquidity(view: pitdata.PriceView) -> pd.Series:
    """Median daily dollar volume over the trailing window, in dollars."""
    window = min(LIQUIDITY_WINDOW, view.bars)
    close = view.close.iloc[-window:]
    volume = view.volume.reindex(columns=close.columns).iloc[-window:]
    return (close * volume).median(skipna=True)


def eligible_at(cutoff: pd.Timestamp, book: pitdata.PriceBook,
                restrict_to: set[str] | None = None) -> Eligible:
    """The ranking universe at `cutoff`. Nothing here reads a later bar."""
    view = book.view(cutoff)
    members = membership.members_at(cutoff)
    if restrict_to is not None:
        members = members & restrict_to

    on_disk = set(view.close.columns) - NON_EQUITY
    priceable = members & on_disk

    history = view.history_length()
    liquidity = _liquidity(view)
    last_price = view.close.ffill().iloc[-1]
    # Sessions since this symbol actually printed — catches a name that stopped
    # trading before the cutoff but whose column still exists.
    def _last_row(column: pd.Series) -> int:
        filled = np.flatnonzero(column.notna().to_numpy())
        return int(filled[-1]) if filled.size else -1

    staleness = (len(view.close) - 1) - view.close.apply(_last_row)

    keep, dropped = [], {"history": 0, "liquidity": 0, "price": 0, "stale": 0}
    for symbol in sorted(priceable):
        if history.get(symbol, 0) < MIN_HISTORY:
            dropped["history"] += 1
            continue
        if not np.isfinite(liquidity.get(symbol, np.nan)) or liquidity[symbol] < MIN_DOLLAR_VOLUME:
            dropped["liquidity"] += 1
            continue
        if not np.isfinite(last_price.get(symbol, np.nan)) or last_price[symbol] < MIN_PRICE:
            dropped["price"] += 1
            continue
        if staleness.get(symbol, 0) > STALE_LIMIT:
            dropped["stale"] += 1
            continue
        keep.append(symbol)

    mapping = membership.sector_map()
    sectors = pd.Series({s: mapping.get(s, "UNKNOWN") for s in keep}, dtype=object)

    diagnostics = {
        "index_members": len(members),
        "priceable": len(priceable),
        "coverage_pct": round(100 * len(priceable) / max(len(members), 1), 1),
        "eligible": len(keep),
        "dropped": dropped,
        "sectors_present": int(sectors.nunique()) if len(sectors) else 0,
        "unknown_sector": int((sectors == "UNKNOWN").sum()) if len(sectors) else 0,
    }
    return Eligible(pd.Timestamp(cutoff).normalize(), keep, sectors, diagnostics)


def watchlist_universe() -> set[str]:
    """The 22 V1 equities, for the like-for-like comparison in deliverable 6."""
    from .download import V1_WATCHLIST_EQUITIES
    return set(V1_WATCHLIST_EQUITIES)
