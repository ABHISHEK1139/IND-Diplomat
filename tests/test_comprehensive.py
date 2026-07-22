import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Import schemas
from dip.core.schema import (
    RawObservation, Signal, Belief, TemporalIndicator, 
    DomainIndex, EscalationResult, StateContext,
    Hypothesis, AssessmentDecision
)

# Import Layers
from dip.layer1_collection.sensors.news_sensor import NewsSensor
from dip.layer3_state.state_provider import StateProvider



@pytest.fixture
def mock_session():
    class MockSession:
        def __init__(self):
            self.state_context = StateContext(country="IND", observation_count=10)
            self.hypotheses = [
                Hypothesis(
                    minister="Military Minister", 
                    hypothesis_type="FORCE_MOBILIZATION",
                    confidence=0.85,
                    reasoning="Troop movements observed.",
                    matched_signals=["SIG_001"],
                    missing_signals=[],
                    recommended_actions=[],
                    predicted_signals=[]
                )
            ]
            self.verification_score = 0.9
            self.evidence_log = []
            self.red_team_report = []
            self.state_context.current_signals = [
                Signal(
                    entity="IND", 
                    action="MIL_EXERCISE", 
                    intensity=0.8, 
                    confidence=0.9, 
                    source_ref="Reuters",
                    domain="military"
                )
            ]
    return MockSession()


@pytest.mark.asyncio
async def test_layer1_news_sensor():
    """Test Layer 1 Collection Module"""
    sensor = NewsSensor()
    # In DIP 2.0, NewsSensor usually has fetch() or similar methods. 
    # Just testing instantiation for now.
    assert hasattr(sensor, "source_type") or hasattr(sensor, "fetch")


@pytest.mark.asyncio
async def test_layer3_state_provider():
    """Test Layer 3 State Provider Module"""
    from unittest.mock import AsyncMock
    with patch('dip.layer1_collection.feed_integrator.FeedIntegrator.fetch_all', new_callable=AsyncMock) as mock_fetch, \
         patch('dip.layer2_knowledge.signal_extractor.SignalExtractor.extract', new_callable=AsyncMock) as mock_extract:
         
        provider = StateProvider()
        mock_fetch.return_value = [RawObservation(source_id="1", content="Border movement", timestamp="now")]
        mock_extract.return_value = [Signal(entity="IND", action="MIL_EXERCISE", intensity=0.5, confidence=0.8, source_ref="StateDept")]
        
        ctx = await provider.build_state_context("IND", "Border tensions")
        assert ctx.country == "IND"
        assert ctx.observation_count == 1
        assert len(ctx.current_signals) == 1


@pytest.mark.skip(reason="layer6_presentation has been migrated to layer6_workspace.dossier")
def test_layer6_presentation(mock_session):
    """Test Layer 6 Synthesis Module"""
    result_payload = {
        "threat_level": "ELEVATED",
        "verification_score": 0.85,
        "briefing": "Mock briefing",
        "trajectory": {"label": "Escalation", "confidence": 0.7}
    }
    
    from dip.layer6_presentation.strategic_narrative import synthesize_narrative
    
    # We force heuristic mode for testing by mocking the Litellm import to fail
    with patch('layer6_presentation.strategic_narrative.litellm', None):
        narrative = synthesize_narrative(mock_session, result_payload)
        
    assert "executive_summary" in narrative
    assert "ELEVATED" in narrative["executive_summary"]
    assert narrative["generation_mode"] == "modular_heuristic"
    assert len(narrative["evidence"]) >= 1


def test_schema_validation():
    """Test Core Schema Validation"""
    # Valid
    sig = Signal(
        entity="CHN",
        action="CYBER_ATTACK",
        intensity=0.9,
        confidence=0.7,
        source_ref="CISA"
    )
    assert sig.domain == "unknown"
    assert sig.weight == 1.0

    # Invalid
    with pytest.raises(ValueError):
        Signal(entity="CHN", action="CYBER") # Missing required fields
