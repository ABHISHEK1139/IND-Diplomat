"""Threat Synthesizer: neuro-symbolic intelligence scoring.

The deterministic heuristic assessment is built first. The LLM may refine
unknowns, gaps, narrative, and forecasts, but it cannot independently override
the heuristic threat level without staying inside bounded confidence rails.
"""

from __future__ import annotations

import logging
from copy import deepcopy

from dip.Config.config import config
from dip.core.schema import IntelligenceAssessment, DualModeAssessment
from dip.nextgen.structured_llm import structured_completion

logger = logging.getLogger("decision.threat_synthesizer")


def decide(session) -> None:
    """Populate `session.final_decision` with a validated assessment JSON."""

    signals = list(session.state_context.current_signals)
    valid_hypotheses = [
        item for item in (session.red_team_report or [])
        if "No hypotheses require" not in str(item)
    ]

    heuristic = _build_heuristic_assessment(session, signals, valid_hypotheses)

    llm = _build_llm_refinement(session, signals, valid_hypotheses, heuristic)
    if llm is None:
        decision = DualModeAssessment(
            heuristic_result=heuristic,
            final=heuristic,
            resolution_action="llm_failed_fallback"
        )
        _finalize(session, decision.final)
        return

    decision = _merge_bounded_assessment(heuristic, llm)
    session.dual_mode_assessment = decision.model_dump(mode="json")
    _finalize(session, decision.final)


def _build_heuristic_assessment(session, signals, valid_hypotheses) -> IntelligenceAssessment:
    assessment = IntelligenceAssessment()

    for sig in signals:
        if sig.intensity >= 0.5:
            assessment.positive_evidence.append(sig)
        else:
            assessment.negative_evidence.append(sig)

    domain_signals: dict = {}
    domain_intensities: dict = {}
    for sig in signals:
        domain = getattr(sig, "domain", "unknown")
        domain_signals.setdefault(domain, []).append(sig)

    for domain, sigs in domain_signals.items():
        domain_intensities[domain] = sum(s.intensity for s in sigs) / len(sigs) if sigs else 0.0

    dim_map = {
        "military": ["military", "defense", "security"],
        "diplomatic": ["diplomatic", "political", "legal"],
        "economic": ["economic", "trade", "sanctions"],
        "cyber": ["cyber", "digital", "information_warfare"],
        "information": ["media", "propaganda", "disinformation"],
    }
    for dim, src_domains in dim_map.items():
        values = [domain_intensities.get(domain, 0.0) for domain in src_domains]
        setattr(assessment.threat_dimensions, dim, round(max(values) if values else 0.0, 3))

    max_dim = _max_dimension(assessment)
    assessment.overall_threat_level = _level_from_score(max_dim)
    assessment.overall_confidence = round(
        sum(h.confidence for h in session.hypotheses) / len(session.hypotheses),
        3,
    ) if session.hypotheses else 0.5

    assessment.collection_gaps = (
        list(session.missing_signals[:6])
        if session.missing_signals else ["No critical collection gaps identified."]
    )
    assessment.unknown_factors = (
        list(getattr(session.state_context, "data_blindspots", []) or [])[:5]
        or ["Adversary intent certainty", "Third-party reactions", "Covert operations"]
    )

    signal_count = len(signals)
    if signal_count > 20:
        assessment.timeline_events = [
            "Accelerating signal density suggests active crisis development",
            "Monitor for indicator threshold crossing within 72 hours",
        ]
    elif signal_count > 10:
        assessment.timeline_events = ["Moderate signal activity: situation developing at normal pace"]
    else:
        assessment.timeline_events = ["Low signal density: situation may be early-stage or de-escalating"]

    assessment.forecast_24h = round(max_dim * 0.9, 3)
    assessment.forecast_7d = round(max_dim * 0.85, 3)
    assessment.forecast_30d = round(max_dim * 0.7, 3)

    if assessment.overall_threat_level == "HIGH":
        assessment.recommendations = [
            "Escalate to senior leadership immediately",
            "Activate crisis monitoring cell with 24/7 staffing",
            "Prepare contingency options for rapid diplomatic and defensive response",
        ]
    elif assessment.overall_threat_level == "ELEVATED":
        assessment.recommendations = [
            "Increase monitoring frequency to 6-hour cycles",
            "Brief key allies on emerging situation",
            "Review and update contingency plans",
        ]
    else:
        assessment.recommendations = [
            "Continue routine monitoring at 24-hour cycle",
            "Update country assessment file with current findings",
            "No immediate action required; maintain watch posture",
        ]

    assessment.alternative_hypotheses = (
        valid_hypotheses if valid_hypotheses
        else ["Routine seasonal training exercise", "Domestic political signaling", "Economic negotiation posture"]
    )
    return assessment


def _build_llm_refinement(session, signals, valid_hypotheses, heuristic: IntelligenceAssessment) -> IntelligenceAssessment | None:
    prompt = (
        "You are a senior intelligence synthesizer. The deterministic assessment below is the rail.\n"
        "You may refine unknowns, collection gaps, timeline events, forecasts, and recommendations using only the provided signals.\n"
        "Do not change any threat dimension by more than +/-0.15 unless the signals contain a critical indicator.\n"
        "Return JSON matching IntelligenceAssessment exactly.\n\n"
        f"DETERMINISTIC_ASSESSMENT:\n{heuristic.model_dump_json(indent=2)}\n\n"
        f"SIGNALS:\n{[s.model_dump(mode='json') for s in signals]}\n\n"
        f"RED_TEAM_ALTERNATIVES:\n{valid_hypotheses}\n"
    )
    return structured_completion(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        output_model=IntelligenceAssessment,
        temperature=0.1,
        max_tokens=900,
    )


def _merge_bounded_assessment(
    heuristic: IntelligenceAssessment,
    llm: IntelligenceAssessment,
) -> DualModeAssessment:
    final = deepcopy(llm)
    disagreements = []
    resolution = "llm_refined_within_bounds"

    for dim in ["military", "diplomatic", "economic", "cyber", "information"]:
        h_val = float(getattr(heuristic.threat_dimensions, dim))
        l_val = float(getattr(llm.threat_dimensions, dim))
        delta = l_val - h_val
        if abs(delta) > 0.15:
            disagreements.append(f"{dim} difference > 0.15 (Heuristic={h_val:.2f}, LLM={l_val:.2f})")
            resolution = "bounded_llm_refinement"
        
        bounded_delta = max(-0.15, min(0.15, delta))
        setattr(final.threat_dimensions, dim, round(max(0.0, min(1.0, h_val + bounded_delta)), 3))

    max_dim = _max_dimension(final)
    final.overall_threat_level = _level_from_score(max_dim)
    
    h_conf = float(heuristic.overall_confidence or 0.0)
    l_conf = float(llm.overall_confidence or 0.0)
    conf_delta = l_conf - h_conf
    if abs(conf_delta) > 0.2:
         disagreements.append(f"Confidence difference > 0.2 (Heuristic={h_conf:.2f}, LLM={l_conf:.2f})")
    
    final.overall_confidence = round(min(l_conf, h_conf + 0.15), 3)
    final.positive_evidence = heuristic.positive_evidence
    final.negative_evidence = heuristic.negative_evidence
    final.assessment_stability = "Dual-mode bounded LLM refinement"
    
    agreement = round(max(0.0, 1.0 - (len(disagreements) * 0.15)), 3)
    
    return DualModeAssessment(
        heuristic_result=heuristic,
        llm_result=llm,
        final=final,
        agreement_score=agreement,
        disagreements=disagreements,
        resolution_action=resolution,
        confidence_adjustment=final.overall_confidence - h_conf
    )


def _max_dimension(assessment: IntelligenceAssessment) -> float:
    return max(
        assessment.threat_dimensions.military,
        assessment.threat_dimensions.diplomatic,
        assessment.threat_dimensions.economic,
        assessment.threat_dimensions.cyber,
        assessment.threat_dimensions.information,
    )


def _level_from_score(score: float) -> str:
    if score >= 0.8:
        return "CRITICAL"
    if score >= 0.6:
        return "HIGH"
    if score >= 0.4:
        return "ELEVATED"
    if score >= 0.2:
        return "MODERATE"
    return "LOW"


def _finalize(session, assessment: IntelligenceAssessment) -> None:
    from dip.decision.consistency_checker import validate_assessment

    try:
        validate_assessment(assessment)
    except ValueError as exc:
        logger.error(str(exc))
        assessment.assessment_stability = f"Unstable: {exc}"
    session.final_decision = assessment.model_dump_json(indent=2)
