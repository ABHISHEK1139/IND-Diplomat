"""
Contagion Engine (Layer 7)
==========================
Uses Mesa Agent-Based Modeling to simulate how conflicts spread across theaters
via geopolitical and economic interdependence.
"""

import logging
from typing import Dict
from dip.layer7_global.interdependence_matrix import COUPLING_MATRIX, get_neighbors

try:
    from mesa import Agent, Model
    from mesa.time import SimultaneousActivation
except ImportError:
    Agent = object
    Model = object
    SimultaneousActivation = None

logger = logging.getLogger("Layer7.contagion")


class CountryAgent(Agent):
    """An agent representing a country in the geopolitical network."""
    def __init__(self, unique_id: str, model: Model, initial_shock: float = 0.0):
        super().__init__(unique_id, model)
        self.escalation_score = initial_shock
        self.next_escalation_score = initial_shock
        
    def step(self):
        """Calculate the contagion effect from neighbors."""
        neighbors = get_neighbors(self.unique_id)
        contagion_sum = 0.0
        
        for neighbor_id, weight in neighbors:
            # Find the neighbor agent
            neighbor_agent = next((a for a in self.model.schedule.agents if a.unique_id == neighbor_id), None)
            if neighbor_agent:
                # Contagion decay factor
                spillover = neighbor_agent.escalation_score * weight * 0.25
                contagion_sum += spillover
                
        # Agent absorbs shock but it naturally decays over time
        new_score = self.escalation_score + contagion_sum
        new_score = new_score * 0.90 # Natural decay
        self.next_escalation_score = min(1.0, round(new_score, 3))
        
    def advance(self):
        """Apply the calculated state."""
        self.escalation_score = self.next_escalation_score


class GlobalContagionModel(Model):
    """A Mesa model simulating global geopolitical contagion."""
    def __init__(self, initial_escalations: Dict[str, float]):
        super().__init__()
        self.schedule = SimultaneousActivation(self)
        
        # Build all agents mentioned in the initial state or coupling matrix
        all_countries = set(initial_escalations.keys())
        for a, b in COUPLING_MATRIX.keys():
            all_countries.add(a)
            all_countries.add(b)
            
        for cc in all_countries:
            shock = initial_escalations.get(cc, 0.0)
            agent = CountryAgent(cc, self, shock)
            self.schedule.add(agent)
            
    def step(self):
        self.schedule.step()


def run_global_cycle(all_escalations: Dict[str, float], steps: int = 3) -> Dict[str, float]:
    """
    Run the agent-based simulation for N steps to see where the contagion settles.
    Returns the final predicted escalation scores for all countries.
    """
    if SimultaneousActivation is None:
        logger.error("Mesa not installed. Returning initial escalations.")
        return all_escalations

    model = GlobalContagionModel(all_escalations)
    
    # Run the simulation
    for _ in range(steps):
        model.step()
        
    final_scores = {}
    for agent in model.schedule.agents:
        if agent.escalation_score > 0.1: # Only report meaningful spillover
            final_scores[agent.unique_id] = agent.escalation_score
            
    return final_scores
