"""Optional-dependency hygiene: minimal installs must keep working.

Every heavy integration (neo4j, dspy, trafilatura, ...) must either import
cleanly when absent or fail lazily with an actionable message — never break
module import of the default pipeline path.
"""
import importlib
import sys

import pytest

pytestmark = pytest.mark.unit


def test_graph_manager_importable_without_neo4j(monkeypatch):
    import dip.pipeline.world_model.state.graph_manager as gm

    monkeypatch.setattr(gm, "_NEO4J_AVAILABLE", False, raising=False)
    with pytest.raises(RuntimeError, match="politiq-ai\\[graph\\]"):
        gm._require_neo4j()
    assert isinstance(gm._NEO4J_AVAILABLE, bool)


def test_goal_decomposer_fails_lazily_without_dspy(monkeypatch):
    monkeypatch.setitem(sys.modules, "dspy", None)
    # Re-import under the blocked dspy to exercise the guard.
    import dip.pipeline.collection.research.goal_decomposer.decomposer as mod

    importlib.reload(mod)
    try:
        assert mod.dspy is None
        with pytest.raises(ImportError, match="politiq-ai\\[reasoning\\]"):
            mod.GoalDecomposer()
    finally:
        del sys.modules["dspy"]
        importlib.reload(mod)


def test_morning_brief_fails_lazily_without_dspy(monkeypatch):
    monkeypatch.setitem(sys.modules, "dspy", None)
    import dip.adaptive.executive_feed.morning_brief as mod

    importlib.reload(mod)
    try:
        assert mod.dspy is None
        with pytest.raises(ImportError, match="politiq-ai\\[reasoning\\]"):
            mod.MorningBriefCompiler()
    finally:
        del sys.modules["dspy"]
        importlib.reload(mod)


def test_extractor_degrades_without_trafilatura(monkeypatch):
    import dip.pipeline.collection.research.retrieval.extractor as mod

    monkeypatch.setattr(mod, "trafilatura", None)
    assert mod.ContentExtractor().extract("http://x", "<html></html>") is None


def test_default_entrypoints_import_without_optionals():
    # These must never hard-require an extra at module import time.
    importlib.import_module("dip.unified_pipeline")
    importlib.import_module("dip.api.rest_api")
    importlib.import_module("dip.core.sanitize")
