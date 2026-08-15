# V5 Phase 8 — Research & Learning UI

**Verdict: `PHASE 8 COMPLETE. THE RESEARCH RECORD IS VISIBLE IN THE APP`.**

A **Research** tab now exists in the Pro workbench, rendering all six sections
the roadmap requires from stored evidence. It reads frozen records and creates
nothing — including the ledger itself, which still does not exist after a full
app render, and a test holds it that way.

| | |
|---|---|
| Roadmap ACTIVE PHASE | **Phase 8 — Research & Learning UI** |
| Deliverable | Working Streamlit UI + this file |
| New code | `app/core/research_view.py`, the Research tab in `app/streamlit_app.py` |
| New tests | `app/tests/test_research_view.py` (15), 4 UI tests in `app/tests/test_ui.py` |
| STOP/GO gate | *"The user should be able to understand whether the system is improving without reading terminal logs."* **Met** — §5 |
| Production weight changed | **None.** No model promoted, demoted or retired |
| Exam | Sealed. Not accessed |

---

## 1. The constraint that shaped the build

Phase 8's first task is *"build UI from stored evidence, not recomputed
hindsight."* Applied honestly to this repository, that has a sharp consequence:

**Almost every panel is empty, and the empty state is the correct state.**

`app/forecast_ledger.sqlite3` does not exist. No forecast has ever been frozen,
so nothing has ever matured, so nothing has ever been scored. A research UI
built on stored evidence therefore has almost no evidence to show — and the
temptation is to fill the screen by recomputing performance over cached history
instead. That would be recomputed hindsight, which is the one thing the task
forbids, and it would present numbers the record cannot support.

So the tab shows what is there, says plainly why the rest is missing, and
distinguishes three states that look identical if you are careless:

| State | What the tab says |
|---|---|
| No ledger | *"No forecast has ever been frozen … empty by fact rather than by filter"* |
| Ledger, no forecasts | *"The ledger exists but holds no forecast yet"* |
| Forecasts, none matured | *"n forecast(s) frozen, none matured and scored yet. Performance becomes readable at maturity, not at the cutoff"* |

Collapsing those into one "no data" message would misreport progress — a
programme that has frozen 40 forecasts and is waiting for them to mature is in a
completely different position from one that has frozen none, and the difference
is precisely what the owner needs to see.

## 2. The finding: rendering must not create the record

`ForecastLedger.__init__` calls `_initialise()`, which runs `CREATE TABLE IF NOT
EXISTS` — **constructing a ledger creates its file.** A read path that
instantiated one to check whether it held anything would manufacture the very
artefact whose absence Phase 7 §6 and Phase 9 §6 both rest on.

That is not a hypothetical. The obvious implementation of "load the record and
see what's in it" is three lines and it silently spends a guarantee: Phase 7's
thresholds are trustworthy *because* they were set while the ledger was empty,
and Phase 9's recommendation turns on the ledger never having been switched on.
A UI that created an empty ledger on first render would not corrupt any data —
but it would blur a distinction the programme depends on, and it would do it
invisibly.

`research_view.load` therefore checks for the file before constructing anything
and returns an empty state otherwise. Two tests hold the line: one at unit level
against a `tmp_path` that must still be absent afterwards, and one that boots the
whole app and asserts `forecast_ledger.DEFAULT_PATH` still does not exist.

**Opening a tab must not start a research record.**

## 3. The six sections

All under a Pro-only **Research** tab. Production and research surfaces are kept
visually distinct by a consistent marker — 🟢 **Production** for what is live,
🔬 **Research** for what is being measured — because the roadmap asks for the
distinction and because conflating them is how a challenger's number gets read
as a production claim.

| § | Section | Source | State today |
|---|---|---|---|
| 1 | **Production** | `model_registry` | 14 components with identity, source-hash version, horizons and retraining policy. Always populated — it does not need a ledger |
| 2 | **Forecast quality** | `outcome_ledger.summarise` / `calibration` / `rolling_summary` | Empty. Nothing scored |
| 3 | **Model leaderboard** | registry × summary | 45 rows, all `n = 0` |
| 4 | **Forecast history** | `performance_frame` | Empty, with its columns intact |
| 5 | **Prediction explanation** | the **live** verdict | Populated — the one live panel, labelled as such |
| 6 | **Research pipeline** | registry + `promotion` | 45 components: 14 Live, 3 Under evaluation, 19 Experimental, 6 Rejected, 3 Retired |

Four choices in there are worth defending.

**Unscored models stay on the leaderboard.** All 45 rows appear with `n = 0`
rather than being filtered out. A leaderboard that hid them would answer *"who is
winning"* when the true answer is *"nothing has run"* — and the second answer is
the one that matters right now.

**The leaderboard lists only what could be scored.** A component with no
`record_key` cannot appear in a frozen forecast at all, so presenting it as
scoreable would be a category error. A test enforces the exclusion.

**Rejected and retired models stay visible.** Six rejected and three retired
components remain on the pipeline surface with their evidence trail. A rejection
that disappears from the app is a rejection nobody learns from — and this
programme's most valuable output so far is its nulls.

**Weights are shown only from frozen records.** The live engine re-derives its
weights at every evaluation and remembers none of them (Phase 0 severity 3), so
the only honest weights to display are the ones a frozen forecast carries.
Today that panel is empty, and it says why rather than showing today's
re-derivation as though it were history.

### 3.1 The one live panel, and why it is labelled

Section 5 reads the **live** verdict already computed for the Ultimate signal
tab — not recomputed, and not a frozen record either. It is there because it is
exactly what a frozen record would capture, and it carries that caption:

> This is the **live** reading … Unless it is frozen it leaves no trace, and
> nothing on the research surfaces above can ever include it.

That sentence is the whole argument for Phase 9's recommendation, put where the
owner will actually see it.

It also carries the Phase 6 result where it belongs — at the point of use:

> **Regime conditioning: not validated, and not applied.** Phase 6 was audited
> and returned INADMISSIBLE AS WRITTEN … so no weight here is conditioned on one.

The roadmap asks section 5 to show *"regime if validated"*. It is not validated,
and the panel says so rather than omitting the row and leaving the reader to
assume it was never considered.

## 4. Sample-size warnings

The threshold the user sees and the threshold the gate enforces are **the same
number** — `research_view.MIN_CUTOFFS is promotion.MIN_INDEPENDENT_CUTOFFS`, and
a test asserts it, so the two cannot drift into telling different stories.

The count shown is **independent cutoffs, not rows**: symbols read on the same
day are one draw, and forecasts whose windows overlap are collapsed before
counting, reusing the Phase 7 machinery. Tests assert that 200 symbols per day
report the same draw count as 2, and that 30 daily cutoffs at a weekly horizon
report fewer than 30.

Thin records are **shown with the warning, not hidden**. Suppressing them would
be its own distortion; the banner says the numbers cannot support a decision at
that resolution, which is the true statement.

## 5. STOP / GO gate

> The user should be able to understand whether the system is improving without
> reading terminal logs.

**MET.** Today the honest answer to *"is it improving?"* is **"there is no
evidence either way, and here is exactly why"** — and the tab delivers that in
four numbers at the top (forecasts frozen, outcomes scored, independent cutoffs,
promotion floor) before any table loads. It also answers the immediate follow-up,
*"why is nothing being promoted?"*, by rendering the Phase 7 gate as a per-model
checklist with each gate's own arithmetic, rather than leaving that in a
terminal.

The gate does not require the answer to be *yes*. It requires the answer to be
**legible**, and a screen that says "nothing has been measured, here is what it
would take" satisfies it more honestly than a dashboard of numbers computed from
cached history.

## 6. What this phase did not do

- **It did not add a freeze button.** Rendering the record and *starting* it are
  different acts. Switching the ledger on is the action Phase 9 §6 identified
  and Phase 7 §8 explicitly left to the programme owner — it permanently ends
  the guarantee that Phase 7's thresholds were set on an empty ledger. Building
  the button would have made a one-way decision as a side effect of a UI phase.
  It is the single decision now waiting.
- **It did not promote, demote or retire anything.** The tab reads
  `promotion.evaluate_promotion` and displays verdicts; nothing writes a status.
- **It did not compute any performance number.** Every figure is a count of an
  empty set or a registry field. No outcome was read, because there are none.
- **It did not touch a prediction path or a methodology surface.** `alpha/` was
  not modified.

## 7. Phase 8 task status

- [x] **Build UI from stored evidence, not recomputed hindsight** — §1. The one
      live panel is labelled as live, and the temptation to fill empty panels
      with recomputed history was declined explicitly.
- [x] **Add empty-state handling** — §1. Three distinct empty states, because
      collapsing them would misreport progress. This is the *normal* path here,
      not an edge case, and it is what most of the tests exercise.
- [x] **Add sample-size warnings** — §4. Counted in independent cutoffs, sharing
      one constant with the promotion gate.
- [x] **Keep research and production visually distinct** — §3. 🟢 Production
      versus 🔬 Research, applied consistently.

**`PHASE 8 COMPLETE. THE RESEARCH RECORD IS VISIBLE IN THE APP`**
