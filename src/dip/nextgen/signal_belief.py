"""Signal belief model: converts observed signals into belief objects and scores."""
from __future__ import annotations

from typing import Dict
from .observed_signal import ObservedSignal


class SignalBeliefModel:
    """Compute a simple corroboration/support score and belief level.

    The algorithm is intentionally lightweight and explainable:
    - support_score = intensity * confidence
    - belief_level mapped: <0.25 weak, <0.6 moderate, >=0.6 strong
    """

    @staticmethod
    def from_observed(sig: ObservedSignal) -> Dict[str, object]:
        intensity = max(0.0, min(1.0, float(sig.intensity or 0.0)))
        confidence = max(0.0, min(1.0, float(sig.confidence or 0.0)))
        support = intensity * confidence

        if support < 0.25:
            level = "weak"
        elif support < 0.6:
            level = "moderate"
        else:
            level = "strong"

        return {
            "signal_code": f"{sig.entity}:{sig.action}",
            "support_score": round(support, 3),
            "belief_level": level,
            "source": sig.source,
            "domain": sig.domain,
        }
