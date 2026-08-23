"""Switching the V5 forecast ledger on: live forecasts become evidence.

This module is the boundary between *making* a forecast and *keeping* one.
Everything below it — the ledger, the schema, the scorer, the promotion gate —
was built across Phases 1, 2, 7 and 8 and then deliberately left idle, because
starting the record is a one-way act and the programme wanted its thresholds
chosen on an empty ledger.  That ordering is now discharged: Phase 7's gate,
Phase 9's arithmetic and AB-1's corporate-action policy were all committed
while `app/forecast_ledger.sqlite3` did not exist.

Four properties this module exists to guarantee:

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

**It never freezes on behalf of a machine.**  Added 2026-08-23, after a second
UI made the gap concrete: `writes_blocked` refuses a *production* write from a
test run or from a process that has switched writes off, and returns the
reading regardless.  A prospective ledger is worth having because a person
chose each cutoff; a row appended because a browser prefetched a page is not
that, and after the fact it is indistinguishable from one that is.  The
`provenance` metadata the freeze paths now pass is the other half of the same
correction — the record can finally say which surface asked.
"""

from __future__ import annotations

import dataclasses
import os
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

#: Environment switch for a process that must not add to the production
#: record: set it to `0`, `off`, `false` or `no`.  Intended for an end-to-end
#: run, a browser-automation run, or a demo server -- anything that opens
#: pages the way a person would without a person having chosen to forecast.
WRITES_ENV_VAR = "FORECAST_LEDGER_WRITES"

_OFF = frozenset({"0", "off", "false", "no"})

#: The real production ledger, resolved once at import from the package's own
#: location.
#:
#: Deliberately *not* read back from `forecast_ledger.DEFAULT_PATH` at call
#: time. That attribute is what a hermetic test redirects, so comparing against
#: its current value would invert the guard exactly: it would refuse every
#: suite that isolates itself properly, and stay silent for the one that forgot
#: and is writing to the real file. This constant is the file the redirect
#: exists to protect, and it cannot be moved by moving the redirect.
PRODUCTION_PATH = pathlib.Path(forecast_ledger.DEFAULT_PATH).resolve()


def ledger_path(path: str | pathlib.Path | None = None) -> pathlib.Path:
    return pathlib.Path(path or forecast_ledger.DEFAULT_PATH)


def _same_file(left: pathlib.Path, right: pathlib.Path) -> bool:
    """Path equality that survives Windows case and `..` segments.

    Neither side need exist: `resolve()` on an absent path is defined, and the
    interesting comparison here is precisely against a ledger that a test has
    arranged not to have created yet.
    """
    return (os.path.normcase(str(left.resolve()))
            == os.path.normcase(str(right.resolve())))


def writes_blocked(destination: str | pathlib.Path | None = None) -> str | None:
    """Why this process must not freeze into `destination`, or `None`.

    Only `PRODUCTION_PATH` is defended, and it is compared as a resolved file
    rather than as whatever `forecast_ledger.DEFAULT_PATH` currently points at.
    A caller writing to a scratch path is doing exactly what a hermetic test is
    supposed to do, and refusing it would break every suite that isolates
    itself correctly while letting through the one that forgot.

    Two detectors, both deliberately narrow, because a false positive here
    silently costs a prospective date -- the scarcest thing this programme
    accumulates:

    **A test run.**  `PYTEST_CURRENT_TEST` is set by pytest for the duration of
    every test.  A test that forgets to redirect the ledger is then refused
    instead of appending to the real record, which is the failure mode that
    `forecast_ledger.assert_prospective`'s own docstring records having already
    happened once ("a UI test froze 2023 bars under a 2026 clock").

    **An explicit switch.**  `FORECAST_LEDGER_WRITES=off` for a run that drives
    the UI without a human behind it.  Nothing is inferred from `CI` or the
    like: the collector is run by hand on purpose, and guessing at automation
    would eventually refuse a real collection sweep.
    """
    if not _same_file(ledger_path(destination), PRODUCTION_PATH):
        return None
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return ("a test run may not write to the production forecast ledger "
                "(redirect it with the `path` argument)")
    setting = os.environ.get(WRITES_ENV_VAR, "").strip().lower()
    if setting in _OFF:
        return f"{WRITES_ENV_VAR}={setting} -- production ledger writes are switched off"
    return None


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

    blocked = writes_blocked(destination)
    if blocked:
        # Decided on the destination alone, so a process that must not add to
        # the production record cannot do so by any route through this
        # function. The engine still runs -- refusing to *record* a reading is
        # no reason to withhold it. Reported as `excluded` rather than `error`:
        # nothing went wrong, a write was deliberately not attempted.
        verdict = ultimate.evaluate(symbol, **engine)
        return verdict, FreezeReport(
            active=True, ledger_path=str(destination), excluded=blocked,
        )

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
