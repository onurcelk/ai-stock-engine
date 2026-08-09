"""Section 2.10 clause-3 correlation ceiling for Family 1's SUE feature.

FEATURE-vs-FEATURE only. The target is never read in this script.

Spearman is invariant to the monotone `z__` (within-cutoff percentile)
transform, so rho(SUE, z__X) == rho(SUE, X) within a cutoff; the base columns
are used directly. Of the 34 V2 input columns only NINE are stock-level - the
other 25 are cutoff-constant context, which have no within-cutoff variance and
therefore cannot correlate with anything cross-sectionally. That is reported
rather than hidden.
"""
import json
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, r"c:/Users/onurc/Desktop/AI Stock/Stock-Prediction-Models")

from alpha import carrier  # noqa: E402

sue = pickle.load(open("alpha/out/sue_panel.pkl", "rb"))["feature"]
panel = pickle.load(open("alpha/out/panel.pkl", "rb"))
frame = panel["frame"]
d3 = json.load(open("alpha/out/v2_3_development.json"))
cols34 = d3["input_columns"]

z_cols = [c for c in cols34 if c.startswith("z__")]
base_of_z = [c[len("z__"):] for c in z_cols]
context = [c for c in cols34 if not c.startswith("z__")]
print("34 input columns = %d stock-level (z__) + %d cutoff-constant context"
      % (len(z_cols), len(context)))

# confirm the context columns really are cutoff-constant on this panel
dev_idx = frame.index.get_level_values("cutoff").isin(sue.index.get_level_values("cutoff").unique())
sub = frame.loc[dev_idx]
present_ctx = [c for c in context if c in sub.columns]
nun = sub[present_ctx].groupby(level=0).nunique().max()
print("context columns present %d; max distinct values within a cutoff = %d"
      % (len(present_ctx), int(nun.max())))

targets = ["ret_12_1"] + base_of_z
missing = [c for c in targets if c not in sub.columns]
assert not missing, missing

both = sub[targets].join(sue["sue"], how="inner")
both = both[both["sue"].notna()]
print("rows with a defined SUE: %d over %d cutoffs"
      % (len(both), both.index.get_level_values("cutoff").nunique()))


def per_cutoff_rho(frame_, a, b, min_n=50):
    out = {}
    for cut, g in frame_.groupby(level="cutoff"):
        g = g[[a, b]].dropna()
        if len(g) >= min_n:
            out[cut] = g[a].rank().corr(g[b].rank())
    return pd.Series(out)


print()
print("=== SECTION 2.10 CLAUSE 3 - CORRELATION CEILING ===")
print("thresholds fixed in alpha/V3_PREREGISTRATION.md 2.1 BEFORE this ran:")
print("  vs z__ret_12_1 : mean|rho| <= 0.30")
print("  vs each of the stock-level inputs : mean|rho| <= 0.50")
print()

rho = per_cutoff_rho(both, "sue", "ret_12_1")
mom_mean_abs = rho.abs().mean()
print("%-24s n=%3d  mean rho %+.4f  mean|rho| %.4f  p95|rho| %.4f  max|rho| %.4f"
      % ("sue vs ret_12_1", len(rho), rho.mean(), mom_mean_abs,
         rho.abs().quantile(.95), rho.abs().max()))
print("   -> ceiling 0.30: %s" % ("PASS" if mom_mean_abs <= 0.30 else "BREACH"))
print()

rows = []
for c in base_of_z:
    r = per_cutoff_rho(both, "sue", c)
    rows.append((r.abs().mean(), r.mean(), r.abs().quantile(.95), c))
rows.sort(reverse=True)
print("against the eight stock-level inputs (as z__<name>):")
worst = 0.0
for a, m, p95, c in rows:
    worst = max(worst, a)
    print("  z__%-24s mean|rho| %.4f  mean %+.4f  p95|rho| %.4f" % (c, a, m, p95))
print("   -> ceiling 0.50, worst %.4f: %s" % (worst, "PASS" if worst <= 0.50 else "BREACH"))

print()
verdict = (mom_mean_abs <= 0.30) and (worst <= 0.50)
print("CLAUSE 3 VERDICT: %s" % ("PASS - Family 1 is admissible"
                                if verdict else "BREACH - Family 1 inadmissible, study does not run"))

json.dump({
    "sue_vs_ret_12_1": {"n_cutoffs": int(len(rho)), "mean_rho": float(rho.mean()),
                        "mean_abs_rho": float(mom_mean_abs),
                        "p95_abs_rho": float(rho.abs().quantile(.95)),
                        "max_abs_rho": float(rho.abs().max()),
                        "threshold": 0.30, "passed": bool(mom_mean_abs <= 0.30)},
    "vs_stock_level_inputs": [
        {"column": "z__" + c, "mean_abs_rho": float(a), "mean_rho": float(m),
         "p95_abs_rho": float(p)} for a, m, p, c in rows],
    "stock_level_ceiling": {"threshold": 0.50, "worst": float(worst),
                            "passed": bool(worst <= 0.50)},
    "context_columns_cutoff_constant": int(nun.max()) == 1,
    "n_context_columns": len(present_ctx),
    "clause_3_passed": bool(verdict),
}, open("alpha/out/v3_family1_ceiling.json", "w"), indent=2)
print("wrote alpha/out/v3_family1_ceiling.json")
