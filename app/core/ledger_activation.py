"""Switching the V5 forecast ledger on: live forecasts become evidence.

This module is the boundary between *making* a forecast and *keeping* one.
Everything below it — the ledger, the schema, the scorer, the promotion gate —
was built across Phases 1, 2, 7 and 8 and then deliberately left idle, because
starting the record is a one-way act and the programme wanted its thresholds
chosen on an empty ledger.  That ordering is now discharged: Phase 7's gate,
Phase 9's arithmetic and AB-1's corporate-action policy were all committed
while `app/forecast_ledger.sqlite3` did not exist.

Three properties this module exists to guarantee:

**It never backfills.**  The only way in is `evaluate_and_freeze`, which runs
the live engine *now* against bars that end now and writes the record before
any outcome for it can exist.  There is no path here that reads history and
manufactures a forecast someone might have made.  A prospective date is worth
having precisely because nobody chose it after seeing the outcome.

**It never freezes anything but the live incumbent.**  Uploaded CSVs and
bundled files go through `ultimate.evaluate_offline`, which this module does
not call and cannot reach.  Challengers are excluded by scope: Phase 7 §9
records versioned fitted artefacts as NOT DONE, so a neural challenger's
weights cannot be reproduced from its record and freezing one would accumulate
evidence that cannot be audited.  The deterministic incumbent has no fitted
state — its source hash *is* the model.

**It never fails silently.**  A ledger write that goes wrong is reported to
the caller and surfaced in the UI.  It does not take the forecast down with it
— a user asking for a reading should still get one — but it is never swallowed.
"""

from __future__ import annotations

import dataclasses
import pathlib
from typing import Any

from . import forecast_ledger, ultimate


#: The switch.  `True` since 2026-08-15, on the programme owner's explicit
#: authorisation, after AB-1 was implemented, tested and committed.
#:
#: Setting this to `False` stops new records being written; it does not and
#: must not delete what has been written.  Accumulated prospective dates are
#: the scarcest thing this programme has.
ACTIVE = True

#: Only the deterministic incumbent accumulates for now.  See the module
#: docstring for why challengers are excluded rather than merely deferred.
INCUMBENT_ONLY = True


@dataclasses.dataclass(frozen=True)
class FreezeReport:
    """What the ledger did on one live render, in terms the UI can show.

    Deliberately plain strings and counts rather than record objects: this
    travels through Streamlit's cache, and a report is for reading, not for
    reconstructing a forecast from.
    """

    active: bool
    ledger_path: str
    frozen_ids: tuple[str, ...] = ()
    frozen_horizons: tuple[str, ...] = ()
    skipped_horizons: tuple[str, ...] = ()
    error: str | None = None
    #: Set when freezing was deliberately declined rather than attempted and
    #: failed. Not an error: a scope decision, reported so it is not mistaken
    #: for a silent omission.
    excluded: str | None = None

    @property
    def wrote_anything(self) -> bool:
        return bool(self.frozen_ids)

    @property
    def failed(self) -> bool:
        return self.error is not None

    def summary(self) -> str:
        """One line for a status caption."""
        if not self.active:
            return "Forecast ledger is off; nothing was frozen."
        if self.failed:
            return f"Forecast ledger write FAILED: {self.error}"
        if self.excluded:
            return f"Not frozen: {self.excluded}"
        if self.wrote_anything:
            horizons = ", ".join(self.frozen_horizons)
            return f"Froze {len(self.frozen_ids)} forecast(s): {horizons}."
        if self.skipped_horizons:
            return (
                "Already frozen on these bars; nothing new to record "
                f"({', '.join(self.skipped_horizons)})."
            )
        return "No horizon was available to freeze."


def ledger_path(path: str | pathlib.Path | None = None) -> pathlib.Path:
    return pathlib.Path(path or forecast_ledger.DEFAULT_PATH)


def evaluate_and_freeze(
    symbol: str,
    *,
    include_agents: bool = True,
    model: ultimate.ModelEvidence | None = None,
    horizons: list[ultimate.Horizon] | None = None,
    force: bool = False,
    fetcher: Any = None,
    path: str | pathlib.Path | None = None,
    active: bool | None = None,
    **record_kwargs: Any,
) -> tuple[ultimate.UltimateVerdict, FreezeReport]:
    """Read a live symbol and freeze the incumbent forecast in one pass.

    The engine runs **once**.  Evaluating separately and freezing afterwards
    would fetch twice and could freeze a verdict the user was never shown.

    A failure to write is returned, not raised: the reading is still valid and
    withholding it would help nobody.  The caller is responsible for putting
    `FreezeReport.error` in front of a human, and `streamlit_app` does.
    """
    enabled = ACTIVE if active is None else active
    destination = ledger_path(path)
    # Kept apart deliberately: these five reach the engine, the rest describe
    # the record. Forwarding one bag to both would make the fallback path
    # below raise TypeError exactly when something has already gone wrong.
    engine = dict(
        include_agents=include_agents, model=model,
        horizons=horizons, force=force, fetcher=fetcher,
    )

    if not enabled:
        verdict = ultimate.evaluate(symbol, **engine)
        return verdict, FreezeReport(active=False, ledger_path=str(destination))

    if model is not None:
        # A model-assisted verdict blends a neural reading into the ensemble,
        # and that reading depends on fitted weights which Phase 7 §9 records
        # as NOT versioned. Freezing it would accumulate evidence nobody can
        # later reproduce — the exact thing the incumbent-only scope excludes.
        # Freezing a model-free verdict instead would be worse: the record
        # would not be of the forecast the user was shown.
        verdict = ultimate.evaluate(symbol, **engine)
        return verdict, FreezeReport(
            active=True, ledger_path=str(destination),
            excluded=(
                "model-assisted verdict — challenger freezing stays off until "
                "fitted artefacts are versioned (Phase 7 §9)"
            ),
        )

    # Generate first, and only then decide whether to open a ledger at all.
    # `ForecastLedger.__init__` creates its file, so opening one in order to
    # discover that nothing may be written would manufacture the artefact
    # whose absence Phases 7, 8 and 9 rest on.
    verdict, records = forecast_ledger.generate_incumbent_records(
        symbol, **engine, **record_kwargs
    )
    try:
        forecast_ledger.assert_prospective(records)
    except forecast_ledger.ForecastLedgerError as error:
        return verdict, FreezeReport(
            active=True, ledger_path=str(destination), error=str(error),
        )
    if not records:
        return verdict, FreezeReport(active=True, ledger_path=str(destination))

    try:
        ledger = forecast_ledger.ForecastLedger(destination)
        fresh, skipped = [], []
        for record in records:
            if ledger.has_frozen_input(
                symbol=record.symbol, horizon=record.horizon,
                input_fingerprint=record.input_fingerprint,
            ):
                skipped.append(record.horizon)
            else:
                fresh.append(record)
        ledger.insert_many(fresh)
    except forecast_ledger.ForecastLedgerError as error:
        # The ledger refused the write. The reading is still valid, so return
        # it rather than taking the app down, and carry the reason up so the
        # UI can put it in front of a human instead of losing it.
        return verdict, FreezeReport(
            active=True, ledger_path=str(destination), error=str(error),
        )

    return verdict, FreezeReport(
        active=True,
        ledger_path=str(destination),
        frozen_ids=tuple(record.forecast_id for record in fresh),
        frozen_horizons=tuple(record.horizon for record in fresh),
        skipped_horizons=tuple(skipped),
    )
