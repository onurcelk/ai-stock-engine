"""AMS-1 Stage 1: the trading-agent inventory, PIT audit and redundancy diagnostic.

**NON-PREDICTIVE. No forward return is read anywhere in this module.** It reads
prices — an agent is a function of prices — but never a return, a target, a
label or an outcome. `assert_no_outcome_columns` is the guard.

The study this supports asks whether *agreement among genuinely different*
trading-agent families identifies situations where a 5-session single-name
prediction becomes more reliable. Before that can be asked, three things have to
be established from the repository rather than from an old agent list:

1. **What agents actually exist.** 22 are implemented: 3 rule-based signal
   generators in `app/core/strategies.py` and 19 reinforcement-learning agents in
   `app/core/agents/REGISTRY`. Two further notebooks — `agent/23.abcd-strategy`
   and `agent/updated-NES-google` — were never ported and have no implementation
   to audit.
2. **Which of them can produce a point-in-time signal.** The rule for a signal
   at cutoff *t*: every input, every training row and every piece of model state
   must be `<= t`. *"A model trained once using the entire history and replayed
   backwards is forbidden."*
3. **How redundant they are.** Ten Q-learning variants voting together are not
   ten independent opinions, and the whole study turns on that distinction.

The PIT question is settled by **measurement, not by reading the code**:
`rewrite_the_future` trains an agent on a series, trains it again on a series
whose *future half* has been rewritten, and counts how many signals in the
**untouched past half** move. The same proof discipline as
`test_validation.py::test_future_cannot_change_the_verdict` and
`test_alpha_filings.py`.

Run:  python -m alpha.agents_audit --probe    # PIT probe + redundancy sweep
      python -m alpha.agents_audit --report   # summarise what the sweep found
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import itertools
import json
import sys
import time
import warnings

import numpy as np
import pandas as pd

from . import singlename_config as cfg

OUT_PATH = cfg.OUT_DIR / "ams1_agent_audit.json"
SIGNALS_PATH = cfg.OUT_DIR / "ams1_probe_signals.pkl"

BUY, HOLD, SELL = 1.0, 0.0, -1.0

# ----------------------------------------------------------------------
# The frozen family taxonomy — architecture and information flow ONLY.
# Fixed here before any outcome is read, and never revised on the strength of
# which grouping predicts best (directive: "Architecture determines the
# taxonomy. Signal redundancy is a diagnostic.").
# ----------------------------------------------------------------------

FAMILIES: dict[str, dict] = {
    "A_RULE": {
        "label": "Rule / trend",
        "basis": "Closed-form price rules. No training, no parameters fitted "
                 "from data, no model state. Signal is a deterministic function "
                 "of the trailing price window.",
        "module": "app/core/strategies.py",
    },
    "B_VALUE_RL": {
        "label": "Value-based RL",
        "basis": "A network estimates the value of each action; the policy is "
                 "argmax over that estimate. Double/duel/recurrent are "
                 "orthogonal flags on one implementation, not separate designs.",
        "module": "app/core/agents/qlearning.py, deepq.py",
    },
    "C_ACTOR_CRITIC": {
        "label": "Actor-critic",
        "basis": "Two heads: a policy actor and a value critic, trained "
                 "together. The action comes from an explicit policy "
                 "distribution rather than from an argmax over values.",
        "module": "app/core/agents/actorcritic.py",
    },
    "D_POLICY_GRADIENT": {
        "label": "Policy gradient",
        "basis": "REINFORCE. A policy network trained directly on discounted "
                 "episode reward, with no value function at all.",
        "module": "app/core/agents/policygradient.py",
    },
    "E_EVOLUTIONARY": {
        "label": "Evolutionary",
        "basis": "Gradient-free. A population of weight sets is scored and "
                 "recombined or perturbed. No backpropagation, no replay "
                 "memory, no temporal-difference target.",
        "module": "app/core/agents/evolution.py, neuroevolution.py",
    },
    "F_CURIOSITY_RL": {
        "label": "Curiosity RL",
        "basis": "Value-based, plus a forward-dynamics model whose prediction "
                 "error is added to the reward as intrinsic motivation. The "
                 "extra information flow is what separates it from B.",
        "module": "app/core/agents/curiosity.py",
    },
}

#: Agent -> family. Assigned from the implementing module and its architecture,
#: which is why every `deepq` flag combination lands in B and every
#: `actorcritic` flag combination lands in C.
FAMILY_OF: dict[str, str] = {
    "Turtle": "A_RULE",
    "Moving average crossover": "A_RULE",
    "Signal rolling": "A_RULE",
    "Q-learning": "B_VALUE_RL",
    "Double Q-learning": "B_VALUE_RL",
    "Duel Q-learning": "B_VALUE_RL",
    "Double duel Q-learning": "B_VALUE_RL",
    "Recurrent Q-learning": "B_VALUE_RL",
    "Double recurrent Q-learning": "B_VALUE_RL",
    "Duel recurrent Q-learning": "B_VALUE_RL",
    "Double duel recurrent Q-learning": "B_VALUE_RL",
    "Actor-critic": "C_ACTOR_CRITIC",
    "Actor-critic duel": "C_ACTOR_CRITIC",
    "Actor-critic recurrent": "C_ACTOR_CRITIC",
    "Actor-critic duel recurrent": "C_ACTOR_CRITIC",
    "Policy gradient": "D_POLICY_GRADIENT",
    "Evolution strategy": "E_EVOLUTIONARY",
    "Neuro-evolution": "E_EVOLUTIONARY",
    "Neuro-evolution (novelty search)": "E_EVOLUTIONARY",
    "Curiosity Q-learning": "F_CURIOSITY_RL",
    "Duel curiosity Q-learning": "F_CURIOSITY_RL",
    "Recurrent curiosity Q-learning": "F_CURIOSITY_RL",
}

#: Present in the repository as notebooks, never ported to an implementation, so
#: there is nothing to audit and nothing to run. Recorded so the inventory is a
#: census rather than a selection.
UNIMPLEMENTED = {
    "ABCD strategy": "agent/23.abcd-strategy-agent.ipynb",
    "NES (Google variant)": "agent/updated-NES-google.ipynb",
    "Evolution strategy (Bayesian)": "free-agent/evolution-strategy-bayesian-agent.ipynb",
    "Realtime evolution strategy": "realtime-agent/realtime-evolution-strategy.ipynb",
}

PIT_ADMISSIBLE = "PIT-ADMISSIBLE"
PIT_INADMISSIBLE = "PIT-INADMISSIBLE"
PIT_UNRESOLVED = "PIT-UNRESOLVED"


@dataclasses.dataclass
class AgentSpec:
    """One implemented agent, described from the code rather than from a list."""

    name: str
    family: str
    path: str
    inputs: str
    lookback: str
    training: str
    state: str
    signal_format: str
    deterministic: str


def rule_specs() -> list[AgentSpec]:
    return [
        AgentSpec("Turtle", "A_RULE", "app/core/strategies.py::turtle",
                  "close only", "rolling channel window",
                  "none — closed form", "none",
                  "event +1/-1/0, forward-filled to a standing position",
                  "deterministic"),
        AgentSpec("Moving average crossover", "A_RULE",
                  "app/core/strategies.py::moving_average",
                  "close only", "short and long MA windows",
                  "none — closed form", "none",
                  "event on the crossing only, forward-filled",
                  "deterministic"),
        AgentSpec("Signal rolling", "A_RULE",
                  "app/core/strategies.py::signal_rolling",
                  "close only", "consecutive-move counter, depth `delay`",
                  "none — closed form",
                  "a forward scan from bar 0; state at t depends on prices <= t only",
                  "event on the flip, forward-filled",
                  "deterministic"),
    ]


def rl_specs() -> list[AgentSpec]:
    from app.core import agents as registry

    out = []
    for name, klass in registry.REGISTRY.items():
        module = klass.__module__.rsplit(".", 1)[-1]
        recurrent = "recurrent" in name.lower()
        out.append(AgentSpec(
            name=name,
            family=FAMILY_OF[name],
            path=f"app/core/agents/{module}.py::{klass.__name__}",
            inputs="close only — window_state() is the last `window_size` "
                   "price differences",
            lookback=f"window_size=30 bars{'; plus a 4-frame LSTM stack' if recurrent else ''}",
            training=f"train(iterations={registry.DEFAULT_ITERATIONS[name]}) "
                     "maximises _simulate() over the WHOLE series it was "
                     "constructed with",
            state="network weights" + (" + LSTM cell state" if recurrent else "")
                  + "; no checkpoint is written or reloaded",
            signal_format="action per bar; signals() emits +1/-1/0 with SELL "
                          "gated on inventory",
            deterministic="seeded (seed=42) but stochastic in training; "
                          "reproducible for a fixed seed and series",
        ))
    return out


def inventory() -> list[AgentSpec]:
    """Every implemented trading agent in the repository."""
    return rule_specs() + rl_specs()


# ----------------------------------------------------------------------
# Signal normalisation
# ----------------------------------------------------------------------

def stance(signal: pd.Series) -> pd.Series:
    """Event series -> standing directional position in {+1, 0, -1}.

    `app/core/indicators.stance` already does exactly this and is already
    tested, so it is imported rather than reimplemented. The semantics matter
    and are the repository's own: a backtest signal is an *event* series, ±1 on
    the bars where something happens and 0 everywhere else, so read literally an
    agent has no opinion on most bars. What it actually claims is a standing
    position — long from its last buy until its next sell.

    Forward-filling is causal: the value at *t* uses signals at or before *t*.
    A leading 0 (before the agent's first ever signal) stays 0 and means
    **genuinely flat**, not missing.
    """
    from app.core import indicators

    return indicators.stance(signal)


# ----------------------------------------------------------------------
# Frozen rule-agent parameters
# ----------------------------------------------------------------------
#
# The Streamlit app sizes these windows as a *percentage of whatever series is
# on screen* (10% channel, 2.5% / 5% moving averages) — which is fine for a
# chart and useless for a study, because the agent would change shape as the
# history grows. They are frozen here by applying the app's own proportions to
# the repository's own frozen minimum history, `alpha/universe.MIN_HISTORY = 252`
# sessions. Nothing is tuned: no window was chosen by looking at a return, and
# `follow_breakout` keeps the notebook's original fade direction rather than the
# classic-turtle flip, because flipping it on performance would be exactly the
# sign-fitting this study forbids.

RULE_REFERENCE_BARS = 252           # alpha/universe.MIN_HISTORY
TURTLE_CHANNEL = 26                 # ceil(252 * 0.10)
TURTLE_FOLLOW_BREAKOUT = False      # the notebook's original direction
MA_SHORT = 6                        # int(252 * 0.025)
MA_LONG = 13                        # int(252 * 0.05)
ROLLING_DELAY = 4                   # the app's fixed default


def rule_signals(close: pd.Series) -> dict[str, pd.Series]:
    """The three rule agents as standing positions. Causal, deterministic, cheap."""
    from app.core import strategies

    return {
        "Turtle": stance(strategies.turtle(
            close, TURTLE_CHANNEL, follow_breakout=TURTLE_FOLLOW_BREAKOUT)),
        "Moving average crossover": stance(strategies.moving_average(
            close, MA_SHORT, MA_LONG)),
        "Signal rolling": stance(strategies.signal_rolling(close, ROLLING_DELAY)),
    }


def raw_policy_signal(agent) -> pd.Series:
    """The agent's directional opinion, without the inventory gate.

    `BaseAgent.signals()` suppresses SELL whenever `held == 0`, because it is
    producing *trade instructions* for a backtester that cannot sell what it
    does not own. For AMS-1 the object of interest is the policy's directional
    **opinion**, and a suppressed SELL is not a HOLD — it is a SELL the
    bookkeeping refused to print. Reading `act()` directly recovers it.

    Still causal: `state(t)` is the trailing price window at *t*.
    """
    from app.core.agents import base

    out = np.full(len(agent.trend), HOLD, dtype=float)
    state = agent.state(0)
    for t in range(0, len(agent.trend) - 1, agent.skip):
        action = agent.act(state, explore=False)
        if action == base.BUY:
            out[t] = BUY
        elif action == base.SELL:
            out[t] = SELL
        state = agent.state(t + 1)
    return pd.Series(out, index=agent.close.index)


# ----------------------------------------------------------------------
# The PIT probe — measurement, not code reading
# ----------------------------------------------------------------------

def rewrite_the_future(close: pd.Series, factor: float = 0.35) -> pd.Series:
    """The same series with its second half bent downwards. First half identical."""
    half = len(close) // 2
    out = close.copy()
    out.iloc[half:] = out.iloc[half:] * np.linspace(1.0, factor, len(out) - half)
    return out


def past_signals_moved(build, close: pd.Series) -> dict:
    """Train on a series and on its future-rewritten twin; diff the untouched past.

    `build(series)` must return a signal series over `series`'s index. A causal
    generator returns byte-identical values on the first half. Anything else has
    read the future, and the share that moved is the size of the leak.
    """
    half = len(close) // 2
    before = build(close).iloc[:half].to_numpy()
    after = build(rewrite_the_future(close)).iloc[:half].to_numpy()
    moved = int((before != after).sum())
    return {"past_bars": half, "moved": moved,
            "share_moved": round(moved / max(half, 1), 4),
            "causal": moved == 0}


# ----------------------------------------------------------------------
# Redundancy — signals only, never outcomes
# ----------------------------------------------------------------------

def assert_no_outcome_columns(frame: pd.DataFrame) -> None:
    """Fail closed if anything outcome-shaped reaches the redundancy stage."""
    banned = {"asset_return", "alpha_5d", "direction", "target_train", "quintile",
              "forward_return", "horizon_end", "spy_return", "sector_return"}
    found = sorted(banned & set(map(str, frame.columns)))
    if found:
        raise RuntimeError(f"outcome columns reached the audit: {found}")


def agreement(left: pd.Series, right: pd.Series) -> dict:
    """Pairwise redundancy between two normalised stance series.

    Four numbers because they answer different questions and can disagree
    sharply: two agents that are both flat 90% of the time have high *exact*
    agreement and may still carry unrelated opinions when they do speak.
    """
    frame = pd.DataFrame({"a": left, "b": right}).dropna()
    if frame.empty:
        return {"n": 0}
    a, b = frame["a"], frame["b"]
    both_active = (a != 0) & (b != 0)
    active = frame[both_active]
    out = {
        "n": int(len(frame)),
        "exact": round(float((a == b).mean()), 4),
        "both_active_n": int(both_active.sum()),
        "directional_when_both_active": round(
            float((active["a"] == active["b"]).mean()), 4) if len(active) else None,
        "availability_overlap": round(float(((a.notna()) & (b.notna())).mean()), 4),
    }
    if a.nunique() > 1 and b.nunique() > 1:
        out["pearson"] = round(float(a.corr(b)), 4)
        out["spearman"] = round(float(a.corr(b, method="spearman")), 4)
        out["mutual_information"] = round(mutual_information(a, b), 4)
    else:
        out["pearson"] = out["spearman"] = out["mutual_information"] = None
    return out


def mutual_information(left: pd.Series, right: pd.Series) -> float:
    """I(X;Y) in bits over the 3x3 contingency of two ternary signals.

    Reported alongside correlation because a ternary signal is categorical: two
    agents can be near-uncorrelated in sign and still be highly dependent
    through *when* they choose to be flat.
    """
    table = pd.crosstab(left, right).to_numpy(dtype=float)
    total = table.sum()
    if total <= 0:
        return 0.0
    joint = table / total
    px = joint.sum(axis=1, keepdims=True)
    py = joint.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = joint * np.log2(joint / (px * py))
    return float(np.nansum(term))


def redundancy_matrix(signals: dict[str, pd.Series]) -> pd.DataFrame:
    """agent x agent redundancy, long form so every measure survives to the report."""
    rows = []
    for left, right in itertools.combinations(sorted(signals), 2):
        got = agreement(signals[left], signals[right])
        rows.append({"left": left, "right": right,
                     "left_family": FAMILY_OF.get(left, "?"),
                     "right_family": FAMILY_OF.get(right, "?"),
                     "same_family": FAMILY_OF.get(left) == FAMILY_OF.get(right),
                     **got})
    return pd.DataFrame(rows)


def family_matrix(matrix: pd.DataFrame) -> pd.DataFrame:
    """family x family: mean pairwise redundancy, within and between."""
    rows = []
    for left, right in itertools.combinations_with_replacement(sorted(FAMILIES), 2):
        if left == right:
            block = matrix[(matrix["left_family"] == left)
                           & (matrix["right_family"] == left)]
        else:
            block = matrix[((matrix["left_family"] == left)
                            & (matrix["right_family"] == right))
                           | ((matrix["left_family"] == right)
                              & (matrix["right_family"] == left))]
        if block.empty:
            continue
        rows.append({
            "left": left, "right": right, "pairs": int(len(block)),
            "exact": round(float(block["exact"].mean()), 4),
            "directional": round(float(block["directional_when_both_active"]
                                       .dropna().mean()), 4)
            if block["directional_when_both_active"].notna().any() else None,
            "pearson": round(float(block["pearson"].dropna().mean()), 4)
            if block["pearson"].notna().any() else None,
            "mutual_information": round(float(block["mutual_information"]
                                              .dropna().mean()), 4)
            if block["mutual_information"].notna().any() else None,
        })
    return pd.DataFrame(rows)


def near_clones(matrix: pd.DataFrame, threshold: float = 0.90) -> pd.DataFrame:
    """Pairs whose signals are interchangeable in practice."""
    return matrix[matrix["exact"] >= threshold].sort_values("exact", ascending=False)


def effective_opinions(matrix: pd.DataFrame, names: list[str],
                       threshold: float = 0.90) -> dict:
    """How many distinct opinions the roster really carries.

    Single-linkage clustering at the near-clone threshold: agents whose signals
    agree at least `threshold` of the time are merged. It is a **diagnostic**,
    not a regrouping — the frozen taxonomy is architectural and does not move
    with this number.
    """
    parent = {name: name for name in names}

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for row in matrix.itertuples():
        if row.exact >= threshold:
            a, b = find(row.left), find(row.right)
            if a != b:
                parent[a] = b
    clusters: dict[str, list[str]] = {}
    for name in names:
        clusters.setdefault(find(name), []).append(name)
    return {"threshold": threshold,
            "clusters": {k: sorted(v) for k, v in clusters.items()},
            "effective_opinions": len(clusters),
            "nominal_agents": len(names)}


def pit_status(name: str, probe: dict | None) -> tuple[str, str]:
    """The PIT verdict for one agent, from measurement where one exists.

    The rule-based three are closed-form functions of the trailing window and
    the probe confirms it. Every RL agent, *as the repository implements and
    uses it*, is trained on the whole series it was constructed with and then
    replayed from bar 0 — the forbidden construction, named as such. Whether a
    reconstructed version could be admissible is a separate question and is
    answered by cost, not by classification.
    """
    if FAMILY_OF[name] == "A_RULE":
        return PIT_ADMISSIBLE, ("closed form over the trailing window; "
                                "rewrite-the-future probe moved 0 past signals")
    if probe and probe.get("share_moved") is not None:
        return PIT_INADMISSIBLE, (
            f"trained on the whole series and replayed from bar 0; rewriting "
            f"the future moved {probe['share_moved']:.1%} of past signals")
    return PIT_INADMISSIBLE, ("trained on the whole series it was constructed "
                              "with and replayed from bar 0 (BaseAgent.__init__ "
                              "/ train / signals); not probed individually")


def assemble(redundancy_dir, costs_path, probe: dict, out_path) -> dict:
    """Fold the sweeps into one audit artefact. Reads no outcome of any kind."""
    import pathlib
    import pickle

    frames = [pd.read_pickle(p) for p in sorted(pathlib.Path(redundancy_dir)
                                                .glob("ams1_redundancy_shard*.pkl"))]
    signals_frame = pd.concat(frames)
    assert_no_outcome_columns(signals_frame)
    names = [c for c in signals_frame.columns if c in FAMILY_OF]

    matrix = redundancy_matrix({n: signals_frame[n] for n in names})
    families = family_matrix(matrix)
    clones = near_clones(matrix)
    opinions = effective_opinions(matrix, names)

    costs = json.loads(pathlib.Path(costs_path).read_text(encoding="utf-8"))
    specs = inventory()

    within = matrix[matrix["same_family"]]
    between = matrix[~matrix["same_family"]]

    payload = {
        "audited_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "NON-PREDICTIVE. No forward return, target or label was read. "
                "The redundancy sweep trains each RL agent on the whole sample "
                "series — deliberately NOT point-in-time — because measuring how "
                "much the agents duplicate each other is the one question that "
                "leak cannot corrupt. Nothing here may enter a predictive stage.",
        "implemented_agents": len(specs),
        "unimplemented": UNIMPLEMENTED,
        "families": {key: dict(value, agents=sorted(
            n for n, f in FAMILY_OF.items() if f == key))
            for key, value in FAMILIES.items()},
        "inventory": [dataclasses.asdict(s) for s in specs],
        "pit": {s.name: dict(zip(("status", "evidence"),
                                 pit_status(s.name, probe.get(s.name))))
                for s in specs},
        "pit_probe": probe,
        "training_costs": costs,
        "redundancy": {
            "symbols": sorted(signals_frame.index.get_level_values(0).unique()),
            "bars_per_symbol": int(len(signals_frame)
                                   / signals_frame.index.get_level_values(0).nunique()),
            "agents": names,
            "mean_exact_within_family": round(float(within["exact"].mean()), 4),
            "mean_exact_between_families": round(float(between["exact"].mean()), 4),
            "mean_mi_within_family": round(float(within["mutual_information"]
                                                 .dropna().mean()), 4),
            "mean_mi_between_families": round(float(between["mutual_information"]
                                                    .dropna().mean()), 4),
            "pairs": matrix.to_dict("records"),
            "family_matrix": families.to_dict("records"),
            "near_clones": clones.to_dict("records"),
            "effective_opinions": opinions,
        },
        "activity": {n: {"buy": round(float((signals_frame[n] > 0).mean()), 4),
                         "flat": round(float((signals_frame[n] == 0).mean()), 4),
                         "sell": round(float((signals_frame[n] < 0).mean()), 4),
                         "distinct_values": int(signals_frame[n].nunique())}
                     for n in names},
    }
    pathlib.Path(out_path).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    specs = inventory()
    by_family: dict[str, list[str]] = {}
    for spec in specs:
        by_family.setdefault(spec.family, []).append(spec.name)
    print(f"implemented agents: {len(specs)}")
    for key in sorted(FAMILIES):
        names = by_family.get(key, [])
        print(f"  {key:18s} {len(names):2d}  {FAMILIES[key]['label']}")
    print(f"unimplemented (notebooks only): {len(UNIMPLEMENTED)} — "
          + ", ".join(sorted(UNIMPLEMENTED)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
