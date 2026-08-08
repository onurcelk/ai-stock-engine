"""Strict-temporal-order walk-forward, and the §8 evaluation that reads it.

§19: train → validate → test in temporal order, no shuffling, grouped by cutoff
date, hyperparameters confined to the development period. The one thing that
makes this file trustworthy is that a model evaluated at cutoff *T* is fitted
on rows whose outcome windows closed at least `horizon + embargo` sessions
before *T* — `dataset.training_cutoffs` computes that boundary and nothing here
is allowed to widen it.

Refitting is periodic rather than per-cutoff (quarterly, pre-registered). That
makes the study cheap enough to run, and it errs in the safe direction: between
refits the model is *older* than the boundary demands, never newer.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from . import dataset, models, stats

# Pre-registered as "refit every 13 cutoffs (quarterly)". Expressed in sessions
# rather than in cutoff-count because the two only coincide on the weekly
# development schedule: the twelve exam cutoffs are spread over four years, and
# a literal every-13th-cutoff rule would predict 2026 with a model trained
# through 2022. 13 cutoffs x 5 sessions = 65 sessions, so this is the same rule
# on the development schedule and the intended one everywhere else.
REFIT_SESSIONS = 65
MIN_TRAIN_CUTOFFS = 60


@dataclasses.dataclass
class Run:
    """Out-of-sample predictions plus the trail needed to audit them."""

    name: str
    predictions: pd.Series          # MultiIndex (cutoff, symbol)
    fits: list[dict]
    columns: list[str]

    @property
    def evaluated_cutoffs(self) -> list[pd.Timestamp]:
        clean = self.predictions.dropna()
        return sorted(clean.index.get_level_values(0).unique())


def walk_forward(panel: dataset.Panel, book, columns: list[str],
                 fit_fn=models.fit_model_a, name: str = "model_a",
                 refit_sessions: int = REFIT_SESSIONS,
                 min_train_cutoffs: int = MIN_TRAIN_CUTOFFS,
                 restrict_test_to: list[pd.Timestamp] | None = None,
                 train_pool: list[pd.Timestamp] | None = None,
                 verbose: bool = True) -> Run:
    """Fit forward through time, predicting only what the fit could not have seen.

    `train_pool` exists for the exam run: exam cutoffs must be predicted by
    models trained on *development* cutoffs, so the pool of admissible training
    dates is passed in rather than taken from the panel being predicted.
    """
    all_cutoffs = panel.cutoffs
    pool = sorted(train_pool) if train_pool is not None else all_cutoffs
    test_cutoffs = sorted(restrict_test_to) if restrict_test_to is not None else all_cutoffs

    calendar = book.calendar
    level0 = panel.frame.index.get_level_values(0)
    predictions = pd.Series(np.nan, index=panel.frame.index, dtype=float)
    fits: list[dict] = []
    fit, fitted_at = None, None

    for cutoff in test_cutoffs:
        usable = dataset.training_cutoffs(pool, cutoff, book)
        if len(usable) < min_train_cutoffs:
            fit, fitted_at = None, None
            continue

        stale = fitted_at is None or (
            calendar.searchsorted(cutoff) - calendar.searchsorted(fitted_at) >= refit_sessions)
        if stale:
            train = panel.frame[level0.isin(pd.DatetimeIndex(usable))]
            fit = fit_fn(train, columns)
            fitted_at = cutoff
            if fit is not None:
                fits.append({"refit_at": str(pd.Timestamp(cutoff).date()),
                             "train_rows": fit.trained_on,
                             "train_cutoffs": len(usable),
                             "trained_through": str(fit.trained_through.date())})
                if verbose:
                    print(f"    refit @ {pd.Timestamp(cutoff).date()}  "
                          f"{fit.trained_on:>7,d} rows  "
                          f"through {fit.trained_through.date()}", flush=True)

        if fit is None:
            continue
        block = panel.frame[level0 == pd.Timestamp(cutoff)]
        predictions.loc[block.index] = fit.predict(block).to_numpy()

    return Run(name, predictions, fits, list(columns))


# ----------------------------------------------------------------------
# Evaluation — the §15 metrics and the §8 pre-registered thresholds.
# ----------------------------------------------------------------------

THRESHOLD_MEAN_IC = 0.03
THRESHOLD_HIT_RATE = 0.55
THRESHOLD_SIGN_STABILITY = 0.60
THRESHOLD_MIN_CUTOFFS = 50


@dataclasses.dataclass
class Evaluation:
    name: str
    ic: stats.Series
    spread: stats.Series
    top: stats.Series
    bottom: stats.Series
    per_cutoff: pd.DataFrame
    regime_ic: pd.DataFrame

    def criteria(self, versus: stats.Series | None = None) -> dict[str, dict]:
        """The seven §8 criteria, each with its number and its verdict."""
        ic_low, ic_high = self.ic.bootstrap_ci()
        spread_low, spread_high = self.spread.bootstrap_ci()
        hit = stats.Series(f"{self.name} IC>0", (self.ic.clean > 0).astype(float), null=0.5)
        hit_low, hit_high = hit.bootstrap_ci()

        out = {
            "1_mean_ic": {
                "value": round(self.ic.mean, 5), "threshold": f"> {THRESHOLD_MEAN_IC}",
                "ci": [round(ic_low, 5), round(ic_high, 5)],
                "passed": bool(self.ic.mean > THRESHOLD_MEAN_IC and ic_low > 0)},
            "2_ic_hit_rate": {
                "value": round(self.ic.hit_rate, 4), "threshold": f"> {THRESHOLD_HIT_RATE}",
                "ci": [round(hit_low, 4), round(hit_high, 4)],
                "passed": bool(self.ic.hit_rate > THRESHOLD_HIT_RATE and hit_low > 0.5)},
            "3_top_minus_bottom": {
                "value": round(self.spread.mean, 5), "threshold": "> 0, CI excludes 0",
                "ci": [round(spread_low, 5), round(spread_high, 5)],
                "passed": bool(self.spread.mean > 0 and spread_low > 0)},
            "4_sign_stability": {
                "value": round(self.ic.hit_rate, 4),
                "threshold": f">= {THRESHOLD_SIGN_STABILITY}",
                "passed": bool(self.ic.hit_rate >= THRESHOLD_SIGN_STABILITY)},
            "6_no_regime_collapse": {
                "value": {k: round(v, 4) for k, v in
                          self.regime_ic["mean_ic"].to_dict().items()},
                "threshold": "mean IC > 0 in every regime",
                "passed": bool(len(self.regime_ic) and (self.regime_ic["mean_ic"] > 0).all())},
            "7_effective_sample": {
                "value": self.ic.n, "threshold": f">= {THRESHOLD_MIN_CUTOFFS} cutoffs",
                "passed": bool(self.ic.n >= THRESHOLD_MIN_CUTOFFS)},
        }
        if versus is not None:
            low, high = versus.bootstrap_ci()
            out["5_beats_simple_factor"] = {
                "value": round(versus.mean, 5), "threshold": "> 0, CI excludes 0",
                "ci": [round(low, 5), round(high, 5)],
                "passed": bool(versus.mean > 0 and low > 0)}
        else:
            out["5_beats_simple_factor"] = {
                "value": None, "threshold": "> 0, CI excludes 0",
                "passed": False, "note": "no baseline supplied"}
        return dict(sorted(out.items()))

    def verdict(self, versus: stats.Series | None = None) -> tuple[bool, list[str]]:
        criteria = self.criteria(versus)
        failed = [k for k, v in criteria.items() if not v["passed"]]
        return (not failed), failed


def evaluate(panel: dataset.Panel, predictions: pd.Series, name: str,
             target: str = "alpha_5d") -> Evaluation:
    """Per-cutoff IC and quintile spread, plus the regime breakdown of §22."""
    frame = panel.frame.copy()
    frame["prediction"] = predictions.reindex(frame.index)
    frame = frame[frame["prediction"].notna()]

    ic = stats.ic_by_cutoff(frame, "prediction", target)
    quintiles = stats.quintile_spread(frame, "prediction", target)

    per_cutoff = pd.DataFrame({"ic": ic}).join(quintiles)
    if len(panel.regimes):
        per_cutoff = per_cutoff.join(panel.regimes)

    regime_rows = []
    for column in ("trend", "vol"):
        if column not in per_cutoff.columns:
            continue
        for value, block in per_cutoff.groupby(column):
            series = block["ic"].dropna()
            regime_rows.append({"regime": str(value), "n_cutoffs": len(series),
                                "mean_ic": float(series.mean()) if len(series) else np.nan,
                                "hit_rate": float((series > 0).mean()) if len(series) else np.nan})
    regime_ic = (pd.DataFrame(regime_rows).set_index("regime")
                 if regime_rows else pd.DataFrame(columns=["n_cutoffs", "mean_ic", "hit_rate"]))

    return Evaluation(
        name=name,
        ic=stats.Series(f"{name} Spearman IC", ic, null=0.0),
        spread=stats.Series(f"{name} top-bottom spread", per_cutoff["spread"], null=0.0),
        top=stats.Series(f"{name} top quintile alpha", per_cutoff["top"], null=0.0),
        bottom=stats.Series(f"{name} bottom quintile alpha", per_cutoff["bottom"], null=0.0),
        per_cutoff=per_cutoff,
        regime_ic=regime_ic,
    )


def evaluate_simple_factors(panel: dataset.Panel, cutoffs: list[pd.Timestamp] | None = None,
                            target: str = "alpha_5d") -> dict[str, pd.Series]:
    """Model A′: one IC series per simple factor (§14, §18)."""
    frame = panel.frame
    if cutoffs is not None:
        level0 = frame.index.get_level_values(0)
        frame = frame[level0.isin(pd.DatetimeIndex(cutoffs))]
    scores = models.simple_factor_scores(frame)

    out = {}
    for name in scores.columns:
        block = frame[[target]].copy()
        block["prediction"] = scores[name]
        out[name] = stats.ic_by_cutoff(block, "prediction", target)
    return out
