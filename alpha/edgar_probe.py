"""Phase 2 information audit: verify EDGAR timestamp semantics.

Answers, with data rather than assumption:
  1. What fraction of 10-K/10-Q filings are ACCEPTED after the 16:00 ET close on
     the date they are stamped with?  If it is material, `filed <= cutoff` leaks.
  2. How long is the gap between period end and filing acceptance (reporting lag)?
  3. How far back does XBRL coverage actually go?
ASCII output only (console is cp1252).
"""
import collections
import datetime as dt
import json
import os
import random
import sys
import time
import urllib.request

UA = {"User-Agent": "research contact onur.celk@gmail.com"}
OUT = os.path.dirname(os.path.abspath(__file__))


def get(url, tries=3):
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                return json.loads(r.read())
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(1.5 * (a + 1))


def et_from_utc(ts):
    """SEC acceptanceDateTime is stamped ...Z but is in fact US/Eastern-derived.

    The published field is UTC. Convert to ET using the US DST rule so the
    comparison against a 16:00 ET close is honest.
    """
    d = dt.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
    y = d.year
    # 2nd Sunday March .. 1st Sunday November
    mar = dt.datetime(y, 3, 8)
    dst_start = mar + dt.timedelta(days=(6 - mar.weekday()) % 7)
    nov = dt.datetime(y, 11, 1)
    dst_end = nov + dt.timedelta(days=(6 - nov.weekday()) % 7)
    offset = 4 if dst_start <= d < dst_end else 5
    return d - dt.timedelta(hours=offset)


def main():
    n_filers = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    syms = sorted(x.rsplit(".", 1)[0] for x in os.listdir("alpha/cache") if x.endswith(".csv"))
    tick = get("https://www.sec.gov/files/company_tickers.json")
    m = {v["ticker"]: v["cik_str"] for v in tick.values()}
    pool = [s for s in syms if s in m]
    random.seed(0)
    sample = random.sample(pool, min(n_filers, len(pool)))

    rows = []
    earliest_xbrl = {}
    for i, s in enumerate(sample):
        cik = m[s]
        try:
            d = get("https://data.sec.gov/submissions/CIK%010d.json" % cik)
        except Exception as e:
            print("  skip %-6s %s" % (s, type(e).__name__))
            continue
        r = d["filings"]["recent"]
        for j in range(len(r["form"])):
            if r["form"][j] not in ("10-K", "10-Q"):
                continue
            acc = r["acceptanceDateTime"][j]
            if not acc:
                continue
            et = et_from_utc(acc)
            fd = dt.datetime.strptime(r["filingDate"][j], "%Y-%m-%d")
            rd = r["reportDate"][j]
            lag = None
            if rd:
                lag = (fd - dt.datetime.strptime(rd, "%Y-%m-%d")).days
            rows.append({
                "sym": s, "form": r["form"][j], "filingDate": r["filingDate"][j],
                "accept_et": et.strftime("%Y-%m-%d %H:%M"),
                "after_close": et.hour >= 16,
                "same_day": et.date() == fd.date(),
                "lag_days": lag, "isXBRL": r["isXBRL"][j],
            })
            if r["isXBRL"][j] and (s not in earliest_xbrl or r["filingDate"][j] < earliest_xbrl[s]):
                earliest_xbrl[s] = r["filingDate"][j]
        time.sleep(0.12)
        if (i + 1) % 10 == 0:
            print("  ... %d/%d filers, %d filings" % (i + 1, len(sample), len(rows)))

    with open(os.path.join(OUT, "edgar_acceptance.json"), "w") as f:
        json.dump({"rows": rows, "earliest_xbrl": earliest_xbrl}, f)

    n = len(rows)
    after = sum(1 for x in rows if x["after_close"])
    notsame = sum(1 for x in rows if not x["same_day"])
    print()
    print("=== ACCEPTANCE TIME vs the 16:00 ET close ===")
    print("filers sampled      %d" % len(sample))
    print("10-K/10-Q filings   %d" % n)
    print("accepted AFTER 16:00 ET on their filingDate:  %d  (%.1f%%)" % (after, 100.0 * after / max(n, 1)))
    print("acceptance date != filingDate:                %d  (%.1f%%)" % (notsame, 100.0 * notsame / max(n, 1)))

    hrs = collections.Counter(int(x["accept_et"][11:13]) for x in rows)
    print()
    print("hour of acceptance (ET)")
    for h in sorted(hrs):
        bar = "#" * min(60, hrs[h] * 60 // max(hrs.values()))
        flag = "  <-- AFTER CLOSE" if h >= 16 else ""
        print("  %02d:00  %5d  %s%s" % (h, hrs[h], bar, flag))

    lags = sorted(x["lag_days"] for x in rows if x["lag_days"] is not None)
    if lags:
        def pct(p):
            return lags[min(len(lags) - 1, int(p / 100.0 * len(lags)))]
        print()
        print("=== REPORTING LAG: period end -> filing date (days) ===")
        print("  n %d  min %d  p10 %d  median %d  p90 %d  p99 %d  max %d"
              % (len(lags), lags[0], pct(10), pct(50), pct(90), pct(99), lags[-1]))
        for form in ("10-K", "10-Q"):
            fl = sorted(x["lag_days"] for x in rows if x["form"] == form and x["lag_days"] is not None)
            if fl:
                print("  %-5s n %4d  median %3d  p90 %3d  max %3d"
                      % (form, len(fl), fl[len(fl) // 2], fl[int(0.9 * len(fl))], fl[-1]))

    if earliest_xbrl:
        e = sorted(earliest_xbrl.values())
        print()
        print("=== EARLIEST XBRL FILING IN THE 'recent' WINDOW (not full history) ===")
        print("  filers with XBRL %d   earliest %s   median %s   latest %s"
              % (len(e), e[0], e[len(e) // 2], e[-1]))


if __name__ == "__main__":
    main()
