"""
Knowledge Layer Combined — API, Ingestion, Mapping, Extraction
===============================================================

Port of DIP_8 engine/Layer2_Knowledge/* modules into unified interface.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer2_Knowledge")


class KnowledgeAPI:
    """Public API for knowledge layer queries."""
    
    def __init__(self):
        self._sources: Dict[str, Dict[str, Any]] = {}
    
    def register_source(self, source_id: str, source_type: str, reliability: float = 0.5) -> None:
        self._sources[source_id] = {"type": source_type, "reliability": reliability, "observations": 0}
    
    def get_source_info(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self._sources.get(source_id)


class CAMEOMapper:
    """Maps events to CAMEO conflict ontology codes."""
    
    CAMEO_MAP = {
        "troop_movement": "18", "military_deployment": "18", "mobilization": "18",
        "sanctions": "16", "trade_restriction": "16", "economic_pressure": "16",
        "diplomatic_visit": "04", "negotiation": "04", "summit": "04",
        "condemnation": "11", "expel_diplomats": "11", "threat": "11",
        "protest": "14", "riot": "14", "unrest": "14",
        "cyber_attack": "19", "missile_test": "18",
    }
    
    def map_action(self, action: str) -> str:
        action_lower = action.lower().replace("sig_", "")
        for key, code in self.CAMEO_MAP.items():
            if key in action_lower:
                return code
        return "00"


class ClaimExtractor:
    """Extracts atomic claims from text using keyword + pattern matching."""
    
    PATTERNS = {
        "deployment": ["deploy", "mobilize", "move troops", "reinforce"],
        "accusation": ["accuse", "allege", "claim", "blame"],
        "threat": ["threaten", "warn", "ultimatum"],
        "agreement": ["agree", "sign", "treaty", "accord"],
        "violation": ["violate", "breach", "break agreement"],
    }
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        claims = []
        text_lower = text.lower()
        for claim_type, keywords in self.PATTERNS.items():
            for kw in keywords:
                if kw in text_lower:
                    claims.append({
                        "type": claim_type,
                        "keyword": kw,
                        "confidence": 0.6 + (0.1 * len([k for k in keywords if k in text_lower])),
                    })
        return claims[:10]


class EngramStore:
    """Persistent memory store for knowledge."""
    
    def __init__(self):
        self._engrams: Dict[str, Dict[str, Any]] = {}
    
    def store(self, key: str, data: Dict[str, Any]) -> None:
        self._engrams[key] = data
    
    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        return self._engrams.get(key)
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        return [v for k, v in self._engrams.items() if q in str(v).lower()]


class SourceRegistry:
    """Tracks and evaluates data sources over time."""
    
    def __init__(self):
        self._sources: Dict[str, Dict[str, Any]] = {}
    
    def register(self, source_id: str, source_type: str) -> None:
        self._sources[source_id] = {
            "type": source_type,
            "observations": 0,
            "verified": 0,
            "contradicted": 0,
        }
    
    def record_observation(self, source_id: str, verified: bool) -> None:
        if source_id in self._sources:
            self._sources[source_id]["observations"] += 1
            if verified:
                self._sources[source_id]["verified"] += 1
            else:
                self._sources[source_id]["contradicted"] += 1
    
    def get_reliability(self, source_id: str) -> float:
        s = self._sources.get(source_id, {})
        total = s.get("observations", 0)
        if total == 0:
            return 0.5
        return s.get("verified", 0) / total


class TreatyLifecycle:
    """Tracks treaty lifecycle: signature, ratification, entry into force, termination."""
    
    STAGES = ["negotiation", "signature", "ratification", "entry_into_force", "amendment", "withdrawal", "termination"]
    
    def __init__(self):
        self._treaties: Dict[str, Dict[str, Any]] = {}
    
    def register_treaty(self, name: str, stage: str = "entry_into_force") -> None:
        self._treaties[name] = {"name": name, "stage": stage, "history": []}
    
    def update_stage(self, name: str, new_stage: str) -> None:
        if name in self._treaties:
            old = self._treaties[name]["stage"]
            self._treaties[name]["stage"] = new_stage
            self._treaties[name]["history"].append({"from": old, "to": new_stage})


# Module-level singletons
knowledge_api = KnowledgeAPI()
cameo_mapper = CAMEOMapper()
claim_extractor = ClaimExtractor()
engram_store = EngramStore()
source_registry = SourceRegistry()
treaty_lifecycle = TreatyLifecycle()
