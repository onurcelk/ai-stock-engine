# V2.3 Evidence Manifest

**Written 2026-08-08 at programme closure. Purpose: define the minimum complete
research record for the V2 / V2.1 / V2.2 / V2.3 alpha programme, record what is
preserved, and record what is deliberately not preserved and why.**

Context: the independent decision audit
([`V2_3_FINAL_DECISION_AUDIT.md`](V2_3_FINAL_DECISION_AUDIT.md)) found that
`git ls-files alpha` returned **zero files** — the entire four-study record was
untracked, so claims of the form "the log is append-only", "no test was edited to
pass" and "the pre-registration was accepted before the first fit" were
unfalsifiable from the repository. This manifest and the commit it accompanies fix
that.

**Nothing in this manifest changes any experiment result.** No pre-registration,
threshold, seed, target, feature, prediction or frozen artefact was modified. Two
textual corrections were made and are itemised in §6.

---

## 1. Scope decision

The record is **self-contained**: `alpha/` imports nothing from `app/` (verified by
grep), and the five alpha test modules import only `alpha`, the standard library,
numpy, pandas and pytest. So the research record can be preserved without dragging
in unrelated application work.

**Included:** everything needed to (a) read what was pre-registered, (b) read what
was found, (c) re-run the studies, and (d) re-derive the headline numbers from
per-cutoff data rather than from summaries.

**Excluded:** regenerable derived data, vendor market data, and unrelated
in-progress application code. Every exclusion is listed in §4 with a reason, and
every excluded *artefact* has its SHA-256 recorded here so it stays identifiable
even though it is not stored.

---

## 2. The record — code and documents

| File | Purpose | Reproducibility | Audit |
|---|---|---|---|
| **Pre-registrations — what was committed to in advance** ||||
| `alpha/PREREGISTRATION.md` | V2 protocol, fixed before first fit | — | **required** |
| `alpha/V2_1_PREREGISTRATION.md` | V2.1 protocol | — | **required** |
| `alpha/V2_1_LADDER_PREREGISTRATION.md` | V2.1 ladder; §5.2 exam gate | — | **required** |
| `alpha/V2_1_VALIDATION_SETUP.md` | 72-cutoff exam construction, benchmark hierarchy, nine gates | required | **required** |
| `alpha/V2_2_PREREGISTRATION.md` | V2.2 carrier protocol | — | **required** |
| `alpha/V2_3_PREREGISTRATION.md` | V2.3 protocol; §9 abandonment criteria | — | **required** |
| `alpha/V2_3_RESEARCH_DESIGN.md` | the design pass V2.3's prereg was argued from (§6, §6.2 superseded) | — | **required** |
| **Reports — what was found** ||||
| `alpha/V2_REPORT.md` | V2 result | — | **required** |
| `alpha/V2_1_LADDER_REPORT.md` | V2.1 result; gate closed | — | **required** |
| `alpha/V2_2_LADDER_REPORT.md` | V2.2 result | — | **required** |
| `alpha/V2_3_LADDER_REPORT.md` | **V2.3 result — the primary record** | — | **required** |
| **Experiment logs — every run, in order** ||||
| `alpha/EXPERIMENT_LOG.md` | V2 runs, incl. the dead-`ret_12_1` run | — | **required** |
| `alpha/V2_1_EXPERIMENT_LOG.md` | V2.1 runs | — | **required** |
| `alpha/V2_2_EXPERIMENT_LOG.md` | V2.2 runs | — | **required** |
| `alpha/V2_3_EXPERIMENT_LOG.md` | V2.3 runs, the abort, the protocol departure, and entry 5 (this closure) | — | **required** |
| **Code — 25 modules under `alpha/`** ||||
| `alpha/download.py`, `universe.py`, `membership.py`, `pitdata.py` | point-in-time universe and price data acquisition | **required** | required |
| `alpha/dataset.py`, `features.py`, `targets.py`, `build_panel.py` | panel construction, features, target definitions | **required** | **required** |
| `alpha/protocol.py`, `walkforward.py`, `stats.py` | scoring protocol, purge/embargo walk-forward, block bootstrap | **required** | **required** |
| `alpha/models.py` | `MODEL_A_PARAMS` — the learner, unchanged since V2.1 | **required** | **required** |
| `alpha/carrier.py` | carriers + the V2.3 `Collinearity` diagnostic | **required** | **required** |
| `alpha/examset.py` | freezes the 72 exam cutoffs; **recomputes and verifies the SHA-256 on load** | **required** | **required** |
| `alpha/exam.py`, `v2_1_exam.py` | V2's 12-date exam; V2.1's sealed 72-date exam and its §5.2 refusal | **required** | **required** |
| `alpha/develop.py`, `ladder.py`, `ladder_v2_2.py`, `ladder_v2_3.py` | the four studies' run scripts | **required** | required |
| `alpha/compare.py`, `adapter.py`, `__init__.py` | comparison utility; the production decision cascade (weight 0 / HOLD) | required | **required** |
| **Tests — 155, all passing** ||||
| `app/tests/test_alpha.py` (29) | V2 invariants | — | **required** |
| `app/tests/test_alpha_v2_1.py` (28) | V2.1 exam-set and leakage invariants | — | **required** |
| `app/tests/test_alpha_v2_1_ladder.py` (17) | V2.1 ladder invariants | — | **required** |
| `app/tests/test_alpha_v2_2.py` (43) | V2.2 invariants; **passing unchanged is the check that `carrier.py` was extended additively** | — | **required** |
| `app/tests/test_alpha_v2_3.py` (38) | V2.3 invariants, incl. exam seal, production 0, and the departure-validity pin | — | **required** |
| `pytest.ini`, `app/tests/conftest.py` | test harness (**already tracked**, unchanged) | **required** | required |

---

## 3. The record — frozen artefacts, with hashes

These are the evidence. The `.json` files are the summaries the reports quote; the
`.pkl` files hold the **per-cutoff series** from which those summaries were computed,
and are what allowed the audit to re-derive every headline number independently
rather than checking summaries against summaries.

| File | Bytes | SHA-256 | Purpose |
|---|---:|---|---|
| `alpha/out/v2_3_development.json` | 131,074 | `f082de280e400080a6cf774dd39bc5c11ce4183eed5d6064ff27e3251d475e5a` | **V2.3 frozen record** — arms, gates, eligibility, λ curves, noise control, bear decomposition |
| `alpha/out/v2_3_development.pkl` | 15,289,837 | `62d1af6163d1c9a01a47d60af5edc48296c74d7487a56fba54c40cacae05119d` | **V2.3 per-cutoff IC series, predictions, collinearity** — the basis of the −0.00120 re-derivation |
| `alpha/out/v2_2_development.json` | 189,964 | `560d77da5c654c881ac9b19120aded72fc0073392522a3e92e2a8b756edaca48` | V2.2 frozen record; still reports V2.2-B at +0.02356 |
| `alpha/out/v2_2_development.pkl` | 34,303,288 | `23ff29a0ccc8b6a69f89ad6c2cf53ab675c25c09537f849d5c93f00bef342c96` | V2.2 per-cutoff series; **read by `ladder_v2_3.py`** for the A-vs-V2.2-B paired contrast |
| `alpha/out/v2_1_development.json` | 81,038 | `398d6f0b0ca299204914f6e7f3194c4c3304e573f4b54267ddb1d86c5383bd30` | V2.1 record + the frozen `exam_configuration` **whose closed gate seals the exam** |
| `alpha/out/v2_1_development.pkl` | 7,616,704 | `3b2be7349fd577058e84990c900fa4622adb522c6234be64366a0470970c6705` | V2.1 per-cutoff series |
| `alpha/out/v2_1_exam_set.json` | 34,688 | `b709a9efc719bdc9bcb4da3e5408092dbe5a94b979a4b1d92e5b56d0970c5f0c` | **the sealed 72 exam cutoffs**; digest `b55e065f…`, recomputed on every load |
| `alpha/out/development.json` | 49,119 | `5dcf087c6952730a20796de184f101c979d14eb83a9515ee4857a8dda7d37f58` | V2 development record |
| `alpha/out/development.pkl` | 12,693,397 | `db5bf977368d4bf4687f0e6535ac2a7b3df7fbe51f2b5bc179768d1c5e50082c` | V2 per-cutoff series |
| `alpha/out/exam_predictions.json` | 1,004,078 | `d00b2f7b4fde70888e369efa92e97647e5cec5c5bd8dc33b5178e7d665259c7f` | V2's **12-date** exam predictions (a finished, opened experiment — not the sealed one) |
| `alpha/out/exam_scores.json` | 8,541 | `49a9ef6343d3321c5a29baf07ac50551beb9872db2f8ce3fc6ca076ef3f4f702` | V2 exam scores — **the file `adapter.py` reads to set production weight 0** |
| `alpha/out/panel_meta.json` | 532 | `4db01007e437f0a6cf62b61ea727bb14f4119ae26b6535ea5db3b394666d7108` | panel fingerprint (249,029 rows, 540 cutoffs, 100 features) — **the check that a rebuilt panel matches** |
| `alpha/out/comparison.json` | 4,389 | — | V2 comparison output |
| `alpha/out/*.log` (3) | small | — | build and development run logs |
| `alpha/out/run1_dead_ret_12_1/development.json` + `.log` + `panel_meta.json` | small | — | the superseded V2 run kept so the effect of the `ret_12_1` fix stays checkable (`V2_REPORT.md` §240) |

**Two exam files that must remain absent** — their absence is itself evidence:
`alpha/out/v2_1_exam_predictions.json` and `alpha/out/v2_1_exam_scores.json`. Verified
absent at closure.

---

## 4. Deliberately excluded, with reasons

Nothing was deleted. Every excluded artefact remains on disk; the hashes below make
it identifiable if it is ever produced later.

| Excluded | Size | Reason | Recovery |
|---|---:|---|---|
| `alpha/out/panel.pkl` | **212 MB** | Derived data, regenerable from committed code. Exceeds practical git limits and GitHub's 100 MB per-file hard limit — committing it would make the repository unusable. SHA-256 `33e019fc95dd5665c961a958d1ddaa9f0162f3f5e730c390770bbe709c3f7e1e`. | `python -m alpha.build_panel`; verify against `panel_meta.json` |
| `alpha/cache/` | **170 MB**, 655 CSVs | Vendor daily price history. Regenerable, third-party data of uncertain redistribution status, and the remote here is a **public repository owned by someone else** (§5). | `python -m alpha.download` |
| `alpha/out/run1_dead_ret_12_1/development.pkl` | 12.7 MB | Per-cutoff series of a **superseded** V2 run. Its `development.json` summary **is** committed, which is what `V2_REPORT.md` relies on to show the fix's effect. SHA-256 `cccd83e37883a63c8c78dd5be29021a88ba6b9cbf04e046f7549be5c51d7f275`. | on disk; not regenerable (superseded code path) |
| `alpha/__pycache__/`, `.pytest_cache/` | — | Build caches. | automatic |
| `.venv/`, `venv/` | — | Virtual environments; already ignored. Note the two are **not** interchangeable — see the reproduction checklist. | `pip install` |
| `app/core/*.py` (new), `app/streamlit_app.py`, `validation/`, `ROADMAP.md`, and other modified app files | — | **In-progress application work, unrelated to the research record.** Out of scope for a closure commit; committing them would mix an unfinished feature branch into the evidence record. | left in the working tree, untouched |
| `app/holdings.json`, `app/transactions.json` | — | **Real positions, cost basis and trade history.** Already gitignored; confirmed still ignored (§5). | never commit |

### 4.1 Consequence for reproducibility, stated plainly

Because `alpha/cache/` and `panel.pkl` are not preserved, **a from-scratch rebuild
depends on vendor data that this commit does not contain.** Daily price history is
revised and delisted symbols disappear, so a rebuild years from now may not be
byte-identical, and `panel_meta.json` is the fingerprint against which any rebuild
must be checked.

**This does not weaken the audit trail.** The committed `.pkl` artefacts contain the
per-cutoff series behind every published number, so the results remain *verifiable*
from this commit alone even if they are not *rebuildable* from raw data. The
distinction is maintained in [`V2_3_REPRODUCTION_CHECKLIST.md`](V2_3_REPRODUCTION_CHECKLIST.md),
which separates checks that need only this commit from checks that need the network.

---

## 5. Questionable material — documented, not silently removed

| # | Finding | Assessment |
|---|---|---|
| 1 | **The `origin` remote is `https://github.com/huseinzol05/Stock-Prediction-Models.git` — a public repository owned by a third party.** This repository is a fork/clone of that open-source project; the alpha programme was developed on top of it. | **Flagged as the highest-consequence finding of this manifest.** A `git push` here would attempt to publish proprietary research onto someone else's public project. This commit is **local only and was not pushed.** Before any push, the remote must be repointed to a repository the author owns, or the research branch kept local permanently. |
| 2 | `app/holdings.json` (1,685 B) and `app/transactions.json` (238 B) — real positions, cost basis, trade history — are present in the working tree. | Confirmed matched by `.gitignore` lines 18–19 via `git check-ignore`. **Not in the candidate set.** No action; the ignore rule protecting `transactions.json` is a pre-existing working-tree change retained in this commit deliberately, because it protects personal financial data. |
| 3 | Secret scan over all candidate `.py`, `.md` and `.json` files: API keys, credentials, tokens, bearer/authorization headers, private-key blocks, `gh*_`/`sk-`/`xox`/`AKIA` patterns. | **No matches.** |
| 4 | Machine-specific path scan (`C:\Users`, `/Users/`, the username, `Desktop`) over candidate source, docs and frozen JSON; plus a binary scan of all four committed `.pkl` files for embedded absolute paths. | **No matches** in source, docs, frozen JSON or any `.pkl`. The artefacts are portable. **But see finding 8 — the scan as originally scoped omitted the `.log` files, and they are not clean.** |
| 5 | `alpha/cache/` contains 655 CSVs of third-party daily price history. | Excluded (§4) — redistribution status is not established and it is regenerable. |
| 6 | `validation/` (point-in-time backtest study: `README.md`, `REPORT.md`, `pit.py`, `model.py`, `metrics.py`, `outcomes.py`, `out/`) is **also entirely untracked.** | **Out of scope for this commit** — it is a distinct study, not part of the V2→V2.3 alpha line. **Flagged as still unpreserved and needing its own decision.** It is not committed here and it is not deleted. |
| 7 | The `reports/` documents at §7 are **copies** of files that live outside the git repository, at `Desktop/AI Stock/`. | Copied in as closure snapshots so they can be versioned at all. The originals were left in place. `PROGRESS_SNAPSHOT_AT_CLOSURE.md` will drift from the live `PROGRESS.md`; it is named to say so. |
| 8 | SHA-256 of all twelve committed frozen artefacts (§3) and both excluded artefacts (§4), recomputed independently at commit time. | **All fourteen match.** |
| 9 | **Three committed run logs embed the author's absolute local path** — `alpha/out/build_panel.log` line 28, `alpha/out/development.log` lines 182–183, `alpha/out/run1_dead_ret_12_1/development.log` lines 182–183, each of the form `froze C:\Users\<user>\Desktop\AI Stock\...\alpha\out\panel.pkl`. This is an OS username and a directory layout, not a credential. **Finding 4's scan missed these because it was scoped to source, docs and JSON; the row above has been corrected to say so.** | **Committed as-is, deliberately, and flagged rather than scrubbed.** These are *run logs* — what the study printed at the moment it executed. Editing one to tidy a path would alter a frozen artefact, which §5 of the closure directive prohibits and which is indistinguishable from tampering with the record. The disclosure cost is a Windows username; the alternative cost is a log that no longer matches its run. **If this repository is ever published, this is the item to weigh** — and the correct remedy is a decision not to publish those three logs, never a quiet rewrite of them. |

---

## 6. The two documentation corrections in this commit

Both are textual. **No experiment data changed.**

**Correction 1 — authority ratio 4.5× → 5.8×.** Applied in `V2_3_LADDER_REPORT.md`
§3, `V2_3_EXPERIMENT_LOG.md` entry 2, and `PROGRESS.md` item 3 (where it had
contradicted that document's own item 1). The authority ratio is 0.3580/0.0619 =
**5.8×**; the resolution ratio is 0.00827/0.00182 = **4.5×**. Only the authority
figure was wrong — the resolution figure is correct and was left alone. Each edit
carries a dated bracketed note preserving the original wording.

**Correction 2 — abandonment criterion 2 is not a satisfied precision condition.**
Pre-registration §9 criterion 2 conditions on a "≈0.004 half-width on 255 cutoffs";
**0.00796 was achieved**. A dated retrospective clarification was added to
`V2_3_LADDER_REPORT.md` §8, `V2_3_POST_MORTEM.md` §4, and `PROGRESS.md`. Criterion
2's operative clause is satisfied (point estimate **negative**, −0.00120), but its
economic argument does not run at 0.00796 and it must not be cited as a formally
satisfied precision condition. **Criterion 6 is met in its exact pre-registered form
and is alone sufficient under §9**; criteria 4-with-5 are independently sufficient.
The decision rests on two independent grounds either way.

**`V2_3_PREREGISTRATION.md` was not edited.** It records what was committed to in
advance and stands as written — that is the whole point of it.

---

## 7. Preserved documents copied in from outside the repository

These were at `Desktop/AI Stock/`, outside the git worktree, and could not be
versioned where they lay.

| Committed as | Original | Role |
|---|---|---|
| `reports/V2_3_POST_MORTEM.md` | `V2.3 Post-Mortem` | Programme retrospective: the V2→V2.3 belief chain, six reasoning errors, §5 what is settled, §6 boundary of the claim |
| `reports/V2_3_FINAL_DECISION_AUDIT.md` | `V2 3 Final Decision Audit` | The independent audit that confirmed closure and found the untracked-record defect this commit fixes |
| `reports/PROGRESS_SNAPSHOT_AT_CLOSURE.md` | `PROGRESS.md` | Running programme record, snapshotted at closure |
| `reports/directives/V2_ALPHA_DIRECTIVE_CORRECTED.md` | `V2_Alpha_Directive_Corrected.md` | The directive that launched V2 |
| `reports/directives/V2_1_ALPHA_RESEARCH_DIRECTIVE.md` | `V2.1 Alpha Research` | The directive that launched V2.1 |
| `reports/directives/V2_1_RESEARCH_LADDER_DIRECTIVE.md` | `v2 1 Research ladder` | The directive that launched the V2.1 ladder |

The directives matter to the audit trail: they are the instructions the
pre-registrations were written *against*, and they show the "do not force a signal,
do not reopen the gate" constraint was imposed from outside at each stage rather
than chosen after seeing results.

`TEST.md` (the point-in-time validation directive) is **not** copied — it belongs to
the `validation/` study flagged at §5.6.

---

## 8. What this commit does and does not establish

**Does:** the record now has a verifiable history. From this commit forward, "the log
is append-only", "no test was edited to pass" and "the artefacts were not altered"
become checkable claims rather than assertions.

**Does not:** it cannot retroactively prove the pre-registrations were written before
the fits. That evidence remains what the audit found — internal consistency, the 155
alpha tests, and a modification-time ordering in which `V2_3_PREREGISTRATION.md`
(17:11) predates `v2_3_development.json` (17:28) and was never touched again.
Mtimes are not an audit trail. **This is the last commit that can be made without
that limitation applying to everything before it.**
