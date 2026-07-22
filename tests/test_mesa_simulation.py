import pytest
from dip.layer8_wargaming.mesa_simulation import run_wargame_simulation, SimulationResult
from dip.layer3_state.working_memory import WorkingMemory
from dip.core.schema import StateContext
from dip.layer4_reasoning.council_session import CouncilSession

@pytest.mark.unit
def test_wargame_simulation_basic():
    """Test the Monte Carlo fallback wargame simulation."""
    domain_indices = {
        "capability": 0.8,
        "intent": 0.9,
        "stability": 0.2
    }
    
    state_context = StateContext(country="TEST")
    
    session = CouncilSession(query="Escalation risk?", state_context=state_context)
    session.working_memory = WorkingMemory()
    
    # Run simulation with high threat
    result = run_wargame_simulation(
        country="TEST",
        sre_score=0.9,
        domain_indices=domain_indices,
        runs=50
    )
    
    assert isinstance(result, SimulationResult)
    assert result.scenario == "wargame_TEST"
    assert result.runs == 50
    assert "major_conflict" in result.outcomes
    assert result.escalation_probability > 0.0

@pytest.mark.unit
def test_wargame_simulation_low_threat():
    """Test wargame with very low threat indices."""
    domain_indices = {
        "capability": 0.1,
        "intent": 0.1,
        "stability": 0.9
    }
    
    result = run_wargame_simulation(
        country="TEST",
        sre_score=0.1,
        domain_indices=domain_indices,
        runs=50
    )
    
    assert result.escalation_probability <= 0.5
