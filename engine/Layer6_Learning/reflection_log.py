import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("diplomat.reflection_log")

try:
    from ind_diplomat.paths import RUNTIME_DIR
    REFLECTION_DIR = RUNTIME_DIR / "memory"
except ImportError:
    REFLECTION_DIR = Path.home() / ".ind_diplomat" / "memory"

MEMORY_FILE = REFLECTION_DIR / "assessment_memory.jsonl"

def _ensure_dir():
    os.makedirs(REFLECTION_DIR, exist_ok=True)

def append_reflection(country_code: str, query: str, decision: str, confidence: float, trace_id: str, feedback: str = "") -> None:
    """Appends an assessment outcome to the persistent memory log."""
    _ensure_dir()
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "country_code": country_code,
        "query": query,
        "decision": decision,
        "confidence": confidence,
        "trace_id": trace_id,
        "feedback": feedback
    }
    try:
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.debug(f"Saved reflection for trace {trace_id}")
    except Exception as e:
        logger.error(f"Failed to append to reflection log: {e}")

def get_recent_reflections(country_code: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve the most recent reflections for a given country."""
    if not MEMORY_FILE.exists():
        return []
    
    matches = []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("country_code") == country_code:
                        matches.append(data)
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"Failed to read reflection log: {e}")
        
    return matches[-limit:]

def format_reflections_for_prompt(country_code: str, limit: int = 3) -> str:
    """Format recent reflections into a string that can be injected into minister prompts."""
    reflections = get_recent_reflections(country_code, limit)
    if not reflections:
        return ""
        
    lines = ["\n[HISTORICAL REFLECTION MEMORY]"]
    lines.append("Review previous assessments for this region to avoid repeating past miscalculations:")
    for r in reflections:
        lines.append(f"- [{r.get('timestamp')[:10]}] Query: '{r.get('query')}' -> Decision: {r.get('decision')} (Conf: {r.get('confidence'):.2f})")
        if r.get('feedback'):
            lines.append(f"  Lesson learned: {r.get('feedback')}")
    lines.append("----------------------------\n")
    return "\n".join(lines)
