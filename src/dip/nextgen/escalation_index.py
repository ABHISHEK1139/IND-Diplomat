"""Compute an escalation index from domain fusion and optional temporal bonuses."""
from __future__ import annotations

from typing import Dict, Any


def compute_escalation(domain_scores: Dict[str, float], temporal_bonus: float = 0.0) -> Dict[str, Any]:
    """Return escalation_score in [0,1] and a threat_level string."""
    capability = float(domain_scores.get("capability", 0.0))
    intent = float(domain_scores.get("intent", 0.0))
    stability = float(domain_scores.get("stability", 0.0))
    cost = float(domain_scores.get("cost", 0.0))

    # heuristic composite
    base = 0.5 * intent + 0.3 * capability + 0.1 * stability + 0.1 * cost
    score = max(0.0, min(1.0, base + float(temporal_bonus)))

    if score >= 0.8:
        level = "CRITICAL"
    elif score >= 0.6:
        level = "HIGH"
    elif score >= 0.35:
        level = "ELEVATED"
    else:
        level = "LOW"

    return {"escalation_score": round(score, 3), "threat_level": level, "inputs": domain_scores}
