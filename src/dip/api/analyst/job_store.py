from __future__ import annotations
from dip.core.Config.config import config
"""Simple JSON-backed job store for async analyst jobs.
Stores jobs in-memory and persists to ``config.DIP_JOB_STORE`` (project-root
data dir by default) for basic durability.
"""

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Iterator, Optional, List

from dip.core.atomic_json import write_json

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None  # type: ignore[assignment]

JOBS_PATH = config.DIP_JOB_STORE
os.makedirs(os.path.dirname(JOBS_PATH), exist_ok=True)

#: Retention for terminal jobs (COMPLETED/FAILED); older entries are pruned.
JOB_RETENTION_DAYS = int(os.getenv("DIP_JOB_RETENTION_DAYS", "30"))
#: Hard ceiling for list_jobs so one request cannot serialize the whole store.
MAX_LIST_LIMIT = 1000


@contextmanager
def _cross_process_lock(path: str) -> Iterator[None]:
    """Serialize read-modify-write cycles across API/worker processes.

    ``write_json`` is atomic per write, but without a lock two processes can
    interleave load->mutate->save and the second save silently drops the
    first process' jobs (last-writer-wins). A no-op on platforms without
    ``fcntl``.
    """
    if fcntl is None:
        yield
        return
    with open(f"{path}.lock", "a+b") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: Optional[str]) -> datetime:
    """Parse an ISO timestamp defensively; unparseable/missing -> epoch."""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


class JobStore:
    def __init__(self, path: str = JOBS_PATH):
        self.path = path
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._jobs = {j["job_id"]: j for j in data}

    def _persist(self) -> None:
        write_json(self.path, list(self._jobs.values()))

    @asynccontextmanager
    async def _mutate(self) -> AsyncIterator[None]:
        """Serialize a read-modify-write across threads AND processes.

        Holds the in-process lock plus a cross-process file lock, reloads
        from disk first (so other processes' jobs are not dropped), and
        persists exactly once when the block exits.
        """
        async with self._lock:
            with _cross_process_lock(self.path):
                self._load()
                yield
                self._persist()

    async def create_job(self, query: str, country: str = "IND", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with self._mutate():
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
            return job

    async def claim_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Atomically transition QUEUED -> RUNNING.

        Returns the claimed job iff this caller won the race; ``None`` means
        another worker claimed (or finished) it first. Safe across processes.
        """
        async with self._mutate():
            job = self._jobs.get(job_id)
            if not job or job.get("status") != "QUEUED":
                return None
            job["status"] = "RUNNING"
            job["started_at"] = _now()
            job["progress"] = 5
            return dict(job)

    async def update_job(self, job_id: str, **fields) -> Optional[Dict[str, Any]]:
        async with self._lock:
            with _cross_process_lock(self.path):
                self._load()
                job = self._jobs.get(job_id)
                if not job:
                    return None
                previous = dict(job)
                job.update(fields)
                try:
                    self._persist()
                except Exception:
                    job.clear()
                    job.update(previous)
                    raise
                return job

    async def mark_interrupted(self, error: str = "Interrupted by server restart") -> int:
        """Fail every QUEUED/RUNNING job (e.g. on startup); returns the count."""
        async with self._mutate():
            count = 0
            for job in self._jobs.values():
                if job.get("status") in {"QUEUED", "RUNNING"}:
                    job["status"] = "FAILED"
                    job["error"] = error
                    job["completed_at"] = _now()
                    count += 1
            return count

    async def prune(self, retention_days: int = JOB_RETENTION_DAYS) -> int:
        """Drop terminal (COMPLETED/FAILED) jobs older than the retention
        window. QUEUED/RUNNING jobs are always kept. Returns the drop count."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        async with self._mutate():
            stale = [
                job_id
                for job_id, job in self._jobs.items()
                if job.get("status") in {"COMPLETED", "FAILED"}
                and _parse_ts(job.get("completed_at") or job.get("created_at")) < cutoff
            ]
            for job_id in stale:
                del self._jobs[job_id]
            return len(stale)

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        # Clamp: an unbounded limit lets one request serialize the whole store.
        limit = max(1, min(int(limit), MAX_LIST_LIMIT))
        async with self._lock:
            jobs = list(self._jobs.values())
            jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
            # List views are summaries: never ship the full result payloads.
            return [
                {k: v for k, v in job.items() if k != "result"}
                for job in jobs[:limit]
            ]


# Single module-level store used by the API
STORE = JobStore()


async def run_job_background(job_id: str, query: str, country: str):
    """Background runner that invokes the main diplomat query and stores results."""
    ws_manager = None
    await STORE.update_job(job_id, status="RUNNING", started_at=_now(), progress=5)
    try:
        # Import lazily to avoid cycles; failures must also terminalize the job.
        from dip.ind_diplomat import PipelineError, diplomat_query

        # send progress update helper
        try:
            from dip.api.ws.ws_manager import manager as ws_manager
        except Exception:
            ws_manager = None

        if ws_manager:
            await ws_manager.publish_topic(f"job:{job_id}", {"type": "job.progress", "job_id": job_id, "status": "RUNNING", "progress": 5})

        result = await diplomat_query(query, country, job_id=job_id)
        if isinstance(result, PipelineError):
            raise RuntimeError(result.error)
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
