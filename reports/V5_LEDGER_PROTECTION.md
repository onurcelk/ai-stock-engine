# Protecting and accumulating the prospective record

**Date:** 2026-08-15
**Status:** `ACCUMULATION INFRASTRUCTURE ONLY. NO PREDICTION PATH CHANGED.`
**Declared while the ledger holds 0 outcomes**, which is the same guarantee
Phase 7's thresholds and AB-1's policy carry: a schedule chosen now cannot have
been chosen to flatter a result, because there is no result.

Three things are settled here: how the ledger is backed up, how it accumulates
without anyone opening the app, and how often — with the arithmetic showing what
the *already-frozen* promotion policy actually requires.

---

## 1. A correction, first

`reports/V5_LEDGER_ACTIVATION.md` and `reports/EXPERIMENT_REGISTRY.md` §17 both
state that activation left the programme at *"1 independent cutoff against the
Phase 7 floor of 20"*. **Both numbers are wrong.** The originals stand unedited
under CLAUDE.md §1.1; this is the correction.

| | Stated | Actual |
|---|---|---|
| Floor | 20 | **50** — `promotion.MIN_INDEPENDENT_CUTOFFS`, promotion.py:77 |
| Available | 1 | **0** |

The count is 0, not 1, because the gate's measure is not "how many dates were
forecast on". `promotion.evidence_for` builds windows from **matured** rows, so
a forecast with no outcome contributes nothing. 86 frozen forecasts across 2
calendar dates yield **zero** independent cutoffs until the first horizon
elapses. Nothing about the record changed; the earlier description of it was
simply wrong, and the error was in the direction of flattering the programme's
position, which is the direction that matters.

---

## 2. What the frozen policy actually requires

`MIN_INDEPENDENT_CUTOFFS = 50`, and `promotion.independent_cutoffs` selects the
largest set of cutoffs whose `[cutoff, matured_at]` windows do not overlap —
greedy earliest-finishing, which is optimal for interval scheduling.
`evidence_for` filters by horizon first, so independence is counted **within one
horizon, for one model**.

A horizon here is a number of bars, not a calendar duration: `4h` is 4 hourly
bars, `1d` is 1 daily bar, `1w` is 5 daily bars. Feeding a daily collection
cadence into the frozen function gives the real requirement:

| Horizon | Window | Trading days of daily collection to reach 50 | Wall clock |
|---|---|---|---|
| `4h` | 4 hourly bars | **50** | ~10 weeks |
| `1d` | 1 daily bar | **50** | ~10 weeks |
| `1w` | 5 daily bars | **246** | **~49 weeks — about a year** |

Computed by running `promotion.independent_cutoffs` itself over simulated
cadences, not by hand. No outcome value was read to produce this table; only
window geometry.

**The binding horizon is `1w`, at roughly a year of daily collection.** That is
the honest cost of the promotion policy as frozen, and it is a fact about the
policy rather than a discovery about the market. It is also exactly why the
schedule below is not "collect as often as possible": nothing about collecting
more often shortens it.

---

## 3. The collection schedule

**Once per trading day, after the close — 22:15 UTC, Monday to Friday.**

Chosen for these reasons, none of which is expected performance:

1. **The last bar must be finished.** A forming bar's close moves. Freezing
   against one would give the same nominal bar different input fingerprints on
   successive runs, which defeats the idempotency guard and mints near-duplicate
   rows carrying no new information. It would also hand AB-1's anchor
   reconciliation a moving reference. 22:15 UTC is comfortably after the 20:00/21:00
   UTC US close in either DST regime.
2. **Daily is the coarsest cadence that loses nothing.** At one run per trading
   day, `4h` and `1d` both reach their maximum possible independent rate of one
   per trading day, and `1w` reaches its maximum of one per five. A finer
   cadence cannot improve `1d` or `1w` at all — their windows already span the
   gap — so the only thing intraday collection would buy is extra `4h` draws, at
   the cost of partial-bar risk on every run. Declined.
3. **A fixed time removes discretion.** Nobody decides *when* to sample, so the
   sampling cannot correlate with what the market just did. A schedule that a
   human triggers is not a schedule.
4. **It is declared before any outcome exists.** Available exactly once.

**Extra rows are not extra draws.** Running the collector more often than daily,
or opening the app between runs, adds ledger rows and adds **no** independent
cutoffs where the windows overlap. Phase 7's definition is untouched and is the
only thing that counts. The Research tab reports both numbers separately for
this reason.

---

## 4. The headless collector

`app/core/collector.py`. Invoked from the `app/` directory:

```
python -m core.collector                 # the declared universe, then a backup
python -m core.collector --no-backup     # collection only
python -m core.collector --symbols AAPL  # ad-hoc, testing
```

Exit code 0 when every symbol succeeded and no backup anomaly was seen, 1
otherwise. Failures print to stderr; one JSON run log per run lands in
`app/collection_logs/`.

**It is not a second forecasting path.** It calls
`ledger_activation.evaluate_and_freeze` — the same function `streamlit_app`
calls — and therefore inherits every existing guarantee: deterministic incumbent
only, AB-1 basis probes, `assert_prospective` and `MAX_CUTOFF_LAG`,
input-fingerprint idempotency, no route to `evaluate_offline`, no challenger.
`test_the_collector_delegates_and_invents_nothing` asserts that structurally, by
forbidding the symbols it would need to reimplement one.

**The universe is declared, not discovered.** `app/collection_universe.txt`
holds the 30 symbols the ledger was switched on with, one per line. Deriving it
from `app/cache/` instead would let a symbol enter or leave the record as a side
effect of browsing; here a change is a change someone made, visible in git.

**Rerunning is free.** A symbol whose bars have not moved is skipped by input
fingerprint. Verified against the production ledger: a second run over all 30
symbols froze 0 records and exited 0.

### How it is triggered — and a directive that changed the answer

An earlier draft of this document recommended registering a Windows Scheduled
Task at 22:15 UTC. **That recommendation is withdrawn.** The owner has since
directed that no Windows Scheduled Task, periodic timer, background sync or
cloud service be used anywhere in this system. The collector is therefore run
one of two ways:

- **`python -m core.collector`**, by hand, when accumulation is wanted; or
- **implicitly**, by opening the app and reading live tickers, which freezes
  through the identical path.

**The honest consequence, stated rather than buried:** without a scheduler,
accumulation depends on someone running the collector or opening the app. §3's
cadence is therefore a *target* to be met by habit, not a guarantee enforced by
the machine. A trading day on which neither happens yields no cutoff, and that
gap is permanent — no backup contains a forecast that was never frozen.

Auto-running collection from `run_app.py` would close that gap, and it was
**deliberately not done**: it would change *when forecasts are generated*, which
§9 of the owner's directive puts out of scope for backup infrastructure. It is
the obvious next candidate if the cadence proves hard to keep by hand.

---

## 5. Backups — local, usage-driven, on a separate physical drive

`app/core/ledger_backup.py`. Destination **`D:\prediction market backup`**, a
separate physical drive. Filenames are
`forecast_ledger_YYYY-MM-DD_HH-MM-SS.sqlite3`.

**There is no cloud service, no scheduled task, no timer, no daemon and no
background sync.** A backup happens only when the application has actually
changed the ledger.

### The lifecycle

```
APP START  ->  recovery backup, if the last run never got one
           ->  normal use; the ledger may gain rows
APP EXIT   ->  backup if changed
```

Both hooks are installed by `run_app.py`, which owns the process:

```
python run_app.py          # instead of `streamlit run app/streamlit_app.py`
```

**Why a launcher and not a hook inside `streamlit_app.py`.** Streamlit
re-executes that script top to bottom on every interaction, and its process
outlives the browser tab — closing a tab is a websocket disconnect, not a
shutdown. There is no reliable "the app is closing" callback inside the script.
The process that owns the lifecycle is the launcher, so `try/finally`, `atexit`,
`SIGINT` and `SIGTERM` all live there. The signal handlers re-raise the default
behaviour afterwards, so the process still dies when asked; a handler that
swallowed the signal would turn a backup convenience into an app that cannot be
stopped.

It also keeps the test suite structurally safe: `test_ui.py` boots
`streamlit_app.py` directly and therefore cannot reach the lifecycle at all.

### Crash recovery

Shutdown callbacks are not guaranteed — a kill, a power cut or a crash skips
every one. `app/ledger_backup_state.json` records the fingerprint, timestamp,
filename and SHA-256 of the last successful backup. On start, if the live ledger
disagrees with that fingerprint, a **recovery backup is taken before any
forecast activity begins**. Repeated starts with no ledger change write nothing,
because the comparison is on immutable content.

If the recorded backup file is missing from the drive — a wiped or disconnected
volume — the state is treated as unknown and a fresh backup is taken. State that
claims success is worthless if the file it names is gone.

### Deciding whether anything changed

The fingerprint is a SHA-256 over every `forecast_id` and its stored
`payload_sha256`, plus outcome identities, row counts, symbol count and the
latest forecast identity. **Filesystem mtime is never consulted**: it moves when
nothing changed and stays still when a row is rewritten in place. Touching the
ledger produces no backup; changing a row always does.

### How a snapshot is taken

1. Fingerprint the live ledger; compare with the last successful backup.
   Identical, and the file still present, gives **`UNCHANGED`** and writes
   nothing.
2. Snapshot via `sqlite3.Connection.backup()` from a **read-only** (`mode=ro`)
   connection into a temporary name prefixed `_incomplete_`. Never a raw
   filesystem copy of an open database — that can catch a torn write and produce
   a file that verifies as SQLite while missing the last transaction.
3. `PRAGMA integrity_check` on the snapshot; must be exactly `ok`.
4. Re-fingerprint the snapshot and require it to match the source.
5. SHA-256 the snapshot.
6. **`os.replace`** the temporary file onto its final name — atomic, so a reader
   can never observe a partial file under a real backup name.
7. Append to the manifest and update the state file, both written atomically.

Any failure at 3–5 deletes the temporary file and returns `FAILED` with the
reason. Nothing is left behind and no manifest entry is written. The
`_incomplete_` prefix falls outside the backup glob, so a snapshot interrupted at
any point can never be counted as a backup or pruned as one.

`backup_if_changed` **never raises**. It runs while the user is closing or
opening the application; an exception there would be a worse outcome than a
missed backup, so failures come back as `FAILED` for the caller to display.

### The manifest

`D:\prediction market backup\backup_manifest.json`, written atomically via a
temporary file and `os.replace`. One entry per backup: filename, timestamp,
reason, row counts, symbol count, ledger fingerprint, latest forecast id,
SHA-256, and integrity status. It records ledger *metadata* only — no prediction
outcome, and no research record is modified by the backup system.

### Retention

**The latest 90 valid snapshots are kept.** Beyond that the oldest verified
backups are removed, and three refusals hold regardless of the manifest's state:

- the **newest** backup is never removed;
- the **only** valid backup is never removed;
- nothing outside the completed-backup glob is ever touched, so temporary and
  incomplete files are neither counted toward retention nor deleted by it.

Retention runs *after* a backup has been written and verified, and a failure in
it is caught and reported without disturbing the new file. A retention bug must
never cost a valid backup — that would defeat the module.

### The live ledger is never written

Every read uses a `mode=ro` URI connection.
`test_the_module_never_writes_to_a_ledger` asserts this structurally, forbidding
`VACUUM`, `DELETE FROM`, `UPDATE`, `DROP` and `INSERT INTO` anywhere in the
module's code.

---

## 6. Recovery procedure

**Nothing restores automatically.** `test_nothing_restores_automatically`
asserts that no lifecycle path calls `restore`. Recovery is a decision a person
makes, with the facts in front of them.

**Symptom: the ledger is corrupt, truncated, or missing.**

1. **Stop writing.** Do not open the app or run the collector — both write, and
   writing to a damaged ledger makes the damage harder to reason about.
2. **Take stock**, from `app/`:
   ```
   python -c "from core import ledger_backup as b; print(b.ledger_fingerprint('forecast_ledger.sqlite3'))"
   python -c "from core import ledger_backup as b; [print(p.name, b.verify_backup(p)) for p in b.list_backups()]"
   ```
   The first fails outright if the file is unreadable. The second prints every
   backup with a live verification — trust the `True` lines only.
3. **Choose** the newest backup that verifies and whose `forecast_rows` is at
   least what you expect. `read_manifest()` shows counts, timestamps and reasons.
4. **Restore:**
   ```
   python -c "from core import ledger_backup as b; print(b.restore(r'D:\prediction market backup\forecast_ledger_<stamp>.sqlite3'))"
   ```
   This **refuses** if the current ledger holds more forecast rows than the
   backup, naming how many prospective forecasts would be discarded.
5. **Only if the current ledger is known to be corrupt**, repeat with
   `force=True`. Even then the replaced file is copied aside first as
   `forecast_ledger.sqlite3.superseded_<stamp>`. Nothing is destroyed.
6. **Confirm and resume:**
   ```
   python -c "from core import ledger_backup as b; print(b.ledger_fingerprint('forecast_ledger.sqlite3'))"
   ```

**What cannot be recovered.** A forecast that was never frozen. If neither the
app nor the collector ran on a given day, that day's cutoff does not exist and
no backup contains it. Gaps in accumulation are permanent — the cost of a
prospective record, and the reason §3's cadence matters.

**Still yours to arrange.** `D:` is a separate physical drive, which covers a
disk failure on `C:` and accidental deletion. It does not cover the machine
being lost, stolen or destroyed. An occasional copy of
`D:\prediction market backup` to somewhere off-machine is the remaining gap, and
it needs no preregistration.

---

## 7. Verification

- **Baseline:** 990 passed, 69 skipped — green, before any edit.
- **Final:** see the roadmap session record for committed counts.
- **Production ledger untouched.** Digest over every stored payload and payload
  hash, before this work began and after it finished:
  `cabcf1bd003a73e8456a289b9797e1faca90661c03c72012c5beb23b9c3b0b0e` — identical.
  86 forecasts, 30 symbols, 4 cutoff stamps, and the same 86 forecast ids.
- **No prediction path changed.** No feature, threshold, horizon, incumbent
  prediction, promotion gate or AB-1 scoring semantic was altered.
- **No outcome inspected.** §2's table is window geometry only; the ledger holds
  zero outcomes and none was read.
- **No cloud, scheduled task, timer, daemon or background sync** exists anywhere
  in this system.
- **Methodology surfaces (CLAUDE.md §1.2):** none touched.
- **Sealed exam:** not accessed.
