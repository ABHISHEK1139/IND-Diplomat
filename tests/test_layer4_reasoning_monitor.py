from engine.Layer4_Analysis.core.reasoning_monitor import (
    analyze_output,
    build_adjustment_feedback,
    recommend_adjusted_budget,
)


def test_reasoning_monitor_flags_overthinking_for_long_low_density_output():
    output_text = " ".join(["analysis"] * 420)
    structured = {
        "primary_drivers": ["Driver A"],
        "critical_gaps": [],
        "counterarguments": [],
        "justification_strength": 0.62,
    }

    analysis = analyze_output(
        output_text=output_text,
        structured=structured,
        max_tokens=300,
        predicted_signals=["SIG_DIP_HOSTILITY"],
    )

    assert analysis.overthinking is True
    assert analysis.should_retry is True
    assert "overthinking_detected" in analysis.issues
    assert "condense" in build_adjustment_feedback(analysis).lower()


def test_reasoning_monitor_flags_underthinking_for_thin_output():
    output_text = "Minimal answer with one point."
    structured = {
        "primary_drivers": ["Driver A"],
        "critical_gaps": [],
        "counterarguments": [],
        "justification_strength": 0.22,
    }

    analysis = analyze_output(
        output_text=output_text,
        structured=structured,
        max_tokens=1200,
        predicted_signals=["SIG_MIL_MOBILIZATION"],
    )

    assert analysis.underthinking is True
    assert analysis.should_retry is True
    assert "underthinking_detected" in analysis.issues
    assert recommend_adjusted_budget(1200, hard_cap=3000, analysis=analysis) > 1200


def test_reasoning_monitor_accepts_balanced_output():
    output_text = (
        "Drivers include coercive bargaining, rising hostility, and force posture changes. "
        "Gaps remain in logistics confirmation, but counterarguments include ongoing diplomacy."
    )
    structured = {
        "primary_drivers": ["Coercive bargaining", "Hostility", "Force posture"],
        "critical_gaps": ["Need logistics confirmation"],
        "counterarguments": ["Diplomacy remains active"],
        "justification_strength": 0.71,
    }

    analysis = analyze_output(
        output_text=output_text,
        structured=structured,
        max_tokens=2400,
        predicted_signals=["SIG_COERCIVE_BARGAINING", "SIG_FORCE_POSTURE"],
    )

    assert analysis.overthinking is False
    assert analysis.underthinking is False
    assert analysis.should_retry is False
    assert analysis.quality_score > 0.4
