import pytest
from dip.core.schema import StateContext, Signal, MinisterHypothesisOutput
from dip.pipeline.synthesis.decision_core.threat_synthesizer import _merge_bounded_assessment

@pytest.fixture
def mock_state_context():
    ctx = StateContext(country="TEST")
    ctx.current_signals.append(Signal(
        entity="TestEntity", action="test_action",
        intensity=0.8, confidence=0.9, source_ref="src",
        domain="military"
    ))
    return ctx

@pytest.mark.unit
def test_dual_mode_agreement():
    """Test that a heuristic and LLM in agreement produces a high agreement score."""
    heuristic = MinisterHypothesisOutput(
        predicted_signals=["sig1"], matched_signals=["sig1"],
        confidence=0.8, rationale="heuristic"
    )
    llm = MinisterHypothesisOutput(
        predicted_signals=["sig1"], matched_signals=["sig1"],
        confidence=0.85, rationale="llm agreed"
    )
    
    from dip.pipeline.deliberation.reasoning.ministers.base import BaseMinister
    class DummyMinister(BaseMinister):
        @property
        def minister_name(self): return "Dummy"
        @property
        def hypothesis_type(self): return "dummy_type"
        @property
        def system_prompt(self): return "dummy"
        
    minister = DummyMinister()
    decision = minister._merge_dual_mode(heuristic, llm)
    
    assert decision.agreement_score == pytest.approx(0.95, abs=0.01)
    assert decision.resolution_action == "llm_refined_within_bounds"

@pytest.mark.unit
def test_dual_mode_disagreement_bounds():
    """Test that if the LLM changes confidence drastically, it gets bounded."""
    heuristic = MinisterHypothesisOutput(
        predicted_signals=["sig1"], matched_signals=["sig1"],
        confidence=0.5, rationale="heuristic"
    )
    llm = MinisterHypothesisOutput(
        predicted_signals=["sig1"], matched_signals=["sig1"],
        confidence=0.9, rationale="llm disagreed drastically",
        critical_signal_refs=[]  # no proof provided!
    )
    
    from dip.pipeline.deliberation.reasoning.ministers.base import BaseMinister
    class DummyMinister(BaseMinister):
        @property
        def minister_name(self): return "Dummy"
        @property
        def hypothesis_type(self): return "dummy_type"
        @property
        def system_prompt(self): return "dummy"
        
    minister = DummyMinister()
    decision = minister._merge_dual_mode(heuristic, llm)
    
    # LLM should be bounded to 0.5 + 0.15 = 0.65
    assert decision.final.confidence == 0.65
    assert decision.resolution_action == "bounded_llm_refinement"
    assert decision.agreement_score == pytest.approx(0.85, abs=0.01) # 1 - abs(0.65 - 0.5)

@pytest.mark.unit
def test_threat_synthesizer_merger():
    """Test the threat synthesizer dual-mode merger."""
    from dip.core.schema import IntelligenceAssessment
    heuristic = IntelligenceAssessment()
    heuristic.threat_dimensions.military = 0.5
    heuristic.overall_confidence = 0.5
    
    llm = IntelligenceAssessment()
    llm.threat_dimensions.military = 0.9 # Drastic change
    llm.overall_confidence = 0.9
    
    dual_mode = _merge_bounded_assessment(heuristic, llm)
    
    # Military threat should be bounded to 0.5 + 0.15 = 0.65
    assert dual_mode.final.threat_dimensions.military == 0.65
    # Overall confidence should be bounded to 0.5 + 0.15 = 0.65
    assert dual_mode.final.overall_confidence == 0.65
    assert dual_mode.resolution_action == "bounded_llm_refinement"
    assert "military difference > 0.15" in str(dual_mode.disagreements)

@pytest.mark.asyncio
async def test_hybrid_dual_engine_integration():
    """Test that unified_pipeline runs both Heuristic and AI engines and merges them."""
    from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
    from dip.core.schema import StateContext, Hypothesis
    from dip.unified_pipeline import _merge_dual_engine_hypotheses
    
    heuristic_baseline = [
        Hypothesis(source="Heuristic", minister="Security Minister", hypothesis_type="military", predicted_signals=[], matched_signals=[], missing_signals=[], confidence=0.8)
    ]
    
    ai_hypotheses = [
        Hypothesis(source="AI", minister="Security Minister", hypothesis_type="military", predicted_signals=[], matched_signals=[], missing_signals=[], confidence=0.85),
        Hypothesis(source="AI", minister="Cyber Minister", hypothesis_type="cyber", predicted_signals=[], matched_signals=[], missing_signals=[], confidence=0.6)
    ]
    
    merged = _merge_dual_engine_hypotheses(heuristic_baseline, ai_hypotheses)
    
    assert len(merged) == 2
    # Check that Security Minister confidence increased because both agreed HIGH (>= 0.7)
    security = next(h for h in merged if h.minister == "Security Minister")
    assert security.source == "Merged"
    assert security.confidence > 0.85  # Rule 1 applied
    
    # Check unmatched AI hypothesis is preserved
    cyber = next(h for h in merged if h.minister == "Cyber Minister")
    assert cyber.source == "AI"
    assert cyber.confidence == 0.6
