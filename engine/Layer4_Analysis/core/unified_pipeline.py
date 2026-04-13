"""
Unified Pipeline — epistemic gate architecture.

Every query passes through exactly this sequence:

    1. Scope check        → OUT_OF_SCOPE
    2. Ops-health probe   → warnings (never blocks, except missing LLM)
    3. State construction  → build Layer-3 StateContext
    4. Epistemic readiness → INSUFFICIENT_EVIDENCE  (light pre-gate)
    5. Council reasoning   → Coordinator state-machine
    6. Outcome mapping     → ASSESSMENT | INSUFFICIENT_EVIDENCE | OUT_OF_SCOPE

Design rationale:
    The system guardian (ops-health) checks whether *software* works.
    The epistemic gate checks whether *evidence* exists.
    The Coordinator's internal safety review checks whether the
    *reasoning* is trustworthy.
    Only the epistemic gate and scope check can block analysis.
    Ops-health produces warnings that travel with the result.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import asyncio
import logging
import urllib.error
import urllib.request
import uuid

from Config.config import OLLAMA_BASE_URL, OLLAMA_FALLBACK_ONLY
from engine.Layer4_Analysis.intake.analyst_input_builder import build_analyst_input
from engine.Layer4_Analysis.coordinator import CouncilCoordinator as Coordinator
from engine.Layer4_Analysis.intake.question_scope_checker import check_question_scope
from engine.Layer4_Analysis.intake.epistemic_readiness import check_epistemic_readiness
from engine.Layer3_StateModel.signal_projection import project_state_to_observed_signals
from engine.Layer5_Reporting.intelligence_report import generate_report as generate_intelligence_report

_ops_log = logging.getLogger("diplomat.ops_health")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _local_ollama_reachable() -> bool:
    if not bool(OLLAMA_FALLBACK_ONLY):
        return False
    base_url = str(OLLAMA_BASE_URL or "http://localhost:11434").strip()
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=4) as resp:
            return int(getattr(resp, "status", 500)) < 400
    except (urllib.error.URLError, urllib.error.HTTPError, Exception):
        return False


def _append_llm_runtime_warnings(operational_warnings: List[str]) -> None:
    try:
        from engine.Layer4_Analysis.core.llm_client import get_llm_runtime_stats

        stats = get_llm_runtime_stats()
    except Exception:
        return

    warning_lines: List[str] = []
    empty_responses = int(stats.get("openrouter_empty_responses", 0) or 0)
    rate_limit_hits = int(stats.get("openrouter_rate_limit_hits", 0) or 0)
    backoff_retries = int(stats.get("openrouter_backoff_retries", 0) or 0)
    backup_successes = int(stats.get("openrouter_backup_successes", 0) or 0)
    backup_attempts = int(stats.get("openrouter_backup_attempts", 0) or 0)
    deterministic_fallbacks = int(stats.get("llm_deterministic_fallbacks", 0) or 0)

    if rate_limit_hits > 0:
        warning_lines.append(
            f"OpenRouter rate-limited {rate_limit_hits} time(s); backoff recovery triggered {backoff_retries} time(s)."
        )
    if empty_responses > 0:
        warning_lines.append(
            f"OpenRouter returned {empty_responses} empty response(s); transient retry recovery was applied."
        )
    if backup_successes > 0:
        warning_lines.append(
            f"Backup cloud model used successfully {backup_successes} time(s) after rate limiting."
        )
    elif backup_attempts > 0:
        warning_lines.append(
            f"Backup cloud model attempted {backup_attempts} time(s) after rate limiting."
        )
    if deterministic_fallbacks > 0:
        warning_lines.append(
            f"Deterministic fallback used for {deterministic_fallbacks} LLM step(s) after model failures."
        )

    for line in warning_lines:
        if line not in operational_warnings:
            operational_warnings.append(line)


def _derive_country_state_from_context(state_context: Any, country_code: str) -> Dict[str, Any]:
    meta = getattr(state_context, "meta", None)
    actors = getattr(state_context, "actors", None)
    signal_beliefs = list(getattr(state_context, "signal_beliefs", []) or [])
    observed_signals = set(getattr(state_context, "observed_signals", set()) or set())
    source_count = _safe_int(getattr(meta, "source_count", 0), 0)
    recent_activity = max(source_count, len(signal_beliefs), len(observed_signals))
    return {
        "country": str(getattr(actors, "subject_country", country_code) or country_code),
        "analysis_confidence": {
            "overall_score": max(0.0, min(1.0, _safe_float(getattr(meta, "data_confidence", 0.0), 0.0))),
        },
        "recent_activity_signals": int(recent_activity),
    }


def _derive_relationship_state_from_context(state_context: Any, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    evidence_ctx = getattr(state_context, "evidence", None)
    signal_provenance = getattr(evidence_ctx, "signal_provenance", {}) if evidence_ctx is not None else {}
    observed_signals = set(getattr(state_context, "observed_signals", set()) or set())
    signal_beliefs = list(getattr(state_context, "signal_beliefs", []) or [])

    provenance_count = 0
    if isinstance(signal_provenance, dict):
        for rows in signal_provenance.values():
            provenance_count += len(list(rows or []))

    observation_count = max(
        len(list(sources or [])),
        provenance_count,
        len(signal_beliefs),
        len(observed_signals),
    )

    return {
        "observation_count": int(observation_count),
        "supporting_evidence": list(sources or []),
    }


def _derive_confidence_seed(state_context: Any, sources: List[Dict[str, Any]]) -> float:
    meta = getattr(state_context, "meta", None)
    meta_conf = _safe_float(getattr(meta, "data_confidence", 0.0), 0.0)
    values: List[float] = []
    for belief in list(getattr(state_context, "signal_beliefs", []) or []):
        if isinstance(belief, dict):
            values.append(_safe_float(belief.get("belief", 0.0), 0.0))
        else:
            values.append(_safe_float(getattr(belief, "belief", 0.0), 0.0))
    belief_avg = (sum(values) / len(values)) if values else 0.0
    source_avg = (
        sum(_safe_float(item.get("score", 0.5), 0.5) for item in sources) / len(sources)
        if sources
        else 0.0
    )
    return max(0.0, min(1.0, max(source_avg, meta_conf, belief_avg)))


def _observation_quality_payload(state_context: Any) -> Dict[str, Any]:
    raw = getattr(state_context, "observation_quality", None)
    if raw is None:
        return {
            "sensor_coverage": 0.0,
            "data_freshness": 0.0,
            "source_count": 0,
            "is_observed": False,
        }
    to_dict = getattr(raw, "to_dict", None)
    if callable(to_dict):
        try:
            payload = to_dict()
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    if isinstance(raw, dict):
        return dict(raw)
    return {
        "sensor_coverage": _safe_float(getattr(raw, "sensor_coverage", 0.0), 0.0),
        "data_freshness": _safe_float(getattr(raw, "data_freshness", 0.0), 0.0),
        "source_count": _safe_int(getattr(raw, "source_count", 0), 0),
        "is_observed": bool(getattr(raw, "is_observed", False)),
    }


# ---------------------------------------------------------------------------
# Canonical outcome values
# ---------------------------------------------------------------------------
OUTCOME_ASSESSMENT = "ASSESSMENT"
OUTCOME_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
OUTCOME_OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass
class PipelineResult:
    """
    Compatibility result exposed to the API layer.
    Fields mirror what ``/v2/query`` consumes.
    """

    answer: str = ""
    status: str = "CONCLUDED"
    outcome: str = OUTCOME_ASSESSMENT   # one of the three canonical outcomes
    sources: List[Dict[str, Any]] = field(default_factory=list)
    references: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    analytic_confidence: float = 0.0
    epistemic_confidence: float = 0.0
    risk_level: Optional[str] = None
    early_warning_index: float = 0.0
    escalation_sync: float = 0.0
    prewar_detected: bool = False
    warning: Optional[str] = None
    trace_id: str = ""
    operational_warnings: List[str] = field(default_factory=list)

    # Optional enrichment fields
    cove_verified: bool = False
    intervention_required: bool = False
    intervention_id: Optional[str] = None
    legal_argument: Optional[Dict[str, Any]] = None
    crag_correction_applied: bool = False
    debate_outcome: Optional[str] = None
    confidence_ledger: Optional[Any] = None
    dossier_hits: Optional[Any] = None
    temporal_briefing: Optional[Any] = None
    scenario_playbook: Optional[Any] = None
    layer4_allowed: Optional[bool] = None
    layer4_gate_reason: Optional[str] = None
    layer4_scope: Optional[Dict[str, Any]] = None
    layer4_readiness: Optional[Dict[str, Any]] = None
    intelligence_report: Optional[Dict[str, Any]] = None
    gate_verdict: Optional[Dict[str, Any]] = None
    council_session: Optional[Dict[str, Any]] = None


class UnifiedPipeline:
    """
    Council-first Layer-4 entrypoint.

    Gate sequence:
        1. Scope check         → OUT_OF_SCOPE
        2. Ops-health probe    → warnings only (blocks only if LLM unreachable)
        3. State construction   → build StateContext via Layer-3
        4. Epistemic readiness → INSUFFICIENT_EVIDENCE
        5. Council execution   → Coordinator state-machine
        6. Outcome mapping     → ASSESSMENT | INSUFFICIENT_EVIDENCE
    """

    def __init__(self):
        self.coordinator = Coordinator()

    async def execute(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **flags,
    ) -> PipelineResult:
        # ── Gate 1: Scope check ───────────────────────────────────────
        scope = check_question_scope(query)
        if not scope.allowed:
            return PipelineResult(
                answer=f"Out of scope: {scope.reason}",
                status="SCOPE_BLOCKED",
                outcome=OUTCOME_OUT_OF_SCOPE,
                sources=[],
                references=[],
                confidence=0.0,
                trace_id="scope_blocked",
                layer4_allowed=False,
                layer4_gate_reason=scope.reason,
                layer4_scope=scope.to_dict(),
                layer4_readiness={
                    "ready": False,
                    "blockers": ["Scope guard blocked this question."],
                },
            )

        try:
            from engine.Layer4_Analysis.core.llm_client import reset_llm_runtime_stats

            reset_llm_runtime_stats()
        except Exception:
            pass

        trace_id = f"council_{uuid.uuid4().hex[:10]}"

        # ── Gate 2: Operational health (warning-only, except LLM) ─────
        operational_warnings: List[str] = []
        health_report: Dict[str, Any] = {
            "overall_ok": True,
            "failed_checks": [],
            "checks": {},
            "skipped": True,
        }
        if bool(flags.get("enable_system_guardian", True)):
            try:
                from engine.Layer4_Analysis.core.system_guardian import (
                    run_full_system_check,
                    summarize_blockers,
                )

                loop = asyncio.get_running_loop()
                health_report = await loop.run_in_executor(
                    None,
                    lambda: run_full_system_check(
                        country_code=str(flags.get("country_code", "UNKNOWN")),
                        as_of_date=flags.get("as_of_date"),
                        query=str(flags.get("system_guardian_probe_query", "") or "") or None,
                        ollama_model=str(flags.get("ollama_model", "") or "") or None,
                        min_internet_results=max(
                            1,
                            _safe_int(flags.get("system_guardian_min_internet_results", 3), 3),
                        ),
                    ),
                )
            except Exception as exc:
                health_report = {
                    "overall_ok": False,
                    "failed_checks": ["system_guardian_runtime"],
                    "checks": {
                        "system_guardian_runtime": {
                            "ok": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    },
                }
                summarize_blockers = lambda report: [  # type: ignore
                    "system_guardian_runtime: runtime failure"
                ]

            # Demoted: ops failures → warnings, NOT blockers.
            # The ONE exception: if the LLM (ollama) is unreachable,
            # reasoning is literally impossible → hard block.
            failed = list(health_report.get("failed_checks", []) or [])
            checks = health_report.get("checks", {}) or {}
            if "ollama" in failed:
                ollama_detail = checks.get("ollama", {})
                provider_name = str(ollama_detail.get("provider", "ollama") or "ollama")
                reason = str(ollama_detail.get("error", f"{provider_name} not reachable"))
                if provider_name == "openrouter" and _local_ollama_reachable():
                    warning = (
                        f"{provider_name}: {reason}. Proceeding with local Ollama fallback because it is reachable."
                    )
                    operational_warnings.append(warning)
                    _ops_log.warning("Operational degradation: %s", warning)
                    failed = [name for name in failed if name != "ollama"]

            if "ollama" in failed:
                ollama_detail = checks.get("ollama", {})
                provider_name = str(ollama_detail.get("provider", "ollama") or "ollama")
                reason = str(ollama_detail.get("error", f"{provider_name} not reachable"))
                return PipelineResult(
                    answer=f"Analysis cannot proceed: LLM is unreachable. {reason}",
                    status="LLM_UNREACHABLE",
                    outcome=OUTCOME_INSUFFICIENT_EVIDENCE,
                    sources=[],
                    references=[],
                    confidence=0.0,
                    trace_id="llm_unreachable",
                    operational_warnings=[f"{provider_name}: {reason}"],
                    layer4_allowed=False,
                    layer4_gate_reason=f"LLM provider ({provider_name}) is not available.",
                    layer4_scope=scope.to_dict(),
                    layer4_readiness={
                        "ready": False,
                        "blockers": ["LLM unreachable — cannot reason."],
                        "system_health": health_report,
                    },
                )

            # All other failures demoted to warnings
            non_llm_failures = [name for name in failed if name != "ollama"]
            if non_llm_failures:
                blocker_lines = summarize_blockers(health_report)
                for line in blocker_lines:
                    # Skip ollama entries (already handled)
                    if line.lower().startswith("ollama"):
                        continue
                    operational_warnings.append(line)
                    _ops_log.warning("Operational degradation: %s", line)

        # ── Gate 3: Build Layer-3 StateContext ─────────────────────────
        #    If the World Monitor has a fresh pre-built state, enrich
        #    the live build with its cached observations + beliefs.
        #    The pipeline ALWAYS rebuilds (for query-specific context)
        #    but merges in the monitor's perception so the start is warm.
        from engine.Layer3_StateModel.interface.state_provider import build_initial_state
        country_code_str = str(flags.get("country_code", "UNKNOWN"))

        initial_context_obj = build_initial_state(
            query,
            country_code=country_code_str,
            as_of_date=flags.get("as_of_date"),
        )

        # ── Merge pre-built state (World Monitor perception) ──────
        try:
            from runtime.world_monitor import get_prebuilt_state, is_state_fresh

            if is_state_fresh(country_code_str, max_age_minutes=120):
                prebuilt = get_prebuilt_state(country_code_str)
                if prebuilt and isinstance(prebuilt, dict):
                    # Merge pre-built signals into the live state
                    prebuilt_signals = prebuilt.get("signals", [])
                    for sig in prebuilt_signals:
                        sig = str(sig).strip().upper()
                        if sig and sig not in initial_context_obj.observed_signals:
                            initial_context_obj.observed_signals.add(sig)
                            # Set a baseline confidence from the monitor
                            if sig not in initial_context_obj.signal_confidence:
                                initial_context_obj.signal_confidence[sig] = 0.40

                    # Boost observation quality with monitor coverage
                    prebuilt_obs_count = int(prebuilt.get("observation_count", 0))
                    if prebuilt_obs_count > 0:
                        oq = initial_context_obj.observation_quality
                        oq.source_count = max(
                            int(getattr(oq, "source_count", 0) or 0),
                            prebuilt_obs_count,
                        )
                        oq.is_observed = True
                        oq.sensor_coverage = max(
                            float(getattr(oq, "sensor_coverage", 0.0) or 0.0),
                            float(prebuilt.get("sensor_coverage", 0.0)),
                        )

                    _ops_log.info(
                        "World Monitor state merged: %d signals, %d obs",
                        len(prebuilt_signals), prebuilt_obs_count,
                    )
        except ImportError:
            pass  # World Monitor not available — degrade gracefully
        except Exception as _wm_err:
            _ops_log.debug("World Monitor merge skipped: %s", _wm_err)

        # ── Gate 3b: Signal Projection (perception bridge) ─────────
        #    Convert raw Layer-3 state into structured belief signals.
        #    This is where "perception" happens — the council will reason
        #    over continuous belief strengths, not boolean flags.
        #
        #    PIPELINE FIREWALL: Legal RAG documents are architecturally
        #    isolated from the empirical analysis pipeline.  We pass an
        #    empty list so that signal projection operates solely on
        #    sensor-derived evidence.  RAG runs post-gate only.
        projected_signals = project_state_to_observed_signals(
            initial_context_obj, retrieved_docs=[],
        )

        # Store the projected beliefs on state_context so the coordinator
        # can consume them directly instead of re-extracting.
        initial_context_obj.projected_signals = projected_signals

        # Also back-fill observed_signals and signal_confidence from
        # projected beliefs so downstream code that still reads the
        # old flat set/dict gets consistent data.
        for sig_name, obs_sig in projected_signals.items():
            initial_context_obj.observed_signals.add(sig_name)
            # Keep the higher confidence if legal/economic reasoning
            # already set one.
            existing_conf = initial_context_obj.signal_confidence.get(sig_name, 0.0)
            initial_context_obj.signal_confidence[sig_name] = max(
                existing_conf, obs_sig.confidence
            )

        # ── Gate 3c: Inject temporal trend briefing ───────────────
        #    Ministers must see *direction*, not just snapshots.
        #    This runs BEFORE the council so deliberation is
        #    temporally-aware: "capability = 0.30 (rising 4 cycles)".
        try:
            from engine.Layer3_StateModel.temporal_memory import analyze_trends

            current_beliefs = dict(initial_context_obj.signal_confidence)
            trend_analysis = analyze_trends(current_beliefs)

            if trend_analysis.sufficient_history:
                # Populate trend_briefing on state context
                for sig, indicator in trend_analysis.indicators.items():
                    initial_context_obj.trend_briefing[sig] = indicator.to_dict()

                initial_context_obj.escalation_patterns = list(
                    trend_analysis.trend_overrides
                )
                initial_context_obj.trend_snapshot_count = trend_analysis.snapshot_count

                _ops_log.info(
                    "Temporal briefing injected: %d signals, %d snapshots, "
                    "%d escalation patterns",
                    len(trend_analysis.indicators),
                    trend_analysis.snapshot_count,
                    len(trend_analysis.trend_overrides),
                )
        except ImportError:
            pass
        except Exception as _trend_err:
            _ops_log.debug("Temporal briefing skipped: %s", _trend_err)

        # ── Gate 4: Epistemic readiness ───────────────────────────────
        readiness = check_epistemic_readiness(initial_context_obj)

        # Thread epistemic warnings into operational_warnings
        operational_warnings.extend(readiness.warnings)

        if not readiness.ready:
            return PipelineResult(
                answer=(
                    "Insufficient evidence to attempt analysis. "
                    + "; ".join(readiness.blockers)
                ),
                status="INSUFFICIENT_EVIDENCE",
                outcome=OUTCOME_INSUFFICIENT_EVIDENCE,
                sources=[],
                references=[],
                confidence=0.0,
                trace_id="insufficient_evidence",
                operational_warnings=operational_warnings,
                layer4_allowed=False,
                layer4_gate_reason="Epistemic readiness gate: insufficient signal/evidence.",
                layer4_scope=scope.to_dict(),
                layer4_readiness=readiness.to_dict(),
            )

        # ── Prepare analyst briefing (formatting, never blocks) ───────
        # Seed sources from Layer-3 evidence metadata and provenance.
        sources: List[Dict[str, Any]] = []
        seen = set()
        evidence_ctx = getattr(initial_context_obj, "evidence", None)
        if evidence_ctx:
            signal_provenance = getattr(evidence_ctx, "signal_provenance", {})
            if isinstance(signal_provenance, dict):
                for signal, rows in list(signal_provenance.items()):
                    for row in list(rows or []):
                        if not isinstance(row, dict):
                            continue
                        key = (
                            str(row.get("source_id", "")),
                            str(row.get("url", "")),
                            str(row.get("publication_date", "")),
                            str(row.get("excerpt", row.get("provenance_summary", ""))),
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
                                "provenance_summary": row.get("excerpt", row.get("provenance_summary", "")),
                                "score": confidence,
                                "signal": signal,
                            }
                        )

        country_code = str(flags.get("country_code", "UNKNOWN"))
        country_state = flags.get("country_state")
        relationship_state = flags.get("relationship_state")
        if country_state is None:
            country_state = _derive_country_state_from_context(initial_context_obj, country_code)
        if relationship_state is None:
            relationship_state = _derive_relationship_state_from_context(initial_context_obj, sources)
        confidence_seed = _derive_confidence_seed(initial_context_obj, sources)

        analyst_input = build_analyst_input(
            question=query,
            country_state=country_state,
            relationship_state=relationship_state,
            confidence=confidence_seed,
            state_context=initial_context_obj,
        )

        # Enrich readiness metadata with system health info (for logging)
        readiness_meta = readiness.to_dict()
        readiness_meta["system_health"] = health_report
        readiness_meta["analyst_input_readiness"] = analyst_input.get("readiness")

        # ── Gate 5: Council execution ─────────────────────────────────
        try:
            council = await self.coordinator.process_query(
                query=query,
                use_mcts=bool(flags.get("enable_mcts") or flags.get("use_mcts")),
                use_causal=bool(flags.get("enable_causal") or flags.get("use_causal")),
                use_red_team=bool(flags.get("enable_red_team", flags.get("use_red_team", True))),
                use_multi_perspective=bool(flags.get("enable_debate") or flags.get("use_multi_perspective")),
                state_context=initial_context_obj,
                max_investigation_loops=int(flags.get("max_investigation_loops", 1) or 1),
            )
        except Exception as exc:
            return await self._execute_core_fallback(
                query=query,
                user_id=user_id,
                session_id=session_id,
                scope=scope.to_dict(),
                flags=flags,
                operational_warnings=operational_warnings,
                failure=exc,
                trace_id=trace_id,
            )

        # ── Gate 6: Outcome mapping ───────────────────────────────────
        session = council.get("council_session", {}) or {}
        reports = session.get("minister_reports", {}) if isinstance(session, dict) else {}
        retrieval_qc = reports.get("retrieval_qc", {}) if isinstance(reports, dict) else {}
        strategy = reports.get("strategy", {}) if isinstance(reports, dict) else {}
        debate = reports.get("debate", {}) if isinstance(reports, dict) else {}

        intelligence_report: Optional[Dict[str, Any]] = None
        try:
            report_obj = generate_intelligence_report(
                council_payload=council if isinstance(council, dict) else {},
                state_context=initial_context_obj,
                query=query,
            )
            intelligence_report = report_obj.to_dict()
        except Exception:
            intelligence_report = None

        # Map Coordinator outcome to canonical three
        king_decision = str(council.get("king_decision", "") or "")
        council_status = str(council.get("status", "CONCLUDED") or "CONCLUDED")
        answer = str(council.get("answer", "")) or str((intelligence_report or {}).get("executive_summary", ""))

        if king_decision == "INSUFFICIENT_EVIDENCE" or council_status == "REFUSED":
            outcome = OUTCOME_INSUFFICIENT_EVIDENCE
        elif not answer.strip():
            outcome = OUTCOME_INSUFFICIENT_EVIDENCE
            answer = answer or "The system could not produce an assessment from available evidence."
        else:
            outcome = OUTCOME_ASSESSMENT

        _append_llm_runtime_warnings(operational_warnings)

        result = PipelineResult(
            answer=answer,
            status=council_status,
            outcome=outcome,
            sources=council.get("sources", sources) or [],
            references=council.get("references", []) or [],
            confidence=float(council.get("confidence", 0.0) or 0.0),
            analytic_confidence=float(council.get("analytic_confidence", council.get("confidence", 0.0)) or 0.0),
            epistemic_confidence=float(council.get("epistemic_confidence", 0.0) or 0.0),
            risk_level=str(council.get("risk_level", "") or "") or None,
            early_warning_index=float(council.get("early_warning_index", 0.0) or 0.0),
            escalation_sync=float(council.get("escalation_sync", 0.0) or 0.0),
            prewar_detected=bool(council.get("prewar_detected", False)),
            warning=str(council.get("warning", "") or "") or None,
            trace_id=str(session.get("session_id") or trace_id),
            operational_warnings=operational_warnings,
            crag_correction_applied=(retrieval_qc.get("details", {}) or {}).get("action") not in {None, "use_retrieved"},
            debate_outcome=str((debate.get("details", {}) or {}).get("outcome")) if debate else council.get("debate_outcome"),
            scenario_playbook=(strategy.get("details", {}) or {}).get("scenario_playbook"),
            layer4_allowed=True,
            layer4_scope=scope.to_dict(),
            layer4_readiness=readiness_meta,
            layer4_gate_reason=None,
            intelligence_report=intelligence_report,
            gate_verdict=council.get("gate_verdict"),
            council_session=session if isinstance(session, dict) else {},
        )
        return result

    async def _execute_core_fallback(
        self,
        query: str,
        user_id: Optional[str],
        session_id: Optional[str],
        scope: Dict[str, Any],
        flags: Dict[str, Any],
        operational_warnings: Optional[List[str]] = None,
        failure: Optional[Exception] = None,
        trace_id: Optional[str] = None,
    ) -> PipelineResult:
        ops_warnings = list(operational_warnings or [])
        failure_text = (
            f"{type(failure).__name__}: {failure}"
            if failure is not None
            else "unknown coordinator failure"
        )
        ops_warnings.append(f"Council execution failed: {failure_text}")
        _append_llm_runtime_warnings(ops_warnings)
        return PipelineResult(
            answer=(
                "The system could not complete council reasoning due to an internal runtime "
                "error. Returning a safe degraded response."
            ),
            status="COORDINATOR_FAILED",
            outcome=OUTCOME_INSUFFICIENT_EVIDENCE,
            sources=[],
            references=[],
            confidence=0.0,
            trace_id=trace_id or "core_fallback",
            operational_warnings=ops_warnings,
            layer4_allowed=False,
            layer4_gate_reason="Council coordinator failed; degraded response returned.",
            layer4_scope=scope,
            layer4_readiness={
                "ready": False,
                "blockers": ["Coordinator execution failed before synthesis."],
                "failure": failure_text,
            },
        )


async def query_diplomat(query: str, **kwargs) -> PipelineResult:
    """
    Convenience wrapper used by legacy callers.
    """
    return await unified_pipeline.execute(query, **kwargs)


# Singleton instance for import convenience
unified_pipeline = UnifiedPipeline()


__all__ = [
    "PipelineResult",
    "UnifiedPipeline",
    "unified_pipeline",
    "query_diplomat",
    "OUTCOME_ASSESSMENT",
    "OUTCOME_INSUFFICIENT_EVIDENCE",
    "OUTCOME_OUT_OF_SCOPE",
]
