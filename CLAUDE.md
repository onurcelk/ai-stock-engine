# Stock-Prediction-Models — Project Rules

## 1. Research Integrity — The Overriding Constraint

This repository is a research programme, not a feature backlog. Every action
Claude takes must preserve the integrity of the experimental record. The
principles below are not guidelines — violating any one of them invalidates
evidence and is equivalent to data corruption.

### 1.1 Append-only records

Files in `alpha/*_PREREGISTRATION.md`, `alpha/*_EXPERIMENT_LOG.md`, and
`reports/EXPERIMENT_REGISTRY.md` are **append-only**. They may never be edited
to match a later belief. Corrections are appended, dated, and leave the
original wording visible. If Claude is asked to modify a frozen record, it must
refuse and explain why.

### 1.2 No silent methodology changes

Any change to:
- Target construction (`alpha/targets.py`)
- Feature engineering (`alpha/features.py`, `alpha/filings_features.py`)
- Model parameters (`alpha/models.py::MODEL_A_PARAMS`)
- Exam set composition (`alpha/examset.py`)
- Walk-forward logic (`alpha/ladder*.py`)
- Point-in-time truncation (`validation/pit.py`)

...requires a **dated amendment** in the relevant preregistration or a new
preregistration document. Claude must never make these changes silently, even
if the user asks for "a quick fix." State what is being changed, why, and
which protocol section authorises it.

### 1.3 Closed programmes stay closed

The V2→V2.3 architecture is **ABANDONED** (production weight 0, action HOLD).
The V3 family-testing programme is **CLOSED** (all 3 budget slots spent). No
entry may be reopened, re-tested with a larger model, a different learner, a
different target, another horizon, or "one more carrier." If a task appears to
reopen a closed programme, Claude must flag the conflict with §0.1/§21 before
proceeding.

---

## 2. Point-in-Time Discipline

### 2.1 The one data door

`validation/pit.fetcher(cutoff)` is the **only** way the prediction stage reads
bars. All code that produces predictions must receive truncated data and be told
nothing about the future. When writing or modifying prediction-path code:

- Never use `.iloc[-1]` on an untrimmed frame
- Never fit a scaler/normaliser on the full series
- Never measure a calibration window from the series end
- Never condition on information that arrives after the cutoff

### 2.2 Two-process separation

`validation/predict.py` writes predictions and never reads outcomes.
`validation/score.py` reads predictions and never writes them. This separation
is structural, not advisory. Do not introduce code paths that blur it.

### 2.3 The leak detector test

`app/tests/test_validation.py::test_future_cannot_change_the_verdict` is the
critical automated guarantee. If this test passes, the engine cannot see the
future. If it fails, the study is void. **This test must never be weakened,
skipped, or have its assertion relaxed.**

---

## 3. Preregistered Gates

### 3.1 What a gate means

A gate (§2.6 power gate, §2.10 admissibility, §5.2 significance) has teeth
only if failing it has consequences. In this programme:
- A failed admissibility gate means the study does not run
- A failed power gate means the family is not implemented
- A failed significance gate means the arm is REJECTED
- A breach **still spends the budget slot** — that is the point

### 3.2 Claude's role at gates

Claude must never:
- Weaken a gate threshold after seeing a result that would fail it
- Suggest "running it anyway to see" after a gate fails
- Propose a modified version of a rejected arm as if it were new work

Claude should:
- Verify gate computations are committed BEFORE any measurement
- Flag if a proposed experiment lacks a preregistered gate
- Confirm budget slot accounting is correct

---

## 4. Test-Before-Edit Workflow

### 4.1 Before modifying any code

1. **Run the fast test suite first:** `pytest`
2. Confirm the baseline is green before touching anything
3. If tests fail at baseline, diagnose and report — do not edit on a red suite

### 4.2 After modifying code

1. Run the fast suite again
2. If the change touches prediction paths, explicitly verify
   `test_future_cannot_change_the_verdict` passes
3. If the change touches alpha infrastructure, run the relevant
   `test_alpha_v2_*.py` file
4. For UI changes, run with `--runslow` or boot the Streamlit app and verify

### 4.3 Hermetic test discipline

- Tests build what they need in `tmp_path`, never read `app/cache/`
- `dataset/` (bundled CSVs) is tracked and safe to read
- Tests never touch the network
- The `@pytest.mark.slow` marker gates expensive tests behind `--runslow`

---

## 5. Commit Discipline

### 5.1 Commit messages declare research state

Follow the established convention. Commits that affect the research record must
state:
- What phase/step of the protocol they implement
- Whether they are committed BEFORE or AFTER a measurement
- What decision was made (PASS/REJECT/CONTINUE/CLOSED)
- What constraints they carry (e.g., "NOT authorized to run")

Examples from this repo:
```
Phase 5 - Family 1 information-only test: REJECT, slot 1 of 3 spent
Family 3 pre-registration and Section 2.6 power gate. Committed BEFORE any measurement
V4 formulation review: design-only. No measurement, no reopening of V3
```

### 5.2 Temporal ordering matters

Preregistrations must be committed **before** the code that implements their
experiment. Gate computations must be committed **before** the measurement they
gate. This ordering is the mechanism that makes "declared in advance"
verifiable in the git history.

---

## 6. What Claude Must Never Do in This Repository

1. **Fit a model on exam cutoffs.** The 72 exam cutoffs in `examset.load().exam`
   are never read, scored, or inspected outside the sealed exam protocol.
2. **Impute missing data.** NaN means absent. Never fill to median — that is a
   silent bet.
3. **Add arms after seeing results.** The number of arms is declared in advance.
   A diagnostic curve may not be promoted to an arm.
4. **Report a point estimate without its resolution.** A number without a CI or
   half-width is not a result.
5. **Delete or overwrite `out/predictions.json`.** The two-process separation
   means this file, once written, is evidence. Suggest deletion only if the user
   explicitly asks to start a new study.

---

## 7. Model Delegation (extends global policy in C:\Users\onurc\CLAUDE.md)

The global `C:\Users\onurc\CLAUDE.md` defines qwen3-coder:30b, qwen3:30b,
qwen3.5:9b, and Gemini CLI delegation. Within this project, additional rules:

### 7.1 Ollama MCP as the default transport

All Ollama delegations must use the `ollama` MCP server tools by default:

- **`mcp__ollama__run`** for single-prompt tasks (equivalent to `ollama run`).
  Parameters: `name` (model name), `prompt`, and optional `temperature`, `think`.
- **`mcp__ollama__chat_completion`** for multi-turn or system-prompt tasks.
  Parameters: `model`, `messages` (array of `{role, content}`), and optional
  `temperature`, `think`.

Direct `ollama run <model>` shell calls via Bash are **fallback-only** — use them
only when the MCP server is confirmed unavailable (tool call returns a connection
error or the server is not listed). When falling back, note in the response that
MCP was unavailable and the shell fallback was used.

### 7.2 Gemini CLI (unchanged)

**Gemini CLI as independent reviewer** is appropriate for: reviewing a
preregistration for logical gaps, checking whether a proposed experiment
reopens a closed question, validating statistical reasoning in gate
computations. Invoked via `gemini -p "..."` as defined in the global policy.

### 7.3 Project-specific delegation scope

- **Never delegate research methodology decisions** to any local model. Protocol
  design, gate evaluation, and "should we run this experiment" are Claude-only.
- **qwen3-coder:30b** may handle: reviewing diffs to alpha code for point-in-time
  violations, generating boilerplate test cases, drafting experiment log entries
  from structured results.
- **qwen3:30b** may handle: summarising experiment results into narrative form,
  comparing CI endpoints across arms, interpreting diagnostic tables.
- **No model** (including Claude) may generate or interpret IC numbers without
  the actual computation having been run. Narrative must follow measurement, not
  precede it.

---

## 8. Key Paths

| Path | Role | Mutable? |
|------|------|----------|
| `alpha/*_PREREGISTRATION.md` | Frozen experiment protocols | Append-only |
| `alpha/*_EXPERIMENT_LOG.md` | Append-only run records | Append-only |
| `reports/EXPERIMENT_REGISTRY.md` | Permanent index of all arms | Append-only |
| `alpha/examset.py` | 72 frozen exam cutoffs | Never modify |
| `alpha/models.py::MODEL_A_PARAMS` | Frozen model hyperparameters | Never modify without amendment |
| `validation/pit.py` | Point-in-time data door | Modify only with protocol amendment |
| `app/tests/test_validation.py` | Leak detector | Never weaken |
| `app/tests/conftest.py` | Hermetic test fixtures | May extend, never relax |
| `pytest.ini` | Test configuration | May extend markers |

---

## 9. Running the Project

```bash
# Fast test suite (default — excludes @slow-marked tests)
pytest

# Full suite including agent training and UI tests
pytest --runslow

# Point-in-time validation study
python -m validation.predict   # writes predictions, refuses to overwrite
python -m validation.score     # reveals outcomes

# Streamlit app
streamlit run app/streamlit_app.py
```
