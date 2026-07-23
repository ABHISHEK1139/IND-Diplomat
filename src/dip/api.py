"""
FastAPI Server for Politiq AI
===============================
Exposes the 7-layer pipeline and War Gaming Engine to the Web Dashboard.
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import os
import sys
import threading
import litellm

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Allow normal LLM execution timeouts
litellm.max_retries = 2
# Remove 2-second timeout so the model can actually think
if "LITELLM_TIMEOUT" in os.environ:
    del os.environ["LITELLM_TIMEOUT"]

from dip.unified_pipeline import execute
from dip.layer3_state.state_provider import StateProvider
from dip.layer8_wargaming.scenario_engine import run_wargame
from dip.core.schema import WargameAction
from dip.Config.config import config


# Analyst job store (async jobs)
from dip.analyst_api.job_store import STORE, run_job_background
from dip.api_ws.router import router as ws_router
from dip.nextgen.job_store import AssessmentJob, job_store
from dip.nextgen.oss_adapters import OSSAdapterRegistry

app = FastAPI(title="Politiq AI API", version="2.5")


@app.on_event("startup")
async def validate_runtime_configuration() -> None:
    """Fail at API startup instead of during an LLM request in production."""
    if config.ENVIRONMENT.lower() == "production":
        config.validate_runtime_credentials()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AssessRequest(BaseModel):
    query: str
    country: str = "IND"

class HeadOfCountryRequest(BaseModel):
    query: str
    country: str = "IND"
    theater: str | None = None

class WargameRequest(BaseModel):
    query: str
    country: str
    action: str

@app.post("/api/assess")
async def api_assess(request: AssessRequest):
    try:
        result = await execute(request.query, request.country)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v2/query")
async def v2_query(request: AssessRequest):
    """Quick synchronous-style query endpoint (awaits pipeline)."""
    try:
        result = await execute(request.query, request.country)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _run_assessment_job(job_id: str) -> None:
    try:
        job = job_store.mark_running(job_id)
        result = await execute(job.query, job.country)
        job_store.mark_complete(job_id, result)
    except Exception as exc:
        job_store.mark_error(job_id, str(exc))

@app.post("/api/v3/assess")
async def api_v3_assess(request: AssessRequest):
    """DIP_8-compatible async assessment endpoint."""
    job = job_store.create(request.query, request.country)
    asyncio.create_task(_run_assessment_job(job.job_id))
    return {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at,
        "status_url": f"/api/v3/jobs/{job.job_id}",
        "result_url": f"/api/v3/jobs/{job.job_id}/result",
    }

@app.get("/api/v3/jobs")
async def api_v3_jobs():
    return [job.model_dump(mode="json") for job in job_store.list()]

@app.get("/api/v3/jobs/{job_id}")
async def api_v3_job_status(job_id: str):
    try:
        job = job_store.get(job_id)
        return {
            "job_id": job.job_id,
            "status": job.status,
            "trace_id": job.trace_id,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "error": job.error,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")

@app.get("/api/v3/jobs/{job_id}/status")
async def api_v3_job_status_alias(job_id: str):
    return await api_v3_job_status(job_id)

@app.get("/api/v3/jobs/{job_id}/result")
async def api_v3_job_result(job_id: str):
    try:
        job = job_store.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")
    if job.result is None:
        return {"job_id": job.job_id, "status": job.status, "result": None, "error": job.error}
    return job.result

@app.get("/api/v3/jobs/{job_id}/evidence")
async def api_v3_job_evidence(job_id: str):
    result = await api_v3_job_result(job_id)
    if "query" not in result:
        return result
    return {
        "job_id": job_id,
        "trace_id": result.get("trace_id"),
        "evidence_log": result.get("evidence_log", []),
        "fuzzy_trace": result.get("fuzzy_trace", {}),
        "blackboard_events": result.get("blackboard_events", []),
    }

@app.get("/api/v3/jobs/{job_id}/verification")
async def api_v3_job_verification(job_id: str):
    result = await api_v3_job_result(job_id)
    if "query" not in result:
        return result
    return {
        "job_id": job_id,
        "trace_id": result.get("trace_id"),
        "verification_score": result.get("verification_score", 0.0),
        "refusal": result.get("refusal"),
        "red_team_report": result.get("red_team_report"),
        "promotion_status": result.get("promotion_status", []),
    }

@app.get("/api/v3/jobs/{job_id}/verify")
async def api_v3_job_verify_alias(job_id: str):
    return await api_v3_job_verification(job_id)

@app.get("/api/v3/trends/{country_code}")
async def api_v3_trends(country_code: str):
    jobs = [
        job for job in job_store.list()
        if job.country.upper() == country_code.upper() and job.result
    ]
    return [
        {
            "job_id": job.job_id,
            "trace_id": job.trace_id,
            "created_at": job.created_at,
            "threat_level": job.result.get("threat_level"),
            "sre_score": (job.result.get("nextgen_sre") or {}).get("sre_escalation_score"),
            "verification_score": job.result.get("verification_score", 0.0),
        }
        for job in jobs[:50]
    ]

@app.get("/api/v3/alerts/{country_code}")
async def api_v3_alerts(country_code: str):
    trends = await api_v3_trends(country_code)
    return [
        item for item in trends
        if str(item.get("threat_level", "")).upper() in {"HIGH", "CRITICAL"}
        or float(item.get("sre_score") or 0.0) >= 0.65
    ]

@app.post("/api/head-of-country")
async def api_head_of_country(request: HeadOfCountryRequest):
    try:
        result = await execute(request.query, request.country)
        return result.get("head_of_country_briefing", result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v3/head-of-country")
async def api_head_of_country_v3(request: HeadOfCountryRequest):
    return await api_head_of_country(request)

@app.get("/health")
async def health_check():
    registry = OSSAdapterRegistry()
    return {
        "status": "healthy",
        "version": app.version,
        "oss_adapters": registry.status(),
    }

@app.get("/api/v3/health")
async def api_v3_health():
    return await health_check()


# ── Prometheus Metrics Endpoint ──────────────────────────────────

# Lazy-init Prometheus metrics
_prom_initialized = False
_prom_counters: dict = {}
_prom_gauges: dict = {}
_prom_histograms: dict = {}
_prom_lock = threading.Lock()

def _init_prometheus():
    """Initialize Prometheus metrics collectors."""
    global _prom_initialized, _prom_counters, _prom_gauges, _prom_histograms
    if _prom_initialized:
        return
    with _prom_lock:
        if _prom_initialized:
            return
        try:
            from prometheus_client import Counter, Gauge, Histogram

            _prom_counters = {
                "assessments_total": Counter(
                    "dip_assessments_total", "Total assessments run",
                    ["country", "status"]
                ),
                "errors_total": Counter(
                    "dip_errors_total", "Total pipeline errors",
                    ["error_type"]
                ),
                "gate_withheld_total": Counter(
                    "dip_gate_withheld_total", "Gate WITHHELD count",
                    ["country"]
                ),
            }

            _prom_gauges = {
                "pipeline_active": Gauge(
                    "dip_pipeline_active", "Currently running pipelines"
                ),
                "last_threat_level": Gauge(
                    "dip_last_threat_level", "Last assessment threat level (0-3)",
                    ["country"]
                ),
                "cache_size": Gauge(
                    "dip_cache_size", "Number of cached items"
                ),
            }

            _prom_histograms = {
                "pipeline_duration_seconds": Histogram(
                    "dip_pipeline_duration_seconds", "Pipeline execution time",
                    buckets=[1, 5, 10, 15, 30, 60, 120, 300]
                ),
                "layer_duration_seconds": Histogram(
                    "dip_layer_duration_seconds", "Per-layer execution time",
                    ["layer"], buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
                ),
            }

            _prom_initialized = True
        except ImportError:
            return


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    _init_prometheus()
    if not _prom_initialized:
        return Response(content="prometheus_client not installed", status_code=500)
    
    from prometheus_client import generate_latest
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4",
    )

@app.post("/api/wargame")
async def api_wargame(request: WargameRequest):
    try:
        provider = StateProvider()
        base_context = await provider.build_state_context(request.country, request.query)
        action = WargameAction(description=request.action, target_country=request.country)
        result = await run_wargame(base_context, action)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/self-model")
async def api_self_model():
    """Return the system's self-model dashboard."""
    try:
        from dip.nextgen.self_model import get_self_model
        model = get_self_model()
        return model.get_dashboard()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/jobs/{job_id}/stix2")
async def api_v3_job_stix2(job_id: str):
    """Export assessment as STIX 2.1 bundle."""
    try:
        job = job_store.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")
    if job.result is None:
        raise HTTPException(status_code=404, detail="job not completed")
    try:
        from dip.nextgen.stix2_adapter import create_stix2_adapter
        adapter = create_stix2_adapter()
        if not adapter:
            raise HTTPException(status_code=501, detail="stix2 not installed. pip install stix2")
        from dip.nextgen.contracts import create_assessment_goal, HeadOfStateBriefing
        goal = create_assessment_goal(job.result.get("query", ""), country=job.result.get("country", "UNKNOWN"))
        briefing = HeadOfStateBriefing(**job.result.get("head_of_country_briefing", {})) if job.result.get("head_of_country_briefing") else HeadOfStateBriefing(goal=goal)
        bundle = adapter.export_assessment(goal, briefing, job.result)
        return json.loads(bundle.serialize(pretty=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# mount websocket router
app.include_router(ws_router)

# Mount the frontend directory to serve static HTML
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# ---------------------
# Analyst async job endpoints (/api/v3)
# ---------------------


@app.post("/api/v3/analyst-jobs")
async def create_job(request: AssessRequest):
    """Create an async analyst job and return job metadata."""
    try:
        job = await STORE.create_job(request.query, request.country)
        # schedule background runner
        asyncio.create_task(run_job_background(job["job_id"], request.query, request.country))
        return {"job_id": job["job_id"], "status": job["status"], "created_at": job["created_at"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/analyst-jobs")
async def list_jobs(limit: int = 50):
    jobs = await STORE.list_jobs(limit=limit)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/api/v3/analyst-jobs/{job_id}")
async def get_job(job_id: str):
    job = await STORE.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/v3/analyst-jobs/{job_id}/result")
async def get_job_result(job_id: str):
    job = await STORE.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("status") != "COMPLETED":
        return {"status": job.get("status"), "progress": job.get("progress", 0)}
    return {"status": "COMPLETED", "result": job.get("result")}
