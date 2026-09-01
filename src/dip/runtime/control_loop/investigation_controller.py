import time
import logging
import asyncio
from typing import Dict, Any, List

from dip.core.schema import StateContext, ResearchLogEntry
from dip.pipeline.knowledge.signal_extractor import SignalExtractor
from dip.engines.step_tracer import trace_step
from dip.pipeline.world_model.state.uncertainty_monitor import apply_uncertainty_decay
from .readiness_engine import evaluate_readiness

logger = logging.getLogger("DIP.ControlLoop.Controller")


class InvestigationController:
    """
    Central orchestrator for the autonomous investigation loop.

    Repeatedly evaluates readiness, identifies gaps, generates RFIs, and
    executes them until readiness is achieved or limits are hit.

    The loop is ADAPTIVE:
      - Default max_iterations=5 (not the old hard 3).
      - If the readiness score IMPROVES between iterations, the loop
        continues searching (evidence is converging).
      - If the score plateaus or regresses for 2 consecutive iterations,
        it stops early (diminishing returns).
      - Each iteration can spawn N parallel RFI searches.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        min_readiness: float = 75.0,
        plateau_patience: int = 2,
    ):
        self.max_iterations = max_iterations
        self.min_readiness = min_readiness
        self.plateau_patience = plateau_patience

    async def run_loop(
        self,
        state_context: StateContext,
        goal: Any,
        query: str,
        country_code: str,
        result_dict: Dict[str, Any],
    ) -> StateContext:
        """
        Executes the adaptive recursive investigation loop.
        Modifies state_context and result_dict in-place.
        """
        current_iteration = 1
        extractor = SignalExtractor()
        previous_score: float = 0.0
        plateau_count: int = 0

        while current_iteration <= self.max_iterations:
            trace_step(
                "COLLECTION",
                "control_loop/investigation_controller.py",
                {
                    "country": country_code,
                    "query": query,
                    "iteration": current_iteration,
                },
                {
                    "observation_count": getattr(
                        state_context, "observation_count", 0
                    )
                },
            )

            # Apply Uncertainty Monitor (Layer 3)
            state_context = apply_uncertainty_decay(state_context)

            # Step 1-6 — Evaluate Readiness, Find Gaps, Generate RFIs
            report = evaluate_readiness(
                state_context, goal, iteration=current_iteration
            )

            # ── Readiness achieved → proceed to Reasoning ──
            if report.is_ready or report.score >= self.min_readiness:
                logger.info(
                    "[ICL] Readiness passed (%.1f%%) on iteration %d. "
                    "Proceeding to Reasoning.",
                    report.score,
                    current_iteration,
                )
                break

            # ── Adaptive plateau detection ──
            score_delta = report.score - previous_score
            if current_iteration > 1:
                if score_delta <= 1.0:
                    # Score didn't meaningfully improve
                    plateau_count += 1
                    logger.info(
                        "[ICL] Score plateau detected (%.1f → %.1f, δ=%.1f). "
                        "Patience %d/%d.",
                        previous_score,
                        report.score,
                        score_delta,
                        plateau_count,
                        self.plateau_patience,
                    )
                    if plateau_count >= self.plateau_patience:
                        logger.warning(
                            "[ICL] Readiness plateaued at %.1f%% after %d "
                            "iterations. Proceeding with available evidence.",
                            report.score,
                            current_iteration,
                        )
                        break
                else:
                    # Score is improving — reset patience counter
                    plateau_count = 0
                    logger.info(
                        "[ICL] Score improving (%.1f → %.1f, δ=+%.1f). "
                        "Continuing search.",
                        previous_score,
                        report.score,
                        score_delta,
                    )

            previous_score = report.score

            # ── Final iteration exhausted ──
            if current_iteration == self.max_iterations:
                logger.warning(
                    "[ICL] Readiness failed (%.1f%%) after %d iterations. "
                    "Requesting Human Override.",
                    report.score,
                    self.max_iterations,
                )
                result_dict["status"] = "HUMAN_OVERRIDE_REQUIRED"
                break

            logger.warning(
                "[ICL] RFI Triggered: %d queries generated (iteration %d).",
                len(report.rfi_queries),
                current_iteration,
            )
            result_dict["status"] = "RFI_REQUIRED"

            # ── Step 7 & 8 — Execute RFIs in parallel and update World Model ──
            async def _execute_rfi(rfi):
                log_entry = ResearchLogEntry(rfi=rfi, status="EXECUTED")
                try:
                    t_start = time.time()
                    new_signals = await extractor.extract_signals(rfi.query)
                    log_entry.execution_time_ms = (time.time() - t_start) * 1000
                    if new_signals:
                        log_entry.status = "EVIDENCE_FOUND"
                        log_entry.evidence_found = len(new_signals)
                        return new_signals, log_entry
                except Exception as e:
                    logger.debug(
                        "[ICL] RFI fetch failed for query '%s': %s",
                        rfi.query,
                        e,
                    )
                return [], log_entry

            # Run HIGH and MEDIUM priority RFIs in parallel
            high_medium_rfis = [
                r for r in report.rfi_queries if r.priority in ["HIGH", "MEDIUM"]
            ]
            if high_medium_rfis:
                tasks = [_execute_rfi(rfi) for rfi in high_medium_rfis]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for res in results:
                    if isinstance(res, Exception):
                        continue
                    new_signals, log_entry = res
                    if new_signals:
                        state_context.current_signals.extend(new_signals)
                        if hasattr(state_context, "observation_count"):
                            state_context.observation_count += len(new_signals)
                    result_dict["research_log"].append(
                        log_entry.model_dump(mode="json")
                    )

            logger.info(
                "[ICL] Iteration %d complete. Signals: %d. Recalculating readiness...",
                current_iteration,
                len(state_context.current_signals),
            )
            current_iteration += 1

        result_dict["readiness_report"] = report.model_dump(mode="json")
        return state_context
