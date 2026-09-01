"""Strategic perception: how DIP 2.0 sees and feels the world.

The model is computational, not emotional.  It converts world-model signals
into pressure channels useful to a head-of-country briefing: tension,
uncertainty, urgency, fragility, surprise, opportunity, and constraint.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from pydantic import BaseModel, Field


def _clip01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return max(0.0, min(1.0, float(default)))


def _mean(values: Iterable[float], default: float = 0.0) -> float:
    clean = [_clip01(value) for value in values]
    if not clean:
        return _clip01(default)
    return _clip01(sum(clean) / len(clean))


def _signal_action(signal: Any) -> str:
    if isinstance(signal, dict):
        return str(signal.get("action") or signal.get("signal") or signal.get("name") or "").upper()
    return str(getattr(signal, "action", "") or getattr(signal, "signal", "") or getattr(signal, "name", "")).upper()


def _signal_confidence(signal: Any) -> float:
    if isinstance(signal, dict):
        return _clip01(signal.get("confidence", 0.0))
    return _clip01(getattr(signal, "confidence", 0.0))


def _signal_intensity(signal: Any) -> float:
    if isinstance(signal, dict):
        return _clip01(signal.get("intensity", signal.get("membership", 0.0)))
    return _clip01(getattr(signal, "intensity", getattr(signal, "membership", 0.0)))


class StrategicPressure(BaseModel):
    """Computed advisory pressure state."""

    tension: float = 0.0
    uncertainty: float = 0.0
    urgency: float = 0.0
    fragility: float = 0.0
    surprise: float = 0.0
    opportunity: float = 0.0
    constraint: float = 0.0
    diplomatic_window: float = 0.0
    drivers: List[str] = Field(default_factory=list)
    blindspots: List[str] = Field(default_factory=list)

    @property
    def pulse(self) -> str:
        if self.urgency >= 0.75 or self.tension >= 0.80:
            return "volatile"
        if self.tension >= 0.60:
            return "rising"
        if self.opportunity >= 0.55 and self.diplomatic_window >= 0.45:
            return "diplomatic-window"
        return "stable-watch"


def compute_strategic_pressure(state_context: Any, result: Dict[str, Any] | None = None) -> StrategicPressure:
    """Compute a pressure vector from StateContext and current pipeline result."""

    result = dict(result or {})
    nextgen_sre = result.get("nextgen_sre") if isinstance(result.get("nextgen_sre"), dict) else {}
    signals = list(getattr(state_context, "current_signals", []) or result.get("signals", []) or [])
    escalation = getattr(state_context, "escalation", None)
    escalation_score = _clip01(
        nextgen_sre.get("sre_escalation_score", getattr(escalation, "escalation_score", result.get("sre_escalation_score", 0.0)))
    )
    confidence_decay = _clip01(getattr(state_context, "confidence_decay", result.get("confidence_decay", 1.0)), 1.0)
    blindspots = list(getattr(state_context, "data_blindspots", []) or result.get("data_blindspots", []) or [])

    weighted_signals = [_signal_confidence(sig) * max(_signal_intensity(sig), 0.25) for sig in signals]
    signal_pressure = _mean(weighted_signals, default=escalation_score)

    actions = [_signal_action(sig) for sig in signals]
    high_urgency_tokens = ("MOBIL", "LOGISTICS", "CLASH", "KINETIC", "MISSILE", "WMD", "CYBER")
    diplomatic_tokens = ("DIPLOMACY", "NEGOTIATION", "TALK", "DEESCALATION", "CHANNEL")
    constraint_tokens = ("SANCTION", "ECON", "LEGAL", "TREATY", "COST", "PRESSURE")

    urgent_count = sum(1 for action in actions if any(token in action for token in high_urgency_tokens))
    diplomatic_count = sum(1 for action in actions if any(token in action for token in diplomatic_tokens))
    constraint_count = sum(1 for action in actions if any(token in action for token in constraint_tokens))

    threat = str(result.get("threat_level") or nextgen_sre.get("risk_level") or getattr(escalation, "threat_level", "LOW")).upper()
    threat_bias = {"LOW": 0.15, "ELEVATED": 0.45, "HIGH": 0.72, "CRITICAL": 0.92}.get(threat, 0.35)

    uncertainty = _clip01((1.0 - confidence_decay) + min(0.35, len(blindspots) * 0.08))
    urgency = _clip01((0.45 * threat_bias) + (0.35 * min(1.0, urgent_count / 4.0)) + (0.20 * escalation_score))
    tension = _clip01((0.55 * escalation_score) + (0.30 * signal_pressure) + (0.15 * threat_bias))
    constraint = _clip01(min(1.0, constraint_count / 4.0))
    diplomatic_window = _clip01(min(1.0, diplomatic_count / 3.0) * (1.0 - min(tension, 0.85)))
    opportunity = _clip01((0.65 * diplomatic_window) + (0.35 * (1.0 - tension)) - (0.25 * urgency))
    fragility = _clip01((0.45 * tension) + (0.35 * uncertainty) + (0.20 * urgency))
    surprise = _clip01(max(0.0, signal_pressure - escalation_score) + min(0.25, len(blindspots) * 0.03))

    drivers = []
    for signal in sorted(signals, key=lambda item: _signal_confidence(item), reverse=True)[:6]:
        action = _signal_action(signal)
        if action:
            drivers.append(action)

    return StrategicPressure(
        tension=tension,
        uncertainty=uncertainty,
        urgency=urgency,
        fragility=fragility,
        surprise=surprise,
        opportunity=opportunity,
        constraint=constraint,
        diplomatic_window=diplomatic_window,
        drivers=drivers,
        blindspots=blindspots,
    )


def build_fuzzy_trace(state_context: Any, result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Expose fuzzy-like memberships using available dip 2.0 structures."""

    result = dict(result or {})
    nextgen_sre = result.get("nextgen_sre") if isinstance(result.get("nextgen_sre"), dict) else None
    if nextgen_sre:
        return {
            "fuzzy_memberships": nextgen_sre.get("fuzzy_memberships", {}),
            "signal_beliefs": nextgen_sre.get("signal_beliefs", []),
            "projected_signals": nextgen_sre.get("projected_signals", []),
            "sre_domains": nextgen_sre.get("sre_domains", {}),
            "sre_input": nextgen_sre.get("sre_input", {}),
            "sre_escalation_score": _clip01(nextgen_sre.get("sre_escalation_score", 0.0)),
            "risk_level": nextgen_sre.get("risk_level", "LOW"),
            "qualitative_bands": nextgen_sre.get("qualitative_bands", {}),
            "escalation_trace": nextgen_sre.get("escalation_trace", []),
            "legal_firewall_rejections": nextgen_sre.get("legal_firewall_rejections", []),
        }
    signals = list(getattr(state_context, "current_signals", []) or [])
    beliefs = list(getattr(state_context, "beliefs", []) or [])
    escalation = getattr(state_context, "escalation", None)
    domains = getattr(escalation, "domain_indices", None)

    return {
        "signal_beliefs": [
            {
                "signal": str(getattr(belief, "signal_code", "")),
                "membership": _clip01(getattr(belief, "support_score", 0.0)),
                "level": str(getattr(belief, "belief_level", "")),
                "sources": int(getattr(belief, "source_count", 0) or 0),
            }
            for belief in beliefs
        ],
        "projected_signals": [
            {
                "signal": _signal_action(signal),
                "confidence": _signal_confidence(signal),
                "membership": _signal_intensity(signal),
                "domain": str(getattr(signal, "domain", "unknown") if not isinstance(signal, dict) else signal.get("domain", "unknown")),
            }
            for signal in signals
        ],
        "sre_domains": {
            "capability": _clip01(getattr(domains, "capability", 0.0)),
            "intent": _clip01(getattr(domains, "intent", 0.0)),
            "instability": _clip01(getattr(domains, "instability", 0.0)),
            "cost": _clip01(getattr(domains, "cost", 0.0)),
        },
        "sre_escalation_score": _clip01(getattr(escalation, "escalation_score", result.get("sre_escalation_score", 0.0))),
        "risk_level": result.get("threat_level") or getattr(escalation, "threat_level", "LOW"),
    }
