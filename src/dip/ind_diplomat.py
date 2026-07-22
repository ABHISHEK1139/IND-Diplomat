"""Wrapper entrypoint that exposes `diplomat_query` used by job workers and APIs.

This module adapts the `unified_pipeline.execute` function into a small async
callable that returns an object with a `.dict()` method so existing job
infrastructure (which expects a pydantic-like return) continues to work.
It also emits WebSocket progress events (when `api_ws.ws_manager` is available).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class PipelineResult(BaseModel):
    """JSON-serializable compatibility result for background job workers."""

    model_config = ConfigDict(extra="allow")


class PipelineError(BaseModel):
    error: str


async def diplomat_query(query: str, country: str = "IND", job_id: str | None = None) -> Any:
    """Run the unified pipeline and return a wrapper with `.dict()`.

    The returned object supports `.dict()` so `analyst_api.job_store.run_job_background`
    can convert results to JSON. Progress events are published to topic
    `job:{job_id}` only if a `job_id` is provided via `context_vars` (best-effort).
    """
    # best-effort import of ws manager for progress updates
    try:
        from dip.api_ws.ws_manager import manager as ws_manager
    except Exception:
        ws_manager = None

    try:
        # Import here to avoid heavy top-level work during module import
        from dip.unified_pipeline import execute as pipeline_execute
    except Exception as exc:  # pragma: no cover - fallback
        logger.exception("Unified pipeline not available: %s", exc)
        return PipelineError(error=str(exc))

    # Run pipeline and send light progress events if ws_manager exists
    result = None
    try:
        if ws_manager:
            try:
                # Publish job-scoped start if job_id available, else broadcast
                topic = f"job:{job_id}" if job_id else None
                payload = {"type": "pipeline.started", "query": query, "country": country}
                if topic:
                    await ws_manager.publish_topic(topic, payload)
                else:
                    await ws_manager.broadcast(payload)
            except Exception:
                logger.warning("Could not publish pipeline start event", exc_info=True)

        result = await pipeline_execute(query, country, job_id=job_id)

        if ws_manager:
            try:
                topic = f"job:{job_id}" if job_id else None
                payload = {"type": "pipeline.completed", "query": query, "country": country, "status": result.get("status")}
                if topic:
                    await ws_manager.publish_topic(topic, payload)
                else:
                    await ws_manager.broadcast(payload)
            except Exception:
                logger.warning("Could not publish pipeline completion event", exc_info=True)

        return PipelineResult.model_validate(result)

    except Exception as exc:  # pragma: no cover
        logger.exception("Pipeline execution failed: %s", exc)
        return PipelineError(error=str(exc))
