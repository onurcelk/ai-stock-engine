"""Repository-root test configuration: the fast/slow gate, and only that.

Moved here from `app/tests/conftest.py` on 2026-08-23. A conftest in a
subdirectory registers as a plugin only once collection reaches that
directory, so the `--runslow` option and the marker that honours it existed
only when `app/tests` happened to be part of the run. With `testpaths =
app/tests api/tests` that was true by collection order and invisible -- but
`pytest api/tests` on its own ran every `@pytest.mark.slow` test regardless,
and `pytest api/tests --runslow` failed on an unrecognised option.

The rootdir conftest is always loaded, whatever subset is selected, so the
marker now means the same thing everywhere. Nothing else moved: the fixtures
and the `sys.path` setup stay in `app/tests/conftest.py` where they are used.
"""

from __future__ import annotations

import pytest


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
