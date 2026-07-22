from __future__ import annotations
from dip.Config.config import config
"""Prefect workflow adapter for scheduled ingestion, backtesting, and guardian audits.

When prefect is installed, this provides flow definitions for recurring tasks.
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Optional import
try:
    from prefect import flow, task, get_run_logger
    from prefect.schedules import Interval, Cron
    from prefect.deployments import Deployment
    PREFECT_AVAILABLE = True
except Exception:
    PREFECT_AVAILABLE = False
    def task(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]): return args[0]
        return decorator
    def flow(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]): return args[0]
        return decorator

from .contracts import AssessmentGoal
from .assessment_graph import HeadOfStatePipelineGraph


@task(name="run_assessment")
async def run_assessment_task(objective: str, country: str = "UNKNOWN") -> Dict[str, Any]:
    """Run a single assessment as a Prefect task."""
    from dip.unified_pipeline import execute
    result = await execute(objective, country)
    return result

@task(name="run_backtest")
async def run_backtest_task(scenario_file: str) -> Dict[str, Any]:
    """Run a backtest scenario."""
    # Backtest logic would go here
    return {"scenario": scenario_file, "status": "completed"}

@task(name="guardian_audit")
async def guardian_audit_task() -> Dict[str, Any]:
    """Run guardian audit of system health."""
    from guardian_runner import run_guardian_check
    result = await run_guardian_check()
    return result

@flow(name="dip2-scheduled-ingestion")
async def scheduled_ingestion_flow(countries: List[str] = None):
    """Scheduled ingestion flow for multiple countries."""
    countries = countries or ["IND", "CHN", "PAK", "USA"]
    for country in countries:
        await run_assessment_task.submit(
            objective=f"Routine situation assessment for {country}",
            country=country
        )

@flow(name="dip2-backtest-suite")
async def backtest_suite_flow(scenario_dir: str = "data/scenarios"):
    """Run backtest suite against historical scenarios."""
    import glob
    scenarios = glob.glob(f"{scenario_dir}/*.json")
    for scenario in scenarios:
        await run_backtest_task.submit(scenario_file=scenario)

@flow(name="dip2-guardian-audit")
async def guardian_audit_flow():
    """Periodic guardian audit flow."""
    await guardian_audit_task.submit()

class PrefectWorkflowAdapter:
    """Prefect-backed workflow definitions for DIP 2.0."""

    def __init__(self):
        if not PREFECT_AVAILABLE:
            raise RuntimeError("prefect not installed. Install with: pip install prefect")
        self.logger = get_run_logger()

    def create_deployments(self) -> List[Deployment]:
        """Create Prefect deployments for scheduled flows."""
        deployments = [
            Deployment.build_from_flow(
                flow=scheduled_ingestion_flow,
                name="dip2-scheduled-ingestion",
                schedule=Cron(cron="0 */6 * * *"),  # Every 6 hours
                work_queue_name="dip2-ingestion",
            ),
            Deployment.build_from_flow(
                flow=backtest_suite_flow,
                name="dip2-backtest-suite",
                schedule=Cron(cron="0 2 * * 0"),  # Weekly on Sunday 2am
                work_queue_name="dip2-backtest",
            ),
            Deployment.build_from_flow(
                flow=guardian_audit_flow,
                name="dip2-guardian-audit",
                schedule=Interval(interval=timedelta(hours=12)),
                work_queue_name="dip2-guardian",
            ),
        ]
        return deployments


def create_prefect_adapter() -> Optional[PrefectWorkflowAdapter]:
    """Factory to create Prefect adapter if available."""
    if not PREFECT_AVAILABLE:
        return None
    if not config.DIP_PREFECT_ENABLED:
            return None
    return PrefectWorkflowAdapter()