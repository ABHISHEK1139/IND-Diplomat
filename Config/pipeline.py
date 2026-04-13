"""
IND-Diplomat Pipeline Entry Point
==================================
Initializes all layers in dependency order and provides run_query().

USAGE:
    from Config.pipeline import run_query
    result = await run_query("What is the India-Pakistan situation?")
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from Config.config import SYSTEM_GUARDIAN_RUN_ON_IMPORT

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Layer-0 System Guardian (lazy by default; import should stay side-effect free)
guardian_report: Dict[str, Any] = {"status": "deferred"}
_guardian_ran = False


def _run_guardian_once() -> Dict[str, Any]:
    global guardian_report, _guardian_ran
    if _guardian_ran:
        return guardian_report
    try:
        from SystemGuardian.guardian_agent import run_guardian

        _guardian_apply_repairs = str(
            os.getenv("SYSTEM_GUARDIAN_APPLY_REPAIRS", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        guardian_report = run_guardian(apply_repairs=_guardian_apply_repairs)
    except Exception as guardian_error:
        guardian_report = {"error": str(guardian_error)}
    _guardian_ran = True
    return guardian_report


if SYSTEM_GUARDIAN_RUN_ON_IMPORT:
    _boot_report = _run_guardian_once()
    if "error" in _boot_report:
        print("SYSTEM GUARDIAN REPORT ERROR:", _boot_report)
    else:
        print("SYSTEM GUARDIAN REPORT:", _boot_report)

# Global initialization flag
_initialized = False


def initialize():
    """
    Initialize all layers in dependency order:
    Layer-1 (Collection) → Layer-2 (Knowledge) → Layer-3 (State) → Layer-4 (Analysis)

    Each initialization is wrapped in try/except so partial boots are possible.
    """
    global _initialized
    if _initialized:
        return

    print("[Pipeline] ========================================")
    print("[Pipeline] Initializing IND-Diplomat Pipeline")
    print("[Pipeline] ========================================")

    guardian_state = _run_guardian_once()
    if "error" in guardian_state:
        print(f"[Pipeline] Guardian WARNING: {guardian_state['error']}")
    else:
        print("[Pipeline] Guardian OK")

    # ── Layer 1: Collection (sensors) ──────────────────────────────
    try:
        from layer1_sensors import ObservationRecord
        print(f"[Pipeline] Layer-1 OK: ObservationRecord loaded")
    except Exception as e:
        print(f"[Pipeline] Layer-1 ERROR: {e}")

    # ── Layer 2: Knowledge (vector store + retrieval) ──────────────
    try:
        from engine.Layer2_Knowledge.retriever import DiplomaticRetriever
        print(f"[Pipeline] Layer-2 OK: DiplomaticRetriever loaded")
    except Exception as e:
        print(f"[Pipeline] Layer-2 WARNING: {e}")

    try:
        from engine.Layer2_Knowledge.knowledge_api import knowledge_api
        print(f"[Pipeline] Layer-2 OK: KnowledgeAPI loaded")
    except Exception as e:
        print(f"[Pipeline] Layer-2 WARNING: knowledge_api: {e}")

    # ── Layer 3: State Model (StateContext + state_provider) ───────
    try:
        from engine.Layer3_StateModel.interface.state_provider import (
            build_initial_state,
            investigate_and_update,
        )
        print(f"[Pipeline] Layer-3 OK: state_provider loaded")
    except Exception as e:
        print(f"[Pipeline] Layer-3 WARNING: {e}")

    # ── Layer 4: Analysis (Coordinator + council) ──────────────────
    try:
        from engine.Layer4_Analysis.coordinator import CouncilCoordinator
        print(f"[Pipeline] Layer-4 OK: CouncilCoordinator loaded")
    except Exception as e:
        print(f"[Pipeline] Layer-4 WARNING: {e}")

    try:
        from engine.Layer4_Analysis.core.llm_client import llm_client
        health = llm_client.health()
        print(f"[Pipeline] LLM: {health.get('provider')}/{health.get('model')} — {health.get('status')}")
    except Exception as e:
        print(f"[Pipeline] LLM WARNING: {e}")

    _initialized = True
    print("[Pipeline] ========================================")
    print("[Pipeline] Initialization complete")
    print("[Pipeline] ========================================")


async def run_query(
    query: str,
    user_id: str = None,
    session_id: str = None,
    country_code: str = "UNKNOWN",
    as_of_date: str = None,
    use_red_team: bool = True,
    use_mcts: bool = False,
    max_investigation_loops: int = 2,
    **flags,
) -> Dict[str, Any]:
    """
    [UNIFIED PIPELINE ENTRY POINT]
    
    This function now delegates to the real pipeline: Layer4_Analysis.core.unified_pipeline.UnifiedPipeline
    
    All execution flows through:
    Layer-1 (sensors) → Layer-2 (knowledge) → Layer-3 (state) → Layer-4 (reasoning)
    
    Args:
        query:       Natural language question
        user_id:     Optional user ID for audit
        session_id:  Optional session ID for conversation context
        country_code: 3-char country code (e.g. "IND") for state building
        as_of_date: optional YYYY-MM-DD runtime date override for historical replay
        use_red_team: Enable adversarial red team challenge
        use_mcts:    Enable MCTS hypothesis exploration
        max_investigation_loops: Max times Layer-4 can request more evidence

    Returns:
        Dict with 'answer', 'king_decision', 'sources', etc.
    """
    initialize()
    
    # Delegate to real unified pipeline
    from engine.Layer4_Analysis.core.unified_pipeline import UnifiedPipeline
    
    pipeline = UnifiedPipeline()
    result = await pipeline.execute(
        query=query,
        user_id=user_id,
        session_id=session_id,
        country_code=country_code,
        as_of_date=as_of_date,
        use_red_team=use_red_team,
        use_mcts=use_mcts,
        max_investigation_loops=max_investigation_loops,
        **flags
    )
    
    # Convert PipelineResult back to dict for backward compatibility
    return {
        "answer": result.answer,
        "outcome": str(getattr(result, "outcome", "ASSESSMENT") or "ASSESSMENT"),
        "confidence": result.confidence,
        "analytic_confidence": float(getattr(result, "analytic_confidence", result.confidence) or 0.0),
        "epistemic_confidence": float(getattr(result, "epistemic_confidence", 0.0) or 0.0),
        "risk_level": getattr(result, "risk_level", None),
        "early_warning_index": float(getattr(result, "early_warning_index", 0.0) or 0.0),
        "escalation_sync": float(getattr(result, "escalation_sync", 0.0) or 0.0),
        "prewar_detected": bool(getattr(result, "prewar_detected", False)),
        "warning": getattr(result, "warning", None),
        "status": str(getattr(result, "status", "CONCLUDED") or "CONCLUDED"),
        "sources": result.sources,
        "trace_id": result.trace_id,
        "operational_warnings": list(getattr(result, "operational_warnings", []) or []),
        "layer4_allowed": result.layer4_allowed,
        "layer4_gate_reason": result.layer4_gate_reason,
        "intelligence_report": getattr(result, "intelligence_report", None),
    }


def run_query_sync(query: str, **kwargs) -> Dict[str, Any]:
    """Synchronous wrapper for run_query."""
    return asyncio.run(run_query(query, **kwargs))


# Export
__all__ = [
    "initialize",
    "run_query",
    "run_query_sync",
]
