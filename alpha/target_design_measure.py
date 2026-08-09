"""Phase 3 target design: empirical class balance and power arithmetic.

Measures ONLY raw outcome distributions (up-rates, move-size frequencies) on
the 316 DEVELOPMENT cutoffs. The 72 sealed exam cutoffs are excluded by
construction (examset.load().development). No feature is read, no model is
fitted, no prediction is scored. ASCII stdout only.
"""
import collections
import glob
import os

import numpy as np
import pandas as pd

from alpha import examset

H = {"5D": 5, "10D": 10, "20D": 20}
BAND = 0.05  # target C: +/-5 percent economic move


def load_closes():
    frames = {}
    for path in glob.glob(os.path.join("alpha", "cache", "*.csv")):
        sym = os.path.basename(path)[:-4]
        if sym.startswith("_"):
            continue
        s = pd.read_csv(path, usecols=["date", "close"], parse_dates=["date"])
        frames[sym] = s.set_index("date")["close"]
    return pd.DataFrame(frames).sort_index()


def main():
    es = examset.load()
    dev = pd.DatetimeIndex(es.development)
    close = load_closes()
    spy = close["SPY"]
    print("symbols %d  sessions %d  dev cutoffs %d" % (close.shape[1], close.shape[0], len(dev)))

    # positions of each dev cutoff in the session index
    idx = close.index
    pos = idx.get_indexer(dev)
    ok = pos >= 0
    print("dev cutoffs found in session index: %d of %d" % (ok.sum(), len(dev)))
    pos = pos[ok]
    dev = dev[ok]

    for name, h in H.items():
        usable = pos[pos + h < len(idx)]
        cuts = idx[usable]
        fwd = close.values[usable + h] / close.values[usable] - 1.0
        fwd = pd.DataFrame(fwd, index=cuts, columns=close.columns)
        spy_fwd = spy.values[usable + h] / spy.values[usable] - 1.0

        # non-overlapping subset: every (h/5)-th cutoff
        step = max(1, h // 5)
        nono = fwd.iloc[::step]
        n_no = len(nono)

        flat = fwd.stack()
        up = (flat > 0).mean()
        # per-cutoff up-rate spread (the thing that breaks "always-up" baselines)
        cu = (fwd > 0).mean(axis=1)
        alpha = fwd.sub(pd.Series(spy_fwd, index=cuts), axis=0)
        aflat = alpha.stack()

        big_up = (flat >= BAND).mean()
        big_dn = (flat <= -BAND).mean()
        hold = 1.0 - big_up - big_dn

        # target D: move vs own trailing 60-session daily vol scaled to horizon
        ret1 = close.pct_change()
        vol = ret1.rolling(60).std()
        volh = vol.values[usable] * np.sqrt(h)
        volh = pd.DataFrame(volh, index=cuts, columns=close.columns)
        z = fwd / volh
        zflat = z.stack().replace([np.inf, -np.inf], np.nan).dropna()
        d_up = (zflat >= 1.0).mean()
        d_dn = (zflat <= -1.0).mean()

        print()
        print("=== horizon %s (h=%d sessions) ===" % (name, h))
        print("cutoffs with outcome        %4d   non-overlapping %4d" % (len(cuts), n_no))
        print("median cross-section        %4d" % int(fwd.notna().sum(axis=1).median()))
        print("B  up-rate pooled           %.4f" % up)
        print("B  per-cutoff up-rate       p10 %.3f  median %.3f  p90 %.3f"
              % (cu.quantile(.1), cu.median(), cu.quantile(.9)))
        print("B  alpha>0 rate (vs SPY)    %.4f" % (aflat > 0).mean())
        print("C  |move|>=5pct  BUY %.4f  SELL %.4f  HOLD %.4f" % (big_up, big_dn, hold))
        print("C  per-cutoff BUY share     p10 %.3f  median %.3f  p90 %.3f"
              % ((fwd >= BAND).mean(axis=1).quantile(.1),
                 (fwd >= BAND).mean(axis=1).median(),
                 (fwd >= BAND).mean(axis=1).quantile(.9)))
        print("D  z>=+1: %.4f   z<=-1: %.4f   |z|<1: %.4f" % (d_up, d_dn, 1 - d_up - d_dn))

        # power arithmetic: scale the record's measured half-width by cutoff count
        base_hw, base_n = 0.00827, 255
        for label, n in (("all usable", len(cuts)), ("non-overlapping", n_no)):
            hw = base_hw * np.sqrt(base_n / max(n, 1))
            print("power  %-16s n=%4d  ->  achievable half-width ~%.5f IC" % (label, n, hw))


if __name__ == "__main__":
    main()
