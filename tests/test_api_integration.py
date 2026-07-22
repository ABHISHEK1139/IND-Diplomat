"""Integration tests for API endpoints and WebSocket job events."""
import asyncio
import json

from fastapi.testclient import TestClient

from dip.api import app


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_v2_query_endpoint():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/v2/query", json={"query": "test query", "country": "CXY"})
    assert resp.status_code == 200
    data = resp.json()
    assert "query" in data
    assert "nextgen_sre" in data


def test_job_lifecycle():
    client = TestClient(app, raise_server_exceptions=False)
    # Create a job via assess endpoint
    resp = client.post("/api/v3/assess", json={"query": "test job", "country": "CXY"})
    assert resp.status_code == 200
    job = resp.json()
    job_id = job["job_id"]
    # Check status
    resp = client.get(f"/api/v3/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"].upper() in ("QUEUED", "RUNNING", "COMPLETED", "FAILED", "ERROR")