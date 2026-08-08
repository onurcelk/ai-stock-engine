"""The V2.1 frozen exam set — construction, freeze, and the only way to read it.

V2's exam paper was twelve dates inherited from V1. Criterion 7 asks for at
least fifty independent cutoffs, so that exam could not pass whatever a model
did, and its IC interval spanned [-0.063, +0.239] — no power against any
plausible effect size. `V2_1_PREREGISTRATION.md` §0 is the argument; this module
is the fix.

The selection rule is deterministic and reads the trading calendar and nothing
else (§2.1):

    grid       every 5th session from 2016-01-04 with a full outcome ahead
    warm-up    the first 504 sessions of the grid are development-only
    exam       every 6th grid cutoff at or after the warm-up boundary
    development every remaining grid cutoff at least HORIZON + EMBARGO
               sessions clear of every exam cutoff

Two properties are worth stating because the whole protocol rests on them:

* Exam outcome windows are 5 sessions long and 30 sessions apart, so **every
  pair is separated by at least 25 clear sessions**. Mechanical overlap is
  absent rather than corrected for.
* No development outcome window touches an exam one. `MIN_SEPARATION` is the
  same `HORIZON + EMBARGO` boundary `dataset.training_cutoffs` enforces at fit
  time, applied here to the *set* rather than to one fit, so a future code path
  that forgets the fit-time rule still cannot produce an abutting window.

Nothing in this file reads a return, an outcome, a target or an IC. The
metadata it freezes alongside the dates — regime, VIX, cross-section width,
index coverage — is computed from a `PriceView`, which is truncated at the
cutoff before it is handed over.

Run:  python -m alpha.examset freeze     # writes out/v2_1_exam_set.json, once
      python -m alpha.examset show       # print the frozen set and its metadata
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import sys

import numpy as np
import pandas as pd

from . import dataset, features, pitdata, universe

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
PATH = OUT_DIR / "v2_1_exam_set.json"

PROTOCOL = "V2.1"

# --- the selection rule, §2.1. Changing any of these changes the exam set, and
# --- the frozen artifact's digest is what makes that impossible to do quietly.
HORIZON = dataset.HORIZON               # 5 sessions
EMBARGO = dataset.EMBARGO               # 5 sessions
SPACING = dataset.SPACING               # 5 sessions between grid cutoffs
STUDY_START = dataset.STUDY_START       # 2016-01-04

EXAM_STEP = 6                           # every 6th grid cutoff -> 30 sessions apart
WARMUP_SESSIONS = 504                   # ~2 years of grid reserved for development
MIN_SEPARATION = HORIZON + EMBARGO      # 10 sessions between any dev and any exam window
MIN_EXAM_CUTOFFS = 60                   # §2.3 — the bar the rule has to clear


@dataclasses.dataclass(frozen=True)
class ExamSet:
    """The frozen paper: dates, the rule that produced them, and per-date metadata.

    Deliberately carries no outcome of any kind. `cutoffs` and `metadata` are
    everything a caller gets, and `metadata` holds only quantities computable
    from bars at or before the cutoff.
    """

    cutoffs: list[pd.Timestamp]
    development: list[pd.Timestamp]
    rule: dict
    metadata: list[dict]
    digest: str
    frozen_at: str

    @property
    def index(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self.cutoffs)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.metadata).set_index("cutoff")


# ----------------------------------------------------------------------
# Selection — calendar arithmetic, and nothing else
# ----------------------------------------------------------------------

def grid(book) -> list[pd.Timestamp]:
    """The 5-session cutoff grid. Identical to V2's schedule, by design."""
    return dataset.schedule(book, spacing=SPACING, start=STUDY_START, horizon=HORIZON)


def warmup_length(points: list[pd.Timestamp]) -> int:
    """How many leading grid points the §2.1 warm-up reserves for development.

    Expressed in sessions and converted here rather than written down as a
    cutoff count, because the development set depends on the exam set and an
    exam set defined in terms of the development set would be circular.
    """
    return min(len(points), WARMUP_SESSIONS // SPACING)


def select(points: list[pd.Timestamp], step: int = EXAM_STEP) -> list[pd.Timestamp]:
    """Every `step`-th grid cutoff at or after the warm-up boundary (§2.1 rule 3)."""
    return list(points[warmup_length(points)::step])


def development(points: list[pd.Timestamp], exam: list[pd.Timestamp],
                calendar: pd.DatetimeIndex,
                separation: int = MIN_SEPARATION) -> list[pd.Timestamp]:
    """Grid cutoffs whose outcome windows stay `separation` sessions clear of the exam.

    A cutoff is dropped when it *is* an exam cutoff or when it sits closer than
    `separation` sessions to one. At `separation = HORIZON + EMBARGO` that is
    exactly "at least EMBARGO clear sessions between the two outcome windows",
    in both directions.
    """
    exam_positions = np.array([calendar.searchsorted(pd.Timestamp(e)) for e in exam])
    keep = []
    for cutoff in points:
        position = calendar.searchsorted(pd.Timestamp(cutoff))
        if exam_positions.size and np.abs(exam_positions - position).min() < separation:
            continue
        keep.append(cutoff)
    return keep


def separations(exam: list[pd.Timestamp], calendar: pd.DatetimeIndex) -> list[int]:
    """Sessions between consecutive exam cutoffs — the §2.4 independence evidence."""
    positions = [calendar.searchsorted(pd.Timestamp(e)) for e in sorted(exam)]
    return [int(b - a) for a, b in zip(positions, positions[1:])]


def independence(exam: list[pd.Timestamp], calendar: pd.DatetimeIndex,
                 horizon: int = HORIZON) -> dict:
    """Is every pair of exam outcome windows disjoint? Reported, not assumed."""
    gaps = separations(exam, calendar)
    return {
        "n_cutoffs": len(exam),
        "horizon_sessions": horizon,
        "min_gap_sessions": min(gaps) if gaps else None,
        "max_gap_sessions": max(gaps) if gaps else None,
        "min_clear_sessions_between_windows": (min(gaps) - horizon) if gaps else None,
        "all_windows_disjoint": bool(gaps) and min(gaps) >= horizon,
        "duplicates": len(exam) - len(set(exam)),
    }


# ----------------------------------------------------------------------
# Metadata — pre-cutoff only
# ----------------------------------------------------------------------

def _regime_at(view: pitdata.PriceView) -> tuple[dict, float, float]:
    """The V2 regime tag plus the VIX inputs behind it, from a truncated view."""
    vix = view.close["^VIX"].dropna() if "^VIX" in view.close.columns else pd.Series(dtype=float)
    level = float(vix.iloc[-1]) if len(vix) else float("nan")
    trailing = vix.iloc[-252:]
    median = float(trailing.median()) if len(vix) > 20 else float("nan")
    percentile = float((trailing <= level).mean()) if len(vix) > 20 else float("nan")
    return features.regime_state(view.close["SPY"].dropna(), level, median), level, percentile


def describe(book: pitdata.PriceBook, cutoff: pd.Timestamp,
             calendar: pd.DatetimeIndex) -> dict:
    """One exam cutoff's pre-cutoff description. Reads a `PriceView` and nothing else."""
    view = book.view(cutoff)
    regime, vix_level, vix_percentile = _regime_at(view)
    eligible = universe.eligible_at(cutoff, book)
    spy = view.close["SPY"].dropna()

    return {
        "cutoff": str(pd.Timestamp(cutoff).date()),
        "session_index": int(calendar.searchsorted(pd.Timestamp(cutoff))),
        "trend_regime": regime["trend"],
        "vol_regime": regime["vol"],
        "vix_level": _finite(vix_level),
        "vix_percentile_252d": _finite(vix_percentile),
        "spy_ret_60d": _finite(float(spy.iloc[-1] / spy.iloc[-61] - 1.0) if len(spy) > 61 else np.nan),
        "spy_ret_252d": _finite(float(spy.iloc[-1] / spy.iloc[-253] - 1.0) if len(spy) > 253 else np.nan),
        "eligible_names": int(eligible.diagnostics["eligible"]),
        "index_members": int(eligible.diagnostics["index_members"]),
        "index_coverage_pct": float(eligible.diagnostics["coverage_pct"]),
        "sectors_present": int(eligible.diagnostics["sectors_present"]),
    }


def _finite(value) -> float | None:
    value = float(value) if value is not None else float("nan")
    return None if not np.isfinite(value) else round(value, 6)


# ----------------------------------------------------------------------
# Freeze / load
# ----------------------------------------------------------------------

def digest_of(cutoffs: list[pd.Timestamp]) -> str:
    """SHA-256 over the sorted date strings — §2.5's immutability check."""
    payload = "\n".join(str(pd.Timestamp(c).date()) for c in sorted(cutoffs))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build(book: pitdata.PriceBook, verbose: bool = True) -> tuple[list, list, dict]:
    """Apply the §2.1 rule. Returns `(exam, development, rule)` — no file written."""
    calendar = book.calendar
    points = grid(book)
    exam = select(points)
    dev = development(points, exam, calendar)

    rule = {
        "protocol": PROTOCOL,
        "study_start": STUDY_START,
        "grid_spacing_sessions": SPACING,
        "horizon_sessions": HORIZON,
        "embargo_sessions": EMBARGO,
        "min_separation_sessions": MIN_SEPARATION,
        "warmup_sessions": WARMUP_SESSIONS,
        "warmup_grid_cutoffs": warmup_length(points),
        "exam_step_grid_cutoffs": EXAM_STEP,
        "exam_spacing_sessions": EXAM_STEP * SPACING,
        "grid_cutoffs": len(points),
        "exam_cutoffs": len(exam),
        "development_cutoffs": len(dev),
        "min_exam_cutoffs_required": MIN_EXAM_CUTOFFS,
        "statement": (
            "Exam = every {step}th cutoff of the {spacing}-session grid at or after "
            "the first {warm} sessions. Development = every remaining grid cutoff at "
            "least {sep} sessions from any exam cutoff. Calendar arithmetic only; no "
            "return, outcome or IC is read.".format(
                step=EXAM_STEP, spacing=SPACING, warm=WARMUP_SESSIONS,
                sep=MIN_SEPARATION)),
    }
    if verbose:
        print(f"grid       {len(points)} cutoffs, {points[0].date()} .. {points[-1].date()}")
        print(f"warm-up    {rule['warmup_grid_cutoffs']} grid cutoffs "
              f"({WARMUP_SESSIONS} sessions), development-only")
        print(f"exam       every {EXAM_STEP}th -> {len(exam)} cutoffs, "
              f"{EXAM_STEP * SPACING} sessions apart")
        print(f"developmnt {len(dev)} cutoffs (>= {MIN_SEPARATION} sessions from any exam date)")
    return exam, dev, rule


def freeze(verbose: bool = True) -> ExamSet:
    """Write the exam set once. Refuses to overwrite (§2.5)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if PATH.exists():
        raise SystemExit(
            f"{PATH} already exists — the V2.1 exam set is frozen.\n"
            "Re-freezing means deleting it, which is a deliberate act that has to "
            "be explained in V2_1_EXPERIMENT_LOG.md. An exam set that can be "
            "rebuilt after a result is not an exam set.")

    book = pitdata.load_book()
    calendar = book.calendar
    exam, dev, rule = build(book, verbose=verbose)

    if len(exam) < MIN_EXAM_CUTOFFS:
        # §10: report the maximum defensible number rather than relax independence.
        print(f"\nWARNING: the rule yields {len(exam)} exam cutoffs, below the "
              f"{MIN_EXAM_CUTOFFS} the protocol asks for. Freezing it anyway and "
              "reporting the shortfall is the pre-registered response; shortening "
              "the embargo or the warm-up to reach 60 is not.")

    independence_report = independence(exam, calendar)
    if not independence_report["all_windows_disjoint"]:
        raise RuntimeError(f"exam outcome windows overlap: {independence_report}")

    if verbose:
        print(f"\nmetadata   describing {len(exam)} cutoffs from pre-cutoff bars...")
    metadata = [describe(book, cutoff, calendar) for cutoff in exam]

    payload = {
        "protocol": PROTOCOL,
        "frozen_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "preregistration": "alpha/V2_1_PREREGISTRATION.md",
        "rule": rule,
        "independence": independence_report,
        "digest": digest_of(exam),
        "exam_cutoffs": [str(pd.Timestamp(c).date()) for c in exam],
        "development_cutoffs": [str(pd.Timestamp(c).date()) for c in dev],
        "metadata": metadata,
        "distribution": distribution(metadata),
        "note": (
            "Frozen before any V2.1 model existed. Contains dates and pre-cutoff "
            "descriptions only — no return, target, outcome or IC. See "
            "V2_1_PREREGISTRATION.md §2.6 for the disclosed limitation that these "
            "dates lie inside the window V2's development ladder ran over."),
    }
    PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    if verbose:
        print(f"froze      {len(exam)} exam cutoffs -> {PATH}")
        print(f"digest     {payload['digest']}")
    return load()


def distribution(metadata: list[dict]) -> dict:
    """Regime, volatility and coverage mix of the frozen set — §2.2's coverage check."""
    frame = pd.DataFrame(metadata)
    if frame.empty:
        return {}
    return {
        "trend_regime": {str(k): int(v) for k, v in frame["trend_regime"].value_counts().items()},
        "vol_regime": {str(k): int(v) for k, v in frame["vol_regime"].value_counts().items()},
        "years": {str(k): int(v) for k, v in
                  pd.to_datetime(frame["cutoff"]).dt.year.value_counts().sort_index().items()},
        "eligible_names": {
            "min": int(frame["eligible_names"].min()),
            "median": int(frame["eligible_names"].median()),
            "max": int(frame["eligible_names"].max())},
        "index_coverage_pct": {
            "min": float(frame["index_coverage_pct"].min()),
            "median": float(frame["index_coverage_pct"].median()),
            "max": float(frame["index_coverage_pct"].max())},
        "vix_level": {
            "min": float(frame["vix_level"].min()),
            "median": float(frame["vix_level"].median()),
            "max": float(frame["vix_level"].max())},
    }


def load(path: pathlib.Path | None = None) -> ExamSet:
    """The only supported way to obtain V2.1 exam dates.

    Recomputes the digest and refuses to hand back a set whose contents have
    drifted from what was frozen. A silently edited exam paper is the failure
    this protocol exists to make impossible, so it fails loudly instead.
    """
    path = PATH if path is None else pathlib.Path(path)
    if not path.exists():
        raise SystemExit(f"no {path} — run: python -m alpha.examset freeze")

    payload = json.loads(path.read_text(encoding="utf-8"))
    cutoffs = [pd.Timestamp(d) for d in payload["exam_cutoffs"]]
    recomputed = digest_of(cutoffs)
    if recomputed != payload.get("digest"):
        raise RuntimeError(
            f"{path} has been edited since it was frozen: digest {recomputed} "
            f"does not match the recorded {payload.get('digest')}.")

    return ExamSet(
        cutoffs=cutoffs,
        development=[pd.Timestamp(d) for d in payload["development_cutoffs"]],
        rule=payload["rule"],
        metadata=payload["metadata"],
        digest=payload["digest"],
        frozen_at=payload["frozen_at"],
    )


def development_only(panel: dataset.Panel, exam_set: ExamSet | None = None) -> dataset.Panel:
    """Slice a panel to development cutoffs and prove no exam date survived.

    §7's "the frozen exam cannot accidentally be used by develop", expressed as
    the one call a development stage is meant to make. The assertion is not
    decoration: `slice_cutoffs` takes a keep-list, so a caller that passes the
    wrong list gets a wrong panel and no error.
    """
    exam_set = load() if exam_set is None else exam_set
    sliced = panel.slice_cutoffs(exam_set.development)
    leaked = sorted(set(sliced.cutoffs) & set(exam_set.cutoffs))
    if leaked:
        raise RuntimeError(f"development panel contains exam cutoffs: {leaked}")
    return sliced


# ----------------------------------------------------------------------

def show() -> None:
    exam_set = load()
    frame = exam_set.frame()
    print(f"protocol   {PROTOCOL}, frozen {exam_set.frozen_at}")
    print(f"digest     {exam_set.digest}")
    print(f"exam       {len(exam_set.cutoffs)} cutoffs, "
          f"{exam_set.cutoffs[0].date()} .. {exam_set.cutoffs[-1].date()}")
    print(f"developmnt {len(exam_set.development)} cutoffs")
    print(f"rule       {exam_set.rule['statement']}\n")
    with pd.option_context("display.max_rows", 200, "display.width", 200,
                           "display.max_columns", 20):
        print(frame[["trend_regime", "vol_regime", "vix_level", "eligible_names",
                     "index_coverage_pct"]])
    print("\ndistribution:")
    print(json.dumps(distribution(exam_set.metadata), indent=1))


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    action = argv[0] if argv else ""
    if action == "freeze":
        freeze()
    elif action == "show":
        show()
    else:
        raise SystemExit("usage: python -m alpha.examset {freeze|show}\n"
                         "  freeze  apply the §2.1 rule and write out/v2_1_exam_set.json (once)\n"
                         "  show    print the frozen set, its metadata and its distribution")


if __name__ == "__main__":
    main()
