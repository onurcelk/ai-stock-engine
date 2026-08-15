"""Phase 7 — the promotion gate has teeth, and the counting unit is the cutoff.

These tests build their own performance frames.  Nothing here reads
`app/forecast_ledger.sqlite3` (which does not exist), the network, or any
cache — a gate that could only be tested against real outcomes would be a gate
nobody could test before it mattered.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from app.core import model_registry, promotion


# ------------------------------------------------------------------ fixtures


def rows(
    *,
    model_id: str = "neural.lstm",
    horizon: str = "5x1d",
    cutoffs: int = 60,
    symbols: int = 8,
    advantage: float = 0.01,
    spread: float = 0.0005,
    spacing_days: int = 14,
    span_days: int = 7,
    directional: float = 1.0,
) -> pd.DataFrame:
    """A performance frame with a known cutoff geometry and a known advantage.

    `spacing_days` is the gap between consecutive cutoffs and `span_days` the
    length of each forecast window, so the two together decide how many draws
    the frame really contains.
    """
    start = pd.Timestamp("2026-01-05", tz="UTC")
    records = []
    for index in range(cutoffs):
        cutoff = start + pd.Timedelta(days=spacing_days * index)
        # A deterministic alternating wobble, so the between-cutoff spread is
        # real but the mean is exactly `advantage`.
        wobble = spread if index % 2 == 0 else -spread
        for symbol in range(symbols):
            records.append({
                "model_key": model_id,
                "horizon": horizon,
                "symbol": f"SYM{symbol}",
                "cutoff_at": cutoff,
                "matured_at": cutoff + pd.Timedelta(days=span_days),
                "baseline_relative_absolute_error": advantage + wobble,
                "directional_correct": directional,
            })
    return pd.DataFrame(records)


# -------------------------------------------------------------- independence


def test_overlapping_cutoffs_are_not_independent_draws():
    """Two forecasts over the same week resolve against the same price path."""
    frame = rows(cutoffs=60, spacing_days=1, span_days=7)
    evidence = promotion.evidence_for(frame, "neural.lstm", "5x1d")

    assert evidence.n_cutoffs == 60, "sixty distinct cutoff dates were recorded"
    assert evidence.n_independent_cutoffs < 60, (
        "daily cutoffs over a weekly horizon overlap and cannot all be draws")
    # 60 daily cutoffs, each spanning 7 days: one survives per week.
    assert evidence.n_independent_cutoffs == 9


def test_non_overlapping_cutoffs_all_count():
    frame = rows(cutoffs=20, spacing_days=14, span_days=7)
    evidence = promotion.evidence_for(frame, "neural.lstm", "5x1d")

    assert evidence.n_cutoffs == 20
    assert evidence.n_independent_cutoffs == 20


def test_breadth_does_not_manufacture_draws():
    """The lesson that cost Phase 5(a): 30 symbols on one day are one draw."""
    narrow = promotion.evidence_for(
        rows(cutoffs=10, symbols=2), "neural.lstm", "5x1d")
    wide = promotion.evidence_for(
        rows(cutoffs=10, symbols=200), "neural.lstm", "5x1d")

    assert wide.n_rows == 100 * narrow.n_rows
    assert wide.n_independent_cutoffs == narrow.n_independent_cutoffs == 10
    assert wide.advantage_half_width == pytest.approx(
        narrow.advantage_half_width), (
        "the interval must come from the spread between cutoffs, so adding "
        "symbols to each cutoff cannot narrow it")


def test_the_interval_widens_as_cutoffs_are_removed():
    many = promotion.evidence_for(rows(cutoffs=80), "neural.lstm", "5x1d")
    few = promotion.evidence_for(rows(cutoffs=20), "neural.lstm", "5x1d")

    assert few.advantage_half_width > many.advantage_half_width


# --------------------------------------------------------------- the gate


def test_an_empty_ledger_blocks_rather_than_abstains():
    """No record is not a neutral state — it is a failed gate."""
    verdict = promotion.evaluate_promotion(
        "neural.lstm", pd.DataFrame(), "5x1d")

    assert verdict.decision == promotion.BLOCK
    assert not verdict.passed
    names = {gate.name for gate in verdict.failed_gates}
    assert "G4 evidence exists" in names
    assert "G5 resolution" in names


def test_a_thin_record_fails_on_resolution_however_good_it_looks():
    """A huge advantage on twelve cutoffs is still twelve cutoffs."""
    frame = rows(cutoffs=12, advantage=5.0)
    verdict = promotion.evaluate_promotion("neural.lstm", frame, "5x1d")

    assert verdict.decision == promotion.BLOCK
    failed = {gate.name for gate in verdict.failed_gates}
    assert failed == {"G5 resolution"}, (
        "the only thing wrong with this record is that it is too small")


def test_a_resolvable_record_with_real_skill_promotes():
    frame = rows(cutoffs=60, symbols=8, advantage=0.01, spread=0.0005)
    verdict = promotion.evaluate_promotion("neural.lstm", frame, "5x1d")

    assert verdict.decision == promotion.PROMOTE, verdict.explain()
    assert verdict.passed
    assert verdict.evidence.n_independent_cutoffs == 60
    assert verdict.evidence.advantage_lower_bound > 0


def test_skill_that_does_not_clear_zero_is_blocked():
    """A positive point estimate inside a wide interval is not a result."""
    frame = rows(cutoffs=60, advantage=0.0001, spread=0.05)
    verdict = promotion.evaluate_promotion("neural.lstm", frame, "5x1d")

    assert verdict.decision == promotion.BLOCK
    assert {gate.name for gate in verdict.failed_gates} == {
        "G7 skill vs declared baseline"}


def test_a_narrow_record_fails_on_breadth():
    frame = rows(cutoffs=60, symbols=2)
    verdict = promotion.evaluate_promotion("neural.lstm", frame, "5x1d")

    assert verdict.decision == promotion.BLOCK
    assert "G6 breadth" in {gate.name for gate in verdict.failed_gates}


def test_a_pit_inadmissible_model_can_never_be_promoted():
    """No amount of evidence buys production weight for a leaking model."""
    rl = next(spec for spec in model_registry.specs()
              if spec.pit_status == model_registry.PIT_INADMISSIBLE)
    frame = rows(model_id=rl.model_id, cutoffs=200, advantage=1.0, spread=1e-9)

    verdict = promotion.evaluate_promotion(rl.model_id, frame, "5x1d")

    assert verdict.decision == promotion.BLOCK
    assert "G3 point-in-time" in {gate.name for gate in verdict.failed_gates}


def test_an_unregistered_model_is_blocked_not_crashed():
    verdict = promotion.evaluate_promotion(
        "neural.nonexistent", pd.DataFrame(), "5x1d")

    assert verdict.decision == promotion.BLOCK
    assert verdict.evidence is None


# --------------------------------------------------------- maturity discipline


def test_evidence_is_restricted_to_what_had_matured():
    """Performance is knowable at maturity, never at the cutoff."""
    frame = rows(cutoffs=60, spacing_days=14, span_days=7)
    midpoint = frame["matured_at"].min() + pd.Timedelta(days=14 * 20)

    early = promotion.evidence_for(
        frame, "neural.lstm", "5x1d", as_of=midpoint)
    everything = promotion.evidence_for(frame, "neural.lstm", "5x1d")

    assert 0 < early.n_independent_cutoffs < everything.n_independent_cutoffs
    assert early.last_cutoff <= midpoint


def test_a_forecast_that_has_not_matured_contributes_nothing():
    frame = rows(cutoffs=60)
    before_anything = frame["cutoff_at"].min() - pd.Timedelta(days=1)

    evidence = promotion.evidence_for(
        frame, "neural.lstm", "5x1d", as_of=before_anything)

    assert evidence.n_rows == 0
    assert evidence.n_independent_cutoffs == 0


# -------------------------------------------------- RR-1, regime conditioning


def test_regime_conditional_evidence_cannot_promote():
    """The record's five bear-regime rescues, refused structurally.

    This is the exact frame that promotes in
    `test_a_resolvable_record_with_real_skill_promotes`.  The only thing that
    changes is what it was drawn under, and that alone must be decisive —
    otherwise the rule is advice.
    """
    frame = rows(cutoffs=60, symbols=8, advantage=0.01, spread=0.0005)
    verdict = promotion.evaluate_promotion(
        "neural.lstm", frame, "5x1d", evidence_scope="BEAR_TREND")

    assert verdict.decision == promotion.BLOCK, verdict.explain()
    assert {gate.name for gate in verdict.failed_gates} == {
        "G0 unconditional evidence"}
    assert "RR-1.1" in verdict.gates[0].detail


def test_the_regime_gate_is_reached_before_any_statistic_is_computed():
    """RR-1: survival is decided before the split is read.

    A BLOCK that still reported an advantage would be publishing the
    regime-conditional number it just refused to act on, and a reader would
    quote it.  `evidence is None` is the point, not an omission.
    """
    frame = rows(cutoffs=60, symbols=8, advantage=5.0, spread=1e-9)
    verdict = promotion.evaluate_promotion(
        "neural.lstm", frame, "5x1d", evidence_scope="BEAR")

    assert verdict.evidence is None
    assert len(verdict.gates) == 1, (
        "no gate after G0 may be evaluated on regime-restricted evidence")


def test_regime_conditional_evidence_cannot_demote_either():
    """A rule that binds promotion but not demotion has a door in it."""
    frame = rows(model_id=model_registry.ULTIMATE_ENSEMBLE,
                 cutoffs=60, advantage=-0.01, spread=0.0005)

    unconditional = promotion.evaluate_degradation(
        model_registry.ULTIMATE_ENSEMBLE, frame, "5x1d")
    conditional = promotion.evaluate_degradation(
        model_registry.ULTIMATE_ENSEMBLE, frame, "5x1d",
        evidence_scope="BEAR_TREND")

    assert unconditional.decision == promotion.DEGRADED
    assert conditional.decision == promotion.INSUFFICIENT_EVIDENCE, (
        "refusing to read the evidence is not a finding of harm")
    assert conditional.evidence is None


def test_the_regime_gate_can_pass_or_it_guarantees_nothing():
    """The invariant must be capable of both verdicts on the same frame."""
    frame = rows(cutoffs=60, symbols=8, advantage=0.01, spread=0.0005)

    passed = promotion.evaluate_promotion(
        "neural.lstm", frame, "5x1d",
        evidence_scope=promotion.UNCONDITIONAL)

    assert passed.decision == promotion.PROMOTE, passed.explain()
    assert passed.gates[0].name == "G0 unconditional evidence"
    assert passed.gates[0].passed


def test_the_default_scope_is_unconditional():
    """The honest call is the short one; declaring a regime is the extra act."""
    frame = rows(cutoffs=60, symbols=8, advantage=0.01, spread=0.0005)

    assert promotion.evaluate_promotion("neural.lstm", frame, "5x1d") == (
        promotion.evaluate_promotion(
            "neural.lstm", frame, "5x1d",
            evidence_scope=promotion.UNCONDITIONAL))


@pytest.mark.parametrize("scope", [None, "", "   ", 3])
def test_an_unstated_scope_is_refused_rather_than_assumed(scope):
    """Absence is not a scope. Defaulting it to unconditional would be a bet."""
    frame = rows(cutoffs=60)

    with pytest.raises(promotion.PromotionError, match="evidence_scope"):
        promotion.evaluate_promotion(
            "neural.lstm", frame, "5x1d", evidence_scope=scope)
    with pytest.raises(promotion.PromotionError, match="evidence_scope"):
        promotion.evaluate_degradation(
            model_registry.ULTIMATE_ENSEMBLE, frame, "5x1d",
            evidence_scope=scope)


def test_an_unregistered_model_still_reports_the_scope_gate():
    """Every promotion verdict carries G0, including the early returns."""
    verdict = promotion.evaluate_promotion(
        "neural.nonexistent", pd.DataFrame(), "5x1d")

    assert verdict.gates[0].name == "G0 unconditional evidence"
    assert verdict.decision == promotion.BLOCK


# ------------------------------------------------------------- degradation


def test_an_unresolvable_record_is_not_a_finding_of_harm():
    """"We cannot tell" and "it is bad" are different verdicts."""
    frame = rows(model_id=model_registry.ULTIMATE_ENSEMBLE,
                 cutoffs=12, advantage=-5.0, spread=0.0005)
    verdict = promotion.evaluate_degradation(
        model_registry.ULTIMATE_ENSEMBLE, frame, "5x1d")

    # The evidence is damning and the model is still not degraded, because
    # twelve cutoffs cannot carry the claim.  Asserting the count as well
    # stops this passing merely because the frame was empty.
    assert verdict.evidence.n_independent_cutoffs == 12
    assert verdict.evidence.advantage_upper_bound < 0
    assert verdict.decision == promotion.INSUFFICIENT_EVIDENCE


def test_a_resolvably_worse_model_is_degraded():
    frame = rows(model_id=model_registry.ULTIMATE_ENSEMBLE,
                 cutoffs=60, advantage=-0.01, spread=0.0005)
    verdict = promotion.evaluate_degradation(
        model_registry.ULTIMATE_ENSEMBLE, frame, "5x1d")

    assert verdict.decision == promotion.DEGRADED


def test_a_model_that_merely_fails_to_shine_is_held_not_degraded():
    frame = rows(model_id=model_registry.ULTIMATE_ENSEMBLE,
                 cutoffs=60, advantage=0.0, spread=0.0005)
    verdict = promotion.evaluate_degradation(
        model_registry.ULTIMATE_ENSEMBLE, frame, "5x1d")

    assert verdict.decision == promotion.HOLD


# --------------------------------------------------------------- invariants


def test_every_production_model_is_declared():
    """The structural gate: production status cannot be acquired quietly."""
    promotion.assert_production_is_declared()
    assert promotion.undeclared_production_models() == ()


def test_adding_a_production_model_without_declaring_it_fails(monkeypatch):
    """The invariant above must be capable of failing, or it guarantees nothing."""
    monkeypatch.setitem(
        promotion.GRANDFATHERED, model_registry.ULTIMATE_ENSEMBLE, "")
    monkeypatch.delitem(
        promotion.GRANDFATHERED, model_registry.ULTIMATE_ENSEMBLE)

    with pytest.raises(promotion.PromotionError, match="without a Phase 7"):
        promotion.assert_production_is_declared()


def test_nothing_has_been_promoted_on_evidence():
    """True at Phase 7, and the reason is the empty ledger, not an oversight."""
    assert promotion.PROMOTED == {}


def test_the_grandfathered_list_names_the_incumbent_debt_separately():
    reasons = set(promotion.GRANDFATHERED.values())
    assert len(reasons) == 2, (
        "closed-form components and the adapting incumbent are tolerated for "
        "different reasons and must not share one blanket excuse")
    assert "Phase 11" in promotion.GRANDFATHERED[model_registry.ULTIMATE_ENSEMBLE]


def test_the_gate_decides_and_never_acts():
    """A verdict must not be able to change a status."""
    before = {spec.model_id: spec.production_status
              for spec in model_registry.specs()}
    frame = rows(cutoffs=60, symbols=8, advantage=0.01, spread=0.0005)

    promotion.evaluate_promotion("neural.lstm", frame, "5x1d")
    promotion.evaluate_degradation(model_registry.ULTIMATE_ENSEMBLE, frame, "5x1d")

    after = {spec.model_id: spec.production_status
             for spec in model_registry.specs()}
    assert before == after


def test_the_policy_is_reportable_as_data():
    """Phase 8 renders this; it must not have to parse a docstring."""
    policy = promotion.policy()

    assert policy["min_independent_cutoffs"] == 50
    assert policy["undeclared"] == ()
    assert policy["promoted"] == {}
    assert model_registry.ULTIMATE_ENSEMBLE in policy["grandfathered"]
    assert policy["evidence_scope"] == promotion.UNCONDITIONAL
    assert policy["policy_version"] == promotion.POLICY_VERSION


def test_the_verdict_explains_itself_line_by_line():
    verdict = promotion.evaluate_promotion(
        "neural.lstm", pd.DataFrame(), "5x1d")
    explanation = verdict.explain()

    assert "BLOCK" in explanation
    assert explanation.count("[PASS]") + explanation.count("[FAIL]") == len(
        verdict.gates)
