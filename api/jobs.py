"""Phase 6: long-running work, started by a POST and polled by a GET.

Training an LSTM or a reinforcement-learning policy takes minutes. Streamlit
could run one inline because a script rerun *is* the request, and its progress
bar is a widget being redrawn in place; an HTTP request cannot hold that open.
So the work moves to a worker thread, the request returns an id, and the page
polls `GET /api/jobs/{id}` for the progress the existing `on_progress`/
`progress` callbacks were already emitting. Nothing about the training code
changes -- this is the plumbing that carries a callback it already had.

**One worker, deliberately.** `forecast._train_once` calls
`tf.keras.backend.clear_session()` before every run, and Phase B identified
that call as what removes a projection's dependence on how many ran before it
in the same process. That state is process-global, so two trainings running
concurrently would clear each other's session mid-run -- a single worker is
necessary for a projection to mean anything, not a decision about CPU. It also
makes `queued` a real state rather than a decorative one.

It is necessary and **not sufficient**: measured on 2026-08-23, two identical
`forecast.project` calls in one process on the main thread, no jobs involved,
still disagree intermittently (see `reports/PHASEB_REPRODUCIBILITY.md`'s
appended note). Nothing in this file causes that and nothing here can fix it --
it is recorded so that a number arriving through a job is not mistaken for a
more reproducible number than the same call makes anywhere else.

**Nothing here can move the book.** Every job body runs inside
`holdings.writes_disabled(...)`, so `execute`, `save` and `save_ledger` raise
if anything in a job ever reaches them. Today nothing does -- `forecast`,
`agents` and `backtest` do not import `holdings`, and a test asserts that --
but a job body is exactly the kind of place where "score it and rebalance"
gets added later, away from the request that would have authorised it.

**Restarts are visible, not silent.** The registry is in memory, so a restart
loses every job. A page polling an id across one must be told that, rather
than getting a 404 that reads like "wrong id". Ids carry the boot they were
minted in, so an id from a previous process is answered `410 Gone` with the
reason, and only a genuinely unknown id from this one is a 404.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"

#: Terminal states. A job in one of these will never change again.
FINISHED = frozenset({COMPLETED, FAILED})

#: Finished jobs kept before the oldest are dropped. One local user polling
#: one page will not come close; the cap exists so a long-lived server cannot
#: grow without bound.
MAX_FINISHED = 200

#: Minted once per process. Every job id carries it, which is what lets a poll
#: after a restart be answered accurately instead of as a missing id.
BOOT_ID = uuid.uuid4().hex[:12]


class UnknownJob(LookupError):
    """No such job in this process."""


class StaleJob(LookupError):
    """A real id, from a process that is no longer running."""


@dataclasses.dataclass
class Progress:
    """How far along, in the two forms a UI wants: a fraction and a sentence."""

    fraction: float = 0.0
    message: str = ""

    def as_dict(self) -> dict:
        return {"fraction": self.fraction, "message": self.message}


@dataclasses.dataclass
class Job:
    id: str
    kind: str
    key: str
    params: dict
    state: str = QUEUED
    progress: Progress = dataclasses.field(default_factory=Progress)
    result: Any = None
    error: str | None = None
    #: Kept for whoever attaches to the process, deliberately not serialised:
    #: `error` is the sentence a page can show, and a Python traceback is not.
    traceback: str | None = None
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def finished(self) -> bool:
        return self.state in FINISHED

    def as_dict(self, *, include_result: bool = True) -> dict:
        body = {
            "id": self.id,
            "kind": self.kind,
            "state": self.state,
            "params": self.params,
            "progress": self.progress.as_dict(),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }
        if include_result:
            body["result"] = self.result
        return body


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def job_key(kind: str, params: dict) -> str:
    """A stable digest of what was asked for, used to spot a duplicate.

    Sorted and JSON-encoded so two requests that differ only in key order --
    which is to say, do not differ -- collide as they should.
    """
    payload = json.dumps({"kind": kind, "params": params}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class JobRegistry:
    """Every job this process knows about, and the one thread that runs them."""

    def __init__(self, *, max_finished: int = MAX_FINISHED) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._futures: dict[str, Future] = {}
        self._order: list[str] = []
        self._counter = 0
        self._max_finished = max_finished
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="job")

    # ------------------------------------------------------------- submitting

    def submit(
        self,
        kind: str,
        params: dict,
        work: Callable[[Job], Any],
    ) -> tuple[Job, bool]:
        """Queue `work`, or hand back the job already doing it.

        Returns `(job, is_duplicate)`. A duplicate is an *identical* request --
        same kind, same parameters -- that is still queued or running. Two
        clicks on a button, or a page remounting mid-request, must not start a
        second five-minute training run; an identical request whose earlier job
        has *finished* is a new one, because the caller may well want it again.
        """
        key = job_key(kind, params)
        with self._lock:
            for existing in self._jobs.values():
                if existing.key == key and not existing.finished:
                    return existing, True

            self._counter += 1
            job = Job(
                id=f"job_{BOOT_ID}_{self._counter:04d}",
                kind=kind, key=key, params=params, created_at=_now(),
            )
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._evict()
            self._futures[job.id] = self._executor.submit(self._run, job, work)
            return job, False

    def _run(self, job: Job, work: Callable[[Job], Any]) -> None:
        from core import holdings

        with self._lock:
            job.state = RUNNING
            job.started_at = _now()
        try:
            # Armed for this worker thread only, so a trade ticket in a
            # concurrent request is unaffected.
            with holdings.writes_disabled(f"running background job {job.id}"):
                result = work(job)
        except BaseException as error:                            # noqa: BLE001
            # Every exception, not just Exception: a job that dies of a
            # KeyboardInterrupt or a MemoryError must still leave a terminal
            # state behind, or the page polls a running job forever.
            with self._lock:
                job.error = f"{type(error).__name__}: {error}"
                job.traceback = traceback.format_exc()
                job.finished_at = _now()
                job.state = FAILED                       # published last
            return
        with self._lock:
            # `state` is assigned last on purpose. A reader takes the lock to
            # find the job and then serialises it outside, so `state` is the
            # flag it keys on -- flipping it before `result` was attached would
            # let a poll see `completed` with nothing in it, exactly once, at
            # the end of a five-minute training.
            job.result = result
            job.progress = Progress(fraction=1.0, message=job.progress.message)
            job.finished_at = _now()
            job.state = COMPLETED

    # -------------------------------------------------------------- reporting

    def report(self, job: Job, fraction: float, message: str) -> None:
        """Called from inside the worker, on every progress callback."""
        with self._lock:
            job.progress = Progress(
                fraction=max(0.0, min(1.0, float(fraction))), message=message)

    # ---------------------------------------------------------------- reading

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                self._reconcile(job)
                return job
        if _is_from_another_boot(job_id):
            raise StaleJob(job_id)
        raise UnknownJob(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            jobs = [self._jobs[i] for i in self._order if i in self._jobs]
            for job in jobs:
                self._reconcile(job)
            return list(reversed(jobs))

    def _reconcile(self, job: Job) -> None:
        """Repair a job whose worker died without recording an outcome.

        `_run` records a terminal state in a `finally`-equivalent for every
        exception, so this should never fire. It exists because "should never"
        and "cannot" are different, and the failure it covers -- a job stuck at
        `running` forever -- is one a polling page has no way out of.
        """
        if job.finished:
            return
        future = self._futures.get(job.id)
        if future is None or not future.done():
            return
        error = future.exception()
        job.error = (
            f"{type(error).__name__}: {error}" if error else
            "the worker finished without recording a result"
        )
        job.finished_at = _now()
        job.state = FAILED                               # published last

    def _evict(self) -> None:
        """Drop the oldest finished jobs once there are too many.

        The cap counts *finished* jobs only, and eviction runs when a new job
        is submitted. A job still queued or running is never dropped, however
        old, because something is polling it -- so the registry can briefly
        hold `max_finished` plus whatever is in flight.
        """
        finished = [i for i in self._order
                    if i in self._jobs and self._jobs[i].finished]
        for job_id in finished[:max(0, len(finished) - self._max_finished)]:
            self._jobs.pop(job_id, None)
            self._futures.pop(job_id, None)
            self._order.remove(job_id)

    # ---------------------------------------------------------------- shutdown

    def shutdown(self, *, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)


def _is_from_another_boot(job_id: str) -> bool:
    """Is this a well-formed id that this process did not mint?"""
    parts = job_id.split("_")
    return (len(parts) == 3 and parts[0] == "job"
            and parts[1] != BOOT_ID and parts[2].isdigit())


#: The one registry the app serves from. Module-level for the same reason
#: `holdings.STORE` is: one process, one of these, and a test replaces it by
#: name rather than by threading it through every endpoint.
REGISTRY = JobRegistry()
