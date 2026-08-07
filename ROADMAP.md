# Roadmap: Live Data + Making the Results Mean Something

## Status — updated 2026-08-06

| # | Item | State |
|---|---|---|
| 1 | Live data via yfinance + disk cache | ✅ **Done** |
| 2 | Transaction costs, position sizing, interval-aware Sharpe | ✅ **Done** |
| 3 | Directional accuracy, MAE / RMSE | ✅ **Done** |
| 3.3 | Walk-forward validation | ✅ **Done** |
| — | Intraday intervals (1h / 4h) | ✅ **Done** |
| — | Lite / Pro interface modes | ✅ **Done** |
| 5a | Portfolio (multi-symbol baskets) | ✅ **Done** |
| 5c | TradingView-style price chart + app-wide dark theme | ✅ **Done** |
| 4 | Reinforcement-learning agents in the UI | ✅ **Done** — 19 of 19 |
| 5b | Run persistence (History tab) | ✅ **Done** |
| 5d | Deploy split, cache warming | ⬜ Not started |

### The verdict walk-forward delivered

Six folds, 30-bar horizon, LSTM at 60 epochs, on **live AAPL daily bars (2021→2026)**:

| Fold | Test window | Accuracy % | Naive % | Beat naive | Directional % |
|---|---|---|---|---|---|
| 1 | 2025-11-17 → 2025-12-30 | 97.67 | 98.02 | no | 43.3 |
| 2 | 2025-12-31 → 2026-02-12 | 92.03 | 94.58 | no | 46.7 |
| 3 | 2026-02-13 → 2026-03-27 | 94.40 | 96.94 | no | 46.7 |
| 4 | 2026-03-30 → 2026-05-11 | 96.04 | 91.74 | **yes** | 53.3 |
| 5 | 2026-05-12 → 2026-06-24 | 96.69 | 96.36 | **yes** | 56.7 |
| 6 | 2026-06-25 → 2026-08-06 | 94.05 | 91.49 | **yes** | 43.3 |

- Mean accuracy **95.14%** against a naive baseline of **94.86%** — a 0.28 point edge.
- **3 of 6** folds beat the baseline. That is a coin flip.
- Directional accuracy **48.3%**, i.e. *below* chance, ranging 43–57% by fold.
- Mean absolute error **$11.16** on a stock trading near $300.

Note fold 1: the **highest** accuracy of the six (97.67%) and it still lost to the naive
baseline, with 43% directional. A single split landing on that window would have been
reported as the model's headline result. That is precisely the failure mode walk-forward
exists to catch, and it is why this repo's advertised 95%+ accuracies mean nothing.

**What the first three changed, measured on `GOOG-year`:**

- Training samples available: **222 → 11,474** (live AAPL at `max`).
- Turtle agent under fair sizing: **3.62% → 14.75%** on identical signals. The old
  number was mostly a sizing artefact, exactly as suspected.
- LSTM on a 30-day window: **96.62%** by the repo's metric, **53.33%** directional.
  The second number is the real one.
- Canary intact: the turtle agent still returns **3.6198%** at zero cost with fixed
  sizing, matching the original notebook.

---

## Context

The Streamlit app in `app/` now wraps the repo's notebooks in a working UI (overview,
rule-based agents, neural forecast, Monte Carlo). But it runs on the CSVs the original
repo shipped with, and those are **7–10 years stale**:

| Dataset | Range | Rows |
|---|---|---|
| `GOOG-year.csv` (every notebook's default) | 2016-11-02 → 2017-11-01 | 252 |
| `TSLA`, `AMD`, `FB`, `TWTR`, … | 2018 → 2019 | ~252 |
| `BTC-sentiment.csv` | 5 days in Aug 2019 | 339 |
| `oil`, `eur-myr`, `usd-myr` | ~1 month in 2017 | 24–30 |

Two consequences, and the second is the bigger one:

1. **The data is old.** Nothing here has seen COVID, the 2022 drawdown, or anything since.
2. **The data is tiny.** 252 rows means the LSTM trains on ~222 samples. That is far too
   little for a 128-unit recurrent net, and it is the real reason the forecasts collapse
   into noise. Pulling 10 years turns 222 samples into ~2,500 — a 10× increase that costs
   one API call.

So live data isn't only a freshness fix; it's the precondition for the models being worth
evaluating at all. That's Priority 1. Priorities 2–3 then fix the things that currently
make a good result indistinguishable from a bad one: no transaction costs, unfair position
sizing, and a single 30-day holdout scored with a metric that flatters everything.

---

## Priority 1 — Live data via yfinance  ✅ DONE

Shipped as `app/core/live.py`. Both gotchas below were confirmed against the live API:
`multi_level_index` does default to `True`, and an unknown symbol returns an empty frame
rather than raising. The disk cache lives in `app/cache/` (gitignored).

**Decision: `yfinance`, no API key.** The app needs daily bars for one symbol at a time,
a few calls per session. That is the lightest possible data requirement, and yfinance is
the only option with zero signup friction that also covers equities, crypto (`BTC-USD`)
and FX (`EURUSD=X`) through one interface. Its weakness — unofficial endpoint, can
rate-limit — is neutralised by the disk cache below. See the appendix for what we give up.

### 1.1 New module: `app/core/live.py`

```python
PERIODS = ["1y", "2y", "5y", "10y", "max"]      # yfinance-native period strings
INTERVALS = {"Daily": "1d", "Weekly": "1wk"}

def fetch(symbol: str, period: str = "5y", interval: str = "1d",
          force: bool = False) -> pd.DataFrame
def cache_entries() -> list[CacheEntry]     # for a "cached symbols" list in the sidebar
def clear_cache(symbol: str | None = None) -> int
```

Two details that will otherwise cost an hour of debugging:

- **`multi_level_index=False` is mandatory.** As of yfinance 1.5.2 it defaults to `True`,
  so even a *single* ticker comes back with MultiIndex columns and every downstream
  `frame["close"]` breaks. Also pass `progress=False` (it writes a progress bar to stdout)
  and `threads=False` (irrelevant for one symbol, and it muddies error handling).
- **`auto_adjust` now defaults to `True`**, which is what we want — `Close` arrives
  split- and dividend-adjusted, so backtests don't see phantom gaps on split dates. Set it
  explicitly rather than inheriting the default, which has flipped between releases.

### 1.2 Reuse the existing normaliser — don't write a second one

`app/core/data.py` already contains `_normalise()`, which lowercases columns, finds the
date and price columns by name, coerces numerics and sorts. A yfinance frame becomes
compatible with one call:

```python
frame = data.normalise(raw.reset_index())   # DatetimeIndex -> a "Date" column
```

**Action:** rename `_normalise` → `normalise` (drop the underscore) in `app/core/data.py`
since a second module now depends on it. It is referenced in exactly two places today
(`load`, `load_upload`). Everything downstream — `data.describe()`, the backtester, the
forecaster, every chart — then works on live data unchanged, because they all only ever
see the normalised `date`/`close` shape.

### 1.3 Disk cache — the thing that makes rate limits a non-issue

- Location `app/cache/`, added to `.gitignore`.
- One CSV per `(symbol, interval)` holding the **widest range ever fetched**, plus a
  sidecar `_meta.json` recording `fetched_at`. CSV, not Parquet, deliberately: Parquet
  drags in `pyarrow`, and 10 years of daily bars is ~2,500 rows — a 150 KB file.
- On `fetch()`: if the cache covers the requested range and `fetched_at` is from today,
  slice and return without touching the network. Otherwise re-fetch and merge.
- Layer `@st.cache_data(ttl=3600)` on top for in-session memoisation. Disk survives
  restarts; `st.cache_data` avoids re-reading during a single session's slider fiddling.
- `force=True` (wired to a **Refresh** button) bypasses both.

Net effect: a symbol is fetched **once per day**, no matter how much the user clicks.
Yahoo's limits never come into play at this volume.

### 1.4 UI changes in `app/streamlit_app.py`

The sidebar radio becomes three-way:

```python
source = st.sidebar.radio("Data source", ["Live ticker", "Bundled dataset", "Upload CSV"])
```

Make **Live ticker the default** — bundled CSVs demote to an offline fallback. The live
branch needs: a symbol `text_input` (default `AAPL`), a period `selectbox`, an interval
`selectbox`, a **Refresh** button, and a caption showing the fetched range and cache age.

Include a few quick-pick buttons (`AAPL`, `NVDA`, `BTC-USD`, `EURUSD=X`) — they double as
documentation for Yahoo's symbol conventions, which are not guessable.

**Failure handling matters here** because this is the app's first network dependency.
Wrap `fetch()` and distinguish three cases: unknown symbol (yfinance returns an *empty*
frame rather than raising — check `.empty` explicitly), rate-limited/offline (offer the
cached copy if one exists, with its age shown), and everything else. Never let a network
error reach the user as a traceback; the app already has this pattern in the upload branch.

### 1.5 Dependency check

Add `yfinance` to `app/requirements.txt`. It pulls `curl_cffi`, `peewee`, `frozendict`,
`platformdirs`, `multitasking`. **Run `pip check` afterwards** — this venv holds a
deliberately pinned stack (`tensorflow==2.15.1`, `streamlit==1.39.0`, `protobuf==4.25.5`)
that took two attempts to reconcile, and a numpy or protobuf bump from yfinance's tree
would break TensorFlow. If it conflicts, yfinance ships a `requests` fallback that avoids
`curl_cffi` entirely.

---

## Priority 2 — Make the backtest honest  ✅ DONE

Shipped in `app/core/backtest.py`: `fee_pct` / `slippage_pct`, three sizing modes, an
`exposure_pct` metric, and buy & hold now charged the same round trip so the comparison
is like-for-like. Defaults are zero-cost + fixed units, which is why the canary still
reproduces the notebook exactly.

Two flaws in `app/core/backtest.py` currently make every agent result unreadable.

**2.1 There are no transaction costs.** `run()` fills at the close with zero fees and zero
slippage. The moving-average agent turns over 12 trades on 252 days; at a realistic 10 bps
round trip that is a meaningful drag, and for any higher-frequency variant it is decisive.

Add `fee_pct` and `slippage_pct` parameters, applied on both sides of every fill (buy at
`price * (1 + slippage)`, pay `notional * fee`; the reverse on sells). Surface both as
sidebar `number_input`s defaulting to 0.1% and 0.05%. A strategy that only wins at zero
cost has not won.

**2.2 Position sizing makes the benchmark comparison meaningless.** `max_buy=1` means the
agent buys *one share*. On GOOG at ~$1,000 that deploys ~10% of a $10,000 account, while
the buy-and-hold benchmark deploys 100%. The agent is being asked to beat a fully-invested
benchmark using a tenth of the capital — so the current "3.62% vs 33.41%" headline is
partly an artefact of sizing, not skill.

Add a sizing mode to `run()`: `"fixed_units"` (today's behaviour, kept as default so
existing numbers stay reproducible), `"pct_equity"` (deploy N% of current equity per
signal), and `"all_in"` (full position, the true like-for-like against buy & hold). Expose
it in the agent tab. Then the benchmark delta means something.

**2.3 While in here:** `Result.sharpe` annualises with `sqrt(252)` unconditionally. That is
wrong for weekly bars, which Priority 1.4 makes reachable. Pass the periods-per-year in
from the interval.

---

## Priority 3 — Evaluation that can fail  ✅ DONE

All three shipped in `app/core/forecast.py`, with walk-forward as a mode toggle on the
Forecast tab. `walk_forward()` fits the scaler on each fold's training slice only, so it
has no look-ahead; `run()` deliberately keeps the notebooks' full-series scaling because
its job is to reproduce them. See the verdict table above for what it found.

The app already shows the naive baseline next to the forecast, which is why you can see
the LSTM losing to "assume the price never moves." Three additions turn that observation
into a real evaluation.

**3.1 Directional accuracy.** The repo's metric — `1 - RMS relative error` — is dominated
by price *level*, which is why everything scores 90%+. What actually matters is whether
the model got the *sign* of each move right. Add it to `app/core/forecast.py` alongside
the existing `accuracy()`. Expect ~50%; that is the honest headline and it belongs on the
metric row next to the flattering one.

**3.2 MAE and RMSE in price units.** "Off by $12 on average" is interpretable in a way
that "94.7% accurate" is not.

**3.3 Walk-forward validation.** `forecast.run()` does one split: train on everything but
the last 30 days, predict those 30. A single fold on one arbitrary window is not evidence.
Add rolling-origin evaluation: N folds, each training up to time *t* and predicting
*t+1…t+h*, then aggregate. With 10 years of data (Priority 1) there is finally enough
history for ~10 folds. Report the distribution, not just the mean — a model that is
excellent on 3 folds and catastrophic on 7 should look different from a consistent one.

This is the change most likely to show that the models don't work. That is the point.

---

## Priority 4 — Bring the reinforcement-learning agents into the UI  ✅ DONE

`agent/4.policy-gradient` through `agent/22.neuro-evolution-novelty-search` are all ported
to `tf.compat.v1` and runnable, but only the three rule-based agents are in the UI. They
share a common shape — an `Agent`/`Model` class with `get_state`, `act`, and a `train(iterations,
checkpoint)` loop — so they can go behind one interface:

```python
# app/core/agents/base.py
class RLAgent(Protocol):
    def train(self, prices, iterations, on_progress) -> None
    def signals(self, prices) -> pd.Series      # feeds the existing backtest.run()
```

Because they emit signals, they plug straight into the Priority 2 backtester and inherit
fees, sizing, and the buy-and-hold benchmark for free.

**Status: the interface holds.** `app/core/agents/` now contains `base.py` (shared
windowed-state function, signal emission, training report), plus `evolution.py` and
`qlearning.py`. Both are in the agent dropdown with a Train button, a learning curve,
and a fingerprint that invalidates a trained policy when the data or settings change.

Two findings from porting them:

- **The RL objective is not the reported result.** These agents optimise a simplified
  return — one unit per trade, no costs. On `GOOG-year` the evolution strategy's own
  objective reached **+9.10%**, but the same policy through the real backtester with
  commissions and fair sizing gave **+4.40%**: 33 trades cost $651 in fees. The app now
  shows both numbers side by side, because the gap *is* the finding.
- **A latent bug in the original.** `6.evolution-strategy-agent.ipynb`'s `get_reward`
  reads the global `close[t]` where it means `self.trend[t]`; it only works because the
  notebook happens to bind them to the same list. The port uses `self.trend` throughout.

**Status: complete — all 19 reinforcement-learning agents are in the UI.** (`1`-`3` and
`23` are rule-based and already lived in `strategies.py`, so the RL set is `4`-`22`.)

They are **19 agents from 6 implementations**, because the notebooks' naming enumerates
combinations rather than algorithms. `double`, `duel` and `recurrent` are three
independent edits to one DQN skeleton, so `deepq.py` carries all eight of notebooks 5 and
7-13 as flags; the same applies to actor-critic and curiosity:

| Module | Notebooks | Agents | Shape |
|---|---|---|---|
| `evolution.py` | 6 | 1 | numpy, no gradients |
| `neuroevolution.py` | 21, 22 | 2 | numpy GA, `novelty_search` flag |
| `policygradient.py` | 4 | 1 | TF, one update per episode |
| `qlearning.py` | 5 | 1 | TF, notebook 5's own hyperparameters |
| `deepq.py` | 7-13 | 7 | TF, `double` × `duel` × `recurrent` |
| `actorcritic.py` | 14-17 | 4 | TF, `duel` × `recurrent` |
| `curiosity.py` | 18-20 | 3 | TF, intrinsic forward model |

Further findings from this pass:

- **Vectorising the population methods.** A feed-forward agent picks its action from the
  price window alone — cash only gates whether that action is *executable* — so a whole
  episode's forward pass is one matmul, not one per bar. `base.all_states()` does this and
  is asserted identical to the per-bar `window_state()`. Neuro-evolution trains 15
  generations on 1,254 bars in **0.4s**.
- **The exploration schedule is calibrated for runs nobody makes.** Notebooks 7-20 reset
  epsilon to ~1.0 after the first iteration and decay it by `exp(-0.005 i)`. Over the tens
  of iterations the UI encourages, the agent is still essentially random, and the traded
  episode's return is *identical across all seven Q-variants* because they draw the same
  seeded random actions. The learning curve therefore reports the **greedy** policy's
  return instead, which is also what the evolution agents report. Training is untouched.
- **Two more latent bugs.** Notebooks 14-17 gate the bootstrap on `replay[0]`'s done-flag
  for every entry in the batch instead of `replay[i]`'s; notebook 22's `_memorize` pops the
  item it just appended, so its novelty archive goes inert the moment it fills. Both are
  fixed rather than reproduced, and noted in the module docstrings.

Canary intact: the turtle agent still returns **3.6198%** on `GOOG-year`.

---

## Priority 5 — Polish  ◐ PARTIAL

- ~~**Multi-symbol comparison.**~~ ✅ Shipped as the **Portfolio** tab
  (`app/core/portfolio.py`): weighted baskets, optional rebalancing, per-holding stats,
  and a correlation matrix. Holdings are joined on an inner index so the basket is only
  defined where every member actually traded.
- ~~**Price chart.**~~ ✅ Shipped as `app/core/charts.py`: candlesticks with a volume pane,
  last-price badge, symbol watermark, and range buttons, in TradingView's dark palette.
  Weekends are collapsed only for series that don't trade through them (decided from the
  data, so crypto keeps its Saturday bars), and intraday charts also hide the overnight
  session. Close-only bundled CSVs fall back to the line-and-gradient style.
  `apply_dark()` puts every other pane in the same palette via `base_chart()`, and
  `.streamlit/config.toml` matches the page background to the chart canvas — without it
  the chart reads as a dark rectangle pasted onto a light page.
- ~~**Persist runs.**~~ ✅ Shipped as `app/core/runs.py` plus a **History** tab. Forecast,
  walk-forward and agent results are written to `app/runs/` the moment training finishes,
  so a browser refresh no longer discards minutes of work, and runs can be compared across
  sessions. One JSON file each — not a pickle, which is tied to the library versions that
  wrote it and unsafe to load. Agent runs keep the buy/sell indices and equity curve rather
  than the full per-bar signal; the folder prunes to the newest 200. Results stay local:
  `app/runs/` is gitignored.
- **Split requirements for deployment.** TensorFlow makes a ~500 MB image. The overview,
  agent and Monte Carlo tabs need only pandas/plotly. A `requirements-lite.txt` that omits
  TF (hiding the forecast tab) deploys to Streamlit Community Cloud comfortably; the full
  stack needs a container. Note Community Cloud must be pinned to Python 3.11 — TF 2.15
  has no 3.12+ wheels.
- **Cache warming.** An optional script that pre-fetches a watchlist so the app is instant
  on first load and works offline afterwards.

---

## Verification

The suite lives in `app/tests/` and is run with pytest from the repo root:

```
venv\Scripts\python.exe -m pytest              # 114 fast checks, ~1s
venv\Scripts\python.exe -m pytest --runslow    # all 146, ~55s
```

The split matters: the slow marker covers the 19-agent training sweep and the headless UI
drivers, which build TensorFlow graphs and boot Streamlit. Everything else is pure numpy
and pandas and stays under a second, so there is no excuse not to run it.

| File | Guards |
|---|---|
| `test_backtest.py` | **The canary** — turtle on `GOOG-year` at zero cost with fixed sizing returns exactly **3.6198%**, matching the original notebook. Also: fees strictly reduce return, `all_in` approaches buy & hold, the engine never goes short |
| `test_data.py` | All four bundled CSV layouts; column aliasing; currency stripping; tz-aware intraday stamps made naive; `periods_per_year` measured against known frequencies |
| `test_live.py` | Cache round-trip, corruption tolerance, `slice_to_period` trimming, and the error taxonomy — a `RequestError` is never answered from cache, while a plain `FetchError` falls back to it |
| `test_agents.py` | Registry integrity (19 agents, defaults and citations aligned); `all_states()` bit-identical to the per-bar `window_state()`; every agent trains, emits legal signals and clears the backtester |
| `test_charts.py` | Session rangebreaks per asset class — equities collapse weekends, crypto keeps them — plus the dark palette and its agreement with `.streamlit/config.toml` |
| `test_ui.py` | The real app under `AppTest`: both modes, every bundled dataset, and one agent per implementation family trained end to end |
| `test_strategies.py`, `test_montecarlo.py`, `test_portfolio.py` | Signal contracts; seeded reproducibility; inner-join alignment and weight drift |

**Tests are hermetic.** `app/cache/` is gitignored, so nothing may read it — `test_live.py`
redirects `live.CACHE_DIR` into `tmp_path` and builds what it needs. `dataset/` is tracked,
so the bundled CSVs are the only fixture data on disk. No test touches the network.

Still worth adding:

1. **Live fetch against the real network**, as an opt-in marker — the current suite proves
   the cache and error handling, not that Yahoo still answers.
2. **`force=True` bypasses the cache** — currently only the fallback direction is covered.

---

## Appendix — Provider comparison (as of 2026)

| Provider | Key? | Free tier | History | Notes |
|---|---|---|---|---|
| **yfinance** | No | Undocumented, IP-throttled | 10y+ per call | Unofficial endpoint. Stocks + crypto + FX. **Chosen.** |
| Twelve Data | Yes | ~800 calls/day | Good | Best keyed free tier; the natural fallback |
| Finnhub | Yes | ~60 calls/min | Limited on free | Highest throughput, thinnest history |
| Tiingo | Yes | Very restrictive (reports vary, 20–250/day) | Strong EOD | Excellent data, stingy free tier |
| Polygon.io | Yes | EOD only on free | Strong | Generous paid tiers |
| Stooq | No | Unlimited CSV | ~5y via `pandas-datareader` | No real API; useful as a no-key backup |
| IEX Cloud | — | — | — | **Deprecated, do not use** |

Free tiers change often — re-check before depending on any figure here.

If yfinance does start failing, the migration is contained: `live.fetch()` is the only
function that touches the network, and everything downstream consumes the normalised frame
from `data.normalise()`. Swapping providers means rewriting one function.
