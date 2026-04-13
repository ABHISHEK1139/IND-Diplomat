"""
Core orchestration package.

Exposes the pipeline orchestrator runtime plus orchestration controllers.
"""

from .runtime import Orchestrator, PipelineResult, orchestrator, run_pipeline


async def run(query: str, user_id: str = None, session_id: str = None, **flags) -> PipelineResult:
    """Compatibility helper for callers using `core.orchestrator.run(...)`."""
    return await orchestrator.run(query, user_id=user_id, session_id=session_id, **flags)


def get_stats():
    """Compatibility helper for callers using `core.orchestrator.get_stats()`."""
    return orchestrator.get_stats()


def enable(module_name: str):
    """Compatibility helper for callers using `core.orchestrator.enable(...)`."""
    return orchestrator.enable(module_name)


def disable(module_name: str):
    """Compatibility helper for callers using `core.orchestrator.disable(...)`."""
    return orchestrator.disable(module_name)


__all__ = [
    "Orchestrator",
    "PipelineResult",
    "orchestrator",
    "run_pipeline",
    "run",
    "get_stats",
    "enable",
    "disable",
]
