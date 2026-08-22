# Next-steps roadmap, 2026-08-22

**Class:** operations/engineering. No information family is opened, no gate is
evaluated, no closed study is reopened. Nothing here needs preregistration —
same standing as `V5_LEDGER_PROTECTION.md`'s backup infrastructure ("not a
research decision").

**Why this document exists.** Six independent studies (PIT-1, SN-1, Family-10,
AMS-1, HR-1, HT-1 — `EXPERIMENT_REGISTRY.md` §7.3) have exhausted the
retrospective research line on free daily price data. The only evidence source
still open is the **prospective forecast ledger**, switched on 2026-08-15,
which needs 50 independent matured cutoffs before `promotion.py` will evaluate
anything (`MIN_INDEPENDENT_CUTOFFS`, promotion.py:77). This roadmap covers what
is left to *do*, not more to *test*.

Phases are ordered by how much silent damage waiting costs, not by effort.

---

## Phase A — Prospective ledger integrity

**Problem found 2026-08-22, before this phase started:** the ledger holds
**141 forecasts, 0 outcomes**. `outcome_ledger.score_matured` exists and is
fully tested but is only ever called against `app/replay_study.sqlite3` (by
`replay_study.py`) and by unit tests — nothing calls it against
`app/forecast_ledger.sqlite3`, the live ledger. Left alone, independent
cutoffs stay at 0 forever regardless of how long collection runs, because
`promotion.evidence_for` counts *matured* rows only. Separately, collection
already has two gaps (no forecasts on 2026-08-18 or 2026-08-21, both trading
days) and the backup on `D:\prediction market backup` is stale since
2026-08-16 while the ledger has since gained rows.

**Steps:**

- [x] A.1 — Add `app/tournament.sqlite3` to `.gitignore` (the only one of the
      four sqlite ledgers not already excluded).
- [x] A.2 — Build `app/core/score_outcomes.py`: a headless scorer mirroring
      `collector.py`'s shape (CLI, run log, exit code), wrapping
      `outcome_ledger.score_matured` against the **production** ledger via
      `live.fetch`. Delegates only — no new scoring logic.
- [x] A.3 — Tests for it, following `test_collector.py`'s pattern
      (delegation assertion, no-write-to-production-by-default assertion,
      idempotency, one-bad-symbol-does-not-cost-the-others).
- [x] A.4 — Run it once against the live ledger to score whatever has already
      matured.
- [x] A.5 — Full test suite green; verify no engine file
      (`ultimate.py`/`forecast.py`/`indicators.py`) or sealed exam touched.
- [x] A.6 — Commit.

**Standing habit, not a one-time step:** run `python -m core.collector` and
`python -m core.score_outcomes` by hand on trading days (no scheduler, per the
owner's directive in `V5_LEDGER_PROTECTION.md` §4.4). A day neither runs is a
permanent gap.

**Result, 2026-08-22.** First scoring run: outcomes went from 0 to 93 across
three horizons (1d: 34, 4h: 26, 1w: 33). Two real bugs were found and fixed in
`score_outcomes.py` before this worked cleanly, neither in the protected
scoring/methodology code:
- Intraday (`1h`) fetches requested a 10-year period, which Yahoo refuses for
  hourly bars (730-day cap). Fixed by making the fetch period interval-aware.
- `score_matured` raising for one symbol (e.g. an AB-1 basis-integrity
  refusal) was crashing the whole run and losing every symbol queued after
  it. Fixed with the same per-symbol isolation `collector.py` already uses on
  the freeze side.

**Five symbols were correctly refused by AB-1's basis check, not a bug:**
AAPL, BTC-USD, ETH-USD, META, NVDA all show a realised anchor price that
disagrees with the frozen one by more than a uniform rescaling (0.03–0.9%
deviation across 8 basis probes) — a genuine adjustment-basis drift between
freeze time and now. This is exactly what `V5_ADJUSTMENT_BASIS_FINDING.md`'s
AB-1 policy exists to catch. Nothing was overridden; these five symbols'
matured forecasts stay unscored until the drift is understood, which is the
system working as designed, not a defect to patch around.

---

## Phase B — `neural.lstm` reproducibility (HT-1's recorded, unfixed defect)

HT-1 (`reports/HT1_TOURNAMENT_RESULT.md` §6) measured `neural.lstm` at a 7.2%
sign-flip rate on identical re-runs and a maximum drift of 1,899 percentage
points, caused by `forecast.py` running with no seed and its dropout wrapper
active at inference. HT-1 explicitly scoped the fix out and did not license
changing anything — this phase is the fix, done as an engineering correction,
not a re-test of any verdict.

**Steps:**

- [ ] B.1 — Seed the LSTM rollout and disable dropout at inference
      (distinguish training-time from prediction-time in `forecast.py`).
- [ ] B.2 — Add a divergence guard on the autoregressive rollout so a
      diverging path is caught rather than silently shown as a number.
- [ ] B.3 — Re-run HT-1's stability probe methodology at small scale to
      confirm GRU/Vanilla-RNN reproducibility is unaffected and LSTM's flip
      rate drops — a verification measurement, not a new tournament.
- [ ] B.4 — Record the fix and the before/after numbers in a short report.
- [ ] B.5 — Full test suite green; commit.

---

## Phase C — Working-tree hygiene

Uncommitted work predates this roadmap and needs a decision so it doesn't sit
indefinitely or get confused with research artefacts:

- [ ] C.1 — Review modified `app/core/charts.py`, `app/streamlit_app.py`,
      `app/tests/test_ui.py` (+316/−9) — commit or park.
- [ ] C.2 — Review untracked `app/core/axis_drag.py` + its test — same.
- [ ] C.3 — Review the Pine indicator `.txt` sources under `agent/` — decide
      whether they belong in the repo (e.g. as HT-1 roster inputs) or are
      scratch.

---

## Phase D — Frontend (Obsidian design system), optional/separate track

Not part of the research programme. `design-system/shell` has the landing
shell only (hero, nav, stat cards, feature grid). Next step is user-directed:
pick the next page/component to extend with the locked tokens
(`design-system/MANIFESTO.md`).

---

## What stays closed (pointer only, not re-litigated here)

V2–V2.3 abandoned; V3 3/3 families rejected; V4 slot 1 spent/slot 2 barred;
Single-Name Phase 1 DO NOT ADVANCE; Family-10 pilot failed on power; AMS-1
rejected; HT-1 0/27. See `reports/EXPERIMENT_REGISTRY.md` for the full record.
No fourth family, no re-test, no threshold rescue, no sign flip — all barred
for the reasons recorded in each study's own report.
