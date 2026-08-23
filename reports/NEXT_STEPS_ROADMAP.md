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

**Done 2026-08-23**, authorised by the account holder ahead of the frontend
rebuild's Forecast page, on the grounds that porting the tab first would ship a
known non-deterministic number in a better-looking wrapper. No record splits:
all three neural challengers hold n = 0 frozen forecasts, no PRODUCTION entry is
versioned on `app.core.forecast`, and `ultimate.py` does not reference it.
Full write-up in `reports/PHASEB_REPRODUCIBILITY.md`.

- [x] B.1 — Dropout was active at inference (a graph constant, so it stayed on
      through `_predict` and discarded a fifth of every inference call's
      outputs) and nothing was seeded. `_build_graph` no longer accepts the
      argument at all; the wrapper reads a `placeholder_with_default(1.0)`, so
      inference is the default and training is the exception — the old mistake
      is now unexpressible rather than merely corrected.
- [x] B.2 — `DivergedRollout` + `DIVERGENCE_LIMIT`. `_predict` checks each
      rollout step for non-finiteness and for leaving ±10 in scaled space, and
      raises **at the step that did it** rather than letting
      `inverse_transform` turn it into a plausible-looking price.
- [x] B.3 — `alpha/phaseb_stability_probe.py`, two arms. **Every model is now
      3/3 bit-identical with zero drift and zero sign flips**; the unseeded
      control is 0/3 with 2.09–7.51 pp drift and Vanilla RNN flipping sign on
      2 of 3. Two intermediate results are recorded because they are
      informative rather than flattering: seed + inference-dropout alone left
      LSTM at 2/3, and adding thread pinning made it **0/3**, so the pinning
      was removed rather than kept as plausible-sounding insurance.
      `clear_session()` is what took every model to 3/3 — exactly as
      `tournament._seeded_tensorflow` predicted after measuring it while
      building a workaround that could not touch `forecast.py`.
- [x] B.4 — `reports/PHASEB_REPRODUCIBILITY.md`, including what the probe does
      **not** say: three trials cannot re-estimate a 7.2% rate, and
      `DIVERGENCE_LIMIT` is derived from the scaling rather than calibrated
      against an observed divergence, so it will first prove itself the day it
      fires.
- [x] B.5 — Six new tests, the rollout guard driven by a stub session so it
      stays in the default suite rather than behind `--runslow`.
      `tournament.py` now passes `seed=SEED` explicitly, keeping HT-1's
      instrument pinned to its own constant rather than to the application
      default; `_seeded_tensorflow` is left exactly as it is.

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
- [x] **Phase 2 — Portfolio writes.** Built and verified.
      `core/holdings.py::execute()` now holds a module-level
      `threading.Lock` around its whole read-modify-write — confirmed the bug
      was real by temporarily removing the fix and widening the race window:
      20 concurrent buys collapsed to a book of quantity 1 (19 trades silently
      lost). With the lock, all 20 land. Regression test
      (`test_concurrent_buys_do_not_clobber_each_other`) added to
      `app/tests/test_holdings.py`, plus an end-to-end version through the
      actual HTTP layer in `api/tests/test_portfolio_trade.py` (new: `api/tests/`,
      a `TestClient` + `holdings.STORE`/`LEDGER`-redirecting fixture, 7 tests,
      none touching the network or the real files).
      `POST /api/portfolio/trade` and `POST /api/portfolio/ledger/clear` added
      to `api/routers/portfolio.py`, calling `holdings.execute`/`save_ledger([])`
      unmodified. Frontend: `trade-form.tsx` wired into the Portfolio page.
      **Live end-to-end verification, on the real book**: snapshotted
      `holdings.json`/`transactions.json` (md5 before), bought then sold 0.01
      AAPL at the identical price through the actual UI, confirmed the round
      trip appeared correctly (positions 18→19→18, realised stayed $0.00,
      market value/cost basis returned to their exact original figures), then
      confirmed `holdings.json` was byte-identical to the pre-test snapshot
      and manually trimmed the two now-superfluous test transactions back out
      of `transactions.json`, restoring it to the identical md5 too — the
      book carries no trace of the test. Fast Python suite unchanged: 1283
      passed, 87 skipped.
- [x] **Phase 3 — The app shell.** Inserted 2026-08-22, ahead of the tab work,
      because the three finished pages turned out to be unreachable: every
      `href` in the frontend was `"#"`, `next/link` was imported nowhere, and
      `<Nav />` rendered only on the landing page, so `/signal`, `/chart` and
      `/portfolio` could be opened only by typing a URL. Four verified pages
      and nothing joining them is a missing-structure problem, and it blocked
      the product reading as a product regardless of how many tabs landed next.
      New `design-system/shell/src/lib/routes.ts` (the nav in one place, with
      the still-owed pages recorded but not rendered), a rewritten `nav.tsx`
      (real routes, `usePathname` active state, one shared `layoutId` pill that
      travels between entries), and `src/app/(app)/layout.tsx` — a route group,
      so URLs are unchanged and each page keeps its own `<main>` and width.
      Dropped the dead "Sign in" control (no auth exists anywhere in this app).
      Verified by clicking rather than by URL, plus the mobile menu at 390px:
      zero console/page errors, portfolio still matching Streamlit exactly
      ($2,870.08 / $2,363.45 / +21.44%, book signal −1 at 14%, NVDA SELL, SPY
      STRONG BUY). `tsc`/`eslint` clean, `next build` green.
      **Remaining phases reordered** to group by infrastructure cost, so each
      one adds exactly one new capability: the three cheap synchronous tabs
      (Monte Carlo, History, Overview) come next, then Research, then the
      long-running jobs. Plan at
      `C:\Users\onurc\.claude\plans\i-want-the-proceed-jolly-book.md`.
- [x] **Phase 4 — The three synchronous tabs.** Built and verified. The desk
      goes from three pages to six.
      New `api/routers/montecarlo.py` (`GET /api/montecarlo/{symbol}`, wrapping
      `core.montecarlo.run` on bars from `live.fetch`), `api/routers/runs.py`
      (`GET /api/runs`, `GET /api/runs/{id}`, `DELETE /api/runs/{id}`,
      `POST /api/runs/clear`, wrapping `core.runs.*`), `api/routers/studies.py`
      (`GET /api/studies` and `GET /api/studies/{symbol}`, wrapping
      `core.pine`), and `GET /api/stats/{symbol}` on the existing chart router
      (`core.data.describe`). New pages `montecarlo/` and `history/`, plus the
      existing `chart/` extended into the Overview with the study picker,
      price-axis overlays and oscillator panes.
      **Cross-checked against direct `core` calls, not by eye**: Monte Carlo at
      seed 42 returns byte-identical figures to `montecarlo.run` (median
      320.0682, p5 273.6463, p95 367.7874, prob_up 63.5), and Supertrend/
      WaveTrend values match `pine.INDICATORS[...].read()` exactly to six
      decimal places. The ORCL walk-forward run renders directionals
      [60, 80, 40] against its stored `mean_directional` of 60.
      Three things worth recording because they were found rather than
      designed: the Monte Carlo response downsamples server-side as planned
      (120 of up to 2,000 paths — the matrix is never serialised); the fan
      chart's first y-domain covered only the 5–95 band, so individual paths
      escaped the card; and `/montecarlo` scrolled horizontally at 390px until
      the symbol input got `min-w-0` (a flex item defaults to `min-width:auto`
      and refuses to shrink below its content). Every route is now checked for
      horizontal overflow at 390px, and none scrolls.
      **`pytest.ini` fixed in passing**: `testpaths` was `app/tests` alone, so
      `api/tests` had never been in the default run — the fast suite could
      report green with every endpoint broken, including through Phases 0–2.
      Now `app/tests api/tests`, and the default run is **1317 passed, 87
      skipped** — the same 1283 app tests as before plus the 34 API ones (7
      from Phase 2, 27 new here). No app test changed.
      `tsc`/`eslint` clean, `next build` green on all 6 routes, zero console
      errors on any page.
      Not ported from Streamlit's Overview, and deliberately noted rather than
      quietly dropped: the return-distribution histogram and the raw-bars
      table. Neither was in this phase's definition; both are small if wanted.
- [x] **Phase 5 — Research tab.** Built and verified. New
      `api/routers/research.py` serving all thirteen surfaces from **one**
      `GET /api/research`, because the tab reads one state — thirteen panels
      built from a single `research_view.load()`, so no two can disagree about
      what the ledger held at the moment they were read. New
      `research/page.tsx` and a generic `data-table.tsx` (columns travel with
      the rows: these frames genuinely differ in shape, and a table naming its
      own columns would silently drop whatever the record gained).
      **Both integrity behaviours survived the port, and one is now pinned by a
      test.** `api/tests/test_research_endpoint.py::
      test_reading_the_page_does_not_create_a_record` points both defaults at
      absent paths, calls the endpoint, and asserts the files are still absent
      — the HTTP layer is exactly where a "quick count" that reached past
      `research_view.load()` would quietly reintroduce the bug that Phase 7 §6
      and Phase 9 §6 rest on. A second test asserts the router delegates and
      passes no path, since a fixture path leaking into production is the other
      way that guard dies. The empty-state captions are carried through
      verbatim, including "an empty record, not a poor one".
      The replay-vs-production distinction is the page's spine, and the numbers
      show why it had to be: **the replay holds 12,873 scored rows across 336
      independent cutoffs at 0.4879 accuracy; the live ledger holds 93 rows
      across 2.** They sit in one labelled table — coverage and accuracy side
      by side, never pooled — under `study_warning` verbatim.
      One rendering defect found by looking: `study_warning` carries markdown
      emphasis (`**reconstructions**`) that Streamlit rendered and React showed
      as literal asterisks. Now rendered as emphasis; a check asserts no
      literal `**` survives anywhere on the page.
      Suite: **1324 passed, 87 skipped** (41 API tests, 7 of them new). No app
      test changed. `tsc`/`eslint` clean, `next build` green on all 7 routes,
      no horizontal overflow at 390px, zero console errors.
- [x] **Phase 6a — the forecast-ledger write boundary.** Inserted 2026-08-23,
      ahead of the job work, because `GET /api/signal/{symbol}` called
      `evaluate_and_freeze`: a *safe* HTTP method was appending to the
      append-only, never-regenerable prospective record. Every prefetch,
      StrictMode double-invoke, end-to-end replay and uptime check that landed
      on moved bars wrote a row nobody chose. Three guards now, each covering
      what the one before cannot: the read is a `GET` returning `freeze: null`
      and the freeze is `POST /api/signal/{symbol}/freeze`; a destination guard
      (`ledger_activation.writes_blocked`) refuses a *production* write from a
      test run or a process with `FORECAST_LEDGER_WRITES=off`, whatever method
      asked; and `api/tests/conftest.py` finally redirects
      `forecast_ledger.DEFAULT_PATH`, which it never had — the first Signal
      test written before this would have appended to the real ledger.
      All three surfaces still share **one** write path
      (`ledger_activation.evaluate_and_freeze`) and now stamp
      `metadata["provenance"]["source"]` — `streamlit`, `api`, `collector` —
      optional and absent by default, so no existing caller's records or
      identity digests move.
      **Found while doing it, recorded rather than fixed:** 21 of the 229
      production rows were written in small AAPL-first bursts on the exact
      dates of the frontend rebuild (2026-08-17 through 08-22), and the record
      cannot say whether a person or a page load asked for them, because
      provenance did not exist yet. Nothing was deleted. See §"Ledger
      provenance gap" below.
      Verified live against the real ledger: five `GET /api/signal/AAPL` page
      loads left it byte-identical (md5 `6851209e…`, 229 forecasts / 93
      outcomes, unchanged), and a `POST .../freeze` on a server started with
      `FORECAST_LEDGER_WRITES=off` returned the reading with
      `excluded: "FORECAST_LEDGER_WRITES=off …"` and wrote nothing.
- [x] **Phase 6b — Forecast + Trading agents as background jobs.** Built.
      New `api/jobs.py` (a `JobRegistry` on a **single** worker thread, since
      `clear_session()` is process-global) and `api/routers/jobs.py`:
      `POST /api/jobs/walkforward|project|agent` start,
      `GET /api/jobs/{id}` polls, `GET /api/jobs` lists, `GET /api/agents`
      serves the roster from `agents.REGISTRY` itself (all 19 names across the
      7 implementation modules, not a hand-copied subset). Each body is a
      transcription of the Streamlit button — same calls, same arguments, same
      `runs.save`, and the existing `progress`/`on_progress` callbacks carried
      into `Job.progress` instead of a `st.progress` widget.
      States are `queued → running → completed | failed`; every exception
      including `BaseException` leaves a terminal state, because a page polling
      a stuck `running` has no way out. An identical request still in flight
      returns the *same* job flagged `duplicate`, so a double-clicked button
      cannot start two trainings. Job ids carry a per-process boot id, so a
      poll after a restart is `410 Gone` with the reason rather than a `404`
      that reads like a typo.
      **No job can move the book.** `holdings.writes_disabled()` (new,
      thread-local so a concurrent trade ticket is unaffected) is armed by the
      registry around every job body, and `execute`/`save`/`save_ledger` raise
      inside it. Structural half asserted too: the jobs router names `holdings`
      nowhere.
      Verified live: two identical agent POSTs collapsed to one job, a third
      queued behind it and ran after, real LSTM walk-forward and projection
      completed with visible progress, results reached `GET /api/runs`, and
      `holdings.json`/`transactions.json` were untouched. The three saved runs
      were deleted afterwards; History is back to 114.
      **Phase B's precondition did not hold, and it is not this layer's
      fault.** Re-running `alpha/phaseb_stability_probe.py` unmodified today
      gives 1/3 models bit-identical in the `fixed` arm, not 3/3, with a sign
      flip in the Vanilla RNN cell — and two identical `forecast.project` calls
      on the main thread with no job involved still disagree intermittently
      (up to 3.66%). Dated correction appended to
      `reports/PHASEB_REPRODUCIBILITY.md`; `forecast.py` untouched, because
      changing it again is an owner call and would need a probe with enough
      trials to measure the surviving rate.
- [x] **Phase 6c — the Forecast and Trading-agents pages.** The other half of
      6b, built 2026-08-23. `/forecast` runs a walk-forward and then a
      projection; `/agents` trains any of the 19 policies and scores it through
      the same backtester. Both drive the job API and nothing else: a shared
      `lib/use-job.ts` starts a job, follows it to a terminal state and exposes
      the four states the server actually reports, and `job-progress.tsx`
      renders them. `queued` is shown as itself rather than as "loading" —
      the desk runs one job at a time on purpose, so waiting behind another
      training is the normal case and a spinner would make the queue look like
      a hang. A stale `410` offers to start again instead of retrying an id
      that can never resolve; a `duplicate` is a note, not an error.
      Two small additions rather than hardcoding: `GET /api/models` serves
      `forecast.MODELS` the way `GET /api/agents` already served
      `agents.REGISTRY`, so a page cannot offer an architecture the engine
      does not have; and `ApiError` now carries `status`, which is what lets a
      stale job be told from a missing one. Both routes moved out of
      `routes.ts`'s `PLANNED` into the live nav, which is now empty.
      **The honesty carried over, not just the controls.** The 0-of-N verdict,
      the "a single split landing on a good window would have looked
      convincing" warning, the note that a projection has nothing to score it
      against and the folds are its track record, and the sizing caveat that
      fixed-units understates an agent against a fully-invested benchmark are
      all on the pages. The projection additionally carries the 6b
      reproducibility finding, since a single path is one draw.
      Verified live against a running API: duplicate POSTs collapsed to one
      job, a real Q-learning training completed with visible progress and
      reached History, `410`/`404` came back for a stale/unknown id, a bad
      symbol and an impossible fold count were refused at start as `400`
      rather than as failed jobs, and `GET /api/signal` left the ledger
      byte-identical while the POST reported `excluded` under
      `FORECAST_LEDGER_WRITES=off`. The test run was deleted; History is 114.
      Suite **1392 passed, 91 skipped**; `tsc`/`eslint` clean, `next build`
      green on all 12 routes.
      **Still not built:** nothing from Phase 6. `forecast.py` remains
      untouched — the reproducibility defect is Phase B's and an owner call.
- [x] **Phase 6d — the instant agents, and a parity audit.** Added 2026-08-23.
      The Trading-agents tab offered three kinds of thing in one dropdown; only
      the RL policies needed Phase 6b's job machinery. The three fixed rules and
      the seven ported studies run in milliseconds, so `api/routers/strategies.py`
      serves them as plain `GET`s: `GET /api/strategies` is the catalogue and
      `GET /api/strategies/{symbol}` scores one. Everything delegates —
      `strategies.turtle`/`.moving_average`/`.signal_rolling`, `pine.signals`,
      `pine.bands`, and `backtest.run` — and a test computes the same numbers
      independently and compares, which is what would fail if the router ever
      grew its own copy of a rule.
      The dispatch table is deliberately **not** a new registry in `core`:
      `strategies.py`'s source hash is the version key for the three registered
      `rule_agent.*` models (`forecast_ledger._module_version`), so adding one
      would re-version live models against a ledger holding 229 real
      prospective forecasts. Same reasoning `pine.py` already gives for
      restating the buy/sell constants rather than importing them.
      **Nothing here writes** — no ledger, no book, no History run. Streamlit
      does not file a run for a rule or a study either (`runs.save` is reached
      only from the RL branch), so this is parity, not a shortcut. Asserted
      structurally from the parsed AST rather than by grepping the text, so the
      docstring is free to name the modules it promises not to import.
      The page groups the dropdown into "Instant · fixed rules", "Instant ·
      ported studies" and "Trains first · RL policies", badges the selected one
      by cost, and keeps every caveat: each study's published rule and its
      "tuning them on the series you are about to score is how a backtest
      flatters itself", the turtle's mean-reverting default, the RL learning
      curve's simplified objective, and the fixed-units sizing caveat.
      26 tests added. Suite **1418 passed, 91 skipped**; `tsc`/`eslint` clean,
      `next build` green on all 12 routes. Verified live: all ten instant
      agents scored against real AAPL bars, overlay studies returned their
      lines and oscillators returned `null`, and the ledger, book and runs
      directory were byte-identical afterwards.

## Streamlit parity: what is still missing (audited 2026-08-23)

Every tab is ported and the tab-for-tab list is complete. Seven capabilities
are not, and Phase 7 should not begin until each is either built or
consciously dropped. Enumerated so the choice is explicit rather than
discovered after `streamlit_app.py` is gone:

1. **Bundled datasets and CSV upload.** The sidebar's "Data source" offers
   Live ticker / Bundled dataset / Upload CSV. The API has one data door,
   `live.fetch`, so `dataset/*.csv` and `data.load_upload` are unreachable —
   and the offline fallback the live path's own error message recommends
   ("switch to a bundled dataset to keep working offline") does not exist.
2. **The multi-symbol portfolio builder.** `portfolio.build`, `align`,
   `normalise_weights`, `correlations`, `per_symbol_stats`,
   `diversification_note`, `REBALANCE` and `MAX_HOLDINGS` are exposed nowhere.
   `GET /api/portfolio` prices the *book you hold*; it cannot construct and
   backtest a weighted basket with a rebalance schedule. This is the single
   largest gap.
3. **Single-split forecasting.** `forecast.run` — the Forecast tab's other
   evaluation mode, with its 1–10 simulations — has no endpoint. Only
   `walk_forward` and `project` do. Arguably the honest half survived, but it
   is a capability that would disappear.
4. **Non-daily bars anywhere in the UI.** The API passes `interval` through
   and all five of `live.INTERVALS` work; no page exposes a switcher, so the
   new frontend is daily-only. Streamlit's toolbar carries 1H/4H/D/W/M across
   every tab. Intraday analysis is reachable by hand-editing a URL and by no
   other means.
5. **The date-range trim.** Streamlit slices the frame once and every tab
   works off that slice. The API takes `period`, not an explicit start/end
   window, so "score this rule on 2021 only" cannot be asked.
6. **The two Ultimate-signal toggles.** `ultimate.evaluate` accepts
   `include_agents` and `model`; `GET /api/signal/{symbol}` passes neither, so
   both sit at their defaults. Turning the rule-based agents off, and the whole
   model-assisted verdict ("Include the forecast" — walk-forward plus
   projection folded in through the significance gate), are unavailable.
7. **The agents price chart.** Streamlit draws candles with buy/sell markers
   and the study's overlay bands beneath them. The API already returns `bands`,
   `buys` and `sells`; the page renders an equity curve and a trade table
   instead. Frontend-only — no API work needed.

Also absent, and deliberately: **Lite mode**. No capability lives there that
Pro lacks, so nothing is lost by the new shell not having a reduced variant.
The return-distribution histogram and the raw-bars table from the Overview tab
are likewise frontend-only omissions — `GET /api/ohlcv` already carries what
they need.

- [ ] **Phase 7 — Cutover.** Once every tab is ported and spot-checked against
      Streamlit, retire `streamlit_app.py` or keep it as an internal fallback.
      The headless habits survive either way: `python -m core.collector` and
      `python -m core.score_outcomes` are run by hand on trading days and have
      nothing to do with the UI.

---

## Ledger provenance gap (found 2026-08-22/23, not remediable)

`app/forecast_ledger.sqlite3` holds 229 forecasts. Their `generated_at` values
fall into three collector sweeps (2026-08-15: 86 rows, 08-16: 32, 08-22: 86)
and eight small bursts of 2–6 rows, every one of them beginning with AAPL:

    08-17 13:52 AAPL      08-20 19:01 AAPL, NVDA     08-21 12:42 AAPL, ORCL
    08-18 01:21 AAPL      08-20 19:04 META           08-22 23:10 AAPL
    08-19 14:37 AAPL

21 rows. Those dates and symbols are the frontend rebuild's own verification
history — Phase 0 checked AAPL and NVDA, Phase 4 checked ORCL — and AAPL is
simultaneously the Streamlit app's default symbol (`streamlit_app.py:373`) and
the new Signal page's (`signal/page.tsx`). **The record cannot say which**, and
that is the finding: until 2026-08-23 no row carried provenance, so a forecast
frozen because a person asked and one frozen because a page mounted are
identical after the fact.

Nothing was deleted, and nothing should be: the ledger is append-only and a row
whose origin is uncertain is still a row, while a ledger someone has pruned on
a judgement call is no longer evidence of anything. What changed is forward:
`GET` no longer writes at all, and every new row names its source. Whether the
21 should be excluded from a future promotion count is an owner decision, and
it can be made because the dates are enumerated above — it cannot be made by
inspecting the rows, which is the point.

---

## What stays closed (pointer only, not re-litigated here)

V2–V2.3 abandoned; V3 3/3 families rejected; V4 slot 1 spent/slot 2 barred;
Single-Name Phase 1 DO NOT ADVANCE; Family-10 pilot failed on power; AMS-1
rejected; HT-1 0/27. See `reports/EXPERIMENT_REGISTRY.md` for the full record.
No fourth family, no re-test, no threshold rescue, no sign flip — all barred
for the reasons recorded in each study's own report.
