import pytest

from dip.core.schema import MinisterHypothesisOutput, Signal, StateContext
from dip.pipeline.deliberation.reasoning.ministers.security_minister import SecurityMinister
from dip.engines.structured_llm import parse_model
from dip.engines.symbolic_guardrails import run_symbolic_guardrails


def test_parse_model_validates_structured_minister_output():
    parsed = parse_model(
        """
        {
          "predicted_signals": ["mobilization"],
          "matched_signals": ["SIG_MIL_MOBILIZATION"],
          "missing_signals": [],
          "confidence": 0.7,
          "rationale": "Matched mobilization.",
          "critical_signal_refs": []
        }
        """,
        MinisterHypothesisOutput,
    )

    assert parsed.confidence == 0.7
    assert parsed.predicted_signals == ["mobilization"]


@pytest.mark.asyncio
async def test_minister_llm_refinement_is_bounded_without_critical_refs(monkeypatch):
    minister = SecurityMinister()
    context = StateContext(
        country="IND",
        current_signals=[
            Signal(
                entity="Military Command",
                action="SIG_MIL_MOBILIZATION",
                intensity=0.7,
                confidence=0.7,
                source_ref="SENSOR_test",
                domain="military",
            )
        ],
    )

    async def fake_refinement(_ctx, _heuristic):
        return MinisterHypothesisOutput(
            predicted_signals=["mobilization", "combat readiness"],
            matched_signals=["SIG_MIL_MOBILIZATION"],
            missing_signals=[],
            confidence=0.99,
            rationale="Too confident without critical refs.",
            critical_signal_refs=[],
        )

    monkeypatch.setattr(minister, "_llm_refinement", fake_refinement)
    hypothesis = await minister.produce_hypothesis(context)

    assert hypothesis.decision_mode == "bounded_llm_refinement"
    assert hypothesis.llm_confidence == 0.99
    assert hypothesis.confidence <= hypothesis.heuristic_confidence + 0.151
    assert hypothesis.disagreement_notes


@pytest.mark.asyncio
async def test_minister_allows_large_refinement_with_critical_refs(monkeypatch):
    minister = SecurityMinister()
    context = StateContext(
        country="IND",
        current_signals=[
            Signal(
                entity="Border Unit",
                action="SIG_KINETIC_ACTIVITY",
                intensity=0.9,
                confidence=0.9,
                source_ref="SENSOR_test",
                domain="military",
            )
        ],
    )

    async def fake_refinement(_ctx, _heuristic):
        return MinisterHypothesisOutput(
            predicted_signals=["kinetic activity"],
            matched_signals=["SIG_KINETIC_ACTIVITY"],
            missing_signals=[],
            confidence=0.92,
            rationale="Critical signal observed.",
            critical_signal_refs=["SIG_KINETIC_ACTIVITY"],
        )

    monkeypatch.setattr(minister, "_llm_refinement", fake_refinement)
    hypothesis = await minister.produce_hypothesis(context)

    assert hypothesis.decision_mode == "llm_refined_within_bounds"
    assert hypothesis.confidence == 0.92
    assert hypothesis.disagreement_notes


def test_symbolic_guardrails_catch_low_narrative_high_sre_contradiction():
    report = run_symbolic_guardrails(
        {
            "threat_level": "LOW",
            "verification_score": 0.9,
            "fuzzy_trace": {"sre_escalation_score": 0.8},
        }
    )

    assert report.passed is False
    assert any(finding.rule == "risk_band_sre_contradiction" for finding in report.findings)
