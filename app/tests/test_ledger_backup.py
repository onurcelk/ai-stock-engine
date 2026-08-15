"""Usage-driven local backup for the one artefact that cannot be regenerated.

Every test builds its own ledger, its own backup root and its own state file in
`tmp_path`. The session-wide `never_touch_the_backup_drive` fixture in
`conftest.py` disables backups by default; tests here opt back in explicitly via
`enabled`, which makes reaching the real `D:\\prediction market backup`
impossible by accident and visible on purpose.
"""

from __future__ import annotations

import datetime as dt
import gc
import json
import pathlib

import numpy as np
import pandas as pd
import pytest

from core import forecast_ledger, ledger_backup, ledger_lifecycle, ultimate


ROWS = 900
HORIZONS = [ultimate.HORIZON_BY_KEY["1d"], ultimate.HORIZON_BY_KEY["1w"]]


@pytest.fixture
def enabled(monkeypatch):
    """Opt this test back into taking backups — against tmp paths only."""
    monkeypatch.delenv(ledger_backup.DISABLE_ENV, raising=False)


def _frame(*, rows: int = ROWS, seed: int = 23) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0007, 0.01, rows)))
    return pd.DataFrame({
        "date": pd.bdate_range("2019-01-01", periods=rows),
        "open": close * 0.999,
        "high": close * 1.006,
        "low": close * 0.994,
        "close": close,
        "volume": rng.integers(1_000_000, 4_000_000, rows).astype(float),
    })


def _fetcher(frame: pd.DataFrame):
    def fetch(symbol: str, *, period: str, interval: str, force: bool = False):
        return frame.copy(deep=True), None
    return fetch


def _ledger(path: pathlib.Path, *, symbol: str = "TEST",
            frame: pd.DataFrame | None = None) -> pathlib.Path:
    forecast_ledger.generate_and_freeze_incumbent(
        forecast_ledger.ForecastLedger(path), symbol,
        horizons=HORIZONS, fetcher=_fetcher(_frame() if frame is None else frame))
    return path


class Bench:
    """A ledger, a backup root and a state file, all inside `tmp_path`."""

    def __init__(self, tmp_path: pathlib.Path):
        self.ledger = tmp_path / "forecast_ledger.sqlite3"
        self.root = tmp_path / "backup_drive"
        self.root.mkdir()
        self.state = tmp_path / "state.json"
        _ledger(self.ledger)

    def kwargs(self) -> dict:
        return {"source": self.ledger, "backup_root": self.root,
                "state_path": self.state}

    def backup(self, **extra):
        return ledger_backup.backup_if_changed(**self.kwargs(), **extra)

    def grow(self, rows: int = ROWS + 1, symbol: str = "TEST"):
        _ledger(self.ledger, symbol=symbol, frame=_frame(rows=rows))

    def files(self) -> list[pathlib.Path]:
        return ledger_backup.list_backups(self.root)


@pytest.fixture
def bench(tmp_path, enabled) -> Bench:
    return Bench(tmp_path)


# ------------------------------------------------------------ changed or not


def test_a_changed_ledger_is_backed_up(bench):
    outcome = bench.backup()

    assert outcome.status == ledger_backup.BACKED_UP
    assert outcome.created is True
    assert outcome.path.exists()
    assert outcome.integrity == "ok"
    assert outcome.sha256 == ledger_backup.file_sha256(outcome.path)
    assert len(bench.files()) == 1


def test_an_unchanged_ledger_writes_nothing(bench):
    first = bench.backup()
    second = bench.backup()

    assert second.status == ledger_backup.UNCHANGED
    assert second.path is None
    assert bench.files() == [first.path]


def test_a_changed_ledger_after_a_backup_earns_a_second(bench):
    first = bench.backup()
    bench.grow()
    second = bench.backup(now=dt.datetime(2026, 8, 16, 22, tzinfo=dt.timezone.utc))

    assert second.created is True
    assert second.path != first.path
    assert len(bench.files()) == 2


def test_change_is_decided_on_contents_not_mtime(bench):
    """Touching the file must not qualify; changing a row always must."""
    bench.backup()
    before = ledger_backup.ledger_fingerprint(bench.ledger)
    bench.ledger.touch()

    assert bench.backup().status == ledger_backup.UNCHANGED

    bench.grow()
    after = ledger_backup.ledger_fingerprint(bench.ledger)
    assert after.digest != before.digest
    assert after.forecast_rows > before.forecast_rows
    assert bench.backup().created is True


def test_a_missing_backup_file_reopens_the_question(bench):
    """State claiming success is worthless if the drive was wiped."""
    first = bench.backup()
    first.path.unlink()

    outcome = bench.backup(now=dt.datetime(2026, 8, 16, 22, tzinfo=dt.timezone.utc))

    assert outcome.created is True


def test_an_unavailable_drive_fails_loudly_without_raising(tmp_path, enabled):
    bench = Bench(tmp_path)
    outcome = ledger_backup.backup_if_changed(
        source=bench.ledger, backup_root=tmp_path / "not_mounted",
        state_path=bench.state)

    assert outcome.status == ledger_backup.FAILED
    assert "not available" in outcome.error
    assert not (tmp_path / "not_mounted").exists()


# ------------------------------------------------------------------ integrity


def test_the_backup_passes_its_own_integrity_check(bench):
    outcome = bench.backup()

    assert ledger_backup.integrity_check(outcome.path) == "ok"
    assert ledger_backup.verify_backup(outcome.path, bench.root) is True
    assert (ledger_backup.ledger_fingerprint(outcome.path).digest
            == ledger_backup.ledger_fingerprint(bench.ledger).digest)


def test_a_failing_snapshot_leaves_nothing_behind(bench, monkeypatch):
    """An incomplete or corrupt temp snapshot must never become a backup."""
    monkeypatch.setattr(ledger_backup, "integrity_check", lambda p: "malformed")

    outcome = bench.backup()

    assert outcome.status == ledger_backup.FAILED
    assert "malformed" in outcome.error
    assert bench.files() == []
    assert list(bench.root.iterdir()) == []          # temp file cleaned up
    assert ledger_backup.read_state(bench.state) is None


def test_a_snapshot_that_does_not_match_its_source_is_rejected(bench, monkeypatch):
    """A file can pass integrity_check and still be the wrong database."""
    import dataclasses

    real = ledger_backup.ledger_fingerprint
    calls = {"n": 0}

    def fake(path):
        calls["n"] += 1
        result = real(path)
        # Call 1 is the source; call 2 is the fresh snapshot being checked
        # against it. Corrupt the second so the comparison must fail.
        return dataclasses.replace(result, digest="0" * 64) if calls["n"] == 2 else result

    monkeypatch.setattr(ledger_backup, "ledger_fingerprint", fake)
    outcome = bench.backup()

    assert outcome.status == ledger_backup.FAILED
    assert "do not match" in outcome.error
    assert bench.files() == []
    assert list(bench.root.iterdir()) == []


def test_incomplete_files_are_never_counted_as_backups(bench):
    bench.backup()
    stray = bench.root / f"{ledger_backup.TEMP_PREFIX}forecast_ledger_x.sqlite3.part"
    stray.write_bytes(b"not a database")

    assert stray not in bench.files()
    assert len(bench.files()) == 1


def test_corruption_is_caught_by_verification(bench):
    outcome = bench.backup()
    assert ledger_backup.verify_backup(outcome.path, bench.root) is True

    with open(outcome.path, "r+b") as handle:
        handle.seek(handle.seek(0, 2) - 64)
        handle.write(b"\x00" * 32)

    assert ledger_backup.verify_backup(outcome.path, bench.root) is False


def test_the_manifest_records_every_backup(bench):
    outcome = bench.backup()

    entries = ledger_backup.read_manifest(bench.root)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["filename"] == outcome.path.name
    assert entry["integrity"] == "ok"
    assert entry["sha256"] == outcome.sha256
    assert entry["forecast_rows"] == 2
    assert entry["fingerprint"] == outcome.fingerprint.digest
    assert ledger_backup.manifest_path(bench.root).exists()


def test_the_filename_follows_the_declared_format(bench):
    outcome = bench.backup(now=dt.datetime(2026, 8, 15, 22, 15, 30,
                                           tzinfo=dt.timezone.utc))

    assert outcome.path.name == "forecast_ledger_2026-08-15_22-15-30.sqlite3"


# ------------------------------------------------------------------ lifecycle


def test_graceful_shutdown_takes_a_backup(bench, capsys):
    outcome = ledger_lifecycle.shutdown(**bench.kwargs())

    assert outcome.created is True
    assert outcome.reason == "shutdown"
    assert len(bench.files()) == 1
    assert "ledger backup" in capsys.readouterr().err


def test_shutdown_on_an_unchanged_ledger_is_silent(bench, capsys):
    ledger_lifecycle.shutdown(**bench.kwargs())
    capsys.readouterr()

    outcome = ledger_lifecycle.shutdown(**bench.kwargs())

    assert outcome.status == ledger_backup.UNCHANGED
    assert capsys.readouterr().err == ""
    assert len(bench.files()) == 1


def test_a_crash_is_recovered_at_the_next_start(bench):
    """Shutdown callbacks are not guaranteed; startup is the safety net."""
    ledger_lifecycle.shutdown(**bench.kwargs())
    bench.grow()                     # the session that died before backing up

    outcome = ledger_lifecycle.start(
        **bench.kwargs(),
        now=dt.datetime(2026, 8, 16, 9, tzinfo=dt.timezone.utc))

    assert outcome.created is True
    assert outcome.reason == "startup-recovery"
    assert len(bench.files()) == 2


def test_repeated_starts_without_change_do_not_duplicate(bench):
    ledger_lifecycle.start(**bench.kwargs())
    for hour in range(10, 14):
        outcome = ledger_lifecycle.start(
            **bench.kwargs(),
            now=dt.datetime(2026, 8, 16, hour, tzinfo=dt.timezone.utc))
        assert outcome.status == ledger_backup.UNCHANGED

    assert len(bench.files()) == 1


def test_install_registers_an_exit_hook(bench, monkeypatch):
    registered = []
    monkeypatch.setattr("atexit.register", lambda fn: registered.append(fn))

    hook = ledger_lifecycle.install(register_signals=False, **bench.kwargs())

    assert registered == [hook]
    assert hook().created is True
    assert len(bench.files()) == 1


def test_the_backup_is_disabled_by_default_under_test(tmp_path):
    """Without the `enabled` fixture, nothing is written anywhere."""
    bench_ledger = _ledger(tmp_path / "forecast_ledger.sqlite3")
    root = tmp_path / "drive"
    root.mkdir()

    outcome = ledger_backup.backup_if_changed(
        source=bench_ledger, backup_root=root, state_path=tmp_path / "s.json")

    assert outcome.status == ledger_backup.UNCHANGED
    assert outcome.reason == "disabled"
    assert list(root.iterdir()) == []


# ------------------------------------------------------------------ retention


def _seed_backups(root: pathlib.Path, count: int, *, integrity: str = "ok"):
    """Cheap stand-ins: retention reads the manifest and the glob, not SQLite."""
    entries = []
    for index in range(count):
        name = f"forecast_ledger_2026-01-{index // 24 + 1:02d}_{index % 24:02d}-00-00.sqlite3"
        (root / name).write_bytes(b"x")
        entries.append({"filename": name, "integrity": integrity,
                        "sha256": "0" * 64, "fingerprint": "f"})
    ledger_backup._write_manifest(root, entries)
    return entries


def test_retention_keeps_the_latest_ninety(tmp_path):
    root = tmp_path / "drive"
    root.mkdir()
    seeded = [entry["filename"] for entry in _seed_backups(root, 95)]
    oldest_five, survivors = sorted(seeded)[:5], sorted(seeded)[5:]

    removed = ledger_backup.apply_retention(root)

    remaining = [p.name for p in ledger_backup.list_backups(root)]
    assert sorted(removed) == oldest_five          # the oldest, precisely
    assert remaining == survivors                  # and nothing else went
    assert len(remaining) == 90
    assert sorted(seeded)[-1] in remaining         # the newest is untouched
    assert ([e["filename"] for e in ledger_backup.read_manifest(root)]
            == survivors)                          # manifest agrees with disk


def test_retention_does_nothing_below_the_limit(tmp_path):
    root = tmp_path / "drive"
    root.mkdir()
    _seed_backups(root, 90)

    assert ledger_backup.apply_retention(root) == []
    assert len(ledger_backup.list_backups(root)) == 90


def test_retention_never_removes_the_only_valid_backup(tmp_path):
    root = tmp_path / "drive"
    root.mkdir()
    _seed_backups(root, 1)

    assert ledger_backup.apply_retention(root, keep=0) == []
    assert len(ledger_backup.list_backups(root)) == 1


def test_retention_never_removes_the_newest(tmp_path):
    root = tmp_path / "drive"
    root.mkdir()
    _seed_backups(root, 5)
    newest = ledger_backup.list_backups(root)[-1]

    ledger_backup.apply_retention(root, keep=1)

    assert newest.exists()
    assert len(ledger_backup.list_backups(root)) == 1


def test_retention_ignores_unverified_and_incomplete_files(tmp_path):
    root = tmp_path / "drive"
    root.mkdir()
    _seed_backups(root, 3, integrity="failed")
    (root / f"{ledger_backup.TEMP_PREFIX}forecast_ledger_z.sqlite3.part").write_bytes(b"x")

    assert ledger_backup.apply_retention(root, keep=1) == []
    assert len(ledger_backup.list_backups(root)) == 3


def test_a_retention_failure_never_costs_the_new_backup(bench, monkeypatch):
    monkeypatch.setattr(ledger_backup, "apply_retention",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("drive busy")))

    outcome = bench.backup()

    assert outcome.created is True
    assert outcome.path.exists()
    assert "retention skipped" in outcome.error


# ------------------------------------------------------------------- source


def test_the_source_is_byte_identical_after_a_backup(bench):
    digest = ledger_backup.file_sha256(bench.ledger)
    fingerprint = ledger_backup.ledger_fingerprint(bench.ledger)

    bench.backup()

    assert ledger_backup.file_sha256(bench.ledger) == digest
    assert ledger_backup.ledger_fingerprint(bench.ledger) == fingerprint


def test_the_module_never_writes_to_a_ledger():
    """Structural: read-only connections, and no mutating SQL anywhere."""
    import inspect

    text = inspect.getsource(ledger_backup)
    code = "".join(text.split('"""')[::2])
    code = "\n".join(line for line in code.splitlines()
                     if not line.strip().startswith("#"))

    assert "mode=ro" in code
    for statement in ("VACUUM", "DELETE FROM", "UPDATE ", "DROP ", "INSERT INTO"):
        assert statement not in code, statement


def test_reading_a_fingerprint_cannot_create_a_ledger(tmp_path):
    missing = tmp_path / "absent.sqlite3"

    with pytest.raises(ledger_backup.LedgerBackupError):
        ledger_backup.ledger_fingerprint(missing)

    assert not missing.exists()


def test_nothing_restores_automatically():
    """`restore` is manual only; no lifecycle path may call it."""
    import inspect

    for module in (ledger_lifecycle, ledger_backup):
        source = inspect.getsource(module)
        body = source.split("def restore(")[0]
        assert "restore(" not in body, module.__name__


def test_restore_refuses_to_discard_newer_forecasts(bench):
    outcome = bench.backup()
    bench.grow()
    grown = ledger_backup.ledger_fingerprint(bench.ledger)

    with pytest.raises(ledger_backup.LedgerBackupError, match="cannot be regenerated"):
        ledger_backup.restore(outcome.path, bench.ledger)

    assert ledger_backup.ledger_fingerprint(bench.ledger) == grown


def test_forced_restore_keeps_what_it_replaced(bench):
    outcome = bench.backup()
    bench.grow()
    grown = ledger_backup.ledger_fingerprint(bench.ledger)
    gc.collect()

    ledger_backup.restore(outcome.path, bench.ledger, force=True,
                          now=dt.datetime(2026, 8, 16, tzinfo=dt.timezone.utc))

    assert (ledger_backup.ledger_fingerprint(bench.ledger).digest
            == outcome.fingerprint.digest)
    superseded = list(bench.ledger.parent.glob(f"{bench.ledger.name}.superseded_*"))
    assert len(superseded) == 1
    assert ledger_backup.ledger_fingerprint(superseded[0]) == grown


# -------------------------------------------------------------- the real ones


def test_no_test_may_reach_the_production_ledger_or_the_backup_drive(tmp_path):
    production = pathlib.Path(forecast_ledger.DEFAULT_PATH)
    drive = ledger_backup.DEFAULT_BACKUP_ROOT

    assert drive == pathlib.Path(r"D:\prediction market backup")
    assert tmp_path != production.parent
    assert not str(tmp_path).startswith(str(drive))
    # The default state file lives beside the ledger, never on the drive.
    assert ledger_backup.DEFAULT_STATE_PATH.parent == production.parent
    assert not ledger_backup.list_backups(tmp_path / "never_created")


def test_the_real_drive_is_untouched_by_this_module_under_test():
    """The session fixture is the guard; this asserts it is actually on."""
    import os

    assert os.environ.get(ledger_backup.DISABLE_ENV) == "1"
