import pytest
import asyncio
from dip.runtime.graph import intelligence_graph, IntelligenceState

@pytest.mark.asyncio
async def test_langgraph_pipeline_execution():
    initial_state: IntelligenceState = {
        "query": "Assess naval deployment and cross-strait military readiness.",
        "country": "TWN",
        "job_id": "test-langgraph-01",
        "iteration": 1
    }
    
    final_state = await intelligence_graph.ainvoke(initial_state)
    
    assert final_state is not None
    assert "status" in final_state
    assert "threat_level" in final_state
    assert "verification_score" in final_state
    assert len(final_state.get("hypotheses", [])) > 0
    assert "strategic_narrative" in final_state
    assert "executive_judgment" in final_state["strategic_narrative"]
    assert "raw_markdown" in final_state["strategic_narrative"]
