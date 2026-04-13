"""
Pre-war sequence detector.

Detects ordered escalation signal chains within a bounded time window.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


PREWAR_SEQUENCE = [
    "SIG_DIP_HOSTILE_RHETORIC",
    "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_DECEPTION_ACTIVITY",
    "SIG_FORCE_POSTURE",
    "SIG_LOGISTICS_PREP",
    "SIG_MIL_MOBILIZATION",
]
WINDOW_DAYS = 90


def _parse_time(value: Any) -> Optional[datetime]:
    token = str(value or "").strip()
    if not token:
        return None
    try:
        # Support timestamps ending with "Z"
        return datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize_signals(value: Any) -> List[str]:
    if not isinstance(value, (list, set, tuple)):
        return []
    out: List[str] = []
    seen = set()
    for token in list(value):
        label = str(token or "").strip().upper()
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
    return out


def detect_prewar_pattern(history: Iterable[Dict[str, Any]], window_days: int = WINDOW_DAYS) -> bool:
    rows: List[Dict[str, Any]] = [row for row in list(history or []) if isinstance(row, dict)]
    if not rows:
        return False

    # Ensure deterministic time order.
    rows.sort(key=lambda r: str(r.get("time", "")))

    matched_index = 0
    first_date: Optional[datetime] = None
    max_window = max(1, int(window_days or WINDOW_DAYS))

    for row in rows:
        ts = _parse_time(row.get("time"))
        if ts is None:
            continue
        signals = set(_normalize_signals(row.get("signals", [])))
        if not signals:
            continue

        expected = PREWAR_SEQUENCE[matched_index]
        if expected not in signals:
            continue

        if matched_index == 0:
            first_date = ts
        elif first_date is not None and (ts - first_date).days > max_window:
            # Window expired; restart match from current row if sequence begins here.
            matched_index = 0
            first_date = None
            if PREWAR_SEQUENCE[0] in signals:
                matched_index = 1
                first_date = ts
            continue

        matched_index += 1
        if matched_index >= len(PREWAR_SEQUENCE):
            return True

    return False


__all__ = ["PREWAR_SEQUENCE", "WINDOW_DAYS", "detect_prewar_pattern"]

