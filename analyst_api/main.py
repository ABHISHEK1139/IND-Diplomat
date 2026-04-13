"""
IND-Diplomat Analyst API — FastAPI Application
================================================
Port 8100  ·  Async job system  ·  Evidence provenance  ·  White-box reasoning

Endpoints:
  POST  /api/v3/assess              → Start async assessment
  GET   /api/v3/jobs/{id}           → Job status + progress
  GET   /api/v3/jobs/{id}/result    → Full structured result
  GET   /api/v3/jobs/{id}/evidence  → Evidence provenance chain
  GET   /api/v3/jobs/{id}/verify    → Reasoning / verification chain
  GET   /api/v3/jobs                → List past jobs
  GET   /api/v3/trends/{cc}         → Temporal trend data
  GET   /api/v3/health              → System health
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from Config import config

# ── Project root ──────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .engine_bridge import run_assessment
from .job_store import job_store
from .models import (
    AssessmentRequest,
    AssessmentResult,
    JobListItem,
    JobStatus,
    TrendPoint,
)
from .trend_store import get_latest_alert, get_trends

# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="IND-Diplomat Analyst API",
    description="White-box intelligence workstation — async assessments with full provenance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/v3/assess", response_model=dict)
async def start_assessment(body: AssessmentRequest):
    """Submit a new intelligence assessment.  Returns immediately with job_id."""
    job_id = job_store.create_job(body)
    # Launch engine in background
    asyncio.create_task(run_assessment(job_id, body))
    return {"job_id": job_id, "status": "QUEUED"}


@app.get("/api/v3/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Poll job status and phase progress."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@app.get("/api/v3/jobs/{job_id}/result", response_model=AssessmentResult)
async def get_job_result(job_id: str):
    """Get the full structured result of a completed assessment."""
    result = job_store.get_result(job_id)
    if not result:
        # Check if job exists but not complete
        job = job_store.get_job(job_id)
        if job and job.status.value not in ("COMPLETED", "FAILED"):
            raise HTTPException(status_code=202,
                                detail=f"Job {job_id} still running (phase: {job.phase.value})")
        if job and job.status.value == "FAILED":
            raise HTTPException(status_code=500,
                                detail=f"Job failed: {job.error}")
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return result


@app.get("/api/v3/jobs/{job_id}/evidence")
async def get_job_evidence(job_id: str):
    """Get the evidence provenance chain for a completed assessment."""
    result = job_store.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No result for job {job_id}")
    return {
        "job_id": job_id,
        "evidence_count": len(result.evidence_chain),
        "evidence": [e.model_dump() for e in result.evidence_chain],
    }


@app.get("/api/v3/jobs/{job_id}/verify")
async def get_job_verification(job_id: str):
    """Get the reasoning / verification chain (white-box explainability)."""
    result = job_store.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No result for job {job_id}")
    chain = result.verification_chain
    if not chain:
        return {"job_id": job_id, "steps": [], "total_steps": 0}
    return {
        "job_id": job_id,
        "total_steps": chain.total_steps,
        "steps": [s.model_dump() for s in chain.steps],
    }


@app.get("/api/v3/jobs", response_model=List[JobListItem])
async def list_jobs(limit: int = 20, offset: int = 0):
    """List past assessment jobs (newest first)."""
    return job_store.list_jobs(limit=min(limit, 100), offset=offset)


@app.get("/api/v3/trends/{country_code}", response_model=List[TrendPoint])
async def get_country_trends(country_code: str, hours: float = 72):
    """Get temporal escalation trend data for Chart.js."""
    return get_trends(country_code.upper(), hours_back=hours)


@app.get("/api/v3/alerts/{country_code}")
async def get_country_alert(country_code: str):
    """Get the latest alert for a country."""
    alert = get_latest_alert(country_code.upper())
    if not alert:
        return {"country": country_code.upper(), "alert": None}
    return {"country": country_code.upper(), "alert": alert}


@app.get("/api/v3/health")
async def health_check():
    """System health status."""
    health = {"status": "ok", "api_version": "1.0.0"}
    try:
        from engine.Layer4_Analysis.core.system_guardian.full_system_check import (
            run_full_system_check,
        )
        report = run_full_system_check()
        checks = report.get("checks", {}) if isinstance(report, dict) else {}
        passed = sum(1 for payload in checks.values() if bool(payload.get("ok", False)))
        total = len(checks)
        health["system_checks"] = f"{passed}/{total} passed"
        health["checks"] = checks
        health["overall_ok"] = bool(report.get("overall_ok", total == passed)) if isinstance(report, dict) else False
        health["failed_checks"] = list(report.get("failed_checks", [])) if isinstance(report, dict) else []
    except Exception as exc:
        health["system_checks"] = f"unavailable: {exc}"
    return health


# ── Standalone runner ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 55)
    print("  IND-Diplomat Analyst API v1.0.0")
    print("=" * 55)
    print(f"\n  Endpoints: http://localhost:8100/api/v3/")
    print(f"  Docs:      http://localhost:8100/docs\n")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8100)
