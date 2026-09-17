import pytest
from fastapi.testclient import TestClient
from dip.api import app
from dip.engines.job_store import job_store

@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)

@pytest.mark.unit
def test_api_v3_job_lifecycle(client, monkeypatch):
    import time

    # TEST-01: the mock must accept the same (query, country, job_id) call
    # signature the real background runner uses, and the test must observe
    # the actual background execution instead of marking the job complete
    # by hand.
    async def mock_execute(query, country, job_id=None):
        assert job_id is not None, "background runner must pass job_id through"
        return {
            "query": query,
            "country": country,
            "trace_id": "test-trace-123",
            "status": "COMPLETE",
            "threat_level": "CRITICAL",
            "verification_score": 0.88,
            "evidence_log": [{"id": "ev1", "text": "border activity"}],
            "fuzzy_trace": {"score": 0.9},
            "blackboard_events": ["event1"],
            "nextgen_sre": {"sre_escalation_score": 0.75}
        }
    monkeypatch.setattr("dip.api.rest_api.execute", mock_execute)
    # Silence WS fan-out; lifecycle assertions below cover the contract.
    monkeypatch.setattr("dip.api.rest_api.ws_manager", None)

    # 1. Create Assessment Job
    res = client.post("/api/v3/assess", json={"query": "Test Border Movement", "country": "IND"})
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["status"].upper() == "QUEUED"
    job_id = data["job_id"]

    # 2. Get Job Status
    res = client.get(f"/api/v3/jobs/{job_id}")
    assert res.status_code == 200
    assert res.json()["job_id"] == job_id

    # 3. Wait for the real background runner to complete the job.
    deadline = time.time() + 15
    while time.time() < deadline:
        job = job_store.get(job_id)
        if job.result is not None:
            break
        time.sleep(0.1)
    else:
        pytest.fail("background runner did not complete the job")

    assert job_store.get(job_id).status == "COMPLETED"

    # 4. Check Result
    res = client.get(f"/api/v3/jobs/{job_id}/result")
    assert res.status_code == 200
    assert res.json()["threat_level"] == "CRITICAL"

    # 5. Check Evidence
    res = client.get(f"/api/v3/jobs/{job_id}/evidence")
    assert res.status_code == 200
    assert len(res.json()["evidence_log"]) == 1

    # 6. Check Verification
    res = client.get(f"/api/v3/jobs/{job_id}/verification")
    assert res.status_code == 200
    assert res.json()["verification_score"] == 0.88

    # 7. Check Trends
    res = client.get("/api/v3/trends/IND")
    assert res.status_code == 200
    assert any(j["job_id"] == job_id for j in res.json())

    # 8. Check Alerts
    res = client.get("/api/v3/alerts/IND")
    assert res.status_code == 200
    assert any(j["job_id"] == job_id for j in res.json())


@pytest.mark.unit
def test_api_v3_job_not_found(client):
    res = client.get("/api/v3/jobs/nonexistent-id-99999")
    assert res.status_code == 404
