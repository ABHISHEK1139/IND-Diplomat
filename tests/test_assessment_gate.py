"""Tests for the Assessment Gate — deterministic verdict rules."""
from dip.pipeline.forecasting.trajectory.assessment_gate import (
    AssessmentState,
    GateVerdict,
    assess,
    build_assessment_state,
    _check_critical_pirs,
    _check_capability_coverage,
    _check_stale_military,
    _check_confidence,
    _check_trend_escalation,
)


class TestGateRules:
    """Test each WITHHOLD rule individually."""

    def test_rule1_critical_pirs_triggers_withhold(self):
        state = AssessmentState(critical_pirs=3)
        assert _check_critical_pirs(state) is not None

    def test_rule1_low_pirs_passes(self):
        state = AssessmentState(critical_pirs=2)
        assert _check_critical_pirs(state) is None

    def test_rule2_low_capability_triggers_withhold(self):
        state = AssessmentState(capability_coverage=0.20)
        assert _check_capability_coverage(state) is not None

    def test_rule2_good_capability_passes(self):
        state = AssessmentState(capability_coverage=0.50)
        assert _check_capability_coverage(state) is None

    def test_rule3_stale_military_triggers_withhold(self):
        state = AssessmentState(stale_military_signals=["SIG_TROOP_MOVEMENT"])
        assert _check_stale_military(state) is not None

    def test_rule3_no_stale_passes(self):
        state = AssessmentState(stale_military_signals=[])
        assert _check_stale_military(state) is None

    def test_rule4_low_confidence_triggers_withhold(self):
        state = AssessmentState(analytic_confidence=0.40)
        assert _check_confidence(state) is not None

    def test_rule4_good_confidence_passes(self):
        state = AssessmentState(analytic_confidence=0.70)
        assert _check_confidence(state) is None

    def test_rule5_trend_escalation_triggers(self):
        state = AssessmentState(momentum=0.40, persistence=0.85)
        assert _check_trend_escalation(state) is not None

    def test_rule5_normal_trend_passes(self):
        state = AssessmentState(momentum=0.20, persistence=0.50)
        assert _check_trend_escalation(state) is None


class TestGateVerdict:
    """Test full assess() function."""

    def test_all_clear_approves(self):
        state = AssessmentState(
            capability_coverage=0.60,
            intent_coverage=0.50,
            analytic_confidence=0.75,
            proposed_decision="HIGH",
            sre_score=0.70,
        )
        verdict = assess(state)
        assert verdict.approved is True
        assert verdict.withheld is False
        assert verdict.decision == "HIGH"

    def test_low_capability_withholds(self):
        state = AssessmentState(
            capability_coverage=0.20,
            analytic_confidence=0.75,
            proposed_decision="HIGH",
        )
        verdict = assess(state)
        assert verdict.approved is False
        assert verdict.withheld is True
        assert verdict.decision == "WITHHELD"
        assert len(verdict.collection_tasks) > 0

    def test_low_confidence_withholds(self):
        state = AssessmentState(
            capability_coverage=0.60,
            analytic_confidence=0.40,
            proposed_decision="HIGH",
        )
        verdict = assess(state)
        assert verdict.approved is False

    def test_trend_override_elevates_low(self):
        state = AssessmentState(
            capability_coverage=0.60,
            analytic_confidence=0.75,
            proposed_decision="LOW",
            momentum=0.45,
            persistence=0.90,
        )
        verdict = assess(state)
        assert verdict.approved is True
        assert verdict.decision == "ELEVATED"

    def test_to_dict_serializable(self):
        state = AssessmentState(
            capability_coverage=0.60,
            proposed_decision="ELEVATED",
            analytic_confidence=0.65,
        )
        verdict = assess(state)
        d = verdict.to_dict()
        assert d["approved"] is True
        assert isinstance(d["reasons"], list)
        assert isinstance(d["collection_tasks"], list)
        import json
        json.dumps(d)  # must not raise
