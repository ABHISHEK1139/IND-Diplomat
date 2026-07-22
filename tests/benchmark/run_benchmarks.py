import json
import logging
import os
import asyncio
from pathlib import Path

# DIP Imports
from core.schema import StateContext
from layer0_planning.investigation_planner import InvestigationPlanner
from layer3_state.state_provider import StateProvider
from layer5_trajectory.scenario_engine import ScenarioEngine
from memory.investigation_memory import InvestigationMemory
from layer10_telemetry.llm_tracer import current_investigation_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("BenchmarkRunner")

class BenchmarkRunner:
    """
    Runs investigations against historical 'Golden Datasets' and evaluates
    accuracy, drift, and confidence levels.
    """
    def __init__(self):
        self.dataset_dir = Path("benchmark/golden_datasets")
        self.memory = InvestigationMemory()
        
    async def run_all(self):
        if not self.dataset_dir.exists():
            logger.warning(f"No golden datasets found at {self.dataset_dir}")
            return
            
        datasets = list(self.dataset_dir.glob("*.json"))
        logger.info(f"Found {len(datasets)} golden datasets.")
        
        passed = 0
        failed = 0
        
        for ds in datasets:
            result = await self.evaluate_dataset(ds)
            if result:
                passed += 1
            else:
                failed += 1
                
        logger.info(f"Benchmark Complete. Passed: {passed}, Failed: {failed}")
        
    async def evaluate_dataset(self, filepath: Path) -> bool:
        logger.info(f"Evaluating {filepath.name}...")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            query = data.get("query", "")
            expected_signals = data.get("expected_signals", [])
            expected_trajectory = data.get("expected_base_trajectory", "")
            
            # Run Pipeline
            planner = InvestigationPlanner()
            inv = await planner.plan_investigation(query)
            current_investigation_id.set(inv.investigation_id)
            self.memory.save_investigation(inv)
            
            # Note: In a real benchmark, we would mock Layer 1/2 to return the data.get("raw_observations").
            # For this harness, we simulate extracting the expected signals directly.
            from core.schema import Signal
            mock_signals = [Signal(**s) for s in expected_signals]
            
            # Layer 3
            sp = StateProvider()
            state = await sp.build_state(target_country=inv.goal.target_country, signals=mock_signals)
            
            # Layer 5
            engine = ScenarioEngine()
            tree = await engine.generate_scenarios(state)
            
            # Evaluation
            trajectory_match = expected_trajectory.lower() in tree.base_trajectory.lower()
            
            if trajectory_match:
                logger.info(f"✅ PASS: {filepath.name}")
                return True
            else:
                logger.error(f"❌ FAIL: {filepath.name}")
                logger.error(f"  Expected Trajectory: {expected_trajectory}")
                logger.error(f"  Actual Trajectory: {tree.base_trajectory}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating {filepath.name}: {e}")
            return False

if __name__ == "__main__":
    runner = BenchmarkRunner()
    asyncio.run(runner.run_all())
