import pytest
from dip.runtime.graph import (
    intelligence_graph,
    build_intelligence_graph,
    node_legal_grounding,
    node_signal_extraction,
    node_state_accumulation,
    IntelligenceState
)

@pytest.mark.unit
def test_graph_structure():
    """Verify all 7 cognitive pipeline nodes are wired into the compiled LangGraph."""
    graph = build_intelligence_graph()
    assert graph is not None
    # LangGraph compiled graph has nodes
    nodes = set(graph.nodes.keys())
    expected_nodes = {
        "collect_osint",
        "legal_grounding",
        "signal_extraction",
        "state_accumulation",
        "council_deliberation",
        "decision_and_sre",
        "narrative_synthesis",
    }
    for node in expected_nodes:
        assert node in nodes, f"Expected node '{node}' missing from graph"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_node_legal_grounding():
    """Verify legal grounding node retrieves treaties and articles."""
    state: IntelligenceState = {
        "query": "Maritime boundary dispute and UNCLOS claims in South China Sea",
        "country": "PHL"
    }
    result = await node_legal_grounding(state)
    assert "legal_passages" in result
    assert isinstance(result["legal_passages"], list)
    assert len(result["legal_passages"]) > 0
    passage = result["legal_passages"][0]
    assert "treaty" in passage
    assert "article" in passage
    assert "content" in passage


@pytest.mark.asyncio
@pytest.mark.unit
async def test_node_signal_extraction():
    """Verify signal extraction produces domain-grounded signals."""
    state: IntelligenceState = {
        "query": "Assess troop mobilization along the northern line",
        "country": "IND",
        "raw_observations": []
    }
    result = await node_signal_extraction(state)
    assert "signals" in result
    signals = result["signals"]
    assert len(signals) >= 2
    domains = {s.domain for s in signals}
    assert "military" in domains or "diplomatic" in domains


@pytest.mark.asyncio
@pytest.mark.unit
async def test_node_state_accumulation():
    """Verify state accumulation produces a valid StateContext."""
    state: IntelligenceState = {
        "query": "Border surveillance alert",
        "country": "IND",
        "signals": []
    }
    result = await node_state_accumulation(state)
    assert "state_context" in result
    ctx = result["state_context"]
    assert ctx is not None
    assert ctx.country in ("IND", "GLOBAL")
