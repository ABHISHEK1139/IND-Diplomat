"""
Compatibility package shim.

Allows lowercase `core.*` imports to resolve into the existing `Core/` package.
"""

from importlib import import_module

_core_pkg = import_module("Core")

# Make this module behave like a package for `core.database.*` imports.
__path__ = _core_pkg.__path__
__package__ = "core"

__all__ = [
    "orchestrator",
    "registry",
    "PipelineResult",
    "PipelineContext",
    "create_context",
]


def __getattr__(name):
    """
    Lazy compatibility exports for callers that use:
        from core import orchestrator, registry, PipelineResult, PipelineContext
    """
    if name == "orchestrator":
        return import_module("Core.orchestrator").orchestrator
    if name == "registry":
        return import_module("Core.registry").registry
    if name == "PipelineResult":
        return import_module("Core.orchestrator").PipelineResult
    if name == "PipelineContext":
        return import_module("Core.context").PipelineContext
    if name == "create_context":
        return import_module("Core.context").create_context
    raise AttributeError(f"module 'core' has no attribute '{name}'")
