"""Deterministic API/storage repair contracts; no live pipeline calls."""
import asyncio
import importlib
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from dip.api import rest_api as api
from dip.engines.job_store import AssessmentJobStore
from dip.api.analyst.job_store import JobStore

pytestmark = pytest.mark.unit


def test_single_health_route():
    assert len([r for r in api.app.routes if r.path == '/health']) == 1


def test_blank_assessment_rejected_at_boundary():
    from fastapi.testclient import TestClient

    client = TestClient(api.app, raise_server_exceptions=False)
    assert client.post("/api/v3/assess", json={"query": "   ", "country": "IND"}).status_code == 422
    assert client.post("/api/v3/assess", json={"query": "x", "country": "   "}).status_code == 422
    res = client.post("/api/v3/assess", json={"query": "border watch", "country": "ind"})
    assert res.status_code == 200
    assert res.json()["status"].upper() == "QUEUED"


def test_configured_cors():
    middleware = next(m for m in api.app.user_middleware if m.cls.__name__ == 'CORSMiddleware')
    expected = [o.strip() for o in api.config.CORS_ALLOWED_ORIGINS if o.strip()]
    assert middleware.kwargs['allow_origins'] == expected
    assert middleware.kwargs['allow_credentials'] == ('*' not in expected)


def test_source_root():
    cfg = importlib.import_module('dip.core.Config.config')
    assert (cfg.ROOT_DIR / 'pyproject.toml').is_file()


def test_assessment_disposition_is_not_job_status(tmp_path):
    # Canonical lifecycle: QUEUED -> RUNNING -> COMPLETED | FAILED (uppercase).
    # Only a pipeline-level ERROR fails the job; every other assessment
    # disposition is retained in result, never copied into status.
    store = AssessmentJobStore(tmp_path / 'jobs.json')
    job = store.create('offline')
    assert store.get(job.job_id).status == 'QUEUED'
    store.mark_running(job.job_id)
    assert store.get(job.job_id).status == 'RUNNING'
    store.mark_complete(job.job_id, {'status': 'WITHHELD'})
    assert store.get(job.job_id).status == 'COMPLETED'
    assert store.get(job.job_id).result['status'] == 'WITHHELD'
    store.mark_complete(job.job_id, {'status': 'ERROR', 'error': 'unavailable'})
    assert store.get(job.job_id).status == 'FAILED'


def test_legacy_lowercase_statuses_are_normalized(tmp_path):
    path = tmp_path / 'jobs.json'
    path.write_text(json.dumps({
        'abc123': {
            'job_id': 'abc123', 'query': 'offline', 'country': 'IND',
            'status': 'completed', 'created_at': 't', 'updated_at': 't',
            'trace_id': None, 'result': None, 'error': None,
        }
    }), encoding='utf-8')
    store = AssessmentJobStore(path)
    assert store.get('abc123').status == 'COMPLETED'


@pytest.mark.parametrize('store_type,empty', [(AssessmentJobStore, '{}'), (JobStore, '[]')])
def test_corrupt_store_is_not_silently_discarded(tmp_path, store_type, empty):
    path = tmp_path / 'jobs.json'
    path.write_text('{broken', encoding='utf-8')
    with pytest.raises((ValueError, json.JSONDecodeError)):
        store_type(path)
    assert path.read_text(encoding='utf-8') == '{broken'


@pytest.mark.asyncio
async def test_analyst_write_failure_rolls_back(tmp_path, monkeypatch):
    store = JobStore(str(tmp_path / 'nested' / 'jobs.json'))
    job = await store.create_job('offline')
    def fail(*args, **kwargs):
        raise OSError('disk unavailable')
    monkeypatch.setattr(store, '_persist', fail)
    with pytest.raises(OSError):
        await store.update_job(job['job_id'], status='COMPLETED')
    assert (await store.get_job(job['job_id']))['status'] == 'QUEUED'


@pytest.mark.asyncio
async def test_assessment_cancellation_is_terminal(tmp_path, monkeypatch):
    store = AssessmentJobStore(tmp_path / 'jobs.json')
    monkeypatch.setattr(api, 'job_store', store)
    monkeypatch.setattr(api, 'execute', AsyncMock(side_effect=asyncio.CancelledError))
    monkeypatch.setattr(api.ws_manager, 'broadcast', AsyncMock())
    monkeypatch.setattr(api.ws_manager, 'publish_topic', AsyncMock())
    job = store.create('offline')
    with pytest.raises(asyncio.CancelledError):
        await api._run_assessment_job(job.job_id)
    assert store.get(job.job_id).status == 'FAILED'


@pytest.mark.asyncio
async def test_ws_reports_store_status_not_hardcoded_complete(tmp_path, monkeypatch):
    # JOB-03: WS must report the store lifecycle status (FAILED when the
    # pipeline itself errored), never a hardcoded COMPLETED.
    store = AssessmentJobStore(tmp_path / 'jobs.json')
    monkeypatch.setattr(api, 'job_store', store)
    monkeypatch.setattr(
        api, 'execute',
        AsyncMock(return_value={'status': 'ERROR', 'error': 'boom', 'trace_id': 't'}),
    )
    seen = []
    async def _broadcast(payload):
        seen.append(payload)
    async def _publish(topic, payload):
        seen.append(payload)
    monkeypatch.setattr(api.ws_manager, 'broadcast', _broadcast)
    monkeypatch.setattr(api.ws_manager, 'publish_topic', _publish)
    job = store.create('offline')
    await api._run_assessment_job(job.job_id)
    assert store.get(job.job_id).status == 'FAILED'
    assert any(p.get('status') == 'FAILED' for p in seen)
    assert any(p.get('assessment_status') == 'ERROR' for p in seen)


@pytest.mark.asyncio
async def test_lifespan_cancels_owned_tasks(monkeypatch):
    monkeypatch.setattr(api.config, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(api, 'job_store', AssessmentJobStore.__new__(AssessmentJobStore))
    api.job_store._jobs = {}
    monkeypatch.setattr(api.STORE, 'list_jobs', AsyncMock(return_value=[]))
    async with api.lifespan(api.app):
        task = api._schedule_job(asyncio.Event().wait())
        await asyncio.sleep(0)
    assert task.cancelled()
    assert not api.app.state.background_tasks
