"""Live-LLM verification (on demand) + no-credential degradation proof.

- `test_structured_completion_degrades_to_none` (unit, always runs):
  every LLM failure mode must resolve to None — never raise, never hang —
  so the heuristic rails own the decision.
- `test_live_structured_completion` (live_llm, excluded from default runs):
  set DIP_LIVE_LLM=1 with a real provider key to actually exercise the
  wire path. Skips cleanly otherwise.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_structured_completion_degrades_to_none(monkeypatch):
    monkeypatch.delenv("FORCE_MINISTER_HEURISTIC", raising=False)
    import litellm

    async def _boom(*args, **kwargs):
        raise RuntimeError("no credential / no route")

    async def _boom_sync(*args, **kwargs):
        raise RuntimeError("no credential / no route")

    monkeypatch.setattr(litellm, "acompletion", _boom)
    monkeypatch.setattr(litellm, "completion", _boom_sync)
    # Block the LangChain fallback too: absence must also degrade to None.
    import builtins

    real_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        if name.startswith("langchain"):
            raise ImportError(f"blocked for test: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    from dip.core.schema import MinisterHypothesisOutput
    from dip.engines.structured_llm import structured_acompletion

    assert await structured_acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "ping"}],
        output_model=MinisterHypothesisOutput,
    ) is None


@pytest.mark.live_llm
@pytest.mark.asyncio
async def test_live_structured_completion():
    if os.getenv("DIP_LIVE_LLM") != "1":
        pytest.skip("set DIP_LIVE_LLM=1 with provider credentials to run")
    if not any(os.getenv(k) for k in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY")):
        pytest.skip("no provider API key configured")

    from dip.core.schema import MinisterHypothesisOutput
    from dip.engines.structured_llm import structured_acompletion
    from dip.core.Config.config import config

    out = await structured_acompletion(
        model=config.LLM_MODEL,
        max_tokens=250,
        messages=[{
            "role": "user",
            "content": (
                "Return only JSON matching MinisterHypothesisOutput: "
                "{ predicted_signals: string[], matched_signals: string[], "
                "missing_signals: string[], confidence: number, rationale: string, "
                "critical_signal_refs: string[] }. Hypothesis: test military posture. "
                "Observed signals: TEST brigade movement (intensity=0.80, confidence=0.90)."
            ),
        }],
        output_model=MinisterHypothesisOutput,
    )
    assert out is not None, "live LLM call failed — check provider key/model"
    assert 0.0 <= out.confidence <= 1.0
    assert isinstance(out.predicted_signals, list)
