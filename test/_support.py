from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def _discover_project_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "Config").exists() and (candidate / "Layer4_Analysis").exists():
            return candidate
    return here.parent.parent


PROJECT_ROOT = _discover_project_root()


def get_test_output_dir() -> Path:
    env_dir = str(os.environ.get("DIP_TEST_OUTPUT_DIR", "") or "").strip()
    if env_dir:
        output_dir = Path(env_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "runtime" / "test_runs" / f"adhoc_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def output_path(*parts: str) -> Path:
    path = get_test_output_dir().joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def script_log_path(name: str) -> Path:
    return output_path("script_logs", name)
