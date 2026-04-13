"""
Trend Store — reads historical escalation data from:
  1. runtime/monitor_log.jsonl  (continuous monitor output)
  2. Layer3 temporal memory snapshots

Returns TrendPoint lists for Chart.js visualization.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from .models import TrendPoint

_ROOT = Path(__file__).resolve().parent.parent
MONITOR_LOG = _ROOT / "runtime" / "monitor_log.jsonl"
ALERTS_DIR = _ROOT / "runtime" / "alerts"


def get_trends(country_code: str, hours_back: float = 72) -> List[TrendPoint]:
    """
    Read trend data from the continuous monitor log.
    Returns a list of TrendPoint sorted by timestamp (oldest first).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    points: List[TrendPoint] = []

    if not MONITOR_LOG.exists():
        return points

    try:
        with open(MONITOR_LOG, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    cycle = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Parse timestamp
                ts_str = cycle.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                except Exception:
                    continue

                # Extract per-country escalation data
                escalation = cycle.get("escalation", {})
                cc_upper = country_code.upper()

                if cc_upper in escalation:
                    data = escalation[cc_upper]
                    domains = data.get("domains", {})
                    points.append(TrendPoint(
                        timestamp=ts_str,
                        country=cc_upper,
                        escalation_score=data.get("escalation_score", 0.0),
                        risk_level=data.get("risk_level", ""),
                        domains={
                            "capability": domains.get("capability", 0.0),
                            "intent": domains.get("intent", 0.0),
                            "stability": domains.get("stability", 0.0),
                            "cost": domains.get("cost", 0.0),
                        },
                    ))
    except Exception:
        pass

    # Sort by timestamp
    points.sort(key=lambda p: p.timestamp)
    return points


def get_latest_alert(country_code: str) -> dict | None:
    """Read the latest alert JSON for a country from runtime/alerts/."""
    if not ALERTS_DIR.exists():
        return None

    cc_upper = country_code.upper()
    latest: dict | None = None
    latest_ts = ""

    try:
        for fp in ALERTS_DIR.glob(f"{cc_upper}_*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
                ts = data.get("timestamp", "")
                if ts > latest_ts:
                    latest_ts = ts
                    latest = data
            except Exception:
                continue
    except Exception:
        pass

    return latest
