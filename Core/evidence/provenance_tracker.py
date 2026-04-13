"""
Signal-level provenance tracking.

Maintains a direct mapping:
signal token -> supporting evidence records.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, DefaultDict, Dict, Iterable, List, Optional

try:
    from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token as _canonicalize
except ImportError:  # guard against circular / early-load issues
    _canonicalize = None  # type: ignore[assignment]


@dataclass
class Evidence:
    source: str
    url: str
    date: str
    excerpt: str
    reliability: float
    source_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "source_id": str(self.source_id or ""),
            "source": str(self.source or "unknown"),
            "source_name": str(self.source or "unknown"),
            "url": str(self.url or ""),
            "date": str(self.date or ""),
            "publication_date": str(self.date or ""),
            "excerpt": str(self.excerpt or ""),
            "reliability": max(0.0, min(1.0, float(self.reliability or 0.0))),
            "confidence": max(0.0, min(1.0, float(self.reliability or 0.0))),
        }
        return payload

    @property
    def source_name(self) -> str:
        return str(self.source or "")

    @property
    def publication_date(self) -> str:
        return str(self.date or "")

    @property
    def confidence(self) -> float:
        try:
            return max(0.0, min(1.0, float(self.reliability or 0.0)))
        except Exception:
            return 0.0

    @classmethod
    def from_any(cls, value: Any) -> "Evidence":
        if isinstance(value, Evidence):
            return value
        data = dict(value or {}) if isinstance(value, dict) else {}
        source = (
            data.get("source")
            or data.get("source_name")
            or "unknown"
        )
        date = (
            data.get("date")
            or data.get("publication_date")
            or ""
        )
        reliability = data.get("reliability", data.get("confidence", 0.0))
        return cls(
            source_id=str(data.get("source_id", "")),
            source=str(source),
            url=str(data.get("url", "")),
            date=str(date),
            excerpt=str(data.get("excerpt", "")),
            reliability=float(reliability or 0.0),
        )


class ProvenanceTracker:
    def __init__(self):
        self.signal_map: DefaultDict[str, List[Evidence]] = defaultdict(list)
        # Backward compatibility: older modules reference `signal_sources`.
        self.signal_sources = self.signal_map

    @staticmethod
    def _normalize_signal(signal: Any) -> str:
        """Delegate to the authoritative signal ontology normaliser."""
        if _canonicalize is not None:
            canon = _canonicalize(str(signal or ""))
            if canon:
                return canon
        return str(signal or "").strip().upper().replace("-", "_").replace(" ", "_")

    def attach(self, signal: Any, evidence: Evidence) -> None:
        token = self._normalize_signal(signal)
        if not token:
            return
        item = Evidence.from_any(evidence)
        self.signal_map[token].append(item)

    def extend(self, signal: Any, evidences: Iterable[Evidence]) -> None:
        for item in list(evidences or []):
            self.attach(signal, item)

    def get(self, signal: Any) -> List[Evidence]:
        token = self._normalize_signal(signal)
        return list(self.signal_map.get(token, []))

    def get_sources(self, signal: Any) -> List[Evidence]:
        return self.get(signal)

    def as_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        payload: Dict[str, List[Dict[str, Any]]] = {}
        for token, items in list(self.signal_map.items()):
            payload[token] = [Evidence.from_any(item).to_dict() for item in list(items or [])]
        return payload

    def export(self) -> Dict[str, List[Evidence]]:
        return {token: list(items or []) for token, items in list(self.signal_map.items())}

    def collect_unique_sources(self, signals: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
        selected_tokens = None
        if signals is not None:
            selected_tokens = {
                self._normalize_signal(item)
                for item in list(signals or [])
                if self._normalize_signal(item)
            }

        seen = set()
        refs: List[Dict[str, Any]] = []
        for token, items in list(self.signal_map.items()):
            if selected_tokens is not None and token not in selected_tokens:
                continue
            for item in list(items or []):
                evidence = Evidence.from_any(item).to_dict()
                key = (
                    evidence.get("source_id", ""),
                    evidence.get("url", ""),
                    evidence.get("publication_date", ""),
                    evidence.get("excerpt", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                refs.append(evidence)
        return refs

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceTracker":
        tracker = cls()
        payload = dict(data or {}) if isinstance(data, dict) else {}
        for signal, rows in list(payload.items()):
            if not isinstance(rows, list):
                continue
            for row in rows:
                tracker.attach(signal, Evidence.from_any(row))
        return tracker
