# Phase B — `neural.*` reproducibility: fixed and measured

**Date:** 2026-08-23
**Class:** engineering correction. No information family is opened, no gate is
evaluated, no closed study is reopened, no budget slot is spent. This repairs a
defect HT-1 recorded and explicitly declined to fix; it does not re-test any
verdict.

---

## 1. What HT-1 recorded

`reports/HT1_TOURNAMENT_RESULT.md` §6, from 180 calls per candidate, each run
twice through the full pipeline in fresh interpreters:

| Candidate | Compared | Sign flips | Flip rate | Median drift | Max drift | Reproducible |
|---|---:|---:|---:|---:|---:|---|
| `neural.lstm` | 180 | 13 | **7.2%** | 0.44 pp | **1,898.7 pp** | **No** |
| `neural.gru` | 180 | 0 | 0.0% | 0.00 | 0.00 | Yes |
| `neural.vanilla_rnn` | 180 | 0 | 0.0% | 0.00 | 0.00 | Yes |

A second probe of the same size returned 17 flips rather than 13 — the
instability estimate was itself unstable. HT-1 scoped the repair out and did not
license it, and recorded the consequence plainly: *"the app presents its
projection to a user as a single number with no interval."*

Authorised by the account holder on 2026-08-23, ahead of the frontend rebuild's
Forecast page, on the grounds that porting the tab first would ship a known
non-deterministic number in a better-looking wrapper.

**No record splits.** `model_registry` derives `neural.*`'s declared version
from `app.core.forecast`'s hash, so editing it changes that version — but all
three neural challengers hold **n = 0 frozen forecasts**, and no entry with
PRODUCTION status uses `app.core.forecast` (`ensemble.ultimate` is
`app.core.ultimate`, `technical.*` is `app.core.indicators`, `rule_agent.*` is
`app.core.strategies`). `app/core/ultimate.py` contains no reference to
`forecast` at all, so the live signal path is untouched. The only other entry
versioned on this module is RETIRED.

## 2. What was actually wrong

Three distinct causes, and the third is the one that mattered most.

**2.1 Dropout was active at inference.** `_build_graph` wrapped the cells in
`DropoutWrapper(output_keep_prob=forget_bias)` where the argument received was
the `dropout` value (0.8). Being a graph constant rather than a fed value, it
stayed on through `_predict`, so every inference call randomly discarded a fifth
of its outputs. The parameter was also misnamed: `forget_bias` in the signature,
a keep probability in fact.

**2.2 Nothing was seeded.** `_train_once` reset the graph and built it with no
graph-level seed, so weight initialisation varied per run.

**2.3 Keras state survived between graphs.** This is the load-bearing one, and
the credit belongs to `tournament._seeded_tensorflow`, which measured it while
building a workaround that could not touch this file:

> `reset_default_graph` plus a seed is not enough on its own: measured over
> four identical sequential LSTM projections it returns two *alternating*
> values (−1.6434, −1.6323, −1.6323, −1.6434), because Keras state surviving
> between graphs shifts the op ordering the op-level seeds are derived from.

That makes a projection depend on how many projections ran before it in the same
process — which is worse than noise, because it is invisible in any single run.

## 3. What changed

`app/core/forecast.py`:

- `_build_graph` no longer takes the dropout argument at all. The wrapper reads
  `graph["keep_prob"]`, a `placeholder_with_default(1.0)`, so **inference is the
  default and training is the exception**. A caller that forgets to feed it gets
  no dropout rather than silent dropout, and the old mistake is now
  unexpressible rather than merely corrected.
- `_train_once` gained `seed: int | None = DEFAULT_SEED` (1337). When seeded it
  clears the Keras session, resets the graph again, and sets the graph-level
  seed. `seed=None` restores the previous behaviour deliberately rather than by
  omission.
- `run`, `walk_forward` and `project` expose the same `seed` parameter with the
  same default, so a re-run is reproducible without the caller doing anything.
- New `DivergedRollout` and `DIVERGENCE_LIMIT = 10.0`. The autoregressive loop
  feeds its own output back in, so a step that leaves the min-max-scaled [0, 1]
  band compounds rather than corrects. `_predict` now checks each step for
  non-finiteness and for leaving ±10 in scaled space, and **raises at the step
  that did it** rather than letting `inverse_transform` turn it into a
  plausible-looking price. This is the 1,899 pp failure, caught.

`app/core/tournament.py`: `_neural_in_process` now passes `seed=SEED` (42)
explicitly. `_seeded_tensorflow` is left exactly as it is — HT-1's instrument
keeps its own wrapper — and the explicit seed pins it to this study's own
constant rather than to whatever the application default later becomes.

## 4. The measurement

`alpha/phaseb_stability_probe.py`. Two arms, so the fix cannot be credited with
stability the harness had all along: `fixed` (the new defaults) against
`unseeded` (`seed=None`). 3 trials × 2 runs per model, 12 epochs, 260 bars, one
deterministic synthetic series so the probe measures the model and not the data.

| Arm | Model | Bit-identical | Sign flips | Median drift | Max drift |
|---|---|---:|---:|---:|---:|
| **fixed** | LSTM | **3/3** | 0 | 0.000 pp | 0.000 pp |
| **fixed** | GRU | **3/3** | 0 | 0.000 pp | 0.000 pp |
| **fixed** | Vanilla RNN | **3/3** | 0 | 0.000 pp | 0.000 pp |
| unseeded | LSTM | 0/3 | 0 | 1.720 pp | 2.091 pp |
| unseeded | GRU | 0/3 | 0 | 3.325 pp | 5.368 pp |
| unseeded | Vanilla RNN | 0/3 | 2 (66.7%) | 7.215 pp | 7.507 pp |

**Two intermediate results are recorded because they are informative, not
because they flatter the fix.**

- Seed and inference-dropout alone gave LSTM **2/3**, max drift 0.039 pp. Better
  by two orders of magnitude, but not reproducible.
- Adding TensorFlow thread pinning — on the reasoning that float addition is not
  associative and parallel reductions do not fix their summation order — gave
  LSTM **0/3**. It did not help, so **it was removed rather than kept as
  plausible-sounding insurance.**
- `clear_session()` is what took every model to 3/3, exactly as
  `_seeded_tensorflow` predicted it would.

## 5. What this does and does not say

**Does:** an identical call to `run`, `walk_forward` or `project` now returns an
identical result, and a diverging rollout raises instead of returning a number.

**Does not:** re-estimate HT-1's 7.2% flip rate. Three trials cannot resolve a
rate that fires one time in fourteen; this probe asks whether the rate is now
*zero on the pairs compared*, and the arms are not comparable to HT-1's own
(HT-1's probe was itself seeded and thread-pinned, so its baseline is not this
one's `unseeded` arm).

**Does not** change any verdict. HT-1's `neural.*` rows were REJECT at all three
horizons by a margin far larger than this noise, and §6 already said so. Nothing
here makes a rejected candidate re-testable — `CLAUDE.md` §1.3 still bars that.

**Does not** make `neural.*` promotable. All three remain CHALLENGER with n = 0
frozen forecasts; what changed is that a number they produce is now the same
number twice.

## 6. What remains

- The probe is small by design. A full-scale re-run of HT-1's 180-call
  methodology would tighten the claim, and is not required to accept that a
  bit-identical pair is bit-identical.
- `DIVERGENCE_LIMIT = 10.0` has not been calibrated against a real divergence,
  because none occurred in this probe (`diverged_caught` was 0 in every cell).
  It is a bound derived from the scaling, not from observed failures, and it
  will first prove itself the day it fires.

## 7. Tests

`app/tests/test_forecast.py` gained six. The rollout guard is exercised through
a stub session rather than TensorFlow, so it runs in milliseconds and stays in
the default suite instead of behind `--runslow`:

- a diverging step raises, and the message names the step
- a non-finite step raises
- an ordinary rollout is untouched by the guard
- the default is reproducible, and `None` is the explicit opt-out
- `_build_graph` no longer accepts the dropout argument, and the wrapper reads
  the placeholder — the old mistake is unexpressible
