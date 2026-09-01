"""
Uncertainty Monitor (Layer 3)
=============================
Scans the current system state for data blindspots (e.g. OSINT feeds failing)
and mathematically decays the system's confidence to prevent hallucinations.
"""

import logging
from dip.core.schema import StateContext

logger = logging.getLogger("Layer3.uncertainty")

def apply_uncertainty_decay(context: StateContext) -> StateContext:
    """
    Checks if there are surprisingly few observations or missing signals,
    and penalizes the confidence if the system is flying blind.
    """
    blindspots = []
    decay = 1.0
    
    # 1. Observation Volume Check
    # If the system only found < 3 observations, it's dangerously uninformed.
    if context.observation_count == 0:
        decay *= 0.3
        blindspots.append("CRITICAL: Zero live observations retrieved. Sensors may be blocked or offline.")
    elif context.observation_count < 3:
        decay *= 0.6
        blindspots.append("WARNING: Extremely low observation volume. Situation awareness is compromised.")
        
    # 2. Domain Missing Check
    # A healthy scan should see at least some economic and diplomatic activity.
    domains_seen = {s.domain for s in context.current_signals}
    if "diplomatic" not in domains_seen and context.observation_count > 0:
        decay *= 0.9
        blindspots.append("Notice: No diplomatic signals detected. Possible communications blackout.")
        
    if "economic" not in domains_seen and context.observation_count > 0:
        decay *= 0.9
        blindspots.append("Notice: No economic data retrieved.")

    # Apply to context
    context.confidence_decay = max(0.1, round(decay, 2))
    context.data_blindspots = blindspots
    
    if blindspots:
        logger.warning(f"Uncertainty Monitor triggered {len(blindspots)} blindspots. Confidence capped at {context.confidence_decay}")
        
    return context
