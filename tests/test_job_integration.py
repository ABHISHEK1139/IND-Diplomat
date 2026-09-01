import asyncio

import pytest

from dip.api.analyst.job_store import STORE, run_job_background


@pytest.mark.asyncio
async def test_run_job_background_creates_result(tmp_path):
    # Create a queued job
    job = await STORE.create_job("test escalation for CountryX", country="CXY")
    job_id = job["job_id"]

    # Run the background runner directly (this will invoke ind_diplomat.diplomat_query)
    await run_job_background(job_id, job["query"], job["country"])

    # Fetch stored job
    stored = await STORE.get_job(job_id)
    assert stored is not None
    assert stored["status"] in ("COMPLETED", "FAILED")
    # If completed, result should include nextgen_sre (pipeline populates it)
    if stored["status"] == "COMPLETED":
        assert stored["result"] is not None
        assert isinstance(stored["result"], dict)
        # nextgen_sre may be at top-level or nested under 'payload'
        assert "nextgen_sre" in stored["result"] or "nextgen_sre" in (stored["result"].get("payload") or {})
