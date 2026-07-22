"""Local import shim for IND-Diplomat during source-tree development."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from pydantic import BaseModel, Field

from dip.unified_pipeline import execute


class DiplomatResult(BaseModel):
    query: str
    country: str
    status: str = "UNKNOWN"
    threat_level: str | None = None
    trace_id: str | None = None
    verification_score: float = 0.0
    payload: Dict[str, Any] = Field(default_factory=dict)


async def diplomat_query(query: str, country: str = "IND", **_: Any) -> DiplomatResult:
    payload = await execute(query, country)
    return DiplomatResult(
        query=payload.get("query", query),
        country=payload.get("country", country),
        status=payload.get("status", "UNKNOWN"),
        threat_level=payload.get("threat_level"),
        trace_id=payload.get("trace_id"),
        verification_score=float(payload.get("verification_score", 0.0) or 0.0),
        payload=payload,
    )


def diplomat_query_sync(query: str, country: str = "IND", **kwargs: Any) -> DiplomatResult:
    return asyncio.run(diplomat_query(query, country, **kwargs))


__all__ = ["DiplomatResult", "diplomat_query", "diplomat_query_sync"]
