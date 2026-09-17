"""Persisted async assessment job store.

This is intentionally lightweight and framework-neutral. It can later be
backed by Prefect/Celery/Postgres without changing the analyst API contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from dip.core.atomic_json import write_json
from dip.core.Config.config import DATA_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


#: Canonical job lifecycle: QUEUED -> RUNNING -> COMPLETED | FAILED.
#: The pipeline assessment disposition (COMPLETE/REFUSED/HUMAN_REVIEW/
#: WITHHELD/ERROR) is retained inside ``result``, never copied into ``status``,
#: except that a pipeline-level ERROR means the job itself FAILED.
JOB_STATUSES = ("QUEUED", "RUNNING", "COMPLETED", "FAILED")

assert set(JOB_STATUSES) == {"QUEUED", "RUNNING", "COMPLETED", "FAILED"}


def _normalize_status(status: str) -> str:
    """Map legacy lowercase statuses to the canonical uppercase contract."""
    upper = str(status or "").upper()
    return upper if upper in JOB_STATUSES else "FAILED"


class AssessmentJob(BaseModel):
    job_id: str
    query: str
    country: str = "IND"
    status: str = "QUEUED"
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    trace_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AssessmentJobStore:
    """Tiny JSON-backed job store for DIP_8-compatible analyst APIs."""

    def __init__(self, path: str | Path = DATA_DIR / "job_store.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, AssessmentJob] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._jobs = {}
        for job_id, payload in raw.items():
            payload = dict(payload)
            if "status" in payload:
                payload["status"] = _normalize_status(payload["status"])
            self._jobs[job_id] = AssessmentJob(**payload)

    def _save(self) -> None:
        payload = {
            job_id: job.model_dump(mode="json")
            for job_id, job in self._jobs.items()
        }
        write_json(self.path, payload)

    def create(self, query: str, country: str = "IND") -> AssessmentJob:
        job = AssessmentJob(job_id=uuid4().hex[:12], query=query, country=country)
        self._jobs[job.job_id] = job
        self._save()
        return job

    def get(self, job_id: str) -> AssessmentJob:
        if job_id not in self._jobs:
            raise KeyError(job_id)
        return self._jobs[job_id]

    def list(self) -> List[AssessmentJob]:
        return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def mark_running(self, job_id: str) -> AssessmentJob:
        job = self.get(job_id)
        job.status = "RUNNING"
        job.updated_at = _now()
        self._save()
        return job

    def mark_complete(self, job_id: str, result: Dict[str, Any]) -> AssessmentJob:
        job = self.get(job_id)
        # Only a pipeline-level ERROR fails the job; every other assessment
        # disposition (COMPLETE/REFUSED/HUMAN_REVIEW/WITHHELD) is a completed
        # job whose outcome lives in ``result``.
        job.status = "FAILED" if str(result.get("status", "")).upper() == "ERROR" else "COMPLETED"
        job.result = result
        job.trace_id = result.get("trace_id")
        job.updated_at = _now()
        self._save()
        return job

    def mark_error(self, job_id: str, error: str) -> AssessmentJob:
        job = self.get(job_id)
        job.status = "FAILED"
        job.error = error
        job.updated_at = _now()
        self._save()
        return job


job_store = AssessmentJobStore()
