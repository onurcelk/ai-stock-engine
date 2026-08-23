"""Repository-root test configuration: the fast/slow gate and the backup guard.

Both are here for the same reason. A conftest in a subdirectory registers as a
plugin only once collection reaches that directory, so anything defined in
`app/tests/conftest.py` applies to a run that selects another directory only by
accident of collection order.

`--runslow` moved here on 2026-08-23: with `testpaths = app/tests api/tests` the
gate worked by ordering and looked fine, but `pytest api/tests` on its own ran
every `@pytest.mark.slow` test regardless, and `pytest api/tests --runslow`
failed on an unrecognised option.

`never_touch_the_backup_drive` moved here at Phase 7, the cutover, for the
identical reason and a sharper one. `app/tests/conftest.py` justified holding
it by noting that "`run_app.py` is the only thing that installs the lifecycle
hooks, and no test imports it" -- true while the only launcher was Streamlit's.
It is not true now: `api/main.py`'s own `lifespan` installs them, so a test
that opened the app as a context manager (`with TestClient(app)`) would run a
real backup. Hermetic by construction, not by collection order.

Nothing else moved: the fixtures and the `sys.path` setup stay in
`app/tests/conftest.py` where they are used.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

_APP = pathlib.Path(__file__).resolve().parent / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))


@pytest.fixture(autouse=True, scope="session")
def never_touch_the_backup_drive():
    """No automated run may write to `D:\\prediction market backup`, ever.

    The backup drive holds copies of prospective forecasts that cannot be
    regenerated. Tests that want backup behaviour pass their own `tmp_path`
    root explicitly; this stops anything that forgets -- a default argument, an
    application lifespan, a launcher imported by accident -- from reaching the
    real drive.
    """
    from core import ledger_backup

    os.environ[ledger_backup.DISABLE_ENV] = "1"
    yield
    os.environ.pop(ledger_backup.DISABLE_ENV, None)


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False,
                     help="also run tests that train a model or boot the app")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="needs --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
