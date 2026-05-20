from types import SimpleNamespace

from engine.Layer4_Analysis.core.intelligence_controller import (
    decide_effort,
    recommend_stage_output_budget,
    stage_budget_instruction,
)


def test_decide_effort_goes_high_for_complex_uncertain_context():
    session = SimpleNamespace(
        state_context=SimpleNamespace(
            actors=SimpleNamespace(subject_country="IND", target_country="CHN", ally_country="USA")
        ),
        hypotheses=[
            SimpleNamespace(coverage=0.22),
            SimpleNamespace(coverage=0.31),
        ],
    )
    full_context = SimpleNamespace(
        signal_confidence={
            "SIG_MIL_MOBILIZATION": 0.22,
            "SIG_DIP_HOSTILITY": 0.28,
            "SIG_ECONOMIC_PRESSURE": 0.35,
            "SIG_INTERNAL_INSTABILITY": 0.19,
            "SIG_FORCE_POSTURE": 0.26,
        },
        contradictions=["a", "b", "c"],
        gaps=["x", "y", "z"],
        escalation_score=0.78,
    )

    decision = decide_effort(session, full_context)

    assert decision.level == "high"
    assert decision.recommended_max_tokens == 3000
    assert decision.score > 0.70


def test_stage_budget_scales_minister_reasoning_by_effort():
    decision = type("Decision", (), {"level": "low"})()
    assert recommend_stage_output_budget("minister_reasoning", 3000, effort=decision) == 1200

    decision.level = "medium"
    assert recommend_stage_output_budget("minister_reasoning", 3000, effort=decision) == 2400

    decision.level = "high"
    assert recommend_stage_output_budget("minister_reasoning", 3000, effort=decision) == 3000


def test_red_team_budget_drops_when_no_disagreement():
    assert recommend_stage_output_budget("red_team", 1800, disagreement_detected=False) == 1000
    assert recommend_stage_output_budget("red_team", 1800, disagreement_detected=True) == 1800


def test_stage_budget_instruction_mentions_conciseness():
    decision = type("Decision", (), {"level": "medium"})()
    instruction = stage_budget_instruction("minister_reasoning", effort=decision)
    assert "220 words or fewer" in instruction
    assert "short and focused" in instruction
