"""
Synthesis Engine — Threat decision + escalation fusion
=======================================================
Extracted from coordinator._synthesize_decision (lines 1570–2400).

Responsible for:
  - Temporal intelligence (trend, prewar, early warning, escalation sync)
  - SRE domain fusion + LCI legal constraint index
  - Conflict state classification (Bayesian)
  - Phase 5: Trajectory + Black Swan detection
  - Phase 6: Forecast archive + resolution + auto-adjustment
  - Phase 7: Global theater update + contagion
  - Confidence pipeline delegation
  - Assessment report construction
  - Warning generation

All results are stored on ``session`` attributes — the function
returns the mutated ``session``.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from engine.Layer4_Analysis.schema import AssessmentReport, ThreatLevel
from engine.Layer4_Analysis.domain_fusion import compute_domain_indices
from engine.Layer4_Analysis.escalation_index import (
    compute_escalation_index, escalation_to_risk, EscalationInput,
)
from engine.Layer4_Analysis.pipeline.confidence_pipeline import compute_weighted_confidence

logger = logging.getLogger(__name__)

# ── Hardcoded Legal Constraint Index (LCI) per country ────────────
_LCI_TABLE = {
    "IRN": 0.35, "PRK": 0.40, "RUS": 0.25, "CHN": 0.15,
    "SYR": 0.30, "ISR": 0.10, "PAK": 0.20, "IND": 0.10,
    "SAU": 0.10, "MMR": 0.20, "VEN": 0.15, "CUB": 0.15,
    "LBY": 0.20, "YEM": 0.15, "SDN": 0.20, "SSD": 0.15,
    "AFG": 0.15, "IRQ": 0.15, "SOM": 0.15, "ETH": 0.10,
    "ERI": 0.15, "BLR": 0.15, "UKR": 0.05,
}


def _session_country(session: Any, default: str = "UNKNOWN") -> str:
    """Resolve primary country code from session/state context safely."""
    try:
        actors = getattr(getattr(session, "state_context", None), "actors", None)
        candidate = str(getattr(actors, "subject_country", "") or "").strip().upper()
        if candidate and candidate != "UNKNOWN":
            return candidate
    except Exception:
        pass
    try:
        candidate = str(getattr(session, "learning_country", "") or "").strip().upper()
        if candidate and candidate != "UNKNOWN":
            return candidate
    except Exception:
        pass
    return str(default or "UNKNOWN").strip().upper() or "UNKNOWN"


def run_synthesis(
    session: Any,
    coordinator: Any,
    verification_score: Optional[float] = None,
) -> Any:
    """Execute the full synthesis pipeline.

    This is a direct extraction of ``CouncilCoordinator._synthesize_decision``.
    ``coordinator`` is a reference to the ``CouncilCoordinator`` instance
    so that helper methods (``_state_dimensions``, ``_generate_fallback_estimate``,
    ``compute_escalation``, ``_driver_score_from_dimensions``,
    ``_average_hypothesis_coverage``) can be called.

    Returns the mutated ``session``.
    """
    if not session.hypotheses:
        logger.info(
            "[SYNTHESIS] No hypotheses survived — generating fallback estimate from state signals"
        )
        return coordinator._generate_fallback_estimate(session)

    dimensions = coordinator._state_dimensions(session)
    observed_signals = set(
        getattr(session.state_context, "observed_signals", []) or []
    )

    # ── Threat level from Layer-3 state model ─────────────────────
    synthesized = coordinator.synthesizer.synthesize(session)
    decision = (
        str(synthesized or "").strip().upper()
        if isinstance(synthesized, str)
        else ""
    )
    if not decision:
        decision = coordinator.compute_escalation(session)
    session.final_decision = decision
    session.king_decision = decision

    # ── Temporal intelligence ─────────────────────────────────────
    _run_temporal_intelligence(session)

    # ── Escalation synchronization floor ──────────────────────────
    _apply_escalation_sync_floor(session)

    # ── Strategic Risk Engine (SRE) ───────────────────────────────
    _run_sre_pipeline(session)

    # ── Phase 6: Auto-threshold adjustment ────────────────────────
    _run_auto_adjustment(session)

    # ── Confidence architecture ───────────────────────────────────
    driver_score = max(
        0.0,
        min(1.0, float(coordinator._driver_score_from_dimensions(dimensions) or 0.0)),
    )
    constraint_score = max(0.0, min(1.0, float(dimensions.get("COST", 0.0) or 0.0)))
    state_net = getattr(session.state_context, "net_escalation", None)
    if state_net is None:
        net_score = max(0.0, min(1.0, float(driver_score - constraint_score)))
    else:
        net_score = max(0.0, min(1.0, float(state_net or 0.0)))
    session.driver_score = driver_score
    session.constraint_score = constraint_score
    session.net_escalation = net_score

    sre_esc = float(getattr(session, "sre_escalation_score", 0.0) or 0.0)
    sensor_score = sre_esc if sre_esc > 0.0 else net_score

    # ── Build projected_list for confidence pipeline ──────────────
    projected = getattr(session.state_context, "projected_signals", None) or {}
    projected_list = (
        list(projected.values()) if isinstance(projected, dict) else list(projected)
    )

    # ── Missing information / PIRs / gaps ─────────────────────────
    missing_information = _build_missing_information(session)

    # ── Assessment report ─────────────────────────────────────────
    threat_map = {
        "CRITICAL": ThreatLevel.HIGH,
        "HIGH": ThreatLevel.HIGH,
        "ELEVATED": ThreatLevel.ELEVATED,
        "RHETORICAL_POSTURING": ThreatLevel.GUARDED,
        "GUARDED": ThreatLevel.GUARDED,
        "LOW": ThreatLevel.LOW,
    }
    recommendation_map = {
        "CRITICAL": "CRITICAL: Multiple escalation patterns with capability+intent saturation; immediate command attention required.",
        "HIGH": "Capability and intent are both high; prioritize immediate escalation monitoring.",
        "ELEVATED": "Capability and intent are elevated with partial stability support; maintain heightened watch.",
        "RHETORICAL_POSTURING": "Intent signals exceed capability; monitor signaling behavior for conversion to action.",
        "GUARDED": "Drivers are materially offset by strategic constraints; maintain guarded monitoring.",
        "LOW": "Escalation preconditions are not jointly satisfied; maintain routine monitoring.",
    }

    session.assessment_report = AssessmentReport(
        threat_level=threat_map.get(session.king_decision, ThreatLevel.LOW),
        confidence_score=max(0.0, min(1.0, float(sensor_score))),
        summary=(
            f"{session.king_decision}: capability={dimensions['CAPABILITY']:.2f}, "
            f"intent={dimensions['INTENT']:.2f}, stability={dimensions['STABILITY']:.2f}, "
            f"cost={dimensions['COST']:.2f}, driver={driver_score:.2f}, "
            f"constraints={constraint_score:.2f}, net={net_score:.2f}"
        ),
        key_indicators=sorted(observed_signals),
        missing_information=missing_information,
        recommendation=recommendation_map.get(
            session.king_decision, recommendation_map["LOW"]
        ),
        minister_consensus=coordinator._average_hypothesis_coverage(session),
        synthesis_logic=(
            f"decision={session.king_decision}; capability={dimensions['CAPABILITY']:.3f}; "
            f"intent={dimensions['INTENT']:.3f}; stability={dimensions['STABILITY']:.3f}; "
            f"cost={dimensions['COST']:.3f}; driver={driver_score:.3f}; "
            f"constraints={constraint_score:.3f}; net={net_score:.3f}"
        ),
    )

    # ── Weighted confidence pipeline ──────────────────────────────
    weighted_confidence = compute_weighted_confidence(
        session=session,
        sensor_score=sensor_score,
        projected_list=projected_list,
        dimensions=dimensions,
        driver_score=driver_score,
    )

    session.final_confidence = weighted_confidence
    session.sensor_confidence = weighted_confidence
    session.document_confidence = 0.0  # pipeline firewall
    session.strategic_status = str(session.king_decision or "LOW").lower()

    # ── Warning generation ────────────────────────────────────────
    session.warning = ""
    if bool(getattr(session, "prewar_detected", False)):
        session.warning = "PRE-WAR SIGNAL SEQUENCE DETECTED"
    elif (
        float(getattr(session, "early_warning_index", 0.0) or 0.0) > 0.25
        and str(session.king_decision or "LOW").upper()
        in {"LOW", "GUARDED", "ELEVATED"}
    ):
        session.warning = "PRE-ESCALATION INDICATORS DETECTED"

    return session


# ═══════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════


def _run_temporal_intelligence(session: Any) -> None:
    """Compute trend momentum + synchronized escalation detection."""
    try:
        from engine.Layer3_StateModel.temporal.trend_analysis import compute_trend
        from engine.Layer3_StateModel.temporal.state_history import load_state_history
        from engine.Layer3_StateModel.temporal.escalation_sync import compute_esi
        from engine.Layer3_StateModel.temporal.prewar_detector import detect_prewar_pattern
        from engine.Layer4_Analysis.decision.early_warning import compute_emi

        actors = getattr(session.state_context, "actors", None)
        country_code = str(
            getattr(actors, "subject_country", "UNKNOWN") or "UNKNOWN"
        )
        trend = compute_trend(country_code)
        history_rows = load_state_history(country_code)
        session.temporal_trend = dict(trend or {})
        session.prewar_detected = bool(detect_prewar_pattern(history_rows))
        session.early_warning_index = float(
            compute_emi(
                session.state_context, trend, prewar_detected=session.prewar_detected
            )
        )
        session.escalation_sync = float(compute_esi(history_rows))
    except Exception:
        session.temporal_trend = {}
        session.early_warning_index = 0.0
        session.escalation_sync = 0.0
        session.prewar_detected = False


def _apply_escalation_sync_floor(session: Any) -> None:
    """Enforce minimum risk tier from synchronized dimension rises."""
    decision_rank = {
        "LOW": 0, "GUARDED": 1, "RHETORICAL_POSTURING": 1,
        "ELEVATED": 2, "HIGH": 3, "CRITICAL": 4,
    }
    reverse_rank = {
        0: "LOW", 1: "GUARDED", 2: "ELEVATED", 3: "HIGH", 4: "CRITICAL",
    }
    current_rank = decision_rank.get(
        str(session.king_decision or "LOW").upper(), 0
    )
    sync_value = float(getattr(session, "escalation_sync", 0.0) or 0.0)
    if sync_value > 0.70:
        current_rank = max(current_rank, 3)
    elif sync_value > 0.40:
        current_rank = max(current_rank, 2)
    session.king_decision = reverse_rank.get(
        current_rank, str(session.king_decision or "LOW").upper()
    )
    session.final_decision = session.king_decision


def _run_sre_pipeline(session: Any) -> None:
    """SRE domain fusion, conflict state, trajectory, black swan, forecasts, global theater."""
    try:
        # Phase 8: resolve expired forecasts at pipeline start so
        # calibration engine accumulates resolved entries over time.
        try:
            from engine.Layer6_Learning.forecast_resolution import resolve_pending
            _rp = resolve_pending()
            if _rp.get("newly_resolved", 0) > 0:
                logger.info("[SRE] Resolved %d pending forecasts at startup", _rp["newly_resolved"])
        except Exception as _rp_exc:
            logger.debug("[SRE] resolve_pending skipped: %s", _rp_exc)

        projected = getattr(session.state_context, "projected_signals", None) or {}
        projected_list = (
            list(projected.values()) if isinstance(projected, dict) else list(projected)
        )
        if not projected_list:
            return

        sre_domains = compute_domain_indices(projected_list)

        # ── LCI injection ─────────────────────────────────────────
        _lci_country = _session_country(session, default="UNKNOWN")
        _lci_value = _LCI_TABLE.get(_lci_country, 0.0)
        if _lci_value > 0:
            _old_cost_raw = sre_domains.get("cost_raw", 0.0)
            _new_cost_raw = min(_old_cost_raw + _lci_value, 1.0)
            sre_domains["cost_raw"] = _new_cost_raw
            sre_domains["cost"] = 1.0 - _new_cost_raw
            logger.info(
                "[FIX3-LCI] country=%s LCI=%.2f cost_raw: %.3f->%.3f cost_for_sre: %.3f",
                _lci_country, _lci_value, _old_cost_raw, _new_cost_raw,
                sre_domains["cost"],
            )
        else:
            logger.info(
                "[FIX3-LCI] country=%s LCI=0.00 (no legal constraint entry)",
                _lci_country,
            )

        # ── Temporal for SRE ──────────────────────────────────────
        from engine.Layer3_StateModel.temporal_memory import analyze_trends as _sre_analyze

        _sre_sc = getattr(session, "state_context", None)
        _sre_beliefs: dict = {}
        if _sre_sc:
            _sig_conf = getattr(_sre_sc, "signal_confidence", {}) or {}
            _proj = getattr(_sre_sc, "projected_signals", {}) or {}
            _empirical_sigs = {
                k
                for k, v in _proj.items()
                if getattr(v, "namespace", "empirical") == "empirical"
            }
            _sre_beliefs = {
                k: float(v)
                for k, v in _sig_conf.items()
                if float(v) > 0 and k in _empirical_sigs
            }
        _sre_temporal = _sre_analyze(_sre_beliefs)

        class _SRETemporal:
            def __init__(self, ta):
                self.escalation_patterns = len(ta.trend_overrides) if ta else 0
                self.spike_count = sum(
                    1
                    for ind in (ta.indicators.values() if ta else [])
                    if getattr(ind, "spike", False)
                )
                spike_mags = [
                    getattr(ind, "spike_magnitude", 0.0)
                    for ind in (ta.indicators.values() if ta else [])
                    if getattr(ind, "spike", False)
                ]
                self.max_spike_severity = max(spike_mags) if spike_mags else 0.0

        _tmp = _SRETemporal(_sre_temporal)

        _proj = getattr(_sre_sc, "projected_signals", {}) or {}
        _mob_sig = _proj.get("SIG_MIL_MOBILIZATION")
        _mob_conf = float(getattr(_mob_sig, "confidence", 0.0)) if _mob_sig else 0.0
        _log_sig = _proj.get("SIG_LOGISTICS_PREP")
        _log_conf = float(getattr(_log_sig, "confidence", 0.0)) if _log_sig else 0.0

        sre_input = EscalationInput(
            capability=sre_domains.get("capability", 0.0),
            intent=sre_domains.get("intent", 0.0),
            instability=sre_domains.get("stability", 0.0),
            cost=sre_domains.get("cost", 0.0),
            escalation_patterns=_tmp.escalation_patterns,
            spike_count=_tmp.spike_count,
            max_spike_severity=_tmp.max_spike_severity,
            mobilization_conf=_mob_conf,
            logistics_conf=_log_conf,
        )
        logger.info("[SRE] EscalationInput = %s", sre_input)

        sre_esc = compute_escalation_index(None, None, inp=sre_input)
        sre_risk = escalation_to_risk(sre_esc)

        old_decision = session.king_decision
        session.king_decision = sre_risk
        session.final_decision = sre_risk
        session.sre_escalation_score = sre_esc
        session.sre_domains = sre_domains
        session.sre_input = sre_input

        logger.info(
            "[SRE] Escalation score = %.3f -> %s  (old council: %s)",
            sre_esc, sre_risk, old_decision,
        )

        # ── SRE baseline benchmark ────────────────────────────────
        import datetime as _dt

        _bench = {
            "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
            "phase": "phase4_signal_quality",
            "input": sre_input.to_dict(),
            "escalation_score": sre_esc,
            "risk_level": sre_risk,
            "domains": sre_domains,
            "signals_total": len(projected_list),
        }
        _bench_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(_bench_dir, exist_ok=True)
        _bench_path = os.path.join(_bench_dir, "sre_baseline.json")
        with open(_bench_path, "w") as _bf:
            json.dump(_bench, _bf, indent=2)
        logger.info("[SRE-BENCHMARK] Saved baseline → %s", _bench_path)

        # ── Conflict State Classification ─────────────────────────
        _run_conflict_state(session, projected, sre_domains)

        # ── Phase 8: SRE ↔ Conflict State Cross-Validation ───────
        # Prevents contradictory outputs (e.g. ACTIVE_CONFLICT + LOW SRE).
        # Position (state) sets a floor on velocity (SRE).
        _cs_label = getattr(session, "conflict_state_label", "UNKNOWN")
        _STATE_SRE_FLOORS = {
            "ACTIVE_CONFLICT": 0.40,
            "FULL_WAR":        0.65,
        }
        _sre_floor = _STATE_SRE_FLOORS.get(_cs_label, 0.0)
        if _sre_floor > 0 and sre_esc < _sre_floor:
            _old_sre = sre_esc
            sre_esc = _sre_floor
            sre_risk = escalation_to_risk(sre_esc)
            session.sre_escalation_score = sre_esc
            session.king_decision = sre_risk
            session.final_decision = sre_risk
            logger.info(
                "[SRE-SYNC] Conflict state %s enforces SRE floor: "
                "%.3f → %.3f (%s)",
                _cs_label, _old_sre, sre_esc, sre_risk,
            )

        # ── Phase 5: Trajectory + Black Swan ──────────────────────
        _run_trajectory_and_black_swan(
            session, sre_esc, sre_risk, sre_domains, _tmp, _mob_conf
        )

        # ── Phase 8.1: War Probability Composite Index ───────────
        _run_wpci(session, sre_esc)

        # ── Phase 6: Forecast Archive + Resolution ────────────────
        _run_forecast_archive(session)

        # ── Phase 7: Global Theater Update + Contagion ────────────
        _run_global_theater(session)

    except Exception as exc:
        logger.warning(
            "[SRE] Strategic Risk Engine failed, keeping council decision: %s", exc
        )


def _run_conflict_state(
    session: Any, projected: dict, sre_domains: dict
) -> None:
    """Bayesian conflict state classification."""
    try:
        from engine.Layer3_StateModel.conflict_state_model import classify_conflict_state

        _prev_traj_prob_up = 0.0
        try:
            _traj_cache = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data",
                "last_trajectory_prob_up.json",
            )
            if os.path.exists(_traj_cache):
                with open(_traj_cache, "r") as _tcf:
                    _prev_traj_prob_up = float(
                        json.load(_tcf).get("prob_up", 0.0)
                    )
        except Exception:
            pass

        _cs_country = _session_country(session, default="UNKNOWN")
        _cs_result = classify_conflict_state(
            projected_signals=projected,
            country=_cs_country,
            sre_domains=sre_domains,
            trajectory_prob_up=_prev_traj_prob_up,
        )
        session.conflict_state = _cs_result.to_dict()
        session.conflict_state_label = _cs_result.state
        logger.info(
            "[CONFLICT-STATE] Classified: %s (conf=%.3f) for %s | 14d P(ACTIVE+)=%.3f",
            _cs_result.state,
            _cs_result.confidence,
            _cs_country,
            _cs_result.p_active_or_higher_14d,
        )
    except Exception as _cs_exc:
        logger.warning("[CONFLICT-STATE] Classification failed: %s", _cs_exc)
        session.conflict_state = {"state": "UNKNOWN", "confidence": 0.0}
        session.conflict_state_label = "UNKNOWN"


def _run_wpci(session: Any, sre_esc: float) -> None:
    """Phase 8.1: War Probability Composite Index — fuses 4 independent channels."""
    try:
        from engine.Layer4_Analysis.war_index import compute_wpci

        _p_active = 0.0
        try:
            _cs_dict = getattr(session, "conflict_state", {}) or {}
            _p_active = float(_cs_dict.get("p_active_or_higher_14d", 0.0))
        except Exception:
            pass

        _traj = getattr(session, "trajectory_result", None)
        _prob_up = float(getattr(_traj, "prob_up", 0.0) or 0.0) if _traj else 0.0

        _ndi_result = getattr(session, "ndi_result", None)
        _ndi = float(getattr(_ndi_result, "ndi", 0.0) or 0.0) if _ndi_result else 0.0

        wpci = compute_wpci(
            sre_score=sre_esc,
            p_active_or_higher=_p_active,
            trajectory_prob_up=_prob_up,
            ndi=_ndi,
        )
        session.wpci_result = wpci
        logger.info(
            "[WPCI] composite=%.3f tier=%s dominant=%s divergent=%s",
            wpci.composite, wpci.tier, wpci.dominant_channel, wpci.divergent,
        )
    except Exception as _wpci_exc:
        logger.warning("[WPCI] War Probability Composite Index failed: %s", _wpci_exc)
        session.wpci_result = None


def _run_trajectory_and_black_swan(
    session: Any,
    sre_esc: float,
    sre_risk: str,
    sre_domains: dict,
    _tmp: Any,
    _mob_conf: float,
) -> None:
    """Phase 5: Predictive Escalation Trajectory + Black Swan Detection."""
    try:
        from engine.Layer5_Trajectory.gkg_ingest import fetch_and_parse_gkg
        from engine.Layer5_Trajectory.narrative_index import compute_narrative_drift
        from engine.Layer5_Trajectory.trajectory_model import compute_trajectory
        from engine.Layer5_Trajectory.trajectory_report import format_trajectory_section  # noqa: F401

        _gkg_metrics = fetch_and_parse_gkg()
        _ndi_result = compute_narrative_drift(_gkg_metrics)

        _p_active_for_traj = 0.0
        try:
            _cs_dict = getattr(session, "conflict_state", {}) or {}
            _p_active_for_traj = float(
                _cs_dict.get("p_active_or_higher_14d", 0.0)
            )
        except Exception:
            pass

        _trajectory = compute_trajectory(
            current_sre=sre_esc,
            current_risk=sre_risk,
            sre_domains=sre_domains,
            escalation_patterns=_tmp.escalation_patterns,
            spike_count=_tmp.spike_count,
            trend_bonus=sre_esc
            - (
                0.35 * sre_domains.get("capability", 0)
                + 0.30 * sre_domains.get("intent", 0)
                + 0.20 * sre_domains.get("stability", 0)
                + 0.15 * sre_domains.get("cost", 0)
            ),
            ndi_result=_ndi_result,
            mobilization_conf=_mob_conf,
            cost=sre_domains.get("cost", 0.0),
            intent=sre_domains.get("intent", 0.0),
            p_active_14d=_p_active_for_traj,
        )

        # Persist trajectory prob_up for next cycle
        try:
            _traj_cache_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data",
                "last_trajectory_prob_up.json",
            )
            os.makedirs(os.path.dirname(_traj_cache_path), exist_ok=True)
            with open(_traj_cache_path, "w") as _tcf:
                json.dump({"prob_up": _trajectory.prob_up}, _tcf)
        except Exception:
            pass

        session.trajectory_result = _trajectory
        session.ndi_result = _ndi_result
        session.gkg_metrics = _gkg_metrics

        from engine.Layer3_StateModel.signal_projection import (  # noqa: E501
            project_state_to_observed_signals,
        )
        project_state_to_observed_signals._expansion_mode = (
            _trajectory.expansion_mode
        )

        logger.info(
            "[PHASE5] Trajectory: P(HIGH)=%.1f%%  P(LOW)=%.1f%%  "
            "expansion=%s  NDI=%.3f  vel=%.3f",
            _trajectory.prob_up * 100,
            _trajectory.prob_down * 100,
            _trajectory.expansion_mode,
            _ndi_result.ndi,
            _trajectory.velocity,
        )

        # ── Phase 5.2: Black Swan Detection ───────────────────────
        try:
            from engine.Layer7_GlobalModel.cross_theater_forecaster import (
                global_black_swan as _p7_gbs,
            )

            _p7_prev_systemic = _p7_gbs()
        except Exception:
            _p7_prev_systemic = False
        try:
            from engine.Layer5_Trajectory.black_swan_detector import detect as bs_detect

            _projected = (
                getattr(
                    getattr(session, "state_context", None),
                    "projected_signals",
                    {},
                )
                or {}
            )

            _bs_result = bs_detect(
                max_spike_severity=float(
                    getattr(_tmp, "max_spike_severity", 0.0) or 0.0
                ),
                velocity=_trajectory.velocity,
                transition_factor=_trajectory.transition_factor,
                projected_signals=_projected,
                systemic_cascade=_p7_prev_systemic,
            )
            session.black_swan_result = _bs_result

            if _bs_result.triggered:
                sre_esc = min(1.0, sre_esc + _bs_result.escalation_boost)
                sre_risk = escalation_to_risk(sre_esc)
                session.sre_escalation_score = sre_esc
                session.king_decision = sre_risk
                session.final_decision = sre_risk

                _trajectory.prob_up = max(
                    _trajectory.prob_up, _bs_result.trajectory_floor
                )
                _trajectory.prob_stable = max(
                    0.0, 1.0 - _trajectory.prob_up - _trajectory.prob_down
                )
                _trajectory.expansion_mode = "FORCED_HIGH"
                _trajectory.acceleration_watch = True
                session.trajectory_result = _trajectory

                logger.warning(
                    "[BLACK_SWAN] Overrides applied: SRE %.3f→%s, "
                    "P(HIGH)=%.0f%%, expansion=FORCED_HIGH",
                    sre_esc,
                    sre_risk,
                    _trajectory.prob_up * 100,
                )
        except Exception as _bs_exc:
            logger.warning("[BLACK_SWAN] Detection failed: %s", _bs_exc)
            session.black_swan_result = None

    except Exception as _p5_exc:
        logger.warning("[PHASE5] Trajectory computation failed: %s", _p5_exc)
        session.trajectory_result = None
        session.ndi_result = None


def _run_forecast_archive(session: Any) -> None:
    """Phase 6: Forecast Archive + Resolution."""
    try:
        from engine.Layer6_Learning.forecast_archive import record_forecast
        from engine.Layer6_Learning.forecast_resolution import resolve_forecasts

        _p6_country = str(
            getattr(
                getattr(session.state_context, "actors", None),
                "subject_country",
                "UNKNOWN",
            )
            or "UNKNOWN"
        ).upper()

        _p6_traj = getattr(session, "trajectory_result", None)
        _p6_ndi = getattr(session, "ndi_result", None)

        if _p6_traj is not None:
            record_forecast(
                country=_p6_country,
                session_id=session.session_id,
                prob_up=_p6_traj.prob_up,
                prob_down=_p6_traj.prob_down,
                prob_stable=_p6_traj.prob_stable,
                sre_escalation_score=float(
                    getattr(session, "sre_escalation_score", 0.0) or 0.0
                ),
                velocity=_p6_traj.velocity,
                ndi=float(getattr(_p6_ndi, "ndi", 0.0) or 0.0)
                if _p6_ndi
                else 0.0,
                expansion_mode=_p6_traj.expansion_mode,
            )

        _p6_esc = float(
            getattr(session, "sre_escalation_score", 0.0) or 0.0
        )
        _p6_resolution = resolve_forecasts({_p6_country: _p6_esc})
        session.learning_resolution = _p6_resolution
        session.learning_country = _p6_country

        logger.info(
            "[PHASE6] Forecast recorded for %s. Resolution: %d newly resolved, %d total",
            _p6_country,
            _p6_resolution.get("newly_resolved", 0),
            _p6_resolution.get("total_resolved", 0),
        )
    except Exception as _p6_exc:
        logger.warning(
            "[PHASE6] Forecast archive/resolution failed: %s", _p6_exc
        )
        session.learning_resolution = None
        session.learning_country = "UNKNOWN"


def _run_global_theater(session: Any) -> None:
    """Phase 7: Global Theater Update + Contagion."""
    try:
        from Config.config import ENABLE_GLOBAL_MODEL as _P7_ON

        if _P7_ON:
            from engine.Layer7_GlobalModel.global_state import update_theater
            from engine.Layer7_GlobalModel.contagion_engine import propagate_all

            _p7_country = _session_country(session, default="UNKNOWN")
            _p7_sre = float(
                getattr(session, "sre_escalation_score", 0.0) or 0.0
            )
            _p7_traj = getattr(session, "trajectory_result", None)
            _p7_ndi = getattr(session, "ndi_result", None)

            update_theater(
                country=_p7_country,
                sre=_p7_sre,
                prob_high=float(getattr(_p7_traj, "prob_up", 0.0) or 0.0)
                if _p7_traj
                else 0.0,
                velocity=float(getattr(_p7_traj, "velocity", 0.0) or 0.0)
                if _p7_traj
                else 0.0,
                ndi=float(getattr(_p7_ndi, "ndi", 0.0) or 0.0)
                if _p7_ndi
                else 0.0,
                expansion_mode=str(
                    getattr(_p7_traj, "expansion_mode", "UNKNOWN") or "UNKNOWN"
                )
                if _p7_traj
                else "UNKNOWN",
            )

            session.p7_contagion = propagate_all()

            logger.info(
                "[PHASE7] Theater %s updated (SRE=%.3f). Contagion: %d sources propagated.",
                _p7_country,
                _p7_sre,
                len(session.p7_contagion),
            )
        else:
            session.p7_contagion = {}
    except Exception as _p7_exc:
        logger.warning(
            "[PHASE7] Global model update failed: %s", _p7_exc
        )
        session.p7_contagion = {}


def _run_auto_adjustment(session: Any) -> None:
    """Phase 6: auto-threshold weight adjustments."""
    try:
        from engine.Layer6_Learning.auto_adjuster import apply_adjustments

        _p6_adj_values = apply_adjustments(force=False)
        session.learning_adjustments = _p6_adj_values
        logger.info(
            "[PHASE6] Auto-adjustment: loaded %d constants",
            len(_p6_adj_values),
        )
    except Exception as _p6_adj_exc:
        logger.warning(
            "[PHASE6] Auto-adjustment load failed: %s", _p6_adj_exc
        )
        session.learning_adjustments = {}


def _build_missing_information(session: Any) -> list:
    """Compile missing_information list from investigation needs, PIRs, gaps."""
    missing_information = list(session.missing_signals or [])
    if session.investigation_needs:
        for sig in session.investigation_needs:
            if sig not in missing_information:
                missing_information.append(sig)

    collection_plan = getattr(session, "collection_plan", None)
    if collection_plan and hasattr(collection_plan, "pirs"):
        for pir in collection_plan.pirs:
            pir_desc = (
                f"PIR: {pir.signal} via {pir.collection.value} "
                f"[{pir.priority.value}] — {pir.reason}"
            )
            if pir_desc not in missing_information:
                missing_information.append(pir_desc)

    gap_report = getattr(session, "gap_report", None)
    if gap_report and hasattr(gap_report, "gaps"):
        for gap_desc in gap_report.gaps or []:
            gap_line = f"GAP: {gap_desc}"
            if gap_line not in missing_information:
                missing_information.append(gap_line)
        for contra_desc in gap_report.contradictions or []:
            contra_line = f"CONTRADICTION: {contra_desc}"
            if contra_line not in missing_information:
                missing_information.append(contra_line)

    return missing_information
