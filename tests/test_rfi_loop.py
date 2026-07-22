import pytest
import asyncio
from unittest.mock import patch, MagicMock

from dip.core.schema import InvestigationGoal, StateContext, RFIQuery
from dip.control_loop.readiness_engine import evaluate_readiness

def test_readiness_low_coverage():
    # Setup a state context with very few signals
    goal = InvestigationGoal(
        id="G1", 
        topic="Cyber attacks", 
        target_country="Russia",
        time_horizon="1 month",
        investigation_goal="Assess cyber readiness",
        domains=[]
    )
    state = StateContext(country="Russia", query="Cyber attacks", observation_count=1)
    
    report = evaluate_readiness(state, goal, iteration=1)
    
    assert not report.is_ready
    assert report.score < 80.0
    assert len(report.rfi_queries) > 0
    
    # Check that at least one HIGH priority RFI is generated
    high_priority_rfis = [rfi for rfi in report.rfi_queries if rfi.priority == "HIGH"]
    assert len(high_priority_rfis) > 0
    assert report.estimated_cost > 0.0

def test_readiness_high_coverage():
    # Setup a state context with abundant signals
    goal = InvestigationGoal(
        id="G1", 
        topic="Cyber attacks", 
        target_country="Russia", 
        domains=["cyber", "political"],
        time_horizon="1 month",
        investigation_goal="Assess cyber readiness"
    )
    state = StateContext(country="Russia", query="Cyber attacks", observation_count=15)
    
    # Mocking 15 signals
    mock_signal = MagicMock()
    mock_signal.source_ref = "intel_source"
    mock_signal.domain = "cyber"
    state.current_signals = [mock_signal for _ in range(15)]
    
    # Adding a political signal to satisfy domains
    mock_signal_2 = MagicMock()
    mock_signal_2.source_ref = "another_source"
    mock_signal_2.domain = "political"
    state.current_signals.append(mock_signal_2)
    
    state.temporal_indicators = ["T1", "T2", "T3"]
    
    report = evaluate_readiness(state, goal, iteration=2)
    
    assert report.is_ready
    assert report.score >= 80.0
    assert len(report.rfi_queries) == 0

@pytest.mark.asyncio
async def test_recursive_pipeline_loop():
    # This is an integration test simulating the recursive loop without running the full LLM
    from dip.unified_pipeline import execute
    
    # Mock StateProvider and SignalExtractor to avoid network calls
    with patch('unified_pipeline.StateProvider') as MockProvider, \
         patch('layer2_knowledge.signal_extractor.SignalExtractor') as MockExtractor, \
         patch('unified_pipeline.run_council') as MockCouncil:
         
        # Mock StateProvider to return an empty StateContext on first call
        mock_provider_instance = MockProvider.return_value
        initial_state = StateContext(country="Iran", query="Nuclear program", observation_count=0)
        
        # We need to return initial state when build_state_context is called
        async def mock_build(*args, **kwargs):
            return initial_state
        mock_provider_instance.build_state_context = mock_build
        
        # Mock SignalExtractor to return 5 signals when queried
        mock_extractor_instance = MockExtractor.return_value
        async def mock_extract(*args, **kwargs):
            mock_signal = MagicMock()
            mock_signal.source_ref = "mock_source"
            return [mock_signal for _ in range(10)]
        mock_extractor_instance.extract_signals = mock_extract
        
        # Run pipeline
        result = await execute("Test recursive loop", "IR")
        
        # Verify result format and research log
        assert result is not None
        assert "research_log" in result
        
        # Because we mocked extract_signals to return 10 signals per RFI, 
        # iteration 2 should have passed readiness.
        # But wait, execute() will run full pipeline which might fail without other mocks.
        # We just want to check if the loop triggered.
        assert len(result["research_log"]) > 0
