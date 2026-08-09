# Point-in-time historical validation

Answers one question: **if this system had been running on a date in the past,
how good would its predictions have turned out to be?**

Not "how well does it fit history" — the app already measures that, and
`ultimate.py` already refuses to trust a fit. This measures the thing a user
actually gets: a call made on a Tuesday, scored against the Tuesday that
followed, with no knowledge of it at the time.

## How the no-look-ahead guarantee is enforced

Three separate mechanisms, because intent is not a mechanism:

1. **One data door.** `pit.fetcher(cutoff)` is the only way the prediction
   stage reads bars, and it truncates before it trims. The production code
   paths (`ultimate.evaluate`, `forecast.project`, the rule agents) run
   unmodified — they receive a shorter frame and are told nothing else.
2. **Two processes.** `predict.py` writes `out/predictions.json` and never
   reads it. `score.py` reads it and never writes it. Re-running stage 1 over
   an existing file is refused outright. Nothing can be "adjusted" after an
   outcome is seen because the code that sees outcomes cannot reach the code
   that makes predictions.
3. **A test that would fail if it leaked.**
   `app/tests/test_validation.py::test_future_cannot_change_the_verdict`
   builds two price series identical up to the cutoff and violently different
   after it, and asserts both produce the same verdict to the last decimal.
   Any leak anywhere in the engine — a scaler fitted on the full series, a
   calibration window measured from the end — turns that test red.

## Running it

```bash
python -m validation.predict   # ~1 min   30 symbols x 12 cutoffs, frozen to JSON
python -m validation.model     # ~70 min  the LSTM, 8 symbols x 12 cutoffs
python -m validation.score     # ~1 min   reveals outcomes, prints every table
```

`predict` refuses to overwrite an existing `out/predictions.json`; delete it
deliberately to start a new study. `model` appends to `out/model.jsonl` and
skips work already done, so it is safe to interrupt and resume.

## What is measured, and against what

| | |
|---|---|
| Systems | the consensus verdict and each of its three horizons, the three rule agents and their majority, the LSTM projection, and the consensus with the LSTM folded in |
| Windows | 4 hours, 1 day, 1 week, 1 month, 3 months, 6 months — every system scored at all of them, headline at its own |
| Baselines | buy-and-hold, trend continuation, 50-bar MA direction, golden cross, an actual coin flip |
| Intervals | clustered by cutoff date, because thirty symbols on one day are not thirty observations |

`out/calls.csv` holds one row per (cutoff, symbol, system, window) with the
prediction, the outcome and the verdict on it, so any number in the report can
be checked by hand.

## Known limits, stated rather than hidden

* Prices are split- and dividend-adjusted, so an adjustment made after a cutoff
  is baked into the level before it. Splits leave returns untouched; dividend
  adjustment shifts them by the yield.
* The universe is whatever the local cache holds — symbols a live user chose to
  watch *today*. Nothing that delisted is in it.
* Yahoo serves ~730 days of hourly bars, so cutoffs before that have no 4-hour
  horizon at all. The engine reports those as unavailable; nothing is filled in.
* Twelve cutoffs is twelve effectively independent market draws. That is the
  binding constraint on every interval in the report, and no amount of extra
  symbols relaxes it.
