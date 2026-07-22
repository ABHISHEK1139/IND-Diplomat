"""
Prefect Deployment Script for DIP 2.0
=====================================
Wraps the unified pipeline in a Prefect Flow for orchestration.
"""

import sys
import asyncio
from pathlib import Path

# Add root to sys path
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    from prefect import flow, task
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    # Mock for testing if not installed
    def task(fn=None, **kwargs):
        if fn: return fn
        def wrapper(f): return f
        return wrapper
    def flow(fn=None, **kwargs):
        if fn: return fn
        def wrapper(f): return f
        return wrapper

from dip.unified_pipeline import execute as run_pipeline

@task(name="Run Unified Pipeline", retries=2, retry_delay_seconds=30)
def execute_pipeline_task(country: str, target: str, crisis_id: str):
    """Executes the pipeline for a single target."""
    return asyncio.run(run_pipeline(target, country, crisis_id))

@flow(name="DIP 2.0 Global Assessment Flow", description="Runs global OSINT assessments.")
def dip2_global_flow(scenarios: list):
    """Main flow that processes multiple scenarios sequentially."""
    results = []
    for scenario in scenarios:
        res = execute_pipeline_task(
            country=scenario.get("country", "IND"),
            target=scenario.get("target", ""),
            crisis_id=scenario.get("crisis_id", "")
        )
        results.append(res)
    return results

if __name__ == "__main__":
    if PREFECT_AVAILABLE:
        # Example local run
        print("Starting Prefect Flow...")
        scenarios = [
            {"country": "IND", "target": "CHN", "crisis_id": "BORDER_SKIRMISH"},
            {"country": "USA", "target": "RUS", "crisis_id": "CYBER_ATTACK"}
        ]
        dip2_global_flow(scenarios)
    else:
        print("Prefect not installed. Install via `pip install prefect`")
