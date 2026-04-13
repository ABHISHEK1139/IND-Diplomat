"""Final diagnostic report for runtime readiness."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "system_bootstrap" / "logs" / "full_trace.json"
WINDOWS_OLLAMA_CANDIDATES = [
    Path(r"C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe"),
    Path(r"C:\Program Files\Ollama\ollama.exe"),
]


def run_py(script: str, timeout: int = 1800) -> Tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    ok = proc.returncode == 0
    detail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    return ok, detail


def check_llm() -> Tuple[bool, str]:
    ollama_bin = shutil.which("ollama")
    if ollama_bin is None and sys.platform.startswith("win"):
        for candidate in WINDOWS_OLLAMA_CANDIDATES:
            resolved = Path(str(candidate).replace("%USERNAME%", os.environ.get("USERNAME", "")))
            if resolved.exists():
                ollama_bin = str(resolved)
                break
    if ollama_bin is None:
        return False, "ollama binary not found"
    proc = subprocess.run(
        [ollama_bin, "run", "deepseek-r1:8b", "Say OK"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    merged = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        return False, f"ollama run failed: {merged[:400]}"
    if "ok" not in merged.lower():
        return False, f"unexpected LLM output: {merged[:400]}"
    return True, merged[:400]


def check_trace_requirements() -> Dict[str, Tuple[bool, str]]:
    if not TRACE_PATH.exists():
        ok, detail = run_py("system_bootstrap/run_shadow_pipeline.py", timeout=3600)
        if not ok:
            return {
                "Sensors": (False, "shadow pipeline failed before trace generation"),
                "Verifier": (False, "shadow pipeline failed before verifier results"),
            }

    try:
        payload = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "Sensors": (False, f"failed to parse {TRACE_PATH}: {exc}"),
            "Verifier": (False, f"failed to parse {TRACE_PATH}: {exc}"),
        }

    signals = (payload.get("signals_detected", {}) or {}).get("count", 0)
    sensors_ok = int(signals) > 0
    sensors_reason = f"signals_detected={signals}"

    grounding = payload.get("grounding_status", {}) or {}
    verifier_ok = bool(grounding.get("grounding_passed")) and bool(grounding.get("claim_support_passed"))
    if verifier_ok:
        verifier_reason = "grounding_passed=true and claim_support_passed=true"
    else:
        verifier_reason = (
            f"grounding_passed={grounding.get('grounding_passed')} "
            f"claim_support_passed={grounding.get('claim_support_passed')}"
        )

    return {
        "Sensors": (sensors_ok, sensors_reason),
        "Verifier": (verifier_ok, verifier_reason),
    }


def status_text(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def main() -> int:
    checks: Dict[str, Tuple[bool, str]] = {}

    checks["Internet Search"] = run_py("system_bootstrap/test_internet.py", timeout=300)
    checks["OCR"] = run_py("system_bootstrap/test_ocr.py", timeout=600)
    checks["RAG"] = run_py("system_bootstrap/test_rag.py", timeout=1800)
    checks["LLM"] = check_llm()
    checks.update(check_trace_requirements())

    headers = ("Check", "Status", "Reason")
    line = "-" * 120
    print(line)
    print(f"{headers[0]:<20} {headers[1]:<8} {headers[2]}")
    print(line)
    for name in ["OCR", "Internet Search", "RAG", "LLM", "Sensors", "Verifier"]:
        ok, reason = checks.get(name, (False, "not executed"))
        reason_compact = " ".join((reason or "").split())
        print(f"{name:<20} {status_text(ok):<8} {reason_compact[:90]}")
    print(line)

    failed = [name for name, (ok, _) in checks.items() if not ok]
    if failed:
        print("FAILED CHECKS:")
        for name in failed:
            print(f"- {name}: {checks[name][1]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
