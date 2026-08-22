"""HT-1 — every price-only component in this repository, on one grid, scored one way.

The repository holds twenty-seven things that will tell you which way a price is
going: seven TradingView studies ported in `pine.py`, the ten sources
`ultimate.py` aggregates, three rule agents, four reinforcement-learning agents
that survive point-in-time reconstruction, and three recurrent architectures.
Each was measured, where it was measured at all, on its own instrument — a
backtest here, a walk-forward there, an audit somewhere else — so no two of the
numbers were ever comparable.  This module measures all of them **on one grid of
historical cutoffs, against one baseline, with one scoring rule**, so that for
the first time the answers can be put in a single column.

**The protocol is `alpha/HT1_TOURNAMENT_PREREGISTRATION.md`, and it is frozen.**
The grid, the cell-admission rule, the roster, the call rule for each family,
the resolution floor, gate G-HT1, the multiplicity correction, the 60/40
chronological split and the challenger rule were all committed before this file
existed.  Nothing here chooses any of them, and nothing here may be changed to
suit a number it produced.

**Diagnostics.  Not evidence.**  Every row is `RETROSPECTIVE_REPLAY` in class
and counts **zero** toward every promotion, demotion and resolution gate.  HR-1
stated the division of labour and it is unchanged:

    historical replay  ->  fast evidence for model development
    prospective ledger ->  final independent production validation

The four reasons a replay can never promote anything are RR-2's and are not
weakened by running a wider roster over them: prices are back-adjusted for
corporate actions that post-date each cutoff, the universe is the one someone
watches today, the intraday depth is whatever the feed still serves, and —
the one no code can fix — whoever runs the study already knows what the market
did.

**What this module must never do**, restated because the roster is large enough
that a shortcut would be tempting:

- **No candidate enters `indicators.SOURCES`.**  `ultimate.evaluate` consumes
  that dict wholesale, so a source added there changes the live incumbent's
  evidence set while the ensemble's version — the sha256 of `ultimate.py` —
  stays put, and the prospective record silently splits across two engines
  wearing one version string.
- **`ultimate.py` and `forecast.py` are read, never written.**  The three
  horizons are passed to `evaluate_frame`; the neural seed is applied by a
  wrapper contained in this file.  Editing either module would re-version
  components against forecasts already frozen in the ledger.
- **Storage is a fourth database.**  The prospective ledger, the RR-2 replay
  ledger and the HR-1 study ledger cannot receive a tournament row, by CHECK
  constraint rather than by convention.

Point-in-time safety rests on three independent mechanisms, none relying on the
others: every candidate reads a frame truncated by `replay._truncating_fetcher`;
`fingerprint_frame(cutoff_at=...)` refuses a frame with a single bar past the
cutoff; and `test_tournament.py` rewrites every bar after the cutoff and
requires every call to be **identical**.  The third is the one that matters —
it does not inspect the truncation, it demonstrates the answer cannot depend on
the future.

Run:
    python -m core.tournament --predict --family closed_form
    python -m core.tournament --predict --family neural --shard 0 --of 12
    python -m core.tournament --score
    python -m core.tournament --report
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys
from collections.abc import Callable, Iterable, Sequence
from typing import Any

# TensorFlow reads these at import, and `forecast` imports it lazily — so
# setting them here is early enough, and it is required rather than cosmetic.
# Amendment 1 measured that a seeded pair still diverges to -10.79% against
# +10.69% under multi-threaded float accumulation. Twelve workers each want one
# thread anyway.
for _var in ("OMP_NUM_THREADS", "TF_NUM_INTRAOP_THREADS",
             "TF_NUM_INTEROP_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")
#: **The one that actually fixed LSTM**, and it took four measurements to find.
#: Python's per-process hash randomisation changes the order in which the graph
#: builder walks its collections, which changes op creation order, which changes
#: the op ids that op-level seeds are derived from — so an identically seeded
#: LSTM returned 0.5773, 0.5894, 0.5773 across three fresh processes. GRU and
#: Vanilla RNN are insensitive to it; LSTM, with twice the state, is not.
#: Pinned to 0, four separate processes agree bit for bit.
#:
#: `PYTHONHASHSEED` cannot be applied to an interpreter that is already running,
#: so setting it here works for exactly one reason: every projection runs in a
#: **spawned child**, which starts fresh and inherits this. Process isolation
#: is what makes the flag reachable at all — see `_fresh_pool`.
os.environ.setdefault("PYTHONHASHSEED", "0")

import numpy as np
import pandas as pd

from . import forecast_ledger, indicators, pine, promotion, replay_study, ultimate


# ------------------------------------------------------- frozen protocol §2–§8
#
# Every constant below is quoted from the pre-registration. None was chosen by
# looking at a forward return, and none may be edited to suit a result.

STUDY_ID = "HT-1"

#: §2. The grid: stride 25 bars on the universe's majority calendar.
GRID_STRIDE_BARS = 25
#: Generator cap. The grid is bounded by available history, not by this.
GRID_COUNT = 500

#: §2.1. One admission rule for every candidate, set by the most demanding of
#: them, so every paired comparison is exact rather than approximately paired.
MIN_HISTORY_BARS = 500
MAX_BARS_AHEAD = 25

#: §2.2. Read from the same cutoff — three readings of one moment.
HORIZON_BARS: dict[str, int] = {"1d": 1, "1w": 5, "5w": 25}

#: §4.4 / Amendment 1. `BaseAgent`'s own default and AMS-1's `AGENT_SEED`.
SEED = 42

#: §4.5. Frozen study parameterisation for the recurrent architectures.
NEURAL_TRAIN_BARS = 500
NEURAL_EPOCHS = 60
NEURAL_ROLLOUT = 25

#: §6.1. Below either floor a cell is UNRESOLVED — not a result, and not
#: entered into the gate family.
MIN_CALLS = 200
MIN_INDEPENDENT_CUTOFFS = 20

#: §6.2. Holm–Bonferroni over the whole family of resolved tests.
GATE_ALPHA = 0.05

#: §7. AMS-1's near-clone threshold, reused rather than re-chosen.
NEAR_CLONE_RHO = 0.90

#: §8.1. Chronological, never random.
SELECTION_FRACTION = 0.60

#: The three calls. `backtest.py`'s convention, and `strategies.py`'s.
BUY, HOLD, SELL = 1.0, 0.0, -1.0

DEFAULT_PATH = pathlib.Path(__file__).resolve().parents[1] / "tournament.sqlite3"
DEFAULT_CACHE = pathlib.Path(__file__).resolve().parents[1] / "cache"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class TournamentError(RuntimeError):
    """A tournament could not be constructed or run as specified."""


def _alpha():
    """AMS-1's frozen research objects, imported from the repository root.

    Reused rather than reimplemented, and that is the whole point: the rule
    agents' 252-bar windows and the RL agents' refit reconstruction were frozen
    before AMS-1 read any outcome. A second copy here would be a second thing
    to keep correct, and the copy that drifted would be the one producing a
    point-in-time leak.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from alpha import agents_audit, ams1_signals, stats
    return agents_audit, ams1_signals, stats


# ----------------------------------------------------------------- the roster

PINE = "pine"
TECHNICAL = "technical"
RULE = "rule"
RL = "rl"
NEURAL = "neural"
REFERENCE = "reference"

#: Families evaluated cell by cell on a truncated frame, in one pass.
CLOSED_FORM_FAMILIES = (PINE, TECHNICAL, RULE)


@dataclasses.dataclass(frozen=True)
class Candidate:
    """One entrant, and where it comes from."""

    key: str
    label: str
    family: str
    describe: str
    #: The registered model this candidate *is*, so a row can be resolved back
    #: to a declared identity, status and version.
    model_id: str
    #: True for the two reference arms, which are measured but never ranked,
    #: never gated, and never eligible for the challenger.
    reference: bool = False


#: The four RL agents that survive point-in-time reconstruction at a cost the
#: study can pay. The other fifteen are excluded on AMS-1's measured cost —
#: `B_VALUE_RL` 175 s/fit, `C_ACTOR_CRITIC` 167 s/fit and degenerate at the
#: repository's own default iterations, `F_CURIOSITY_RL` 43 s/fit — and per
#: registry §11.3 their exclusion may not later be offered as a reason the
#: result would have been different.
PIT_RL_AGENTS = (
    "Policy gradient",
    "Evolution strategy",
    "Neuro-evolution",
    "Neuro-evolution (novelty search)",
)

RULE_AGENTS = ("Turtle", "Moving average crossover", "Signal rolling")

NEURAL_MODELS = ("LSTM", "GRU", "Vanilla RNN")


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


def _build_roster() -> dict[str, Candidate]:
    roster: dict[str, Candidate] = {}

    for key, indicator in pine.INDICATORS.items():
        roster[f"pine.{key}"] = Candidate(
            key=f"pine.{key}", label=indicator.name, family=PINE,
            describe=pine.SIGNAL_RULES[key], model_id=f"pine.{key}")

    for key, source in indicators.SOURCES.items():
        roster[f"technical.{key}"] = Candidate(
            key=f"technical.{key}", label=source.name, family=TECHNICAL,
            describe=f"{source.describe} Called on the sign, with no threshold.",
            model_id=f"technical.{key}")

    for name in RULE_AGENTS:
        roster[f"rule.{_slug(name)}"] = Candidate(
            key=f"rule.{_slug(name)}", label=name, family=RULE,
            describe="Standing position, windows frozen at the 252-bar "
                     "reference in alpha/agents_audit.py.",
            model_id=f"rule_agent.{_slug(name)}")

    for name in PIT_RL_AGENTS:
        roster[f"rl.{_slug(name)}"] = Candidate(
            key=f"rl.{_slug(name)}", label=name, family=RL,
            describe="Policy fitted on the 500 bars before the most recent "
                     "annual refit boundary at or before the cutoff.",
            model_id=f"rl.{_slug(name)}")

    for name in NEURAL_MODELS:
        roster[f"neural.{_slug(name)}"] = Candidate(
            key=f"neural.{_slug(name)}", label=f"{name} projection",
            family=NEURAL,
            describe=f"{name} trained on the trailing {NEURAL_TRAIN_BARS} bars "
                     f"at {NEURAL_EPOCHS} epochs; one {NEURAL_ROLLOUT}-bar "
                     f"rollout read at 1, 5 and 25.",
            model_id=f"neural.{_slug(name)}")

    roster["reference.always_buy"] = Candidate(
        key="reference.always_buy", label="Always BUY", family=REFERENCE,
        describe="The trivial baseline HR-1 found the incumbent could not beat "
                 "at any horizon.",
        model_id="reference.always_buy", reference=True)
    roster["reference.incumbent"] = Candidate(
        key="reference.incumbent", label="Ultimate consensus", family=REFERENCE,
        describe="The frozen production incumbent, via evaluate_frame on the "
                 "identical cells.",
        model_id=ultimate_model_id(), reference=True)
    return roster


def ultimate_model_id() -> str:
    from . import model_registry
    return model_registry.ULTIMATE_ENSEMBLE


CANDIDATES: dict[str, Candidate] = _build_roster()

#: The 27 ranked entrants, in roster order. The two reference arms are measured
#: on the same cells but are never ranked and never gated.
RANKED = tuple(key for key, c in CANDIDATES.items() if not c.reference)


# -------------------------------------------------------------- price history


def load_frames(
    symbols: Sequence[str] | None = None,
    *,
    cache_dir: str | pathlib.Path | None = None,
) -> dict[str, pd.DataFrame]:
    """The frozen daily history every pass of the study reads.

    Read from `app/cache/*__1d.csv` directly rather than through `live.fetch`,
    for two reasons that both matter over a multi-hour sharded run. `fetch`
    trims to a requested period, which would silently shorten the deepest
    series and move the grid; and a study whose workers each re-download would
    let the series change underneath itself, making two cutoffs incomparable
    for a reason that has nothing to do with the market. One fixed history,
    read identically by every worker.
    """
    directory = pathlib.Path(cache_dir or DEFAULT_CACHE)
    if symbols is None:
        from . import collector
        symbols = collector.read_universe()

    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        path = directory / f"{symbol.upper()}__1d.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        frame["date"] = pd.to_datetime(frame["date"], errors="raise", utc=True)
        frame = frame.sort_values("date").reset_index(drop=True)
        if len(frame):
            frames[symbol.upper()] = frame
    if not frames:
        raise TournamentError(f"no cached daily bars under {directory}")
    return frames


def build_grid(frames: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    """§2. The 88 cutoffs, from `replay_study`'s generator, unmodified."""
    spec = replay_study.horizon_for("5w")
    return replay_study.shared_calendar(
        frames, bars_ahead=MAX_BARS_AHEAD, count=GRID_COUNT,
        stride_bars=GRID_STRIDE_BARS,
        min_history=replay_study.min_history_bars(spec))


@dataclasses.dataclass(frozen=True)
class Cell:
    """One `(symbol, cutoff)` the whole roster is asked about."""

    symbol: str
    cutoff: pd.Timestamp
    #: Position of the cutoff bar in that symbol's own series. Carried so the
    #: scorer never has to search for it a second time and risk finding a
    #: different bar.
    position: int


def admissible_cells(
    frames: dict[str, pd.DataFrame], grid: Sequence[pd.Timestamp],
) -> list[Cell]:
    """§2.1. A bar at the cutoff, 500 behind it, 25 ahead of it.

    A grid date the symbol did not trade is skipped, never snapped to a
    neighbouring bar: truncating at a non-bar date would leave the frame ending
    earlier than the declared session, which is a different question quietly
    substituted for the one asked.
    """
    cells: list[Cell] = []
    for symbol in sorted(frames):
        dates = frames[symbol]["date"]
        total = len(dates)
        lookup = pd.Series(range(total), index=pd.Index(dates))
        for cutoff in grid:
            position = lookup.get(cutoff)
            if position is None:
                continue
            position = int(position)
            if position + 1 < MIN_HISTORY_BARS:
                continue
            if position + MAX_BARS_AHEAD >= total:
                continue
            cells.append(Cell(symbol=symbol, cutoff=cutoff, position=position))
    return cells


def truncate(frame: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """The data door. Delegates to the truncation RR-2 and HR-1 already use."""
    from . import replay

    def source(symbol, *, period, interval, force=False):
        return frame, None

    truncated, _ = replay._truncating_fetcher(source, pd.Timestamp(cutoff))(
        "", period="10y", interval="1d")
    return truncated


# --------------------------------------------------------------- the families


def closed_form_calls(frame: pd.DataFrame) -> dict[str, float]:
    """Families P, T and R, read at the last bar of an already-truncated frame.

    One pass over the frame serves all twenty, which is why they are computed
    together: the truncation is the expensive part and it is shared.
    """
    agents_audit, _, _ = _alpha()
    calls: dict[str, float] = {}

    for key in pine.INDICATORS:
        try:
            events = pine.signals(key, frame)
            calls[f"pine.{key}"] = float(indicators.stance(events).iloc[-1])
        except pine.MissingColumns:
            calls[f"pine.{key}"] = HOLD

    for key, source in indicators.SOURCES.items():
        try:
            value = float(source.read(frame).iloc[-1])
        except Exception:                                       # noqa: BLE001
            value = float("nan")
        # §4.2: the sign, with no threshold. A magnitude cut-off would be a
        # free parameter with no pre-registered value.
        if not np.isfinite(value) or value == 0.0:
            calls[f"technical.{key}"] = HOLD
        else:
            calls[f"technical.{key}"] = BUY if value > 0 else SELL

    for name, series in agents_audit.rule_signals(frame["close"]).items():
        value = float(series.iloc[-1])
        calls[f"rule.{_slug(name)}"] = value if np.isfinite(value) else HOLD

    return calls


def rl_stances(
    frame: pd.DataFrame, grid: Sequence[pd.Timestamp],
) -> dict[str, pd.Series]:
    """Family A, as a standing position per bar, for one symbol.

    `ams1_signals.pit_agent_stance` is AMS-1's own reconstruction, imported
    rather than copied. Its guarantee, in its words: for a bar *t* in
    `[boundary_i, boundary_{i+1})` the policy was fitted on
    `close[:boundary_i][-500:]`, every element of which is at or before
    `boundary_i <= t`, and the action at *t* is read from the trailing price
    window. Nothing after *t* is reachable — which is why this family can be
    computed once per symbol rather than once per cutoff without becoming a
    replay of a policy that saw the future.
    """
    from . import agents as agentmod

    _, ams1, _ = _alpha()
    close = pd.Series(frame["close"].to_numpy(dtype=float),
                      index=pd.Index(frame["date"]))
    boundaries = ams1.refit_boundaries(list(grid))

    out: dict[str, pd.Series] = {}
    for name in PIT_RL_AGENTS:
        stance = ams1.pit_agent_stance(
            close, agentmod.REGISTRY[name], agentmod.DEFAULT_ITERATIONS[name],
            boundaries, train_bars=NEURAL_TRAIN_BARS)
        out[f"rl.{_slug(name)}"] = stance
    return out


@contextlib.contextmanager
def _seeded_tensorflow(seed: int = SEED):
    """Amendment 1. Make `forecast.project` reproducible without editing it.

    `forecast._train_once` calls `reset_default_graph()` and then builds, so a
    seed set beforehand is discarded with the graph it was set on. Wrapping the
    reset is the smallest intervention that survives it, and it leaves
    `app/core/forecast.py` byte-identical — which matters, because that file's
    sha256 is the version every `neural.*` spec reports.

    **`clear_session()` is load-bearing, not defensive.** `reset_default_graph`
    plus a seed is not enough on its own: measured over four identical
    sequential LSTM projections it returns two *alternating* values
    (−1.6434, −1.6323, −1.6323, −1.6434), because Keras state surviving between
    graphs shifts the op ordering the op-level seeds are derived from. The
    consequence is worse than noise — it makes a projection depend on how many
    projections ran before it in the same process, so a sharded sweep would
    return different numbers for a different shard layout. With the session
    cleared first, all four agree exactly.
    """
    from . import forecast

    tf = forecast._load_tf()
    original = tf.reset_default_graph

    def reset_and_seed():
        original()
        try:
            tf.keras.backend.clear_session()
        except Exception:                                       # noqa: BLE001
            pass
        original()
        tf.set_random_seed(seed)

    tf.reset_default_graph = reset_and_seed
    try:
        yield tf
    finally:
        tf.reset_default_graph = original


def _neural_in_process(closes: list[float]) -> dict[str, dict[str, tuple[float, float]]]:
    """The projection itself. Runs in a **fresh interpreter** — see `neural_calls`.

    One 25-bar rollout per architecture serves all three horizons. A 25-step
    autoregressive rollout's first step is identical to a 1-step rollout's
    first step — same weights, same deterministic loop — so reading the path at
    bars 1, 5 and 25 costs one fit where three would otherwise be needed.
    """
    from . import forecast

    close = pd.Series(closes, dtype=float)
    dates = pd.Series(pd.date_range("2000-01-03", periods=len(close), freq="B"))
    last_price = float(close.iloc[-1])

    out: dict[str, dict[str, tuple[float, float]]] = {}
    with _seeded_tensorflow():
        for name in NEURAL_MODELS:
            # `seed=SEED` explicitly, not `forecast.DEFAULT_SEED`. Phase B
            # moved the seeding and session-clearing that `_seeded_tensorflow`
            # monkeypatched in from the outside into `forecast._train_once`
            # itself; passing this study's own constant keeps HT-1's instrument
            # pinned to the value it was measured under rather than to whatever
            # the application's default happens to become.
            projection = forecast.project(
                close, dates, model=name, epochs=NEURAL_EPOCHS,
                horizon=NEURAL_ROLLOUT, seed=SEED)
            readings: dict[str, tuple[float, float]] = {}
            for horizon, bars in HORIZON_BARS.items():
                value = float(projection.path[bars - 1])
                move = (value - last_price) / last_price * 100.0 if last_price else 0.0
                call = HOLD if move == 0.0 else (BUY if move > 0 else SELL)
                readings[horizon] = (call, move)
            out[f"neural.{_slug(name)}"] = readings
    return out


def _neural_task(closes: list[float]):
    """Module-level entry point so `spawn` can pickle it."""
    return _neural_in_process(closes)


def _fresh_pool(workers: int = 1):
    """A pool whose every task gets an interpreter that has never seen TensorFlow.

    **Process isolation does two jobs, and both were established by
    measurement rather than assumed.**

    First, it removes cross-call state. Inside one interpreter,
    `reset_default_graph` plus a seed alternates between two values over
    repeated identical projections, and `keras.backend.clear_session()` narrows
    without closing it — so a projection's answer depended on how many
    projections preceded it, and a sharded sweep would return different numbers
    for a different shard layout.

    Second, and the reason LSTM is reproducible at all: it is the only way to
    apply `PYTHONHASHSEED`, which cannot be set on a running interpreter. A
    child starts fresh and inherits it. Without it an identically seeded LSTM
    returns two different values across fresh processes; with it, four agree bit
    for bit.

    `max_tasks_per_child=1` retires the worker after every cell, so each
    projection starts from an interpreter that has never seen TensorFlow, with
    the same seed and the same input. The cost is one import per cell — about
    5 s against the ~29 s the three fits take — and it buys a number that does
    not depend on its neighbours or on the run.
    """
    import concurrent.futures
    import multiprocessing

    return concurrent.futures.ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1)


def neural_calls(frame: pd.DataFrame) -> dict[str, dict[str, tuple[float, float]]]:
    """Family N on one truncated frame: `{candidate: {horizon: (call, move%)}}`.

    Only the trailing 500 closes cross into the worker. Nothing else can: the
    child is handed a list of floats, so there is no frame for a bar past the
    cutoff to hide in.
    """
    closes = [float(v) for v in frame["close"].iloc[-NEURAL_TRAIN_BARS:]]
    with _fresh_pool(1) as pool:
        return pool.submit(_neural_task, closes).result()


def incumbent_calls(frame: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """The reference incumbent, per horizon, on a truncated frame.

    `evaluate_frame` is called with a `Horizon` passed in. `5w` is
    `replay_study.FIVE_WEEKS` and is **not** added to `ultimate.HORIZONS` —
    doing so would change `ultimate.py`, whose sha256 is the model identity
    every frozen forecast records.
    """
    out: dict[str, tuple[float, float]] = {}
    for horizon in HORIZON_BARS:
        verdict = ultimate.evaluate_frame(frame, replay_study.horizon_for(horizon))
        action = verdict.action
        if action in (ultimate.BUY, ultimate.STRONG_BUY):
            call = BUY
        elif action in (ultimate.SELL, ultimate.STRONG_SELL):
            call = SELL
        else:
            call = HOLD
        out[horizon] = (call, float(verdict.score))
    return out


# ------------------------------------------------------------------- the store


_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    signal_id         TEXT PRIMARY KEY,
    study_id          TEXT NOT NULL CHECK (study_id = 'HT-1'),
    candidate         TEXT NOT NULL,
    family            TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    cutoff_at         TEXT NOT NULL,
    horizon           TEXT NOT NULL,
    call              REAL NOT NULL CHECK (call IN (-1.0, 0.0, 1.0)),
    magnitude         REAL,
    last_price        REAL NOT NULL,
    position          INTEGER NOT NULL,
    input_fingerprint TEXT NOT NULL,
    frozen_at         TEXT NOT NULL,
    UNIQUE (candidate, symbol, cutoff_at, horizon)
);
CREATE INDEX IF NOT EXISTS signals_candidate ON signals (candidate, horizon);
CREATE INDEX IF NOT EXISTS signals_cell ON signals (symbol, cutoff_at);

CREATE TABLE IF NOT EXISTS outcomes (
    signal_id           TEXT PRIMARY KEY REFERENCES signals (signal_id),
    matured_at          TEXT NOT NULL,
    matured_price       REAL NOT NULL,
    realised_return     REAL NOT NULL,
    directional_correct INTEGER,
    scored_at           TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS signals_are_immutable
BEFORE UPDATE ON signals
BEGIN
    SELECT RAISE(ABORT, 'a frozen tournament signal cannot be modified');
END;

CREATE TRIGGER IF NOT EXISTS signals_are_permanent
BEFORE DELETE ON signals
BEGIN
    SELECT RAISE(ABORT, 'a frozen tournament signal cannot be deleted');
END;
"""


class TournamentStore:
    """Frozen signals and their outcomes, in a file nothing else can write.

    The CHECK on `study_id` is the same device RR-2 used: a row from another
    study cannot land here by accident, and a tournament row cannot land in the
    prospective ledger, because each file's constraint admits only its own
    class. The immutability triggers make "frozen before the outcome was read"
    a property of the storage rather than a claim about the order two functions
    happened to be called in.
    """

    def __init__(self, path: str | pathlib.Path | None = None):
        self.path = pathlib.Path(path or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path))
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    # -- writing signals only ------------------------------------------------

    def insert_many(self, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        with self._connection:
            self._connection.executemany(
                "INSERT OR IGNORE INTO signals (signal_id, study_id, candidate,"
                " family, symbol, cutoff_at, horizon, call, magnitude,"
                " last_price, position, input_fingerprint, frozen_at)"
                " VALUES (:signal_id, :study_id, :candidate, :family, :symbol,"
                " :cutoff_at, :horizon, :call, :magnitude, :last_price,"
                " :position, :input_fingerprint, :frozen_at)", rows)
        return len(rows)

    def has(self, candidate: str, symbol: str, cutoff_at: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM signals WHERE candidate = ? AND symbol = ?"
            " AND cutoff_at = ? LIMIT 1", (candidate, symbol, cutoff_at)
        ).fetchone()
        return row is not None

    def done_cells(self, candidate: str) -> set[tuple[str, str]]:
        return {
            (row["symbol"], row["cutoff_at"])
            for row in self._connection.execute(
                "SELECT DISTINCT symbol, cutoff_at FROM signals"
                " WHERE candidate = ?", (candidate,))
        }

    def count(self) -> int:
        return int(self._connection.execute(
            "SELECT COUNT(*) FROM signals").fetchone()[0])

    # -- writing outcomes only -----------------------------------------------

    def unscored(self) -> list[sqlite3.Row]:
        return list(self._connection.execute(
            "SELECT s.* FROM signals s LEFT JOIN outcomes o"
            " ON o.signal_id = s.signal_id WHERE o.signal_id IS NULL"))

    def record_outcomes(self, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        with self._connection:
            self._connection.executemany(
                "INSERT OR IGNORE INTO outcomes (signal_id, matured_at,"
                " matured_price, realised_return, directional_correct, scored_at)"
                " VALUES (:signal_id, :matured_at, :matured_price,"
                " :realised_return, :directional_correct, :scored_at)", rows)
        return len(rows)

    # -- reading -------------------------------------------------------------

    def performance(self) -> pd.DataFrame:
        frame = pd.read_sql_query(
            "SELECT s.candidate, s.family, s.symbol, s.cutoff_at, s.horizon,"
            " s.call, s.magnitude, s.last_price, o.realised_return,"
            " o.directional_correct, o.matured_at"
            " FROM signals s JOIN outcomes o ON o.signal_id = s.signal_id",
            self._connection)
        if not frame.empty:
            frame["cutoff_at"] = pd.to_datetime(frame["cutoff_at"], utc=True)
            frame["matured_at"] = pd.to_datetime(frame["matured_at"], utc=True)
        return frame

    def signals_frame(self) -> pd.DataFrame:
        frame = pd.read_sql_query(
            "SELECT candidate, symbol, cutoff_at, horizon, call FROM signals",
            self._connection)
        if not frame.empty:
            frame["cutoff_at"] = pd.to_datetime(frame["cutoff_at"], utc=True)
        return frame


def _signal_id(candidate: str, symbol: str, cutoff_at: str, horizon: str) -> str:
    return "ht1_" + forecast_ledger._digest(
        {"c": candidate, "s": symbol, "t": cutoff_at, "h": horizon})[:20]


def _row(candidate: str, cell: Cell, horizon: str, call: float,
         magnitude: float | None, last_price: float, fingerprint: str,
         frozen_at: str) -> dict[str, Any]:
    stamp = forecast_ledger._utc_iso(cell.cutoff)
    return {
        "signal_id": _signal_id(candidate, cell.symbol, stamp, horizon),
        "study_id": STUDY_ID,
        "candidate": candidate,
        "family": CANDIDATES[candidate].family,
        "symbol": cell.symbol,
        "cutoff_at": stamp,
        "horizon": horizon,
        "call": float(call),
        "magnitude": None if magnitude is None else float(magnitude),
        "last_price": float(last_price),
        "position": int(cell.position),
        "input_fingerprint": fingerprint,
        "frozen_at": frozen_at,
    }


# ------------------------------------------------------------------ predicting


@dataclasses.dataclass(frozen=True)
class PredictRun:
    family: str
    shard: int
    of: int
    cells: int
    rows: int
    seconds: float
    failures: tuple[str, ...] = ()


def predict(
    family: str = "closed_form",
    *,
    shard: int = 0,
    of: int = 1,
    workers: int = 1,
    path: str | pathlib.Path | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> PredictRun:
    """Write signals. Reads no outcome, no forward return, no future bar.

    The two-process separation is Phase 2's and applies here exactly as it
    applies to the live ledger: this function never opens the `outcomes` table
    and `score` never opens `signals` for writing.
    """
    started = dt.datetime.now(dt.timezone.utc)
    frozen_at = forecast_ledger._utc_iso(started)
    frames = frames if frames is not None else load_frames()
    grid = build_grid(frames)
    cells = admissible_cells(frames, grid)
    store = TournamentStore(path)
    failures: list[str] = []
    written = 0

    try:
        if family == RL:
            symbols = sorted({cell.symbol for cell in cells})
            mine = [s for i, s in enumerate(symbols) if i % of == shard]
            by_symbol: dict[str, list[Cell]] = {}
            for cell in cells:
                by_symbol.setdefault(cell.symbol, []).append(cell)
            for index, symbol in enumerate(mine):
                if on_progress:
                    on_progress(index, len(mine), symbol)
                try:
                    stances = rl_stances(frames[symbol], grid)
                except Exception as error:                      # noqa: BLE001
                    failures.append(f"{symbol}: {type(error).__name__}: {error}")
                    continue
                rows: list[dict[str, Any]] = []
                for cell in by_symbol[symbol]:
                    frame = frames[symbol]
                    last_price = float(frame["close"].iloc[cell.position])
                    for candidate, stance in stances.items():
                        value = stance.get(cell.cutoff, np.nan)
                        # Before the first admissible refit boundary an agent
                        # has no policy. That is *unavailable*, and inventing a
                        # HOLD would invent an opinion it could not have had.
                        if not np.isfinite(value):
                            continue
                        for horizon in HORIZON_BARS:
                            rows.append(_row(
                                candidate, cell, horizon, float(value), None,
                                last_price, "rl:refit", frozen_at))
                written += store.insert_many(rows)
            return PredictRun(family, shard, of, len(cells), written,
                              _elapsed(started), tuple(failures))

        if family == NEURAL:
            mine = [c for i, c in enumerate(cells) if i % of == shard]
            written, neural_failures = _predict_neural(
                mine, frames, store, frozen_at, workers, on_progress)
            failures.extend(neural_failures)
            return PredictRun(family, shard, of, len(mine), written,
                              _elapsed(started), tuple(failures))

        mine = [c for i, c in enumerate(cells) if i % of == shard]
        for index, cell in enumerate(mine):
            if on_progress and index % 10 == 0:
                on_progress(index, len(mine), f"{cell.symbol} {cell.cutoff.date()}")
            frame = frames[cell.symbol]
            try:
                truncated = truncate(frame, cell.cutoff)
                # Refuses if a single bar past the cutoff survived. Checks the
                # frame that is about to be read, not the call that produced it.
                fingerprint = forecast_ledger.fingerprint_frame(
                    truncated, cutoff_at=cell.cutoff)
                last_price = float(truncated["close"].iloc[-1])
                rows = []

                if family == "closed_form":
                    for candidate, call in closed_form_calls(truncated).items():
                        for horizon in HORIZON_BARS:
                            rows.append(_row(candidate, cell, horizon, call,
                                             None, last_price, fingerprint,
                                             frozen_at))
                elif family == REFERENCE:
                    for horizon, (call, score) in incumbent_calls(truncated).items():
                        rows.append(_row("reference.incumbent", cell, horizon,
                                         call, score, last_price, fingerprint,
                                         frozen_at))
                    for horizon in HORIZON_BARS:
                        rows.append(_row("reference.always_buy", cell, horizon,
                                         BUY, None, last_price, fingerprint,
                                         frozen_at))
                else:
                    raise TournamentError(f"unknown family {family!r}")

                written += store.insert_many(rows)
            except Exception as error:                          # noqa: BLE001
                failures.append(
                    f"{cell.symbol} {cell.cutoff.date()}: "
                    f"{type(error).__name__}: {error}")
    finally:
        store.close()

    return PredictRun(family, shard, of, len(mine), written,
                      _elapsed(started), tuple(failures))


def _predict_neural(
    cells: Sequence[Cell],
    frames: dict[str, pd.DataFrame],
    store: TournamentStore,
    frozen_at: str,
    workers: int,
    on_progress: Callable[[int, int, str], None] | None,
) -> tuple[int, list[str]]:
    """Family N over many cells, one fresh interpreter per cell.

    Rows are written as futures complete rather than at the end, so a sweep
    interrupted after four hours keeps every cell it finished — and the
    duplicate guard makes resuming free.
    """
    import concurrent.futures

    todo: list[tuple[Cell, list[float], str, float]] = []
    failures: list[str] = []
    for cell in cells:
        try:
            truncated = truncate(frames[cell.symbol], cell.cutoff)
            fingerprint = forecast_ledger.fingerprint_frame(
                truncated, cutoff_at=cell.cutoff)
            closes = [float(v) for v in
                      truncated["close"].iloc[-NEURAL_TRAIN_BARS:]]
            todo.append((cell, closes, fingerprint,
                         float(truncated["close"].iloc[-1])))
        except Exception as error:                              # noqa: BLE001
            failures.append(f"{cell.symbol} {cell.cutoff.date()}: "
                            f"{type(error).__name__}: {error}")

    written = 0
    with _fresh_pool(max(1, workers)) as pool:
        futures = {
            pool.submit(_neural_task, closes): (cell, fingerprint, last_price)
            for cell, closes, fingerprint, last_price in todo
        }
        for index, future in enumerate(
                concurrent.futures.as_completed(futures)):
            cell, fingerprint, last_price = futures[future]
            if on_progress:
                on_progress(index, len(futures),
                            f"{cell.symbol} {cell.cutoff.date()}")
            try:
                readings_by_candidate = future.result()
            except Exception as error:                          # noqa: BLE001
                failures.append(f"{cell.symbol} {cell.cutoff.date()}: "
                                f"{type(error).__name__}: {error}")
                continue
            rows = [
                _row(candidate, cell, horizon, call, move, last_price,
                     fingerprint, frozen_at)
                for candidate, readings in readings_by_candidate.items()
                for horizon, (call, move) in readings.items()
            ]
            written += store.insert_many(rows)
    return written, failures


def stability_probe(
    *,
    sample: int = 60,
    workers: int = 12,
    frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Amendment 2: how often does a re-run change the call, per architecture?

    Family N is only partly reproducible — GRU and Vanilla RNN return identical
    paths, LSTM does not — and a directional accuracy is only as meaningful as
    the stability of the directions it counts. This runs the same cells twice
    and reports the share of calls that changed sign.

    The amendment committed the study to publishing this number, so it is
    measured rather than asserted, and it is the figure that tells a reader
    whether `neural.lstm`'s leaderboard row can be read at all.
    """
    frames = frames if frames is not None else load_frames()
    cells = admissible_cells(frames, build_grid(frames))
    step = max(1, len(cells) // sample)
    chosen = cells[::step][:sample]

    payloads = []
    for cell in chosen:
        truncated = truncate(frames[cell.symbol], cell.cutoff)
        payloads.append(
            (cell, [float(v) for v in
                    truncated["close"].iloc[-NEURAL_TRAIN_BARS:]]))

    passes: list[dict[tuple[str, str, str], tuple[float, float]]] = []
    for _ in range(2):
        readings: dict[tuple[str, str, str], tuple[float, float]] = {}
        with _fresh_pool(max(1, workers)) as pool:
            futures = {pool.submit(_neural_task, closes): cell
                       for cell, closes in payloads}
            import concurrent.futures
            for future in concurrent.futures.as_completed(futures):
                cell = futures[future]
                for candidate, per_horizon in future.result().items():
                    for horizon, (call, move) in per_horizon.items():
                        key = (candidate, cell.symbol,
                               forecast_ledger._utc_iso(cell.cutoff) + horizon)
                        readings[key] = (call, move)
        passes.append(readings)

    rows = []
    for candidate in (f"neural.{_slug(n)}" for n in NEURAL_MODELS):
        keys = [k for k in passes[0] if k[0] == candidate and k in passes[1]]
        flips = sum(1 for k in keys if passes[0][k][0] != passes[1][k][0])
        drift = [abs(passes[0][k][1] - passes[1][k][1]) for k in keys]
        # Median and p90 alongside the mean because the drift is heavy-tailed:
        # the LSTM rollout occasionally diverges outright, and a mean shaped by
        # those cells would describe neither the typical case nor the failure.
        rows.append({
            "Candidate": candidate,
            "Compared": len(keys),
            "Sign flips": flips,
            "Flip rate": flips / len(keys) if keys else float("nan"),
            "Median drift pp": float(np.median(drift)) if drift else float("nan"),
            "p90 drift pp": float(np.quantile(drift, 0.9)) if drift else float("nan"),
            "Mean drift pp": float(np.mean(drift)) if drift else float("nan"),
            "Max drift pp": float(np.max(drift)) if drift else float("nan"),
            "Reproducible": flips == 0 and (max(drift) if drift else 0) == 0.0,
        })
    return pd.DataFrame(rows)


def _elapsed(started: dt.datetime) -> float:
    return (dt.datetime.now(dt.timezone.utc) - started).total_seconds()


# --------------------------------------------------------------------- scoring


def score(
    *,
    path: str | pathlib.Path | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
) -> int:
    """Read outcomes for every frozen signal. Writes outcomes only.

    The frame here is the **untruncated** history, deliberately: reading the
    future is what scoring *is*. The guarantee that matters is that the signal
    being scored cannot change, and the immutability trigger makes that a
    property of the file.
    """
    frames = frames if frames is not None else load_frames()
    store = TournamentStore(path)
    scored_at = forecast_ledger._utc_iso(dt.datetime.now(dt.timezone.utc))
    rows: list[dict[str, Any]] = []

    try:
        for signal in store.unscored():
            frame = frames.get(signal["symbol"])
            if frame is None:
                continue
            position = int(signal["position"])
            ahead = HORIZON_BARS[signal["horizon"]]
            maturity = position + ahead
            if maturity >= len(frame):
                continue
            anchor = float(frame["close"].iloc[position])
            matured = float(frame["close"].iloc[maturity])
            if not anchor:
                continue
            realised = matured / anchor - 1.0
            call = float(signal["call"])
            # A HOLD is an abstention and carries no accuracy. Scoring it as a
            # miss would count an abstention as a wrong answer.
            correct: int | None
            if call == HOLD:
                correct = None
            else:
                correct = int((call > 0 and realised > 0)
                              or (call < 0 and realised < 0))
            rows.append({
                "signal_id": signal["signal_id"],
                "matured_at": forecast_ledger._utc_iso(
                    frame["date"].iloc[maturity]),
                "matured_price": matured,
                "realised_return": realised,
                "directional_correct": correct,
                "scored_at": scored_at,
            })
        return store.record_outcomes(rows)
    finally:
        store.close()


# ------------------------------------------------------------------- reporting


def independent_cutoffs(group: pd.DataFrame) -> int:
    """Draws in a group, under the rule the promotion gate uses."""
    if group.empty:
        return 0
    spans = group.groupby("cutoff_at").agg(matured_at=("matured_at", "max"))
    return len(promotion.independent_cutoffs(
        [(cutoff, spans.at[cutoff, "matured_at"]) for cutoff in spans.index]))


def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (float("nan"), float("nan"))
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    margin = z * np.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return (float(centre - margin), float(centre + margin))


def leaderboard(frame: pd.DataFrame) -> pd.DataFrame:
    """§5 and §6. One row per (candidate, horizon), with the gate applied.

    The baseline is always-BUY on **identical rows**: for each candidate the
    comparison is restricted to the cells that candidate actually called, so
    the difference is a difference in accuracy and not a difference in which
    days each arm happened to speak on.
    """
    _, _, stats = _alpha()
    if frame.empty:
        return pd.DataFrame()

    rows = []
    for (candidate, horizon), group in frame.groupby(["candidate", "horizon"],
                                                     sort=True):
        spec = CANDIDATES.get(candidate)
        called = group.loc[group["directional_correct"].notna()].copy()
        n_calls = int(len(called))
        cutoffs = independent_cutoffs(called) if n_calls else 0
        resolved = n_calls >= MIN_CALLS and cutoffs >= MIN_INDEPENDENT_CUTOFFS

        accuracy = float(called["directional_correct"].mean()) if n_calls else float("nan")
        low, high = _wilson(int(called["directional_correct"].sum()), n_calls)

        # The baseline on the same rows: always-BUY is correct exactly when the
        # realised return is positive.
        baseline = (called["realised_return"] > 0).astype(float)
        advantage = called["directional_correct"].astype(float) - baseline
        per_cutoff = advantage.groupby(called["cutoff_at"]).mean()
        values = per_cutoff.to_numpy(dtype=float)

        if len(values) >= 4:
            ci_low, ci_high = stats.block_bootstrap_ci(
                values, block=stats.BLOCK_LENGTH, draws=stats.BOOTSTRAP_DRAWS)
            p_value = stats.block_bootstrap_p(
                values, block=stats.BLOCK_LENGTH, draws=stats.BOOTSTRAP_DRAWS)
        else:
            ci_low = ci_high = p_value = float("nan")

        buys = called.loc[called["call"] > 0, "realised_return"]
        sells = called.loc[called["call"] < 0, "realised_return"]
        spread = (float(buys.mean()) - float(sells.mean())) * 1e4 if len(buys) and len(sells) else float("nan")

        rows.append({
            "Candidate": candidate,
            "Label": spec.label if spec else candidate,
            "Family": spec.family if spec else "?",
            "Horizon": horizon,
            "Cells": int(len(group)),
            "Calls": n_calls,
            "Coverage": n_calls / len(group) if len(group) else float("nan"),
            "Independent cutoffs": cutoffs,
            "Accuracy": accuracy,
            "CI low": low,
            "CI high": high,
            "Baseline accuracy": float(baseline.mean()) if n_calls else float("nan"),
            "Advantage": float(np.mean(values)) if len(values) else float("nan"),
            "Adv CI low": ci_low,
            "Adv CI high": ci_high,
            "p": p_value,
            "BUY-SELL bp": spread,
            "Resolved": resolved,
            "Reference": bool(spec.reference) if spec else False,
        })

    table = pd.DataFrame(rows)
    return _apply_gate(table)


def _apply_gate(table: pd.DataFrame) -> pd.DataFrame:
    """§6.2. Interval strictly above zero **and** Holm–Bonferroni at α = 0.05.

    The correction runs over the whole family of resolved, non-reference tests,
    and the family was declared before its size was known. A candidate clearing
    the interval but not the correction is REPORTED AS NOT BEATING THE
    BASELINE; its uncorrected interval is still printed, because suppressing it
    would be its own distortion.
    """
    _, _, stats = _alpha()
    if table.empty:
        return table

    names = table["Candidate"].astype(str) + "@" + table["Horizon"].astype(str)
    eligible = table["Resolved"] & ~table["Reference"] & np.isfinite(table["p"])
    family = dict(zip(names[eligible], table.loc[eligible, "p"].astype(float)))
    decisions = stats.holm_bonferroni(family, alpha=GATE_ALPHA) if family else {}

    table["Family size"] = len(family)
    table["p Holm"] = [decisions.get(name, {}).get("p_holm") for name in names]
    table["Holm reject"] = [
        bool(decisions.get(name, {}).get("significant", False)) for name in names
    ]
    table["Beats baseline"] = (
        table["Resolved"] & ~table["Reference"] & table["Holm reject"]
        & np.isfinite(table["Adv CI low"]) & (table["Adv CI low"] > 0.0)
    )
    table["Verdict"] = np.select(
        [table["Reference"], ~table["Resolved"], table["Beats baseline"]],
        ["REFERENCE", "UNRESOLVED", "BEATS BASELINE"],
        default="REJECT")
    return table.sort_values(
        ["Horizon", "Advantage"], ascending=[True, False]).reset_index(drop=True)


def correlation(frame: pd.DataFrame, horizon: str = "1d") -> pd.DataFrame:
    """§7. The call series of every candidate, aligned cell by cell.

    Diagnostic. No hypothesis, no gate, no p-value — reported because a
    leaderboard of twenty-seven candidates that are secretly three candidates
    would be a misleading object.
    """
    subset = frame.loc[frame["horizon"] == horizon]
    if subset.empty:
        return pd.DataFrame()
    return subset.pivot_table(
        index=["symbol", "cutoff_at"], columns="candidate", values="call")


def redundancy(matrix: pd.DataFrame) -> dict[str, Any]:
    """Pairwise correlation, near-clones at |ρ| ≥ 0.9, effective opinions."""
    ranked = [c for c in matrix.columns if c in RANKED]
    subset = matrix[ranked]
    pearson = subset.corr(method="pearson")
    spearman = subset.corr(method="spearman")

    pairs = []
    for i, left in enumerate(ranked):
        for right in ranked[i + 1:]:
            rho = float(pearson.at[left, right])
            agree = float((subset[left] == subset[right]).mean())
            pairs.append({"a": left, "b": right, "pearson": rho,
                          "spearman": float(spearman.at[left, right]),
                          "agreement": agree,
                          "near_clone": bool(abs(rho) >= NEAR_CLONE_RHO)})
    pair_frame = pd.DataFrame(pairs)

    # Effective opinions: single-linkage clusters at the near-clone threshold.
    parent = {name: name for name in ranked}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for pair in pairs:
        if pair["near_clone"]:
            a, b = find(pair["a"]), find(pair["b"])
            if a != b:
                parent[a] = b

    clusters = len({find(name) for name in ranked})
    return {
        "pearson": pearson,
        "spearman": spearman,
        "pairs": pair_frame,
        "n_candidates": len(ranked),
        "n_pairs": len(pairs),
        "n_near_clones": int(pair_frame["near_clone"].sum()) if len(pair_frame) else 0,
        "effective_opinions": clusters,
    }


def split_cutoffs(cutoffs: Sequence[pd.Timestamp]) -> tuple[list, list]:
    """§8.1. Chronological 60/40. Never random."""
    ordered = sorted(set(pd.to_datetime(pd.Series(list(cutoffs)), utc=True)))
    cut = int(round(len(ordered) * SELECTION_FRACTION))
    return ordered[:cut], ordered[cut:]


@dataclasses.dataclass
class Challenger:
    """§8.2. Equal-weight majority vote of the SELECTION survivors."""

    built: bool
    reason: str
    members: tuple[str, ...] = ()
    table: pd.DataFrame | None = None


def build_challenger(frame: pd.DataFrame) -> Challenger:
    """Rank on SELECTION, vote on VALIDATION, and refuse where §0.1 bars it."""
    if frame.empty:
        return Challenger(False, "no scored rows")

    selection, validation = split_cutoffs(frame["cutoff_at"].unique())
    left = frame.loc[frame["cutoff_at"].isin(selection)]
    board = leaderboard(left)
    if board.empty:
        return Challenger(False, "SELECTION produced no leaderboard")

    survivors = tuple(board.loc[board["Beats baseline"], "Candidate"].unique())

    if len(survivors) < 2:
        return Challenger(
            False,
            f"§8.2: {len(survivors)} candidate(s) passed G-HT1 on SELECTION; "
            "fewer than two, so no challenger is built. That is the outcome, "
            "not a reason to weaken the rule.",
            survivors)

    families = {CANDIDATES[key].family for key in survivors}
    if families <= {RULE, RL}:
        return Challenger(
            False,
            "§0.1: every survivor is a trading agent, so the equal-weight vote "
            "would be cross-family trading-agent agreement — the construction "
            "AMS-1 rejected and EXPERIMENT_REGISTRY §11.3 bars. Not built.",
            survivors)

    right = frame.loc[frame["cutoff_at"].isin(validation)
                      & frame["candidate"].isin(survivors)]
    votes = right.pivot_table(index=["symbol", "cutoff_at", "horizon"],
                              columns="candidate", values="call")
    consensus = np.sign(votes.mean(axis=1))          # ties -> 0 -> HOLD
    truth = right.groupby(["symbol", "cutoff_at", "horizon"])[
        "realised_return"].first()
    joined = pd.DataFrame({"call": consensus, "realised_return": truth}).dropna()
    joined = joined.reset_index()
    joined["candidate"] = "challenger.ht1"
    joined["family"] = "challenger"
    joined["directional_correct"] = np.where(
        joined["call"] == 0, np.nan,
        ((joined["call"] > 0) & (joined["realised_return"] > 0))
        | ((joined["call"] < 0) & (joined["realised_return"] < 0)))
    joined["matured_at"] = joined["cutoff_at"]
    CANDIDATES.setdefault("challenger.ht1", Candidate(
        key="challenger.ht1", label="HT-1 challenger", family="challenger",
        describe="Equal-weight majority vote of the SELECTION survivors.",
        model_id="challenger.ht1"))
    return Challenger(True, "built from SELECTION survivors", survivors,
                      leaderboard(joined))


# ----------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.tournament",
        description="HT-1: every price-only component on one grid. "
                    "Diagnostics only — no row here can support a promotion.")
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--stability", action="store_true",
                        help="Amendment 2: measure the neural sign-flip rate")
    parser.add_argument("--family", default="closed_form",
                        choices=["closed_form", RL, NEURAL, REFERENCE])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--of", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1,
                        help="parallel workers for the neural family; each cell "
                             "gets a fresh interpreter regardless")
    parser.add_argument("--path", default=None)
    arguments = parser.parse_args(argv)

    if arguments.predict:
        run = predict(arguments.family, shard=arguments.shard, of=arguments.of,
                      workers=arguments.workers, path=arguments.path,
                      on_progress=lambda i, n, what: print(
                          f"[{arguments.family} {arguments.shard}/{arguments.of}]"
                          f" {i + 1}/{n} {what}", flush=True))
        print(f"{run.rows} signal(s) over {run.cells} cell(s) "
              f"in {run.seconds:.0f}s")
        for failure in run.failures[:20]:
            print(f"  FAILED {failure}")

    if arguments.score:
        print(f"{score(path=arguments.path)} newly scored outcome(s)")

    if arguments.stability:
        with pd.option_context("display.width", 200,
                               "display.float_format", lambda v: f"{v:.4f}"):
            print(stability_probe(workers=arguments.workers).to_string(index=False))

    if arguments.report:
        store = TournamentStore(arguments.path)
        try:
            frame = store.performance()
        finally:
            store.close()
        board = leaderboard(frame)
        if board.empty:
            print("nothing scored yet")
            return 0
        columns = ["Candidate", "Horizon", "Calls", "Coverage", "Accuracy",
                   "Baseline accuracy", "Advantage", "Adv CI low",
                   "Adv CI high", "p", "Verdict"]
        with pd.option_context("display.width", 200,
                               "display.max_rows", 200,
                               "display.float_format", lambda v: f"{v:.4f}"):
            print(board[columns].to_string(index=False))
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
