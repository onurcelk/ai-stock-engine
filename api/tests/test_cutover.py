"""Phase 7: what the cutover asserted, so it cannot quietly come undone.

The rebuild was verified page by page against Streamlit and the final
retirement audit came back clean. That audit was a diff run by hand on
2026-08-23; these are the parts of it a machine can keep re-running.

Four properties, each protecting a different way the cutover could rot:

**The desk does not depend on Streamlit.** Structural and transitive -- an
`import streamlit` anywhere in the graph the API reaches would make the
fallback a dependency of the product, which is the opposite of a cutover.

**Every endpoint the cutover shipped is still served.** The frontend is a
separate repository; a route deleted here fails there, at runtime, on a page
nobody happened to open that day.

**The four retired capabilities stay retired.** They were retired by an owner
decision recorded in `reports/NEXT_STEPS_ROADMAP.md`, not by oversight. Any of
them reappearing should be a deliberate act with a decision behind it, not a
convenience someone adds while passing.

**The server owns the ledger backup, and the launcher owns the freeze.** The
two halves of the lifecycle that Phase 7 moved. Getting either backwards is
silent: a missing backup looks like nothing, and a freeze on boot looks like
a productive collector.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "api"
CORE_DIR = REPO_ROOT / "app" / "core"


def _api_sources() -> list[pathlib.Path]:
    """Every module the service is built from. Its own tests are not part of
    the service, and a fixture is allowed to import whatever it needs."""
    return sorted(
        path for path in API_DIR.rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts
    )


def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _core_imports(tree: ast.Module, *, inside_core: bool) -> set[str]:
    """Which `core.*` modules this file pulls in, absolute or relative.

    Relative forms only count inside `core` itself, where `from . import
    ultimate` and `from .foo import bar` are how the package refers to itself.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "core" or alias.name.startswith("core."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if not inside_core:
                    continue
                base = "core" if not node.module else f"core.{node.module}"
            else:
                base = node.module or ""
            if base == "core":
                found |= {f"core.{alias.name}" for alias in node.names}
            elif base.startswith("core."):
                found.add(base)
    return found


def _imports_streamlit(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "streamlit"
                   for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if not node.level and (node.module or "").split(".")[0] == "streamlit":
                return True
    return False


def _reachable_core_modules() -> dict[str, pathlib.Path]:
    """Close the API's `core` imports over `core`'s own imports.

    A direct scan of `api/` would miss the case that actually matters: an
    endpoint importing a clean module that itself imports `core.theme`, which
    imports Streamlit. Depth is where this would go wrong, so the walk goes to
    the bottom.
    """
    pending = set()
    for path in _api_sources():
        pending |= _core_imports(_parse(path), inside_core=False)

    resolved: dict[str, pathlib.Path] = {}
    while pending:
        name = pending.pop()
        if name in resolved:
            continue
        module_file = CORE_DIR / f"{name.split('.')[-1]}.py"
        if not module_file.exists():
            # `from core import SOME_CONSTANT` -- a name, not a module.
            continue
        resolved[name] = module_file
        pending |= _core_imports(_parse(module_file), inside_core=True)
    return resolved


# ------------------------------------------------ the desk is Streamlit-free


def test_no_api_module_imports_streamlit():
    offenders = [str(path.relative_to(REPO_ROOT))
                 for path in _api_sources() if _imports_streamlit(_parse(path))]
    assert offenders == []


def test_nothing_the_api_reaches_imports_streamlit():
    """Transitive, because the two presentation-only `core` modules are real.

    `core/theme.py` and `core/axis_drag.py` do import Streamlit -- they are the
    2 of ~28 the Phase D survey found, and they are why this test walks the
    graph instead of grepping `api/`. Reaching either of them from an endpoint
    would put the fallback back underneath the product.
    """
    reachable = _reachable_core_modules()
    assert reachable, "the walk resolved nothing -- the resolver is broken"

    offenders = sorted(name for name, path in reachable.items()
                       if _imports_streamlit(_parse(path)))
    assert offenders == []


def test_the_walk_would_notice_theme():
    """Guards the test above: it must be the walk doing the work.

    A resolver that silently found nothing would pass the real test forever.
    `core.theme` is known to import Streamlit, so detecting it is the proof
    the detector works, and its absence from the reachable set is the result.
    """
    assert _imports_streamlit(_parse(CORE_DIR / "theme.py"))
    assert "core.theme" not in _reachable_core_modules()


# ------------------------------------------------------- the endpoint surface


#: Every route the API served at the cutover, 2026-08-23. Additions are free;
#: this list exists so a removal has to be a deliberate edit here as well.
CUTOVER_ROUTES = [
    ("GET", "/api/agents"),
    ("GET", "/api/basket"),
    ("GET", "/api/basket/options"),
    ("GET", "/api/health"),
    ("GET", "/api/jobs"),
    ("POST", "/api/jobs/agent"),
    ("POST", "/api/jobs/project"),
    ("POST", "/api/jobs/walkforward"),
    ("GET", "/api/jobs/{job_id}"),
    ("GET", "/api/models"),
    ("GET", "/api/montecarlo/{symbol}"),
    ("GET", "/api/ohlcv/{symbol}"),
    ("GET", "/api/portfolio"),
    ("POST", "/api/portfolio/ledger/clear"),
    ("POST", "/api/portfolio/trade"),
    ("GET", "/api/research"),
    ("GET", "/api/runs"),
    ("POST", "/api/runs/clear"),
    ("DELETE", "/api/runs/{run_id}"),
    ("GET", "/api/runs/{run_id}"),
    ("GET", "/api/signal/{symbol}"),
    ("POST", "/api/signal/{symbol}/freeze"),
    ("GET", "/api/sources"),
    ("GET", "/api/stats/{symbol}"),
    ("GET", "/api/strategies"),
    ("POST", "/api/strategies/upload"),
    ("GET", "/api/strategies/{symbol}"),
    ("GET", "/api/studies"),
    ("GET", "/api/studies/{symbol}"),
    ("GET", "/api/watchlist"),
]


def _served() -> set[tuple[str, str]]:
    from api.main import app

    spec = app.openapi()
    return {(method.upper(), path)
            for path, operations in spec["paths"].items()
            for method in operations}


@pytest.mark.parametrize("method,path", CUTOVER_ROUTES,
                         ids=[f"{m} {p}" for m, p in CUTOVER_ROUTES])
def test_every_endpoint_the_cutover_shipped_is_still_served(method, path):
    assert (method, path) in _served()


def test_reading_the_surface_is_still_safe():
    """The read/write split, stated once rather than inferred per endpoint.

    Everything that changes something the desk cannot regenerate -- the book,
    the transaction ledger, the forecast ledger, a saved run -- is a POST or a
    DELETE. Phase 6a's whole finding was a safe method that wrote, so this is
    the shape of that mistake, checked at the level of the route table.
    """
    reads = {path for method, path in _served() if method == "GET"}
    for path in reads:
        assert not path.endswith(("/freeze", "/trade", "/clear")), path


# ----------------------------------------------- the four retired capabilities


#: Retired by owner decision at the cutover. `reports/NEXT_STEPS_ROADMAP.md`,
#: "Streamlit retirement audit (2026-08-23, FINAL -- clean)".
RETIRED_ATTRIBUTES = {
    ("forecast", "run"): "single-split forecasting; walk_forward and project "
                         "are the supported paths",
    ("forecast", "estimate_train_seconds"): "the pre-run time estimate; the "
                                            "job API makes the wait explicit",
    ("ultimate", "ModelEvidence"): "the model-assisted verdict",
    ("holdings", "editable"): "editing positions directly, bypassing the "
                              "transaction ledger",
    ("holdings", "from_frame"): "editing positions directly, bypassing the "
                                "transaction ledger",
}

#: The other half of the model-assisted verdict: a toggle rather than a type.
RETIRED_KEYWORD = "include_agents"


def _attribute_uses(tree: ast.Module) -> set[tuple[str, str]]:
    return {
        (node.value.id, node.attr)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }


def test_no_retired_capability_is_reachable_from_the_api():
    offences = []
    for path in _api_sources():
        tree = _parse(path)
        for use in _attribute_uses(tree) & set(RETIRED_ATTRIBUTES):
            offences.append(f"{path.name}: {use[0]}.{use[1]} -- retired "
                            f"({RETIRED_ATTRIBUTES[use]})")
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == RETIRED_KEYWORD:
                offences.append(f"{path.name}: {RETIRED_KEYWORD}= -- retired "
                                "(the engine default stands)")
    assert offences == []


def test_the_engine_still_has_them():
    """Guards the test above, and records what "retired" means here.

    Retiring a capability was a decision about the *product surface*. Nothing
    was deleted from `core`, and deleting any of it would re-version modules
    the forecast ledger identifies by source hash. So the assertion is that
    the API does not reach them -- not that they stopped existing.
    """
    import inspect

    from core import forecast, holdings, ultimate

    assert callable(forecast.run)
    assert callable(forecast.estimate_train_seconds)
    assert hasattr(ultimate, "ModelEvidence")
    assert callable(holdings.editable)
    assert "include_agents" in inspect.signature(ultimate.evaluate).parameters


# --------------------------------------------------- the two lifecycle halves


def test_the_server_owns_the_ledger_backup():
    """`api/main.py`'s lifespan is the hook Streamlit never had."""
    import inspect

    from api import main

    source = inspect.getsource(main.lifespan)
    assert "ledger_lifecycle.start()" in source
    assert "ledger_lifecycle.shutdown()" in source


def test_the_lifespan_actually_runs_both_hooks(monkeypatch):
    """Behavioural, not just structural: enter and leave the app, count calls.

    Spies rather than a redirected backup root, because what is under test is
    the wiring. `ledger_backup` has its own suite for whether a snapshot is
    correct, and this one must not be able to write a file at all.
    """
    from fastapi.testclient import TestClient

    from api import main
    from core import ledger_lifecycle

    calls = []
    monkeypatch.setattr(ledger_lifecycle, "start",
                        lambda **_: calls.append("start"))
    monkeypatch.setattr(ledger_lifecycle, "shutdown",
                        lambda **_: calls.append("shutdown"))

    with TestClient(main.app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert calls == ["start"]          # not yet shut down

    assert calls == ["start", "shutdown"]


def test_a_test_run_still_cannot_reach_the_backup_drive():
    """The guard the lifespan made load-bearing, asserted rather than assumed.

    Before the cutover the only thing installing these hooks was `run_app.py`,
    which no test imports -- so `app/tests/conftest.py` could hold the guard
    and nothing would notice that a run selecting only `api/tests` never loaded
    it. The lifespan changed that: opening the app as a context manager, as the
    test above does, now runs the real hooks. The guard moved to the rootdir
    conftest so it is loaded whatever subset is selected, and this is the
    assertion that it was.
    """
    import os

    from core import ledger_backup

    assert os.environ.get(ledger_backup.DISABLE_ENV)
    outcome = ledger_backup.backup_if_changed(reason="test-probe")
    assert outcome.status == ledger_backup.UNCHANGED
    assert outcome.reason == "disabled"


def test_the_server_does_not_freeze_forecasts_at_boot():
    """The prospective sweep belongs to a launcher, not to a server's startup.

    `uvicorn --reload` restarts on every file save. A boot that froze the
    collection universe would fill the one record this programme cannot
    regenerate with rows nobody chose -- the same hazard Phase 6a took off
    `GET /api/signal`, arriving by a different door.

    Read from the parsed AST rather than from the text, on Phase 6d's
    precedent: the docstring above is then free to name the very modules the
    module promises not to reach.
    """
    tree = _parse(API_DIR / "main.py")

    imported = _core_imports(tree, inside_core=False)
    assert "core.startup" not in imported
    assert "core.collector" not in imported
    assert "core.replay" not in imported

    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)}
    assert "collect_then_replay" not in called
    assert "collect" not in called
