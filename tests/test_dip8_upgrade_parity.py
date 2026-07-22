import asyncio
import pytest
from pathlib import Path

from fastapi.testclient import TestClient

import dip.api
from dip.layer4_reasoning.coordinator import _build_ministers


def test_project_has_dip8_successor_packaging():
    root = Path(__file__).resolve().parents[1]

    assert (root / "pyproject.toml").exists()
    assert (root / "Makefile").exists()
    assert (root / "src" / "dip" / "run.py").exists()
    assert (root / "src" / "dip" / "api.py").exists()


def test_python_public_api_exports_diplomat_query():
    from dip import ind_diplomat

    assert hasattr(ind_diplomat, "DiplomatResult")
    assert hasattr(ind_diplomat, "diplomat_query")
    assert hasattr(ind_diplomat, "diplomat_query_sync")


@pytest.mark.skip(reason="Ministers not yet implemented in DIP 2.0")
def test_council_has_all_seven_dip8_ministers():
    names = [minister.minister_name for minister in _build_ministers()]

    assert names == [
        "Security Minister",
        "Strategy Minister",
        "Diplomacy Minister",
        "Economic Minister",
        "Domestic Minister",
        "Alliance Minister",
        "Contrarian Minister",
    ]


def test_dip8_compatible_api_surfaces(monkeypatch):
    async def fake_execute(query: str, country: str):
        return {
            "query": query,
            "country": country,
            "status": "COMPLETE",
            "trace_id": "dip2-test",
            "threat_level": "LOW",
            "verification_score": 0.9,
            "evidence_log": ["source-a"],
            "fuzzy_trace": {"sre_escalation_score": 0.1},
            "blackboard_events": [],
            "nextgen_sre": {"sre_escalation_score": 0.1},
            "promotion_status": [],
            "red_team_report": [],
        }

    monkeypatch.setattr(dip.api, "execute", fake_execute)

    with TestClient(dip.api.app) as client:
        health = client.get("/api/v3/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"
        assert "oss_adapters" in health.json()

        sync_response = client.post("/v2/query", json={"query": "test", "country": "IND"})
        assert sync_response.status_code == 200
        assert sync_response.json()["trace_id"] == "dip2-test"

        job_response = client.post("/api/v3/assess", json={"query": "test", "country": "IND"})
        assert job_response.status_code == 200
        job_id = job_response.json()["job_id"]

        for _ in range(20):
            status_response = client.get(f"/api/v3/jobs/{job_id}/status")
            assert status_response.status_code == 200
            if status_response.json()["status"] == "complete":
                break
            asyncio.run(asyncio.sleep(0.01))

        result_response = client.get(f"/api/v3/jobs/{job_id}/result")
        assert result_response.status_code == 200
        assert result_response.json()["trace_id"] == "dip2-test"

        evidence_response = client.get(f"/api/v3/jobs/{job_id}/evidence")
        assert evidence_response.status_code == 200
        assert evidence_response.json()["evidence_log"] == ["source-a"]

        verification_response = client.get(f"/api/v3/jobs/{job_id}/verification")
        assert verification_response.status_code == 200
        assert verification_response.json()["verification_score"] == 0.9
