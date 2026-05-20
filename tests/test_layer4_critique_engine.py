from types import SimpleNamespace

from engine.Layer4_Analysis.core.critique_engine import build_improvement_feedback, critique_minister_output


def test_critique_engine_flags_missing_core_reasoning_fields():
    parsed = {
        "risk_level_adjustment": "increase",
        "primary_drivers": [],
        "critical_gaps": [],
        "counterarguments": [],
        "confidence_modifier": 0.04,
        "justification_strength": 0.02,
        "rationale": "",
    }
    report = SimpleNamespace(predicted_signals=["SIG_MIL_MOBILIZATION"])
    full_context = SimpleNamespace(gaps=["Need fresher logistics evidence"])

    result = critique_minister_output(parsed, report, full_context)
    feedback = build_improvement_feedback(result)

    assert result.issues_found is True
    assert result.should_retry is True
    assert "primary_drivers is empty" in result.critical_issues
    assert "Improve only these areas." in feedback
