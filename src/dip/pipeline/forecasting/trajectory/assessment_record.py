"""
Assessment Record — Immutable Audit Log
========================================

Records every gate verdict as an append-only JSONL entry for:
- Audit trail
- Calibration tracking
- Minister performance analysis
- Post-hoc review
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RECORDS_PATH = Path(__file__).resolve().parent.parent / "data" / "assessment_records.jsonl"


def record_assessment(
    session: Any,
    result: Dict[str, Any],
    gate_verdict: Any,
    trace_id: Optional[str] = None,
) -> None:
    """Append an assessment record to the audit log.

    Args:
        session: CouncilSession with hypotheses, conflicts, etc.
        result: Pipeline result dict
        gate_verdict: GateVerdict from assessment_gate.assess()
        trace_id: Optional trace ID override
    """
    RECORDS_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "trace_id": trace_id or result.get("trace_id", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": getattr(session, "query", ""),
        "gate_verdict": gate_verdict.to_dict() if hasattr(gate_verdict, "to_dict") else gate_verdict,
        "threat_level": result.get("threat_level"),
        "verification_score": result.get("verification_score", 0.0),
        "sre_score": (result.get("nextgen_sre") or {}).get("sre_escalation_score", 0.0),
        "hypotheses": [
            {
                "minister": getattr(h, "minister", getattr(h, "minister_name", getattr(h, "domain", ""))),
                "type": getattr(h, "hypothesis_type", getattr(h, "type", "")),
                "confidence": getattr(h, "confidence", 0.0),
            }
            for h in (getattr(session, "hypotheses", []) or [])
        ],
        "status": result.get("status", "UNKNOWN"),
        "elapsed_seconds": result.get("elapsed_seconds", 0.0),
    }

    with open(RECORDS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_records(limit: int = 100) -> List[Dict[str, Any]]:
    """Load recent assessment records."""
    if not RECORDS_PATH.exists():
        return []
    records: List[Dict[str, Any]] = []
    with open(RECORDS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records[-limit:]
