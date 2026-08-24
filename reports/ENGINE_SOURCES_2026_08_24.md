# Engine source additions — owner decision, 2026-08-24

**Class: owner decision and implementation record. Not a study. 0 budget slots spent,
no forward return read, no gate evaluated, no measurement of any kind performed.**

This document exists because four components now hold PRODUCTION status without evidence
carrying them there, and `app/core/promotion.py` requires that debt to be named in writing
rather than implied.

---

## 1. What was directed, and what the account holder was shown first

On 2026-08-24 the account holder asked for six indicators: opening range breakout, VWAP
mean reversion, VIX mean reversion, post-earnings announcement drift, options selling, and
option premium harvesting.

**These are the same six directed on 2026-08-22, all of which were resolved and closed two
days earlier.** That conflict was raised before any code was written, per `CLAUDE.md` §1.3,
and the standing verdicts were restated:

| Candidate | Verdict as it stood | Where |
|---|---|---|
| `vwap_reversion` | REJECTED | `EXPERIMENT_REGISTRY.md` §22 |
| `orb_1h` | REJECTED — +0.9 bp against a 39 bp hurdle, −4.1 bp net of costs | §24, `ORB1H_RESULT.md` |
| PEAD-1 (SUE, event-time) | REJECTED — real, sub-threshold, market-confounded | §25, `PEAD1_RESULT.md` |
| VIX1 | Power gate FAILED, closed at 0 slots | §26, `VIX1_POWER_GATE.md` |
| Options execution layer | Stage 1 data admissibility FAIL — structurally inadmissible | `OPTIONS1_ADMISSIBILITY.md` §3 |

The account holder was offered three paths for the four free-data candidates — ship them as
catalogue strategies, add them to the prediction engine, or leave them closed — and was told
in the same breath that the engine path re-versions the incumbent and splits the live
prospective record. **The account holder chose the engine.** For the options half, of the
three paths offered (live-chain screener with no backtest, amend §27B to permit paid data,
or drop), **the account holder chose the screener.**

Both are the account holder's decisions to make. This document records them; it does not
re-argue them.

---

## 2. What this decision is NOT

Stated explicitly, because the distance between these two things is the whole of §3.2:

* **It is not a re-measurement.** No forward return was read. No gate was run, re-run,
  weakened, or reinterpreted. The verdicts in §1 stand exactly as written and are unchanged
  by anything here.
* **It is not a reversal of those verdicts.** Every one of the four remains REJECTED or
  gate-failed on the record. Entering the engine is a production decision, not a research
  finding, and no document in `reports/` now says otherwise.
* **It does not reopen a programme.** No budget slot was spent or freed. PEAD-1's §25
  closure of SUE "permanently at every formulation tested" is untouched: this ships SUE as
  a weighted input, it does not test SUE again.
* **It does not touch HT-1.** See §4 — the frozen roster is still 27, and this was very
  nearly broken silently.

---

## 3. What changed

### 3.1 Four sources entered `indicators.SOURCES`

| Key | Family | Construction |
|---|---|---|
| `vwap_reversion` | `reversion` | `_bollinger_reversion` with a 10-bar VWAP as the band centre. Window and sign copied from `ht2_vwap.py`, which froze both before any forward return was read. |
| `vix_reversion` | `reversion` | Williams Vix Fix, z-scored against its own 22-bar distribution, firing above +2σ. **One-sided.** |
| `opening_range` | `trend` | Break beyond the session's first bar in ATRs. Intraday frames only; detects this from the frame's own timestamps. |
| `pead` | `fundamental` (new) | SUE decaying linearly across 60 days from the filing's acceptance. |

Three points of construction discipline:

**`vix_reversion` is one-sided on purpose.** The Vix Fix is a bottom finder. An elevated
reading is capitulation and argues up; a *low* reading is merely the absence of fear, and no
study has claimed that predicts a fall. The short half was not invented, and a test asserts
the source can never argue short.

**`pead` gets its own family.** `ultimate.cap_families` exists to stop correlated evidence
carrying a verdict alone, and that only works if the grouping tracks what would actually
double-count. An earnings surprise does not double-count a moving average — it is the one
source in the engine that is not a reading of the price. Filing it under `reversion` or
`momentum` would have let it absorb a cap it has no business absorbing.

**No parameter was retuned.** `pead` reuses `NetIncomeLoss`, PEAD-1's own concept, because
choosing a different one would be retuning a rejected arm's free parameter. `vwap_reversion`
reuses HT-2's frozen window and threshold. Nothing here reads a result to pick a setting.

### 3.2 A second data door, and why it did not bend the source contract

`indicators.py`'s sources are pure functions of a frame: no network, no state, no symbol
identity. PEAD needs all three. Rather than widen that contract, `app/core/filings_evidence.py`
attaches two **columns** (`sue`, `days_since_filing`) to the frame in `ultimate.evaluate` —
the one place that knows which firm it is holding — and `_pead_drift` reads them like any
other column. A frame without them scores zero, which is the same "no opinion" a close-only
frame already gets from the volume sources.

Point-in-time safety is `alpha/filings_features.replay`'s, unmodified: each bar reads the
acceptance step in force strictly before its own 16:00 ET close, so a restatement accepted in
March cannot reach into January. `app/tests/test_filings_evidence.py` checks the
truncate-and-compare property directly at every bar, and
`test_future_cannot_change_the_verdict` still passes.

### 3.3 The cache is untracked, and that is visible rather than silent

`alpha/edgar/facts.parquet` is gitignored — a local rebuild, not repository content. A
machine without it produces a permanently silent `pead` source while carrying an **identical**
`technical_sources` version string to a machine that has it. That is precisely the "two
engines wearing one version string" failure `tournament.py`'s docstring warns about.

What closes it is the ledger: `forecast_ledger.fingerprint_frame` digests the frame's columns
and rows, so a forecast made without the cache carries a different input fingerprint from one
made with it. The distinction lands in the record, which is where it has to land. `attach`
therefore returns the frame *unchanged* when it cannot look, rather than adding a column of
NaN — "we could not look" and "we looked and found nothing" are different claims and the
fingerprint must be able to tell them apart.

---

## 4. The near-miss worth recording

`tournament.py::_build_roster` derived HT-1's technical family by iterating the **live**
`indicators.SOURCES` dict. That was safe only under an invariant the module stated in its own
docstring — "no candidate enters `indicators.SOURCES`" — and this decision broke it.

**Adding four sources silently grew HT-1's frozen 27-candidate roster to 30.** The other three
families were already explicit frozen tuples; the technical one was the single derived
exception. `test_the_roster_is_the_declared_twenty_seven_plus_two_references` caught it
immediately.

Fixed by naming the ten sources HT-1 actually measured in `tournament.HT1_TECHNICAL`, so the
frozen roster is now immune to any future engine edit. **Sources added after HT-1 ran are not
HT-1 entrants and are not backfilled into its leaderboard.**

This is recorded rather than quietly repaired because the lesson generalises: a frozen record
that derives any part of itself from live code is not actually frozen, and the census test was
the only thing standing between this decision and a corrupted study.

---

## 5. The version split

Both hashes moved. This is the cost the account holder was told about and accepted:

| Version key | Module | Moved? |
|---|---|---|
| `technical_sources` | `app/core/indicators.py` | **Yes** — four sources added |
| `ultimate_ensemble` | `app/core/ultimate.py` | **Yes** — the filings attachment, and one stale comment (`MIN_T`'s justification said "thirteen sources"; it is sixteen) |

`application_version` is recorded on every forecast and gates nothing, so no logic changes.
What changes is that forecasts frozen from 2026-08-24 onward are **not comparable** to earlier
ones as the same engine, and must not be pooled with them. `PooledVersionsError` already
refuses to span a version boundary in one measurement; this is the boundary it will refuse at.

`app/forecast_ledger.sqlite3` was not touched. Nothing was deleted, regenerated or rewritten.

---

## 6. Promotion status: four new entries in the debt table

All four hold PRODUCTION and none passed a gate. `promotion.GRANDFATHERED` now carries a
third distinct reason alongside "closed form, the gate is the wrong instrument" and "incumbent
by history":

> Measured standalone on this repository's own instrument and **REJECTED**, holding PRODUCTION
> because the account holder directed it, not because evidence carried it there.

`PROMOTED` remains empty. Nothing in this repository has ever been promoted on evidence, and
this decision does not change that — it is the first time something has been promoted
*explicitly without* it, which is why the reason is worded to survive being read a year from
now by someone who was not in the conversation.

**What protects the verdict is downstream, not here.** `ultimate.py` weights every source by
measured skill on a held-out tail, shrunk by its own t-statistic, and may lower a weight to
zero but is structurally forbidden from flipping a sign. A source with no edge contributes
nothing and says so in its own `Why not` column. That is the mechanism that makes admitting
four rejected sources survivable; it is not a reason to admit a fifth.

---

## 7. The options half

Scoped to `OPTIONS1_ADMISSIBILITY.md` §4's second path, and no further.

**Shipped:** `app/core/options.py` and `api/routers/options.py` — a live-chain premium screen
for cash-secured puts and covered calls. Strike, bid/ask, mid, implied vol, open interest,
days to expiry, moneyness, static yield and cushion, ranked by yield.

**Not shipped, and not shippable under §27B:** option P&L, margin modelling, tail-risk
simulation, assignment probability, greeks, or any backtest. Naked calls and spreads are not
offered as structures at all, because both need a margin model and a margin model needs the
historical implied-vol surface that §3 established does not exist for free.

Three properties are enforced by test rather than by convention:

1. **`WARNING` is part of every payload**, on the same principle as `research_view`'s
   `study_warning`. A yield column with no caveat is read as a backtested return.
2. **Nothing writes.** `api/tests/test_options.py` asserts the router reaches neither
   `holdings`, `ledger_activation` nor `forecast_ledger`, and declares no non-GET method. A
   premium screen must never be recordable as a prospective forecast: the ledger's value rests
   on every row being replayable against real subsequent prices, and an expired option's quote
   can never be.
3. **In-the-money strikes are hidden by default, visibly.** Ranking purely by yield puts
   the worst trade on the board at the top: an in-the-money put quotes an enormous premium
   *because* it is nearly certain to be assigned, and on expiry day that annualises into the
   thousands of percent. Verified against live AAPL data — a 322.5 put against a 309.35 spot
   ranked first at 1562% p.a. with a −4.3% cushion. That is correct arithmetic answering a
   question nobody asked, so `out_of_the_money_only` defaults to True. It is a switch, not a
   silent filter: the payload states which way it was set, `cushion` says which side of the
   money every row is on, and turning it off hides nothing.
4. **No column may claim to be a realised return.** A test enumerates the forbidden names and
   requires anything yield-shaped to carry `static_` in its own name, so the assumption that
   makes premium selling look free — that the option expires worthless — is visible in every
   column header that depends on it.

---

## 8. Test state

Baseline before any edit: **1563 passed, 91 skipped.**
After: **1618 passed, 91 skipped.** 55 tests added, none removed, none weakened.

`test_future_cannot_change_the_verdict` verified passing explicitly after the prediction-path
change, per `CLAUDE.md` §4.2.

One test assertion was changed:
`test_the_grandfathered_list_names_the_incumbent_debt_separately` required exactly two distinct
reasons in the debt table. It now requires three, **and additionally** requires each
owner-directed entry to contain the word REJECTED in its reason and to differ from the
closed-form excuse. The test's stated purpose — "must not share one blanket excuse" — is
strengthened by this, not relaxed: the change adds a kind of debt and adds an assertion about
it.
