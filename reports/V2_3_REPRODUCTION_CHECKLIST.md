# V2.3 Reproduction Checklist

**Exact commands to independently verify the V2.3 result and the closure state.
Written 2026-08-08 at programme closure. Every command below was executed as
written and its output is recorded.**

Run everything from the repository root:

```bash
cd "Stock-Prediction-Models"
```

---

## Before you start: two things that will trip you up

**1. There are two virtual environments and they are not interchangeable.**

| | `.venv` | `venv` |
|---|---|---|
| python / numpy / pandas / sklearn / scipy | 3.11.9 / 1.26.4 / 2.3.3 / 1.9.0 / 1.17.1 | **identical** |
| pytest | **MISSING** | 9.1.1 |

`venv` is a strict superset and runs everything, **including the tests**. `.venv` is
what the historical run commands in the reports use and what produced the frozen
artefacts; the package versions are identical, so results agree. **Use `venv` unless
you are reproducing a recorded command verbatim.** Running `pytest` under `.venv`
fails with `No module named pytest`, which looks like a broken checkout and is not.

**2. Re-running the ladder overwrites the evidence.**
`alpha/ladder_v2_3.py` writes `alpha/out/v2_3_development.json` and `.pkl`
unconditionally — there is no overwrite guard. Do not run check 6 until checks 1–5
pass and the record is committed. Once committed, `git status` after a re-run is
itself the verification (see check 6).

**Tiers.** Checks 1–5 need **only this commit**. Check 6 additionally needs
`alpha/out/panel.pkl`, which is deliberately not committed. Check 7 needs the
network. See `V2_3_EVIDENCE_MANIFEST.md` §4.1.

---

## Tier 1 — verifiable from this commit alone

### Check 1 — the exam seal recomputes

```bash
./venv/Scripts/python.exe -W ignore -c "from alpha import examset; es = examset.load(); print(es.digest); print(len(es.cutoffs), 'cutoffs', es.cutoffs[0].date(), '..', es.cutoffs[-1].date()); print(len(es.development), 'development')"
```

**Expected**

```
b55e065f4c9f91737b7a56fd715f0913cf8f41207bdb24d91452c10bc1c98ab0
72 cutoffs 2017-12-27 .. 2026-06-22
316 development
```

**Why it matters.** `examset.load()` **recomputes** the SHA-256 from the cutoff list
and raises if it disagrees with the stored value — it does not read the digest and
report it back. So this command proves the 72 frozen cutoffs are the same 72 that
were frozen before any V2.1 fit. If a single date had been added, removed or shifted,
the load fails rather than printing a different number.

### Check 2 — the exam refuses to open

```bash
./venv/Scripts/python.exe -W ignore -m alpha.v2_1_exam predict; echo "exit=$?"
```

**Expected**

```
the §5.2 gate is CLOSED — the exam stays sealed.
  development paired IC difference vs Benchmark 1 (12-1 momentum, +1)
  threshold > 0 and 95% block-bootstrap CI excludes 0
  measured  0.01312 CI [-0.01862, 0.05006] over 255 development cutoffs
A closed gate is the ladder's result. Opening the exam anyway, swapping the gate's
benchmark, or relaxing it to 'mean > 0' are each ruled out in
V2_1_LADDER_PREREGISTRATION.md §5.2.
exit=1
```

**Why it matters.** The seal is **enforced in code, not by discipline**. The refusal
is read out of the frozen `exam_configuration` in `v2_1_development.json`, so the
exam cannot be opened without first editing a frozen artefact — which is now a
visible diff. Note it quotes its own measured value: the gate closed at +0.01312
with an interval spanning zero.

Also confirm the two files that must not exist:

```bash
ls alpha/out/v2_1_exam_predictions.json alpha/out/v2_1_exam_scores.json
```

**Expected:** `No such file or directory` for both. Their **absence is evidence** —
the 72 cutoffs have never been scored.

### Check 3 — production weight is 0 / HOLD

```bash
./venv/Scripts/python.exe -W ignore -c "from alpha import adapter; ev = adapter.load_evidence(); print('weight', ev.weight); print('passed_all', ev.passed_all_criteria); print('criteria', ev.criteria)"
```

**Expected**

```
weight 0.0
passed_all False
criteria {'1_mean_ic': False, '2_ic_hit_rate': False, '3_top_minus_bottom': False, '4_sign_stability': False, '5_beats_simple_factor': False, '6_no_regime_collapse': False, '7_effective_sample': False}
```

**Why it matters.** The weight is **computed by executing the decision cascade**, not
read from a document. It is 0 because all seven production criteria are False in the
frozen exam scores, and the cascade fails closed — any criterion that cannot be
evaluated is a HOLD. Note `adapter.py` reads `exam_scores.json`, which is **V2's
finished 12-date exam**, a different artefact from the sealed 72-cutoff V2.1 exam.

### Check 4 — V2.3-B vs B3 = −0.00120, re-derived from per-cutoff data

This is the headline result. It re-derives the number from the **per-cutoff series**
rather than reading the summary, with an independently written moving-block bootstrap
under a seed different from the ladder's.

```bash
./venv/Scripts/python.exe -W ignore -c "
import pickle, numpy as np, pandas as pd
d = pickle.load(open('alpha/out/v2_3_development.pkl','rb'))
B  = d['ic_series']['V2.3-B'].dropna()
b3 = d['benchmark_ic']['b3_regime_switched']
common = B.index.intersection(b3.dropna().index)
diff = (B.reindex(common) - b3.reindex(common)).dropna().sort_index()
rng = np.random.default_rng(12345); x = diff.values; n = len(x); block = 4
nb = int(np.ceil(n/block)); idx = rng.integers(0, n-block+1, size=(10000, nb))
take = (idx[:,:,None] + np.arange(block)[None,None,:]).reshape(10000,-1)[:,:n]
means = x[take].mean(axis=1); lo, hi = np.percentile(means,[2.5,97.5])
h = (len(diff)+1)//2          # the ladder puts the odd cutoff in the FIRST half: 128/127
print('n cutoffs      ', len(diff))
print('B3 mean IC     ', round(b3.reindex(common).mean(),5))
print('V2.3-B mean IC ', round(B.mean(),5))
print('paired diff    ', round(diff.mean(),5))
print('95%% CI         [%+.5f, %+.5f]' % (lo,hi))
print('breadth        ', round((diff>0).mean(),4))
print('halves         ', round(diff.iloc[:h].mean(),5), '/', round(diff.iloc[h:].mean(),5))
"
```

**Expected**

```
n cutoffs       255
B3 mean IC      0.02836
V2.3-B mean IC  0.02716
paired diff     -0.0012
95% CI         [-0.00922, +0.00642]
breadth         0.451
halves          -0.00034 / -0.00206
```

**Why it matters.** This is the result the whole programme turns on: **a bounded
contextual adjustment subtracts from the hand-coded regime rule.** The point estimate
is negative, the breadth is under 50%, and both chronological halves are negative.
Because the recomputation starts from per-cutoff data with a different bootstrap
implementation and seed, it is not merely checking the summary against itself. CI
endpoints will differ from the report's `[-0.00939, +0.00653]` in the fourth decimal
— that is Monte-Carlo spread between seeds. **The point estimate, breadth and halves
must match exactly.**

### Check 5 — no exam cutoff entered the development record

```bash
./venv/Scripts/python.exe -W ignore -c "
import pickle, pandas as pd
from alpha import examset
exam = {pd.Timestamp(c) for c in examset.load().cutoffs}
d = pickle.load(open('alpha/out/v2_3_development.pkl','rb'))
total = 0
for group in ('ic_series','benchmark_ic'):
    for name, s in d[group].items():
        k = len(exam & {pd.Timestamp(i) for i in s.index}); total += k
        print(f'{name:24s} {len(s):4d} cutoffs, exam overlap {k}')
for name, s in d['predictions'].items():
    idx = {pd.Timestamp(i) for i in pd.Index(s.index.get_level_values(0)).unique()}
    k = len(exam & idx); total += k
    print(f'predictions[{name}]      {len(idx):4d} cutoffs, exam overlap {k}')
print('TOTAL EXAM CONTAMINATION:', total)
"
```

**Expected:** `exam overlap 0` on every line and `TOTAL EXAM CONTAMINATION: 0`
across all ten series.

**Why it matters.** The seal (checks 1–2) proves the exam was not *scored*. This
proves it was not *touched* — no exam date leaked into the development series the
result was computed from, so the four studies were genuinely run on 316 development
cutoffs with the other 72 held out.

### Check 6 — the test suite

```bash
./venv/Scripts/python.exe -W ignore -m pytest -q --runslow
```

**Expected:** `625 passed` — none skipped, none xfailed, exit 0. Takes ~2m 50s.

For the research record alone (the 155 tests in this commit's five alpha modules):

```bash
./venv/Scripts/python.exe -W ignore -m pytest app/tests/test_alpha.py app/tests/test_alpha_v2_1.py app/tests/test_alpha_v2_1_ladder.py app/tests/test_alpha_v2_2.py app/tests/test_alpha_v2_3.py -q --runslow
```

**Expected:** `155 passed` in ~43s.

**Why it matters.** The 625 figure covers the whole application; **155 is the number
that verifies the research**, and it is the number a checkout of this commit
reproduces. Three of those tests are the closure invariants:
`test_the_v2_1_exam_is_untouched`, `test_the_frozen_record_left_production_at_zero`,
and `test_the_v2_2_record_is_untouched` — the last being what makes "`carrier.py` was
extended additively" checkable, since all 43 V2.2 tests pass unchanged against the
extended module.

---

## Tier 2 — needs the local panel (not committed)

### Check 7 — re-run the V2.3 development study

> **Destructive.** This overwrites `alpha/out/v2_3_development.json` and `.pkl`.
> Only run it on a clean, committed working tree.

Requires `alpha/out/panel.pkl` (212 MB, excluded — see manifest §4).

```bash
./.venv/Scripts/python.exe -W ignore -m alpha.ladder_v2_3 --quiet   # ~5 min
git status --short alpha/out/
git diff --stat alpha/out/
```

**Expected:** the run completes on 143,675 rows / 316 cutoffs with 34 refits per arm,
and reports the closed gate. Then **`v2_3_development.json` shows only its
`written_at` timestamp changed**, and `v2_3_development.pkl` is unchanged.

**Why it matters.** The study is deterministic — `random_state=0`, seeded bootstrap,
frozen panel and cutoff list — so a re-run must reproduce the artefacts exactly apart
from the timestamp. **This check only became possible with this commit:** before it,
a re-run overwrote the evidence with nothing to compare against. Now `git diff` is
the comparison. If anything other than `written_at` differs, the environment or the
panel has changed and the discrepancy must be explained before any number in the
reports is trusted.

---

## Tier 3 — needs the network

### Check 8 — rebuild the panel from raw data

```bash
./.venv/Scripts/python.exe -W ignore -m alpha.download      # rebuilds alpha/cache/, 655 symbols
./.venv/Scripts/python.exe -W ignore -m alpha.build_panel   # rebuilds alpha/out/panel.pkl
cat alpha/out/panel_meta.json
```

**Expected fingerprint** — compare against the committed `panel_meta.json`:

```
rows 249029 · features 100 · cutoffs_built 540 · cutoffs_development 484
median_cross_section 465 · first_cutoff 2016-01-04 · last_cutoff 2026-07-28
```

**Why it matters, and its honest limit.** This is the only check that reconstructs the
study from raw data, and it is the **least reliable** one. Vendor daily history is
revised, delisted symbols disappear, and index membership is reconstructed
point-in-time — so a rebuild long after 2026-08-08 may not match, and a mismatch is
not by itself evidence of error. `panel_meta.json` is the fingerprint to compare
against; if it diverges, Tier 1 remains the authoritative verification because it
does not depend on re-acquiring data.

---

## Summary

| # | Check | Needs | Expected |
|---|---|---|---|
| 1 | Exam digest recomputes | this commit | `b55e065f…`, 72 cutoffs |
| 2 | Exam refuses to open | this commit | §5.2 refusal, exit 1; predictions absent |
| 3 | Production weight | this commit | `0.0`, all seven criteria False |
| 4 | **V2.3-B vs B3** | this commit | **−0.00120**, breadth 0.451, halves −0.00034 / −0.00206 |
| 5 | Exam contamination | this commit | 0 across ten series |
| 6 | Tests | this commit | 625 full / **155 research** |
| 7 | Ladder re-run | + `panel.pkl` | only `written_at` differs |
| 8 | Panel rebuild | + network | fingerprint matches `panel_meta.json` |

**Checks 1–6 are the audit trail. They depend on nothing outside this commit.**
