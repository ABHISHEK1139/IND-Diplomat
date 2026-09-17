"""Central guardrails for outbound LLM calls.

A hung provider must never hang the pipeline: every litellm request in this
repo inherits the global ``litellm.request_timeout`` set here from
``DIP_LLM_TIMEOUT`` (seconds, default 60). Call
:func:`apply_default_timeout` once at module import of each LLM entry module
(tracer, structured clients). Individual calls may still pass an explicit
``timeout=`` to override per request.
"""
from __future__ import annotations

import os

DEFAULT_TIMEOUT_SECONDS = 60.0


def default_timeout() -> float:
    try:
        return max(1.0, float(os.getenv("DIP_LLM_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def apply_default_timeout() -> float:
    """Set the process-wide litellm request timeout. No-op without litellm."""
    timeout = default_timeout()
    try:
        import litellm

        litellm.request_timeout = timeout
    except ImportError:
        pass
    return timeout
