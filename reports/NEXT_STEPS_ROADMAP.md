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

## Phase E — reopening PEAD/VIX and two new candidates (account-holder directive, 2026-08-22)

**Class: research, not operations.** On 2026-08-22 the account holder asked to add six
indicators (opening-range breakout, VWAP mean reversion, VIX mean reversion, PEAD, option
selling, option-premium harvesting). Two of the six are not new ground: PEAD is SUE, closed
at every horizon by V3 and V4; VIX mean reversion is `pine.vix_fix`, already measured and
rejected by HT-1. `CLAUDE.md` §1.3 requires flagging that conflict before proceeding, which
was done; the account holder, shown the conflict, **explicitly chose to reopen both**,
explicitly chose "new alpha claim" over "informational only," and explicitly chose "full
options extension" over "signal only." This phase is that directive, executed to the same
pre-registration standard the rest of this programme holds itself to — charter and power
gate before any measurement, exactly like `alpha/V4_CHARTER.md` was for SUE's last
reopening.

**Steps:**

- [x] E.1 — `alpha/PEAD1_CHARTER.md`: reopens SUE under an event-time, absolute-return
      formulation (not V3/V4's calendar-grid cross-sectional IC), passing the same
      six-condition reuse test `V4_CHARTER.md` §3.2 established. Names the power gate that
      must be built before any slot is spent; does not build it.
- [x] E.2 — `reports/OPTIONS1_ADMISSIBILITY.md`: checked directly whether free options data
      (chains, historical IV, greeks) exists point-in-time. **It does not** — yfinance
      (and every other free source checked) serves live snapshots only, with expired
      contracts unrecoverable at any price. **Verdict: FAIL for the options execution
      layer** (chain/greek/margin/tail-risk modelling cannot be built under the programme's
      free-data-only rule, §27B, without a provider-spend decision only the account holder
      can make). The VIX-mean-reversion reformulation itself (timing a realised-vol
      contraction, not equity direction) remains admissible as a **signal-only** question,
      answerable from `^VIX` and existing daily price history alone — scoped as VIX1, not
      yet run.
- [x] E.3 — `alpha/HT2_TOURNAMENT_PREREGISTRATION.md`: opening-range breakout and VWAP
      mean reversion, as new (not reopened) candidates. Checked free intraday-data depth
      directly: 5-minute bars only go back ~2 months, which is inadmissible for a true
      opening-range design on power grounds alone. Substitutes an hourly-bar proxy
      (`orb_1h`, needs its own power gate, ≤730 days of data) and a daily swing-VWAP variant
      (`vwap_reversion`, reuses HT-1's own grid and already-passed power gate outright).
- [x] E.4 — **Decided 2026-08-22 by the account holder**: free-data-only. Drop the options
      execution build-out (chains/greeks/margin/tail-risk); keep only the free-data VIX1
      signal study (elevated VIX predicts a realised-vol contraction) as a future candidate.
- [x] E.7 (partial) — **`vwap_reversion` measured and reported**, gate already satisfied by
      HT-1's own. **REJECTED at all three horizons** — advantage −0.0391 (1d) / −0.0240 (1w)
      / −0.1194 (5w), the `5w` interval entirely below zero but `p Holm = 1.0` across the
      combined 84-test family (HT-1's 81 + these 3). See `reports/HT2_TOURNAMENT_RESULT.md`.
      New module `app/core/ht2_vwap.py` (8 tests), reuses HT-1's `tournament.leaderboard`
      pipeline unmodified — does not touch `CANDIDATES` or `app/tournament.sqlite3`.
- [x] E.8 (partial) — VWAP result recorded in `reports/EXPERIMENT_REGISTRY.md` §22.
- [ ] E.5 — Build PEAD-1's power gate (`alpha/PEAD1_CHARTER.md` §6): independent-block
      census of the point-in-time earnings-event calendar, half-width estimated without
      reading any forward return, compared against the 39 bp / block-length-floor hurdles.
      **Expected to fail** per the charter's own stated prior — recording that outcome is
      itself the deliverable, not a setback. Not started.
- [ ] E.6 — Build `orb_1h`'s power gate (`HT2_TOURNAMENT_PREREGISTRATION.md` §4). Also
      **expected to fail** on the same free-data-depth grounds. Not started.
- [ ] E.9 — If the account holder wants it: build VIX1 (§E.4's free-data-only path) —
      needs its own power gate and confirmatory pre-registration, same discipline as
      everything else in this phase. Not started, not yet requested.

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
