
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import time
from Config import config

# Lightweight in-process metrics for local observability.
METRICS = {
    "requests_total": 0,
    "errors_total": 0,
    "latency_ms_total": 0.0,
    "by_path": {},
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IND-Diplomat-API")

# Create App
app = FastAPI(
    title="IND-Diplomat Intelligence API",
    description="Exposes geopolitical signals and knowledge graph to the MoltBot interface.",
    version="1.0.0"
)

# CORS (Allow local UI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
try:
    from .endpoints import router as api_router
    app.include_router(api_router, prefix="/api/v1")
except ImportError:
    logger.warning("Endpoints module not found (yet). Running in skeleton mode.")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    METRICS["requests_total"] += 1
    path_metrics = METRICS["by_path"].setdefault(
        request.url.path,
        {"count": 0, "errors": 0, "latency_ms_total": 0.0},
    )
    path_metrics["count"] += 1

    try:
        response = await call_next(request)
    except Exception:
        METRICS["errors_total"] += 1
        path_metrics["errors"] += 1
        raise

    latency_ms = (time.perf_counter() - started) * 1000.0
    METRICS["latency_ms_total"] += latency_ms
    path_metrics["latency_ms_total"] += latency_ms

    if response.status_code >= 500:
        METRICS["errors_total"] += 1
        path_metrics["errors"] += 1

    return response

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {
        "status": "operational",
        "system": "IND-Diplomat Intelligence Engine",
        "version": "1.0.0"
    }


@app.get("/metrics")
def metrics():
    """Simple JSON metrics endpoint for quick production diagnostics."""
    avg_latency = (
        METRICS["latency_ms_total"] / METRICS["requests_total"]
        if METRICS["requests_total"]
        else 0.0
    )
    by_path = {}
    for path, stats in METRICS["by_path"].items():
        count = stats["count"] or 1
        by_path[path] = {
            "count": stats["count"],
            "errors": stats["errors"],
            "avg_latency_ms": round(stats["latency_ms_total"] / count, 3),
        }
    return {
        "requests_total": METRICS["requests_total"],
        "errors_total": METRICS["errors_total"],
        "avg_latency_ms": round(avg_latency, 3),
        "by_path": by_path,
    }

if __name__ == "__main__":
    uvicorn.run("analysis_api.main:app", host="0.0.0.0", port=8000, reload=True)
