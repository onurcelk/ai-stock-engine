"""What the research record says, assembled for display and nothing else.

Phase 8 has one rule that shapes every function here: **build the UI from
stored evidence, not recomputed hindsight.**  So this module reads frozen
records and returns frames.  It fits nothing, calls no model, regenerates no
forecast, and writes nothing.

One consequence is worth stating because it is easy to get wrong and the tests
enforce it: `ForecastLedger.__init__` *creates* its SQLite file, so merely
constructing one to see whether it holds anything would manufacture the very
artefact whose absence Phase 7 §6 and Phase 9 §6 both rest on.  Every entry
point below therefore checks for the file first and returns an empty state
without constructing anything.  **Opening a tab must not start a record.**
"""

from __future__ import annotations

import dataclasses
import pathlib
from typing import Any

import pandas as pd

from . import (
    forecast_ledger,
    model_registry,
    outcome_ledger,
    promotion,
    replay_study,
)
from .forecast_ledger import ForecastRecord
from .outcome_ledger import OutcomeRecord


#: Below this many independent cutoffs, every headline number is decoration.
#: Taken from the Phase 7 policy rather than invented here, so the warning the
#: user sees and the gate the model must pass are the same number.
MIN_CUTOFFS = promotion.MIN_INDEPENDENT_CUTOFFS


@dataclasses.dataclass(frozen=True)
class ResearchState:
    """Everything the research surfaces read, loaded once per render."""

    ledger_path: pathlib.Path
    exists: bool
    forecasts: tuple[ForecastRecord, ...]
    outcomes: tuple[OutcomeRecord, ...]
    performance: pd.DataFrame

    @property
    def has_forecasts(self) -> bool:
        return bool(self.forecasts)

    @property
    def has_outcomes(self) -> bool:
        return not self.performance.empty

    @property
    def n_independent_cutoffs(self) -> int:
        """Draws, not rows — the only count a claim may be built on.

        Reconstructions are excluded here as well as in `promotion`. A replay
        is a forecast for a session that had already closed, so counting one
        toward a resolution floor would let a missed week be recovered into
        evidence — the exact substitution the separation exists to prevent.
        """
        if self.performance.empty:
            return 0
        prospective = self.performance
        if "status" in prospective.columns:
            prospective = prospective.loc[
                prospective["status"] != forecast_ledger.RETROSPECTIVE_REPLAY]
        if prospective.empty:
            return 0
        spans = prospective.groupby("cutoff_at").agg(
            matured_at=("matured_at", "max"))
        windows = [(cutoff, spans.at[cutoff, "matured_at"])
                   for cutoff in spans.index]
        return len(promotion.independent_cutoffs(windows))

    @property
    def thin(self) -> bool:
        return self.n_independent_cutoffs < MIN_CUTOFFS


def _empty(path: pathlib.Path) -> ResearchState:
    return ResearchState(ledger_path=path, exists=False, forecasts=(),
                         outcomes=(), performance=pd.DataFrame())


def load(path: str | pathlib.Path | None = None) -> ResearchState:
    """Read the frozen record, or return an empty state without creating it."""
    ledger_path = pathlib.Path(path or forecast_ledger.DEFAULT_PATH)
    if not ledger_path.exists():
        return _empty(ledger_path)

    ledger = forecast_ledger.ForecastLedger(ledger_path)
    store = outcome_ledger.OutcomeStore(ledger_path)
    forecasts = tuple(ledger.list())
    outcomes = tuple(store.list())

    by_id = {record.forecast_id: record for record in forecasts}
    pairs = [(by_id[outcome.forecast_id], outcome) for outcome in outcomes
             if outcome.forecast_id in by_id]
    performance = (outcome_ledger.performance_frame(pairs) if pairs
                   else pd.DataFrame())
    return ResearchState(ledger_path=ledger_path, exists=True,
                         forecasts=forecasts, outcomes=outcomes,
                         performance=performance)


# ------------------------------------------------------------- production


def production_panel(state: ResearchState) -> pd.DataFrame:
    """What is live: identity, version, horizons, and when it last refit.

    `Last refit` is read from the registry's own retraining policy rather than
    from a timestamp, because for every component here there is no timestamp
    to read — nothing persists a fit (Phase 7 §1).  Saying "never" would be a
    guess about a thing that does not exist; the registry's own words are the
    honest answer.
    """
    rows = []
    for spec in model_registry.by_status(model_registry.PRODUCTION):
        frozen = [record for record in state.forecasts
                  if record.production_or_challenger
                  == forecast_ledger.PRODUCTION_INCUMBENT]
        rows.append({
            "Model": spec.label,
            "Identity": spec.model_id,
            "Version": spec.version[:12],
            "Horizons": ", ".join(spec.horizons) if spec.horizons else "—",
            "Retraining policy": spec.retraining_policy,
            "Frozen forecasts": sum(
                1 for record in frozen
                if model_registry.record_spec(record).model_id == spec.model_id),
        })
    return pd.DataFrame(rows)


def active_weights(state: ResearchState) -> pd.DataFrame:
    """Constituent weights **as frozen on the most recent record**.

    The live engine re-derives its weights at every evaluation and remembers
    none of them (Phase 0 severity 3), so the only weights that can honestly be
    displayed are the ones a frozen forecast carries.  An empty frame here does
    not mean the ensemble is unweighted — it means nothing has been frozen.
    """
    if not state.forecasts:
        return pd.DataFrame()
    latest = max(state.forecasts, key=lambda record: record.generated_at)
    rows = [{"Source": name, "Weight": value,
             "Prediction": latest.model_predictions.get(name)}
            for name, value in sorted(latest.model_weights.items())]
    return pd.DataFrame(rows)


# --------------------------------------------------------- forecast quality


def quality(state: ResearchState) -> pd.DataFrame:
    """Directional accuracy, error, and baseline-relative skill, with `n`."""
    if state.performance.empty:
        return pd.DataFrame()
    return outcome_ledger.summarise(state.performance, min_samples=MIN_CUTOFFS)


def rolling(state: ResearchState, window: int = 20) -> pd.DataFrame:
    if state.performance.empty:
        return pd.DataFrame()
    return outcome_ledger.rolling_summary(state.performance, window=window)


def calibration(state: ResearchState) -> pd.DataFrame:
    if state.performance.empty:
        return pd.DataFrame()
    return outcome_ledger.calibration(state.performance)


# ------------------------------------------------------------ leaderboard


def leaderboard(state: ResearchState, *, recent: int = 20) -> pd.DataFrame:
    """Every ledger-reaching model, its status, and what it has actually shown.

    Models with no scored forecast still appear, with blank scores and `n = 0`.
    A leaderboard that hid them would answer "who is winning" when the true
    answer is "nothing has run".
    """
    summary = quality(state)
    recent_summary = rolling(state, window=recent)

    rows = []
    for spec in model_registry.specs():
        if spec.record_key is None:
            continue  # cannot reach a frozen forecast, so cannot be scored
        for horizon in (spec.horizons or ("—",)):
            row: dict[str, Any] = {
                "Model": spec.label,
                "Identity": spec.model_id,
                "Status": spec.production_status,
                "Horizon": horizon,
                "n": 0,
                "Long-run accuracy": float("nan"),
                "Recent accuracy": float("nan"),
                "vs baseline": float("nan"),
                "Weight": float("nan"),
            }
            if not summary.empty:
                match = summary.loc[(summary["model_key"] == spec.model_id)
                                    & (summary["horizon"] == horizon)]
                if not match.empty:
                    row["n"] = int(match["n"].iloc[0])
                    row["Long-run accuracy"] = float(
                        match["directional_accuracy"].iloc[0])
                    row["vs baseline"] = float(match["mae_advantage"].iloc[0])
            if not recent_summary.empty:
                match = recent_summary.loc[
                    (recent_summary["model_key"] == spec.model_id)
                    & (recent_summary["horizon"] == horizon)]
                if not match.empty:
                    row["Recent accuracy"] = float(
                        match["directional_accuracy"].iloc[-1])
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------- forecast history


HISTORY_COLUMNS = ("Forecast date", "Symbol", "Horizon", "Predicted",
                   "Direction", "Probability", "Realised", "Error", "Correct")


def history(state: ResearchState) -> pd.DataFrame:
    """One row per matured prediction, newest first."""
    if state.performance.empty:
        return pd.DataFrame(columns=list(HISTORY_COLUMNS))
    frame = state.performance
    table = pd.DataFrame({
        "Forecast date": frame["cutoff_at"],
        "Symbol": frame["symbol"],
        "Horizon": frame["horizon"],
        "Predicted": frame["predicted_return"],
        "Direction": frame["predicted_direction"],
        "Probability": frame["probability_positive"],
        "Realised": frame["realised_return"],
        "Error": frame["error"],
        "Correct": frame["directional_correct"],
    })
    return table.sort_values("Forecast date", ascending=False).reset_index(drop=True)


# --------------------------------------------------------- research pipeline


def pipeline() -> pd.DataFrame:
    """Every component the programme has ruled on, and what the ruling was.

    Read from the registry, which carries each closed entry's own evidence
    trail.  This is the surface that makes a rejection visible instead of
    letting it quietly disappear from the app.
    """
    rows = []
    for spec in model_registry.specs():
        if spec.production_status in (model_registry.PRODUCTION,
                                      model_registry.CHALLENGER):
            outcome = ("Live" if spec.production_status
                       == model_registry.PRODUCTION else "Under evaluation")
        elif spec.production_status == model_registry.REJECTED:
            outcome = "Rejected"
        elif spec.production_status == model_registry.RETIRED:
            outcome = "Retired"
        else:
            outcome = "Experimental"
        rows.append({
            "Model": spec.label,
            "Status": spec.production_status,
            "Outcome": outcome,
            "PIT": spec.pit_status,
            "Why": spec.notes or "—",
            "Evidence": "; ".join(spec.evidence) if spec.evidence else "—",
        })
    return pd.DataFrame(rows)


def promotion_requirements(state: ResearchState) -> pd.DataFrame:
    """What each challenger still has to do — the gate, rendered as a to-do.

    This is `promotion.evaluate_promotion` read back as a list of conditions,
    so the answer to "why is nothing being promoted" is on screen rather than
    in a terminal.
    """
    rows = []
    for spec in model_registry.by_status(model_registry.CHALLENGER):
        for horizon in (spec.horizons or ("—",)):
            verdict = promotion.evaluate_promotion(
                spec.model_id, state.performance, horizon)
            for gate in verdict.gates:
                rows.append({
                    "Model": spec.label,
                    "Horizon": horizon,
                    "Decision": verdict.decision,
                    "Gate": gate.name,
                    "Met": bool(gate.passed),
                    "Detail": gate.detail,
                })
    return pd.DataFrame(rows)


# ------------------------------------------------- historical replay study


@dataclasses.dataclass(frozen=True)
class StudyState:
    """The historical replay study, loaded for display and nothing else."""

    path: pathlib.Path
    exists: bool
    performance: pd.DataFrame

    @property
    def has_outcomes(self) -> bool:
        return not self.performance.empty

    @property
    def n_scored(self) -> int:
        return int(len(self.performance))

    @property
    def n_independent_cutoffs(self) -> int:
        return replay_study.independent_cutoff_count(self.performance)

    @property
    def n_symbols(self) -> int:
        if self.performance.empty:
            return 0
        return int(self.performance["symbol"].nunique())

    @property
    def versions(self) -> tuple[str, ...]:
        if self.performance.empty:
            return ()
        return tuple(sorted(self.performance["model_version"].dropna().unique()))


def load_study(path: str | pathlib.Path | None = None) -> StudyState:
    """Read the study, or return an empty state **without creating the file**.

    Same discipline as `load`: `ReplayLedger.__init__` creates its database, so
    a panel that constructed one to find out whether it held anything would
    manufacture the artefact it was asking about.
    """
    target = pathlib.Path(path or replay_study.DEFAULT_STUDY_PATH)
    if not target.exists():
        return StudyState(path=target, exists=False, performance=pd.DataFrame())
    return StudyState(path=target, exists=True,
                      performance=replay_study.load_performance(target))


def study_summary(state: StudyState) -> pd.DataFrame:
    return replay_study.summary_table(state.performance)


def study_actions(state: StudyState) -> pd.DataFrame:
    return replay_study.action_table(state.performance)


def study_versions(state: StudyState) -> pd.DataFrame:
    return replay_study.versions_table(state.performance)


def study_vs_live(state: StudyState, live: ResearchState) -> pd.DataFrame:
    """The two records side by side, on the columns they genuinely share.

    Deliberately a comparison of *coverage and accuracy*, never a pooled
    number.  The study and the prospective ledger answer different questions
    about the same engine, and the row labels say which is which so no reader
    has to infer it from a footnote.
    """
    rows = []

    def describe(label: str, frame: pd.DataFrame, counts_as_evidence: bool) -> None:
        if frame is None or frame.empty:
            rows.append({
                "Record": label, "Scored": 0, "Independent cutoffs": 0,
                "Symbols": 0, "Horizons": "—", "From": None, "To": None,
                "Accuracy": float("nan"), "vs baseline (MAE)": float("nan"),
                "Counts toward promotion": counts_as_evidence,
            })
            return
        called = frame.loc[frame["directional_correct"].notna()]
        rows.append({
            "Record": label,
            "Scored": int(len(frame)),
            "Independent cutoffs": replay_study.independent_cutoff_count(frame),
            "Symbols": int(frame["symbol"].nunique()),
            "Horizons": ", ".join(sorted(frame["horizon"].unique())),
            "From": pd.Timestamp(frame["cutoff_at"].min()).date(),
            "To": pd.Timestamp(frame["cutoff_at"].max()).date(),
            "Accuracy": (float(called["directional_correct"].mean())
                         if len(called) else float("nan")),
            "vs baseline (MAE)": float(
                frame["baseline_relative_absolute_error"].mean()),
            "Counts toward promotion": counts_as_evidence,
        })

    describe("Historical PIT replay (diagnostic)", state.performance, False)
    describe("Live prospective ledger (evidence)", live.performance, True)
    return pd.DataFrame(rows)


def study_warning(state: StudyState) -> str | None:
    """The sentence that must sit above every study number.

    It is not a sample-size caveat.  A study can have a thousand rows and fifty
    independent cutoffs and still not be promotion evidence, because what
    disqualifies it is retrospection, not resolution — so the warning says that
    instead of quoting `n`.
    """
    if not state.exists:
        return ("No historical replay study has been run. "
                f"`{state.path.name}` does not exist.")
    if not state.has_outcomes:
        return ("The study holds forecasts but none has been scored yet. Run "
                "the scoring pass.")
    return (
        "These are **reconstructions**, not forecasts anyone made at the time. "
        "They are back-adjusted for corporate actions that post-date each "
        "cutoff, drawn from today's symbol universe, and produced by someone "
        "who already knew what the market did — so they may inform model "
        "development and may never support a promotion. The prospective "
        "ledger remains the only record that can."
    )


def sample_size_warning(state: ResearchState) -> str | None:
    """The sentence that must sit above every number on these surfaces."""
    if not state.exists:
        return ("No forecast has ever been frozen. `"
                + str(state.ledger_path.name)
                + "` does not exist, so every panel below is empty by fact "
                  "rather than by filter.")
    if not state.has_forecasts:
        return "The ledger exists but holds no forecast yet."
    if not state.has_outcomes:
        return (f"{len(state.forecasts)} forecast(s) frozen, none matured and "
                "scored yet. Performance becomes readable at maturity, not at "
                "the cutoff.")
    draws = state.n_independent_cutoffs
    if draws < MIN_CUTOFFS:
        return (f"{draws} independent cutoff(s) against the {MIN_CUTOFFS} the "
                "promotion policy requires. Numbers below are shown because "
                "hiding them would be its own distortion — but at this "
                "resolution none of them can support a decision.")
    return None
