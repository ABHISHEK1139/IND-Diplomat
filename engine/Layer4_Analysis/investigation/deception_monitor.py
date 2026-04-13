from __future__ import annotations

from typing import Any, Dict


class DeceptionMonitor:
    """
    Detects capability-intent mismatch patterns.
    """

    def evaluate(self, state_context: Dict[str, Any] | Any) -> Dict[str, Any]:
        state = dict(state_context or {})
        diplomatic = dict(state.get("diplomatic", {}) or {})
        capability = dict(state.get("capability", {}) or {})

        intent = str(diplomatic.get("official_stance", "unknown") or "unknown").strip().lower()
        mobilization = str(capability.get("troop_mobilization", "none") or "none").strip().lower()
        logistics = str(capability.get("logistics_activity", "none") or "none").strip().lower()
        stockpiling = str(capability.get("supply_stockpiling", "none") or "none").strip().lower()
        evacuation = str(capability.get("evacuation_activity", "none") or "none").strip().lower()
        cyber = str(capability.get("cyber_activity", "none") or "none").strip().lower()

        if intent == "peaceful" and (
            mobilization == "high"
            or logistics == "high"
            or stockpiling == "high"
            or evacuation == "active"
        ):
            return {
                "level": "HIGH",
                "type": "CAPABILITY_INTENT_MISMATCH",
                "message": "Military preparation contradicts diplomatic stance.",
                "intent": intent,
                "capability_snapshot": {
                    "troop_mobilization": mobilization,
                    "logistics_activity": logistics,
                    "supply_stockpiling": stockpiling,
                    "cyber_activity": cyber,
                    "evacuation_activity": evacuation,
                },
            }

        if cyber == "high" and intent == "peaceful":
            return {
                "level": "MEDIUM",
                "type": "CYBER_INTENT_MISMATCH",
                "message": "Cyber activity is elevated despite peaceful messaging.",
                "intent": intent,
            }

        return {"level": "LOW", "type": "NONE", "message": "No deception pattern detected."}


__all__ = ["DeceptionMonitor"]
