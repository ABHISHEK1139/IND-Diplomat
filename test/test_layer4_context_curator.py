from types import SimpleNamespace

from engine.Layer4_Analysis.core.context_curator import build_minister_reasoning_pack
from engine.Layer4_Analysis.core.llm_client import LocalLLM, _extract_structured_json_text


def _fake_state():
    actors = SimpleNamespace(subject_country="IND", target_country="PAK")
    military = SimpleNamespace(mobilization_level=0.72, clash_history=3, exercises=2)
    diplomatic = SimpleNamespace(hostility_tone=0.81, negotiations=0.22, alliances=0.61)
    economic = SimpleNamespace(sanctions=0.48, trade_dependency=0.31, economic_pressure=0.57)
    domestic = SimpleNamespace(regime_stability=0.43, unrest=0.52, protests=0.21)
    observation_quality = SimpleNamespace(is_observed=True)
    signal_confidence = {
        "SIG_MIL_MOBILIZATION": 0.82,
        "SIG_DIP_HOSTILITY": 0.74,
        "SIG_ECONOMIC_PRESSURE": 0.63,
        "SIG_INTERNAL_INSTABILITY": 0.41,
    }
    signal_evidence = {
        "SIG_MIL_MOBILIZATION": [
            {
                "source": "satellite-watch",
                "publication_date": "2026-03-29T00:00:00+00:00",
                "excerpt": "Troop movement observed near the frontier.",
                "confidence": 0.88,
            }
        ],
        "SIG_ECONOMIC_PRESSURE": [
            {
                "source": "finance-monitor",
                "publication_date": "2026-03-27T00:00:00+00:00",
                "excerpt": "Trade and sanctions pressure increased.",
                "confidence": 0.71,
            }
        ],
    }
    evidence = SimpleNamespace(signal_provenance={})
    return SimpleNamespace(
        actors=actors,
        military=military,
        diplomatic=diplomatic,
        economic=economic,
        domestic=domestic,
        observation_quality=observation_quality,
        signal_confidence=signal_confidence,
        signal_evidence=signal_evidence,
        evidence=evidence,
        pressures={
            "intent_pressure": 0.68,
            "capability_pressure": 0.79,
            "stability_pressure": 0.34,
            "economic_pressure": 0.58,
        },
        risk_level="ELEVATED",
        capability_index=0.71,
        intent_index=0.66,
        stability_index=0.38,
        cost_index=0.44,
    )


def test_context_curator_is_role_specific_and_budgeted():
    state = _fake_state()
    session = SimpleNamespace(question="What is driving India-Pakistan tensions?", state_context=state)
    full_context = SimpleNamespace(
        gaps=["SIG_INTERNAL_INSTABILITY needs fresher evidence"],
        contradictions=["SIG_DIP_HOSTILITY and SIG_DIPLOMACY_ACTIVE are both elevated"],
        trajectory={"prob_up": 0.64, "prob_stable": 0.21, "velocity": 0.58},
        escalation_score=0.73,
    )
    report = SimpleNamespace(predicted_signals=["SIG_MIL_MOBILIZATION", "SIG_DIP_HOSTILITY"])

    security_pack = build_minister_reasoning_pack(
        minister_name="Security Minister",
        session=session,
        full_context=full_context,
        report=report,
        output_schema='{"risk_level_adjustment":"increase|decrease|maintain"}',
    )
    economic_pack = build_minister_reasoning_pack(
        minister_name="Economic Minister",
        session=session,
        full_context=full_context,
        report=report,
        output_schema='{"risk_level_adjustment":"increase|decrease|maintain"}',
    )

    assert security_pack.estimated_tokens <= security_pack.input_budget
    assert economic_pack.estimated_tokens <= economic_pack.input_budget
    assert security_pack.rendered_prompt != economic_pack.rendered_prompt
    assert "SIG_MIL_MOBILIZATION" in security_pack.rendered_prompt


def test_stage_budget_rejects_large_prompt_before_network():
    llm = LocalLLM(provider="openrouter", model="nvidia/nemotron-3-super-120b-a12b:free")
    huge_prompt = "signal " * 10000
    result = llm.generate(
        system_prompt="Classify the current state.",
        user_prompt=huge_prompt,
        json_mode=True,
        task_type="classification",
    )
    assert "INPUT_BUDGET_EXCEEDED" in result


def test_openrouter_window_overflow_fails_instead_of_middle_trimming():
    llm = LocalLLM(provider="openrouter", model="custom/unknown-window")
    llm.openrouter_api_key = "test-key"
    very_large_prompt = "X" * 280000
    result = llm.generate(
        system_prompt="Respond briefly.",
        user_prompt=very_large_prompt,
        json_mode=False,
        task_type=None,
        max_tokens=512,
    )
    assert "PROVIDER_WINDOW_EXCEEDED" in result
    assert "AUTO-COMPACTED" not in result


def test_json_normalizer_keeps_only_structure():
    raw = '<think>hidden</think>Lead text {"risk":"HIGH","rationale":"brief"} trailing text'
    normalized = _extract_structured_json_text(raw)
    assert normalized == '{"risk":"HIGH","rationale":"brief"}'
