"""
War Gaming Simulation Engine (Layer 8)
======================================
Monte Carlo style simulation loop projecting downstream trajectories.
"""

import random
from typing import Dict, Any
from dip.core.schema import StateContext

def run_simulation(context: StateContext, num_iterations: int = 1000) -> Dict[str, Any]:
    """
    Runs a Monte Carlo style simulation using heuristics to project 3 trajectories:
    'Status Quo', 'Escalation', 'De-escalation'.
    Returns probabilities and outcomes for each.
    """
    escalation_score = context.escalation.escalation_score if context.escalation else 0.0
    
    results = {
        "Escalation": 0,
        "Status Quo": 0,
        "De-escalation": 0
    }
    
    for _ in range(num_iterations):
        # Heuristic rules:
        # A random roll modified by the current escalation score
        roll = random.random()
        
        # Determine thresholds based on escalation score
        # e.g., if escalation_score = 0.8, Escalation threshold is high
        escalate_thresh = max(0.1, 0.3 + (escalation_score * 0.4))
        deescalate_thresh = max(0.1, 0.4 - (escalation_score * 0.3))
        
        if roll < escalate_thresh:
            results["Escalation"] += 1
        elif roll < escalate_thresh + deescalate_thresh:
            results["De-escalation"] += 1
        else:
            results["Status Quo"] += 1
            
    probabilities = {
        k: v / num_iterations for k, v in results.items()
    }
    
    outcomes = {
        "Escalation": {
            "description": "Conflict intensity increases, broader mobilization likely.",
            "expected_escalation_shift": "+0.15"
        },
        "Status Quo": {
            "description": "Current trajectory maintained, tense but stable.",
            "expected_escalation_shift": "0.00"
        },
        "De-escalation": {
            "description": "Tensions cool, diplomatic off-ramps are taken.",
            "expected_escalation_shift": "-0.15"
        }
    }
    
    return {
        "trajectories": {
            "Escalation": {
                "probability": probabilities["Escalation"],
                "outcome": outcomes["Escalation"]
            },
            "Status Quo": {
                "probability": probabilities["Status Quo"],
                "outcome": outcomes["Status Quo"]
            },
            "De-escalation": {
                "probability": probabilities["De-escalation"],
                "outcome": outcomes["De-escalation"]
            }
        },
        "most_likely_trajectory": max(probabilities.items(), key=lambda x: x[1])[0]
    }
