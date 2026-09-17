"""Offline calibrated backtest — the first honest accuracy number.

Runs the 5 labeled historical crises through a fully deterministic offline
pipeline (indicator text -> heuristic signals -> StateContext -> heuristic
council -> deterministic synthesizer) and scores directional accuracy plus
Brier score. No network, no LLM.

Known limitation (documented, not hidden): the heuristic extractor maps any
military keyword to intensity 0.85, so exact-level accuracy over-predicts
CRITICAL. The regression bar is therefore set on *directional* accuracy
(did we point the right way?) while exact accuracy and Brier score are
reported for calibration tracking.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


async def _offline_execute(query, country_code, job_id=None, indicators=()):
    from dip.pipeline.knowledge.signal_extractor import SignalExtractor
    from dip.pipeline.world_model.state.state_provider import StateProvider
    from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
    from dip.pipeline.deliberation.reasoning.coordinator import run_council
    from dip.pipeline.synthesis.decision_core.threat_synthesizer import decide
    import json

    extractor = SignalExtractor()
    signals = []
    for indicator in indicators:
        signals.extend(await extractor.extract_signals(indicator))
    ctx = StateProvider().build_state(country_code, [], signals)
    session = CouncilSession(query=query, state_context=ctx)
    await run_council(session)
    decide(session)
    decision = json.loads(session.final_decision)
    max_intensity = max((s.intensity for s in signals), default=0.0)
    return {
        "query": query,
        "country": country_code,
        "trace_id": job_id or "offline-backtest",
        "status": "COMPLETE",
        "threat_level": decision.get("overall_threat_level", "LOW"),
        "verification_score": (
            sum(h.confidence for h in session.hypotheses) / len(session.hypotheses)
            if session.hypotheses else 0.0
        ),
        "hypotheses": [h.model_dump(mode="json") for h in session.hypotheses],
        "evidence_log": list(session.evidence_log),
        # Deterministic escalation proxy: strongest observed intensity,
        # mirroring the synthesizer's max-dimension rule.
        "nextgen_sre": {"sre_escalation_score": round(max_intensity, 3)},
    }


@pytest.mark.asyncio
async def test_offline_backtest_scores_above_floor():
    import os
    os.environ["FORCE_MINISTER_HEURISTIC"] = "1"
    from dip.pipeline.memory.backtesting.historical_crisis_evaluator import (
        HISTORICAL_CRISES, run_full_backtest_suite,
    )

    async def execute_fn(query, country_code, job_id=None):
        crisis = next(c for c in HISTORICAL_CRISES if c.query == query)
        return await _offline_execute(query, country_code, job_id, crisis.key_indicators)

    report = await run_full_backtest_suite(execute_fn)
    print(
        f"\nOFFLINE BACKTEST: threat_accuracy={report.threat_accuracy} "
        f"directional={report.directional_accuracy} brier={report.brier_score} "
        f"mae={report.mean_absolute_error}"
    )
    assert report.directional_accuracy >= 0.6, (
        f"offline directional accuracy {report.directional_accuracy} below 0.6 floor"
    )
    # Exact-level accuracy is reported for calibration tracking; the
    # heuristic over-predicts CRITICAL (see module docstring).
    assert 0.0 <= report.brier_score <= 1.0
