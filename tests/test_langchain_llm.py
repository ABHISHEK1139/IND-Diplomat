import pytest
from langchain_core.messages import HumanMessage
from dip.engines.langchain_llm import get_chat_model, DeterministicHeuristicChatModel

def test_deterministic_heuristic_chat_model():
    model = get_chat_model()
    response = model.invoke([HumanMessage(content="Assess deliberation hypothesis")])
    assert response is not None
    assert response.content != ""
    assert "risk_score" in response.content or "deliberation" in response.content or "Strategic" in response.content
