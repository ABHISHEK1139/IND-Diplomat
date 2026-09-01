"""
E2E Integration Tests — DIP 2.1

Comprehensive end-to-end tests covering:
  - Full pipeline with heuristic mode
  - Strategic narrative synthesis
  - STIX2 export
  - Step tracer
  - Deliberation module heuristic fallbacks
"""

import asyncio
import json
import os
import sys
import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FORCE_MINISTER_HEURISTIC"] = "1"


@pytest.mark.asyncio
async def test_full_pipeline_heuristic_completes():
    """Pipeline must complete without hanging in heuristic mode."""
    from dip.unified_pipeline import execute
    
    result = await execute(
        query="Assess India-Pakistan border tensions",
        country_code="IN",
        job_id="e2e-test-001",
    )
    
    assert result["status"] in ("COMPLETE", "WITHHELD", "HUMAN_REVIEW", "REFUSED")
    assert result["trace_id"].startswith("dip2-")
    assert result["elapsed_seconds"] > 0
    assert len(result.get("hypotheses", [])) >= 0


@pytest.mark.asyncio
async def test_strategic_narrative_generated():
    """Strategic narrative must be present with all required keys."""
    from dip.unified_pipeline import execute
    
    result = await execute(
        query="China Taiwan strait military activity",
        country_code="CN",
        job_id="e2e-test-002",
    )
    
    narrative = result.get("strategic_narrative")
    assert narrative is not None, "Strategic narrative missing"
    assert "executive_summary" in narrative
    assert "threat_assessment" in narrative
    assert "evidence" in narrative
    assert "forecast" in narrative
    assert "recommendations" in narrative
    assert narrative["generation_mode"] == "modular_heuristic"


@pytest.mark.asyncio
async def test_stix2_export_generated():
    """STIX2 bundle must be present and valid."""
    from dip.unified_pipeline import execute
    from unittest.mock import patch
    from dip.runtime.control_loop.investigation_controller import InvestigationController
    
    async def mock_run_loop(self, state_context, goal, query, country_code, result_dict):
        result_dict["readiness_report"] = {"is_ready": True, "score": 100.0, "iteration": 1}
        return state_context
        
    with patch.object(InvestigationController, 'run_loop', new=mock_run_loop):
        result = await execute(
            query="North Korea missile test assessment",
            country_code="KP",
            job_id="e2e-test-003",
        )
        
        stix = result.get("stix2_bundle")
        assert stix is not None, "STIX2 bundle missing"
        assert stix["type"] == "bundle"
        assert "objects" in stix
        assert len(stix["objects"]) >= 2, f"Expected >=2 objects, got {len(stix['objects'])}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_step_tracer_produces_files():
    """Step tracer must write trace files for each pipeline step."""
    from dip.unified_pipeline import execute
    from pathlib import Path
    from unittest.mock import patch
    from dip.runtime.control_loop.investigation_controller import InvestigationController
    
    async def mock_run_loop(self, state_context, goal, query, country_code, result_dict):
        result_dict["readiness_report"] = {"is_ready": True, "score": 100.0, "iteration": 1}
        return state_context
        
    with patch.object(InvestigationController, 'run_loop', new=mock_run_loop):
        result = await execute(
            query="Russia Ukraine conflict status",
            country_code="UA",
            job_id="e2e-test-004",
        )
        
        from dip.engines.step_tracer import TRACES_DIR
        trace_dir = TRACES_DIR / result["trace_id"]
        assert trace_dir.exists(), f"Trace directory {trace_dir} does not exist"
        
        json_files = list(trace_dir.glob("*.json"))
        assert len(json_files) >= 5, f"Expected >=5 trace files, found {len(json_files)}"
        
        # Verify trace_summary.json exists
        summary_file = trace_dir / "trace_summary.json"
        assert summary_file.exists(), "trace_summary.json missing"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_cove_heuristic_does_not_hang():
    """CoVe deliberation must complete instantly in heuristic mode."""
    from dip.pipeline.deliberation.deliberation.cove import decompose, _heuristic_decompose
    from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
    from dip.core.schema import Hypothesis
    import time
    
    # Build a minimal session
    session = CouncilSession(query="test", state_context=None)
    session.hypotheses = [
        Hypothesis(
            minister="Security Minister",
            hypothesis_type="military_escalation",
            predicted_signals=["troop_movement", "military_exercise"],
            matched_signals=["troop_movement"],
            missing_signals=["military_exercise", "satellite_imagery"],
            confidence=0.65,
        ),
        Hypothesis(
            minister="Diplomacy Minister",
            hypothesis_type="diplomatic_breakdown",
            predicted_signals=["embassy_recall", "summit_canceled"],
            matched_signals=["embassy_recall"],
            missing_signals=["summit_canceled"],
            confidence=0.45,
        ),
    ]
    
    t0 = time.time()
    claims = _heuristic_decompose(session)
    elapsed = time.time() - t0
    
    assert len(claims) >= 4, f"Expected >=4 claims, got {len(claims)}"
    assert elapsed < 1.0, f"Heuristic CoVe took {elapsed:.2f}s (should be <1s)"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_crag_heuristic_does_not_hang():
    """CRAG investigation must complete instantly in heuristic mode."""
    from dip.pipeline.deliberation.deliberation.crag import _heuristic_investigate
    from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
    import time
    
    session = CouncilSession(query="test", state_context=None)
    session.missing_signals = [
        "satellite_imagery_confirmation",
        "diplomatic_backchannel_confirmation",
        "economic_sanctions_announcement",
    ]
    
    # Set up minimal state_context with required attributes
    class MockSC:
        country = "TEST"
        current_signals = []
        active_conflicts = []
    
    session.state_context = MockSC()
    
    t0 = time.time()
    result = _heuristic_investigate(session)
    elapsed = time.time() - t0
    
    assert len(result.evidence_log) >= 3, f"Expected >=3 log entries, got {len(result.evidence_log)}"
    assert elapsed < 1.0, f"Heuristic CRAG took {elapsed:.2f}s (should be <1s)"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_red_team_heuristic_does_not_hang():
    """Red Team challenge must complete instantly in heuristic mode."""
    from dip.pipeline.deliberation.deliberation.red_team import _heuristic_challenge, _select_targets
    from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
    from dip.core.schema import Hypothesis
    import time
    
    session = CouncilSession(query="test", state_context=None)
    session.hypotheses = [
        Hypothesis(
            minister="Security Minister",
            hypothesis_type="military_escalation",
            predicted_signals=["troop_movement"],
            matched_signals=["troop_movement"],
            missing_signals=[],
            confidence=0.85,
        ),
        Hypothesis(
            minister="Strategy Minister",
            hypothesis_type="strategic_assessment",
            predicted_signals=[],
            matched_signals=[],
            missing_signals=["all_source_intelligence"],
            confidence=0.25,
        ),
    ]
    
    targets = _select_targets(session)
    assert len(targets) >= 1, "Expected at least 1 low-confidence target"
    
    t0 = time.time()
    challenges = _heuristic_challenge(targets, session)
    elapsed = time.time() - t0
    
    assert len(challenges) >= 1, f"Expected >=1 challenges, got {len(challenges)}"
    assert elapsed < 1.0, f"Heuristic Red Team took {elapsed:.2f}s (should be <1s)"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_threat_synthesizer_heuristic():
    """Threat synthesizer must produce valid assessment in heuristic mode."""
    from dip.pipeline.synthesis.decision_core.threat_synthesizer import _build_heuristic_assessment
    from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
    from dip.core.schema import IntelligenceAssessment, Signal
    import time
    
    session = CouncilSession(query="test", state_context=None)
    session.hypotheses = []
    session.missing_signals = ["test_gap"]
    
    # Create mock signals with all required Pydantic fields
    class MockSignal:
        def __init__(self, action, domain, intensity):
            self.action = action
            self.domain = domain
            self.intensity = intensity
    
    class MockStateContext:
        current_signals = [
            MockSignal(action="troop buildup", domain="military", intensity=0.9),
            MockSignal(action="border closure", domain="military", intensity=0.7),
            MockSignal(action="diplomatic protest", domain="diplomatic", intensity=0.5),
        ]
        data_blindspots = {"adversary_intent", "third_party_reaction"}
    
    session.state_context = MockStateContext()
    
    t0 = time.time()
    assessment = _build_heuristic_assessment(session, MockStateContext.current_signals, [])
    elapsed = time.time() - t0
    
    assert assessment.overall_threat_level in ("CRITICAL", "HIGH", "ELEVATED", "LOW")
    assert assessment.threat_dimensions.military > 0
    assert len(assessment.recommendations) == 3
    assert elapsed < 1.0, f"Heuristic decide took {elapsed:.2f}s (should be <1s)"


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.skip(reason="layer6_presentation superseded by dossier")
async def test_narrative_markdown_export():
    """Narrative must export to valid markdown."""
    from dip.pipeline.synthesis.presentation.strategic_narrative import narrative_to_markdown
    
    narrative = {
        "executive_judgment": "Test judgment.",
        "evidentiary_pillars": [
            {"pillar": "Test", "minister": "Security", "confidence": "80%", "evidence": "Signals A, B"}
        ],
        "alternative_futures": [
            {"scenario": "Test Future", "probability": "50%", "trigger": "Event X", "impact": "Outcome Y"}
        ],
        "actionable_implications": ["Do thing 1", "Do thing 2"],
        "confidence_statement": "Test confidence.",
        "generation_mode": "heuristic",
        "generated_at": "2025-01-01T00:00:00Z",
    }
    
    md = narrative_to_markdown(narrative)
    assert "# Strategic Intelligence Assessment" in md
    assert "## 📋 Executive Judgment" in md
    assert "## 🔍 Key Evidentiary Pillars" in md
    assert "## 🔮 Alternative Futures" in md
    assert "## ⚡ Actionable Implications" in md
    assert "## 📊 Analytic Confidence" in md


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_multiple_countries_sequential():
    """Pipeline must handle multiple sequential country assessments."""
    from dip.unified_pipeline import execute
    
    countries = [
        ("IN", "India China border"),
        ("US", "US Iran nuclear deal"),
    ]
    
    for code, query in countries:
        result = await execute(query=query, country_code=code, job_id=f"e2e-multi-{code}")
        assert result["status"] in ("COMPLETE", "WITHHELD", "HUMAN_REVIEW", "REFUSED")
        assert result["country"] == code
