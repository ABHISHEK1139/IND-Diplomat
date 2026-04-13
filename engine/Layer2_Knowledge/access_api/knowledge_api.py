"""
Layer-2 Knowledge API.

Layer-3 should request evidence through this API contract instead of importing
Layer-2 implementation details (vector store, index manager, registry internals).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from engine.Layer2_Knowledge.multi_index import KnowledgeSpace, multi_index_manager
from engine.Layer2_Knowledge.entity_registry import entity_registry
from engine.Layer2_Knowledge.source_registry import source_registry
from engine.Layer2_Knowledge.claim_extractor import claim_extractor
from engine.Layer2_Knowledge.retrieval.time_selector import filter_documents_by_time
from engine.Layer2_Knowledge.legal_signal_extractor import (
    legal_signal_extractor,
    precedence_engine,
)
from schemas.claim_schema import ClaimRecord


@dataclass
class KnowledgeRequest:
    """Structured request from Layer-3 to Layer-2."""

    query: str
    indexes: List[str] = field(default_factory=lambda: ["event"])
    filters: Dict[str, Any] = field(default_factory=dict)
    time_filter: Optional[Tuple[str, str]] = None
    top_k: int = 10


@dataclass
class KnowledgeResponse:
    """Structured response from Layer-2 to Layer-3."""

    documents: List[Dict[str, Any]]
    source: str = "layer2_knowledge_api"
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeAPI:
    """
    Layer-2 facade for evidence access and source trust lookup.
    """

    def __init__(self):
        self._manager = multi_index_manager

    def search(self, request: KnowledgeRequest) -> KnowledgeResponse:
        self._manager.initialize()

        spaces = self._normalize_spaces(request.indexes)
        docs = self._manager.search(
            query=request.query,
            spaces=spaces,
            top_k=max(1, int(request.top_k)),
            time_filter=request.time_filter,
            filters=request.filters,
        )
        timed_docs = filter_documents_by_time(docs, request.time_filter)
        filtered_docs = self._apply_metadata_filters(timed_docs, request.filters)

        return KnowledgeResponse(
            documents=filtered_docs,
            metadata={
                "requested_indexes": request.indexes,
                "resolved_spaces": [space.value for space in spaces],
                "result_count": len(filtered_docs),
            },
        )

    def get_source_trust(self, source: str) -> float:
        return source_registry.get_trust(source or "unknown")

    def resolve_entity(self, text: str) -> Optional[str]:
        if not text:
            return None
        return entity_registry.resolve(text)

    def extract_legal_signals(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        signals = legal_signal_extractor.extract_from_documents(documents)
        resolved = precedence_engine.resolve_conflicts(signals)
        return {
            "signal_count": len(signals),
            "signals": [signal.to_dict() for signal in signals],
            "precedence": resolved,
        }

    def extract_claims(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        claims = claim_extractor.extract_batch(documents)
        validated: List[Dict[str, Any]] = []
        for claim in claims:
            try:
                model = ClaimRecord.model_validate(claim)
            except Exception:
                continue
            validated.append(model.model_dump())
        return validated

    def _normalize_spaces(self, indexes: List[str]) -> List[KnowledgeSpace]:
        if not indexes:
            return [KnowledgeSpace.EVENT]

        resolved: List[KnowledgeSpace] = []
        for idx in indexes:
            text = (idx or "").strip().lower()
            try:
                resolved.append(KnowledgeSpace(text))
            except ValueError:
                # Unknown index names are ignored; fallback below handles empty.
                continue

        return resolved or [KnowledgeSpace.EVENT]

    def _apply_metadata_filters(
        self,
        docs: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not filters:
            return docs

        result: List[Dict[str, Any]] = []
        for doc in docs:
            meta = doc.get("metadata", {}) or {}
            keep = True

            for key, expected in filters.items():
                if key == "entities":
                    entities = meta.get("entities", [])
                    if expected and isinstance(expected, list):
                        exp_set = {str(v).upper() for v in expected}
                        seen = {str(v).upper() for v in entities}
                        if not exp_set.intersection(seen):
                            keep = False
                            break
                    continue

                actual = meta.get(key)
                if expected is not None and actual != expected:
                    keep = False
                    break

            if keep:
                result.append(doc)

        return result


knowledge_api = KnowledgeAPI()

__all__ = [
    "KnowledgeRequest",
    "KnowledgeResponse",
    "KnowledgeAPI",
    "knowledge_api",
]
