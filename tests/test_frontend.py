"""Frontend contract: every backend pipeline phase must map to a tracker step.

Prevents drift where the backend emits a stage the UI silently drops
(tracker steps stuck in "waiting" mid-run).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "src" / "dip" / "unified_pipeline.py"
PAGE = ROOT / "frontend-next" / "src" / "app" / "investigations" / "[id]" / "page.tsx"

TRACKER_STEPS = {"planning", "collection", "worldmodel", "reasoning", "forecasting", "workspace", "learning"}


def _backend_phases() -> set[str]:
    text = PIPELINE.read_text(encoding="utf-8")
    return set(re.findall(r'"phase":\s*"([a-z_]+)"', text))


def _phase_map() -> dict[str, str]:
    text = PAGE.read_text(encoding="utf-8")
    return dict(re.findall(r'(\w+):\s*"(\w+)"', text.split("PHASE_MAP")[1].split("};")[0]))


def test_all_backend_phases_mapped():
    assert PAGE.is_file(), "investigation page missing"
    phase_map = _phase_map()
    missing = sorted(p for p in _backend_phases() if p not in phase_map)
    assert not missing, f"backend phases with no tracker mapping: {missing}"


def test_mappings_target_real_tracker_steps():
    phase_map = _phase_map()
    bad = {k: v for k, v in phase_map.items() if v not in TRACKER_STEPS}
    assert not bad, f"mappings to nonexistent tracker steps: {bad}"
