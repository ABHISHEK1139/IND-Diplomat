import logging
from typing import Dict, Any, List
import random

try:
    from mesa import Agent, Model
    from mesa.time import RandomActivation
except ImportError:
    Agent, Model, RandomActivation = object, object, None

logger = logging.getLogger("DIP3.Layer5.MesaSimulation")

class SectorAgent(Agent):
    """
    An agent representing a domain or sector (e.g., Economy, Geopolitics).
    It holds a tension state and passes shockwaves to its neighbors.
    """
    def __init__(self, unique_id, model, sector: str, initial_tension: float):
        super().__init__(unique_id, model)
        self.sector = sector
        self.tension = initial_tension
        
    def step(self):
        # In a real model, this would check neighbors on a Network grid
        # and propagate tension based on edges (e.g., Economy impacts Supply Chain)
        # Here we do a simplified random walk mixing with the global average.
        global_avg = sum(a.tension for a in self.model.schedule.agents) / self.model.num_agents
        
        # Pull towards global average + some random volatility
        volatility = random.uniform(-0.1, 0.1)
        self.tension = (self.tension * 0.7) + (global_avg * 0.3) + volatility
        
        # Clamp between 0 and 1
        self.tension = max(0.0, min(1.0, self.tension))

class RippleModel(Model):
    """
    Simulates the ripple effects of an event across interconnected sectors.
    """
    def __init__(self, num_agents: int, sectors: List[str], initial_shock_sector: str):
        super().__init__()
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        
        for i, sector in enumerate(sectors):
            # Apply a high initial tension to the sector hit by the hypothesis
            initial_tension = 0.9 if sector == initial_shock_sector else 0.2
            agent = SectorAgent(i, self, sector, initial_tension)
            self.schedule.add(agent)

    def step(self):
        self.schedule.step()

class AgentBasedSimulation:
    """
    Uses Mesa to simulate the ripple effects of an event across interconnected sectors.
    """
    def __init__(self):
        pass

    def run_simulation(self, event: str, sectors: List[str]) -> Dict[str, Any]:
        logger.info(f"Running Mesa ABM for event: {event}")
        
        if not RandomActivation:
            logger.warning("mesa library not found. Returning mocked simulation.")
            return {
                "event": event,
                "impacts": {sector: "mock_impact" for sector in sectors}
            }
            
        # Determine the initial shock sector based on keywords, default to the first
        initial_shock = sectors[0]
        for s in sectors:
            if s.lower() in event.lower():
                initial_shock = s
                break
                
        # Initialize and run the Mesa model for 10 time steps (e.g., 10 months)
        model = RippleModel(len(sectors), sectors, initial_shock)
        for i in range(10):
            model.step()
            
        # Collect results
        impacts = {}
        for agent in model.schedule.agents:
            # Categorize tension level
            if agent.tension > 0.7:
                status = "CRITICAL"
            elif agent.tension > 0.4:
                status = "ELEVATED"
            else:
                status = "STABLE"
                
            impacts[agent.sector] = {
                "final_tension": round(agent.tension, 3),
                "status": status
            }
            
        return {
            "event": event,
            "steps_simulated": 10,
            "impacts": impacts
        }
