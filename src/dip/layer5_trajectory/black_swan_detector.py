"""
Black Swan Detector (Layer 5)
=============================
Detects discontinuity events that invalidate smooth-trend assumptions.
"""

from dip.core.schema import BlackSwanResult
from dip.layer4_reasoning.council_session import CouncilSession
import logging

logger = logging.getLogger("Layer5.black_swan")

RARE_HIGH_IMPACT_SIGNALS = {
    "SIG_WMD_RISK",
    "SIG_ALLIANCE_INVOCATION",
    "SIG_MASS_MOBILIZATION",
    "SIG_REGIME_COLLAPSE",
}

def detect_black_swan(session: CouncilSession) -> dict:
    ctx = session.state_context
    result = BlackSwanResult()
    
    # Channel 1: Spike Severity
    max_spike = max((i.spike_severity for i in ctx.temporal_indicators if i.is_spike), default=0.0)
    if max_spike >= 3.5:
        result.triggered = True
        result.channels_fired.append("SPIKE_SEVERITY")
        result.reasons.append(f"Extreme statistical anomaly detected (sigma: {max_spike})")

    # Channel 2: Structural Discontinuity (velocity check)
    # Re-calculate simple velocity
    velocity = 0.0
    if ctx.temporal_indicators:
        velocity = sum(i.momentum for i in ctx.temporal_indicators) / len(ctx.temporal_indicators)
        
    if abs(velocity) > 0.6:
        result.triggered = True
        result.channels_fired.append("STRUCTURAL_DISCONTINUITY")
        result.reasons.append(f"Massive trajectory shift detected (velocity: {velocity:.2f})")

    # Channel 3: Rare High-Impact Signals
    for s in ctx.current_signals:
        if s.action in RARE_HIGH_IMPACT_SIGNALS and s.confidence > 0.85:
            result.triggered = True
            result.channels_fired.append("RARE_HIGH_IMPACT_SIGNAL")
            result.reasons.append(f"High-confidence detection of rare event: {s.action}")

    if result.triggered:
        result.escalation_boost = 0.20
        result.trajectory_floor = 0.70
        result.confidence_cap = 0.60
        result.mandatory_review = True
        
    return result.model_dump()
