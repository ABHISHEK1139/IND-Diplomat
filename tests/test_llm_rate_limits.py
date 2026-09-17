"""LLM resilience: timeouts, unmasked errors, hypothesis provenance."""
import pytest

pytestmark = pytest.mark.unit


def test_default_timeout_applies_to_litellm(monkeypatch):
    monkeypatch.delenv("DIP_LLM_TIMEOUT", raising=False)
    from dip.core import llm_limits

    assert llm_limits.default_timeout() == 60.0
    assert llm_limits.apply_default_timeout() == 60.0
    import litellm

    assert litellm.request_timeout == 60.0


def test_timeout_env_override_and_invalid(monkeypatch):
    from dip.core import llm_limits

    monkeypatch.setenv("DIP_LLM_TIMEOUT", "12")
    assert llm_limits.default_timeout() == 12.0
    monkeypatch.setenv("DIP_LLM_TIMEOUT", "nonsense")
    assert llm_limits.default_timeout() == 60.0
    monkeypatch.setenv("DIP_LLM_TIMEOUT", "0")
    assert llm_limits.default_timeout() == 1.0


def test_hypothesis_provenance_preserved():
    from dip.core.schema import Hypothesis
    from dip.unified_pipeline import _hypothesis_to_dict

    h = Hypothesis(
        minister="Security Minister",
        hypothesis_type="military_escalation",
        predicted_signals=["a"],
        matched_signals=["b"],
        missing_signals=["c"],
        confidence=0.8,
        decision_mode="bounded_llm_refinement",
        heuristic_confidence=0.7,
        llm_confidence=0.85,
        agreement_score=0.85,
    )
    d = _hypothesis_to_dict(h)
    assert d["decision_mode"] == "bounded_llm_refinement"
    assert d["heuristic_confidence"] == 0.7
    assert d["llm_confidence"] == 0.85
    assert d["agreement_score"] == 0.85


def test_hypothesis_provenance_defaults_for_legacy():
    from types import SimpleNamespace

    from dip.unified_pipeline import _hypothesis_to_dict

    d = _hypothesis_to_dict(SimpleNamespace(minister="M", confidence=0.5))
    assert d["decision_mode"] is None
    assert d["type"] == "hypothesis"
