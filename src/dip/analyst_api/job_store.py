from __future__ import annotations
from dip.Config.config import config
"""Simple JSON-backed job store for async analyst jobs.
Stores jobs in-memory and persists to `data/jobs.json` for basic durability.
"""

import asyncio
import json
import os
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JOBS_PATH = config.DIP_JOB_STORE
os.makedirs(os.path.dirname(JOBS_PATH), exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, path: str = JOBS_PATH):
        self.path = path
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._jobs = {j["job_id"]: j for j in data}
        except Exception:
            self._jobs = {}

    def _persist(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(list(self._jobs.values()), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    async def create_job(self, query: str, country: str = "IND", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with self._lock:
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "query": query,
                "country": country,
                "status": "QUEUED",
                "created_at": _now(),
                "started_at": None,
                "completed_at": None,
                "progress": 0,
                "result": None,
                "error": None,
                "meta": meta or {},
            }
            self._jobs[job_id] = job
            self._persist()
            return job

    async def update_job(self, job_id: str, **fields) -> Optional[Dict[str, Any]]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.update(fields)
            self._persist()
            return job

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        async with self._lock:
            jobs = list(self._jobs.values())
            jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
            return jobs[:limit]


# Single module-level store used by the API
STORE = JobStore()


async def run_job_background(job_id: str, query: str, country: str):
    """Background runner that invokes the main diplomat query and stores results."""
    # Import here to avoid cycle at module import time
    from dip.ind_diplomat import diplomat_query

    await STORE.update_job(job_id, status="RUNNING", started_at=_now(), progress=5)
    try:
        # send progress update helper
        try:
            from dip.api_ws.ws_manager import manager as ws_manager
        except Exception:
            ws_manager = None

        if ws_manager:
            await ws_manager.publish_topic(f"job:{job_id}", {"type": "job.progress", "job_id": job_id, "status": "RUNNING", "progress": 5})

        result = await diplomat_query(query, country, job_id=job_id)
        # pydantic model -> dict (use model_dump for V2, dict for V1 compat)
        if hasattr(result, "model_dump"):
            payload = result.model_dump(mode="json")
        elif hasattr(result, "dict"):
            payload = result.dict()
        else:
            payload = result
        await STORE.update_job(job_id, status="COMPLETED", completed_at=_now(), progress=100, result=payload)
        if ws_manager:
            await ws_manager.publish_topic(f"job:{job_id}", {"type": "job.completed", "job_id": job_id, "status": "COMPLETED", "result": payload})
    except Exception as exc:  # noqa: BLE001
        await STORE.update_job(job_id, status="FAILED", completed_at=_now(), progress=100, error=str(exc))
        if ws_manager:
            await ws_manager.publish_topic(f"job:{job_id}", {"type": "job.failed", "job_id": job_id, "status": "FAILED", "error": str(exc)})
