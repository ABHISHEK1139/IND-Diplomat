import pytest
from scripts.deploy_prefect import dip2_global_flow

@pytest.mark.unit
def test_prefect_flow_dry_run(monkeypatch):
    """Ensure the Prefect flow can compile and run without exceptions."""
    # Mock the pipeline task so we don't actually call the LLMs
    def mock_execute(*args, **kwargs):
        return {"status": "COMPLETE", "threat_level": "ELEVATED"}
    
    import scripts.deploy_prefect as dp
    monkeypatch.setattr(dp, "execute_pipeline_task", mock_execute)
    
    scenarios = [
        {"country": "IND", "target": "CHN", "crisis_id": "TEST_1"},
    ]
    
    # Run flow
    results = dp.dip2_global_flow(scenarios)
    assert len(results) == 1
    assert results[0]["status"] == "COMPLETE"
