"""
Layer 4 SRE Parity Modules — Counterfactual, Curiosity, Epistemic, Gap, War Index, Withheld
============================================================================================

Combined module: all remaining Layer 4 SRE parity components from DIP_8.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger("Layer4_Reasoning.sre_parity")


# ═══════════════════════════════════════════════════════════════
# Counterfactual Engine — "What if we removed minister X?"
# ═══════════════════════════════════════════════════════════════

def run_counterfactual(
    session: Any,
    remove_minister: str,
) -> Dict[str, Any]:
    """Recompute council decision without a specific minister.

    Args:
        session: CouncilSession with hypotheses
        remove_minister: Minister name to exclude

    Returns:
        {original_decision, counterfactual_decision, impact, minister_influence}
    """
    hyps = getattr(session, "hypotheses", [])
    if isinstance(hyps, list) and hyps and not hasattr(hyps[0], "minister"):
        hyps = [type("h", (), {"minister": h.get("minister", ""), "confidence": h.get("confidence", 0)})() for h in hyps]

    original_confidences = [h.confidence for h in hyps]
    original_avg = np.mean(original_confidences) if original_confidences else 0.0

    filtered = [h for h in hyps if h.minister != remove_minister]
    filtered_confidences = [h.confidence for h in filtered]
    filtered_avg = np.mean(filtered_confidences) if filtered_confidences else 0.0

    impact = original_avg - filtered_avg

    return {
        "original_avg_confidence": round(original_avg, 4),
        "counterfactual_avg_confidence": round(filtered_avg, 4),
        "impact": round(impact, 4),
        "minister_influence": "high" if abs(impact) > 0.1 else "moderate" if abs(impact) > 0.05 else "low",
        "removed_minister": remove_minister,
    }


# ═══════════════════════════════════════════════════════════════
# Curiosity Controller — What should we investigate next?
# ═══════════════════════════════════════════════════════════════

def generate_curiosity_questions(
    session: Any,
    max_questions: int = 5,
) -> List[Dict[str, Any]]:
    """Generate curiosity-driven investigation questions.

    Based on: gaps between minister confidences, missing signals, low-confidence areas.
    """
    hyps = getattr(session, "hypotheses", [])
    missing = getattr(session, "missing_signals", [])

    if isinstance(hyps, list) and hyps and not hasattr(hyps[0], "minister"):
        hyps = [type("h", (), {"minister": h.get("minister", ""), "confidence": h.get("confidence", 0), "hypothesis_type": h.get("type", "")})() for h in hyps]

    questions = []

    # High spread → ask about disagreement
    confidences = [h.confidence for h in hyps]
    if len(confidences) >= 2 and max(confidences) - min(confidences) > 0.4:
        high = max(hyps, key=lambda h: h.confidence)
        low = min(hyps, key=lambda h: h.confidence)
        questions.append({
            "question": f"Why does {high.minister} ({high.confidence:.0%}) disagree with {low.minister} ({low.confidence:.0%})?",
            "type": "disagreement",
            "priority": 0.9,
        })

    # Missing signals → ask about collection
    for sig in missing[:3]:
        questions.append({
            "question": f"What additional evidence would confirm or refute '{sig}'?",
            "type": "collection_gap",
            "priority": 0.7,
        })

    # Low confidence → ask about corroboration
    low_conf = [h for h in hyps if h.confidence < 0.5]
    for h in low_conf[:2]:
        questions.append({
            "question": f"What evidence would increase confidence in {h.minister}'s assessment?",
            "type": "confidence_gap",
            "priority": 0.5,
        })

    return sorted(questions, key=lambda q: q["priority"], reverse=True)[:max_questions]


# ═══════════════════════════════════════════════════════════════
# Epistemic Needs — What evidence would change the conclusion?
# ═══════════════════════════════════════════════════════════════

def assess_epistemic_needs(
    session: Any,
    threat_level: str = "UNKNOWN",
) -> Dict[str, Any]:
    """Determine what evidence would most change the current assessment.
    
    Returns the information with highest expected value of information (EVOI).
    """
    missing = getattr(session, "missing_signals", [])
    evidence_log = getattr(session, "evidence_log", [])

    needs = {
        "critical_gaps": [],
        "high_value_targets": [],
        "evoi_ranked": [],
    }

    for sig in missing[:10]:
        if any(word in sig.lower() for word in ["military", "troop", "deploy", "mobilize"]):
            needs["critical_gaps"].append({"signal": sig, "reason": "Military-related — directly impacts escalation assessment"})
        elif any(word in sig.lower() for word in ["diplomatic", "treaty", "sanction"]):
            needs["high_value_targets"].append({"signal": sig, "reason": "Diplomatic/economic — impacts intent and cost domains"})

    needs["evoi_ranked"] = needs["critical_gaps"] + needs["high_value_targets"]

    return needs


# ═══════════════════════════════════════════════════════════════
# Gap Engine — Intelligence gap detection and prioritization
# ═══════════════════════════════════════════════════════════════

def detect_intelligence_gaps(
    sre_domains: Dict[str, float],
    verification_score: float,
    missing_signals: List[str],
) -> Dict[str, Any]:
    """Detect and prioritize intelligence gaps across domains."""
    gaps = {}

    for domain, score in sre_domains.items():
        if score < 0.3:
            gaps[domain] = {"status": "critical_gap", "score": score, "priority": "CRITICAL"}
        elif score < 0.5:
            gaps[domain] = {"status": "significant_gap", "score": score, "priority": "HIGH"}
        else:
            gaps[domain] = {"status": "adequate", "score": score, "priority": "LOW"}

    return {
        "domain_gaps": gaps,
        "verification_gap": verification_score < 0.55,
        "missing_signals_count": len(missing_signals),
        "overall_assessment": "insufficient" if any(g["priority"] == "CRITICAL" for g in gaps.values()) else "adequate",
    }


# ═══════════════════════════════════════════════════════════════
# War Index — War probability computation
# ═══════════════════════════════════════════════════════════════

def compute_war_index(
    capability: float,
    intent: float,
    stability: float,
    cost: float,
    trend_bonus: float = 0.0,
    active_conflicts: int = 0,
) -> Dict[str, Any]:
    """Compute a war probability index from domain indices.

    Formula: weighted geometric mean with conflict floor and trend amplifier.
    """
    weights = {"capability": 0.35, "intent": 0.30, "stability": 0.15, "cost": 0.20}

    # Weighted geometric mean
    log_sum = (
        weights["capability"] * np.log(max(0.01, capability)) +
        weights["intent"] * np.log(max(0.01, intent)) +
        weights["stability"] * np.log(max(0.01, stability)) +
        weights["cost"] * np.log(max(0.01, cost))
    )
    base_index = np.exp(log_sum)

    # Trend amplifier
    index = base_index * (1.0 + trend_bonus)

    # Conflict floor
    if active_conflicts > 0:
        index = max(index, 0.35)

    # Clamp
    index = round(max(0.0, min(1.0, index)), 4)

    if index < 0.20:
        level = "LOW"
    elif index < 0.40:
        level = "ELEVATED"
    elif index < 0.65:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return {
        "war_index": index,
        "level": level,
        "components": {
            "capability_contribution": round(weights["capability"] * capability, 4),
            "intent_contribution": round(weights["intent"] * intent, 4),
            "stability_contribution": round(weights["stability"] * stability, 4),
            "cost_contribution": round(weights["cost"] * cost, 4),
            "trend_amplifier": round(trend_bonus, 4),
        },
    }
