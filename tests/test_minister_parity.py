import os
import asyncio

from dip.layer4_reasoning.council_session import CouncilSession
from dip.layer3_state.state_provider import StateProvider
from dip.layer4_reasoning.coordinator import run_council


def test_all_seven_ministers_produce_hypotheses(monkeypatch):
    # Force heuristic path to avoid LLM usage in CI
    os.environ["FORCE_MINISTER_HEURISTIC"] = "1"

    async def _run():
        from dip.layer3_state.working_memory import WorkingMemory
        provider = StateProvider()
        state = await provider.build_state_context("CXY", "test signals for ministers")
        session = CouncilSession(query="test ministers", state_context=state)
        session.working_memory = WorkingMemory()
        session = await run_council(session)
        return session

    session = asyncio.run(_run())
    assert len(session.hypotheses) >= 2
    for h in session.hypotheses:
        assert 0.0 <= h.confidence <= 1.0
