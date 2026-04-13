"""
SQLite-backed job persistence for the Analyst API.
Stores job state, phase transitions, and results.
DB file: runtime/analyst_jobs.db
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .models import (
    AssessmentRequest,
    AssessmentResult,
    JobListItem,
    JobPhase,
    JobStatus,
    PhaseUpdate,
)

# ── DB Location ────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "runtime" / "analyst_jobs.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class JobStore:
    """Thread-safe SQLite job store.  One instance per process."""

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = str(db_path or DB_PATH)
        self._lock = threading.Lock()
        self._ensure_dir()
        self._init_db()

    # ── Internal ──────────────────────────────────────────────────────

    def _ensure_dir(self):
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id       TEXT PRIMARY KEY,
                        status       TEXT NOT NULL DEFAULT 'QUEUED',
                        phase        TEXT NOT NULL DEFAULT 'QUEUED',
                        phase_detail TEXT NOT NULL DEFAULT '',
                        progress_pct INTEGER NOT NULL DEFAULT 0,
                        request_json TEXT NOT NULL DEFAULT '{}',
                        result_json  TEXT,
                        phases_json  TEXT NOT NULL DEFAULT '[]',
                        error        TEXT NOT NULL DEFAULT '',
                        created_at   TEXT NOT NULL,
                        started_at   TEXT,
                        completed_at TEXT
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    # ── Public API ────────────────────────────────────────────────────

    def create_job(self, request: AssessmentRequest) -> str:
        """Create a new job in QUEUED state.  Returns job_id."""
        job_id = f"job_{uuid4().hex[:12]}"
        now = _now_iso()
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    """INSERT INTO jobs
                       (job_id, status, phase, request_json, phases_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (job_id, "QUEUED", "QUEUED",
                     request.model_dump_json(), "[]", now),
                )
                conn.commit()
            finally:
                conn.close()
        return job_id

    def update_phase(
        self,
        job_id: str,
        phase: JobPhase,
        detail: str = "",
        progress_pct: int = 0,
    ):
        """Record a phase transition."""
        now = _now_iso()
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT phases_json, started_at, created_at FROM jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if not row:
                    return

                phases: list = json.loads(row["phases_json"] or "[]")
                created = row["created_at"]
                started = row["started_at"] or now
                elapsed = self._elapsed(created)

                phases.append({
                    "phase": phase.value,
                    "detail": detail,
                    "started_at": now,
                    "elapsed_sec": round(elapsed, 1),
                })

                conn.execute(
                    """UPDATE jobs
                       SET status=?, phase=?, phase_detail=?,
                           progress_pct=?, phases_json=?, started_at=COALESCE(started_at, ?)
                       WHERE job_id=?""",
                    (phase.value, phase.value, detail,
                     progress_pct, json.dumps(phases), now, job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def complete_job(self, job_id: str, result: AssessmentResult):
        """Mark job as COMPLETED and store the result."""
        now = _now_iso()
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    """UPDATE jobs
                       SET status='COMPLETED', phase='COMPLETED',
                           phase_detail='Assessment complete',
                           progress_pct=100, result_json=?, completed_at=?
                       WHERE job_id=?""",
                    (result.model_dump_json(), now, job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def fail_job(self, job_id: str, error: str):
        """Mark job as FAILED."""
        now = _now_iso()
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    """UPDATE jobs
                       SET status='FAILED', phase='FAILED',
                           phase_detail=?, progress_pct=0, error=?, completed_at=?
                       WHERE job_id=?""",
                    (error[:200], error, now, job_id),
                )
                conn.commit()
            finally:
                conn.close()

    def get_job(self, job_id: str) -> Optional[JobStatus]:
        """Get current status of a job."""
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE job_id=?", (job_id,)
                ).fetchone()
            finally:
                conn.close()

        if not row:
            return None

        phases = [PhaseUpdate(**p) for p in json.loads(row["phases_json"] or "[]")]
        created = row["created_at"] or ""
        elapsed = self._elapsed(created) if created else 0.0

        return JobStatus(
            job_id=row["job_id"],
            status=JobPhase(row["status"]),
            phase=JobPhase(row["phase"]),
            phase_detail=row["phase_detail"] or "",
            progress_pct=row["progress_pct"],
            phases_completed=phases,
            created_at=created,
            started_at=row["started_at"] or "",
            completed_at=row["completed_at"] or "",
            elapsed_sec=round(elapsed, 1),
            error=row["error"] or "",
        )

    def get_result(self, job_id: str) -> Optional[AssessmentResult]:
        """Get the full result of a completed job."""
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT result_json FROM jobs WHERE job_id=? AND status='COMPLETED'",
                    (job_id,),
                ).fetchone()
            finally:
                conn.close()

        if not row or not row["result_json"]:
            return None
        return AssessmentResult.model_validate_json(row["result_json"])

    def get_request(self, job_id: str) -> Optional[AssessmentRequest]:
        """Get the original request for a job."""
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT request_json FROM jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
            finally:
                conn.close()

        if not row or not row["request_json"]:
            return None
        return AssessmentRequest.model_validate_json(row["request_json"])

    def list_jobs(self, limit: int = 20, offset: int = 0) -> List[JobListItem]:
        """List jobs (newest first)."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    """SELECT job_id, status, request_json, result_json,
                              created_at, started_at, completed_at
                       FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall()
            finally:
                conn.close()

        items = []
        for row in rows:
            req = json.loads(row["request_json"] or "{}")
            res = json.loads(row["result_json"] or "{}") if row["result_json"] else {}
            created = row["created_at"] or ""
            completed = row["completed_at"]
            elapsed = self._elapsed_between(created, completed) if completed else self._elapsed(created)

            items.append(JobListItem(
                job_id=row["job_id"],
                status=row["status"],
                query_preview=(req.get("query", "")[:80] + "…") if len(req.get("query", "")) > 80 else req.get("query", ""),
                country_code=req.get("country_code", ""),
                risk_level=res.get("risk_level", ""),
                confidence=res.get("confidence", 0.0),
                created_at=created,
                elapsed_sec=round(elapsed, 1),
            ))
        return items

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _elapsed(iso_start: str) -> float:
        try:
            start = datetime.fromisoformat(iso_start.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - start).total_seconds()
        except Exception:
            return 0.0

    @staticmethod
    def _elapsed_between(iso_start: str, iso_end: str) -> float:
        try:
            start = datetime.fromisoformat(iso_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(iso_end.replace("Z", "+00:00"))
            return (end - start).total_seconds()
        except Exception:
            return 0.0


# Singleton
job_store = JobStore()
