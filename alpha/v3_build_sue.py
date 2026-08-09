"""Build the Family 1 SUE panel on the 316 development cutoffs, then run the
Section 2.10 clause-3 correlation ceiling: SUE vs z__ret_12_1 and vs the
34-column V2 input set. FEATURE-vs-FEATURE only - the target is never read.
ASCII stdout only."""
import json
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, r"c:/Users/onurc/Desktop/AI Stock/Stock-Prediction-Models")

from alpha import examset, filings, filings_features as ff  # noqa: E402

t0 = time.time()
book = filings.load_book()
meta = json.load(open("alpha/edgar/filings_meta.json"))
sym2cik = {s: int(c) for s, c in meta["symbol_to_cik"].items()}

es = examset.load()
dev = pd.DatetimeIndex(sorted(es.development))

panel = pickle.load(open("alpha/out/panel.pkl", "rb"))
frame = panel["frame"]
members = frame.index.to_frame(index=False)[["cutoff", "symbol"]]
members = members[members["cutoff"].isin(dev)]
print("members rows %d on %d cutoffs" % (len(members), members["cutoff"].nunique()))

sue = ff.build_feature(book._facts, "NetIncomeLoss", dev, members, sym2cik)
print("sue panel rows %d  built in %.1fs" % (len(sue), time.time() - t0))

with open("alpha/out/sue_panel.pkl", "wb") as f:
    pickle.dump({"feature": sue, "concept": "NetIncomeLoss",
                 "built_at": pd.Timestamp.now().isoformat()}, f)

# coverage
cov = sue["sue"].notna().groupby(level="cutoff").mean()
n = sue["sue"].notna().groupby(level="cutoff").sum()
print()
print("SUE coverage per cutoff: median %.3f  p10 %.3f  min %.3f (%s)"
      % (cov.median(), cov.quantile(.1), cov.min(), cov.idxmin().date()))
print("SUE names per cutoff:    median %d  p10 %d  min %d"
      % (n.median(), n.quantile(.1), n.min()))
stale = sue["staleness_days"].dropna()
print("staleness days:          p10 %d  median %d  p90 %d"
      % (stale.quantile(.1), stale.median(), stale.quantile(.9)))
print("SUE distribution:        p1 %.2f  p25 %.2f  median %.2f  p75 %.2f  p99 %.2f"
      % tuple(sue["sue"].dropna().quantile([.01, .25, .5, .75, .99])))

# ---------------------------------------------------------------------------
# Section 2.10 clause 3 - the correlation ceiling. Features only.
# ---------------------------------------------------------------------------
d3 = json.load(open("alpha/out/v2_3_development.json"))
cols34 = d3["input_columns"]
assert "z__ret_12_1" not in cols34

joined = frame.loc[frame.index.get_level_values("cutoff").isin(dev),
                   ["z__ret_12_1"] + [c for c in cols34 if c in frame.columns]]
missing = [c for c in cols34 if c not in frame.columns]
if missing:
    print("NOTE: %d of the 34 columns not in panel frame: %s" % (len(missing), missing[:5]))
both = joined.join(sue["sue"], how="inner").dropna(subset=["sue"])
print()
print("joined rows with SUE: %d" % len(both))


def per_cutoff_spearman(x, y):
    out = []
    for _, g in pd.DataFrame({"x": x, "y": y}).groupby(level="cutoff"):
        g = g.dropna()
        if len(g) >= 50:
            out.append(g["x"].rank().corr(g["y"].rank()))
    return pd.Series(out)


rho_mom = per_cutoff_spearman(both["sue"], both["z__ret_12_1"])
print()
print("=== correlation ceiling ===")
print("SUE vs z__ret_12_1 per-cutoff Spearman: mean %+.4f  mean|rho| %.4f  p95|rho| %.4f"
      % (rho_mom.mean(), rho_mom.abs().mean(), rho_mom.abs().quantile(.95)))

worst = []
for c in [c for c in cols34 if c in both.columns]:
    r = per_cutoff_spearman(both["sue"], both[c])
    worst.append((r.abs().mean(), r.mean(), c))
worst.sort(reverse=True)
print()
print("top |rho| against the 34-column set:")
for a, m, c in worst[:8]:
    print("  %-36s mean|rho| %.4f  mean %+.4f" % (c, a, m))
print()
print("total %.1fs" % (time.time() - t0))
