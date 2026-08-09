"""Fetch the SEC Form 13F structured data sets covering the study era.

The SEC changed the file naming in 2024: quarterly `2015q2_form13f.zip` up to
`2023q4`, then overlapping three-month windows named by date range. Both forms
are listed on the data-sets page and both are fetched here; the archive name is
never parsed for meaning, because what dates a file covers is a property of the
filings inside it, not of its name.

Free bulk data (roadmap §27B). ASCII stdout only.
"""

from __future__ import annotations

import pathlib
import re
import sys
import time
import urllib.request

BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
INDEX = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
UA = {"User-Agent": "research contact onur.celk@gmail.com"}
OUT = pathlib.Path(__file__).resolve().parent / "edgar" / "f13"

#: Earliest archive needed. The first development cutoff is 2016-01-04, whose
#: newest deadline-passed quarter is 2015-09-30 and whose prior quarter is
#: 2015-06-30 - filed during 2015q3. 2015q2 is taken for margin.
FIRST_QUARTER = "2015q2"


def listing() -> list[str]:
    request = urllib.request.Request(INDEX, headers=UA)
    with urllib.request.urlopen(request, timeout=90) as response:
        html = response.read().decode("utf-8", "replace")
    names = sorted({m.rsplit("/", 1)[1] for m in
                    re.findall(r'href="([^"]*form13f[^"]*\.zip)"', html, re.I)})
    keep = []
    for name in names:
        quarter = re.match(r"^(\d{4})q(\d)_", name)
        if quarter:
            if name[:6] >= FIRST_QUARTER:
                keep.append(name)
        else:
            keep.append(name)          # the 2024+ date-range archives
    return keep


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names = listing()
    print("%d archives to consider" % len(names))
    fetched = skipped = 0
    total = 0
    for name in names:
        target = OUT / name
        if target.exists() and target.stat().st_size > 0:
            skipped += 1
            total += target.stat().st_size
            continue
        for attempt in range(3):
            try:
                request = urllib.request.Request(BASE + name, headers=UA)
                with urllib.request.urlopen(request, timeout=600) as response:
                    payload = response.read()
                target.write_bytes(payload)
                total += len(payload)
                fetched += 1
                print("  %-40s %6.1f MB" % (name, len(payload) / 1e6))
                break
            except Exception as exc:
                if attempt == 2:
                    print("  %-40s FAILED %s" % (name, exc))
                else:
                    time.sleep(2 + 3 * attempt)
        time.sleep(0.15)               # be polite to sec.gov
    print("\nfetched %d, already present %d, total %.1f GB"
          % (fetched, skipped, total / 1e9))
    return 0


if __name__ == "__main__":
    sys.exit(main())
