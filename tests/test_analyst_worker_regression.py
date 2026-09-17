"""Offline regressions for analyst worker imports and failure outcomes."""
import builtins
import importlib
from unittest.mock import AsyncMock

import pytest

worker = importlib.import_module("dip.api.analyst.job_store")
wrapper = importlib.import_module("dip.ind_diplomat")


@pytest.fixture
def isolated_worker(tmp_path, monkeypatch):
    store = worker.JobStore(str(tmp_path / "jobs.json"))
    monkeypatch.setattr(worker, "STORE", store)
    manager = importlib.import_module("dip.api.ws.ws_manager").manager
    monkeypatch.setattr(manager, "publish_topic", AsyncMock(return_value=0))
    # Guard both entrypoints against accidental live execution on regression.
    pipeline = importlib.import_module("dip.unified_pipeline")
    shim = importlib.import_module("dip.pipeline.deliberation.ind_diplomat")
    blocked = AsyncMock(side_effect=AssertionError("Live pipeline called in unit test"))
    monkeypatch.setattr(pipeline, "execute", blocked)
    monkeypatch.setattr(shim, "execute", blocked)
    return store


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_uses_public_wrapper(isolated_worker, monkeypatch):
    query = AsyncMock(return_value=wrapper.PipelineResult(status="SUCCESS"))
    monkeypatch.setattr(wrapper, "diplomat_query", query)
    job = await isolated_worker.create_job("Offline test", "IND")
    await worker.run_job_background(job["job_id"], job["query"], job["country"])
    stored = await isolated_worker.get_job(job["job_id"])
    assert stored["status"] == "COMPLETED"
    assert stored["result"] == {"status": "SUCCESS"}
    query.assert_awaited_once_with("Offline test", "IND", job_id=job["job_id"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_import_failure_is_persisted(isolated_worker, monkeypatch):
    real_import = builtins.__import__

    def fail_wrapper(name, *args, **kwargs):
        if name == "dip.ind_diplomat":
            raise ImportError("wrapper unavailable")
        return real_import(name, *args, **kwargs)

    job = await isolated_worker.create_job("Offline test")
    monkeypatch.setattr(builtins, "__import__", fail_wrapper)
    await worker.run_job_background(job["job_id"], job["query"], job["country"])
    stored = await isolated_worker.get_job(job["job_id"])
    assert stored["status"] == "FAILED"
    assert stored["error"] == "wrapper unavailable"
    assert stored["completed_at"] is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_pipeline_error_is_not_success(isolated_worker, monkeypatch):
    monkeypatch.setattr(wrapper, "diplomat_query", AsyncMock(
        return_value=wrapper.PipelineError(error="pipeline unavailable")
    ))
    job = await isolated_worker.create_job("Offline test")
    await worker.run_job_background(job["job_id"], job["query"], job["country"])
    stored = await isolated_worker.get_job(job["job_id"])
    assert stored["status"] == "FAILED"
    assert stored["error"] == "pipeline unavailable"
    assert stored["result"] is None
