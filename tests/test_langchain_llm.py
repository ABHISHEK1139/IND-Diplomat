import pytest
from langchain_core.messages import HumanMessage
from dip.engines.langchain_llm import get_chat_model, DeterministicHeuristicChatModel

def test_deterministic_heuristic_chat_model():
    model = get_chat_model()
    response = model.invoke([HumanMessage(content="Assess deliberation hypothesis")])
    assert response is not None
    assert response.content != ""
    assert "risk_score" in response.content or "deliberation" in response.content or "Strategic" in response.content


def test_heuristic_proposal_has_no_junk_gap_tokens():
    """Filler words must not become expect_this_indicator-style gaps."""
    import re

    from dip.core.schema import StateContext
    from dip.pipeline.deliberation.reasoning.ministers.security_minister import SecurityMinister

    proposal = SecurityMinister()._heuristic_proposal(StateContext(country="IND"))
    junk = re.compile(r"expect_(this|that|what|with|from|genuine|real|about|into|over|under)_indicator")
    bad = [s for s in proposal.predicted_signals + proposal.missing_signals if junk.search(s)]
    assert not bad, f"junk gap tokens: {bad}"
    assert proposal.predicted_signals, "expected at least one domain token"


def test_unreachable_ollama_falls_through_to_deterministic(monkeypatch):
    """A dead Ollama host (or missing model) must not raise or hang the factory."""
    for key in ("FORCE_MINISTER_HEURISTIC", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    model = get_chat_model()
    assert isinstance(model, DeterministicHeuristicChatModel)


def test_openrouter_branch_uses_configured_model(monkeypatch):
    try:
        import langchain_openai  # noqa: F401
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOpenAI  # noqa: F401
        except ImportError:
            pytest.skip("no langchain OpenAI provider installed")
    for key in ("FORCE_MINISTER_HEURISTIC", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    model = get_chat_model()
    assert type(model).__name__ == "ChatOpenAI"
