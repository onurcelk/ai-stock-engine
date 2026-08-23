"""Start the desk: the FastAPI service and the Next.js frontend, together.

    python run_desk.py                # the desk, on http://localhost:3000
    python run_desk.py --dev          # Next in dev mode (hot reload)
    python run_desk.py --api-only     # just the API, on :8000
    python run_desk.py --no-collect   # skip the startup freeze/replay
    python run_desk.py --no-browser   # do not open a tab

Phase 7, the cutover.  This replaces `run_app.py` as the way the desk is
opened; `run_app.py` still starts the Streamlit fallback, and both are
described in `CLAUDE.md` section 9.

**What this owns that neither server does.**  Two processes serve the desk and
neither of them is the right place for the things that must happen once, at the
start and the end of a session:

*The prospective freeze, then the missed-day replays.*  `core.startup
.collect_then_replay` -- the same sequence, in the same order, that
`run_app.py` has always run.  It appends to the append-only forecast ledger, so
it belongs to a process a person started rather than to an HTTP server's boot,
which `uvicorn --reload` repeats on every file save.

*The ledger backup lifecycle.*  A recovery snapshot on the way in, a snapshot
on the way out.  `api/main.py` installs the same hooks on its own lifespan, so
the guarantee holds for someone who starts uvicorn by hand too; both are
fingerprint-guarded, so the second one to run on an unchanged ledger writes
nothing.

**Why the frontend path is configurable.**  `design-system/shell` is a separate
git repository sitting beside this one, not a subdirectory of it.  The default
below is the layout on this machine; `DESK_FRONTEND` overrides it, and if the
directory is not there the API still comes up and says so rather than failing.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

REPO_ROOT = pathlib.Path(__file__).resolve().parent
APP_DIR = REPO_ROOT / "app"
sys.path.insert(0, str(APP_DIR))

from core import ledger_lifecycle, startup          # noqa: E402

#: Beside this repository, not inside it. See the module docstring.
DEFAULT_FRONTEND = REPO_ROOT.parent / "design-system" / "shell"

API_PORT = int(os.environ.get("DESK_API_PORT", "8000"))
WEB_PORT = int(os.environ.get("DESK_WEB_PORT", "3000"))

#: How long a cold start may take before we stop waiting and report it. The
#: API imports TensorFlow through `core`, which is tens of seconds on a cold
#: filesystem cache, so this is generous on purpose.
STARTUP_TIMEOUT_SECONDS = 180


def frontend_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("DESK_FRONTEND", str(DEFAULT_FRONTEND)))


def _responds(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except urllib.error.HTTPError:
        # A 4xx is still a server answering, which is all this asks.
        return True
    except Exception:                                            # noqa: BLE001
        return False


def _wait_for(url: str, process: subprocess.Popen, label: str) -> bool:
    """Poll `url` until it answers, the process dies, or we run out of patience.

    Watching the process matters as much as watching the port: a server that
    exited on "address already in use" would otherwise be waited on for three
    minutes and then reported as slow rather than as dead.
    """
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(f"[desk] {label} exited with code {process.returncode} "
                  f"before it served {url}", file=sys.stderr)
            return False
        if _responds(url):
            return True
        time.sleep(0.5)
    print(f"[desk] {label} did not answer {url} within "
          f"{STARTUP_TIMEOUT_SECONDS}s", file=sys.stderr)
    return False


def _stop(process: subprocess.Popen | None, label: str) -> None:
    """End a child and everything it spawned.

    `terminate()` alone is not enough on Windows: it ends the process it names
    and orphans its children, and `next start` runs its server in one. The
    whole tree has to go or the port stays held and the next launch fails on
    "address already in use" -- which reads like a bug in the launcher rather
    than a leftover from the last run.
    """
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            process.terminate()
        process.wait(timeout=20)
    except Exception as error:                                   # noqa: BLE001
        print(f"[desk] could not stop {label}: {error}", file=sys.stderr)


def start_api(*, reload: bool = False) -> subprocess.Popen:
    command = [sys.executable, "-m", "uvicorn", "api.main:app",
               "--port", str(API_PORT)]
    if reload:
        command.append("--reload")
    print(f"[desk] API      http://localhost:{API_PORT}")
    return subprocess.Popen(command, cwd=str(REPO_ROOT))


def start_frontend(*, dev: bool) -> subprocess.Popen | None:
    directory = frontend_dir()
    if not (directory / "package.json").exists():
        print(f"[desk] no frontend at {directory} -- API only. Set "
              f"DESK_FRONTEND to point at design-system/shell.",
              file=sys.stderr)
        return None

    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        print("[desk] npm is not on PATH -- API only.", file=sys.stderr)
        return None

    built = (directory / ".next" / "BUILD_ID").exists()
    if not dev and not built:
        print("[desk] no production build in .next -- starting in dev mode. "
              "Run `npm run build` there for the faster one.", file=sys.stderr)
    script = "dev" if (dev or not built) else "start"

    environment = dict(os.environ)
    # The frontend reads this at build time for a production build and at
    # runtime in dev; setting it here keeps a non-default API port working
    # without editing the other repository.
    environment.setdefault("NEXT_PUBLIC_API_BASE", f"http://localhost:{API_PORT}")
    environment.setdefault("PORT", str(WEB_PORT))

    print(f"[desk] frontend http://localhost:{WEB_PORT}  (npm run {script})")
    return subprocess.Popen([npm, "run", script], cwd=str(directory),
                            env=environment, shell=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start the desk: the API and the Next.js frontend.")
    parser.add_argument("--dev", action="store_true",
                        help="run Next in dev mode and uvicorn with --reload")
    parser.add_argument("--api-only", action="store_true",
                        help="do not start the frontend")
    parser.add_argument("--no-collect", action="store_true",
                        help="skip the startup prospective freeze and replays")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser tab")
    options = parser.parse_args(argv)

    # `launcher/start.ps1` runs this with its output redirected, and Python
    # block-buffers a redirected stdout -- so every line below, including
    # "ready" and every reason a server did not come up, would appear only
    # once the process ended. A launcher whose diagnostics arrive after the
    # thing it was diagnosing is no launcher.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:                                            # noqa: BLE001
        pass

    # Recovery first: if the last run died before its shutdown backup, take one
    # now, before any forecast can be frozen on top of the unbacked state.
    ledger_lifecycle.start()

    # SIGTERM has to arrive as an exception, and this has to be set *before*
    # `install()`. `ledger_lifecycle` chains onto whatever handler it finds:
    # SIGINT already has one that raises `KeyboardInterrupt`, so Ctrl-C reaches
    # the `finally` below and the children are stopped -- but SIGTERM's default
    # is `SIG_DFL`, so a polite kill would back the ledger up and then end the
    # process on the spot, orphaning uvicorn and Node with the ports still
    # held. Installing this first makes `install()` chain onto it instead.
    def _terminate(_signum, _frame):
        raise KeyboardInterrupt

    for _name in ("SIGTERM", "SIGBREAK"):
        _number = getattr(signal, _name, None)
        if _number is not None:
            try:
                signal.signal(_number, _terminate)
            except (ValueError, OSError):
                pass

    ledger_lifecycle.install()

    # START -> CURRENT PROSPECTIVE FREEZE -> MISSED-DAY REPLAYS -> SERVERS.
    #
    # Today's bar must be claimed by the genuine prospective freeze before any
    # reconstruction runs, so a replay can never be the row that owns the
    # current session. The ordering inside is asserted by
    # `app/tests/test_replay.py::test_the_launcher_snapshots_before_it_collects`.
    if options.no_collect:
        print("[desk] --no-collect: no prospective freeze, no replays.")
    else:
        startup.collect_then_replay()

    api = web = None
    try:
        api = start_api(reload=options.dev)
        if not _wait_for(f"http://localhost:{API_PORT}/api/health", api, "API"):
            return 1

        if not options.api_only:
            web = start_frontend(dev=options.dev)
            if web is not None and not _wait_for(
                    f"http://localhost:{WEB_PORT}/", web, "frontend"):
                return 1

        target = (f"http://localhost:{WEB_PORT}/" if web is not None
                  else f"http://localhost:{API_PORT}/docs")
        print(f"[desk] ready. {target}   Ctrl-C to stop.")
        if not options.no_browser:
            webbrowser.open(target)

        # Hold until either child ends or the person stops us. Polling rather
        # than `wait()` because there are two of them and the first to die
        # should bring the other down: half a desk is worse than none, since
        # the surviving half looks like it works.
        while True:
            for process, label in ((api, "API"), (web, "frontend")):
                if process is not None and process.poll() is not None:
                    print(f"[desk] {label} stopped (code "
                          f"{process.returncode}); shutting down.",
                          file=sys.stderr)
                    return int(process.returncode or 0)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[desk] stopping.")
        return 0
    finally:
        _stop(web, "frontend")
        _stop(api, "API")
        # After the children, so the snapshot covers anything the API froze.
        # Fingerprint-guarded: if the API's own lifespan already took one,
        # this writes nothing.
        ledger_lifecycle.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
