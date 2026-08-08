"""Stage 0 — build the (cutoff x symbol) panel once and freeze it.

Every experiment in §27 reads the same panel and differs only in which columns
it is allowed to use. Building it once is not just a speed decision: it means
V2-A and V2-B are provably looking at the same rows, the same universe and the
same outcomes, so a difference between them is a difference in features rather
than a difference in anything else.

The panel contains both development and exam cutoffs. That is safe — a row is
not a result — and the discipline that matters lives downstream:
`alpha.develop` slices to development cutoffs and never sees the others, and
`alpha.exam` is a separate process that refuses to overwrite its own output.

Run:  python -m alpha.build_panel
"""

from __future__ import annotations

import json
import pathlib
import time

import pandas as pd

from . import dataset, pitdata

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
PANEL_PATH = OUT_DIR / "panel.pkl"
META_PATH = OUT_DIR / "panel_meta.json"

TIERS = ("absolute", "relative", "context")


def panel_cutoffs(book: pitdata.PriceBook) -> tuple[list, list, list]:
    """Every cutoff the panel must carry: `(built, development, exam)`.

    The twelve exam dates are V1's, chosen years before this schedule existed,
    so they do not sit on a 5-session grid anchored at 2016-01-04 — only four
    of them land on it by coincidence. The panel is built over the union, or
    `alpha.exam` has no rows to predict on two thirds of its own paper.

    Development is still defined by the schedule alone and is unchanged by the
    union: the exam dates are extra rows, and `alpha.develop` slices them away
    before it looks at anything. Separated out from `main` so the invariant
    "the panel covers the exam" is a thing a test can assert.
    """
    scheduled = dataset.schedule(book)
    development, exam = dataset.split(scheduled, book)
    return sorted(set(scheduled) | set(exam)), development, exam


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    book = pitdata.load_book()
    cutoffs = dataset.schedule(book)
    build_cutoffs, development, exam = panel_cutoffs(book)

    print(f"calendar   {book.calendar[0].date()} .. {book.calendar[-1].date()}")
    print(f"cutoffs    {len(cutoffs)} scheduled  ->  {len(development)} development, "
          f"{len(exam)} exam ({dataset.EXAM_GUARD}-session guard applied)")
    print(f"building   {len(build_cutoffs)} cutoffs (schedule + the "
          f"{len(set(exam) - set(cutoffs))} exam dates not on the schedule)")
    print(f"spacing    {dataset.SPACING} sessions, horizon {dataset.HORIZON} "
          f"-> outcome windows non-overlapping")

    started = time.time()
    panel = dataset.build(book, build_cutoffs, tiers=TIERS, with_beta=True)
    print(f"\npanel      {len(panel.frame):,} rows  ·  {len(panel.feature_columns)} features "
          f"·  {time.time() - started:.0f}s")

    pd.to_pickle({"frame": panel.frame, "feature_columns": panel.feature_columns,
                  "regimes": panel.regimes, "diagnostics": panel.diagnostics,
                  "development": development, "exam": exam}, PANEL_PATH)

    coverage = panel.diagnostics
    META_PATH.write_text(json.dumps({
        "built_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "rows": int(len(panel.frame)),
        "features": len(panel.feature_columns),
        "cutoffs_scheduled": len(cutoffs),
        "cutoffs_built": len(build_cutoffs),
        "cutoffs_development": len(development),
        "cutoffs_exam": len(exam),
        "exam_dates_off_schedule": len(set(exam) - set(cutoffs)),
        "first_cutoff": str(cutoffs[0].date()),
        "last_cutoff": str(cutoffs[-1].date()),
        "spacing_sessions": dataset.SPACING,
        "horizon_sessions": dataset.HORIZON,
        "embargo_sessions": dataset.EMBARGO,
        "median_cross_section": int(panel.frame.groupby(level=0).size().median()),
        "min_cross_section": int(panel.frame.groupby(level=0).size().min()),
        "max_cross_section": int(panel.frame.groupby(level=0).size().max()),
        "median_index_coverage_pct": float(coverage["coverage_pct"].median())
        if "coverage_pct" in coverage else None,
        "earliest_index_coverage_pct": float(coverage["coverage_pct"].iloc[0])
        if "coverage_pct" in coverage else None,
    }, indent=2), encoding="utf-8")
    print(f"froze      {PANEL_PATH}")


def load() -> tuple[dataset.Panel, list[pd.Timestamp], list[pd.Timestamp]]:
    if not PANEL_PATH.exists():
        raise SystemExit("no panel — run: python -m alpha.build_panel")
    blob = pd.read_pickle(PANEL_PATH)
    panel = dataset.Panel(blob["frame"], blob["feature_columns"],
                          blob["regimes"], blob["diagnostics"])
    return panel, blob["development"], blob["exam"]


if __name__ == "__main__":
    main()
