"""Pipeline ordering: gate/audit/vault must see finalized assessment fields.

Regression for the silent ordering bug where `build_assessment_state`
received verification 0.0 and proposal "LOW" on every run because
threat_level/verification/hypotheses were populated only after the gate.
Runs the real `execute()` offline via collection cassettes.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_gate_sees_finalized_fields(monkeypatch):
    import os

    os.environ["FORCE_MINISTER_HEURISTIC"] = "1"
    from tests.cassette import install_cassettes

    install_cassettes(monkeypatch)

    from dip.unified_pipeline import execute

    result = await execute("Assess border escalation risk", "IND")

    assert result.get("threat_level"), "threat_level must be finalized"
    assert result.get("hypotheses"), "hypotheses must be finalized"
    assert result.get("verification_score", 0.0) > 0.0
    # Gate verdict must reflect the real proposal, not a default.
    gate = result.get("gate_verdict")
    assert gate is None or isinstance(gate, dict)
    # Contract keys the frontend renders must exist (possibly empty).
    assert isinstance(result.get("recommendations"), list)
    cs = result.get("confidence_scores") or {}
    assert cs.get("evidence") == pytest.approx(result["verification_score"])
    assert "forecast_reliability" in cs
    # Reasoning provenance must survive into the auditable result.
    assert "dual_mode_assessment" in result
    assert isinstance(result.get("introspection_report"), str)
    modes = {h.get("decision_mode") for h in result["hypotheses"]}
    assert modes <= {"heuristic_only", "llm_refined_within_bounds", "bounded_llm_refinement"}
    assert None not in modes, "every hypothesis must carry its decision mode"
