"""
Pipeline Step Tracer — Records input/output of every pipeline step.
Each step writes: {step_name, timestamp, input_summary, output_summary, source_file}
Stored in: data/traces/<trace_id>/
"""

from __future__ import annotations

import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

TRACES_DIR = Path(__file__).resolve().parent.parent / "data" / "traces"


class StepTracer:
    """Records every pipeline step with input and output."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.dir = TRACES_DIR / trace_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.steps: list[dict] = []
        self._start_time = time.time()

    def record(self, step_name: str, source_file: str, input_data: Any = None,
               output_data: Any = None, metadata: dict = None) -> str:
        """Record a pipeline step."""
        step = {
            "step": step_name,
            "source_file": source_file,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_from_start": round(time.time() - self._start_time, 3),
            "input_summary": self._summarize(input_data),
            "output_summary": self._summarize(output_data),
            "metadata": metadata or {},
        }
        self.steps.append(step)

        # Save individual step
        step_file = self.dir / f"{len(self.steps):04d}_{step_name}.json"
        full = {
            **step,
            "input_full": self._safe_serialize(input_data),
            "output_full": self._safe_serialize(output_data),
        }
        with open(step_file, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2, default=str, ensure_ascii=False)

        return str(step_file)

    def finalize(self, result: dict = None):
        """Write the complete trace summary."""
        summary = {
            "trace_id": self.trace_id,
            "total_steps": len(self.steps),
            "total_elapsed": round(time.time() - self._start_time, 3),
            "steps": [{k: v for k, v in s.items() if k != "input_full"}
                      for s in self.steps],
        }
        with open(self.dir / "trace_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str, ensure_ascii=False)

        # Also write steps index
        index = [f"{s['step']} ← {s['source_file']}" for s in self.steps]
        with open(self.dir / "steps_index.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(index))

    def _summarize(self, data: Any) -> str:
        if data is None:
            return "None"
        if isinstance(data, dict):
            keys = list(data.keys())[:8]
            return f"dict({len(data)} keys): {keys}"
        if isinstance(data, list):
            return f"list({len(data)} items)"
        if isinstance(data, str):
            return data[:100] + ("..." if len(data) > 100 else "")
        return str(type(data).__name__)

    def _safe_serialize(self, data: Any) -> Any:
        try:
            if hasattr(data, 'model_dump'):
                return data.model_dump(mode='json')
            if hasattr(data, 'dict'):
                return data.dict()
            if isinstance(data, (dict, list, str, int, float, bool, type(None))):
                return data
            return str(data)
        except Exception:
            return str(type(data).__name__)


# Global tracer
_tracer: Optional[StepTracer] = None


def start_trace(trace_id: str) -> StepTracer:
    global _tracer
    _tracer = StepTracer(trace_id)
    return _tracer


def get_tracer() -> Optional[StepTracer]:
    return _tracer


def trace_step(step_name: str, source_file: str, input_data: Any = None,
               output_data: Any = None, metadata: dict = None):
    """Convenience: record a step if tracer is active."""
    t = get_tracer()
    if t:
        t.record(step_name, source_file, input_data, output_data, metadata)
