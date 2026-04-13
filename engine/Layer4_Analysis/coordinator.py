"""
The King (Coordinator).
Orchestrates the Council of Ministers and judges hypotheses against evidence.

This is the heart of Layer-4 execution. All modules flow through:
1. convene_council() - collect hypotheses
2. Detect conflicts
3. Red team if needed
4. CRAG investigation if signals are missing
5. Synthesize decision
6. Verify claims
7. Check refusal threshold
8. Check HITL threshold
"""

import logging
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import List, Set, Dict, Any, Optional, Tuple
from dataclasses import asdict
from engine.Layer3_StateModel.schemas.state_context import StateContext
from Config.config import (
    OPTIONAL_LLM_STAGE_MAX_EMPTY_RESPONSES,
    OPTIONAL_LLM_STAGE_MAX_RATE_LIMIT_HITS,
)

logger = logging.getLogger(__name__)
from engine.Layer4_Analysis.council_session import CouncilSession, MinisterReport, SessionStatus
from engine.Layer4_Analysis.reasoning_phase import ReasoningPhase
from engine.Layer4_Analysis.ministers import (
    BaseMinister, 
    SecurityMinister, 
    EconomicMinister, 
    DomesticMinister, 
    DiplomaticMinister,
    ContrarianMinister,
)
from engine.Layer4_Analysis.schema import AssessmentReport, Hypothesis, ThreatLevel
from engine.Layer4_Analysis.decision.threat_synthesizer import ThreatSynthesizer
from engine.Layer4_Analysis.investigation.anomaly_sentinel import AnomalySentinel
from engine.Layer4_Analysis.investigation.investigation_controller import InvestigationController
from engine.Layer4_Analysis.investigation.knowledge_sufficiency import knowledge_is_sufficient
from engine.Layer4_Analysis.evidence.pressure_mapper import map_state_to_pressures
from Core.intelligence.pir import (
    build_collection_plan,
    detect_belief_gaps,
    gaps_to_pirs,
    log_pirs,
    PIR,
    PIRPriority,
    SIGNAL_COLLECTION_MODALITY,
    CollectionPlan,
    BeliefGap,
)
from engine.Layer5_Judgment.assessment_gate import (
    evaluate as gate_evaluate,
    build_assessment_state as gate_build_state,
    GateVerdict,
)
from engine.Layer4_Analysis.domain_fusion import compute_domain_indices
from engine.Layer4_Analysis.escalation_index import (
    compute_escalation_index, escalation_to_risk, EscalationInput,
)

# â”€â”€ Pipeline sub-modules (surgical extraction) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from engine.Layer4_Analysis.pipeline.synthesis_engine import run_synthesis as _pipeline_synthesis
from engine.Layer4_Analysis.pipeline.output_builder import (
    build_council_reasoning_dict as _pipeline_council_reasoning,
    serialize_hypotheses as _pipeline_serialize_hyps,
    build_withheld_output as _pipeline_withheld_output,
    build_approved_output as _pipeline_approved_output,
    _minister_dimension as _pipeline_minister_dim,
)
from engine.Layer4_Analysis.pipeline.legal_rag_runner import run_post_gate_legal_rag as _pipeline_legal_rag
from engine.Layer4_Analysis.pipeline.withheld_recollection import run_recollection_loop as _pipeline_recollection


class CouncilCoordinator:
    RED_TEAM_CONFIDENCE_THRESHOLD = 0.65
    MATCHED_BELIEF_THRESHOLD = 0.20      # lowered: continuous belief; was 0.50 binary
    LOGIC_REFUSAL_THRESHOLD = 0.35
    MAX_PHASE_LOOPS = 20
    HIGH_IMPACT_THREAT_LEVELS = {ThreatLevel.ELEVATED, ThreatLevel.HIGH, ThreatLevel.CRITICAL}
    PREDICTIVE_MARKERS = (
        "predict",
        "prediction",
        "probability",
        "likely",
        "will",
        "forecast",
        "chance",
        "risk of",
        "scenario",
        "if ",
    )
    GROUPTHINK_CONTEXT_GAP_SIGNAL_RE = re.compile(r"\bSIG_[A-Z0-9_]+\b")

    def __init__(self, **kwargs):
        self.ministers: List[BaseMinister] = [
            SecurityMinister(),
            EconomicMinister(),
            DomesticMinister(),
            DiplomaticMinister(),
            ContrarianMinister(),   # Phase 8: devil's advocate
        ]
        self.synthesizer = ThreatSynthesizer()
        self.sentinel = AnomalySentinel()
        self.investigation_controller = InvestigationController()

    def _set_phase(self, session: CouncilSession, phase: ReasoningPhase):
        """Transition session to next phase with logging."""
        old_phase = session.phase.value if session.phase else "UNDEFINED"
        new_phase = phase.value
        logger.info(f"[PHASE TRANSITION] {old_phase} Ã¢â€ â€™ {new_phase}")
        session.transition_to(phase)

    def _reset_for_reanalysis(self, session: CouncilSession):
        """
        Reset deliberation artifacts so refreshed state is analyzed cleanly.
        NOTE: investigation_needs is NOT cleared Ã¢â‚¬â€ it accumulates across loops
        so the final assessment retains the full list of what was sought.
        """
        session.ministers_reports.clear()
        session.hypotheses.clear()
        session.identified_conflicts.clear()
        # session.red_team_report intentionally NOT cleared -- red team only
        # runs in cycle 1 (CHALLENGE phase). Clearing here would wipe results
        # before APPROVED/WITHHELD paths serialize, causing false report output.
        session.missing_signals = []
        # investigation_needs intentionally NOT cleared

    async def _run_investigation_phase(self, session: CouncilSession, query: str) -> Tuple[CouncilSession, Dict[str, Any]]:
        """
        Run investigation bridge, rebuild state context, and re-enter deliberation.
        Integrates CRAGEngine to evaluate current evidence quality first.
        """
        max_cycles = int(getattr(session, "MAX_INVESTIGATION_CYCLES", 3) or 3)
        max_rounds = int(getattr(session, "MAX_INVESTIGATION_ROUNDS", 3) or 3)

        if int(getattr(session, "investigation_rounds", 0) or 0) >= max_rounds:
            session.investigation_closed = True
            return session, {
                "requested_signals": [],
                "state_rebuilt": False,
                "new_observations": 0,
                "reason": "evidence_exhausted",
                "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
                "max_investigation_rounds": int(max_rounds),
                "investigation_cycles": int(session.investigation_cycles),
                "max_investigation_cycles": int(max_cycles),
                "investigation_closed": True,
            }

        if session.investigation_cycles >= max_cycles:
            session.investigation_closed = True
            return session, {
                "requested_signals": [],
                "state_rebuilt": False,
                "new_observations": 0,
                "reason": "investigation_budget_exhausted",
                "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
                "max_investigation_rounds": int(max_rounds),
                "investigation_cycles": int(session.investigation_cycles),
                "max_investigation_cycles": int(max_cycles),
                "investigation_closed": True,
            }

        if knowledge_is_sufficient(session):
            session.investigation_closed = True
            return session, {
                "requested_signals": [],
                "state_rebuilt": False,
                "new_observations": 0,
                "reason": "knowledge_sufficient",
                "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
                "max_investigation_rounds": int(max_rounds),
                "investigation_cycles": int(session.investigation_cycles),
                "max_investigation_cycles": int(max_cycles),
                "investigation_closed": True,
            }

        logger.info(f"[INVESTIGATION] Starting investigation with {len(session.missing_signals)} missing signals")
        session.status = SessionStatus.INVESTIGATING
        missing = self._collect_missing_signals(session)
        missing = self._canonical_signal_set(missing)
        session.missing_signals = missing
        if not missing:
            session.investigation_closed = True
            return session, {
                "requested_signals": [],
                "state_rebuilt": False,
                "new_observations": 0,
                "reason": "no_critical_missing_signals",
                "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
                "max_investigation_rounds": int(max_rounds),
                "investigation_cycles": int(session.investigation_cycles),
                "max_investigation_cycles": int(max_cycles),
                "investigation_closed": True,
            }

        should_skip, skip_reason = self._should_skip_repeated_investigation(session, missing)
        if should_skip:
            session.investigation_closed = True
            return session, {
                "requested_signals": list(missing),
                "state_rebuilt": False,
                "new_observations": 0,
                "reason": skip_reason,
                "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
                "max_investigation_rounds": int(max_rounds),
                "investigation_cycles": int(session.investigation_cycles),
                "max_investigation_cycles": int(max_cycles),
                "investigation_closed": True,
            }
        for signal in missing:
            if signal not in session.investigation_needs:
                session.investigation_needs.append(signal)

        before_signature = self._state_material_signature(session.state_context, missing)

        # â”€â”€ Attach collection plan to investigation metadata â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # The collection plan contains typed PIRs (not text queries).
        # investigate_and_update() receives structured collection tasks.
        plan: CollectionPlan = getattr(session, "collection_plan", None) or CollectionPlan()
        if not plan.pirs and missing:
            plan = self._ensure_collection_plan_for_signals(
                session,
                missing,
                reason_prefix="missing_signal_reinvestigation",
            )
            session.collection_plan = plan

        # â”€â”€ ARS SAFEGUARD â€” suppress MoltBot if confidence is adequate â”€â”€
        # MoltBot web collection is expensive and noisy.  Only trigger it
        # when:  (a) average hypothesis coverage < 0.60  AND
        #        (b) collection plan has at least one CRITICAL PIR.
        #
        # If either condition fails, the investigation still proceeds but
        # with an EMPTY plan â€” state rebuild uses existing RAG data only.
        avg_coverage = self._average_hypothesis_coverage(session)
        _COLLECTION_COVERAGE_THRESHOLD = 0.60
        if plan.pirs and (avg_coverage >= _COLLECTION_COVERAGE_THRESHOLD or not plan.has_critical):
            logger.info(
                "[INVESTIGATION] MoltBot collection SUPPRESSED â€” "
                "avg_coverage=%.3f (threshold=%.2f), has_critical=%s",
                avg_coverage, _COLLECTION_COVERAGE_THRESHOLD, plan.has_critical,
            )
            investigation_meta_note = (
                f"collection_suppressed: coverage={avg_coverage:.3f}>={_COLLECTION_COVERAGE_THRESHOLD} "
                f"or no_critical_pir={not plan.has_critical}"
            )
            plan = CollectionPlan()  # Empty plan â€” no MoltBot calls
        else:
            investigation_meta_note = ""
            if plan.pirs:
                logger.info(
                    "[INVESTIGATION] MoltBot collection AUTHORIZED â€” "
                    "avg_coverage=%.3f, critical_PIRs=%d",
                    avg_coverage,
                    sum(1 for p in plan.pirs if p.priority.value == "CRITICAL"),
                )

        investigation_meta: Dict[str, Any] = {
            "requested_signals": list(session.missing_signals),
            "state_rebuilt": False,
            "new_observations": 0,
            "reason": "missing_signals" if missing else "black_swan_forced",
            "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
            "max_investigation_rounds": int(max_rounds),
            "investigation_cycles": int(session.investigation_cycles),
            "max_investigation_cycles": int(max_cycles),
            "collection_note": investigation_meta_note or "collection_plan_active",
            "avg_coverage": round(avg_coverage, 4),
        }

        # 1. CRAG Evaluation
        try:
            from engine.Layer4_Analysis.deliberation.crag import CRAGEngine, RetrievalQuality, CRAGAction
            crag = CRAGEngine()
            evidence_docs = [{"content": str(sig)} for sig in session.evidence_log]
            
            # evaluate current evidence as documents
            ctx_dict = session.state_context.to_dict() if hasattr(session.state_context, "to_dict") else {}
            crag_result = await crag.evaluate_and_correct(query, evidence_docs, ctx_dict)
            
            investigation_meta["crag_quality"] = crag_result.quality.value
            investigation_meta["crag_action"] = crag_result.action_taken.value
            
            if crag_result.quality == RetrievalQuality.CORRECT:
                # Evidence is actually sufficient, skip state rebuild
                investigation_meta["reason"] = "crag_deemed_sufficient"
                session.investigation_closed = True
                return session, investigation_meta
                
            if crag_result.action_taken == CRAGAction.REFINE_QUERY and crag_result.refined_query:
                query = crag_result.refined_query  # Use refined query for the rebuild
                investigation_meta["refined_query"] = query
                
            elif crag_result.action_taken == CRAGAction.REFUSE:
                # Treat retrieval refusal as investigation closure, not automatic anomaly.
                # Preserve existing hypotheses so verification/synthesis can continue.
                investigation_meta["reason"] = "crag_refusal_no_rebuild"
                session.investigation_closed = True
                return session, investigation_meta
                
        except Exception as crag_exc:
            investigation_meta["crag_error"] = str(crag_exc)

        # 2. State Rebuild â€” driven by collection plan, not text queries
        try:
            from engine.Layer3_StateModel.interface.state_provider import investigate_and_update

            current_state = session.state_context.to_dict() if hasattr(session.state_context, "to_dict") else {}

            # Pass the collection plan as structured investigation needs.
            # investigate_and_update receives typed PIRs, NOT search strings.
            pir_dicts = [p.to_dict() for p in plan.pirs[:5]] if plan.pirs else []
            if plan.pirs:
                logger.info(
                    "[INVESTIGATION] Issuing %d PIRs â†’ modalities: %s",
                    len(plan.pirs),
                    plan.modalities_needed,
                )

            updated_context, new_observations = investigate_and_update(
                query=query,
                current_state=current_state,
                investigation_needs={
                    "missing_signals": list(session.missing_signals),
                    "black_swan": bool(session.black_swan),
                    "collection_plan": plan.to_dict() if plan.pirs else {},
                    "pirs": pir_dicts,
                },
            )
            if updated_context is not None:
                session.state_context = updated_context
                try:
                    pressures = map_state_to_pressures(session.state_context).to_dict()
                except Exception:
                    pressures = dict(getattr(session.state_context, "pressures", {}) or {})
                session.pressures = dict(pressures or {})
                if hasattr(session.state_context, "pressures"):
                    session.state_context.pressures = dict(session.pressures)
                self._ensure_pressure_derived_signals(session.state_context, session.pressures)
                investigation_meta["state_rebuilt"] = True

            if isinstance(new_observations, list):
                investigation_meta["new_observations"] = len(new_observations)
                for obs in new_observations:
                    token = str(obs or "").strip()
                    if token:
                        session.evidence_log.append(token)
        except Exception as exc:
            investigation_meta["error"] = str(exc)

        after_signature = self._state_material_signature(session.state_context, missing)
        material_change = bool(before_signature != after_signature)
        session.last_investigated_signal_set = list(missing)
        session.last_investigation_state_signature = after_signature
        session.last_investigation_material_change = material_change
        investigation_meta["material_state_change"] = material_change
        investigation_meta["state_signature_before"] = before_signature
        investigation_meta["state_signature_after"] = after_signature

        session.turn_count += 1
        session.investigation_cycles += 1
        session.investigation_rounds = int(getattr(session, "investigation_rounds", 0) or 0) + 1
        investigation_meta["investigation_rounds"] = int(session.investigation_rounds)
        investigation_meta["investigation_cycles"] = int(session.investigation_cycles)
        if not material_change:
            session.investigation_closed = True
            investigation_meta["investigation_closed"] = True
            investigation_meta["reason"] = str(investigation_meta.get("reason") or "no_material_state_change")
        if session.investigation_cycles >= max_cycles or session.investigation_rounds >= max_rounds:
            session.investigation_closed = True
            investigation_meta["investigation_closed"] = True
            if session.investigation_rounds >= max_rounds:
                investigation_meta["reason"] = "evidence_exhausted"
        # Only clear deliberation artifacts when we expect to rerun ministers.
        if not session.investigation_closed:
            self._reset_for_reanalysis(session)
        return session, investigation_meta

    def _average_hypothesis_coverage(self, session: CouncilSession) -> float:
        if not session.hypotheses:
            return 0.0
        return sum(max(0.0, min(1.0, float(h.coverage or 0.0))) for h in session.hypotheses) / len(session.hypotheses)

    @staticmethod
    def _canonical_signal_set(signals: List[str]) -> List[str]:
        deduped: List[str] = []
        seen: Set[str] = set()
        for signal in list(signals or []):
            token = str(signal or "").strip().upper()
            if not token or token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return sorted(deduped)

    def _signal_has_sufficient_recent_support(self, session: CouncilSession, signal: str) -> bool:
        token = str(signal or "").strip().upper()
        if not token:
            return False
        belief_map, temporal_map, source_map = self._build_signal_belief_maps(getattr(session, "state_context", None))
        belief = float(belief_map.get(token, 0.0) or 0.0)
        temporal = float(temporal_map.get(token, 0.0) or 0.0)
        source = float(source_map.get(token, 0.0) or 0.0)
        return belief >= 0.45 and temporal >= 0.55 and source >= 0.35

    def _signals_already_covered(self, session: CouncilSession, signals: List[str]) -> bool:
        canonical = self._canonical_signal_set(signals)
        if not canonical:
            return False
        return all(self._signal_has_sufficient_recent_support(session, signal) for signal in canonical)

    def _state_material_signature(self, state_context: Optional[StateContext], signals: Optional[List[str]] = None) -> str:
        belief_map, temporal_map, source_map = self._build_signal_belief_maps(state_context)
        target_signals = self._canonical_signal_set(signals or list(belief_map.keys())[:12])
        payload: Dict[str, Any] = {
            "signals": {
                token: {
                    "belief": round(float(belief_map.get(token, 0.0) or 0.0), 4),
                    "temporal": round(float(temporal_map.get(token, 0.0) or 0.0), 4),
                    "source": round(float(source_map.get(token, 0.0) or 0.0), 4),
                }
                for token in target_signals
            },
            "risk_level": str(getattr(state_context, "risk_level", "") or ""),
            "capability_index": round(float(getattr(state_context, "capability_index", 0.0) or 0.0), 4) if state_context is not None else 0.0,
            "intent_index": round(float(getattr(state_context, "intent_index", 0.0) or 0.0), 4) if state_context is not None else 0.0,
            "stability_index": round(float(getattr(state_context, "stability_index", 0.0) or 0.0), 4) if state_context is not None else 0.0,
            "cost_index": round(float(getattr(state_context, "cost_index", 0.0) or 0.0), 4) if state_context is not None else 0.0,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()

    def _should_skip_repeated_investigation(self, session: CouncilSession, signals: List[str]) -> Tuple[bool, str]:
        canonical = self._canonical_signal_set(signals)
        if not canonical:
            return True, "no_target_signals"
        if self._signals_already_covered(session, canonical):
            return True, "target_signals_already_have_fresh_support"

        current_signature = self._state_material_signature(getattr(session, "state_context", None), canonical)
        last_signals = self._canonical_signal_set(list(getattr(session, "last_investigated_signal_set", []) or []))
        last_signature = str(getattr(session, "last_investigation_state_signature", "") or "")
        last_changed = bool(getattr(session, "last_investigation_material_change", False))
        if canonical == last_signals and current_signature == last_signature and not last_changed:
            return True, "repeated_signal_set_without_material_change"
        return False, ""

    @staticmethod
    def _risk_vote_value(adjustment: str) -> float:
        token = str(adjustment or "maintain").strip().lower()
        if token == "increase":
            return 1.0
        if token == "decrease":
            return -1.0
        return 0.0

    @staticmethod
    def _report_weight(report: MinisterReport) -> float:
        confidence = max(0.10, min(0.95, float(getattr(report, "confidence", 0.5) or 0.5)))
        justification = max(0.10, min(0.95, float(getattr(report, "justification_strength", 0.5) or 0.5)))
        return confidence * justification

    def _aggregate_minister_outputs(self, reports: List[MinisterReport]) -> Dict[str, Any]:
        votes = {"increase": 0, "decrease": 0, "maintain": 0}
        weighted_votes = {"increase": 0.0, "decrease": 0.0, "maintain": 0.0}
        weighted_modifier_sum = 0.0
        weighted_risk_sum = 0.0
        total_weight = 0.0

        for report in list(reports or []):
            adjustment = str(getattr(report, "risk_level_adjustment", "maintain") or "maintain").lower().strip()
            if adjustment not in votes:
                adjustment = "maintain"
            votes[adjustment] += 1
            weight = self._report_weight(report)
            weighted_votes[adjustment] += weight
            total_weight += weight
            weighted_modifier_sum += weight * float(getattr(report, "confidence_modifier", 0.0) or 0.0)
            weighted_risk_sum += weight * self._risk_vote_value(adjustment)

        total_weight = max(total_weight, 1e-6)
        weighted_modifier = weighted_modifier_sum / total_weight
        weighted_risk = weighted_risk_sum / total_weight
        weighted_majority = max(weighted_votes, key=weighted_votes.get) if weighted_votes else "maintain"
        disagreement = len({adj for adj, count in votes.items() if count > 0}) > 1

        return {
            "votes": votes,
            "weighted_votes": weighted_votes,
            "weighted_modifier": weighted_modifier,
            "weighted_risk": weighted_risk,
            "weighted_majority": weighted_majority,
            "total_weight": total_weight,
            "disagreement": disagreement,
        }


    @staticmethod
    def _minister_dimension(minister_name: str) -> str:
        return _pipeline_minister_dim(minister_name)

    @staticmethod
    def _build_council_reasoning_dict(session: CouncilSession) -> Dict[str, Any]:
        """Build council reasoning summary for output serialisation."""
        return _pipeline_council_reasoning(session)

    def _dimension_coverages(self, session: CouncilSession) -> Dict[str, float]:
        dimensions = {
            "CAPABILITY": 0.0,
            "INTENT": 0.0,
            "STABILITY": 0.0,
            "COST": 0.0,
        }
        for h in list(session.hypotheses or []):
            dim = str(getattr(h, "dimension", "UNKNOWN") or "UNKNOWN").strip().upper()
            if dim not in dimensions:
                continue
            value = max(0.0, min(1.0, float(getattr(h, "coverage", 0.0) or 0.0)))
            dimensions[dim] = max(dimensions[dim], value)
        return dimensions

    def _state_dimensions(self, session: CouncilSession) -> Dict[str, float]:
        state = getattr(session, "state_context", None)
        if state is None:
            return self._dimension_coverages(session)

        cap = max(0.0, min(1.0, float(getattr(state, "capability_index", 0.0) or 0.0)))
        intent = max(0.0, min(1.0, float(getattr(state, "intent_index", 0.0) or 0.0)))
        stability = max(0.0, min(1.0, float(getattr(state, "stability_index", 0.0) or 0.0)))
        cost = max(0.0, min(1.0, float(getattr(state, "cost_index", 0.0) or 0.0)))

        if max(cap, intent, stability, cost) <= 0.0:
            return self._dimension_coverages(session)

        return {
            "CAPABILITY": cap,
            "INTENT": intent,
            "STABILITY": stability,
            "COST": cost,
        }

    @staticmethod
    def _driver_score_from_dimensions(dimensions: Dict[str, float]) -> float:
        capability = max(0.0, min(1.0, float((dimensions or {}).get("CAPABILITY", 0.0) or 0.0)))
        intent = max(0.0, min(1.0, float((dimensions or {}).get("INTENT", 0.0) or 0.0)))
        stability = max(0.0, min(1.0, float((dimensions or {}).get("STABILITY", 0.0) or 0.0)))
        cost = max(0.0, min(1.0, float((dimensions or {}).get("COST", 0.0) or 0.0)))
        # Capability + intent drive escalation, stability and cost are secondary enabling factors.
        return max(
            0.0,
            min(
                1.0,
                (capability * 0.40)
                + (intent * 0.35)
                + (stability * 0.15)
                + (cost * 0.10),
            ),
        )

    @staticmethod
    def _constraint_score(session: CouncilSession) -> float:
        ctx = getattr(session, "state_context", None)
        constraints = getattr(ctx, "constraints", None) if ctx is not None else None
        if constraints is None:
            return 0.0
        total_fn = getattr(constraints, "total_constraint", None)
        if callable(total_fn):
            try:
                return max(0.0, min(1.0, float(total_fn() or 0.0)))
            except Exception:
                return 0.0
        # Compatibility: accept dict-like payload.
        if isinstance(constraints, dict):
            try:
                return max(0.0, min(1.0, float(constraints.get("total_constraint", 0.0) or 0.0)))
            except Exception:
                return 0.0
        return 0.0

    def _net_escalation_score(self, session: CouncilSession) -> Tuple[float, float, float]:
        dimensions = self._dimension_coverages(session)
        driver_score = self._driver_score_from_dimensions(dimensions)
        constraint_score = self._constraint_score(session)
        net_score = max(0.0, min(1.0, driver_score - constraint_score))
        return driver_score, constraint_score, net_score

    def compute_escalation(self, session: CouncilSession) -> str:
        dimensions = self._dimension_coverages(session)
        driver_score, constraint_score, net_score = self._net_escalation_score(session)
        session.driver_score = driver_score
        session.constraint_score = constraint_score
        session.net_escalation = net_score

        if dimensions["INTENT"] >= 0.6 and dimensions["CAPABILITY"] < 0.4 and net_score >= 0.25:
            return "RHETORICAL_POSTURING"
        if net_score >= 0.70:
            return "HIGH"
        if net_score >= 0.50:
            return "ELEVATED"
        if net_score >= 0.30:
            return "GUARDED"
        return "LOW"

    def detect_contradictions(self, session: CouncilSession) -> Tuple[bool, List[str]]:
        dims = self._dimension_coverages(session)
        reasons: List[str] = []

        if dims["INTENT"] > 0.7 and dims["CAPABILITY"] < 0.3:
            reasons.append("intent_high_capability_low")
        if dims["CAPABILITY"] > 0.7 and dims["STABILITY"] < 0.3:
            reasons.append("capability_high_stability_low")

        return bool(reasons), reasons

    def _build_signal_belief_maps(
        self,
        state_context: Optional[StateContext],
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        belief_map: Dict[str, float] = {}
        temporal_map: Dict[str, float] = {}
        source_map: Dict[str, float] = {}

        default_temporal = 0.5
        default_source = 0.5
        if state_context is not None:
            meta = getattr(state_context, "meta", None)
            temporal = getattr(state_context, "temporal", None)
            if temporal is not None:
                default_temporal = max(0.0, min(1.0, float(getattr(temporal, "stability", 0.5) or 0.5)))
            elif meta is not None:
                default_temporal = max(
                    0.0, min(1.0, float(getattr(meta, "temporal_stability", getattr(meta, "time_recency", 0.5)) or 0.5))
                )

            if meta is not None:
                default_source = max(
                    0.0, min(1.0, float(getattr(meta, "source_consistency", getattr(meta, "data_confidence", 0.5)) or 0.5))
                )

        rows = list(getattr(state_context, "signal_beliefs", []) or []) if state_context is not None else []
        for row in rows:
            token = str(getattr(row, "signal", "") or "").strip().upper()
            if not token:
                continue
            belief = max(0.0, min(1.0, float(getattr(row, "belief", 0.0) or 0.0)))
            temporal_value = max(
                0.0,
                min(1.0, float(getattr(row, "temporal_stability", default_temporal) or default_temporal)),
            )
            source_value = max(
                0.0,
                min(1.0, float(getattr(row, "source_agreement", default_source) or default_source)),
            )

            if token not in belief_map or belief > belief_map[token]:
                belief_map[token] = belief
                temporal_map[token] = temporal_value
                source_map[token] = source_value

        if not belief_map and state_context is not None:
            raw_confidence = dict(getattr(state_context, "signal_confidence", {}) or {})
            for token, value in list(raw_confidence.items()):
                canonical = str(token or "").strip().upper()
                if not canonical:
                    continue
                belief_map[canonical] = max(0.0, min(1.0, float(value or 0.0)))
                temporal_map[canonical] = default_temporal
                source_map[canonical] = default_source

        # Enrich from projected signals (the structured belief set).
        # Projected signals carry composite confidence = membership Ã— reliability Ã— recency.
        # Use them to fill gaps and upgrade any existing values that are weaker.
        if state_context is not None:
            projected = getattr(state_context, "projected_signals", None)
            if isinstance(projected, dict):
                for token, obs in projected.items():
                    sig = str(token or "").strip().upper()
                    if not sig:
                        continue
                    proj_conf = max(0.0, min(1.0, float(getattr(obs, "confidence", 0.0) or 0.0)))
                    proj_rec = max(0.0, min(1.0, float(getattr(obs, "recency", default_temporal) or default_temporal)))
                    proj_rel = max(0.0, min(1.0, float(getattr(obs, "reliability", default_source) or default_source)))
                    if sig not in belief_map or proj_conf > belief_map[sig]:
                        belief_map[sig] = proj_conf
                        temporal_map[sig] = proj_rec
                        source_map[sig] = proj_rel

        return belief_map, temporal_map, source_map

    def _ensure_pressure_derived_signals(
        self,
        state_context: Optional[StateContext],
        pressure_map: Dict[str, float],
    ) -> None:
        """
        Compatibility fallback:
        If Layer-3 did not provide signal beliefs/observed signals, derive
        provisional signal confidence from strategic pressures.
        """
        if state_context is None:
            return

        if isinstance(state_context, dict):
            existing_beliefs = list(state_context.get("signal_beliefs", []) or [])
            existing_observed = set(state_context.get("observed_signals", set()) or set())
            existing_conf = dict(state_context.get("signal_confidence", {}) or {})
        else:
            existing_beliefs = list(getattr(state_context, "signal_beliefs", []) or [])
            existing_observed = set(getattr(state_context, "observed_signals", set()) or set())
            existing_conf = dict(getattr(state_context, "signal_confidence", {}) or {})
        if existing_beliefs or existing_observed or existing_conf:
            return

        p_intent = max(0.0, min(1.0, float((pressure_map or {}).get("intent_pressure", 0.0) or 0.0)))
        p_cap = max(0.0, min(1.0, float((pressure_map or {}).get("capability_pressure", 0.0) or 0.0)))
        p_stab = max(0.0, min(1.0, float((pressure_map or {}).get("stability_pressure", 0.0) or 0.0)))
        p_econ = max(0.0, min(1.0, float((pressure_map or {}).get("economic_pressure", 0.0) or 0.0)))

        derived = {
            "SIG_MIL_ESCALATION": p_cap,
            "SIG_FORCE_POSTURE": p_cap,
            "SIG_LOGISTICS_PREP": p_cap,
            "SIG_CYBER_ACTIVITY": p_cap,
            "SIG_DIP_HOSTILITY": p_intent,
            "SIG_ALLIANCE_SHIFT": p_intent,
            "SIG_NEGOTIATION_BREAKDOWN": p_intent,
            "SIG_INTERNAL_INSTABILITY": p_stab,
            "SIG_DECEPTION_ACTIVITY": p_stab,
            "SIG_ECON_PRESSURE": p_econ,
            "SIG_ECONOMIC_PRESSURE": p_econ,
            "SIG_SANCTIONS_ACTIVE": p_econ,
        }

        if isinstance(state_context, dict):
            state_context["signal_confidence"] = dict(derived)
        else:
            state_context.signal_confidence = dict(derived)
        observed = set()
        for token, value in derived.items():
            if float(value) >= self.MATCHED_BELIEF_THRESHOLD:
                observed.add(token)
        if isinstance(state_context, dict):
            state_context["observed_signals"] = observed
        else:
            state_context.observed_signals = observed

    def _observed_signals_from_beliefs(
        self,
        belief_map: Dict[str, float],
        *,
        threshold: float,
    ) -> List[str]:
        observed: List[str] = []
        for signal, value in list((belief_map or {}).items()):
            token = str(signal or "").strip()
            if not token:
                continue
            belief = max(0.0, min(1.0, float(value or 0.0)))
            if belief >= threshold:
                observed.append(token)
        return observed

    def _collect_missing_signals(self, session: CouncilSession) -> List[str]:
        """
        Derive missing signals from the collection plan (PIR-based).

        The collection plan was built from belief gaps during convene_council().
        We extract signal tokens targeted by PIRs â€” these are the signals that
        need investigation because the system BELIEVES something but LACKS evidence.

        This replaces the old three-source approach.  The single source of truth
        is now:  belief gap â†’ PIR â†’ signal.
        """
        plan: CollectionPlan = getattr(session, "collection_plan", None)
        if not plan or not plan.pirs:
            # Fallback: hypothesis-level missing signals
            candidates: List[str] = []
            seen = set()
            for hypothesis in session.hypotheses:
                for signal in list(hypothesis.missing_signals or []):
                    token = str(signal or "").strip()
                    if not token or token in seen:
                        continue
                    seen.add(token)
                    candidates.append(token)
            return self.investigation_controller.select_investigations(
                session,
                candidate_signals=candidates,
            )

        # Primary path: PIR-targeted signals
        return list(plan.signals_targeted)

    def _estimate_signal_coverage(self, session: CouncilSession) -> float:
        """Continuous coverage from projected beliefs (structured) or fallback to belief_map."""
        projected = getattr(session.state_context, 'projected_signals', None)
        strengths_map, _, _ = self._build_signal_belief_maps(session.state_context)
        support_values: List[float] = []
        seen = set()
        for hypothesis in session.hypotheses:
            for signal in list(hypothesis.predicted_signals or []):
                token = str(signal or "").strip().upper()
                if not token or token in seen:
                    continue
                seen.add(token)
                # Prefer projected confidence, fall back to belief_map
                if projected and token in projected:
                    val = float(getattr(projected[token], 'confidence', 0.0) or 0.0)
                else:
                    val = float(strengths_map.get(token, 0.0) or 0.0)
                support_values.append(max(0.0, min(1.0, val)))
        if not support_values:
            return 0.0
        # Continuous coverage in [0,1] from fuzzy support strengths.
        return sum(support_values) / len(support_values)

    def _is_predictive_query(self, query: str) -> bool:
        lower = f" {str(query or '').lower()} "
        return any(marker in lower for marker in self.PREDICTIVE_MARKERS)

    def _is_high_impact_prediction(self, session: CouncilSession, query: str) -> bool:
        if not self._is_predictive_query(query):
            return False
        if session.assessment_report and session.assessment_report.threat_level in self.HIGH_IMPACT_THREAT_LEVELS:
            return True
        return session.final_confidence >= self.RED_TEAM_CONFIDENCE_THRESHOLD

    def _should_trigger_red_team(self, session: CouncilSession) -> Tuple[bool, str]:
        """Always trigger red team when hypotheses exist so weak ones are
        eliminated **before** synthesis."""
        if session.hypotheses:
            contradictory, reasons = self.detect_contradictions(session)
            if contradictory:
                return True, ",".join(reasons)
            return True, "pre_synthesis_challenge"
        return False, "not_triggered"

    @staticmethod
    def _optional_llm_stage_degraded() -> Tuple[bool, str]:
        try:
            from engine.Layer4_Analysis.core.llm_client import get_llm_runtime_stats

            stats = get_llm_runtime_stats()
        except Exception:
            return False, ""

        rate_hits = int(stats.get("openrouter_rate_limit_hits", 0) or 0)
        empty_hits = int(stats.get("openrouter_empty_responses", 0) or 0)

        reasons: List[str] = []
        if rate_hits >= int(OPTIONAL_LLM_STAGE_MAX_RATE_LIMIT_HITS):
            reasons.append(f"rate_limit_hits={rate_hits}")
        if empty_hits >= int(OPTIONAL_LLM_STAGE_MAX_EMPTY_RESPONSES):
            reasons.append(f"empty_responses={empty_hits}")
        if not reasons:
            return False, ""
        return True, ",".join(reasons)

    def _should_investigate_groupthink(
        self,
        session: CouncilSession,
        round1_reports: List[MinisterReport],
    ) -> Tuple[bool, List[str], str]:
        if not bool(getattr(session, "groupthink_flag", False)):
            return False, [], "groupthink_not_detected"
        if bool(getattr(session, "groupthink_reinvestigated", False)):
            return False, [], "groupthink_reinvestigation_already_used"
        if int(getattr(session, "investigation_rounds", 0) or 0) >= int(getattr(session, "MAX_INVESTIGATION_ROUNDS", 3) or 3):
            return False, [], "investigation_budget_exhausted"

        avg_coverage = self._average_hypothesis_coverage(session)
        low_coverage = avg_coverage < 0.60

        gap_candidates: List[str] = []
        for report in list(round1_reports or []):
            for gap in list(getattr(report, "critical_gaps", []) or []):
                token = str(gap or "").strip()
                if token:
                    gap_candidates.append(token)

        gap_report = getattr(session, "gap_report", None)
        for gap in list(getattr(gap_report, "gaps", []) or []):
            token = str(gap or "").strip()
            if token:
                gap_candidates.append(token)

        plan = getattr(session, "collection_plan", None)
        for pir in list(getattr(plan, "pirs", []) or []):
            signal = str(getattr(pir, "signal", "") or "").strip()
            if signal:
                gap_candidates.append(signal)

        deduped_gaps: List[str] = []
        for gap in gap_candidates:
            if gap not in deduped_gaps:
                deduped_gaps.append(gap)

        if not low_coverage and not deduped_gaps:
            return False, [], "groupthink_without_context_gap"

        reason_bits: List[str] = []
        if low_coverage:
            reason_bits.append(f"low_coverage={avg_coverage:.3f}")
        if deduped_gaps:
            reason_bits.append(f"context_gaps={len(deduped_gaps)}")
        return True, deduped_gaps, ",".join(reason_bits) or "thin_context"

    def _signal_dimension(self, session: CouncilSession, signal: str) -> str:
        token = str(signal or "").strip().upper()
        if not token:
            return "UNKNOWN"
        for hypothesis in list(getattr(session, "hypotheses", []) or []):
            predicted = {str(item or "").strip().upper() for item in list(getattr(hypothesis, "predicted_signals", []) or [])}
            missing = {str(item or "").strip().upper() for item in list(getattr(hypothesis, "missing_signals", []) or [])}
            if token in predicted or token in missing:
                return str(getattr(hypothesis, "dimension", "UNKNOWN") or "UNKNOWN").upper()
        return "UNKNOWN"

    def _derive_groupthink_signal_targets(
        self,
        session: CouncilSession,
        round1_reports: List[MinisterReport],
        context_gaps: List[str],
    ) -> List[str]:
        targets: List[str] = []
        seen: Set[str] = set()

        def _add(signal: str) -> None:
            token = str(signal or "").strip().upper()
            if not token or token in seen:
                return
            if token not in SIGNAL_COLLECTION_MODALITY:
                return
            seen.add(token)
            targets.append(token)

        for hypothesis in list(getattr(session, "hypotheses", []) or []):
            for signal in list(getattr(hypothesis, "missing_signals", []) or []):
                _add(signal)

        for signal in list(getattr(session, "missing_signals", []) or []):
            _add(signal)

        plan = getattr(session, "collection_plan", None)
        for signal in list(getattr(plan, "signals_targeted", []) or []):
            _add(signal)

        for report in list(round1_reports or []):
            for gap in list(getattr(report, "critical_gaps", []) or []):
                for match in self.GROUPTHINK_CONTEXT_GAP_SIGNAL_RE.findall(str(gap or "").upper()):
                    _add(match)

        for gap in list(context_gaps or []):
            for match in self.GROUPTHINK_CONTEXT_GAP_SIGNAL_RE.findall(str(gap or "").upper()):
                _add(match)

        return targets

    def _ensure_collection_plan_for_signals(
        self,
        session: CouncilSession,
        signals: List[str],
        *,
        reason_prefix: str,
        force_critical: bool = False,
    ) -> CollectionPlan:
        existing_plan: CollectionPlan = getattr(session, "collection_plan", None) or CollectionPlan()
        existing_pirs = list(getattr(existing_plan, "pirs", []) or [])
        targeted = {str(getattr(pir, "signal", "") or "").strip().upper() for pir in existing_pirs}

        projected = getattr(session.state_context, "projected_signals", None) or {}
        if not isinstance(projected, dict):
            projected = {}
        country = str(getattr(getattr(session.state_context, "actors", None), "subject_country", "") or getattr(existing_plan, "country", "") or "")
        cycle = int(getattr(session, "investigation_cycles", 0) or getattr(existing_plan, "cycle", 0) or 0)

        supplemental_pirs: List[PIR] = []
        for signal in list(signals or []):
            token = str(signal or "").strip().upper()
            if not token or token in targeted:
                continue

            modalities = SIGNAL_COLLECTION_MODALITY.get(token) or []
            if not modalities:
                continue

            proj = projected.get(token)
            recency = float(getattr(proj, "recency", 1.0) or 1.0) if proj is not None else 1.0
            confidence = float(getattr(proj, "confidence", 0.0) or 0.0) if proj is not None else 0.0
            priority = PIRPriority.CRITICAL if force_critical or confidence < 0.20 or recency < 0.25 else PIRPriority.HIGH

            min_date = ""
            if recency < 0.25:
                min_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

            supplemental_pirs.append(
                PIR(
                    dimension=self._signal_dimension(session, token),
                    signal=token,
                    collection=modalities[0],
                    priority=priority,
                    reason=(
                        f"{reason_prefix}: repeated agreement under incomplete context. "
                        f"Need fresh measurement for {token} before final council synthesis."
                    ),
                    country=country,
                    current_confidence=confidence,
                    current_recency=recency,
                    confidence_gap=max(0.0, 1.0 - confidence),
                    min_date=min_date,
                )
            )
            targeted.add(token)

        if not supplemental_pirs:
            return existing_plan

        logger.info(
            "[GROUPTHINK] Added %d supplemental PIRs for reinvestigation: %s",
            len(supplemental_pirs),
            [pir.signal for pir in supplemental_pirs],
        )
        log_pirs(supplemental_pirs)
        return CollectionPlan(
            pirs=existing_pirs + supplemental_pirs,
            belief_gaps=list(getattr(existing_plan, "belief_gaps", []) or []),
            country=country,
            cycle=cycle,
        )

    def _should_trigger_full_verification(self, session: CouncilSession, query: str) -> Tuple[bool, str]:
        predictive = self._is_predictive_query(query)
        elevated_threat = bool(
            session.assessment_report
            and session.assessment_report.threat_level in self.HIGH_IMPACT_THREAT_LEVELS
        )
        if predictive and elevated_threat:
            return True, "predictive_query_and_elevated_threat"
        if elevated_threat:
            return True, "elevated_threat"
        if predictive:
            return True, "predictive_query"
        return False, "not_triggered"

    def _build_draft_answer(self, session: CouncilSession) -> str:
        """
        Build a narrative draft answer that CoVe can verify against evidence.

        Instead of emitting raw signal tokens, produce grounded natural-language
        sentences tied to the state dimensions and signal evidence so that
        CoVe's atomic claim decomposition finds real overlap with provenance.
        """
        lines: List[str] = []
        ctx = session.state_context
        dims = self._state_dimensions(session)

        # Level + headline
        level = str(session.king_decision or "LOW").upper()
        lines.append(f"The assessed escalation risk level is {level}.")

        # Capability narrative
        cap = dims.get("CAPABILITY", 0.0)
        mob = float(getattr(getattr(ctx, "military", None), "mobilization", 0.0) or 0.0)
        if cap >= 0.30:
            lines.append(
                f"Military capability indicators are elevated (mobilization index {mob:.2f}). "
                "Force posture and logistics signals suggest preparatory activity."
            )
        else:
            lines.append(
                f"Military capability indicators remain limited (mobilization index {mob:.2f})."
            )

        # Intent narrative
        intent = dims.get("INTENT", 0.0)
        hostility = float(getattr(getattr(ctx, "diplomatic", None), "hostility", 0.0) or 0.0)
        if intent >= 0.20:
            lines.append(
                f"Diplomatic hostility is present at {hostility:.2f}. "
                "Alliance shifts and negotiation breakdown signals indicate coercive intent."
            )
        else:
            lines.append(
                f"Diplomatic hostility remains below escalation threshold ({hostility:.2f})."
            )

        # Cost narrative
        cost = dims.get("COST", 0.0)
        eco = float(getattr(getattr(ctx, "economic", None), "economic_pressure", 0.0) or 0.0)
        if cost >= 0.30:
            lines.append(
                f"Economic pressure is significant ({eco:.2f}). "
                "Active sanctions and economic coercion are present."
            )
        else:
            lines.append(
                f"Economic pressure is present but does not correlate with force preparation ({eco:.2f})."
            )

        # Stability narrative
        stab = dims.get("STABILITY", 0.0)
        if stab >= 0.20:
            lines.append(
                "Internal instability signals are present, potentially enabling risk-taking."
            )

        # Conclusion
        lines.append(f"Therefore escalation risk is assessed as {level}.")

        # Also append minister token summary for structured traceability
        for report in session.ministers_reports:
            tokens = ", ".join(list(report.predicted_signals or [])) or "NONE"
            lines.append(f"[{report.minister_name}] predicted_signals={tokens}")

        return "\n".join(line for line in lines if line).strip()

    def _generate_fallback_estimate(self, session: CouncilSession) -> CouncilSession:
        """
        FIX-1 + FIX-4: Generate a probabilistic estimate from raw state signals
        when no hypotheses survive or when the anomaly sentinel would have
        triggered a Black Swan.

        Instead of shutting down reasoning, produce a graded low-confidence
        assessment using the numeric world model that Layer-3 already computed.
        """
        ctx = session.state_context
        mil = float(getattr(getattr(ctx, "military", None), "mobilization_level", 0.0) or 0.0)
        dip_hostility = float(getattr(getattr(ctx, "diplomatic", None), "hostility_tone", 0.0) or 0.0)
        eco = float(getattr(getattr(ctx, "economic", None), "economic_pressure", 0.0) or 0.0)
        dom_stability = float(getattr(getattr(ctx, "domestic", None), "regime_stability", 0.5) or 0.5)
        meta = getattr(ctx, "meta", None)
        data_confidence = float(getattr(meta, "data_confidence", 0.5) or 0.5)

        # Weighted risk from raw state dimensions
        risk = max(0.0, min(1.0,
            0.40 * mil +
            0.20 * dip_hostility +
            0.20 * eco +
            0.20 * (1.0 - dom_stability)
        ))

        # Determine threat tier from risk score
        if risk >= 0.70:
            threat_label = "HIGH"
        elif risk >= 0.45:
            threat_label = "ELEVATED"
        elif risk >= 0.25:
            threat_label = "GUARDED"
        else:
            threat_label = "LOW"

        # Discount confidence heavily â€” this is a fallback, not a full analysis
        fallback_confidence = max(0.05, min(0.50, risk * 0.35 * data_confidence))

        observed_signals = sorted(set(getattr(ctx, "observed_signals", []) or []))

        threat_map = {
            "HIGH": ThreatLevel.HIGH,
            "ELEVATED": ThreatLevel.ELEVATED,
            "GUARDED": ThreatLevel.GUARDED,
            "LOW": ThreatLevel.LOW,
        }
        recommendation_map = {
            "HIGH": "Fallback estimate indicates high risk from raw signals; full analysis incomplete â€” prioritize manual review.",
            "ELEVATED": "Fallback estimate indicates elevated risk; competing hypotheses could not be formed â€” increase monitoring.",
            "GUARDED": "Fallback estimate indicates guarded risk; analytical ambiguity prevents full assessment.",
            "LOW": "Fallback estimate indicates low risk; insufficient competing hypotheses for detailed analysis.",
        }

        session.king_decision = threat_label
        session.final_decision = threat_label
        session.final_confidence = fallback_confidence
        session.sensor_confidence = fallback_confidence
        session.document_confidence = 0.0
        session.strategic_status = threat_label.lower()
        session.low_confidence_assessment = True

        session.assessment_report = AssessmentReport(
            threat_level=threat_map.get(threat_label, ThreatLevel.LOW),
            confidence_score=fallback_confidence,
            summary=(
                f"FALLBACK ESTIMATE ({threat_label}): Produced from raw state signals â€” "
                f"military={mil:.2f}, hostility={dip_hostility:.2f}, "
                f"economic_pressure={eco:.2f}, stability={dom_stability:.2f}. "
                f"No competing hypotheses survived; analytical ambiguity."
            ),
            key_indicators=observed_signals,
            missing_information=["Competing hypotheses could not be formed or survived red team"],
            recommendation=recommendation_map.get(threat_label, recommendation_map["LOW"]),
        )

        logger.info(
            "[FALLBACK] Generated fallback estimate: %s (confidence=%.3f, risk=%.3f)",
            threat_label, fallback_confidence, risk,
        )
        return session

    async def _run_full_verification(
        self,
        *,
        query: str,
        draft_answer: str,
        sources: List[Dict[str, Any]],
        baseline_score: float,
        session: Optional[CouncilSession] = None,
    ) -> Dict[str, Any]:
        """
        Full verification pipeline:
        1. Baseline signal verification (from _verify_claims)
        2. Chain of Verification (CoVe) â€” atomic claim decomposition
        3. Logical/causal verification
        4. Combined score
        """
        cove_score = max(0.0, min(1.0, float(baseline_score or 0.0)))
        logic_score = 0.0
        logic_breakdown: Dict[str, Any] = {"logic_score": 0.0, "hypothesis_scores": []}
        if session is not None:
            try:
                from engine.Layer4_Analysis.decision.verifier import logical_verification, logical_verification_details
                logic_score = float(logical_verification(session))
                logic_breakdown = logical_verification_details(session)
            except Exception:
                logic_score = max(0.0, min(1.0, float(getattr(session, "logic_score", 0.0) or 0.0)))
                logic_breakdown = {"logic_score": logic_score, "hypothesis_scores": []}

        # â”€â”€ CoVe Integration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Wire the ChainOfVerification module for atomic claim verification.
        # CoVe decomposes the draft answer into atomic claims and checks each
        # against the evidence log (signal provenance, not raw documents).
        cove_details: Dict[str, Any] = {}
        try:
            from engine.Layer4_Analysis.deliberation.cove import ChainOfVerification
            cove_engine = ChainOfVerification(retriever=None, llm_client=None, engram_store=None)

            # Build evidence docs from signal provenance metadata (not raw content)
            evidence_docs = []
            if session is not None:
                for entry in list(getattr(session, "evidence_log", None) or []):
                    if isinstance(entry, dict):
                        evidence_docs.append(entry)
                    elif isinstance(entry, str):
                        evidence_docs.append({"signal": entry, "source": "evidence_log"})

            cove_result = await cove_engine.run_cove_loop(
                query=query,
                initial_draft=draft_answer,
                sources=evidence_docs,
            )
            # CoVeResult dataclass with faithfulness_score attribute
            if hasattr(cove_result, "faithfulness_score"):
                cove_score = max(0.0, min(1.0, float(cove_result.faithfulness_score or cove_score)))
                cove_details = {
                    "faithfulness": cove_result.faithfulness_score,
                    "valid": cove_result.valid,
                    "state": str(getattr(cove_result, "state", "")),
                    "revisions_made": getattr(cove_result, "revisions_made", 0),
                    "gaslighting_detected": getattr(cove_result, "gaslighting_detected", False),
                    "rrf_threshold_met": getattr(cove_result, "rrf_threshold_met", False),
                    "atomic_claims_count": len(getattr(cove_result, "atomic_claims", [])),
                    "refusal_reason": getattr(cove_result, "refusal_reason", None),
                }
            elif isinstance(cove_result, dict):
                cove_faithfulness = float(cove_result.get("faithfulness_score", cove_score) or cove_score)
                cove_score = max(0.0, min(1.0, cove_faithfulness))
                cove_details = cove_result
        except Exception as cove_exc:
            cove_details = {"error": str(cove_exc)}
            # Fallback: keep baseline_score as cove_score
        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        details: Dict[str, Any] = {
            "mode": "deterministic+causal+cove",
            "baseline_score": float(baseline_score),
            "sensor_score": cove_score,
            "rag_score": 0.0,
            "ragas_score": 0.0,
            "cove_score": cove_score,
            "cove_details": cove_details,
            "logic_score": logic_score,
            "logic_breakdown": logic_breakdown,
            "errors": [],
        }

        # Layer-4 firewall: no document scoring in Layer-4.
        # Use state-grounded verification signal only.
        state_score = cove_score
        details["rag_score"] = state_score
        details["ragas_score"] = state_score
        evidence_score = min(cove_score, state_score)
        details["evidence_score"] = evidence_score
        evidence_weight_score = 0.0
        try:
            from Core.analysis.evidence_weighting import compute_evidence_score

            observed_signals = []
            if session is not None:
                observed_signals = list(
                    getattr(getattr(session, "state_context", None), "observed_signals", []) or []
                )
            evidence_weight_score = float(compute_evidence_score(observed_signals))
        except Exception:
            evidence_weight_score = 0.0

        try:
            from engine.Layer4_Analysis.decision.verifier import combine_verification_scores
            base_verification_score = float(combine_verification_scores(cove_score, state_score, logic_score))
        except Exception:
            base_verification_score = (0.6 * evidence_score) + (0.4 * logic_score)

        # Blend grounding strength with weighted evidence severity.
        details["base_verification_score"] = float(max(0.0, min(1.0, base_verification_score)))
        details["evidence_weight_score"] = float(max(0.0, min(1.0, evidence_weight_score)))
        details["verification_score"] = float(
            max(
                0.0,
                min(
                    1.0,
                    (0.7 * float(details["base_verification_score"]))
                    + (0.3 * float(details["evidence_weight_score"])),
                ),
            )
        )
        details["sensor_score"] = float(details["verification_score"])

        # Store CoVe score on session for downstream consumers
        if session is not None:
            session.cove_score = cove_score

        return details

    def _estimate_rag_score(self, sources: List[Dict[str, Any]]) -> float:
        if not sources:
            return 0.0
        scores: List[float] = []
        for source in list(sources or []):
            try:
                score = float((source or {}).get("score", 0.0) or 0.0)
                scores.append(max(0.0, min(1.0, score)))
            except Exception:
                continue
        if scores:
            return sum(scores) / len(scores)
        return 0.0

    def _should_trigger_black_swan_interrupt(self, session: CouncilSession) -> Tuple[bool, Dict[str, Any]]:
        observed_signals = set(session.evidence_log or [])
        coverage = self._estimate_signal_coverage(session)
        triggered = self.sentinel.check_for_anomaly(
            session=session,
            observed_signals=observed_signals,
            coverage=coverage,
        )
        return triggered, {
            "coverage": round(float(coverage), 6),
            "observed_signals": len(observed_signals),
        }

    def convene_council(self, session: CouncilSession) -> CouncilSession:
        """
        STAGE 1: DELIBERATION
        
        Ministers propose hypotheses based on StateContext.
        All ministers read ONLY from StateContext, not external sources.
        Returns Hypothesis objects with predicted vs matched signals.
        """
        logger.info("[DELIBERATION] Convening council...")
        session.status = SessionStatus.DELIBERATING

        # Store state_context reference so _evaluate_evidence can read projected_signals.
        self._current_state_context = session.state_context

        # Ensure latent strategic pressures are available for all ministers.
        if not getattr(session, "pressures", {}):
            try:
                session.pressures = map_state_to_pressures(session.state_context).to_dict()
            except Exception:
                session.pressures = {}
        if hasattr(session.state_context, "pressures"):
            state_pressures = dict(getattr(session.state_context, "pressures", {}) or {})
            if not state_pressures and session.pressures:
                session.state_context.pressures = dict(session.pressures)
            elif state_pressures:
                session.pressures = dict(state_pressures)
        self._ensure_pressure_derived_signals(session.state_context, dict(session.pressures or {}))
        
        # Authoritative observation path: Layer-4 consumes only Layer-3 observed signals.
        belief_map, _, _ = self._build_signal_belief_maps(session.state_context)
        observed_signals = list(getattr(session.state_context, "observed_signals", []) or [])
        session.evidence_log.extend(observed_signals)
        
        # Convene ministers - each proposes a hypothesis
        for minister in self.ministers:
            # Call deliberate once - produce_hypothesis wraps the output
            report = minister.deliberate(session.state_context)
            if report:
                matched_signals, missing_signals, coverage = self._evaluate_evidence(
                    report,
                    belief_map,
                )
                session.add_report(report)
                
                # Create hypothesis from report (do not call LLM again)
                hypothesis = Hypothesis(
                    minister=report.minister_name,
                    predicted_signals=report.predicted_signals,
                    matched_signals=matched_signals,
                    missing_signals=missing_signals,
                    coverage=coverage,
                    dimension=self._minister_dimension(report.minister_name),
                )
                session.add_hypothesis(hypothesis)

        # â”€â”€ CURIOSITY ENGINE + COLLECTION PLANNING â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # The system does NOT collect everything missing.
        # It computes Value of Information (VOI) for each signal and
        # investigates ONLY what would most change its conclusion.
        #
        # VOI(signal) = hypothesis_weight Ã— uncertainty Ã— impact
        #
        # This replaces passive gap detection with active hypothesis testing.
        projected = getattr(session.state_context, "projected_signals", None) or {}
        actors = getattr(session.state_context, "actors", None)
        country = str(getattr(actors, "subject_country", "") or "")
        signal_confidence = dict(getattr(session.state_context, "signal_confidence", {}) or {})
        observed_signals = set(getattr(session.state_context, "observed_signals", set()) or set())

        try:
            from engine.Layer4_Analysis.curiosity_controller import CuriosityController, curiosity_to_pirs

            curiosity = CuriosityController(max_targets=3)
            curiosity_plan = curiosity.evaluate(
                hypotheses=session.hypotheses,
                signal_confidence=signal_confidence,
                observed_signals=observed_signals,
            )

            # Store curiosity plan on session for diagnostic access
            session.curiosity_plan = curiosity_plan

            if curiosity_plan.targets:
                # VOI-driven collection plan â€” focused on high-value signals
                collection_plan = curiosity_to_pirs(
                    curiosity_plan=curiosity_plan,
                    hypotheses=session.hypotheses,
                    projected_signals=projected,
                    country=country,
                    cycle=int(getattr(session, "investigation_cycles", 0) or 0),
                )
            else:
                # Curiosity found nothing above threshold â€” fall back to gap detection
                logger.info("[CURIOSITY] No high-VOI targets â€” falling back to gap-based collection")
                collection_plan = build_collection_plan(
                    hypotheses=session.hypotheses,
                    projected_signals=projected,
                    country=country,
                    cycle=int(getattr(session, "investigation_cycles", 0) or 0),
                )
        except Exception as curiosity_err:
            logger.warning("[CURIOSITY] Engine failed, falling back: %s", curiosity_err)
            session.curiosity_plan = None
            collection_plan = build_collection_plan(
                hypotheses=session.hypotheses,
                projected_signals=projected,
                country=country,
                cycle=int(getattr(session, "investigation_cycles", 0) or 0),
            )

        # Store collection plan on session â€” investigation phase consumes this
        session.collection_plan = collection_plan

        # â”€â”€ GAP REASONING ENGINE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Structural gap and contradiction detection.
        # "Escalation without logistics â€” suspicious. Investigate."
        try:
            from engine.Layer4_Analysis.gap_engine import analyse_gaps

            # Build signal confidence map from projected signals + belief map
            gap_signal_conf: Dict[str, float] = {}
            for sig_name, bel in belief_map.items():
                if isinstance(bel, (int, float)):
                    gap_signal_conf[sig_name] = float(bel)
                elif isinstance(bel, dict):
                    gap_signal_conf[sig_name] = float(bel.get("confidence", 0.0))
            # Also include raw signal_confidence from state context
            raw_sc = dict(signal_confidence or {})
            for k, v in raw_sc.items():
                if k not in gap_signal_conf:
                    gap_signal_conf[k] = float(v)

            gap_report = analyse_gaps(gap_signal_conf)
            session.gap_report = gap_report

            # Feed structural gaps into curiosity targets for investigation
            if gap_report.gaps and hasattr(session, "collection_plan"):
                for gap_desc in gap_report.gaps:
                    # Extract the missing signal name from gap description
                    parts = gap_desc.split(" without ")
                    if len(parts) == 2:
                        missing_sig = parts[1].split(" (")[0].strip()
                        if missing_sig not in session.missing_signals:
                            session.missing_signals.append(missing_sig)
        except Exception as gap_err:
            logger.warning("[GAP-ENGINE] Failed: %s", gap_err)
            session.gap_report = None

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        #  TWO-ROUND COGNITIVE DELIBERATION
        #
        #  Round 1: Blind independent reasoning (no minister sees others)
        #  Groupthink check: semantic similarity across responses
        #  Synthesis: deterministic aggregation of Round 1
        #  Round 2: Informed revision (each minister sees synthesis)
        #  Final: weighted council_adjustment for confidence layer
        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

        try:
            from engine.Layer4_Analysis.council_session import FullContext

            # â”€â”€ Build FullContext snapshot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _traj_dict = {}
            try:
                _traj_obj = getattr(session, "trajectory_result", None)
                if _traj_obj and hasattr(_traj_obj, "to_dict"):
                    _traj_dict = _traj_obj.to_dict()
            except Exception:
                pass

            _state_probs = {}
            try:
                _cs = getattr(session, "conflict_state", None) or {}
                if isinstance(_cs, dict):
                    _state_probs = dict(_cs.get("posterior", {}) or {})
            except Exception:
                pass

            _gap_obj = getattr(session, "gap_report", None)
            _gaps_list = list(getattr(_gap_obj, "gaps", []) or []) if _gap_obj else []
            _contra_list = list(getattr(_gap_obj, "contradictions", []) or []) if _gap_obj else []

            _sre_score = 0.0
            try:
                _sre_score = float(getattr(session, "escalation_score", 0.0) or 0.0)
            except Exception:
                pass

            _trend_briefing = dict(getattr(session.state_context, "trend_briefing", {}) or {})

            # Build signal confidence from belief_map
            _sig_conf_map: Dict[str, float] = {}
            for _sn, _bv in belief_map.items():
                if isinstance(_bv, (int, float)):
                    _sig_conf_map[_sn] = float(_bv)
                elif isinstance(_bv, dict):
                    _sig_conf_map[_sn] = float(_bv.get("confidence", 0.0))
            for _sk, _sv in (signal_confidence or {}).items():
                if _sk not in _sig_conf_map:
                    _sig_conf_map[_sk] = float(_sv)

            full_context = FullContext(
                pressures=dict(session.pressures or {}),
                projected_signals={},  # projected is complex â€” ministers see signal_confidence
                trajectory=_traj_dict,
                state_probabilities=_state_probs,
                gaps=_gaps_list,
                contradictions=_contra_list,
                escalation_score=_sre_score,
                trend_patterns=_trend_briefing,
                signal_confidence=_sig_conf_map,
            )
            session.full_context = full_context

            # â”€â”€ ROUND 1: Blind independent reasoning â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            logger.info("[COUNCIL] Round 1: blind independent reasoning (%d ministers)", len(self.ministers))
            round1_reports: list = []
            for minister in self.ministers:
                # Find this minister's classification report
                cls_report = None
                for r in session.ministers_reports:
                    if r.minister_name == minister.name:
                        cls_report = r
                        break
                if cls_report is None:
                    continue
                enriched = minister.reason(full_context, cls_report, synthesis_summary="", session=session)
                round1_reports.append(enriched)
            session.round1_reports = round1_reports

            # â”€â”€ GROUPTHINK CHECK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            try:
                from engine.Layer4_Analysis.groupthink_detector import detect_groupthink
                gt_flag, gt_penalty, gt_sim = detect_groupthink(round1_reports)
                session.groupthink_flag = gt_flag
                session.groupthink_penalty = gt_penalty
                if gt_flag:
                    logger.info(
                        "[COUNCIL] GROUPTHINK detected: similarity=%.3f penalty=%.2f",
                        gt_sim, gt_penalty,
                    )
            except Exception as _gt_err:
                logger.warning("[COUNCIL] Groupthink detection failed: %s", _gt_err)
                session.groupthink_flag = False
                session.groupthink_penalty = 0.0

            should_reinvestigate, context_gaps, groupthink_reason = self._should_investigate_groupthink(
                session,
                round1_reports,
            )
            session.groupthink_investigation_needed = should_reinvestigate
            session.groupthink_context_gaps = list(context_gaps)
            session.groupthink_reason = groupthink_reason
            if should_reinvestigate:
                signal_targets = self._derive_groupthink_signal_targets(session, round1_reports, context_gaps)
                for gap in list(context_gaps or []):
                    token = str(gap or "").strip()
                    if token and token not in session.investigation_needs:
                        session.investigation_needs.append(token)
                for signal in signal_targets:
                    if signal not in session.missing_signals:
                        session.missing_signals.append(signal)
                    if signal not in session.investigation_needs:
                        session.investigation_needs.append(signal)
                session.collection_plan = self._ensure_collection_plan_for_signals(
                    session,
                    signal_targets,
                    reason_prefix=f"groupthink_reinvestigation({groupthink_reason})",
                    force_critical=True,
                )
                session.round2_reports = []
                session.council_adjustment = 0.0
                session.synthesis_summary = (
                    "Council paused after Round 1 because semantic convergence appeared "
                    "to come from thin context. Additional collection requested before rerun."
                )
                logger.info(
                    "[COUNCIL] Groupthink appears context-thin; requesting investigation before rerun "
                    "(reason=%s, signals=%s, gaps=%s)",
                    groupthink_reason,
                    signal_targets,
                    context_gaps,
                )
                return session

            # â”€â”€ SYNTHESIS (deterministic) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            aggregation_r1 = self._aggregate_minister_outputs(round1_reports)
            _votes = dict(aggregation_r1["votes"])
            _all_drivers: list = []
            _all_gaps: list = []
            _all_counterargs: list = []
            _dissent_notes: list = []

            for rpt in round1_reports:
                _all_drivers.extend(getattr(rpt, "primary_drivers", []) or [])
                _all_gaps.extend(getattr(rpt, "critical_gaps", []) or [])
                _all_counterargs.extend(getattr(rpt, "counterarguments", []) or [])

            # Build synthesis summary text for Round 2
            majority_vote = str(aggregation_r1.get("weighted_majority", "maintain") or "maintain")
            n_total = sum(_votes.values())
            _synth_parts = [
                f"ROUND 1 RESULTS ({n_total} ministers):",
                f"  Votes: increase={_votes['increase']}  decrease={_votes['decrease']}  maintain={_votes['maintain']}",
                f"  Weighted recommendation: {majority_vote.upper()}",
                f"  Weighted risk score: {float(aggregation_r1.get('weighted_risk', 0.0)):+.3f}",
            ]
            if _all_drivers:
                _synth_parts.append(f"  Key drivers: {'; '.join(_all_drivers[:6])}")
            if _all_gaps:
                _synth_parts.append(f"  Flagged gaps: {'; '.join(_all_gaps[:4])}")
            if _all_counterargs:
                _synth_parts.append(f"  Counterarguments raised: {'; '.join(_all_counterargs[:4])}")

            # Note dissenting ministers
            for rpt in round1_reports:
                adj = getattr(rpt, "risk_level_adjustment", "maintain") or "maintain"
                if adj != majority_vote:
                    _dissent_notes.append(
                        f"{rpt.minister_name} dissents ({adj})"
                    )
            if _dissent_notes:
                _synth_parts.append(f"  Dissent: {'; '.join(_dissent_notes)}")

            synthesis = "\n".join(_synth_parts)
            session.synthesis_summary = synthesis
            logger.info("[COUNCIL] Synthesis: majority=%s votes=%s", majority_vote, _votes)

            # â”€â”€ ROUND 2: Informed revision â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            logger.info("[COUNCIL] Round 2: informed revision (%d ministers)", len(self.ministers))
            round2_reports: list = []
            for minister in self.ministers:
                cls_report = None
                for r in session.ministers_reports:
                    if r.minister_name == minister.name:
                        cls_report = r
                        break
                if cls_report is None:
                    continue
                # Create fresh copy for round 2 to avoid mutating round 1
                from copy import deepcopy
                r2_report = deepcopy(cls_report)
                enriched2 = minister.reason(full_context, r2_report, synthesis_summary=synthesis, session=session)
                round2_reports.append(enriched2)
            session.round2_reports = round2_reports

            # â”€â”€ FINAL AGGREGATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Use round-2 results for council_adjustment
            aggregation_r2 = self._aggregate_minister_outputs(round2_reports)
            r2_votes = dict(aggregation_r2["votes"])
            weighted_mod = float(aggregation_r2.get("weighted_modifier", 0.0) or 0.0)
            weighted_risk = float(aggregation_r2.get("weighted_risk", 0.0) or 0.0)
            r2_majority = str(aggregation_r2.get("weighted_majority", "maintain") or "maintain")

            council_adj = max(
                -0.10,
                min(
                    0.10,
                    (weighted_mod * 0.7) + (weighted_risk * 0.03),
                ),
            )
            session.council_adjustment = council_adj
            if bool(aggregation_r2.get("disagreement", False)):
                marker = "minister_risk_disagreement"
                if marker not in session.identified_conflicts:
                    session.identified_conflicts.append(marker)
            logger.info(
                "[COUNCIL] Final: R2 votes=%s weighted_majority=%s weighted_mod=%+.3f weighted_risk=%+.3f council_adj=%+.4f disagreement=%s",
                r2_votes, r2_majority, weighted_mod, weighted_risk, council_adj,
                bool(aggregation_r2.get("disagreement", False)),
            )

        except Exception as _council_err:
            logger.warning("[COUNCIL] Two-round deliberation failed: %s", _council_err)
            import traceback
            traceback.print_exc()
            session.round1_reports = []
            session.round2_reports = []
            session.council_adjustment = 0.0

        return session
    
    def _detect_conflicts(self, session: CouncilSession) -> CouncilSession:
        """
        STAGE 2: DETECT CONFLICTS
        
        Check if causal dimensions contradict each other.
        """
        if not session.hypotheses:
            return session

        contradictory, reasons = self.detect_contradictions(session)
        if contradictory:
            session.identified_conflicts.extend(
                reason for reason in reasons if reason not in session.identified_conflicts
            )
        
        return session
    
    def _run_red_team(self, session: CouncilSession) -> CouncilSession:
        """
        STAGE 3: RED TEAM CHALLENGE
        
        Uses the full RedTeamAgent for state-grounded challenges.
        The agent checks 6 dimensions: military, diplomatic, economic,
        domestic, confidence, and evidence thinness.
        Falls back to simple logic if RedTeamAgent fails.
        """
        if not session.hypotheses:
            return session
        
        weak_hypotheses = [
            h for h in session.hypotheses if float(getattr(h, "coverage", 0.0) or 0.0) < 0.50
        ]
        contradictions = list(session.identified_conflicts or [])

        # â”€â”€ FIX-2: Bayesian hypothesis weighting (replaces hard elimination) â”€â”€
        # No hypothesis is destroyed â€” only down-weighted by coverage.
        # This preserves competing interpretations of reality.
        for h in session.hypotheses:
            cov = max(0.0, min(1.0, float(getattr(h, "coverage", 0.0) or 0.0)))
            h.weight = max(0.01, float(getattr(h, "weight", 1.0) or 1.0) * (0.5 + cov))
            logger.debug(
                "Hypothesis (%s) weight=%.3f after Bayesian update (coverage=%.3f)",
                h.minister, h.weight, cov,
            )
        if session.hypotheses:
            logger.info(
                "FIX-2: Bayesian weighting applied to %d hypotheses (no elimination)",
                len(session.hypotheses),
            )

        degraded, degraded_reason = self._optional_llm_stage_degraded()
        if degraded:
            logger.warning(
                "Skipping optional LLM red-team due to degraded runtime: %s",
                degraded_reason,
            )
            session.red_team_report = {
                "active": False,
                "agent": "skipped_llm_degraded",
                "skip_reason": degraded_reason,
                "is_robust": True,
                "challenged_hypotheses": max(len(weak_hypotheses), len(contradictions)),
                "contradictions": contradictions,
                "counter_evidence": [],
            }
        else:
            # BUG-06 FIX: Use the full RedTeamAgent instead of inline stub
            try:
                from engine.Layer4_Analysis.deliberation.red_team import RedTeamAgent
                
                # Build state dict from session's StateContext
                state_dict = session.state_context.to_dict() if hasattr(session.state_context, 'to_dict') else {}
                agent = RedTeamAgent(state_context=state_dict)
                round2_reports = list(getattr(session, "round2_reports", []) or [])
                if not round2_reports:
                    round2_reports = list(getattr(session, "round1_reports", []) or [])
                risk_votes = {
                    str(getattr(report, "risk_level_adjustment", "maintain") or "maintain").strip().lower()
                    for report in round2_reports
                    if getattr(report, "risk_level_adjustment", None) is not None
                }
                conflict_markers = list(getattr(session, "identified_conflicts", []) or [])
                agent.disagreement_detected = bool(len(risk_votes) > 1 or "minister_risk_disagreement" in conflict_markers)
                
                # Build a draft answer from the strongest hypothesis for the agent to challenge
                strongest = max(session.hypotheses, key=lambda h: float(getattr(h, "coverage", 0.0) or 0.0))
                strongest_tokens = ", ".join(list(strongest.predicted_signals or [])) or "NONE"
                draft = f"Hypothesis ({strongest.minister}): predicted_signals={strongest_tokens}"

                # â”€â”€ Feed minister reasoning context into red team â”€â”€â”€â”€â”€â”€â”€â”€â”€
                _r2_reports = round2_reports
                if not _r2_reports:
                    _r2_reports = getattr(session, "round1_reports", []) or []
                if _r2_reports:
                    _minister_ctx_parts = []
                    for _mr in _r2_reports:
                        _drivers = "; ".join(getattr(_mr, "primary_drivers", []) or [])[:200]
                        _c_gaps = "; ".join(getattr(_mr, "critical_gaps", []) or [])[:200]
                        _cargs = "; ".join(getattr(_mr, "counterarguments", []) or [])[:200]
                        _adj = getattr(_mr, "risk_level_adjustment", "maintain")
                        _minister_ctx_parts.append(
                            f"{_mr.minister_name} ({_adj}): drivers=[{_drivers}] gaps=[{_c_gaps}] counter=[{_cargs}]"
                        )
                    agent.minister_context = "\n".join(_minister_ctx_parts)
                    draft += f"\n\nMINISTER COUNCIL REASONING:\n" + agent.minister_context
                
                # execute_attack is async Ã¢â‚¬â€ run it synchronously
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're already in an async context
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            is_robust, critique, evidence = pool.submit(
                                asyncio.run, agent.execute_attack(draft)
                            ).result(timeout=30)
                    else:
                        is_robust, critique, evidence = loop.run_until_complete(agent.execute_attack(draft))
                except RuntimeError:
                    is_robust, critique, evidence = asyncio.run(agent.execute_attack(draft))
                
                session.red_team_report = {
                    "active": True,
                    "agent": "RedTeamAgent",
                    "is_robust": is_robust,
                    "challenged_hypotheses": max(len(weak_hypotheses), len(contradictions)),
                    "contradictions": contradictions,
                    "critique": critique,
                    "counter_evidence": evidence,
                }
                
            except Exception as e:
                # Fallback to simple logic if RedTeamAgent unavailable
                logger.warning(f"RedTeamAgent failed, using simple fallback: {e}")
                session.red_team_report = {
                    "active": True,
                    "agent": "fallback",
                    "challenged_hypotheses": max(len(weak_hypotheses), len(contradictions)),
                    "contradictions": contradictions,
                    "counter_evidence": [],
                }

        # â”€â”€ FIX-3: Mandatory adversary â€” always produce challenge content â”€â”€
        # If red team produced no counter-evidence (LLM returned empty/malformed),
        # generate deterministic attack queries so CHALLENGE phase always has substance.
        counter_evidence = list((session.red_team_report or {}).get("counter_evidence", []) or [])
        if not counter_evidence and session.hypotheses:
            strongest = max(session.hypotheses, key=lambda h: float(getattr(h, "weight", 1.0) or 1.0))
            primary_signals = list(strongest.predicted_signals or [])[:2]
            default_attacks = []
            for sig in primary_signals:
                default_attacks.extend([
                    f"Evidence against {sig} in this context",
                    f"Historical false alarms for {sig}",
                    f"Alternative explanations for {sig}",
                ])
            if not default_attacks:
                default_attacks = [
                    f"Counter-evidence for {strongest.minister} assessment",
                    f"Historical false alarms in {strongest.dimension} dimension",
                    f"Alternative explanations for observed signal pattern",
                ]
            session.red_team_report["counter_evidence"] = default_attacks
            session.red_team_report["agent"] = "mandatory_adversary"
            logger.info(
                "FIX-3: Generated %d mandatory adversary challenges (LLM red-team was empty)",
                len(default_attacks),
            )

        # â”€â”€ Red-team confidence penalty (severity-weighted) â”€â”€â”€â”€â”€â”€â”€â”€
        # If the red team found the assessment NOT robust, penalise
        # confidence proportionally so downstream synthesis reflects it.
        # Weights vary by finding severity:
        #   Contradiction with measured state  â†’ 0.05 each
        #   Missing dimension / blind spot     â†’ 0.04 each
        #   Evidence thinness / sparse sources â†’ 0.03 each
        #   Generic challenged hypothesis      â†’ 0.03 each (fallback)
        rt_report = session.red_team_report or {}
        rt_penalty = 0.0
        if rt_report.get("active") and not rt_report.get("is_robust", True):
            n_contradictions = len(rt_report.get("contradictions", []) or [])
            critique_text = str(rt_report.get("critique", "") or "").upper()
            # Count severity categories from critique
            n_missing_dim = critique_text.count("MISSING FACTOR") + critique_text.count("BLIND DIMENSION")
            n_thin = critique_text.count("EVIDENCE THINNESS") + critique_text.count("SPARSE")
            n_unchallenged = critique_text.count("UNCHALLENGED ASSUMPTION")
            n_challenged = int(rt_report.get("challenged_hypotheses", 0) or 0)
            # Subtract accounted-for challenges so we don't double-count
            n_generic = max(0, n_challenged - n_missing_dim - n_thin - n_unchallenged)
            rt_penalty = round(min(0.15,
                0.05 * n_contradictions +
                0.04 * n_missing_dim +
                0.04 * n_unchallenged +
                0.03 * n_thin +
                0.03 * n_generic
            ), 4)
        session.red_team_confidence_penalty = rt_penalty
        if rt_penalty > 0:
            logger.info("Red-team penalty: -%.4f (contradictions=%d, missing_dim=%d, thin=%d, unchallenged=%d, generic=%d)",
                        rt_penalty, n_contradictions, n_missing_dim, n_thin, n_unchallenged, n_generic)

        return session
    
    # NOTE: _investigate_missing_signals was removed (BUG-05).
    # The real investigation path is _run_investigation_phase() which calls
    # investigate_and_update() from state_provider to rebuild StateContext.
    
    def _synthesize_decision(
        self,
        session: CouncilSession,
        *,
        verification_score: Optional[float] = None,
    ) -> CouncilSession:
        """
        STAGE 5: THREAT SYNTHESIZER
        
        Fuse state evidence with minister-proposed signals into a final threat level.
        Delegated to pipeline.synthesis_engine.run_synthesis().
        """
        return _pipeline_synthesis(session, self, verification_score=verification_score)
    
    def _verify_claims(self, session: CouncilSession) -> CouncilSession:
        """
        STAGE 6: CoVe VERIFICATION
        
        Decompose claims into atomic assertions and verify against evidence.
        Calculates verification_score based on independent state signal extraction.

        FIX (BUG-09): Previously checked matched_signals against evidence_log
        where they were already inserted Ã¢â‚¬â€ circular verification (always ~1.0).
        Now verifies ALL predicted_signals against independently extracted state
        signals to get a real grounding score.
        """
        if not session.hypotheses:
            session.verification_score = 0.0
            session.logic_score = 0.0
            return session
        
        # Verify ALL predicted signals deterministically against StateContext.
        all_predicted: List[str] = []
        for h in session.hypotheses:
            all_predicted.extend(h.predicted_signals)
        
        if not all_predicted:
            session.verification_score = 0.0
            session.logic_score = 0.0
            return session

        try:
            from engine.Layer4_Analysis.decision.verifier import full_verifier, logical_verification

            session.verification_score = float(full_verifier.verify(all_predicted, session.state_context))
            session.logic_score = float(logical_verification(session))
        except Exception:
            session.verification_score = 0.0
            session.logic_score = 0.0
        
        return session

    def _has_valid_state_context(self, state_context: Any) -> bool:
        if not state_context:
            return False
        required_sections = ("actors", "military", "diplomatic", "economic", "domestic")
        for section in required_sections:
            value = getattr(state_context, section, None)
            if value is None and isinstance(state_context, dict):
                value = state_context.get(section)
            if value is None:
                return False
        return True
    
    def _check_refusal_threshold(self, session: CouncilSession) -> bool:
        """
        STAGE 7: REFUSAL ENGINE
        
        Returns True for:
        - invalid/corrupted state
        - anomaly interrupt
        - logically weak explanations (causal grounding below threshold)
        """
        missing_critical_sensors = not session.hypotheses and not session.ministers_reports
        state_valid = self._has_valid_state_context(session.state_context) and not missing_critical_sensors
        anomaly_detected = bool(session.black_swan)
        logic_score = max(0.0, min(1.0, float(getattr(session, "logic_score", 0.0) or 0.0)))
        has_hypotheses = bool(session.hypotheses)
        logic_weak = has_hypotheses and logic_score < self.LOGIC_REFUSAL_THRESHOLD

        try:
            from engine.Layer4_Analysis.safety.safeguards import should_refuse as _should_refuse
            base_refusal = bool(_should_refuse(state_valid=state_valid, anomaly_detected=anomaly_detected))
            return bool(base_refusal or logic_weak)
        except Exception:
            # Fallback path keeps behavior deterministic even if safeguards import fails.
            return (not state_valid) or anomaly_detected or logic_weak
    
    def _check_hitl_threshold(self, session: CouncilSession, query: str) -> bool:
        """
        STAGE 8: HITL (Human-in-the-Loop)
        
        Returns True if human review is needed.
        Triggers on high-impact prediction + low certainty.
        """
        if not session.assessment_report:
            return False
        
        high_impact_prediction = self._is_high_impact_prediction(session, query)
        low_certainty = session.final_confidence < self.RED_TEAM_CONFIDENCE_THRESHOLD
        return high_impact_prediction and low_certainty

    def _run_safety_review(
        self,
        session: CouncilSession,
        *,
        query: str,
        draft_answer: str,
        doc_sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Mandatory final safety gate after verification.
        """
        result: Dict[str, Any] = {
            "should_refuse": False,
            "needs_human_review": False,
            "response_payload": None,
            "grounding": {},
        }

        all_sources = self._collect_output_sources(session)
        decision_label = str(
            getattr(session, "king_decision", getattr(session, "final_decision", "LOW")) or "LOW"
        ).strip().upper()
        grounded = False
        atom_count = 0
        required_atoms = 1
        claim_supported = False
        epistemic_confidence = 0.0
        evidence_weight_score = 0.0
        try:
            from engine.Layer4_Analysis.verifier.grounding_verifier import verify_grounding
            from engine.Layer4_Analysis.verifier.claim_support import check_claim_support
            from engine.Layer4_Analysis.verifier.confidence_model import compute_epistemic_confidence
            from Core.analysis.evidence_weighting import compute_evidence_score

            grounded, atom_count, atoms = verify_grounding(sources=all_sources, min_atoms=3)
            session.evidence_atoms = list(atoms or [])
            epistemic_confidence = float(compute_epistemic_confidence(session) or 0.0)
            evidence_weight_score = float(
                compute_evidence_score(list(getattr(session.state_context, "observed_signals", []) or []))
            )
            epistemic_confidence = float(
                max(
                    0.0,
                    min(
                        1.0,
                        (0.7 * float(epistemic_confidence)) + (0.3 * float(evidence_weight_score)),
                    ),
                )
            )

            # Temporal override gate:
            # Upgrade to HIGH only when pre-war sequence is detected and evidence reliability is strong.
            if (
                bool(getattr(session, "prewar_detected", False))
                and float(epistemic_confidence) > 0.60
                and str(decision_label).upper() not in {"HIGH", "CRITICAL"}
            ):
                decision_label = "HIGH"
                session.king_decision = "HIGH"
                session.final_decision = "HIGH"
                session.strategic_status = "high"

            claim_supported, required_atoms = check_claim_support(decision_label, atom_count)
        except Exception:
            grounded = False
            atom_count = 0
            claim_supported = False
            required_atoms = 1
            session.evidence_atoms = []
            epistemic_confidence = 0.0
            evidence_weight_score = 0.0

        session.evidence_atom_count = int(atom_count)
        session.grounding_passed = bool(grounded)
        session.required_atoms_for_decision = int(required_atoms)
        session.claim_support_passed = bool(claim_supported)
        session.epistemic_confidence = max(0.0, min(1.0, float(epistemic_confidence)))
        session.low_confidence_assessment = False
        result["grounding"] = {
            "decision": decision_label,
            "evidence_atom_count": int(atom_count),
            "signal_type_count": int(atom_count),
            "min_atoms": 3,
            "grounded": bool(grounded),
            "claim_support_passed": bool(claim_supported),
            "required_atoms_for_decision": int(required_atoms),
            "epistemic_confidence": float(session.epistemic_confidence),
            "evidence_weight_score": float(max(0.0, min(1.0, evidence_weight_score))),
        }

        should_refuse = self._check_refusal_threshold(session)
        if should_refuse:
            result["should_refuse"] = True
            fallback_message = "The system cannot determine whether conflict is likely. Additional evidence required."
            refusal_reason = "invalid_state_context"
            logic_score = max(0.0, min(1.0, float(getattr(session, "logic_score", 0.0) or 0.0)))
            has_hypotheses = bool(session.hypotheses)
            logic_weak = has_hypotheses and logic_score < self.LOGIC_REFUSAL_THRESHOLD

            if logic_weak:
                fallback_message = "The explanation does not uniquely explain observed signals. Additional discriminating evidence required."
                refusal_reason = "logical_grounding_failure"
            if session.black_swan:
                fallback_message = "Black Swan anomaly detected. Predictive output has been disabled until forced investigation completes."
                refusal_reason = "black_swan_interrupt"
            elif not self._has_valid_state_context(session.state_context):
                fallback_message = "State context is missing or corrupted. Additional state reconstruction required."
                refusal_reason = "invalid_state_context"

            response_payload = {
                "type": "refusal",
                "message": fallback_message,
                "reason": refusal_reason,
                "logic_score": logic_score,
                "evidence_atom_count": int(atom_count),
                "required_atoms": int(required_atoms),
                "grounded": bool(grounded),
                "epistemic_confidence": float(session.epistemic_confidence),
            }

            result["response_payload"] = response_payload
            return result

        # Graded epistemic behavior:
        # <0.25 -> refusal, 0.25..0.5 -> low-confidence assessment, >=0.5 -> normal
        if session.epistemic_confidence < 0.25:
            result["should_refuse"] = True
            result["response_payload"] = {
                "type": "refusal",
                "message": (
                    "The system cannot responsibly conclude due to insufficient independent evidence types. "
                    f"Only {int(atom_count)} independent signal types available."
                ),
                "reason": "insufficient_evidence",
                "evidence_atom_count": int(atom_count),
                "required_atoms": 3,
                "decision": decision_label,
                "epistemic_confidence": float(session.epistemic_confidence),
            }
            return result

        if not claim_supported:
            if session.epistemic_confidence < 0.50:
                session.low_confidence_assessment = True
                result["response_payload"] = {
                    "type": "caveat",
                    "message": (
                        f"Low confidence assessment: decision '{decision_label}' has limited support "
                        f"({int(atom_count)}/{int(required_atoms)} independent signal types)."
                    ),
                    "reason": "claim_support_limited",
                    "evidence_atom_count": int(atom_count),
                    "required_atoms": int(required_atoms),
                    "decision": decision_label,
                    "epistemic_confidence": float(session.epistemic_confidence),
                }
            else:
                result["should_refuse"] = True
                result["response_payload"] = {
                    "type": "refusal",
                    "message": (
                        f"Decision '{decision_label}' is not sufficiently supported by independent signal types "
                        f"({int(atom_count)}/{int(required_atoms)})."
                    ),
                    "reason": "claim_support_failure",
                    "evidence_atom_count": int(atom_count),
                    "required_atoms": int(required_atoms),
                    "decision": decision_label,
                    "epistemic_confidence": float(session.epistemic_confidence),
                }
                return result

        if 0.25 <= session.epistemic_confidence < 0.50:
            session.low_confidence_assessment = True

        result["needs_human_review"] = self._check_hitl_threshold(session, query=query)
        return result
    
    def _evaluate_evidence(
        self,
        report: MinisterReport,
        belief_map: Dict[str, float],
    ) -> Tuple[List[str], List[str], float]:
        """
        Compare predicted signals against observed belief support and return
        matched signals, missing signals, and **continuous** coverage.

        Coverage is no longer binary (matched / total).  It is the mean
        belief strength of all predicted signals â€” a fuzzy overlap score
        that lets the Bayesian weighting differentiate hypotheses.
        """
        matched: List[str] = []
        missing: List[str] = []
        strengths: List[float] = []
        predicted = [str(signal or "").strip().upper() for signal in list(report.predicted_signals or [])]
        predicted = [token for token in predicted if token]

        # Try projected signals first (structured beliefs)
        projected = None
        try:
            ctx = getattr(self, '_current_state_context', None)
            if ctx is not None:
                projected = getattr(ctx, 'projected_signals', None)
        except Exception:
            pass

        belief_map = dict(belief_map or {})
        for token in predicted:
            # Use projected ObservedSignal confidence if available
            proj_conf = 0.0
            if projected and token in projected:
                proj_conf = float(getattr(projected[token], 'confidence', 0.0) or 0.0)
            belief_conf = max(0.0, min(1.0, float(belief_map.get(token, 0.0) or 0.0)))
            strength = max(proj_conf, belief_conf)
            strengths.append(strength)

            if strength >= self.MATCHED_BELIEF_THRESHOLD:
                matched.append(token)
            else:
                missing.append(token)

        # Continuous coverage: mean belief strength across predicted signals.
        # This replaces the old binary count (matched/total).
        if strengths:
            coverage = sum(strengths) / len(strengths)
        else:
            coverage = 0.0

        # Retain report-level scalar for legacy displays.
        report.confidence = max(0.0, min(1.0, float(coverage)))
        return matched, missing, float(coverage)

    def _signal_provenance(self, session: CouncilSession) -> Dict[str, List[Dict[str, Any]]]:
        payload = dict(getattr(session.state_context, "signal_evidence", {}) or {})
        if not payload:
            evidence = getattr(session.state_context, "evidence", None)
            payload = getattr(evidence, "signal_provenance", {}) if evidence else {}
        if not isinstance(payload, dict):
            return {}
        out: Dict[str, List[Dict[str, Any]]] = {}
        for signal, rows in list(payload.items()):
            token = str(signal or "").strip().upper()
            if not token:
                continue
            valid_rows: List[Dict[str, Any]] = []
            for row in list(rows or []):
                if isinstance(row, dict):
                    valid_rows.append(row)
                else:
                    to_dict = getattr(row, "to_dict", None)
                    if callable(to_dict):
                        try:
                            payload_row = to_dict()
                            if isinstance(payload_row, dict):
                                valid_rows.append(payload_row)
                        except Exception:
                            continue
                out[token] = valid_rows
        return out

    def _serialize_hypotheses(self, session: CouncilSession) -> List[Dict[str, Any]]:
        """Lightweight export of hypotheses for logging/reporting."""
        return _pipeline_serialize_hyps(session)

    def _format_ieee_reference(self, evidence: Dict[str, Any], index: int) -> str:
        source_name = str(evidence.get("source_name") or evidence.get("source") or "Unknown Source")
        excerpt = str(evidence.get("excerpt") or evidence.get("content") or "").strip().replace("\n", " ")
        publication_date = str(evidence.get("publication_date") or "n.d.")
        url = str(evidence.get("url") or "")
        if excerpt:
            return f"[{index}] {source_name}, \"{excerpt}\", {publication_date}. Available: {url or 'N/A'}"
        return f"[{index}] {source_name}, {publication_date}. Available: {url or 'N/A'}"

    def _build_reference_bundle(
        self,
        session: CouncilSession,
        signals: List[str],
    ) -> Tuple[Dict[str, List[int]], List[Dict[str, Any]]]:
        provenance = self._signal_provenance(session)
        index_map: Dict[Tuple[str, str, str, str], int] = {}
        references: List[Dict[str, Any]] = []
        signal_refs: Dict[str, List[int]] = {}

        for signal in list(signals or []):
            token = str(signal or "").strip().upper()
            if not token:
                continue
            rows = list(provenance.get(token, []) or [])
            if not rows:
                continue
            mapped_indexes: List[int] = []
            for row in rows:
                key = (
                    str(row.get("source_id", "")),
                    str(row.get("url", "")),
                    str(row.get("publication_date", "")),
                    str(row.get("excerpt", row.get("content", ""))),
                )
                if key not in index_map:
                    index_map[key] = len(references) + 1
                    references.append(row)
                mapped_indexes.append(index_map[key])
            if mapped_indexes:
                signal_refs[token] = sorted(set(mapped_indexes))

        return signal_refs, references

    def _collect_output_sources(self, session: CouncilSession) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        seen = set()

        provenance = self._signal_provenance(session)
        for signal, rows in list(provenance.items()):
            for row in list(rows or []):
                key = (
                    str(row.get("source_id", "")),
                    str(row.get("url", "")),
                    str(row.get("publication_date", "")),
                    str(row.get("excerpt", row.get("content", ""))),
                )
                if key in seen:
                    continue
                seen.add(key)
                try:
                    confidence = float(row.get("confidence", 0.0) or 0.0)
                except Exception:
                    confidence = 0.0
                sources.append(
                    {
                        "id": row.get("source_id", ""),
                        "source": row.get("source_name", row.get("source", "unknown")),
                        "url": row.get("url", ""),
                        "publication_date": row.get("publication_date", ""),
                        "content": row.get("excerpt", row.get("content", "")),
                        "score": confidence,
                        "signal": signal,
                    }
                )

        # â”€â”€ Supplement from projected signals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # GDELT + MoltBot observations may not appear in document
        # provenance but they ARE independent evidence sources that the
        # grounding verifier should count.
        try:
            ctx = getattr(session, "state_context", None)
            projected = getattr(ctx, "projected_signals", None) or {}
            if isinstance(projected, dict):
                projected = projected.values()
            for obs in projected:
                sig_name = str(getattr(obs, "name", "") or "").strip().upper()
                conf = float(getattr(obs, "confidence", 0.0) or 0.0)
                if not sig_name or conf <= 0.0:
                    continue
                src_list = list(getattr(obs, "sources", []) or [])
                src_label = ",".join(src_list) if src_list else "derived"
                key = (sig_name, src_label, "projected", "")
                if key in seen:
                    continue
                seen.add(key)
                sources.append({
                    "id": f"projected:{sig_name}",
                    "source": src_label,
                    "source_type": src_label,
                    "url": "",
                    "publication_date": "",
                    "content": f"Projected signal {sig_name} (conf={conf:.3f})",
                    "score": conf,
                    "signal": sig_name,
                })
        except Exception:
            pass

        return sources

    def generate_result(self, session: CouncilSession) -> 'AnalysisResult':
        """
        Converts the finalized session into a standardized AnalysisResult.
        """
        from engine.Layer3_StateModel.schemas.analysis_result import AnalysisResult, EvidenceReference
        status = str(getattr(session, "strategic_status", "stable") or "stable")
        sensor_confidence = float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0)
        document_confidence = float(getattr(session, "document_confidence", 0.0) or 0.0)
        epistemic_confidence = float(getattr(session, "epistemic_confidence", 0.0) or 0.0)
        all_signals = sorted(
            {
                str(token).strip()
                for report in list(session.ministers_reports or [])
                for token in list(report.predicted_signals or [])
                if str(token).strip()
            }
        )
        weak_signals = sorted(
            {
                str(token).strip()
                for hypothesis in list(session.hypotheses or [])
                for token in list(getattr(hypothesis, "missing_signals", []) or [])
                if str(token).strip()
            }
        )
        dimensions = self._dimension_coverages(session)
        
        # Determine summary based on decision
        if session.king_decision == "NO_CONSENSUS":
            summary = "The Council could not reach a consensus due to conflicting indicators."
        else:
            summary = session.king_decision
        if bool(getattr(session, "low_confidence_assessment", False)):
            summary = f"LOW CONFIDENCE ASSESSMENT: {summary}"
            
        key_signals = []
        if session.assessment_report and getattr(session.assessment_report, "key_indicators", None):
            key_signals = [str(token).strip() for token in list(session.assessment_report.key_indicators or []) if str(token).strip()]
        if not key_signals:
            key_signals = list(all_signals)

        signal_refs, references = self._build_reference_bundle(session, key_signals)

        # Compile evidence references with provenance.
        evidence_list = []
        for idx, ref in enumerate(references, start=1):
            source_id = str(ref.get("source_id") or f"prov_{idx}")
            source_name = str(ref.get("source_name") or ref.get("source") or "Unknown Source")
            publication_date = str(ref.get("publication_date") or "n.d.")
            confidence = max(0.0, min(1.0, float(ref.get("confidence", 0.0) or 0.0)))
            evidence_list.append(
                EvidenceReference(
                    source_id=source_id,
                    source_type="provenance",
                    description=f"{source_name} ({publication_date})",
                    confidence=confidence,
                )
            )

        # Create detailed reasoning from minister reports
        details = []
        try:
            from Layer5.explainer import explain
            explanation = explain(
                status=status,
                signals=all_signals,
                state=session.state_context,
            ).strip()
        except Exception:
            explanation = ""
        if explanation:
            details.append(explanation)
        details.append(
            f"[STATUS] {status.upper()} | sensor_confidence={sensor_confidence:.2f} | document_confidence={document_confidence:.2f}"
        )
        details.append(
            "[EPISTEMIC] "
            f"confidence={epistemic_confidence:.2f} | atoms={int(getattr(session, 'evidence_atom_count', 0) or 0)} | "
            f"grounded={bool(getattr(session, 'grounding_passed', False))}"
        )
        details.append(
            "[EARLY_WARNING] "
            f"emi={float(getattr(session, 'early_warning_index', 0.0) or 0.0):.3f} | "
            f"esi={float(getattr(session, 'escalation_sync', 0.0) or 0.0):.3f} | "
            f"prewar={bool(getattr(session, 'prewar_detected', False))} | "
            f"warning={str(getattr(session, 'warning', '') or 'NONE')}"
        )
        if bool(getattr(session, "low_confidence_assessment", False)):
            details.append(
                "[CONFIDENCE_NOTE] Indicators suggest elevated risk, but evidence reliability is limited; treat as low-confidence assessment."
            )
        details.append(
            "[DIMENSIONS] "
            f"CAPABILITY={dimensions['CAPABILITY']:.2f}, "
            f"INTENT={dimensions['INTENT']:.2f}, "
            f"STABILITY={dimensions['STABILITY']:.2f}, "
            f"COST={dimensions['COST']:.2f}"
        )
        if weak_signals:
            details.append(f"[WEAK_SIGNALS] {', '.join(weak_signals)}")
        for report in session.ministers_reports:
            tokens = ", ".join(list(report.predicted_signals or [])) or "NONE"
            minister_dimension = self._minister_dimension(report.minister_name)
            details.append(
                f"[{report.minister_name}] predicted_signals={tokens} "
                f"(Coverage: {float(report.confidence):.2f}, Dimension: {minister_dimension})"
            )
        if signal_refs:
            details.append("[SIGNAL_PROVENANCE]")
            for signal in key_signals:
                token = str(signal or "").strip().upper()
                refs_for_signal = signal_refs.get(token, [])
                if not refs_for_signal:
                    continue
                refs_text = ", ".join(f"[{ref_id}]" for ref_id in refs_for_signal)
                details.append(f"{token}: {refs_text}")
        if references:
            details.append("[REFERENCES]")
            for idx, ref in enumerate(references, start=1):
                details.append(self._format_ieee_reference(ref, idx))
        
        return AnalysisResult(
            agent_name="CouncilCoordinator",
            summary_text=summary,
            detailed_reasoning="\n".join(details),
            confidence_score=session.final_confidence,
            evidence_used=evidence_list,
            metadata={
                "status": session.status.name,
                "strategic_status": status,
                "sensor_confidence": sensor_confidence,
                "document_confidence": document_confidence,
                "conflicts": session.identified_conflicts,
                "needs": session.investigation_needs,
                "pressures": dict(getattr(session, "pressures", {}) or {}),
                "weak_signals": weak_signals,
                "signal_citations": signal_refs,
                "citation_count": len(references),
                "assessment_report": asdict(session.assessment_report) if session.assessment_report else None,
                "verification_score": session.verification_score,
                "logic_score": float(getattr(session, "logic_score", 0.0) or 0.0),
                "evidence_atom_count": int(getattr(session, "evidence_atom_count", 0) or 0),
                "grounding_passed": bool(getattr(session, "grounding_passed", False)),
                "claim_support_passed": bool(getattr(session, "claim_support_passed", False)),
                "required_atoms_for_decision": int(getattr(session, "required_atoms_for_decision", 0) or 0),
                "epistemic_confidence": epistemic_confidence,
                "analytic_confidence": float(session.final_confidence),
                "low_confidence_assessment": bool(getattr(session, "low_confidence_assessment", False)),
                "early_warning_index": float(getattr(session, "early_warning_index", 0.0) or 0.0),
                "escalation_sync": float(getattr(session, "escalation_sync", 0.0) or 0.0),
                "prewar_detected": bool(getattr(session, "prewar_detected", False)),
                "warning": str(getattr(session, "warning", "") or ""),
                "temporal_trend": dict(getattr(session, "temporal_trend", {}) or {}),
                "groupthink_flag": bool(getattr(session, "groupthink_flag", False)),
                "groupthink_reinvestigated": bool(getattr(session, "groupthink_reinvestigated", False)),
                "groupthink_reason": str(getattr(session, "groupthink_reason", "") or ""),
                "groupthink_context_gaps": list(getattr(session, "groupthink_context_gaps", []) or []),
            }
        )

    async def process_query(self, query: str, use_mcts: bool=False, use_causal: bool=False, use_red_team: bool=False, use_multi_perspective: bool=False, state_context: StateContext=None, max_investigation_loops: int=1, **kwargs) -> Dict[str, Any]:
        """
        Deterministic Layer-4 lifecycle:
        INITIAL_DELIBERATION -> CHALLENGE -> INVESTIGATION -> VERIFICATION -> SAFETY_REVIEW -> FINALIZED
        """
        import uuid

        session_id = f"council_{uuid.uuid4().hex[:12]}"
        max_investigation_loops = max(1, int(max_investigation_loops or 1))

        try:
            if not state_context:
                raise ValueError("state_context is required for Council coordinator")
            if not query or not isinstance(query, str):
                raise ValueError("query must be a non-empty string")

            try:
                pressure_map = map_state_to_pressures(state_context).to_dict()
            except Exception:
                pressure_map = dict(getattr(state_context, "pressures", {}) or {})
            if hasattr(state_context, "pressures"):
                state_context.pressures = dict(pressure_map or {})
            self._ensure_pressure_derived_signals(state_context, pressure_map)

            session = CouncilSession(
                session_id=session_id,
                question=query,
                state_context=state_context,
                pressures=dict(pressure_map or {}),
            )
            self._set_phase(session, ReasoningPhase.INITIAL_DELIBERATION)

            escalation_trace: Dict[str, Any] = {
                "level_1_council": True,
                "level_2_red_team": False,
                "level_3_crag": False,
                "level_4_full_verification": False,
                "level_5_refusal": False,
                "level_6_hitl": False,
                "black_swan_interrupt": False,
            }
            verification_details: Dict[str, Any] = {
                "mode": "quick",
                "verification_score": 0.0,
            }
            investigation_runs = 0
            needs_human_review = False
            anomaly_meta: Dict[str, Any] = {}
            safety_response_payload: Dict[str, Any] = {}

            while session.phase not in {ReasoningPhase.FINALIZED, ReasoningPhase.FAILED}:
                session.loop_count += 1
                if session.loop_count > self.MAX_PHASE_LOOPS:
                    session.status = SessionStatus.FAILED
                    self._set_phase(session, ReasoningPhase.FAILED)
                    return {
                        "answer": "Analysis failed: Phase loop limit reached.",
                        "sources": [],
                        "references": [],
                        "confidence": 0.0,
                        "council_session": {
                            "session_id": session.session_id,
                            "status": session.status.name,
                            "error": "phase_loop_limit_reached",
                            "phase_history": list(session.phase_history),
                            "escalation_trace": escalation_trace,
                        },
                    }

                if session.phase == ReasoningPhase.INITIAL_DELIBERATION:
                    session = self.convene_council(session)
                    if bool(getattr(session, "groupthink_investigation_needed", False)):
                        escalation_trace["level_3_crag"] = True
                        escalation_trace["groupthink_reinvestigation"] = True
                        escalation_trace["groupthink_reinvestigation_reason"] = str(
                            getattr(session, "groupthink_reason", "") or "thin_context"
                        )
                        escalation_trace["groupthink_context_gaps"] = list(
                            getattr(session, "groupthink_context_gaps", []) or []
                        )
                        session.groupthink_reinvestigated = True
                        session.groupthink_investigation_needed = False
                        session.investigation_closed = False
                        self._set_phase(session, ReasoningPhase.INVESTIGATION)
                        continue
                    session = self._detect_conflicts(session)

                    anomaly_interrupt, anomaly_meta = self._should_trigger_black_swan_interrupt(session)
                    if anomaly_interrupt:
                        # FIX-1: Only set black_swan for genuine anomalies (sentinel
                        # now requires hypotheses + high contradictions + very low coverage).
                        escalation_trace["black_swan_interrupt"] = True
                        session.black_swan = True
                        session.allow_prediction = False
                        session.king_decision = ThreatLevel.ANOMALY.value
                        self._set_phase(session, ReasoningPhase.INVESTIGATION)
                        continue

                    # FIX-1: If no hypotheses AND anomaly sentinel did NOT trigger,
                    # this is analytical ambiguity â€” route to VERIFICATION with fallback.
                    if not session.hypotheses:
                        logger.info(
                            "[FIX-1] No hypotheses and no anomaly â€” routing to "
                            "VERIFICATION with fallback estimate"
                        )
                        session = self._generate_fallback_estimate(session)
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                        continue

                    should_run_red_team, red_team_reason = self._should_trigger_red_team(session)
                    if use_red_team and should_run_red_team:
                        escalation_trace["level_2_red_team"] = True
                        escalation_trace["level_2_reason"] = red_team_reason
                        self._set_phase(session, ReasoningPhase.CHALLENGE)
                        continue

                    # Even if red-team was disabled, still route through CHALLENGE
                    # so hypothesis elimination occurs before synthesis.
                    if session.hypotheses:
                        self._set_phase(session, ReasoningPhase.CHALLENGE)
                        continue

                    session.missing_signals = self._collect_missing_signals(session)
                    if knowledge_is_sufficient(session):
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                    elif session.missing_signals:
                        escalation_trace["level_3_crag"] = True
                        self._set_phase(session, ReasoningPhase.INVESTIGATION)
                    else:
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                    continue

                if session.phase == ReasoningPhase.CHALLENGE:
                    session = self._run_red_team(session)

                    # â”€â”€ Debate Orchestrator Integration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    # If red team found the hypothesis NOT robust, or there are
                    # unresolved conflicts, run multi-perspective MADAM-RAG debate
                    # to adjudicate competing positions.
                    red_report = getattr(session, "red_team_report", None) or {}
                    has_conflicts = bool(session.identified_conflicts)
                    not_robust = red_report.get("active") and not red_report.get("is_robust", True)
                    if has_conflicts or not_robust:
                        degraded, degraded_reason = self._optional_llm_stage_degraded()
                        if degraded:
                            logger.warning(
                                "Skipping optional debate orchestrator due to degraded runtime: %s",
                                degraded_reason,
                            )
                            session.debate_result = {
                                "skipped": True,
                                "reason": degraded_reason,
                            }
                        else:
                            try:
                                from engine.Layer4_Analysis.deliberation.debate_orchestrator import MADAMRAGOrchestrator
                                debate_orch = MADAMRAGOrchestrator(retriever=None, llm_client=None)
                                # Build evidence docs from signal provenance (no raw content)
                                debate_sources = []
                                for entry in list(getattr(session, "evidence_log", None) or []):
                                    if isinstance(entry, dict):
                                        debate_sources.append(entry)
                                    elif isinstance(entry, str):
                                        debate_sources.append({"signal": entry, "source": "evidence_log"})
                                debate_result = await debate_orch.orchestrate_debate(
                                    query=query,
                                    sources=debate_sources,
                                )
                                session.debate_result = {
                                    "outcome": str(getattr(debate_result, "outcome", "unknown")),
                                    "confidence": float(getattr(debate_result, "confidence", 0.0)),
                                    "conflicts_surfaced": getattr(debate_result, "conflicts_surfaced", []),
                                    "consensus_points": getattr(debate_result, "consensus_points", []),
                                    "synthesis": getattr(debate_result, "final_synthesis", ""),
                                    "advisory": getattr(debate_result, "user_advisory", ""),
                                }
                            except Exception as debate_exc:
                                logger.warning(f"Debate orchestrator failed: {debate_exc}")
                            session.debate_result = {"error": str(debate_exc)}
                    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

                    session.missing_signals = self._collect_missing_signals(session)
                    if knowledge_is_sufficient(session):
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                    elif session.missing_signals:
                        escalation_trace["level_3_crag"] = True
                        self._set_phase(session, ReasoningPhase.INVESTIGATION)
                    else:
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                    continue

                if session.phase == ReasoningPhase.INVESTIGATION:
                    if session.investigation_closed:
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                        continue

                    if session.investigation_cycles >= int(getattr(session, "MAX_INVESTIGATION_CYCLES", 3) or 3):
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                        continue

                    if int(getattr(session, "investigation_rounds", 0) or 0) >= int(
                        getattr(session, "MAX_INVESTIGATION_ROUNDS", 3) or 3
                    ):
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                        continue

                    if investigation_runs >= max_investigation_loops:
                        session.investigation_closed = True
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                        continue

                    session, investigation_meta = await self._run_investigation_phase(session, query=query)
                    investigation_runs += 1
                    escalation_trace["level_3_crag"] = True
                    escalation_trace["investigation_meta"] = investigation_meta
                    if session.investigation_closed:
                        self._set_phase(session, ReasoningPhase.VERIFICATION)
                    else:
                        self._set_phase(session, ReasoningPhase.INITIAL_DELIBERATION)
                    continue

                if session.phase == ReasoningPhase.VERIFICATION:
                    session = self._verify_claims(session)
                    verification_details = {
                        "mode": "quick",
                        "verification_score": float(session.verification_score),
                    }
                    doc_sources: List[Dict[str, Any]] = []

                    draft_answer = self._build_draft_answer(session)
                    verification_details = await self._run_full_verification(
                        query=query,
                        draft_answer=draft_answer,
                        sources=doc_sources,
                        baseline_score=session.verification_score,
                        session=session,
                    )
                    session.verification_score = float(
                        verification_details.get("verification_score", session.verification_score) or 0.0
                    )
                    session.logic_score = float(
                        verification_details.get("logic_score", getattr(session, "logic_score", 0.0)) or 0.0
                    )
                    session = self._synthesize_decision(
                        session,
                        verification_score=session.verification_score,
                    )
                    escalation_trace["level_4_full_verification"] = True
                    self._set_phase(session, ReasoningPhase.SAFETY_REVIEW)
                    continue

                if session.phase == ReasoningPhase.SAFETY_REVIEW:
                    doc_sources: List[Dict[str, Any]] = []
                    draft_answer = self._build_draft_answer(session)

                    safety_result = self._run_safety_review(
                        session,
                        query=query,
                        draft_answer=draft_answer,
                        doc_sources=doc_sources,
                    )
                    needs_human_review = bool(safety_result.get("needs_human_review", False))
                    safety_response_payload = dict(safety_result.get("response_payload") or {})

                    if bool(safety_result.get("should_refuse", False)):
                        escalation_trace["level_5_refusal"] = True
                        session.status = SessionStatus.CONCLUDED
                        session.king_decision = "INSUFFICIENT_EVIDENCE"
                        self._set_phase(session, ReasoningPhase.FINALIZED)
                        message = safety_response_payload.get(
                            "message",
                            "The system cannot determine whether conflict is likely. Additional evidence required.",
                        )
                        return {
                            "answer": message,
                            "sources": [],
                            "references": [],
                            "confidence": 0.0,
                            "analytic_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
                            "epistemic_confidence": float(getattr(session, "epistemic_confidence", 0.0) or 0.0),
                            "risk_level": str(getattr(session, "king_decision", "UNKNOWN") or "UNKNOWN"),
                            "early_warning_index": float(getattr(session, "early_warning_index", 0.0) or 0.0),
                            "escalation_sync": float(getattr(session, "escalation_sync", 0.0) or 0.0),
                            "prewar_detected": bool(getattr(session, "prewar_detected", False)),
                            "warning": str(getattr(session, "warning", "") or ""),
                            "status": str(getattr(session, "strategic_status", "stable") or "stable"),
                            "sensor_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
                            "document_confidence": float(getattr(session, "document_confidence", 0.0) or 0.0),
                            "council_session": {
                                "session_id": session.session_id,
                                "status": session.status.name,
                                "refused": True,
                                "reason": safety_response_payload.get("reason", "safety_refusal"),
                                "strategic_status": str(getattr(session, "strategic_status", "stable") or "stable"),
                                "sensor_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
                                "document_confidence": float(getattr(session, "document_confidence", 0.0) or 0.0),
                                "verification_score": session.verification_score,
                                "logic_score": float(getattr(session, "logic_score", 0.0) or 0.0),
                                "evidence_atom_count": int(getattr(session, "evidence_atom_count", 0) or 0),
                                "grounding_passed": bool(getattr(session, "grounding_passed", False)),
                                "claim_support_passed": bool(getattr(session, "claim_support_passed", False)),
                                "required_atoms_for_decision": int(getattr(session, "required_atoms_for_decision", 0) or 0),
                                "epistemic_confidence": float(getattr(session, "epistemic_confidence", 0.0) or 0.0),
                                "analytic_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
                                "risk_level": str(getattr(session, "king_decision", "UNKNOWN") or "UNKNOWN"),
                                "early_warning_index": float(getattr(session, "early_warning_index", 0.0) or 0.0),
                                "escalation_sync": float(getattr(session, "escalation_sync", 0.0) or 0.0),
                                "prewar_detected": bool(getattr(session, "prewar_detected", False)),
                                "warning": str(getattr(session, "warning", "") or ""),
                                "temporal_trend": dict(getattr(session, "temporal_trend", {}) or {}),
                                "low_confidence_assessment": bool(getattr(session, "low_confidence_assessment", False)),
                                "verification_details": verification_details,
                                "hypotheses": self._serialize_hypotheses(session),
                                "prediction_disabled": bool(session.black_swan),
                                "pressures": dict(getattr(session, "pressures", {}) or {}),
                                "missing_signals": list(session.missing_signals),
                                "investigation_needs": list(session.investigation_needs),
                                "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
                                "max_investigation_rounds": int(getattr(session, "MAX_INVESTIGATION_ROUNDS", 3) or 3),
                                "investigation_cycles": int(getattr(session, "investigation_cycles", 0) or 0),
                                "max_investigation_cycles": int(getattr(session, "MAX_INVESTIGATION_CYCLES", 3) or 3),
                                "investigation_closed": bool(getattr(session, "investigation_closed", False)),
                                "phase_history": list(session.phase_history),
                                "anomaly_meta": anomaly_meta,
                                "escalation_trace": escalation_trace,
                            },
                        }

                    if needs_human_review:
                        escalation_trace["level_6_hitl"] = True

                        # â”€â”€ HITL Circuit-Breaker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                        # If threat is HIGH/CRITICAL AND verification is weak,
                        # halt and return an interim assessment requiring human
                        # review instead of finalizing at dangerous confidence.
                        threat_label = str(
                            getattr(session, "king_decision", "") or ""
                        ).strip().upper()
                        v_score = float(getattr(session, "verification_score", 1.0) or 1.0)
                        high_threat = threat_label in ("HIGH", "CRITICAL", "SEVERE", "EXTREME")
                        weak_verification = v_score < 0.5

                        if high_threat and weak_verification:
                            try:
                                from engine.Layer4_Analysis.investigation.hitl import HITLManager, InterventionType
                                hitl_mgr = HITLManager()
                                await hitl_mgr.request_intervention(
                                    query=query,
                                    proposed_response=draft_answer,
                                    confidence=float(session.final_confidence),
                                    intervention_type=InterventionType.LOW_CONFIDENCE,
                                    reason=f"Threat={threat_label}, verification={v_score:.2f}",
                                    sources=list(self._collect_output_sources(session)),
                                    urgent=True,
                                )
                            except Exception as hitl_exc:
                                logger.warning(f"HITLManager.request_intervention failed: {hitl_exc}")

                            session.status = SessionStatus.CONCLUDED
                            self._set_phase(session, ReasoningPhase.FINALIZED)
                            return {
                                "answer": (
                                    f"[INTERIM â€” HUMAN REVIEW REQUIRED] "
                                    f"Threat assessment: {threat_label}. "
                                    f"Verification score ({v_score:.2f}) is below threshold. "
                                    f"This assessment requires human analyst review before dissemination."
                                ),
                                "sources": list(self._collect_output_sources(session)),
                                "references": [],
                                "confidence": float(session.final_confidence),
                                "analytic_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
                                "epistemic_confidence": float(getattr(session, "epistemic_confidence", 0.0) or 0.0),
                                "risk_level": threat_label,
                                "needs_human_review": True,
                                "hitl_circuit_breaker": True,
                                "verification_score": v_score,
                                "council_session": {
                                    "session_id": session.session_id,
                                    "status": "HUMAN_REVIEW",
                                    "phase_history": list(session.phase_history),
                                    "escalation_trace": escalation_trace,
                                    "verification_details": verification_details,
                                    "hypotheses": self._serialize_hypotheses(session),
                                },
                            }
                        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

                    session.status = SessionStatus.CONCLUDED
                    self._set_phase(session, ReasoningPhase.FINALIZED)
                    continue

                session.status = SessionStatus.FAILED
                self._set_phase(session, ReasoningPhase.FAILED)
                return {
                    "answer": "Analysis failed due to invalid phase transition.",
                    "sources": [],
                    "references": [],
                    "confidence": 0.0,
                    "council_session": {
                        "session_id": session.session_id,
                        "status": session.status.name,
                        "error": f"unknown_phase:{session.phase.value}",
                        "phase_history": list(session.phase_history),
                    },
                }

            session.status = SessionStatus.CONCLUDED
            analysis_result = self.generate_result(session)
            final_sources: List[Any] = self._collect_output_sources(session)
            try:
                from engine.Layer4_Analysis.report_generator import build_references
                final_references: List[Any] = build_references(session.state_context)
            except Exception:
                final_references = []

            # â”€â”€ Layer-5 Assessment Gate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # The council analyzed.  The gate authorizes or withholds.
            try:
                gate_state = gate_build_state(session)
                gate_verdict: GateVerdict = gate_evaluate(gate_state)
            except Exception as gate_err:
                logger.error("[GATE] Assessment gate failed: %s â€” defaulting to WITHHELD", gate_err)
                gate_verdict = GateVerdict(approved=False, withheld=True, decision="WITHHELD",
                    reasons=[f"Gate evaluation error: {gate_err}"])

            # ── WITHHELD → Directed Collection feedback loop ──────────
            # Delegated to pipeline.withheld_recollection
            session, gate_verdict, analysis_result = _pipeline_recollection(
                session, self, gate_verdict, gate_build_state, gate_evaluate,
            )

            if gate_verdict.withheld:
                # ── Build WITHHELD output — delegated to pipeline.output_builder
                return _pipeline_withheld_output(
                    session, gate_verdict, final_sources, final_references, question=query,
                )

            # ── Gate APPROVED — continue with normal output ──────────
            # Derive country_code for legal RAG
            _country = ""
            try:
                _country = str(getattr(getattr(session.state_context, "actors", None), "subject_country", "") or "")
            except Exception:
                pass

            # ── POST-GATE RAG: Legal evidence retrieval ──────────────
            # Delegated to pipeline.legal_rag_runner
            _post_gate_rag, _post_gate_doc_conf, _legal_constraint_analysis, _legal_evidence_items, _inferred_behaviors = _pipeline_legal_rag(
                session, query, _country,
            )

            # ── Build APPROVED output — delegated to pipeline.output_builder
            return _pipeline_approved_output(
                session, analysis_result, gate_verdict,
                final_sources, final_references,
                escalation_trace,
                verification_details,
                needs_human_review,
                _country,
                question=query,
            )


        except ValueError as e:
            print(f"[ERROR] Input validation failed: {e}")
            return {
                "answer": f"Analysis failed: Invalid input - {str(e)}",
                "sources": [],
                "references": [],
                "confidence": 0.0,
                "council_session": {
                    "session_id": session_id,
                    "status": SessionStatus.FAILED.name,
                    "error": str(e),
                },
            }
        except Exception as e:
            print(f"[CRITICAL ERROR] Unexpected exception in process_query: {e}")
            import traceback
            traceback.print_exc()
            return {
                "answer": "Analysis failed due to unexpected system error. Please try again.",
                "sources": [],
                "references": [],
                "confidence": 0.0,
                "council_session": {
                    "session_id": session_id,
                    "status": SessionStatus.FAILED.name,
                    "error": f"Unexpected exception: {type(e).__name__}: {str(e)}",
                },
            }

