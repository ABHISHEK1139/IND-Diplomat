"""
LAYER-4 BOUNDARY CONTRACT
==========================

This module defines and enforces the architectural firewall that separates
Layer-4 (Analysis/Reasoning) from lower layers.

RULE: Layer-4 must NEVER import from:
  - Layer2_Knowledge
  - layer2_extraction
  - Layer1_Sensors
  - LAYER1_COLLECTION

Layer-4 may ONLY import from:
  - Layer3_StateModel.interface.state_provider  (the single L3→L4 interface)
  - Layer3_StateModel.schemas.state_context     (the contract object)
  - layer4_reasoning.*                          (shared ontology/fuzzy support)
  - Layer4_Analysis.*                           (own package)
  - Config.*                                    (thresholds, paths)
  - contracts.*                                 (shared data contracts)

WHY THIS MATTERS:
  If Layer-4 reads documents directly, the system degrades to "RAG with extra steps".
  Layer-4 must reason ONLY from the StateContext (interpreted reality),
  never from raw text, documents, or database queries.

  Documents → Layer-2 signals → Layer-3 state rebuild → new StateContext → Layer-4
  Layer-4 never touches documents. It only sees the updated world state.

Run this module directly to validate:
    python -m Layer4_Analysis.BOUNDARY_CONTRACT
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Forbidden import prefixes for Layer-4 code
FORBIDDEN_IMPORTS: Set[str] = {
    "Layer2_Knowledge",
    "layer2_extraction",
    "Layer1_Sensors",
    "LAYER1_COLLECTION",
}

# Allowed import prefixes for Layer-4 code
ALLOWED_IMPORTS: Set[str] = {
    "Layer3_StateModel",
    "layer4_reasoning",
    "Layer4_Analysis",
    "Config",
    "contracts",
}

# Files exempt from checking (diagnostics, not reasoning paths)
EXEMPT_FILES: Set[str] = {
    "BOUNDARY_CONTRACT.py",
}


def _extract_imports(filepath: Path) -> List[Tuple[str, int]]:
    """Extract all import module names and line numbers from a Python file."""
    imports: List[Tuple[str, int]] = []
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.lineno))
    return imports


def validate_imports(
    layer4_root: Path = None,
) -> Dict[str, List[str]]:
    """
    Scan all .py files under Layer4_Analysis/ for forbidden imports.

    Returns:
        Dict mapping filepath → list of violation descriptions.
        Empty dict = clean.
    """
    if layer4_root is None:
        layer4_root = Path(__file__).resolve().parent

    violations: Dict[str, List[str]] = {}

    for py_file in sorted(layer4_root.rglob("*.py")):
        if py_file.name in EXEMPT_FILES:
            continue
        # Skip __pycache__
        if "__pycache__" in str(py_file):
            continue

        relative = py_file.relative_to(layer4_root)
        file_violations: List[str] = []

        for module_name, lineno in _extract_imports(py_file):
            top_module = module_name.split(".")[0]
            if top_module in FORBIDDEN_IMPORTS:
                file_violations.append(
                    f"  Line {lineno}: imports '{module_name}' "
                    f"(FORBIDDEN: Layer-4 must not import from {top_module})"
                )

        if file_violations:
            violations[str(relative)] = file_violations

    return violations


def print_report(violations: Dict[str, List[str]]) -> None:
    """Print a human-readable boundary violation report."""
    if not violations:
        print("=" * 60)
        print("BOUNDARY CONTRACT: PASSED")
        print("No forbidden imports found in Layer4_Analysis/")
        print("=" * 60)
        return

    print("=" * 60)
    print("BOUNDARY CONTRACT: VIOLATIONS DETECTED")
    print("=" * 60)
    total = 0
    for filepath, issues in sorted(violations.items()):
        print(f"\n{filepath}:")
        for issue in issues:
            print(issue)
            total += 1
    print(f"\nTotal violations: {total}")
    print("=" * 60)


if __name__ == "__main__":
    violations = validate_imports()
    print_report(violations)
    sys.exit(1 if violations else 0)
