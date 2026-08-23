"""Phase 6: the background-job layer.

The registry is tested against trivial work rather than against a real training
run -- an LSTM fold is minutes long and belongs behind `--runslow`, and none of
what is asserted here (states, duplicates, exceptions, restarts, the write
guard) depends on what the work actually computes. The three real bodies are
covered separately: their wiring by source inspection, and their argument
shapes by `--runslow` tests in `test_jobs_slow.py`.
"""

from __future__ import annotations

import inspect
import threading

import pytest

from core import holdings

from api import jobs as jobs_module
from api.jobs import Job, JobRegistry, StaleJob, UnknownJob


@pytest.fixture
def registry():
    made = JobRegistry()
    try:
        yield made
    finally:
        made.shutdown(wait=True)


def _wait(registry_, job, timeout: float = 10.0) -> Job:
    """Poll until the job reaches a terminal state, the way the page does."""
    deadline = threading.Event()
    for _ in range(int(timeout / 0.01)):
        current = registry_.get(job.id)
        if current.finished:
            return current
        deadline.wait(0.01)
    raise AssertionError(f"job {job.id} never finished (state {job.state})")


# ------------------------------------------------------------------ the states


def test_a_job_runs_and_completes(registry):
    job, duplicate = registry.submit("demo", {"n": 1}, lambda _job: {"answer": 42})

    assert duplicate is False
    assert job.state in (jobs_module.QUEUED, jobs_module.RUNNING)

    finished = _wait(registry, job)
    assert finished.state == jobs_module.COMPLETED
    assert finished.result == {"answer": 42}
    assert finished.error is None
    assert finished.progress.fraction == 1.0
    assert finished.started_at and finished.finished_at


def test_a_job_that_raises_fails_and_keeps_the_reason(registry):
    def explode(_job):
        raise ValueError("the model diverged")

    job, _ = registry.submit("demo", {}, explode)
    finished = _wait(registry, job)

    assert finished.state == jobs_module.FAILED
    assert "ValueError: the model diverged" == finished.error
    assert finished.result is None
    assert finished.finished_at, "a failed job must still be terminal"


def test_even_a_baseexception_leaves_a_terminal_state(registry):
    """A page polling a job has no way out of `running` if the worker vanishes."""
    def explode(_job):
        raise KeyboardInterrupt

    job, _ = registry.submit("demo", {}, explode)
    finished = _wait(registry, job)

    assert finished.state == jobs_module.FAILED
    assert "KeyboardInterrupt" in finished.error


def test_progress_travels_from_the_callback_to_the_poll(registry):
    seen = threading.Event()

    def work(job):
        registry.report(job, 0.5, "halfway")
        seen.wait(2)
        return "done"

    job, _ = registry.submit("demo", {}, work)
    for _ in range(500):
        if registry.get(job.id).progress.fraction == 0.5:
            break
        threading.Event().wait(0.01)
    mid = registry.get(job.id)
    assert mid.progress.fraction == 0.5
    assert mid.progress.message == "halfway"
    seen.set()
    _wait(registry, job)


def test_progress_is_clamped(registry):
    def work(job):
        registry.report(job, 5.0, "over")
        return None

    job, _ = registry.submit("demo", {}, work)
    _wait(registry, job)
    assert registry.get(job.id).progress.fraction <= 1.0


def test_work_is_serialised_so_a_queued_job_is_really_queued(registry):
    """One worker, because `clear_session()` is process-global.

    `forecast._train_once` clears the Keras session before every run. A second
    training running alongside would clear the first's session mid-run, so
    concurrency here would corrupt both. Necessary, not sufficient: sequential
    runs still disagree intermittently, which is `forecast.py`'s property and
    not this layer's -- see `api/jobs.py`'s module docstring.
    """
    release = threading.Event()
    order = []

    def first(_job):
        order.append("first-start")
        release.wait(5)
        order.append("first-end")
        return None

    def second(_job):
        order.append("second-start")
        return None

    one, _ = registry.submit("demo", {"i": 1}, first)
    two, _ = registry.submit("demo", {"i": 2}, second)

    for _ in range(500):
        if "first-start" in order:
            break
        threading.Event().wait(0.01)
    assert registry.get(two.id).state == jobs_module.QUEUED

    release.set()
    _wait(registry, one)
    _wait(registry, two)
    assert order == ["first-start", "first-end", "second-start"]


# -------------------------------------------------------------- duplicate jobs


def test_an_identical_request_still_running_is_not_started_twice(registry):
    """Two clicks on a button must not start two five-minute trainings."""
    release = threading.Event()
    started = []

    def work(_job):
        started.append(1)
        release.wait(5)
        return None

    first, dup_first = registry.submit("train", {"symbol": "AAPL"}, work)
    second, dup_second = registry.submit("train", {"symbol": "AAPL"}, work)

    assert dup_first is False
    assert dup_second is True
    assert second.id == first.id

    release.set()
    _wait(registry, first)
    assert started == [1]


def test_key_order_does_not_make_a_request_different(registry):
    release = threading.Event()
    work = lambda _job: release.wait(5)                          # noqa: E731

    first, _ = registry.submit("train", {"a": 1, "b": 2}, work)
    second, duplicate = registry.submit("train", {"b": 2, "a": 1}, work)

    assert duplicate is True and second.id == first.id
    release.set()
    _wait(registry, first)


def test_a_different_request_is_a_different_job(registry):
    release = threading.Event()
    work = lambda _job: release.wait(5)                          # noqa: E731

    first, _ = registry.submit("train", {"symbol": "AAPL"}, work)
    second, duplicate = registry.submit("train", {"symbol": "NVDA"}, work)

    assert duplicate is False and second.id != first.id
    release.set()
    _wait(registry, first)
    _wait(registry, second)


def test_repeating_a_finished_request_starts_a_new_job(registry):
    """Finished is not running. Asking again is a new question, not a duplicate."""
    first, _ = registry.submit("train", {"symbol": "AAPL"}, lambda _job: 1)
    _wait(registry, first)

    second, duplicate = registry.submit("train", {"symbol": "AAPL"}, lambda _job: 1)
    _wait(registry, second)

    assert duplicate is False
    assert second.id != first.id


# --------------------------------------------------------- stale after restart


def test_an_id_from_a_previous_process_is_gone_not_missing(registry):
    """A page polling across a restart is told what happened to its job."""
    with pytest.raises(StaleJob):
        registry.get("job_deadbeefcafe_0001")


def test_an_id_this_process_never_minted_is_simply_unknown(registry):
    with pytest.raises(UnknownJob):
        registry.get("job_not_an_id_at_all")
    with pytest.raises(UnknownJob):
        registry.get(f"job_{jobs_module.BOOT_ID}_9999")


def test_finished_jobs_are_evicted_oldest_first():
    small = JobRegistry(max_finished=3)
    try:
        made = []
        for index in range(6):
            job, _ = small.submit("demo", {"i": index}, lambda _job: None)
            made.append(job)
            _wait(small, job)

        kept = [job.id for job in small.list()]

        # Bounded, newest kept, oldest gone. Not an exact count: eviction runs
        # at submit time and never drops a job that is still in flight, so the
        # registry can hold the cap plus whatever is running.
        assert len(kept) <= 4
        assert made[-1].id in kept
        assert made[0].id not in kept
        with pytest.raises(UnknownJob):
            small.get(made[0].id)
    finally:
        small.shutdown(wait=True)


# ----------------------------------------------------- no writes from a worker


def test_a_job_cannot_move_the_book(registry, tmp_path, monkeypatch):
    """The guarantee: a background job cannot execute a real trade.

    Not because nothing in a job body calls `holdings` today -- the test below
    asserts that too -- but because if something ever does, it raises rather
    than trading.
    """
    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")

    def rogue(_job):
        return holdings.execute("buy", "AAPL", 1, 100.0)

    job, _ = registry.submit("demo", {}, rogue)
    finished = _wait(registry, job)

    assert finished.state == jobs_module.FAILED
    assert "WritesDisabledError" in finished.error
    assert not (tmp_path / "holdings.json").exists()
    assert not (tmp_path / "transactions.json").exists()


def test_the_guard_is_per_thread_not_per_process(tmp_path, monkeypatch):
    """A trade ticket in a concurrent request must keep working while a job runs."""
    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")

    inside = threading.Event()
    finish = threading.Event()

    def worker():
        with holdings.writes_disabled("a background job"):
            inside.set()
            finish.wait(5)

    thread = threading.Thread(target=worker)
    thread.start()
    assert inside.wait(5)

    # This thread was never disarmed, so the trade goes through as normal.
    transaction = holdings.execute("buy", "AAPL", 1, 100.0)
    assert transaction.symbol == "AAPL"

    finish.set()
    thread.join(5)

    # And the arming was undone when the block exited.
    assert holdings.execute("sell", "AAPL", 1, 101.0).symbol == "AAPL"


def test_writes_are_re_enabled_even_if_the_body_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")

    with pytest.raises(RuntimeError):
        with holdings.writes_disabled("a background job"):
            raise RuntimeError("boom")

    assert holdings.execute("buy", "AAPL", 1, 100.0).symbol == "AAPL"


@pytest.mark.parametrize("call", [
    lambda: holdings.execute("buy", "AAPL", 1, 100.0),
    lambda: holdings.save([]),
    lambda: holdings.save_ledger([]),
])
def test_every_writer_in_holdings_is_guarded(call, tmp_path, monkeypatch):
    monkeypatch.setattr(holdings, "STORE", tmp_path / "holdings.json")
    monkeypatch.setattr(holdings, "LEDGER", tmp_path / "transactions.json")

    with holdings.writes_disabled("a background job"):
        with pytest.raises(holdings.WritesDisabledError):
            call()


def test_no_job_body_reaches_the_portfolio_at_all():
    """The structural half: the job router does not import or name `holdings`.

    Same discipline as `test_collector.py::test_the_collector_delegates_and_-
    invents_nothing`. The runtime guard above catches a call that gets added;
    this catches it at the point someone writes it.
    """
    from api.routers import jobs as jobs_router

    source = inspect.getsource(jobs_router)
    code = "".join(source.split('"""')[::2])
    code = "\n".join(line for line in code.splitlines()
                     if not line.strip().startswith("#"))

    for forbidden in ("holdings", "execute(", "save_ledger(", "portfolio."):
        assert forbidden not in code, forbidden


def test_the_registry_arms_the_guard_for_every_job():
    """The arming is in the registry, not in each body, so it cannot be
    forgotten by whoever adds the fourth kind of job."""
    source = inspect.getsource(jobs_module.JobRegistry._run)
    assert "writes_disabled" in source
