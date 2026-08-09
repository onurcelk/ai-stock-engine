# `validation/` Evidence Manifest — the point-in-time single-name study

**Written 2026-08-09 under master roadmap v2 §3.2. Purpose: record the preservation
decision for the `validation/` study, define its minimum complete record, and state
what is deliberately not preserved and why.**

Context: `V2_3_EVIDENCE_MANIFEST.md` §5 finding 6 flagged `validation/` as "**also
entirely untracked** … a distinct study, not part of the V2 → V2.3 alpha line …
**flagged as still unpreserved and needing its own decision.**" This manifest is that
decision.

**Nothing in this manifest changes any result.** No prediction, score, report figure or
frozen artefact was modified. Nothing was scrubbed, tidied or regenerated.

---

## 1. The decision

**`validation/` is preserved as its own study, in its own commit, with its own manifest
— not merged into the V2 → V2.3 record.**

Three parts, all three required by roadmap §3.2:

1. **Preserve.** It is a real study with a real result, a real leakage-control design
   and a conclusion the programme now relies on (roadmap §2.3 makes always-up and
   no-change *mandatory* baselines **because of this study**; §18 forbids loosening the
   HOLD floor **because of this study**). A load-bearing result that exists only as
   untracked files is exactly the defect the V2.3 audit found for `alpha/`.
2. **Reuse, deliberately.** The Phase 7b harness decision is made at §6 below, not left
   open.
3. **Do not merge.** Different question, different object, different baseline, different
   protocol. Its numbers never enter a V2/V2.3 table and never enter a V3 cross-sectional
   comparison. It is registered as `PIT-1` in `EXPERIMENT_REGISTRY.md` §3.5.

---

## 2. Scope — and why the study's *subject* is in scope with it

`validation/` alone is not a preservable record. The study's finding is a statement
about a specific prediction engine, and the modules that engine lives in are
**untracked or modified**. Preserving the harness without them would preserve the
question and lose the thing it was asked about — the same class of defect being fixed.

The scope is therefore the **import closure**, computed rather than guessed:

```
validation/pit.py       -> app.core.live
validation/predict.py   -> app.core.indicators, app.core.ultimate
validation/model.py     -> app.core.forecast, app.core.ultimate
app/core/ultimate.py    -> app.core.{data, indicators, live, strategies}
app/core/live.py        -> app.core.data
app/core/forecast.py    -> sklearn, tensorflow (no first-party imports)
app/tests/test_validation.py -> app.core.{live, ultimate}, validation.{metrics, outcomes, pit}
```

`data.py` and `strategies.py` are **already tracked and unmodified**. The closure adds
exactly **four** engine modules.

**The tests of those four modules come with them**, so the commit is self-verifying:
a checkout can run the tests for every module it contains, which is the standard the
V2.3 commit met with its 155 alpha tests. `test_live.py`'s working-tree change is
**purely additive** (65 insertions, 0 deletions) and covers the new `live.py` functions;
`test_ultimate.py`, `test_indicators.py` and `test_forecast.py` are new files importing
only closure modules. **184 tests, all passing** (2.9s).

`app/core/quotes.py` and `app/core/theme.py` are untracked but are **not** in the
closure — they are application UI work and stay excluded, together with `charts.py`,
`holdings.py`, `streamlit_app.py`, `ROADMAP.md` and the tests of those modules
(`test_charts.py`, `test_ui.py`, `test_holdings.py`, `test_quotes.py`, `test_theme.py`).
No committed file imports any of them.

### 2.1 Provenance of the four engine modules

The frozen predictions were written at **2026-08-07 23:12:10**. Every module in the
closure was last modified **before** that, and none has been touched since:

| File | Last modified | vs. predictions frozen |
|---|---|---|
| `app/core/live.py` | 2026-08-07 17:31:56 | −5h 40m |
| `app/core/indicators.py` | 2026-08-07 17:44:42 | −5h 27m |
| `app/core/ultimate.py` | 2026-08-07 21:44:52 | −1h 27m |
| `app/core/forecast.py` | 2026-08-07 22:07:39 | −1h 05m |
| — | **2026-08-07 23:12:10** | **`out/predictions.json` written** |
| `app/tests/test_validation.py` | 2026-08-07 23:20:29 | +8m |
| `validation/out/model.jsonl` | 2026-08-08 00:15:31 | +1h 03m |
| `validation/out/calls.csv` | 2026-08-08 00:15:50 | +1h 04m |
| `validation/REPORT.md` | 2026-08-08 00:20:49 | +1h 09m |

So the committed engine is, on this evidence, the engine that produced the predictions.

**The honest limit, stated in the same terms as `V2_3_EVIDENCE_MANIFEST.md` §8:
mtimes are not an audit trail.** They establish an ordering consistent with the claim;
they cannot prove it. From this commit forward the claim becomes checkable. Before it,
it does not.

---

## 3. The record — code and documents

| File | Bytes | SHA-256 | Purpose |
|---|---:|---|---|
| **The study's own account** ||||
| `validation/README.md` | 3,535 | `dca2fe23909e532dade716858c429174ac8b725194cf59f4f56b1e731718d838` | design, the three leakage mechanisms, **and the known limits stated rather than hidden** |
| `validation/REPORT.md` | 46,607 | `deda3daea32d7c397fa904db6685ae353a03b9eaadbe139540171f0dde677fd5` | **the result — the primary record** |
| **Harness — the one-door design Phase 7b reuses** ||||
| `validation/pit.py` | 6,918 | `dad0a2f7fc8909b2001be7bc8b74dcad16fe6b7546b1296c6d6fa2ce3fcc9479` | **the single data door.** `fetcher(cutoff)` truncates before it trims; the only way the prediction stage reads bars |
| `validation/schedule.py` | 3,916 | `12f84e0de076afa4b01fe89e9ee7662a3b95c6d9f6ccc0e377ad1532e439a8cd` | the experiment grid: which dates, which symbols, which horizons |
| `validation/predict.py` | 9,359 | `d69d420c646b44384ae008ae7cce9cd2e54085d352b5e952d4a2cb7682f084a2` | stage 1 — **writes `out/predictions.json` and never reads it**; refuses to overwrite |
| `validation/model.py` | 6,967 | `6e3cd82ec931dd16f16e5ce2507387f2a1116fdf88d1626e0c54ac561db5449e` | the LSTM arm; appends to `model.jsonl`, resumable |
| `validation/outcomes.py` | 6,957 | `a83e97295ab1237ce93d58792a48d925d0775b5db0de6cdfc1315783ba1483fe` | **the forward-reading side**, reachable only from scoring |
| `validation/metrics.py` | 5,558 | `f7e5475d18df34a0b45d6ff4272671f439dfadae37c90b8b3fd478a369d9387e` | intervals **clustered by cutoff date** |
| `validation/score.py` | 43,976 | `3ae447f631c453ee40d460cbd857a79ca9d113d8f131e4abdcb02a8744d95003` | stage 2 — **reads predictions and never writes them**; prints every table |
| `validation/__init__.py` | 606 | `9ad2badaa9b7306791a2c9d27b823c55f20afb291da9c192324ed0852a377d6f` | package marker |
| **The subject — the engine the study measured (§2)** ||||
| `app/core/ultimate.py` | 43,936 | `e629405d1b6b23c513853cd81336bfcd78a44d0c0e1a84b4604ac44d6fb8f97a` | **the consensus engine, the HOLD floor and the significance gates** — `MIN_T`, `MIN_CONFIDENCE`, `FAMILY_CAP` |
| `app/core/indicators.py` | 15,230 | `b36bc166fe61a7d1934eeed986c2bd217a37ba46e846cda899669cd18f1b9263` | the indicator layer the rule agents read |
| `app/core/forecast.py` | 19,629 | `2a34a5483c70db67f03f2d4ce28f49b21f05c472086c9e70904c801755f08434` | the LSTM projection — **the component that changed zero verdicts** |
| `app/core/live.py` | 13,646 | `03584fc16884707c0e4893d93c61c19e5db276783b74cbfa90ed2bb51338d2ee` | bar access; the door `pit.py` wraps |
| **Tests — 184, all passing** ||||
| `app/tests/test_validation.py` | 8,754 | `134e5a3f11510baed497fb86f9a1a882b4981e39edd0fb8aafffd0411216d017` | **`test_future_cannot_change_the_verdict`** — two series identical to the cutoff, violently different after, asserted to the last decimal |
| `app/tests/test_ultimate.py` | 21,650 | `0a642bc52b759debf8ed37d915abff3e9c0793deadcded42f6baabc6e0e311fa` | the consensus engine, the HOLD floor, the significance gates |
| `app/tests/test_indicators.py` | 8,346 | `a1ae58a86662ff51fadb144cf54591593972b7bdaca85097423ad5498e27c4b9` | the indicator layer |
| `app/tests/test_forecast.py` | 3,777 | `eb313ac73a17fd8a3e530f7a6d14b167ffb4396efd8abb64fd77c670d093b29d` | the LSTM projection |
| `app/tests/test_live.py` | 9,992 | `ecf91ebbc64589e5db4110e1806502c2bb26296b8aa7c56d6f9a1fad5b8388e6` | bar access and cache behaviour (**additive change**, +65/−0) |

---

## 4. The record — frozen artefacts, with hashes

These are the evidence. `calls.csv` is to this study what the `.pkl` per-cutoff series
are to V2.3: **one row per (cutoff, symbol, system, window)** carrying the prediction,
the outcome and the verdict, so any number in the report can be re-derived from
per-observation data rather than checked against a summary.

| File | Bytes | SHA-256 | Purpose |
|---|---:|---|---|
| `validation/out/predictions.json` | 6,288,337 | `e5a2c61defff42fec1656f74d08911a1b5a1066d155ec2554c31db1bf714cbb7` | **the 360 frozen predictions** — written before any outcome was read |
| `validation/out/calls.csv` | 4,398,664 | `9e764a1bec999d07377d5da9b33eed04d04f2a026637af97268a019569e55702` | **20,999 scored rows** — the re-derivation basis |
| `validation/out/model.jsonl` | 89,212 | `f6e90977653f88328874e6a212cc58b994a4173141af748b56e97792666e8538` | the 96 neural-forecast experiments |
| `validation/out/report_raw.txt` | 32,940 | `e20f752dc6d7188334b314cf2b207cc4d4651e2ba32341c4d7b458a98aa94b31` | the scoring run's raw stdout — **see §5 finding 2** |

**Study parameters, fixed by the artefacts rather than by prose:**

| | |
|---|---|
| Cutoffs (12) | 2022-03-08 · 2022-10-10 · 2024-08-13 · 2024-09-05 · 2024-12-10 · 2025-03-27 · 2025-06-23 · 2025-11-28 · 2026-02-06 · 2026-05-07 · 2026-07-07 · 2026-07-24 |
| Symbols (30) | AAOI AAPL AMD AMZN AVAV BTC-USD CBRS EOSE ETH-USD EURUSD=X GOOGL HIMX INTC META MSFT NBIS NVDA ORCL PL PLTR QQQ RKLB SLV SNDK SPCX SPY T TSLA UAMY VOO |
| **Effective n** | **12.** Thirty symbols on one day are not thirty observations |

---

## 5. Questionable material — documented, not silently removed

| # | Finding | Assessment |
|---|---|---|
| 1 | **The `origin` remote is `huseinzol05/Stock-Prediction-Models`, a third party's public repository.** | Unchanged from `V2_3_EVIDENCE_MANIFEST.md` §5 finding 1 and roadmap §0.4. **This commit is local only and is not pushed.** A push is a §27A human decision and would publish this work into someone else's repo. |
| 2 | `validation/out/report_raw.txt` line 660 embeds the author's absolute local path: `Wrote C:\Users\<user>\Desktop\AI Stock\...\validation\out\calls.csv`. | **Committed as-is, deliberately, and flagged rather than scrubbed** — identical treatment to `V2_3_EVIDENCE_MANIFEST.md` §5 finding 9. This is a *run log*: what the study printed as it executed. Editing it to tidy a path alters a frozen artefact and is indistinguishable from tampering. The disclosure is a Windows username. **If this repository is ever published, the remedy is a decision not to publish this file — never a quiet rewrite of it.** |
| 3 | **The 30-symbol universe is a personal watchlist**, not an index. It includes crypto (BTC-USD, ETH-USD), FX (EURUSD=X), ETFs and several small caps, and it appears in `schedule.py`'s output, `predictions.json` and `calls.csv`. | **Preserved, and flagged as a disclosure.** The universe is a study parameter — `README.md` already says so ("whatever the local cache holds — symbols a live user chose to watch *today*. Nothing that delisted is in it"), and removing it would destroy the record's meaning and its survivorship caveat at once. It reveals *what is watched*; it reveals **no position, cost basis or trade**. **This is the second item to weigh before any push.** |
| 4 | Secret scan over all candidate `.py`, `.md`, `.json`, `.csv`, `.jsonl` and `.txt` files: API keys, credentials, tokens, bearer/authorization headers, `sk-`/`xox`/`AKIA` patterns. | **No matches.** |
| 5 | Machine-path scan (`C:\Users`, `/Users/`, the username, `Desktop`) over all candidate source, docs and artefacts. | **One match — finding 2.** Source and documents are clean; `predictions.json`, `calls.csv` and `model.jsonl` are clean. |
| 6 | Does the study read personal financial data? | **No.** No module in `validation/` references `holdings`, `transactions` or `portfolio`; the universe comes from `pit.cached_symbols()`, i.e. the local bar cache. `app/holdings.json` and `app/transactions.json` remain gitignored — re-verified via `git check-ignore` at `.gitignore` lines 18–19. |
| 7 | `validation/__pycache__/` (144 KB). | Excluded; already matched by `.gitignore` line 3 (`*__pycache__`). |

---

## 6. Harness reuse — the Phase 7b decision (roadmap §3.2 item 2)

Phase 7b re-scores any surviving V3 signal **per symbol**, and this harness is already
the machinery for it. The decision, made now so Phase 7b does not re-litigate it:

| Component | Decision | Why |
|---|---|---|
| `pit.py` one-door fetcher | **reuse as-is** | The guarantee is structural — truncate before trim, one entry point — and it is the same shape roadmap §6.1 prescribes for the EDGAR filings door. Rewriting it would discard a tested guarantee to gain nothing. |
| Two-process predict/score split | **reuse as-is** | The property that matters is that *the code which sees outcomes cannot reach the code which makes predictions*. This is enforced by process boundary and a refuse-to-overwrite rule, not by intent. |
| `test_future_cannot_change_the_verdict` | **reuse, and extend** | Extend it with the restatement case roadmap §6.1 requires: **a later restatement of an earlier period must not enter a historical observation**, on top of the existing rewrite-the-future case. |
| `metrics.py` cutoff-clustered intervals | **reuse, with one change** | Adopt `alpha/stats.py`'s moving-block bootstrap (`BLOCK_LENGTH = 4`) as the headline interval so V3's single-name and cross-sectional numbers are computed the same way and are comparable. Roadmap §2.6 names those functions as the ones to reuse rather than rewrite. |
| `schedule.py` 12-cutoff grid | **rebuild** | **Twelve cutoffs cannot support Phase 7b.** This is a §2.6 matter, not a preference: the grid must be re-derived from the effect being sought, and the achievable half-width recorded in the preregistration **before** any Phase 7b run. Reusing 12 cutoffs would repeat the study's own binding limitation. |
| `score.py` report generation | **rebuild** | 43,976 bytes written around this study's specific nine components. The *baselines* it encodes — always-up, no-change, and scoring against the period's actual up-rate rather than 50% — are what carry forward, and roadmap §2.3 already carries them. |
| `model.py` LSTM arm | **do not reuse** | It contributed **zero** verdicts across 257 of 257 gated horizon-slots and lost to always-long. Re-testing it with a larger model is precisely the move roadmap §2.9 forbids. |

---

## 7. What this commit does and does not establish

**Does:** the study's design, its subject, its frozen predictions and its per-row scored
outcomes now have a verifiable history. The claims "the predictions were frozen before
outcomes were read", "the leakage test was not edited to pass" and "the engine was not
adjusted after the result" become checkable from here forward.

**Does not:** it cannot retroactively prove any of those about the run on 2026-08-07.
The evidence for that remains what §2.1 records — a modification-time ordering in which
every engine module predates the frozen predictions — plus the structural controls
(one door, two processes, a leakage test) which are checkable now.

**Does not, either:** it does not make the study's conclusion stronger. Twelve cutoffs
is twelve effectively independent market draws. Preserving a resolution-bound result
preserves a resolution-bound result — which is the point of recording the resolution
next to it.
