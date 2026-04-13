"""
IND-Diplomat — White-Box Intelligence Web App
==================================================
Self-contained web server that:
  1. Serves the existing Frontend/ dashboard
  2. Provides /v2/query (quick mode) and /api/v3/* (analyst mode)
  3. Calls diplomat_query() directly — no separate API servers needed
  4. Maps PipelineResult → the JSON format Frontend/ already consumes

Usage:
    python app_server.py                 # http://localhost:8000
    python app_server.py --port 8080     # custom port
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ── Bootstrap ─────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from run import diplomat_query, diplomat_query_sync, _check_ollama, _setup_logging, DiplomatResult
from Config import config

logger = logging.getLogger("webapp")

# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(title="IND-Diplomat", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = _ROOT / "Frontend"
_background_tasks: Set[asyncio.Task[Any]] = set()


# ═══════════════════════════════════════════════════════════════════════
# Job Store — in-memory tracking for analyst async assessments
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Job:
    job_id: str
    query: str
    params: Dict[str, Any]
    status: str = "QUEUED"                   # QUEUED | RUNNING | COMPLETED | FAILED
    phase: str = "SCOPE_CHECK"
    progress_pct: int = 0
    phase_detail: str = "Queued…"
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: str = ""
    risk_level: Optional[str] = None

    def status_dict(self) -> dict:
        return {
            "status": self.status,
            "phase": self.phase,
            "progress_pct": self.progress_pct,
            "phase_detail": self.phase_detail,
            "error": self.error,
        }

    def summary_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "query_preview": self.query[:80],
            "risk_level": self.risk_level,
            "created_at": self.created_at,
            "status": self.status,
        }

    def to_record(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "query": self.query,
            "params": self.params,
            "status": self.status,
            "phase": self.phase,
            "progress_pct": self.progress_pct,
            "phase_detail": self.phase_detail,
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "risk_level": self.risk_level,
        }

    @classmethod
    def from_record(cls, data: Dict[str, Any]) -> "Job":
        return cls(
            job_id=str(data.get("job_id", "")),
            query=str(data.get("query", "")),
            params=data.get("params", {}) if isinstance(data.get("params"), dict) else {},
            status=str(data.get("status", "QUEUED")),
            phase=str(data.get("phase", "SCOPE_CHECK")),
            progress_pct=int(data.get("progress_pct", 0) or 0),
            phase_detail=str(data.get("phase_detail", "Queued…")),
            error=data.get("error"),
            result=data.get("result") if isinstance(data.get("result"), dict) else None,
            created_at=str(data.get("created_at", "")),
            risk_level=data.get("risk_level"),
        )


class JobStore:
    """Thread-safe job store with lightweight JSON persistence."""

    def __init__(self, max_jobs: int = 50, persist_path: Optional[Path] = None):
        self._jobs: Dict[str, Job] = {}
        self._order: List[str] = []          # newest first
        self._max = max_jobs
        self._persist_path = persist_path or (_ROOT / "runtime" / "job_store.json")
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self._persist_path.exists():
                return
            try:
                payload = json.loads(self._persist_path.read_text(encoding="utf-8"))
                order = payload.get("order") if isinstance(payload, dict) else []
                jobs = payload.get("jobs") if isinstance(payload, dict) else {}
                if not isinstance(order, list):
                    order = []
                if isinstance(jobs, list):
                    jobs = {
                        str(item.get("job_id", "")): item
                        for item in jobs
                        if isinstance(item, dict) and item.get("job_id")
                    }
                if not isinstance(jobs, dict):
                    jobs = {}

                loaded: Dict[str, Job] = {}
                for jid, raw in jobs.items():
                    if not isinstance(raw, dict):
                        continue
                    job = Job.from_record(raw)
                    if job.job_id:
                        loaded[job.job_id] = job

                self._jobs = loaded
                self._order = [str(jid) for jid in order if str(jid) in self._jobs]
                for jid in sorted(self._jobs.keys(), key=lambda k: self._jobs[k].created_at, reverse=True):
                    if jid not in self._order:
                        self._order.append(jid)
                self._order = self._order[: self._max]
            except Exception as exc:
                logger.warning("Unable to load job store from %s: %s", self._persist_path, exc)

    def _persist_locked(self) -> None:
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "order": self._order[: self._max],
                "jobs": {
                    jid: self._jobs[jid].to_record()
                    for jid in self._order
                    if jid in self._jobs
                },
            }
            tmp_path = self._persist_path.with_suffix(self._persist_path.suffix + ".tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(self._persist_path)
        except Exception as exc:
            logger.warning("Unable to persist job store to %s: %s", self._persist_path, exc)

    def create(self, query: str, params: dict) -> str:
        with self._lock:
            jid = uuid.uuid4().hex[:12]
            job = Job(
                job_id=jid,
                query=query,
                params=params,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._jobs[jid] = job
            self._order.insert(0, jid)
            while len(self._order) > self._max:
                old = self._order.pop()
                self._jobs.pop(old, None)
            self._persist_locked()
            return jid

    def get(self, jid: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(jid)

    def update(self, jid: str, **fields: Any) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(jid)
            if not job:
                return None
            for key, value in fields.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            self._persist_locked()
            return job

    def list_recent(self, limit: int = 10) -> List[dict]:
        with self._lock:
            out = []
            for jid in self._order[:limit]:
                job = self._jobs.get(jid)
                if job:
                    out.append(job.summary_dict())
            return out


_store = JobStore()


# ═══════════════════════════════════════════════════════════════════════
# Result Mapping — PipelineResult → Frontend JSON format
# ═══════════════════════════════════════════════════════════════════════

def _safe(obj: Any) -> Any:
    """Make any object JSON-serializable."""
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return _safe(obj.dict())
        except Exception as exc:
            logger.debug("dict() serialization fallback for %s: %s", type(obj).__name__, exc)
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return _safe(obj.model_dump())
        except Exception as exc:
            logger.debug("model_dump() serialization fallback for %s: %s", type(obj).__name__, exc)
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(i) for i in obj]
    if hasattr(obj, "to_dict"):
        return _safe(obj.to_dict())
    if hasattr(obj, "__dict__"):
        return _safe({k: v for k, v in vars(obj).items() if not k.startswith("_")})
    return str(obj)


def _to_ratio(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _preferred_answer(result: DiplomatResult) -> str:
    """
    Use the rich briefing only for actual assessments.
    Non-assessment outcomes should surface the explicit pipeline answer.
    """
    if str(result.outcome or "").upper() != "ASSESSMENT":
        return result.answer
    return result.briefing or result.answer


def _whitebox_payload(result: DiplomatResult) -> Dict[str, Any]:
    """
    Full transparency payload for end users, including WITHHELD outcomes.
    """
    try:
        exported = result.to_dict(whitebox=True, include_run_log=True, include_briefing=True)
        return _safe(exported.get("whitebox", {}))
    except Exception as exc:
        return {"error": f"whitebox_payload_failed: {exc}"}


def _map_v2_response(result: DiplomatResult) -> dict:
    """
    Map DiplomatResult → V2 response for app.js (quick mode).
    """
    raw = result.raw  # PipelineResult or None
    elapsed_ms = round(result.elapsed_seconds * 1000)

    outcome_upper = str(result.outcome or "").upper()
    resp: Dict[str, Any] = {
        "success": outcome_upper == "ASSESSMENT",
        "outcome": result.outcome,
        "answer": _preferred_answer(result),
        "confidence": result.confidence,
        "risk_level": result.risk_level,
        "trace_id": result.trace_id,
        "latency_ms": elapsed_ms,
        "stages_completed": [],
        "stage_times": {},
        "sources": _safe(result.sources[:15]) if result.sources else [],
        "warnings": _safe(result.operational_warnings or []),
        "dossier_hits": [],
        "confidence_ledger": [],
        "scenario_playbook": None,
        "verification": {
            "cove_verified": False,
            "cove_revisions": 0,
            "red_team_passed": False,
            "input_safe": True,
            "output_safe": True,
            "pii_masked": 0,
        },
        "reasoning": [],
        "whitebox": _whitebox_payload(result),
    }

    if outcome_upper in {"OUT_OF_SCOPE", "INSUFFICIENT_EVIDENCE"}:
        resp["outcome"] = outcome_upper
        resp["answer"] = result.answer

    if not raw:
        return resp

    # ── Verification ──────────────────────────────────────────────
    resp["verification"]["cove_verified"] = getattr(raw, "cove_verified", False)
    resp["verification"]["crag_correction_applied"] = getattr(raw, "crag_correction_applied", False)

    cs_obj = getattr(raw, "council_session", None)
    cs = _safe(cs_obj) if cs_obj else {}
    resp["council_session"] = cs
    resp["gate_verdict"] = _safe(getattr(raw, "gate_verdict", None)) or cs.get("gate_verdict", {})
    resp["intelligence_report"] = _safe(getattr(raw, "intelligence_report", None) or {})
    red = cs.get("red_team_report")
    if isinstance(red, dict):
        resp["verification"]["red_team_passed"] = red.get("is_robust", False)
    elif red is not None:
        resp["verification"]["red_team_passed"] = bool(getattr(red, "is_robust", False))

    # ── Dossier hits ──────────────────────────────────────────────
    dh = getattr(raw, "dossier_hits", None)
    if dh:
        resp["dossier_hits"] = _safe(dh) if isinstance(dh, (list, tuple)) else []

    # ── Confidence ledger ─────────────────────────────────────────
    cl = getattr(raw, "confidence_ledger", None)
    if cl:
        if isinstance(cl, (list, tuple)):
            resp["confidence_ledger"] = _safe(cl)
        elif isinstance(cl, dict):
            resp["confidence_ledger"] = [_safe(cl)]
        elif hasattr(cl, "__dict__"):
            resp["confidence_ledger"] = [_safe(cl)]

    # ── Scenario playbook ─────────────────────────────────────────
    sp = getattr(raw, "scenario_playbook", None)
    if sp:
        resp["scenario_playbook"] = _safe(sp)

    # ── Reasoning chain from council ──────────────────────────────
    resp["reasoning"] = _build_reasoning_chain(result)

    return resp


def _map_v3_response(result: DiplomatResult, country_code: str = "UNKNOWN") -> dict:
    """
    Map DiplomatResult → V3 response for analyst.js (full assessment).
    Extends V2 with SRE, gate, evidence chain, formatted report.
    """
    raw = result.raw
    resp = _map_v2_response(result)

    # Add fields analyst.js expects
    resp["job_id"] = result.trace_id
    resp["request"] = {"country_code": country_code}

    if not raw:
        return resp
    cs = _safe(getattr(raw, "council_session", None) or {})
# ── SRE ───────────────────────────────────────────────────────
    sre_domains = cs.get("sre_domains") or {}
    resp["sre"] = {
        "escalation_score": cs.get("sre_escalation_score", 0) or 0,
        "risk_level": cs.get("risk_level") or getattr(raw, "risk_level", None) or "low",
        "capability": sre_domains.get("capability", 0) or 0,
        "intent": sre_domains.get("intent", 0) or 0,
        "stability": sre_domains.get("stability", 0) or 0,
        "cost": sre_domains.get("cost", 0) or 0,
        "trend_bonus": cs.get("temporal_trend", {}).get("trend_bonus", 0) if isinstance(cs.get("temporal_trend"), dict) else 0,
    }

    # ── Gate Verdict ──────────────────────────────────────────────
    gv = getattr(raw, "gate_verdict", None) or cs.get("gate_verdict")
    if isinstance(gv, dict):
        resp["gate_verdict"] = {
            "approved": gv.get("approved", True),
            "decision": gv.get("decision") or ("APPROVED" if gv.get("approved", True) else "WITHHELD"),
            "confidence": gv.get("confidence", result.confidence),
            "reasons": gv.get("reasons") or [],
            "intelligence_gaps": gv.get("intelligence_gaps") or [],
            "collection_tasks": _safe(gv.get("collection_tasks") or []),
        }
    elif gv and hasattr(gv, "to_dict"):
        resp["gate_verdict"] = _safe(gv)
    else:
        resp["gate_verdict"] = {
            "approved": True,
            "decision": "APPROVED",
            "confidence": result.confidence,
            "reasons": [],
            "intelligence_gaps": [],
            "collection_tasks": [],
        }

    # ── Evidence Chain ────────────────────────────────────────────
    resp["evidence_chain"] = _build_evidence_chain(cs)

    # ── Country Code ──────────────────────────────────────────────
    resp["country_code"] = country_code

    # ── Formatted Report ──────────────────────────────────────────
    resp["formatted_report"] = _preferred_answer(result)

    # ── Verification Chain (reasoning from ministers) ─────────────
    resp["verification_chain"] = {"steps": _build_minister_reasoning(cs)}

    return resp


# Canonical signal → SRE dimension mapping
_SIGNAL_DIM = {
    "SIG_MIL_MOBILIZATION": "CAPABILITY", "SIG_MIL_ESCALATION": "CAPABILITY",
    "SIG_FORCE_POSTURE": "CAPABILITY", "SIG_LOGISTICS_PREP": "CAPABILITY",
    "SIG_CYBER_ACTIVITY": "CAPABILITY", "SIG_KINETIC_ACTIVITY": "CAPABILITY",
    "SIG_WMD_RISK": "CAPABILITY", "SIG_MIL_FORWARD_DEPLOYMENT": "CAPABILITY",
    "SIG_DIP_HOSTILITY": "INTENT", "SIG_DIPLOMACY_ACTIVE": "INTENT",
    "SIG_COERCIVE_BARGAINING": "INTENT", "SIG_ALLIANCE_ACTIVATION": "INTENT",
    "SIG_NEGOTIATION_BREAKDOWN": "INTENT", "SIG_DETERRENCE_SIGNALING": "INTENT",
    "SIG_INTERNAL_INSTABILITY": "STABILITY", "SIG_PUBLIC_PROTEST": "STABILITY",
    "SIG_DECEPTION_ACTIVITY": "STABILITY", "SIG_ELITE_FRACTURE": "STABILITY",
    "SIG_MILITARY_DEFECTION": "STABILITY", "SIG_DOM_INTERNAL_INSTABILITY": "STABILITY",
    "SIG_ECONOMIC_PRESSURE": "COST", "SIG_ECO_SANCTIONS_ACTIVE": "COST",
    "SIG_SANCTIONS_ACTIVE": "COST", "SIG_ECO_PRESSURE_HIGH": "COST",
}


def _build_evidence_chain(cs: dict) -> List[dict]:
    """Build evidence_chain from council session evidence_log."""
    evidence_log = cs.get("evidence_log") or []
    chain = []
    for i, ev in enumerate(evidence_log[:30]):
        if isinstance(ev, dict):
            sig = ev.get("signal_name") or ev.get("signal") or ev.get("name", f"signal_{i}")
            chain.append({
                "dimension": ev.get("dimension") or ev.get("category") or _SIGNAL_DIM.get(sig, "UNKNOWN"),
                "signal_name": sig,
                "source_type": ev.get("source_type") or ev.get("source", "unknown"),
                "confidence": ev.get("confidence", 0),
                "source_detail": ev.get("source_detail") or ev.get("detail") or ev.get("content", "")[:100],
                "raw_snippet": ev.get("raw_snippet") or ev.get("snippet", ""),
            })
        elif isinstance(ev, str):
            chain.append({
                "dimension": _SIGNAL_DIM.get(ev.strip(), "UNKNOWN"),
                "signal_name": ev[:60],
                "source_type": "text",
                "confidence": 0.5,
                "source_detail": ev[:100],
            })
    return chain


def _build_reasoning_chain(result: DiplomatResult) -> List[dict]:
    """Build reasoning steps from the pipeline execution."""
    steps = []
    step = 0

    raw = result.raw
    if not raw:
        return steps
    cs = _safe(getattr(raw, "council_session", None) or {})
# Step: Scope
    scope = getattr(raw, "layer4_scope", None)
    if scope:
        step += 1
        steps.append({"step": step, "title": "Scope Check", "description": f"Query classified. Scope: {_safe(scope)}"})

    # Step: Epistemic readiness
    readiness = getattr(raw, "layer4_readiness", None)
    if readiness:
        step += 1
        steps.append({"step": step, "title": "Epistemic Readiness", "description": f"Data sufficiency check: {_safe(readiness)}"})

    # Step: Evidence collection
    ev_count = cs.get("evidence_atom_count") or cs.get("signal_count") or 0
    if ev_count:
        step += 1
        steps.append({"step": step, "title": "Evidence Collection", "description": f"Collected {ev_count} evidence atoms from sensors and knowledge base."})

    # Step: Council deliberation
    minister_reports = cs.get("minister_reports") or {}
    if minister_reports:
        names = list(minister_reports.keys())[:6]
        step += 1
        steps.append({"step": step, "title": "Council Deliberation", "description": f"Ministers consulted: {', '.join(names)}."})

    # Step: Debate
    debate = cs.get("debate_result")
    if isinstance(debate, dict):
        step += 1
        steps.append({"step": step, "title": "Council Debate", "description": f"Outcome: {debate.get('outcome', 'consensus')}. Consensus points: {len(debate.get('consensus_points', []))}."})
    elif debate:
        step += 1
        steps.append({"step": step, "title": "Council Debate", "description": str(debate)[:200]})

    # Step: Red Team
    red = cs.get("red_team_report")
    if isinstance(red, dict):
        step += 1
        robust = red.get("is_robust", False)
        penalty = red.get("confidence_penalty", 0)
        steps.append({"step": step, "title": "Red Team Challenge", "description": f"Robust: {robust}. Confidence penalty: {penalty}. Contradictions: {len(red.get('contradictions', []))}."})

    # Step: Verification
    cove = getattr(raw, "cove_verified", False)
    step += 1
    steps.append({"step": step, "title": "Verification", "description": f"CoVe verified: {cove}. CRAG correction: {getattr(raw, 'crag_correction_applied', False)}."})

    # Step: Gate verdict
    gv = getattr(raw, "gate_verdict", None)
    if isinstance(gv, dict):
        step += 1
        approved = gv.get("approved", True)
        gate_conf = _to_ratio(gv.get("confidence", 0.0), default=0.0)
        steps.append({"step": step, "title": "Assessment Gate", "description": f"{'APPROVED' if approved else 'WITHHELD'}. Confidence: {gate_conf:.1%}."})

    # Step: Final assessment
    step += 1
    steps.append({"step": step, "title": "Final Assessment", "description": f"Outcome: {result.outcome}. Overall confidence: {_to_ratio(result.confidence):.1%}. Risk level: {result.risk_level or 'N/A'}."})

    return steps


def _build_minister_reasoning(cs: dict) -> List[dict]:
    """Build detailed reasoning from minister reports for analyst view."""
    steps = []
    minister_reports = cs.get("minister_reports", {})
    step = 0

    for name, report in minister_reports.items():
        if not isinstance(report, dict):
            continue
        step += 1
        conf = _to_ratio(report.get("confidence", 0), default=0.0)
        dim = report.get("dimension") or report.get("classification_source", "unknown")
        drivers = report.get("primary_drivers") or []
        gaps = report.get("critical_gaps") or []
        reasoning = report.get("reasoning_text", "")

        desc = f"Source: {dim}. Confidence: {conf:.1%}."
        if drivers:
            desc += f" Drivers: {', '.join(str(d) for d in drivers[:3])}."
        if gaps:
            desc += f" Gaps: {', '.join(str(g) for g in gaps[:3])}."
        if reasoning:
            desc += f" Logic: {reasoning}"

        steps.append({"step": step, "title": f"Minister: {name}", "description": desc})

    # Add debate + red team as reasoning steps too
    debate = cs.get("debate_result")
    if isinstance(debate, dict):
        step += 1
        outcome = debate.get("outcome", "")
        consensus = debate.get("consensus_points") or []
        conflicts = debate.get("conflicts_surfaced") or []
        desc = f"Outcome: {outcome}."
        if consensus:
            desc += f" Consensus: {', '.join(str(c) for c in consensus[:3])}."
        if conflicts:
            desc += f" Conflicts: {', '.join(str(c) for c in conflicts[:3])}."
        steps.append({"step": step, "title": "Debate Synthesis", "description": desc})

    red = cs.get("red_team_report")
    if isinstance(red, dict):
        step += 1
        desc = f"Robust: {red.get('is_robust', False)}. Penalty: {red.get('confidence_penalty', 0)}."
        critique = red.get("critique") or red.get("counter_evidence") or []
        if critique:
            desc += f" Issues: {', '.join(str(c) for c in (critique if isinstance(critique, list) else [critique])[:3])}."
        steps.append({"step": step, "title": "Red Team Analysis", "description": desc})

    return steps


# ═══════════════════════════════════════════════════════════════════════
# Background Job Runner
# ═══════════════════════════════════════════════════════════════════════

async def _run_job(job_id: str) -> None:
    """Run a diplomat_query as a tracked background job with phase updates."""
    job = _store.get(job_id)
    if not job:
        return

    params = dict(job.params or {})
    query = str(job.query)
    _store.update(
        job_id,
        status="RUNNING",
        phase="SCOPE_CHECK",
        progress_pct=5,
        phase_detail="Checking query scope…",
        error=None,
    )

    try:
        # Map depth to loops
        depth_mapping = {"fast": 1, "standard": 2, "deep": 3}
        loops = depth_mapping.get(params.get("collection_depth", "standard"), 2)

        _store.update(
            job_id,
            phase="SENSORS",
            progress_pct=30,
            phase_detail="Collecting sensor and knowledge evidence…",
        )

        dr = await asyncio.to_thread(
            diplomat_query_sync,
            query,
            country_code=params.get("country_code", "UNKNOWN"),
            as_of_date=params.get("as_of_date"),
            use_red_team=params.get("use_red_team", True),
            use_mcts=params.get("use_mcts", False),
            max_investigation_loops=loops,
            evidence_strictness=params.get("evidence_strictness", "balanced"),
            gate_threshold=params.get("gate_threshold", "default"),
            time_horizon=params.get("time_horizon", "30d"),
            source_mode=params.get("source_mode", "hybrid")
        )

        _store.update(
            job_id,
            phase="GATE",
            progress_pct=85,
            phase_detail="Finalizing gate verdict and report…",
        )

        # Store mapped result
        country = params.get("country_code", "UNKNOWN")
        mapped = _map_v3_response(dr, country)
        mapped["job_id"] = job_id
        _store.update(
            job_id,
            status="COMPLETED",
            phase="REPORT",
            progress_pct=100,
            phase_detail="Complete",
            result=mapped,
            risk_level=dr.risk_level,
            error=None,
        )

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        _store.update(
            job_id,
            status="FAILED",
            phase="REPORT",
            progress_pct=100,
            phase_detail="Failed",
            error=str(e),
        )


# ═══════════════════════════════════════════════════════════════════════
# Routes — Static Files (Frontend/)
# ═══════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def serve_app():
    html_path = FRONTEND_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend/index.html not found</h1>", status_code=404)


@app.get("/styles.css")
async def serve_css():
    return FileResponse(str(FRONTEND_DIR / "styles.css"), media_type="text/css")


@app.get("/app.js")
async def serve_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"), media_type="application/javascript")


@app.get("/analyst.js")
async def serve_analyst_js():
    return FileResponse(str(FRONTEND_DIR / "analyst.js"), media_type="application/javascript")


# ═══════════════════════════════════════════════════════════════════════
# Routes — V2 Quick Query (used by app.js)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/v2/query")
async def v2_query(request: Request):
    """Quick query — run pipeline and return immediately."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = str(body.get("query", "")).strip()
    if not query:
        return JSONResponse({"error": "Missing 'query' field"}, status_code=400)
    country_code = str(body.get("country_code") or body.get("country") or "UNKNOWN").strip().upper() or "UNKNOWN"
    as_of_date = body.get("as_of_date")
    try:
        max_loops = int(body.get("max_investigation_loops", 1))
    except Exception:
        max_loops = 1

    try:
        result = await diplomat_query(
            query=query,
            country_code=country_code,
            as_of_date=as_of_date,
            use_red_team=body.get("use_red_team", True),
            use_mcts=body.get("use_mcts", False),
            max_investigation_loops=max(0, max_loops),
        )
        return JSONResponse(_safe(_map_v2_response(result)))

    except Exception as e:
        error_id = uuid.uuid4().hex[:10]
        logger.exception("V2 query failed (error_id=%s): %s", error_id, e)
        return JSONResponse({
            "error": "Internal server error",
            "error_id": error_id,
            "success": False,
        }, status_code=500)


@app.post("/api/simple/query")
async def simple_query(request: Request):
    """Minimal query interface suitable for quick Ollama testing."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = str(body.get("query", "")).strip()
    if not query:
        return JSONResponse({"error": "Missing 'query' field"}, status_code=400)

    country_code = str(body.get("country_code") or body.get("country") or "UNKNOWN").strip().upper() or "UNKNOWN"
    try:
        result = await diplomat_query(query=query, country_code=country_code)
        return JSONResponse(
            {
                "outcome": result.outcome,
                "answer": _preferred_answer(result),
                "confidence": result.confidence,
                "risk_level": result.risk_level,
                "trace_id": result.trace_id,
            }
        )
    except Exception as e:
        error_id = uuid.uuid4().hex[:10]
        logger.exception("Simple query failed (error_id=%s): %s", error_id, e)
        return JSONResponse({"error": "Internal server error", "error_id": error_id}, status_code=500)


# ═══════════════════════════════════════════════════════════════════════
# Routes — V3 Analyst Assessment (used by analyst.js)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v3/assess")
async def v3_assess(request: Request):
    """Start an async assessment job. Returns { job_id }."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = str(body.get("query", "")).strip()
    if not query:
        return JSONResponse({"error": "Missing 'query' field"}, status_code=400)

    job_id = _store.create(query, body)

    # Track background tasks so they can be cancelled cleanly on shutdown.
    task = asyncio.create_task(_run_job(job_id), name=f"assessment:{job_id}")
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return JSONResponse({"job_id": job_id})


@app.on_event("shutdown")
async def _shutdown_background_tasks() -> None:
    if not _background_tasks:
        return

    logger.info("Shutting down %d background assessment task(s)", len(_background_tasks))
    for task in list(_background_tasks):
        task.cancel()
    await asyncio.gather(*list(_background_tasks), return_exceptions=True)
    _background_tasks.clear()


@app.get("/api/v3/jobs/{job_id}")
async def v3_job_status(job_id: str):
    """Poll job status."""
    job = _store.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse(job.status_dict())


@app.get("/api/v3/jobs/{job_id}/result")
async def v3_job_result(job_id: str):
    """Get completed job result."""
    job = _store.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.status == "RUNNING":
        return JSONResponse({"status": "RUNNING"}, status_code=202)
    if job.status == "FAILED":
        return JSONResponse({"error": job.error or "Unknown error"}, status_code=500)
    if job.result is None:
        return JSONResponse({"error": "No result available"}, status_code=404)
    return JSONResponse(_safe(job.result))


@app.get("/api/v3/jobs")
async def v3_list_jobs(limit: int = 10):
    """List recent assessment jobs."""
    return JSONResponse(_store.list_recent(min(limit, 50)))


@app.get("/api/v3/trends/{country_code}")
async def v3_trends(country_code: str, hours: int = 72):
    """Trend data from persistent trend store with graceful fallback."""
    try:
        from analyst_api.trend_store import get_trends

        points = get_trends(country_code.upper(), hours_back=hours)
        return JSONResponse(_safe(points))
    except Exception as exc:
        logger.warning("Trend lookup failed for %s: %s", country_code, exc)
        return JSONResponse([])


# ═══════════════════════════════════════════════════════════════════════
# Routes — Health / Ollama
# ═══════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    ollama = _check_ollama()
    return JSONResponse({
        "status": "ok",
        "ollama": ollama,
        "project_root": str(_ROOT),
    })


@app.get("/api/ollama")
async def api_ollama():
    return JSONResponse(_check_ollama())


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="IND-Diplomat Web App")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    _setup_logging("INFO")

    print("=" * 55)
    print("  IND-Diplomat — White-Box Intelligence Web App")
    print("=" * 55)
    print(f"\n  Dashboard: http://{args.host}:{args.port}")
    print(f"  Quick API: http://{args.host}:{args.port}/v2/query")
    print(f"  Analyst:   http://{args.host}:{args.port}/api/v3/assess")
    print(f"  API Docs:  http://{args.host}:{args.port}/docs")
    print()
    print("=" * 55)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

