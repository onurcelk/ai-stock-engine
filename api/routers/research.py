"""Phase 5: GET /api/research.

Wraps `core.research_view` unmodified. That module's own docstring states the
rule this endpoint inherits whole: **build the surface from stored evidence,
not recomputed hindsight.** It fits nothing, calls no model, regenerates no
forecast and writes nothing, and neither does this.

One property is load-bearing and easy to destroy from here.
`ForecastLedger.__init__` and `ReplayLedger.__init__` *create* their SQLite
files, so constructing one to find out whether it holds anything manufactures
the very artefact whose absence Phase 7 §6 and Phase 9 §6 rest on.
`research_view.load()` and `load_study()` check for the file first and return
an empty state without constructing anything -- so this router calls them with
**no path argument** and never touches `forecast_ledger.ForecastLedger`
directly. Opening a page must not start a record.

Everything is served from one request because the tab reads one state: thirteen
surfaces built from a single `load()`, so no two of them can disagree about
what the ledger held at the moment they were read.

The warnings are part of the payload, not decoration around it. A reader who
sees hundreds of scored replay rows above two frozen ones will otherwise draw
exactly the wrong conclusion, and `study_warning` is the sentence that stops
them -- it is carried through verbatim rather than restated.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from core import research_view

from ..schemas import to_jsonable

router = APIRouter()


def table(frame: pd.DataFrame | None) -> dict:
    """A frame as columns plus rows.

    Columns travel with the data because these frames genuinely differ in
    shape -- `quality` and `leaderboard` carry whatever the record happened to
    hold -- so a caller that hardcoded column names would silently drop new
    ones. An empty frame keeps its columns where it has them: knowing which
    measurements *would* be there is itself information about coverage.
    """
    if frame is None:
        return {"columns": [], "rows": []}
    return {
        "columns": [str(c) for c in frame.columns],
        "rows": to_jsonable(frame.to_dict(orient="records")),
    }


@router.get("/api/research")
def get_research() -> dict:
    state = research_view.load()
    study = research_view.load_study()

    return {
        "exists": state.exists,
        "ledger_name": state.ledger_path.name,
        "counts": {
            "forecasts": len(state.forecasts),
            "outcomes": len(state.outcomes),
            "independent_cutoffs": state.n_independent_cutoffs,
            "min_cutoffs": research_view.MIN_CUTOFFS,
        },
        # Shown rather than hidden: at this resolution the numbers below cannot
        # support a decision, and the warning is what says so.
        "warning": research_view.sample_size_warning(state),
        "thin": state.thin,
        "has_forecasts": state.has_forecasts,
        "has_outcomes": state.has_outcomes,

        "production": table(research_view.production_panel(state)),
        "weights": table(research_view.active_weights(state)),
        "quality": table(research_view.quality(state)),
        "calibration": table(research_view.calibration(state)),
        "rolling": table(research_view.rolling(state)),
        "leaderboard": table(research_view.leaderboard(state)),
        "history": table(research_view.history(state)),
        "promotion_requirements": table(
            research_view.promotion_requirements(state)),
        "pipeline": table(research_view.pipeline()),

        "study": {
            "exists": study.exists,
            "name": study.path.name,
            # Not a sample-size caveat: what disqualifies a replay is
            # retrospection, not resolution.
            "warning": research_view.study_warning(study),
            "has_outcomes": study.has_outcomes,
            "n_scored": study.n_scored,
            "n_independent_cutoffs": study.n_independent_cutoffs,
            "n_symbols": study.n_symbols,
            "versions": list(study.versions),
            "summary": table(research_view.study_summary(study)),
            "actions": table(research_view.study_actions(study)),
            "versions_table": table(research_view.study_versions(study)),
            "vs_live": table(research_view.study_vs_live(study, state)),
        },
    }
