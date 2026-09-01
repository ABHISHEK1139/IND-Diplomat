import json
import pytest
from fastapi.testclient import TestClient
from dip.api import app

@pytest.mark.unit
def test_api_assess_health():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json().get("status") == "healthy"

@pytest.mark.unit
def test_api_assess_endpoint(monkeypatch):
    # Mock the execute function
    async def mock_execute(query, country):
        return {"threat_level": "HIGH", "query": query, "country": country}
    
    # The import in rest_api.py is: from dip.unified_pipeline import execute
    monkeypatch.setattr("dip.api.rest_api.execute", mock_execute)

    client = TestClient(app, raise_server_exceptions=False)
    res = client.post(
        "/api/assess",
        json={"query": "Assess recent military movements near the border", "country": "IND"}
    )
    if res.status_code != 200:
        print("API ERROR:", res.json())
    assert res.status_code == 200
    data = res.json()
    assert "status" in data or "threat_level" in data or "query" in data

if __name__ == "__main__":
    client = TestClient(app)
    res = client.post(
        "/api/assess",
        json={"query": "Assess recent military movements near the border", "country": "IND"}
    )
    print("Response status:", res.status_code)
    print("Response data:", res.json())

