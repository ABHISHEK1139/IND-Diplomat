from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from project_root import PROJECT_ROOT, TEST_OUTPUT_ROOT


def get_test_output_dir() -> Path:
    env_dir = str(os.environ.get("DIP_TEST_OUTPUT_DIR", "") or "").strip()
    if env_dir:
        output_dir = Path(env_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = TEST_OUTPUT_ROOT / f"adhoc_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def output_path(*parts: str) -> Path:
    path = get_test_output_dir().joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def script_log_path(name: str) -> Path:
    return output_path("script_logs", name)
