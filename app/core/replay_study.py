"""Historical point-in-time replay — fast evidence, never production evidence.

The live prospective ledger accumulates one cutoff per trading day, and the
Phase 7 gate needs fifty independent ones.  At the binding `1w` horizon that is
roughly forty-nine weeks of waiting, and Phase 9 established that no dataset
shortens it.  What Phase 9 established is about **production validation**.  It
says nothing about *model development*, which needs to know whether a change
helps long before it needs to know whether a change may hold production weight.

This module supplies the first without pretending to supply the second.

**What it does.**  Pick a historical cutoff `T`, hand the engine a price history
that stops at `T`, freeze what it says, then read the bar `bars_ahead` later and
score the frozen call.  Repeat across a grid of cutoffs and a universe of
symbols.  Nothing here is new machinery: the truncation is `replay`'s, the
freezing is Phase 1's, the scoring is Phase 2's, and the independence rule is
Phase 7's.  What is new is the *sweep* — a cutoff generator, and a driver that
walks it.

**Why these are `RETROSPECTIVE_REPLAY` and can never be promoted evidence.**
Exactly the reasons RR-2 gave, unchanged and not weakened by doing more of it:
the price history is back-adjusted for corporate actions that post-date `T`, the
symbol universe is the one someone watches today, the intraday depth is whatever
survives now, and — the one no code can fix — whoever runs the study already
knows what the market did.  A study that can be re-run with a different universe
until it flatters is a diagnostic.  The separation is physical: these rows live
in their own database file under a CHECK constraint that admits nothing else,
`promotion.evidence_for` drops them before measuring, and
`research_view.n_independent_cutoffs` ignores them.

**The intended division of labour**, stated once so it is not re-litigated:

    historical replay  ->  fast evidence for model development
    prospective ledger ->  final independent production validation

A change that looks good here has earned a prospective test.  It has not earned
production weight, and this module must never be cited as though it had.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import numpy as np
import pandas as pd

from . import forecast_ledger, indicators, model_registry, outcome_ledger, ultimate


#: Study rows never share a file with the missed-session replays of RR-2.  Both
#: are `RETROSPECTIVE_REPLAY` and both are diagnostics, but they answer
#: different questions and one is regenerable on demand while the other tracks
#: a specific gap in collection.  Keeping them apart also keeps each file's
#: `outcomes` table joined to exactly the forecasts it scores.
DEFAULT_STUDY_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "replay_study.sqlite3")

#: One JSON record per sweep — which cutoffs, which symbols, what failed.  A
#: study is regenerable, so this is not evidence; it is what lets a later reader
#: tell whether two runs asked the same question.
DEFAULT_LOG_DIR = pathlib.Path(__file__).resolve().parents[1] / "study_logs"

#: The five-week horizon, defined **here rather than in `ultimate.HORIZONS`**.
#:
#: This is the whole reason the study can exist without touching the incumbent.
#: `ultimate.evaluate` already accepts a `horizons=` argument, and a `Horizon`
#: is an inert description of which bars to read — so a new one composes the
#: frozen engine rather than modifying it.  Adding `5w` to `ultimate.HORIZONS`
#: would change `app/core/ultimate.py`, and its version is the sha256 of that
#: file: every live forecast frozen afterwards would carry a different engine
#: identity than the ones already accumulated.
#:
#: 25 trading days is five weeks.  The mapping is a written table for the same
#: reason `ultimate.HORIZONS` is one — a week is five sessions, not seven days.
FIVE_WEEKS = ultimate.Horizon(
    "5w", "5 weeks", "1d", 25, "10y", {"1d": 25, "1wk": 5}, min_bars=300)

#: Horizons a study may be run at.  The three daily-interval ones are reused
#: from the production engine unchanged, so a `1d` or `1w` study row is directly
#: comparable with a `1d` or `1w` row in the prospective ledger.
#:
#: `4h` is deliberately absent.  Yahoo serves roughly two years of hourly bars,
#: so a historical grid at that horizon reaches back almost nowhere; and PIT-1
#: measured the 4-hour after-close case **inverted** at p = 0.009, which is a
#: finding to respect rather than re-open with a bigger sample.
STUDY_HORIZONS: dict[str, ultimate.Horizon] = {
    "1d": ultimate.HORIZON_BY_KEY["1d"],
    "1w": ultimate.HORIZON_BY_KEY["1w"],
    "5w": FIVE_WEEKS,
}

#: The horizon a study runs at when the caller does not say.  Five weeks is far
#: enough out that a daily-bar engine is making a real claim, and short enough
#: that ten years of history still yields ~100 non-overlapping draws.
DEFAULT_HORIZON = "5w"

STUDY_SOURCE = "historical_pit_replay"


class StudyError(RuntimeError):
    """A study could not be constructed or run as specified."""


# ------------------------------------------------------------------ horizons


def horizon_for(key: str) -> ultimate.Horizon:
    if key not in STUDY_HORIZONS:
        raise StudyError(
            f"unknown study horizon {key!r}; available: "
            + ", ".join(sorted(STUDY_HORIZONS)))
    return STUDY_HORIZONS[key]


def min_history_bars(horizon: ultimate.Horizon, interval: str | None = None) -> int:
    """Bars a cutoff needs behind it before the engine will read the horizon.

    Derived from `ultimate.evaluate_frame`'s own admission test rather than
    guessed, so a cutoff this function accepts is one the engine will not
    decline as too short.  Reading the constants is not modifying them.
    """
    bars = horizon.bars_on(interval or horizon.interval) or horizon.bars
    return max(horizon.min_bars,
               indicators.WARMUP + bars + ultimate.MIN_SAMPLES * 2)


# ------------------------------------------------------------------- cutoffs


def historical_cutoffs(
    dates: Sequence[pd.Timestamp] | pd.Series,
    *,
    bars_ahead: int,
    count: int,
    stride_bars: int | None = None,
    min_history: int,
) -> list[pd.Timestamp]:
    """A grid of historical cutoffs, newest first in construction, returned old to new.

    Two constraints shape every cutoff, and both are structural rather than
    stylistic:

    - **It must have a future to be scored against.**  A cutoff within
      `bars_ahead` of the end of the series has no maturity bar, so it would
      freeze a forecast that can never resolve.  Those are excluded here rather
      than left for the scorer to skip, because an unscoreable row still looks
      like coverage on a count of frozen forecasts.
    - **It must have a past the engine will read.**  `min_history` comes from
      `ultimate.evaluate_frame`'s own admission test.

    `stride_bars` defaults to `bars_ahead`, which makes consecutive windows
    *touch but not overlap* — every cutoff is then an independent draw under
    `promotion.independent_cutoffs`, rather than being collapsed by it.  A
    smaller stride is allowed and yields more rows, but those rows resolve
    against overlapping price paths: they are more observations, not more
    draws, and the study reports both numbers so the difference stays visible.
    """
    if bars_ahead < 1:
        raise StudyError("bars_ahead must be at least one bar")
    if count < 1:
        raise StudyError("a study needs at least one cutoff")
    stride = bars_ahead if stride_bars is None else int(stride_bars)
    if stride < 1:
        raise StudyError("stride_bars must be at least one bar")

    stamps = pd.to_datetime(pd.Series(list(dates)), errors="raise", utc=True)
    total = len(stamps)
    # The newest bar that still has `bars_ahead` bars after it.
    newest = total - 1 - bars_ahead
    if newest < min_history:
        return []

    positions: list[int] = []
    position = newest
    while position >= min_history and len(positions) < count:
        positions.append(position)
        position -= stride
    return [stamps.iloc[index] for index in sorted(positions)]


def shared_calendar(
    frames: dict[str, pd.DataFrame],
    *,
    bars_ahead: int,
    count: int,
    stride_bars: int | None = None,
    min_history: int,
    reference: str | None = None,
) -> list[pd.Timestamp]:
    """One cutoff grid for the whole universe, built from a reference symbol.

    Symbols read on the same day are one draw — that is the counting rule the
    whole programme runs on — so the study generates *dates*, not
    symbol-specific cutoffs, and every symbol is asked the same question on the
    same day.  A grid built per symbol would scatter cutoffs across adjacent
    sessions whose windows overlap; `promotion.independent_cutoffs` would
    collapse them correctly, but the study would have paid for observations it
    could not count.

    The grid is laid on the universe's **majority calendar** — the dates at
    least half the symbols traded — rather than on any one symbol's bars.  On a
    mixed universe that distinction decides whether the study's cutoffs are
    independent at all, and two simpler rules were tried and both fail:

    - *The symbol with the deepest history* picks `BTC-USD`, which trades seven
      days a week.  Its grid is spaced 25 **calendar** days, so consecutive
      equity windows — 25 *trading* days long — overlap, and
      `promotion.independent_cutoffs` correctly collapses most of them.  The
      sweep would pay for cutoffs it could not count.
    - *The most-shared calendar* picks whichever symbol listed most recently: a
      hundred-bar series is trivially contained in every longer one, so it
      scores perfect containment on almost no dates.

    A majority calendar has neither failure mode, is derived from the data
    rather than from a hardcoded notion of what an equity is, and degenerates
    correctly: on an all-crypto universe it is every day, which is right.
    Symbols that did not trade on a chosen grid date simply skip it — see
    `run_study`.
    """
    if not frames:
        return []
    if reference is not None:
        return historical_cutoffs(
            frames[reference]["date"], bars_ahead=bars_ahead, count=count,
            stride_bars=stride_bars, min_history=min_history)
    return historical_cutoffs(
        majority_calendar(frames), bars_ahead=bars_ahead, count=count,
        stride_bars=stride_bars, min_history=min_history)


def majority_calendar(frames: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    """Dates at least half the universe traded, ascending.

    The market calendar this universe actually runs on, read off the bars.  A
    bar exists exactly when a symbol traded, so counting them answers the
    calendar question without a holiday table and without ever being wrong
    about a half-day or an unscheduled close.

    "At least half" rather than "all": intersecting every symbol would let one
    recently-listed ticker shorten the calendar to its own lifetime, and
    intersecting none would let a seven-day-a-week series lengthen it to
    weekends.
    """
    if not frames:
        return []
    counts: dict[pd.Timestamp, int] = {}
    for frame in frames.values():
        for stamp in set(pd.to_datetime(frame["date"], errors="raise", utc=True)):
            counts[stamp] = counts.get(stamp, 0) + 1
    needed = (len(frames) + 1) // 2
    return sorted(stamp for stamp, seen in counts.items() if seen >= needed)


# --------------------------------------------------------------- provenance


def study_provenance(
    *, study_id: str, session: str, reconstructed_at: str,
    horizon_key: str, bars_ahead: int, stride_bars: int,
) -> dict[str, Any]:
    """The `metadata["replay"]` block every study row carries.

    `reason` and the two timestamps are what `forecast_ledger.assert_replay`
    checks.  The `study` block is what distinguishes a swept historical row
    from an RR-2 missed-session recovery, so a reader of a single record can
    tell which loop produced it without consulting the file it came from.
    """
    return {
        "reconstructed_at": reconstructed_at,
        "session": session,
        "reason": "historical point-in-time replay study",
        "study": {
            "study_id": study_id,
            "source": STUDY_SOURCE,
            "horizon": horizon_key,
            "bars_ahead": int(bars_ahead),
            "stride_bars": int(stride_bars),
        },
    }


def assert_study(records: Iterable[forecast_ledger.ForecastRecord]) -> None:
    """Everything `assert_replay` checks, plus the study block.

    Layered rather than replacing: the reconstruction provenance is the part
    that keeps a replay from reading as a live forecast, and that check is
    RR-2's and stays exactly as it was.
    """
    pending = list(records)
    forecast_ledger.assert_replay(pending)
    for record in pending:
        study = (record.metadata.get("replay") or {}).get("study") or {}
        if study.get("source") != STUDY_SOURCE:
            raise forecast_ledger.ForecastIntegrityError(
                f"{record.forecast_id} is not a historical replay study row")
        if not study.get("study_id"):
            raise forecast_ledger.ForecastIntegrityError(
                f"{record.forecast_id} carries no study identity")
        if int(study.get("bars_ahead", 0)) != int(record.metadata["bars_used"]):
            raise forecast_ledger.ForecastIntegrityError(
                f"{record.forecast_id} declares a study horizon of "
                f"{study.get('bars_ahead')} bars but froze "
                f"{record.metadata['bars_used']}")


# ------------------------------------------------------------------ fetching


class MemoisedFetcher:
    """One download per `(symbol, period, interval)`, reused across cutoffs.

    A study runs the engine at a hundred cutoffs per symbol against the same
    underlying history.  Re-fetching for each would be a hundred identical
    downloads, and — worse — a hundred chances for the series to change
    underneath the study, which would make two cutoffs incomparable for a
    reason that has nothing to do with the market.  Fetching once makes the
    whole sweep read one fixed history.
    """

    def __init__(self, source: Callable[..., tuple[pd.DataFrame, Any]] | None = None):
        self._source = source
        self._cache: dict[tuple[str, str, str], tuple[pd.DataFrame, Any]] = {}

    def _resolve(self):
        if self._source is None:
            from . import live
            self._source = live.fetch
        return self._source

    def __call__(self, symbol: str, *, period: str, interval: str,
                 force: bool = False):
        key = (symbol.upper(), period, interval)
        if key not in self._cache:
            frame, entry = self._resolve()(
                symbol, period=period, interval=interval, force=force)
            self._cache[key] = (frame.reset_index(drop=True), entry)
        frame, entry = self._cache[key]
        return frame.copy(deep=True), entry

    def frame(self, symbol: str, *, period: str, interval: str) -> pd.DataFrame:
        return self(symbol, period=period, interval=interval)[0]


# ------------------------------------------------------------------ the sweep


@dataclasses.dataclass(frozen=True)
class SymbolResult:
    symbol: str
    status: str                 # replayed | skipped | error
    cutoffs: int = 0
    records: int = 0
    detail: str | None = None

    @property
    def is_failure(self) -> bool:
        return self.status == "error"


@dataclasses.dataclass(frozen=True)
class StudyRun:
    study_id: str
    started_at: str
    finished_at: str
    horizon: str
    bars_ahead: int
    stride_bars: int
    cutoffs: tuple[str, ...]
    results: tuple[SymbolResult, ...]
    frozen_records: int
    path: str

    @property
    def failures(self) -> tuple[SymbolResult, ...]:
        return tuple(r for r in self.results if r.is_failure)

    def summary(self) -> str:
        return (f"{self.frozen_records} study record(s) at {self.horizon} "
                f"across {len(self.cutoffs)} cutoff(s) and "
                f"{sum(1 for r in self.results if r.records)} symbol(s)")

    def as_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "horizon": self.horizon,
            "bars_ahead": self.bars_ahead,
            "stride_bars": self.stride_bars,
            "cutoffs": list(self.cutoffs),
            "frozen_records": self.frozen_records,
            "path": self.path,
            "results": [dataclasses.asdict(r) for r in self.results],
        }


def _study_id(horizon: str, cutoffs: Sequence[pd.Timestamp], symbols: Sequence[str]) -> str:
    payload = {
        "horizon": horizon,
        "cutoffs": [forecast_ledger._utc_iso(c) for c in cutoffs],
        "symbols": sorted({s.upper() for s in symbols}),
    }
    return "study_" + forecast_ledger._digest(payload)[:16]


def run_study(
    symbols: Sequence[str],
    *,
    horizon: str = DEFAULT_HORIZON,
    count: int = 60,
    stride_bars: int | None = None,
    path: str | pathlib.Path | None = None,
    fetcher: Callable[..., tuple[pd.DataFrame, Any]] | None = None,
    now: dt.datetime | pd.Timestamp | None = None,
    include_agents: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
    log_dir: str | pathlib.Path | None = None,
) -> StudyRun:
    """Freeze the incumbent at every grid cutoff, for every symbol.

    Writes forecasts only.  Nothing here reads an outcome, computes a return,
    or looks at a bar past a cutoff — scoring is `score_study`, a separate pass
    over already-frozen rows, which is Phase 2's two-process separation applied
    to the study exactly as it applies to the live ledger.

    One symbol failing never stops the sweep, for the same reason it does not
    stop collection: one delisted ticker must not cost the others their grid.
    """
    spec = horizon_for(horizon)
    ledger = forecast_ledger.ReplayLedger(pathlib.Path(path or DEFAULT_STUDY_PATH))
    memo = fetcher if isinstance(fetcher, MemoisedFetcher) else MemoisedFetcher(fetcher)
    started = dt.datetime.now(dt.timezone.utc)
    reconstructed_at = forecast_ledger._utc_iso(
        now or dt.datetime.now(dt.timezone.utc))
    names = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))

    frames: dict[str, pd.DataFrame] = {}
    results: list[SymbolResult] = []
    for symbol in names:
        try:
            frames[symbol] = memo.frame(
                symbol, period=spec.period, interval=spec.interval)
        except Exception as error:                              # noqa: BLE001
            results.append(SymbolResult(
                symbol=symbol, status="error",
                detail=f"{type(error).__name__}: {error}"))

    stride = spec.bars if stride_bars is None else int(stride_bars)
    grid = shared_calendar(
        frames, bars_ahead=spec.bars, count=count, stride_bars=stride,
        min_history=min_history_bars(spec))
    if not grid:
        raise StudyError(
            f"no historical cutoff at {horizon} has both "
            f"{min_history_bars(spec)} bars of history behind it and "
            f"{spec.bars} bars ahead of it in the available series")

    study_id = _study_id(horizon, grid, list(frames))
    stamps = {forecast_ledger._utc_iso(cutoff) for cutoff in grid}
    frozen_total = 0

    for index, symbol in enumerate(sorted(frames)):
        if on_progress:
            on_progress(index, len(frames), symbol)
        # A grid date the symbol did not trade is skipped, never snapped to a
        # neighbouring bar: truncating at a non-bar date would leave the frame
        # ending earlier than the declared session, and `assert_replay` would
        # correctly refuse the mismatch.
        own = set(pd.to_datetime(frames[symbol]["date"], errors="raise", utc=True))
        usable = [cutoff for cutoff in grid if cutoff in own]
        written = 0
        try:
            for cutoff in usable:
                session = forecast_ledger._utc_iso(cutoff)
                _, records = forecast_ledger.generate_incumbent_records(
                    symbol,
                    include_agents=include_agents,
                    horizons=[spec],
                    fetcher=_truncated(memo, cutoff),
                    cutoff_at=cutoff,
                    generated_at=reconstructed_at,
                    record_class=forecast_ledger.RETROSPECTIVE_REPLAY,
                    replay=study_provenance(
                        study_id=study_id, session=session,
                        reconstructed_at=reconstructed_at,
                        horizon_key=horizon, bars_ahead=spec.bars,
                        stride_bars=stride),
                )
                fresh = [r for r in records if not ledger.has_frozen_input(
                    symbol=r.symbol, horizon=r.horizon,
                    input_fingerprint=r.input_fingerprint)]
                assert_study(fresh)
                ledger.insert_many(fresh)
                written += len(fresh)
        except Exception as error:                              # noqa: BLE001
            results.append(SymbolResult(
                symbol=symbol, status="error", cutoffs=len(usable),
                records=written, detail=f"{type(error).__name__}: {error}"))
            frozen_total += written
            continue

        frozen_total += written
        results.append(SymbolResult(
            symbol=symbol,
            status="replayed" if written else "skipped",
            cutoffs=len(usable), records=written,
            detail=None if written else "every cutoff was already frozen"))

    run = StudyRun(
        study_id=study_id,
        started_at=started.isoformat(),
        finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        horizon=horizon, bars_ahead=spec.bars, stride_bars=stride,
        cutoffs=tuple(sorted(stamps)), results=tuple(results),
        frozen_records=frozen_total, path=str(ledger.path),
    )
    if log_dir is not None:
        _write_log(run, log_dir)
    return run


def _truncated(memo: MemoisedFetcher, cutoff: pd.Timestamp):
    """The engine's data door for one cutoff.

    Thin on purpose — it delegates to `replay._truncating_fetcher`, which is
    the same truncation the RR-2 recovery path uses.  Two different truncations
    for two replay paths would be two things to keep correct.
    """
    from . import replay

    return replay._truncating_fetcher(memo, pd.Timestamp(cutoff))


def _write_log(run: StudyRun, log_dir: str | pathlib.Path) -> pathlib.Path:
    directory = pathlib.Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = run.started_at.replace(":", "").replace("-", "")[:15]
    destination = directory / f"replay_study_{stamp}Z.json"
    destination.write_text(json.dumps(run.as_dict(), indent=2), encoding="utf-8")
    return destination


# ------------------------------------------------------------------- scoring


def score_study(
    *,
    path: str | pathlib.Path | None = None,
    fetcher: Callable[..., tuple[pd.DataFrame, Any]] | None = None,
    symbol: str | None = None,
    scored_at: dt.datetime | pd.Timestamp | None = None,
) -> list[outcome_ledger.OutcomeRecord]:
    """Read outcomes for every matured study forecast.  Writes outcomes only.

    This is `outcome_ledger.score_matured` unmodified, pointed at the study
    file.  It never calls a model and never regenerates a forecast — the rows
    it scores were frozen by a previous pass and are immutable by trigger, so
    "frozen before the outcome was read" is a property of the storage rather
    than a claim about the order two functions happened to be called in.

    The frame handed to the scorer is the **untruncated** history, deliberately.
    Reading the future is what scoring *is*; the guarantee that matters is that
    the forecast being scored cannot change, and it cannot.
    """
    target = pathlib.Path(path or DEFAULT_STUDY_PATH)
    if not target.exists():
        return []
    ledger = forecast_ledger.ReplayLedger(target)
    store = outcome_ledger.OutcomeStore(target)
    memo = fetcher if isinstance(fetcher, MemoisedFetcher) else MemoisedFetcher(fetcher)

    def frames(name: str, interval: str) -> pd.DataFrame | None:
        # Ten years covers every study horizon defined here, and the memo means
        # one download serves every cutoff of every symbol.
        try:
            return memo.frame(name, period="10y", interval=interval)
        except Exception:                                       # noqa: BLE001
            return None

    return outcome_ledger.score_matured(
        ledger, store, frames, symbol=symbol, scored_at=scored_at)


# --------------------------------------------------------------- performance


def load_performance(path: str | pathlib.Path | None = None) -> pd.DataFrame:
    """The scored study as a tidy frame, or empty without creating anything.

    `ReplayLedger.__init__` creates its file, so the existence check comes
    first — the same discipline `research_view.load` follows for the
    prospective ledger, and for the same reason.
    """
    target = pathlib.Path(path or DEFAULT_STUDY_PATH)
    if not target.exists():
        return pd.DataFrame()
    ledger = forecast_ledger.ReplayLedger(target)
    store = outcome_ledger.OutcomeStore(target)
    by_id = {record.forecast_id: record for record in ledger.list()}
    pairs = [(by_id[outcome.forecast_id], outcome) for outcome in store.list()
             if outcome.forecast_id in by_id]
    if not pairs:
        return pd.DataFrame()
    frame = outcome_ledger.performance_frame(pairs)
    # The action is the thing a user acts on, and it is not the sign of the
    # predicted return: `classify` vetoes a direction below the confidence
    # floor, so a bullish score can still read HOLD.  Both are carried.
    actions = {record.forecast_id:
               (record.model_predictions.get("ensemble") or {}).get("action")
               for record in by_id.values()}
    frame["action"] = frame["forecast_id"].map(actions)
    return frame


def independent_cutoff_count(frame: pd.DataFrame) -> int:
    """Draws in a study frame, under the same rule the promotion gate uses."""
    from . import promotion

    if frame is None or frame.empty:
        return 0
    spans = frame.groupby("cutoff_at").agg(matured_at=("matured_at", "max"))
    windows = [(cutoff, spans.at[cutoff, "matured_at"]) for cutoff in spans.index]
    return len(promotion.independent_cutoffs(windows))


@dataclasses.dataclass(frozen=True)
class StudySummary:
    """One engine version, at one horizon, over one study."""

    model_id: str
    model_version: str
    horizon: str
    n_scored: int
    n_directional: int
    n_independent_cutoffs: int
    n_symbols: int
    first_cutoff: pd.Timestamp | None
    last_cutoff: pd.Timestamp | None
    directional_accuracy: float
    directional_ci_low: float
    directional_ci_high: float
    baseline_directional_accuracy: float
    mae: float
    baseline_mae: float
    mae_advantage: float
    mae_advantage_half_width: float
    actions: dict[str, int]
    acted_n: int
    acted_accuracy: float

    @property
    def beats_baseline(self) -> bool:
        """Strictly, and resolvably — the same shape as the Phase 7 G7 gate."""
        lower = self.mae_advantage - self.mae_advantage_half_width
        return bool(np.isfinite(lower) and lower > 0.0)


#: Actions that are a call to do something, as opposed to an abstention.
ACTED = (ultimate.BUY, ultimate.STRONG_BUY, ultimate.SELL, ultimate.STRONG_SELL)


def summarise_study(frame: pd.DataFrame) -> list[StudySummary]:
    """One row per `(model, version, horizon)` — never pooled across versions.

    HR-1 in the reporting layer.  `outcome_ledger.summarise` groups by whatever
    it is told to; being told to include `model_version` is what stops a study
    that spans an engine change from reporting one accuracy for two engines.
    """
    if frame is None or frame.empty:
        return []
    summaries: list[StudySummary] = []
    grouped = frame.groupby(["model_key", "model_version", "horizon"],
                            dropna=False, sort=True)
    for (model_id, version, horizon), group in grouped:
        stats = outcome_ledger._summarise_group(group)
        called = group.loc[group["directional_correct"].notna()]
        acted = called.loc[called["action"].isin(ACTED)]
        counts = group["action"].value_counts().to_dict()
        summaries.append(StudySummary(
            model_id=str(model_id), model_version=str(version),
            horizon=str(horizon),
            n_scored=int(len(group)),
            n_directional=int(stats["n_directional"]),
            n_independent_cutoffs=independent_cutoff_count(group),
            n_symbols=int(group["symbol"].nunique()),
            first_cutoff=group["cutoff_at"].min(),
            last_cutoff=group["cutoff_at"].max(),
            directional_accuracy=float(stats["directional_accuracy"]),
            directional_ci_low=float(stats["directional_ci_low"]),
            directional_ci_high=float(stats["directional_ci_high"]),
            baseline_directional_accuracy=float(
                stats["baseline_directional_accuracy"]),
            mae=float(stats["mae"]),
            baseline_mae=float(stats["baseline_mae"]),
            mae_advantage=float(stats["mae_advantage"]),
            mae_advantage_half_width=float(stats["mae_advantage_half_width"]),
            actions={str(k): int(v) for k, v in counts.items()},
            acted_n=int(len(acted)),
            acted_accuracy=(float(acted["directional_correct"].mean())
                            if len(acted) else float("nan")),
        ))
    return summaries


def summary_table(frame: pd.DataFrame) -> pd.DataFrame:
    """`summarise_study` as a display frame, for the research UI."""
    rows = []
    for summary in summarise_study(frame):
        rows.append({
            "Model": summary.model_id,
            "Version": summary.model_version[:19] + "…",
            "Horizon": summary.horizon,
            "Scored": summary.n_scored,
            "Directional n": summary.n_directional,
            "Independent cutoffs": summary.n_independent_cutoffs,
            "Symbols": summary.n_symbols,
            "From": (None if summary.first_cutoff is None
                     else pd.Timestamp(summary.first_cutoff).date()),
            "To": (None if summary.last_cutoff is None
                   else pd.Timestamp(summary.last_cutoff).date()),
            "Accuracy": summary.directional_accuracy,
            "CI low": summary.directional_ci_low,
            "CI high": summary.directional_ci_high,
            "Baseline accuracy": summary.baseline_directional_accuracy,
            "MAE": summary.mae,
            "Baseline MAE": summary.baseline_mae,
            "MAE advantage": summary.mae_advantage,
            "± half-width": summary.mae_advantage_half_width,
            "Beats baseline": summary.beats_baseline,
        })
    return pd.DataFrame(rows)


def action_table(frame: pd.DataFrame) -> pd.DataFrame:
    """The BUY/HOLD/SELL breakdown, with accuracy where a call was made.

    HOLD carries no accuracy on purpose.  A HOLD is either a neutral score or a
    direction vetoed below the confidence floor; scoring it as a directional
    miss would count an abstention as a wrong answer, which is precisely the
    reading `ultimate`'s design note rejects.
    """
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows = []
    for action in ultimate.ACTIONS:
        subset = frame.loc[frame["action"] == action]
        called = subset.loc[subset["directional_correct"].notna()]
        rows.append({
            "Call": action,
            "n": int(len(subset)),
            "Share": (len(subset) / len(frame)) if len(frame) else float("nan"),
            "Scoreable": int(len(called)),
            "Accuracy": (float(called["directional_correct"].mean())
                         if len(called) and action in ACTED else float("nan")),
            "Mean realised %": (float(subset["realised_return"].mean())
                                if len(subset) else float("nan")),
        })
    return pd.DataFrame(rows)


def versions_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Every engine version the study holds, and how much of it each produced.

    The panel that makes HR-1 visible: if this has two rows, no number
    elsewhere may be read as describing "the engine".
    """
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows = []
    for (model_id, version), group in frame.groupby(
            ["model_key", "model_version"], dropna=False, sort=True):
        # Display-only annotation: "is this row the engine running today?".
        # `ModelSpec.version` re-imports the source module to hash it, so it can
        # fail for reasons that have nothing to do with the study — an
        # unregistered id, or an import path that does not resolve from the
        # caller's working directory. A panel must not die for a tick mark.
        try:
            live_version = model_registry.get(str(model_id)).version
        except Exception:                                       # noqa: BLE001
            live_version = None
        rows.append({
            "Model": str(model_id),
            "Version": str(version),
            "Is the live engine": live_version == str(version),
            "Scored": int(len(group)),
            "Horizons": ", ".join(sorted(group["horizon"].unique())),
            "From": pd.Timestamp(group["cutoff_at"].min()).date(),
            "To": pd.Timestamp(group["cutoff_at"].max()).date(),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.replay_study",
        description="Replay the frozen incumbent across historical cutoffs, "
                    "then score the results. Diagnostics only — study rows can "
                    "never support a promotion.",
    )
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="symbols to sweep; defaults to the collection universe")
    parser.add_argument("--horizon", default=DEFAULT_HORIZON,
                        choices=sorted(STUDY_HORIZONS),
                        help=f"study horizon (default {DEFAULT_HORIZON})")
    parser.add_argument("--cutoffs", type=int, default=60,
                        help="how many historical cutoffs to generate")
    parser.add_argument("--stride", type=int, default=None,
                        help="bars between cutoffs; defaults to the horizon "
                             "length, which makes every cutoff independent")
    parser.add_argument("--path", default=None, help="study database path")
    parser.add_argument("--score-only", action="store_true",
                        help="skip the sweep and score what is already frozen")
    arguments = parser.parse_args(argv)

    if arguments.symbols is None:
        from . import collector
        symbols = collector.read_universe()
    else:
        symbols = arguments.symbols

    if not arguments.score_only:
        run = run_study(
            symbols, horizon=arguments.horizon, count=arguments.cutoffs,
            stride_bars=arguments.stride, path=arguments.path,
            log_dir=DEFAULT_LOG_DIR,
            on_progress=lambda i, n, s: print(f"[{i + 1:>3}/{n}] {s}"),
        )
        print(run.summary())
        for failure in run.failures:
            print(f"  FAILED {failure.symbol}: {failure.detail}")

    scored = score_study(path=arguments.path)
    print(f"{len(scored)} newly scored outcome(s)")

    frame = load_performance(arguments.path)
    for summary in summarise_study(frame):
        print(f"{summary.model_id} @ {summary.horizon} "
              f"[{summary.model_version[:19]}…]: "
              f"{summary.directional_accuracy:.3f} accuracy over "
              f"{summary.n_directional} calls, "
              f"{summary.n_independent_cutoffs} independent cutoffs")
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
