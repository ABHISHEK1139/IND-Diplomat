from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Dict


PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = SRC_ROOT.parent

LEGACY_PACKAGE_DIRS: Dict[str, str] = {
    "analysis": "analysis",
    "analyst_api": "analyst_api",
    "api": "API",
    "bootstrap": "system_bootstrap",
    "config": "Config",
    "contracts": "contracts",
    "core": "Core",
    "engine": "engine",
    "frontend": "Frontend",
    "schemas": "schemas",
    "system_guardian": "SystemGuardian",
    "utils": "Utils",
}


def ensure_legacy_root_on_syspath() -> Path:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PROJECT_ROOT


def bind_legacy_package(module: ModuleType, legacy_dir_name: str) -> None:
    ensure_legacy_root_on_syspath()
    legacy_dir = PROJECT_ROOT / legacy_dir_name
    module.__path__ = [str(legacy_dir)]
    module.__package__ = module.__name__


def legacy_dir(package_name: str) -> Path:
    ensure_legacy_root_on_syspath()
    return PROJECT_ROOT / LEGACY_PACKAGE_DIRS[package_name]
