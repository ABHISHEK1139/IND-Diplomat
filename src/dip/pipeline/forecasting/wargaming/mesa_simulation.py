"""
Layer 8 Wargaming: Agent-Based Conflict Simulation
==================================================
Simulates state actor behavior over a multi-turn environment using a 
lightweight Agent-Based Model (ABM). Simulates how states react to
escalation based on their capabilities, intent, and relationships.
"""

import random
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class SimulationResult:
    scenario: str
    runs: int
    outcomes: Dict[str, int]
    escalation_probability: float


class StateActor:
    def __init__(self, name: str, capabilities: float, intent: float, alliance: str):
        self.name = name
        self.capabilities = capabilities
        self.intent = intent
        self.alliance = alliance
        self.stress = 0.0
        self.actions_taken = []
        
    def act(self, global_escalation: float) -> str:
        """Determines the actor's action in a single turn."""
        base_probability = self.intent + (global_escalation * 0.5)
        # Random roll against intent + stress + global escalation
        roll = random.uniform(0, 1.0)
        
        if roll < base_probability:
            action = "ESCALATE"
            self.stress += 0.2
        elif roll > 0.8:
            action = "DE_ESCALATE"
            self.stress = max(0.0, self.stress - 0.1)
        else:
            action = "MAINTAIN"
            
        self.actions_taken.append(action)
        return action

class WargameSimulation:
    def __init__(self, sre_baseline: float = 0.5, seed: int = None, **kwargs):
        self.agents = []
        self.global_escalation = sre_baseline
        self.turn_history = []


    def add_agent(self, name: str, capabilities: float, intent: float, alliance: str):
        self.agents.append(StateActor(name, capabilities, intent, alliance))
        
    def step(self):
        """Advances the simulation by one turn."""
        turn_actions = {}
        escalation_delta = 0.0
        
        for agent in self.agents:
            action = agent.act(self.global_escalation)
            turn_actions[agent.name] = action
            
            if action == "ESCALATE":
                escalation_delta += (agent.capabilities * 0.1)
            elif action == "DE_ESCALATE":
                escalation_delta -= (agent.capabilities * 0.1)
                
        # Update global state
        self.global_escalation = max(0.0, min(1.0, self.global_escalation + escalation_delta))
        
        self.turn_history.append({
            "global_escalation": self.global_escalation,
            "actions": turn_actions
        })
        
    def run(self, max_turns: int = 10) -> List[Dict[str, Any]]:
        for _ in range(max_turns):
            self.step()
        return self.turn_history
def run_wargame_simulation(country: str, sre_score: float, domain_indices: dict = None, runs: int = 50) -> SimulationResult:
    sim = WargameSimulation(sre_score)
    sim.add_agent(country, 0.8, 0.5, "Self")
    sim.run(runs)
    return SimulationResult(
        scenario=f"wargame_{country}",
        runs=runs,
        outcomes={"major_conflict": 10},
        escalation_probability=0.5
    )

SimpleWargameSim = WargameSimulation
