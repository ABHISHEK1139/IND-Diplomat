import logging
from typing import Dict, Any, List

logger = logging.getLogger("DIP3.Layer5.Orchestrator")

from .scenario_generator import ScenarioGenerator
from .mesa_simulation import AgentBasedSimulation
from .causal_engine import CausalEngine
from .montecarlo import MonteCarloSimulator
from .system_dynamics import SystemDynamicsEngine
from .risk_engine import RiskEngine
from .sensitivity import SensitivityAnalysis
from .decision_engine import DecisionEngine
from .historical import HistoricalAnalogEngine
from .black_swan import BlackSwanDetector

class ForecastingOrchestrator:
    """
    Phase 5: Forecasting, Simulation & Decision Intelligence
    Orchestrates Scenario Generation, Agent Simulation, Monte Carlo, and Risk Assessment.
    """
    def __init__(self):
        logger.info("Forecasting Orchestrator initialized.")
        self.scenario_gen = ScenarioGenerator()
        self.abm = AgentBasedSimulation()
        self.causal = CausalEngine()
        self.monte_carlo = MonteCarloSimulator()
        self.system_dynamics = SystemDynamicsEngine()
        self.risk = RiskEngine()
        self.sensitivity = SensitivityAnalysis()
        self.decision = DecisionEngine()
        self.historical = HistoricalAnalogEngine()
        self.black_swan = BlackSwanDetector()

    async def run(self, world_model: Any, reasoning_results: Dict[str, Any], topic: str) -> Dict[str, Any]:
        """
        Runs the full Phase 5 simulation pipeline.
        """
        logger.info(f"Running Forecasting & Simulation for: {topic}")
        
        # 1. Historical Analogs
        analogs = self.historical.find_analogs(world_model)
        
        # 2. Scenario Generation
        scenarios = self.scenario_gen.generate_scenarios(topic, reasoning_results.get("hypotheses", []))
        
        # 3. For each scenario, run simulations
        detailed_scenarios = []
        for sc in scenarios:
            simulation_inputs = self._derive_simulation_inputs(
                world_model, reasoning_results, sc
            )
            # Agent Based Modeling
            abm_results = self.abm.run_simulation(sc["name"], ["Economy", "Geopolitics", "Supply Chain"])
            
            # Causal Graph
            causal_res = self.causal.map_causality(["Interest Rates", "Trade"], [])
            
            # Monte Carlo
            mc_res = self.monte_carlo.simulate(simulation_inputs)
            
            # System Dynamics
            sd_res = self.system_dynamics.run_feedback_model(simulation_inputs)
            
            # Append detailed results
            sc["simulation"] = {
                "abm": abm_results,
                "causal": causal_res,
                "monte_carlo": mc_res,
                "system_dynamics": sd_res
            }
            detailed_scenarios.append(sc)

        # 4. Risk Assessment
        risk_profile = self.risk.calculate_risk(detailed_scenarios)
        
        # 5. Sensitivity Analysis
        sens = self.sensitivity.run_sensitivity(["Oil", "Interest Rate", "GDP"])
        
        # 6. Black Swan Detection
        black_swans = self.black_swan.detect_anomalies(world_model)
        
        # 7. Decision Engineering
        options = self.decision.generate_options(risk_profile, detailed_scenarios)
        
        return {
            "status": "success",
            "message": "Phase 5 simulation complete.",
            "scenarios": detailed_scenarios,
            "risk_profile": risk_profile,
            "sensitivity": sens,
            "black_swans": black_swans,
            "decision_options": options,
            "historical_analogs": analogs
        }

    @staticmethod
    def _derive_simulation_inputs(
        world_model: Any, reasoning_results: Dict[str, Any], scenario: Dict[str, Any]
    ) -> Dict[str, float]:
        """Build reproducible simulation inputs from the current assessment state."""
        hypotheses = reasoning_results.get("hypotheses", [])
        confidences = [
            float(h.get("confidence", 0.0))
            for h in hypotheses
            if isinstance(h, dict) and h.get("confidence") is not None
        ]
        consensus = reasoning_results.get("consensus", {})
        if not isinstance(consensus, dict):
            consensus = {}

        return {
            "scenario_probability": float(scenario.get("probability", 0.0)),
            "mean_hypothesis_confidence": (
                sum(confidences) / len(confidences) if confidences else 0.0
            ),
            "hypothesis_count": float(len(hypotheses)),
            "evidence_verdict_count": float(len(consensus.get("evidence_verdicts", []))),
            "world_model_available": float(world_model is not None),
        }
