"""
Rolling state history persistence for temporal trend analysis.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from Config.runtime_clock import RuntimeClock

HISTORY_DIR = Path("runtime/state_history")
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
MAX_HISTORY_ROWS = 30


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value, 0.0)))


def _record_from_state(state_context: Any) -> Dict[str, Any]:
    capability = _clip01(getattr(state_context, "capability_index", 0.0))
    intent = _clip01(getattr(state_context, "intent_index", 0.0))
    stability = _clip01(getattr(state_context, "stability_index", 0.0))
    conflict = _clip01(
        getattr(
            state_context,
            "net_escalation",
            max(capability, intent, stability),
        )
    )
    observed = getattr(state_context, "observed_signals", set()) or set()
    signals: List[str] = []
    for token in list(observed):
        label = str(token or "").strip().upper()
        if label and label not in signals:
            signals.append(label)

    # Include signal confidence values when available
    sig_conf_raw = getattr(state_context, "signal_confidence", {}) or {}
    signal_confidence = {}
    for k, v in sig_conf_raw.items():
        try:
            fv = float(v)
            if fv > 0:
                signal_confidence[str(k)] = round(fv, 4)
        except (TypeError, ValueError):
            pass

    record: Dict[str, Any] = {
        "time": RuntimeClock.now(timezone.utc).isoformat(),
        "capability": capability,
        "intent": intent,
        "stability": stability,
        "conflict": conflict,
        "signals": sorted(signals),
    }
    if signal_confidence:
        record["signal_confidence"] = signal_confidence
    return record


def _history_path(country_code: str) -> Path:
    token = str(country_code or "UNKNOWN").strip().upper() or "UNKNOWN"
    return HISTORY_DIR / f"{token}.json"


def load_state_history(country_code: str) -> List[Dict[str, Any]]:
    path = _history_path(country_code)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    rows: List[Dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        row: Dict[str, Any] = {
            "time": str(item.get("time", "")),
            "capability": _clip01(item.get("capability", 0.0)),
            "intent": _clip01(item.get("intent", 0.0)),
            "stability": _clip01(item.get("stability", 0.0)),
            "conflict": _clip01(item.get("conflict", 0.0)),
            "signals": sorted(
                {
                    str(token or "").strip().upper()
                    for token in list(item.get("signals", []) or [])
                    if str(token or "").strip()
                }
            ),
        }
        # Preserve signal_confidence when present (written by World Monitor)
        sc = item.get("signal_confidence")
        if isinstance(sc, dict) and sc:
            row["signal_confidence"] = sc
        # Preserve observation_count / sensor_coverage / source tag
        for extra_key in ("observation_count", "sensor_coverage", "source"):
            if extra_key in item:
                row[extra_key] = item[extra_key]
        rows.append(row)
    return rows[-MAX_HISTORY_ROWS:]


def save_state(country_code: str, state_context: Any) -> Dict[str, Any]:
    """
    Persist a single state snapshot into per-country rolling history.
    """
    path = _history_path(country_code)
    history = load_state_history(country_code)
    record = _record_from_state(state_context)
    history.append(record)
    history = history[-MAX_HISTORY_ROWS:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return record


__all__ = ["save_state", "load_state_history"]
