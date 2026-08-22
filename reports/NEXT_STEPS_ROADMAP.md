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
- [x] E.5 — Built PEAD-1's power gate (`alpha/pead1_power_gate.py`). **PASSED for the
      5-session and 20-session windows** (12.5 bp and 27.8 bp vs a 39 bp MDE) — **contrary
      to the charter's own stated prior**. 60-session window fails (67.1 bp). 5-session
      window selected on variance-only grounds (largest margin). See
      `reports/PEAD1_POWER_GATE.md`.
- [x] E.6 — Built `orb_1h`'s power gate (`alpha/orb1h_power_gate.py`). **PASSED** — 7.3 bp
      half-width against the 39 bp MDE, a 5.3x margin, **also contrary to the
      pre-registration's stated prior** (the free `1h` cache has accumulated since
      2023-09-26 through ordinary app use, well past the 730-day fresh-fetch ceiling). See
      `reports/ORB1H_POWER_GATE.md`.
- [x] E.10 — Wrote PEAD-1's confirmatory pre-registration (`alpha/PEAD1_PREREGISTRATION.md`):
      5-session window, four-criterion CONTINUE rule including a market-relative control,
      noise control. Committed before the first event-return for this study was read.
- [x] E.11 — Wrote `orb_1h`'s confirmatory design (`HT2_TOURNAMENT_PREREGISTRATION.md`
      Amendment 2): same-session outcome unchanged from the gate, three-criterion CONTINUE
      rule, noise control. Committed before the first inspected measurement.
- [x] E.12 (orb_1h) — **Run. REJECTED.** Advantage +0.9 bp vs a 39 bp hurdle, interval
      [−6.5, +8.1] straddles zero, first sample half negative. See
      `reports/ORB1H_RESULT.md`, registry §24.
- [x] E.12 (PEAD-1) — **Run. REJECTED — but not a flat null.** Advantage +14.7 bp, 95% CI
      [+2.1, +27.0] (excludes zero — a real, statistically detectable effect), but too
      small against the 39 bp economic bar and substantially explained by market exposure
      once the SPY-relative control is applied (CI low −4.3 bp). Caught and fixed a
      tz-handling bug before trusting this result. See `reports/PEAD1_RESULT.md`,
      registry §25. **SUE is now closed permanently at every formulation tested.**

**Phase E is complete.** All five 2026-08-22 account-holder-directed indicators are
resolved: `vwap_reversion`, `orb_1h`, and PEAD-1 all REJECTED (measured); the options
execution layer is inadmissible (no free point-in-time data, `OPTIONS1_ADMISSIBILITY.md`);
VIX1 (the free-data vol-timing signal) remains open but was not requested to be built.
- [x] E.9 — Built and ran VIX1's power gate (`alpha/vix1_power_gate.py`). **FAILED at both
      candidate windows** (5-session half-width 7.57 pts, 20-session 5.45 pts, vs a 3.0-pt
      MDE) — unlike PEAD-1/orb_1h, this prediction held: realised volatility is noisier to
      estimate than a return at comparable sample size. **VIX1 CLOSED per its own rule, 0
      slots spent, no confirmatory measurement run.** See `reports/VIX1_POWER_GATE.md`.

**All six 2026-08-22 account-holder-directed indicators are now resolved**: `vwap_reversion`,
`orb_1h`, PEAD-1 all measured and REJECTED; VIX1 gate-failed and closed; the options
execution layer inadmissible. Phase E is fully complete.

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

## Phase D — Frontend rebuild in the Obsidian design system

**Superseded 2026-08-22** by an explicit account-holder decision: unify the
Streamlit app and the Obsidian landing page into one product, rebuilding the
app's actual functionality as Next.js pages in Obsidian's design, backed by a
new FastAPI layer in front of the existing `app/core/*` logic (no
reimplementation — confirmed by direct inspection that only 2 of ~28 `core`
modules touch Streamlit at all, both presentation-only). Full plan at
`C:\Users\onurc\.claude\plans\swirling-finding-zephyr.md`. Approach:
strangler-fig — build alongside Streamlit, port one tab at a time, verify
each against the original, retire Streamlit only once everything is ported.

- [x] **Phase 0 — the Signal page, end to end.** Built and verified. New
      `Stock-Prediction-Models/api/` (FastAPI: `main.py`, `routers/signal.py`,
      `schemas.py`) exposes `GET /api/signal/{symbol}`, calling
      `core.ledger_activation.evaluate_and_freeze` unmodified — the exact
      function Streamlit's Signal tab calls, so the new page and the old tab
      share one write path into the forecast ledger, never two. New
      `design-system/shell/src/app/signal/page.tsx` (+ `signal-card.tsx`,
      `horizon-card.tsx`, `lib/api.ts`) renders it in Obsidian's tokens/motion.
      Verified against live Streamlit data for two symbols (AAPL: HOLD/+0/0%;
      NVDA: SELL/-23/21%, matching the Portfolio tab's own reading exactly).
      Zero console/page errors, `tsc --noEmit` and `eslint` clean, fast Python
      suite unchanged at 1282 passed.
- [x] **Phase 1 — Chart + Portfolio (read side).** Built and verified. New
      `api/routers/chart.py` (`GET /api/ohlcv/{symbol}`, wraps `core.live.fetch`
      unmodified) and `api/routers/portfolio.py` (`GET /api/portfolio`, wraps
      `holdings.load/load_ledger/value/realised_total/fees_total`,
      `portfolio.fetch_many` for pricing, and `ultimate.scan` + `book_signal`
      for per-position calls — the same non-freezing engine call
      `streamlit_app.py`'s own `scan_book` uses, confirmed by reading its
      source, so this can never disagree with the tab for the same ticker).
      New `design-system/shell`: `candlestick-chart.tsx` (hand-built SVG, no
      new chart-library dependency), `app/chart/page.tsx`,
      `app/portfolio/page.tsx`. Verified byte-for-byte against a fresh
      Streamlit screenshot of the same 18-position book: market value
      $2,870.08, cost basis $2,363.45, +21.44% unrealised, book signal −1/14%
      confidence, reading buy 2/sell 2, and every row's P&L/weight/call —
      all matched exactly, including NVDA SELL/-23.2/21% and SPY STRONG BUY.
      Read-only: grepped `api/` for any `holdings.execute/save/buy/sell` call
      and found none. Zero console/page errors, `tsc`/`eslint` clean, fast
      Python suite unchanged at 1282 passed.
- [ ] **Phase 2 — Portfolio writes.** Fix `core/holdings.py::execute()`'s
      concurrency bug first (naive read-modify-write on `holdings.json`/
      `transactions.json`, no locking — two concurrent requests can clobber a
      trade; add a process-wide `threading.Lock`). Then
      `POST /api/portfolio/trade`, `POST /api/portfolio/ledger/clear`, the
      trade form UI.
- [ ] **Phase 3 — Research tab.** Read-only; `core.research_view.load()`'s
      many DataFrames (production panel, leaderboard, promotion requirements,
      calibration) as `GET /api/research/*` endpoints and Next.js
      tables/charts. High-value given it's this session's own subject matter.
- [ ] **Phase 4 — Forecast + Trading agents (long-running).** LSTM/RL training
      already streams progress via callback (`on_progress`) in the existing
      code; the API equivalent is `POST` starts a background job (FastAPI
      `BackgroundTasks` + an in-memory status dict, no Celery/Redis needed for
      one local user) and `GET /jobs/{id}` the frontend polls.
- [ ] **Phase 5 — Remaining tabs.** Monte Carlo (`core.montecarlo.run`,
      already fast/vectorized — trivially synchronous), History
      (`core.runs.*`), Overview.
- [ ] **Phase 6 — Cutover.** Once every tab is ported and spot-checked against
      Streamlit, retire `streamlit_app.py` or keep it as an internal fallback.

---

## What stays closed (pointer only, not re-litigated here)

V2–V2.3 abandoned; V3 3/3 families rejected; V4 slot 1 spent/slot 2 barred;
Single-Name Phase 1 DO NOT ADVANCE; Family-10 pilot failed on power; AMS-1
rejected; HT-1 0/27. See `reports/EXPERIMENT_REGISTRY.md` for the full record.
No fourth family, no re-test, no threshold rescue, no sign flip — all barred
for the reasons recorded in each study's own report.
