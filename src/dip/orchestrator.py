"""
Orchestrator (Layer 1 Automation)
=================================
Prefect flow to run the data collection and extraction pipeline on a schedule.
"""

import asyncio
import logging

try:
    from prefect import flow, task
except ImportError:
    # Dummy decorators if prefect is missing/broken
    def flow(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]): return args[0]
        return decorator
    def task(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]): return args[0]
        return decorator

from dip.pipeline.collection.feed_integrator import FeedIntegrator
from dip.pipeline.knowledge.signal_extractor import SignalExtractor


logger = logging.getLogger("Orchestrator")


@task(retries=3, retry_delay_seconds=60)
async def collect_raw_observations(country: str) -> list:
    """Task: Collect raw data from GDELT and News feeds."""
    logger.info(f"Starting data collection for {country}")
    integrator = FeedIntegrator()
    obs = await integrator.fetch_all(country)
    logger.info(f"Collected {len(obs)} raw observations.")
    return obs


@task(retries=2, retry_delay_seconds=30)
async def extract_semantic_signals(observations: list) -> list:
    """Task: Parse raw observations into Signals using LLM."""
    if not observations:
        return []
    logger.info("Starting semantic LLM extraction...")
    extractor = SignalExtractor()
    signals = await extractor.extract(observations)
    logger.info(f"Extracted {len(signals)} semantic signals.")
    return signals


@flow(name="Intelligence Ingestion Pipeline")
async def run_ingestion_pipeline(country: str = "IND"):
    """Main flow that orchestrates data collection and signal extraction."""
    logger.info(f"--- Starting Prefect Flow for {country} ---")
    
    observations = await collect_raw_observations(country)
    signals = await extract_semantic_signals(observations)
    
    # In a full deployment, these signals would be persisted to a database here.
    # For now, we return them to the caller.
    logger.info("--- Flow Complete ---")
    return signals


if __name__ == "__main__":
    # To run on a schedule, you would typically use:
    # run_ingestion_pipeline.serve(name="15-min-scraper", interval=900)
    asyncio.run(run_ingestion_pipeline("IND"))
