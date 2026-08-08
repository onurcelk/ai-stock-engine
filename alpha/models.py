"""Model A (alpha regression), Model A′ (simple factors), Model B (ranker).

§14's correction is the whole shape of this file: **A′ runs before B, not
after**, so the simple-factor baseline acts as a gate rather than as a
post-hoc comparison. §18 calls that "the single most important bar in the whole
directive". The code therefore makes A′ cheap and always-computed, and puts
Model B behind an explicit gate argument that the caller has to satisfy.

Hyperparameters are the ones written into `PREREGISTRATION.md` §7 and are not
tuned. lightgbm/xgboost/catboost are not installed in this environment;
`HistGradientBoostingRegressor` is the same histogram-binned gradient-boosted
tree algorithm, handles NaN natively (which matters, because the pipeline
refuses to impute), and is what §14's "LightGBM/XGBoost/CatBoost regression"
is asking for in substance.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

# Pre-registered in PREREGISTRATION.md §7. Changing these after seeing a result
# is the thing the pre-registration exists to prevent.
MODEL_A_PARAMS = dict(
    loss="squared_error",
    max_iter=300,
    learning_rate=0.05,
    max_leaf_nodes=31,
    min_samples_leaf=100,
    l2_regularization=1.0,
    max_bins=255,
    early_stopping=False,
    random_state=0,
)

# §14 Model A′. Each is ranked within the cutoff and evaluated at its natural
# positive sign; the sign that gets used is fixed on the development set only.
SIMPLE_FACTORS = {
    "mom_5d": "ret_5d",
    "mom_20d": "ret_20d",
    "mom_60d": "ret_60d",
    "mom_12_1": "ret_12_1",
    "rs_vs_spy_20d": "ret_20d__vs_spy",
    "rs_vs_sector_20d": "ret_20d__vs_sector",
}


@dataclasses.dataclass
class Fit:
    model: HistGradientBoostingRegressor
    columns: list[str]
    trained_on: int
    trained_through: pd.Timestamp

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        matrix = frame.reindex(columns=self.columns).to_numpy(dtype=float)
        return pd.Series(self.model.predict(matrix), index=frame.index)


def fit_model_a(train: pd.DataFrame, columns: list[str],
                target: str = "target_train", params: dict | None = None) -> Fit | None:
    """One GBM fit on a training slice. No validation split, no early stopping.

    Early stopping is off deliberately: a random holdout inside the training
    window would be drawn from the same weeks as the rows it is scoring, so it
    would measure memorisation, not generalisation, and it would spend part of
    the sample doing it. The iteration count is fixed in advance instead.
    """
    usable = train[list(columns) + [target]].replace([np.inf, -np.inf], np.nan)
    usable = usable[usable[target].notna()]
    if len(usable) < 2_000:
        return None

    # A column that is entirely NaN over the training slice carries no
    # information and, in sklearn 1.9, crashes the histogram binner outright.
    # Dropping it is not imputation — an imputed cross-sectional mean would be
    # computed from the same cutoff it is filling, which is exactly the leak
    # the pipeline refuses elsewhere. The survivors are recorded on the Fit, so
    # prediction uses the same list.
    live = [c for c in columns if usable[c].notna().any()]
    if not live:
        return None

    x = usable[live].to_numpy(dtype=float)
    y = usable[target].to_numpy(dtype=float)
    model = HistGradientBoostingRegressor(**(params or MODEL_A_PARAMS))
    model.fit(x, y)
    return Fit(model, live, len(usable),
               pd.Timestamp(train.index.get_level_values(0).max()))


def simple_factor_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Model A′ predictions: the within-cutoff percentile of each raw factor.

    A rank rather than the raw value because these are compared by Spearman IC,
    which is rank-based anyway, and because ranking makes the six factors
    commensurable across cutoffs with wildly different dispersion.
    """
    out = {}
    for name, column in SIMPLE_FACTORS.items():
        if column not in frame.columns:
            continue
        out[name] = frame.groupby(level=0)[column].rank(pct=True, na_option="keep")
    return pd.DataFrame(out, index=frame.index)


def choose_best_simple_factor(ic_by_factor: dict[str, pd.Series]) -> tuple[str, int]:
    """Pick the reference factor and its sign — on development data only (§7).

    Sign selection is a real degree of freedom and pretending otherwise is how
    a short-horizon reversal effect gets reported as momentum "working". It is
    resolved here, once, on the development set, and then frozen: the exam set
    never gets a vote on either the factor or its direction.
    """
    scored = {name: float(series.dropna().mean()) for name, series in ic_by_factor.items()
              if series.notna().any()}
    if not scored:
        return "", 1
    best = max(scored, key=lambda k: abs(scored[k]))
    return best, (1 if scored[best] >= 0 else -1)


# ----------------------------------------------------------------------
# Model B — cross-sectional ranker. Gated (§14, §27): only constructed once a
# regression has been shown to beat the best simple factor on development data.
# ----------------------------------------------------------------------

def fit_model_b(train: pd.DataFrame, columns: list[str], gate_passed: bool,
                target: str = "target_rank") -> Fit | None:
    """LambdaRank stand-in: regression onto the within-cutoff percentile rank.

    Two honesty notes.

    First, the gate. §14 makes the ranker conditional on Model A beating the
    best simple factor, and §27 repeats it. `gate_passed=False` returns None —
    the ranker is not built, rather than built and then caveated.

    Second, the algorithm. A true LambdaRank needs a listwise objective
    (lightgbm's `lambdarank`), which is not installed here. Regressing onto the
    per-cutoff percentile rank with `group = cutoff_date` optimises a pointwise
    surrogate of the same quantity: it is what the ranking literature calls a
    pointwise ranker, it is weaker than LambdaRank, and any report using it
    must say so rather than claim a ranker was tested.
    """
    if not gate_passed:
        return None
    return fit_model_a(train, columns, target=target)


def fit_model_c(train: pd.DataFrame, columns: list[str], gate_passed: bool) -> Fit | None:
    """Sector-neutral ranker (§14 Model C): rank within sector, not within universe."""
    if not gate_passed:
        return None
    frame = train.copy()
    within = frame.groupby([frame.index.get_level_values(0), frame["sector"]])["alpha_5d"]
    frame["target_sector_rank"] = within.rank(pct=True, na_option="keep")
    return fit_model_a(frame, columns, target="target_sector_rank")
