"""Entrypoint hygiene: standalone scripts must bootstrap the package.

Every root-level and scripts/ entrypoint that imports `dip` at module top
level must anchor <root>/src on sys.path first, so `python <script>` works
from any CWD without requiring an installed distribution.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((ROOT / "scripts").glob("*.py"))
ROOT_SCRIPTS = [ROOT / name for name in ("run_10_cases.py", "run_backtest.py", "run_replay.py")]

# Pointer scripts exit before importing; they document their own replacement.
EXEMPT = {"verify_live_dossier.py"}


def _top_level_dip_import(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == "dip" for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "dip" and (node.level or 0) == 0:
                return True
    return False


def test_entrypoints_bootstrap_package():
    offenders = []
    for path in [*SCRIPTS, *ROOT_SCRIPTS]:
        if path.name in EXEMPT or not path.is_file():
            continue
        if _top_level_dip_import(path) and '"src"' not in path.read_text(encoding="utf-8").replace("'", '"'):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "entrypoints importing dip without src bootstrap:\n" + "\n".join(offenders)


def test_retired_verifier_points_elsewhere():
    proc = subprocess.run(
        [sys.executable, "scripts/verify_live_dossier.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert "test_offline_backtest" in proc.stdout
