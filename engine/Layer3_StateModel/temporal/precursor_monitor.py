from __future__ import annotations

from typing import Any, Dict


class PrecursorMonitor:
    """
    Flags short-notice precursor patterns (flashpoint risk).
    """

    def evaluate(self, state_context: Dict[str, Any] | Any) -> Dict[str, Any]:
        state = dict(state_context or {})
        capability = dict(state.get("capability", {}) or {})
        meta = dict(state.get("meta", {}) or {})

        evacuation = str(capability.get("evacuation_activity", "none") or "none").strip().lower()
        cyber = str(capability.get("cyber_activity", "none") or "none").strip().lower()
        mobilization = str(capability.get("troop_mobilization", "none") or "none").strip().lower()
        intensity = float(meta.get("signal_intensity", 0.0) or 0.0)
        volatility = float(meta.get("event_volatility", 0.0) or 0.0)

        if evacuation == "active":
            return {
                "level": "CRITICAL",
                "message": "Embassy/consular evacuation activity detected.",
                "window": "24-72h",
            }

        if cyber == "high" and mobilization == "high":
            return {
                "level": "CRITICAL",
                "message": "Concurrent cyber spike and force mobilization detected.",
                "window": "24-72h",
            }

        if cyber == "high" or (intensity > 0.75 and volatility > 0.65):
            return {
                "level": "WARNING",
                "message": "Pre-operation risk indicators are elevated.",
                "window": "72h+",
            }

        return {"level": "NORMAL", "message": "No immediate precursor alarm."}


__all__ = ["PrecursorMonitor"]
