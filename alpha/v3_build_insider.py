"""Build the Family 2 `insider_purchase_intensity` panel on the 316 development
cutoffs, then run the two checks `reports/FAMILY2_ELIGIBILITY.md` §7 left as
mechanical: the §2.10 clause-3 correlation ceiling, and the turnover input to
the MDE.

FEATURE-ONLY. The target is never read, no arm is scored, no IC against forward
returns is computed, and nothing here depends on the prediction horizon — which
is exactly why it can run while `V3_FAMILY2_PREREGISTRATION.md` §6 is still
open. `alpha/targets.py` is not imported.

Implements only what §1-§5 of that pre-registration froze:

* open-market purchases of common equity (`TRANS_CODE == 'P'`, non-derivative,
  acquisitions), already isolated by `alpha/build_insider.py`;
* value = shares x price, summed across every insider of the issuer, with no
  role weighting;
* normalised by market capitalisation at the cutoff = shares outstanding
  (`dei:EntityCommonStockSharesOutstanding`, read through the same acceptance
  door as every other filing fact) x close (through `pitdata.PriceView`);
* a 90 calendar-day lookback on the *transaction* date, admissibility on the
  *acceptance* timestamp;
* no eligible purchase in the window -> exactly 0.0, never NaN, never imputed.

The one case §5 does not name, resolved literally rather than by invention: a
zero numerator is 0.0 whatever the denominator, because "no insider bought" is
scale-free. A *positive* numerator with an unavailable market cap is undefined
and carries NaN — never a filled-in value (§2.1).

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

from alpha import carrier, examset, filings, pitdata, protocol  # noqa: E402

WINDOW_DAYS = 90                                    # §4, frozen on economic grounds
SHARES_CONCEPT = "EntityCommonStockSharesOutstanding"
PURCHASES = "alpha/edgar/insider_purchases.parquet"
OUT_PANEL = "alpha/out/insider_panel.pkl"

# §8 of the pre-registration, carried unchanged from Family 1 and fixed BEFORE
# this measurement was taken. Not adjustable here.
CEILING_MOMENTUM = 0.30
CEILING_INPUT = 0.50
LAMBDA = 0.25          # Section 8, carried unchanged from Family 1. Not scanned.


def build_panel(dev: pd.DatetimeIndex, members: pd.DataFrame,
                sym2cik: dict[str, int]) -> pd.DataFrame:
    purchases = pd.read_parquet(PURCHASES)
    book = filings.load_book()
    shares_only = book._facts[book._facts["concept"] == SHARES_CONCEPT].copy()
    # Same door class, same tested acceptance filter, less data through it.
    shares_book = filings.FilingsBook(shares_only)
    prices = pitdata.load_book()

    by_cutoff = {c: g["symbol"].tolist()
                 for c, g in members.groupby("cutoff", sort=True)}

    records: list[dict] = []
    for n, cutoff in enumerate(dev, 1):
        edge = filings.close_of(cutoff)
        floor = pd.Timestamp(cutoff).normalize() - pd.Timedelta(days=WINDOW_DAYS)

        window = purchases[(purchases["accepted"] < edge)
                           & (purchases["trans_date"] >= floor)
                           & (purchases["trans_date"] <= pd.Timestamp(cutoff))]
        value_by_cik = window.groupby("cik")["value"].sum()
        buyers_by_cik = window.groupby("cik")["accn"].nunique()

        known = shares_book.view(cutoff).latest_period(SHARES_CONCEPT)
        shares_by_cik = known.set_index("cik")["value"] if len(known) else pd.Series(dtype=float)
        close = prices.view(cutoff).last_close()

        for symbol in by_cutoff.get(cutoff, ()):
            cik = sym2cik.get(symbol)
            bought = float(value_by_cik.get(cik, 0.0)) if cik is not None else 0.0
            if bought <= 0.0:
                records.append(dict(cutoff=cutoff, symbol=symbol, intensity=0.0,
                                    purchase_value=0.0, filings_in_window=0,
                                    market_cap=np.nan))
                continue
            sh = shares_by_cik.get(cik, np.nan)
            px = close.get(symbol, np.nan)
            cap = float(sh) * float(px) if np.isfinite(sh) and np.isfinite(px) else np.nan
            intensity = bought / cap if np.isfinite(cap) and cap > 0 else np.nan
            records.append(dict(cutoff=cutoff, symbol=symbol, intensity=intensity,
                                purchase_value=bought,
                                filings_in_window=int(buyers_by_cik.get(cik, 0)),
                                market_cap=cap))
        if n % 50 == 0:
            print("  ... %d/%d cutoffs" % (n, len(dev)))

    return (pd.DataFrame(records)
            .set_index(["cutoff", "symbol"])
            .sort_index())


def per_cutoff_spearman(x: pd.Series, y: pd.Series) -> pd.Series:
    out = []
    for _, g in pd.DataFrame({"x": x, "y": y}).groupby(level="cutoff"):
        g = g.dropna()
        if len(g) >= 50 and g["x"].nunique() > 1 and g["y"].nunique() > 1:
            out.append(g["x"].rank().corr(g["y"].rank()))
    return pd.Series(out)


def turnover(prediction: pd.Series, quantile: float = 0.2) -> float:
    """Mean share of the long book replaced between consecutive cutoffs.

    Identical definition to `alpha/v3_family1.py::_turnover`, so the number is
    comparable to Family 1's 0.091 and to B3's. Ranks use the average method,
    which §5 of the pre-registration already fixed as the tie rule.
    """
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
    sym2cik = {s: int(c) for s, c in meta["symbol_to_cik"].items()}

    es = examset.load()
    dev = pd.DatetimeIndex(sorted(es.development))

    panel = pickle.load(open("alpha/out/panel.pkl", "rb"))
    frame = panel["frame"]
    members = frame.index.to_frame(index=False)[["cutoff", "symbol"]]
    members = members[members["cutoff"].isin(dev)]
    print("members rows %d on %d cutoffs" % (len(members), members["cutoff"].nunique()))

    # `cutoffs` is the sealed exam paper; `development` is the 316 we may use.
    exam_overlap = len(set(dev) & set(es.cutoffs))
    print("exam contamination: %d cutoffs (must be 0)" % exam_overlap)
    assert exam_overlap == 0

    print("\nbuilding insider_purchase_intensity ...")
    feat = build_panel(dev, members, sym2cik)
    print("panel rows %d  built in %.1fs" % (len(feat), time.time() - t0))

    with open(OUT_PANEL, "wb") as f:
        pickle.dump({"feature": feat, "window_days": WINDOW_DAYS,
                     "built_at": pd.Timestamp.now().isoformat()}, f)

    x = feat["intensity"]
    nonzero = (x > 0)
    print()
    print("=== coverage (the pre-registered feature, not 'any Form 4') ===")
    print("defined (non-NaN):        %.4f   NaN rows %d"
          % (x.notna().mean(), int(x.isna().sum())))
    share = nonzero.groupby(level="cutoff").mean()
    count = nonzero.groupby(level="cutoff").sum()
    print("non-zero share per cutoff: mean %.4f  median %.4f  p10 %.4f  min %.4f"
          % (share.mean(), share.median(), share.quantile(.1), share.min()))
    print("non-zero NAMES per cutoff: median %d  p10 %d  min %d  max %d"
          % (count.median(), count.quantile(.1), count.min(), count.max()))
    positive = x[nonzero].dropna()
    print("intensity | > 0:          p10 %.3e  median %.3e  p90 %.3e  max %.3e"
          % tuple(positive.quantile([.1, .5, .9, 1.0])))
    print("purchase value | > 0 ($): median %.3e  p90 %.3e"
          % (feat.loc[nonzero, "purchase_value"].median(),
             feat.loc[nonzero, "purchase_value"].quantile(.9)))

    # ------------------------------------------------- data-completeness bounds
    # Both boundaries are properties of which bulk archives the SEC has
    # published, not of the information. Recorded before any study so they
    # cannot later be mistaken for a finding.
    purchases = pd.read_parquet(PURCHASES)
    last_trans = purchases["trans_date"].max()
    truncated = [c for c in dev if pd.Timestamp(c) > last_trans]
    print()
    print("=== data-completeness boundary ===")
    print("last transaction date in the bulk archives: %s" % last_trans.date())
    print("development cutoffs whose 90d window runs past it: %d of %d"
          % (len(truncated), len(dev)))
    if truncated:
        print("  first %s  last %s" % (truncated[0].date(), truncated[-1].date()))

    # ------------------------------------------------------ denominator quality
    # The pre-registered denominator is dei:EntityCommonStockSharesOutstanding.
    # It is a cover-page value and a few filers report a placeholder, which
    # makes the ratio nonsensical for them. Measured, never silently repaired:
    # no winsorisation is pre-registered (Section 2) and none is applied.
    impossible = feat[feat["intensity"] > 1.0]
    print()
    print("=== denominator quality (reported, NOT repaired) ===")
    print("rows implying insiders bought >100%% of the company: %d of %d non-zero"
          % (len(impossible), int(nonzero.sum())))
    if len(impossible):
        print("  affected symbols: %s"
              % ", ".join(sorted(impossible.index.get_level_values("symbol").unique())))
        print("  rows > 0.50: %d   rows > 0.10: %d"
              % (int((x > 0.50).sum()), int((x > 0.10).sum())))

    # ---------------------------------------------------------------- clause 3
    d3 = json.load(open("alpha/out/v2_3_development.json"))
    cols34 = d3["input_columns"]
    assert "z__ret_12_1" not in cols34

    # `z__c = rank_pct(c) - 0.5` within cutoff (alpha/carrier.py). The panel
    # stores the raw columns and the ladder adds the ranks at fit time, so they
    # are constructed here with the same tested function rather than assumed.
    dev_frame = frame.loc[frame.index.get_level_values("cutoff").isin(dev)]
    needed = ["ret_12_1"] + [c[len(carrier.RANK_PREFIX):] for c in cols34
                             if c.startswith(carrier.RANK_PREFIX)]
    missing_raw = [c for c in needed if c not in dev_frame.columns]
    assert not missing_raw, "cannot build the z__ columns: %s" % missing_raw
    dev_frame, _ = carrier.add_rank_columns(dev_frame, tuple(dict.fromkeys(needed)))

    missing = [c for c in cols34 if c not in dev_frame.columns]
    assert not missing, "34-column set incomplete: %s" % missing
    joined = dev_frame[["z__ret_12_1"] + list(cols34)]
    both = joined.join(x, how="inner").dropna(subset=["intensity"])
    print("\njoined rows with the feature: %d" % len(both))

    rho_mom = per_cutoff_spearman(both["intensity"], both["z__ret_12_1"])
    mom_abs = rho_mom.abs().mean()
    print()
    print("=== Section 2.10 clause 3 - correlation ceiling ===")
    print("ceilings fixed in V3_FAMILY2_PREREGISTRATION.md Section 8, before this run:")
    print("  vs z__ret_12_1        <= %.2f" % CEILING_MOMENTUM)
    print("  vs each 34-set column <= %.2f" % CEILING_INPUT)
    print()
    print("intensity vs z__ret_12_1: mean %+.4f  mean|rho| %.4f  p95|rho| %.4f  n %d  -> %s"
          % (rho_mom.mean(), mom_abs, rho_mom.abs().quantile(.95), len(rho_mom),
             "PASS" if mom_abs <= CEILING_MOMENTUM else "FAIL"))

    worst = []
    for c in [c for c in cols34 if c in both.columns]:
        r = per_cutoff_spearman(both["intensity"], both[c])
        worst.append((r.abs().mean(), r.mean(), c))
    worst.sort(reverse=True)
    breaches = [w for w in worst if w[0] > CEILING_INPUT]
    print("\ntop |rho| against the 34-column set:")
    for a, m, c in worst[:8]:
        print("  %-40s mean|rho| %.4f  mean %+.4f" % (c, a, m))
    print("\nhighest of all %d columns: %.4f (%s) -> %s"
          % (len(worst), worst[0][0], worst[0][2],
             "PASS" if not breaches else "FAIL (%d breach)" % len(breaches)))

    # ---------------------------------------------------------------- turnover
    # No winsorisation: Section 2 of the pre-registration fixes none, and a rank
    # is invariant to it in any case.
    rank = x.groupby(level="cutoff").rank(pct=True, na_option="keep")
    turn_feature = turnover(rank)

    # Arm 1 exactly as Section 8 declares it. Turnover reads no forward return
    # and no target, so this is still feature-side work.
    benchmarks = protocol.benchmark_scores(dev_frame, panel["regimes"])
    b3_rank = benchmarks["b3_regime_switched"].groupby(
        level=0).rank(pct=True, na_option="keep")
    arm1 = b3_rank + LAMBDA * (rank.reindex(b3_rank.index) - 0.5)
    turn_b3, turn_arm1 = turnover(b3_rank), turnover(arm1)
    extra = turn_arm1 - turn_b3

    print()
    print("=== turnover (the MDE input FAMILY2_ELIGIBILITY.md Section 5.3 could not fill) ===")
    print("Arm 0  feature-only book        %.4f   (Family 1 SUE was 0.091)" % turn_feature)
    print("B3     incumbent book           %.4f" % turn_b3)
    print("Arm 1  B3 + %.2f tilt           %.4f" % (LAMBDA, turn_arm1))
    print("EXTRA turnover, Arm 1 - B3      %+.4f  (%.1f pp)" % (extra, extra * 100))
    print("MDE holds while extra turnover <= 30 pp  ->  %s"
          % ("PASS, +0.007 MDE stands" if extra <= 0.30 else "FAIL, MDE must be raised"))

    print("\ntotal %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
