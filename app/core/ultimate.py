"""The ultimate indicator: one call, from evidence weighted by measured skill.

Everything else in this app produces *a* number. The forecast produces an
accuracy, each trading agent produces a return, each technical source produces
a reading. None of them is a decision, and averaging them would only produce a
more confident average of things that mostly do not work — this repo's own
walk-forward found the LSTM below a coin flip on direction.

So this module does not average opinions. It **measures** them first.

For every source, at every horizon:

1. Score the whole history on the source's own [-1, +1] scale.
2. Take the bars where it actually had an opinion, and check how often the
   sign of that opinion matched the sign of the realised forward return.
3. Do that check on a **held-out tail** the calibration never sees.
4. Shrink the resulting edge by its own t-statistic, computed on the
   *effective* sample size — overlapping forward windows are not independent
   observations, and pretending otherwise is how a 5-bar horizon manufactures
   significance out of 2,000 correlated draws.
5. Weight the source by what survives. An edge of zero weighs nothing.

The verdict is then the weight-normalised sum, its confidence is the product
of three gates that can each independently zero it, and no single family of
sources may carry more than `FAMILY_CAP` of the total — four trend followers
agreeing is one observation, not four.

The design consequence worth stating plainly: **this thing is allowed to say
it does not know.** When nothing clears significance, the weights are zero,
the confidence is zero, and the reading is HOLD with a conclusion that says
why. That is not a degraded mode; it is the correct output for most symbols on
most days, and an indicator that cannot produce it is not measuring anything.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import pandas as pd

from . import data, filings_evidence, indicators, live, strategies

# ------------------------------------------------------------------- verdicts

STRONG_BUY = "STRONG BUY"
BUY = "BUY"
HOLD = "HOLD"
SELL = "SELL"
STRONG_SELL = "STRONG SELL"

ACTIONS = [STRONG_SELL, SELL, HOLD, BUY, STRONG_BUY]

# Score bands, on the -100..+100 scale. Deliberately wide around zero: the
# cost of a wrong HOLD is an opportunity, the cost of a wrong BUY is money.
STRONG_BAND = 40.0
ACT_BAND = 15.0

# Below this confidence the score is not allowed to name a direction, however
# large it is. A big number assembled from sources with no measured edge is
# the exact failure this module exists to prevent. STRONG needs a good deal
# more than the floor before it may be said at all.
MIN_CONFIDENCE = 12.0
STRONG_CONFIDENCE = 30.0

# No family may carry more than this share of the surviving weight. Four trend
# followers on one tape are one observation seen four ways.
FAMILY_CAP = 0.55

# Calibration settings. The threshold keeps a source from being scored on bars
# where it was saying nothing; the holdout is the tail its weight is measured
# on; below min_samples a source is simply not weighted.
FIRE_THRESHOLD = 0.15
HOLDOUT = 0.30
MIN_SAMPLES = 25

# A source must clear this t-statistic before it may carry any weight at all.
# Shrinkage alone is not enough: it scales an edge down but never to zero, so
# without a floor the *least insignificant* source in a field of noise still
# ends up carrying the verdict — which is exactly what a first pass on AAPL
# did, handing 70% of the weight to a 54% hit rate at t = 0.7.
#
# 1.65 is the one-sided 5% point. It is deliberately not the ~2.3 that a full
# Bonferroni correction over sixteen sources would demand: the multiplicity
# is handled downstream instead, by requiring FULL_BREADTH families to agree
# before a horizon speaks at full volume, which is a much harder bar to clear
# by chance than any single-source threshold. Measured over eighteen symbols
# on ten years of daily bars, this leaves roughly two thirds of them reading
# HOLD — which is the point.
MIN_T = 1.65

# The raw weight a horizon needs before its score is allowed to reach full
# scale. Roughly four sources at a 3-point edge and t≈1.5. Scores are divided
# by this rather than by their own total, so one lonely source produces a
# small score instead of a maximal one — thin evidence should read as a weak
# call, not as a confident call made on nothing.
REFERENCE_WEIGHT = 6.0

# Reaching full marks on the skill gate needs a weighted edge of this many
# percentage points over a coin flip.
FULL_EDGE = 6.0

# How many *different* families have to be saying something before a horizon
# may speak at full volume. One source with a large edge is still one source:
# on EURUSD=X a single agent measured at 58.5% over 77 independent weeks was
# enough to produce a 99%-confident STRONG SELL on its own, which is precisely
# the kind of number this module exists not to print.
FULL_BREADTH = 3

TECHNICAL, AGENT, MODEL = "technical", "agent", "model"


# ------------------------------------------------------------------ horizons


@dataclasses.dataclass(frozen=True)
class Horizon:
    """One prediction distance, and the bars it is best measured on.

    `interval`/`bars` is the pairing this horizon is *fetched* at — chosen so
    the mapping is exact rather than inferred, and so each horizon gets the
    deepest history Yahoo will serve for it. `bars_at` covers the other case:
    a frame that is already loaded (a bundled CSV, an upload) and cannot be
    re-fetched at a different resolution.
    """

    key: str
    label: str
    interval: str
    bars: int
    period: str
    bars_at: dict[str, int]
    min_bars: int = 260

    def bars_on(self, interval: str) -> int | None:
        """How many bars of `interval` this horizon spans, or None if it can't."""
        return self.bars_at.get(interval)


# A US session is 6.5 hours, which is 7 hourly bars and 2 four-hour bars — the
# reason these are a written table rather than horizon_hours / bar_hours.
HORIZONS: list[Horizon] = [
    Horizon("4h", "4 hours", "1h", 4, "2y",
            {"1h": 4, "4h": 1}, min_bars=300),
    Horizon("1d", "1 day", "1d", 1, "10y",
            {"1h": 7, "4h": 2, "1d": 1}, min_bars=260),
    Horizon("1w", "1 week", "1d", 5, "10y",
            {"1h": 33, "4h": 10, "1d": 5, "1wk": 1}, min_bars=300),
]

HORIZON_BY_KEY = {h.key: h for h in HORIZONS}


def infer_interval(dates: pd.Series) -> str:
    """Which bar size a loaded frame is on, measured from its own timestamps.

    Only needed for frames that did not come from `live.fetch` and so carry no
    interval of record — the bundled CSVs and user uploads.
    """
    per_year = data.periods_per_year(dates)
    if per_year >= 3_000:
        return "1h"
    if per_year >= 700:
        return "4h"
    if per_year >= 150:
        return "1d"
    if per_year >= 30:
        return "1wk"
    return "1mo"


# --------------------------------------------------------------- calibration


@dataclasses.dataclass
class Skill:
    """What a source's opinions have actually been worth at one horizon."""

    hit_rate: float          # % of firings whose sign matched the outcome
    samples: int             # firings scored
    effective: float         # samples discounted for overlapping windows
    edge: float              # hit_rate - 50, in percentage points
    t_stat: float            # edge over its own standard error
    weight: float            # raw, pre-normalisation; 0 when nothing survived
    note: str = ""           # why the weight is zero, when it is

    @property
    def active(self) -> bool:
        return self.weight > 0

    @property
    def significant(self) -> bool:
        """Two standard errors, the usual line. Reported, never gated on."""
        return self.t_stat >= 2.0


DEAD = Skill(hit_rate=50.0, samples=0, effective=0.0, edge=0.0, t_stat=0.0,
             weight=0.0, note="never fired")


def forward_return(close: pd.Series, bars: int) -> pd.Series:
    """The return `bars` ahead of each bar. NaN at the tail, by construction."""
    return close.shift(-bars) / close - 1.0


def calibrate(
    scores: pd.Series,
    close: pd.Series,
    bars: int,
    *,
    holdout: float = HOLDOUT,
    threshold: float = FIRE_THRESHOLD,
    min_samples: int = MIN_SAMPLES,
    warmup: int = indicators.WARMUP,
) -> Skill:
    """Measure one source against the realised forward returns.

    Three details do the real work here:

    - **Only firings count.** A source at 0.02 is not making a call, and
      scoring it there would dilute its hit rate towards 50% no matter how
      good its actual calls were.
    - **Only the holdout counts.** The tail the weights are read off is not
      the body the source was designed against.
    - **Effective sample size, not sample count.** A 5-bar forward return
      sampled every bar gives five overlapping views of the same week. The
      standard error uses `samples / bars`, so a week-ahead source needs five
      times the raw observations to claim the same significance as a
      day-ahead one. Skipping this is the single easiest way to turn noise
      into a confident indicator.
    """
    forward = forward_return(close, bars)
    fired = scores.abs() >= threshold

    usable = fired & forward.notna() & scores.notna()
    if warmup:
        usable.iloc[:warmup] = False

    split = int(len(close) * (1 - holdout))
    tested = usable.copy()
    tested.iloc[:split] = False

    count = int(tested.sum())
    if count < min_samples:
        return dataclasses.replace(
            DEAD, samples=count,
            note=f"only {count} scored calls in the holdout, needs {min_samples}",
        )

    called = np.sign(scores[tested].to_numpy())
    happened = np.sign(forward[tested].to_numpy())
    hit_rate = float((called == happened).mean() * 100)
    edge = hit_rate - 50.0

    # Overlapping windows are not independent draws.
    effective = max(1.0, count / max(1, bars))
    # Standard deviation of a coin-flip proportion, expressed in points.
    standard_error = 50.0 / np.sqrt(effective)
    t_stat = float(edge / standard_error)

    if edge <= 0:
        return Skill(hit_rate=hit_rate, samples=count, effective=effective,
                     edge=edge, t_stat=t_stat, weight=0.0,
                     note="called it wrong more often than right")
    if t_stat < MIN_T:
        return Skill(hit_rate=hit_rate, samples=count, effective=effective,
                     edge=edge, t_stat=t_stat, weight=0.0,
                     note=f"edge of {edge:+.1f} pts is inside its own noise "
                          f"(t = {t_stat:.2f}, needs {MIN_T:.1f})")

    # Shrink towards zero by the t-statistic: half the edge survives at t=1,
    # 90% at t=3. Nothing here flips a sign — a source that is anti-predictive
    # is dropped, never inverted, because inverting on a fit is how you find
    # an edge in pure noise.
    shrink = t_stat ** 2 / (t_stat ** 2 + 1.0)
    return Skill(hit_rate=hit_rate, samples=count, effective=effective,
                 edge=edge, t_stat=t_stat, weight=float(edge * shrink))


def typical_move(close: pd.Series, bars: int, holdout: float = HOLDOUT) -> float:
    """Median absolute return over `bars`, in percent — the horizon's own yardstick.

    An expected move only means something next to what a move usually is:
    +0.4% is a strong call on a bond ETF and noise on a small-cap.
    """
    forward = forward_return(close, bars).dropna()
    if forward.empty:
        return 0.0
    split = int(len(forward) * (1 - holdout))
    tail = forward.iloc[split:] if len(forward) - split >= 20 else forward
    return float(tail.abs().median() * 100)


# ------------------------------------------------------------------ readings


@dataclasses.dataclass
class Reading:
    """One source's live call at one horizon, plus what that call is worth."""

    key: str
    name: str
    family: str
    kind: str
    describe: str
    score: float
    skill: Skill
    detail: str = ""
    weight: float = 0.0      # normalised across the horizon; filled by the aggregator

    @property
    def direction(self) -> str:
        if self.score >= FIRE_THRESHOLD:
            return "bullish"
        if self.score <= -FIRE_THRESHOLD:
            return "bearish"
        return "neutral"

    @property
    def firing(self) -> bool:
        return abs(self.score) >= FIRE_THRESHOLD

    @property
    def counts(self) -> bool:
        """Weighted *and* saying something — the only readings that move the score."""
        return self.weight > 0 and self.firing

    @property
    def contribution(self) -> float:
        """This reading's share of the -100..+100 score."""
        return self.weight * self.score * 100


def _readings_from(
    frame: pd.DataFrame,
    bars: int,
    scores: dict[str, pd.Series],
    catalogue: dict[str, indicators.Source],
    kind: str,
) -> list[Reading]:
    close = frame["close"]
    out = []
    for key, series in scores.items():
        source = catalogue[key]
        if series.abs().max() == 0:
            skill = dataclasses.replace(DEAD, note="not computable on this frame")
        else:
            skill = calibrate(series, close, bars)
        out.append(Reading(
            key=key, name=source.name, family=source.family, kind=kind,
            describe=source.describe, score=float(series.iloc[-1]), skill=skill,
        ))
    return out


def agent_sources(close: pd.Series) -> dict[str, indicators.Source]:
    """The rule-based trading agents, as evidence rather than as backtests.

    Their windows scale with the series the way the Trading agents tab sets
    them by default, so what this reads is the same agent the rest of the app
    would run — the point is to fold their standing position into the verdict,
    not to introduce a fourth tuning surface.
    """
    length = max(20, len(close))
    channel = max(2, min(int(np.ceil(length * 0.1)), length // 3))
    short = max(2, int(0.025 * length))
    long = max(short + 1, int(0.05 * length))

    def turtle(frame: pd.DataFrame) -> pd.Series:
        return indicators.stance(strategies.turtle(frame["close"], channel))

    def crossover(frame: pd.DataFrame) -> pd.Series:
        return indicators.stance(
            strategies.moving_average(frame["close"], short, long))

    def rolling(frame: pd.DataFrame) -> pd.Series:
        return indicators.stance(strategies.signal_rolling(frame["close"], 4))

    return {
        "agent_turtle": indicators.Source(
            "agent_turtle", "Turtle agent", AGENT,
            f"Standing position of the {channel}-bar channel agent.", turtle),
        "agent_crossover": indicators.Source(
            "agent_crossover", "MA crossover agent", AGENT,
            f"Standing position after the {short}/{long} crossover.", crossover),
        "agent_rolling": indicators.Source(
            "agent_rolling", "Signal rolling agent", AGENT,
            "Standing position of the momentum-flip agent.", rolling),
    }


@dataclasses.dataclass
class ModelEvidence:
    """A neural forecast, reduced to what the consensus can use.

    The forecast tab produces a predicted path and a directional accuracy.
    Only two numbers survive the trip here: which way it points, and how often
    that pointing has been right out of sample. The second is what decides
    whether the first is worth anything, and this repo's walk-forward is on
    record that it usually is not.
    """

    name: str
    interval: str
    horizon_bars: int
    predicted_move_pct: float
    directional_pct: float
    samples: int

    def reading(self, bars: int, yardstick: float) -> Reading:
        # Drift scales with time; the forecast's own horizon is rarely one of
        # ours, so its move is pro-rated rather than taken at face value.
        scaled = self.predicted_move_pct * bars / max(1, self.horizon_bars)
        score = float(np.tanh(scaled / yardstick)) if yardstick > 0 else 0.0

        edge = self.directional_pct - 50.0
        effective = max(1.0, self.samples / max(1, self.horizon_bars))
        t_stat = float(edge / (50.0 / np.sqrt(effective)))
        if edge <= 0:
            weight = 0.0
            note = "directional accuracy at or below a coin flip"
        elif t_stat < MIN_T:
            weight = 0.0
            note = (f"directional edge of {edge:+.1f} pts is inside its own "
                    f"noise (t = {t_stat:.2f})")
        else:
            shrink = t_stat ** 2 / (t_stat ** 2 + 1.0)
            weight, note = float(edge * shrink), ""

        return Reading(
            key="model", name=self.name, family=MODEL, kind=MODEL,
            describe="Neural forecast, weighted by its own directional accuracy.",
            score=score,
            skill=Skill(hit_rate=self.directional_pct, samples=self.samples,
                        effective=effective, edge=edge, t_stat=t_stat,
                        weight=weight, note=note),
            detail=f"{self.predicted_move_pct:+.2f}% over {self.horizon_bars} "
                   f"{self.interval} bars, pro-rated to {scaled:+.2f}% here",
        )


# ---------------------------------------------------------------- aggregation


def cap_families(weights: dict[str, float],
                 families: dict[str, str],
                 cap: float = FAMILY_CAP) -> dict[str, float]:
    """Hold every family to `cap` of the surviving total, and return that total shrunk.

    Four trend followers on the same tape are one observation seen four ways.
    Without a cap they out-vote every other kind of evidence on any trending
    symbol and the verdict becomes a moving average wearing a committee's
    clothes.

    The constraint is on the *post-cap* total, which makes it a water-filling
    problem rather than a rescale: a family may hold at most
    `cap / (1 - cap)` times the weight of everything outside it. Scaling and
    renormalising in a loop instead — the obvious implementation — converges
    towards the cap far too slowly to enforce it, and silently leaves a single
    family at 70% of a verdict it is supposed to be limited to 55% of.

    Weight lost to the cap is *not* redistributed. It was double-counted
    evidence; removing it should lower the horizon's coverage, and it does.
    """
    members: dict[str, list[str]] = {}
    for key, family in families.items():
        members.setdefault(family, []).append(key)

    live = {f: sum(weights.get(k, 0.0) for k in keys)
            for f, keys in members.items()}
    live = {f: total for f, total in live.items() if total > 0}
    if len(live) <= 1 or cap >= 1.0:
        # One family is all the evidence there is; capping it against nothing
        # would zero the horizon rather than balance it.
        return dict(weights)

    allowed = cap / (1.0 - cap)
    capped = dict(weights)
    # Largest first: shrinking the biggest family lowers the ceiling for the
    # next one, so the order matters and descending is the one that settles.
    for family in sorted(live, key=live.get, reverse=True):
        total = sum(capped.get(k, 0.0) for k in members[family])
        outside = sum(v for k, v in capped.items() if families[k] != family)
        ceiling = allowed * outside
        if total > ceiling and total > 0:
            scale = ceiling / total
            for key in members[family]:
                capped[key] = capped.get(key, 0.0) * scale
    return capped


def classify(score: float, confidence: float) -> str:
    """Score to action, with confidence holding the veto.

    The veto is not a safety rail bolted on afterwards — it is the point. A
    +70 score assembled entirely from sources measured at chance is a
    confident statement about nothing, and it has to come out as HOLD. The
    same logic gates STRONG one band higher: naming a strong call on evidence
    that only just cleared the floor is the same mistake in a smaller coat.
    """
    if confidence < MIN_CONFIDENCE:
        return HOLD
    strong = confidence >= STRONG_CONFIDENCE
    if score >= STRONG_BAND:
        return STRONG_BUY if strong else BUY
    if score >= ACT_BAND:
        return BUY
    if score <= -STRONG_BAND:
        return STRONG_SELL if strong else SELL
    if score <= -ACT_BAND:
        return SELL
    return HOLD


@dataclasses.dataclass
class HorizonVerdict:
    """The call at one prediction distance."""

    horizon: Horizon
    readings: list[Reading]
    score: float
    confidence: float
    agreement: float          # share of live weight on the winning side
    weighted_edge: float      # measured edge behind the call, in points
    typical_move_pct: float
    bars_used: int
    interval: str
    rows: int
    last_price: float
    as_of: pd.Timestamp | None
    coverage: float = 0.0     # surviving weight against REFERENCE_WEIGHT, 0..1
    unavailable: str = ""     # non-empty means this horizon could not be read

    @property
    def available(self) -> bool:
        return not self.unavailable

    @property
    def action(self) -> str:
        return classify(self.score, self.confidence)

    @property
    def expected_move_pct(self) -> float:
        """Where the score points, sized by what a move at this horizon is worth."""
        return self.score / 100.0 * self.typical_move_pct

    @property
    def target_price(self) -> float:
        return self.last_price * (1 + self.expected_move_pct / 100.0)

    @property
    def live(self) -> list[Reading]:
        """Readings that are both weighted and saying something, heaviest first."""
        return sorted([r for r in self.readings if r.counts],
                      key=lambda r: abs(r.contribution), reverse=True)

    @property
    def supporting(self) -> list[Reading]:
        side = np.sign(self.score)
        return [r for r in self.live if np.sign(r.score) == side and side != 0]

    @property
    def dissenting(self) -> list[Reading]:
        side = np.sign(self.score)
        return [r for r in self.live if np.sign(r.score) == -side and side != 0]

    def table(self) -> pd.DataFrame:
        """Every source's evidence, whether or not it counted."""
        rows = []
        for reading in sorted(self.readings,
                              key=lambda r: (-r.weight, -abs(r.score))):
            skill = reading.skill
            rows.append({
                "Source": reading.name,
                "Family": reading.family,
                "Reading": round(reading.score, 3),
                "Says": reading.direction,
                "Hit rate %": round(skill.hit_rate, 1) if skill.samples else None,
                "Calls": skill.samples or None,
                "Independent": round(skill.effective, 1) if skill.samples else None,
                "Edge pts": round(skill.edge, 2) if skill.samples else None,
                "t": round(skill.t_stat, 2) if skill.samples else None,
                "Weight %": round(reading.weight * 100, 1),
                "Contributes": round(reading.contribution, 1),
                "Why not": skill.note,
            })
        return pd.DataFrame(rows)


def evaluate_frame(
    frame: pd.DataFrame,
    horizon: Horizon,
    *,
    bars: int | None = None,
    interval: str | None = None,
    include_agents: bool = True,
    model: ModelEvidence | None = None,
) -> HorizonVerdict:
    """Score one already-loaded frame at one horizon. No network, no TensorFlow.

    This is the whole engine; `evaluate()` above it only decides which frames
    to hand it. Keeping the two apart is what makes the arithmetic testable
    against a synthetic series with a known answer.
    """
    interval = interval or infer_interval(frame["date"])
    bars = bars if bars is not None else horizon.bars_on(interval)

    empty = HorizonVerdict(
        horizon=horizon, readings=[], score=0.0, confidence=0.0, agreement=0.0,
        weighted_edge=0.0, typical_move_pct=0.0, bars_used=bars or 0,
        interval=interval, rows=len(frame),
        last_price=float(frame["close"].iloc[-1]) if len(frame) else 0.0,
        as_of=frame["date"].iloc[-1] if len(frame) else None,
    )

    if not bars:
        return dataclasses.replace(
            empty, unavailable=f"{horizon.label} is shorter than one {interval} bar")
    if len(frame) < max(horizon.min_bars, indicators.WARMUP + bars + MIN_SAMPLES * 2):
        return dataclasses.replace(
            empty,
            unavailable=f"{len(frame)} {interval} bars is too few to measure "
                        f"a {horizon.label} edge on")

    catalogue = dict(indicators.SOURCES)
    scores = indicators.read_all(frame)
    kinds = {key: TECHNICAL for key in scores}

    if include_agents:
        extra = agent_sources(frame["close"])
        catalogue.update(extra)
        for key, source in extra.items():
            scores[key] = source.read(frame)
            kinds[key] = AGENT

    readings = _readings_from(frame, bars, scores, catalogue, TECHNICAL)
    for reading in readings:
        reading.kind = kinds[reading.key]

    yardstick = typical_move(frame["close"], bars)
    if model is not None and model.interval == interval:
        readings.append(model.reading(bars, yardstick))

    survived = cap_families(
        {r.key: max(0.0, r.skill.weight) for r in readings},
        {r.key: r.family for r in readings},
    )

    # Two discounts, both applied to the weights themselves so the score, the
    # contributions and the displayed percentages can never disagree.
    #
    # Divided by REFERENCE_WEIGHT, not by its own total: normalising to the
    # total would make one surviving source carry a full-scale verdict, since
    # the weights would sum to 1 no matter how little evidence there was.
    #
    # Then scaled by breadth, because weight is not the same as independence.
    # A single family at maximum weight is one observation with a loud voice.
    total = sum(survived.values())
    families = {r.family for r in readings if survived.get(r.key, 0.0) > 0
                and r.firing}
    breadth = min(1.0, len(families) / FULL_BREADTH)
    scale = breadth / max(total, REFERENCE_WEIGHT) if total > 0 else 0.0

    for reading in readings:
        reading.weight = survived.get(reading.key, 0.0) * scale

    score = float(np.clip(sum(r.contribution for r in readings), -100.0, 100.0))
    counted = [r for r in readings if r.counts]
    live_weight = sum(r.weight for r in counted)

    if live_weight > 0 and score != 0:
        side = np.sign(score)
        agreement = sum(r.weight for r in counted
                        if np.sign(r.score) == side) / live_weight
    else:
        agreement = 0.0

    weighted_edge = (sum(r.weight * r.skill.edge for r in counted) / live_weight
                     if live_weight > 0 else 0.0)

    # Three independent gates, multiplied. Any one of them at zero is a
    # sufficient reason not to trust the number, so none of them may be
    # averaged away by the other two: no measured edge, no majority, or
    # nothing to read all mean the same thing here.
    skill_gate = min(1.0, max(0.0, weighted_edge) / FULL_EDGE)
    accord_gate = max(0.0, 2.0 * agreement - 1.0)
    coverage_gate = min(1.0, total * scale)
    confidence = float(100.0 * skill_gate * accord_gate * coverage_gate)

    return dataclasses.replace(
        empty, readings=readings, score=score, confidence=confidence,
        agreement=float(agreement), weighted_edge=float(weighted_edge),
        typical_move_pct=yardstick, coverage=float(coverage_gate),
    )


# ----------------------------------------------------------- the whole verdict


@dataclasses.dataclass
class UltimateVerdict:
    """The three horizons, and what they add up to."""

    symbol: str
    horizons: list[HorizonVerdict]
    score: float
    confidence: float
    alignment: str            # "aligned" | "split" | "quiet"
    generated_at: dt.datetime
    errors: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def action(self) -> str:
        return classify(self.score, self.confidence)

    @property
    def available(self) -> list[HorizonVerdict]:
        return [h for h in self.horizons if h.available]

    @property
    def last_price(self) -> float:
        for verdict in self.available:
            if verdict.horizon.key == "1d":
                return verdict.last_price
        return self.available[0].last_price if self.available else 0.0

    def by_key(self, key: str) -> HorizonVerdict | None:
        return next((h for h in self.horizons if h.horizon.key == key), None)

    def table(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "Horizon": h.horizon.label,
                "Call": h.action,
                "Score": round(h.score, 1),
                "Confidence %": round(h.confidence, 1),
                "Agreement %": round(h.agreement * 100, 0),
                "Coverage %": round(h.coverage * 100, 0),
                "Edge pts": round(h.weighted_edge, 2),
                "Expected move %": round(h.expected_move_pct, 2),
                "Typical move %": round(h.typical_move_pct, 2),
                "Sources counted": len(h.live),
                "Bars": f"{h.bars_used} × {h.interval}",
            }
            for h in self.available
        ])

    @property
    def conclusion(self) -> str:
        return conclude(self)


def _phrase(verdict: HorizonVerdict) -> str:
    return (f"{verdict.horizon.label} reads **{verdict.action}** "
            f"({verdict.score:+.0f}, {verdict.confidence:.0f}% confidence)")


def conclude(verdict: UltimateVerdict) -> str:
    """The written finding: what the call is, what it rests on, and what would move it.

    Assembled from the numbers rather than chosen from a list of templates, so
    it cannot drift away from what the engine actually computed.
    """
    if not verdict.available:
        reasons = "; ".join(f"{k}: {v}" for k, v in verdict.errors.items())
        return (f"No horizon could be read for {verdict.symbol}. "
                f"{reasons or 'No usable price history.'}")

    parts: list[str] = []
    parts.append(
        f"**{verdict.symbol} — {verdict.action}.** Net score "
        f"{verdict.score:+.0f} out of 100 at {verdict.confidence:.0f}% confidence, "
        f"from {len(verdict.available)} of {len(verdict.horizons)} horizons."
    )
    parts.append(
        "Across horizons: " + "; ".join(_phrase(h) for h in verdict.available) + "."
    )

    if verdict.alignment == "aligned":
        parts.append(
            "All readable horizons point the same way, which is the strongest "
            "configuration this measures — the short and long views agreeing "
            "is harder to produce by chance than either one alone."
        )
    elif verdict.alignment == "split":
        bullish = [h.horizon.label for h in verdict.available if h.score > ACT_BAND]
        bearish = [h.horizon.label for h in verdict.available if h.score < -ACT_BAND]
        parts.append(
            f"The horizons disagree — {', '.join(bullish)} bullish against "
            f"{', '.join(bearish)} bearish — so the net score is discounted and "
            "no strong call is available from this evidence."
        )
    else:
        parts.append(
            "No horizon is far enough from neutral to argue a direction."
        )

    # The single heaviest live reading anywhere, quoted with its measurement.
    best: tuple[float, Reading, HorizonVerdict] | None = None
    for horizon in verdict.available:
        for reading in horizon.live:
            key = abs(reading.contribution) * max(horizon.confidence, 1.0)
            if best is None or key > best[0]:
                best = (key, reading, horizon)

    if best is not None:
        _, reading, horizon = best
        skill = reading.skill
        parts.append(
            f"The heaviest single input is **{reading.name}** at "
            f"{horizon.horizon.label}, reading {reading.score:+.2f} on a "
            f"measured {skill.hit_rate:.1f}% hit rate over {skill.samples:,} calls "
            f"(≈{skill.effective:.0f} independent), an edge of {skill.edge:+.1f} "
            f"points at t = {skill.t_stat:.1f}. It carries "
            f"{reading.weight * 100:.0f}% of that horizon's weight."
        )

    dead = [h for h in verdict.available if not h.live]
    if dead:
        parts.append(
            f"Nothing cleared significance at {', '.join(h.horizon.label for h in dead)}, "
            "so " + ("that horizon contributes" if len(dead) == 1
                     else "those horizons contribute") + " no confidence at all."
        )

    strongest = max(verdict.available, key=lambda h: h.confidence, default=None)
    if strongest is not None and strongest.dissenting:
        names = ", ".join(r.name for r in strongest.dissenting[:3])
        parts.append(
            f"Arguing the other way at {strongest.horizon.label}: {names}. "
            f"Agreement there is {strongest.agreement * 100:.0f}% of live weight."
        )

    if verdict.confidence < MIN_CONFIDENCE:
        parts.append(
            "**Confidence is below the floor, so the call is HOLD regardless of "
            "the score.** On this history these sources have not demonstrated "
            "enough measured edge to act on, which is the ordinary result — "
            "most symbols on most days do not have a readable edge, and an "
            "indicator that never says so is not measuring anything."
        )
    else:
        best_horizon = max(verdict.available, key=lambda h: h.confidence)
        parts.append(
            f"Read this as a lean, not a certainty: the strongest horizon "
            f"({best_horizon.horizon.label}) is built on a weighted edge of "
            f"{best_horizon.weighted_edge:.1f} points over a coin flip, which "
            f"implies roughly a {50 + best_horizon.weighted_edge:.0f}/"
            f"{50 - best_horizon.weighted_edge:.0f} split, not a certainty. "
            f"Expected move there is {best_horizon.expected_move_pct:+.2f}% "
            f"against a typical {best_horizon.typical_move_pct:.2f}%."
        )

    return " ".join(parts)


def combine(symbol: str, verdicts: list[HorizonVerdict],
            errors: dict[str, str] | None = None) -> UltimateVerdict:
    """Fold the horizons into one call, weighted by their own confidence.

    Confidence-weighting is what stops a horizon that measured nothing from
    voting. A horizon at 0% confidence contributes literally zero, so the
    aggregate is the opinion of whichever timeframes could actually be
    measured, rather than an average that quietly includes the ones that
    could not.
    """
    # A horizon at 3% confidence is not a vote; letting it into `directions`
    # would let a rounding error decide whether the timeframes are aligned.
    live = [h for h in verdicts
            if h.available and h.confidence >= MIN_CONFIDENCE / 3]

    if not live:
        readable = [h for h in verdicts if h.available]
        return UltimateVerdict(
            symbol=symbol, horizons=verdicts, score=0.0, confidence=0.0,
            alignment="quiet" if readable else "none",
            generated_at=dt.datetime.now(), errors=errors or {},
        )

    total = sum(h.confidence for h in live)
    score = sum(h.confidence * h.score for h in live) / total
    confidence = sum(h.confidence ** 2 for h in live) / total

    directions = {int(np.sign(h.score)) for h in live if abs(h.score) >= ACT_BAND}
    if not directions:
        alignment, multiplier = "quiet", 1.0
    elif len(directions) == 1 and len(live) > 1:
        # Agreement across timeframes is genuinely more evidence, but only a
        # little: the horizons share sources and a common price series, so
        # they are correlated rather than independent confirmations.
        alignment, multiplier = "aligned", 1.15
    elif len(directions) > 1:
        alignment, multiplier = "split", 0.70
    else:
        alignment, multiplier = "aligned", 1.0

    # The multiplier moves the score but deliberately not the confidence.
    # Timeframes agreeing is evidence about *direction*; it says nothing about
    # how well any of them was measured, and letting it inflate confidence
    # would let a rhetorical flourish push a reading to certainty.
    return UltimateVerdict(
        symbol=symbol,
        horizons=verdicts,
        score=float(np.clip(score * multiplier, -100.0, 100.0)),
        confidence=float(np.clip(confidence, 0.0, 100.0)),
        alignment=alignment,
        generated_at=dt.datetime.now(),
        errors=errors or {},
    )


def evaluate(
    symbol: str,
    *,
    include_agents: bool = True,
    model: ModelEvidence | None = None,
    horizons: list[Horizon] | None = None,
    force: bool = False,
    fetcher=None,
) -> UltimateVerdict:
    """The full reading for a live symbol, fetching each horizon's own bars.

    `fetcher` is injectable so tests can run the whole engine offline against
    a known series; it defaults to `live.fetch` and is the only thing here
    that touches the network.
    """
    fetch = fetcher or live.fetch
    horizons = horizons or HORIZONS

    frames: dict[tuple[str, str], pd.DataFrame] = {}
    errors: dict[str, str] = {}
    verdicts: list[HorizonVerdict] = []

    for horizon in horizons:
        key = (horizon.interval, horizon.period)
        if key not in frames:
            try:
                frame, _ = fetch(symbol, period=horizon.period,
                                 interval=horizon.interval, force=force)
                # The earnings-drift source reads two columns the price feed
                # does not carry. Attached here, at the one place that knows
                # which firm this is, so `evaluate_frame` below stays a pure
                # function of a frame. A machine without the EDGAR cache gets
                # the frame back untouched and the source stays silent.
                frames[key] = filings_evidence.attach(frame, symbol)
            except live.FetchError as error:
                frames[key] = None
                errors[horizon.label] = str(error)

        frame = frames[key]
        if frame is None:
            verdicts.append(HorizonVerdict(
                horizon=horizon, readings=[], score=0.0, confidence=0.0,
                agreement=0.0, weighted_edge=0.0, typical_move_pct=0.0,
                bars_used=horizon.bars, interval=horizon.interval, rows=0,
                last_price=0.0, as_of=None,
                unavailable=errors.get(horizon.label, "no data"),
            ))
            continue

        verdicts.append(evaluate_frame(
            frame, horizon, bars=horizon.bars, interval=horizon.interval,
            include_agents=include_agents, model=model,
        ))

    return combine(symbol.upper(), verdicts, errors)


# ------------------------------------------------------------ scanning a book


def scan(
    symbols: list[str],
    *,
    include_agents: bool = True,
    force: bool = False,
    fetcher=None,
    on_progress=None,
) -> dict[str, UltimateVerdict]:
    """Read every symbol in a list, one verdict each.

    Deliberately the same `evaluate()` a single symbol goes through rather
    than a cheaper approximation. A portfolio row reading BUY while the signal
    tab reads HOLD for the same ticker would be worse than no row at all, and
    the only way to guarantee they agree is to run the same code on the same
    horizons at the same depths.

    A symbol that fails outright still gets an entry — an unreadable holding
    is a fact about the book, and dropping it from the table would quietly
    shorten a list the user is counting.
    """
    verdicts: dict[str, UltimateVerdict] = {}
    ordered = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))

    for index, symbol in enumerate(ordered):
        if on_progress:
            on_progress(index, len(ordered), symbol)
        try:
            verdicts[symbol] = evaluate(symbol, include_agents=include_agents,
                                        force=force, fetcher=fetcher)
        except Exception as error:  # noqa: BLE001 - one bad symbol, not a dead tab
            verdicts[symbol] = UltimateVerdict(
                symbol=symbol, horizons=[], score=0.0, confidence=0.0,
                alignment="none", generated_at=dt.datetime.now(),
                errors={"all": str(error)},
            )
    return verdicts


def scan_table(verdicts: dict[str, UltimateVerdict]) -> pd.DataFrame:
    """One row per symbol, ready to merge onto a holdings table."""
    rows = []
    for symbol, verdict in verdicts.items():
        row = {
            "Symbol": symbol,
            "Call": verdict.action,
            "Signal": round(verdict.score, 1),
            "Confidence %": round(verdict.confidence, 0),
        }
        for horizon in HORIZONS:
            found = verdict.by_key(horizon.key)
            row[horizon.label] = (found.action if found and found.available
                                  else "—")
        row["Horizons"] = f"{len(verdict.available)}/{len(HORIZONS)}"
        rows.append(row)
    return pd.DataFrame(rows)


@dataclasses.dataclass
class BookSignal:
    """What a whole book reads, and which positions disagree with holding it."""

    counts: dict[str, int]
    score: float              # market-value weighted, -100..+100
    confidence: float         # market-value weighted
    selling: list[str]        # held, but reading SELL or STRONG SELL
    buying: list[str]         # held, and reading BUY or STRONG BUY
    unreadable: list[str]

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def describe(self) -> str:
        parts = [f"{count} {action.lower()}"
                 for action, count in self.counts.items() if count]
        return " · ".join(parts) if parts else "nothing readable"


def book_signal(verdicts: dict[str, UltimateVerdict],
                weights: dict[str, float] | None = None) -> BookSignal:
    """Aggregate a scan into one reading for the whole book.

    Weighted by market value, not by position count: a 40% holding that reads
    SELL is not one vote among eighteen. Confidence is weighted the same way,
    so a book made mostly of symbols nothing could be measured on comes out
    near zero rather than averaging a handful of confident readings into a
    statement about the whole thing.
    """
    counts = {action: 0 for action in ACTIONS}
    selling, buying, unreadable = [], [], []
    weighted_score = weighted_confidence = total_weight = 0.0

    for symbol, verdict in verdicts.items():
        action = verdict.action
        counts[action] = counts.get(action, 0) + 1
        if not verdict.available:
            unreadable.append(symbol)
        if action in (SELL, STRONG_SELL):
            selling.append(symbol)
        elif action in (BUY, STRONG_BUY):
            buying.append(symbol)

        weight = (weights or {}).get(symbol, 1.0)
        if weight > 0:
            total_weight += weight
            weighted_score += weight * verdict.score
            weighted_confidence += weight * verdict.confidence

    if total_weight > 0:
        weighted_score /= total_weight
        weighted_confidence /= total_weight

    return BookSignal(
        counts=counts, score=float(weighted_score),
        confidence=float(weighted_confidence), selling=selling, buying=buying,
        unreadable=unreadable,
    )


def evaluate_offline(
    frame: pd.DataFrame,
    label: str,
    *,
    include_agents: bool = True,
    model: ModelEvidence | None = None,
    interval: str | None = None,
) -> UltimateVerdict:
    """Read every horizon that one already-loaded frame can express.

    The path for bundled CSVs and uploads, which cannot be re-fetched at a
    different resolution. A daily frame answers 1 day and 1 week and declines
    4 hours, which is the honest answer rather than an interpolated one.
    """
    interval = interval or infer_interval(frame["date"])
    verdicts = [
        evaluate_frame(frame, horizon, interval=interval,
                       include_agents=include_agents, model=model)
        for horizon in HORIZONS
    ]
    return combine(label.upper(), verdicts)
