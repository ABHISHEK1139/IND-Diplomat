"""Run a no-code-change shadow execution and export full trace diagnostics."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "system_bootstrap" / "logs"
TRACE_JSON = LOG_DIR / "full_trace.json"
RAW_TRACE_JSON = LOG_DIR / "raw_trace.json"


def run_cmd(cmd: List[str], timeout: int = 1200) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _layer_timings(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    layers: Dict[str, Dict[str, float]] = {}
    for event in events:
        layer = str(event.get("layer", "UNKNOWN"))
        t = float(event.get("t", 0.0) or 0.0)
        slot = layers.setdefault(layer, {"first_t": t, "last_t": t})
        slot["first_t"] = min(slot["first_t"], t)
        slot["last_t"] = max(slot["last_t"], t)
    for slot in layers.values():
        slot["duration"] = max(0.0, slot["last_t"] - slot["first_t"])
    return layers


def _extract_signals(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    signals = []
    for event in events:
        if event.get("event") == "SIGNAL_ACTIVATED":
            data = event.get("data", {}) or {}
            signals.append(
                {
                    "signal": data.get("signal"),
                    "confidence": data.get("confidence"),
                    "t": event.get("t"),
                }
            )
    return {"count": len(signals), "signals": signals}


def _extract_first(events: List[Dict[str, Any]], event_name: str) -> Dict[str, Any]:
    for event in events:
        if event.get("event") == event_name:
            return event.get("data", {}) or {}
    return {}


def _extract_all(events: List[Dict[str, Any]], event_name: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for event in events:
        if event.get("event") == event_name:
            rows.append(event.get("data", {}) or {})
    return rows


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()

    pipeline_cmd = [
        sys.executable,
        "Scripts/run_real_world_test.py",
        "--query",
        "What factors indicate conflict escalation risk between China and Taiwan?",
        "--country",
        "CHN",
    ]
    run_result = run_cmd(pipeline_cmd, timeout=2400)

    trace_cmd = [
        sys.executable,
        "research_lab/telemetry/trace_session.py",
        "--query",
        "What factors indicate conflict escalation risk between China and Taiwan?",
        "--country",
        "CHN",
        "--output",
        str(RAW_TRACE_JSON),
    ]
    trace_result = run_cmd(trace_cmd, timeout=2400)

    if not RAW_TRACE_JSON.exists():
        payload = {
            "status": "failed",
            "reason": "raw trace file was not created",
            "pipeline_returncode": run_result.returncode,
            "trace_returncode": trace_result.returncode,
            "pipeline_stdout": run_result.stdout,
            "pipeline_stderr": run_result.stderr,
            "trace_stdout": trace_result.stdout,
            "trace_stderr": trace_result.stderr,
        }
        TRACE_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

    trace_data = json.loads(RAW_TRACE_JSON.read_text(encoding="utf-8"))
    events = trace_data.get("events", []) or []
    metadata = trace_data.get("metadata", {}) or {}
    execution_trace_meta = metadata.get("execution_trace", {}) if isinstance(metadata, dict) else {}
    artifact_meta = metadata.get("artifacts", {}) if isinstance(metadata, dict) else {}
    execution_trace_json_path = Path(str(execution_trace_meta.get("json_path", "") or ""))
    execution_trace_exists = execution_trace_json_path.exists() if execution_trace_json_path else False
    execution_trace_event_count = int(execution_trace_meta.get("event_count", 0) or 0)
    if execution_trace_exists:
        try:
            trace_payload = json.loads(execution_trace_json_path.read_text(encoding="utf-8"))
            execution_trace_event_count = int(trace_payload.get("event_count", execution_trace_event_count) or execution_trace_event_count)
        except Exception:
            pass

    output = {
        "status": "ok" if run_result.returncode == 0 and trace_result.returncode == 0 else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - started, 3),
        "pipeline_command": pipeline_cmd,
        "pipeline_returncode": run_result.returncode,
        "pipeline_stdout": run_result.stdout,
        "pipeline_stderr": run_result.stderr,
        "trace_command": trace_cmd,
        "trace_returncode": trace_result.returncode,
        "trace_stdout": trace_result.stdout,
        "trace_stderr": trace_result.stderr,
        "trace_file": str(RAW_TRACE_JSON),
        "trace_run_id": trace_data.get("run_id"),
        "session_ledger_file": str(artifact_meta.get("session_ledger_path", "")),
        "layer_timings": _layer_timings(events),
        "signals_detected": _extract_signals(events),
        "grounding_status": _extract_first(events, "GROUNDING_STATUS"),
        "grounding_result": _extract_first(events, "GROUNDING_RESULT"),
        "llm_calls": {
            "called": _extract_all(events, "LLM_CALLED"),
            "response": _extract_all(events, "LLM_RESPONSE"),
            "async_called": _extract_all(events, "LLM_ASYNC_CALLED"),
            "async_response": _extract_all(events, "LLM_ASYNC_RESPONSE"),
        },
        "verifier_results": {
            "grounding_start": _extract_first(events, "GROUNDING_START"),
            "grounding_result": _extract_first(events, "GROUNDING_RESULT"),
            "grounding_status": _extract_first(events, "GROUNDING_STATUS"),
        },
        "execution_trace": {
            "metadata": execution_trace_meta,
            "json_exists": bool(execution_trace_exists),
            "event_count": execution_trace_event_count,
        },
        "final_decision": _extract_first(events, "FINAL_DECISION"),
        "result_summary": (trace_data.get("metadata", {}) or {}).get("result_summary", {}),
    }

    TRACE_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"SHADOW_TRACE_WRITTEN: {TRACE_JSON}")
    return 0 if output["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
