"""
Threat synthesizer for causal council mode.

In Phase-3, threat determination is computed by coordinator-level
causal precondition coverage. The synthesizer now acts as a pass-through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ThreatAssessment:
    level: str
    score: float
    summary: str
    synthesis_logic: str = ""
    primary_drivers: List[str] = field(default_factory=list)


class ThreatSynthesizer:
    """
    Compatibility adapter.
    """

    def synthesize(self, session: Any, *args, **kwargs) -> Any:
        _ = kwargs
        state_context = getattr(session, "state_context", None)
        if state_context is not None:
            state_risk = str(getattr(state_context, "risk_level", "") or "").strip().upper()
            if state_risk:
                return state_risk

        if hasattr(session, "final_decision") or hasattr(session, "king_decision"):
            return str(getattr(session, "final_decision", getattr(session, "king_decision", "LOW")) or "LOW")

        # Legacy fallback path for ad-hoc scripts that still call
        # synthesize(reports, observed_signals, ...).
        reports = list(session or [])
        observed_signals = list(args[0] if args else [])
        support = 0.0
        if reports:
            support = min(1.0, len(observed_signals) / max(len(reports), 1))
        level = "LOW"
        if support >= 0.70:
            level = "HIGH"
        elif support >= 0.50:
            level = "ELEVATED"
        return ThreatAssessment(
            level=level,
            score=support,
            summary=f"{level}: legacy compatibility synthesis",
            synthesis_logic=f"support={support:.3f}",
            primary_drivers=[str(item) for item in observed_signals[:3]],
        )


__all__ = [
    "ThreatAssessment",
    "ThreatSynthesizer",
]
