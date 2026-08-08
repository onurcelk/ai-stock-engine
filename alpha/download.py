"""Fetch bars for the expanded universe into `alpha/cache`.

Deliberately writes to its own directory. `app/cache` is what
`validation.pit.cached_symbols()` enumerates, and that list *is* the V1 study's
universe — dropping 700 tickers into it would silently redefine the frozen
comparison this V2 work has to be measured against.

Symbols fetched:

* every ticker that was an S&P 500 constituent at any point since the download
  floor, including ones that have since been removed (the point of §2);
* the 22 equities from the V1 watchlist, so V1 and V2 can be compared on
  identical names as well as on the wider set;
* SPY (the market leg of the alpha target), QQQ, the eleven SPDR sector funds
  (cross-check only — sector returns are computed from index members, not from
  these), and ^VIX for the regime features of §10.

Run:  python -m alpha.download          # incremental, skips what it has
      python -m alpha.download --force  # re-fetch everything
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time

import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alpha import membership  # noqa: E402

CACHE_DIR = membership.CACHE_DIR
META_DIR = membership.META_DIR

# Study floor. Two extra years before the first cutoff so the deepest feature
# (a 252-day beta window on top of a 60-day momentum lookback) is warm from the
# first evaluated date rather than back-filled.
DOWNLOAD_START = "2014-01-01"

BENCHMARKS = ["SPY", "QQQ", "^VIX"]
SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]

# The V1 watchlist, equities only (§2: no crypto, no FX, no broad/commodity ETFs).
V1_WATCHLIST_EQUITIES = [
    "AAOI", "AAPL", "AMD", "AMZN", "AVAV", "CBRS", "EOSE", "GOOGL", "HIMX", "INTC",
    "META", "MSFT", "NBIS", "NVDA", "ORCL", "PL", "PLTR", "RKLB", "SNDK", "T",
    "TSLA", "UAMY",
]

BATCH = 40


def _safe(symbol: str) -> str:
    return symbol.replace("^", "_").replace("=", "_").replace("/", "_")


def path_for(symbol: str) -> pathlib.Path:
    return CACHE_DIR / f"{_safe(symbol)}.csv"


def wanted_symbols() -> dict[str, list[str]]:
    ever = membership.ever_member(pd.Timestamp(DOWNLOAD_START))
    return {
        "sp500_ever": sorted(ever),
        "watchlist": [s for s in V1_WATCHLIST_EQUITIES if s not in ever],
        "benchmarks": BENCHMARKS,
        "sector_etfs": SECTOR_ETFS,
    }


def _flatten(raw: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
    """yfinance hands back a column MultiIndex for batches and a flat one for singles."""
    if raw is None or raw.empty:
        return None
    frame = raw
    if isinstance(frame.columns, pd.MultiIndex):
        if symbol not in frame.columns.get_level_values(-1):
            return None
        frame = frame.xs(symbol, axis=1, level=-1)
    # Lowercase *after* reset_index: the date lives in the index until then, so
    # renaming columns first leaves it capitalised and unfindable.
    frame = frame.reset_index()
    frame.columns = [str(c).lower() for c in frame.columns]
    frame = frame.rename(columns={"index": "date", "datetime": "date"})
    if "date" not in frame.columns:
        return None
    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in frame.columns]
    frame = frame[keep].dropna(subset=["close"])
    if frame.empty:
        return None
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None).dt.normalize()
    return frame.sort_values("date").drop_duplicates("date").reset_index(drop=True)


def fetch_batch(symbols: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    import yfinance

    raw = yfinance.download(symbols, start=start, end=end, interval="1d",
                            auto_adjust=True, progress=False, threads=True,
                            group_by="column")
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = _flatten(raw, symbol)
        if frame is not None and len(frame) >= 30:
            out[symbol] = frame
    return out


def run(force: bool = False) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    groups = wanted_symbols()
    targets = sorted({s for group in groups.values() for s in group})

    todo = [s for s in targets if force or not path_for(s).exists()]
    print(f"universe: {len(targets)} symbols  ·  {len(todo)} to fetch", flush=True)

    end = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    got, missing, started = 0, [], time.time()
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            frames = fetch_batch(chunk, DOWNLOAD_START, end)
        except Exception as error:  # noqa: BLE001 — one bad batch is not a dead download
            print(f"  batch {i // BATCH}: {error}", flush=True)
            frames = {}
        for symbol in chunk:
            frame = frames.get(symbol)
            if frame is None:
                missing.append(symbol)
                continue
            frame.to_csv(path_for(symbol), index=False)
            got += 1
        print(f"  {min(i + BATCH, len(todo)):4d}/{len(todo)}  ok={got} "
              f"missing={len(missing)}  ({time.time() - started:.0f}s)", flush=True)

    have = sorted(p.stem for p in CACHE_DIR.glob("*.csv"))
    manifest = {
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "download_start": DOWNLOAD_START,
        "requested": len(targets),
        "on_disk": len(have),
        "unavailable": sorted(set(missing)),
        "groups": {k: len(v) for k, v in groups.items()},
        "note": ("Symbols listed under 'unavailable' were index members at some point "
                 "but Yahoo no longer serves daily bars for them (acquired, delisted, "
                 "renamed). They remain in the membership count and are reported as "
                 "coverage loss per cutoff rather than quietly dropped."),
    }
    (META_DIR / "download_manifest.json").write_text(json.dumps(manifest, indent=2),
                                                     encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    membership.refresh()
    manifest = run(force=args.force)
    print(f"\non disk: {manifest['on_disk']}  unavailable: {len(manifest['unavailable'])}")


if __name__ == "__main__":
    main()
