"""
Layer-2 time-aware document selection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple


def filter_documents_by_time(
    documents: Sequence[Dict],
    time_filter: Optional[Tuple[str, str]],
) -> List[Dict]:
    if not time_filter:
        return list(documents or [])
    start = _parse(time_filter[0])
    end = _parse(time_filter[1])
    result: List[Dict] = []
    for doc in documents or []:
        meta = doc.get("metadata", {}) or {}
        raw = str(meta.get("date") or meta.get("published_at") or "")
        dt = _parse(raw)
        if not dt:
            continue
        if start and dt < start:
            continue
        if end and dt > end:
            continue
        result.append(doc)
    return result


def _parse(text: str):
    raw = str(text or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw[:10], fmt)
        except ValueError:
            continue
    return None


__all__ = ["filter_documents_by_time"]

