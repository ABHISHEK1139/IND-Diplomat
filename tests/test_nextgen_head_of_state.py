from pathlib import Path
from types import SimpleNamespace

from dip.core.schema import NextGenSREOutput, Signal, StateContext
from dip.nextgen.assessment_graph import HeadOfStatePipelineGraph, PipelinePhase
from dip.nextgen.contracts import AdvisoryMode, create_assessment_goal
from dip.nextgen.oss_adapters import OSSAdapterRegistry
from dip.nextgen.briefing import build_head_of_country_briefing
from dip.nextgen.perception import compute_strategic_pressure
from dip.nextgen.sre import (
    falling,
    project_state_to_observed_signals,
    rising,
    run_fuzzy_sre,
    trapezoidal,
    triangular,
)


def test_assessment_goal_defaults_are_head_of_state_safe():
    goal = create_assessment_goal(
        "Assess escalation risk and options",
        country="ind",
        mode=AdvisoryMode.OPTIONS_ANALYSIS,
    )

    assert goal.country == "IND"
    assert goal.trace_id.startswith("dip2-")
    assert any(boundary.name == "human_authority" for boundary in goal.safety_boundaries)
    assert "explicit uncertainty and blindspots" in goal.success_criteria


def test_pipeline_graph_creates_blackboard_and_checkpoint(tmp_path: Path):
    graph = HeadOfStatePipelineGraph(checkpoint_dir=tmp_path)
    goal, blackboard = graph.start("Brief the PM on border escalation", country="IND")

    assert blackboard.trace_id == goal.trace_id
    assert blackboard.history(PipelinePhase.GOAL_INTAKE)[0].event_type == "goal.created"
    assert (tmp_path / goal.trace_id / "goal_intake.json").exists()


def test_oss_adapter_registry_reports_replacement_map():
    registry = OSSAdapterRegistry()
    replacement_map = registry.replacement_map()
    status = registry.status()

    assert replacement_map
    assert any(row["name"] == "NetworkX" for row in status)
    assert all("installed" in row for row in status)


def test_strategic_pressure_reads_world_signals():
    state_context = SimpleNamespace(
        current_signals=[
            SimpleNamespace(action="SIG_MIL_MOBILIZATION", confidence=0.9, intensity=0.8, domain="military"),
            SimpleNamespace(action="SIG_LOGISTICS_PREP", confidence=0.8, intensity=0.7, domain="military"),
            SimpleNamespace(action="SIG_DIPLOMACY_ACTIVE", confidence=0.5, intensity=0.5, domain="diplomatic"),
        ],
        beliefs=[],
        escalation=SimpleNamespace(escalation_score=0.72, threat_level="HIGH", domain_indices=None),
        confidence_decay=0.7,
        data_blindspots=["diplomatic_source_gap"],
    )

    pressure = compute_strategic_pressure(state_context, {"threat_level": "HIGH"})

    assert pressure.tension > 0.6
    assert pressure.urgency > 0.6
    assert pressure.uncertainty > 0.2
    assert "SIG_MIL_MOBILIZATION" in pressure.drivers


def test_head_of_country_briefing_contains_decision_ready_sections():
    goal = create_assessment_goal("Assess escalation options", country="IND")
    state_context = SimpleNamespace(
        current_signals=[
            SimpleNamespace(action="SIG_MIL_MOBILIZATION", confidence=0.9, intensity=0.8, domain="military"),
        ],
        beliefs=[
            SimpleNamespace(signal_code="SIG_MIL_MOBILIZATION", support_score=0.81, belief_level="strong", source_count=2),
        ],
        escalation=SimpleNamespace(
            escalation_score=0.72,
            threat_level="HIGH",
            domain_indices=SimpleNamespace(capability=0.8, intent=0.6, instability=0.3, cost=0.4),
        ),
        confidence_decay=0.75,
        data_blindspots=["economic_followup"],
    )
    result = {
        "trace_id": goal.trace_id,
        "status": "COMPLETE",
        "threat_level": "HIGH",
        "verification_score": 0.74,
        "red_team_report": ["Mobilization may be defensive signaling."],
    }

    briefing = build_head_of_country_briefing(goal, state_context, result)

    assert briefing.executive_summary
    assert briefing.options
    assert briefing.required_human_decisions
    assert briefing.fuzzy_trace["sre_escalation_score"] == 0.72
    assert briefing.risk_matrix["knowledge_graph"]["nodes"]


def test_fuzzy_membership_primitives_are_clamped_and_shaped():
    assert triangular(-1, 0.0, 0.5, 1.0) == 0.0
    assert triangular(0.5, 0.0, 0.5, 1.0) == 1.0
    assert trapezoidal(0.5, 0.1, 0.3, 0.7, 0.9) == 1.0
    assert rising(2, 0.2, 0.8) == 1.0
    assert falling(2, 0.2, 0.8) == 0.0


def test_projected_signal_confidence_uses_dip8_style_multiplication():
    state_context = SimpleNamespace(
        current_signals=[
            SimpleNamespace(
                action="SIG_MIL_MOBILIZATION",
                confidence=0.9,
                intensity=0.82,
                source_ref="GOV_border_report",
                domain="military",
                timestamp=None,
            ),
        ],
        beliefs=[],
        temporal_indicators=[],
        active_conflicts=[],
        confidence_decay=1.0,
    )

    projected = project_state_to_observed_signals(state_context)

    assert projected[0].signal_code == "MIL_MOBILIZATION"
    assert projected[0].membership == 1.0
    assert projected[0].reliability == 0.75
    assert projected[0].evidence_support == 0.9
    assert projected[0].confidence == 0.675


def test_nextgen_sre_excludes_legal_rag_signals_from_domain_fusion():
    state_context = SimpleNamespace(
        current_signals=[
            SimpleNamespace(
                action="SIG_MIL_MOBILIZATION",
                confidence=0.95,
                intensity=0.95,
                source_ref="LEGAL_RAG_treaty_memo",
                domain="legal",
                timestamp=None,
            ),
        ],
        beliefs=[],
        temporal_indicators=[],
        active_conflicts=[],
        confidence_decay=1.0,
    )

    assessment = run_fuzzy_sre(state_context)

    assert assessment.projected_signals[0].excluded_from_sre is True
    assert assessment.legal_firewall_rejections
    assert assessment.sre_domains.capability == 0.0
    assert assessment.sre_escalation_score < 0.30


def test_nextgen_sre_mobilization_and_logistics_triggers_raise_risk():
    state_context = SimpleNamespace(
        current_signals=[
            SimpleNamespace(action="SIG_MIL_MOBILIZATION", confidence=0.95, intensity=0.95, source_ref="SENSOR_satellite", domain="military"),
            SimpleNamespace(action="SIG_LOGISTICS_PREP", confidence=0.88, intensity=0.90, source_ref="SIGINT_rail", domain="military"),
            SimpleNamespace(action="SIG_HOSTILITY", confidence=0.80, intensity=0.75, source_ref="NEWS_border", domain="diplomatic"),
        ],
        beliefs=[],
        temporal_indicators=[SimpleNamespace(signal="SIG_MIL_MOBILIZATION", trend_label="accelerating", is_spike=True, spike_severity=3.0, persistence=0.8)],
        active_conflicts=[],
        confidence_decay=1.0,
    )

    assessment = run_fuzzy_sre(state_context)

    assert assessment.sre_input.mobilization_trigger is True
    assert assessment.sre_input.logistics_trigger is True
    assert assessment.risk_level in {"HIGH", "CRITICAL"}
    assert any(step["step"] == "mobilization_trigger" for step in assessment.escalation_trace)


def test_nextgen_sre_active_conflict_prevents_low_output():
    state_context = SimpleNamespace(
        current_signals=[],
        beliefs=[],
        temporal_indicators=[],
        active_conflicts=["ACTIVE_CONFLICT_BORDER"],
        confidence_decay=1.0,
    )

    assessment = run_fuzzy_sre(state_context)

    assert assessment.sre_input.conflict_floor_applied is True
    assert assessment.sre_escalation_score == 0.50
    assert assessment.risk_level == "ELEVATED"


def test_core_state_context_accepts_nextgen_sre_contract():
    context = StateContext(
        country="IND",
        current_signals=[
            Signal(
                entity="Border Command",
                action="SIG_MIL_MOBILIZATION",
                intensity=0.90,
                confidence=0.90,
                source_ref="SENSOR_satellite",
                domain="military",
            )
        ],
    )

    assessment = run_fuzzy_sre(context)
    context.nextgen_sre = NextGenSREOutput(**assessment.model_dump(mode="json"))

    assert context.nextgen_sre is not None
    assert context.nextgen_sre.projected_signals[0].signal_code == "MIL_MOBILIZATION"
    assert context.nextgen_sre.sre_domains.capability > 0.0
    assert context.model_dump(mode="json")["nextgen_sre"]["risk_level"] in {"LOW", "MODERATE", "ELEVATED", "HIGH", "CRITICAL"}
