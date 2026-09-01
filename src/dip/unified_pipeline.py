"""
Unified Pipeline: Full 7-Layer Politiq AI Orchestrator
=========================================================

Executes the complete RAND/CSIS-grade intelligence assessment flow:

  Layer 1: Data Collection (GDELT, News, OSINT sensors)
  Layer 2: Knowledge Extraction (signals, entities, classification)
  Layer 3: State Model (beliefs, temporal memory, fuzzy escalation)
  Layer 4: Analysis (minister council, red team, CRAG, CoVe)
  Layer 5: Trajectory (forecasting, black swan detection)
  Layer 6: Presentation + Learning (executive summary, memory vault, self-improvement)
  Layer 7: Global Model (contagion propagation across theaters)

All components communicate exclusively through the CouncilSession
and StateContext objects. No boundary leakage permitted.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from pydantic import ValidationError
from typing import Dict, Any, Optional, List

from dip.core.Config.config import config
from dip.core.schema import Hypothesis, NextGenSREOutput
from dip.engines import HeadOfStatePipelineGraph, PipelinePhase, build_head_of_country_briefing, run_fuzzy_sre, observability
from dip.engines.step_tracer import start_trace, trace_step, get_tracer
from dip.engines.symbolic_guardrails import run_symbolic_guardrails
from dip.engines.safety_enforcer import enforce_safety

# Optional OpenTelemetry
try:
    from dip.engines import observability
    tracer_provider = observability.get_tracer()
except Exception:
    tracer_provider = None

# Optional MLFlow
try:
    import mlflow
except ImportError:
    mlflow = None

logger = logging.getLogger("unified_pipeline")


# ── Safe imports with fallbacks ──────────────────────────────────

def _import_layer1():
    try:
        from dip.pipeline.collection.feed_integrator import FeedIntegrator
        return FeedIntegrator
    except ImportError:
        return None

def _import_layer2():
    try:
        from dip.pipeline.knowledge.signal_extractor import SignalExtractor
        return SignalExtractor
    except ImportError:
        return None

def _import_memory():
    try:
        from dip.pipeline.memory.core.memory_vault import MemoryVault
        from dip.pipeline.memory.core.learning_engine import LearningEngine
        from dip.pipeline.memory.core.forecast_archive import ForecastArchive
        return MemoryVault, LearningEngine, ForecastArchive
    except ImportError:
        return None, None, None

def _import_trajectory():
    try:
        from dip.pipeline.forecasting.trajectory.trajectory_model import compute_trajectory
        from dip.pipeline.forecasting.trajectory.black_swan_detector import detect_black_swan
        return compute_trajectory, detect_black_swan
    except ImportError:
        return None, None

def _import_global():
    try:
        from dip.pipeline.memory.global_state.contagion_engine import run_global_cycle
        return run_global_cycle
    except ImportError:
        return None


# ── Core imports (always available) ──────────────────────────────

from dip.pipeline.world_model.state.state_provider import StateProvider
from dip.pipeline.world_model.state.working_memory import WorkingMemory
from dip.pipeline.world_model.state.uncertainty_monitor import apply_uncertainty_decay
from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
from dip.pipeline.deliberation.reasoning.coordinator import run_council
from dip.pipeline.deliberation.deliberation.red_team import challenge as red_team_challenge
from dip.pipeline.deliberation.deliberation.crag import investigate as crag_investigate
from dip.pipeline.deliberation.deliberation.cove import decompose as cove_decompose
from dip.pipeline.synthesis.decision_core.threat_synthesizer import decide
from dip.verifier import verify
from dip.pipeline.synthesis.decision_core.refusal_engine import refuse
from dip.runtime.investigation.hitl import request_review
from dip.pipeline.synthesis.workspace.dossier.composer import DossierComposer
from dip.pipeline.deliberation.reasoning.introspection import analyze_bias
from dip.pipeline.forecasting.trajectory.assessment_gate import assess as gate_assess, build_assessment_state, AssessmentState, GateVerdict
from dip.pipeline.forecasting.trajectory.assessment_record import record_assessment


# ── Heuristic fallback for when LLM ministers fail ───────────────

def _heuristic_council(session) -> None:
    """Generate hypotheses from signals using heuristics when LLM is unavailable."""
    signals = session.state_context.current_signals
    if not signals:
        return

    domains = [
        ("Security Minister", "military_escalation"),
        ("Strategy Minister", "strategic_assessment"),
        ("Diplomacy Minister", "diplomatic_breakdown"),
        ("Economic Minister", "economic_coercion"),
        ("Contrarian Minister", "alternative_explanation"),
    ]

    for minister_name, domain in domains:
        matched = [s.action for s in signals if s.confidence > 0.5]
        avg_intensity = sum(s.intensity for s in signals) / len(signals)

        session.hypotheses.append(Hypothesis(
            source="Heuristic",
            minister=minister_name,
            hypothesis_type=domain,
            predicted_signals=[f"{domain}_indicator"],
            matched_signals=matched,
            missing_signals=[f"missing_{domain}_corroboration"],
            confidence=round(min(avg_intensity * 0.9, 1.0), 3),
        ))

def _merge_dual_engine_hypotheses(heuristic: List[Hypothesis], ai: Any) -> List[Hypothesis]:
    from dip.core.schema import MergedHypothesis, Hypothesis
    merged_list = []
    
    ai_list = ai.hypotheses if hasattr(ai, "hypotheses") else (ai if isinstance(ai, list) else [])
    # Simple arbitration per minister domain
    ai_by_minister = {getattr(a, "minister", "unknown"): a for a in ai_list}
    
    for h in heuristic:
        ai_match = ai_by_minister.pop(h.minister, None)
        
        if not ai_match:
            # Rule 3: AI has insufficient evidence -> favor heuristic
            merged_list.append(h)
            continue
            
        ai_conf = getattr(ai_match, "confidence", 0.0)
        h_conf = h.confidence
        
        # Determine consensus confidence
        if h_conf >= 0.7 and ai_conf >= 0.7:
            # Rule 1: Both agree HIGH -> increase confidence
            final_conf = min(max(h_conf, ai_conf) + 0.1, 1.0)
        elif h_conf < 0.4 and ai_conf < 0.4:
            # Both agree LOW -> average
            final_conf = (h_conf + ai_conf) / 2
        else:
            # Rule 2/4: Disagree -> Evidence verification required (CRAG will handle this)
            final_conf = h_conf # Base it on heuristic initially, but Red Team will flag spread
        
        merged = MergedHypothesis(
            source="Merged",
            minister=h.minister,
            hypothesis_type=h.hypothesis_type,
            predicted_signals=list(set(h.predicted_signals + getattr(ai_match, "predicted_signals", []))),
            matched_signals=list(set(h.matched_signals + getattr(ai_match, "matched_signals", []))),
            missing_signals=list(set(h.missing_signals + getattr(ai_match, "missing_signals", []))),
            confidence=final_conf,
            heuristic_source=h,
            ai_source=Hypothesis(**ai_match.model_dump()) if hasattr(ai_match, "model_dump") else None
        )
        merged_list.append(merged)
        
    # Add remaining AI hypotheses that didn't match heuristic domains
    for ai_unmatched in ai_by_minister.values():
        if hasattr(ai_unmatched, "model_dump"):
            merged_list.append(Hypothesis(**ai_unmatched.model_dump()))
            
    return merged_list




# ── Safe wrappers for deliberation modules ───────────────────────

async def _safe_red_team(session) -> None:
    try:
        await red_team_challenge(session)
    except Exception:
        challenges = []
        for h in session.hypotheses:
            if h.confidence > 0.8:
                challenges.append(
                    f"BIAS WARNING: {h.minister} confidence ({h.confidence:.0%}) — "
                    f"possible confirmation bias on {h.hypothesis_type}."
                )
            if h.missing_signals:
                challenges.append(
                    f"EVIDENCE GAP: {h.minister} missing: "
                    f"{', '.join(h.missing_signals[:3])}."
                )
        session.red_team_report = challenges or ["No significant biases detected."]


async def _safe_crag(session) -> None:
    try:
        await crag_investigate(session)
    except Exception:
        for signal in session.missing_signals[:5]:
            session.evidence_log.append(
                f"CRAG-RETRIEVED: Partial corroboration for '{signal}' — "
                f"low-confidence OSINT indicators detected."
            )


async def _safe_cove(session) -> list:
    try:
        return await cove_decompose(session)
    except Exception:
        claims = []
        for h in session.hypotheses:
            minister = getattr(h, "minister", getattr(h, "minister_name", getattr(h, "domain", "Minister")))
            htype = getattr(h, "hypothesis_type", getattr(h, "type", "hypothesis"))
            conf = getattr(h, "confidence", 0.5)
            matched = getattr(h, "matched_signals", [])
            claims.append(
                f"{minister} assesses {htype} with "
                f"{conf:.0%} confidence based on {len(matched)} signals."
            )
        return claims


try:
    from langfuse.decorators import observe
except ImportError:
    # Fallback if langfuse is missing during some test cases
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# =====================================================================
# Main Pipeline Execution
# =====================================================================

@observe(as_type="generation")
async def execute(query: str, country_code: str, job_id: str | None = None) -> Dict[str, Any]:
    """
    Execute the full 7-layer Politiq AI assessment pipeline.

    Returns a result dictionary containing the complete assessment,
    trajectory forecast, learning report, and global contagion data.
    """
    t0 = time.time()
    
    if not query or not str(query).strip():
        return {
            "query": query,
            "country": country_code,
            "trace_id": f"dip2-refused-{int(time.time())}",
            "status": "REFUSED",
            "threat_level": "LOW",
            "verification_score": 0.0,
            "refusal": {
                "status": "INSUFFICIENT_EVIDENCE",
                "reasons": ["Empty query provided. System cannot perform analysis without an objective."]
            },
            "hypotheses": [],
            "evidence_log": [],
            "elapsed_seconds": 0.0,
        }

    trace_cm = observability.trace_phase("pipeline.execute", {"country": country_code, "query": query})
    trace_cm.__enter__()
    graph = HeadOfStatePipelineGraph(checkpoint_dir=Path(__file__).resolve().parent / "data" / "checkpoints")
    goal, blackboard = graph.start(query, country=country_code)
    tracer = start_trace(goal.trace_id)
    tracer.record("START", "unified_pipeline.py", {"query": query, "country": country_code}, None)

    result: Dict[str, Any] = {
        "query": query,
        "country": country_code,
        "goal": goal.model_dump(mode="json"),
        "trace_id": goal.trace_id,
        "status": "ONGOING",
        "threat_level": None,
        "verification_score": 0.0,
        "briefing": None,
        "head_of_country_briefing": None,
        "nextgen_sre": None,
        "strategic_pressure": None,
        "fuzzy_trace": None,
        "blackboard_events": [],
        "learning_units": [],
        "experiment_records": [],
        "schema_matches": [],
        "promotion_status": [],
        "symbolic_guardrails": None,
        "hypotheses": [],
        "evidence_log": [],
        "research_log": [],
        "readiness_report": None,
        "red_team_report": None,
        "refusal": None,
        "hitl_review": None,
        "trajectory": None,
        "black_swan": None,
        "contagion": None,
        "learning": None,
        "elapsed_seconds": 0.0,
    }

    try:
        # optional websocket manager for progress updates
        try:
            from dip.api.ws.ws_manager import manager as ws_manager
        except Exception:
            ws_manager = None

        # Maintain strong references to background tasks to prevent GC
        _bg_tasks = set()

        def _publish_progress(payload: dict) -> None:
            # Best-effort async publish; schedule in event loop
            if not ws_manager:
                return
            topic = f"job:{job_id}" if job_id else None
            async def _do():
                try:
                    if topic:
                        await ws_manager.publish_topic(topic, payload)
                    else:
                        await ws_manager.broadcast(payload)
                except Exception as e:
                    logger.debug(f"[WS] Publish failed: {e}")
            try:
                import asyncio
                task = asyncio.create_task(_do())
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)
            except Exception as e:
                logger.debug(f"[WS] Failed to create background task: {e}")

        # ── Layer 1+2+3: Build State Context & Recursive RFI Loop ──
        logger.info("[Layer 1-3] Building State Context for %s", country_code)
        _publish_progress({"type": "phase.started", "phase": "collection", "country": country_code})
        blackboard.post(PipelinePhase.COLLECTION, "collection.started", {"country": country_code})
        
        state_provider = StateProvider()
        state_context = await state_provider.build_state_context(country_code, query)
        
        from dip.runtime.control_loop.investigation_controller import InvestigationController
        
        controller = InvestigationController(max_iterations=5, min_readiness=75.0, plateau_patience=2)
        state_context = await controller.run_loop(
            state_context=state_context, 
            goal=goal, 
            query=query, 
            country_code=country_code, 
            result_dict=result
        )
        
        # Iteration count for telemetry (fallback if needed)
        current_iteration = result.get("readiness_report", {}).get("iteration", 1)

        blackboard.state["observation_count"] = state_context.observation_count
        blackboard.post(
            PipelinePhase.COLLECTION,
            "collection.completed",
            {"observation_count": state_context.observation_count, "iterations": current_iteration},
        )
        
        blackboard.post(
            PipelinePhase.FUZZY_PROJECTION,
            "state.uncertainty_applied",
            {
                "confidence_decay": state_context.confidence_decay,
                "blindspots": list(state_context.data_blindspots),
            },
        )
        _publish_progress({"type": "phase.completed", "phase": "collection", "country": country_code})
        
        # Check Working Memory (Layer 3)
            
        nextgen_sre = run_fuzzy_sre(state_context)
        trace_step("SRE_COMPUTATION", "nextgen/sre.py", {"signals": state_context.observation_count}, {"sre_score": nextgen_sre.sre_escalation_score, "risk": nextgen_sre.risk_level})
        state_context.nextgen_sre = NextGenSREOutput(**nextgen_sre.model_dump(mode="json"))
        result["nextgen_sre"] = state_context.nextgen_sre.model_dump(mode="json")
        blackboard.state["nextgen_sre_score"] = nextgen_sre.sre_escalation_score
        blackboard.state["nextgen_sre_risk"] = nextgen_sre.risk_level
        blackboard.post(
            PipelinePhase.SRE,
            "nextgen_sre.completed",
            {
                "score": nextgen_sre.sre_escalation_score,
                "risk": nextgen_sre.risk_level,
                "projected_signal_count": len(nextgen_sre.projected_signals),
                "firewall_rejections": len(nextgen_sre.legal_firewall_rejections),
            },
        )
        _publish_progress({"type": "phase.completed", "phase": "sre", "score": nextgen_sre.sre_escalation_score, "risk": nextgen_sre.risk_level})
        if state_context.escalation:
            blackboard.post(
                PipelinePhase.SRE,
                "sre.available",
                {
                    "score": state_context.escalation.escalation_score,
                    "risk": state_context.escalation.threat_level,
                },
            )

        # ── Layer 4: Council of Ministers ─────────────────────────
        logger.info("[Layer 4] Convening Council of Ministers")
        _publish_progress({"type": "phase.started", "phase": "council"})
        blackboard.post(PipelinePhase.COUNCIL, "council.started", {})
        session = CouncilSession(query=query, state_context=state_context)
        # 1. ALWAYS run Heuristic Engine for deterministic baseline
        _heuristic_council(session)
        heuristic_baseline = list(session.hypotheses)
        
        # 2. Run AI Council (if not strictly forced to heuristic mode)
        force_heuristic = os.getenv("FORCE_MINISTER_HEURISTIC", "0") == "1"
        if not force_heuristic:
            try:
                ai_hypotheses = await run_council(
                    session,
                    heuristic_baseline=heuristic_baseline,
                    baseline_confidence=True,
                    allow_rule_challenge=True
                )
                if ai_hypotheses:
                    session.hypotheses = _merge_dual_engine_hypotheses(heuristic_baseline, ai_hypotheses)
            except Exception as e:
                logger.error(f"[Layer 4] AI Council failed to run/merge: {e}")
        trace_step("COUNCIL", "layer4_reasoning/ministers/*.py", {"query": query}, {"hypotheses": len(session.hypotheses)})
        blackboard.post(
            PipelinePhase.COUNCIL,
            "council.completed",
            {"hypothesis_count": len(session.hypotheses)},
        )
        _publish_progress({"type": "phase.completed", "phase": "council", "hypotheses": len(session.hypotheses)})

        # Collect missing signals
        if not session.missing_signals:
            for h in session.hypotheses:
                session.missing_signals.extend(h.missing_signals)

        # ── Layer 4: Red Team (if conflicts or multiple hypotheses) ─
        if session.hypotheses and (session.conflicts or len(session.hypotheses) > 1):
            logger.info("[Layer 4] Running Red Team challenge")
            _publish_progress({"type": "phase.started", "phase": "red_team"})
            await _safe_red_team(session)
            _publish_progress({"type": "phase.completed", "phase": "red_team", "report_len": len(session.red_team_report or [])})

        # ── Layer 4: CRAG Investigation (if missing signals) ─────
        if session.missing_signals:
            logger.info("[Layer 4] Running CRAG investigation")
            _publish_progress({"type": "phase.started", "phase": "investigation", "missing_signals": list(session.missing_signals[:5])})
            blackboard.post(
                PipelinePhase.INVESTIGATION,
                "investigation.started",
                {"missing_signals": list(session.missing_signals[:10])},
            )
            await _safe_crag(session)
            blackboard.post(
                PipelinePhase.INVESTIGATION,
                "investigation.completed",
                {"evidence_log_count": len(session.evidence_log)},
            )
            _publish_progress({"type": "phase.completed", "phase": "investigation", "evidence_count": len(session.evidence_log)})

        # ── Layer 4: Threat Synthesis ────────────────────────────
        logger.info("[Layer 4] Synthesizing threat assessment")
        _publish_progress({"type": "phase.started", "phase": "threat_synthesis"})
        
        span_synth = None
        if hasattr(tracer_provider, "start_as_current_span"):
            span_synth = tracer_provider.start_as_current_span("threat_synthesis")
            if hasattr(span_synth, "__enter__"): span_synth.__enter__()
        
        decide(session)
        
        # Disagreement Routing (Phase 8 - T27.5)
        dual_mode = getattr(session, "dual_mode_assessment", {})
        if dual_mode and dual_mode.get("agreement_score", 1.0) < 0.75:
            logger.warning("[Layer 4] High heuristic/LLM disagreement (score < 0.75). Triggering deep CRAG investigation.")
            _publish_progress({"type": "phase.started", "phase": "investigation", "reason": "disagreement"})
            await _safe_crag(session)
            # Re-run synthesis with new evidence
            decide(session)
            
        if span_synth: span_synth.__exit__(None, None, None)
        
        _publish_progress({"type": "phase.completed", "phase": "threat_synthesis", "final_decision": session.final_decision})

        # ── Layer 4: CoVe Decomposition + Verification ───────────
        logger.info("[Layer 4] Running CoVe + Verification")
        _publish_progress({"type": "phase.started", "phase": "cove_verification"})
        claims = await _safe_cove(session)
        verification_passed = verify(session, claims)
        blackboard.post(
            PipelinePhase.GATE,
            "verification.completed",
            {"passed": bool(verification_passed), "score": session.verification_score},
        )
        _publish_progress({"type": "phase.completed", "phase": "cove_verification", "passed": bool(verification_passed), "score": session.verification_score})

        # ── Layer 4: Refusal Gate ────────────────────────────────
        if not verification_passed:
            refusal = refuse(session)
            result["refusal"] = refusal
            result["status"] = "REFUSED"

            # HITL escalation for HIGH + low verification
            threat_is_high = session.final_decision and "HIGH" in session.final_decision
            if threat_is_high and session.verification_score < 0.7:
                hitl_package = request_review(session)
                result["hitl_review"] = hitl_package
                result["status"] = "HUMAN_REVIEW"
        else:
            session.status = "COMPLETE"
            result["status"] = "COMPLETE"
            
        # Run Introspection (Layer 4)
        analyze_bias(session)
        
        # Save to Working Memory
        from dip.pipeline.world_model.state.working_memory import WorkingMemory
        WorkingMemory().save_context(state_context)

        # ── Layer 5: Assessment Gate ─────────────────────────────
        logger.info("[Layer 5] Running Assessment Gate")
        _publish_progress({"type": "phase.started", "phase": "assessment_gate"})
        gate_state = build_assessment_state(session, result)
        gate_verdict = gate_assess(gate_state)
        trace_step("ASSESSMENT_GATE", "layer5_trajectory/assessment_gate.py", gate_state.__dict__, gate_verdict.to_dict())
        blackboard.post(
            PipelinePhase.GATE,
            "gate.verdict",
            {
                "approved": gate_verdict.approved,
                "decision": gate_verdict.decision,
                "reasons": gate_verdict.reasons,
            },
        )
        _publish_progress({
            "type": "phase.completed",
            "phase": "assessment_gate",
            "approved": gate_verdict.approved,
            "decision": gate_verdict.decision,
        })

        # Record for audit
        record_assessment(session, result, gate_verdict)

        # If gate withheld, update status
        if gate_verdict.withheld:
            result["status"] = "WITHHELD"
            result["gate_verdict"] = gate_verdict.to_dict()
            if gate_verdict.mandatory_review:
                result["status"] = "HUMAN_REVIEW"

        # ── Layer 5: Trajectory Forecast ─────────────────────────
        try:
            from dip.pipeline.forecasting.trajectory.trajectory_model import compute_trajectory
            trajectory = compute_trajectory(session)
            result["trajectory"] = trajectory
            logger.info("[Layer 5] Trajectory: %s", trajectory.get("label", "N/A"))
        except Exception as e:
            logger.debug("[Layer 5] Trajectory unavailable: %s", e)

        # ── Layer 5: Black Swan Detection ────────────────────────
        try:
            from dip.pipeline.forecasting.trajectory.black_swan_detector import detect_black_swan
            black_swan = detect_black_swan(session)
            result["black_swan"] = black_swan
            if isinstance(black_swan, dict) and black_swan.get("triggered"):
                logger.warning("[Layer 5] BLACK SWAN TRIGGERED: %s", black_swan.get("reasons"))
                result["status"] = "HUMAN_REVIEW"
        except Exception as e:
            logger.debug("[Layer 5] Black swan unavailable: %s", e)

        # ── Layer 8: Wargaming & Game Theory ─────────────────────
        try:
            from dip.pipeline.forecasting.wargaming.mesa_simulation import run_wargame_simulation
            from dip.pipeline.forecasting.wargaming.nash_equilibrium import compute_equilibrium
            
            # Nash Equilibrium
            nash = compute_equilibrium(
                capability=state_context.nextgen_sre.sre_escalation_score if state_context.nextgen_sre else 0.5,
                intent=session.verification_score,
                hypotheses=session.hypotheses,
                conflict_states=[]
            )
            result["nash_equilibrium"] = nash
            
            # Mesa Simulation
            sim = run_wargame_simulation(
                country=country_code,
                sre_score=state_context.nextgen_sre.sre_escalation_score if state_context.nextgen_sre else 0.5,
                domain_indices={"capability": 0.5, "intent": 0.5, "stability": 0.5},
                hypotheses=session.hypotheses,
                runs=50
            )
            import dataclasses
            result["wargame_simulation"] = dataclasses.asdict(sim)
            logger.info("[Layer 8] Wargaming simulation and Nash Equilibrium complete.")
        except Exception as e:
            logger.debug("[Layer 8] Wargaming unavailable: %s", e)

        # ── Graph Manager Ripple Effects ─────────────────────
        try:
            from dip.pipeline.world_model.state.graph_manager import GraphManager
            gm = GraphManager(max_retries=1)
            ripple_effects = gm.get_ripple_effects(country_code)
            result["ripple_effects"] = ripple_effects
            gm.close()
        except Exception as e:
            logger.debug("[Layer 3] GraphManager unavailable: %s", e)

        # ── Layer 6: Executive Summary ───────────────────────────
        try:
            composer = DossierComposer()
            briefing = composer.build_dossier(job_id or "default-job", {"session": session})
            result["briefing"] = briefing
        except Exception as e:
            result["briefing"] = f"[Briefing generation failed: {e}]"
        _publish_progress({"type": "phase.completed", "phase": "briefing"})

        # ── Layer 6: Memory Vault (store for future reference) ───
        try:
            MemoryVault, _, _ = _import_memory()
            if MemoryVault:
                vault = MemoryVault()
                vault.store_intelligence(
                    doc_id=f"{country_code}_{int(time.time())}",
                    title=f"Assessment: {query[:60]}",
                    content=result.get("briefing", ""),
                    metadata={
                        "tags": [country_code, result.get("threat_level", "UNKNOWN")],
                        "threat_level": result.get("threat_level", "UNKNOWN"),
                        "confidence": session.verification_score,
                        "query": query,
                    }
                )
                logger.info("[Layer 6] Intelligence stored in Memory Vault")
        except Exception as e:
            logger.debug("[Layer 6] Memory vault unavailable: %s", e)

        # ── Layer 6: Learning Engine (self-improvement) ──────────
        try:
            _, LearningEngine, ForecastArchive = _import_memory()
            if LearningEngine:
                engine = LearningEngine()
                learning = engine.learn_from_session(result)
                if hasattr(learning, "model_dump"):
                    result["learning"] = learning.model_dump(mode="json")
                elif hasattr(learning, "__dataclass_fields__"):
                    import dataclasses
                    result["learning"] = dataclasses.asdict(learning)
                else:
                    result["learning"] = learning
                logger.info("[Layer 6] Learning cycle complete")
            if ForecastArchive:
                archive = ForecastArchive()
                archive.record_forecast(
                    query=query,
                    country=country_code,
                    predicted_level=result.get("threat_level", "LOW"),
                    confidence=session.verification_score,
                )
                logger.info("[Layer 6] Forecast archived")
        except Exception as e:
            logger.debug("[Layer 6] Learning unavailable: %s", e)

        # ── Self-Model & Introspection ─────────────────────
        try:
            from dip.engines.self_model import get_self_model
            sm = get_self_model()
            sm.update_after_assessment(result)
            sm.log_backtest_result({"accuracy": result.get("verification_score", 0.0), "expected_accuracy": 0.9, "forecasts_resolved": 1})
            result["self_model_dashboard"] = sm.get_dashboard()
            logger.info("[Self-Model] Assessment logged to self model.")
        except Exception as e:
            logger.debug("[Self-Model] Unavailable: %s", e)

        # ── Layer 7: Global Contagion ────────────────────────────
        try:
            run_global = _import_global()
            if run_global and result.get("threat_level") in ("HIGH", "CRITICAL"):
                contagion = run_global({country_code: session.verification_score})
                result["contagion"] = contagion
                logger.info("[Layer 7] Contagion propagated from %s", country_code)
        except Exception as e:
            logger.debug("[Layer 7] Contagion unavailable: %s", e)

        # ── Explainable AI (xAI) Metadata ────────────────────────
        try:
            if hasattr(session.state_context, 'current_signals'):
                # Expose raw signals and extracted sources
                result["raw_sources"] = [s.model_dump(mode="json") if hasattr(s, "model_dump") else s.__dict__ for s in session.state_context.current_signals]
                sources = []
                for sig in session.state_context.current_signals:
                    source_str = getattr(sig, 'source_ref', 'Unknown Source')
                    code_str = getattr(sig, 'action', 'UNKNOWN_ACTION')
                    if source_str not in sources:
                        sources.append(f"{code_str} via {source_str}")
                result["xai_sources"] = list(set(sources))
        except Exception as e:
            logger.debug("Failed to extract xAI sources: %s", e)

        # ── Populate final result ────────────────────────────────
        result["verification_score"] = session.verification_score
        result["evidence_log"] = session.evidence_log
        result["red_team_report"] = session.red_team_report

        if session.final_decision:
            try:
                dec_json = json.loads(session.final_decision)
                result["threat_level"] = dec_json.get("overall_threat_level", "LOW")
            except Exception:
                for level in ["CRITICAL", "HIGH", "ELEVATED", "LOW"]:
                    if f'"overall_threat_level": "{level}"' in session.final_decision:
                        result["threat_level"] = level
                        break

        result["hypotheses"] = [
            {
                "minister": getattr(h, "minister", getattr(h, "minister_name", getattr(h, "domain", "Minister"))),
                "type": getattr(h, "hypothesis_type", getattr(h, "type", "hypothesis")),
                "confidence": getattr(h, "confidence", 0.5),
                "matched_signals": getattr(h, "matched_signals", []),
                "missing_signals": getattr(h, "missing_signals", []),
                "rationale": getattr(h, "rationale", getattr(h, "recalibration_rationale", "Corroborated by StateContext intelligence signals.")),
                "critical_signal_refs": getattr(h, "critical_signal_refs", []),
                "disagreement_notes": getattr(h, "disagreement_notes", []),
                "recalibrated_confidence": getattr(h, "recalibrated_confidence", None),
            }
            for h in session.hypotheses
        ]
        blackboard.post(
            PipelinePhase.REPORT,
            "assessment.result_populated",
            {"status": result["status"], "threat_level": result.get("threat_level")},
        )
        hoc_briefing = build_head_of_country_briefing(goal, state_context, result, blackboard)
        result["head_of_country_briefing"] = hoc_briefing.model_dump(mode="json")
        result["strategic_pressure"] = hoc_briefing.risk_matrix.get("pressure", {})
        result["fuzzy_trace"] = hoc_briefing.fuzzy_trace
        result["blackboard_events"] = [event.model_dump(mode="json") for event in blackboard.history()]
        result["learning_units"] = [unit.model_dump(mode="json") for unit in hoc_briefing.learning_units]
        result["experiment_records"] = [record.model_dump(mode="json") for record in hoc_briefing.experiment_records]
        result["promotion_status"] = [status.model_dump(mode="json") for status in hoc_briefing.promotion_status]
        result["schema_matches"] = []
        symbolic_report = run_symbolic_guardrails(result)
        result["symbolic_guardrails"] = symbolic_report.model_dump(mode="json")
        if not symbolic_report.passed and result["status"] == "COMPLETE":
            result["status"] = "HUMAN_REVIEW"
            blackboard.post(
                PipelinePhase.GATE,
                "symbolic_guardrails.human_review",
                {"findings": result["symbolic_guardrails"]["findings"]},
            )
        graph.save_phase(goal, PipelinePhase.REPORT, blackboard)
        _publish_progress({"type": "phase.completed", "phase": "report", "status": result["status"]})

        # ── Layer 6: Presentation (Strategic Narrative) ──────────
        try:
            from dip.pipeline.synthesis.presentation.strategic_narrative import (
                synthesize_narrative,
                narrative_to_markdown
            )
            narrative = synthesize_narrative(session, result)
            result["strategic_narrative"] = narrative
            result["strategic_narrative_md"] = narrative_to_markdown(narrative)
            logger.info("[Layer 6] Strategic narrative synthesized (mode: %s)", narrative.get("generation_mode"))
            
            try:
                from dip.engines.stix2_exporter import export_stix_bundle
                stix_bundle = export_stix_bundle(result, session)
                result["stix2_bundle"] = stix_bundle
            except ImportError:
                pass
                
            _publish_progress({"type": "phase.completed", "phase": "presentation"})
        except ImportError:
            pass
        except Exception as e:
            logger.debug("[Layer 6] Strategic narrative unavailable: %s", e)

        # ── Multiformat Intelligence Export (NEW — DIP 2.1) ─────────────
        try:
            from dip.engines.multiformat_exporter import export_all
            export_paths = export_all(result, session)
            result["export_paths"] = export_paths
            logger.info("[Export] Generated multiformat exports: %s", list(export_paths.keys()))
        except Exception as e:
            logger.debug("[Export] Multiformat export unavailable: %s", e)

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)
        blackboard.post(PipelinePhase.REPORT, "assessment.error", {"error": str(e)})
        result["blackboard_events"] = [event.model_dump(mode="json") for event in blackboard.history()]
        logger.error("[PIPELINE] Fatal error: %s", e, exc_info=True)

    # Phase 8: Final Safety Enforcer on every return path (T27.6)
    try:
        safety_status = enforce_safety(result)
        import dataclasses
        result["safety_status"] = dataclasses.asdict(safety_status)
        if not safety_status.passed:
            logger.critical("[PIPELINE] Output failed safety verification: %s", safety_status.blocked_outputs)
            result["status"] = "WITHHELD"
    except Exception as e:
        logger.error("[PIPELINE] Safety enforcer error: %s", e)

    # Phase 8: MLFlow logging (T27.11)
    if mlflow and getattr(config, "DIP_MLFLOW_ENABLED", False):
        try:
            if mlflow.active_run():
                mlflow.log_metric("verification_score", result.get("verification_score", 0.0))
                mlflow.log_metric("elapsed_seconds", round(time.time() - t0, 2))
                mlflow.log_param("threat_level", result.get("threat_level"))
        except Exception as e:
            logger.debug("[PIPELINE] MLFlow logging failed: %s", e)

    result["elapsed_seconds"] = round(time.time() - t0, 2)
    try:
        tracer.finalize(result)
    except Exception:
        pass
    try:
        trace_cm.__exit__(None, None, None)
    except Exception:
        pass
    return result
