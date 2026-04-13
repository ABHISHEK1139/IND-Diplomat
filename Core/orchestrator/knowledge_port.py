"""
Layer-3 Knowledge Port.

This module is Layer-3's single access point for Layer-2 knowledge services.
It keeps the rest of Layer-3 free from direct Layer-2 implementation imports.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from engine.Layer2_Knowledge.knowledge_api import (
    KnowledgeRequest,
    KnowledgeResponse,
    knowledge_api,
)


class KnowledgePort:
    """Thin adapter that enforces request/response contracts."""

    def __init__(self):
        self._api = knowledge_api

    def search_documents(
        self,
        query: str,
        indexes: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        time_filter: Optional[Tuple[str, str]] = None,
        top_k: int = 10,
    ) -> KnowledgeResponse:
        request = KnowledgeRequest(
            query=query,
            indexes=indexes or ["event"],
            filters=filters or {},
            time_filter=time_filter,
            top_k=top_k,
        )
        return self._api.search(request)

    def get_source_trust(self, source: str) -> float:
        return self._api.get_source_trust(source)

    def resolve_entity(self, text: str) -> Optional[str]:
        return self._api.resolve_entity(text)

    def extract_legal_signals(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._api.extract_legal_signals(documents)

    def extract_claims(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._api.extract_claims(documents)


knowledge_port = KnowledgePort()

__all__ = ["KnowledgePort", "knowledge_port"]
