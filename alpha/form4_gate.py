"""Family 2 (Form 4 insiders) §2.6 power gate. Gate-only — builds no feature.

Three subcommands, matching the three inputs `reports/FAMILY2_POWER_GATE.md`
records:

    coverage    Form 4 availability per development cutoff, read from the
                filing INDEX only (form type + acceptanceDateTime). No Form 4
                XML is fetched or parsed; no transaction direction, size,
                price or owner is read. This is the "universe" input of §2.6
                step 2.

    halfwidth   the half-width the design achieves, measured with
                coverage-matched UNINFORMATIVE features — uniform random draws
                on exactly the names a real feature would cover. §2.6 step 2
                asks for the resolution of the design, and for a rank-based
                bounded arm that is set by lambda and coverage, not by whether
                the feature predicts anything. Includes the validation against
                Family 1's measured 0.00229.

    ceiling     the attainable-effect ceiling: an ORACLE tilt (perfect
                foresight) through the same arm. §2.12 warns that a free power
                gain means the arm is doing nothing; this measures the other
                end of that dial. No real feature can beat perfect foresight,
                so an oracle advantage below the MDE would fail the gate on
                structure rather than on resolution.

Nothing here reads Form 4 content, spends a budget slot, or implements
Family 2. The existing machinery is reused, not rewritten: `alpha/stats.py`
`block_bootstrap_ci` at BLOCK_LENGTH = 4, and `paired_difference`.

ASCII stdout only — the console is cp1252.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
import zipfile

import numpy as np
import pandas as pd

from . import examset, filings, protocol, stats, v3_family1

EDGAR_DIR = "alpha/edgar"
OUT_DIR = "alpha/out"

WINDOWS = (30, 90, 180, 365)     # calendar-day lookbacks, reported not chosen
LAMBDA = 0.25                    # Family 1's pre-registered arm form
LAMBDAS = (0.10, 0.25, 0.50, 1.00, 2.00)
DRAWS = 24                       # uninformative features per coverage level
SEED = 20260809

#: Family 1's measured half-width for the identical arm at coverage 0.930.
#: The estimator in `halfwidth` is calibrated against it.
FAMILY1_MEASURED = 0.00229
FAMILY1_COVERAGE = 0.930


def _development_frame():
    panel = pickle.load(open(f"{OUT_DIR}/panel.pkl", "rb"))
    dev = pd.DatetimeIndex(sorted(examset.load().development))
    frame = panel["frame"]
    frame = frame.loc[frame.index.get_level_values("cutoff").isin(dev)]
    return frame, panel["regimes"], dev


def _base(frame, regimes):
    """B3, rank-transformed — the base every contrast is paired against."""
    benchmarks = protocol.benchmark_scores(frame, regimes)
    b3 = benchmarks["b3_regime_switched"].groupby(
        level=0).rank(pct=True, na_option="keep")
    return b3, v3_family1._ic_series(b3, frame[v3_family1.TARGET])


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------

def coverage() -> dict:
    started = time.time()
    meta = json.load(open(f"{EDGAR_DIR}/filings_meta.json"))
    symbol_to_cik = {s: int(c) for s, c in meta["symbol_to_cik"].items()}
    ciks = sorted(set(symbol_to_cik.values()))

    archive = zipfile.ZipFile(f"{EDGAR_DIR}/submissions.zip")
    accepted_by_cik: dict[int, np.ndarray] = {}
    for count, cik in enumerate(ciks, 1):
        try:
            head = json.loads(archive.read("CIK%010d.json" % cik))
        except KeyError:
            continue
        shards = [head["filings"]["recent"]]
        for extra in head["filings"].get("files", ()):
            try:
                shards.append(json.loads(archive.read(extra["name"])))
            except KeyError:
                continue
        stamps = []
        for shard in shards:
            forms, accepted = shard["form"], shard["acceptanceDateTime"]
            for j in range(len(forms)):
                if forms[j] == "4" and accepted[j]:
                    stamps.append(filings.et_from_utc(accepted[j]))
        if stamps:
            accepted_by_cik[cik] = np.array(sorted(stamps), dtype="datetime64[ns]")
        if count % 150 == 0:
            print("  ... %d/%d issuers" % (count, len(ciks)))

    every = np.concatenate(list(accepted_by_cik.values()))
    after_close = float(np.mean([pd.Timestamp(s).hour >= 16 for s in every]))
    print()
    print("issuers with any Form 4  %d of %d" % (len(accepted_by_cik), len(ciks)))
    print("Form 4 filings indexed   %d" % len(every))
    print("first / last accepted    %s / %s"
          % (pd.Timestamp(every.min()).date(), pd.Timestamp(every.max()).date()))
    print("accepted after 16:00 ET  %.3f" % after_close)

    frame, _, dev = _development_frame()
    members = frame.index.to_frame(index=False)[["cutoff", "symbol"]]
    by_cutoff = {c: g["symbol"].tolist() for c, g in members.groupby("cutoff")}

    print()
    print("=== Form 4 availability per development cutoff (%d cutoffs) ===" % len(dev))
    print("%-8s %10s %10s %10s %10s" % ("window", "median", "p10", "min", "mean names"))
    out: dict[int, pd.Series] = {}
    for window in WINDOWS:
        shares, counts = [], []
        for cutoff in dev:
            edge = np.datetime64(filings.close_of(cutoff))
            low = np.datetime64(pd.Timestamp(cutoff) - pd.Timedelta(days=window))
            names = by_cutoff.get(cutoff, [])
            have = 0
            for symbol in names:
                stamps = accepted_by_cik.get(symbol_to_cik.get(symbol))
                if stamps is None:
                    continue
                if np.searchsorted(stamps, edge, "left") > np.searchsorted(
                        stamps, low, "left"):
                    have += 1
            shares.append(have / max(len(names), 1))
            counts.append(have)
        series = pd.Series(shares, index=dev)
        out[window] = series
        print("%-8s %10.3f %10.3f %10.3f %10.1f"
              % ("%dd" % window, series.median(), series.quantile(.1),
                 series.min(), float(np.mean(counts))))

    payload = {"coverage": out, "windows": WINDOWS,
               "issuers_with_form4": len(accepted_by_cik),
               "form4_filings": int(len(every)),
               "accepted_after_close": after_close}
    pickle.dump(payload, open(f"{OUT_DIR}/form4_coverage.pkl", "wb"))
    print("\nwrote form4_coverage.pkl   %.1fs" % (time.time() - started))
    return payload


# ---------------------------------------------------------------------------
# halfwidth
# ---------------------------------------------------------------------------

def _half_width_at(frame, b3, base_ic, target, coverage_spec, label, rng,
                   draws=DRAWS) -> float:
    cutoffs = frame.index.get_level_values("cutoff")
    widths, effects = [], []
    for _ in range(draws):
        values = pd.Series(rng.random(len(frame)), index=frame.index)
        keep = pd.Series(rng.random(len(frame)), index=frame.index)
        if isinstance(coverage_spec, pd.Series):
            threshold = pd.Series(coverage_spec.reindex(cutoffs).to_numpy(),
                                  index=frame.index)
        else:
            threshold = pd.Series(float(coverage_spec), index=frame.index)
        ranked = values.where(keep < threshold).groupby(
            level=0).rank(pct=True, na_option="keep")
        arm = b3 + LAMBDA * (ranked - 0.5)
        difference = stats.paired_difference(
            v3_family1._ic_series(arm, target), base_ic, "x").values.dropna()
        lo, hi = stats.block_bootstrap_ci(difference.to_numpy(dtype=float))
        widths.append((hi - lo) / 2.0)
        effects.append(difference.mean())
    widths = np.array(widths)
    print("%-34s half-width %.5f  (sd %.5f)   mean effect %+.5f"
          % (label, widths.mean(), widths.std(ddof=1), float(np.mean(effects))))
    return float(widths.mean())


def halfwidth() -> dict:
    frame, regimes, _ = _development_frame()
    target = frame[v3_family1.TARGET]
    b3, base_ic = _base(frame, regimes)
    print("base: B3 rank, %d cutoffs, mean IC %+.5f" % (len(base_ic), base_ic.mean()))

    per_window = pickle.load(open(f"{OUT_DIR}/form4_coverage.pkl", "rb"))["coverage"]
    rng = np.random.default_rng(SEED)

    print()
    print("=== VALIDATION against Family 1's measured resolution ===")
    print("Family 1 measured %.5f at coverage %.3f, lambda %.2f"
          % (FAMILY1_MEASURED, FAMILY1_COVERAGE, LAMBDA))
    validation = _half_width_at(frame, b3, base_ic, target, FAMILY1_COVERAGE,
                                "uninformative @ coverage %.3f" % FAMILY1_COVERAGE, rng)
    calibration = FAMILY1_MEASURED / validation
    print("estimator runs %.2fx of measured -> calibration factor %.2fx"
          % (validation / FAMILY1_MEASURED, calibration))

    print()
    print("=== §2.6 STEP 2: achievable half-width for Family 2's universe ===")
    results = {}
    for window in WINDOWS:
        raw = _half_width_at(frame, b3, base_ic, target, per_window[window],
                             "Form 4 availability, %dd" % window, rng)
        results[window] = {"raw": raw, "calibrated": raw * calibration}
    results["full"] = {}
    raw = _half_width_at(frame, b3, base_ic, target, 1.0,
                         "uninformative @ coverage 1.000", rng)
    results["full"] = {"raw": raw, "calibrated": raw * calibration}

    print()
    print("%-24s %12s %12s" % ("universe", "raw", "calibrated"))
    for key, value in results.items():
        print("%-24s %12.5f %12.5f" % (key, value["raw"], value["calibrated"]))

    payload = {"validation": validation, "calibration": calibration,
               "results": results, "lambda": LAMBDA, "draws": DRAWS, "seed": SEED}
    pickle.dump(payload, open(f"{OUT_DIR}/form4_gate_halfwidths.pkl", "wb"))
    print("\nwrote form4_gate_halfwidths.pkl")
    return payload


# ---------------------------------------------------------------------------
# ceiling
# ---------------------------------------------------------------------------

def ceiling() -> dict:
    frame, regimes, _ = _development_frame()
    target = frame[v3_family1.TARGET]
    b3, base_ic = _base(frame, regimes)

    per_window = pickle.load(open(f"{OUT_DIR}/form4_coverage.pkl", "rb"))["coverage"]
    cutoffs = frame.index.get_level_values("cutoff")
    rng = np.random.default_rng(SEED)
    keep = pd.Series(rng.random(len(frame)), index=frame.index)
    threshold = pd.Series(per_window[90].reindex(cutoffs).to_numpy(), index=frame.index)
    mask = keep < threshold
    print("Form 4 90d availability mask: %.3f of rows retained" % mask.mean())

    oracle = target.where(mask).groupby(level=0).rank(pct=True, na_option="keep")

    print()
    print("=== ATTAINABLE-EFFECT CEILING: oracle tilt (perfect foresight) ===")
    print("%8s %12s %12s %12s" % ("lambda", "arm IC", "vs B3", "half-width"))
    out = {}
    for lam in LAMBDAS:
        ic = v3_family1._ic_series(b3 + lam * (oracle - 0.5), target)
        difference = stats.paired_difference(ic, base_ic, "x").values.dropna()
        lo, hi = stats.block_bootstrap_ci(difference.to_numpy(dtype=float))
        out[lam] = {"arm_ic": float(ic.mean()), "vs_b3": float(difference.mean()),
                    "half_width": (hi - lo) / 2.0}
        print("%8.2f %+12.5f %+12.5f %12.5f"
              % (lam, ic.mean(), difference.mean(), (hi - lo) / 2.0))

    print()
    print("pre-registered MDE (economic floor) +0.00700")
    print("=== required signal strength, as a share of perfect foresight ===")
    for lam in LAMBDAS:
        attainable = out[lam]["vs_b3"]
        print("  lambda %.2f: oracle %+.5f -> a real feature must be %.1f%% as good "
              "as perfect foresight" % (lam, attainable, 100 * 0.007 / attainable))

    payload = {"ceiling": out, "coverage_used": float(mask.mean()),
               "lambdas": LAMBDAS, "seed": SEED}
    pickle.dump(payload, open(f"{OUT_DIR}/form4_gate_ceiling.pkl", "wb"))
    print("\nwrote form4_gate_ceiling.pkl")
    return payload


# ---------------------------------------------------------------------------
# pit — timestamp semantics and independence from Family 1
# ---------------------------------------------------------------------------

def pit() -> dict:
    """Form 4 timestamp semantics (§2.1) and independence from Family 1 (§2.10/§21).

    Index-only, like `coverage`: form type, `reportDate` (the period of report,
    i.e. the transaction date for a Form 4), `filingDate`, `acceptanceDateTime`.
    No Form 4 XML, no transaction code, direction, size, price or owner.
    """
    started = time.time()
    meta = json.load(open(f"{EDGAR_DIR}/filings_meta.json"))
    ciks = sorted({int(c) for c in meta["symbol_to_cik"].values()})
    archive = zipfile.ZipFile(f"{EDGAR_DIR}/submissions.zip")

    records, periodic = [], {}
    for count, cik in enumerate(ciks, 1):
        try:
            head = json.loads(archive.read("CIK%010d.json" % cik))
        except KeyError:
            continue
        shards = [head["filings"]["recent"]]
        for extra in head["filings"].get("files", ()):
            try:
                shards.append(json.loads(archive.read(extra["name"])))
            except KeyError:
                continue
        quarterly = []
        for shard in shards:
            forms, accepted = shard["form"], shard["acceptanceDateTime"]
            report, filed = shard["reportDate"], shard["filingDate"]
            for j in range(len(forms)):
                if not accepted[j]:
                    continue
                if forms[j] == "4":
                    records.append((cik, report[j], filed[j],
                                    filings.et_from_utc(accepted[j])))
                elif forms[j] in ("10-K", "10-Q"):
                    quarterly.append(filings.et_from_utc(accepted[j]))
        if quarterly:
            periodic[cik] = np.array(sorted(quarterly), dtype="datetime64[ns]")
        if count % 200 == 0:
            print("  ... %d/%d issuers, %d form 4s" % (count, len(ciks), len(records)))

    frame = pd.DataFrame(records, columns=["cik", "reportDate", "filingDate", "accepted"])
    frame["accepted"] = pd.to_datetime(frame["accepted"])
    frame["reportDate"] = pd.to_datetime(frame["reportDate"], errors="coerce")
    era = frame[frame["accepted"] >= pd.Timestamp("2016-01-01")].copy()
    print("\nForm 4 records %d, with reportDate %.3f; study era (2016+) %d"
          % (len(frame), frame["reportDate"].notna().mean(), len(era)))

    era["lag_days"] = (era["accepted"].dt.normalize() - era["reportDate"]).dt.days
    lag = era["lag_days"].dropna()
    lag = lag[(lag >= 0) & (lag <= 400)]
    print("\n=== transaction date -> acceptance lag (calendar days) ===")
    print("  p10 %.0f  p25 %.0f  median %.0f  p75 %.0f  p90 %.0f  p99 %.0f"
          % tuple(lag.quantile(q) for q in (.1, .25, .5, .75, .9, .99)))
    print("  <=2d %.3f   <=4d %.3f   >10d %.3f"
          % ((lag <= 2).mean(), (lag <= 4).mean(), (lag > 10).mean()))

    era["after_close"] = era["accepted"].dt.hour >= 16
    by_year = era.groupby(era["accepted"].dt.year)["after_close"].mean()
    print("\n=== accepted after the 16:00 ET close ===")
    print("  study era overall %.3f" % era["after_close"].mean())
    print("  by year: " + "  ".join("%d:%.3f" % (y, v) for y, v in by_year.items()))

    distances = []
    for cik, group in era.groupby("cik"):
        marks = periodic.get(cik)
        if marks is None or not len(marks):
            continue
        accepted = group["accepted"].to_numpy(dtype="datetime64[ns]")
        idx = np.clip(np.searchsorted(marks, accepted), 1, len(marks) - 1)
        distances.append(np.minimum(
            np.abs((accepted - marks[idx - 1]) / np.timedelta64(1, "D")),
            np.abs((accepted - marks[idx]) / np.timedelta64(1, "D"))))
    gap = np.concatenate(distances)
    print("\n=== independence: distance to the issuer's nearest 10-K/10-Q ===")
    print("  n %d   median %.1f days" % (len(gap), np.median(gap)))
    for window in (2, 5, 10, 21, 45):
        expected = min(1.0, window / 45.5)     # uniform across a ~91-day quarter
        print("  within %2dd: %.3f   (uniform would give %.3f, ratio %.2fx)"
              % (window, (gap <= window).mean(), expected,
                 (gap <= window).mean() / expected))

    payload = {
        "n_form4_total": int(len(frame)), "n_form4_era": int(len(era)),
        "lag_quantiles": {str(q): float(lag.quantile(q)) for q in (.1, .25, .5, .75, .9, .99)},
        "lag_le_2": float((lag <= 2).mean()), "lag_le_4": float((lag <= 4).mean()),
        "after_close_era": float(era["after_close"].mean()),
        "after_close_by_year": {int(y): float(v) for y, v in by_year.items()},
        "gap_median_days": float(np.median(gap)),
        "gap_within": {int(w): float((gap <= w).mean()) for w in (2, 5, 10, 21, 45)},
    }
    pickle.dump(payload, open(f"{OUT_DIR}/form4_pit_semantics.pkl", "wb"))
    print("\nwrote form4_pit_semantics.pkl   %.1fs" % (time.time() - started))
    return payload


COMMANDS = {"coverage": coverage, "halfwidth": halfwidth, "ceiling": ceiling,
            "pit": pit}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print("usage: python -m alpha.form4_gate {%s}" % "|".join(COMMANDS))
        return 2
    COMMANDS[argv[1]]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
