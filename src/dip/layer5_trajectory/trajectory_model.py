"""
Trajectory Model (Layer 5)
==========================
Forecasts the escalation path over 14, 30, and 60 days.
"""

from dip.core.schema import TrajectoryForecast
from dip.core.fuzzy import rising, _clamp
from dip.layer4_reasoning.council_session import CouncilSession

def compute_trajectory(session: CouncilSession) -> dict:
    ctx = session.state_context
    esc_result = ctx.escalation
    if not esc_result:
        return TrajectoryForecast().model_dump()
        
    current_esc = esc_result.escalation_score
    
    # Compute base velocity from temporal indicators
    avg_momentum = 0.0
    avg_persistence = 0.0
    spike_boost = 0.0
    
    indicators = ctx.temporal_indicators
    if indicators:
        avg_momentum = sum(i.momentum for i in indicators) / len(indicators)
        avg_persistence = sum(i.persistence for i in indicators) / len(indicators)
        spike_count = sum(1 for i in indicators if i.is_spike)
        spike_boost = min(0.15, spike_count * 0.05)
        
    velocity = avg_momentum * (avg_persistence + 0.5)
    
    # Phase transition detection (fuzzy)
    transition_factor = rising(abs(velocity), 0.1, 0.5)
    
    # Forecasts (14d, 30d, 60d)
    # Simple linear extrapolation with decay/acceleration
    p_14 = _clamp(current_esc + (velocity * 1.0) + spike_boost)
    p_30 = _clamp(current_esc + (velocity * 2.0) + spike_boost)
    p_60 = _clamp(current_esc + (velocity * 3.5) + spike_boost)
    
    if velocity > 0.05 or (velocity > 0 and transition_factor > 0.5):
        label = "ESCALATING"
    elif velocity < -0.05:
        label = "DE_ESCALATING"
    else:
        label = "STABLE"
        
    forecast = TrajectoryForecast(
        prob_14d=round(p_14, 3),
        prob_30d=round(p_30, 3),
        prob_60d=round(p_60, 3),
        velocity=round(velocity, 4),
        trajectory_label=label
    )
    
    return forecast.model_dump()
