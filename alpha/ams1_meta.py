"""AMS-1 meta-signals: raw consensus, family consensus, agreement, disagreement.

**Feature-side only. No forward return, target or label is read in this module.**

The study's whole point is the distinction between

```
18 / 22 agents BUY          <- may be one opinion, repeated
4 / 5 independent families BUY   <- may be four
```

so every construction here comes in a raw form and a family form, and the two
are scored against each other rather than blended.

**One family, one vote.** A family's vote is `sign(mean(stances of its
admissible agents))`. `E_EVOLUTIONARY` has three implementations and
`D_POLICY_GRADIENT` has one; after this rule they carry equal weight. A mean of
exactly zero is a genuine abstention and votes 0. There is no tie that resolves
by anything other than arithmetic, and no weight anywhere in this module was
fitted to an outcome.

Availability is handled explicitly and is never silently turned into HOLD: an
agent with no admissible policy at a cutoff is **absent**, which is a different
statement from "flat". A row is only given a consensus state when all
`MIN_FAMILIES` families are present.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import ams1_config as cfg


def family_votes(stances: pd.DataFrame) -> pd.DataFrame:
    """(cutoff, symbol) x family, each in {-1, 0, +1, NaN}.

    NaN means the family had too few admissible agents to speak — recorded, not
    imputed. `MIN_AGENTS_PER_FAMILY` is what "too few" means and it is frozen.
    """
    out = {}
    for family, names in cfg.AGENTS.items():
        present = [n for n in names if n in stances.columns]
        block = stances[present]
        available = block.notna().sum(axis=1)
        mean = block.mean(axis=1, skipna=True)
        vote = np.sign(mean).where(available >= cfg.MIN_AGENTS_PER_FAMILY)
        out[family] = vote
    return pd.DataFrame(out, index=stances.index)


def meta_signals(stances: pd.DataFrame, votes: pd.DataFrame,
                 weights: dict[str, float] | None = None) -> pd.DataFrame:
    """M0–M6, all frozen in `alpha/AGENT_META_PREREGISTRATION.md` §3."""
    agents = [c for c in stances.columns if c in
              {n for names in cfg.AGENTS.values() for n in names}]
    block = stances[agents]
    available = block.notna().sum(axis=1)

    buys = (block > 0).sum(axis=1)
    sells = (block < 0).sum(axis=1)
    families_present = votes.notna().sum(axis=1)
    family_buys = (votes > 0).sum(axis=1)
    family_sells = (votes < 0).sum(axis=1)

    out = pd.DataFrame(index=stances.index)
    # M0 — raw BUY fraction over available agents.
    out["M0_raw_buy_fraction"] = (buys / available).where(available > 0)
    # M1 — raw net vote.
    out["M1_raw_net_vote"] = block.mean(axis=1, skipna=True).where(available > 0)
    # M2 — family BUY fraction; each family capped at one vote.
    out["M2_family_buy_fraction"] = (family_buys / families_present).where(
        families_present >= cfg.MIN_FAMILIES)
    # M3 — family net vote, equal weight per family. The ladder's coordinate.
    out["M3_family_net_vote"] = votes.mean(axis=1, skipna=True).where(
        families_present >= cfg.MIN_FAMILIES)
    # M4 — agreement strength: the consensus margin, |net vote|. 1 is unanimity.
    out["M4_agreement"] = out["M3_family_net_vote"].abs()
    # M5 — diversity-aware agreement. Weights come from the Stage 1 redundancy
    # measurement, which read no outcome; a family that duplicates the others
    # counts for less. With equal weights this collapses to M3 exactly.
    if weights:
        total = sum(weights.get(f, 0.0) for f in votes.columns)
        weighted = sum(votes[f].fillna(0.0) * weights.get(f, 0.0)
                       for f in votes.columns)
        out["M5_diversity_weighted"] = (weighted / total).where(
            families_present >= cfg.MIN_FAMILIES)
    else:
        out["M5_diversity_weighted"] = out["M3_family_net_vote"]
    # M6 — disagreement: the normalised entropy of the family votes. 0 when the
    # families are unanimous, 1 when they are spread evenly over the three
    # states. This is the candidate NO EDGE input.
    out["M6_disagreement"] = _vote_entropy(votes).where(
        families_present >= cfg.MIN_FAMILIES)

    out["families_present"] = families_present
    out["agents_available"] = available
    out["raw_buys"] = buys
    out["raw_sells"] = sells
    out["family_buys"] = family_buys
    out["family_sells"] = family_sells
    return out


def _vote_entropy(votes: pd.DataFrame) -> pd.Series:
    """Normalised Shannon entropy of one row's family votes over {-1, 0, +1}."""
    counts = pd.DataFrame({
        "sell": (votes < 0).sum(axis=1),
        "flat": (votes == 0).sum(axis=1),
        "buy": (votes > 0).sum(axis=1),
    }, index=votes.index).astype(float)
    total = counts.sum(axis=1)
    share = counts.div(total.where(total > 0), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = -share * np.log(share)
    entropy = terms.fillna(0.0).sum(axis=1)
    return (entropy / np.log(3.0)).where(total > 0)


def ladder_state(net_vote: pd.Series) -> pd.Series:
    """The five ordered consensus states. Boundaries are arithmetic, not fitted.

    With three ternary family votes the net vote can only take the seven values
    {-1, -2/3, -1/3, 0, 1/3, 2/3, 1}. Unanimity is |net| == 1; everything
    strictly between 0 and 1 is moderate; exactly 0 is mixed. No boundary here
    was placed by looking at a hit rate, and none may be moved after one is seen.
    """
    state = pd.Series(pd.NA, index=net_vote.index, dtype=object)
    defined = net_vote.notna()
    value = net_vote.where(defined)
    state[defined & (value <= -cfg.STRONG_THRESHOLD)] = "strong bearish"
    state[defined & (value < cfg.MIXED_THRESHOLD)
          & (value > -cfg.STRONG_THRESHOLD)] = "moderate bearish"
    state[defined & (value == cfg.MIXED_THRESHOLD)] = "mixed"
    state[defined & (value > cfg.MIXED_THRESHOLD)
          & (value < cfg.STRONG_THRESHOLD)] = "moderate bullish"
    state[defined & (value >= cfg.STRONG_THRESHOLD)] = "strong bullish"
    return pd.Categorical(state, categories=list(cfg.LADDER), ordered=True)


def raw_ladder_state(raw_net: pd.Series) -> pd.Series:
    """The same five states from the RAW agent vote, for the H2 comparison.

    Deliberately the same shape so the two ladders are read side by side. The
    raw net vote is continuous, so unanimity means every available agent agrees.
    """
    state = pd.Series(pd.NA, index=raw_net.index, dtype=object)
    defined = raw_net.notna()
    value = raw_net.where(defined)
    state[defined & (value <= -1.0)] = "strong bearish"
    state[defined & (value < 0) & (value > -1.0)] = "moderate bearish"
    state[defined & (value == 0)] = "mixed"
    state[defined & (value > 0) & (value < 1.0)] = "moderate bullish"
    state[defined & (value >= 1.0)] = "strong bullish"
    return pd.Categorical(state, categories=list(cfg.LADDER), ordered=True)


def to_unit(net_vote: pd.Series) -> pd.Series:
    """Map a net vote in [-1, 1] onto [0, 1].

    `singlename.fit_linear` centres its single feature at 0.5, because every
    feature the single-name harness was written for is a within-cutoff rank.
    Mapping here rather than changing that function keeps AMS-1 on the same
    tested arm as S2, S3 and S4.
    """
    return (net_vote + 1.0) / 2.0


def diversity_weights(family_matrix: pd.DataFrame) -> dict[str, float]:
    """Per-family weight for M5, from the Stage 1 redundancy measurement only.

    A family that agrees more with the others carries less independent
    information, so its weight is `1 - mean between-family exact agreement`.
    Computed from signals, never from returns, and frozen before scoring.
    """
    weights = {}
    for family in cfg.FAMILIES:
        block = family_matrix[((family_matrix["left"] == family)
                               | (family_matrix["right"] == family))
                              & (family_matrix["left"] != family_matrix["right"])]
        overlap = float(block["exact"].mean()) if len(block) else 0.5
        weights[family] = max(1e-6, 1.0 - overlap)
    total = sum(weights.values())
    return {k: v / total * len(weights) for k, v in weights.items()}
