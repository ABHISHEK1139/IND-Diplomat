"""Counterfactual grounding test (design.txt Step 3) — fully offline.

The real proof the system works: manually alter the StateContext and ask
the same question. If the council answer changes, reasoning is grounded in
the world model. If not, the LLM is dominating reasoning.

Variants (tests/fixtures/offline_border_crisis.json):
  baseline    military buildup + hostility  -> CRITICAL/HIGH
  no_military buildup removed               -> strictly lower
  cooperation inverted to cooperation       -> LOW/MODERATE
  empty       genuine absence of evidence    -> LOW + conservative confidence

No network, no LLM calls: heuristic ministers + deterministic synthesizer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "offline_border_crisis.json"

RANK = {"LOW": 0, "MODERATE": 1, "ELEVATED": 2, "HIGH": 3, "CRITICAL": 4}


async def _assess(signals_data, country="IND", query="Assess border escalation risk"):
    from dip.core.schema import Signal
    from dip.pipeline.world_model.state.state_provider import StateProvider
    from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
    from dip.pipeline.deliberation.reasoning.coordinator import run_council
    from dip.pipeline.synthesis.decision_core.threat_synthesizer import decide

    signals = [Signal(**s) for s in signals_data]
    ctx = StateProvider().build_state(country, [], signals)
    session = CouncilSession(query=query, state_context=ctx)
    await run_council(session)
    decide(session)
    decision = json.loads(session.final_decision)
    avg_conf = (
        sum(h.confidence for h in session.hypotheses) / len(session.hypotheses)
        if session.hypotheses else 0.0
    )
    return decision.get("overall_threat_level", "LOW"), avg_conf, len(session.hypotheses)


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_baseline_is_high():
    data = _load()
    level, _, n = await _assess(data["baseline"])
    assert n > 0
    assert level in ("CRITICAL", "HIGH"), f"baseline escalated fixture -> {level}"


@pytest.mark.asyncio
async def test_removing_military_buildup_lowers_threat():
    data = _load()
    base, _, _ = await _assess(data["baseline"], query=data["query"])
    altered, _, _ = await _assess(data["no_military"], query=data["query"])
    assert RANK[altered] < RANK[base], f"no-military {altered} not lower than baseline {base}"


@pytest.mark.asyncio
async def test_inverted_cooperation_yields_low():
    data = _load()
    level, _, _ = await _assess(data["cooperation"], query=data["query"])
    assert level in ("LOW", "MODERATE"), f"cooperation fixture -> {level}"


@pytest.mark.asyncio
async def test_empty_state_is_conservative():
    data = _load()
    level, avg_conf, _ = await _assess(data["empty"], query=data["query"])
    assert level == "LOW", f"empty StateContext -> {level}"
    assert avg_conf < 0.4, f"empty StateContext must stay conservative, got {avg_conf:.2f}"
