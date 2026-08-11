"""AMS-1: point-in-time trading-agent signals on the development panel.

**NON-PREDICTIVE. Reads prices, never a return, a target or a label.**

The audit (`alpha/agents_audit.py`, `reports/AGENT_META_AUDIT.md`) measured that
every one of the 19 reinforcement-learning agents, *as the repository implements
and uses them*, is the construction the study forbids: `BaseAgent.__init__`
takes the whole close series, `train()` maximises `_simulate()` over that whole
series, and `signals()` then replays the fitted policy from bar 0. Rewriting the
future moves 47–71% of the **past** signals.

This module is the repair, and it is a repair by *reconstruction*, not by
permission: an agent's policy at cutoff *t* is trained only on bars at or before
its most recent refit boundary, which is itself at or before *t*.

```
             refit r0            refit r1            refit r2
   |----500 bars----|         |----500 bars----|  |----500 bars----|
   trained on <= r0 ......... trained on <= r1 ... trained on <= r2
                    ^ signals for t in [r0, r1) come from the r0 policy
```

Three families are reconstructed here. The other three are not, and the audit
records why with measured costs rather than assertions:

| family | agents | status |
|---|---:|---|
| `A_RULE` | 3 | closed form; no training to redo |
| `D_POLICY_GRADIENT` | 1 | reconstructed — 8.5 s per fit |
| `E_EVOLUTIONARY` | 3 | reconstructed — 6.7 s per fit |
| `B_VALUE_RL` | 8 | **excluded** — 175 s per fit |
| `C_ACTOR_CRITIC` | 4 | **excluded** — 167 s per fit, and degenerate at the repository's own default iterations |
| `F_CURIOSITY_RL` | 3 | **excluded** — 43 s per fit |

Every frozen constant below was fixed before any outcome was read, and none was
chosen by looking at a return.

Build:  python -m alpha.ams1_signals --shard 0 --of 4
        python -m alpha.ams1_signals --combine
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import time
import warnings

import numpy as np
import pandas as pd

from . import agents_audit as audit
from . import examset, pitdata
from . import singlename_config as cfg

OUT_DIR = cfg.OUT_DIR
SHARD_DIR = OUT_DIR / "ams1_shards"
SIGNALS_PATH = OUT_DIR / "ams1_signals.pkl"
META_PATH = OUT_DIR / "ams1_signals_meta.json"

# ----------------------------------------------------------------------
# Frozen design constants — §2 of alpha/AGENT_META_PREREGISTRATION.md
# ----------------------------------------------------------------------

#: Families reconstructed point-in-time. Frozen by *measured cost*, recorded in
#: the audit before any outcome existed — never by which family predicts best.
PIT_FAMILIES = ("A_RULE", "D_POLICY_GRADIENT", "E_EVOLUTIONARY")

#: A fixed trailing training window, not an expanding one. Fixed length keeps
#: the cost per refit constant and keeps a 2018 policy and a 2026 policy fitted
#: on the same amount of evidence, so a change in their agreement is not just a
#: change in how much data each saw.
TRAIN_BARS = 500

#: Refit boundaries: the first development cutoff on or after 1 January of each
#: year. Annual is the densest schedule the roster's measured cost supports at
#: this breadth; every signal still comes from a policy trained strictly before
#: the session it speaks on.
REFIT_MONTH_DAY = (1, 1)

#: Symbol sample. Eligibility is a *data-availability* filter — a name must
#: appear in enough of the panel to be worth training on — and the sample is
#: then drawn with a frozen seed. Neither step consults a return.
MIN_CUTOFF_COVERAGE = 100
SAMPLE_SIZE = 100
SAMPLE_SEED = 20260811

AGENT_SEED = 42                     # BaseAgent's own default; not tuned


def eligible_symbols(index: pd.MultiIndex) -> list[str]:
    counts = pd.Series(index.get_level_values("symbol")).value_counts()
    return sorted(counts[counts >= MIN_CUTOFF_COVERAGE].index)


def sample_symbols(index: pd.MultiIndex, size: int = SAMPLE_SIZE,
                   seed: int = SAMPLE_SEED) -> list[str]:
    """A frozen, reproducible, outcome-blind sample of the panel's names."""
    pool = eligible_symbols(index)
    rng = np.random.default_rng(seed)
    if len(pool) <= size:
        return pool
    picked = rng.choice(len(pool), size=size, replace=False)
    return sorted(pool[i] for i in picked)


def refit_boundaries(cutoffs: list[pd.Timestamp]) -> list[pd.Timestamp]:
    """One boundary per calendar year: the first development cutoff in it."""
    frame = pd.Series(sorted(cutoffs))
    return sorted(frame.groupby(frame.dt.year).first())


def pit_agent_stance(close: pd.Series, klass, iterations: int,
                     boundaries: list[pd.Timestamp],
                     train_bars: int = TRAIN_BARS) -> pd.Series:
    """One agent's standing position over `close`, refit at each boundary.

    The guarantee, stated as the code enforces it: for a bar *t* in
    `[boundary_i, boundary_{i+1})` the policy was fitted on
    `close[:boundary_i][-train_bars:]`, every element of which is at or before
    `boundary_i <= t`; and the action at *t* is read from `state(t)`, the
    trailing price window. Nothing after *t* is reachable.

    Bars before the first boundary have no admissible policy and are left NaN —
    **unavailable, not HOLD**. Turning them into HOLD would invent an opinion
    the agent could not have had.
    """
    actions = pd.Series(np.nan, index=close.index, dtype=float)
    usable = [b for b in boundaries if (close.index < b).sum() >= train_bars]
    for position, boundary in enumerate(usable):
        history = close[close.index < boundary].iloc[-train_bars:]
        end = usable[position + 1] if position + 1 < len(usable) else None
        span = close.index[(close.index >= boundary)
                           & ((close.index < end) if end is not None else True)]
        if not len(span):
            continue
        agent = klass(history, seed=AGENT_SEED)
        try:
            agent.train(iterations)
            # Replay the frozen policy over the live span. `_forward` re-reads
            # the trailing window at each bar from the full series, so the agent
            # sees real out-of-sample prices — but never fits to them.
            actions.loc[span] = _forward(agent, close, span)
        finally:
            # TF1 graphs are process-global; one refit per year per symbol is
            # nine hundred sessions over this sweep, and leaking them exhausts
            # memory long before the sweep finishes. The agents already expose
            # the teardown — it just has to be called.
            if hasattr(agent, "close_session"):
                agent.close_session()
    return audit.stance(actions.fillna(0.0)).where(actions.notna())


def _forward(agent, close: pd.Series, span: pd.DatetimeIndex) -> np.ndarray:
    """The trained policy's action on each bar of `span`, read causally."""
    from app.core.agents import base

    trend = close.to_numpy(dtype=float)
    positions = close.index.get_indexer(span)
    out = np.zeros(len(span), dtype=float)
    for slot, t in enumerate(positions):
        state = base.window_state(trend, int(t), agent.window_size)
        action = agent.act(state, explore=False)
        out[slot] = audit.BUY if action == base.BUY else (
            audit.SELL if action == base.SELL else audit.HOLD)
    return out


def agents_for(families: tuple[str, ...] = PIT_FAMILIES) -> dict[str, tuple]:
    """(name -> (class, iterations)) for every trainable agent in `families`."""
    from app.core import agents as registry

    return {name: (registry.REGISTRY[name], registry.DEFAULT_ITERATIONS[name])
            for name, family in audit.FAMILY_OF.items()
            if family in families and name in registry.REGISTRY}


def build_symbol(close: pd.Series, cutoffs: pd.DatetimeIndex,
                 boundaries: list[pd.Timestamp]) -> pd.DataFrame:
    """Every admissible agent's stance for one symbol, sampled at the cutoffs."""
    columns: dict[str, pd.Series] = dict(audit.rule_signals(close))
    for name, (klass, iterations) in agents_for().items():
        columns[name] = pit_agent_stance(close, klass, iterations, boundaries)
    frame = pd.DataFrame(columns)
    return frame.reindex(cutoffs, method="ffill")


def main(argv: list[str] | None = None) -> int:
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--of", type=int, default=1)
    parser.add_argument("--combine", action="store_true")
    args = parser.parse_args(argv)

    from . import build_panel

    panel, _, _ = build_panel.load()
    development = examset.development_only(panel)
    index = development.frame.index
    cutoffs = pd.DatetimeIndex(sorted(index.get_level_values(0).unique()))
    symbols = sample_symbols(index)
    boundaries = refit_boundaries(list(cutoffs))

    if args.combine:
        frames = []
        for path in sorted(SHARD_DIR.glob("shard_*.pkl")):
            frames.append(pd.read_pickle(path))
        merged = pd.concat(frames).sort_index()
        merged.to_pickle(SIGNALS_PATH)
        meta = {
            "built_at": dt.datetime.now().isoformat(timespec="seconds"),
            "note": "Point-in-time agent stances. No forward return, target or "
                    "label was read while building this file.",
            "pit_families": list(PIT_FAMILIES),
            "train_bars": TRAIN_BARS,
            "refit_boundaries": [str(b.date()) for b in boundaries],
            "sample_seed": SAMPLE_SEED,
            "sample_size": len(symbols),
            "symbols": symbols,
            "cutoffs": len(cutoffs),
            "agents": sorted(merged.columns),
            "rows": int(len(merged)),
            "availability": {c: round(float(merged[c].notna().mean()), 4)
                             for c in merged.columns},
        }
        META_PATH.write_text(json.dumps(meta, indent=1), encoding="utf-8")
        print(f"combined {len(frames)} shards -> {merged.shape}")
        print(f"wrote {SIGNALS_PATH}\nwrote {META_PATH}")
        return 0

    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    book = pitdata.load_book()
    closes = book._matrices["close"]
    mine = [s for i, s in enumerate(symbols) if i % args.of == args.shard]
    print(f"shard {args.shard}/{args.of}: {len(mine)} symbols, "
          f"{len(boundaries)} refit boundaries, {len(cutoffs)} cutoffs")

    out = {}
    started = time.time()
    for count, symbol in enumerate(mine, 1):
        close = closes[symbol].dropna()
        if len(close) < TRAIN_BARS + 50:
            continue
        out[symbol] = build_symbol(close, cutoffs, boundaries)
        print(f"  {count}/{len(mine)} {symbol} "
              f"({time.time() - started:.0f}s elapsed)", flush=True)

    frame = pd.concat(out, names=["symbol", "cutoff"])
    frame = frame.reorder_levels(["cutoff", "symbol"]).sort_index()
    frame.to_pickle(SHARD_DIR / f"shard_{args.shard}.pkl")
    print(f"wrote shard {args.shard}: {frame.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
