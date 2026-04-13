"""
IND-Diplomat API v4.0.0
Production-grade REST API with all features integrated.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Security, Depends, Request, Response
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
import os
import uuid
import time
import asyncio

# Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATELIMIT_AVAILABLE = True
except ImportError:
    RATELIMIT_AVAILABLE = False

# Layer engine imports
try:
    from engine.Layer4_Analysis.core.coordinator import Coordinator
except Exception:
    Coordinator = None

try:
    from engine.Layer4_Analysis.core.llm_client import llm_client
except Exception:
    llm_client = None

try:
    from engine.Layer4_Analysis.safety.guard import llama_guard
except Exception:
    llama_guard = None

try:
    from engine.Layer4_Analysis.intake.question_scope_checker import check_question_scope
except Exception:
    check_question_scope = None

try:
    from engine.Layer3_StateModel.construction.analysis_readiness import evaluate_analysis_readiness
except Exception:
    evaluate_analysis_readiness = None

# Pipeline (proper entry point — routes L3→L2→L4)
from Config.pipeline import initialize, run_query

try:
    from Utils.logger import logger
except Exception:
    import logging
    logger = logging.getLogger("api")

try:
    from Utils.cache import cache
except Exception:
    cache = None

try:
    from Utils.session import session_manager
except Exception:
    session_manager = None

try:
    from Utils.audit import audit_trail
except Exception:
    audit_trail = None

try:
    from Utils.report_generator import report_generator
except Exception:
    report_generator = None

try:
    from API.metrics import metrics
except Exception:
    metrics = None

try:
    from API.auth import jwt_auth, RBAC, Role, User
except Exception:
    jwt_auth = None
    RBAC = None
    Role = None
    User = None

# Config
from Config import config


# Rate limiter setup
if RATELIMIT_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None


def _log_event(level: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """Send structured logs to either the custom logger or stdlib logging."""
    payload = dict(payload or {})
    
    # Try to use the custom logger methods first
    method = getattr(logger, level, None)
    if callable(method):
        try:
            method(message, **payload)
            return
        except TypeError:
            try:
                method(f"{message} | {payload}" if payload else message)
                return
            except TypeError:
                pass
    
    # If custom logger doesn't have the method, try standard logging
    import logging
    
    # For standard logging, we need to map level strings to logging constants
    level_map = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "debug": logging.DEBUG,
        "critical": logging.CRITICAL
    }
    
    log_level = level_map.get(level.lower(), logging.INFO)
    fallback_logger = logging.getLogger("api")
    
    # For standard logging, we need to format the message with payload
    formatted_message = f"{message}"
    if payload:
        formatted_message = f"{message} | {payload}"
    
    fallback_logger.log(log_level, formatted_message)


def _cache_get_query_result(query: str) -> Optional[Dict[str, Any]]:
    if cache and hasattr(cache, "get_cached_query_result"):
        try:
            return cache.get_cached_query_result(query)
        except Exception:
            return None
    return None


def _cache_set_query_result(query: str, result: Dict[str, Any]) -> None:
    if cache and hasattr(cache, "cache_query_result"):
        try:
            cache.cache_query_result(query, result)
        except Exception:
            pass


def _cache_connected() -> bool:
    if cache and hasattr(cache, "is_connected"):
        try:
            return bool(cache.is_connected())
        except Exception:
            return False
    return False


def _llm_available() -> bool:
    return bool(llm_client and getattr(llm_client, "is_available", False))


def _record_cache_access(cache_type: str, hit: bool) -> None:
    if metrics and hasattr(metrics, "record_cache_access"):
        try:
            metrics.record_cache_access(cache_type, hit)
        except Exception:
            pass


def _record_request(endpoint: str, method: str, status: int, latency: float) -> None:
    if metrics and hasattr(metrics, "record_request"):
        try:
            metrics.record_request(endpoint, method, status, latency)
        except Exception:
            pass


def _record_faithfulness(score: float) -> None:
    if metrics and hasattr(metrics, "record_faithfulness"):
        try:
            metrics.record_faithfulness(score)
        except Exception:
            pass


async def _audit_log(*args, **kwargs) -> None:
    if audit_trail and hasattr(audit_trail, "log"):
        try:
            await audit_trail.log(*args, **kwargs)
        except Exception:
            pass


def _session_add_message(session_id: Optional[str], role: str, content: str) -> None:
    if session_id and session_manager and hasattr(session_manager, "add_message"):
        try:
            session_manager.add_message(session_id, role, content)
        except Exception:
            pass


async def _classify_content(content: str) -> Dict[str, Any]:
    if llama_guard and hasattr(llama_guard, "classify_content"):
        try:
            return await llama_guard.classify_content(content)
        except Exception as exc:
            return {"is_safe": True, "reason": f"safety_unavailable: {exc}"}
    return {"is_safe": True, "reason": "safety_unavailable"}


def _normalize_sources(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _build_query_response(
    result: Dict[str, Any],
    *,
    request_id: str,
    session_id: Optional[str],
    reasoning_engine: str,
) -> Dict[str, Any]:
    answer = str(result.get("answer", "No answer generated.") or "No answer generated.")
    confidence = float(result.get("confidence", 0.0) or 0.0)
    outcome = str(result.get("outcome", "ASSESSMENT") or "ASSESSMENT")
    sources = _normalize_sources(result.get("sources"))
    warnings = list(result.get("operational_warnings", []) or [])
    if outcome != "ASSESSMENT":
        warnings.append(f"Pipeline outcome: {outcome}")

    _record_faithfulness(confidence)

    return {
        "answer": answer,
        "sources": sources[:5],
        "faithfulness_score": confidence,
        "warnings": warnings,
        "reasoning_engine": reasoning_engine,
        "request_id": request_id,
        "session_id": session_id,
        "confidence_ledger": result.get("confidence_ledger") or [],
        "dossier_hits": result.get("dossier_hits") or [],
        "scenario_playbook": result.get("scenario_playbook"),
        "temporal_briefing": result.get("temporal_briefing"),
    }


def _build_v2_response(
    result: Dict[str, Any],
    *,
    request_id: str,
    session_id: Optional[str],
) -> Dict[str, Any]:
    response_data = _build_query_response(
        result,
        request_id=request_id,
        session_id=session_id,
        reasoning_engine="unified_pipeline_v2",
    )
    response_data.update(
        {
            "outcome": str(result.get("outcome", "ASSESSMENT") or "ASSESSMENT"),
            "trace_id": result.get("trace_id", request_id),
            "verified": bool(result.get("verified", False)),
            "intervention_required": bool(result.get("intervention_required", False)),
            "intervention_id": result.get("intervention_id"),
            "legal_citations": int(result.get("legal_citations", 0) or 0),
            "crag_correction_applied": bool(result.get("crag_correction_applied", False)),
            "debate_outcome": result.get("debate_outcome"),
            "layer4_allowed": result.get("layer4_allowed"),
            "layer4_gate_reason": result.get("layer4_gate_reason"),
            "layer4_scope": result.get("layer4_scope"),
            "layer4_readiness": result.get("layer4_readiness"),
            "intelligence_report": result.get("intelligence_report"),
            "risk_level": result.get("risk_level"),
            "analytic_confidence": float(result.get("analytic_confidence", 0.0) or 0.0),
            "epistemic_confidence": float(result.get("epistemic_confidence", 0.0) or 0.0),
            "early_warning_index": float(result.get("early_warning_index", 0.0) or 0.0),
            "escalation_sync": float(result.get("escalation_sync", 0.0) or 0.0),
            "prewar_detected": bool(result.get("prewar_detected", False)),
            "warning": result.get("warning"),
            "gate_verdict": result.get("gate_verdict"),
            "council_session": result.get("council_session"),
            "references": _normalize_sources(result.get("references")),
            "whitebox": {
                "outcome": str(result.get("outcome", "ASSESSMENT") or "ASSESSMENT"),
                "trace_id": result.get("trace_id", request_id),
                "gate_verdict": result.get("gate_verdict"),
                "council_session": result.get("council_session"),
                "intelligence_report": result.get("intelligence_report"),
                "layer4_scope": result.get("layer4_scope"),
                "layer4_readiness": result.get("layer4_readiness"),
                "operational_warnings": result.get("operational_warnings", []) or [],
            },
        }
    )
    return response_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    _log_event("info", "IND-Diplomat API starting up", {"version": "4.0.0"})
    if audit_trail and hasattr(audit_trail, "connect"):
        try:
            await audit_trail.connect()
        except Exception:
            pass
    yield
    # Shutdown
    _log_event("info", "IND-Diplomat API shutting down")


# Create FastAPI app
app = FastAPI(
    title="IND-Diplomat Sovereign Intelligence API",
    description="Production-grade diplomatic intelligence system with advanced reasoning and verification",
    version="4.0.0",
    lifespan=lifespan
)

# Add rate limiting
if RATELIMIT_AVAILABLE and limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Pydantic Models ==============

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    use_mcts: bool = False
    use_causal: bool = False
    use_red_team: bool = False
    use_multi_perspective: bool = False
    session_id: Optional[str] = None

class TokenRequest(BaseModel):
    username: str
    password: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    faithfulness_score: float
    warnings: List[str]
    reasoning_engine: str
    c2pa_manifest: Optional[Dict[str, Any]] = None
    request_id: str
    session_id: Optional[str] = None
    confidence_ledger: Optional[List[Dict[str, Any]]] = None
    dossier_hits: Optional[List[Dict[str, Any]]] = None
    scenario_playbook: Optional[Dict[str, Any]] = None
    temporal_briefing: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    components: Dict[str, str]


# ============== Security ==============

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_api_key_or_jwt(
    api_key: str = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> Optional[User]:
    """Validates API key or JWT token."""
    # Check API key first
    if api_key:
        valid_key = str(
            os.getenv("IND_DIPLOMAT_API_KEY")
            or os.getenv("API_KEY")
            or ""
        ).strip()

        if not valid_key:
            raise HTTPException(
                status_code=401,
                detail="API key auth is not configured. Set IND_DIPLOMAT_API_KEY (or API_KEY) in environment.",
            )

        if api_key == valid_key:
            return User(user_id="api_key_user", username="api", role=Role.ANALYST, organization="API")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Check JWT
    if bearer:
        user = jwt_auth.get_user_from_token(bearer.credentials)
        if user:
            return user
    
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Use Bearer token or configure X-API-Key via IND_DIPLOMAT_API_KEY.",
    )


def require_permission(permission: str):
    """Decorator to require specific permission."""
    async def check_permission(user: User = Depends(get_api_key_or_jwt)):
        if not RBAC.has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
        return user
    return check_permission


# ============== Endpoints ==============

@app.post("/auth/token")
async def login(request: TokenRequest):
    """Authenticates user and returns JWT tokens."""
    user = jwt_auth.authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "access_token": jwt_auth.create_access_token(user),
        "refresh_token": jwt_auth.create_refresh_token(user),
        "token_type": "bearer"
    }


@app.post("/query", response_model=QueryResponse)
async def query(
    request: Request,
    body: QueryRequest,
    user: User = Depends(require_permission("query"))
):
    """Main query endpoint with full pipeline."""
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    
    _log_event("info", "Query received", {
        "request_id": request_id,
        "user": user.username,
        "query_length": len(body.query)
    })
    
    # Check cache first
    cached = _cache_get_query_result(body.query)
    if cached:
        _record_cache_access("query", hit=True)
        cached["request_id"] = request_id
        cached["session_id"] = body.session_id
        await _audit_log(user.user_id, "query", "cache_hit", {"query": body.query[:100]})
        return cached
    
    _record_cache_access("query", hit=False)
    
    # Input safety check
    safety_result = await _classify_content(body.query)
    if not safety_result["is_safe"]:
        await _audit_log(user.user_id, "query_blocked", "safety", safety_result)
        raise HTTPException(status_code=400, detail=f"Query blocked: {safety_result['reason']}")
    
    # Session handling
    session_id = body.session_id
    _session_add_message(session_id, "user", body.query)
    
    # Process query via Pipeline
    # This ensures consistency with CLI and Test scripts
    result = await run_query(
        query=body.query,
        user_id=None, # user.user_id if available context
        session_id=session_id,
        country_code="UNKNOWN", # Should be extracted or passed
        use_mcts=body.use_mcts,
        use_red_team=body.use_red_team,
        max_investigation_loops=2
    )

    # Normalize result to API format
    response_data = _build_query_response(
        result,
        request_id=request_id,
        session_id=session_id,
        reasoning_engine=str(result.get("method", "pipeline") or "pipeline"),
    )
    
    # Cache result
    _cache_set_query_result(body.query, response_data)
    
    # Session
    _session_add_message(session_id, "assistant", response_data["answer"])
    
    # Audit
    await _audit_log(
        user.user_id, "query", "success",
        {"query": body.query[:100], "faithfulness": response_data["faithfulness_score"]},
        request_id=request_id,
        response_status=200
    )
    
    # Metrics
    latency = time.perf_counter() - start_time
    _record_request("/query", "POST", 200, latency)
    
    return response_data


@app.post("/v2/query")
async def query_v2(
    request: Request,
    body: QueryRequest,
    user: User = Depends(require_permission("query"))
):
    """
    V2 Query Endpoint - Uses fully integrated pipeline with:
    - Observability tracing
    - RBAC document filtering
    - CRAG correction
    - CoVe verification
    - MADAM-RAG debate (for low confidence)
    - HITL intervention
    - Legal provenance mapping
    - DPDP PII masking
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    
    _log_event("info", "V2 Query received", {
        "request_id": request_id,
        "user": user.username,
        "query_length": len(body.query)
    })
    
    # Input safety check
    safety_result = await _classify_content(body.query)
    if not safety_result["is_safe"]:
        await _audit_log(user.user_id, "query_blocked", "safety", safety_result)
        raise HTTPException(status_code=400, detail=f"Query blocked: {safety_result['reason']}")
    
    try:
        result = await run_query(
            query=body.query,
            user_id=user.user_id,
            session_id=body.session_id,
            country_code="UNKNOWN",
            use_mcts=body.use_mcts,
            use_red_team=body.use_red_team,
            use_multi_perspective=body.use_multi_perspective,
        )
        
        response_data = _build_v2_response(
            result,
            request_id=request_id,
            session_id=body.session_id,
        )
        
        # Add warnings
        if response_data["faithfulness_score"] < 0.5:
            response_data["warnings"].append("Low confidence score - answer may need verification")
        if response_data["intervention_required"]:
            response_data["warnings"].append("Human-in-the-loop intervention requested")
        if response_data["crag_correction_applied"]:
            response_data["warnings"].append("Retrieval was corrected by CRAG")
        if response_data["layer4_allowed"] is False:
            response_data["warnings"].append(f"Layer-4 gate: {response_data['layer4_gate_reason'] or 'blocked'}")
        
        # Cache
        _cache_set_query_result(body.query, response_data)
        
        # Session
        _session_add_message(body.session_id, "assistant", response_data["answer"])
        
        # Audit
        await _audit_log(
            user.user_id, "query_v2", "success",
            {
                "query": body.query[:100],
                "confidence": response_data["faithfulness_score"],
                "trace_id": response_data["trace_id"],
            },
            request_id=request_id,
            response_status=200
        )
        
        # Metrics
        latency = time.perf_counter() - start_time
        _record_request("/v2/query", "POST", 200, latency)
        
        return response_data
    
    except Exception as e:
        _log_event("error", f"V2 Query failed: {e}", {"request_id": request_id})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_stream(
    request: Request,
    body: QueryRequest,
    user: User = Depends(require_permission("query_stream"))
):
    """Streaming query endpoint for real-time responses."""
    request_id = str(uuid.uuid4())
    
    # Safety check
    safety_result = await _classify_content(body.query)
    if not safety_result["is_safe"]:
        raise HTTPException(status_code=400, detail=f"Query blocked: {safety_result['reason']}")

    scope_reason = None
    if check_question_scope:
        scope = check_question_scope(body.query)
        if not scope.allowed:
            scope_reason = str(scope.reason)
            raise HTTPException(status_code=422, detail=f"Out of scope for grounded analysis: {scope_reason}")

    result = await run_query(
        query=body.query,
        user_id=user.user_id,
        session_id=body.session_id,
        country_code="UNKNOWN",
        use_mcts=body.use_mcts,
        use_red_team=body.use_red_team,
        use_multi_perspective=body.use_multi_perspective,
    )
    outcome = str(result.get("outcome", "ASSESSMENT") or "ASSESSMENT")
    if outcome != "ASSESSMENT":
        detail = scope_reason or f"Pipeline outcome: {outcome}"
        raise HTTPException(status_code=422, detail=detail)
    answer = str(result.get("answer", "") or "")
    
    async def generate():
        chunk_size = 256
        for idx in range(0, len(answer), chunk_size):
            yield f"data: {answer[idx : idx + chunk_size]}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Request-ID": request_id}
    )


@app.get("/session/new")
async def create_session(user: User = Depends(get_api_key_or_jwt)):
    """Creates a new conversation session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager unavailable")
    session = session_manager.create_session(user.user_id)
    return {"session_id": session.session_id}


@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str, user: User = Depends(get_api_key_or_jwt)):
    """Gets conversation history for a session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager unavailable")
    history = session_manager.get_conversation_history(session_id)
    return {"history": history}


@app.get("/export/{format}")
async def export_report(
    format: str,
    query: str,
    user: User = Depends(require_permission("export_report"))
):
    """Exports query result as PDF or DOCX."""
    if format not in ["pdf", "docx"]:
        raise HTTPException(status_code=400, detail="Invalid format")
    
    # Get cached or process query
    cached = _cache_get_query_result(query)
    if not cached:
        raise HTTPException(status_code=404, detail="Query not found in cache")
    
    cached["query"] = query
    
    if format == "pdf":
        content = report_generator.generate_pdf(cached)
        media_type = "application/pdf"
    else:
        content = report_generator.generate_docx(cached)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    if content is None:
        raise HTTPException(status_code=500, detail="Report generation failed")
    
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="report.{format}"'}
    )


# ============== Health & Metrics ==============

@app.get("/health", response_model=HealthResponse)
async def health():
    """Basic health check."""
    return {
        "status": "healthy",
        "version": "4.0.0",
        "components": {
            "cache": "connected" if _cache_connected() else "disconnected",
            "llm": "available" if _llm_available() else "degraded"
        }
    }


@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe."""
    # Check critical components
    if not _llm_available():
        raise HTTPException(status_code=503, detail="LLM not available")
    return {"status": "ready"}


@app.get("/metrics")
async def get_metrics(user: User = Depends(require_permission("view_metrics"))):
    """Returns Prometheus metrics."""
    content = b"# Metrics unavailable\n"
    media_type = "text/plain"
    if metrics:
        try:
            content = metrics.get_metrics()
            media_type = metrics.get_content_type()
        except Exception:
            pass
    return Response(
        content=content,
        media_type=media_type
    )


@app.get("/audit")
async def get_audit(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    user: User = Depends(require_permission("view_audit"))
):
    """Queries audit log."""
    if not audit_trail or not hasattr(audit_trail, "query"):
        return {"entries": []}
    entries = await audit_trail.query(user_id=user_id, action=action, limit=limit)
    return {"entries": entries}


if __name__ == "__main__":
    uvicorn.run("API.main:app", host="0.0.0.0", port=8000, reload=True)
