"""Build the Family 3 `inst_holdings_change` panel on the 316 development
cutoffs, then run the §2.10 clause-3 correlation ceiling and measure turnover.

FEATURE-ONLY. The target is never read and no IC against forward returns is
computed here. Implements only what `alpha/V3_FAMILY3_PREREGISTRATION.md`
§2-§5 froze:

* `S(i, Q)` = total shares of issuer i reported held at quarter-end Q, summed
  over every 13F filer, counting only filings **filed strictly before** the
  cutoff (§4 - stricter than the acceptance-time door, and therefore incapable
  of leaking);
* amendments resolved as restatements are: per (filer, period) the **latest
  admissible** filing wins;
* Q1 = the most recent quarter-end whose **45-day deadline has passed** at the
  cutoff, Q0 = the quarter-end before it (§3);
* feature = `S(Q1)/S(Q0) - 1`, and **NaN** whenever either is unavailable or
  S(Q0) is zero (§5) - never filled.

ASCII stdout only.
"""

from __future__ import annotations

import json
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, r"c:/Users/onurc/Desktop/AI Stock/Stock-Prediction-Models")

from alpha import carrier, examset, protocol  # noqa: E402

EVENTS = "alpha/edgar/f13_events.parquet"
OUT_PANEL = "alpha/out/f13_panel.pkl"

DEADLINE_DAYS = 45          # §3, statutory. Not a tuning knob.
LAMBDA = 0.25               # §8, fixed, not scanned
CEILING_MOMENTUM = 0.30     # §8, fixed before the correlation is read
CEILING_INPUT = 0.50


def holdings_by_cutoff(events: pd.DataFrame, cutoffs: pd.DatetimeIndex
                       ) -> dict[pd.Timestamp, pd.Series]:
    """(cutoff, period) -> Series cik -> total admissible shares.

    Returns a dict keyed by cutoff holding the two period totals the feature
    needs, so each period is sorted once rather than once per cutoff.
    """
    periods = np.array(sorted(events["period"].unique()))
    by_period = {p: g.sort_values(["filed", "accn"], kind="mergesort")
                 for p, g in events.groupby("period", sort=True)}

    # which (period, cutoff) pairs are actually needed
    need: dict[np.datetime64, list[pd.Timestamp]] = {}
    plan: dict[pd.Timestamp, tuple] = {}
    for cutoff in cutoffs:
        deadline = np.datetime64(pd.Timestamp(cutoff) - pd.Timedelta(days=DEADLINE_DAYS))
        eligible = periods[periods < deadline]
        if len(eligible) < 2:
            plan[cutoff] = (None, None)
            continue
        q1, q0 = eligible[-1], eligible[-2]
        plan[cutoff] = (q1, q0)
        need.setdefault(q1, []).append(cutoff)
        need.setdefault(q0, []).append(cutoff)

    totals: dict[tuple, pd.Series] = {}
    for period, wanted in need.items():
        group = by_period.get(pd.Timestamp(period))
        if group is None:
            continue
        # A filing is the latest admissible one for its (filer, issuer) at T iff
        # it was filed before T and the filer's NEXT filing for this period was
        # not. Precomputing that interval once turns "latest per filer at each
        # cutoff" from a groupby per cutoff into a boolean mask per cutoff.
        group = group.sort_values(["cik", "filer", "filed", "accn"],
                                  kind="mergesort")
        nxt = group.groupby(["cik", "filer"], sort=False)["filed"].shift(-1)
        filed = group["filed"].to_numpy()
        nxt = nxt.to_numpy()
        never_superseded = pd.isna(nxt)
        shares = group["shares"].to_numpy()
        ciks = group["cik"].to_numpy()
        for cutoff in wanted:
            edge = np.datetime64(pd.Timestamp(cutoff))
            active = (filed < edge) & (never_superseded | (nxt >= edge))
            if not active.any():
                continue
            totals[(cutoff, period)] = pd.Series(
                shares[active], index=ciks[active]).groupby(level=0).sum()
    return plan, totals


def build_panel(dev, members, symbol_to_cik) -> pd.DataFrame:
    events = pd.read_parquet(EVENTS)
    print("events %d rows, %d filers, %d issuers, periods %s..%s"
          % (len(events), events["filer"].nunique(), events["cik"].nunique(),
             pd.Timestamp(events["period"].min()).date(),
             pd.Timestamp(events["period"].max()).date()))

    plan, totals = holdings_by_cutoff(events, dev)
    by_cutoff = {c: g["symbol"].tolist() for c, g in members.groupby("cutoff", sort=True)}

    records = []
    for n, cutoff in enumerate(dev, 1):
        q1, q0 = plan[cutoff]
        s1 = totals.get((cutoff, q1), pd.Series(dtype=float)) if q1 is not None else pd.Series(dtype=float)
        s0 = totals.get((cutoff, q0), pd.Series(dtype=float)) if q0 is not None else pd.Series(dtype=float)
        for symbol in by_cutoff.get(cutoff, ()):
            cik = symbol_to_cik.get(symbol)
            a = s1.get(cik, np.nan) if cik is not None else np.nan
            b = s0.get(cik, np.nan) if cik is not None else np.nan
            value = (a / b - 1.0) if (np.isfinite(a) and np.isfinite(b) and b > 0) else np.nan
            records.append(dict(cutoff=cutoff, symbol=symbol, change=value,
                                shares_q1=a, shares_q0=b,
                                q1=pd.Timestamp(q1) if q1 is not None else pd.NaT))
        if n % 50 == 0:
            print("  ... %d/%d cutoffs" % (n, len(dev)))
    return pd.DataFrame(records).set_index(["cutoff", "symbol"]).sort_index()


def per_cutoff_spearman(x, y) -> pd.Series:
    out = []
    for _, g in pd.DataFrame({"x": x, "y": y}).groupby(level="cutoff"):
        g = g.dropna()
        if len(g) >= 50 and g["x"].nunique() > 1 and g["y"].nunique() > 1:
            out.append(g["x"].rank().corr(g["y"].rank()))
    return pd.Series(out)


def turnover(prediction, quantile: float = 0.2) -> float:
    frame = prediction.dropna()
    books, cutoffs = {}, sorted(frame.index.get_level_values(0).unique())
    for cutoff in cutoffs:
        group = frame.loc[cutoff]
        rank = group.rank(pct=True)
        books[cutoff] = set(group.index[rank > 1 - quantile])
    changes = []
    for before, after in zip(cutoffs, cutoffs[1:]):
        a, b = books[before], books[after]
        if a:
            changes.append(len(b - a) / len(a))
    return float(np.mean(changes)) if changes else float("nan")


def main() -> int:
    t0 = time.time()
    meta = json.load(open("alpha/edgar/filings_meta.json"))
    symbol_to_cik = {s: int(c) for s, c in meta["symbol_to_cik"].items()}

    es = examset.load()
    dev = pd.DatetimeIndex(sorted(es.development))
    exam_overlap = len(set(dev) & set(es.cutoffs))
    print("exam contamination: %d (must be 0)" % exam_overlap)
    assert exam_overlap == 0

    panel = pickle.load(open("alpha/out/panel.pkl", "rb"))
    frame = panel["frame"]
    members = frame.index.to_frame(index=False)[["cutoff", "symbol"]]
    members = members[members["cutoff"].isin(dev)]
    print("members rows %d on %d cutoffs" % (len(members), members["cutoff"].nunique()))

    feat = build_panel(dev, members, symbol_to_cik)
    print("panel rows %d built in %.1fs" % (len(feat), time.time() - t0))
    with open(OUT_PANEL, "wb") as f:
        pickle.dump({"feature": feat, "deadline_days": DEADLINE_DAYS,
                     "built_at": pd.Timestamp.now().isoformat()}, f)

    x = feat["change"]
    print()
    print("=== coverage ===")
    print("defined (non-NaN): %.4f   NaN rows %d" % (x.notna().mean(), int(x.isna().sum())))
    per = x.notna().groupby(level="cutoff").mean()
    cnt = x.notna().groupby(level="cutoff").sum()
    print("per cutoff: mean %.4f  median %.4f  p10 %.4f  min %.4f"
          % (per.mean(), per.median(), per.quantile(.1), per.min()))
    print("names per cutoff: median %d  p10 %d  min %d" % (cnt.median(), cnt.quantile(.1), cnt.min()))
    d = x.dropna()
    print("change distribution: p1 %+.4f  p25 %+.4f  median %+.4f  p75 %+.4f  p99 %+.4f"
          % tuple(d.quantile([.01, .25, .5, .75, .99])))
    cutoff_col = pd.Series(feat.index.get_level_values("cutoff"), index=feat.index)
    lag = (cutoff_col - feat["q1"]).dt.days
    print("staleness of Q1 at the cutoff: median %d days  p90 %d days"
          % (np.nanmedian(lag), np.nanpercentile(lag.dropna(), 90)))

    # ---------------------------------------------------------- clause 3
    d3 = json.load(open("alpha/out/v2_3_development.json"))
    cols34 = d3["input_columns"]
    dev_frame = frame.loc[frame.index.get_level_values("cutoff").isin(dev)]
    needed = ["ret_12_1"] + [c[len(carrier.RANK_PREFIX):] for c in cols34
                             if c.startswith(carrier.RANK_PREFIX)]
    dev_frame, _ = carrier.add_rank_columns(dev_frame, tuple(dict.fromkeys(needed)))
    both = dev_frame[["z__ret_12_1"] + list(cols34)].join(x, how="inner").dropna(subset=["change"])
    print("\njoined rows with the feature: %d" % len(both))

    rho = per_cutoff_spearman(both["change"], both["z__ret_12_1"])
    mom = rho.abs().mean()
    print()
    print("=== Section 2.10 clause 3 (ceilings fixed in the preregistration) ===")
    print("vs z__ret_12_1: mean %+.4f  mean|rho| %.4f  p95 %.4f  n %d  -> %s"
          % (rho.mean(), mom, rho.abs().quantile(.95), len(rho),
             "PASS" if mom <= CEILING_MOMENTUM else "FAIL"))
    worst = []
    for c in cols34:
        r = per_cutoff_spearman(both["change"], both[c])
        worst.append((r.abs().mean(), r.mean(), c))
    worst.sort(reverse=True)
    print("top |rho| against the 34-column set:")
    for a, m, c in worst[:6]:
        print("   %-38s mean|rho| %.4f  mean %+.4f" % (c, a, m))
    breaches = [w for w in worst if w[0] > CEILING_INPUT]
    print("highest of %d columns: %.4f (%s) -> %s"
          % (len(worst), worst[0][0], worst[0][2],
             "PASS" if not breaches else "FAIL (%d breach)" % len(breaches)))

    # ---------------------------------------------------------- turnover
    rank = x.groupby(level="cutoff").rank(pct=True, na_option="keep")
    benchmarks = protocol.benchmark_scores(dev_frame, panel["regimes"])
    b3 = benchmarks["b3_regime_switched"].groupby(level=0).rank(pct=True, na_option="keep")
    arm1 = b3 + LAMBDA * (rank.reindex(b3.index) - 0.5)
    t_feat, t_b3, t_a1 = turnover(rank), turnover(b3), turnover(arm1)
    print()
    print("=== turnover ===")
    print("Arm 0 feature-only  %.4f" % t_feat)
    print("B3 incumbent        %.4f" % t_b3)
    print("Arm 1 B3+0.25 tilt  %.4f" % t_a1)
    print("EXTRA Arm1-B3       %+.4f (%.1f pp) -> %s"
          % (t_a1 - t_b3, (t_a1 - t_b3) * 100,
             "MDE +0.007 stands" if (t_a1 - t_b3) <= 0.30 else "MDE must be raised"))

    # §2.12 diagnostic: how much does the tilt actually reorder?
    rows = []
    for c, g in pd.DataFrame({"a": arm1, "b": b3}).groupby(level=0):
        g = g.dropna()
        if len(g) >= 50:
            rows.append(g["a"].corr(g["b"], method="spearman"))
    print("Spearman(Arm1, B3) per cutoff: mean %.6f  min %.6f"
          % (np.mean(rows), np.min(rows)))
    print("\ntotal %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
