from types import SimpleNamespace

from engine.Layer6_Learning import calibration_engine
from engine.Layer6_Learning.self_directed_learning import (
    SelfDirectedLearningAgent,
    assess_self_directed_learning,
)


def _session():
    return SimpleNamespace(
        session_id="sdl-test-1",
        learning_country="IND",
        final_confidence=0.41,
        epistemic_confidence=0.33,
        sensor_confidence=0.52,
        gate_verdict=SimpleNamespace(
            passed=False,
            reasons=["confidence below floor", "stale military evidence"],
        ),
        state_context=SimpleNamespace(
            actors=SimpleNamespace(subject_country="IND"),
            meta=SimpleNamespace(source_count=2),
        ),
        hypotheses=[
            SimpleNamespace(coverage=0.21),
            SimpleNamespace(coverage=0.34),
        ],
        missing_signals=[
            "SIG_MIL_MOBILIZATION",
            "SIG_FORCE_POSTURE",
            "SIG_DIP_HOSTILITY",
        ],
        investigation_needs=["SIG_LOGISTICS_PREP"],
        identified_conflicts=["military posture conflicts with diplomatic calm"],
        full_context=SimpleNamespace(
            signal_confidence={
                "SIG_MIL_MOBILIZATION": 0.22,
                "SIG_FORCE_POSTURE": 0.31,
                "SIG_ECONOMIC_PRESSURE": 0.72,
            },
            contradictions=["source A says mobilization, source B denies"],
            gaps=["no fresh border posture data"],
        ),
        ministers_reports=[
            SimpleNamespace(
                reasoning_monitor_issues=["low signal density"],
                self_critique_issues=[],
                classification_degraded=False,
                reasoning_degraded=True,
            )
        ],
    )


def test_self_directed_learning_creates_goals_and_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        calibration_engine,
        "calibration_score",
        lambda country=None: {
            "tier": "MISCALIBRATED",
            "avg_brier": 0.31,
            "n_resolved": 24,
            "min_required": 20,
            "eligible": True,
        },
    )

    agent = SelfDirectedLearningAgent(memory_path=str(tmp_path / "memory.json"))
    cycle = agent.reflect(_session(), persist=True)

    trigger_kinds = {trigger.kind for trigger in cycle.triggers}
    goal_kinds = {goal.kind for goal in cycle.selected_goals}

    assert "evidence_gap" in trigger_kinds
    assert "gate_failure" in trigger_kinds
    assert "calibration_error" in trigger_kinds
    assert "model_calibration" in goal_kinds
    assert "gate_recovery" in goal_kinds
    assert cycle.human_approval_required is True
    assert cycle.memory_summary["stored_goals"] >= len(cycle.selected_goals)


def test_assess_self_directed_learning_can_run_without_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr(
        calibration_engine,
        "calibration_score",
        lambda country=None: {
            "tier": "INSUFFICIENT",
            "avg_brier": None,
            "n_resolved": 2,
            "min_required": 20,
            "eligible": False,
        },
    )

    result = assess_self_directed_learning(
        _session(),
        persist=False,
        memory_path=str(tmp_path / "memory.json"),
    )

    assert result["autonomy_level"] == "bounded_assistive"
    assert result["country"] == "IND"
    assert result["selected_goals"]
    assert result["memory_summary"]["stored_goals"] == 0
