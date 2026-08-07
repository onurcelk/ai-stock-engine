"""Loading the repo's bundled CSVs into one consistent shape.

dataset/ holds four different layouts (Yahoo OHLCV, an oil export with a
"Price" column, a BTC sentiment feed, and two headerless FX rate files).
Everything downstream only wants a date-indexed frame with a `close`
column, so all the shape-guessing is contained here.
"""

from __future__ import annotations

import pathlib
from typing import IO

import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "dataset"

# Candidate names, most specific first, for the two columns we actually need.
# "datetime" is what yfinance names the index on intraday bars, "date" on daily.
DATE_NAMES = ("date", "datetime", "timestamp", "time")
CLOSE_NAMES = ("close", "price", "adj close", "value")

OPTIONAL_COLUMNS = ("open", "high", "low", "volume")


def list_datasets() -> list[str]:
    """Names of the bundled CSVs, nicest ones first."""
    names = sorted(p.stem for p in DATASET_DIR.glob("*.csv"))
    # GOOG-year is what every notebook in the repo defaults to.
    preferred = "GOOG-year"
    if preferred in names:
        names.remove(preferred)
        names.insert(0, preferred)
    return names


def _pick(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def normalise(raw: pd.DataFrame) -> pd.DataFrame:
    """Reduce an arbitrary price table to date + close (+ OHLCV when present).

    Shared with live.py, which feeds it a yfinance frame after reset_index().
    """
    raw = raw.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]

    date_col = _pick(list(raw.columns), DATE_NAMES)
    close_col = _pick(list(raw.columns), CLOSE_NAMES)

    # The FX files have no real header — their two columns are a title
    # string and "unnamed: 1" — so fall back to position.
    if date_col is None:
        date_col = raw.columns[0]
    if close_col is None:
        remaining = [c for c in raw.columns if c != date_col]
        if not remaining:
            raise ValueError("CSV needs at least two columns (a date and a price)")
        close_col = remaining[0]

    # A one-column file whose header is a price name (e.g. just "close") matches
    # close_col by name and date_col by position, landing on the same column.
    # Parsing prices as dates then yields nanosecond timestamps rather than an
    # error, so reject it here instead of returning convincing nonsense.
    if date_col == close_col:
        raise ValueError("CSV needs at least two columns (a date and a price)")

    column = raw[date_col]
    if pd.api.types.is_datetime64_any_dtype(column):
        dates = pd.to_datetime(column, errors="coerce")
    else:
        dates = pd.to_datetime(column, errors="coerce", format="mixed", dayfirst=True)

    # Intraday bars arrive tz-aware (America/New_York). Keeping the tz would
    # break the CSV round-trip through the cache once a DST boundary puts two
    # different UTC offsets in one column, so store naive local wall-clock.
    if isinstance(dates.dtype, pd.DatetimeTZDtype):
        dates = dates.dt.tz_localize(None)

    close = pd.to_numeric(
        raw[close_col].astype(str).str.replace(r"[,$]", "", regex=True),
        errors="coerce",
    )

    out = pd.DataFrame({"date": dates, "close": close})
    for name in OPTIONAL_COLUMNS:
        if name in raw.columns:
            out[name] = pd.to_numeric(
                raw[name].astype(str).str.replace(r"[,$]", "", regex=True),
                errors="coerce",
            )

    out = out.dropna(subset=["date", "close"]).sort_values("date")
    if out.empty:
        raise ValueError("no rows survived parsing — is this a price CSV?")
    return out.reset_index(drop=True)


def load(name: str) -> pd.DataFrame:
    """Load a bundled dataset by stem, e.g. "GOOG-year"."""
    path = DATASET_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return normalise(pd.read_csv(path))


def load_upload(handle: IO[bytes]) -> pd.DataFrame:
    """Load a user-supplied CSV from a Streamlit upload widget."""
    return normalise(pd.read_csv(handle))


def periods_per_year(dates: pd.Series) -> int:
    """How many bars this series contains per calendar year.

    Measured from the data rather than assumed, because the answer differs by
    interval *and* by market: ~252 for daily equities, ~1750 for hourly
    equities (6.5-hour sessions), ~8760 for hourly crypto that never closes.
    Anything annualised — Sharpe, volatility — needs this to be right.
    """
    if len(dates) < 3:
        return 252
    span_days = (dates.iloc[-1] - dates.iloc[0]).total_seconds() / 86_400
    if span_days <= 0:
        return 252
    return max(1, round(len(dates) / (span_days / 365.25)))


def describe(frame: pd.DataFrame) -> dict[str, object]:
    """Headline numbers for the overview panel."""
    close = frame["close"]
    first, last = close.iloc[0], close.iloc[-1]
    returns = close.pct_change().dropna()
    bars_per_year = periods_per_year(frame["date"])
    return {
        "rows": len(frame),
        "start": frame["date"].iloc[0].date(),
        "end": frame["date"].iloc[-1].date(),
        "first": first,
        "last": last,
        "change_pct": (last - first) / first * 100,
        "high": close.max(),
        "low": close.min(),
        "bars_per_year": bars_per_year,
        "volatility_pct": returns.std() * (bars_per_year ** 0.5) * 100,
    }
