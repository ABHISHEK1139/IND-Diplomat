import time
import logging
import asyncio
from typing import Dict, Any, List

from dip.core.schema import StateContext, ResearchLogEntry
from dip.layer2_knowledge.signal_extractor import SignalExtractor
from dip.nextgen.step_tracer import trace_step
from dip.layer3_state.uncertainty_monitor import apply_uncertainty_decay
from .readiness_engine import evaluate_readiness

logger = logging.getLogger("DIP.ControlLoop.Controller")

class InvestigationController:
    """
    Central orchestrator for the autonomous investigation loop.
    Repeatedly evaluates readiness, identifies gaps, generates RFIs, and executes them
    until readiness is achieved or limits are hit.
    """
    def __init__(self, max_iterations: int = 3, min_readiness: float = 80.0):
        self.max_iterations = max_iterations
        self.min_readiness = min_readiness
        
    async def run_loop(self, state_context: StateContext, goal: Any, query: str, country_code: str, result_dict: Dict[str, Any]) -> StateContext:
        """
        Executes the recursive loop. Modifies state_context and result_dict in-place.
        """
        current_iteration = 1
        extractor = SignalExtractor()
        
        while current_iteration <= self.max_iterations:
            trace_step("COLLECTION", "control_loop/investigation_controller.py", 
                       {"country": country_code, "query": query, "iteration": current_iteration}, 
                       {"observation_count": getattr(state_context, 'observation_count', 0)})
            
            # Apply Uncertainty Monitor (Layer 3)
            state_context = apply_uncertainty_decay(state_context)
            
            # Step 1-6 - Evaluate Readiness, Find Gaps, Generate RFIs
            report = evaluate_readiness(state_context, goal, iteration=current_iteration)
            
            if report.is_ready or report.score >= self.min_readiness:
                logger.info(f"[ICL] Readiness passed ({report.score:.1f}%). Proceeding to Reasoning.")
                break
                
            if current_iteration == self.max_iterations:
                logger.warning(f"[ICL] Readiness failed ({report.score:.1f}%) after {self.max_iterations} iterations. Requesting Human Override.")
                result_dict["status"] = "HUMAN_OVERRIDE_REQUIRED"
                break
                
            logger.warning(f"[ICL] RFI Triggered: {len(report.rfi_queries)} queries generated.")
            result_dict["status"] = "RFI_REQUIRED"
            
            # Step 7 & 8 - Execute RFIs and Update World Model
            for rfi in report.rfi_queries:
                if rfi.priority in ["HIGH", "MEDIUM"]:
                    log_entry = ResearchLogEntry(rfi=rfi, status="EXECUTED")
                    try:
                        t_start = time.time()
                        new_signals = await extractor.extract_signals(rfi.query)
                        log_entry.execution_time_ms = (time.time() - t_start) * 1000
                        
                        if new_signals:
                            log_entry.status = "EVIDENCE_FOUND"
                            log_entry.evidence_found = len(new_signals)
                            state_context.current_signals.extend(new_signals)
                            if hasattr(state_context, 'observation_count'):
                                state_context.observation_count += len(new_signals)
                    except Exception as e:
                        logger.debug(f"[ICL] RFI fetch failed for query '{rfi.query}': {e}")
                        
                    result_dict["research_log"].append(log_entry.model_dump(mode="json"))
                    
            logger.info(f"[ICL] Iteration {current_iteration} complete. Recalculating readiness...")
            current_iteration += 1
            
        result_dict["readiness_report"] = report.model_dump(mode="json")
        return state_context
