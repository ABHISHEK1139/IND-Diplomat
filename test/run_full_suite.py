from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from test._support import PROJECT_ROOT


STANDALONE_SCRIPTS = [
    "test/run_fallback_test.py",
    "test/manual/manual_test_anomaly.py",
    "test/manual/run_real_world_test.py",
    "test/test_drill.py",
    "test/test_system.py",
    "test/system_bootstrap/test_internet.py",
    "test/system_bootstrap/test_ocr.py",
    "test/system_bootstrap/test_rag.py",
]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_command(command: list[str], *, cwd: Path, env: dict[str, str], stdout_path: Path, stderr_path: Path, timeout: int = 3600) -> dict[str, object]:
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    duration = round(time.time() - started, 2)
    _write_text(stdout_path, proc.stdout)
    _write_text(stderr_path, proc.stderr)
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "duration_sec": duration,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = PROJECT_ROOT / "runtime" / "test_runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DIP_TEST_OUTPUT_DIR"] = str(run_dir)
    env["PYTHONUTF8"] = "1"

    summary: dict[str, object] = {
        "run_dir": str(run_dir),
        "started_at": datetime.now().isoformat(),
        "pytest": {},
        "standalone_scripts": [],
    }

    try:
        summary["pytest"] = _run_command(
            [sys.executable, "-m", "pytest", "test", "-vv", "--maxfail=0", f"--junitxml={run_dir / 'pytest_junit.xml'}"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout_path=run_dir / "pytest_stdout.log",
            stderr_path=run_dir / "pytest_stderr.log",
            timeout=7200,
        )
    except Exception as exc:
        summary["pytest"] = {"error": str(exc)}

    for idx, script in enumerate(STANDALONE_SCRIPTS, start=1):
        try:
            result = _run_command(
                [sys.executable, script],
                cwd=PROJECT_ROOT,
                env=env,
                stdout_path=run_dir / "standalone" / f"{idx:02d}_{Path(script).stem}_stdout.log",
                stderr_path=run_dir / "standalone" / f"{idx:02d}_{Path(script).stem}_stderr.log",
                timeout=7200,
            )
            result["script"] = script
        except Exception as exc:
            result = {"script": script, "error": str(exc)}
        summary["standalone_scripts"].append(result)

    summary["finished_at"] = datetime.now().isoformat()
    summary["overall_exit_code"] = 0
    if isinstance(summary.get("pytest"), dict) and summary["pytest"].get("exit_code", 1) != 0:
        summary["overall_exit_code"] = 1
    if any(isinstance(item, dict) and item.get("exit_code", 0) != 0 for item in summary["standalone_scripts"]):
        summary["overall_exit_code"] = 1

    _write_text(run_dir / "summary.json", json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return int(summary["overall_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
