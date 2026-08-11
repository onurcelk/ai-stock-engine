"""Family 10 Stage 3: independent information units, the block freeze, the power gate.

**NON-PREDICTIVE.** No forward return is read here. The only distributional
inputs are the **marginal properties of the target** already measured and
committed in `alpha/source_probe.py` — the standard deviation of the 5-session
return, its within-date correlation, and the block-bootstrap inflation
calibrated against Phase 1's measured half-width. That is precisely what a §2.6
power gate is computed from in this programme, and no candidate feature, no
conditioning and no outcome of this family enters it.

The module runs in **two modes, in a fixed order**, and the git history is the
evidence that the order held:

```
python -m alpha.family10_power --freeze   # structure + block length. NO half-width.
python -m alpha.family10_power --gate     # the half-widths and the verdict.
```

`--freeze` refuses to compute a half-width, so the block length cannot have been
chosen to make the gate pass. This is the same two-part discipline
`reports/V4_SUE_POWER_GATE.md` used, for the same reason.

---

## The block length, and why it is 24 sessions

Family 10 samples in **event time**, not on the 5-session cutoff grid, so the
dependence structure is not the one V3 and V4 faced and the block cannot be
inherited unchanged.

**1. Mechanical overlap.** Two events on sessions `s1 < s2` share forward
sessions whenever `s2 - s1 < HORIZON`. At `HORIZON = 5` the highest lag carrying
mechanical overlap is therefore **q = 4 sessions** — where V3's grid study had
`q = 0`, because its cutoffs were spaced exactly one horizon apart.

**2. The record's own persistence allowance.** `alpha/stats.py` sets
`BLOCK_LENGTH = 4` cutoffs and names the span: *"block length 4 cutoffs (~one
month)"*. At `H = 5` on that grid the mechanical overlap was zero, so the whole
**20 sessions** was an allowance for *"the market's own persistence"*. The
market is the same market and the horizon is the same horizon, so the same
allowance applies here — added on top of an overlap that did not exist there.

```
L  =  q  +  the record's persistence allowance  =  4  +  20  =  24 sessions
```

**3. The independent rule, which lands in the same place.** The moving-block
rule of thumb is `L ~ n^(1/3)` in the units of the resampling *observation*. In
V4-SUE the observations were cutoffs: `313^(1/3) = 6.79 -> 7` cutoffs. Here they
are **event sessions**, of which there are 1,221: `1221^(1/3) = 10.69` event
sessions, and an event session is worth `2664 / 1221 = 2.18` calendar sessions,
so `10.69 x 2.18 = 23.3 -> 24` calendar sessions.

Two derivations, one from the overlap structure plus the record's own standard
and one from the `n^(1/3)` rule, both give **24**. `alpha/V4_CHARTER.md` §6.1's
tie-break — where more than one length is defensible and the evidence does not
clearly favour the shorter, take the longer — is not even needed.

> **SELECTED BLOCK LENGTH: L = 24 sessions. D = 2,664 // 24 = 111 blocks.**

The source survey's §1.1 pre-declared 532 five-session blocks and 266
ten-session ones, with *"the conservative column governs the verdict"*. **111 is
more conservative than both**, and it is arrived at from the dependence
structure rather than from either of those figures. Both survey columns are
reported alongside so the cost of the choice is visible, but **only L = 24
decides.**
"""

from __future__ import annotations

import datetime as dt
import json
import pickle
import sys

import numpy as np
import pandas as pd

from . import examset, family10_panel, pitdata, source_probe
from . import singlename_config as cfg

EVENTS = cfg.OUT_DIR / "family10_events.parquet"
PANEL_PKL = cfg.OUT_DIR / "panel.pkl"
FREEZE_PATH = cfg.OUT_DIR / "family10_block_freeze.json"
GATE_PATH = cfg.OUT_DIR / "family10_power_gate.json"

HORIZON = family10_panel.HORIZON            # 5 sessions, inherited
EMBARGO = cfg.EMBARGO                       # 5 sessions, inherited

#: FROZEN. See the module docstring for the two derivations. Committed before
#: any half-width was computed; changing it after a gate result is a protocol
#: breach, not a refactor (CLAUDE.md §1.2).
BLOCK_LENGTH = 24

#: Reported for comparison only. Neither decides anything.
SURVEY_BLOCKS_5D = source_probe.BLOCKS_5D   # 532
SURVEY_BLOCKS_10D = source_probe.BLOCKS_10D  # 266

#: The base rate the directional claim is measured against. Marginal property of
#: the target, from `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md` §1.2 — no
#: conditioning, no feature, no candidate.
BASE_UP_RATE = 0.537
SUB_50 = 0.50

#: The economic claim's hurdle, fixed in `reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md`
#: §1.2 claim (c) and committed at `4a966a2` **before this pilot began**: an
#: effect is economically useful only above ~39 bp per 5 sessions, Phase 1's
#: covered-book resolution. §3.3 of the same survey judged this family by
#: whether its half-width sat inside that number, and passed it on 27.7–35.6 bp.
#: A gate has teeth only if failing it has consequences (CLAUDE.md §3.1), so the
#: number is read here exactly as it was written there.
ECONOMIC_HURDLE_BP = 39.0


def development_safe(events: pd.DataFrame, calendar: pd.DatetimeIndex,
                     exam: list[pd.Timestamp],
                     separation: int = examset.MIN_SEPARATION) -> pd.Series:
    """Events at least `separation` sessions from every sealed exam cutoff.

    `examset.development` keeps a grid cutoff only when it is `MIN_SEPARATION =
    HORIZON + EMBARGO = 10` sessions from every exam cutoff. This is that rule
    with the event's information session in place of the cutoff — not a new
    convention, the existing one applied to a new sampling scheme, so a
    development study on this family cannot warm itself on a window abutting the
    sealed paper.
    """
    session_pos = calendar.searchsorted(pd.DatetimeIndex(events["session"]),
                                        side="left")
    exam_pos = np.sort(calendar.searchsorted(pd.DatetimeIndex(sorted(exam)),
                                             side="left"))
    nearest = np.searchsorted(exam_pos, session_pos)
    distance = np.full(len(session_pos), np.inf)
    for offset in (-1, 0):
        probe = np.clip(nearest + offset, 0, len(exam_pos) - 1)
        distance = np.minimum(distance, np.abs(session_pos - exam_pos[probe]))
    return pd.Series(distance >= separation, index=events.index)


def on_panel(events: pd.DataFrame, grid: list[pd.Timestamp],
             calendar: pd.DatetimeIndex, index: pd.MultiIndex,
             horizon: int = HORIZON) -> pd.Series:
    """Whether the research panel carries the name on the cutoff owning that session.

    Membership is not enough: `alpha/universe.py` also demands bars, 252 sessions
    of history, $3M median dollar volume and a $3 price. An event on a name the
    panel cannot carry has no computable forward return on this cache, so it
    cannot be part of the usable sample however well it is identified.

    Evaluated against the **whole** 532-cutoff grid, not the development subset,
    so that priceability and the exam split stay separate questions.
    """
    grid_index = pd.DatetimeIndex(sorted(grid))
    grid_pos = calendar.searchsorted(grid_index, side="left")
    session_pos = calendar.searchsorted(pd.DatetimeIndex(events["session"]),
                                        side="left")
    slot = np.searchsorted(grid_pos, session_pos, side="left")
    inside = slot < len(grid_index)
    distance = np.where(inside, grid_pos[np.clip(slot, 0, len(grid_index) - 1)]
                        - session_pos, horizon + 1)
    keep = inside & (distance < horizon)

    cells = set(index)
    out = []
    for row, ok, position in zip(events.itertuples(), keep, slot):
        cutoff = grid_index[position] if ok else None
        out.append(bool(ok) and any((cutoff, ticker) in cells
                                    for ticker in str(row.tickers).split("|")
                                    if ticker))
    return pd.Series(out, index=events.index)


def block_structure(events: pd.DataFrame, calendar: pd.DatetimeIndex,
                    block: int = BLOCK_LENGTH) -> dict:
    """Independent information units. **No half-width is computed here.**

    2,000 events on a small number of dates are not 2,000 draws, and this is
    where that is quantified rather than assumed.
    """
    if events.empty:
        return {"events": 0}
    session_pos = pd.Series(calendar.searchsorted(
        pd.DatetimeIndex(events["session"]), side="left"), index=events.index)
    block_id = session_pos // block
    total_blocks = int(len(calendar) // block)

    per_block = events.assign(_b=block_id).groupby("_b")
    sizes = per_block.size()
    issuers = per_block["cik"].nunique()
    per_date = events.groupby("session").size()
    per_issuer = events.groupby("cik").size()

    gaps = (events.assign(_p=session_pos).sort_values(["cik", "_p"])
            .groupby("cik")["_p"].diff().dropna())

    return {
        "block_length_sessions": int(block),
        "calendar_sessions": int(len(calendar)),
        "total_blocks": total_blocks,
        "occupied_blocks": int(block_id.nunique()),
        "events": int(len(events)),
        "unique_event_sessions": int(events["session"].nunique()),
        "unique_issuers": int(events["cik"].nunique()),
        "events_per_block_over_all_blocks": round(len(events) / total_blocks, 3),
        "events_per_occupied_block_mean": round(float(sizes.mean()), 3),
        "events_per_occupied_block_median": float(sizes.median()),
        "events_per_occupied_block_max": int(sizes.max()),
        "issuers_per_occupied_block_mean": round(float(issuers.mean()), 3),
        "issuers_per_occupied_block_max": int(issuers.max()),
        "largest_block_share": round(float(sizes.max() / len(events)), 4),
        "events_per_date_mean": round(float(per_date.mean()), 3),
        "events_per_date_max": int(per_date.max()),
        "dates_with_one_event_share": round(float((per_date == 1).mean()), 4),
        "events_per_issuer_mean": round(float(per_issuer.mean()), 3),
        "events_per_issuer_max": int(per_issuer.max()),
        "top_issuer_share": round(float(per_issuer.max() / len(events)), 4),
        "top10_issuer_share": round(float(per_issuer.nlargest(10).sum()
                                          / len(events)), 4),
        "same_issuer_gap_median_sessions": float(gaps.median()) if len(gaps) else None,
        "same_issuer_pairs": int(len(gaps)),
        "same_issuer_pairs_under_horizon": int((gaps < HORIZON).sum()),
        "same_issuer_pairs_under_block": int((gaps < block).sum()),
        "same_issuer_pairs_under_block_share": round(
            float((gaps < block).mean()), 4) if len(gaps) else None,
    }


# ----------------------------------------------------------------------
# The gate. Only reachable from --gate, and only after the freeze exists.
# ----------------------------------------------------------------------

def resolution(events: int, blocks: int) -> dict:
    """Half-widths on the two quantities a directional family has to move.

    `source_probe.resolution_for_events` derives the per-block count from the
    event total so that `k * D = n` by construction — the accounting error the
    survey caught in itself and fixed there rather than here.
    """
    return source_probe.resolution_for_events(events, blocks)


def gate(events: int, blocks: int) -> dict:
    """Minimum detectable effects, and what the sub-50% claim additionally needs."""
    got = resolution(events, blocks)
    up_half = got["up_rate_half_width_pp"]
    return {
        **got,
        "blocks": blocks,
        "events": events,
        "directional_mde_pp": up_half,
        "economic_mde_bp": got["return_half_width_bp"],
        "sub50_shift_required_pp": round(100 * (BASE_UP_RATE - SUB_50) + up_half, 2),
        "sub50_baseline_gap_pp": round(100 * (BASE_UP_RATE - SUB_50), 2),
    }


def _usable(verbose: bool = True) -> dict:
    """The three nested event samples, and the calendar they live on."""
    calendar = pitdata.load_calendar().calendar
    calendar = calendar[calendar >= pd.Timestamp(family10_panel.STUDY_START)]
    events = pd.read_parquet(EVENTS)
    sealed = examset.load()

    panel = pickle.load(open(PANEL_PKL, "rb"))
    index = panel["frame"].index
    grid = sorted(index.get_level_values("cutoff").unique())

    priced = on_panel(events, grid, calendar, index)
    safe = development_safe(events, calendar, [pd.Timestamp(c) for c in sealed.cutoffs])

    if verbose:
        print(f"calendar {len(calendar)} sessions, grid {len(grid)} cutoffs, "
              f"sealed exam {len(sealed.cutoffs)} cutoffs "
              f"(digest {sealed.digest[:16]}…, never opened)")
        print(f"all events                       {len(events):5,}")
        print(f"on a name the panel carries      {int(priced.sum()):5,}"
              f"  ({priced.mean():.1%})")
        print(f"…and clear of the sealed exam    {int((priced & safe).sum()):5,}"
              f"  ({(priced & safe).mean():.1%})")

    return {"calendar": calendar, "events": events,
            "priced": priced, "safe": safe,
            "grid_cutoffs": len(grid), "sealed": sealed}


def freeze(verbose: bool = True) -> dict:
    """Step 1. Structure and the frozen block length. **Computes no half-width.**"""
    world = _usable(verbose)
    events, calendar = world["events"], world["calendar"]
    priced, safe = world["priced"], world["safe"]

    samples = {
        "all_events": events,
        "panel_priceable": events[priced],
        "primary_development_safe": events[priced & safe],
    }
    structure = {name: block_structure(frame, calendar)
                 for name, frame in samples.items()}

    payload = {
        "frozen_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "Block length frozen BEFORE any half-width was computed. This "
                "artefact deliberately contains no MDE, no half-width and no "
                "verdict; `--gate` writes those in a later commit.",
        "block_length_sessions": BLOCK_LENGTH,
        "derivation": {
            "mechanical_overlap_sessions": HORIZON - 1,
            "record_persistence_allowance_sessions": 20,
            "additive": HORIZON - 1 + 20,
            "n_cube_root_event_sessions": round(
                structure["all_events"]["unique_event_sessions"] ** (1 / 3), 3),
            "sessions_per_event_session": round(
                len(calendar) / structure["all_events"]["unique_event_sessions"], 3),
            "n_cube_root_in_calendar_sessions": round(
                structure["all_events"]["unique_event_sessions"] ** (1 / 3)
                * len(calendar) / structure["all_events"]["unique_event_sessions"], 2),
            "source": "alpha/stats.py BLOCK_LENGTH=4 cutoffs (~one month) at H=5 "
                      "with q=0; alpha/V4_CHARTER.md 6.1 tie-break",
        },
        "blocks": int(len(calendar) // BLOCK_LENGTH),
        "survey_comparison": {"blocks_5d": SURVEY_BLOCKS_5D,
                              "blocks_10d": SURVEY_BLOCKS_10D,
                              "note": "reported only; neither decides the gate"},
        "primary_sample": "primary_development_safe",
        "structure": structure,
    }
    FREEZE_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    if verbose:
        print(f"\nBLOCK LENGTH FROZEN: L = {BLOCK_LENGTH} sessions  ->  "
              f"D = {payload['blocks']} blocks "
              f"(survey reported {SURVEY_BLOCKS_5D} at L=5, "
              f"{SURVEY_BLOCKS_10D} at L=10)")
        for name, got in structure.items():
            print(f"\n{name}: {got['events']:,} events, {got['unique_issuers']} "
                  f"issuers, {got['unique_event_sessions']} sessions, "
                  f"{got['occupied_blocks']}/{got['total_blocks']} blocks occupied")
            print(f"  per occupied block: {got['events_per_occupied_block_mean']} "
                  f"events (max {got['events_per_occupied_block_max']}), "
                  f"{got['issuers_per_occupied_block_mean']} issuers")
            print(f"  concentration: largest block {got['largest_block_share']:.2%}, "
                  f"top issuer {got['top_issuer_share']:.2%}, "
                  f"top 10 {got['top10_issuer_share']:.2%}")
            print(f"  repetition: {got['same_issuer_pairs_under_block']} of "
                  f"{got['same_issuer_pairs']} consecutive same-issuer pairs fall "
                  f"inside one block ({got['same_issuer_pairs_under_block_share']:.1%})")
        print("\nNo half-width computed. Run --gate after this is committed.")
    return payload


def run_gate(verbose: bool = True) -> dict:
    """Step 2. The half-widths, on the block length frozen in step 1."""
    if not FREEZE_PATH.exists():
        raise SystemExit("the block freeze must be committed before the gate runs")
    frozen = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if frozen["block_length_sessions"] != BLOCK_LENGTH:
        raise SystemExit("block length changed after the freeze — protocol breach")

    world = _usable(verbose)
    events, priced, safe = world["events"], world["priced"], world["safe"]
    calendar = world["calendar"]
    blocks = int(len(calendar) // BLOCK_LENGTH)

    samples = {"all_events": len(events),
               "panel_priceable": int(priced.sum()),
               "primary_development_safe": int((priced & safe).sum())}

    results = {name: gate(n, blocks) for name, n in samples.items()}
    comparison = {
        f"survey_L{length}_blocks{count}": gate(samples["primary_development_safe"],
                                                count)
        for length, count in ((5, SURVEY_BLOCKS_5D), (10, SURVEY_BLOCKS_10D))
    }

    # Robustness, computed *after* the freeze and unable to change it: the
    # verdict must not turn on the one number this stage chose. Reported for
    # every defensible block length, not only the frozen one.
    sensitivity = {
        str(length): {
            "blocks": 2664 // length,
            "primary": gate(samples["primary_development_safe"], 2664 // length),
            "all_events": gate(samples["all_events"], 2664 // length),
        }
        for length in (5, 7, 10, 14, 21, BLOCK_LENGTH, 30)
    }
    # The floor: what the half-width tends to as the event count grows without
    # bound. Because the bracket tends to rho, it does not go to zero — the
    # common market move never diversifies away (survey 1.1).
    floors = {str(length): gate(10 ** 9, 2664 // length)["economic_mde_bp"]
              for length in (5, 10, BLOCK_LENGTH)}

    primary = results["primary_development_safe"]
    payload = {
        "measured_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "No forward return read. Inputs are the marginal target "
                "properties committed in alpha/source_probe.py.",
        "block_length_sessions": BLOCK_LENGTH,
        "blocks": blocks,
        "base_up_rate": BASE_UP_RATE,
        "variance_inputs": {"return_sd": source_probe.RETURN_SD,
                            "return_rho": source_probe.RETURN_RHO,
                            "up_variance": source_probe.UP_VAR,
                            "up_rho": source_probe.UP_RHO,
                            "block_inflation": source_probe.BLOCK_INFLATION},
        "samples": results,
        "primary": primary,
        "survey_block_comparison": comparison,
        "block_length_sensitivity": sensitivity,
        "half_width_floor_bp_as_n_grows": floors,
        "economic_hurdle_bp": ECONOMIC_HURDLE_BP,
        "economic_hurdle_source":
            "reports/ABSOLUTE_ALPHA_SOURCE_SURVEY.md 1.2 claim (c), committed "
            "at 4a966a2 before this pilot began: an effect is economically "
            "useful only above ~39 bp per 5 sessions (Phase 1's covered-book "
            "resolution), and 3.3 judged the family by whether its half-width "
            "sat inside that.",
        "economic_claim_detectable": bool(
            primary["economic_mde_bp"] <= ECONOMIC_HURDLE_BP),
        "passed": bool(primary["economic_mde_bp"] <= ECONOMIC_HURDLE_BP),
    }
    GATE_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    if verbose:
        print(f"\nblock length L = {BLOCK_LENGTH} (frozen), D = {blocks} blocks")
        print(f"{'sample':32s} {'n':>6s} {'return bp':>10s} {'up-rate pp':>11s} "
              f"{'sub-50 need':>12s}")
        for name, got in results.items():
            print(f"{name:32s} {got['events']:6,} {got['economic_mde_bp']:10.1f} "
                  f"{got['directional_mde_pp']:11.2f} "
                  f"{got['sub50_shift_required_pp']:12.2f}")
        print(f"\nreported for comparison only (neither decides the gate):")
        for name, got in comparison.items():
            print(f"{name:32s} {got['events']:6,} {got['economic_mde_bp']:10.1f} "
                  f"{got['directional_mde_pp']:11.2f} "
                  f"{got['sub50_shift_required_pp']:12.2f}")

        print(f"\nblock-length sensitivity (computed after the freeze; "
              f"cannot change it):")
        print(f"{'L':>4s} {'blocks':>7s} {'primary bp':>11s} {'all-events bp':>14s}")
        for length, got in sensitivity.items():
            mark = " <= hurdle" if got["primary"]["economic_mde_bp"] <= \
                ECONOMIC_HURDLE_BP else ""
            print(f"{length:>4s} {got['blocks']:>7d} "
                  f"{got['primary']['economic_mde_bp']:>11.1f} "
                  f"{got['all_events']['economic_mde_bp']:>14.1f}{mark}")
        print(f"\nhalf-width floor as the event count grows without bound: "
              + ", ".join(f"L={k}: {v:.1f} bp" for k, v in floors.items()))
        print(f"\nhurdle {ECONOMIC_HURDLE_BP} bp (survey §1.2 claim c, committed "
              f"at 4a966a2)  |  primary {primary['economic_mde_bp']:.1f} bp  ->  "
              f"{'PASS' if payload['passed'] else 'FAIL'}")
    return payload


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--gate" in argv:
        run_gate()
    else:
        freeze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
