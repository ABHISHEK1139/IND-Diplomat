"""Layer-4 boundary lock (design.txt Step 1).

Layer-4 (deliberation) must NEVER read documents or raw retrieval output.
It may only read StateContext, KGI coverage reports, and provenance
summaries. This test statically enforces the boundary so the violation
cannot silently regress:

- No imports from Layer-1 (``dip.pipeline.collection``) or Layer-2
  (``dip.pipeline.knowledge``) anywhere under ``pipeline/deliberation``.
- No retrieval/scraping libraries (web_surfer, signal_extractor,
  ResearchPlanner, trafilatura, duckduckgo, feedparser, httpx, aiohttp).

LLM reasoning (litellm) and world-model *types* remain allowed: Layer-4
reasons over StateContext, it just never fetches documents itself.
Live fetching belongs to InvestigationController/StateProvider (Layer 1-3).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

DELIBERATION_ROOT = Path(__file__).resolve().parent.parent / "src" / "dip" / "pipeline" / "deliberation"

FORBIDDEN_MODULE_PREFIXES = (
    "dip.pipeline.collection",
    "dip.pipeline.knowledge",
)

FORBIDDEN_NAMES = {
    "web_surfer",
    "signal_extractor",
    "ResearchPlanner",
    "ResilientWebSurfer",
    "trafilatura",
    "duckduckgo_search",
    "duckduckgo",
    # The upstream DuckDuckGo distribution was renamed to `ddgs`; the compat
    # shim re-exports DDGS from it. Layer-4 must stay locked out of both.
    "ddgs",
    "search_compat",
    "feedparser",
    "httpx",
    "aiohttp",
    "DDGS",
}


def _iter_imports(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module
            for alias in node.names:
                yield alias.name


def test_deliberation_has_no_retrieval_imports():
    assert DELIBERATION_ROOT.is_dir(), f"missing deliberation tree: {DELIBERATION_ROOT}"
    violations = []
    for path in sorted(DELIBERATION_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            violations.append(f"{path}: unparseable ({exc})")
            continue
        for name in _iter_imports(tree):
            dotted = str(name)
            if dotted.startswith(FORBIDDEN_MODULE_PREFIXES):
                violations.append(f"{path}: forbidden layer import '{dotted}'")
            elif dotted.split(".")[0] in FORBIDDEN_NAMES or dotted in FORBIDDEN_NAMES:
                violations.append(f"{path}: forbidden retrieval import '{dotted}'")
    assert not violations, "Layer-4 boundary violations:\n" + "\n".join(violations)


def test_no_raw_text_injection_helpers():
    """No deliberation module may reference raw observation/document fields
    as retrieval input (obs.content / e.text patterns belong to Layer 1-3)."""
    offenders = []
    for path in sorted(DELIBERATION_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in ("obs.content", "obs.text", "[e.text", "e.publisher"):
            if marker in text:
                offenders.append(f"{path}: raw-text marker '{marker}'")
    assert not offenders, "Layer-4 raw-text usage:\n" + "\n".join(offenders)
